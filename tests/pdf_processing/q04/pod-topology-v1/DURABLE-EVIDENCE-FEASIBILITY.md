# Durable evidence feasibility

Status: **Option A implemented and locally fault-tested; `READY_FOR_AUTHORIZATION`**.
No PVC, object, Pod, workflow, source upload, or inference was created while
implementing it.

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

## Option A: dedicated run-owned evidence PVC — implemented

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

The fixed claim is `q04-pod-cgroup-a-evidence-20260919-a`: RWO, `standard`,
Filesystem, 1 GiB, no owner reference, and an explicit automatic-delete=false
annotation. `/q04-evidence` is the only durable evidence/state root. The private
input bundle and capacity record remain on `/q04-control`; parser scratch remains
the separate `/scratch` emptyDir. Cleanup deletes the exact Pod, Deployment and
source ConfigMaps by recorded UID while retaining the claim on every exit.

The capacity decision is recorded in `EVIDENCE-CAPACITY.json`. Four retained
fixture-07 archives were inventoried locally. The largest archive was 26,316,800
bytes; its members totalled 26,220,356 bytes across 101 files. The maximum JSONL
file was 4,234,743 bytes and the maximum aggregate JSONL payload was 4,712,396
bytes. The claim reserves its final 128 MiB and stops before logical evidence
exceeds 896 MiB, leaving 939,524,096 usable bytes, 35.83 times the observed
maximum uncompressed inventory. This is headroom, not a future size guarantee.

Implemented acceptance details:

- the controller samples logical evidence bytes and filesystem free bytes; the
  Pod-local writer rejects a record before it crosses the same 128 MiB reserve;
- use a new claim name/UID and never reuse or overwrite historical evidence;
- every record uses create-only temporary write, flush, file fsync, atomic
  replace and directory fsync; the terminal path fsyncs completed files and
  directories before committing its immutable inventory;
- a terminal PASS requires a read-back-verified terminal manifest, complete
  inventory, cleanup markers, and stable hashes;
- missing terminal manifest, partial file, failed fsync, or recovery-only PVC is
  `INCOMPLETE`, never PASS;
- neither the Deployment nor any other object owns the PVC;
- PVC deletion is a separate destructive action and is disabled by default.

The terminal manifest is committed only after cleanup markers exist, then read
back with every inventory size and SHA-256. `PASS_CANDIDATE` means only that this
Pod-local durable protocol succeeded; the outer controller must still validate
the graph/oracles, transport ledger, resource guards, cleanup, claim UID and
post-cleanup health before accepting the run. Missing terminal, partial
`.incomplete` file, capacity stop, failed fsync, missing inventory member,
digest mismatch, PVC/PV/node identity mismatch, export failure, or API cleanup
uncertainty cannot produce a runner PASS.

On controller export failure, the runner still stops submission, terminates the
exact owned process group, scales the exact Deployment to zero, deletes the
exact Pod and source objects, and retains the PVC. A separately authorized
recovery helper must mount that exact claim read-only on the recorded node and
record claim UID, PV UID, node, access mode, run UID/GID/fsGroup and filesystem
permissions before copying data. If the API is unreachable, the cleanup record
is `NEEDS_INTERVENTION`; it never claims the Pod is stopped or the claim is
retained without API proof.

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

## Decision and remaining gate

Option A is the implemented path. Option B remains an unselected design. The
runner is ready for main-session review and a new explicit authorization whose
scope includes the four-object payload, claim retention, and fixed digest.

This implementation does not authorize server-side dry-run, source upload, PVC
creation, runtime execution, inference, service pause/resume, claim deletion,
or historical artifact deletion. The 32 held Deployments remain off.
