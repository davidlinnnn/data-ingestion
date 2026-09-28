# DC: candidate rollout stopped before workload

Result: **NOT QUALIFIED**. Executed once at source commit `ff57ee9` on
2026-09-28. New identity `t09a-bounds-20260928-dc`, planned prefix
`t09a/bounds-20260928-dc/`. No retry occurred.

The approved native object request768Mi/limit1Gi/Recreate configuration was
applied. The new Pod was Running with its container marked Ready, so
`object_policy.await_ready()` returned. The immediate coordinator request to
the object Service health endpoint failed with `URLError` caused by
`ConnectionRefusedError` errno111. The controller stopped and restored the
complete original resources and RollingUpdate strategy.

The Deployment has no readiness probe. Kubernetes therefore does not use an
application readiness check before reporting the container ready; see the
[official probe semantics](https://kubernetes.io/docs/concepts/workloads/pods/probes/#probe-results).
The harness incorrectly treated container identity/readiness as proof that
MinIO was reachable through its Service. Whether this specific refusal came
from MinIO initialization or endpoint propagation is **unknown**: the failed
Pod's application logs and endpoint state at the refusal were not captured.
Kubernetes events place candidate startup at03:52:13Z and rollback Pod startup
at03:52:15Z. These are coarse timestamps, not a reconstructed exact timeline.

The necessary local regression reproduces the bug: when container Ready is
available before HTTP ready, the old helper performed zero health calls and
returned too early. The corrected shared deployment-policy helper requires
HTTP200 through the Service within the existing120s readiness deadline, and
also uses that condition for replacement and rollback. Persistent failure
still stops; it does not retry a workflow or relax a resource gate. The
regression went red before the fix and green afterward. DC's runner/manifests
remain frozen at their executed version; the helper fix is a later commit.

| Gate | DC outcome |
| --- | --- |
| Local launch/projection/contract/cleanup and review | PASS before execution |
| Candidate initial rollout | Pod started; Service health failed |
| Deliberate second Pod replacement / object readback | NOT EXECUTED |
| 32-on normal-topology window | NOT EXECUTED; all32 remained off |
| Pre-inference gates / workflow / Activity / inference | NOT EXECUTED |
| Five business results / full output equality / recycle | NOT EXECUTED |
| PSI/OOM/memory qualification | NOT MEASURED in DC |
| Original configuration restoration | PASS, independent readback |
| Service health / Temporal idle | PASS, HTTP200 and no Running workflows |
| Owned runtime and observer cleanup | None started; DC runtime Pod absent |
| Historical evidence / object PVC | Retained, same object PVC UID and PV |
| Permanent candidate adoption / #44 closure | NOT READY |

This is an acceptance-tool readiness failure. It supplies no evidence for or
against the candidate's workload capacity, PSI behavior or permanent adoption.
#51 remains closed for its previously accepted exact identities. #44 stays
open and #45 stays blocked.

Next necessary qualification uses a new identity after the readiness fix and
review, with unchanged production bytes, limits, original PSI policy and
approved five-document scope. The failed DC window was not repeated.
