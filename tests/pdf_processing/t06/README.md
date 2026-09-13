# T06 — typed content and durable source evidence

The confirmed seam is versioned request → real Temporal Activities/shared object
store → explicit failure or complete internal handoff. See [CONTRACT.md](CONTRACT.md)
and the [consumer interface](../../../src/pdf_processing/README.md#typed-content-and-source-evidence-t06).
The bounded qualification and its limitations are in [evidence/VERDICT.md](evidence/VERDICT.md).

## Reproduce in the retained local qualification cluster

This harness intentionally uses the existing local Docker/Kubernetes qualification
cluster, the retained `pdf-t04-validation` deployment specs, pinned
`pdf-checkpoint-prototype:linux-v2` image/model cache, and the performance
storage/Temporal templates. It creates only `pdf-t06-validation`, bucket `t06`,
prefix `final`, queues `t06-workflows`/`t06-pdf`. It is not production provisioning.
Temporal uses the test dev server with PVC persistence; MinIO is local shared
storage. Production HA, provider durability, capacity and throughput are not qualified.

1. Retain the source PDFs and S2 worktree at `7b3d5ac7a3515758956c10dd1f67a0895e98f7d1`.
   Scripts use the user's local fixture catalog under
   `docs/fixtures/pdf-s2-candidates-2026-09-13` and S2's local ignored oracles.
   The private files are prerequisites, not downloaded by this harness.
2. Run `prepare_fixtures.py` with the existing prototype Python environment. It
   verifies original source digests and writes bounded PDFs/manifest under
   `/private/tmp/t06-fixtures`. Run `prepare_quality_oracle.py` to freeze prior S2
   source-audited text hashes. Do not substitute current output as a quality oracle.
3. Prepare the existing synthetic integration fixtures under
   `/private/tmp/pdf-integration-fixtures`. Run `python3 tests/pdf_processing/t06/setup.py`.
   It loads package/worker/profile ConfigMaps. For a fresh namespace first create
   bucket `t06` and enable versioning (the `legacy.py` setup does this). Copy bounded
   files individually to coordinator `/tmp/t06-fixtures`, original PDFs to
   `/tmp/t06-originals/<id>.pdf`, and the S2 source-reviewed table/code/region oracles
   to `/tmp/t06-oracles` as named in `real_cases.py`. Copy scripts to `/tmp/t06-test`.
   Keep large/private PDFs out of ConfigMaps and version control.
4. Run `upload.py` in coordinator. It uploads immutable originals and generates
   `/tmp/t06-profile.json`. Copy that profile to host `/private/tmp/t06-profile.json`,
   rerun setup, and restart T06 workflow/Activity deployments. All runtime code,
   frozen profile, limits and original object versions are recorded in `runtime.json`.
   New derivative bytes require new exact source-digest reviews and uploads.
5. In coordinator use `/experiment/.venv/bin/python` (with `PYTHONPATH=/app`) to run
   `real_cases.py`, `check_quality.py` (oracle at `/tmp/quality-oracle.json`),
   `fresh_compare.py`, `check_review_failures.py`, `tc_supplement.py` and `legacy.py`.
   The TC fixture is the retained `/tmp/nccu-page3.pdf`. Independent uninterrupted
   baselines are generated once; `fresh_compare.py --existing-baselines` compares
   later finalization-only fixes without redundant parser inference. Never reuse
   them across source/parser/method changes.
6. After completion, record the Activity Pod UID, delete only that Pod, wait for its
   replacement and record the new UID/image. Run `after_replacement.py` in a fresh
   coordinator Python process. It verifies checked artifact reads, nonblank evidence
   crops, identical final registration and all page/assembly/OCR steps reused.
7. Run `collect_runtime.py`. Retain the private `/tmp/t06-results` and fresh baseline
   documents locally. Commit only metadata, hashes, scoped results and logs. The
   committed evidence manifest binds those metadata files and implementation hashes.

The harness keeps each failed exploratory run separate. A scorer failure is not
silently recorded as a parser defect or a successful acceptance check. Results from
an earlier producer must not be relabeled as those of a newer worker.

## Focused regression checks

Run with the existing prototype Python dependencies:

```sh
PYTHONPATH=src python -m unittest discover -s tests/pdf_processing/t04
PYTHONPATH=src python -m unittest discover -s tests/pdf_processing/t05
```

Typecheck `src/pdf_processing` and `deploy/pdf-processing/worker.py` with Python 3.12
and the pinned Temporal/Docling dependency paths. These checks supplement actual
service validation; they do not replace it. T03 publication/fault and T05 active
shutdown evidence remain in the earlier merged integration gate. This ticket adds
post-completion replacement retrieval, not a new claim of active OCR-kill coverage.

The complete unittest run additionally includes the existing scanned-PDF
fresh-process restoration regression (10 tests total). In an isolated worktree,
set `PDF_TEST_FIXTURE_ROOT` to the original checkout's
`docs/prototypes/pdf-checkpoint-prototype` containing the retained fixture/model
cache, then run `PYTHONPATH=src python tests/pdf_processing/t06/run_unit_suite.py`.
The retained full-suite log uses the host's existing Python 3.12 environment;
production handoff qualification above uses the separately pinned Linux runtime.
