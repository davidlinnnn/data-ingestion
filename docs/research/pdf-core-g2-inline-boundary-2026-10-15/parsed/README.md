# Offline segment parsing

All six new responses pass the unchanged prior strict JSON contract. The adapter imports the frozen prior validator and renderer; it preserves model strings, block order, uncertainty strings, null/unknown evidence, and code indentation. It performs no transcription or LaTeX repair and makes no Docling Core/provider-output claim.

Each input directory contains `original-blocks.json`, `document.md`, and `render-map.json`. The map records the exact raw API output hash, input metadata, model image bounds, and block/segment Markdown offsets. Bounds remain model predictions within the supplied image; they are not source glyph coordinates. Source fragment transforms remain in the frozen producer metadata. A contract failure would be saved separately and would not stop parsing other responses.

`selfcheck.json` covers null roots, invalid bounds/types/fields/nonfinite numbers, math delimiters/fences, preserved unknown/null evidence, literal backticks, indentation, and segment offsets. The original parser and prior evidence are unchanged. Semantic quality is independently reviewed.
