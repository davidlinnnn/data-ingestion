# CR: manager-owned protection and persistence admission

Base64f8dcf. CQ lost Burstable memory.low after56.64s before inference. A real,
owned temporary systemd slice reproduces the pattern: raw8MiB low becomes0 when
CPUWeight updates; manager MemoryLow8MiB survives the same class of update.
The specific writer in historical CQ remains unknown.

CR uses the same temporary768MiB hierarchical allowance and object/Pod1Gi caps.
Only the Burstable layer additionally uses systemd runtime MemoryLow so its
manager agrees with the kernel. Snapshot original property and its one override
file before writes. Journal before mutation; on interruption stop raw helpers,
serialize manager writes with native flock and bounded systemctl, then restore
manager property/override plus all raw low values. Never revert unrelated unit
properties. Historical evidence/runners remain intact.

Before any workload, check every ancestor and manager property for125seconds,
covering two one-minute QoS reconciliation periods. Keep VM floor/OOM/PSI and
object max/full-PSI checks during this admission. Never reapply lost protection:
fail-stop. If admission passes, execute exactly one full [06,07,08,native,06]
window,29groups,recycle20, unchanged producer/image/bundle/output oracle and all
resource/deadline guards. Use fresh t09a-bounds-20260927-cr and its own prefix/PVC.
No automatic retry, no permanent policy or larger hard limits.

Use the existing kind cluster; temporarily enable all32 historical Deployments
for the authorized normal-topology scope. Finally restore32off/object512Mi/health,
all manager and kernel protection values, remove owned diagnostics, retain PVC
and prefix. A full functional pass remains bounded evidence for#44, not universal
sizing. #51 remains historically closed; issue updates stay local draft.

Validation: actual-systemd red/green reproduction with owned-slice cleanup,
six focused rollback/timeout/manager tests, offline contract and actual image
imports; Standards/Spec review against64f8dcf before runtime. No extra workload
is launched solely to test setup. If125second admission fails, retain it as the
single attempt and diagnose before proposing a different candidate.
