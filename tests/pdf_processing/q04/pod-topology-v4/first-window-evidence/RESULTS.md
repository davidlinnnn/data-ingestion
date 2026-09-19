# Q04 YOLO Pod cgroup E window result

Status: **FAIL_PRE_INFERENCE_CLI_BINDING; no retry**.

The single authorized run used commit
`8148d1626efe53af90ba56b729ff69dc163bc1c5`, run identity
`q04-yolo-pod-cgroup-20260920-e`, and authorization scope
`670d884635cead08ce4031bc37057fe9cbf6d222f2fb3bb9d29ce5353810e315`.
No second E run was attempted.

Outer admission, Pod readiness, pinned image identity, the new PVC/PV backend,
the application-owned directory durability contract and binary staging of the
bundle, capacity, source manifest and Pod identity all passed. The aggregate
pre-inference program then exited before running its gates because argparse
provided `source_manifest` while `run_preflight()` requires
`source_manifest_path`.

Fresh, restored and exact replay are `NOT_STARTED`. No Temporal workflow,
parser, model or inference started and no object-prefix write occurred. The E
PVC is retained with pre-workload control evidence only.

Cleanup completed with disposition
`CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED`. The exact Deployment,
ReplicaSet, Pod and ConfigMaps are absent. The retained PVC UID is
`c8022f9e-0d90-4c8c-a31c-b2407724182a` and PV UID is
`b94d329b-6562-4a0d-8bda-d208bcd6464d`. Final health, PSI and OOM checks
passed; the 32 held Deployments remained closed.
