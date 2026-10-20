# Standard pipeline after classifier normalization

All four derived-input Standard CPU probes completed, with the original G1
registry/source and all 92 frozen baseline files unchanged. This extends the
orientation unit evidence through layout, OCR, assembly and stock Markdown
export; semantic/order verdicts belong to the independent review.

| Original SRC05 page | Classifier-predicted correction CCW | Child elapsed seconds | Sampled tree peak GiB |
| --- | ---: | ---: | ---: |
| 3 | 0 | 6.572 | 3.053 |
| 4 | 270 | 6.049 | 3.364 |
| 5 | 180 | 6.308 | 3.339 |
| 6 | 90 | 6.050 | 3.226 |

`run.py` imports the unchanged frozen `../baseline/run.py`, reusing its stock
Docling worker, observation hooks and bounded supervisor. Module globals point
to this lane's explicitly derived input manifest and four jobs. Same cached
model hashes, CPU four threads, batch one, effective classification enabled,
actual ONNX CPU sessions, shared lock, 180-second child timeout, sampled 6 GiB
RSS stop and pre-launch 8 GiB available-memory requirement apply. No model was
downloaded and no guard fired. Requested `lang=["en"]` still uses the explicitly
pinned Chinese PP-OCRv6 recognizer and embedded dictionary documented in the
baseline language note.

`inputs/derived-normalized-controls.pdf` has its own SHA-256
`1469914e8a987931e25792576e1fdbd2ac7615e3e5a9721495cc86b2d6656db3`.
It is a six-page diagnostic intermediate with blank pages 1-2 and the saved
classifier-normalized PNGs placed full-bleed on pages 3-6 at 612x792 points,
without a text layer. `SRC05` inside the **local derived manifest** is solely a
compatibility lookup alias for the unchanged worker; its actual identity is
`DERIVED-NORMALIZED-CONTROLS`. Its filename, path and SHA are derivative values,
and it must never be represented as original G1 source bytes. The frozen G1
registry was not edited. `input-manifest.json` records the original source,
classifier prediction/output hash, normalized-image hash and source transforms
for each page. No expected angle, oracle region or oracle text was supplied to
the derivation or pipeline.

The input/render chain differs from the original baseline: original PDF ->
orientation agent's direct PDFium 3x RGB page raster -> classifier-selected
lossless quarter-turn -> ReportLab image placement in a derived PDF -> stock
Docling PDFium 4.5x rendering -> resize to 3x OCR image -> stock RapidOCR
preprocessing. The original baseline rendered its original PDF directly at
4.5x then resized to 3x. These are explicit **method and input transformation
comparisons**, with an additional raster/render boundary and resampling
confound. An OCR or order improvement cannot be attributed causally to rotation
correction alone. The existing four-angle classifier evidence remains separate.

The derivative PDF was checked with `pdfinfo` and all four content pages were
rendered with Poppler at 72 dpi and visually inspected; each is upright and
contains the complete page without clipping. Those PNGs are saved in `inputs/`.
This visual check validates the intermediate, not the Standard reading order.

Every `runs/normalized-pN-full/` preserves its raw derivative
`conversion-result.json`, `document.json`, `document.md`, model/options/timing
records, OCR input PNG, unfiltered/filtered OCR arrays and cell fusion. Raw
documents retain the derivative origin, page dimensions, images and coordinates.
The separate `mapped-review.json` is a review wrapper, not a provider document.
It records original source identity/page/size, classifier angle, the point-space
matrix from normalized PDF top-left coordinates to original PDF top-left
coordinates, and transformed quadrilaterals plus envelopes for every final
item's provenance. It also retains original item references and body order.
The matrix composes the orientation agent's normalized-raster-to-original-PDF
matrix with three pixels per normalized PDF point. Render rounding, resampling
and provider bounding-box uncertainty remain; no new pixel-IoU tolerance exists.

`map_review.py` validates all four successful jobs, CPU/options constraints,
provider-schema equivalence between raw and exported derivative documents,
derivative SHA/page identity, page-corner transforms and unchanged frozen
inputs/baseline payloads, then writes mapped wrappers and `verification.json`.

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-orientation-2026-10-15/normalized/map_review.py
```

No production adapter, unseen holdout, broad language qualification or isolated
causal orientation experiment is claimed.
