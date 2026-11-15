# #199 paper-pdf@1 end to end on the Temporal workflow: accuracy and tokens

Run 2026-11-15 with [run.py](run.py) (harness commits `1708d7f`..`3ddfb3f`; the last rescore ran on `3ddfb3f`). All 20 corpus papers
(551 pages) and W2 went through the `paper-pdf` workflow on a real Temporal server, the S3
stand-in and real model endpoints, without admission, one paper at a time. No paper was
replaced or skipped, and all 21 completed. The enrichments were scored against the gold of
`t3-accuracy`, `t4-accuracy` and `t5b-accuracy` ([score.py](score.py)). The token tables come
from the receipts ([tokens.py](tokens.py); #203 reruns the same script on the company
environment).

## Verdict

**The integration is correct, but `paper-pdf@1` is not ready to release: 3 output defects need a
fix first.** Two more findings go to the tickets that already own them.

- **Integration.** For every scored VLM item the workflow sent the same request body as the
  method run alone (64 of 64). The local methods give the same results (picture OCR 304 = 304
  units, tables 15 = 15). Every difference in score is explained below: the model's run-to-run
  variation, or a code region that the layout finds and that differs from the fixed region t3
  measured.
- **To fix before release** (per the user's 2026-11-13 rule: release only when nothing is left
  to fix):
  1. **Code listings are split by the layout.** For 4 of 13 #84 code units, the inventory's
     code items cover only part of the listing (CER 71–81 %, against 0.1–0.9 % on the fixed
     region). The rest of each listing arrives as body text. Owner: the native parse
     (`docling-parse@1`) and the inventory.
  2. **Chart value label roles are not fixed by the method.** The same request gives different
     label layouts across runs: image 21 scores 30/30 in the workflow and 0/30 alone, with all
     30 values right both times. Image 16 scores 0/18 in both because x and category are
     swapped. On t4's bar (diagnosis view, not below #84's Luna, 83/88) the workflow scores
     66/88. With x and category swapped back it scores 84. Owner: `picture-interpretation@1`
     (prompt or schema).
  3. **Non-formula lines are inventoried as formulas.** Page 25 of paper 16 lists SWE-bench
     instance ids (`django__django-…`). docling labels 35 of them as formulas. Sonnet returns an
     empty LaTeX string for 24 of them, so they are `failed EMPTY_OUTPUT` and cost 49 invalid
     requests. Luna had wrapped them in `\text` or `\texttt`. Two of these ids are in t4's formula sample
     (p16-e1d8a234b6b9, p16-35fa058a6093), where t4 judged Luna's answers PASS. Owner: the
     native parse and the inventory, or the formula prompt. *Corrected 2026-11-15: this item
     said 44 ids and one in t4's sample. 44 is paper 16's whole formula count, the 35 ids plus
     9 real formulas on page 22. Fixed by #212 ([report](../212/README.md)).*
- **Not a fix: descriptions are one short of t4's bar.** The workflow passes 15/18 descriptions,
  against #84's Luna at 16/18. It sent the same request as the method run alone, and the method
  alone meets the bar (16/18). The one extra miss (image 3) is the model's run-to-run variation.
  The bar for the released model (Qwen3.8-27B) is measured in #203.
- **Handed to the tickets that own them, not fixed here:**
  - The d3 table check flags 117 of 167 tables, including 4 of the 6 tables that #84's human
    review judged PASS. The threshold retest belongs to #83/#203 (t5c-seam-b).
  - TPM is far above #93's estimate, mostly from the summary → #78, #137.

## Models and runtime

| Component | Released profile | This run |
|---|---|---|
| `picture-interpretation@1`, `formula@1`, `code@1` | `company-vlm/Qwen3.8-27B` | `anthropic/claude-sonnet-5-5` via Anthropic's OpenAI-compatible endpoint (user, 2026-11-15; the DEV OpenAI key for gpt-6-luna had expired) |
| `document-summary@2` | `company-vlm/Qwen3.8-27B` | `anthropic/claude-sonnet-5-5`, same endpoint (the DEV profile) |
| `d3-check@1` | `company-d3/vllm-sr/d3-mini@bd0090dd` | `d3-server/vllm-sr/d3-mini@bd0090dd`, local `d3_server.py` on MPS |
| W2 (not a corpus paper, #129) | — | VLM stand-in (t5c's replay of the recordings) and the DEV summary fake |

The methods, module digests, `status_rule` and `limitations` match `paper-pdf@1.yaml`. Each paper's
`profile_differs_from_released` checks this. **Runtime relaxed for the local d3:**
`d3_concurrency_per_document` 4 → 1 (one MPS process serves one request at a time). Nothing else
changed.

Effects of the endpoint, from Anthropic's
[OpenAI SDK compatibility](https://platform.claude.com/docs/en/api/openai-sdk) page:

- `reasoning_effort` is ignored. Sonnet 5.5 thinks by default at effort high, which is what the
  methods ask for.
- `completion_tokens_details` is always empty. Reasoning tokens are therefore inside the output
  counts and cannot be separated (the Reasoning column shows "—").
- `system_fingerprint` is empty.

## Per paper

Every paper has the same `limitations`: `READING_ORDER_DEFECTS`, `CAPTION_INTERRUPTS_BODY`,
`INLINE_MATH_NOT_RECONSTRUCTED` and `INLINE_CODE_NOT_RECONSTRUCTED`. Every summary has outcome
`success`. Times are activity seconds. Full rows are in `papers/<index>.json`: status per
enrichment, d3 per check kind, receipts per method, summary steps and sections, and stages.

| Paper | Pages | Items | Outcome | Time (s) | Parse / VLM / summary / check (s) | VLM requests (invalid) | Summary requests (not ok) | d3 scored / `not_run` / unjudged / flagged | `disputed` | `failed` | Cost (US$) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| W2 | 14 | 49 | complete | 46 | 6 / 2 / 1 / 35 | 40 | 32 | 39 / 0 / 0 / 35 | formula native 35 | — | 0.00 |
| 1 | 28 | 42 | complete | 93 | 15 / 18 / 39 / 36 | 19 | 52 | 24 / 0 / 0 / 6 | formula native 4, table d3 6 | — | 0.53 |
| 2 | 22 | 23 | complete | 37 | 8 / 10 / 21 / 5 | 2 | 32 | 3 / 0 / 0 / 1 | table d3 1 | — | 0.23 |
| 3 | 25 | 42 | complete | 100 | 16 / 19 / 34 / 47 | 14 | 51 | 28 / 0 / 0 / 12 | table d3 12 | — | 0.47 |
| 4 | 27 | 34 | complete | 93 | 15 / 15 / 43 / 33 | 7 | 56 (1 SCHEMA_INVALID) | 13 / 0 / 0 / 6 | table d3 6 | — | 0.51 |
| 5 | 31 | 39 | complete | 221 | 14 / 15 / 153 / 51 | 15 | 75 (7 TIMEOUT) | 30 / 0 / 0 / 15 | formula d3 1, table d3 14 | — | 0.49 |
| 6 | 29 | 49 | complete | 123 | 17 / 22 / 54 / 48 | 11 | 65 (1 SCHEMA_INVALID) | 32 / 0 / 0 / 16 | table d3 16 | — | 0.64 |
| 7 | 18 | 20 | complete | 56 | 5 / 11 / 34 / 14 | 8 | 39 | 9 / 0 / 0 / 1 | table d3 1 | — | 0.35 |
| 8 | 12 | 12 | complete | 38 | 5 / 7 / 21 / 11 | 3 | 33 | 7 / 0 / 0 / 3 | table d3 3 | — | 0.25 |
| 9 | 28 | 48 | complete | 123 | 24 / 21 / 29 / 67 | 30 | 59 | 39 / 0 / 0 / 6 | table d3 6 | — | 0.46 |
| 10 | 30 | 38 | complete | 90 | 13 / 25 / 38 / 36 | 15 | 57 | 22 / 0 / 0 / 6 | table d3 6 | — | 0.63 |
| 11 | 20 | 41 | complete | 87 | 10 / 32 / 38 / 37 | 17 | 44 | 22 / 0 / 0 / 3 | table d3 3 | — | 0.55 |
| 12 | 28 | 48 | complete | 105 | 13 / 29 / 32 / 57 | 32 | 49 | 41 / 0 / 0 / 8 | formula native 7, table d3 8 | — | 0.56 |
| 13 | 27 | 71 | complete | 113 | 10 / 27 / 47 / 53 | 37 | 71 | 45 / 0 / 0 / 7 | formula d3 1, formula native 2, table d3 6 | — | 0.65 |
| 14 | 16 | 31 | complete | 73 | 7 / 17 / 27 / 36 | 18 | 37 | 21 / 0 / 0 / 3 | table d3 3 | — | 0.38 |
| 15 | 27 | 34 | complete | 115 | 14 / 15 / 43 / 56 | 7 | 63 | 27 / 0 / 0 / 9 | table d3 9 | — | 0.53 |
| 16 | 64 | 123 | complete | 113 | 16 / 50 / 28 / 41 | 77 (49) | 42 | 31 / 0 / 0 / 2 | formula d3 1, table d3 1 | formula EMPTY_OUTPUT 24 | 0.56 |
| 17 | 22 | 28 | complete | 56 | 8 / 18 / 25 / 21 | 10 | 38 | 19 / 0 / 0 / 2 | formula d3 1, table d3 1 | — | 0.36 |
| 18 | 18 | 30 | complete | 74 | 9 / 14 / 32 / 31 | 15 | 38 | 23 / 0 / 0 / 3 | table d3 3 | — | 0.36 |
| 19 | 29 | 58 | complete | 109 | 10 / 38 / 40 / 56 | 36 | 71 | 42 / 0 / 0 / 8 | formula d3 1, formula native 1, table d3 7 | — | 0.80 |
| 20 | 50 | 108 | complete | 169 | 19 / 48 / 69 / 77 | 38 | 92 | 47 / 0 / 0 / 5 | formula native 2, table d3 5 | — | 1.19 |

Notes on the table:

- **"flagged"** counts d3 contradictions. A `FORMULA_NATIVE_MISMATCH` comes from the rule, not
  from d3. W2's 35 are the stand-in's canned answers, and catching them is the right outcome.
- **No item is `not_run` or unjudged.** Every check item got a d3 score. The 24 failed formulas and the
  pictures without text are not judged.
- **Paper 5's summary.** The 7 overview verify requests hit the 120 s deadline together and
  succeeded on their retry. This is provider latency; the paper still finished in 221 s. The 2
  `SCHEMA_INVALID` answers (papers 4, 6) also succeeded on retry.
- **No code item called the VLM.** `code@1` falls back to the VLM only without a text layer,
  and every corpus paper has one.
- **VLM latency.** The longest single VLM request took 27.1 s, against the 60 s deadline.

## Accuracy

The sample and gold are those of t3, t4 and t5b, unchanged. W2 is the one gold paper outside the
corpus; it carries 3 of the code units. "Alone" means the method run outside the workflow:

- **Local methods:** t3's own rows.
- **VLM methods:** t4's 64 targets. The exact request bodies t4-seam-b sent were sent once to
  Sonnet through the workflow's transport (`score.alone_answers`).

"Luna" is t4's recorded gpt-6-luna answer, shown for reference only.

| Area | Sample | Workflow | Alone | Luna (t4) | Difference explained |
|---|---|---|---|---|---|
| Picture OCR | 358 units in 18 images | 304 literal pass | 304 | — | none: every unit equal |
| Code | 13 units (10 corpus, 3 W2) | CER median 0.42 %; operators and numbers exact 9/13 | 0.18 %; 13/13 | — | 4 units, region (below) |
| Tables | 15 #84 tables | 15 grids identical to E0 | 15 | — | none |
| Chart values | 88 points in 5 images | diagnosis 66, formal 66 | 35, 35 | 84, 66 | label layout (below) |
| Chart values, x and category swapped back | same | 84 | 53 | 84 | as above |
| Descriptions | 18 gold images | 15/18 | 16/18 | 17/18 | run-to-run variation (below) |
| Display formulas | t4's 46 | 44/46 | 44/46 | 34/46 | none: same verdict on every formula |
| Summary verify (A7) | 150 planted sentences | see A7 | — | — | — |

- **Code.** Four units score worse in the workflow than alone, all for the same reason: the
  method alone runs on the union of #84's regions, while the workflow runs on the code items the
  layout found. t3's `inventory_covers_region` counted any overlap as covering, so it did not
  show the gap.

  | Unit | Regions | Covered by code items | Characters read |
  |---|---|---|---|
  | P-01 code 11 | 9 | 1 | 146 of 697 |
  | P-04 code 7 (known since t3) | 8 | 1 | 334 of 1,388 |
  | P-04 code 8 | 9 | 3 | 317 of 1,100 |
  | P-04 code 10 | 8 | 1 | 187 of 1,007 |

  The other 9 units score the same in both.
- **Chart values.** The workflow and alone sent the same request for all 5 images.
  - Image 16: Sonnet writes the model name as `x` and the metric as `category`, both times;
    Luna and t4's diagnosis view do the opposite. Swapped back, all 18 points pass.
  - Image 21: the workflow answer uses Luna's layout (30/30). The alone answer puts the panel in
    the series name ("MaTTS w/o memory (Parallel)") and leaves `category` empty, which scores
    0/30. All 30 (series, panel, x, value) tuples are equal to Luna's.
  - Image 17: 8 points in the workflow against 7 alone, from run-to-run variation.
- **Descriptions.** Same request on all 18.
  - Image 3: the workflow answer invents a figure title ("RL Outer Loop Iteration t"), FAIL;
    the alone answer passes.
  - Image 5: Sonnet infers the publisher both times, which the obligations rule out (Luna
    PASS).
  - Image 18: all three answers FAIL, as in t4.
  - Against t4's bar (not below #84's Luna, 16/18), the workflow is one short and alone meets it.
- **Formulas.** The workflow and alone got the same verdict on all 46.
  - p01-a5304a07488e: Sonnet writes a plain C for the calligraphic C (#152's font evidence).
    The workflow marks it `disputed FORMULA_NATIVE_MISMATCH`.
  - p16-e1d8a234b6b9: one of paper 16's instance ids. Sonnet answers an empty string both times.
    p16-35fa058a6093 is the other id in the sample; Sonnet's answers pass both times (alone:
    `\texttt{…}`, as Luna's).
  - Statuses on the 46: 4 are `disputed`. One of them is the wrong p01 formula; the other 3 are
    right (p17-ae7b5caad363 by d3, p19-4350684380ca and p20-e5976e29bae2 by the native rule).
    The empty answer is `failed`, so both wrong answers carry a status other than `unverified`.
- **d3 on the gold tables.** All 15 grids equal the ones #84 adjudicated. d3 flags
  `TABLE_D3_UNFAITHFUL` on all 9 tables #84 judged FAIL, and on 4 of the 6 it judged PASS. On
  all 167 tables it flags 117, the same count as t5c-seam-b. t5c read the flag as table quality
  (#153: 78 % `meaning_changed` with cell matching on); these 6 labelled tables say part of it
  is false flags. The sample is small. → #83/#203.
- **d3 on picture OCR.** No flags on the 164 OCR items it scored, while 54 of the 358 gold units
  fail the literal gate. This matches #153's "OCR weak". → #83.

### Where the workflow's requests come from

- For 384 of the 386 VLM items, t4-seam-b recorded the same request the workflow sent last (same
  `params_digest`, which leaves the model out).
- The other 2, a picture each in papers 11 and 14, have the same digest too. t4-seam-b sent
  them 3 times each to Luna and all 3 tries timed out at 60 s, so no answer was kept.
- The measurement works: it matched requests in every paper.

### Judging

- **Judge.** Each answer that differs from Luna's (whitespace aside) was judged blind against
  t4's rules by a Claude Opus 5.5 subagent: 60 sheets in two rounds (24 in the pilot, 36 now).
  An answer equal to Luna's keeps t4's verdict, and an item with no answer is FAIL.
- **Self-check before each round.**
  - Each item appears once.
  - Each image is the gold asset, or the crop of t4's target item fetched through t4's own
    store lookup (hashes equal).
  - Each letter's answer matches `letters.json`.
- **Control.** Luna's answer was on every sheet as the control; the judge agreed with t4 on 58
  of 60. The 2 disagreements came in the pilot:
  - p01-a5304a07488e: the judge passed Sonnet's plain C. It was reversed to FAIL, following
    t4's documented font evidence; the note is in `judgments.json`.
  - Image 18: the judge passed Luna. The verdict on Sonnet was FAIL either way.
- **Judgement calls.** The notes record 9 on this run's answers, all passed: 7 in the pilot
  round and 2 now. Examples:
  - Several p01 descriptions convey a table cell's role without naming the table.
  - p10-06d7a06c831b names an untitled axis "scaling factor k".
  - p09-ede3d51fae44 writes a hyphen as a math minus.

### A7: the summary's verify step, by error severity

t5b-accuracy's planted-error check on this run's summaries, with the same sets, seed 155 and
production verify request on Sonnet 5.5. Two changes from t5b:

- **Planter.** Sonnet 5.5 plants the errors instead of gpt-6-luna, whose DEV key had expired.
- **Error types in three tiers** (user, 2026-11-15; `score.SEVERITY`). The tiers take turns
  over the sample.

| Tier | What it gets wrong | Types |
|---|---|---|
| Severe | The paper's finding | fabrication (an invented result, dataset, number or entity), reversal (direction or polarity) |
| Moderate | One fact of the finding | t5b's five: number, causation, subject, scope, comparison |
| Subtle | A claim's strength, by one word | modality (must ↔ may, required ↔ optional), certainty (suggests ↔ shows) |

| | Held-out (15 papers) | Dev (papers 2, 4, 6, 16, 20) | Both |
|---|---|---|---|
| Sample (invalid plants) | 100 (2) | 50 (1) | 150 (3) |
| Severe caught | 33/33 | 17/17 | **50/50** (fabrication 26/26, reversal 24/24) |
| Moderate caught | 32/33 | 16/16 | **48/49** (the miss: "all" added, scope) |
| Subtle caught | 14/32 | 5/16 | **19/48** |
| False drops | 1/100 | 1/50 | 2/150 |
| Judge cost | US$1.11 | US$0.78 | US$1.88 |

The subtle tier, read plant by plant ([subtle-direction.json](subtle-direction.json): case,
type, direction and caught, with no paper text):

| Direction | Caught | Examples |
|---|---|---|
| Strengthened, other than "must" | 9/10 | not reliably → never, most → all, proposed as → shown to be; the miss: "definitely" added |
| Strengthened, "must" added | 6/14 | distills → must distill, every component matters → must matter |
| Weakened | 4/23 | must → may, prevents → can prevent, showing → suggesting |
| No change in meaning | 0/1 | a stray quote mark |

- **Weakened plants.** A weakened sentence is mostly still supported by the source, so "missed"
  there is largely the right verdict. One of the 4 catches names an unrelated claim.
- **Added "must".** The real gap is a "must" added to a descriptive sentence. The judge's
  reasons call it framing.
- **False drops.** Both are judge readings of the original that the pipeline's own verify
  passed: a gain stated for one model only, and a comparison called "arguably consistent".
- **Moderate tier vs #155.** 48/49 is in line with #155's held-out 80/86 (93.0 %) on the same
  five types. The planter differs, so the numbers do not compare directly.

What the pipeline itself did to its sentences, summed from `papers/<index>.json`, against
t5b-seam-b's `frozen-1` run of the same prompts:

| Sentences kept / rewritten / dropped | Held-out, this run | Held-out, frozen-1 | Dev, this run | Dev, frozen-1 |
|---|---|---|---|---|
| Section | 636 / 44 / 1 (6.5 %, 0.1 % of 681) | 638 / 38 / 3 (5.6 %, 0.4 % of 679) | 227 / 27 / 3 (10.5 %, 1.2 % of 257) | 231 / 20 / 3 (7.9 %, 1.2 % of 254) |
| Overview | 93 / 7 / 0 (7.0 % of 100) | 98 / 2 / 0 (2.0 % of 100) | 37 / 2 / 0 (5.1 % of 39) | 38 / 1 / 0 (2.6 % of 39) |

Rewrites run slightly higher than in frozen-1, with the same prompts and model; drops stay rare.
The two runs differ only by the model's run-to-run variation.

## Tokens and TPM

[tokens.md](tokens.md) has every paper × component row (requests, input, output, reasoning,
model), the aggregates, requests per document and tokens per request per component, and TPM
at every rate below; `tokens.py` writes all of it, so #203's rerun reproduces these tables.
Over the 20 corpus papers:

| | Median | Max |
|---|---|---|
| Tokens per document | 180,892 | 437,971 (paper 20, 50 pages) |
| Tokens per page | 7,189 | 9,659 |

Shares of all tokens: `document-summary` 65.7 %, `picture-interpretation` 21.5 %, `d3-check`
9.6 %, `formula` 3.3 %, `code` 0 %.

| Per document (mean) | #93 estimate | Measured |
|---|---|---|
| VLM requests (R) | ≈ 30 (pictures ~10, formulas ~15, category 1, slack) | 20.6 (pictures 8.2, formulas 12.3, code 0) |
| Tokens per VLM request (T) | ≈ 2.5k | 2,265, the VLM's tokens over its requests (pictures 4,915, formulas 505) |
| VLM tokens | ≈ 75k | 46,537 |
| Summary | 1 request, left out of TPM | 53.2 requests, 123,394 tokens |
| d3 | not in TPM | 26.2 requests, 17,944 input tokens (d3 generates no text) |
| Pages | 20 | 27.6 |

TPM is the mean tokens per document times documents per minute (`tokens.RATES`):

| TPM (`tokens.md` row) | VLM | Summary | d3 | VLM + summary (one endpoint in the released profile) | #93 |
|---|---|---|---|---|---|
| Pilot, 0.5/min (`pilot`) | 23,268 | 61,697 | 8,972 | 84,965 | VLM 37.5k → request 50k |
| #93's PROD mean, 6.94/min (`prod_mean_93`) | 322,965 | 856,352 | 124,530 | 1,179,317 | mean ~520k |
| #93's PROD peak, 20.82/min, k = 3 (`prod_peak_93`) | 968,894 | 2,569,057 | 373,591 | 3,537,951 | peak ~1.56M → the 0.5–1.5M tier |
| PROD peak, 50/min for 10 min (`prod_peak`, the ticket's) | 2,326,835 | 6,169,685 | 897,192 | 8,496,520 | — |

- **VLM alone is under #93's estimate.** It has fewer requests than #93 assumed, with heavier
  pictures.
- **The summary is the new load.** It sends one request per map, reduce, repair and verify
  step, not one per document. In the released profile the summary and the VLM share the company
  VLM endpoint, so the pilot needs about 85k TPM there, against the 50k requested.
- **These are not the final numbers.** They are Sonnet 5.5's tokenizer and image tokens
  (high-resolution tier) through the compatible endpoint, with thinking inside the output
  counts. The company VLM (Qwen3.8-27B) has its own tokenizer, thinks by default, and counts
  reasoning tokens against TPM. #203 reruns `tokens.py` there.

## Handoffs

- **#137, the release decision.** Hold the release on the 3 fixes above. After they land, rerun
  the parts they touch: the code units, the chart images and paper 16. Everything else here
  stands.
- **#203, the company environment.** Rerun, with the company VLM and d3:
  - `run.py` on the 20 papers; its `VLM_COMPONENT` and the profile's component swap become the
    company components;
  - `tokens.py` on that run's receipts;
  - `score.py` for accuracy, including A7;
  - the d3 table and OCR threshold retest, on this run's evidence of 4 false flags in 6 #84-PASS
    tables.

  Watch the summary's 120 s deadline (7 overview timeouts on paper 5).
- **#83, the rest of the scope.**
  - The table and OCR thresholds on labelled outputs (the 15 #84 tables are a start).
  - d3's missing OCR signal.
  - Wider gold.
  - The summary verify's gap on added "must" (6/14 caught) and its weakened-claim behaviour, if
    the product needs them.
- **#78, against #93's parameters.**
  - Requests per document: R ≈ 20.6, not 30.
  - Tokens per VLM request: T ≈ 2.3k (pictures 4.9k).
  - The summary adds about 53 requests and 123k tokens per document on the same endpoint, so
    the pilot TPM request becomes about 85k, not 50k.
  - The PROD peak for VLM + summary is about 3.5M at #93's 20.82/min, or 8.5M at the 50/min
    burst. Add d3 (0.9M at the burst) on its own service.
  - `c` and the I/O slots were not stressed: one paper at a time here.

## Spend

| Item | US$ |
|---|---|
| Workflow, 20 papers (Sonnet 5.5 at US$2 / US$10 per million tokens) | 10.48 |
| Methods alone, 64 requests | 0.36 |
| A7 judge, 150 cases (the planter is not counted by t5b; small) | 1.88 |
| Pilot A7 and probes | about 0.45 |
| **Total** | **about 13.2** (estimate US$12–14, stop line US$20) |

## Files

- In the repo, alongside the scripts and their tests (`test_score.py`, `test_tokens.py`):
  - `papers/<index>.json`
  - `accuracy.json`
  - `tokens.json` and `tokens.md`
  - `judgments.json`: verdicts by answer sha256, with notes
  - `evidence-held-out.json` and `evidence-dev.json`: A7 counts, no text
  - `subtle-direction.json`: the direction of each subtle A7 plant, by manual review
  - `manifest.json`
- **`manifest.json`** holds the sha256 of everything kept outside git:
  - the papers;
  - the profile the workers loaded;
  - the d3 package manifest;
  - the gold and scorers;
  - per request, the count and digest of its objects in the S3 stand-in (result and receipts,
    2,153 objects);
  - the raw outputs under OUT: the alone answers, the summaries, A7's cases and the judging
    sheets.
- **OUT is `~/archive/research/199-e2e/pilot2`, outside the repo.** It holds the S3 stand-in's
  data, the Temporal database, the logs, the alone answers, the summaries with their text, A7's
  cases and spot checks, and the judging sheets with their crops.
- **Reading OUT later.** `OUT/s3` is RustFS's own disk format, so its objects can be read only
  through a running stand-in, and that stand-in writes its own state into the data directory.
  `run.py archive OUT` checks OUT against `manifest.json` (`differs from manifest.json: none`
  on 2026-11-15) and leaves OUT unchanged. `--keep` leaves a stand-in serving a copy, on a free
  port so it does not collide with a run's 9199, and prints how to stop it.

## Run

```
set -a; . ~/.config/kp-dev/anthropic.env; set +a
A=~/archive/data-ingestion-wip-2026-10-21/untracked
scripts/heavy-lock 199-e2e -- env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/199/run.py \
    ~/archive/research/199-e2e/pilot2 "$A/docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json" "$A" \
    ~/models/issue84/w4b-d3-models/d3-mini ~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python \
    w2 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20
.venv/bin/python docs/validation/199/score.py summary ~/archive/research/199-e2e/pilot2 held-out 100 \
    1 3 5 7 8 9 10 11 12 13 14 15 17 18 19
.venv/bin/python docs/validation/199/score.py summary ~/archive/research/199-e2e/pilot2 dev 50 2 4 20 16 6
```

Papers already in `OUT/requests.json` are not run again, so the first command, rerun, only
rescores. When it leaves answers to judge, it writes them to `OUT/judging/sheets.json`. A judge
then writes `verdicts.json` beside them, and the next rescore merges it into `judgments.json`.
