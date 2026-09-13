# Request-driven PDF execution (T01)

These internal execution seams extract the known Docling checkpoint algorithm and
S3 publication protocol from investigation #30. They are not a canonical schema,
public ingestion API, or production worker lifecycle. Historical prototype scripts
and evidence remain frozen and are not imported by this package.

`ParseRequest` describes one baseline/capture/restore invocation, with explicit
PDF path, output directory, model cache, extraction profile and optional expected
method inventory. Send its JSON through stdin to `python -m pdf_processing.parse`.
Run exactly one invocation per interpreter: instrumentation installs process-wide
Docling stage guards, and warm process reuse is S1's separate question. Importing
this module does not initialize Docling, fetch models or choose source paths.

`SourceRequest` binds a captured Source Revision, source digest, explicit method
inventory and locally accessible immutable PDF/model cache. `Execution.produce`
accepts one group, assembly or selected-component OCR operation and returns the
registered object-store operation identity. The caller supplies Store, scratch
root and heartbeat callback. Payloads, not local paths, enter the registered store;
every result includes source/method/code/operation attribution. Models must already
be available; the invocation environment can enforce `HF_HUB_OFFLINE=1`.

Assembly receives group operation identities and a complete page range. OCR
receives a parsed operation identity and explicit Docling picture self-reference.
The preserved crop path supports single-page BOTTOMLEFT provenance at cached scale
1, with pixel validation; broader crop/profile support belongs to T04/T06. The
returned OCR report describes execution, not canonical acceptance or downstream
readiness. Fixture-specific caption and label scoring lives only in verification.

`temporal.PDFExecution` is a small verification harness over these operations. Its
caller supplies the group plan and component list. It uses a single activity slot,
finite retries and fresh subprocesses; it does not adopt the historical orchestration
or select deployment policy for T02. Methods and source paths are carried explicitly
in this temporary internal request. T02 replaces caller policy with versioned
source references/preflight and its reviewed operation contracts.

The all-producer identity and strict complete method inventory are intentionally
preserved; T07 owns selective compatibility. Conditional publication is preserved
without redesigning its race/retention semantics; T03 owns hardening. No object GC,
HTTP admission, profile expansion, warm worker or canonical delivery is added here.

For a small in-process integration, construct `Execution(SourceRequest(...),
Store(s3_client, bucket, prefix), scratch, heartbeat)` and await `produce` with
`kind=group`, then `kind=assembly`, then `kind=ocr`. For real-service verification,
see the acceptance runbook under `tests/pdf_processing`.

<<<<<<< HEAD
## Recovery storage operations (T03)

`Store.resolve` returns `None` only for absent registration. It validates the
versioned manifest, one attempt namespace, unique safe artifact names, lengths
and application SHA-256 on each referenced read. `StoreFailure` distinguishes
`integrity` (committed bytes/manifest invalid), `configuration` (access/bucket
configuration) and `storage` (retryable service/transport unavailability).
Processing maps the first two to permanent failures. There is no automatic repair.

Publication uses immutable attempt keys and conditional registration. Ambiguous
write responses reconcile by read; concurrent losers validate and return the
winner. Observably different attempted payload sets are retained in diagnostic
records. Nothing in this adapter changes a Workflow's terminal state.

Operators can run `python -m pdf_processing.object_store --max-objects 10000
--capacity-bytes <prefix-budget>` with the worker's `OBJECT_ENDPOINT`,
`OBJECT_BUCKET`, `OBJECT_PREFIX` and credential environment. It performs read-only
bounded inventory: registration/artifact counts, invalid registrations, observed
bytes and orphan candidates. Exit 2 reports corrupt registration or exceeded
logical capacity; exit 3 means the listing was incomplete and needs a larger
observation budget. Never treat orphan candidates as deletion authorization.

The inventory is not a transactional snapshot; compare exact counts only while
writers are quiescent. Truncation or corruption suppresses orphan classification.
Listed live versions provide a byte lower bound, not physical disk usage or all
historical object versions; monitor provider disk/PVC capacity separately. Shared
GC and canonical retention ownership remain deferred.
=======
## Required component OCR (T04)

Existing version-1 requests still finish at internal `parsed_ready`. For the complete
processing path, submit a new request identity with `version: 2` and
`completion: required_picture_ocr_v1`, retaining the immutable source reference,
digest, Source Revision reference and published profile fields. The completion
target is part of the frozen request; do not reuse a request ID to change it.

The workflow persists all assembled PictureItem candidates under a versioned rule,
schedules one required OCR at a time, and returns `processing_complete: true` only
after the final processing-result registration validates all dependencies. Follow
`processing_result` to the manifest, then each `enrichments[].operation` to its OCR
JSON and matching crop artifact. Large text/image bytes are not Temporal payloads.
A successful result has `canonical_accepted: false`; its extraction quality remains
separate from execution completion. Unsupported selected crop geometry or exhausted
required OCR fails processing. See the T04 acceptance instructions for the bounded
coordinate/rendering support and evidence.
>>>>>>> codex/pdf-t04-component-ocr
