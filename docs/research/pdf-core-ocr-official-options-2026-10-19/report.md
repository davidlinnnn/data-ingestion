# Official OCR option comparison — 2026-10-19

Decision: retain **StandardPdfPipeline + Heron + RapidOCR with FULL_PAGE as a scanned-page candidate**, without accepting it as a globally qualified profile. No production code or SDK modifications. The fixed comparison is finished; no automatic parameter search follows.

## Direct answer

Docling2.132.0 has no public maximum-merge-size or keep-column OCR-region switch. Native geometry replay turns the actual22 Heron boxes into one OCR input rectangle at internal dilation_size20. LAYOUT_REGIONS still performs that merge. Disabling RapidOCR Det.use_dilation changes a different detector mask operation, not Docling region merging. Disabling use_det sends the whole paragraph/page region as one recognition crop; it is unsuitable for multiline OCR. Raw Heron-region OCR is possible through custom integration, but is our engineering, not this public option. Previous separated-crop diagnosis fixed mixing but lost a heading, so is not adopted.

## Fixed execution

All14 registered configurations ×7 pages =98 successful StandardPdfPipeline conversions, zero automatic inference retries and zero API calls. Exact versions/models/options/hashes: [registration](registration.json). Four CPU threads, PyPdfium backend, Heron layout, TableFormer accurate/cell matching on, code/formula/image enrichment off. RapidOCR3.9.2 ONNX uses PP-OCRv6 small detector and recognizer plus mobile-v2 direction classifier on. TesseractCLI5.5.3 uses eng+chi_tra with complete frozen tessdata/TSV config. EasyOCR1.7.2 uses CRAFT craft_mlt_25k.pth and chinese.pth (zh_tra_g1), standard recognizer, en+ch_tra, CPU, confidence .5. EasyOCR dependencies isolated; retained runtime untouched. All98 results include ReadingOrder timing; this stage was not bypassed.

The same seven raster pages comprise the exposed known failure and six frozen regression pages from four public documents, including two-column English, inline math, single-column English and Traditional Chinese SOPs. References and acceptance unchanged. This is exposed development/regression evidence, not an unseen benchmark.

## Results

Counts below are source-text diagnostic flags on the known page (raw cells / final document). Zero is not a semantic pass; engine cell granularity differs. All profiles have a source-confirmed counterexample in [manual review](manual-review.json), with native document refs and hashes.

| Profile | Known mix flags raw / document | Seven-page conversion seconds | Peak sampled tree GiB | Finding |
|---|---:|---:|---:|---|
| LAYOUT_REGIONS | 3 / 2 | 18.67 | 4.41 | All7 cells/documents exactly equal retained R0 |
| PDF_AWARE_LAYOUT_REGIONS | 3 / 2 | 19.01 | 4.52 | All7 cells/documents exactly equal retained R0 |
| FULL_PAGE | 0 / 0 | 16.58 | 3.26 | Known mix gone; Background restored; existing ※ linkage loss remains |
| scale=2 | 0 / 0 | 18.34 | 4.54 | Known mix gone; Background corrupt; inline x2 lost |
| Det.use_dilation=false | 2 / 1 | 19.86 | 4.89 | One final mixed paragraph remains |
| Det.limit_type=max | 3 / 2 | 16.99 | 3.42 | Mixed sentences remain; version-specific adaptive resolution |
| Det.thresh=.5 | 2 / 1 | 19.51 | 4.32 | One final mixed paragraph remains |
| Det.box_thresh=.6 | 3 / 2 | 19.27 | 4.95 | Mixed sentences remain |
| Det.score_mode=slow | 3 / 2 | 19.45 | 4.75 | Mixed sentences remain |
| Det.unclip_ratio=2 | 3 / 2 | 18.25 | 4.80 | Mixed sentences remain |
| Tesseract PSM1 | 0 / 0 | 19.51 | 1.67 | Columns improve; inline math identifiers corrupted |
| Tesseract PSM11 | 0 / 0 | 18.31 | 1.64 | Columns improve; ※ note improves; inline math identifiers corrupted |
| Tesseract PSM12 | 0 / 0 | 19.45 | 1.64 | Columns improve; inline math identifiers corrupted |
| EasyOCR CRAFT / zh_tra_g1 | 0 / 1 | 150.64 | 9.99 | Raw mix flags0; final document still mixes columns; slower CPU |

Retained R0 took18.54s for the same seven pages; FULL_PAGE16.58s and EasyOCR150.64s in this run. These single-run conversion totals include debug/artifact overhead, exclude pipeline initialization, and are not throughput/p95/SLO evidence. Do not interpret the small RapidOCR differences as a speed ranking. Initialization and full guarded worker times remain in each profile directory.

FULL_PAGE fixes the known page without changing weights or disabling the direction classifier. It changes image extent/context and detector preprocessing; it does **not** enforce columns or prove why every individual box improved. Seven-page regression still loses the source ※ symbols both on login-only functions and in their explanatory note (ndhu-p9). This pre-existing defect breaks the relationship, rather than merely changing punctuation. Source image visually checked. Other included inline formula equalities also have OCR differences; no full-profile pass is claimed.

EasyOCR has no mixed raw-line diagnostic flag on the known page, but final paragraph #/texts/6 combines left Emergent Abilities with right Instruction following / chain-of-thought and other paragraphs. This is a final layout/assembly defect, not evidence that its detector made one wide line. It is not a successful end-to-end replacement.

## Coverage and limits

All8 public OCR option classes and their fields are enumerated in [inventory](public-field-inventory.json); detailed dispositions and the predeclared14 profiles are in [plan](plan.md). This is coverage of relevant public option families, not every positive real threshold/scale, combination, arbitrary model path or supported deployment. DEFAULT and cls-off/PSM3 are retained prior measurements; the three other region modes ran here. Deprecated force_full_page_ocr is a FULL_PAGE alias. No undocumented dilation override, lexical fix, padding rule or custom plugin was tested here.

Unclip2 tests the other documented endpoint, which increases expansion. RapidOCR3.9.2 max mode ignores the requested limit_side_len and selects adaptive960/1500/2000; official docs describe a3.10 fix. max_candidates was not varied and pre-threshold contour counts were not captured: the plan’s “not approached” statement is only a screening assumption, not measured proof. Confidence/text_score filters were not searched because they cannot separate an existing mixed line. Alternative weights/backend libraries remain untested here.

Auto selects an available engine and is not a distinct OCR model; engines/models were pinned for reproducibility. Tesserocr Python adapter and macOS-only OCRMac are not installed/tested, and CLI equivalence to the Python adapter is not claimed. Nemotron native runtime validation actually rejects this Mac (Linux required; CUDA resource requirements remain). No KServe service supplied. Tesseract modes assuming a single block/line/word or not producing OCR were screened as inapplicable to these multi-column inputs, not falsely marked measured. See [availability](availability.json).

## Recommendation and stop

For this scanned double-column failure, prefer evaluating the official FULL_PAGE setting before custom column-preserving OCR engineering. Preserve the existing RapidOCR weights and other options and change only `options.ocr_options.mode = OcrMode.FULL_PAGE`. Keep it scoped to raster/scanned documents: FULL_PAGE discards native PDF text in favor of OCR, so these all-raster results do not justify applying it to all born-digital PDFs.

No global replacement approved: unresolved semantic content and downstream ordering remain separate gates. This fixed experiment is closed, rather than automatically adding combinations such as FULL_PAGE+cls-off or more threshold points. A broader source-independent holdout and a deviation decision are needed before production acceptance; this round does not validate natural/noisy scans, page rotations, table/formula/code enrichment, GPU, or ingestion throughput.

## Verification

Nine retained evaluator/runner unit tests passed. [Native checks](native-option-checks.json) verify22→1 geometry, no public region-merge control, no-det single-crop behavior and unchanged non-OCR options without inference. All332 previously sealed artifacts unchanged. Frozen new registration and source/runtime/weight fingerprints verify after inference. [Diagnostics](diagnostics.json), [manual decisions](manual-review.json), and final artifact seal retain all98 outputs.

Official references: [pinned region merge implementation](https://raw.githubusercontent.com/docling-project/docling/v2.132.0/docling/models/base_ocr_model.py), [pinned public options](https://raw.githubusercontent.com/docling-project/docling/v2.132.0/docling/datamodel/pipeline_options.py), [RapidOCR parameter docs](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/parameters/).

Post-run QA correction (zero inference): an initial credential-prefix scan matched its own source literal. The checker now detects full token-shaped strings, with positive/negative assertions. No model attempt, frozen option, reference or result changed.
