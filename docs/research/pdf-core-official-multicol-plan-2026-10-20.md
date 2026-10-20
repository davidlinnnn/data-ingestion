# Official-only scanned multi-column experiment plan — 2026-10-20

Status: proposed, no new inference performed. Supersedes the recommendation to extend C10. User rejects custom padding, crop connectivity, ownership/dedup and layout-specific tuning. C0/C10 remain immutable diagnostic evidence and are removed from adoption candidates. No custom OCR/layout/reading-order plugin, SDK patch or output repair in this plan.

## Finite candidate set

Use the pinned Docling2.132.0 runtime, StandardPdfPipeline, PyPdfium backend, existing RapidOCR ONNX v6small detector/recognizer and mobilev2 classifier, same scale/threads/table/enrichment options and native ReadingOrderModel. Single layout alternative: official `layout_egret_large`; resolve and lock immutable model revision and all weight hashes before inference. No version upgrade mixed into this comparison.

| Layout | OCR DEFAULT | OCR FULL_PAGE |
|---|---|---|
| Heron default | Retained seven-page R0 control | Retained seven-page official/full control |
| Egret Large | New7 conversions | New7 conversions |

Only14 new page attempts, once per profile/page, no output retries or added configurations after results. Exact pipeline option diff must be confined to layout model/preset and the predeclared OCR mode. Each configuration applies unchanged to all pages; no page-specific gutter/line-spacing values. Official EgretLarge support is in the pinned runtime, and the public options docstring explicitly suggests EgretLarge/XLarge for complex documents. EgretMedium was already tested in the old11-page native round and did not solve the known order issue; it is not falsely counted as untried. Heron101/XLarge/different OCR weights are not automatically appended to this round.

In FULL_PAGE, OCR input is independent of layout. Verify that saved OCR cells reproduce the Heron FULL_PAGE control where expected; a difference is investigated as a control/environment issue rather than attributed to layout quality. DEFAULT tests whether different official layout proposals affect the actual native crop/assembly outcome, but the same20 kernel remains. This is a bounded official comparison, not a guarantee that a larger model can bypass region merging.

## Preflight and anti-overfit safeguards

Before image inference, lock sources, references, options, runtime/model identity and evaluator version. Check real model support and local load/memory feasibility; budget900s/profile,180s/page/init,12GiB sampled tree RSS, prelaunch10GiB available and8GiB floor as prior runs. A resource stop is not an accuracy failure, and cannot silently trigger another model. CPU first; no GPU-speed claim.

Retain seven exposed regression pages. Validate the order diagnostic without inference against known C10 positive control (12 main-body units in correct order) and FULL_PAGE negative control (5 pair inversions). Preserve frozen meanings: real paragraph continuations across columns are legal; NCCU headings present with wrong enumeration are not whole-heading omissions. Check partial-line duplication in addition to whole-unit flags, without altering parsed content. Review source pages and diagnostic flags manually.

Before candidate outputs are seen, freeze an independent six-page set from at least three additional documents, spanning narrow/wide gutters, tighter/looser line spacing, full-width headings/figures and varied scan quality; aim to include natural scans rather than only clean born-digital rasterizations. Record actual coverage and any missing stratum honestly. Do not open or reuse existing sealed holdout answers. Sources/page numbers/images/expected main-body order and source-critical units must be locked before inference; no replacement after failure.

## Evaluation and one-time validation

Compare capabilities separately: cross-column sentence corruption, final native body.children main-body order, heading/paragraph coverage, partial/whole duplication, content/identifier/inline-math meaning, elapsed conversion/init and guarded RSS. General OCR glyph/formatting differences remain reviewable minor deviations under the accepted criteria, not a reason to automatically call all source content absent. Critical sentence/identifier/math changes remain major. This is an OCR/layout/order capability decision, not proof all #84 requirements pass.

Select at most one configuration from development results, then run it once on the six frozen independent pages with no tuning afterwards. If no development candidate qualifies, do not run validation for appearance's sake. Total maximum20 new page attempts (14 development +6 validation). All final outputs get the same source/parsed visualization. Cached historical timings are descriptive, not a paired SLO benchmark; no formal latency limit has been agreed.

## Stop and decision

- If one official configuration has acceptable content/order and passes independent variation checks, retain it as a scoped scanned-PDF candidate and assess measured cost; do not assume born-digital FULL_PAGE adoption.
- If both Egret configurations still have required multi-column/order defects, close this finite Standard-native comparison. Do not automatically add XL/101/kernel/threshold/cropping variants.
- If independent validation fails, report lack of demonstrated generalization and stop tuning on those pages.
- Next decision would be an official structured VLM pipeline with its own resource budget, accept/defer the limitation, or an upstream fix. Existing Granite/dots/Nemotron results are not assumed qualified; whole-page VLM is not silently adopted for high-frequency ingestion.

## Input from the linked advanced-options page

[Official advanced options](https://docling-project.github.io/docling/usage/advanced_options/):

- [Control PDF parser threads](https://docling-project.github.io/docling/usage/advanced_options/#control-pdf-parser-threads): `ThreadedDoclingParseBackendOptions.parser_threads` configures docling-parse; `accelerator_options.num_threads` controls model CPU inference. Current tests explicitly use PyPdfium, so the parser thread setting is not the active backend control. It belongs in later cloud-native concurrency/resource measurements, not a remedy for OCR merging or logical order. Do not blindly assign8 threads to every worker.
- [Use visible PDF rules for reading order](https://docling-project.github.io/docling/usage/advanced_options/#use-visible-pdf-rules-for-reading-order): native supported geometry signal, already enabled in our options. It uses PDF vector rules and affects order, not OCR region selection. Raster images provide no such vector separator; a line visible inside an image is not automatically that geometry.
- `table_structure_options.do_cell_matching=False` concerns table cell assignment, not newspaper/paper body columns. Do not add it as a multi-column prose hypothesis.
- `NativePdfPipeline` extracts PDF-native cells/bitmaps without layout/OCR/table models. Useful as a separate born-digital efficiency route; cannot recover scanned text and is not an alternative for the current raster failure.
- Public scale choices exist and the earlier14-option round tested scale3/2. Do not return to per-page scale/kernel tuning under this plan. Image DPI metadata determines physical size, so source geometry is frozen and checked.

[Official model catalog](https://docling-project.github.io/docling/usage/model_catalog/) and [pinned options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py) establish supported model choices. Latest release2.140.0 was checked separately; the noted OCR fix removes contained duplicate regions, not a demonstrated split of an already-connected cross-column crop. No claim that version-only upgrade fixes this case.

Sources of existing evidence: [S0/S1 native results](pdf-core-native-round-results-2026-10-17.md), [official OCR options](pdf-core-ocr-official-options-2026-10-19/report.md), [C10 vs FULL_PAGE native order audit](pdf-core-c10-reading-order-audit-2026-10-20.md).
