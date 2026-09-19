# Durable evidence feasibility

Status: **offline design only; `NOT_RUNTIME_READY`**. No PVC, object, Pod, or
workflow was created while preparing this note.

## Existing capability

The target namespace already runs MinIO through Deployment `objects`. Its data
volume is PVC `object-data` (UID `ebd0ba41-443c-4971-859a-3b2ca8f5b1d4`), bound
at 2 GiB and currently Ready. The `standard` storage class uses
`rancher.io/local-path`, `WaitForFirstConsumer`, and reclaim policy `Delete`.
Consequently:

- MinIO objects survive a worker-Pod deletion because MinIO owns a separate PVC.
- A dedicated worker-evidence PVC also survives worker-Pod deletion while the
  claim is retained. Deleting that claim would delete its local-path volume.
- Both choices are node/local-cluster durability, not off-cluster backup.
- If the Kubernetes API is unavailable, the controller cannot truthfully
  guarantee scale-to-zero or Pod deletion. Durable evidence does not fix that
  control-plane failure.

## Option A: dedicated owned evidence PVC — recommended

Create one run-identity-named RWO PVC in `pdf-t09a-validation`, bind it to the
pinned worker node through the existing `WaitForFirstConsumer` behavior, and
mount it as the evidence root. Keep input bundle and scratch outside the
evidence claim. The runner records the PVC UID independently from the
Deployment/Pod UID.

On a normal terminal path, export and verify the archive, stop/delete the exact
Pod, then either retain the PVC until main review or delete it only under an
explicit artifact-retention decision. On an export failure, stop/delete the Pod
but retain the PVC. A later read-only recovery Pod can mount the claim on the
same node and recover evidence without the original worker or source-bearing
ConfigMaps.

Required acceptance details:

- capacity-size the claim before the window; 1 GiB is only a proposal, not an
  established bound;
- use a new claim name/UID and never reuse or overwrite historical evidence;
- fsync completed records/manifests and record an append-only durable inventory;
- a terminal PASS requires a read-back-verified terminal manifest, complete
  inventory, cleanup markers, and stable hashes;
- missing terminal manifest, partial file, failed fsync, or recovery-only PVC is
  `INCOMPLETE`, never PASS;
- do not give the Deployment an owner reference that garbage-collects the PVC;
- PVC deletion is a separate destructive action and is disabled by default.

This is the smallest design that removes Pod `emptyDir` as the sole evidence
copy while preserving the current one-container/cgroup topology. It adds one
Kubernetes object and one volume mount, so a future runtime authorization must
explicitly include PVC creation, retention, capacity, node locality, and later
deletion policy.

## Option B: incremental MinIO evidence — feasible with a bounded loss window

Use a separate immutable object prefix under the existing bucket. Upload only
complete chunks/files with sequence, offset, length, SHA-256, Pod/container/PID
identity, and idempotent object names. Commit a terminal inventory only after
read-back verifies every object. Never overwrite prior evidence objects.

This avoids a new PVC and already has credentials/service routing in the worker.
It adds uploader and reconciliation logic and shares the 2 GiB MinIO capacity
with workflow artifacts. More importantly, a process/Pod failure can occur
after a local write but before the final upload or inventory commit. The latest
unflushed sample or terminal marker may be lost. Such a run must remain
`INCOMPLETE`; incremental MinIO cannot promise zero loss on every failure path.

Before choosing this option, a future read-only check must measure free/logical
prefix capacity and existing object inventory. The current Store supports
immutable `put_once`, digest/read-back verification, and bounded inventory, but
its workflow artifact registration is not itself a raw diagnostic evidence
protocol.

## Decision

Recommend Option A for the next revision because it separates raw evidence from
workflow objects, survives worker deletion without a final network upload, and
requires less new failure-state logic. Option B is reasonable only if accepting
an explicitly bounded last-upload loss window and `INCOMPLETE` disposition.

Neither option authorizes server-side dry-run, source upload, PVC creation,
runtime execution, inference, service pause/resume, or historical artifact
deletion. The current runner remains `NOT_RUNTIME_READY` until one durable path
is implemented, locally tested, reviewed, and separately authorized.
