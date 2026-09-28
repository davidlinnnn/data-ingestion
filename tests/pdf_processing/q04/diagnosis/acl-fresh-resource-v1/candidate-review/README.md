# ACL fixture 09 Option A source-review package

**Status: NOT ACCEPTED. Acceptance remains FAIL against the active exact graph.**

This copy-on-write package turns the retained ACL output into a concrete review
candidate without changing the active reference, quality oracle, frozen bundle,
R3 evidence, production code or runtime state. The complete candidate graph and
derived content evidence remain in the immutable private review root
`/private/tmp/q04-option-a-review-v3`; this repository does not publish the
fixture's copyrighted extracted text. `artifacts/` contains the derived hash-only
quality oracle, the required two-fragment split record and a manifest binding the
private complete artifacts by SHA-256.

The candidate proves one representation delta: historical `#/texts/97` becomes
candidate `#/texts/97` and `#/texts/98`. The first fragment is 343 characters and
the second is 86 characters; both are `text`, both have parent `#/body`, their
reading-order positions are 16 and 17, and their provenance rebases exactly to
the historical two-region provenance. The full strings, bboxes, charspans and
mapping live in `artifacts/split-review.json`.

The candidate quality oracle is evidence-derived. Its fixture-09 page counts are
40, 69 and 21. Each item is rebuilt from the candidate traversal with its actual
type, JSON text hash, page-specific source boxes and caption text hashes. All
non-09 entries equal the active oracle. The manifest also binds the unchanged Q01
continuation oracle, Q03 reviewed representation and Q04 fixture manifest.

`SOURCE-PAGE-LOCATOR.json` reproduces original PDF page 3 at 216 dpi and gives
both fragment boxes in PDF and rendered-pixel coordinates. Visual inspection of
the recorded render shows the first fragment ending at the bottom of the left
column and the second beginning near the top of the right column.

Build and verify from the retained immutable inputs:

```bash
python3 tests/pdf_processing/q04/diagnosis/acl-fresh-resource-v1/candidate-review/build_candidate.py \
  --reference /private/tmp/q04-inputs-local-v5/references/09.json \
  --candidate /private/tmp/q04-acl-fresh-resource-analysis-v1/state/acl-fresh-resource-v1/fresh-09/document.json \
  --retained-report /private/tmp/q04-retained-content-v1/09.json \
  --quality-oracle /private/tmp/q04-inputs-local-v5/oracles/quality-oracle.json \
  --original-pdf /private/tmp/q04-inputs-local-v5/originals/09.pdf \
  --fixture-pdf /private/tmp/q04-inputs-local-v5/fixtures/09.pdf \
  --ocr-summary tests/pdf_processing/q04/sentinel/acl-fresh-resource-v1/evidence/summary.json \
  --continuation-oracle /private/tmp/q04-inputs-local-v5/oracles/continuation-oracle.json \
  --reviewed-representation tests/pdf_processing/q03/reviewed-representation.json \
  --fixtures-manifest tests/pdf_processing/q04/fixtures.json \
  --output /private/tmp/q04-option-a-review-copy

python3 tests/pdf_processing/q04/diagnosis/acl-fresh-resource-v1/candidate-review/verify_candidate.py \
  --reference /private/tmp/q04-inputs-local-v5/references/09.json \
  --active-quality /private/tmp/q04-inputs-local-v5/oracles/quality-oracle.json \
  --package /private/tmp/q04-option-a-review-copy
```

The builder requires all reviewed input hashes, creates its output directory
exclusively, refuses any existing target and rejects output paths inside the
repository. The verifier keeps exact graph comparison strict. Offline tests prove
removal of either fragment or provenance, changed text, wrong order or parent,
and an unexpected node are all rejected.
