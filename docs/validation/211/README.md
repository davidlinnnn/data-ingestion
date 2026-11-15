# #211 chart value label roles of picture-interpretation@1

Run 2026-11-15 with [run.py](run.py). `picture-interpretation@1` ran alone, outside the
workflow, on t4's 18 gold pictures with Sonnet 5.5, and was scored with #199's methods
([score.py](../199/score.py), imported unchanged). #199 found that the method did not fix where a
chart's labels go, which is fix 2 of the 3 that hold the release of `paper-pdf@1`.

## Verdict

**The label roles are fixed: every chart answer in 3 runs places series, category and x as #84's
gold does. Two acceptance criteria were met only by user ruling (2026-11-15), both for reasons
outside the label roles.**

| Criterion | Result | Met |
|---|---|---|
| 5 charts (88 points), 3 runs, diagnosis view at least 83 each | 83, 82, 83 | runs 1 and 3; run 2 by ruling (below) |
| x and category swapped back does not score higher | equal in every run, by construction (below) | yes |
| Formal view, listed | 83, 82, 83 (#199: 66 in the workflow, 35 alone) | — |
| 18 descriptions judged blind, not below #199's workflow (15/18) | 15/18; 14/18 as the judge gave them | by ruling (below) |
| Caption, description and figure type do not regress | figure type 18/18 against the gold and against the recorded answers, 18/18 captions not blank | yes |

- **Run 2 is one point short, on a value read off image 17.** Image 17 is a line chart of noisy
  training curves without printed values. Its 12 gold points were bound to an answer in every
  run; the misses are read-offs outside the gold's tolerance. The ticket leaves value accuracy
  out of scope. Ruling: accept, and hand line-chart read-offs to #83 and #203.
- **Image 21's description was failed by this round's judge and passed by ruling.** The judge
  failed the answer and the control (Luna's recorded answer) for calling the untitled x-axis
  "scaling factor k". t4 passed the control, and #199's judge passed the same wording on the
  same image. Ruling: keep #199's call. `judgments.json` records the reversal.

## What changed in the method

The prompt asked only to "preserve series, category, x and values". The prompt and the schema
now carry one definition per field (`ROLES` in the method package), placed as #84's chart gold
places them:

| Field | Holds | In the gold |
|---|---|---|
| `series` | The mark's data series: the legend entry or line label as printed, with nothing added. Null for a single unnamed series. | image 16: `Before RL` |
| `category` | The mark's label on a categorical position axis (tick labels that are names). With several panels: the panel title as printed, followed by that label when the axis is categorical. Null for a single panel with a numeric position axis. | images 6, 22: `Qwen3.5-4B`, `No Memory`; image 16: `(a) Llama3.1-8B-Instruct F1`; images 17, 21: `(a) Parallel Scaling` |
| `x` | The mark's position on a numeric position axis, as a number. An axis whose tick labels are numbers is numeric, also under bars. Null on a categorical axis. | image 17: the training step; image 21: k |

- **`x` is now number or null** (it was number, string or null), so a label cannot go there.
  Anthropic's OpenAI-compatible endpoint accepts `response_format` only as `json_schema` with
  `strict: true` and applies it as structured outputs
  ([OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk)).
- **`VERSION` stays 1.** `paper-pdf@1` is not released.
- **Recorded answers.** Of the 162 gpt-6-luna answers under `tests/fixtures/vlm`, 12 put a label
  in `x` and are now `SCHEMA_INVALID`; the test of the recordings expects that.

## Chart values

PASS points per image, of #84's frozen comparator in t4's two views. The request, the model and
the gold are #199's; only the method changed.

| Run | Image 6 (16) | Image 16 (18) | Image 17 (12) | Image 21 (30) | Image 22 (12) | Diagnosis | Formal | x and category exchanged | series and category exchanged |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 16 | 18 | 7 | 30 | 12 | 83 | 83 | 83 | 0 |
| 2 | 16 | 18 | 6 | 30 | 12 | 82 | 82 | 82 | 0 |
| 3 | 16 | 18 | 7 | 30 | 12 | 83 | 83 | 83 | 0 |
| #199 workflow | 16 | 0 | 8 | 30 | 12 | 66 | 66 | 84 | — |
| #199 alone | 16 | 0 | 7 | 0 | 12 | 35 | 35 | 53 | 0 |

- **Same layout in every run.** For each of the 5 images the set of (series, category) pairs is
  identical across the 3 runs, `x` is a number on images 17 and 21 and null on the others, and
  no series name carries an added note.
- **The formal view equals the diagnosis view.** The diagnosis view exists to map label layouts
  the old schema allowed. No answer needed it.
- **Exchanging x and category cannot change a score now.** #199's `swapped` exchanges the two
  only when both are strings. The column is kept because the ticket asks for it. The exchange
  the schema still allows is series with category: it scores 0 in every run, so the roles are
  not reversed.
- **Image 17.** The misses are at x = 25 (3 to 4 of the 4 points per run) and on 2 points at
  x = 100. The comparator interpolates between the answer's points; run 2 gave points at
  x = 0, 20, 100 and 200, the other runs at steps of 50.

### Controls of the scorer

Run before any request was sent, on recorded answers:

| Input | Formal | Diagnosis | x and category exchanged | series and category exchanged | Chart check |
|---|---|---|---|---|---|
| #199's alone answers | 35 | 35 | 53 | 0 | fail |
| Luna's recorded answers (t4: 84, 66) | 66 | 84 | 66 | 0 | pass |
| Luna's answers with series and category reversed | 0 | 0 | 0 | 84 | fail |

The first row reproduces #199's alone numbers, on the descriptions too (16/18, the same verdict
on every image).

## Descriptions, figure types and captions

Run 1's 18 answers. Every description differs from Luna's, so all 18 were judged.

| Image | This run | #199 workflow | #199 alone | Why |
|---|---|---|---|---|
| 3 | FAIL | FAIL | PASS | Invents a figure title, the same miss as #199's workflow answer. |
| 5 | FAIL | FAIL | FAIL | Infers the publisher, as in #199. |
| 18 | FAIL | FAIL | FAIL | As in t4 and #199. |
| 21 | PASS by ruling (judged FAIL) | PASS | PASS | See the verdict. |
| the other 14 | PASS | PASS | PASS | — |

- **Judge.** A Claude Opus 5.5 subagent, blind, by t4's rules, as in #199. It saw each sheet's
  two answers as A and B in a seeded order, without the letter key.
- **Control.** Luna's answer was on every sheet. The judge agreed with t4 on 14 of 18 (#199: 58
  of 60); all 4 disagreements are a FAIL where t4 passed. Three are the table-cell symbols of
  paper 1 (images 11, 12, 14: the control does not say the symbol is a table cell), where this
  run's answers passed. The fourth is image 21.
- **Self-check before judging.** Each item appears once, and each image's sha256 is the gold
  crop's.
- **Figure types.** 18/18 say "chart" exactly where the gold does, and 18/18 equal Luna's
  recorded answer, which #199's Sonnet answers also equal on all 18.
- **Captions.** There is no gold. 18/18 are not blank.

## Where #84's gold is not consistent

Listed here as the ticket asks; the gold is unchanged.

- **`x` of printed charts is compared by position, not by value.** For images 21 and 22 the
  comparator expects `x` to be the point's index (1, 2, 3, …). Image 21's k runs from 1 to 5,
  so the result is the same. A numeric axis that does not start at 1 in steps of 1 would fail a
  correct `x`.
- **The panel letter.** The contract of images 16 and 17 names panels without "(a)", image
  21's gold with it. Evaluator v2 removes a leading "(a) " from the answer before comparing;
  v1 does not, and would fail a panel title written as printed. t4, #199 and this run use v2.
- **Image 6 and 16 mappings of the diagnosis view** accept a label in `x`. They no longer apply.

## What the change does to the recordings

The 162 picture answers under `tests/fixtures/vlm` are named by their request's digest, which
the new prompt changes. The VLM stand-in of t5c-seam-b and t6-seam-b therefore answers a corpus
paper's picture request with the canned answer and no longer replays a recording. Nothing else
depends on the match: CI reads the recordings' content only, W2's requests never had a
recording, and the formula recordings are unchanged. They were not recorded again (user,
2026-11-15: gpt-6-luna is no longer used).

## Handoffs

- **#137, the release decision.** Fix 2 of #199's 3 is done. The chart images need no further
  rerun on Sonnet 5.5.
- **#203, the company environment.** Rerun `run.py` with the company VLM (`MODEL`, `ANTHROPIC`
  and the key become the company endpoint's): the 5 charts 3 times and the 18 descriptions. Two
  things to watch: whether the endpoint enforces the schema (an answer with a label in `x` is
  `SCHEMA_INVALID` and loses all four fields of the picture), and image 17's read-offs.
- **#83, the rest of the scope.** Read-offs on line charts without printed values: image 17
  scores 6 to 8 of 12 in #199 and here, and decides whether a run reaches t4's bar.

## Spend

28 requests, all answered with valid content: 121,093 input and 25,983 output tokens, US$0.50
at US$2 / US$10 per million tokens (estimate US$0.5–0.8). The longest request took 12.4 s.

## Files

- `evidence.json`: per run and image the chart scores; per image the description verdict beside
  #199's, the control, the figure type; the request totals. Its `pass` flags are the criteria as
  written, so run 2's is false and the script exits 1.
- `judgments.json`: verdicts by answer sha256, with the judge's notes and the reversal.
- `manifest.json`: sha256 of the gold files read and of everything under OUT.
- OUT is `~/archive/research/211-chart-roles`, outside the repo: the answers of each run, the
  judging sheets with their crops, and the logs.

## Run

```
set -a; . ~/.config/kp-dev/anthropic.env; set +a
.venv/bin/python docs/validation/211/run.py ~/archive/research/211-chart-roles \
    ~/archive/data-ingestion-wip-2026-10-21/untracked
```

It needs t4-seam-b's runs on the S3 stand-in of `tests/s3/compose.yaml` (port 9100), and starts
nothing else. An answer already in OUT for the same request and model is not sent again, so a
rerun only rescores. When it leaves answers to judge, it writes them to `OUT/judging/sheets.json`;
a judge writes `verdicts.json` beside them, and the next run merges it into `judgments.json`.
