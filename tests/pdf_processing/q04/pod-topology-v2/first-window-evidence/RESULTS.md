# Q04 YOLO Pod cgroup C window result

Status: **FAIL — evidence mount fsGroup ownership gate; no retry**

The single authorized run used commit
`fcae991d7fc6ed6ef2881cef0dc64c449f6de86a`, run identity
`q04-yolo-pod-cgroup-20260919-c`, and authorization scope
`bc889ca368fa9d6bd123d80004fd8f9f9f149e2ca4ee726ed470241b218c0202`.
The fixed 1,500-second lease began at epoch `1789829714.517576`. No second run
was attempted.

## Admission and readiness

Outer admission passed after 48 samples and 60.40 continuous seconds. The
minimum available memory was 8,371,265,536 bytes, PSI full avg10 stayed zero,
and VM OOM kill stayed zero. T09a was healthy and idle, and the 32 fixed
historical Deployment identities remained at replicas/ready zero.

The Deployment, ReplicaSet, Pod and both immutable ConfigMaps were created. The
worker Pod became Ready with the reviewed image digest and these identities:

- Deployment UID `845d2aeb-11cd-4b01-97fb-73f767070595`;
- ReplicaSet UID `267b52cc-2285-40c0-b188-2c865e2ce2ec`;
- Pod UID `5f4219b1-73d5-4b90-9a0f-dfc24156810a`;
- container ID
  `containerd://a231a4908e87b213cd46320dc8540bc3f1e4731d3c49b65491ec7cd15e166dca`.

## Failure boundary

Immediately after readiness, the runner checked the mounted evidence volume.
It was writable and had group-write permission, but its observed ownership was
`uid=0`, `gid=0`, mode `0777`. The reviewed contract requires `gid=1000` from
the Pod `fsGroup`, so the runner raised
`ValueError('evidence mount fsGroup ownership changed')` and stopped.

The failure happened before source upload, workload initialization, Temporal
workflow submission, parser/model loading, inference or object-prefix writes.
Fresh, restored and exact replay are all `NOT_STARTED`; graph, oracle, source,
replay and resource acceptance are `NOT_EVALUATED`. The terminal worker-cgroup
sample observed 7,409,664 bytes, PSI zero and no cgroup or VM OOM event. This is
only control-plane/idle worker usage and is not a workload peak.

The absence of `supervisor-ownership.json` caused a cleanup evidence-capture
error because the supervisor had never started. This did not prevent owned
resource cleanup. It is retained verbatim in `outer-cleanup.json` and is not
reclassified as workload evidence.

## Cleanup and retained state

The runner scaled the exact Deployment to zero, sent UID-fenced Pod deletion
with a 60-second grace period, and UID-fenced deletion of the Deployment and
both ConfigMaps. Its final checks passed with disposition
`CLEANED_WITH_DURABLE_EVIDENCE`.

The later read-only reconciliation confirmed:

- no owned Deployment, Pod, ReplicaSet or source ConfigMap remains;
- T09a healthy, object health HTTP 200 and no running workflow;
- VM OOM kill zero, PSI full avg10 zero and 8,385,093,632 available bytes;
- all 32 fixed historical Deployments retain exact UIDs and remain paused;
- new PVC `q04-pod-cgroup-c-evidence-20260919-c`, UID
  `b1e16e99-90d5-42b7-b802-dca6643170be`, remains Bound to PV UID
  `c0629afb-4db0-4e93-b289-eb0b8f37bcc6` and is empty;
- earlier PVC `q04-pod-cgroup-a-evidence-20260919-a`, UID
  `ecba9310-5378-4e2b-a5c7-928ae194c86f`, remains Bound and empty;
- both local-path host directories were observed as `root:root 0777`.

No cleanup intervention is required. The new PVC is intentionally retained;
the earlier PVC was not modified or deleted.

## Remaining acceptance work

The mount ownership contract must be reconciled before another authorized
window. This result does not establish that the current local-path behavior is
acceptable, and it does not authorize weakening the gate. Fixture 07 still
requires fresh/restored/exact replay, complete graph and oracle checks, source
evidence, exact replay proof, workload resource attribution and Pod drain. A
future run requires a reviewed plan, a new identity and separate authorization.
