# CR: policy persistence fixed; allocator PSI still stops final fixture

CR ran once, no retries, with the approved768MiB best-effort memory.low chain,
temporary object/Pod1Gi and all original resource/deadline guards. It added only
manager-owned MemoryLow for the Burstable slice and125second persistence admission.
No production code, permanent configuration or acceptance criterion changed.

## What was fixed

A real disposable systemd slice reproduced CQ's setup pattern: raw memory.low8MiB
became0 after an unrelated CPUWeight update; setting systemd MemoryLow8MiB made
the value survive the equivalent update. The owned slice/service and overrides
were removed. This proves the failure mode, not the identity of CQ's historical
writer. CR's manager/kernel values survived125.035613seconds of admission;
all2,459 object samples retained the kernel protection, including the workload stop. CQ's loss-of-protection
symptom did not recur.

Preparation e9a401c; reviewed early-admission cleanup correction a39139b.
Six focused tests passed, along with actual image imports/offline contract.
Standards0 findings; Spec1 early-cleanup gap fixed, re-review0. The actual cleanup
verifier also passed before runtime with no PVC/observer yet (`pre-runtime-cleanup.json`).

## Exact stopping cause

-15:58:11.752939 UTC: preceding object sample, full PSI0.
-15:58:11.849926: exact MinIO TGID951727/TID951846 enters psi_memstall_enter from
 `__alloc_pages_noprof`, through `ext4_readdir -> ext4_bread -> __getblk_slow ->
 __filemap_get_folio -> __folio_alloc_noprof`.
-15:58:12.004648: first retained object full PSI89us.
-15:58:12.064540: controller stop on the original object max/full-PSI guard.
-15:58:12.437339: final Wiki06 Temporal cancellation requested.
-15:58:12.456077: execution COMPLETED, business failed/activity_budget_exhausted,
 processing_complete=false,5registered pages. No preceding ActivityTaskFailed.

This is an allocator stall while reading directory metadata, distinct from CP's
workingset read/wait stack and CK's cgroup charge-limit stack. During the252ms
onset interval VM allocstall_movable increased4, direct scans500, background
scans9,003; compaction/OOM increments0. These counters plus the inline allocation
caller support direct reclaim in the global allocator, not a demonstrated local
hard-limit stall or recurrence of the OCR THP-compaction bug. Kernel reference:
[page allocator](https://raw.githubusercontent.com/torvalds/linux/v6.12/mm/page_alloc.c).

At onset object682,225,664 bytes (~650.6MiB), below768MiB low and1Gi max. All six
observed levels retained low768MiB, min0 and their prior max values; high/max/OOM
counters remained0. Leaf local low events increased30 and Pod local low1 before
onset, indicating reclaim below the low boundary. [Kernel memory.events contract](https://www.kernel.org/doc/html/v6.12/admin-guide/cgroup-v2.html)
defines that counter explicitly; memory.low is best effort, not a no-stall guarantee.
Do not infer that increasing memory.low/max will solve this from these results.
The exact allocation order/zone and directory key were not captured.

Trace retained19 target calls:1before stop,18after stop. One earlier call at
15:54:47.486796/TID970143 lacks task identity; it cannot be assigned to MinIO or
used as proof that every stall is attributed. Trace buffers report no dropped
or overrun events. The positively identified pre-stop call is retained separately
from cleanup-period calls. Object PSI totals429us through cleanup.

## Acceptance matrix

| Gate | CR result |
| --- | --- |
|125second persistence /11pre-inference gates | Passed |
|Wiki06,YOLO07,AIMA08,native51 | Complete; all four full document/checks JSON equal accepted AI/AJ fresh references |
|Final Wiki06 | Failed after guard cancellation;5pages registered |
|Full29groups / final recycle proof | Not established by this run |
|Object zero-full-PSI criterion | Failed:89us first trigger,429us through cleanup |
|OOM / observed high/max events | None |
|Failure sealing / independent restoration | Passed |

Object max732,749,824 bytes; max sampling gap0.263398s. Worker max2,757,246,976
bytes; minimum measured VM available2,693,722,112,at-stop2,974,203,904 bytes.
These are observations, not universal capacity guarantees. `verify_failure.py`
passes using the actual runner guard and retained causal ordering. Complete
four-fixture equality is recorded in `fresh-output-comparison.json`.

## Restoration and disposition

Independent readback confirms original systemd MemoryLow and its override file,
all surviving journaled raw low values,32Deployments off/no owned Pods,
object512Mi/Ready/health200, worker/observer/diagnostic containers/private trace
instances absent. Supervisor proves parser/scratch absence. CR PVC Bound and
all historical prefixes/PVCs retained. Raw directories:
`/private/tmp/t09a-bounds-20260927-cr`,
`/private/tmp/t09a-bounds-object-20260927-cr`,
`/private/tmp/t09a-normal-topology-20260927-cr`.

The best-effort protection candidate does not satisfy the existing zero-PSI
criterion. Do not rerun it unchanged or promote it to a permanent fix. CP/CR
business failures follow controller cancellation; whether the interrupted fixture
would otherwise complete correctly remains unmeasured. A proposed next functional
diagnostic is documented in `../NEXT-DECISION.md`; it changes a stop criterion
and therefore requires the user's critical decision before execution. #44 remains
open,#45 blocked,#51's historical acceptance unchanged. Ticket text stays a draft.
