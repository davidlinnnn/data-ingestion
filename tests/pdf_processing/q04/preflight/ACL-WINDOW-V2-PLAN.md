# ACL fixture 09 outer-admission v2 window

This is an execution plan for a separately authorized 25-minute process-mode
window. Preparing and testing this runner does not authorize or start runtime,
inference, Temporal work, Kubernetes mutation or a retry of retained ACL trial C.

## Fixed scope and identities

The runner is
`tests/pdf_processing/q04/sentinel/run_acl_v2.py`. It reuses the already reconciled
frozen bundle, state, producer, profile and versioned object namespace under
`/tmp/q04-keynote-18be1b3-20260916-b`. It does not rerun `init` or change frozen
`state/config.json`.

| Item | New immutable value |
| --- | --- |
| Matrix phase | `acl-window-v2-a` |
| Local evidence root | `/private/tmp/q04-acl-window-20260917-v2-a` |
| Remote capacity | `/tmp/q04-keynote-18be1b3-20260916-b/capacity-acl-window-v2-a.json` |
| Remote reservation | `/tmp/q04-keynote-18be1b3-20260916-b/reservation-acl-window-v2-a.json` |
| Remote release marker | `/tmp/q04-keynote-18be1b3-20260916-b/release-reservation-acl-window-v2-a` |
| Outer samples | `/tmp/q04-keynote-18be1b3-20260916-b/pre-admission-acl-window-v2-a.jsonl` |
| Outer verdict | `/tmp/q04-keynote-18be1b3-20260916-b/admission-acl-window-v2-a.json` |
| Staged admission code | `/tmp/q04-keynote-18be1b3-20260916-b/runner-acl-window-v2-a` |
| Runtime log | `/tmp/q04-keynote-18be1b3-20260916-b/logs/acl-window-v2-a.log` |

All paths must be absent. Staging uses exclusive creation and records SHA-256 for
the committed `outer_admission.py` and `acl_admission.py`. Any collision rejects
the attempt; no path is removed or overwritten.

The runtime command is one `matrix --fixture 09` invocation. The existing matrix
adapter runs exactly fresh, restored/new request and exact replay. Its checked
consumer verifies the six source-reviewed equations, equation 2 as `TextItem`,
complete typed graph/captions/source evidence and required selected-component OCR.
No other fixture, invalidation, warm, drain or Pod mode is in scope.

## Lease and stop points

The runner stamps the capacity record only after read-only frozen checks,
reservation acquisition and versioned runner staging have succeeded.

| Lease segment | Bound | Enforcement |
| --- | ---: | --- |
| Whole lease | 1,500 s | `ends_at = starts_at + 1500` |
| Outer observation | at most 180 s | monotonic `outer_admission.observe_capacity` |
| Required qualifying interval | continuous 60 s | MemAvailable ≥ 4,831,838,208 B and full PSI avg10 = 0 |
| Runtime workload | 825 s retained | outer policy plus GNU `timeout 825s` |
| Owned cleanup | final 300 s | no new work at or after `ends_at - 300` |
| Setup/verification margin | 195 s | `1500 - 180 - 825 - 300` |

Low memory or positive PSI resets the continuous interval and retains every JSONL
sample. Samples are never stitched across a reset. New VM/cgroup OOM, cgroup ceiling
violation, missing/invalid/stale/gapped telemetry, reservation drift or coordinator
identity drift rejects immediately. Observation cannot borrow from the 825-second
workload budget or final 300-second cleanup reserve. Admission rejection and any
runtime failure are terminal for the window; the runner performs no automatic retry.
After admission returns, the host checks the PASS result and rechecks the monotonic
lease immediately before launch; it repeats the check after writing the phase state.
Bundle verification and the matrix driver both run inside the 825-second timeout.

The existing per-case admission and active guards remain unchanged after outer
admission. Each fresh/restored/replay worker still runs the frozen Q04 60-second
4.5-GiB/zero-PSI admission, telemetry freshness, memory/cgroup, OOM, worker-health
and publication guards.

## Cooperative callback audit

`sentinel/acl_admission.py` is staged with the reviewed outer helper and runs in the
coordinator driver's main thread.

| Callback | Operations inside callback | Contract check |
| --- | --- | --- |
| `verify_identity` | Read the exclusive reservation JSON, `/etc/hostname`, exact `/proc/<pid>/stat` state/start ticks, `/proc/locks` flock ownership and release-marker existence | Local files only; no subprocess, network, sleep or exception handler. Exact coordinator UID, hostname, live PID/start ticks, lock device/inode, token and phase are compared every sample. |
| `sample` | Call the existing `telemetry.sample` against `/proc` and cgroup v2 files | Local bounded reads and parsing only; no exception handler. |
| `record` | Serialize one row, append it to the exclusive line-buffered JSONL stream and flush | Local append only; short writes fail; no exception handler. |

All three callbacks allow the helper's `BaseException` timeout control flow to
propagate. Local tests inject a `BaseException` into each callback and prove it is
not swallowed. The in-process alarm remains a cooperative bound: future callback
changes that catch `BaseException`, use bare `except`, perform network/subprocess
work or enter native code that can defer Python signal delivery require a separate
externally supervised process before use.

## Exact future command

Run only after main and the capacity owner provide a fresh authorization reference:

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_v2.py \
  --execute \
  --owner '<approved capacity owner>' \
  --approval-reference '<fresh 25-minute ACL authorization>'
```

The runner first rechecks the coordinator UID, frozen package/model/profile/bundle,
Temporal/object-storage health and idle state. It also verifies the same 32
historical Deployment UIDs remain at `replicas=0`, `ready=0`, with no matching Pods.
It contains no scale or restore operation. Those Deployments remain main-owned and
closed on every exit.

On every post-reservation exit, owned cleanup retains partial histories/artifacts,
stops only owned worker/workflow/process state, audits incomplete publication,
captures new evidence, verifies frozen config and all 32 held Deployments, and then
releases the exact reservation. A PASS for this ACL window is bounded evidence for
fixture 09 only and does not publish or close #51.
