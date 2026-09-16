# Q03 source-reviewed representation decisions — 2026-09-16

This review is performed by the Q03 implementation agent against the retained
rendered source pages, independent historical native transcripts and the original
uncorrected extraction. It is an explicit **new bounded profile decision**, not
permission inherited from the experimental scorer. Independent structural
expectations remain the frozen Q02/P2 oracle; production does not import it.

Source derivative SHA-256:
`b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980`.
Original source SHA-256:
`0609d012bf123d210c3587d1c1610074f5079217a996299123a2f7872f28a8e9`.
Private reviewed page images: `/private/tmp/aima-quality-candidate/source-{03,05,09,10}.png`.
Full native transcripts: `/private/tmp/t09a-code-oracle.json`; captions:
`/private/tmp/aima-quality-candidate/caption-source.json`. The retained Q02 oracle
pins their source/caption fingerprints. See `evidence/manifest.json` for artifact
hashes and `reviewed-representation.json` for the machine-readable decisions.

| Occurrence | Observation | Selected disposition |
| --- | --- | --- |
| BFS / uniform-cost | Exact whitespace-only source sequence, complete header/body/caption | No symbol exception |
| Depth-limited decrement | Source native U+2212; extracted U+002D. Render shows the decrement. | `retain_uninterpreted`: preserve `-`, native difference and source view; no equivalence claim |
| Depth-limited body | Native U+0007 is absent from ordered text; separate extracted U+0338 exists. | Both observations `retain_uninterpreted`; no attachment or insertion position is inferred |
| Iterative-deepening body | Same native-control/isolated-mark discrepancy | Both observations `retain_uninterpreted`, separately source-linked |
| Iterative-deepening caption | Two native U+0002 line-end controls; extracted `depthlimited` joins | Each occurrence `retain_uninterpreted`; preserve full caption and both localized differences |

The page images show the full algorithms including the recursive depth-limited
function, captions, and the visible inequality glyphs. This does not establish how
the parser's isolated mark should be placed or mathematically interpreted. Its
zero-width provenance is retained; a full-page view is context, not invented glyph
geometry. The local crop for the complete algorithm/caption is also available.

All required structures remain mandatory. Every selected observation can instead
be set to `release_gate`, which leaves its explanation/evidence available in the
intermediate report but prohibits final complete delivery. Missing review entries,
unknown dispositions or additional differences cannot inherit these decisions.
An unresolved future review therefore remains a release gate. This profile does
not assert that symbols were recovered or that the extraction equals native text.

`freeze_review.py` reproduces only fingerprints and localized symbol excerpts
from independent source regions and original extraction, with source transcript
and caption fingerprints checked against committed historical evidence. It never
calls production derivation and is not imported by production. Re-running it is
not authorization to accept a new discrepancy; a new source review/profile version
is required when scope or decisions change.

Runtime acceptance of these decisions for the new immutable producer is pending.
No historical failure, source byte, candidate artifact or accepted request is
rewritten, and the earlier Q01/Q02 runtime PASS is not extended to these cases.
