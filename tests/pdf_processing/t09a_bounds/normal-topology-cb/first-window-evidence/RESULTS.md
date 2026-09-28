# CB result: OCR-only fix does not yet qualify normal topology

CB (`t09a-bounds-20260927-cb`, source candidate `a96fd8f`) ran once with
all 32 recorded Deployments active. Admission and 11/11 pre-inference gates
passed, including the new projected execution producer/bundle contract.
Wiki06 parsed and assembled 28 pages, then started picture0 OCR. No complete
accepted document was produced; later sequence members and request-20 recycle
were not reached. The historical parser progress sample still said assembly;
Temporal history and process telemetry establish that OCR was already active.

The object-service guard stopped at 2026-09-27 03:07:53.766 UTC. The retained
object sample 137 ms earlier has full PSI total +34 us, memory.current
265,441,280 of 1,073,741,824 bytes, zero max/OOM events, and avg10 zero.
Worker memory.current was 2,207,027,200 bytes; VM MemAvailable 3,499,929,600,
with zero OOM and avg10 zero. These values do not prove adequate capacity or
justify ignoring the real object PSI event.

In the 1.655-second pre-stop VM sample interval, compact_stall and
thp_fault_alloc did not rise, but allocstall_movable rose 133 and
pgscan_direct rose 8,512. OCR child PID219 grew while warm parser PID131
was idle at 1,164,300,288 anonymous bytes. The previously isolated synchronous
THP compaction mechanism was not observed in this interval; a separate
remaining direct-reclaim pressure path persists under the full topology.
Neither the allocating task's kernel stack nor the object stall's exact
cause is proven. The isolated NumPy fix is insufficient to certify #44.

No ActivityTaskFailed preceded cancellation. Temporal execution COMPLETED
with business status failed / activity_budget_exhausted,
processing_complete=false, canonical_accepted=false, 28 registered pages,
zero of 11 selected OCR components registered. This is a guard-driven abort,
not ingestion success or evidence that retries exhausted first.

Complete cleanup markers, workload exit, durable INCOMPLETE terminal and
FAILURE_EVIDENCE_RETAINED export are present. The outer controller restored
32 Deployments to zero/no owned Pods, returned object service to 512Mi/Ready,
and reported no restoration errors. Independent checks confirm CB Pod absent
and CB PVC Bound. Historical PVCs/prefixes remain preserved. No retry followed.

Raw evidence:
- `/private/tmp/t09a-bounds-20260927-cb`
- `/private/tmp/t09a-bounds-object-20260927-cb`
- `/private/tmp/t09a-normal-topology-20260927-cb`

Selected evidence and decoded history summary are in this directory.

| Gate | Result |
| --- | --- |
| Exact command / projected configuration / local imports | Passed |
| 32-service readiness, admission, 11 pre-inference gates | Passed |
| Fixed full five-document sequence and request-20 recycle | Not completed |
| Formal object PSI gate | Failed |
| Failure sealing and restoration | Passed |
| #44 normal-topology acceptance / closure | Not qualified |

Pre-runtime review found an ambiguous Kubernetes patch-response cleanup gap.
CB now records the authorized identity before activation; an applied-then-
timeout regression reproduces and verifies the correction. Historical
controllers were not rewritten.


Post-cleanup read-only inspection of both surviving kind-node/kubelet/burstable
ancestor chains found memory.high=max throughout; the kubepods parent has
memory.max=12,526,280,704 bytes. All inspected memory.events.local high/max/OOM
counters are zero. Hierarchical max counters contain historical descendant
events and are not evidence of a CB ancestor-limit breach. These readings
narrow the surviving-ancestor hypothesis but do not reconstruct removed Pod
cgroups or identify the allocating task. See post-cleanup-ancestor-limits.json.
