# #135 Seam B: Worker Versioning (V1, local) and reuse across requests and profiles (V3)

`run.py` runs one corpus paper through builds of Worker Deployment `canonicalization` on the
local stack: Temporal CLI 1.9.1 dev server (Server 1.32.0), temporalio 1.34.0, the RustFS S3
stand-in, `tools/fake_admission`, and one `kp-canonicalization worker --build-id <build>`
process per task queue. Every request goes through `kp-canonicalization start-request --builds
MAP`, the stand-in for #95's dispatcher. No request leaves the machine: the VLM stand-in replays
the gpt-6-luna recordings, the summary stand-in is the DEV fake, and the d3 stand-in answers
every question with 0.99.

Profiles are the DEV profile under two ids. `A` is `paper-pdf@1` without `d3-check@1`. `B` is
`paper-pdf@2`, which adds `d3-check@1`, as the rehearsal of adding a method. The dev server
refreshes drainage every 2 s and forgets pollers after 5 s; the defaults are minutes.

`cli/` keeps the output of every temporal CLI step, and `evidence.json` keeps the checks. The
paper is third-party and stays out of git.

## Results

Run 2026-11-08 on corpus paper 8 (12 pages, third-party). Every step passed; raw numbers in
[evidence.json](evidence.json), CLI output in [cli/](cli/).

| Step | What ran | Result |
|---|---|---|
| 1 | `start-request --builds` pinned to `paper-pdf-1-r1` before that build existed; then its four workers started; `set-current-version` | Refused: `Pinned version 'canonicalization:paper-pdf-1-r1' is not present in task queue 'orchestration' of type 'Workflow'` ([01](cli/01-describe-version-paper-pdf-1-r1.txt) lists the four queues once the workers polled; [02](cli/02-set-current-1-r1.txt)) |
| 2 | R1 pinned to `1-r1` | Complete in 8.5 s; 3 VLM and 31 summary requests; 21 enrichments, 17 item folders registered; every Activity on `1-r1`; `workflow describe` shows the pinned override ([04](cli/04-describe-req_ef6993_r1.txt)) |
| 3 | R2, a resubmission under a new Source Revision; R3, an operator redrive | V3: 0.7 s and 1.2 s; no inference request, no fresh Activity, 21 of 21 enrichments `reused`, nothing added under `documents/` |
| 4 | `1-r2` started beside `1-r1`, which stays current; R4 (map → `1-r2`) and R5 (old map → `1-r1`) at once | Each ran every Activity on its own build (1.1 s, 1.2 s); both reused everything; [10](cli/10-describe-deployment-2.txt) still names `1-r1` current |
| 5 | current → `1-r2`; `1-r1`'s inference worker stopped; R6 pinned to `1-r1` | R6 stayed open: visibility counted 1 ([12](cli/12-count-open-1-r1-while-r6.txt)) and the version read `draining` ([13](cli/13-describe-version-1-r1-while-r6.txt)); its parse waited for `1-r1` instead of running on the current build. Worker back: R6 complete on `1-r1` (10.0 s, of which 8 s waiting), every Activity on `1-r1`; count 0, `drained`. `delete-version` refused three times, `cannot be deleted since it has active pollers` ([17](cli/17-delete-version-1-r1.txt)), then succeeded about 6 s after the workers stopped ([18](cli/18-delete-version-1-r1.txt)) |
| 6 | `2-r1` (profile B) started; a map sending `paper-pdf@1` to it; R7 | Failure report: `platform`, category `integrity`, `ADOPTED_VERSION_MISMATCH`; no request, nothing registered; the Activities that ran were on `2-r1` |
| 7 | R8, `adopted_version: paper-pdf@2`, map → `2-r1` | Complete in 0.9 s: 7 d3 requests, one per check item (formulas, tables and picture OCR with a `success` outcome); no VLM or summary request; fresh Activities `check` and `inventory` only; 21 of 21 enrichments `reused`; 8 item folders added, the 7 checks and the rebuilt inventory; the result's profile section names `paper-pdf@2` and `d3-check@1` with its module digest; `set-current-version 2-r1` ([24](cli/24-describe-deployment-4.txt)) |

Step 7 is the Q13 rehearsal: a method added in a new profile version costs that method's
requests plus an inventory, nothing else.

## SDK and server behaviour (for #78 and #137)

Measured on Server 1.32.0 and temporalio 1.34.0, in `run.py` and in probes of the same server:

1. **No server switch.** Worker Deployments work on the dev server without dynamic config.
2. **Worker side.** Each worker passes `deployment_config=WorkerDeploymentConfig(version,
   use_worker_versioning=True, default_versioning_behavior=PINNED)`. The SDK docstring still
   marks `deployment_config` as experimental, so only `make_worker` touches it.
3. **Names.** Build IDs with `-`, `@`, `.` and `/` are accepted. A deployment name may not
   contain `.`, because the SDK splits `<deployment>.<build>` at the first `.`. Builds are
   named `paper-pdf-<N>-r<patch>`, without `@`, so that a build ID also fits a Kubernetes
   label value.
4. **Two spellings of a version.** The SDK and `workflow describe` write
   `canonicalization.paper-pdf-1-r1`. Server errors and the visibility attribute
   `TemporalWorkerDeploymentVersion` use `canonicalization:paper-pdf-1-r1`. A visibility query
   with the `.` form matches nothing and raises no error, and `workflow count` prints `{}` for
   zero.
5. **A build is routable only after its workers poll.** A start pinned to a build whose
   workers have not polled yet is refused with `Pinned version 'canonicalization:<build>' is
   not present in task queue '<queue>' of type 'Workflow'`. The dispatcher map may name a
   build only after `describe-version` lists every queue of the profile.
6. **Activities follow the pinned build** on every queue the build's workers have polled, and
   the membership outlives the workers: in step 5, with `1-r1`'s inference worker down for
   8 s (longer than the 5 s poller history), R6's parse waited for `1-r1` instead of running
   on the current build. By the documentation, an Activity on a queue the build has never
   polled is an Independent Activity and runs on that queue's current version, so each build
   starts workers for every queue its profile uses before the map names it.
7. **Drainage counts override-started workflows.** A workflow started on a non-current build
   through a pinned override kept that build `draining` until the workflow ended.
8. **Deleting a version** (`delete-version`, no `--yes` flag) is refused while the version is
   current, draining, or has recent pollers. The poller window is `matching.PollerHistoryTTL`,
   5 minutes by default ([constants.go](https://github.com/temporalio/temporal/blob/main/common/dynamicconfig/constants.go));
   this run set it to 5 s and the delete went through about 6 s after the workers stopped.
   Drainage is refreshed every `matching.wv.VersionDrainageStatusRefreshInterval` (default
   3 minutes) and lags visibility by `matching.wv.VersionDrainageStatusVisibilityGracePeriod`
   (default 3 minutes); both were 2 s here.

## Differences from the design (#129 "部署身分")

| #129 says | Found | Done |
|---|---|---|
| One Worker Deployment `paper-pdf` | Queues are shared across pipelines, and Temporal keeps the current version per task queue | One deployment named after the layer's work, `canonicalization`, like the namespace `knowledge-canonicalization-<env>` |
| Build ID `<profile number>-r<patch>` | One deployment serves every pipeline | `paper-pdf-<N>-r<patch>` |
| Drainage does not count workflows started through an override, so check visibility before retiring | On 1.32.0 drainage counts them (item 7) | Retirement still checks the visibility count; it does not depend on the server's drainage rule |
| A patch build changes only shared code, logging and `runtime` | Once a method version moves on `dev`, `dev` can no longer load the older profile | A patch to an older profile's build starts from that build's release commit (`profiles/README.md`) |

The procedure for adding or changing a method, from code to retirement, is
[`src/kp_canonicalization/profiles/README.md`](../../../../src/kp_canonicalization/profiles/README.md).
