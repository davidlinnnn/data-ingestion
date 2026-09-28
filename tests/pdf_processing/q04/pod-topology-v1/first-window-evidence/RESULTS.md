# Q04 YOLO Pod/PVC window result

Status: **FAIL — worker Pod readiness timeout; no retry**

The single authorized run used commit
`e25918945ed1278d68119fd317ba68102c77da73` and authorization scope
`20aba35d2c792b31fea4b84699d568252cef3214159dfc14573b68b667c5ed0a`.
The fixed 1,500-second lease began at epoch `1789824497.64079`. No second run was
attempted.

## Admission

Outer admission passed after 49 samples and 60.67 continuous seconds. The
minimum available memory was 8,441,405,440 bytes, PSI full avg10 stayed zero,
and VM OOM kill stayed zero. T09a was healthy and idle, and the 32 fixed
historical Deployment identities remained at replicas/ready zero.

## Failure boundary

The four objects were created and the Deployment was scaled from zero to one.
PVC `q04-pod-cgroup-a-evidence-20260919-a` bound successfully on
`internal-a2a-vs6-local-worker2`. Pod
`q04-pod-cgroup-a-activities-5f5cfddf96-s6vn7`, UID
`46d4a137-0ce9-4e9a-8403-e2dc0200e6ae`, was scheduled and its container
started, but the runner did not accept it as Ready within 120 seconds and raised
`TimeoutError('worker Pod readiness expired')`.

No kubelet `Unhealthy` event was retained. After termination, the PVC host
directory was empty and `root:root 0777`, so no evidence establishes whether
the readiness probe remained false or `validate_pod` rejected an otherwise
Ready Pod because one of its status/image identity checks differed. The current
loop catches those validation errors without recording the last Pod status or
rejection reason. This run therefore does not assign a narrower root cause.

Initialization, Temporal workflow submission, parser/model loading, inference,
fresh/restored/replay and object-prefix writes did not start. The retained PVC
has no evidence records or terminal manifest and is `INCOMPLETE`, never PASS.

## Cleanup and retained state

The runner scaled the exact Deployment to zero and UID-fenced deletion of the
Deployment and both ConfigMaps succeeded. Its immediate final check occurred
while the Pod was still inside its 60-second termination grace period, so
`outer-cleanup.json` correctly recorded `NEEDS_INTERVENTION` rather than a false
cleanup claim.

The later read-only reconciliation confirmed:

- no Pod or ReplicaSet with `q04-run=q04-pod-cgroup-a`;
- no owned Deployment or source ConfigMap;
- T09a healthy, object health HTTP 200, and no running workflow;
- VM OOM kill zero, PSI full avg10 zero, and 8,447,488,000 available bytes;
- all 32 fixed historical Deployments still paused;
- PVC UID `ecba9310-5378-4e2b-a5c7-928ae194c86f` retained and Bound;
- PV UID `3fbb0e35-f926-4264-bb0c-0f2de49ef2c2` retained on the pinned node.

The reconciled state is `POST_RUN_CLEANUP_CONFIRMED_AFTER_GRACE`. The PVC remains
intentionally retained and was not modified or deleted.

## Required runner correction before another authorization

Record every readiness-loop Pod snapshot and the exact `validate_pod` rejection.
Capture the non-Ready Pod UID as soon as exactly one owned labeled Pod exists so
cleanup can UID-delete and wait for it even when readiness never succeeds. The
final identity/health check must wait through the Pod termination grace period
within the reserved cleanup budget. Any future run requires a new identity,
output location, reviewed commit and explicit authorization.
