# Q04 YOLO Pod cgroup G window result

Status: **FAIL_MANIFEST_RUNTIME_IDENTITY; no retry**.

The single authorized run used commit
`2ea4f565f8446880cde8065bd5aa694a4caedf4b`, run identity
`q04-yolo-pod-cgroup-20260920-g`, and authorization scope
`b94f7ba6a9abd197d2b30625822bbad5b09a8aba50dad0ef2ae29e1a5938f05d`.
No second G run was attempted.

Outer admission, readiness, image/PVC identity, durable directory setup and all
11 aggregate pre-inference gates passed, including projected workload imports.
The supervisor and init then completed. Init captured the original fixture PDF
under the new G object prefix, but no Temporal workflow or parser/model inference
started.

The reviewed workload rejected the historical A runtime identity in
`pod-topology-v1/INTEGRATION-MANIFEST.json` against the active G phase and
prefix. Fresh, restored and exact replay did not begin. This is a harness
contract-staging defect, not a document-processing result.

Cleanup completed with disposition
`CLEANED_WITH_PVC_RETAINED_WORKLOAD_EVIDENCE_INCOMPLETE`. The exact
Deployment, ReplicaSet, Pod and ConfigMaps are absent. The retained PVC UID is
`3b118998-677e-4974-8973-d3efe1be8a28` and PV UID is
`5c46548b-5e5a-403b-8b22-63ced1a79d6f`. Final cluster health, PSI and OOM
checks passed, and the 32 held Deployments remained closed.
