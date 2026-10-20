# Fixed raster OCR region-policy experiment

2026-10-20 Asia/Taipei. Two new profiles C0/C10, seven unchanged exposed raster regression pages each, one attempt per job;14 maximum, no inference retries or post-result variants. Cached R0 and FULL_PAGE are controls, not rerun. Prior isolated crop B is a required known negative control, not a production implementation.

Use actual StandardPdfPipeline, Heron, RapidOCR v6small det/rec, mobilev2 direction classifier ON, CPU4, PyPdfium, TableFormer accurate. Preserve all other stages. Own OCR plugin discovered through a local dist-info entry point on the child PYTHONPATH, allow_external_plugins=True; installed SDK/global constants unchanged. The custom policy is our engineering through an official extension seam, not an official option.

C0: native dedup dilation0 to group only touching/overlapping layout masks; no extra crop context. C10: same groups, each independently expanded by DEFAULT_DILATION_SIZE/2 (10 page points), clipped to page; never re-merge after context expansion. This preserves baseline context magnitude while separating the connectivity decision. No column detection or gap threshold, no text fixes, no OCR cell dedup. Overlap may duplicate nearby text or admit adjacent-column content: count as failure, no automatic follow-up fix. C0 vsC10 is a fixed causal contrast, not a padding search.

Raster-only scope enforced: require no native PDF text cells. LAYOUT_REGIONS used because all task pages are images. Not a general mixed-PDF selector, production plugin package or automatic routing implementation.

Before inference: verify Pydantic options, real plugin discovery without loading models; geometry controls for separate boxes, overlapping boxes, boundary clipping and empty input; unchanged non-OCR options except explicit plugin enable flag. Preserve all source/runtime/model/evaluator hashes and retained controls.

Reuse frozen semantic acceptance/evaluator from previous regression: unrelated mixed sentences, missing heading/paragraph, identifier/math/meaning change, duplicates or new major regression reject global method; minor glyph differences tolerated. Source-anchored automatic flags only diagnostics; adjudicate against unchanged reference and visual source. A confirmed counterexample suffices to reject global qualification; otherwise all7 pages require source review. Capture each requested OCR rectangle and comparison to baseline, raw cells, native document/Markdown, all timing stages and guarded RSS.

Limits: per-profile900s, page180s, init180s, sampled tree12GiB, prelaunch available10GiB, available floor8GiB. Zero API/GPU/model downloads. One fixed round then close: adopt scoped candidate only with source coverage and no unacceptable regressions, otherwise reject policy; do not reopen kernel/padding/model search. Existing global content and reading-order gaps remain separate, never relabel as passed.
