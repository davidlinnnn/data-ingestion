# Readiness preflight B offline reconciliation

The authorized run remains **FAIL_IMAGE_ID_CONTRACT**. Its admission,
Ready/probe and cleanup observations remain direct evidence; this offline work
does not change its result. The first Pod/PVC window remains a distinct
readiness failure with unknown root cause and is not retrospectively accepted.

The committed final Pod snapshot reports spec image and Kubernetes `imageID`
`docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`,
status image `docker.io/library/pdf-checkpoint-prototype:linux-v2`, restart count
zero and a concrete containerd container ID. Local read-only containerd content
proves `8ffa…` is an OCI platform manifest rather than an index. Its config
descriptor is `60b…`; the exact config bytes identify `linux/arm64`. CRI inspect
binds config ID `60b…`, the pinned repo digest `8ffa…`, and the local status tag.

The prior validator stripped wrappers and compared every representation to the
config digest. It therefore rejected the valid repository/platform-manifest
representation. The replacement parses representation kind and requires the
corresponding repository, manifest, config, status tag and platform evidence.
It rejects wrong values and bare content IDs that cannot bind a repository.

All inspection was local and read-only. No registry access, pull, image update,
Kubernetes mutation, source upload, workflow or inference was performed.
