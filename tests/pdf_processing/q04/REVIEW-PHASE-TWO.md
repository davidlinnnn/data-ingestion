# Q04 phase-two review

Fixed point: `a82d1c8`. Initial implementation reviewed: `8c28eb5`.
Two independent reviewers applied the code-review Standards and Spec axes.

## Standards and correctness

No separate AGENTS/domain/triage violations. Two initial correctness findings and one follow-up boundary finding:

1. P1: an exited local kubectl launcher skipped remote worker cleanup. The fix
   checks the original Pod UID and exact worker command/recorded creation time
   independently of launcher liveness, preserves uncertain ownership for retry,
   and retains a remote absence record. Local transport tests cover disconnected
   launcher, pre-publication startup failure, changed Pod identity and retry.
2. P2: cleanup failures could hide the initiating error and skip subsequent
   evidence capture. The original failure is now durable before cleanup, each
   operation records its own outcome, and history is required before success.
   The local regression injects simultaneous cancellation, worker cleanup,
   publication scan and history failures; all are retained without losing cause.

3. Follow-up P1: a parent already gone could leave its parser unaudited. Cleanup
   now retains ownership until child and scratch absence are proven; missing proof
   is explicitly pending, even when no worker command remains. Negative tests cover missing local proof and a surviving orphan in the remote
   transport case.

The independent Spec reviewer rechecked P2: zero residual findings.

## Spec

Zero actionable findings on six fixtures, graph/oracle coverage, reuse,
invalidation, old-request protection, warm/resource/drain and bounded historical
reuse. Process recovery and optional Pod recovery remain distinct. The adapter
and local test results do not accept real Temporal/K8s qualification or close #51.

Final local validation and artifact bindings are in PHASE-TWO-RESULTS.md and
`evidence/phase-two-local-final.json`. All earlier failure logs and the initial
implementation evidence remain unchanged.

Final recheck: Spec independently rechecked the parent-gone P1 and P2 fixes;
zero residual findings. Root reviewed ownership constraints and corrected the
normal-launcher-exit race. Final Standards/Spec residual count: 0.
Combined suite: 101 PASS in 59.257 seconds; Pyright: 0 errors/warnings.
