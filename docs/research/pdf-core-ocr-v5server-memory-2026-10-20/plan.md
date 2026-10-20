# Resource-only continuation of the single PP-OCRv5 server comparison

User explicitly authorized raising the memory fence. Same candidate options, models, seven inputs, scoring and acceptance boundary as the sealed initial attempt. CPU4, StandardPdfPipeline, PyPdfium, Heron, official DEFAULT OCR regions, PP-OCRv5 server det/rec and unchanged v2 classifier. No new models, SDK changes or content repairs.

Change ONLY parent resource budget: sampled process-tree RSS limit12→16GiB, host available floor8→4GiB; prelaunch10GiB,180s/init/page and900s/profile unchanged. One user-authorized rerun; zero automatic retries. At most7 new regression attempts; only source-reviewed qualifying results allow6 previously frozen additional pages. Maximum13 new attempts in this round,14 cumulative including the initial interrupted page. Any confirmed major defect closes this candidate round without extra pages or variants.

Reuse cached R0/FULL_PAGE/C10; C10 is positive control for specific reading order, not source ground truth. Minor ordinary glyph/format errors allowed; substantial omissions, unrelated column mixing, repeated paragraph material and changed critical numbers/identifiers/conditions fail. Final reading order follows body/group refs. Preserve legitimate ACL-p1 continuation and distinguish NCCU enumeration glyphs from missing headings. No score-only acceptance.

Public configuration references:
- https://docling-project.github.io/docling/_generated/examples/rapidocr_with_custom_models/
- https://rapidai.github.io/RapidOCRDocs/v3.9.2/install_usage/rapidocr/how_to_use_ppocrv5/

Retain earlier sealed failure and its diagnostics. Freeze this amendment before the new page attempt. No API, VLM or GPU. Record actual provider/weights/dictionary, source-review all seven results, render final native output for inspection if conversions complete, and verify historical seals. No formal SLO or general-accuracy claim from these exposed clean raster pages.
