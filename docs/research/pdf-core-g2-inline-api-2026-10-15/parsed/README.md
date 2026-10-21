# Offline API block validation and rendering

All 22 saved API outputs passed the explicit JSON contract and rendered to
Markdown: 17 paragraph/item images and five complete-page images. Original
model blocks and uncertainties remain unchanged in `original-blocks.json`;
`render-map.json` records raw-output/input hashes, predicted image-pixel block
boxes and exact block/segment offsets into `document.md`. Failures would be
saved per input as `failure.json` while other inputs continue.

`parse.py` checks exact fields, finite in-image nonempty block boxes, declared
block/segment types, nullable segment text, fence-safe language labels and
compatible standalone code/formula segments. Math text remains verbatim
inside added Markdown delimiters; code indentation, operators and literal
backticks remain intact using a sufficiently long fence. Text receives Markdown
escaping for display. No formula, wording, paragraph boundary or source crop is
repaired. Explicit unknown/null spans render as `[unknown source span]` and make
the paragraph ineligible for automatic association; raw values are retained.

The schema is an external structured-segment component contract. These parsed
artifacts are not Docling Core objects or official VlmPipeline results. The five
page outputs remain direct API component comparisons against the exact old CPU
engine input images. Model block boxes and segment associations are inferred;
they are not measured source glyph boxes. Paragraph source-fragment transforms
remain the frozen input references, including the SEAL p3-to-p4 provenance join.

```sh
rtk python3 -B docs/research/pdf-core-g2-inline-api-2026-10-15/parsed/parse.py --selfcheck
```

The saved self-check covers invalid JSON root/null, out-of-bounds/nonfinite
boxes, segment types, extra fields, math delimiters, unknown/null preservation,
code indentation/literal fences and segment offsets. Schema success does not
establish complete transcription or semantic correctness.
