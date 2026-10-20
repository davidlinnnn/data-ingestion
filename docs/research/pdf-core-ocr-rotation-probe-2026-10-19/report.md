# S0 direction-rotation causal probe

2026-10-19. User narrowed the investigation to OCR regions, detector output and orientation. This is a new bounded component probe, separate from the sealed crop ablation. It does not reopen #84 A/B/C, change acceptance criteria or qualify a production profile.

## Finding

The native recognizer recovered the complete line when given its saved pre-classifier crop:

| S0 line index 39 | Native recognition | Score |
|---|---|---:|
| Saved post-classifier crop, rotated 180 degrees | `Bs  a    ler` | 0.61771 |
| Saved pre-classifier crop, upright | `Background. Typically, large language models (LLMs) refer` | 0.97489 |

The first call reproduced all 114 saved texts and scores (absolute score tolerance 1e-7). The second call used all 114 pre-classifier crops with unchanged shapes, order and actual reader configuration. Only index 39 had changed pixels; only index 39 had changed output text. The other 113 lines remain identical, including the existing cross-column content; this probe does not repair detector segmentation.

## Method and limits

- Two calls to the pinned `RapidOCR.recognize_txt` seam; 114 line crops each, native aspect-ratio sorting and batch 6 retained. This is not two full-page OCR runs or two neural forward passes.
- RapidOCR 3.9.2, ONNXRuntime CPU, exact saved `PP-OCRv6_rec_small.onnx` and reader configuration. No detector, classifier, Heron, table or VLM inference; no downloads, new weights, SDK patches or text repairs. Source hashes remained unchanged.
- The causal intervention is removal of the recorded rotation. It does not itself test a full `RapidOcrOptions(use_cls=False)` pipeline, rotated-page handling, throughput or an independent accuracy set. Whole-profile adoption remains unqualified.
- The actual S0 rotation model is `ch_ppocr_mobile_v2.0_cls_mobile.onnx`, a line-level 0/180 classifier. It predicted 180 with 0.9755069017, above `cls_thresh=0.9`. Why the network made that confident mistake is not isolated. Compressing the 684x30 strip into its 192x48 input is a hypothesis, not a demonstrated root cause.
- The 90-second alarm is a Python deadline, not hard isolation of a blocked native ONNX call. It was not reached.

## Preflight correction

The v1 configuration assertion stopped before either recognizer call: live config contained `Path` objects while retained JSON contained strings. The inspection process also initialized cached models but made no inference. V2 applies the retained capture helper's exact JSON normalization before comparing. No model options, inputs or hypothesis changed. Original script and registration are retained as `run-pre-path-normalization.py` and `registration.json`; actual two-call execution uses `run.py` and `registration-v2.json`. See `result.json` for outputs; there were no inference retries.

## Current decision

The false 180-degree rotation is a verified cause of this line's corruption. Do not raise the threshold to fit this example or deploy a global classifier-off change without genuinely inverted-input controls. OCR region merging/detection remains unresolved: the previous zero-dilation arm removed three mixed lines but lost an entire heading, so it is not accepted. Pinned `LAYOUT_REGIONS` also uses the same 20-unit dedup dilation and is not an automatic bypass. Reading order and other downstream work remain deferred under the user's narrowed scope.

The visualization's former `index:nan` labels were placeholders supplied by the gallery generator because detector scores were not retained. They were not detector failures. The gallery now shows saved detector geometry with index-only custom labels and retains the original native rendering as an explicitly explained alternative.
