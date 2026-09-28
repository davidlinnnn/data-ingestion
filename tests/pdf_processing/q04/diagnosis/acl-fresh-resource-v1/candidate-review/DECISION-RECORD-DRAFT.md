# Draft: fixture 09 reviewed representation delta

Status: **DRAFT - NOT ACCEPTED**

## Decision under review

Accept the two-node representation in this package only as a reviewed delta for
the fixed fixture 09 bytes. The delta replaces one historical text node with two
adjacent text nodes whose source regions, concatenated text, label and parent are
identical to the historical node after rebasing the second charspan. All later
text references are renumbered by one. No other graph difference remains after
that diagnostic merge and renumber operation.

This decision, if approved later, applies only to fixture 09 with captured PDF
SHA-256 `bd33fffb2c91f35225f5b89feb29a93013f4814558ac578bef000b632fd169bf`.
It does not define a normalization rule, allow arbitrary paragraph splits, widen
continuation behavior, change the canonical schema, or promise general PDF
quality. Exact graph comparison remains the acceptance mechanism.

## Evidence required for a later decision

- Review the two full text fragments, their order, common `text` label and
  `#/body` parent, both source bboxes and charspans in `artifacts/split-review.json`.
- Review original PDF page 3 using `SOURCE-PAGE-LOCATOR.json`.
- Confirm the candidate graph hash and the one-split proof in
  `artifacts/review-manifest.json`.
- Confirm page 2's 69 quality items were regenerated from candidate typed source
  evidence. Pages 1 and 3 retain 40 and 21 items; every non-09 oracle page is
  unchanged.
- Confirm all six formula review IDs, equation 2's `TextItem`, both required OCR
  outcomes, both caption edges, full graph and source bindings remain present.

## Consequences if accepted later

A separate adoption change must create a new versioned bundle, frozen state and
phase. Existing request identities continue to resolve against the old bundle;
they must not be reinterpreted. Fresh, restored and exact replay must then produce
and verify the new exact graph. This draft and its candidate files do not perform
that adoption and do not turn the retained runtime result into PASS.
