# Coordinate interpretation

The frozen runner's `pixel_to_source_pdf_top_left` records **the stock Docling
OCR mapping**: output crop pixels divided by 3, then the requested OCR
rectangle's left/top offsets. It is not a claim that every rendered pixel has
an exact unrounded affine relation to the PDF. Final `ConversionResult`/
`DoclingDocument` provenance is the authoritative provider PDF-coordinate
record. No pixel-IoU tolerance was introduced.

The selected `PdfFormatOption` uses `DoclingParseDocumentBackend` (installed
`document_converter.py`, line 179). Its
`get_page_image` (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/backend/docling_parse_backend.py`)
(lines 190–224) renders with PDFium at `scale * 1.5` (4.5 for OCR), supplies
the requested crop margins, then resizes to
`round(cropbox.width * scale)` by `round(cropbox.height * scale)`.
The installed
`pypdfium2` rendering implementation (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/pypdfium2/_helpers/page.py`)
(lines 459–478) uses `ceil(page_dimension * scale)` and
`ceil(crop_margin * scale)` before rendering. This creates rounding and
resampling uncertainty relative to the runner's idealized mapping, especially
for fractional PDF page sizes/crop edges. Raw input PNG dimensions and requested
OCR rectangles are saved for every call. C12 selective OCR requests integer
rectangle `[32, 164, 551, 351]` points and returns 1557×561 pixels; the full mixed
pages request approximately 595.276×841.890 points and return 1786×2526 pixels.

Text/cell bounds are provider observations. They do not prove source attribution
by themselves. `cell-merge.json` preserves native-before, OCR-before and
merged-after cells; `document.json` separately retains picture children,
caption references and PDF provenance. Main Markdown is the unchanged stock
export, including its `<!-- image -->` marker rather than an invented image
reference. The independent evaluator must assess image OCR access/binding and
duplicate counts separately.
