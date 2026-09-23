# Q04 continuation v3 offline result

Status: **source-reviewed exact oracle candidate; no Temporal/shared-storage acceptance**.

The v2 cross-page adjacency filter correctly removed six invalid native joins,
but an offline AIMA 12-page capture found one regression: reference text
`#/texts/129` on source pages 5–6 was split because Docling placed a narrow
page-margin picture between its two text parts in predicted reading order.
Rendered pages 5–6 show the paragraph really continues; the picture is a small
hand-pointer outside the body text column, while a separate narrow
`DEPTH-FIRST SEARCH` label is already ignored. The focused regression failed
on v2 (`{}` instead of `{0: [2]}`). Source review then found that width alone
would also ignore a small picture *inside* a body column; a second regression
failed on that unsafe variant. V3 now ignores a narrow picture only when it
falls outside the horizontal span of all wide body text on its page. Both
focused cases pass;
existing owner/entrance and source-column checks are unchanged. The method is
`column-edge-continuation-v3`, source SHA-256
`ab5f1bb51b86c1cd8966c645e6e96df839c86460ce265be079451530402935ed`.
V1 and v2 method bindings are rejected before parsing.

The same pinned image `pdf-checkpoint-prototype:linux-v2` recaptured each exact
PDF under this final source with no network, 10 GiB container limit and four
CPUs. Those outputs are retained under `/private/tmp/q04-local-native-v3-envelope/`.
The complete local v3 documents have these SHA-256 digests:

| Fixture | v3 document | Comparison |
| --- | --- | --- |
| native (51 pages) | `70673bdc5cb548d37c81efa91bb1c5460f71f94148bdb5d1218a319c6af9f152` | Byte-identical to source-reviewed v2 capture. |
| Wiki06 (28 pages) | `5f00af22b9264c32462f006f4debadff20fe52051424b38c8f06e5e28404cb68` | Byte-identical to source-reviewed v2 capture. |
| YOLO07 (15 pages) | `27596742b5f41936e91abd2d9b260d7f966bf190d62b985efe7cd92f3f168708` | Byte-identical to AG warm document. |
| AIMA08 (12 pages) | `dd0115f20c6a173ae9c1a1ebef793696e46df0fdbbe0902f2bf8d68f803ebbfe` | Byte-identical to AG warm document; valid page 5–6 continuation restored. |
| ACL09 (3 pages) | `ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506` | Full graph equals retained reference. |
| Keynote10 (1 page) | `893af666a8dac763bd79ed217b3f2defe474af4b9bafed1acecafdf3de8b4c57` | Full graph equals retained reference. |

The complete native and Wiki06 document bytes are unchanged under v3, so the
38 exact source-reviewed splits, graph links, geometry and order in the
[v2 source-review decision](../continuation-v2/SOURCE-REVIEW-DECISION.md)
apply without reinterpreting a single component. The new
[EXACT-ORACLE.json](EXACT-ORACLE.json) binds the v3 method to those two exact
graph digests and all six local document digests. The shared exact graph gate
rejects any additional split or text, geometry, relation or order change; v2
method is rejected by the v3 oracle. Local captures remain diagnostic only.

The six focused v3 continuation tests pass. Eleven retained Q01 synthetic
tests pass; two Q01 tests requiring absent historical checkpoint files remain
unrun. Four exact-oracle tests pass, including source-preserving extra-split
and graph mutation checks. No historical runner, reference, AG evidence,
resource guard, acceptance threshold or cluster state changed. A new identity,
profile, bundle and controlled runtime are still required for fresh, restored,
exact replay, warm equality and recovery rows. #51 remains open.
