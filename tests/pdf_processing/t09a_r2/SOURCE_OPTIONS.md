# AIMA source-quality localization and decisions

No parser/profile or association policy is changed in this round. The required
quality scope is unchanged. Source remains original SHA-256
`0609d012bf123d210c3587d1c1610074f5079217a996299123a2f7872f28a8e9`, contiguous
99–110 derivative `b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980`.

## Reproduced cause

`source_probe.py --assert-quality` is a 0.33-second RED replay over all 12 retained
page checkpoint element lists. It uses Docling 2.102.0, docling-core 2.96.0 and
docling-ibm-models 3.15.0. The local reading-order module hash matches the retained
Linux module byte-for-byte ([fingerprint](evidence/linux-rule-fingerprint.json)).
Input checkpoint hashes, exact cluster references and text hashes are retained in
[source-localization.json](evidence/source-localization.json); full text stays private.

`ReadingOrderPredictor.predict_merges` skips headers/footers/table/picture/caption/
footnote elements, then considers consecutive TEXT elements across pages (or
strictly horizontally separated). If the predecessor ends in a lowercase letter,
comma or hyphen and the successor begins with a Latin letter, it merges them.
The original-103 prose ends in “second path”; the selected next TEXT on 104 is
the margin label. That uppercase label also matches the rule. The replay selects
`#/6/14` instead of the independently source-reviewed continuation. This confirms
the merge mechanism without invoking native models or rewriting the output.

## Earlier-stage findings, not fully isolated causes

The breadth-first heading and body fragments, uniform-cost heading, iterative
figure description and isolated combining marks already have their reported TEXT
labels in saved page elements before reading-order assembly. Depth-limited retains
CODE. Therefore those classifications are not introduced by this repository's
checkpoint reconstruction. Their complete upstream layout/text-extraction cause is
not yet isolated. Caption attachment also depends on the resulting classified
elements and page relationships; fixing the cross-page merge alone cannot close
all four algorithm expectations. Source-native U+0007 versus extracted U+0338
inequality remains representation uncertainty, not permission to normalize symbols.

## Smallest decision options for main

1. **Versioned upstream rule correction.** Evaluate a generic, geometry-aware
   cross-page continuation rule in a separate parser release, against the exact
   retained checkpoint replay first. It must reject this margin join while retaining
   true page/column continuations and the original source regions. This handles
   association only; it does not solve layout labels or inequality.
2. **Versioned upstream layout/parser change.** Test a supported upstream fix or
   pinned model/package revision for algorithm and caption classification. This
   requires new native parsing, fresh full fixtures and new model/package identity;
   a reading-order-only replay cannot validate it.
3. **Explicit attributed unresolved relationships in a future consumer contract.**
   If main chooses this product/schema direction, define how candidate associations
   and unresolved text/glyph relationships are represented without altering the raw
   graph. This is not an automatic substitute for today's required quality gate,
   nor authorization to reduce support scope.

Any accepted parser change needs a new immutable method/profile/release identity,
appropriate dependency fingerprint and request IDs. A patched upstream module must
not keep the same apparent package identity while changing output. Parse/assembly
checkpoints must be recomputed or reused only under a reviewed stage-compatibility
decision. Historical results, source hashes and seals remain unchanged.

Cross-fixture acceptance must include native 51 pages, full WikiSkill and YOLO,
contiguous AIMA, ACL six equations/typed full graph and Keynote 27 textboxes, required
OCR, original source links, true cross-page/column continuations, margin exclusion,
all four algorithm header/body/caption relationships and explicit inequality
uncertainty. Full fresh/warm equality alone is insufficient; repeat resource and
recovery qualification for any affected method/runtime. No AIMA item-ID hardcoding,
raw JSON relabelling or symbol replacement is proposed.
