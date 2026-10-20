# Fixed development evaluation contract

Frozen before candidate outputs were inspected. [evaluation-contract.json](evaluation-contract.json) fixes the source refs and scope from the unchanged [evaluation protocol](../../pdf-core-g2-eval-freeze-2026-10-15/protocol.json) and [regression retention manifest](../../pdf-core-g2-eval-freeze-2026-10-15/regression-manifest.json). These are exposed development/regression documents. No holdout source was opened; no inference, API call, or GitHub action is part of this review.

| Native document | All source item refs | Group refs | Existing selected physical pages |
| --- | ---: | ---: | --- |
| controls | 20 | 1 | 1 |
| SEAL | 326 | 15 | 3, 4 |
| WikiSkill | 514 | 16 | 21 |
| DGM | 734 | 28 | 51 |
| Total | 1594 | 60 | 5 distinct document/page pairs |

The **1594-item structural denominator** is every native text, picture, table, key-value or form item, including hidden children. It is independent of candidate emission. Groups, body/furniture roots, provider order and raw source bytes are additional graph-preservation checks. These item counts are not a semantic accuracy denominator. All-items runs must account for each source ref; selected-page runs must report their declared target/context scope and every omitted or ambiguous boundary explicitly.

The **17 prior source ref/scope records** stay fixed, including failures and the two-root SEAL34 response. Only **four bounded positives** are protected: WikiSkill363 (E14 F13 math/prose), SEAL30 (E13 cross-page F13), DGM648 (E04 selected F14 tokens/bindings/numbers, with the existing hyphenation limitation), and WikiSkill362 (restored opening sentence). The other 13 records are retained evidence, not newly labeled positives. The contract links each old output hash and exact native provenance/character scope; source rubrics remain the existing independent reviews.

Structural review verifies complete parent/child formula envelopes, adjacent code context, physical pages, source-to-pixel transforms, explicit target/consumed/context separation, complete span accounting, and outside-content preservation. The controls matrix, fraction and piecewise envelopes must retain complete structure. Code comment/body refs12+13 must remain visible once, with inline ref14 separate. An intentionally unchanged or ambiguous SEAL34 is allowed only as an explicit unresolved boundary with both native34 provenance spans and native45 continuation preserved; it cannot be called a repaired paragraph. Blanket abstention or silently skipped difficult refs cannot establish useful context planning.

Semantic review stays separate. SEAL32's saved wrong model identity/subscript/prime remains rejected or explicitly unapproved; adjacent formula33 cannot mask it. SEAL34's prior missing prose is not repaired by a structural pass. A valid formula crop is not a faithful formula transcript. No structural result establishes F13/F14 semantic completion, a full V01–V19 pass, Canonical Acceptance, or permission to use the holdout.

Old responses are replay-compatible only when image bytes/fragment order, prompt/schema/model/settings, and target/consumed/context scope are the same. Changed context inputs cannot reuse old output as new inference or a fresh model-quality result. Adapter replay on exact legacy scope can retain the old four positive labels separately from structural eligibility; if a positive gets changed context, its new-input semantic result is **not evaluated**, not passed or relabeled negative.

The candidate review should report each document and task separately, every regression and abstention, and small negative controls for clipped bounds, stale hashes, wrong physical pages/transforms, duplicate/overlapping consumption, missing hidden children, consumed context and outside deletion. The 57 retained G1 references and V01–V19 scope remain governed by the frozen manifest; unexecuted or inapplicable cases stay visible.

Not checked here: new model behavior, untouched sources, local GPU/company serving, production SLOs, and broad semantic equivalence. The retained four-document evidence supports only this bounded development review.
