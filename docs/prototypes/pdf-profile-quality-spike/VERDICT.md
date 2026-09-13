# S2 verdict: mixed default unsupported for faulty text; adoption remains inconclusive

The corrected synthetic matrix supports the pinned model's ability to recognize the declared English, Traditional Chinese and mixed strings. **It does not establish a production mixed default or satisfy #41's adoption gate.** The region-based mixed profile retains incorrect native text on the faulty-layer case; full-page OCR recovers that case. Reviewed quality minima and representative real documents are still missing.

## Fixed evidence and scope

- Starting code/evidence revision: `85925faa5b6167ee6e750fd02a0f3930d7ed8089`.
- Primary fixture: [manifest](artifacts-aspect/manifest.json), frozen before recognition, SHA-256 `c5c4b1fa2c442d498ff9787dcb60a57b9941259d6a0674e961391022f9bf3aec`.
- Seven original synthetic pages; no external document text. [Generator](spike.py) records source font hash, each PNG hash, PDF hash, expected lines and page-space image placement.
- Exact ordered-line checks ignore whitespace only; Traditional/Simplified character changes fail. These criteria were set before recognition but have **not been reviewed/accepted by the user**. They are provisional diagnostics, not post-hoc tuned thresholds.
- Direct uninterrupted Docling conversion only, no checkpoint adapter. This isolates recognition/profile behavior from option-3 assembly and restoration; those mechanisms are not requalified here.

## Target results

“Supported” below means only that the predeclared synthetic diagnostic passes, not general language support.

| Target | Native (OCR off) | Mixed (bitmap OCR, keep native text) | Scanned (force full-page OCR) | Original source PNG OCR | Target verdict |
|---|---|---|---|---|---|
| Native English + Traditional Chinese + mixed line | Pass | Pass | Pass | Pass, separate control | Supported on fixture |
| English raster-only | Expected omission | Pass | Pass | Pass | Supported on fixture |
| Traditional Chinese raster-only | Expected omission | Pass | Pass | Pass | Supported on fixture |
| Mixed-language raster-only | Expected omission | Pass | Pass | Pass | Supported on fixture |
| Small bitmap plus native surrounding text | Bitmap omitted | Pass | Pass | Pass | Supported at tested size |
| Incorrect hidden native layer over correct bitmap | Wrong text | **Fails** | Pass | Pass | Mixed strategy unsupported for this case; explicit full-page override supported |
| Mild degraded Traditional Chinese image | Expected omission | Pass | Pass | Pass | Supported only for declared synthetic degradation |

All three Docling conversions returned success, and all emitted text items had valid page-number provenance under the narrow check. Success is distinct from quality: mixed fails content expectations despite successful execution. Native omission is expected with OCR disabled, rather than an OCR engine returning no text. None of these fixtures exercises a blank image/no-detection result; no claim is made for that outcome.

[Native scores](artifacts-aspect/native-scores.json), [mixed scores](artifacts-aspect/mixed-scores.json), [scanned scores](artifacts-aspect/scanned-scores.json), [crop scores](artifacts-aspect/crop-scores.json), complete JSON/Markdown outputs and [run log](artifacts-aspect/run.log) are retained.

The faulty-layer mixed output contains `WRONG SOURCE TEXT` and `INCORRECT VERSION 0000`, and omits required `正確版本 2026`. Full-page OCR produces both required correct lines and removes the false native content on this fixture. Thus the smallest demonstrated adjustment is an explicit full-page OCR override for known unreliable native text layers. Automatically detecting those layers and safely choosing/combining results is **not demonstrated**.

## Exact candidate identity

macOS 26.4 ARM64, Python 3.12; Docling/docling-slim 2.102.0, RapidOCR 3.9.2, ONNX Runtime 1.24.3, PyTorch 2.14.0, pypdfium2 5.13.0. CPU with four configured Docling threads. [Environment](artifacts-aspect/environment.json) contains exact Python string, all packages, complete pipeline options and cache/model hashes.

All candidates use the baseline RapidOCR ONNX detector `PP-OCRv6_det_small`, recognizer `PP-OCRv6_rec_small`, and classifier `ch_ppocr_mobile_v2.0_cls_mobile`. No alternate-model search, model download, language-model substitution or Traditional/Simplified normalization was performed. Native differs by disabling OCR; mixed enables region OCR; scanned enables forced full-page OCR. Table structure and page/picture image generation remain enabled in all three, but table/formula semantics are not assessed by this corpus.

## Fixture correction and limits

The preliminary [manifest](artifacts/manifest.json) and outputs remain unchanged. Visual inspection found an unembedded CID font losing native glyphs and anisotropically stretched raster pages. Those preliminary failures are **excluded from language-quality conclusions**. The primary fixture embeds a subset font and preserves image aspect ratio; its [native render](artifacts-aspect/native-preview.png) was inspected before recognition. The older montage in the primary directory was rendered before the font correction and is removed from the evidence package to avoid confusing the two source versions.

The corrected raster region is about 24% of the page, while the small bitmap is about 6%; this does not probe bitmap coverage below Docling's threshold or establish whole-page dense scan behavior. The degradation is fixed 1.5-degree rotation, 0.65-pixel Gaussian blur and deterministic salt-like light specks, not a claim of representative physical scanning. Sparse system-font fixtures are easier than dense 50-page papers, unusual fonts, skewed cameras, low DPI or multi-column layouts. Original-PNG recognition does not validate production crop selection or page-render coordinate handling.

No repeated-run statistical accuracy/performance claim, K8s equivalence, full-document throughput, warm lifecycle or production profile integration is made. Timings in output are execution metadata only.

## Gate and next decision

Overall adoption: **inconclusive**. Keep #35 open and #41 blocked until reviewed minima and representative source cases are provided and the unreliable-text-layer policy is resolved. The bounded executable investigation is complete, but missing agreement is not converted into successful acceptance.

1. Review the expected-content criteria and provide/approve a small representative Traditional Chinese/mixed source set (including a real degraded scan and unreliable native text layer).
2. Retain current pinned models as a candidate; this evidence does not require a model replacement.
3. Decide whether v1 permits an explicit force-OCR profile selection for known faulty layers. Automatic detection remains an unresolved method question, not a proven feature.
4. Recheck only these gaps against the fixed diagnostic fixtures and approved representative cases before freezing T06 profiles. Do not silently narrow the required language/content scope.
