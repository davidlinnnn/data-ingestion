# Producer boundary/context inputs

Six new crops use frozen producer geometry and the existing direct-PDFium 3x
page rasters, with 2-point outward crop padding. No model call, oracle text,
gold region or source rewrite was used to prepare them. The old CPU 646-payload
and API 200-payload sets remain unchanged.

| Input | Producer rule | Working scope |
| --- | --- | --- |
| controls-pictures-0/1/2 | Union each formula's parent picture and every child provenance. | Replace the picture serialization boundary; preserve all original picture/child data. |
| controls-code-context | Uninterrupted adjacent same-parent CodeItems on one page, left edges within 2 points and gap at most 14 points. | Coalesce comment and code items 12+13; inline item 14 remains separate. |
| seal-prose-continuation | Nearest lower text fragment, left alignment within 2 points, gap at most min(4 points, half next height), unfinished prior fragment and lowercase successor. | Stitch first fragment of item 34 with uniquely found item 45; keep the parallel spatial fragment separately. |
| seal-paragraph-formula-context | Colon-ended body paragraph followed immediately by a formula within 4 points. | Item 32 is the target; formula 33 is context only. |

Parent-only formula bounds would still be insufficient: the fraction child
extends below its parent and the piecewise child extends to its right. The union
crops visibly retain matrix brackets, fraction bar and piecewise brace/cases.
The SEAL continuation uses separate crops rather than a rectangular envelope
that would include the parallel algorithm. Fragment-to-canvas/source affine
maps, native provenance, consumed/context-only refs and source hashes are explicit.
These are source-region associations, not measured model-token/glyph boxes.

The native pre-reading-order SEAL checkpoint contains the parallel fragment as
a separate `text` element. Its caption role is a prior API interpretation,
retained with a matching-content check and exact output/hash/block reference.
It is not treated as a native automatic caption label. No caption is deleted.
The prior item-14 API paragraph/inline-code result is also reused without a new
call, with exact normalized native-token agreement and native mixed-font word
evidence. Both reuse records stay outside new model prompt content.

All six images have been visually inspected. The prepared SEAL continuation
remains a conservative spatial/orthographic candidate; the rule is not a general
paragraph or reading-order proof. Any derived source-graph split/coalescence
must remain an explicit working Markdown/structured delta with original provider
custody intact, and unsafe associations must abstain.

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-inline-boundary-2026-10-15/inputs/prepare.py
```

The saved check verifies six input identities, seven source fragments, referenced
rasters/PDFs, distinct consumed/context scope and the unchanged prior payloads.
