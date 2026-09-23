# Q04 continuation v2 source-review decision

Status: **reviewed fixture-specific exact oracle candidate; runtime acceptance pending**.
This decision covers only the pinned 51-page native PDF and 28-page Wiki06 PDF,
the two local v2 captures, and `column-edge-continuation-v2` at source SHA-256
`8c5e68006af438e2c1a5d5f82614436c8e1e7e5fc7f6e0a1d77645c640b23305`.
Their PDF, historical reference, exact document and exact nine-collection graph
hashes are frozen in [EXACT-ORACLE.json](EXACT-ORACLE.json). The original
references and AG runtime documents remain unchanged.

All **38** reviewed one-to-two components are individually listed in
[REVIEWED-SPLITS.tsv](REVIEWED-SPLITS.tsv), with both exact source page/bbox/
character ranges, intervening body items, label, parent, child/caption counts
and source-fragment identity. For every row, both v2 nodes have the historical
node's label and all non-text/provenance metadata; they have `#/body` parent,
zero children/captions, and their ordered `text` and `orig` concatenate to the
historical text. Rebased provenance equals the historical provenance exactly.
The first part precedes the second in `body.children`. No intervening body
prose or heading exists. The 31 rows without an intervening table/picture/
caption contain only page headers, footers, footnotes or no item between parts.

The seven rows with independent visual content between parts were compared
against the rendered source pages:

| Component | Rendered source reading order | Decision |
| --- | --- | --- |
| native `#/texts/123`, pages 5–6 | Page 5 corpus prose ends; page 6 Table 1 title and explanatory text begin. The historical node joined body prose to table explanation. | Keep two nodes; table caption/title remains in source order. |
| native `#/texts/162`, pages 8–9 | Page 8 right-column multilingual paragraph ends; page 9 Figure 2 precedes its continuation. | Keep the figure before the second text node. |
| native `#/texts/327`, pages 13–14 | Page 13 training paragraph ends; page 14 Table 4 precedes the paragraph's continuation. | Keep the table before the second text node. |
| Wiki06 `#/texts/128`, pages 7–8 | Page 7 result prose ends; page 8 Table 1 and its explanatory caption begin. The historical node joined prose to table explanation. | Keep table and caption order. |
| Wiki06 `#/texts/146`, pages 10–11 | Page 10 ablation prose ends; page 11 table, figure items and Table 3 precede its continuation. | Keep visual items before the second text node. |
| Wiki06 `#/texts/161`, pages 11–12 | Page 11 wiki-pattern paragraph ends; page 12 Figure 3 precedes its continuation. | Keep the figure before the second text node. |
| Wiki06 `#/texts/346`, pages 19–20 | Page 19 benchmark prose ends; page 20 Table 5 precedes its continuation. | Keep the table before the second text node. |

The only ambiguous unchanged correspondence is native's two duplicate `OPT`
picture labels: they have the same source box and text, picture parent, empty
children and source order, as recorded in the AG source review. It introduces
no new v2 edge. A diagnostic remap of *only* the 38 reviewed split pairs and
unchanged one-to-one nodes, accounting for that duplicate, reproduced all nine
historical graph collections for **both** fixtures. This comparison establishes
that no other text, page, table-cell, picture, caption, parent/child or ordering
delta is hidden; it is not a runtime normalization policy.

The runtime gate in [exact_oracle.py](exact_oracle.py) compares the complete
actual graph digest with the frozen fixture digest. It also binds the source PDF,
historical reference and continuation method. It rejects any extra split,
changed text/geometry, parent/child/caption/table/picture relation or body
order. Mutation checks exercise those failures against the retained full local
captures. No acceptance threshold or resource guard changes. Fresh, restored,
exact replay, warm equality and recovery remain unproven for this new producer
until a new controlled runtime completes those rows.
