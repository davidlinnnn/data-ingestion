# Q04 AI current-v3 Wiki06/native matrix

Status: **bounded matrix passed; #51 remains open**. See
[independently verified results](first-window-evidence/RESULTS.md).

AI used the existing `kind-internal-a2a-vs6-local` cluster and
`pdf-t09a-validation` namespace with new run identity
`q04-matrix-pod-cgroup-20260924-ai`, object prefix
`q04/matrix-pod-cgroup-20260924-ai/`, and retained evidence PVC
`q04-pod-cgroup-ai-evidence-20260924-ai`. Its inactive topology started at
zero replicas. One controlled execution ran without automatic retry.

The same AH v3 bundle and exact source-reviewed oracle were reused. Wiki06
and native each ran fresh, checked restored/new request, and exact replay in
one worker lifetime. Every document had to equal its AH warm document digest.
The 250 ms attribution cadence, one-second sample gap, node/Pod PSI and OOM
guards, memory floors, request-20 parser budget, and deadlines were unchanged.
The [runtime integration manifest](RUNTIME-INTEGRATION-MANIFEST.json),
[source manifest](SOURCE-MANIFEST.json), [runner manifest](RUNNER-MANIFEST.json),
and [inactive topology](WORKER.yaml) bind that execution.

Seven AI local tests passed, including projected workspace imports, fail-closed
AH digest binding, seal-to-mirror finalization and cleanup with a retained
`worker-1.log`. Six inherited supervisor interruption regressions also passed.
Independent Standards and Spec review found and resolved a missing success
contract field before runtime. The current-v3 YOLO/AIMA fresh comparison,
ACL/Keynote applicability, method invalidation and recovery gates remain open.
