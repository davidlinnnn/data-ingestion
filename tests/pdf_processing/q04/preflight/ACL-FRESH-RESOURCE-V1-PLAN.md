# ACL fixture-09 fresh-only resource calibration v1

This is a reviewable plan for a separately authorized 25-minute process-mode
measurement window. It does not authorize runtime, inference, workflow submission,
a reservation or a Kubernetes mutation. Historical v3-a and v3-b paths and evidence
remain immutable. The 32 main-owned historical Deployments remain closed and this
runner has no scale or restore operation.

## Scope and identity

The runner is `tests/pdf_processing/q04/sentinel/run_acl_resource_v1.py`. It may
run fixture 09 **fresh only**. It cannot request restored or exact replay, another
fixture, invalidation, warm, drain or Pod mode. It does not change production,
Docling lifecycle, the frozen producer or the frozen profile.

| Identity | New v1 value |
| --- | --- |
| Phase | `acl-fresh-resource-v1` |
| Local output | `/private/tmp/q04-acl-fresh-resource-20260917-v1` |
| Runtime state | `/tmp/q04-keynote-18be1b3-20260916-b/state/acl-fresh-resource-v1` |
| Capacity | `/tmp/q04-keynote-18be1b3-20260916-b/capacity-acl-fresh-resource-v1.json` |
| Reservation | `/tmp/q04-keynote-18be1b3-20260916-b/reservation-acl-fresh-resource-v1.json` |
| Release marker | `/tmp/q04-keynote-18be1b3-20260916-b/release-reservation-acl-fresh-resource-v1` |
| Outer samples/result | `pre-admission-acl-fresh-resource-v1.jsonl` / `admission-acl-fresh-resource-v1.json` |
| Staged runner | `/tmp/q04-keynote-18be1b3-20260916-b/runner-acl-fresh-resource-v1` |
| Runtime log | `/tmp/q04-keynote-18be1b3-20260916-b/logs/acl-fresh-resource-v1.log` |
| Driver lock | `/tmp/q04-keynote-18be1b3-20260916-b/acl-fresh-resource-v1.driver.lock` |

Every path must be absent before reservation and is created exclusively. A collision
stops the attempt without deletion, overwrite or reuse. The local output uses
exclusive directory creation. There is no automatic retry.

The run reuses the reviewed frozen bundle at
`/tmp/q04-keynote-18be1b3-20260916-b/inputs`, SHA-256
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`,
and the frozen state/config SHA-256
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`.
It verifies run ID `q04-7b4f958ff3ac4e2da5b54dcaa66914b9`, producer,
fixture-09 method and existing object prefix
`q04/keynote-18be1b3-20260916-b/` before work.

The existing prefix is intentional: the frozen state binds it. The fresh trial
generates a new `q04-<uuid>` request and captures fixture 09 as a new versioned
source-object version under that namespace. `phase-complete.json` records the new
request ID and exact artifact key/version. Existing versions and requests are not
overwritten or reinterpreted. A new object prefix would require a separate `init`
and independent frozen state; this slice does neither.

## Capacity and stop rules

| Rule | Value |
| --- | ---: |
| Whole lease | 1,500 s |
| Outer observation | at most 180 s |
| Outer admission | continuous 60 s, MemAvailable at least 4,831,838,208 B (4.5 GiB), PSI full avg10 = 0 |
| Per-case admission | continuous 60 s, MemAvailable at least 3,221,225,472 B (3 GiB), PSI full avg10 = 0 |
| Active VM floor | 1,610,612,736 B (1.5 GiB) |
| Candidate sampled cgroup ceiling | 4,294,967,296 B (4 GiB) |
| Existing worker guard gap | at most 3 s |
| Attribution cadence / evidence gap | 250 ms / at most 1 s |
| VM/cgroup OOM | baseline 0 / 0 with no increment |
| Per-workflow bound | 180 s |
| Workload budget | 825 s, SIGINT then 180 s kill-after |
| Cleanup reserve | final 300 s |

The 3 GiB per-case value is a **MemAvailable admission threshold**. The 4 GiB
value is a provisional **sampled cgroup observation ceiling for this calibration**.
It is not a worker policy, Kubernetes request/limit, Pod sizing or Q04 acceptance
requirement. The existing active VM/PSI/OOM and worker-telemetry guards remain the
fail-closed controls. A 4 GiB crossing stops the attempt and proves only that the
candidate observation envelope was too low.

Before reservation, recheck the exact Pod/container/restart/start/boot/PID-1
identity, OOM=0, frozen hashes, packages/models, T09a health and idle state, all 32
Deployment UID/replica/Ready values, absence of candidate Pods and every new path.
Outer admission must PASS and at least 825 + 300 seconds remain before launch.

Stop without retry on identity or ownership drift, path collision, T09a activity,
held locks, resumed historical services, outer-admission failure, VM floor or PSI
violation, OOM increment, 4 GiB cgroup crossing, worker telemetry loss, workflow
failure, collector required-field failure, deadline or cleanup uncertainty. Optional
RSS/PSS or `memory.stat`/`memory.peak` absence is recorded as incomplete attribution;
it is not reported as a memory violation. The result cannot be measurement-complete
without the reviewed attribution evidence.

The driver creates and exclusively locks the new driver-lock path before entering
its async runtime. Each cooperative runtime guard call also checks the age of the
last completed attribution sample, so a stall over one second stops work at the
next guard check. Collector shutdown sets its stop signal before a bounded two-second
join; a stuck collector is reported as incomplete cleanup and cannot block the
controller's process exit.

## Attribution evidence

`acl_resource_telemetry.ResourceCollector` starts before the worker and stops only
after owned cancellation/worker cleanup. At 250 ms it records:

- `/proc/self/cgroup`, the cgroup-v2 mount root/point, observed directory device
  and inode;
- `memory.current`, `memory.events`, selected `memory.stat` fields and
  `memory.peak` when readable;
- controller-rooted owned process PID, parent, start ticks, command-class hash,
  RSS/PSS, anonymous/file/shmem RSS, faults and CPU ticks;
- lifecycle markers for collector start, worker start/readiness, per-case admission,
  fresh completion and owned cleanup;
- owned PSS total and `memory.current - PSS` as a labelled diagnostic residual.

`memory.peak` is the shared cgroup's lifetime high-water mark. The collector never
resets it and the report must not call it the current run's peak. The per-run peak is
derived from this run's `memory.current` series. PSS and the residual are auxiliary
attribution fields: PSS can be unavailable or race process exit, RSS can double-count
shared pages, and the residual also contains cache/kernel charges and timing skew.
These values do not replace the existing guard.

Missing/permission-denied optional fields and process-exit races are retained in
each row. They mark attribution incomplete. File cache remaining after cleanup is
not by itself a leak and is not a reason for automatic reruns. The headroom formula,
residual threshold and cleanup-release percentage in the diagnosis are candidate
heuristics for later review, not acceptance requirements in this window.

## Exact command after separate authorization

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_resource_v1.py \
  --execute \
  --owner '<approved capacity owner>' \
  --approval-reference '<new fresh-only ACL resource-window authorization>'
```

The future authorization must name `acl-fresh-resource-v1`, permit one fresh-only
fixture-09 attempt with the provisional 4 GiB sampled ceiling, preserve all other
guards and the 300-second cleanup reserve, forbid automatic retry, and require the
32 Deployments to remain closed.

The runner stages the outer-admission adapter, existing guard telemetry, fresh-only
driver and attribution collector by SHA-256. The nested shell verifies the bundle,
uses safe quoting, checks the phase and driver-lock paths immediately before the
timeout wrapper, and invokes only `acl_fresh_measure.py`. The driver verifies the
frozen state, performs per-case admission, creates one fresh request, runs the full
fixture-09 consumer/oracle checks, then cancels/stops only owned work and closes the
collector. The outer runner independently runs owner cleanup, frozen-state/hash
checks, evidence capture, service health/closure checks and exact reservation
release on every exit. Owner cleanup recognizes only the historical reviewed
controller or the exact staged `runner-acl-fresh-resource-v1/acl_fresh_measure.py`
entrypoint when its arguments bind it to this run's state directory.

## Evidence to retain

- coordinator/container/boot/PID-1 identity and runtime package/model/frozen probes;
- before/after 32-Deployment snapshots and T09a health;
- capacity, reservation identity, staged-source manifest and outer admission rows;
- phase config, fresh request/admission/workflow/progress/result/history/oracle and
  incomplete-publication/cleanup records;
- existing worker `samples.jsonl` plus `resource-attribution.jsonl` and its summary;
- runner log, cleanup result, frozen postcheck, remote evidence tar and local
  artifact manifest/hash list;
- final release/lock/process/workflow/OOM/health verification.

Local preparation validates only synthetic files and processes, command transport,
identity collision, deadline and cleanup code. It does not qualify Linux runtime
telemetry, the 4 GiB candidate, ACL output, or any production/Pod resource policy.
