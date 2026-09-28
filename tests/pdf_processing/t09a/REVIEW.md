# Standards and Spec review / validation

Reviews ran independently against integrated T07 and the originating T09a plan.
There is no dedicated repository coding-standards document; root AGENTS instructions,
domain/issue docs and surrounding package contracts supplied the review context.

| Axis | Finding | Correction and disposition |
|---|---|---|
| Standards | Full-suite timeout could leave parser descendants alive after flock release | Track psutil process identities, suspend before final descendant inventory, terminate/reap owned processes before unlocking. Reviewer static recheck: resolved. Runtime full suite deferred. |
| Spec | Replay selected failed fresh AIMA and ignored producer transition | Replay successful `evidence-08` on new producer; original successful requests on exact retained baseline; old failed AIMA replay explicitly expects original failure. Reviewer static recheck: resolved. Replay runtime deferred. |
| Spec | Fault evidence written only on success and lacked retained-group/attempt proof | Incremental and exception records; exact durable-group, retry-attempt, container and scratch assertions. Reviewer static recheck: resolved. Trial interrupted on global OOM before all assertions; not passed. |
| Standards | Summary could override a rejected controller observation as uninterrupted | Require affirmative controller continuity; absent legacy fields remain unqualified. Controller records sampler exit/restarts and stops a sequence after observation failure. Static recheck and scoped typecheck only. |

The production change is limited to `evidence.py` and its package documentation:
combining-only zero-width TextItem evidence gets explicit full-page uncertainty.
Neither reviewer reported an actionable production-code issue. Raw Docling JSON,
source associations and parser output types were not rewritten.

Final Standards recheck confirmed the continuity-summary correction. Final Spec
report review found no actionable overclaim: global OOM, interrupted drain,
source-quality gaps and all deferred checks are represented as partial/open.

Passed before the stop-heavy instruction:

- Existing T05 focused tests: 4 passed ([log](evidence/t05-tests.log)).
- Existing T04 focused tests after the production fix: 5 passed ([log](evidence/t04-tests.log)).
- Real Temporal/store AIMA red-to-green complete-result evidence regression:
  old `region_outside_page` failure retained; new evidence completes with raw equality.
- Real Temporal/store geometry suite: all 12 cases passed; negative cases attempt 1.
- Scale-4 profile transition: native groups/assembly reused, 11 actual OCR reports
  at scale 4, full-document equality.
- Full successful fresh/warm result checks and declared source audits as qualified
  in REPORT.md; AIMA expectations remain open and warm continuity failed.
- Final scoped Pyright: zero errors/warnings; script syntax, JSON parse and artifact
  hash/link validation. These static checks do not replace deferred integration work.

Explicitly **unrun/deferred** under main's instruction after observed global OOM:

- Exact-request replacement replay (including old failed request behavior).
- Inference-containing full 10-test regression suite in this worktree.
- Runtime exercise of corrected sampler/restart stop guard and full-suite cleanup.
- Successful completion of drain recovery and all end-to-end proof assertions.
- Clean uninterrupted warm sequence, planned recycle and stable memory envelope.

No reviewer approval is represented as runtime qualification. No overall #44 PASS,
push, merge or issue closure is implied by these corrections or commits.
