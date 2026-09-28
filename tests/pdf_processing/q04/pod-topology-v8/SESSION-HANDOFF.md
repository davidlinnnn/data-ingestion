# Q04 / #51 execution-session handoff

The two requested H tool defects are repaired, tested and reviewed. One I runtime
was executed and stopped without retry. Its failure is now determinable: normal
scratch cleanup violated the existing transport inventory contract. Q04 remains
unqualified; #51 is not ready to close. No push or ticket update was performed.

## Commits and verification

- Base `f0d40f7`: original H runner and evidence; unchanged.
- `49eba63`: versioned I repair, red/green regressions, recovered H diagnosis.
- `41a8816`: review-discovered interruption allowlist correction; actual I runtime
  used this exact commit. Generated source/worker/runner manifests bind its bytes.
- Final evidence commit is the commit containing this handoff and the draft.

104 offline tests passed, including the real controller-loop rejection path,
terminal rejection persistence, full launch argv, isolated projected workspace
and validate_reviewed_inputs, interrupted supervisor seal, actual process-group
interrupt/reap, real snapshot/mirror/archive readback and existing cleanup suites.
Two independent review axes found/fixed the new interruption allowlist omission
before runtime; corrected diagnosis and the full suite were independently checked.
The new I transport reproducer confirms both transient disappearance and the
cleanup receipt-gap defect without running another workload.

## Acceptance matrix

| Row | Current acceptance | This session's evidence / remaining gap |
| --- | --- | --- |
| H rejecting-sample retention defect | repaired; local regression proven | I persists raw node/cgroup samples and stop timestamps live; no I node-PSI rejection occurred, so the rejecting branch remains local-test proof |
| H worker-log cleanup defect | repaired; local and runtime proven | I worker-1.log coexists with worker-1; failed workload sealed with complete cleanup |
| Projected source, full argv, runtime contract | local and I pre-inference proven | 11/11 gates pass; not equivalent to ingestion success |
| YOLO 07 fresh | unproven | I registered 5/15 pages before transport-caused cancellation |
| YOLO restored / exact replay / full graph / fresh index | unproven | Not started / not produced |
| Native / WikiSkill 06 | unproven | No new runtime |
| AIMA 08 Q04 modes | unproven | Historical Q03 reference remains reusable within its existing identity limits |
| ACL 09 / Keynote 10 | previously proven bounded rows retained | No new changes or expanded claims |
| Integrated resource bounds / warm sequence and recycle | unproven | Partial I measurements and one recycle do not cover the required workload |
| Active telemetry-loss qualification / process and Pod drain | unproven | Supervisor cleanup is not the required workload recovery acceptance |
| Continuous evidence transport | failed; new remaining blocker | Transient scratch included in durable mirror; >5s stop/drain blocks final receipt |
| Failed-workload terminal sealing and readonly recovery | proven for I | 38 sealed inventory entries, exact digest/file-set verification; no automatic-export promotion |
| Six-fixture complete matrix / #44 bounds report | unproven | Existing missing matrix and cross-cutting rows remain |

## Root causes and uncertainty

H: recovered worker PSI full avg10=.54 plus cgroup-positive tail, inner VM PSI
abort -> workflow cancellation, overlapping outer supervisor interruption, then
bad worker-* glob blocks sealing. No Activity timeout/failure event; generic
activity_budget_exhausted is the cancellation fallback. Exact outer rejecting
sample and relative signal timing are missing. Task-level pressure cause and
full-workload capacity remain unknown.

I: group 1–5 Activity completes -> scratch is removed -> durable mirror reports
missing evidence -> controller SIGINT -> supervisor KeyboardInterrupt -> workflow
cancellation. All 194 node samples have full avg10=0; cgroup full avg10 reaches
.18, no OOM. The cause is transport, not Activity budget or node PSI. These
partial-window observations do not prove capacity sufficiency or justify a
threshold change, more memory or a new cluster.

## Runtime and cleanup

See [I results](first-window-evidence/RESULTS.md),
[H diagnosis](../diagnosis/yolo-pod-h-stop/DIAGNOSIS.md),
[review](REVIEW.md), and [next-window proposal](../diagnosis/yolo-pod-i-transport/NEXT-WINDOW.md).
I used q04/yolo-pod-cgroup-20260920-i/ with no retry. Automatic export failed;
original disposition remains INCOMPLETE. A separate read-only retained-PVC export
verified the terminal inventory. Owned runtime is gone; no owned Running Temporal
execution; all 32 held UIDs remain stopped; historical PVC UIDs unchanged. I PVC
40b563b4-05f2-4b86-bafb-efcb1422a296 and PV
256b3fea-6362-45f9-b0d9-cd364f08c07f are retained. Main checkout was not edited.

## Integration decision

Main can integrate the two reviewed tool repairs, diagnostics and retained failure
evidence while preserving every FAIL/unknown status. The runner is not ready for
another acceptance attempt until the transient/durable transport boundary and
failed-window forensic export are repaired and reviewed under a new identity.
Do not rerun I, relax guards, publish a fresh acceptance index, declare Q04 PASS,
or close #51. The [ticket draft](TICKET-51-UPDATE-DRAFT.md) is prepared for main to
publish; this session did not send it.
