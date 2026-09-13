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

## Merged execution gate

T03/T04/T05 integration and fresh OCR shutdown are verified in
`tests/pdf_processing/integration`. Enrichment uses checked storage reads; worker
shutdown reaps fresh children before removing owned `activity-*` and `ocr-*` scratch.

## Typed content and source evidence (T06)

Use a **new immutable request identity**, `version: 3`, and
`completion: required_evidence_v1` for the evidence-bearing completion path.
Version 1 retains `parsed_ready`; version 2 retains required picture OCR. Version 3
finishes only after all selected picture OCR and source-evidence publication have
succeeded. Failed required evidence does not become a successful processing result.
`processing_complete` still does not mean canonical acceptance or quality approval.

Resolve the returned `processing_result` with `Store.resolve`, read its
`processing-result.json` via `Store.read_artifact`, and follow `content_evidence`
to its registered `content-evidence.json`. These are internal operation identities,
not HTTP URLs or canonical schema IDs. Follow the registration's checked file refs
for `source.pdf`, optional `original-source.pdf`, and `page-N.png`; never build a
local worker path or guess an object key. The final manifest also retains assembly,
parsed-result, selection and required OCR references. Do not delete their artifacts
when a Temporal run ends: consumer lifetime and shared GC remain separate work.

The assembly's original `document.json` bytes are unchanged and hash-bound in the
content manifest. Its full graph is the typed authority, including tables/cells,
body/furniture, parent/caption links and PictureItem children. The added `items`
index visits each reference once and preserves unlinked content; it does not make
traversal into a universal reading-order guarantee. Preserve provenance `charspan`
when an item crosses regions/pages. A CodeItem stays code, not a PictureItem;
caption and source evidence do not imply executable indentation/AST. Parser links
are retained; nearby body/note association is not inferred as a canonical fact.

Every retained region references a persisted page image and its SHA-256, TOPLEFT
page-local PDF-point rectangle, and a scale-3 pixel crop recipe. Page metadata
records dimensions, original/processed page number, effective box/CropBox, rotation,
renderer version and scale. Evidence rendering accepts rotation 0 and enforces the
configured pixel budget. The version-3 picture OCR path additionally accepts tested
nonzero CropBox origins, preserving source/picture pixel checks; v1/v2 geometry
behavior is unchanged. This is bounded geometry support, not arbitrary PDF support.

A frozen maintainer profile may add `content_evidence` with
`version: typed-source-evidence-v1` and `reviews` keyed by **exact processed PDF
SHA-256**. Each review carries that source digest, `original_pages` mapping from
processed page-number strings to original physical page integers, and optional
`original_source` containing Source Revision plus immutable artifact reference.
When original bytes are supplied, mapped page geometry and rendered pixels must
match the processed derivative; both sources are retained. No page map is guessed.

Review `regions` contain unique `id`, `kind` (`formula` or `representation`),
processed `page`, and `bbox` (`l,t,r,b,coord_origin`). Representation regions also
supply a `reason`. See the source-bound fixture preparation script for executable
examples. This is a reviewed test/profile extension point, not client-authorized
formula annotations or a universally qualified source classifier.

`formula_occurrences` includes parser FormulaItem candidates and source-reviewed
occurrences, including formulas classified as TextItem. Distinct reviewed IDs may
share a typed ref. Actual types/text are never rewritten. Coverage is `unreviewed`
without a source review; a reviewed inventory qualifies only its declared scope,
not every formula in an arbitrary document. Missing readable formula regions and
unresolvable required review regions fail explicitly. Known representation differences
are separate region-bound `textual_or_mathematical_representation_unconfirmed`
observations, with exact source/result and readable evidence. They are not silent
symbol normalizations or declarations of mathematical equivalence.

LaTeX interpretation is not implemented. A future required enrichment needs a new
versioned selection/method and must join the completion barrier before success.
T07 owns compatibility/reuse policy; canonical delivery/schema and public admission
are separate tracks. See [T06 validation](../../tests/pdf_processing/t06/README.md)
for qualified pages, limitations and actual replacement evidence.
