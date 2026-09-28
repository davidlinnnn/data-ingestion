# CS: approved object-PSI diagnostic stopped by unchanged VM guard

User explicitly approved CR/NEXT-DECISION.md. CS ran once, no automatic retry,
with the same workload/producer/image/resources as CR. Only the object stop rule
changed: cumulative full PSI was retained as diagnostic, positive object full
avg10 remained fatal. VM/worker/OOM/max/memory/deadline guards were unchanged.
This is a functional diagnostic, never an original zero-event qualification.

## Result

125second protection admission and all11 pre-inference gates passed. The first
Wiki06 finished28page registrations, then entered component_ocr. VM full avg10
reached0.18 and stopped the run. Final business result is failed with
activity_budget_exhausted,processing_complete=false,28pages,0registered of11
selected components. No full document/checks equality or full29group/recycle
claim is possible; remaining four fixtures were not started.

Object full PSI117us was retained and allowed, with maximum object full avg10=0.
The new rule therefore behaved as approved. No further guard was weakened.
The actual retained samples pass the new object checker, while the real VM
trigger is rejected by the unchanged base guard (`verify_failure.py` PASS).

| Gate | CS result |
| --- | --- |
|5 diagnostic guard tests +6 existing protection tests | Passed |
|Runtime image imports / source projection /125s admission /11gates | Passed |
|Approved object diagnostic rule | Passed:117us retained,avg10=0 |
|Original zero-object-PSI rule | Would fail; not revised retrospectively |
|VM PSI rule | Failed:full avg10=0.18 |
|Wiki06 complete ingestion | Failed after cancellation in component OCR |
|Remaining fixtures /full equality /29groups /recycle | Not established |
|Independent cleanup | Passed |

## Causal evidence

At16:18:44.470277–16:18:44.732485 UTC the VM full-total counter increased22,894us.
The trace contains196 identified entry calls in that interval. Of these173
allocator entries came from18threads of TGID1018098 in the exact CS worker Pod
8ff20522-117c-4690-9ec2-4c09c4d71bbe/container76aef3e7...;89 retain an anonymous
page-fault stack containing vma_alloc_zeroed_movable_folio. Other calls include
kswapd and other VM processes; counts are not a per-process share of stall time.
Do not assign the whole global-pressure duration to one process.

The same interval has VM allocstall_movable+183,direct scans+11,968,background
scans+13,440,compaction+0. This supports allocator/direct-reclaim pressure rather
than the previously fixed OCR THP-compaction mechanism. No OOM or observed
object/worker hard-limit event occurred. The worker cgroup's own avg10 was0 at
the controller trigger, while the shared VM avg10 was0.18.

-16:18:44.752690: first retained object full PSI117us,avg10=0.
-16:18:45.035057: VM avg10 still0; the diagnostic continues.
-16:18:45.335335: VM avg10 updates to0.18; controller stops.
-16:18:45.436027: Temporal cancellation requested.
-16:18:45.481745: execution COMPLETED with business failure.

There was no preceding ActivityTaskFailed. VM total did not increase in the last
sample interval: avg10 updated after the preceding pressure wave. The terminal
activity-budget label follows guard cancellation and does not prove an independent
timeout. Trace identity coverage resolved all839 captured entries and buffers
reported zero dropped/overrun events. Two exact-object allocator calls are also
retained; they are not the reason the new diagnostic stopped.

## Limits of attribution and next focused experiment

Temporal identifies the active stage as component_ocr. The nearby process sample
shows a warm parser (~1.37GiB RSS) plus a newly created owned child. However, host
TGID→container PID mapping was not collected, so the precise child/library/pool
responsible for the173calls is not conclusively identified. No Python allocation
stack, allocation order or exact pool provenance was captured.

Read-only inspection of the actual runtime image found RapidOCR intra/inter-op
thread settings=-1, leaving ONNX SessionOptions defaults; production calls
RapidOCR()(crop) without an explicit thread bound. This makes native thread-pool
allocation a falsifiable candidate, not a proved cause. The next step should
isolate this exact component and capture PID-namespace mapping plus actual pool
size; only then compare a bounded thread setting while retaining identical crop,
OCR output and all remaining guards. Keep the warm-parser overlap represented.
Do not rerun the whole matrix or relax VM PSI to conceal this failure.

## Verification and restoration

Preparation0d7e9ad; scope-wording correction061d9de. Standards0; Spec1 wording
finding corrected and re-review0. Guard tests isolated positive-average recovery,
max/OOM,VM/worker limits,telemetry loss and deadline behavior; actual CR89us was
red under old rule and green/preserved under CS. Protection code is unchanged
apart from run-owned names. `verify_failure.py` replays CS's real guard outcome.

Object1479samples,max gap0.265782s,max352,731,136bytes; worker max2,281,553,920;
minimum VM available3,261,558,784bytes,at-stop3,289,587,712. These measurements do
not establish pressure-free capacity. Systemd property/override and all raw low
values restored;32Deployments0/no owned Pods,object512Mi/Ready/health200,
worker/parser/scratch/observer/tracers/private trace instances absent. Manager
lock absent,PVC Bound,historical prefixes/PVCs retained.

Raw evidence remains in `/private/tmp/t09a-bounds-20260928-cs`,
`/private/tmp/t09a-bounds-object-20260928-cs`,
`/private/tmp/t09a-normal-topology-20260928-cs`.
#44 remains open,#45 blocked,#51's accepted history unchanged. This diagnostic
failed its remaining guards; no integration-completion or closing claim is made.
Issue text remains a local draft for unified publication.
