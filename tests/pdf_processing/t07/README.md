# T07 compatibility qualification

Seam: versioned captured-source request → real Temporal Activities/shared object
storage → complete result or explicit failure. The run uses only
`pdf-t07-validation`, `t07` bucket / `final` prefix, `t07-workflows` and dedicated
`t07-matrix-*` Activity queues. The pinned image and retained T04 specs are prerequisites.
No T06 registrations, workers, source PDFs or root-checkout documents are modified.

1. With the retained local Docker/Kubernetes cluster and synthetic fixtures in
   `/private/tmp/pdf-integration-fixtures`, run `python3 tests/pdf_processing/t07/setup.py`.
   This derives isolated infrastructure from the retained T04 deployment specs and
   loads the checked-in native profile (never T06 source-specific object refs).
2. In coordinator, run `/driver/verify.py` with `/experiment/.venv/bin/python` and
   `PYTHONPATH=/app`. It creates/version-enables the isolated bucket. Before the
   implementation this failed: a deliberate request repeated parsing and assembly.
   `evidence/red-reprocess.json` preserves that initial observation.
3. Run `python3 tests/pdf_processing/t07/run_matrix.py`. Every scenario runs a fresh
   real Temporal Activity worker in the coordinator, with a separate queue and a
   private `/tmp/t07-runtime` package copy. The normal Workflow worker remains in
   its own deployment. OCR implementation and parser implementation variants alter
   attributed output metadata; OCR also changes the actual render scale from 3 to 4.
   The unrelated variant changes the legacy Temporal adapter, unused by this seam.
   All producer hashes are recorded per scenario. Two-page input is synthetic.
4. The OCR case also materializes the actual baseline checkpoint from MinIO and
   invokes the real guarded restore child. It checks exact full document equality,
   zero repeated page stages, unsupported-format rejection and undeclared-producer
   rejection. The main request must reuse assembly without invoking restore.
5. Run the existing T03 `verify_store.py` with T07 bucket/endpoint to verify real
   duplicate publication, lost acknowledgements, checked reads and authorization.
   Those tests use separate random prefixes and do not alter accepted artifacts.
6. Run `t06/run_unit_suite.py` with the retained Python 3.12 environment and
   `PDF_TEST_FIXTURE_ROOT` pointing to the original prototype fixture/model directory.
   Typecheck the processing package and deployment worker using the pinned dependency
   paths and an explicit Pyright typeshed path (the retained npm cache needs it).

Only request/operation metadata, producer/environment hashes and bounded reports
are committed. Full JSON, images, source files and checkpoints remain in local
MinIO. A real restore intentionally performs document assembly for the isolated
restore check; the OCR-only end-to-end request performs neither parsing nor assembly.
