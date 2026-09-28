# CC result: object PSI still blocks #44

CC (`t09a-bounds-20260927-cc`, prefix `t09a/bounds-20260927-cc/`) ran once
with all 32 recorded Deployments active. Admission and 11/11 pre-inference
gates passed. Wiki06 parsed 28 pages and completed all 11 selected OCR
component activities. The next activity was scheduled but had not started when
the object-service full-PSI guard stopped the run at
2026-09-27 04:28:52.038 UTC. The remaining sequence and request-20 recycle
were not reached.

The first object full-PSI increase was 1,990 us in the sample 48 ms before
stop; it reached 5,133 us during cleanup. The object cgroup used about 250 MiB
of its observed 1 GiB limit at the first increase, with zero max/OOM events.
The node full-PSI counter also rose. Worker cgroup and VM direct-reclaim
counters, and VM compaction stalls, were flat for the final 2.4 seconds.

The host-PID trace captured 283 direct-reclaim begin/end pairs overall, 266
from the CC worker Pod. A burst of 253 pairs occurred 18.1–17.1 seconds before
stop during OCR, including its PID 219. It captured **no direct-reclaim event
in the final 17 seconds before the PSI stop**. This confirms that the CC
worker's OCR path can initiate reclaim, but does not show direct reclaim as
the immediate cause of this object-service stall. The object stall mechanism
remains unknown; available memory, low object usage, and no OOM do not
invalidate the measured PSI event. Post-run swap availability is not a
measurement of swap activity at the stop.

Temporal recorded 20 completed activities and no ActivityTaskFailed event.
After the guard requested cancellation, the execution reached COMPLETED with
business status `failed` / `activity_budget_exhausted`,
`processing_complete=false`, `canonical_accepted=false`, 28 registered pages,
and 11/11 registered selected components. Completion of component work is
therefore not a completed accepted document.

Failure evidence was sealed. The outer controller restored all 32 Deployments
to 0/0 with no owned Pods, removed the CC runtime Pod, retained its Bound PVC,
restored object service to 512Mi/Ready, and removed the tracer container.
There was no automatic retry. Historical runs, PVCs, and object prefixes were
left intact.

| Gate | Result |
| --- | --- |
| Exact CC identity, source projection, admission, 11 pre-inference gates | Passed |
| Wiki06 OCR components | 11/11 completed |
| Full five-document sequence and request-20 recycle | Not reached |
| Formal object full-PSI gate | Failed |
| Failure sealing and restoration | Passed |
| #44 normal-topology acceptance / closure | Not qualified |

Raw evidence remains at `/private/tmp/t09a-bounds-20260927-cc`,
`/private/tmp/t09a-bounds-object-20260927-cc`, and
`/private/tmp/t09a-normal-topology-20260927-cc`. Selected evidence here
includes the full direct-reclaim trace, its attribution summary, PSI onset,
Temporal reconciliation, and cleanup records.

The next measurement should target the object-service stall itself: capture
its swap usage, major faults, refault/reclaim counters, and memcg reclaim
tracepoints through finalization under the unchanged guard. A production or
acceptance-threshold change is not justified by CC alone.
