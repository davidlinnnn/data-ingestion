# #135 Seam B: reuse across requests and Processing Profile versions (V3), and a version's life under Worker Versioning (V1, local)

`run.py` runs one corpus paper through the upgrade flow of
[`profiles/README.md`](../../../../src/kp_canonicalization/profiles/README.md) on the local stack:
Temporal CLI 1.9.1 dev server (Server 1.32.0), temporalio 1.34.0, the RustFS S3 stand-in,
`tools/fake_admission`, and five `kp-canonicalization worker` processes per build, one per task
queue. A worker takes its Worker Deployment and build ID from `TEMPORAL_DEPLOYMENT_NAME` and
`TEMPORAL_WORKER_BUILD_ID`, as the chart will inject them. Every request goes through
`kp-canonicalization start-request`, which calls admission's own start. The Temporal side is
changed only by `kp-canonicalization promote`, the promoter CronJob's command, over a values file
the run rewrites the way a deployment values PR would. No request leaves the machine: the VLM
stand-in replays the gpt-6-luna recordings, the summary stand-in is the DEV fake, and the d3
stand-in answers every question with 0.99.

`paper-pdf@1` is the DEV Processing Profile. `paper-pdf@2` is the same with
`picture-interpretation@2`, served from a second tree: a copy of `src/kp_canonicalization` whose
`picture_interpretation` package says `VERSION = 2`. One tree loads one version, as one image
does. The dev server refreshes drainage every 2 s and forgets pollers after 5 s; the defaults are
minutes.

`cli/` keeps the output of every temporal CLI and promoter step, and `evidence.json` keeps the
checks. The paper is third-party and stays out of git.

## Results

Run 2026-11-11 (`85de0e`) on corpus paper 7 (18 pages, third-party), which yields an enrichment of
every kind; step 2 checks that, so a kind the paper lacks cannot pass as reused. Every step passed;
raw numbers in [evidence.json](evidence.json), CLI output in [cli/](cli/). Durations are the
workflow's, from the server's start and close times. Builds are named `paper-pdf-<N>-r<n>` here;
the image tag format is #137's.

| Step | What ran | Result |
|---|---|---|
| 1 | R1 started before any worker of `paper-pdf-1` existed; a worker of this tree started with `TEMPORAL_DEPLOYMENT_NAME=paper-pdf-2`; then `1-r1`'s workers on four queues, then the fifth; the promoter after each | The start was accepted and R1 waited: 1 open workflow on `paper-pdf-1.orchestration` ([04](cli/04-count-open-before-current.txt)). The mislisted worker exited 2 naming both versions. With four queues polled the promoter exited 0 and left the deployment without a current version ([03](cli/03-promote-four-queues.txt)); with five it made `1-r1` current ([06](cli/06-promote-five-queues.txt), [07](cli/07-describe-version-1-r1.txt)) |
| 2 | R1 runs | Complete in 19.5 s, the wait included; 8 VLM, 29 summary and 9 d3 requests; 38 enrichments of all six kinds (picture OCR, picture interpretation, formula, code, table status, summary), 35 item folders registered; every Activity on `1-r1`; `workflow describe` shows `VERSIONING_BEHAVIOR_PINNED` to `paper-pdf-1` / `1-r1` and no override ([08](cli/08-describe-req_85de0e_r1.txt)) |
| 3 | R2, a resubmission under a new Source Revision; R3, an operator redrive | V3: 0.6 s and 1.2 s; no inference request, no fresh Activity, 38 of 38 enrichments `reused`, nothing added under `documents/` |
| 4 | Patch. `1-r2` started and listed beside `1-r1`; R4 started on the current `1-r1` with that build's inference worker stopped; `current: 1-r2`; R5; `1-r1`'s tag taken off the values while R4 was open, then put back; the worker restarted; the tag taken off again, pods still up, then stopped | The promoter switched in one run (0.9 s). R5 ran on `1-r2` in 1.0 s and closed 8.4 s before R4, which stayed on `1-r1` for 10.8 s and ran every Activity there: its parse waited for `1-r1` instead of running on the current build. Both reused everything. `1-r1` read `draining` ([16](cli/16-describe-deployment-while-r4.txt)). Tag off early: the promoter exited 1 with `1 open workflows are pinned to a build that is off the deployment values` and changed nothing ([17](cli/17-promote-1-r1-tag-off-early.txt)); tag back: exit 0. After R4, `drained` ([20](cli/20-describe-deployment-1-r1-drained.txt)). Tag off with pods up: delete refused for active pollers, exit 0 ([21](cli/21-promote-1-r1-tag-off-pods-up.txt)); pods stopped: the version was deleted on the sixth run, 7.5 s later ([23](cli/23-promote-1-r1-deleted.txt)) |
| 5 | Upgrade. `2-r1` from the second tree started and listed as `paper-pdf-2`; R6, the platform refresh with `adopted_version: paper-pdf@2` | The promoter made `2-r1` current on its second run (2.8 s); `paper-pdf-1` kept `1-r2`. R6 complete in 0.7 s on `paper-pdf-2.orchestration`, Pinned to `2-r1`: 6 VLM requests, one per picture, all `picture-interpretation@2`; no summary and no d3 request; fresh Activities `enrich_vlm` and `inventory` only (no parse); 24 of 38 enrichments fresh, the four fields of the six pictures, the other 14 `reused`; 7 item folders added, the six interpretations and the rebuilt inventory; the result's profile section names `paper-pdf@2` and `picture-interpretation@2` with a new module digest, every other method with the digest R1 recorded |
| 6 | R7, a resubmission under `paper-pdf@2` | 1.1 s; no inference request; no fresh Activity; 38 of 38 enrichments `reused`; nothing added |
| 7 | Retirement. `paper-pdf-1` taken off the values with its pods up, then the pods stopped; R8 under `paper-pdf@2` | 0 open workflows on `paper-pdf-1.orchestration` ([28](cli/28-count-open-paper-pdf-1.txt)). First run: set unversioned, delete refused while `draining`, exit 0 ([30](cli/30-promote-retire-pods-up.txt)). Next run, pods gone: version deleted, Worker Deployment deleted ([31](cli/31-promote-retired.txt)); `describe` answers `no Worker Deployment found` ([32](cli/32-describe-deployment-1-after-retirement.txt)). `paper-pdf-2` untouched; R8 reused everything in 0.7 s |
| 8 | A worker joining with each candidate name | Build IDs `a-1`, `a@1`, `a.1` and `a/1` listed ([34](cli/34-describe-version-name-1.txt) to [37](cli/37-describe-version-name-4.txt)); deployment `names.probe` not found ([38](cli/38-describe-version-name-5.txt)) |

Step 5 is the Q13 rehearsal: a method changed in a new Processing Profile version costs that
method's requests plus an inventory, nothing else.

The promoter's alarms and its retirement guard are tested apart, on the same server version, in
[`tests/test_promoter.py`](../../../../tests/test_promoter.py): a build that polls four queues
past the time limit, `current` missing from `builds`, a rollback by changing `current`, and an
unlisted deployment with an open workflow, which is left untouched and reported.

The run of 2026-11-08 (`501b11`), under the earlier design with one deployment, a dispatcher map
and a pinned override, is in this directory's history at commit `50ad946`.

## SDK and server behaviour (for #78 and #137)

Measured on Server 1.32.0 and temporalio 1.34.0, in `run.py`, in `tests/test_promoter.py` and in
the run of 2026-11-08:

1. **No server switch.** Worker Deployments work on the dev server without dynamic config.
2. **Worker side.** Each worker passes `deployment_config=WorkerDeploymentConfig(version,
   use_worker_versioning=True, default_versioning_behavior=PINNED)`. The SDK docstring still
   marks `deployment_config` as experimental, so only `make_worker` touches it. A workflow
   started with no override on a queue whose deployment has a current version is Pinned to that
   version by this default (step 2).
3. **Names** (step 8). Build IDs with `-`, `@`, `.` and `/` are accepted. A deployment name may
   not contain `.`: the SDK splits `<deployment>.<build>` at the first `.`, so the server does
   not find `names.probe`. Task queue names may contain `.`, hence `paper-pdf-<N>.<queue>`.
4. **Two spellings of a version.** The SDK and `workflow describe` write
   `paper-pdf-1.paper-pdf-1-r1`. Server errors and the visibility attribute
   `TemporalWorkerDeploymentVersion` use `paper-pdf-1:paper-pdf-1-r1`. A visibility query with
   the `.` form matches nothing and raises no error, and `workflow count` prints `{}` for zero.
5. **A start never waits for a rollout.** A request started on a queue that nothing polls, or
   whose deployment has no current version yet, is accepted and waits as backlog (step 1). No
   start is refused any more: the refusal of the 2026-11-08 run came from the pinned override.
6. **Activities follow the pinned build** on every queue the build's workers have polled, and
   the membership outlives the workers: in step 4, with `1-r1`'s inference worker down for
   longer than the poller history, R4's parse waited for `1-r1` instead of running on the
   current build. By the documentation, an Activity on a queue the build has never polled runs
   on that queue's current version, so the promoter makes a build current only once
   `describe-version` lists all five queues.
7. **`describe-version` lists a queue once per task type.** The orchestration queue appears
   twice, for its workflow and its Activity tasks.
8. **The deployment list lags.** `ListWorkerDeployments` returned no deployment for a moment
   after `set-current-version`, while `describe` by name answered at once. The promoter
   describes listed deployments by name and uses the list only to find unlisted ones.
9. **No current version reads as an empty string** in the CLI's JSON
   (`routingConfig.currentVersionBuildID`), before the first promotion and after
   `--unversioned`.
10. **Deleting a version** has three refusals, each seen in steps 4 and 7 or in the 2026-11-08
    run: `cannot be deleted since it is current or ramping`, `... since it is draining` and
    `... since it has active pollers`. All are gRPC `FAILED_PRECONDITION`. The poller window is
    `matching.PollerHistoryTTL`, 5 minutes by default
    ([constants.go](https://github.com/temporalio/temporal/blob/main/common/dynamicconfig/constants.go));
    this run set it to 5 s. Drainage is refreshed every
    `matching.wv.VersionDrainageStatusRefreshInterval` (default 3 minutes) and lags visibility by
    `matching.wv.VersionDrainageStatusVisibilityGracePeriod` (default 3 minutes); both were 2 s
    here. With a 5 s window an idle worker, whose long poll lasts about a minute, can already
    count as forgotten, so the timings of the deletes here say nothing about PROD.
11. **A version set unversioned drains like a replaced one**: it read `draining`, then was
    deletable, with no `--skip-drainage` (step 7).

## Differences from the design (#129)

#178 replaced #129's deployment identity (one deployment, a dispatcher map and a pinned override)
with one Worker Deployment and one set of task queues per Processing Profile version; #129's
"實作修正 — 2026-11-09" and "— 2026-11-10" blocks record that. What remains different:

| #129 or #178 says | Found | Done |
|---|---|---|
| Drainage does not count workflows started through an override, so check visibility before retiring | There is no override any more, and a retired version is still current, so it never reads `draining` | The promoter counts open workflows on the version's orchestration queue before it retires anything |
| A patch build changes only shared code, logging and `runtime` | `runtime` is in the released file, so a new value is a new version. Once a method version moves on `dev`, `dev` can no longer load the older Processing Profile | A patch changes shared code or logging, on the version's release branch; CI refuses a method change there |
| A wrong map entry is stopped by the workflow's `adopted_version` assertion | There is no map. An image listed under another version's deployment would poll that version's queues | The worker refuses to start (step 1); `ADOPTED_VERSION_MISMATCH` in `prepare` stays as the backstop |
| The promoter deletes a Worker Deployment that has no version and is no longer listed | A deployment that leaves the values still has its current version, which never drains | The promoter retires it: unversioned first, then each version, then the deployment (step 7) |

The procedure for adding or changing a method, from code to retirement, is
[`src/kp_canonicalization/profiles/README.md`](../../../../src/kp_canonicalization/profiles/README.md).
