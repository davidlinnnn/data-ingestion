# ACL fixture 09 post-Docker-restart window v3

This is an execution plan for a separately authorized 25-minute process-mode
window. Preparing and testing this runner does not authorize or start runtime,
inference, Temporal work, Kubernetes mutation or a retry. The consumed v2 attempt
and every older trial remain unchanged.

## Fixed scope and new identities

The runner is `tests/pdf_processing/q04/sentinel/run_acl_v3.py`. It uses the
verified restored bundle, state, producer, profile and object namespace under
`/tmp/q04-keynote-18be1b3-20260916-b`. It does not rerun `init` or change frozen
`state/config.json`.

| Item | New immutable value |
| --- | --- |
| Matrix phase | `acl-window-v3-a` |
| Local evidence root | `/private/tmp/q04-acl-window-20260917-v3-a` |
| Remote capacity | `/tmp/q04-keynote-18be1b3-20260916-b/capacity-acl-window-v3-a.json` |
| Remote reservation | `/tmp/q04-keynote-18be1b3-20260916-b/reservation-acl-window-v3-a.json` |
| Remote release marker | `/tmp/q04-keynote-18be1b3-20260916-b/release-reservation-acl-window-v3-a` |
| Outer samples | `/tmp/q04-keynote-18be1b3-20260916-b/pre-admission-acl-window-v3-a.jsonl` |
| Outer verdict | `/tmp/q04-keynote-18be1b3-20260916-b/admission-acl-window-v3-a.json` |
| Staged admission code | `/tmp/q04-keynote-18be1b3-20260916-b/runner-acl-window-v3-a` |
| Runtime log | `/tmp/q04-keynote-18be1b3-20260916-b/logs/acl-window-v3-a.log` |
| VM/cgroup OOM baseline | `0` / `0` |

All paths were absent during the read-only preparation and must still be absent.
Staging uses exclusive creation and records SHA-256 for the committed outer
admission, callback adapter and telemetry guard. The runtime prepends that staged
directory and sets `PYTHONSAFEPATH=1`; direct controller and worker script
entrypoints therefore cannot put their frozen script directory ahead of the
staged telemetry guard. This enforces the reviewed OOM=0 baseline without
rewriting the restored frozen source. Any collision rejects the attempt; no path
is removed or overwritten.

The runtime command remains one `matrix --fixture 09` invocation for exactly
fresh, restored/new request and exact replay. Its consumer checks the six reviewed
equations, equation 2 as `TextItem`, complete typed graph/captions/source evidence
and required selected-component OCR. No other fixture, invalidation, warm, drain
or Pod mode is in scope.

## Restart and ownership fences

Before reservation, the runner must match the baseline in
`post-docker-restart-a/BASELINE.md`: Pod UID, exact container ID, restart count 1,
container start time, Linux boot ID, PID 1 start ticks and VM/cgroup OOM counters.
Any further restart, replacement or OOM increment stops before admission.

The runner then verifies Python/platform, all packages and model artifacts, the
restored Q04 producer, restored bundle/profile, frozen state hash, existing
Keynote completion and absence of PDF processes. `/app/pdf_processing` is not the
selected producer. The missing pre-restart `/tmp/q03-20260916-d` path is not used.
Both the complete frozen state hash and bundle hash are pinned to the reviewed
post-restart values; matching only selected fields is insufficient.

Restored reservation records are historical evidence: their PIDs are dead, locks
are not held and release markers exist. A future authorized invocation generates a
new random token and a new holder PID/start-ticks/lock device/inode identity. That
exact identity is rechecked before every outer-admission sample. The shared lock
and new exclusive reservation prevent concurrent ownership.

## Unchanged capacity and stop points

| Lease segment | Bound | Enforcement |
| --- | ---: | --- |
| Whole lease | 1,500 s | `ends_at = starts_at + 1500` |
| Outer observation | at most 180 s | monotonic `outer_admission.observe_capacity` |
| Outer qualifying interval | continuous 60 s | MemAvailable ≥ 4,831,838,208 B and full PSI avg10 = 0 |
| Per-case qualifying interval | continuous 60 s | MemAvailable ≥ 3,221,225,472 B and full PSI avg10 = 0 |
| Runtime workload | 825 s retained | outer policy plus GNU `timeout 825s` |
| Owned cleanup | final 300 s | no new work at or after `ends_at - 300` |
| Setup/verification margin | 195 s | `1500 - 180 - 825 - 300` |

Low memory or positive PSI resets only the outer continuous interval and retains
every JSONL sample. New VM/cgroup OOM, cgroup ceiling violation, stale/gapped
telemetry, reservation drift, container drift or identity drift rejects
immediately. Admission failure and runtime failure remain terminal; there is no
automatic retry and no threshold reduction. The v3 capacity record carries OOM
baseline zero explicitly; the consumed v2 record and adapter default remain 28.

The three callbacks retain the reviewed cooperative contract: bounded local reads
and writes, no subprocess/network/sleep, no `BaseException` handler, and timeout
control flow propagates. Any callback that ceases to cooperate requires an external
process supervisor before use.

## Exact future command

Run only after main and the capacity owner provide a new authorization reference:

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_v3.py \
  --execute \
  --owner '<approved capacity owner>' \
  --approval-reference '<new 25-minute ACL authorization>'
```

The runner first rechecks all identities and baselines, T09a health/idle state and
the same 32 historical Deployment UIDs at `replicas=0`, `ready=0`, with no matching
Pods. It contains no scale or restore operation. Those Deployments remain
main-owned and closed on every exit.

Every post-reservation exit performs owned cleanup, retains partial histories and
artifacts, verifies frozen state and held Deployments, captures evidence and
releases the exact reservation. A PASS would be bounded evidence for ACL fixture
09 only; it would not publish or close #51.
