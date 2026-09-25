# Server-side dry-run scope and endpoint provenance

This is a read-only inventory for review. It does not authorize or perform a
server-side dry-run, ConfigMap upload, Deployment create, workflow, or inference.

## Destination provenance

- kubeconfig context, cluster, and user: `kind-internal-a2a-vs6-local`
- Kubernetes API URL: `https://127.0.0.1:58329`
- Docker mapping: the `internal-a2a-vs6-local-control-plane` container publishes
  its `6443/tcp` endpoint at `127.0.0.1:58329`
- control-plane container ID:
  `1febdda42fb21f67f95d3222e51b35bbee19fda46b638c55f9e63cf33737cec0`
- control-plane image/version: `kindest/node:v1.34.3`, Kubernetes `v1.34.3`
- target namespace: `pdf-t09a-validation`, UID
  `97dbf297-9069-4143-8cdd-38b1490af27e`
- pinned worker node: `internal-a2a-vs6-local-worker2`, UID
  `b33ff221-3443-4b27-83bd-01ce69d0bb01`, boot ID
  `c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3`

These values were obtained from kubeconfig, Docker container metadata/port
mapping, Kubernetes `/version`, the Node object, and the Namespace object. No
token, client key, certificate body, Secret value, or ConfigMap value was read
from the cluster.

## Proposed API action

A future server-side dry-run would submit the four objects in `WORKER.yaml` to
the API server with the Kubernetes `dryRun=All` option. Although the API server
would not persist the objects, the complete object bodies would leave the local
process and be received and processed by the API endpoint above. It is therefore
an external transmission of the embedded source and evidence payload, unlike
the completed `--dry-run=client --validate=false` parse.

The rendered manifest SHA-256 is
`d50fa041caafe6d6138265940be3199541bd7f4fb071b5443bd0748a3a403d67` and
contains:

1. Immutable ConfigMap `q04-pod-code-a6501b471bd3193a`: 20 frozen production
   Python modules, 159,261 UTF-8 bytes. These are the `pdf_processing` package
   implementation for compatibility, continuation, enrichment, evidence,
   execution, object storage, OCR, parsing, preflight, processing/workflows,
   relationships, routing, supervision, Temporal integration, and the warm
   parser child. Purpose: mount the exact reviewed producer read-only at
   `/workspace/src/pdf_processing`.
2. Immutable ConfigMap `q04-pod-harness-b371166fdfa8f6da`: 47 files, 420,950
   UTF-8 bytes. Content types are Python runner/controller/worker/telemetry and
   oracle code; JSON fixture, oracle, review, budget, resource-analysis,
   integration, and historical-method evidence; and the deployment worker
   entrypoint. Purpose: mount the exact fixture-07 acceptance harness read-only
   at `/workspace`, including fresh/restored/exact-replay graph and source
   evidence checks, the Pod workload/init/transport adapters, and the 250 ms
   resource attribution collector.
3. PVC `q04-pod-cgroup-a-evidence-20260919-a`: 1 GiB, RWO, Filesystem,
   `standard`, no owner reference and automatic deletion disabled. Purpose:
   persist only state, raw evidence, cleanup markers and the terminal inventory
   across exact worker-Pod deletion. It contains no source or fixture payload at
   create time.
4. Inactive Deployment `q04-pod-cgroup-a-activities`, initially `replicas: 0`.
   Purpose: define the pinned one-container UID/GID-1000 worker Pod, immutable
   image, read-only source projections, scoped Secret references, emptyDirs,
   evidence-PVC mount,
   resource request/limit, security context, queues, and service addresses. A
   dry-run submits Secret *references* but does not submit or read Secret values.

The private fixture PDF/model bundle is not embedded in `WORKER.yaml` and would
not be transmitted by this dry-run. It is copied only by a separately authorized
runtime path after admission. No object-store payload or Temporal request is
part of the dry-run.

## Current approval state

The earlier server-side dry-run was rejected and must not be retried or
repackaged. Any future request must name this exact endpoint, manifest digest,
four-object scope, source-bearing ConfigMap payload and retained-PVC lifecycle.
Client-side parsing is
only syntax/rendering evidence; it is not server schema, admission, defaulting,
or policy evidence.
