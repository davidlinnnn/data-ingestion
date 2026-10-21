# G2 image comparison inputs

2026-10-14. Source preparation only; no classifier, VLM, chart extractor, provider call or candidate acceptance was run by this input-preparation task.

Six distinct source crops are available for the classifier and image-understanding comparison. `model-inputs.json` contains only IDs, image paths, hashes and dimensions. Use the same image bytes for each candidate. `input-manifest.json` adds pinned source identity, physical page, fixed bbox and pixel-to-PDF mapping. `oracle-references.json` is evaluation-only and points to the already frozen G1 oracles; keep it out of model prompts.

| Input | Source | Page | PNG pixels | SHA-256 |
|---|---|---:|---|---|
| G1-S05 | SRC01 | 4 | 1416 x 678 | `5069621b6ce14c3ed40d3292d6a2ed59d0b345f07b7833dbc1000ab6b20e95ba` |
| G1-S07 | SRC03 | 3 | 685 x 230 | `67daf56dc4b467605c202096cb16413818dd22063a85dc13a40d2401ce109f68` |
| G1-C03 | SRC05 | 2 | 684 x 666 | `e594303ccdf3d50e5c5c22c41c7336391eebccf65827e88a0939ae510d307cda` |
| G1-C04 | SRC05 | 2 | 693 x 744 | `f95f814872b223f7b083df124d29f69fa9b72d1416220868ecaf25a6f09d64b0` |
| G1-C05 | SRC05 | 2 | 714 x 717 | `dd821ef93dea301167fdc88aae25d7561b336302333c301bffec03abd4801a8f` |
| G1-C06 | SRC05 | 2 | 714 x 717 | `fccf6d430a928e07991af3d1de46dba2ec1455b4014fb763367a16f94a995fa5` |

## Source and coordinate provenance

- S05 comes from pinned WikiSkill `2608.27454v1` page 4, graphic bbox `[62, 83, 534, 309]` PDF points with top-left origin. The graphic-only PNG excludes the separate original caption; the source caption locator remains in the manifest. It was rendered at 3 pixels per PDF point (216 DPI equivalent), then cropped at integer pixel bounds.
- S07 is an exact byte copy of the frozen selected NCCU screenshot panel. Its original embedded Image35 pixels were cropped at `[240, 132, 925, 362]`, with no resize. The screenshot is stretched in the PDF placement; x/y mapping therefore uses separate point-per-pixel factors. The manifest records the embedding rectangle and both factors.
- C03-C06 use the four fixed page 2 boxes of the original synthetic controls PDF, rendered at scale 3. Page 2 contains original toy labels and numbers; none of the source-derived contents from pages 3-8 are included. The four crops preserve 13 numeric observations in total; they are controls rather than real-paper quality evidence.
- The fixed control bboxes start at panel-title baselines, so partial heading glyphs appear at the top edges. Axes, units, category/series labels and all plotted marks are complete. The G1 boxes and source bytes were kept unchanged.

## Public source verification

The unauthenticated public GETs in `source-safety.json` returned HTTP 200 and exactly matched the pinned local PDFs:

- [WikiSkill fixed-version PDF](https://arxiv.org/pdf/2608.27454v1): 1,177,706 bytes, SHA-256 `65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69`.
- [NCCU manual](https://posman.nccu.edu.tw/files/archive/424_1f69c9f2.pdf): 996,382 bytes, SHA-256 `3a8d8a946a5962cc1b666ec6a33dc5482556da7013a70ca096fc8d86439a5f6e`.

Initial sandbox DNS attempts failed; one approved read-only network retry completed both checks. Download bytes were hashed in memory and were not written over the fixtures. No credential file or environment secret was read. Selected S07 contains public generic UI instructions rather than a populated personal statement. This evidence concerns public source identity, and does not supply separate authorization for any model/API operation.

## Evaluation boundary

V09 requires the source-specific components, relations, direction, conditions and trends. Expected semantics remain solely in the frozen references. Classifier family output cannot replace generated image meaning or chart data. S05 includes required directed workflow/layer checks; S07 includes the screenshot navigation and link/instruction checks. C03-C06 retain exact printed-value rules and existing unprinted-value estimates/tolerances. The G1-N11 reference preserves the no-text/unknown-classification routing negative, but is not a seventh inference image.

Source references: `docs/fixtures/pdf-core-g1-2026-10-14/cases.json`; `docs/research/docling-pdf-core-g1-source-cases-2026-10-14.md`; `docs/research/docling-pdf-core-capability-validation-plan-2026-10-14.md` (V09/V10); `docs/fixtures/pdf-core-g1-controls-2026-10-14/generate.py`.

`validation.json` records file integrity, dimensions, distinct hashes, source hashes, oracle pointers and mapping checks. No G1 or production file was edited. Broader photo/decoration coverage and model quality are outside this bounded preparation.
