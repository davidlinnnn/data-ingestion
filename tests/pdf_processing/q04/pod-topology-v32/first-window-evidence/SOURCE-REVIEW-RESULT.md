# AG source-review result

Status: **REJECTED_CURRENT_NATIVE_GRAPH**. No oracle is adopted.

This review binds the reference and AG document hashes in
[SOURCE-REVIEW-REQUEST.md](SOURCE-REVIEW-REQUEST.md) to native source PDF
SHA-256 `d58be5fc39608dc9aec45194c602436d793f2f2bf56f267d0e38d6258a9f7a9e`
(`/private/tmp/q04-inputs-warm-lifecycle-ag-final/originals/native.pdf`).
Rendered source pages 5, 12–13, 16–19, 21–22, and 28–29 were inspected against
the retained text provenance. Both documents have the same source-fragment
multiset. Native has 29 changed fragment components: 23 one-to-two splits and
the six many-to-many components below. In the table, L/R mean the left/right
body columns; arrows follow fragment order within the text nodes.

| Source pages | Reference text nodes → AG text nodes | Source reading order and AG defect | Disposition |
| --- | --- | --- | --- |
| 5 | `71, 84` → `72, 85` | Both `OPT` labels have the same source box, text, picture parent, empty children and order. The duplicate source box prevents a unique pairwise correspondence, but this component contains no reordered fragment. | Benign within this component; not an oracle decision. |
| 12–13 | `303, 308` → `314, 315, 320` | Source: p12 L → p12 R → p13 L. AG joins p12 L → p13 L before p12 R. | Reject: page 12 right-column text is skipped. |
| 16–17 | `396, 398, 404` → `412, 413, 415, 421` | Source: p16 L → p16 R → p17 L → p17 R. AG joins p16 L → p17 L and p16 R → p17 R; the resulting `Key Factors... The quality of from pre-training...` is malformed. | Reject: two cross-page joins cross intervening columns. |
| 18–19 | `423, 429` → `440, 442` | Source: p18 R → p19 L → p19 R. AG joins p18 R → p19 R before the p19 L continuation. | Reject: page 19 left-column text is skipped. |
| 21–22 | `530, 533` → `547, 548, 551` | Source: p21 L → p21 R → p22 L. AG joins p21 L → p22 L before p21 R. | Reject: page 21 right-column text is skipped. |
| 28–29 | `607, 615` → `631, 633` | Source: p28 R → p29 L → p29 R. AG joins p28 R → p29 R before the p29 L continuation. | Reject: page 29 left-column text is skipped. |

The five rejected components preserve their exact source fragments but change
their **sequence inside text nodes**. The reference sequence matches the PDF
columns. This is a concrete reading-order failure, not just an unreviewed graph
representation difference. The other 23 native splits and six Wiki06 splits
have not been individually approved; their fragment equality alone does not
prove full graph semantics.

`src/pdf_processing/continuation.py` v1 admits a next-page target with the same
column coordinates and checks for later content only *within the source column*.
That rule is consistent with all five invalid cross-page joins. The retained
assembled documents do not include the pre-merge ordered elements, so whether
this rule is the sole cause remains **unproven**. A revised, versioned producer
needs a regression check at the `predict_merges` seam, source review of any new
graph delta, and fresh/restored/exact-replay qualification. No historical
reference, AG evidence, acceptance threshold or resource guard is changed.
