# Kubernetes gate: inconclusive — runtime unavailable

Checked 2026-09-11. This is new preparation evidence, not a replacement for the
[measured macOS/local Temporal results](../VERDICT.md).

## Environment observations

- Working branch: `codex/pdf-checkpoint-prototype`; prior commit/evidence preserved.
- Docker CLI exists but `/Users/david/.docker/run/docker.sock` does not exist;
  `docker info --format '{{.ServerVersion}}'` could not reach a daemon.
- `kubectl cluster-info --request-timeout=5s` initially hit sandbox restrictions.
  An approved read-only unsandboxed retry confirmed **connection refused** at the
  configured local API endpoint. This is not merely an unrequested permission.
- No cluster mutations, container build, shared bucket writes, Pod-loss run, or
  shared-storage transfer benchmark was performed. No contexts or credentials changed.

## Completed preparation

- `object_store.py`: candidate immutable-object/conditional-registration protocol,
  deliberately separate from the unchanged local harness.
- `probe_protocol.py`: executable in-memory or real-service probe. The recorded
  [unit evidence](protocol-unit-evidence.json) used only a test double and passed
  incomplete registration rejection, registered-result retry reconciliation, and
  eight competing attempts resolving one accepted manifest.
- `Dockerfile`: Linux baseline recipe with required caller-selected base digest;
  package/model pins retained. **Not built or verified.**
- `README.md`: exact continuation steps, identity constraints, storage semantics,
  heartbeat/child cancellation work and evidence needed for actual distributed runs.

The probe is a protocol-level check with tiny synthetic bytes. It proves neither
S3 compatibility nor parser integration, cross-Pod recovery, power-loss durability,
interrupted multipart handling, or performance for the 52.7 MB checkpoint. The
original full-brief verdict remains **inconclusive**.

Next external prerequisite: a running disposable Linux container/Kubernetes runtime
and selected isolated shared storage. Then build the image, establish its baseline,
validate actual store semantics and integrate/run real Pod fault trials. This
preparation does not select the production storage service or infrastructure model.
