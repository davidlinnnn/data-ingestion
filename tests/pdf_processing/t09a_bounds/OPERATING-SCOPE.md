# T09a approved initial operating scope; persistent candidate pending

Status2026-09-28: OCR fixes are integrated at57fcc2e. The user approved the
limited initial scope and native object request768Mi/limit1Gi/Recreate
candidate, without persistent host memory.low overrides. Permanent adoption
requires complete qualification. DC stopped during first object rollout on
Service connection refusal before any workload; original128Mi/512Mi and
RollingUpdate were restored. #44 remains open. See the
[approved plan](normal-topology-dc/PLAN.md) and
[DC result](normal-topology-dc/first-window-evidence/RESULTS.md).

## Verified configuration

DB used production `970f28c`: OCR children disable NumPy hugepage advice before
imports and component OCR uses ONNX intra-op4. One serial worker on the existing
kind VM,4CPU quota,5GiB container hard limit,4GiB sample guard; existing models,
rendering,profiles,continuation and reviewed output oracles. All32 historical
Deployments were temporarily active. The object service had an effective1GiB
cap and reversible768MiB memory.low protection along its ancestor path.
Admission,VM/worker PSI/OOM/memory floors,telemetry and deadlines remained active.
The user-approved CS functional object policy records cumulative full PSI and
stops on positive full avg10. DB happened to record zero cumulative object PSI.

| Evidence-backed result | Observation |
| --- | --- |
| Sequence | Wiki28pages,YOLO15,AIMA12,native51,Wiki28 |
| Full outputs/checks | All5 equal accepted AI/AJ fresh references |
| Warm/recycle |29groups,request20 recycle,2parser identities,post-recycle completion |
| Business completion |All5 complete;registered pages28/15/12/51/28 |
| Worker memory |Maximum2,803,494,912bytes,below4GiB guard |
| VM available memory |Minimum2,739,621,888bytes;no avg10/OOM violation |
| Object memory/pressure |Maximum734,707,712bytes;no max/OOM or full-PSI increment |
| Cleanup |32off,object512Mi/Ready/HTTP200,all low values restored,owned runtime absent |

Those are observed outcomes,not safe maxima or capacity guarantees. The auxiliary
whole-node cgroup observer failed before workload on a disappearing-directory
race; outer controller exit1 is retained. Mandatory guard/process sampling,
terminal export and independent cleanup were complete. The new observer has an
actual-platform regression fix. No missing attribution samples were inferred.
See [DB results](normal-topology-db/first-window-evidence/RESULTS.md).

## Approved scope and remaining acceptance

Initial support is one serial worker for the named WikiSkill28-page,
YOLO15-page,AIMA12-page contiguous chapter and native51-page fixtures with
required figure OCR and reviewed quality rules,including a Wiki repeat.
Keep group5,recycle20,OCR intra-op4,4CPU,5GiB hard limit and4GiB sample guard.
The existing100MiB/file,51page and20M-pixel/page admission caps are rejection
ceilings. Tested PDF sizes are308,913–1,817,841bytes; arbitrary inputs at the
configured maxima remain unqualified. Concurrency,whole books,scan-first and
universal language/PPT coverage remain outside this initial scope.

The native768Mi request/1Gi limit candidate has no explicit host protection.
A request supplies scheduler accounting; actual cgroup low/min values must be
observed. It cannot inherit DB's managed-low qualification. DC did not reach
the workload and supplies no capacity or PSI conclusion.

Remaining: qualify the concrete native setting with the fixed five-document
window,original zero-new-object-full-PSI condition,all business/output/resource
and cleanup gates,then retain on PASS or restore on failure. The readiness
helper now waits for actual Service HTTP200 within the original deadline;
local red/green and read-only coordinator checks passed. DC was not retried.
Inherited Q04 recovery results retain their original identities and require
an explicit impact mapping before closure. #45 remains blocked and #51 closed.
