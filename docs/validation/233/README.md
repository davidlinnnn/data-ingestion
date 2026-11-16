# #233 paper-pdf@1 before release: #199's 21-paper workflow run with the three fixes together

Run 2026-11-16 on this Mac with [#199's run.py and score.py](../199/README.md#reuse), on `dev` at
`19b92af` (the harness fix below is `52da203`; it changes no method). All 20 corpus papers and W2
went through the `paper-pdf` workflow on a real Temporal server with #199's models, stand-ins and
runtime, one paper at a time, and every paper and item is compared with #199's pilot2
([compare.py](compare.py), [compare.json](compare.json)).

## Verdict

**`paper-pdf@1` can be released: the three fixes hold together on the tree that ships, and no
paper or item got worse.** Merging #186 is the user's call.

- All 21 papers `complete`, rule `pass`, no `failed` enrichment (pilot2: 24).
- Every difference from pilot2 is one of the three fixes or the model's run-to-run variation
  (tables below). No difference is a regression.
- Only the two method packages the fixes touched changed digest: `docling-parse@1`
  (`6cb4374d` → `57a4415f`, #210 and #212) and `picture-interpretation@1` (`191e75e0` →
  `dbbd23a6`, #211). The other six are byte-identical to pilot2's.

| Fix | Criterion (#233 scope 4) | Result |
|---|---|---|
| Code (#210) | #84's 13 code units: region covered by code items, operators and numbers 13/13 | **Holds.** Operators 13/13, numbers 13/13 (pilot2 9/9 of 13); CER median 0.35 % (0.42 %). The four split listings: CER 79, 76, 71, 81 % → 0.86, 0.36, 0.45, 0.30 %, 1 → 9, 8, 9, 8 items. Coverage is not remeasured here: `docling-parse@1` is `57a4415f`, the digest of #210's 21-paper inventory where the gold characters of all 13 lie in code items' boxes ([#210](../210/README.md)), and this run's inventory has the same items per paper and method as that one on all 21 papers (code, formula, table, picture OCR, summary; picture interpretation counts 4 enrichments per item there) |
| Charts (#211) | t4's bar on the workflow, diagnosis ≥ 83/88; images 16 and 21 not swapped; image 17's read-off not counted (#211 ruling 1) | **Holds.** Diagnosis 83/88 and formal 83/88 (pilot2 66 and 66), alone 82. Image 16 0 → 18/18, image 21 30/30 in the workflow and 0 → 30/30 alone; images 6, 16, 21, 22 76/76. Image 17 7/12 (pilot2 8); the bar is met even counting it |
| Formulas (#212) | Paper 16 page 25: no SWE-bench id in the formula inventory, no `failed EMPTY_OUTPUT` | **Holds.** Page 25: 0 formula items, 0 requests; paper 16: 0 failed formulas, `formula@1` 9 requests, 0 invalid (pilot2 69, 49 invalid). Also #212's own checks: all 60 ids of page 25 verbatim in the assembly ([formula-p16.json](formula-p16.json), #212's `run.py e2e`) |

## Models and runtime

As in #199: `picture-interpretation@1`, `formula@1`, `code@1` and `document-summary@2` on
`anthropic/claude-sonnet-5-5` through Anthropic's OpenAI-compatible endpoint; `d3-check@1` on the
local `d3_server.py` with d3-mini `bd0090dd` on MPS; W2 on the VLM stand-in (t5c's replay) and the
DEV summary fake; `d3_concurrency_per_document` 4 → 1. Each paper's
`profile_differs_from_released` equals pilot2's.

OUT is `~/archive/research/233-release-rerun/run1`, outside the repo.

## Per paper

pilot2 → this run; one value where equal. Every paper has outcome `complete`, summary outcome
`success` and the same four `limitations` as in #199.

| Paper | Items | Time (s) | VLM requests (invalid) | Summary requests (not ok) | `disputed` / `failed` | US$ |
|---|---|---|---|---|---|---|
| W2 | 49 | 46 → 54 | 40 | 32 | formula FORMULA_NATIVE_MISMATCH 35 | 0.00 → 0.00 |
| 1 | 42 → 69 | 93 → 99 | 19 | 52 → 55 (3 TIMEOUT) | formula FORMULA_NATIVE_MISMATCH 4, table-status TABLE_D3_UNFAITHFUL 6 | 0.53 → 0.52 |
| 2 | 23 | 37 → 36 | 2 | 32 → 30 | table-status TABLE_D3_UNFAITHFUL 1 | 0.23 → 0.22 |
| 3 | 42 | 100 → 95 | 14 | 51 → 47 | table-status TABLE_D3_UNFAITHFUL 12 | 0.47 → 0.46 |
| 4 | 34 → 70 | 93 → 92 | 7 | 56 (1 SCHEMA_INVALID) → 47 | table-status TABLE_D3_UNFAITHFUL 6 | 0.51 → 0.48 |
| 5 | 39 | 221 → 107 | 15 | 75 (7 TIMEOUT) → 61 | formula FORMULA_D3_UNFAITHFUL 1 → 0; table-status TABLE_D3_UNFAITHFUL 14 | 0.49 → 0.47 |
| 6 | 49 | 123 → 110 | 11 | 65 (1 SCHEMA_INVALID) → 57 | table-status TABLE_D3_UNFAITHFUL 16 | 0.64 → 0.57 |
| 7 | 20 → 23 | 56 → 51 | 8 | 39 → 37 | table-status TABLE_D3_UNFAITHFUL 1 | 0.35 → 0.33 |
| 8 | 12 → 13 | 38 → 38 | 3 | 33 → 31 | table-status TABLE_D3_UNFAITHFUL 3 | 0.25 → 0.24 |
| 9 | 48 → 50 | 123 → 136 | 30 | 59 → 61 | table-status TABLE_D3_UNFAITHFUL 6 | 0.46 → 0.49 |
| 10 | 38 | 90 → 88 | 15 | 57 → 51 | table-status TABLE_D3_UNFAITHFUL 6 | 0.63 → 0.60 |
| 11 | 41 | 87 → 83 | 17 | 44 | table-status TABLE_D3_UNFAITHFUL 3 | 0.55 → 0.56 |
| 12 | 48 | 105 → 109 | 32 | 49 → 47 | formula FORMULA_NATIVE_MISMATCH 7, table-status TABLE_D3_UNFAITHFUL 8 | 0.56 → 0.52 |
| 13 | 71 → 94 | 113 → 111 | 37 | 71 | formula FORMULA_D3_UNFAITHFUL 1, FORMULA_NATIVE_MISMATCH 2, table-status TABLE_D3_UNFAITHFUL 6 | 0.65 → 0.63 |
| 14 | 31 | 73 → 74 | 18 | 37 → 35 | table-status TABLE_D3_UNFAITHFUL 3 | 0.38 → 0.40 |
| 15 | 34 | 115 → 119 | 7 | 63 → 65 | table-status TABLE_D3_UNFAITHFUL 9 | 0.53 → 0.53 |
| 16 | 123 → 88 | 113 → 80 | 77 (49) → 17 | 42 → 34 | formula EMPTY_OUTPUT 24 → 0; formula FORMULA_D3_UNFAITHFUL 1, table-status TABLE_D3_UNFAITHFUL 1 | 0.56 → 0.43 |
| 17 | 28 | 56 → 71 | 10 | 38 → 44 | formula FORMULA_D3_UNFAITHFUL 1 → 0; table-status TABLE_D3_UNFAITHFUL 1 | 0.36 → 0.38 |
| 18 | 30 | 74 → 76 | 15 | 38 → 37 | table-status TABLE_D3_UNFAITHFUL 3 | 0.36 → 0.34 |
| 19 | 58 | 109 → 124 | 36 | 71 → 82 | formula FORMULA_D3_UNFAITHFUL 1 → 0; FORMULA_NATIVE_MISMATCH 1, table-status TABLE_D3_UNFAITHFUL 7 | 0.80 → 0.88 |
| 20 | 108 | 169 → 175 | 38 | 92 → 84 | formula FORMULA_NATIVE_MISMATCH 2 → 1; table-status TABLE_D3_UNFAITHFUL 5 | 1.19 → 1.13 |
| **Sum** | | **2,033 → 1,927** | | | | **10.48 → 10.18** |

### Attribution

| Difference | Papers | Cause | Why |
|---|---|---|---|
| More code items (+27, +36, +3, +1, +2, +23 = 92), all `unverified` | 1, 4, 7, 8, 9, 13 | #210 | 92 is #210's count of new corpus code items (185 → 277); `code@1` reads the text layer and sends no request |
| 35 fewer formula items, 24 `failed` → 0, 49 invalid → 0, 60 fewer `formula@1` and 11 fewer d3 requests | 16 | #212 | the 35 page-25 ids are text lines; the other 9 formulas send 9 requests, 0 invalid |
| Formula `disputed` 1 → 0 (FORMULA_D3_UNFAITHFUL) or 2 → 1 (FORMULA_NATIVE_MISMATCH) | 5, 17, 19, 20 | variation | `formula@1` is unchanged and #210/#212 change no other formula item (#212: 222/222 same request; #210: 0 items of other methods changed); the answer differs, so d3's score and the native check do. The two in t4's sample (p17-ae7b5caad363, p20-e5976e29bae2) are judged PASS in both runs: two correct answers no longer flagged |
| Summary request counts (−14 … +11), summary TIMEOUT / SCHEMA_INVALID retries | all | variation | `document-summary@2` is byte-identical; its request count follows the model's sentences and verify rewrites, and differs as much on papers no fix touched (10: −6, 19: +11) as on those whose text changed (4, 16). The 3 TIMEOUTs on paper 1 succeeded on retry, as pilot2's 7 on paper 5 did; every summary is `success` |
| Time | all | variation and #212 | paper 5's 221 s in pilot2 was the summary timeouts; paper 16 is 33 s faster without the 60 formula requests |
| Table d3 flags | — | none | identical on all 20 papers |

## Accuracy

Same sample, gold and scorer as #199. "Alone" is the method run outside the workflow.

| Enrichment | pilot2 | This run | Cause of the difference |
|---|---|---|---|
| Picture OCR, literal | 304/358 | 304/358 | — |
| Tables, `table-status` same as alone | 15/15 | 15/15 | — |
| Code, operators / numbers exact | 9/13, 9/13 | 13/13, 13/13 | #210 |
| Charts, diagnosis (formal) | 66 (66)/88 | 83 (83)/88 | #211: image 16 0 → 18; image 17 8 → 7 is a read-off of the unprinted line chart, out of scope by #211's ruling 1 |
| Charts alone, diagnosis | 35/88 | 82/88 | #211: image 16 0 → 18, image 21 0 → 30 |
| Descriptions | 15/18 | 16/18 | variation: image 5 (p01-2fe0065e348a) FAIL → PASS; images 3 and 18 fail in both |
| Formulas | 44/46 | 43/44 | #212: the two t4 ids are text lines now (p16-35fa058a6093 was PASS, p16-e1d8a234b6b9 FAIL); on the 44 real formulas the verdicts are the same, the one FAIL p01-a5304a07488e in both |

The other fields of `compare.json` that differ:

| Field | Cause | Why |
|---|---|---|
| `descriptions.pass_alone` 16 → 17 | variation | image 5 alone, the same item as the workflow's change |
| `recorded_request` true → false on the 18 descriptions | #211 | the prompt changed, so the request no longer has the digest of Luna's recording; #211 recorded this and did not re-record |
| `charts.diagnosis_swapped` 84 → 83, `diagnosis_swapped_alone` 53 → 82 | #211 | `x` is a number or null, so swapping x and category changes no answer: the column equals diagnosis, as #211 noted |
| Image 17 alone 7 → 6 | variation | a read-off of the unprinted line chart, out of scope by #211's ruling 1 |
| `formulas.same_answer` 33 → 31 (12 items flip either way) | variation, and #212 for the two page-25 ids | whether Sonnet's answer equals Luna's character for character; the request is the same on all 44 (`same_request`) |

**Judging.** The 29 answers that differ from Luna's were judged blind by two Claude Opus 5.5
subagents (effort high) with t4's rules, as in #199: 18 descriptions, 11 formulas. Self-check
before judging: each item once, each picture image's sha256 the gold crop's, each formula crop's
equal to pilot2's crop of the same item, each sheet's letters those of `letters.json` with one
`recorded`. **Control:** Luna's answer was on every sheet and the judges agreed with t4 on 29 of
29; with #199's 60 sheets that `judgments.json` keeps, 59 of 60 labels agree (`judge_control`;
pilot2 58), the one left being #199's p01-a5304a07488e. Judgement calls are in `judgments.json` notes; the closest: on p09-ede3d51fae44 a hyphen
outside `\mathrm` was passed as the same character, and three paper-1 answers on a table cell's
symbol that never say "table" were passed.

## A7: the summary's verify step

#199's planted-error check on this run's summaries, same seed (155), planter and judge (Sonnet 5.5).

| Tier | pilot2 | This run |
|---|---|---|
| Severe | 50/50 | 50/51 |
| Moderate | 48/49 | 45/49 |
| Subtle | 19/48 | 25/46 |
| False drops | 2/150 | 3/150 |
| Invalid plants | 3 | 4 |

**Variation, not a regression.** `document-summary@2` and its verify request are unchanged; the
sample is drawn from this run's summaries, so the planted sentences differ. The one severe miss
is a reversal on paper 4 ("human skills are longer yet lose" → "yet win") that the verify judge
read as "SkillOpt wins". Moderate 45/49 (91.8 %) is in line with #155's held-out 93.0 % on the
same five types.

## Tokens

[tokens.md](tokens.md), [tokens.json](tokens.json), from the receipts as in #199.

| Component | Requests per paper | Tokens per request | Share of tokens |
|---|---|---|---|
| `picture-interpretation@1` | 8.2 | 4,915 → 5,280 | 21.5 → 23.5 % |
| `formula@1` | 12.35 → 9.35 | 505 → 523 | 3.3 → 2.7 % |
| `document-summary@2` | 53.2 → 51.0 | 2,319 → 2,321 | 65.7 → 64.2 % |
| `d3-check@1` | 26.25 → 25.7 | 684 → 690 | 9.6 % |

Picture requests are 7 % larger: #211's role definitions (#211 measured about 400 input tokens
more per request). Formula requests per paper fall by paper 16's 60 (#212). Per-document median
180,892 → 182,838 tokens.

## Spend

| Item | US$ |
|---|---|
| Workflow, 20 papers | 10.18 |
| Methods alone, 64 requests (usage summed over OUT/alone: 96,974 input, 17,787 output tokens) | 0.37 |
| A7 judge, 150 cases (held-out 1.07, dev 0.77) | 1.84 |
| **Total** | **12.39** (estimate US$12–14, stop line US$20) |

## Harness fix

The first A7 run stopped before its first request: #202 (`19b92af`) changed `OpenAIChat`'s third
argument from an API key to a headers mapping and updated t5b's callers, but not the planter that
`docs/validation/199/score.py` substitutes for t5b's Luna client. `52da203` passes the bearer as a
header. Nothing was sent before the error. It is the only change under `docs/validation/199`, a
deliberate exception to the ticket's "199 not changed": the evidence there is pilot2's, and the
fix restores the script #203 also reruns.

## Files

- `papers/<index>.json`, `accuracy.json`, `tokens.json`, `tokens.md`, `judgments.json`,
  `evidence-held-out.json`, `evidence-dev.json`, `manifest.json`: what #199's run.py and score.py
  wrote for this run, moved here. `manifest.json` holds the sha256 of the papers, the profile, the
  d3 package, the gold and the raw outputs under OUT.
- `formula-p16.json`: #212's paper-16 check on this OUT.
- `compare.py`, `compare.json`: every value that differs from pilot2 (#199's evidence at `19b92af`).

## Run

```
set -a; . ~/.config/kp-dev/anthropic.env; set +a
A=~/archive/data-ingestion-wip-2026-10-21/untracked
O=~/archive/research/233-release-rerun/run1
scripts/heavy-lock 233-release-rerun -- env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/199/run.py \
    $O "$A/docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json" "$A" \
    ~/models/issue84/w4b-d3-models/d3-mini ~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python \
    w2 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
.venv/bin/python docs/validation/199/score.py summary $O held-out 100 1 3 5 7 8 9 10 11 12 13 14 15 17 18 19
.venv/bin/python docs/validation/199/score.py summary $O dev 50 2 4 20 16 6
# judges write $O/judging/verdicts.json; the first command again rescores
PYTHONPATH=. .venv/bin/python docs/validation/212/run.py e2e $O e2e-233
# move what these wrote under docs/validation/199 and 212 here, git checkout docs/validation/199
.venv/bin/python docs/validation/233/compare.py
```
