# #161 Seam B: the d3 Quality Check against d3-mini

`run.py` runs corpus papers through the real stack with the DEV profile
(`tests/profiles/paper-pdf-dev.yaml`): Temporal dev server, the RustFS S3 stand-in,
`tools/fake_admission`, and one `kp-processing worker` process per queue, the new `d3` queue
included. The d3 worker calls the model package's `d3_server.py` (d3-mini, revision
`bd0090dd`, `--device mps --batch-size 1`) at `POST /v1/systemone` with a bearer key; the DEV
profile sends one check request at a time per document, so every request is its own forward, as
in #153.

No request leaves the machine. The VLM stand-in replays the gpt-6-luna responses recorded for
the corpus (`tests/fixtures/vlm`, #133 and #152), so the judged formulas are real model output;
a request without a recording gets the canned answer. The summary stand-in is the DEV fake.
`against_153.py` compares the package with #153's frozen inputs and scores, and `vllm_sr.sh`
points the same client at vLLM Semantic Router.

## Scenarios and acceptance criteria

| # | Scenario | Acceptance criteria |
|---|---|---|
| A | `against_153.py`: the package builds a request for every #153 formula and OCR item (dev and test) from the original image and the reconstruction; the test items are then sent through `SystemOne` to the d3 server | state, question and the sha256 of the image as sent equal #153's `model-inputs.json`; every image #153 downsized comes out with the same sha256; every test score equals #153's `run_d3.py` score; the same items are contradicted |
| W | Switch, one paper in one bucket: `before` (the code and DEV profile of the commit this branch started from), `off` (this code, the DEV profile without `d3-check`, no d3 worker, no `KP_D3_*` variable), `on` (this code, the DEV profile, the d3 worker) | `off`: no request, nothing new under `documents/`, result equal to `before`'s by sha256 (without `request_id` and the `reused` flags). `on`: every enrichment reused, only d3 requests, only the check items new under `documents/`, the same inventory, and no difference from `off` beyond the d3 signals and the status of contradicted items. `worker --queue d3` without `KP_D3_BASE_URL` exits 2 and names the variable |
| S | Each of the 20 papers in a fresh bucket | exit 0; every formula, table-status and picture-ocr item whose outcome is `success` carries a d3 score; no item is `not_run`; one ok d3 request per check item |
| C | A second request for the same document, same bucket | exit 0; no request; every check outcome reused; nothing new under `documents/` |
| V | `vllm_sr.sh`: the lowest- and highest-scored #153 test item per category through `SystemOne` to vLLM Semantic Router's Engine mode (Docker, CPU, `--dtype float32`) | a score is read from every reply; each judgement equals #153's |

## Result

Runs of 2026-11-05 on the 48 GiB M5 Mac, each under `scripts/heavy-lock`.

### A: the requests and scores of #153

All pass (`evidence-153.json`).

| | Items | Result |
|---|---|---|
| Requests, formula (dev + test) | 220 | state, question and image sha256 equal #153's for all 220 |
| Requests, OCR (dev + test) | 29 | equal for all 29 |
| Images #153 downsized to 1.6 MP (any category) | 131 | the package's downsized PNG has the same sha256 for all 131 |
| Scores, formula test | 110 | all 110 equal #153's (largest difference 0); 24 contradicted, the same 24 as in #153 |
| Scores, OCR test | 13 | all 13 equal; none contradicted (weak signal) |

A request took 0.59 / 0.83 / 4.52 s (min / median / max). No formula or OCR image of #153 is over
1.6 MP, which is why the downsized images are compared separately. Tables are not in this case:
the package takes a table's text from the assembly, so it cannot be handed #153's text (see
"Input format" below).

### W: the switch (paper 8, 12 pages)

Passes (`evidence-switch.json`, run `2dc1d2`). The sha256 is comparable within a run only.

| Request | Wall clock | Requests sent | New under `documents/` | Enrichments reused | Result sha256 |
|---|---|---|---|---|---|
| before | 11.4 s | 31 summary, 3 picture-interpretation | 56 objects | 0 of 21 | `e811d992…` |
| off | 2.1 s | 0 | 0 | 21 of 21 | `e811d992…` |
| on | 12.3 s | 7 d3-check | 14 objects in 7 item folders, none elsewhere | 21 of 21 | `80e21236…` |

- `off` reuses every item `before` registered, so adding the check changes no reuse key, and the
  two results are equal.
- `on` adds one folder per check item (its outcome record and the service's reply) and nothing
  else; its check Activity ran 10.3 s for 7 requests. Its result differs from `off`'s only in the
  d3 signals and in the status of the three tables d3 contradicts.
- `kp-processing worker --queue d3` without `KP_D3_BASE_URL` exits 2 with
  `KP_D3_BASE_URL is required for the d3 worker`.

### S and C: the 20 papers (551 pages)

All 20 pass both cases (`evidence-1.json` to `evidence-20.json`, run `ecf447`).

| Paper | Pages | Formulas judged / items | Tables judged / items | Picture OCR judged / items | d3 requests | Check Activity (s) | d3 request median / max (s) | Formulas d3 contradicts | `FORMULA_D3_UNFAITHFUL` | `FORMULA_NATIVE_MISMATCH` | `TABLE_D3_UNFAITHFUL` | S (s) | C (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 28 | 8 / 8 | 7 / 7 | 9 / 11 | 24 | 34.1 | 0.88 / 4.26 | 2 | 1 | 1 | 6 | 56.0 | 1.2 |
| 2 | 22 | 0 / 0 | 1 / 1 | 2 / 2 | 3 | 6.1 | 1.33 / 3.31 | 0 | 0 | 0 | 1 | 17.9 | 1.0 |
| 3 | 25 | 6 / 6 | 14 / 14 | 8 / 8 | 28 | 45.4 | 1.00 / 7.59 | 0 | 0 | 3 | 12 | 70.8 | 1.1 |
| 4 | 27 | 3 / 3 | 6 / 6 | 4 / 4 | 13 | 31.7 | 1.38 / 12.05 | 0 | 0 | 1 | 6 | 55.8 | 1.1 |
| 5 | 31 | 9 / 9 | 15 / 15 | 6 / 6 | 30 | 48.7 | 1.36 / 3.32 | 2 | 1 | 2 | 14 | 72.6 | 1.3 |
| 6 | 29 | 1 / 1 | 22 / 22 | 9 / 10 | 32 | 46.0 | 1.10 / 4.94 | 0 | 0 | 0 | 16 | 75.3 | 1.2 |
| 7 | 18 | 2 / 2 | 1 / 1 | 6 / 6 | 9 | 14.0 | 1.33 / 3.31 | 0 | 0 | 0 | 1 | 28.5 | 0.8 |
| 8 | 12 | 0 / 0 | 4 / 4 | 3 / 3 | 7 | 10.4 | 1.29 / 2.53 | 0 | 0 | 0 | 3 | 21.5 | 0.7 |
| 9 | 28 | 25 / 25 | 9 / 9 | 5 / 5 | 39 | 63.1 | 0.84 / 6.97 | 2 | 0 | 2 | 6 | 96.3 | 1.2 |
| 10 | 30 | 0 / 0 | 7 / 7 | 15 / 15 | 22 | 34.8 | 1.21 / 3.99 | 0 | 0 | 0 | 6 | 62.7 | 1.1 |
| 11 | 20 | 6 / 6 | 5 / 5 | 11 / 11 | 22 | 35.5 | 1.20 / 4.66 | 1 | 1 | 0 | 3 | 59.5 | 0.8 |
| 12 | 28 | 26 / 26 | 9 / 9 | 6 / 6 | 41 | 52.7 | 0.95 / 3.69 | 2 | 1 | 8 | 8 | 75.7 | 1.2 |
| 13 | 27 | 29 / 29 | 8 / 8 | 8 / 8 | 45 | 48.0 | 0.85 / 3.83 | 3 | 1 | 3 | 6 | 69.0 | 1.3 |
| 14 | 16 | 10 / 10 | 3 / 3 | 8 / 8 | 21 | 35.3 | 0.98 / 5.09 | 0 | 0 | 0 | 3 | 57.2 | 0.8 |
| 15 | 27 | 1 / 1 | 20 / 20 | 6 / 6 | 27 | 54.9 | 1.92 / 7.97 | 0 | 0 | 0 | 9 | 80.2 | 1.2 |
| 16 | 64 | 39 / 44 | 3 / 3 | 8 / 8 | 50 | 53.3 | 0.84 / 2.92 | 10 | 8 | 5 | 1 | 83.4 | 2.0 |
| 17 | 22 | 4 / 4 | 9 / 9 | 6 / 6 | 19 | 19.5 | 0.85 / 1.91 | 1 | 1 | 0 | 1 | 36.3 | 1.0 |
| 18 | 18 | 10 / 10 | 8 / 8 | 5 / 5 | 23 | 29.1 | 0.87 / 2.54 | 0 | 0 | 1 | 3 | 46.6 | 1.0 |
| 19 | 29 | 22 / 22 | 7 / 7 | 13 / 14 | 42 | 51.8 | 0.92 / 2.21 | 0 | 0 | 5 | 7 | 76.2 | 1.2 |
| 20 | 50 | 16 / 16 | 9 / 9 | 22 / 22 | 47 | 73.3 | 1.08 / 4.81 | 3 | 2 | 3 | 5 | 112.6 | 1.8 |
| **All** | 551 | 217 / 222 | 167 / 167 | 160 / 164 | 544 | 787.7 | | 26 | 16 | 34 | 117 | 1254.1 | 23.0 |

"Judged" is the items whose outcome is `success`, and every one of them carries a d3 score: the
5 failed formulas (paper 16) and the 4 pictures without text are not judged. The three reason
columns count `disputed` enrichments by status reason; "Formulas d3 contradicts" also counts the
10 formulas that the rule contradicts first (`FORMULA_NATIVE_MISMATCH` is then the status
reason).

- **S.** 544 check items, 544 d3 requests, all answered on the first send; no item is `not_run`.
  The check Activity took 787.7 s in all, 1.45 s per check item with one request at a time per
  document. The requests carried 365,447 input tokens (672 each).
- **C.** The second request sent nothing, added nothing under `documents/` and reused all 544
  check outcomes.
- **VLM stand-in.** All 227 formula requests and 162 of 164 picture-interpretation requests were
  answered from the recordings; 2 got the canned answer.
- **Formulas.** d3 contradicts 26 of 217 (12%). 41 of the 217 have a crop and LaTeX that are
  byte for byte a #153 item's, and all 41 get #153's score.
- **Picture OCR** is a weak signal and changes no status: p is 0.18 / 0.50 / 0.96 (min / median
  / max), below 0.5 for 81 of 160.

### Tables: d3 contradicts 117 of 167

The grid of every table of papers 1 and 8 was read (11 tables), with the crop beside it where
the text alone left doubt. All 11 grids are wrong: several columns of numbers sit in one cell,
and header cells are displaced. d3 contradicts 9; the other 2 pass with p 0.79 and 0.35, above
the threshold 0.306.

The rate matches what #153's labels say about this docling configuration, so it reads as table
quality, not as a threshold that moved: of #153's tables from the baseline with cell matching
on (the profile's setting), 18 of 23 are labelled `meaning_changed` (78%), against 11 of 36
(31%) with cell matching off. With `d3-check@1` on, most tables of such papers are therefore
`disputed`. The table extraction is outside #161.

### V: vLLM Semantic Router

Passes (`evidence-vllm-sr.json`): `vllm-sr` 0.5.0.dev20261020093359, Engine mode in Docker on
the CPU (`--dtype float32 --max-num-seqs 1`), d3-mini at revision `bd0090dd`, no API key.

| #153 test item | Score | #153's score | Judgement |
|---|---|---|---|
| Formula, lowest score | 0.02556 | 0.02548 | contradicted, as in #153 |
| Formula, highest score | 0.99428 | 0.99426 | not contradicted, as in #153 |
| OCR, lowest score | 0.13565 | 0.13467 | weak signal, no contradiction |
| OCR, highest score | 0.96822 | 0.96930 | weak signal, no contradiction |

The reply holds `answers`, `model` (`vllm-sr/d3-mini`) and `usage` (`input_tokens`,
`output_tokens`), which is what the client and the token metric read. The scores differ from
#153's by at most 0.0011: float32 on the CPU against BF16 on MPS. A request took 4.0 to 13.1 s,
which says nothing about PROD. No table is sent: `against_153.py` cannot build a table request
without an assembly, and a table request differs from these only in its state and question.

### Not covered

- The table and OCR thresholds on `paper-pdf@1`'s own outputs: no labels exist for them. #83
  retests them on the deployed service.
- The deployed model revision cannot be read through the API; the signal records the revision
  the constants were measured at.
- PROD latency and throughput: this is d3-mini on MPS, one request per forward.

## Input format compared with #153

The check sends what `paper-pdf@1` itself produced. For formulas that is what #153 measured;
for tables and picture OCR, #153 measured #84's outputs, and these differences remain:

| | #153 | `d3-check@1` on `paper-pdf@1` |
|---|---|---|
| Formula image | the crop the formula method made (#152 and #133 items), or #84's crop (CodeFormulaV2 items) | the formula item's evidence crop: the same crop for the #152 items |
| Formula text | the method's LaTeX | the outcome record's content, the same LaTeX |
| Table image | the table's box rendered from the PDF at scale 2.5 with a margin of 16 pt left and right, 30 pt above and 42 pt below, so a caption next to the table is usually in the picture | table-status's evidence: the page image (scale 2.0) cut to the table's box with no margin, so the caption is not in the picture |
| Table text | #84 W3's saved RAW Markdown export: the caption, a blank line and the grid, or the grid alone (11 of 59) | docling's `export_to_markdown` of the table node in the assembly: the same layout and the same `tabulate` grid |
| Table producer | docling in two #84 configurations: E0 (23 items) and cell matching off (36) | the profile's pinned docling, TableFormer accurate with cell matching on |
| OCR image | #84's picture crop | the picture image the profile registered |
| OCR text | RapidOCR's lines, one per row | picture-ocr's content: RapidOCR's lines joined by newlines |

The table question says "a caption line above the grid is not judged", so the caption text is
sent in both. Whether the table and OCR thresholds hold on these inputs is #83's retest; this
run reports how often d3 contradicts them and looks at a sample.

