# PaddleOCR-VL output-join preflight, zero inference

2026-10-20. User authorizes checking coordinates, images, multipage and primary Markdown delivery before model inference. This is an output-contract test, not a model quality or latency experiment. Do not load/download weights, install Paddle inference engines, call predict or API models. A separate /private/tmp client-only venv installs pinned PaddleX3.7.2 OCR result/export dependencies from PyPI; preserve resolver report and lock, do not change retained Docling runtimes. Network is denied in behavioral workers.

Reuse frozen Docling2.132.0/Core2.99.0 importer (unchanged from2.140) and official PaddleX3.7.2 complete Result/export/postprocessing code. No SDK patch, AST extraction, dependency stubs, text repair, layout-specific crop rules or semantic custom joins. Public postprocess is invoked as its unbound method because constructing the inference pipeline would initialize models; record this scope precisely.

Register before behavioral execution. Synthetic legal perfect provider responses exercise:
1. Complete PaddleOCRVLResult native JSON and save_to_markdown(pretty=False,show_formula_number=True), code/math/table/captions and actual crop bytes on disk.
2. Pixel coordinate canvas, nonzero physical pages3/4, different page sizes; only an explicit orientation/unwarp-disabled renderer mapping may claim original PDF points. Unknown transform cannot imply original geometry.
3. Same image label+bbox across pages, raw shared-directory collision, page-qualified derived export and same-revision image-key/asset map.
4. Real directory move/reload plus missing/wrong-revision asset rejection. Asset hashes prove integrity, not component identity. Raw result serialized before mutable restructuring.
5. Native live vs saved-dict restructure; global/group/content mutation, image-byte retention and concatenated payload importer rejection. Do not equate appended pages with semantic paragraph joins.
6. Cross-page table merge with repeated headers and paragraph continuation controls; source page fragments retained separately; no new merge algorithm.
7. Native Markdown primary meaning: plain/fenced algorithm literals and required indentation, prose inline math vs separate inline fragments, bare/delimited math+equation numbers, HTML table spans, source captions vs image OCR/chart supplements. No failure solely for absent backticks or typed inline labels.
8. Docling single-page import/JSON roundtrip/public concatenate, saved Markdown render and source-preserving supplementary fields. No fabricated cell/character bbox or caption association.

End with a per-gate verdict: supported natively, supported with deterministic packaging, unsupported/needs semantic engineering, or not tested. A required blocked gate prevents a full-method pass; do not proceed to model inference automatically. Preserve existing historical artifacts and a final hash manifest. Do not claim synthetic controls validate recognition, source order prediction, real cross-page semantics, GPU or ingest throughput.
