# DB: full production OCR window completes; auxiliary observer incomplete

One attempt, new producer970f28c with OCR intra-op4, no diagnostic hook or
constructor override. Main runner exited0; outer controller exited1 because
its auxiliary node attribution observer had already exited on a departing
cgroup directory. Preserve that failure; this is not an all-tools PASS.

| Check | Result |
| --- | --- |
| Fresh source/bundle,11pre-inference gates | PASS; only producer.ocr.py changed |
| Wiki06,YOLO07,AIMA08,native51,Wiki06 | All5 business complete,processing_complete=true |
| Full document and checks vs accepted AI/AJ | All5 exactly equal |
|29group requests,recycle after20,post-recycle | PASS,2parser identities,1recycle |
| Worker/process resource telemetry |1399samples,complete,all-sample gate PASS |
| Worker maximum / VM minimum available |2,803,494,912 /2,739,621,888bytes |
| VM/worker full PSI avg10 and OOM | No violations; VM maxavg10=0,OOM=0 |
| Object telemetry |2543samples,maxgap0.265s,max734,707,712bytes;fullPSIdelta0 |
| Managed object protection admission |125.339s continuous samples at6visible levels;separate host checks verify7levels at768MiB |
| Durable terminal/export,worker/scratch cleanup | PASS |
| Independent restoration |32off,no ownedPods,object512Mi/Ready/HTTP200,low restored,PVCBound |
| Auxiliary node-wide cgroup attribution | INCOMPLETE; early traversal race |

Temporal histories have no Activity failure/cancellation; all5 complete with
business status complete and registered pages28/15/12/51/28. Existing
canonical_accepted=false is retained; processing completion is not publication.

## Observer cause and timing

The auxiliary observer's last sample ended1790533175.6689, during initial object
Pod rollout, before the first workload. Python3.11 Path.rglob lists a descendant
then descends after it disappears. The read_text-only FileNotFoundError handler
cannot catch the iterator's exception. The controller checks this auxiliary
process at stop, explaining the late reported error. No missing historical
samples were reconstructed. Mandatory VM/worker/object sampling and the direct
stall tracer continued; target object calls0,unattributed calls0,no trace loss.

A two-case local regression on the same Linux Python3.11 reproduced the traversal
exception before the fix and also showed rglob suppressing permission errors.
The new observer uses stdlib os.walk, skips only vanished descendants and
propagates other errors. Both tests pass. Historical observer/controller remain
unchanged. No second full runtime was started to hide this tool failure.

## Readiness verification correction

The125s deadline starts before the first VM sample. Their first/last timestamps
span124.998252s, so the old post-check incorrectly rejected the run. Continuous
object telemetry enclosing these endpoints spans125.338789s,has<1s gaps and
shows all6visible ancestors at768MiB; separate host checks verify7levels. verify_results.py checks those actual
samples with the original125s requirement; no threshold/tolerance was relaxed.

## What this establishes

The actual production thread fix now passes one complete normal32-on mixed
window, full fidelity checks and recycle under the existing CS policy. This run
also observed zero cumulative object PSI. One pass does not establish permanent
MinIO sizing, intermittent reliability or universal file/page/pixel limits.
#44 remains open,#45blocked; accepted#51history is unchanged. The next action is
to review/integrate the tested OCR fix and define only the remaining operating
bounds; do not repeat this same matrix solely for the auxiliary observer.

Raw evidence: /private/tmp/t09a-bounds-20260928-db,
/private/tmp/t09a-bounds-object-20260928-db,
/private/tmp/t09a-normal-topology-20260928-db. Retained snapshots accompany this
report. Run verify_results.py for full functional comparison and explicit tool
failure classification; test_observer.py reproduces the fixed race locally.
