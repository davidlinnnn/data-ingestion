# Frozen orientation and mixed OCR source review

Reviewed 2026-10-15 by the independent reviewer. The unchanged G1 cases (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`) have SHA-256 `8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a`. All six relevant frozen full-page images and the source PDF were rehashed successfully. The independent source check (`source-check.json`) records source hashes, page dimensions, PDF rotation and native text-layer observations. No oracle was edited.

## Source and selected scope

All six cases use physical pages 3–8 of the controls PDF (`docs/fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf`), registry SRC05, SHA-256 `8ddae37b0461b3749402e44b4a40b0e65b3d6b9ad78cf2f03ed20d1950faba90`. The generator (`docs/fixtures/pdf-core-g1-controls-2026-10-14/generate.py`) and truth (`docs/fixtures/pdf-core-g1-controls-2026-10-14/truth.json`) document the image rotation and rasterization. Visual review covered each complete frozen page.

| Case | Physical page and evidence | Content CCW rotation | Corrective CCW rotation | Source page points |
| --- | --- | ---: | ---: | --- |
| G1-C08 | 3 (`docs/research/evidence/pdf-core-g1-2026-10-14/controls/controls-3.png`) | 0° | 0° | 612 × 792 |
| G1-C09 | 4 (`docs/research/evidence/pdf-core-g1-2026-10-14/controls/controls-4.png`) | 90° | 270° | 792 × 612 |
| G1-C10 | 5 (`docs/research/evidence/pdf-core-g1-2026-10-14/controls/controls-5.png`) | 180° | 180° | 612 × 792 |
| G1-C11 | 6 (`docs/research/evidence/pdf-core-g1-2026-10-14/controls/controls-6.png`) | 270° | 90° | 792 × 612 |

All four pages have `/Rotate` equivalent 0 and zero native text characters according to independent PDFium inspection. Their visible content is the same two-column English page, rotated in the page image itself. A model's orientation label must be interpreted according to its corrective-angle convention; matching a source content angle to a corrective angle would reverse the quarter turns.

The frozen positive transcript is only the 16 lines in two paragraphs at the upper-left of the normalized upright page, originally from G1-O03. It compares related reviews, then maps Sections 2/3/4–7/8 to the survey's scope. The right-column bullets, lower `2 OVERVIEW` section and footnotes lie outside this positive transcript. They remain part of full-page OCR output and cannot be interleaved into the selected paragraphs while claiming correct reading order.

The normalized selected envelope is `[45, 42, 303.5, 229]` PDF points with top-left origin. Its frozen source-page envelopes are `[45, 42, 303.5, 229]`, `[42, 308.5, 229, 567]`, `[308.5, 563, 567, 750]` and `[563, 45, 750, 303.5]` for pages 3–6 respectively. These are approximate manual envelopes, not new overlap thresholds. Source page numbers and a declared inverse transform must accompany normalized OCR boxes. Normalized boxes alone cannot be asserted to be source coordinates.

G1-C12 physical page 7 (`docs/research/evidence/pdf-core-g1-2026-10-14/controls/controls-7.png`) has five native text blocks: the page title, before paragraph, Figure 1 source caption, after paragraph and final mixed Chinese/English sentence. Independent native extraction returns all five, including exactly `請確認 GPU worker 在 ready 狀態後，呼叫 OpenAI-compatible API。`. The embedded screenshot contains the five G1-O01 items: breadcrumb; 我的專區; 應用系統; the instruction containing quoted 連結; and B5A:個人簡要自述. The original selected panel (`docs/research/evidence/pdf-core-g1-2026-10-14/ocr/nccu-embedded-selected-panel.png`) was also inspected for those glyphs and repeated labels.

Native before and after paragraphs must each be delivered once. Screenshot OCR is derived content linked to this page's Figure 1 image; the main Markdown must refer to the same-version image rather than merge screenshot recognition into native source prose. The real Figure 1 caption must appear once and remain attached to that image. The additional native mixed sentence retains the `ready` condition, `後`, OpenAI-compatible and API in one sentence.

G1-C13 physical page 8 (`docs/research/evidence/pdf-core-g1-2026-10-14/controls/controls-8.png`) is a complete raster-only copy of page 7; independent extraction returns zero native text characters. Its frozen oracle covers all ten ordered blocks: title, before paragraph, five screenshot items, caption, after paragraph and the final mixed sentence. The final sentence must retain Traditional Chinese and English together, including the ready-after condition. Page-7 native extraction is not evidence of page-8 OCR success.

## Evaluation contract

Keep learned model input separate from source ground truth: the candidate receives original rendered pages and model preprocessing, never frozen expected angles or transcripts. Report model class, score and corrective-angle interpretation separately from OCR fidelity. A confident wrong angle is still wrong. PDF metadata does not count as learned correction evidence.

For C08–C11, evaluate all 16 expected line/semantic units and both paragraph sequences, retaining raw producer indices. Report strict transcript differences and explicitly allowed source normalizations separately; do not erase quote width, punctuation or Chinese glyph changes silently. Line wrapping and source-authorized `re-`/`sources` joining can be explained without inventing a character-error threshold. Identify matched selected lines without sorting them into oracle order. Correct selected relative order does not establish coherent full-page or paragraph output if unrelated right-column lines interrupt the producer stream.

Independently check source page, declared coordinate basis, corrective transform, normalized dimensions and inverse mapping for OCR geometry. Check that transformed source-region envelopes agree with the frozen approximate source locations. Numerical transform consistency may be checked directly; no new IoU/CER acceptance threshold is introduced. Record whether image normalization is a reproducible processing step, an unofficial glue step or a full conversion pipeline feature.

For C12, inspect exact multiplicity and source/derived separation, native text preservation, main Markdown and image-reference linkage, source caption association and exact mixed native sentence. For C13, inspect all ten source blocks in raw output order, repeated distinct labels, screenshot recognition, caption and same-sentence mixed condition. Do not give native-layer credit to the raster-only page.

The reviewer will deliberately corrupt the corrective-angle sign, inverse coordinate mapping, physical page provenance, native-line multiplicity, output order, quotes and Traditional Chinese text to verify that the evaluator detects each failure. Existing baseline errors remain visible and are not reclassified as source ambiguity or silently repaired.

Limits: C08–C11 have a selected-region transcript oracle, not full-page accuracy evidence; C12/C13 are controlled derivatives, not additional real-world document quality evidence. No inference, package install, source oracle change or remote write was performed by this reviewer.
