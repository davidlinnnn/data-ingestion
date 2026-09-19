# Q04 fixture 07 Pod topology v3

This directory contains the offline D candidate that follows the C mount-root
failure. C remains historical: its runner, raw evidence, empty retained PVC and
failure classification are not rewritten.

The storage reconciliation shows that this kind cluster dynamically provisions
an in-tree `hostPath DirectoryOrCreate` PV through `rancher.io/local-path`; its
setup script creates the backing directory as `0777`, and no CSI driver is
registered. Kubernetes documents that hostPath volumes do not support ownership
management. The D contract therefore verifies the mount root as a backend-owned
directory and moves ownership isolation to one application-owned child created
exclusively by UID/GID 1000 at mode `0700`.

That design is locally executable and fail-closed, but has not been proven in a
live D Pod. No new Pod or PVC was created while preparing it. See
`STORAGE-RECONCILIATION.json`, `PRE-INFERENCE-GATES.md` and `RUN-PLAN.md` before
considering a separate runtime authorization.
