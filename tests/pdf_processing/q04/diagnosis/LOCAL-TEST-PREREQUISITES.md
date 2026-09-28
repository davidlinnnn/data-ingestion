# Q04 local discovery fixture prerequisites

This is a read-only inventory for the three external-fixture errors in the full
Q04 discovery run. It does not create replacements or treat a newly generated
artifact as historical evidence.

## AIMA transcript

The missing historical path is `/private/tmp/t09a-code-oracle.json`. The frozen
bundle contains the original corresponding transcript at
`/private/tmp/q04-inputs-local-v5/oracles/aima-code.json`, SHA-256
`ae3176eb987341243a90dc0fb4a476be3286f2f63c56196c8706f8067788ae7c`.
That hash exactly matches `tests/pdf_processing/q03/evidence/manifest.json`.

`tests/pdf_processing/q02/oracle/score.py` supports the explicit
`Q02_SOURCE_ORACLE` path override, and both Q04 runtime adapters set it to the
frozen bundle copy. `tests/pdf_processing/q03/freeze_review.py` still uses the
historical absolute path and has no override. A reproducible full-discovery setup
must expose the verified bundle file at that exact path, or separately review a
path-injection change. No transcript should be reconstructed.

## T06 fixture-09 evidence

The missing file is `/private/tmp/t06-final-results/09-evidence.json`. The existing
retained original is `/private/tmp/q04-retained-content-v1/09.json`, SHA-256
`32bf568a25a4f9c7d85d3673edeb6e715b76b6a7bba41552aa224d2945f15afe`.
That hash is recorded as fixture `09.json` in
`tests/pdf_processing/q04/evidence/phase-two-local-reviewed.json`. Its
`document_sha256` is the accepted historical graph hash
`aaa62538d423472fd4999675fdcd39501eaa11bce89d630843c8609177533c6c`.
The retained evidence passes `check_graph` with the existing historical
`/private/tmp/t06-final-results/09-document.json`; this is a read-only compatibility
check, not regeneration.

`tests/pdf_processing/q04/test_adapter.py` has no environment or path override for
the T06 directory. To reproduce the full local suite, stage the hash-verified
retained original under its historical filename before test discovery, or first
review a narrow fixture-root injection. Do not substitute current ACL output or
derive a new evidence report from it.

Before this correction, main observed 100 tests with 97 passing and these same
three errors. After adding thirteen ownership regressions, local process enumeration
produced 113 tests with 110 passing and the same three errors—one missing AIMA path
and two tests opening the same missing fixture-09 evidence file. They are fixture
setup errors, not assertion regressions in this cleanup change.
