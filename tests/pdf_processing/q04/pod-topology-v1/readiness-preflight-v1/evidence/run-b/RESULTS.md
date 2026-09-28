# Q04 YOLO readiness preflight B result

Status: **FAIL — image identity contract rejected; no retry**

The single authorized execution used commit
`4e61b95d07834925c270c4c41f6c130881228891`, run identity
`q04-yolo-readiness-preflight-20260919-b`, and authorization scope
`70c17c3029933796cf9a40f6a8a2c2eeb40bb638945de7d95ec5840ebf43b2bb`.
No workflow, inference, PDF processing, source upload, object-store write, PVC
mount, or retained-PVC access occurred.

## Admission

Admission passed after 46 samples and 60.348 continuous seconds. Minimum
available memory was 8,406,179,840 bytes; PSI full avg10 and VM OOM kill stayed
zero. The fixed node/boot identity and all 32 held Deployment identities at
replicas/ready zero passed.

## Permanent rejection

The Pod reached `Running`, the container reached `Ready=True`, and the fixed
readiness probe passed. Events show the image was already present, followed by
container Created and Started; no readiness-probe `Unhealthy` event was
observed.

The fixed Pod spec image was
`docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
Kubernetes reported the container `imageID` as that same repository plus
manifest digest. The runner's reviewed image contract expected content ID
`sha256:60b91ce18ac0ef8d4efdec17e79946278f44f62c9fc346b7e19214d8b8ad10ce`,
so it raised `PodIdentityRejected('worker image digest changed')` immediately.

This establishes the reason for this preflight rejection. It does not establish
the missing imageID/status from the earlier failed window, whose root cause
remains unknown. No threshold or identity contract was changed after failure.

## Cleanup

The exact Deployment was scaled to zero and the exact Pod UID was sent a
UID-preconditioned delete with 60 seconds grace. The runner confirmed the Pod,
all CRI records and all four emptyDirs absent, then deleted the exact Deployment
UID and confirmed the ReplicaSet absent. Cleanup disposition is
`CLEANED_NO_INFERENCE_PREFLIGHT`.

An independent read-only reconciliation confirmed no run-labeled Pod or
ReplicaSet and no named Deployment. All 32 held Deployments remained off; VM
available memory was 8,410,963,968 bytes with PSI full avg10 zero and VM OOM
kill zero.
