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
