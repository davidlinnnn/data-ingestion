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

A request took 0.62 / 0.83 / 4.49 s (min / median / max). No formula or OCR image of #153 is over
1.6 MP, which is why the downsized images are compared separately. Tables are not in this case:
the package takes a table's text from the assembly, so it cannot be handed #153's text (see
"Input format" below).

### W: the switch (paper 8, 12 pages)

Passes (`evidence-switch.json`).

| Request | Wall clock | Requests sent | New under `documents/` | Enrichments reused | Result sha256 |
|---|---|---|---|---|---|
| before | 11.9 s | 31 summary, 3 picture-interpretation | 56 objects | 0 of 21 | `86d25861…` |
| off | 2.1 s | 0 | 0 | 21 of 21 | `86d25861…` |
| on | 12.1 s | 7 d3-check | 14 objects in 7 item folders | 21 of 21 | `0ab886a8…` |

- `off` reuses every item `before` registered, so adding the check changes no reuse key, and the
  two results are equal.
- `on` adds one folder per check item (its outcome record and the service's reply) and nothing
  else; its check Activity ran 10.1 s for 7 requests. Its result differs from `off`'s only in the
  d3 signals and in the status of the three tables d3 contradicts.
- `kp-processing worker --queue d3` without `KP_D3_BASE_URL` exits 2 with
  `KP_D3_BASE_URL is required for the d3 worker`.

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

