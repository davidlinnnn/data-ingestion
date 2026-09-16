# Q03 runtime qualification — 2026-09-16

**INCOMPLETE.** Four full-request cases and three of 22 finalization matrix cases
passed. Nineteen matrix cases still require acceptance. Do not close #50 or
release Q04/#51 from these results.

Production is unchanged from `17e34fd`; the tested candidate was `48f4f0a`.
All production file hashes match `evidence/producer.json`. This reconciliation
changes only the runtime test harness, a regression test and evidence/docs.

## Verified results

| Case | Result |
| --- | --- |
| Fresh native request | PASS: AIMA original pages 99–110, 12 pages, real parsing/assembly and 9 selected OCR components |
| Fresh-process reuse | PASS: upstream parsing/assembly reused with new downstream work |
| Exact replay | PASS: same final identity |
| Evidence-policy variation | PASS: unchanged document/assembly; new evidence/final identity |
| Matrix valid | PASS: actual Temporal finalization and real evidence child |
| Matrix split | PASS: injected fragmented representation through real finalization |
| Matrix interrupted-evidence | PASS: owned evidence child killed after first decoded page; no evidence/final publication, partial bytes retained; child/scratch cleaned; same-plan retry and exact replay passed |

Full cases retain `quality_accepted=false` and `canonical_accepted=false`.
This is bounded structural delivery with representation uncertainty, not LaTeX,
mathematical-equivalence, whole-book quality or general PDF qualification.
Matrix upstream assembly/selection is seeded; it does not replace full-request
proof. Interruption kills an owned child, not a Pod: no Pod-loss claim follows.

## Trial history and harness repair

- **A:** four full cases passed. Matrix startup failed because the invocation
  omitted the Q02/Q03 fixture import roots. No matrix workflow was submitted.
- **B:** valid, split and interrupted-evidence passed. The first symbol gate's
  Activity correctly failed with non-retryable `integrity`, whose nested cause
  was `ValueError: representation_release_gate`. The harness followed causes
  to the innermost exception and incorrectly asserted its type was `integrity`.
  It stopped before completing retained-evidence/no-final assertions for this
  case, so this gate is **not counted as accepted**.
- **Repair:** classify the first application error below Temporal wrappers;
  retain deeper causes as diagnostics. Never search past an unexpected outer
  application classification for a convenient nested category. A regression
  test covers this distinction. Production and producer identity are unchanged.
- **C:** corrected harness uploaded, but admission failed before execution:
  3,198,218,240 bytes available (2.98 GiB), below the 3 GiB threshold. No
  threshold was relaxed and no matrix workflow was started.

Post-repair local Q03 suite: **32 tests PASS**, typecheck **0 errors/warnings**.
An initial sandboxed run could not inspect processes (`psutil`/`sysctl`), causing
six interruption-test errors/failures; the same suite passed outside that
restriction. This is not a new complete Q01/Q02/Q03 suite count.

## Capacity and cleanup

Authorized window: at most 30 minutes; pause only the 20 existing Deployments in
`pdf-t03-validation` through `pdf-t07-validation` (activities/workflows/objects/
temporal), save replicas and UIDs, restore on every exit. All three trials
restored original replica counts. Final checks connected to each Temporal
service, found no running workflows and returned HTTP 200 for all five object
storage readiness endpoints. The Q03 namespace was idle and no Q03 child
processes remained. PVCs/data were preserved. Global OOM count remained 28.

The coordinator has no per-Pod resource limits. These results qualify only the
controlled shared-VM setup, not production resource sizing or isolation.

## Evidence and next run

[`evidence/runtime-20260916/manifest.json`](evidence/runtime-20260916/manifest.json)
contains production/harness hashes, verified case summaries, workflow IDs and
SHA-256 inventories of private retained artifacts. Trial state and telemetry
are alongside it. Private PDF/image/text/history bundles remain at
`/private/tmp/q03-results-20260916-a` and `...-b`, with remote copies in the
coordinator under `/tmp/q03-20260916-a/results` and `...-b/results`.
Do not publish copyrighted fixture bytes or raw extracted text.

Next: coordinate a fresh capacity window meeting the existing 3 GiB/60-second
admission rule. Run the corrected 22-case matrix using RUNTIME-PLAN.md and
INTERRUPTION.md, a new output directory and object prefix, plus all three
PYTHONPATH roots (`src`, Q02 tests, Q03 tests). Seven independent symbol gates
and twelve corrupt/missing/attribution cases remain unaccepted. Replaying the
three lightweight successes is acceptable; do not rerun native inference merely
for the test-harness correction. Revalidate producer hashes before reusing the
four full-case proofs. Preserve failed-trial records and restore services again.
Only after matrix completion, review the combined evidence for #50 acceptance.
