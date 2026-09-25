# N validation scope

Requires original AIMA profile identity/oracle and budget20; negative tests must
reject budget1, region/representation mutations and wrong identity/scope. Full
supervisor argv must parse through the real new driver; projected source hashes
and imported contract must pass. Existing real interruption, sample preservation,
sealing, persistent-channel failures and cleanup regressions target versionN.
No local test or frozen manifest alone qualifies runtime.

## Executed results

- 131 focused N runner/transport/THP/probe/persistent-channel/interruption/
  cleanup/contract tests passed before execution, including full supervisor
  argument parsing and projected source validation.
- 32 original consumer/adapter/controller/matrix/host tests passed with the
  existing prototype venv, isolated `/private/tmp/q04-local-deps-20260920`
  dependencies and the SHA-verified existing Q02 baseline. See
  `consumer-verified.log`; prior sandbox failure remains retained.
- The broad suite attempt collected 702 tests and ended with 5 failures and
  19 errors. **It did not pass.** See `full-suite-environment-failure.log`.
  Missing historical Q01 checkpoints/default Q02 baseline, missing venv
  Temporal/botocore dependencies and macOS process-inspection restrictions
  prevented complete verification. A scanned-restoration check also failed in
  that environment; it has not been requalified. One obsolete matrix assertion
  was corrected to the evidence-backed M status and passed focused rechecking.
  Historical inputs were not fabricated and the main venv was not modified.
- After N, two real-evidence image audit tests passed, including seven negative
  mutations and the original consumer rejection. Five acceptance-matrix tests
  passed. Independent Spec review reran all seven; Standards review reran the
  two image tests using the existing prototype venv.

Reproduce the post-N checks with `PYTHONDONTWRITEBYTECODE=1` and
`/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python`:
`-m unittest discover -s tests/pdf_processing/q04/diagnosis/aima-n -p test_image_audit.py`
and `PYTHONPATH=tests/pdf_processing/q04 ... -m unittest test_acceptance_matrix`.
The image tests intentionally require the retained private N output and fixed
bundle; their absence is an error, not a skipped pass.
