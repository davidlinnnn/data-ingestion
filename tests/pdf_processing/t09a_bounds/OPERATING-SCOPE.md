# T09a approved initial operating scope and retained object configuration

Status 2026-09-28: OCR fixes are integrated at `57fcc2e`. DH passed the user
approved limited initial scope with native object request 768Mi, limit 1Gi,
`Recreate`, and no host memory.low override. All five exact outputs, recycle,
resource guards, terminal evidence, and cleanup passed; the object configuration
is retained. Earlier DD–DG failures remain historical evidence. See
[DH result](normal-topology-dh/first-window-evidence/RESULTS.md) and
[recovery impact mapping](RECOVERY-IMPACT.md).

## Verified configuration

DH used production `970f28c`: OCR children disable NumPy hugepage advice before
imports and component OCR uses ONNX intra-op4. One serial worker on the existing
kind VM,4CPU quota,5GiB container hard limit,4GiB sample guard; existing models,
rendering,profiles,continuation and reviewed output oracles. All32 historical
Deployments were temporarily active. The object service used request768Mi,
limit1Gi and `Recreate`, with no host memory.low override. Admission,VM/worker
PSI/OOM,memory floors,telemetry and deadlines remained active. Cumulative object
full PSI is telemetry; positive object avg10,max or OOM remains fatal.

| Evidence-backed result | Observation |
| --- | --- |
| Sequence | Wiki28pages,YOLO15,AIMA12,native51,Wiki28 |
| Full outputs/checks | All5 equal accepted AI/AJ fresh references |
| Warm/recycle |29groups,request20 recycle,2parser identities,post-recycle completion |
| Business completion |All5 complete;registered pages28/15/12/51/28 |
| Worker memory |Maximum2,852,814,848bytes,below4GiB guard |
| VM available memory |Minimum2,719,670,272bytes;no avg10/OOM violation |
| Object memory/pressure |Maximum736,923,648bytes;no max/OOM or full-PSI increment |
| Cleanup |32off,object1Gi/Ready/HTTP200,candidate retained,owned runtime absent |

Those are observed outcomes,not safe maxima or capacity guarantees. All1,358
worker and1,995 object samples,terminal export,direct trace and independent
cleanup passed. Workload,runner and outer controller exited0. See
[DH results](normal-topology-dh/first-window-evidence/RESULTS.md).

## Approved scope and excluded bounds

Initial support is one serial worker for the named WikiSkill28-page,
YOLO15-page,AIMA12-page contiguous chapter and native51-page fixtures with
required figure OCR and reviewed quality rules,including a Wiki repeat.
Keep group5,recycle20,OCR intra-op4,4CPU,5GiB hard limit and4GiB sample guard.
The existing100MiB/file,51page and20M-pixel/page admission caps are rejection
ceilings. Tested PDF sizes are308,913–1,817,841bytes; arbitrary inputs at the
configured maxima remain unqualified. Concurrency,whole books,scan-first and
universal language/PPT coverage remain outside this initial scope.

The native768Mi request/1Gi limit candidate has no explicit host protection.
DD measured container/Pod low=min=0. It cannot inherit DB's managed-low
qualification. DD object peak539,328,512bytes and zero max/OOM show no observed
limit hit; the27us trigger does not establish a capacity deficit or false PSI.
The precise task/kernel stall mechanism remains unknown. No threshold changed.

DE's minimal32MiB conditional PUT/GET probe and DF's bounded replay of256
retained DD small objects under the candidate and32-on topology both recorded
low operation latency,zero object PSI/max/OOM and no target stall call. They
rule out those isolated operation shapes as sufficient triggers; they do not
resolve DD's event. The complete producer chronology, accumulated cache/reclaim
state and intermittent background filesystem work remain unseparated. Another
object-only probe is not justified. A next runtime must test a concrete
sustainable object-policy candidate while capturing the exact object caller in
a bounded mixed producer window; repeating DD unchanged would only retest the
rejected result. No automatic retry of DD, DE or DF. Original zero-new-full-PSI
and all other gates remain declared. Actual Service readiness, Pod replacement,
PVC identity and old-object readback passed DD; no repeat of unchanged readiness
regressions is needed. [Recovery impact](RECOVERY-IMPACT.md) preserves original
Q04 identities and records the affected dependency projections and current local
checks. It does not claim32-on interruption/recovery capacity. #45 remains
blocked and #51 closed. Arbitrary maxima/concurrency/intermittent reliability
remain outside approved initial support, not passed deployment guarantees.

## DG qualification result

The approved cumulative-telemetry object policy allowed DG to complete the full
mixed sequence with exact accepted outputs and recycle. Object avg10/max/OOM
remained zero at the 1GiB candidate. DG still does not qualify permanent adoption:
the unchanged outer VM guard saw avg10=0.18 after workload exit, during final
cleanup, with stalls attributed to kindnet `iptables` tasks. The candidate was
therefore restored to the original 512Mi configuration. Permanent object settings
remain pending #44; no supported input or concurrency bound is expanded.

## DH retained configuration and closure boundary

DH passed one controlled full-topology qualification under the approved object
and terminal VM PSI policies. Worker max was 2,852,814,848 bytes, object max was
736,923,648 bytes, minimum VM available was 2,719,670,272 bytes, and no worker,
object, or VM avg10/OOM/max violation occurred. All five outputs exactly match
accepted references; 29 groups and request-20 recycle completed. Independent
cleanup passed and the candidate remains 768Mi/1Gi/`Recreate`.

This is the permanent object setting for the approved initial serial fixture
scope. It does not promote admission ceilings to tested maxima or add support
for concurrency, whole books, or scan-first workloads. DG's kindnet trigger
source remains unknown because DH did not reproduce it. #44 is ready to close
for the approved scope; broader bounds require a separately approved scope.
