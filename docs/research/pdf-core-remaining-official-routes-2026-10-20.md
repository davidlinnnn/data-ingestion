# Remaining official OCR / reading-order routes

Checked **2026-10-20 Asia/Taipei**, using upstream GitHub API/source and the published plugin package. This is a source audit: **no new inference, installation, credential access, or GitHub write**. Historical experiment files remain unchanged.

## What newer upstream work actually provides

| Route | Verified status | Relevance to our scanned two-column failures |
| --- | --- | --- |
| Upgrade Docling 2.132.0 → **2.140.0** | Latest GitHub release, published 2026-10-16. Its release notes include #4748 and #4633. [Release](https://github.com/docling-project/docling/releases/tag/v2.140.0) | A legitimate version comparison, **not a demonstrated fix** for this corpus. Do not infer qualification from release notes. |
| **#4748**, enclosed OCR regions | Merged 2026-10-14. Drops a crop wholly contained in another; deliberately retains partially overlapping crops. `FULL_PAGE` bypasses this selector. [PR and exact scope](https://github.com/docling-project/docling/pull/4748) | Does not split the original single cross-column crop. Does not establish a fix for C10's partially overlapping context crops. The fix concerns crop selection, not paragraph ordering. |
| **#4633**, reading-order separator limits | Merged 2026-10-16. Caps dense PDF-vector separator work and propagates timeout budgets. PR states unchanged behavior when limits do not intervene. [PR](https://github.com/docling-project/docling/pull/4633) | Relevant to hangs/resource bounds, not evidence of corrected ordering on our raster pages without vector separators. |
| **#4571**, overlapping text predictions | **Open, unmerged**; head `051c317e0aa11c72b31aede712ee052b7e8ea8d3`. Resolves overlapping layout predictions before cell assignment and restores supported paragraph boundaries. Its reported integration validation disables OCR/table inference on born-digital PDFs. [PR](https://github.com/docling-project/docling/pull/4571) | An experimental code change with some two-column tests, not a shipped option or demonstrated raster-OCR repair. It does not claim to change the shared OCR crop dilation or replace `predict_reading_order` / `predict_merges`. |

## A different public reading-order model is not currently a configuration choice

Both examined Standard implementations directly instantiate `ReadingOrderModel`, which constructs the rule-based predictor. The public pipeline option examined is `use_reading_order_separators`; there is no model factory/selector at that seam in these versions. This is a source finding, not a claim that subclassing is impossible. [2.132 Standard](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L653), [2.140 Standard](https://github.com/docling-project/docling/blob/v2.140.0/docling/pipeline/standard_pdf_pipeline.py#L682), [2.140 reading-order model](https://github.com/docling-project/docling/blob/v2.140.0/docling/models/stages/reading_order/readingorder_model.py).

The proposed `spatial_ordering` / `OrderingStrategy` examples in #2683 remain issue-author proposals. A human maintainer described a future choice of reading-order modules; that comment is not an available API. [Issue](https://github.com/docling-project/docling/issues/2683), [maintainer comment](https://github.com/docling-project/docling/issues/2683#issuecomment-3579864884).

## SuryaOCR: a real official example, an external integration

Docling does publish a Surya example, and it already exists in **both 2.132.0 and 2.140.0**. It imports `SuryaOcrOptions` from the separately installed `docling-surya` package and enables external plugins. Thus it is an **untried supported integration example**, not a new native Docling OCR implementation or a proven column fix. [Pinned example](https://github.com/docling-project/docling/blob/v2.132.0/docs/examples/suryaocr_with_custom_models.py), [current-release example](https://github.com/docling-project/docling/blob/v2.140.0/docs/examples/suryaocr_with_custom_models.py).

Published `docling-surya` **0.1.0** metadata declares Python ≥3.12, Docling ≥2.60.0, and Surya OCR ≥0.17.0. These lower bounds include our pinned Python/Docling versions but do not establish runtime compatibility with the resolved dependencies. The package README advertises **Linux x86_64 only**; Mac support cannot be assumed from the platform-neutral wheel. [Package metadata](https://pypi.org/pypi/docling-surya/0.1.0/json), [package documentation](https://pypi.org/project/docling-surya/0.1.0/).

Source inspection of that release's published wheel shows:

- It calls inherited `get_ocr_rects(page)` before running Surya detection/recognition. It therefore retains Docling's crop-selection seam; swapping the engine does not itself remove the shared crop merge.
- It returns OCR cells to the standard pipeline and does not replace Docling's layout/reading-order model. Surya as an OCR engine here must not be confused with adopting a separate end-to-end Surya layout/order pipeline.
- Although options expose `lang` and `use_gpu`, this implementation does not forward them into the predictor constructors/call. Actual language/device behavior needs separate verification; do not claim an option works from its schema alone.

The official example explicitly identifies external GPL licensing; package/model terms need review before selecting it for delivery. No licensing conclusion is made here. [Official example notice](https://github.com/docling-project/docling/blob/v2.140.0/docs/examples/suryaocr_with_custom_models.py), [published plugin source distribution](https://pypi.org/project/docling-surya/0.1.0/#files).

## PaddleOCR-VL: external full pipeline, not RapidOCR weight selection

The official `paddleocr_vl_result_to_docling.py` example consumes **already produced** PaddleOCR-VL JSON; it explicitly neither imports Paddle/PaddleX nor runs/downloads models. The examined 2.140 example targets PaddleOCR-VL 1.6 / PaddleX 3.7.2 single-page results and notes processed-page geometry, rectangular polygon approximations, absent image bytes in ordinary saved JSON, and no `restructure_pages()` parity. [Official importer example](https://github.com/docling-project/docling/blob/v2.140.0/docs/examples/paddleocr_vl_result_to_docling.py).

Thus the full Paddle inference path remains an untested alternative in this investigation, distinct from the completed **Standard + RapidOCR + PP-OCRv5 server det/rec** comparison. It requires an external inference pipeline and adapter validation, not just selecting a Standard OCR engine. An importer passing on saved results does not establish end-to-end model accuracy, latency, multipage behavior, or provenance parity.

## Finite recommendation

1. **Do not label all official possibilities exhausted.** A version comparison, external Surya integration, and other engines remain different from the configurations already inferred. Conversely, public support is not proof that they fix our observed defects.
2. Before another paid/model round, require a source-level reason the proposed change reaches the failing seam: crop selection, native ordering, native merges, or OCR recognition. The currently cited 2.140 fixes do not justify promising a two-column repair. Existing saved native replays already locate ordering/merge failures; repeating them unchanged adds no evidence.
3. If selecting Surya as one final OCR candidate, first perform a **zero-inference compatibility/device/language check in a separate environment**. Treat Linux availability as a prerequisite given the plugin's stated support. Freeze one package/model configuration; run the existing seven-page regression once, then the frozen six-page validation only if it survives. No automatic fallback into a custom Mac port, additional engine sweep, or parameter search.
4. Keep C10 as an existing positive control for the two audited page orders, with its duplicate/content failures retained. Repairing crop ownership or replacing native order is **custom engineering**, outside the user's present preference. Upstream reproducer/patch work and selective VLM remain separate explicit method choices, not undisclosed extensions of an OCR configuration test.

No remaining route above has demonstrated qualification on this corpus. This audit does not estimate general failure rates, compare production latency, or claim that seven exposed development pages provide independent benchmark accuracy.
