# Single official PP-OCRv5 server OCR pair — 2026-10-20

User authorized one fixed model configuration, seven exposed regression pages; only if all seven meet the existing acceptance boundary may the six already frozen additional pages run. Maximum13 new page attempts, zero automatic retries, no new variants.

Configuration: pinned Docling2.132.0 StandardPdfPipeline, PyPdfium, Heron, native default OCR-region selection/dilation, native assembly/ReadingOrder; RapidOCR3.9.2 ONNXRuntime CPU4. Replace only det/rec model paths plus matching PP-OCRv5/server metadata. Keep mobile-v2 line classifier enabled and all other options fixed. This follows Docling's public explicit-model options and RapidAI's version/type selection; it is not Paddle's complete pipeline, and no claim that this pair is a registered Docling preset.

Official references:
- https://docling-project.github.io/docling/_generated/examples/rapidocr_with_custom_models/
- https://rapidai.github.io/RapidOCRDocs/v3.9.2/install_usage/rapidocr/how_to_use_ppocrv5/

Artifacts use the installed RapidAI3.9.2 registry URL and SHA256. Filenames are adapted to that registry, not blindly copied from the live example. No SDK change, custom OCR regions, text correction, de-duplication or sorting. Keep RapidOCR published default normalization/threshold/resize settings; no model-specific parameter search.

Reuse cached R0, FULL_PAGE and C10 results. C10 is a positive control for specific reading-order cases, not full-content ground truth. Freeze input, model, implementation and evaluator hashes before candidate inference. Record actual engine config, provider, model hashes and embedded recognizer dictionary after initialization. Runtime session initialization performs no page inference.

Read final body/group refs, not texts storage order. Source review overrides diagnostic flags: legitimate ACL-p1 cross-column continuation is allowed; missing NCCU enumeration is not missing headings; minor ordinary glyph/format errors allowed; unrelated column mixing, missing substantial content, repeated paragraph material, altered critical numbers/identifiers/conditions are failures. No semantic pass inferred from zero flags. Formula enrichment is off: this round judges this fixed OCR method, not all future enhancement capabilities.

Budget:900s/profile,180s/init or page,12GiB sampled process-tree RSS,10GiB prelaunch available/8GiB available floor. Timing includes debug/files, excludes init; cached controls are not paired SLO measurements. No GPU/API/VLM.

Stop: any source-confirmed major defect rejects the fixed candidate; still inspect seven outputs to characterize tradeoffs, then leave six additional pages unrun. A qualifying seven-page candidate must pass source review before those six are authorized by a recorded gate. Failure does not automatically open another model round.
