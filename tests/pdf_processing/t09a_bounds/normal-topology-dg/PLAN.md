# DG final mixed qualification with the approved object PSI policy

Approved by the user2026-09-28. Production bytes, DB bundle/oracle, candidate
request768Mi/limit1Gi/Recreate and all non-object guards are unchanged from DD.
New identity `t09a-bounds-20260928-dg`, prefix
`t09a/bounds-20260928-dg/`; no host memory.low override.

The approved object rule retains cumulative full PSI as telemetry and stops on
positive full avg10, max or OOM. VM/worker PSI, memory floors, telemetry loss,
deadlines, output equality, recycle and cleanup requirements remain unchanged.
A direct `psi_memstall_enter` trace records exact task cgroups throughout.

Run once with all32 historical Deployments temporarily Ready. Fail-stop with no
automatic retry. Retain the candidate only if all five results,29 groups,
request20 recycle, resource evidence, direct trace, terminal export and cleanup
qualify; otherwise restore exact128Mi/512Mi/RollingUpdate. Always restore32off.
