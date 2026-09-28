# DH final mixed qualification with the approved terminal VM boundary

Approved by the user 2026-09-28. Production bytes, DB bundle/oracle, candidate
request768Mi/limit1Gi/Recreate and all non-object guards are unchanged from DD.
New identity `t09a-bounds-20260928-dh`, prefix
`t09a/bounds-20260928-dh/`; no host memory.low override.

The approved object rule retains cumulative full PSI as telemetry and stops on
positive full avg10, max or OOM. VM/worker PSI, memory floors, telemetry loss,
deadlines, output equality, recycle and cleanup requirements remain unchanged.
A direct `psi_memstall_enter` trace records exact task cgroups throughout. The
VM OOM and the memory floor remain fatal throughout. VM PSI stays fatal until
successful workload exit, a passing terminal worker sample and complete
worker-child cleanup markers are durable; after that boundary only PSI remains
telemetry while final Kubernetes cleanup runs.

Run once with all32 historical Deployments temporarily Ready. Fail-stop with no
automatic retry. Retain the candidate only if all five results,29 groups,
request20 recycle, resource evidence, direct trace, terminal export and cleanup
qualify; otherwise restore exact128Mi/512Mi/RollingUpdate. Always restore32off.
