# Q04 fixture 07 Pod topology v7

This directory contains the offline H candidate following the G runtime
identity failure. G remains immutable: its runner revision, raw evidence,
retained PVC and failure classification are not rewritten.

G proved the Pod topology, durable evidence directory, all 11 pre-inference
gates and staged import closure. It then rejected the historical A identity in
`pod-topology-v1/INTEGRATION-MANIFEST.json` against the active G phase and
prefix before workflow or inference began.

H adds `RUNTIME-INTEGRATION-MANIFEST.json`. It preserves every reviewed
artifact, policy and authorization-scope byte from the historical integration
manifest and changes only the runtime identity to the unique H phase and
prefix. The workload consumes that derived manifest. The existing
`workload_imports` pre-inference gate now also calls the real
`validate_reviewed_inputs` contract against the projected workspace and frozen
fixture bundle. A local regression reconstructs the generated ConfigMaps and
runs this complete gate in a fresh Python process.

The H PVC remains a new 1 GiB local-path claim. UID/GID 1000 exclusively owns
one `0700` child beneath the backend-owned mount root. A live H run must still
prove fresh, restored and exact replay, resource limits, durable evidence and
UID-fenced cleanup. Historical A/C/D/E/F/G PVCs and evidence remain untouched.
