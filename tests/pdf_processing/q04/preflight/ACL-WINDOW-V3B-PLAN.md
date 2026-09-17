# ACL fixture 09 corrected post-restart window v3-b

This is a plan for a separately authorized 25-minute process-mode window. It
does not authorize runtime, inference, workflow submission, a reservation or a
Kubernetes mutation. The failed v3-a attempt, commit `f556c10`, its remote files
and `/private/tmp/q04-acl-window-20260917-v3-a` remain immutable historical
evidence. Nothing in v3-b reads v3-a as live ownership or overwrites it.

## Corrected command boundary

The runner is `tests/pdf_processing/q04/sentinel/run_acl_v3b.py`. Its runtime
command passes a shell-quoted Python program as one argument to the inner
`sh -c`. That program constructs the bundle path from exported environment
variable `R`:

```python
verify_bundle(Path(os.environ["R"]) / "inputs")
```

It therefore does not interpolate a quoted path inside Python source. The local
regression executes the same outer shell, timeout wrapper and inner shell with a
temporary absolute root containing spaces. A safe fake `verify_bundle` records
the received path, then a safe fake `q04_runtime.py` records its arguments. The
test requires the exact absolute input path, staged telemetry import, fixture 09
matrix arguments and `acl-window-v3-b` name. It submits no Temporal workflow and
imports no Docling parser or model.

## New exclusive identities

| Item | v3-b value |
| --- | --- |
| Phase | `acl-window-v3-b` |
| Local evidence root | `/private/tmp/q04-acl-window-20260917-v3-b` |
| Remote capacity | `/tmp/q04-keynote-18be1b3-20260916-b/capacity-acl-window-v3-b.json` |
| Remote reservation | `/tmp/q04-keynote-18be1b3-20260916-b/reservation-acl-window-v3-b.json` |
| Remote release marker | `/tmp/q04-keynote-18be1b3-20260916-b/release-reservation-acl-window-v3-b` |
| Outer samples | `/tmp/q04-keynote-18be1b3-20260916-b/pre-admission-acl-window-v3-b.jsonl` |
| Outer verdict | `/tmp/q04-keynote-18be1b3-20260916-b/admission-acl-window-v3-b.json` |
| Staged admission code | `/tmp/q04-keynote-18be1b3-20260916-b/runner-acl-window-v3-b` |
| Runtime state | `/tmp/q04-keynote-18be1b3-20260916-b/state/acl-window-v3-b` |
| Runtime log | `/tmp/q04-keynote-18be1b3-20260916-b/logs/acl-window-v3-b.log` |

All nine locations and the local evidence root were absent in the 2026-09-17
14:51 UTC read-only preparation probe. The runner rechecks every location before
reservation. Local output uses `mkdir` without `exist_ok`; remote capacity,
reservation, release, admission and staged files use exclusive creation. Any
collision rejects the attempt without deletion or reuse.

## Frozen state and service fences

The read-only preparation probe matched the same Pod UID, exact container ID,
restart count 1, container start time, Linux boot ID and PID 1 start ticks as the
post-restart baseline. VM and cgroup OOM-kill remained zero, full PSI avg10 was
zero and MemAvailable was 9,486,084 KiB at the point sample. No qualification
lock or Q04 process was active.

The restored Python 3.12.13 environment had 112 packages and 17 model artifacts
with zero differences. The restored producer, bundle, five-page profile and
frozen state matched. Bundle SHA-256 remains
`b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297`;
state SHA-256 remains
`6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7`.

T09a Temporal was healthy with no Running workflow and object readiness returned
200. All 32 historical PDF Deployment UIDs matched and every Deployment remained
`replicas=0`, `ready=0`, with no matching Pods. The v3-b runner contains no scale
or restore operation. Those Deployments remain main-owned and closed on every
exit.

The runner repeats these checks before creating a reservation. A container
replacement, restart, boot/PID identity change, OOM increment, frozen hash
change, active PDF process, Running workflow, held lock, path collision or resumed
historical Deployment stops the attempt before admission.

## Capacity, watchdog and cleanup

| Lease segment or guard | Required value |
| --- | ---: |
| Whole lease | 1,500 s |
| Outer observation | at most 180 s |
| Outer qualifying interval | continuous 60 s, MemAvailable at least 4,831,838,208 B, full PSI avg10 = 0 |
| Per-case qualifying interval | continuous 60 s, MemAvailable at least 3,221,225,472 B, full PSI avg10 = 0 |
| Active memory floor | 1,610,612,736 B |
| Active cgroup ceiling | 3,221,225,472 B |
| Telemetry gap ceiling | 3 s |
| VM/cgroup OOM baseline | 0 / 0, no increment |
| Runtime workload budget | 825 s |
| Per-case workflow bound | 180 s |
| External runtime timeout | 825 s, SIGINT then 180 s kill-after |
| Owned cleanup reserve | final 300 s |

Outer admission cannot launch runtime unless it returns PASS and at least
825 + 300 seconds remain. Positive PSI or low memory resets the continuous outer
interval; OOM, identity drift, stale telemetry or cgroup violation rejects it.
Runtime failure is terminal and is not retried. At the cleanup boundary the
driver receives SIGINT; the runner then performs owner cleanup, frozen-state
verification, evidence capture, held-service verification and exact reservation
release. Historical Deployments are checked but never restored.

The staged outer admission, callback adapter and telemetry guard are copied with
SHA-256 verification. `PYTHONSAFEPATH=1` plus the staged directory at the front of
`PYTHONPATH` makes controller and worker script entrypoints import the staged
OOM=0 telemetry guard instead of the frozen copy.

## Fixed acceptance scope

One future invocation may execute only ACL fixture 09 original pages 2–4 as
fresh, restored/new request and exact replay. It must verify all six reviewed
equations, equation 2 as `TextItem`, the complete typed graph, captions, source
evidence and required selected-component OCR. It may not run another fixture,
invalidation, warm, drain or Pod mode. A PASS remains bounded ACL evidence and
does not close Q04 or #51.

## Exact future command and authorization

After main approves a new capacity owner and authorization reference for one
25-minute v3-b window:

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_v3b.py \
  --execute \
  --owner '<approved capacity owner>' \
  --approval-reference '<new ACL v3-b 25-minute authorization>'
```

Preparation, local tests and read-only probes do not grant that authorization.
The next authorization must name v3-b, permit only fixture 09
fresh/restored/exact replay, retain all thresholds and cleanup reserve, forbid
automatic retry, and require the 32 historical Deployments to remain closed.
