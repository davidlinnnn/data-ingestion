# YOLO fixture-07 fresh-only attribution calibration B

This is a reviewable offline preparation for one separately authorized 25-minute
process-mode calibration. It grants no runtime, inference, Temporal workflow,
reservation, Kubernetes mutation, Pod, or cgroup creation. The 32 historical
Deployments remain main-owned and closed. The runner contains no scale or restore
operation.

## Bounded purpose

The phase is `yolo-attribution-b`. It runs fixture 07 **fresh only**, at most
once, with no retry. It measures the existing shared coordinator cgroup, every
readable process in that cgroup, and the owned subtree rooted at the calibration
controller. It does not
run restored or replay, does not accept fixture 07, and cannot close issue #51.
The unchanged live-init step copies the six frozen source fixtures into the new
prefix because that is the harness contract; the only workflow invocation is
still fixture 07 fresh.

The unchanged worker telemetry remains the active qualification guard. The new
collector is diagnostic evidence. Missing data cannot raise a memory limit, but
it makes the affected sample `unknown`/`incomplete`; PSS and unattributed bytes
remain `null`, never zero.

## Decision, execution and acceptance path

This run answers one blocking question: **which observed process class or
shared-cgroup charge accounts for fixture 07 approaching the unchanged 4 GiB
guard during fresh assembly and cancellation?** A decision requires continuous
250 ms rows from baseline through an externally observed assembling state,
cancellation and post-cleanup, with every row identity-fenced and complete. A
guard stop may be measured successfully, but never counts as fixture acceptance.

The next action is fixed by the evidence:

1. If one owned parser/worker class explains the rise and the shared-cgroup
   remainder stays small, change only that class's lifetime or retained data;
   discard this path if the class peak does not align with `memory.current`.
2. If shared-cgroup processes outside the owned tree explain the rise, isolate
   or reschedule that exact workload; discard an owned-parser change.
3. If process PSS stays bounded while `memory.stat` file/slab/kernel charges
   explain the rise, change the corresponding buffering/cache lifetime; do not
   label the generic residual as cache without those fields.
4. If any row, required marker, identity fence or cleanup proof is incomplete,
   make no implementation choice. The only allowed follow-up is the smallest
   measurement needed to recover that named field or boundary; do not add broad
   instrumentation or rerun the same incomplete setup repeatedly.

Any eventual processing change must rerun fixture 07 fresh first, then its
restored and exact-replay cases. Existing Keynote and ACL evidence, the frozen
bundle/profile checks, old-request binding and cleanup contracts remain reusable
unless the change touches their producer or shared harness hashes. The six-fixture
matrix follows in bounded batches only after fixture 07 passes its three modes;
Pod drain remains a separate gate. Release blockers are the fixed per-fixture
oracles, complete graph/delivery, compatibility/replay semantics, invalidation,
resource/cleanup guards and interruption/retry/replay behavior. Extra internal
stage markers and general PDF-quality claims remain deferred and cannot lower
those criteria.

## Exclusive identity

| Field | Value |
| --- | --- |
| Remote root | `/tmp/q04-yolo-attribution-20260918-b` |
| Object prefix | `q04/yolo-attribution-20260918-b/` |
| Local output | `/private/tmp/q04-yolo-attribution-20260918-b` |
| Phase | `yolo-attribution-b` |
| Runner directory | `/tmp/q04-yolo-attribution-20260918-b/runner-yolo-attribution-b` |
| Driver lock | `/tmp/q04-yolo-attribution-20260918-b/yolo-attribution-b.driver.lock` |
| Capacity | `/tmp/q04-yolo-attribution-20260918-b/capacity-yolo-attribution-b.json` |
| Reservation | `/tmp/q04-yolo-attribution-20260918-b/reservation-yolo-attribution-b.json` |
| Release marker | `/tmp/q04-yolo-attribution-20260918-b/release-reservation-yolo-attribution-b` |

Every path and prefix must be absent before the runner claims them. Creation is
exclusive; a collision stops without deleting or reusing anything. The existing
matrix-A prefix, paths, result and raw evidence remain immutable.

The runner clones the already reviewed harness tree, verifies bundle SHA-256
`9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2`,
runtime SHA-256
`5fc631f0076001b75815901d610b974b99db52a50d2eb9b8a3b735ab3d109471`,
fixture/reference/oracle hashes, and creates a new run ID and unused object
prefix through the unchanged `q04_runtime.py --phase init`. The frozen producer,
profile method and input bytes are verified; no existing state or profile is
edited in place.

## Fixed staged sources

`OFFLINE-MANIFEST.json` is the machine-readable authority. The outer runner
first requires the manifest and all staged sources to match committed `HEAD`
with no staged or unstaged edits, compares every local SHA to the manifest,
uploads each file exclusively, then reads it back and rejects any SHA mismatch.

| Source | SHA-256 |
| --- | --- |
| `run_yolo_attribution_b.py` | `c28dcde0bbb4fbe6e6033b49bf56f36e568d5df859b93b9ea7be772e62c76931` |
| `yolo_fresh_measure.py` | `596ee24579109780d4ce333c145ac28f69e0461258e8cf24f523f13c21ee75e9` |
| `yolo_attribution_telemetry.py` | `3dc682ea2aeea9cbcee62a2e83193358179b8892f3c8eb330896a0d4cf6f3982` |
| `acl_resource_telemetry.py` | `bec7f4d520c29b9c9054a233a718afd67d67714dcad9f36da58546c1839f53a3` |
| `cleanup.py` | `9e3342883f39159e31a8fddce22011d9f4052b436a4a4ee7f80c6e1cbf36d169` |
| `acl_admission.py` | `eda4e58232185200b279b1a612bb59e9439bd753488699af614e6c0857ad6872` |
| `outer_admission.py` | `175a9f31fb02d8938c0751eb832dcf4faf35d4262975fc0072536377b363033e` |
| `telemetry.py` | `556f3b5c5c49bf869a4a664ba837a23c13319a8d4a0a75b62f49c3fc508d7891` |

The new collector reuses the ACL parser/cgroup identity implementation but owns
the stricter completeness semantics, process lifecycle, observational markers,
collector-cost accounting, and post-cleanup report behind one interface.

## Capacity and guard budget

| Rule | Fixed value |
| --- | ---: |
| Whole window | 1,500 s |
| Outer observation | at most 180 s |
| Outer admission | 60 continuous s at MemAvailable ≥ 4,831,838,208 B and PSI full avg10 = 0 |
| Per-case admission | 60 continuous s at MemAvailable ≥ 3,221,225,472 B and PSI full avg10 = 0 |
| Active VM floor | 1,610,612,736 B |
| Active shared-cgroup ceiling | 4,294,967,296 B (4 GiB) |
| Worker telemetry gap | at most 3 s |
| Attribution cadence/gap | 250 ms / at most 1 s |
| VM and cgroup OOM | no increment from zero baseline |
| Per-workflow bound | 180 s |
| Workload wrapper | 825 s; SIGINT then 180 s kill-after |
| Cleanup reserve | final 300 s |

Admission may consume the full 180 seconds only if at least 825 + 300 seconds
still remain before launch. Identity drift, resumed Deployment, active T09a
workflow, held lock, path collision, failed admission, PSI, OOM, VM floor, 4 GiB
crossing, worker telemetry loss, collector gap, unexpected workflow failure, or
cleanup uncertainty stops the attempt. No threshold is lowered. There is no automatic retry.

An expected 4 GiB guard stop may still yield a **complete measurement** when all
attribution and cleanup requirements pass. It remains a failed fresh workload
and is never converted into fixture acceptance.

## Evidence and marker semantics

Each 250 ms row records shared-cgroup `memory.current`, `memory.events`,
`memory.pressure`, selected `memory.stat` fields, and a double-enumerated process
set filtered by exact cgroup membership, with PID, PPID, start ticks, owned/shared
classification, command hash/class, current RSS/PSS,
anonymous/file/shmem RSS, faults and CPU ticks. Re-enumeration fences birth,
exit, and PID reuse races. Unreadable process identity, cmdline, status, PSS, or
cgroup fields remain explicit unknowns.

`owned_pss_total_bytes`, `shared_cgroup_process_pss_total_bytes` and
`diagnostic_unattributed_bytes` are emitted only for a complete synchronized
sample. The latter subtracts all observed same-cgroup process PSS and still
contains file/cache, kernel and other non-process cgroup charges plus sequential
read timing skew. Process PSS reads share one measured sample window but are not
atomic. The value is explicitly not labelled cache, and PSS class maxima are
never summed.

Collector cost is retained as per-sample wall/thread-CPU time, aggregate wall,
thread-CPU, maximum sample duration, output bytes, and controller baseline/maximum
PSS. Full rows stream to an append-only `.inflight` spool; only the byte boundary
after a completed flush and matching compact-row append is committed. Stop seals
that committed prefix into the final JSONL. A partial write or publication
exception latches abandonment, so a later terminal sample cannot commit past the
last valid row. Only compact summary fields remain in memory. Because the
collector is a thread in the controller, its memory cannot be
isolated from other driver allocations; the summary says so explicitly rather
than claiming the controller PSS delta is collector-only. A peak-memory sample
must have complete attribution. Any sample that races a process transition or
has a read/coverage gap makes the whole measurement incomplete, even if complete
samples bracket it within one second. The bracket span remains diagnostic only.

No producer instrumentation is injected. Markers have these limited meanings:

- driver callbacks record baseline, worker readiness, admission and return from
  owned cleanup;
- `workflow-intent.json` and `workflow.json` show persisted intent/submission,
  not Activity start;
- a progress query reporting `assembling` remains workflow state, not proof that
  assembly Activity started;
- `merged/` existence shows filesystem presence, not the instant materialization
  began;
- a new identity-fenced `python -m pdf_processing.parse` process proves process
  birth, but its stdin and restore mode are not visible to the collector.

Therefore this plan does not promise exact assembly-materialization or restore
spawn markers. If those internal boundaries remain necessary after external
measurement, a separate minimal hook design must be reviewed with new producer
hashes and behavior/equivalence tests before changing the frozen producer.
Measurement completeness still requires the externally observed sequence
baseline → workflow progress `assembling` → cancel callback → post-cleanup
sample. Missing or out-of-order markers are incomplete.

## Exact command after separate authorization

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_yolo_attribution_b.py \
  --execute \
  --owner '<approved capacity owner>' \
  --approval-reference '<new YOLO attribution-B authorization>'
```

After exclusive init returns the new `q04-*` run ID, the runner builds this argv
list without user text or shell interpolation:

```text
/experiment/.venv/bin/python
/tmp/q04-yolo-attribution-20260918-b/runner-yolo-attribution-b/yolo_fresh_measure.py
--bundle /tmp/q04-yolo-attribution-20260918-b/inputs
--state /tmp/q04-yolo-attribution-20260918-b/state
--capacity /tmp/q04-yolo-attribution-20260918-b/capacity-yolo-attribution-b.json
--name yolo-attribution-b
--expected-run-id <new q04-* ID read from state-init.json>
--expected-prefix q04/yolo-attribution-20260918-b/
--trial-seconds 180
--attribution-interval-seconds 0.25
--attribution-gap-seconds 1
--capacity-approved
```

The fixed argv is wrapped by `timeout --signal=INT --kill-after=180s 825s` and
shell-quoted with `shlex.join`. The driver exposes no fixture, mode, prefix,
profile, producer or retry argument.

## Cleanup and retained result

The driver stops or cancels only its owned workflow and worker, then takes a
terminal attribution sample after those callbacks return. The outer runner runs
the reviewed identity-fenced `cleanup.py`, verifies no owned workflow/process,
scratch or incomplete publication remains, captures all evidence, confirms T09a
health and all 32 Deployments still have replicas/Ready zero, then releases the
exact reservation. It never restores those Deployments.

Every exit reserves the final 300 seconds for cleanup. A collector thread that
does not stop within two seconds is abandoned without waiting on a blocked
writer. Only the already committed spool prefix is sealed, so its final JSONL
and summary cannot change afterward; the run is incomplete and outer cleanup
continues. A normal reservation-release write or wait failure invokes a
bounded fallback that validates the acquired token, PID, start ticks and lock
inode before terminating that exact remote holder, then verifies the process and
lock are gone. Cleanup also re-reads the token-bound record for every launched
holder, so a lost local acquisition acknowledgement cannot skip reconciliation.
Historical matrix-A artifacts and original frozen state are
rehashed afterward. The final record must distinguish workload outcome,
measurement completeness and cleanup completeness, with
`acceptance_claimed=false`.
