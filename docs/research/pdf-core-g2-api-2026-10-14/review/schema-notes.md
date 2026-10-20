# Temporary API candidate: evaluation contract

This is an isolated GPT-6 Luna Chat Completions comparison on the same saved images as local CPU candidates. It does not establish company Qwen3 quality, self-hosted serving/GPU latency, full Docling integration, or Canonical Acceptance. No source values or source transcriptions belong in inference prompts.

Suggested response fields:

| Task | Minimal JSON |
|---|---|
| Direct screenshot OCR | `{"blocks":[{"text":"...","bbox":[0,0,1,1]}]}` in source reading order |
| Formula crop | `{"latex":"...","equation_label":null,"footnote_markers":[{"marker":"...","anchor_text":"..."}],"footnote_bodies":[{"marker":"...","text":"..."}],"uncertainties":[]}` |
| Complete English page | `{"blocks":[{"text":"...","bbox":[0,0,1,1],"kind":"..."}]}` in source reading order |
| Table2 and its visible caption/conditions | `{"caption":"...","conditions":[],"panels":[{"panel_label":"...","title":"...","columns":[],"rows":[{"setting":"...","values":[{"column":"...","value":"..."}]}]}]}` |

All bboxes refer to input-image pixels with top-left origin. Bounds and numerical values are illustrations of the JSON shape only. Numeric source values should be strings to retain their printed precision. Return visible content only; do not infer a footnote body outside the image. A formula's note marker and equation label must be separate observations. Each table panel carries its own title, setting, metric headers and data bindings.

Evaluation uses frozen G1 source/oracles without rewriting them. OCR allows whitespace and typographic quote-width normalization, not Simplified→Traditional conversion. English allows layout-line joining, the printed `re-`/`sources` split and range-dash normalization. Formula branch recovery, mathematical/syntactic fidelity, note marker preservation and unseen footnote-body delivery are assessed separately. Table evaluation fixes the denominator at84numeric datapoints, checks all source row/panel/metric bindings and all8critical comparisons, and keeps missing/extra output from enlarging the denominator. Caption/conditions remain an additional semantic check. JSON parseability and successful API execution are separate from extraction quality.
