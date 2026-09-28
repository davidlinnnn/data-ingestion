# #51 update draft — not published

The Q04 acceptance-tool repairs are complete and covered by regressions. The
controller now persists and flushes a sample before applying runtime guards, so
the rejecting sample survives. Cleanup now treats only `worker-N` directories
as worker roots, so sibling files such as `worker-1.log` cannot raise
`NotADirectoryError`. Historical runners, evidence, PVCs and object prefixes
remain unchanged.

H is still a failed run. Recovered history proves that the inner node-PSI
failure caused owned cancellation, while the outer node-PSI guard caused
supervisor interruption during cleanup; their exact relative decision/signal
order is unknown. The cleanup glob defect prevented terminal sealing. Temporal
`COMPLETED` carried business `failed`,
`activity_budget_exhausted`, `processing_complete=false` and zero registered
pages. There is no Activity timeout/failure event, so actual Activity budget
exhaustion is rejected for H. The original outer rejecting row was lost, so the
stalling task, exact guard interleaving, capacity sufficiency and need for a
different kind node remain unknown. No threshold was relaxed.

The repaired production lifecycle preserves one native WarmParser across
capture → restore → capture, counts captures toward request-20 recycling, keeps
scanned restore handoff behavior, and retains non-retryable checkpoint integrity
classification. Local regression, real offline Docling mode-switch and two-axis
review passed before runtime.

Controlled execution Q (`3b54e7d`,
`q04-aima-pod-cgroup-20260920-q`) ran once with no retry. All pre-inference
gates passed. AIMA08 fresh, restored and exact replay each completed 12 pages,
nine OCR components, 615-item oracle, four algorithms and eight continuation
edges. Temporal histories and decoded business results agree; all three document
and full-reference graph digests match. The lifecycle records one PID for three
captures and one native restore.

All 949 attribution samples are complete and the unchanged 4 GiB, PSI and OOM
gates passed. Outer telemetry recorded 924 samples, minimum available memory
6,144,229,376 bytes and peak cgroup usage 1,762,107,392 bytes. The sealed
82-entry inventory and 83-file archive independently match; archive SHA-256 is
`3d1da2cf5e2050797244d08cafd64905bb030ff9444229479c08524d1897a640`.
Owned runtime was removed, the evidence PVC remains Bound, Temporal is idle,
object health is 200 and all 32 held Deployments remain exact and off.

One evidence-label caveat is recorded: Q's sealed reviewed-window contract
inherits P's phrase `source-bound reap-before-spawn handoff`. Q's executable
measurement contract and attribution summary instead require and prove same-PID
warm continuity. The sealed artifact was not rewritten; the stale phrase should
be corrected under the next run identity.

Accepted scope now includes bounded current-producer AIMA08, plus the earlier
bounded YOLO07 and exact historical ACL09/Keynote10 identities. Native and
WikiSkill06 remain unproven for the current producer; ACL09/Keynote10 current
producer applicability is also unproven. The original 29-group cross-document
warm/request-20 recycle, native invalidation, compatible reuse, changed-profile
rejection, injected telemetry-loss fail-closed guard, and process/Pod
interruption/recovery gates remain open. Q04 is not a full PASS, and #51 is not
ready to close or merge solely from Q.

Evidence:
`tests/pdf_processing/q04/pod-topology-v16/first-window-evidence/RESULTS.md`

Matrix: `tests/pdf_processing/q04/CURRENT-ACCEPTANCE-MATRIX.md`
