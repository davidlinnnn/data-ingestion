# Q01 + Q02 joint runtime reconciliation — 2026-09-16

**Bounded runtime matrix PASS.** Q01/Q02's previously missing full-request,
actual-selected-OCR and real checked parsing/assembly reuse evidence is now present.
Main publication/merge and ticket updates have not occurred. Q04 and T09a #44
remain separate broader qualification gates. This report supersedes the earlier
NOT RUN statements for the exact cases below, not for broader support claims.

## Outcomes

Executed on the existing K8s `pdf-t09a-validation/coordinator`, using actual
Temporal workflows/Activities and versioned shared object storage. The complete
cases used native captured AIMA original pages 99–110, not seeded upstream results.

| Case | Result |
| --- | --- |
| Fresh | PASS: all 12 pages in 3 native groups, assembly, 9 selected actual OCR executions; corrected continuation and independently scored BFS/uniform-cost relationships on the same delivered document |
| New request, fresh process | PASS: all 3 groups plus assembly reused through checked shared storage; OCR executed for the new selection; evidence/final identities changed |
| Exact accepted request, fresh process | PASS: parsing/assembly and all 9 OCR outcomes reused; exact same final identity |
| Evidence-only policy variant, fresh process | PASS: all groups and assembly reused; new evidence/final identity; both required relationships still pass under the selected-region policy |
| Seeded final-boundary fault matrix | PASS: 29 cases, 3 successful deliveries and 26 expected failures with no complete registration; same production inventory as full-request cases |

The fault matrix remains explicitly seeded and is not itself native/OCR evidence.
Full cases supply that evidence separately. New requests rerun selected OCR;
this is not a claim of OCR reuse across new requests. No same-process warm-state,
Pod-loss/drain or six-fixture acceptance is inferred from fresh-process reuse.

## Actual defect found and fixed

Trial A failed before workflow submission because the macOS-specific lock directory
was absent in Linux. Driver locks and private oracle/input locations are now
configurable. Historical trial A is retained; its services were restored.

Trial B completed parsing and all 9 OCR components but failed at finalization:
`relationship_evidence_attribution_mismatch`. Typed content evidence hashes the
retained serialized `document.json`; Q02 compared this to a compact re-encoding
of the parsed dict. Legitimate whitespace/serialization differences therefore
failed, while a incorrectly re-encoded evidence digest could pass the old check.

New publication tests reproduced BOTH errors before the fix. Finalization now
compares the evidence hash against the exact document artifact in the checked
assembly registration. Relationship structural hashing remains its existing
separate contract; no evidence field or original artifact was rewritten. The
runtime consumer check uses the retained bytes too. Trial B's final publication
was correctly prevented; a separate storage audit found no complete registration.

Trial C uses a new producer inventory, release/request identities and storage
namespace. It passes all cases above. Source PDF, historical trials, and prior
accepted requests were not reinterpreted or replaced. Production changes are
limited to this hash comparison; other adjustments are harness portability and
regression evidence.

## Regression and evidence

- Serialized-document regression: observed RED (one false rejection, one false
  acceptance), then GREEN; Q02 suite 13 PASS.
- Combined local suite after correction: **42 PASS**, including scanned
  restoration, process supervision, Q01/Q02 and joint oracle tests.
- Expanded production/harness/test typecheck: zero errors/warnings (run before
  addition of the straightforward combined suite runner).
- Machine-readable cases, producer hashes, workflow IDs, artifact identities and
  history hashes: `evidence/runtime-20260916/summary.json`.
- The same directory retains fault-matrix results, capacity telemetry, replica
  restoration state, API health, image/Pod identity, final cleanup audit and logs.
- Private full histories/admissions/results remain at
  `/private/tmp/q01-q02-results-20260916-c`; local controller evidence for all
  trials remains `/private/tmp/q01-q02-window-20260916-{a,b,c}`. Private PDFs and
  extracted document bytes have not been added to Git.

## Capacity and cleanup

The user authorized temporarily pausing exactly activities/workflows/objects/
temporal in pdf-t03-validation through pdf-t07-validation. Each window checked
that all five namespaces had no Running workflows, saved exact replica counts,
paused the selected twenty Deployments, and required a 60-second capacity window
with at least 3 GiB available, zero full memory PSI and unchanged OOM counter.

Trial C observed minimum VM available 2,247,376,896 bytes (~2.09 GiB), maximum
sampled full PSI avg10 0.49, and unchanged cumulative OOM counter 28. These are
observations within the serial guarded VM, not production sizing bounds. The
retained coordinator has no explicit per-Pod resource limits; no claim of Pod
budget qualification or final deployment packaging is made.

All original replicas were restored after every trial. Final API checks passed:
all five Temporal services healthy, all five object readiness endpoints HTTP 200.
No own runtime processes or Running workflows remained in the T09a service.
No PVC/source/result deletion or unrelated service mutation occurred.

## Next

Reconcile/review this production correction and fixed evidence on the integration
branch, then publish/merge and update #48/#49 through main coordination. Q03 can
start once #49 is formally accepted, using the relationship contract and this
exact serialized-artifact hash rule. Q04 still owns the final combined four-case
algorithm/six-fixture and affected recovery/resource matrix; #44 is not closed by
this bounded AIMA run. No ticket was closed or remote branch published here.
