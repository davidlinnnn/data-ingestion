# Q04 YOLO Pod cgroup D window result

Status: **FAIL_PRE_INFERENCE_CONTROL_STAGING; no retry**.

The single authorized run used commit
`178d189175038e5127eb0aa4425e69c4cbc007b1`, run identity
`q04-yolo-pod-cgroup-20260919-d`, and authorization scope
`73d2e670aaa76686bf0b639b5b4318e3630692f7604df24dc36b83c91ac4877c`.
No second D run was attempted.

Outer admission, Pod readiness and pinned image identity passed. The new PVC
mounted as the expected local-path hostPath. UID/GID 1000 successfully created
the exclusive `0700` run-owned evidence directory, and the file fsync, atomic
rename, directory fsync, byte-for-byte readback and capacity checks passed.

The controller then copied the fixed input bundle and staged `capacity.json`.
Staging `source-manifest.json` failed because the remote Python snippet opened
the destination in binary mode but passed `sys.stdin.read()` text to `write()`.
The identical latent defect in the subsequent `pod-identity.json` staging path
was found by source inspection. The aggregate pre-inference gate set was not
reached.

Fresh, restored and exact replay are `NOT_STARTED`. No Temporal workflow,
parser, model or inference started and no object-prefix write occurred. The D
PVC is retained and contains only pre-workload control evidence; it is not
classified as workload evidence.

Cleanup completed with disposition
`CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED`. The exact Deployment,
ReplicaSet, Pod and immutable ConfigMaps are absent; the retained PVC UID is
`0a04fa93-8832-47f3-b5c6-89ffc0852348` and PV UID is
`634c2111-02b5-4805-bbb4-bc52af2bd1ec`. Final Temporal/object health, PSI and
OOM checks passed. The 32 held Deployments remained closed.
