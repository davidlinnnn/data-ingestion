# Native Docling visualization of scan-p1

Uses retained S0 (`StandardPdfPipeline`, Docling 2.132.0 / Core 2.99.0) from the first page of `scan-pages-3-5.pdf`, corresponding to the requested `inputs/scan-p1.png`. This is visualization of the existing parsing result, not a new PNG conversion or model comparison.

Only the in-memory presentation copy's page image is replaced by the exact requested PNG, at the same 612×792 PDF page geometry / 1224×1584 pixels. Saved text, provenance, ordering, historical JSON/Markdown and sealed experiments remain unchanged.

- Native split-page view (`output/source-and-parsed.html`): left is the native layout/reading-order overlay, right is the actual parsed HTML text, including defects.
- Final layout (`output/final-layout.png`): native `LayoutVisualizer`, showing final `DocItem.prov` boxes, not raw Heron proposals.
- Reading order (`output/reading-order.png`): native `DoclingDocument.get_visualization`, red arrows follow the saved inferred order, not correct reference order.
- OCR input and cells (`output/debug_scan-p1/ocr_page_00001.png`): native `BaseOcrModel.draw_ocr_rects_and_cells`; yellow is the merged OCR input region and magenta is OCR textline cells.

Native layout labels are hidden because the visualizer's default `1.00` is not a measured model confidence. No custom boxes, arrows, text repairs or ordering are added. The renderer's assertions check preserved text/geometry and source hashes, expected page size and valid output images; no model or download is needed.

Official references: [Docling visualization API](https://docling-project.github.io/docling/reference/docling_document/#docling_core.types.doc.document.DoclingDocument.get_visualization), [Core 2.99.0 layout visualizer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/visualizer/layout_visualizer.py), [native HTML visualizer integration](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/html.py#L1128).

## Intermediate stages

The 13-stage evidence viewer (`output/stages/index.html`) adds PDF native cells, raw Heron proposals, merged OCR regions, RapidOCR preprocessing/detection/orientation/recognition, PDF/OCR merge, layout postprocessing, inactive table/enrichment stages, paragraph assembly, reading order and export. Serve `output/` with a local HTTP server; the viewer loads `stages/data.json` and cannot load it through `file://`.

`render_stages.py` uses native Docling drawing/debug APIs, plus exact retained crops and text. The detector main image draws retained quads with custom index-only labels; a linked alternative uses RapidOCR's native drawing function. The responsive stage navigation is a custom viewer, not an official Docling timeline. No model inference, downloads, SDK changes or text repairs occur. Run it with the pinned native experiment environment. Its assertions verify the replay identity, stage counts, coordinates, the false 180-degree rotation and unchanged source hashes; `output/stages/manifest.json` records inputs and generated assets.

The mainline is the original S0 trace. RapidOCR internals come from the separate, exactly equivalent A replay in `pdf-core-ocr-crop-ablation-2026-10-19`; its boxes/texts/scores/cells match S0, but it was not the same execution. This is not the separated-crop B output. No raw model probability maps were captured. The original native detector graphic contains `nan` placeholders supplied by this viewer because scores were not retained, not because the detector emitted invalid scores. The main image now displays only indices to avoid implying a model failure.

Useful checkpoints: **2** Heron has no cross-column proposals; **3** region merging produces one cross-column OCR input; **5** detector indices 3/4/15 already cross columns before recognition; **6** index 39 is wrongly rotated; **9/11** these errors enter paragraph groups and line joining. These observations localize the saved failure, without proving a replacement method or broader accuracy result.

Docling's intermediate debug flags are documented in [the pinned settings source](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/settings.py#L44): `visualize_cells`, `visualize_raw_layout`, `visualize_ocr`, `visualize_layout` and `visualize_tables`.
