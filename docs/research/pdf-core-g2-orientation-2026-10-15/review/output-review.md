# Independent orientation and mixed OCR output review

The learned orientation model correctly chooses corrective CCW angles `0, 270, 180, 90` for frozen C08–C11, and all four normalized pages yield the 16 selected source lines exactly. Source page numbers and inverse geometry are preserved in the saved review mappings. Reading order remains incomplete: raw OCR alternates selected left-column lines with unrelated right-column lines, and Standard integration still places an unrelated paragraph between the two selected source paragraphs.

Mixed OCR remains unqualified. C12 selective OCR preserves native content and attaches recognized image text to the picture, but recognizes only 3/5 selected screenshot units and supplies no usable image reference in main Markdown. C13 recognizes 7/10 complete-page units, with missing instruction text, a Simplified glyph substitution and an `OpenAI` identifier error.

The [source review](source-review.md), [source checks](source-check.json), [independent checker](check.py), [pixel/tensor checks](pixel-check.json) and [machine-readable results](output-review.json) provide exact artifacts and observations. No frozen oracle, candidate payload or old heading artifact was edited. Scores use exact source units after neutral whitespace only; closest-line matches are diagnostics and grant no credit.

## Orientation, transcript and reading order

| Frozen case / physical page | Correct model correction | Baseline exact selected lines | Model-normalized exact selected lines | Selected producer indices after normalization |
| --- | ---: | ---: | ---: | --- |
| C08 / 3 | 0° | 16/16 | 16/16 | 1, 3, …, 31 |
| C09 / 4 | 270° | 14/16 | 16/16 | 1, 3, …, 31 |
| C10 / 5 | 180° | 12/16 | 16/16 | 1, 3, …, 31 |
| C11 / 6 | 90° | 16/16 | 16/16 | 1, 3, …, 31 |

The [orientation method](../orientation/method.json) uses the pinned official PP-LCNet ONNX model with its declared preprocessing and direct four-class argmax. The saved raw tensors, class labels and corrective rotations agree. All orientation and RapidOCR sessions report CPU providers. Model output maxima are approximately 0.923–0.927; no new score threshold was used. The stock baseline's line classifier has only 0/180 labels and is not evidence of learned whole-page orientation correction.

All four learned runs have the selected source units in relative order **without sorting them**: their actual producer indices are 1, 3, …, 31. Every intervening even index is right-column content. Neither selected paragraph occurs contiguously in the raw stream. The rotated baselines also have order errors even where individual line strings survive; page 6 has all 16 strings but producer order is reversed/nonmonotonic. Text presence alone therefore does not pass the frozen reading-order requirement.

The additional [Standard integration](../normalized/input-manifest.json) runs convert a clearly identified derived raster PDF containing the classifier-normalized images. All four have 16/16 selected lines and both selected paragraphs individually intact, in their expected relative order. Their final document/Markdown places the unrelated right-column `In-context learning` paragraph between those selected paragraphs. The unchanged upright baseline already has this same gap. The integration demonstrates compatibility and text recovery for this controlled transformed source, while preserving the remaining reading-order failure.

The baseline and orientation inputs share 216-dpi dimensions but differ in pixel bytes: stock Docling renders through its backend's higher-resolution/downsampling path, while the orientation method directly renders with PDFium. The integration adds another raster-PDF/render boundary. These results compare methods plus input transformations; they do not isolate rotation as the sole cause of recognition differences. All four normalized image arrays are themselves identical, so the four rotations are controlled derivatives of one page rather than four independent real-world documents.

## Geometry and evidence identity

The [candidate mappings](../orientation/runs/p4/source-mapping.json) explicitly use top-left continuous raster edges `[0,W] × [0,H]`, with sample centers at `(column + .5, row + .5)`. An independent PIL transpose reproduces every normalized image exactly. Pixel-center lookups using the saved inverse matrices agree with the original source pixels. Independent forward/inverse corner checks and all 936 raw/filtered OCR polygon mappings pass arithmetic consistency checks. No width-minus-one pixel-index transform is substituted for the declared edge convention.

The observed selected source envelopes in PDF points are:

| Physical page | Independently checked envelope |
| --- | --- |
| 3 | `[46.219, 43.512, 302.414, 228.339]` |
| 4 | `[43.512, 309.586, 228.339, 565.781]` |
| 5 | `[309.586, 563.661, 565.781, 748.488]` |
| 6 | `[563.661, 46.219, 748.488, 302.414]` |

These lie in the corresponding frozen approximate selected source regions. The checker records exact values and uses no IoU/CER quality threshold. A small floating-point consistency tolerance is used only to compare equivalent transform arithmetic. Detector calibration and source envelope precision are not established at subpixel resolution.

The derived Standard PDF has SHA-256 `1469914e8a987931e25792576e1fdbd2ac7615e3e5a9721495cc86b2d6656db3`, distinct from original SRC05. Its manifest identifies the local `SRC05` worker key as a compatibility alias, records original source identity and classifier-only transformation inputs, and retains physical page labels 3–6 using blank derivative pages 1–2. Independent checks verify every wrapper item identity/content/parent/children/caption, root order, copied derivative provenance, original page number and inverse-mapped quadrilateral. The wrapper remains review evidence; raw derivative output provenance is not relabeled as original source evidence. This is not a production adapter or a full pipeline restart/recovery test.

Stock baseline raw pixel-to-PDF affine records follow Docling's divide-by-three plus crop-offset convention. Its backend performs intermediate render rounding and resampling, documented in the [coordinate note](../baseline/coordinate-note.md). The final provider PDF provenance is retained separately. Neither those records nor the derivative wrapper create stronger geometric precision claims.

## Mixed native/image C12 and raster-only C13

For C12 selective OCR, the native before paragraph, after paragraph, source caption and mixed sentence each appear exactly once in the final document and Markdown and remain native cells. The caption is attached to `#/pictures/0`. Four recognized screenshot rows are picture children; OCR cell observations remain available separately. Thus picture attribution and native duplicate suppression have useful bounded evidence.

Both C12 selective and forced-full-page runs match only 3/5 screenshot units exactly: 我的專區, 應用系統 and B5A:個人簡要自述. The breadcrumb ends in `應用系统`, substituting Simplified `统` for Traditional `統`. The instruction detector is present, but its raw recognizer text is empty after the line classifier selects 180°; it is subsequently absent from filtered provider output and the document. No source ambiguity or acceptance normalization is substituted for these misses.

Main Markdown contains the source caption and `<!-- image -->`, but no usable Markdown image reference and none of the screenshot OCR children. The JSON has an embedded image and child references; the consumer delivery binding requested by C12 is still absent from this Markdown export. A planned adapter cannot be credited as implemented delivery.

Forced full-page C12 OCR replaces the native cells with OCR cells. Before/after paragraphs and the caption remain once, but the final mixed sentence becomes `請確認 GPU worker 在 ready 狀態後，呼叫 OpenAl-compatible API。`. The lower-case `l` in `OpenAl` replaces the capital `I` in `OpenAI`; selective OCR preserves the exact native sentence. Native duplicate suppression therefore succeeds while native text preservation differs between these modes.

C13 has zero native cells before OCR and cannot receive native-layer extraction credit. Its raw provider stream matches 7/10 ordered blocks: title, before paragraph, two panel titles, B5A label, caption and after paragraph. The same breadcrumb glyph substitution, missing instruction and `OpenAl` error account for the three misses. The matched raw subset remains in source order, but the complete-page contract fails because blocks are missing/wrong. In document traversal, the caption precedes the screenshot's text children, adding a source-order error. Main Markdown exposes only 4/10 exact visible blocks after ignoring heading markup; the image placeholder does not expose screenshot text.

The [effective model note](../baseline/language-path-note.md) records that all these probes use the fixed Chinese PP-OCRv6 small recognizer and its embedded dictionary. A requested Docling `en` language setting is not proof that an English recognizer ran. These are diagnostic observations for the captured model set, not broad English/Traditional-Chinese quality qualification.

## Exact-input line-classifier diagnostics

Two additional [paired diagnostics](../line-cls/comparison.json) reuse the exact baseline input PNGs, array type/channels, models, dictionary and resolved configuration, changing only the call to `use_cls=False`. Independent comparison confirms identical detector boxes/scores and preprocessing. Line-classifier inference count is zero. Across all 15 raw lines, the only text changes are the two formerly blank instruction rows becoming nonblank; all other recognized strings stay the same.

For C12 selective input, the recovered instruction contains the correct Traditional Chinese words and `連結`, with curly quotes and different neutral spacing. Its strict score stays 3/5 because the literal oracle quotation/spacing is not silently rewritten. Under the explicitly reported quotation/whitespace allowance from base G1-O01, its instruction words are recovered; the breadcrumb `统` error still prevents complete screenshot fidelity. For C13, the recovered instruction reads `連结`, substituting Simplified `结` for Traditional `結`, and has curly quotes, so even that separate quotation diagnostic does not recover the source words. C13 strict complete-page units stay 7/10, and `OpenAl-compatible` remains unchanged.

This isolates the observed instruction disappearance to line classification for these exact inputs. It neither repairs the native/image delivery contract nor proves that disabling classification is correct for other line orientations. No new Standard document or Markdown output is claimed for these two calls.

## Checks, execution scope and verdict

The evaluator rejects deliberately swapped producer order, a duplicated native line, silently changed quote width, a Traditional-to-Simplified glyph change, a wrong corrective-angle sign, skipped inverse geometry and a wrong source page. Source, manifest and output hashes are checked independently; no oracle-derived angle, transcript or selected-region crop is fed to the candidate.

The four final learned-orientation jobs completed under the recorded 180-second/6-GiB guards in approximately 2.36–2.38 seconds each with sampled tree peaks 2.42–2.44 GB. They include orientation plus full-page RapidOCR. The four derived Standard integration jobs completed in approximately 6.05–6.57 seconds with sampled peaks 3.28–3.61 GB. These are bounded local method measurements, not whole-ingest throughput. The preserved earlier serialization failure is excluded from final semantic scoring and remains visible as an execution attempt.

Verdict: learned four-direction correction and bounded source-coordinate preservation succeed on the controlled rotations. Selected text presence improves in the transformed method, while raw and assembled reading order remain incomplete. C12 picture-bound OCR delivery and C13 complete mixed-language page fidelity remain unresolved. A broad orientation/OCR or full-pipeline qualification claim would exceed the evidence.

Skipped: new OCR models, CER/IoU thresholds, real scan/skew robustness, full-page English transcription certification and production adapter implementation. No inference, installs, oracle edits or remote writes were performed by this reviewer.
