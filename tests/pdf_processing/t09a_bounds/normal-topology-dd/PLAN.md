# DD qualification after the DC readiness correction

Approved by the user2026-09-28. Same initial support scope and candidate as
[the accepted DC plan](../normal-topology-dc/PLAN.md). Source begins at ecba2d2;
production bytes and the DB input bundle/oracle are unchanged. DC evidence
and its consumed identity remain preserved.

New identity `t09a-bounds-20260928-dd`, prefix `t09a/bounds-20260928-dd/`.
Use the corrected shared deployment-policy helper: correct Pod identity and
Service HTTP200 must both be ready within the original deadline.

1. Confirm32 exact/off historical Deployments, idle Temporal and healthy object
   service. Capture original resources, strategy and PVC identity.
2. Apply native request768Mi/limit1Gi/Recreate. Verify health, replace the
   object Pod once, verify retained settings/PVC and read an existing object.
3. Run one normal-topology32-on window with sequence06/07/08/native/06,
   29groups,request20 recycle and two parser identities. Require complete
   business outcomes,full document/check equality and all existing guard,
   deadline,telemetry and cleanup checks. Original zero-new-object-full-PSI
   condition applies; no host memory.low writes or constructor overrides.
4. Stop on failure and preserve evidence. Retain candidate only after complete
   qualification; otherwise restore exact original configuration. Restore32off
   in either outcome. No automatic runtime retry.

Only the new identity/launch/projection/contract and changed retention checks
need local verification; already-passed unchanged regressions are reused.
Review before runtime. Before #44 closure, map the OCR-policy changes to
inherited Q04 compatibility/recovery evidence without relabelling old runs.
