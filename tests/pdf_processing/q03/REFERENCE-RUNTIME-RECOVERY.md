# Separate reference-inventory recovery — 2026-09-16

User authorized investigation and repair while Q03 qualification proceeded.
Namespace: `internal-a2a-vs6-local`; deployment: `reference-inventory-runtime`.

## Cause and repair

The initial readiness assertion failed at 0/2. Both application startup paths
failed with `TopologyIncompatible`, caused by JetStream `stream not found`.
Management-credential read-only inspection confirmed both
`IA2A_REFERENCE_CONTROL` and `IA2A_REFERENCE_LIVE` were absent. Runtime and
bootstrap stream names and subject prefix matched. Thus this was missing
topology, not merely a runtime permission or naming failure.

The existing image's privileged bootstrap explicitly creates absent streams and
rejects incompatible existing streams. Ran that command with the existing Job's
image/configuration/secret references using a temporary diagnostic Pod. No
credentials were printed, no existing stream deleted, no database migration run.
Restarted only the runtime Deployment after successful bootstrap. Rollout and
its HTTP `/health/ready` probe passed: two replicas Ready, zero restarts. The
temporary Pod was deleted and absence confirmed.

## Durability follow-up

NATS startup logs show its actual JetStream store is `/tmp/nats/jetstream`.
The Deployment mounts an `emptyDir` at `/data` but does not configure JetStream
to use that path. The active store is therefore in the container writable layer;
container recreation can lose topology/data. The historical cause of deletion
cannot be proved solely from the current snapshot, but this persistence gap is
verified. Recreating streams does not recover any previously lost messages.

A durable correction should be made in the owning infrastructure source:
configure an explicit storage directory backed by PVC, preserve/migrate current
stream data during a controlled NATS outage, re-run topology verification and
exercise restart recovery. Do not simply patch the storage path and restart,
which would hide existing stream state in a different directory. This data
migration was not bundled into the application availability repair.

The PDF repository received no reference-inventory production code changes.
