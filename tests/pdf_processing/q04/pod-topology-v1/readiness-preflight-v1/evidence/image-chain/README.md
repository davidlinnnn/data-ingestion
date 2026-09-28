# Fixed local image identity chain

These files are read-only captures made after readiness preflight B. No registry
request or image pull was used.

`platform-manifest.json` is an OCI image manifest whose byte digest is
`sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
It points to `config.json`, whose byte digest is
`sha256:60b91ce18ac0ef8d4efdec17e79946278f44f62c9fc346b7e19214d8b8ad10ce`.
The config and CRI inspection both identify `linux/arm64`. `cri-inspect.json`
binds that config ID to repo digest
`docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`
and local tag `docker.io/library/pdf-checkpoint-prototype:linux-v2`.

The preflight Pod snapshot therefore used a valid repository/platform-manifest
`imageID`; it did not report the config digest. The run remains historically
`FAIL_IMAGE_ID_CONTRACT`: this later evidence explains the validator defect but
does not rewrite the recorded result. The earlier first-window readiness
failure remains a separate unknown cause and is not retrospectively accepted.
