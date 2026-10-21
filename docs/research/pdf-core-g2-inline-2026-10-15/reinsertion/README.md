# Inline paragraph association experiment

The prepared input set inventories every ordinary body-text paragraph intersecting
WikiSkill p21, DGM p51, SEAL pp3-4 and controls p1: 28 items. A fixed character
gate selects Unicode math symbols, Greek or mathematical alphanumeric characters,
or ASCII `_ = < > ^ { }`, giving 11 ordinary paragraphs. Six controls p1
formula/code-labelled items form separate regressions. All 17 candidates and
19 provenance fragments were prepared without oracle text, expected formulas,
gold crop boxes or title-specific fallback rules. The independent review assesses
the gate's source coverage; 17 selected candidates are not a precision/recall claim.

`../inputs/input-manifest.json` records all 28 ordinary candidates, gate decisions,
complete provider text, source/document hashes and exact item references. The four
baseline documents remain byte-identical snapshots of saved provider outputs;
WikiSkill, DGM and SEAL use their complete 28-, 64- and 22-page assembled native
documents, including prior continuation-v3 processing. Controls uses the saved
stock page-1 result. No new Standard inference was performed. Selection preserves
whole items and every provider provenance fragment, even across page boundaries.
The selected SEAL paragraph is one provider item with p3 and p4 fragments and a
single whitespace join; it was never independently truncated to p4.

Paragraph crops use direct PDFium RGB rendering at 3 pixels/point, 2-point padding,
and outward integer pixel crop edges. Multiple fragments are stitched in provider
charspan order, separated by 24 white pixels. Each fragment retains the physical
source page, provider box/charspan, page size, crop pixel box, stitched placement
and affine mapping from paragraph pixels to source top-left PDF points. Those
mappings describe rendered paragraph regions, not measured token/glyph positions.
The original input manifest and its 72 preparation payloads are frozen.

`apply.py` reuses Docling's Markdown text-serializer extension point to substitute
saved candidate Markdown at declared whole-item references. It does not mutate
the provider document or rewrite model formulas. `plan.json` records full source
document/item/text hashes, complete replacement spans, neighboring provider items
and hashes, source fragments and join gaps. Supplemental output records proposed
model structure, explicit math/code delimiter spans, main Markdown character
ranges, inferred source associations and neighbor checks. Original provider boxes
remain paragraph/page-fragment evidence; no inferred inline location is promoted
to source-measured precision.

Two decoder/parser methods remain explicit:

| Method | Structurally applied | Not applied | Interpretation |
| --- | ---: | ---: | --- |
| Stock component decode/parser | 0 | 17 | Raw decode drops final `>` from the closing DocTags wrapper; strict parsing rejects it. |
| Token-aware decoder/parser candidate | 9 | 8 | Terminal EOS/PAD IDs alone are removed; application establishes source association, not semantic correctness. |

The token-aware method rejects three SEAL candidates with multiple model root
blocks, including the target p3-to-p4 paragraph whose raw generation repeats its
p4 fragment. It rejects the controls comment's newly repeated five-word prose
runs and the controls inline-code candidate's multiple blocks. Three controls
formula children remain unapplied because stock Markdown hides them inside
pictures; this experiment does not rewrite the outer picture. Every rejected
candidate keeps its complete raw generation, parsed blocks and proposed Markdown
visible through the supplemental record. Nothing is silently selected, deduplicated
or repaired.

The duplicate guard compares English-word five-gram counts against the original
provider text, excluding explicit math markup and formula items. It catches newly
repeated substantial prose runs. It can conservatively abstain on legitimate
rephrasing and does not detect every short repetition, mathematical duplication,
word omission, semantic mistake or wrong code language. The controls nested code
applies structurally with the model's YAML label unchanged. WikiSkill's target
paragraph and the DGM inline-command paragraph apply as plain text with zero
explicit inline spans; their source typing requirements are not inferred from
characters alone. Semantic outcomes remain for independent review.

Fail-closed checks reject malformed/unsupported DocTags, unfinished generation,
incompatible or multiple root blocks, stale source/document/item hashes, unknown
or duplicate item proposals, incomplete replacement spans and neighbor changes.
Selected items must serialize exactly once, and all outside-scope serialization
uses the unchanged stock serializer. `selfcheck.json` records small positive and
negative checks for stale hash, duplicate item, unknown reference, dropped outside
content, partial scope, multiple roots, new prose repetition and malformed markup.
`verify.py` independently checks saved Markdown spans, source/model hashes,
neighbor invariants and whole-document output equivalence to the declared map.

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-inline-2026-10-15/reinsertion/apply.py --selfcheck
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-inline-2026-10-15/reinsertion/verify.py
```

The `attempts/` folder preserves an initial serializer-count validation failure
and the complete outputs preceding generic guard refinement. Current top-level
method folders are the final evidence. No production inline mapper, new model,
API path, source correction or broad unseen-document qualification was added.
