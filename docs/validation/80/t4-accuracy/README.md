# #133 accuracy of the VLM methods

Run 2026-11-01 with [run.py](run.py), against the #84 gold kept outside git (it quotes
third-party papers). Luna's answers are the ones the real-model runs of
[t4-seam-b](../t4-seam-b/README.md) registered for the 20 public papers; nothing was re-sent to
Luna for this check. Claude Opus 5.5 (`claude-opus-5-5`) answered the same method requests,
translated to the Messages API with the method's schema as the output format, as a ceiling.
Bar, set before the run (user ruling 2026-11-01): our Luna not below #84's Luna on the same
images, for descriptions and chart values. Formulas: report only.

Round 1 (the first prompt) missed the bar; the user ruled to change the prompt and raise the
effort, then check again. Round 2 is the shipped state.

| Area | Sample | Our Luna | #84 Luna | #84 Sol | Opus 5.5 | Bar |
|---|---|---|---|---|---|---|
| Descriptions | 18 gold images in the corpus, all matched (box overlap 1.0) | 17/18 (round 1: 10/18) | 16/18 | — | 18/18 (round 1: 18/18) | pass |
| Chart values, diagnosis view | 88 points in images 6, 16, 17, 21, 22 | 84 (round 1: 67) | 83 | 86 | 84 (round 1: 76) | pass |
| Chart values, formal view | same | 66 (round 1: 67) | 83 | 52 | 66 (round 1: 58) | see below |
| Display formulas | 46 (at most 3 per paper, seed 133) | 36/46 (round 1: 34/46) | — | — | 45/46 (round 1: 46/46) | report only |
| `disputed` on those formulas | Luna wrong 10 | 1 flagged, 0 of them wrong (round 1: 1 flagged, 0 of 12 wrong) | | | | report only |

What changed between the rounds:

- The picture-interpretation prompt gained generic rules: describe only the target picture;
  cover labelled components, arrows with direction and label, marks and who carries them,
  trends, and what an icon denotes in the page context; read against the axis scale, which need
  not start at zero; give estimated read-offs when nothing is printed; for stacked bars give
  each segment's cumulative top and say so.
- Both VLM methods send `reasoning_effort` "high". Opus ran at effort `high` in round 1
  (adaptive thinking: it thought on 5 of 64 items) and at `max` in round 2 (all 64).
  `run.py opus` now sends `high`: Opus is the ceiling, and `max` multiplied its output tokens by 10.

How each is scored:

- **Chart values**: #84's frozen comparator `chart_receipts`. The formal view is #84's
  evaluator v2. The diagnosis view adds round 6's `axis_view` (copied) and drops a trailing
  parenthetical from series names. Evaluator v2 strips only "(cumulative boundary)", the wording
  #84's own prompt produced. Round 2's Luna writes "(cumulative top edge)" and reads image 16's
  cumulative tops correctly, so it scores 0/18 formal and 18/18 in diagnosis. #84 scored Sol's
  label-binding misses the same way (`round6-sol/binding-diagnostic.json`). The bar is read on the
  diagnosis view; the formal view is kept to show the label dependence.
- **Descriptions**: blind A/B judgement against each image's frozen `description_obligations`
  by #84's meaning-slice rule. Every required role, condition and directed relation must be
  present, and no false assertion may be made. Literal OCR and numbers are separate gates.
  #84's verdicts come from `round5-strict/human-C-review-v1.json`.
- **Formulas**: blind A/B judgement of LaTeX equivalence while viewing the crop. Calligraphic,
  blackboard and letter-case changes count as different symbols. Accepted as equivalent:
  `\text` vs `\mathrm` vs `\texttt`, spacing, line breaks, trailing punctuation, `*` vs
  `\star`, `\epsilon` vs `\varepsilon`, `a/b` vs `\frac{a}{b}`, and a missing list bullet.

Findings:

- Luna's remaining formula errors are mostly letter styles: a calligraphic or blackboard letter
  lost or added (6 of 10). The status rule's native-text check compares symbols by text, so it
  cannot see a font change: `disputed`
  caught none of the errors in either round, and its only flag was a correct formula.
- Round 2's one description failure is a single extra claim: Luna's axis ticks the crop does
  not show (image 18).
- On image 17 (line chart, no printed values) round 1's Opus returned no values, citing "never
  invent unreadable values". Round 2's prompt asks for estimated read-offs, and both models give
  8/12.
- With effort "high", Luna answers more slowly. Three pictures reached the 60 s call deadline in
  the re-recording (t4-seam-b README).

Judging and self-preference: the judge is Claude Opus 5.5, the same model as the ceiling. Answers
were shown as A and B in a seeded random order with the model names hidden (`key.json`). The
user spot-checked 10 judgments on 2026-11-01 and agreed with 9; the tenth (image 5, Opus) was
reversed from FAIL to PASS. Judgement calls are marked in `judgments.json` notes.

Files: `targets.json` (items, Luna's answers), `responses/opus/` (Opus responses, parsed by the
method), `judgments.json`, `evidence.json` (per item and summary); `round1/` holds the same
files for round 1. The blind sheets and formula crops (`packet`) stay outside git.

Spend: Luna's answers come from the t4-seam-b recordings. Opus: round 1 used 83,184 input and
16,526 output tokens, round 2 used 86,730 and 174,619 (about US$4.50 at list price, paid from
free credits), plus one round 2 attempt that hit the 16,000-token cap at `max`; that item was
re-run with 64,000 and streaming.

## Run

```sh
G=<#84 live-preflight folder>
.venv/bin/python docs/validation/80/t4-accuracy/run.py collect $G <corpus manifest>
env ANTHROPIC_API_KEY=... uv run --with anthropic python docs/validation/80/t4-accuracy/run.py opus
env GOLD_ROOT=$G .venv/bin/python docs/validation/80/t4-accuracy/run.py packet <folder outside git>
.venv/bin/python docs/validation/80/t4-accuracy/run.py score $G
```
