# Next normal-topology measurement after BQ

BQ executed once and stopped on node full PSI 0.18 during the first warm workload. The exact BQ worker cgroup also recorded full PSI, but the source of the entire node event remains unknown. The outer controller sent a second interruption after the runner recorded its own guard stop; terminal sealing did not finish. Preserve BP and BQ evidence. No automatic retry.

Before another runtime:

1. The BR outer-controller candidate now detects a fresh, runner-owned `controller-stop.json` and gives bounded cleanup time without a second SIGINT. If the runner has not stopped, it retains the outer guard's SIGINT and finite force deadline. A local process regression passed both branches, including a delayed terminal write. Integrate it with a complete BR runner before runtime. This is a cleanup fix, not a guard relaxation.
2. Keep BQ's incomplete-marker sealing and failure-only evidence export checks. Verify the whole interruption-to-export path with a local simulated stop, including `workload-exit.json`, `cleanup-complete.json`, an `INCOMPLETE` terminal manifest, and exported failure evidence. Never classify these as workload success.
3. For a fresh run ID, prefix, outputs and PVC, prepare the complete projected source and exact command. Keep the same 32-Deployment normal topology, fixed workload, 1 GiB temporary object-service observation, unchanged node PSI/OOM/memory floor, Pod cgroup checks and deadlines. Reuse the read-only half-second node/cgroup PSI observer; it added no pressure event during admission and identified the BQ worker cgroup at the trigger.
4. Review the diff, pass the local projection and cleanup tests, and check live cluster identities before starting one controlled runtime. Stop on any existing guard breach, never retry automatically, restore all 32 Deployments to zero and object service to 512Mi, and retain evidence. Verify restoration independently.

A repeated PSI stop remains an acceptance failure even with spare MemAvailable. A clean run must satisfy the full existing workload and evidence matrix; the temporary 1 GiB object limit still needs sustained evidence or an explicit acceptance decision before it becomes permanent. Keep #44 open.

## After BR

BR was executed once. It fixed the BQ terminal-evidence loss: runner-owned
stop, complete cleanup markers, durable `INCOMPLETE` manifest, and finalized
failure export are all present. Three warm segments completed; native was
cancelled when the object-service cgroup full-PSI total rose by 9 microseconds
with no max/OOM event and memory.current about 511MB of 1GiB. The existing
zero-event guard correctly stopped the run. No retry or threshold change.

The live #44 candidate explicitly requires zero full-PSI violations. BR's
9-microsecond object-container event is independently visible in the node
observer and fails that rule. Do not repeat BR unchanged or raise the object
limit merely because it stopped: BR used only about half of 1 GiB, had no
max/OOM event, and the cause of its cgroup stall is not isolated.

Before another runtime, choose and document one materially different, feasible
operating configuration for the existing cluster. In particular, inspect the
worker2 placement and storage constraints before proposing any relocation;
the current object Deployment is pinned there and uses PVC `object-data`.
Keep the existing zero-PSI/OOM guards unless #44 explicitly adopts a new
criterion. A new configuration needs a fresh identity/prefix, one controlled
window, failure stop, and restoration proof. BK remains the proven isolated
case; normal 32-Deployment operation remains unqualified.

## After BU

The distinct worker1 placement was tested. BS and BT stopped on inherited
node-identity checks before inference; each defect has a focused local
regression and historical evidence remains intact. BU passed those checks,
admission and all 11 pre-inference gates, but stopped during first Wiki 06
when the exact object-container cgroup accumulated full PSI on worker2. Its
object memory peaked below 0.3 GiB of the temporary 1 GiB limit, with no
max/OOM event. Failure evidence sealed and the cluster was independently
restored. Moving only the Q04 worker off worker2 therefore did not qualify
the 32-Deployment topology.

Do not launch another unchanged full workload or raise the object limit based
on BU. The next useful work is a decision on the supported operating scope:
BK proves the fixed serial workload only with the 32 historical Deployments
held off and a temporary, observed 1 GiB object limit; BR and BU show that
the all-on state fails the existing zero-full-PSI gate in two worker
placements. Treat all-on operation and permanent object sizing as
unqualified until a specific alternative configuration addresses the
observed shared-VM/object pressure and passes the same guards. Keep #44 open and
publish the measured boundary through the normal mainline review; no
additional runtime is justified by these results alone.


## Scope correction and next useful measurement

The post-BU read-only probe proves worker1 and worker2 share the VM memory
and global PSI domain (see RESULTS). Relocation within this kind cluster
cannot test memory-domain isolation. Do not repeat that experiment or
interpret a single node cgroup scan as a complete VM pressure attribution.

Before any next full workload, inspect existing VM reclaim/compaction counters
and the pressure of both node cgroup roots together. If historical samples
lack those counters, explicitly retain that causal uncertainty. Any future
controlled window should correlate one VM-wide series with both node-root
and exact worker/object leaf series, using the existing observers; do not
add another runner copy just for this diagnosis. This improves attribution,
not the pass criteria. A further workload needs a concrete hypothesis about
contention that the chosen configuration changes; neither another Pod move
nor a larger object limit is justified by the present evidence.


The historical-counter inspection is now complete: BU shows allocation
stalls and direct/background reclaim immediately before stop, with no
compaction-counter change in the last two seconds. Do not repeat this read.
The remaining diagnostic gap is process/ancestor attribution, not whether
reclaim happened. Resolve that gap before choosing another configuration;
current evidence does not justify increasing memory or changing acceptance.


## After process attribution

The existing BU evidence now identifies the growing OCR child, while its
warm parser is idle with retained memory. Use the existing OCR phase probe
to distinguish imports, crop construction, engine initialization and inference
in a targeted diagnostic before considering a full acceptance window. First
validate marker delivery through the real descendant launch path (AR failed
before inference; AS lost its startup hook). Preserve output equivalence and
the request-20 warm-parser lifetime. Do not remove the warm parser, lower
render scale, or alter zero-PSI acceptance merely to make this pass. The
current data do not identify a safe production fix yet.


## After BV

The isolated plain OCR diagnostic also encountered a brief local PSI stall,
so warm-parser overlap is not a necessary condition. Do not implement parser
recycling as the presumed remedy. Marker transport is now locally verified,
but the plain-first run stopped before the observed variant. A future
explicitly selected diagnostic should collect phases in its first child,
then attempt an uninstrumented equivalence comparison only if it finishes.
Keep the BV identity consumed. Distinguish the additional total-based
diagnostic abort from the historical VM avg10 acceptance guard; do not claim
these are identical. Until actual phase evidence exists, initialization versus
inference and the underlying reclaim mechanism remain unknown. No production
memory tuning is justified yet.

The prepared `ocr-phase-probe/run.py` now orders observed before plain and
removes the trace variable for the plain child. It has not been executed.
The exact BV script is frozen in `ocr-phase-probe/bv-evidence/run.py`.


## After BW

Phase delivery now works in real OCR. BW narrows the first measured stall
to late ONNX initialization / the first milliseconds of inference; imports,
document decoding and crop construction finished earlier. Do not keep
repeating the full workflow. Next inspect the installed OCR/ONNX session
configuration and the first inference allocation path against this bracket.
Any proposed memory optimization must preserve model artifacts, render scale,
OCR outputs and warm-parser continuity. The exact allocator/operator remains
unknown; a new runtime needs a specific candidate or discriminating probe,
not another unchanged BW invocation. BW's additional total-based abort and
the formal acceptance guards remain explicitly distinct.


## After BX/BY/BZ/CA: a tested fix exists

Stop exploratory OCR runs: the THP reversal and narrower NumPy-only control
isolate a correctable mechanism. `Execution.fresh_child` now applies
`NUMPY_MADVISE_HUGEPAGE=0` only to OCR children. The exact code candidate
completed real OCR with zero PSI/compaction stalls and matching output.

Next is integration qualification, not another identical diagnostic: create
a fresh source projection/input producer contract for this execution change,
verify it locally, and exercise the original full workload with its original
formal guards. Preserve the required request-20 warm lifetime and 32-service
scope; do not infer those from the isolated picture0 success. The diagnostic
extra total-PSI rule remains separate from formal acceptance. Keep #44 open.


## After CB: full topology still fails; do not repeat unchanged

CB passed the actual source/bundle and all pre-inference checks, then stopped
on object full PSI during first OCR. The latest frozen failure evidence shows
direct reclaim without compaction in the pre-stop interval. Do not characterize
all stops as NumPy THP compaction or declare the isolated fix sufficient.

The next diagnostic needs to distinguish VM/global reclaim, ancestor pressure,
and workload allocation under the all-on condition. Inspect existing ancestor
limits and retained samples first; if a new measurement is necessary, collect
per-task reclaim attribution at the trigger. Merely adding another lettered
runner, moving between kind nodes, increasing the object limit or weakening
zero-PSI acceptance is not an evidence-backed remedy. #44 remains open.

## After CD / CE / CF / CG (current)

CG is the first retained successful normal32-on mixed window after the OCR
policy fix: complete sequence, post-recycle completion, full fresh-reference
JSON equality, unchanged resource guards and restoration all passed. CD with
the same producer/config failed late with object full PSI+417us; changing the
probe did not fix production. Preserve both verdicts.

Do not run another unchanged full matrix just to accumulate a pass. The
functional sequence and output comparison are now verified for CG. Remaining
#44 questions are intermittent object pressure and sustainable operating scope.
The direct PSI caller probe is ready for a future independently justified
measurement; it captured no target event in CG. CD supports a refault/read-wait
hypothesis but did not prove thread-to-target attribution; CE idle and CF bounded
read-only tests did not reproduce it. No additional production memory tuning or
zero-PSI rule change is justified from these results alone.

A critical scope/criterion decision must be explicit before changing the
zero-event contract or declaring the temporary1Gi setting permanent. Until
then keep object512Mi after each run, preserve all32-off resting state, and keep
#44 open. The code fix/evidence can be reviewed independently of that decision.


## After CH–CN (current): effective ancestor limit matters

A small idle reproduction now attributes512MiB PSI to the actual MinIO server's
ext4 directory reads entering `try_charge_memcg`. The same process continued
cache work without PSI for30s with both leaf and Pod at1GiB; after restoring both
limits, PSI and Pod-only max events returned in0.51s. Container-only events miss
this ancestor pressure. No production or permanent resource change was made.

Two diagnostics are explicitly excluded: CJ was contaminated by our version-query
subprocess; CL changed only the leaf and left the effective Pod cap512MiB. The
corrected CM/CN contrast and raw records are in `object-stall-probe/RESULTS.md`.
This explains the reproducible idle512MiB case, not the historical CD1GiB stop.

Next capture effective ancestor limits/local events and direct PSI callers in
a short directory-read observation under the original1GiB/full-topology scope.
A full ingestion rerun needs a concrete candidate fix or a discriminating
workload hypothesis; do not repeat CG merely to get another pass. Keep guards,
32-off resting state and object512Mi unchanged; #44 stays open.


## After CO (current): return to the missing mixed-load interaction

The short1GiB/all32-on control completed30s idle and20 preserved-object reads
without object/Pod PSI or max/OOM increments. No VM direct/background reclaim
occurred; exact-target tracer calls were absent. All cleanup checks passed.
This is a negative diagnostic control, not resolution of historical CD.

Do not add another standalone idle/read variant. The remaining discriminating
runtime is the real [06,07,08,native,06] mixed producer, once, with CO's ancestor
sampler and the direct PSI tracer. Preserve the trigger and classify charge-limit
versus page-read-wait/global-reclaim behavior. Existing guards and output checks
remain unchanged. There is no proven new fix to apply; a pass alone cannot establish
intermittent resolution. Keep #44 open and object512Mi/all32-off after the run.


## After CP (current): target workingset-read PSI proven

The real mixed workload reproduced object PSI155us at onset. Fourteen exact
MinIO calls before the guard stop entered from read_pages/folio_wait_bit_common,
with ext4 file reads, not try_charge_memcg. Leaf/Pod remained below1Gi and all
observed ancestor high/max/OOM counters were0. Prior global/object reclaim and
refault growth support the workingset-read mechanism. Guard stop preceded
Temporal cancellation and the native business failure. No automatic retry.

Stop generic attribution-only runs. The next candidate is reversible best-effort
object working-set protection using memory.low along the exact ancestor path;
current values are0. Trial768MiB covers CG's observed object peak without raising
memory.max1Gi or changing any formal guard. It is not a proven permanent resource
setting and may move reclaim to siblings; check effective hierarchy/restoration
locally first, measure one new real-workload window, fail-stop and restore every
value plus32-off/object512Mi. Do not use memory.min or increase hardware here.
See normal-topology-cp/first-window-evidence/RESULTS.md for cause, evidence and limits.

## After CQ (current): fix policy ownership before another workload

CQ applied768MiB low to seven ancestors, then the Burstable slice reset0 after
56.64s. The guard stopped before workload; zero object PSI is not qualification.
Systemd MemoryLow was0; the one-minute QoS reconciliation is consistent with this
reset, but the exact writer is untraced. Raw cgroup writes are not a stable policy.
Next evaluate a reversible systemd runtime MemoryLow setting, snapshot manager
and kernel values, and gate inference on persistence through two reconciliation
intervals. Do not use a reapply loop or bypass the guard. Local interruption and
restoration checks precede a new identity; no unchanged CQ retry. All original
values/32off/object512Mi restored. See normal-topology-cq/first-window-evidence/RESULTS.md.

## After CR (current): protection persists, allocator PSI remains

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

## After CS (current): isolate OCR-stage allocator pressure

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
