# Proposed capacity candidates — NOT AUTHORIZED

Only if main approves a fresh capacity lease. Current headcount is 20 Deployments, all 1 → proposed 0 → restore 1.
Every namespace returned Temporal health=true, a complete Running query with 0 executions, and object readiness HTTP 200.
Coordinator/activity/workflow Pod process scans found 0 matching parser/Q03/Q04 processes. This is a dated snapshot, not a lock or proof about independent S3 clients.
Recheck immediately before any approved pause. Do not automatically widen scope if admission still fails.

| Namespace | Deployment | UID | Current / ready | Proposed / restore | Idle snapshot |
|---|---|---|---|---|---|
| pdf-t03-validation | activities | `e85f2d98-3967-4f3a-b8ac-3cad6b67efbf` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t03-validation | objects | `68da72a3-d241-4815-b011-8a2847eb6cb8` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t03-validation | temporal | `3625e9ec-f914-4158-b8ea-62808ad454e9` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t03-validation | workflows | `76080d5e-7d36-420c-a137-ea876d96ccc4` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t04-validation | activities | `a8cc35cb-e573-437a-8d9a-22313fab9e35` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t04-validation | objects | `4ecb44ce-68cd-441d-a57b-7d0011db20ff` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t04-validation | temporal | `a3f5b91f-2cf2-4e26-a687-e0c4f5295e0d` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t04-validation | workflows | `33375e63-f88f-48e2-bdf9-89e6ad8007d2` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t05-validation | activities | `f07fb1ed-db49-4726-b583-a47b92fb9058` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t05-validation | objects | `1dcd9af2-5ba3-4dd3-8a32-791bfe924a1e` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t05-validation | temporal | `addb5865-279a-430d-97b2-4ba4f70aabaf` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t05-validation | workflows | `d776ad65-853b-475d-85b0-59abe6ccc925` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t06-validation | activities | `ace4dbdf-36cd-44b6-9767-928be3ebc758` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t06-validation | objects | `f066a15b-ca17-40db-a212-786373f9cda5` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t06-validation | temporal | `2079d4c4-7cb2-48d6-b539-0f29077d8c86` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t06-validation | workflows | `e37e8d2c-b151-4b46-805d-cbd67f61b0e3` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t07-validation | activities | `4ca318d9-093c-4ada-9184-eec75c5094d4` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t07-validation | objects | `c8f1a916-0b66-4e13-b5fa-15493a3e1a65` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t07-validation | temporal | `b3526e9c-3faa-41b4-a098-dcae0f5e634b` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |
| pdf-t07-validation | workflows | `d28986b9-3697-4800-adcf-f5915ead4417` | 1 / 1 | 0 / 1 | Running=0; parser=0; services healthy |

Pause order after approval: Activities and workflow pollers first; verify owned service Pods/CRI stopped; then objects and Temporal. Preserve all PVCs.
Restore objects and Temporal first, wait Ready and health endpoints, then restore original activity/workflow replicas. Match original Deployment UID and use current resourceVersion preconditions; stop on identity changes.
T09a, coordinators, zero-replica Deployments, application services, PVCs and node resources are outside this proposed pause set.
An operator must own restore-on-every-exit, including sentinel failure, and retain pre/post UID/replica/health evidence. No pause/restore command has been executed.
