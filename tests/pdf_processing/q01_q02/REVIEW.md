# Q01 + Q02 static integration review

Status: static integration PASS within the scope below; runtime acceptance OPEN.
No inference, Temporal submission, Kubernetes workload, shared-service change,
push or main-checkout integration was performed during this review.

## Fixed inputs

Baseline `9ba0bab559f4248aaeb2d54b6b74c8e01c0e12b7`.
Q01 is the complete sequence `35cd136` plus
`9f6d37bdd98c80753acea27e9da248c0c59d2ea8`, not just its final fix.
Q02 is `1481d572db7b139bce7fca787198888f4fcf9c1c`.
Isolated branch `codex/q01-q02-integration`, worktree
`/private/tmp/q01-q02-integration`; assembled production HEAD `3dcaf39`.

The three cherry-picks applied without text conflicts. No production edits were
needed for this static integration. This is a targeted coordinating review of
shared seams and evidence, not a new independent two-agent full code review.

## Findings and checks

- The combined compatibility projection contains the Q01 continuation helper in
  group/assembly and both Q02 helpers in evidence/finalize. Policy-dependent
  finalization identities remain present. Neither branch's dependency additions
  were lost in the merge.
- Q01's opt-in predictor selection remains in fresh/capture and restored assembly.
  Its four-removal/one-addition source decision preserves three legitimate inline
  joins; the original seven-removal experimental result is not the adopted oracle.
- Q02 finalization still runs after selected OCR checks, validates the exact
  corrected document/source/result and separately registers relationship evidence
  before complete. Canonical/blanket quality acceptance remains false.
- New checkpoint integration checks confirm the corrected continuation and both
  source-oracle algorithm structures on the SAME corrected document. Old
  assembly/result attribution is rejected. Method-only evidence changes preserve
  parsing dependency projections under the same contract; continuation helper
  changes alter group/assembly projections. This is not actual runtime reuse.
- Original branch profiles/releases and old baseline registrations cannot be
  relabelled as the integrated producer. Both branches change compatibility bytes;
  freeze new combined producer/profile identities after harness preparation.
- No actionable production integration defect was found by these scoped checks.
  Runtime qualification is still missing for both #48 and #49.

## Verification performed

From this worktree, using the retained prototype Python and
`PYTHONPATH=src:/private/tmp/q02-deps:/private/tmp/t01-type-deps`:

- `python -m unittest discover -s tests/pdf_processing/q01`: 15 PASS.
- `python -m unittest discover -s tests/pdf_processing/q02`: 11 PASS.
- `python -m unittest discover -s tests/pdf_processing/q01_q02`: 2 PASS.
- Pyright over production, the two existing runtime drivers and the new combined
  tests: see `evidence/typecheck.log` and `evidence/typecheck-config.json`.

The expanded typecheck included Q02's runtime harness (its earlier clean check
covered production only). After adding explicit test import roots it exposed two
harness typing gaps: exception-chain attribute access and a nullable storage read.
Use guarded attribute access and explicitly assert a listed registration still
exists before decoding. Both are fixed in this integration branch; production
bytes are unchanged. The expanded final check has zero errors/warnings. The
initial diagnostics are retained in `evidence/typecheck-initial.log`. These edits
are statically checked only; the runtime matrix has not been re-executed.

These are 28 focused tests, not a rerun of either branch's full suite. The new
combined test reconstructs retained checkpoints without page inference. Existing
full suites include native/scanned processing and were deliberately not invoked.
The initial new test harness failed on an ambiguous `runtime` import and missing
mock profile format fields; both harness defects were corrected. Preserve the
initial log separately; no product change or prior evidence rewrite was needed.

## Acceptance blockers and next step

See `RUNTIME-PLAN.md`. The existing Q01 driver does not score relationships; the
Q02 driver seeds upstream state and has fixed local endpoints. Neither is a
complete combined acceptance driver as currently written. Prepare a combined
harness and validate it without inference before acquiring the capacity window.
#48/#49 remain open, Q03 remains blocked by #49, and Q04/#44 acceptance is unclaimed.
