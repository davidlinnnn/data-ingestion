## Current result: bounded normal-topology sequence passed; #44 remains open

CG (`t09a-bounds-20260927-cg`) completed one controlled window with all 32 recorded Deployments active, the OCR-only NumPy hugepage policy fix, temporary object1Gi, and unchanged formal memory/OOM/PSI/deadline guards.

- Five required-work results completed in [06,07,08,native,06] order. Full document JSON and complete reviewed checks equal the accepted AI/AJ fresh references, without removing fields. This supplies the post-run equality check that the raw phase record left pending.
- 29 group requests, one parser recycle at request20, two parser generations, and successful post-recycle completion.
- Worker cgroup maximum2,608,893,952 bytes; minimum VM MemAvailable2,849,722,368 bytes; formal workload measurement1,441 samples with no violations. Object maximum734,961,664 bytes; zero max-event or full-PSI increase across2,224 samples.
- Runner exit0, durable PASS_CANDIDATE terminal, complete cleanup. Independent verification: exact32 Deployments0/0/no owned Pods, object512Mi/Ready, CG runtime absent, PVC Bound, all diagnostic containers/private trace instances absent. Historical prefixes/PVCs preserved.

CD immediately before this still failed late in final Wiki06 on object full PSI+417us. Object swap/max/OOM were zero; read/refault evidence suggests file-cache pressure, but direct attribution of that exact historical stall remains unproven. Temporal business failure followed guard cancellation, with no preceding ActivityTaskFailed. The standalone idle/read-only probes did not reproduce it. CG captured373 VM memory-stall calls and none in the exact target object container.

**No production/configuration fix occurred between CD and CG.** The passing window therefore establishes a successful bounded execution, not resolution of intermittent PSI or a sustainable permanent object limit. Do not close#44 or unblock#45 on this alone. #51's historical acceptance remains unchanged. Input ceilings beyond these fixtures remain unqualified.

Evidence: `tests/pdf_processing/t09a_bounds/normal-topology-{cd,cg}/first-window-evidence/RESULTS.md`. Local check: `python3 tests/pdf_processing/t09a_bounds/normal-topology-cg/verify_results.py`. Four targeted activation/interruption/OCR-policy regressions passed; real tracer startup/cleanup probes passed after fixing close-before-switch ordering.

Do not repeat an unchanged full matrix just to collect another pass. Keep the current guards and resting topology while deciding the remaining sustainable-scope requirement; changes to the zero-event criterion or permanent resource setting need an explicit decision.


### Follow-up: idle object-pressure cause isolated (CH–CN)

A short read-only probe now reproduced real MinIO server PSI at resting512MiB:
exact task/cgroup stacks show ext4 directory reads entering `try_charge_memcg`.
A same-process contrast raised both container and Pod caps temporarily to1GiB:
30s of continued cache work produced no new PSI/direct reclaim. Restoring512MiB
brought PSI back within0.51s, with Pod-local max events+2 while the leaf max counter
stayed unchanged. This exposes an ancestor-event diagnostic blind spot; the
formal PSI stop still works. Effective limits were restored and the32-off /
object512Mi/Ready/health200 / no-tracer cleanup checks passed.

CJ is excluded because our version query contaminated it; CL is excluded because
its leaf-only limit change left the Pod capped512MiB. CK/CM/CN supply the corrected
attribution and reversal. The offline evidence check passes. No production code,
acceptance criterion, permanent resource configuration or historical evidence
was changed. These results explain the idle512MiB mechanism, **not the exact
CD1GiB stop**; #44 remains open, #45 blocked, #51 unchanged. Next use ancestor-aware
short measurement under the original scope before considering another full run.
Evidence: `tests/pdf_processing/t09a_bounds/object-stall-probe/RESULTS.md`.


### CO follow-up: normal-topology short control completed

With all32 Deployments Ready and both exact object/Pod caps temporarily1GiB,
30s idle plus20 preserved-object reads (4,066,907 bytes) produced no object/Pod
PSI, max or OOM increments. Direct tracing captured36 other VM stalls and none
in the exact object container; there was no VM direct/background reclaim. This
short control did not reproduce CD's mixed-workload pressure and is not a fix.
Local cap/trigger-persistence checks and retained guard/trace/cleanup verification
passed. Both limits restored512Mi, all32 returned off, service health200, and all
owned diagnostics were removed. No producer/configuration/acceptance change.
Next, if executing a further runtime, use the actual mixed producer once with
ancestor plus direct-caller evidence; stop standalone idle/read variants.
#44/#45/#51 status conclusions remain unchanged. Evidence: `object-stall-probe/co-normal/RESULTS.md`.


### CP: mixed-workload stop classified by direct evidence

CP reproduced the unchanged object PSI guard during native51. Exact MinIO
read_pages/folio_wait_bit_common stacks occurred before the155us onset sample,
then controller stop, then Temporal cancellation. At onset object~472MiB/1Gi,
all observed ancestor high/max/OOM events0, swap0; earlier reclaim/refault activity
supports workingset page-read waits. This is distinct from the resting512MiB
charge-limit mechanism. No ActivityTaskFailed preceded cancellation; native
COMPLETED only at execution level, with business failed/activity_budget_exhausted,
processing_complete=false and15pages. Final06 did not start.

The first three full document/check graphs match accepted fresh results. Full
mixed/recycle qualification failed this run. Trigger/stack/guard/Temporal checks
and independent cleanup passed;32off, object512Mi/health200, runtime/tracers absent,
PVC Bound and prefixes retained. Preparation:f0d7578, Standards0/Spec0 review.

Next candidate is reversible, ancestor-effective memory.low working-set protection
(trial768MiB), retaining memory.max1Gi and all guards; not yet applied or qualified.
No new hardware or relaxed PSI rule is proposed. #44 remains open,#45 blocked,#51
unchanged. Evidence: normal-topology-cp/first-window-evidence/RESULTS.md.

### CQ: temporary protection setup rejected before workload

CQ applied768MiB memory.low along seven ancestors, but the Burstable ancestor
reset0 after56.64s. All11 pre-inference gates passed; the unchanged protection
guard stopped before workload launch. No workflows/functional results, object
PSI0 and target calls0; this does not test the remedy's effectiveness. Systemd
MemoryLow=0 plus the upstream one-minute QoS update supports a reconciliation
hypothesis, not proof of the writing process. Next correct policy ownership and
verify persistence before any further full workload; no raw-write retry.

Four helper regressions, actual image imports and retained actual-guard replay
pass. Standards0; Spec timeout race fixed and re-review0. Independent cleanup
passed including original memory.low values,32off/object512Mi/health200 and no
owned diagnostics. PVC/prefix retained. Commits bee73bd,44be657 plus evidence.
#44 remains open,#45 blocked,#51 unchanged. Evidence: normal-topology-cq/first-window-evidence/RESULTS.md.

### CR: policy ownership fixed; full run still rejected

CR manager-owned protection survived125s admission and all2,459 samples. Four
fixtures completed with full document/checks equality. Final06 stopped after
exact MinIO directory-metadata allocation PSI89us, then Temporal cancellation
and business failure after5pages. Leaf low events+30, no high/max/OOM; this is
best-effort protection being reclaimed, not CQ's reset or proven cap exhaustion.
One earlier trace call is unattributed; exact pre-stop target call is retained.
Original policy/override,raw low values,32off/object512Mi/health200 and owned
runtime cleanup independently passed. Six regressions and actual guard replay
pass; review issue fixed. No automatic retry or permanent policy/criterion change.
Next functional-diagnostic proposal requires an explicit critical decision on
object PSI stop behavior; see normal-topology-cr/NEXT-DECISION.md. #44 remains
open,#45 blocked,#51 unchanged. Results: normal-topology-cr/first-window-evidence/RESULTS.md.

### CS: approved functional diagnostic stopped on VM pressure

User approved the object PSI diagnostic. CS retained/allowed117us atavg10=0,
but unchanged VM PSI avg10=0.18 stopped firstWiki06 during component_ocr.
28pages were registered,0of11components; business failure follows cancellation,
not a preceding ActivityTaskFailed. A22,894us VM pressure interval contains173
allocator calls across18threads in the exact worker container, with anonymous
page-fault stacks and no compaction increment. Exact child/pool mapping remains
unproven. Installed RapidOCR leaves ONNX thread options at defaults; next isolate
this component with PID/pool attribution rather than repeat the full matrix.
5newguardtests+6existingprotectiontests and actual failure replay pass. Standards0,
Spec wording issue fixed/re-review0. Full manager/kernel/32off/object512Mi cleanup
independently passed; historical PVCs/prefixes retained. No more guards relaxed.
#44 remains open,#45 blocked,#51 unchanged. Evidence: normal-topology-cs/first-window-evidence/RESULTS.md.

## CT–CX OCR thread diagnosis (local draft)

- Confirmed default three ONNX pools expand OCR from7 to58 threads in a4-CPU-quota container with18 visible CPUs. A diagnostic-only intra-op=4 copy reduced engine-ready threads to16; full OCR report except timing and PNG bytes match. Minor faults did not fall, so this is not a proven PSI remedy and no production thread patch was made.
- With the actual CS inherited THP policy and unchanged VM avg10 predicate, native Wiki06 capture plus resident parser and OCR completed in48.90s: VM avg10=0, no OOM/max.32 Deployments stayed off. This is not normal-topology acceptance; CS child/pool attribution remains unknown.
- Retained failed instrumentation/control variants with explicit exclusions. All owned containers/parser removed; object512Mi Ready and32off independently checked. Replay: `python3 -B tests/pdf_processing/t09a_bounds/ocr-thread-probe/verify.py`. See `ocr-thread-probe/RESULTS.md`.
- Next: first-component allocation attribution under existing normal topology, preserving grouped capture and recording host/container PID mapping. No full-matrix retry, criterion relaxation, #44 closure, or #45 unblock.

## CY/CZ and production thread bound (local draft; #44 remains open)

CY reproduces OCR allocator/reclaim pressure under normal32-on load with exact
NStgid/start-time mapping:230 entries across OCR main+17 engine-created threads,
VM avg10 eventually0.18, no compaction. Planned first-output failure preceded the
delayed average guard; it did not cause the earlier pressure.

CZ changes only the supported diagnostic intra-op parameter to4. It records30
entries across4 OCR threads, direct scans1921 versus38353, VM avg10=0 and object
full PSI delta0. Full first-component report except timing and PNG bytes equal CY.
There is residual reclaim and the measured starting memory differs between runs;
this is a bounded improvement, not proof of universal zero pressure.

Production now explicitly bounds the shared component OCR constructor to4. Actual
production-path regression is red on automatic [0,0,0] native sessions before the
change and green on [4,4,4] afterward, preserving complete report/crop. Existing
OCR NumPy/lifecycle regression passes. A preliminary regression control stopped
on its older cumulative-PSI predicate and is excluded, not counted as the red case.

Both controlled runs stop after one component, attempt1/non-retryable; business
processing_complete=false,28pages/0registered components. No later components,
complete fixture graph, full29group sequence or recycle was validated here. All
32 Deployments restored off, object512Mi/Ready/HTTP200, owned processes/tracers gone,
low policies restored, PVCs/prefixes retained.

Next: bind the changed production OCR source into a fresh input/projection and
review its unchanged oracle boundary, then one full mixed diagnostic under the
existing CS policy. Do not reuse CY/CZ frozen producer manifests or promote narrow
component evidence to full acceptance. No #44 closure/#45 unblock/#51 reopening.
Reports: normal-topology-{cy,cz}/first-window-evidence/RESULTS.md and
ocr-thread-probe/production-regression/README.md.
