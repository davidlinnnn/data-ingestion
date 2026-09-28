# T09a bounded mixed-warm trial (2026-09-26)

The BK window passed its fixed mixed-warm scope on the existing
`kind-internal-a2a-vs6-local` cluster. It is one bounded run with the historical
Deployments held off and a temporary 1 GiB MinIO limit; it does not qualify the
normal all-Deployments-on operating envelope or establish a permanent MinIO
limit. Issue #44 remains open.

| Window | Identity | Result |
| --- | --- | --- |
| BI | `t09a-bounds-20260926-bi` | Stopped before inference: inherited supervisor rejected the valid `t09a-` run ID. No capacity conclusion. |
| BJ | `t09a-bounds-20260926-bj` | Stopped after workload start: inherited evidence mirror rejected the new phase path. Workload outcome unknown. |
| BK | `t09a-bounds-20260926-bk` | Passed the five-case mixed-warm sequence, Pod measurement contract, durable evidence export, and cleanup. |
| BL | `t09a-normal-topology-20260926-bl` | Admission-only: all 32 historical Deployments reached 1/1 Ready, with no OOM or full PSI increase; restored to zero. No workload claim. |
| BM | `t09a-bounds-20260926-bm` | Stopped before admission because the controller pre-created the runner output directory. No workload claim. |
| BN | `t09a-bounds-20260926-bn` | Stopped at admission because the inherited guard expected the 32 Deployments to remain at zero. No workload claim. |
| BO | `t09a-bounds-20260926-bo` | Passed outer admission with 32 Deployments active, then stopped before inference: the Pod projection omitted two required files. No workload claim. |
| BP | `t09a-bounds-20260926-bp` | Passed all 11 pre-inference gates and started the first warm Wiki 06 workload. Node full PSI reached 0.18 and the existing guard stopped the run. Workload failed; no normal-topology qualification. |
| BQ | `t09a-bounds-20260926-bq` | Passed admission and all 11 pre-inference gates. First warm Wiki 06 stopped at node full PSI 0.18. BQ worker cgroup also recorded full PSI; no normal-topology qualification. |
| BR | `t09a-bounds-20260926-br` | Passed admission, all 11 gates, and warm 06/07/08. Stopped on exact object-container full PSI during native; sealed failure evidence and restored services. No normal-topology qualification. |
| BS | `t09a-bounds-20260927-bs` | Stopped before Pod creation: relocated worker's admission still expected worker2's node UID. No workload or capacity conclusion. |
| BT | `t09a-bounds-20260927-bt` | Passed admission; 10/11 pre-inference gates passed. Image gate still expected worker2 after the worker moved to worker1. No inference or capacity conclusion. |
| BU | `t09a-bounds-20260927-bu` | Passed admission and 11/11 gates with worker1; stopped during first Wiki 06 on exact object-container full PSI with 32 historical Deployments on worker2. Failure evidence sealed and services restored. |

BK evidence: `/private/tmp/t09a-bounds-20260926-bk` and retained PVC
`t09a-bounds-bk-evidence-20260926`. The sequence was Wiki 06, YOLO 07,
AIMA 08, native, Wiki 06: 29 group requests, one recycle at request 20,
two parser generations. The Pod measurement contract reports workload success,
complete qualification and 1,482 continuous 250 ms cgroup samples with zero
memory, OOM, and full-PSI violations. The durable terminal manifest is
`PASS_CANDIDATE`; workload exit was 0, with no timeout or forced stop. The
outer VM guard observed at least 4,651,737,088 available bytes and a maximum
2,526,662,656-byte worker cgroup reading.

The object observer recorded 2,228 samples under the temporary 1 GiB limit,
maximum memory.current 739,414,016 bytes, zero `memory.events.max` increase,
and zero full-PSI increase. The outer cleanup deleted BK-owned Deployment and
ConfigMaps with UID preconditions, retained the BK evidence PVC, and exported
the controller evidence. MinIO was restored to 512Mi and Ready 1/1; the BK
Deployment is absent. BI and BJ evidence PVCs and object prefixes were retained.

The phase record was written with fresh-output equality pending. A post-run
comparison against the accepted current-v3 fresh results completed that check:
BK's full `document.json` SHA and `full_reference_graph_sha256` match AI's fresh
Wiki06 and native outputs and AJ's fresh YOLO07 and AIMA08 outputs. Both BK
Wiki06 runs also match each other. All five BK accepted records are verified
and processing-complete, and retain the reviewed v3 continuation identity.
This comparison reuses the already accepted AI/AJ fresh runs; BK did not repeat
fresh-mode executions.

#44 still needs an agreed sustainable object-service setting and qualification
with the normal Deployment set restored. Do not infer those from one 1 GiB
isolated window.

BO's outer admission passed 48 samples and 60 seconds continuous observation:
minimum available memory was 5,053,358,080 bytes against the existing
4,831,838,208-byte floor, with full PSI zero and VM OOM count zero. Nine of
11 Pod pre-inference gates passed. Configuration failed because the projected
workspace lacked `tests/pdf_processing/t09a_bounds/BI-MANIFEST.json`, and
workload imports failed because it lacked `pod_remote_evidence_bo.py`.
Workflow and inference were not started. The outer controller restored all
32 historical Deployments to zero and verified no owned Pods. MinIO returned
to 512Mi and Ready 1/1; the BO evidence PVC remains Bound. The 532 MinIO
observer samples had no max-event or full-PSI increase, but covered no
workload. See `/private/tmp/t09a-bounds-20260926-bo`,
`/private/tmp/t09a-bounds-object-20260926-bo`, and
`/private/tmp/t09a-normal-topology-20260926-bo`.

BP's local projected configuration and import gates passed, and its single
controlled runtime passed all 11 pre-inference gates. The first Wiki 06
workflow started at 13:41:08 UTC. Node full PSI avg10 rose from 0 to 0.18
at 13:41:18.211, causing the existing guard to stop the run at 13:41:18.212.
At the trigger, node MemAvailable was 3,821,957,120 bytes, above the BP
runtime floor of 1,610,612,736 bytes; worker cgroup memory was 1,507,434,496
bytes, with no recorded OOM or memory.events max increase. Direct reclaim and
compaction counters had risen before the trigger. The evidence supports real
node pressure but does not identify its source or establish that capacity is
sufficient. No threshold was relaxed and no retry occurred.

Temporal history shows the group Activity scheduled at 13:41:08.973 and no
ActivityTaskStarted or ActivityTaskFailed event before the guard stop. A
workflow cancellation was requested at 13:41:18.469; the Activity was then
cancel-requested and the workflow execution completed with a *failed* business
result (`activity_budget_exhausted`, `processing_complete=false`, zero
registered pages). This is not an ingestion success or evidence that an
Activity failure caused the PSI stop.

The interrupted worker had not written `worker-1/stopped.json`; BP's cleanup
reader raised `FileNotFoundError`, leaving terminal workload evidence
incomplete. Outer cleanup proved the supervisor and owned process group absent,
removed the BP Pod/Deployment/ConfigMaps, and retained the BP PVC. A separate
cluster read confirmed all 32 historical Deployment UIDs at zero replicas,
no BP Pod, BP PVC Bound, and object service back at 512Mi/Ready. The object
observer's 823 samples had no max-event or full-PSI increase. Evidence:
`/private/tmp/t09a-bounds-20260926-bp` and
`/private/tmp/t09a-bounds-object-20260926-bp`.

#44 remains open. Before another runtime, make the interrupted cleanup path
record an incomplete marker set without throwing and verify it locally. Do
not infer a supported normal-topology operating bound from BP.

The next-run BQ cleanup candidate now does that without changing BP. A local
regression reproduces BP's missing `stopped.json` and stray `worker-1.log`,
then verifies false cleanup proof flags and an `INCOMPLETE` durable terminal
record; the complete-marker case still passes. The outer failed-evidence
export path also required complete cleanup markers. The BQ candidate now
allows incomplete cleanup markers in *failure-evidence* finalization only,
while preserving success checks and supervisor-absence proof. A local test
passes; this has not been exercised in Kubernetes. See
`NEXT-MEASUREMENT-PLAN.md`.

BQ was one fresh controlled runtime with no automatic retry. Its outer
admission passed 48 samples and 60 seconds; the workload then started Wiki 06.
The last VM sample at 2026-09-26 16:38:21.492 UTC recorded node full-PSI
avg10 0.18, MemAvailable 3,735,699,456 bytes (above the unchanged
1,610,612,736-byte runtime floor), worker cgroup memory 1,762,557,952 bytes,
and zero worker OOM events. Node direct reclaim counters rose immediately
before the trigger. The guard stopped the run without retry.

The new read-only node observer recorded 416 half-second samples. Across its
window, node full-PSI total increased 47,172 microseconds. The exact BQ
worker container cgroup (Pod UID `35b411cc-a126-4b79-a82e-0e3c65c42a5d`,
container ID beginning `6a59821f`) increased 7,637 microseconds; only one
other container leaf showed a 1-microsecond increase. Parent cgroup counters
are hierarchical and must not be added to child counters. Node and cgroup PSI
are not an additive attribution ledger, so this identifies worker pressure
without proving that the worker alone caused the node event. The object
observer had 824 samples, peak memory.current 188,522,496 bytes, zero max
events and zero full-PSI increase under the temporary 1 GiB limit.

Temporal's group Activity was scheduled at 16:38:12.868, with no start or
failure event before the guard stop at 16:38:21.493. Cancellation was
requested at 16:38:21.866, and the execution completed at 16:38:21.875 with
business status `failed`, `activity_budget_exhausted`,
`processing_complete=false`, and zero registered pages. This is not ingestion
success or evidence that Activity failure caused the PSI stop.

The outer controller also detected the PSI guard and sent an interruption
while the runner was stopping. The supervisor did not finish terminal sealing:
the retained PVC contains `workload-exit.json.incomplete`, but no
`cleanup-complete.json`. The failure-evidence export therefore could not reach
the BQ-specific incomplete-marker handling. A second interruption is a
plausible contributor, not yet a proven sole cause. Outer force-stop proved
supervisor/process-group and scratch absence. Independent cluster verification
found all 32 historical Deployment UIDs at zero replicas, no BQ Pod, the BQ
PVC Bound, and object service back at 512Mi/Ready. See
`/private/tmp/t09a-bounds-20260926-bq`,
`/private/tmp/t09a-bounds-object-20260926-bq`, and
`/private/tmp/t09a-normal-topology-20260926-bq`.

#44 remains open. Before any further controlled runtime, make the outer
controller defer to an already recorded runner stop and preserve its bounded
cleanup deadline; prove the interruption/sealing path locally. Do not relax
the PSI guard or infer a supported normal-topology operating bound from BQ.

Local follow-up: `outer_guard_handoff.py` now implements that decision for a
future BR controller. A real subprocess regression first reproduced the
second-SIGINT interruption during a delayed terminal write, then passed after
the change; the no-runner-stop branch still sends SIGINT. The BR controller
candidate retains the existing 300/330-second terminate/kill deadlines. No
BR runtime had been prepared or started at that point.

BR ran once with a fresh identity and no automatic retry. Local checks passed
for the exact command, projected source imports/runtime contract, the two
outer handoff branches, incomplete-marker cleanup, failure-only export, and
node observer self-test. The pre-run cluster check found the expected kind
context, all 32 historical Deployment UIDs at zero, object service at
512Mi/Ready, and no BR Pod/PVC/output. BR passed all 11 pre-inference gates.

Warm 06, 07 and 08 produced completed business results with 28, 15 and 12
registered pages respectively. During the native segment the object-service
cgroup full-PSI total first increased from 0 to 9 microseconds at
2026-09-27 00:17:09 UTC. The unchanged zero-increase guard recorded
`object-service max/full-PSI event during mixed warm run` and stopped the run.
At the stop, object memory.current was 510,640,128 bytes of a temporary
1,073,741,824-byte limit; memory.events max and OOM stayed zero. The nearest
node sample had full-PSI avg10 zero, MemAvailable 3,688,820,736 bytes, worker
cgroup memory 1,705,410,560 bytes and zero OOM events. Node full-PSI avg10
rose later during cleanup, so the later 0.18 avg10 value did not cause this
guard stop. The separate node observer also read a 9-microsecond increase in
the exact object-container leaf cgroup in the half-second before the stop;
node full-PSI total increased 4 microseconds in that interval. These counters
are not additive. The full-PSI counter is a measured stall, but this evidence
does not establish why it occurred or justify changing the zero-event rule.

Native Temporal cancellation completed after the guard stop; its retained
`failure.json` records `CancelledError`. The fourth warm segment and parser
recycle proof were not reached. The outer guard detected pressure too but
recorded `outer_guard_handoff=runner_cleanup` and sent no second SIGINT.
The retained PVC and local `failure-evidence/` contain `workload-exit.json`,
`cleanup-complete.json` with all owned children/scratch absent, and a durable
`INCOMPLETE` terminal manifest. Forensic transport finalized as
`FAILURE_EVIDENCE_RETAINED`; this is a failed run, not an acceptance pass.
Independent post-run verification found all 32 historical UIDs at zero with
no owned pods, no BR Pod, BR PVC Bound, and object service restored to
512Mi/Ready. Sources: `/private/tmp/t09a-bounds-20260926-br`,
`/private/tmp/t09a-bounds-object-20260926-br`, and
`/private/tmp/t09a-normal-topology-20260926-br`.

#44 remains open. BR resolved the terminal-evidence loss seen in BQ but did
not complete the full mixed-warm workload under the existing pressure gate.
No further runtime was started at that point.

The live #44 candidate explicitly requires zero full-PSI violations. BK and
BR both pinned the worker and object service to worker2 with the same temporary
1 GiB object limit: BK completed with the 32 historical Deployments off and
zero object full PSI; BR stopped with those Deployments on, even though its
object memory peak (515,792,896 bytes) was below BK's (739,414,016 bytes).
This supports treating the normal topology as a distinct unqualified state;
it does not prove which colocated workload or kernel path produced the stall.
The object Deployment is currently pinned to worker2, uses PVC `object-data`,
and requests only 128Mi while limited to 512Mi at idle. Changing placement or
requests would be a different operating configuration, not a repeat of BR.

BS and BT tested a distinct placement with the object service and all 32
historical Deployments still pinned to worker2, and a fresh Q04 worker pinned
to the existing worker1 node. The pinned image was imported to worker1 with
the same manifest digest. BS was rejected before Pod creation because an
inherited admission check still pinned worker2's node UID. BT fixed that
exact identity check and passed admission, but its Pod pre-inference image gate
still pinned worker2; 10/11 gates passed and no inference began. Both runs
stopped without retry, the 32 Deployments returned to zero, and object
service returned to 512Mi/Ready. These failures do not measure capacity.
Focused local tests now cover worker1 UID/boot and the projected image-node
check; historical BS/BT files and evidence remain unchanged. BS created no
evidence PVC; BT's PVC remains Bound. Their controller records are at
`/private/tmp/t09a-normal-topology-20260927-bs` and
`/private/tmp/t09a-normal-topology-20260927-bt`.

BU used another fresh identity with both exact-node checks corrected. Local
projection, source/import, capacity contract, full command and cleanup tests
passed. Admission and all 11 Pod pre-inference gates passed. During first
Wiki 06, the exact object-container cgroup full-PSI total first rose to
21 microseconds and the unchanged zero-event guard stopped the run at
2026-09-27 00:48:58.658 UTC. At that sample object memory.current was
251,420,672 bytes of the temporary 1 GiB limit, with no max/OOM events; its
observed peak was 286,998,528 bytes. The worker1 node sample at the stop had
MemAvailable 3,774,865,408 bytes, full-PSI avg10 zero, worker cgroup
1,855,229,952 bytes and no OOM. The worker2 outer sample 0.34 seconds later
had MemAvailable 3,917,807,616 bytes, full-PSI avg10 zero and no OOM. The
node2 observer separately recorded exact object-leaf pressure; node full-PSI
total had also increased before the stop even though avg10 rounded to zero.
Cgroup and node counters are not additive, and the source of the preceding
node pressure is not identified.

Temporal history has 10 ActivityTaskCompleted events and no ActivityTaskFailed
event before the guard stop. Cancellation followed; execution COMPLETED with
business `status=failed`, `activity_budget_exhausted`,
`processing_complete=false` and `canonical_accepted=false`. The first Wiki
case did not produce an accepted result; later cases and parser recycle were
not reached. The retained PVC and local failure export contain workload exit,
complete cleanup markers and a durable `INCOMPLETE` manifest. Forensic
transport finalized `FAILURE_EVIDENCE_RETAINED`. Independent cluster checks
found all 32 historical Deployment UIDs at zero/no ready Pods, BU Pod absent,
BU PVC Bound, and object service 512Mi/Ready. Evidence:
`/private/tmp/t09a-bounds-20260927-bu`,
`/private/tmp/t09a-bounds-object-20260927-bu`, and
`/private/tmp/t09a-normal-topology-20260927-bu`.

The worker1 relocation did not prevent object cgroup full PSI on worker2.
It cannot be counted as a successful normal-topology configuration. Do not
increase the object limit on these data: BU used less than 0.3 GiB and had no
max/OOM event. No further runtime followed this failed controlled window.


## Measurement-scope correction after BU (2026-09-27)

A concurrent, read-only probe of worker1 and worker2 confirms that they share
one Linux VM memory domain. Raw readings are retained in
`shared-memory-domain-20260927.json`: identical boot ID, MemTotal
12,232,696 kB, MemAvailable 7,738,416 kB, and global full-PSI total
4,372,512 microseconds. Both Docker memory limits are unset and both node
cgroup roots report `memory.max=max`. Their private cgroup namespaces differ,
as do their root cgroup full-PSI totals (117,152 versus 3,523,729 microseconds).

Therefore historical fields named node PSI/MemAvailable are VM-wide readings,
not independent node capacity measurements. Worker1 relocation tested Pod
placement, **not memory-domain isolation**. Any earlier implication that it
isolated worker2 memory pressure is withdrawn. The observer scans only its
visible node cgroup subtree while reading global VM PSI; it cannot attribute
all global pressure to that node or exhaustively explain it. Counter deltas
across scopes must not be subtracted as an attribution budget.

A local replay through the actual BU `verify_sample` function (with unrelated
base guards stubbed) accepts an unchanged object sample and rejects the first
real increase: full PSI +21 microseconds, max +0, all OOM counters zero,
memory.current 251,420,672 bytes of 1 GiB. The stop condition was real under
the existing zero-event rule, not an avg10 parsing error. Linux documents
that microsecond totals can capture stalls too short to affect averages:
https://docs.kernel.org/accounting/psi.html . This replay does not rerun
inference or validate the unrelated base guards.

Known causal sequence remains object PSI observation -> controller stop ->
workflow cancellation -> failed business result. No ActivityTaskFailed
preceded the stop. The allocation/reclaim mechanism and originating workload
behind that brief stall remain unknown. Spare MemAvailable and no OOM do not
prove sufficient capacity or make the guard false. This diagnostic made no
cluster mutations and launched no workload; the prior restored state remains
unchanged by it. Q04/#51 acceptance is not reopened; #44 remains unqualified.


Existing BU samples do contain reclaim counters. The derived, reproducible
interval deltas are in `bu-pre-stop-reclaim.json`. In the intervals ending
1.075, 0.811, 0.553 and 0.002 seconds before stop, `allocstall_movable`
increased by 32, 88, 14 and 17; `pgscan_direct` increased by 2,048, 5,696,
896 and 1,088. Background file reclaim also increased. This supports actual
VM allocation stalls/direct reclaim near the object PSI event, rather than
an inference from MemAvailable alone. It does not identify the allocating
process, prove which reclaim operation stalled the object process, or prove
that adding memory is necessary. Compaction counters did not change in these
last two seconds. The historical scope names are retained in raw evidence.


## BU process attribution follow-up

`diagnose_bu_overlap.py /private/tmp/t09a-bounds-20260927-bu` replays the
retained process and VM samples without cluster access. Its assertions pass;
derived results are in `bu-process-overlap.json`. The growing child is PID
219, matched to the recorded lifecycle-child OCR command. In the last 1.52
seconds before stop its anonymous RSS grows from 36,982,784 to a sampled
peak of 561,590,272 bytes. Warm parser PID 131 remains at 1,156,014,080
anonymous bytes with unchanged CPU ticks throughout these samples.
Temporal schedules `component_ocr` for `#/pictures/0` at 00:48:56.785 UTC,
before the 00:48:58.658 stop. Thus the active allocation burst is OCR,
not a currently executing warm-parser inference. The idle parser's retained
memory overlaps that burst.

Over the corresponding VM sample window, direct scan/steal both increase
9,728 and background scan increases 26,496. The worker leaf's matching
memory.stat reclaim counters do not increase. Those leaf counters describe
reclaimed pages charged to the cgroup; they do not establish which task
initiated VM reclaim. This is temporal attribution of an allocation burst,
not proof that OCR alone caused the object-service stall. The exact object
and worker leaf max/high/OOM events remain zero; historical parent limits
and per-task reclaim stacks are unavailable, so ancestor effects and other
VM activity are not ruled out.

Code confirms enrichment constructs a fresh OCR Execution independently of
the warm parser. Killing that parser before OCR would alter the tested
cross-document request-20 lifetime; do not apply that as an incidental fix.
The existing AR phase instrumentation is available, but AR never reached
inference and AS lost its hook through descendant PYTHONPATH replacement.
Neither supplies the missing phase attribution for BU. A future targeted
OCR probe must first demonstrate its markers in the actual descendant
launch path. No new runtime, acceptance change, or production change was
made during this follow-up.


## BV bounded OCR diagnostic (not an acceptance run)

One network-disabled container used the existing Linux image, the accepted
BK Wiki06 document and fixture06 picture0, with the production Execution
and lifecycle-child launch path. The 32 held Deployments were independently
verified off and the object service 512Mi/Ready; neither was changed. Hard
memory limit was 5 GiB, stop watermark 4 GiB, VM admission floor 4.5 GiB,
runtime floor 1.5 GiB, workload deadline 120 seconds and outer deadline 150.
The diagnostic additionally stopped on any VM/container full-PSI total
increase. **That total-based VM/container rule is stricter than the historical
VM avg10 guard; it is not an unchanged acceptance policy.** No acceptance
standard was modified. BV cannot be counted as a failed full #44 matrix run.

BV stopped in the plain baseline, about one second after startup. Retained
samples show VM full PSI +12,362 us and diagnostic cgroup full PSI +12,743 us,
with both avg10 fields still zero. The trigger memory.current was 524,062,720
bytes, VM MemAvailable 7,604,617,216 bytes, and max/OOM events zero. There was
no warm parser in this diagnostic. This demonstrates that a local cgroup
stall can occur without warm-parser overlap or the 32 active Deployments;
it does not prove the same low-level cause as BU, nor rule out background
VM effects. OCR logs show detection/classification/recognition ONNX models
being loaded before the stop, but do not locate the stall within initialization
versus inference.

The observed variant never started: ordered phase markers and output
equivalence were **not obtained**. Baseline-first ordering was unsuitable
for a fail-stop phase diagnostic; preserve this limitation rather than
claiming the planned measurement succeeded. No retry occurred. The exact
owned container exited and was removed; raw results remain under
`/private/tmp/t09a-ocr-phase-20260927-bv`, with selected evidence retained in
`ocr-phase-probe/bv-evidence`.

A cheap local regression now exercises the actual supervisor environment
assembly and actual lifecycle launcher with a no-inference fake OCR module.
It proves that the workspace/src startup hook produces `ocr_enter` despite
supervisor PYTHONPATH replacement. Run
`python3 tests/pdf_processing/t09a_bounds/ocr-phase-probe/test_hook.py`.
This verifies marker transport only, not real OCR phase coverage or output
equivalence. The preserved AS observer is reused with imports/document markers;
no production source or historical runner was edited.


## BW observed-first OCR diagnostic

User-authorized BW ran once with the same BV diagnostic limits and isolated
fixture scope, observed variant first. The actual supervisor/lifecycle/hook
transport regression passed before launch. The real OCR child emitted seven
ordered stages: entry, imports ready, document ready, crop ready, engine
start, engine ready, inference start. No inference-ready or result-written
marker exists. The plain comparison never started, so output equivalence
remains unverified. This is diagnostic evidence, not #44 acceptance.

PSS at entry/imports/document/crop/engine-ready was respectively 16,206 /
82,724 / 90,932 / 118,312 / 187,708 KiB. The last clean PSI sample was at
1790475008.730323; engine ready at 1790475008.796534; inference start at
1790475008.798784; the trigger sample at 1790475008.833052. Thus the stall
is bounded to a 102.73 ms interval spanning late initialization and early
inference, with the trigger sampled 34.27 ms after inference began. The
sampling does **not** prove whether the stall itself preceded or followed
inference entry, nor identify an ONNX operator or allocator.

In that interval global full PSI rose 2,499 us and diagnostic cgroup full PSI
3,190 us; both avg10 values remained zero. Cgroup memory increased from
114,462,720 to 319,356,928 bytes. Trigger VM available memory was
7,627,632,640 bytes, with zero OOM/max events. As in BV, the total-based
abort is an additional diagnostic rule, not the historical VM avg10 gate.
PSS and cgroup charges are different measurements and must not be subtracted
as a memory accounting identity.

BW fail-stopped and did not retry. Independent cleanup verified its exact
container absent, all 32 held Deployment identities off, object service
512Mi/Ready. Raw artifacts: `/private/tmp/t09a-ocr-phase-20260927-bw`;
retained script, markers, samples, logs and cleanup:
`ocr-phase-probe/bw-evidence`. No producer code, cluster setting, or
acceptance criterion changed.


## Root cause isolated: NumPy hugepage advice triggers synchronous compaction

The installed RapidOCR already sets `enable_cpu_mem_arena: false`; toggling
that setting would not address this reproduction. The VM has THP enabled
`always` and defrag set to `madvise`. At inspection, its Normal zone had no
free order-9/order-10 blocks despite substantial aggregate free memory.
That is a fragmentation snapshot, not a historical proof of BU zone state.

Four distinct bounded experiments tested one control at a time, using the
same Wiki06 picture0 and stricter diagnostic total-PSI abort. None retried
a failed identity, changed host settings, or activated the 32 Deployments:

| Run | Control | Result | VM / cgroup full PSI delta | Compaction stalls |
| --- | --- | --- | --- | --- |
| BX | Disable THP only in diagnostic process/descendants | OCR + plain/observed comparison complete | 0 / 0 us | Not sampled |
| BY | Restore process THP after BX warmed caches | Stop at inference entry | 26,595 / 29,382 us | 12 |
| BZ | THP enabled, only `NUMPY_MADVISE_HUGEPAGE=0` | OCR + comparison complete | 0 / 0 us | 0 |
| CA | Actual OCR-only launcher fix; parent policy unchanged | OCR + comparison complete | 0 / 0 us | 0 |

BX/BZ/CA reports and crop bytes also match one another exactly after removing
elapsed time. BZ/CA still record THP allocations (631/658 VM-wide), so the
successful control does not require eliminating every hugepage. The evidence
supports **NumPy's hugepage advice entering synchronous compaction during
OCR allocations on this VM** as the cause of this isolated stop. The THP
reversal makes a warmed-file-cache-only explanation insufficient. VM counters
are global, and no kernel stack was captured; the exact allocation/operator
and whether every historical BU/BR stop had this same cause remain unproven.

This mechanism matches the documented Linux `defrag=madvise` behavior:
[Linux THP controls](https://docs.kernel.org/admin-guide/mm/transhuge.html).
NumPy documents that its advice can be disabled before import:
[NumPy global state](https://numpy.org/doc/2.0/reference/global_state.html).
The advice is a performance policy, not an OCR/model acceptance threshold.
No memory increase or cluster replacement is justified by this reproduction.

The minimal fix in `src/pdf_processing/execution.py` sets that variable only
in the environment of `pdf_processing.ocr` children, before Python/NumPy
imports, and preserves it through the lifecycle wrapper. Parent and non-OCR
children retain their environment; parser lifetime, model files, render scale,
and guards are unchanged. The real-child regression first failed in both
launch paths, then passed after the fix. Three cancellation/cleanup tests and
three warm-continuity tests pass. An initial test command used the wrong
class name for the cancellation tests; the corrected invocation passed.
Standards and Spec reviews of `c53ac6b...d1ed706` found no actionable issues.

Run `python3 tests/pdf_processing/t09a_bounds/ocr-phase-probe/verify_thp_diagnosis.py`
to recheck the retained comparisons. Each BX/BY/BZ/CA exact container is
independently absent; all 32 held Deployments are off and object service
512Mi/Ready. Evidence is under `ocr-phase-probe/{bx,by,bz,ca}-evidence` and
`/private/tmp/t09a-ocr-phase-20260927-{bx,by,bz,ca}`.

### Acceptance boundary after the fix

| Scope | Status |
| --- | --- |
| Q04/#51 historical accepted baseline | Remains recorded; not reclassified by diagnostics |
| OCR-only launch policy, wrapper and cleanup | Regression passed |
| Wiki06 picture0 OCR with actual fix | Complete, zero PSI/compaction stalls, matching outputs |
| New source full Q04 matrix / normal 32-Deployment #44 workload | Not run |
| Sustainable permanent object sizing / #44 closure | Not established |

This is a tested fix for the isolated reproducer, not permission to close
#44 or claim the changed producer passed the full matrix. A next controlled
acceptance must project the new execution source in a fresh producer/bundle
contract and retain the original formal guards. Do not run a historical
frozen manifest against the changed source or silently rewrite old manifests.


## CB full-topology result after OCR fix

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

## CC direct-reclaim attribution (2026-09-27)

CC preserved the CB workload and guards under a new identity, with a
host-PID/cgroup direct-reclaim trace. It again failed the formal object
full-PSI gate, now just after all 11 Wiki06 OCR components completed and
before finalization started. The CC worker Pod did initiate reclaim during
OCR, but the last traced direct-reclaim event was 17.1 seconds before the
object PSI stop; VM reclaim and compaction counters were flat at the stop.
Thus direct reclaim is real but is not established as this stop's immediate
cause. The object stall mechanism remains unknown. Temporal's COMPLETED
execution has business status failed, and #44 remains unqualified. Failure
evidence, held-Deployment restoration, object restoration, and tracer cleanup
passed. See `normal-topology-cc/first-window-evidence/RESULTS.md`.

## CD object-stall measurement (2026-09-27)

Four full fixture results passed local checks, but the final Wiki06 stopped
with object full PSI +417us. No immediate swap/direct-reclaim increase was
observed; object file refaults and MinIO read-wait stacks narrow the hypothesis
to cache/read pressure, without proving thread-to-object attribution. Planned
recycle was reached. Failure sealing and restoration passed; #44 remains open.
See `normal-topology-cd/first-window-evidence/RESULTS.md`.

## CG bounded normal-topology success (2026-09-27)

The same fixed five-document sequence passed all formal guards with 32 held
Deployments active, the OCR launch-policy fix, and temporary object1Gi. Full
JSON and reviewed checks equal the accepted fresh references for all five
results. 29 group requests, one planned recycle and final completion passed.
Object full PSI and max-event deltas were zero. Independent cleanup passed.
No new production fix occurred between CD and CG: this single success does not
resolve earlier intermittent object PSI failures or establish permanent object
sizing. #44 remains open. See `normal-topology-cg/first-window-evidence/RESULTS.md`.
