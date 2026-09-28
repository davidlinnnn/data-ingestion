# Local validation

Status: **PASS for review-package integrity; NOT ACCEPTED for Q04**.

Validated on 2026-09-18 Asia/Taipei without starting a parser, workflow,
Temporal client, Kubernetes action or inference process.

- Candidate rebuild: all five generated artifact SHA-256 values in new immutable
  `/private/tmp/q04-option-a-review-v5` matched preserved v3 byte-for-byte. The
  proof format and candidate graph/oracle/content hashes did not change. The
  repository copy of the quality oracle, split record and manifest matches those
  packages; the full graph and content evidence remain private.
- Candidate verifier: `PASS_REVIEW_PACKAGE_ONLY`; exact graph has 134 nodes and
  fixture-09 quality coverage is 40/69/21.
- Focused tests: 15 passed (`test_acl_option_a_candidate` plus retained graph
  diagnosis tests).
- Full Q04 discovery: 126 passed in 9.609 seconds. The two previously absent
  historical fixtures were staged only when their targets did not exist, after
  their source SHA-256 values matched committed manifests. The AIMA source
  oracle also used its supported environment override.
- Pyright 1.1.405: 0 errors, 0 warnings, 0 informations for the graph analyzer,
  builder, verifier and candidate tests.
- `git diff --check`: clean.
- Original PDF page 3: rendered at 216 dpi to 1786 x 2526 pixels, SHA-256
  `92fe326b36b5e88cda6c8f05d3d7a63b8fc0fb50a13c964cd802d2070d77a509`;
  visual inspection confirmed both fragment locations recorded in
  `SOURCE-PAGE-LOCATOR.json`.

The complete suite used an existing local dependency directory and process-table
access for cleanup tests that create and terminate only their own temporary sleep
processes. No service state was changed. The 32 historical Deployments were not
queried or restored in this offline phase.
