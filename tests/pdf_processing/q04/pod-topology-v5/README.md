# Q04 fixture 07 Pod topology v4

This directory contains the offline F candidate that follows the E preflight
CLI-binding failure. E remains historical: its runner revision, raw evidence,
retained PVC and failure classification are not rewritten. F keeps the proven
mount and binary control-staging behavior, and maps every CLI option to the
`run_preflight()` interface before another workload attempt.

The storage reconciliation shows that this kind cluster dynamically provisions
an in-tree `hostPath DirectoryOrCreate` PV through `rancher.io/local-path`; its
setup script creates the backing directory as `0777`, and no CSI driver is
registered. Kubernetes documents that hostPath volumes do not support ownership
management. The F contract therefore verifies the mount root as a backend-owned
directory and moves ownership isolation to one application-owned child created
exclusively by UID/GID 1000 at mode `0700`.

That design is locally executable and fail-closed, but has not been proven in a
live F Pod. No new Pod or PVC was created while preparing it. See
`STORAGE-RECONCILIATION.json`, `PRE-INFERENCE-GATES.md` and `RUN-PLAN.md` before
considering a separate runtime authorization.

The immutable v3 `READONLY-PREFLIGHT-RECONCILIATION.json` records the original
cache-only model lookup. `MODEL-ARTIFACT-RESOLUTION.md` adds the subsequent
read-only proof that all 17 profile artifacts exist at their actual runtime
locations. The remaining F-specific gap is live execution of this topology.
