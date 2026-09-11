# Real Linux / Kubernetes recovery extension — THROWAWAY

Question and scope: [prototype brief](../../../design/pdf-checkpoint-prototype-brief.md).
[Results](VERDICT.md) distinguish actual measured runs from remaining gaps.
[Earlier environment-blocked preparation](PREPARATION-VERDICT.md) remains available.
Original macOS code/evidence and `uv.lock` are unchanged.

## Runtime and isolation

The measured experiment uses local Docker Desktop ARM64 and the existing local kind
cluster, in **only** namespace `pdf-checkpoint-prototype`. The YAML files pin MinIO
and Temporal image digests. Both have separate PVCs; worker artifacts are fetched
through HTTP/S3, not a worker-shared filesystem. The volumes use kind's local-path
storage, so this tests Pod loss, not node/host/disk loss or production HA.

The YAML node selector is this machine's `internal-a2a-vs6-local-worker2`. Adjust it
only for an explicitly disposable target. Do not apply these files to an arbitrary
current context. Credentials in YAML are deliberate local-only prototype values.

## Build and establish baseline

The parent README describes acquiring the fixed PDFs/model snapshots. The Docker
build expects those existing ignored `fixtures/` and `PROTOTYPE-wipe-me/hf/` inputs.
It verifies the original model hashes while generating a **new Linux method**.

```sh
cd docs/prototypes/pdf-checkpoint-prototype
docker build -f k8s/Dockerfile -t pdf-checkpoint-prototype:linux-v2 .
```

The base image is digest-pinned Python 3.12.13. `linux-requirements.txt` is exported
from `uv.lock`, excluding Torch/GPU packages; Torch 2.14.0+cpu and torchvision
0.29.0+cpu are installed from the official CPU index. This avoids unused CUDA
libraries, and is explicitly a different runtime from macOS. Temporal requirements
and boto3 are installed before baseline creation. Exact resolved inventory and image
identity are captured in `evidence-linux/linux-method.json` and `image-v2.json`.
A rebuilt image may resolve OS/S3 transitive versions differently; record a fresh
baseline rather than pretending package pins alone guarantee the old image digest.

Load the image into the selected kind node (a local registry is another option):

```sh
docker save pdf-checkpoint-prototype:linux-v2 | docker exec -i internal-a2a-vs6-local-worker2 ctr -n k8s.io images import -
kubectl create namespace pdf-checkpoint-prototype
kubectl apply -f k8s/storage.yaml -f k8s/temporal.yaml -f k8s/workloads.yaml
kubectl -n pdf-checkpoint-prototype wait --for=condition=Ready pod/coordinator --timeout=60s
kubectl -n pdf-checkpoint-prototype exec coordinator -- /experiment/.venv/bin/python k8s/bootstrap.py
```

The measured run also loaded the cached MinIO and Temporal images into that node.
`bootstrap.py` performs native/scanned uninterrupted conversion, capture, fresh-process
restoration and full-field comparison before publishing baseline references. Existing
method/platform/package checks remain enforced. All nodes used here have the same
kernel; cross-kernel restore compatibility is not claimed. Raw original metrics name
`ru_maxrss` as macOS bytes; the evidence copies explicitly normalize Linux KiB to bytes.

## Real store and concurrent registration checks

```sh
kubectl -n pdf-checkpoint-prototype exec coordinator -- /experiment/.venv/bin/python k8s/probe_protocol.py --bucket pdf-prototype --endpoint-url http://objects:9000 --prefix protocol-linux
kubectl apply -f k8s/race-pods.json
```

The probe checks eight simultaneous writers, incomplete attempted outputs, accepted
result reconciliation, and a real uncompleted multipart upload. The multipart upload
is then aborted; it does not simulate a TCP connection dying mid-request. The race
Pods rendezvous after staging different results, then compete for one registration.
Change their operation string/names for a fresh run. The JSON currently references
the original measured `linux-v1` image; use the available image for a new experiment
and record its identity. Small synthetic payloads test semantics, not parser fidelity.

`object_store.py` writes immutable attempt objects, reads back/hashes all bytes, then
conditionally creates the accepted manifest with `If-None-Match: *`. Racing losers
resolve the winner. Retries revalidate accepted data. Unregistered attempts are not
reusable, even if some files are complete. 409/transport errors propagate for retry;
permission failures are not cache misses. This relies on the real service's conditional
write behavior, which was tested on MinIO, not inferred from the in-memory double.
[AWS reference](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).
The local experiment assumes writers never delete or overwrite accepted objects;
production IAM/object retention enforcement is outside its scope.

## Temporal normal, fault and reuse runs

Use a **fresh prefix and dedicated task queue per independent trial**. Worker and
client must have identical prefix/queue configuration. Fully stop obsolete workers
when changing image/configuration; a rolling update can otherwise route Activities
to incompatible stores. This failure was observed and retained in evidence.

`prepare_run.py linux-v1 NEW_PREFIX` copies immutable baseline references and refuses
an existing prefix. Copy that helper to the coordinator if using the originally
measured image, which predates the helper. Then configure the deployment environment
`PDF_STORE_PREFIX=NEW_PREFIX` and `PDF_TASK_QUEUE=NEW_QUEUE`, and scale to one worker.
Run in the coordinator with the same environment:

```sh
kubectl -n pdf-checkpoint-prototype exec coordinator -- env PDF_STORE_PREFIX=NEW_PREFIX PDF_TASK_QUEUE=NEW_QUEUE /experiment/.venv/bin/python k8s/driver.py normal
```

For a separate fault trial, prepare another fresh prefix/queue, start the matching
worker, run `python3 k8s/kill_faults.py` on the host, and run `driver.py fault` in the
coordinator. The controller deletes **only** labeled prototype worker Pods at five
announced points. It records Pod names, UIDs and deletion responses. The actual
runtime termination state must be collected as well; API deletion alone is not proof
that a container stopped. Run `driver.py reuse` with the completed fault trial's
prefix/queue to demonstrate reuse without new producers.

Fault points are deliberately synchronized: after group registration before Activity
acknowledgement; after page 7 persistence during an unfinished group; after the first
shared-object upload before group registration; at reading-order invocation entry;
and after OCR engine initialization before recognition. A real worker Pod is killed,
not an Activity exception substituted for Pod loss. Assembly/OCR points are stage
entry boundaries, not random interruption deep inside model computation.

The workflow uses 15-second heartbeat and ten-minute start-to-close timeouts. Child
processes run in separate process groups; Activity cancellation cleanup kills a still
running child. The fault upload callback intentionally blocks until the Pod is killed;
live cancellation of that test-only callback is not validated. Accepted manifests,
not cancellation or worker liveness, decide reuse.

## Evidence and cleanup

`driver.py` saves result, full Temporal history and durable ledger in coordinator
scratch. Copy them after each trial. `export_store.py` copies **all** isolated bucket
objects into coordinator scratch; preserve that directory and Linux baseline before
removing the namespace. The helper can be copied into the original coordinator image.
Large artifacts belong under the ignored parent `PROTOTYPE-wipe-me/`, not committed
alongside small evidence. `summarize_linux.py` checks the copied normal/fault/reuse
records and generates the concise measured summary.

The normal-path measurement includes a deliberately simple one-second polling loop
around publication (up to one second per Activity), repeated Python/model startup,
local validation and readback. S3 request timings are reported separately. It is not
an optimized throughput benchmark. Artifact hashes and full document equality are
checked before OCR; OCR checks source coordinates, matching crop pixels, caption
content and document-relative references instead of a macOS-specific text index.

After copying evidence, cleanup is scoped to `kubectl delete namespace
pdf-checkpoint-prototype`. Never delete the existing kind cluster or unrelated
images/workloads. Consult the verdict for the measured run's actual cleanup status.
