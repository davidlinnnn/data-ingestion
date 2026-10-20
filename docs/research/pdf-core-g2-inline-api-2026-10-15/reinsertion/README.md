# API paragraph source association

The offline adapter structurally applies 11 of 17 paragraph/item outputs and
abstains on six. The SEAL p3-to-p4 target is associated with its complete original
provider item and both source fragments. Association status is separate from
independent transcription, formula and code quality review.

| Outcome | Items | Reason |
| --- | ---: | --- |
| Structurally applied; semantics unverified | 11 | One compatible complete block, validated source identity and unchanged outside scope. |
| Not applied | 1 | SEAL item 34 produces multiple blocks; all model blocks remain visible. |
| Not applied | 3 | Controls formula items are hidden picture children in stock Markdown; no outer-picture rewrite. |
| Not applied | 2 | Controls comment/inline-code model block roles differ from native code-item roles. |

`apply.py` imports the previously frozen adapter's `make_plan`, `check_shape`,
`validate_batch` and `render` functions without writing to the old experiment.
API `paragraph` roles map to a guard view of `text`; math is delimited only in
that duplicate-check view so the existing prose guard excludes it. Original API
blocks and segment text remain unchanged. The guard requires one compatible
root block, rejects newly repeated five-word prose runs relative to native text,
checks complete item references/charspans and document/item/text/neighbor hashes,
and ensures each applied item serializes exactly once. It does not prove semantic
equivalence, repair errors or detect every short repetition/omission.

Each source folder contains the complete stock `baseline.md`, `candidate.md`
and `inline-structure.json`. Supplemental records retain all original model
blocks, uncertainties and proposed Markdown even for abstentions. Applied rows
include exact main-Markdown item and segment offsets, original provider fragment
boxes/charspans, physical pages, source join whitespace and unchanged neighbor
hashes. Provider documents remain immutable and all outside-scope serialization
uses the stock serializer. Inferred model boxes/segments are never presented as
measured source glyph locations.

Existing source-region limits remain attributable to input selection: the matrix
paragraph crop clips source bracket edges, and SEAL item 34's provider geometry
includes unrelated caption content and a truncated paragraph. This experiment
preserves those inputs and model responses; it does not reconstruct missing
pixels or remove source-adjacent content. Full-page API outputs are retained as
separate direct-component evidence, without an official pipeline or production
mapper claim.

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-inline-api-2026-10-15/reinsertion/apply.py --selfcheck
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-inline-api-2026-10-15/reinsertion/verify.py
```

The saved checks pass stale/duplicate/unknown-reference/outside-scope-drop and
multiple-root/new-prose-repeat negatives, verify exact saved JSON/PNG identity,
all rendered segment offsets, whole-item association and unchanged outside
serialization. All 646 prior payloads remain unchanged. Preparation, parsing
and association performed no API calls, key access or new model inference.
