## Q04 acceptance update — AB

AB (`q04-warm-pod-cgroup-20260921-ab`) executed once from commit `d58118b`; automatic retry was disabled. All 11 pre-inference gates passed. All five Temporal workflows completed with `processing_complete=true` and registered 28, 15, 12, 51 and 28 pages. The fixed warm sequence issued 29 group requests and recycled the parser at request 20 (PID 131 → 1836).

The combined warm/resource acceptance row remains **unproven**. Of 1,305 process samples, index 691 observed fresh child identity `(pid=1753,start_ticks=19040994)` exit during enumeration. Adjacent complete samples and the complete stable retry prove the exact exit and leave no unclassified cgroup transition, but the exited child's PSS is unknown. Under the adopted contract, `cgroup_resource_complete=true` and `process_attribution_complete=false`; the workload correctly failed closed after business completion. We rejected and removed a proposed one-line change that would have mislabeled the unknown PSS as complete.

This was not a PSI, OOM, memory-floor, deadline, Temporal Activity, ingestion-business, or supervisor-interruption failure. Node and Pod-cgroup full PSI remained 0.00, VM/cgroup OOM counters remained zero, minimum available memory was 5,161,975,808 bytes, and outer/inner cgroup maxima were 2,601,865,216 / 2,637,160,448 bytes. No threshold or cluster change is supported.

Cleanup passed independently. The owned Deployment, Pod and ConfigMaps are absent; PVC `q04-pod-cgroup-ab-evidence-20260921-ab` remains Bound with UID `1111fa94-ca48-4a4a-a5ef-c7853f3904e4`; all 32 historical Deployments remain exact/off. Historical evidence and prefixes are retained.

Changes are committed on `codex/q04-acceptance`:

- `d58118b` — classifier support for the narrowly proven complete-retry membership-exit shape, with regression tests and AA evidence.
- `30d173b` — AB runtime evidence, diagnosis and current acceptance matrix.

Validation: 51 focused unit/regression tests pass; both specification and repository-standards reviews report no findings on the final AB classification and matrix.

Next: do not rerun the same warm runtime. Design and locally verify a stable complete-process snapshot that retains every cgroup guard observation and does not reinterpret unknown PSS as known. After review, use a new bundle/run identity/prefix/PVC for one controlled no-retry execution. #51 is not ready to close: the warm/resource row plus the remaining current-producer fixture, reuse/invalidation, telemetry-loss, process-drain and Pod-drain rows are still unproven.
