# T09a measured operating scope after DB

Status: the OCR fixes are ready for integration. The fixed mixed-document
functional window passes; #44 remains open for an accepted operating envelope.
This document records measurements and a proposed next decision. It changes no
acceptance criterion or permanent cluster setting.

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

## Remaining acceptance and next decision

1. Adopt a permanent object-service policy only through an explicit scope
   decision. The resting512MiB setting has reproduced ancestor charge stalls;
   temporary1GiB alone also had historical mixed-load stalls. DB's1GiB plus
   managed768MiB low is a measured candidate,not an installed sustainable policy.
2. State the initial support envelope. The five fixed documents and serial
   configuration are verified. Arbitrary documents at configured file/page/pixel
   caps,concurrency changes,whole books and deferred scan/language/PPT claims
   remain unqualified. Configured rejection limits are not successful capacity.
3. If adopting the bounded candidate, implement its policy in the deployment
   configuration and measure that concrete persistent configuration. Use one
   new identity and the declared guard contract; stop on failure. A repetition
   with the same temporary controller would not establish policy deployment.

Recommended decision: carry the fixed serial scope and propose the measured
object candidate for explicit operating-scope approval. Keep broader conditions
as deployment gates. This needs a decision before permanent policy installation
or #44closure; it does not require more exploratory OCR or an unchanged full
matrix. #45 stays blocked; #51's existing acceptance remains closed.
