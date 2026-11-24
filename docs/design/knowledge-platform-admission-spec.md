# Knowledge Platform admission specification

**Status:** current contract, kept up to date when a decision changes. The implementation
tickets #95–#99, #194, #251 and #252 build from this document.

The buildable contract for
[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31).
The decisions and their reasons are in the
[admission design notes](knowledge-platform-admission.md) (rounds 1–5, with
question numbers such as Q9.4). This document states only the current result.
The rules in §6 are also modelled in the
[admission rules prototype](https://github.com/davidlinnnn/data-ingestion/blob/prototype/31-admission-rules/docs/prototypes/admission-rules.prototype.html), whose
19 scenarios pass. Domain terms follow `CONTEXT.md`. The file upload path (why
it is a platform endpoint, the architecture, the sequence diagrams and the
Source-facing guide) is the [document submission guide](knowledge-platform-file-upload.md);
§5 here stays the contract.

Sizing figures marked *unmeasured* are provisional until the cluster-tier
validation (§13) measures them.

## 1. Scope

In scope: document submission through batches, file upload through the
platform, durable admission, dispatch to Temporal, request and document status, Source Deletion,
application retry and the platform scan, retention, and the validation plan.

Out of scope here, with owners:

| Topic | Owner |
|---|---|
| Resource API, grants and authorization decisions | #85 (pilot), #86 (GAM) |
| Stopping disclosure, governance withdrawal, protected status | #56 |
| Custody, retained bytes, Custody Purge | #57 (purge with #56) |
| Canonical processing and the workflow implementation | #80, with the #91 manifest v2 |
| Projection consumption, the handoff channel, product removal | #55 |
| Serving results and filtering | #76 |
| Database deployment and backup, Temporal, configuration loading, topology, observability | #78 |

Deferred: callbacks and webhooks, client cancellation, inline content, filterable
attributes, full-snapshot reconciliation, rename, a Source-facing `reprocess`,
cross-region recovery.

## 2. Sources

A Source is registered by platform configuration (#78 loads it). Admission uses
these fields:

| Field | Meaning |
|---|---|
| `source_id` | Readable fixed string, unique per tenant; given to the application with its credential |
| `tenant_id` | Stored on every admission record |
| credentials | Each belongs to exactly one Source and holds `submit` and/or `manage_relations` |
| `projections` | The Knowledge Profile: required Projection Types for readiness |
| `ordering` | `source_version` (default) or `arrival` (§6.3) |
| `default_resource_id` | Optional; one of the Source's own Resource keys (§5.1) |
| quota overrides | Optional overrides of §11 |

Requests never carry a tenant or Source; both come from the credential.

## 3. Resources and data model

Logical records; the physical schema is I1's.

| Record | Key fields | Notes |
|---|---|---|
| `batch` | `batch_id`, `source_id`, `state` (`open`, `finalized`, `expired`), `created_at`, `expires_at`, `finalized_at`, `cleaned_at` (its upload cleanup done, §6.2) | The history of one submission |
| `batch_item` | `batch_id`, `index`, `document_id`, `document_uid`, `status`, `request_id`, `source_revision_id`, `error`, the item as declared (files with lowercase `sha256`, catalog fields, the Resource's full identifier, whether the document is new, and each carried-over file's `custody_ref`), the placement decisions at declaration and at finalization (`decision_id`, `evaluated_at`, a deny's `reason`) | §5.1 statuses. A file to upload is one not carried over |
| `document` | `document_uid`, `source_id`, `document_id`, `resource_id`, `title`, `source_url`, `metadata`, `deleted_at`, `delete_request_id`, `latest_source_revision_id`, `created_at`, the current Canonical Revision (`current_source_revision_id`, `current_canonical_revision_id`; the two values selection compares, `current_source_revision_sequence` and `current_adoption_sequence`; and `current_adopted_version`, the version that made it), `acceptance_version` | Unique (`source_id`, `document_id`) among documents not deleted. The latest Source Revision of §6.3 and §6.4 is the one finalization created last. The current Canonical Revision is Canonical Acceptance's (below) |
| `source_revision` | `source_revision_id`, `document_uid`, `source_version`, `sequence` (1, 2, … per document in finalization order, unique per document), `files` (`path` → `custody_ref` (§10), `sha256`, `size`, `media_type`, `role`), `outcome` (`pending`, `accepted`, `rejected`, `failed`) | One per change of content from the latest Source Revision (§6.3). Under `ordering: source_version`, its `source_version` is the highest submitted while it is the latest (§6.4) |
| `request` | `request_id`, `kind` (`process`, `delete`), `document_uid`, `source_revision_id`, `state`, `initiator` (`source`, `operator`, `platform`), `retry_of`, `batch_id`, `priority`, `adopted_version`, `adoption_sequence`, `trace_id`, timestamps, `error`, `attempt_id` (the current attempt, §7.3), `last_report` and `reported_at` (the current attempt's last report taken, and when) | `request_id` equals the Temporal workflow ID |
| `canonical_revision` | `canonical_revision_id` (`crv_` and the request id's 32 hex digits), `document_uid`, `source_revision_id`, `request_id`, `adopted_version`, `adoption_sequence`, `content_ref`, `content_sha256`, `content_size`, `accepted_at` | An accepted Canonical Revision, one per request, fixed once written (ADR-0003). `content_ref` is the candidate's `ref`, checked to be the revision's own key (§7.3) |
| `withdrawn_version` | `media_type`, `version`, `withdrawn_at` | Processing Profile versions withdrawn per main-file media type (#57 B6); written by declarative adoption (#261) |
| `outbox` | `request_id`, `available_at`, `attempts`, `dispatched_at` | Written in the same transaction as the request |
| `idempotency_key` | (`source_id`, key), body hash, stored HTTP status and response, `created_at` | 24 hours |
| `intake_quota` | `source_id`, `tokens`, `refilled_at` | The token bucket of §11 |
| `adoption` | `sequence`, `tenant_id`, `media_type`, `adopted_version` (none on a declared cancellation), `adopted_at`, `cancelled_at`, `declaration` (none on a row of the local `adopt` command), `refresh` | The adoption record, below. Unique (`tenant_id`, `media_type`, `declaration`) |
| `adoption_check` | `check_id`, `tenant_id`, `media_type`, `version`, `attempt`, `started_at` | Each test workflow of the adoption gate (below). Unique (`media_type`, `version`, `attempt`) |
| `adoption_run` | `tenant_id`, `media_type`, `result`, `reason`, `runs` | `apply-adoption`'s runs counted by result and reason, for the `api`'s gauges (below) |
| `adoption_status` | `media_type`, `tenant_id`, `result`, `reason`, `since` | Each media type's latest result and reason, and when the result last changed |

Constraints:

- At most one `process` request in `queued` or `processing` per
  (`document_uid`, `source_revision_id`): a partial unique index (Q9.7a).
- Finalization and re-declaration are serialized per document (row lock on the
  document). Each reads the latest Source Revision after the operation before it
  on that document has committed, so §6.3 orders against a version §6.4 recorded
  meanwhile.
- `source_revision.outcome` is set by canonical processing outcomes of
  Source-initiated and operator requests; platform refreshes (`initiator:
  platform`) never change it (round 3 R2), except that Canonical Acceptance
  (below) makes every accepted revision's Source Revision `accepted`, a
  refresh's included. A Source Revision is `accepted` exactly when it has a
  `canonical_revision`. When such a `process` request ends,
  whether a status report (§7.3) or the reconciler (§9) records it first, its
  Source Revision's outcome follows in the same transaction:

  | The request ends | `source_revision.outcome` |
  |---|---|
  | `failed` with `VERSION_WITHDRAWN` (§9) or `DOCUMENT_DELETED` (§8) | unchanged: neither says anything of the revision |
  | `failed`, any other error whose `error.metadata.cause` is `source` | `rejected` |
  | `failed`, any other error, `WORKFLOW_ENDED_WITHOUT_RESULT` included | `failed` |
  | `succeeded` | `pending`; `accepted` in the same transaction when it forms Canonical Acceptance (below) |

  An `accepted` outcome stays: a later request, whatever its outcome, does not
  undo the acceptance. A request that has ended keeps its outcome; whichever of the two
  records it first wins.
- A declaration in which every item is rejected keeps no record, its placement
  decisions included. An item rejected at finalization before its placement
  re-check still records that re-check's decision.

The adoption record (#96) names the Processing Profile version that new
`process` requests run, by the media type of the main file: the pilot has one
profile per file format. It is declared in the deployment repository and applied
by a CronJob (#261, ADR-0016): nobody runs a command inside a pod in the
company's production clusters. The deployment values hold one entry per media
type (its `declaration` number is not a batch declaration of §5.1):

```yaml
adoption:
  application/pdf:
    declaration: 12        # raised by one at every change
    version: paper-pdf@3   # or none: the media type has no version
    refresh: none          # none, all or {made_by: [paper-pdf@2]}; required
    withdrawn: []          # versions withdrawn, for example [paper-pdf@2]
    kept: []               # higher versions not withdrawn on a downgrade, for example [paper-pdf@4]
```

The chart passes the mapping to `kp-admission apply-adoption --tenant <tenant>`
as JSON in `KP_ADOPTION`. Each run takes each media type in turn; a media type
that fails a rule is refused (logged, exit 1) and nothing of it is written,
while the others go on:

1. A media type that has an adoption record but no entry is refused
   (`media_type_missing`): a mistake in the values must not refuse every
   submission. An entry that does not parse is refused (`bad_declaration`):
   `refresh` is required, and a cancellation (`version: none`) takes `refresh:
   none`.
2. A `declaration` not above the highest one applied for the media type is
   skipped when its version, refresh scope and withdrawn versions equal those of
   the record in effect (the highest `sequence`) and the withdrawn versions
   recorded; otherwise it is refused (`declaration_not_raised`). Comparing with
   the record in effect, not the older one of the same number, refuses values
   reverted whole. A pod that starts late with an older ConfigMap is refused
   too, so an alert counts consecutive refusals.
3. The rules (`version_withdrawn`, `withdrawn_removed`,
   `downgrade_undeclared`): a withdrawn version, declared or recorded, is never
   adopted; a recorded withdrawn version stays in the entry; a version lower than
   one of the same profile adopted before needs each such higher version in
   `withdrawn` or `kept`, so reverting the version line alone is refused.
   `kept` answers this check only and is not recorded: whether that version's
   documents are redone is the refresh scope's, and every later entry for the
   lower version repeats it.
4. The gate (`kp_admission.gate`), for a version, not a cancellation; until it
   passes the run writes nothing and the next one tries again (`waiting`):
   - The version's Worker Deployment has a current build polling all five
     queues, and its routing change is `COMPLETED`. A change still
     `IN_PROGRESS` ten minutes after the current build changed
     (temporalio/temporal#11842) passes on the rest of the gate, logged with
     reason `routing_in_progress`.
   - For a version not adopted through the gate before (a row of the local
     `adopt` command does not count): a test workflow of the version on that build
     returned `outcome: complete` with a well-formed `candidate` (§7.3; required
     from #81). Temporal reads a workflow `COMPLETED`
     whatever its outcome, so the gate reads its result. The CronJob starts it
     itself, with workflow ID `chk_` and 32 hex digits, a new `document_uid`
     each time, and the synthetic page shipped with admission
     (`kp_admission/check.pdf`), which it writes to the custody bucket under
     `checks/` when missing. A later run reads the result; a failed one is
     replaced by a new one ten minutes after it started (reason `check_failed`
     until then), since each costs model calls; one version has one at a time
     (`adoption_check`), except that two runs overlapping as one starts it may
     start a second. The log line of each start and failure names its
     `check_id`.
     Admission answers the test workflow's status reports `202` and records
     nothing. A version adopted before runs none: a rollback often happens while a
     model service is down.
5. One transaction locks the media type's latest adoption record, checks steps
   2 and 3 again (a pod that waited at the gate must not apply over a newer
   entry), then writes the adoption record with the next `sequence` of
   the deployment, its `declaration` and `refresh`, and the new withdrawn
   versions. A cancellation is a record with no version, cancelled when written.

A gate that cannot answer (Temporal or storage unreachable) leaves its media type
waiting with reason `gate_unavailable` and the run fails (exit 1); the next run
tries again.

Each run logs one line per media type (`media_type`, `declaration`, `version`,
`result`, `reason`) and records the result in `adoption_run` and
`adoption_status`, since the CronJob's pod is gone before any scrape. The `api`
measures them every 15 seconds: `kp_admission_adoption_runs` (runs by media type,
result and reason; it only rises), `kp_admission_adoption_status` (1 on each media
type's latest result and reason) and `kp_admission_adoption_status_seconds` (how
long that result has held, across changes of reason). Alerts on a refusal or a
long wait use these (#78).

`kp-admission adopt --tenant <tenant> [--refresh <scope>] <media_type>
<version>` and `kp-admission cancel-adoption --tenant <tenant> <media_type>
<version>` stay for local development and tests. Neither checks the gate or
the rules above, and `--refresh` defaults to `none`.

- Each adoption is a row with the next `sequence` of the deployment. A request
  copies its media type's `adopted_version` and that row's `sequence`, as its
  `adoption_sequence`, when it is made (§10), and keeps both: no later adoption
  or cancellation changes a request already made.
- The counter is deployment-wide, not kept per Source as the admission design
  record's R1a first wrote: in the pilot no Source pins a version, and
  current-revision selection compares the sequences of one document's requests
  only, for which a deployment-wide counter rises as a per-Source one would.
  When Sources select profiles, the count moves per Source.
- A media type's adopted version is the one of its highest `sequence`, unless
  that row is cancelled. Each applied entry is a new row, the same
  version with a new refresh scope included; the `adopt` command makes none
  for the version and scope already adopted. Rolling back from `N+1` to `N` is
  adopting `N` again, with `N+1` withdrawn or kept, which supersedes `N+1` with
  no gap. The refresh scope of the latest row of a Document's main-file media
  type is the one #98's scan reads.
- A cancellation leaves the media type without a version: it never falls back to
  an earlier one, whose workers may be retired. Adopting again makes a new row.
  A cancellation waits for the batch declarations and finalizations that read
  the row it supersedes; no request is made under that version after it commits.
- A request that names a version with no workers is not refused; it waits as
  backlog (profiles README, P1). Retiring a version therefore also waits until no
  queued or processing request names it.
- The record governs which version new requests run. Which accepted revision
  is a document's current one is Canonical Acceptance's selection (below).
- A main file whose media type has no adopted version is `UNSUPPORTED_FORMAT`,
  at declaration (§6.1 rule 2) and at finalization (§6.2 step 4).
- Before the first batch declaration, the values adopt `paper-pdf@1` for
  `application/pdf` and the CronJob has applied them.

**Canonical Acceptance** (#251, #57 scopes 2–4) is the commit of the
transaction that records a `process` request `succeeded`, when that transaction
records a Canonical Revision. Whichever of status intake (§7.3) and the
reconciler (§9) records the success first runs it, and both pass the run's
candidate (§7.3) into the same function. In that transaction, in order:

1. It serializes with every other transaction on the Document (finalization,
   deletion, another acceptance) before it touches the request. On PostgreSQL:
   the Document's row is locked, then the request's, and every transaction that
   ends a request takes them in this order, which #98 relies on. A request that
   has ended changes nothing.
2. The request becomes `succeeded`.
3. No acceptance forms when the Document is deleted (§8), the success carries
   no candidate, the candidate's `ref` is not the revision's own key (§7.3), or
   the request's `adopted_version` is among the withdrawn versions of its main
   file's media type at that moment. The Source Revision is not made
   `accepted`: it keeps the outcome the table above gives it, no
   Canonical Revision is recorded, the current one stays and no event is
   appended. Each reason is counted (`kp_admission_not_accepted_total`,
   `reason` `document_deleted`, `no_candidate`, `ref_mismatch` or
   `version_withdrawn`) and logged. The `ref` check exists because reads
   follow a revision's `ref`: a wrong or forged report must not point one
   Document's revision at another Document's object.
4. Otherwise the Canonical Revision is recorded and its Source Revision becomes
   `accepted`.
5. It becomes the Document's current Canonical Revision when the Document has
   none, or when it is of a Source Revision with a higher `sequence`, or of the
   same one under a higher `adoption_sequence`. A lower or equal candidate
   leaves the current one. Completion time does not count, so results that
   arrive in any order leave the same current revision. A new current revision
   is written with a `current_revision_changed` event (ADR-0009): `normal` when
   the revision it replaces was made by a withdrawn version (a canonical
   rollback), otherwise `background` for a platform refresh and `normal` for
   any other request (canonical consumption DR §3).

- A success writes the Document on every path, `acceptance_version` when it
  forms no acceptance or loses, so that on MongoDB a concurrent deletion
  conflicts with it (#239).
- Selection compares a candidate with the current revision only, once. That
  holds while nothing clears a current revision: the pilot has no governance
  withdrawal, and a failed redo after a withdrawn version keeps serving the
  revision it had (user, 2026-11-22). Adding withdrawal or invalidation changes
  this rule.
- A withdrawn version is never the adopted one: declarative adoption (#261)
  refuses to adopt it. Withdrawing takes no lock on the Document, so a result
  accepted just before the withdrawal stays, as every revision already current
  does; #98's scan redoes those Documents under the adopted version, and the
  result wins as a higher `adoption_sequence` of the same Source Revision.
- Canonical processing hands over candidates; it does not choose the current
  revision.

## 4. API conventions

- Base path `/v1`; snake_case JSON; RFC 3339 UTC times; AIP-158 pagination
  (`page_size`, `page_token`, `next_page_token`).
- Authentication: the Source credential (pilot service-account token, §2).
- Errors follow AIP-193:

```json
{
  "error": {
    "code": 409,
    "status": "FAILED_PRECONDITION",
    "message": "The batch expired at 2026-10-22T09:00:00Z.",
    "details": [
      { "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "BATCH_EXPIRED", "domain": "admission.knowledge-platform",
        "metadata": { "batch_id": "bat_01J…" } }
    ]
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

- `trace_id`: every request to the platform API has one, the internal authz
  API included. It is the trace id of the request's `traceparent` header (W3C
  Trace Context: 32 lowercase hexadecimal characters); when the header is
  absent or invalid, the platform generates one. A caller is not required to
  send the header. Every response returns the value in the `X-Trace-Id` header,
  and an error returns it in its body as well. The platform writes it on each
  log line and on every request record the call creates (§3), so one value
  joins the caller's log, the platform's log and the workflow. It is not
  `request_id`, which names one accepted processing or deletion request.
  W3C Trace Context defines no response header, so `X-Trace-Id` is the
  platform's own name. An `x-request-id` header is logged when present and is
  not part of this contract.
  [#204](https://github.com/davidlinnnn/data-ingestion/issues/204) builds the
  shared handling.
- Item errors inside results use `{ "reason": "…", "message": "…" }`.
- Protected things the caller cannot see return `404`; a missing permission of
  the caller's own credential returns `403` (Q3.7).

## 5. Endpoints

### 5.1 Declare: `POST /v1/batches`

Header `Idempotency-Key` (optional, recommended; at most 255 characters). A
repeat with the same key and body within 24 hours returns the stored response;
one with another body is `422 IDEMPOTENCY_KEY_REUSED`. A repeat that arrives
while the first is in progress returns the first's response once it commits;
until then it may get a `429` or `503` to retry. Body:

```json
{
  "items": [
    {
      "document_id": "hr:leave-policy",
      "source_version": "3",
      "title": "Leave policy",
      "source_url": "https://km.example/hr/leave-policy",
      "resources": ["hr-all"],
      "uploaded_by": "sso:user-1",
      "metadata": { "km_folder": "HR/Policies", "owner_team": "hr-ops" },
      "files": [
        { "path": "policy.pdf", "role": "main", "sha256": "9f2c…", "size": 18342, "media_type": "application/pdf" },
        { "path": "assets/flow.png", "role": "attachment", "sha256": "1ab0…", "size": 220114, "media_type": "image/png" }
      ]
    }
  ]
}
```

An item requires `document_id` and `files`, and a file all five of its fields.
`source_version` is required under `ordering: source_version` (§6.1 rule 3), and
`resources` for a new document of a Source without a default Resource (rule 5).
`title`, `source_url` and `metadata` are optional (§6.5). `uploaded_by` is
optional: the identity of the person who submitted the document, as the Source
asserts it. It is recorded with the item and is neither used for authorization
nor proof that the person acted (Q3.8).

Response `201`:

```json
{
  "batch_id": "bat_01J…",
  "state": "open",
  "expires_at": "2026-10-22T09:00:00Z",
  "items": [
    { "index": 0, "document_id": "hr:leave-policy", "document_uid": "doc_7f3…", "status": "declared",
      "uploads": [ { "path": "assets/flow.png", "method": "PUT", "url": "https://kp.example/v1/batches/bat_01J…/items/0/files/assets/flow.png" } ],
      "carried_over": ["policy.pdf"] }
  ]
}
```

Each `uploads[]` entry names the platform endpoint of §5.2 for one file; it is
valid until the batch is finalized or expires. `url` is an absolute URL on
the platform's public origin, the one Sources call (a deployment setting, not
the address a request reached), and `method` is `PUT`. A client uploads to the
`url` as returned and does not build it, sends its credential to that origin
only, and ignores response fields it does not know, so that a later version can
add one (API review of 2026-11-19, recorded in the
[design notes](knowledge-platform-admission.md#api-review-on-2026-11-19)).

A `resources` value is the Source's own key for a Resource it has registered
through the Resource API
([ADR-0013](../adr/0013-resource-identified-by-source-key.md),
[#114](https://github.com/davidlinnnn/data-ingestion/issues/114)). Under a
Source credential the key appears alone, in requests and in responses. The
platform's records hold the full identifier, which names the Source as well.

Item `status` after declaration:

| Status | Meaning |
|---|---|
| `declared` | Waiting for upload and finalization; `uploads` lists only changed files |
| `unchanged` | Content equals the latest Source Revision; catalog fields and metadata applied; final |
| `queued` | Same content with a request already active, or a retry after a platform failure; carries `request_id`; final for this batch |
| `rejected` | Carries `error`; final |

Later statuses: `expired` (never finalized), then for admitted items the
request's `queued`, `processing`, `succeeded` or `failed`.

Whole-request outcomes: `400` (malformed, `TOO_MANY_ITEMS`), `401`, `403`,
`422 ALL_ITEMS_REJECTED` (no batch is created; the body lists every item's
outcome in `items`, beside `error`), `422 IDEMPOTENCY_KEY_REUSED`,
`429 RATE_LIMITED`, `503 AUTHZ_UNAVAILABLE`, `503 ADMISSION_PAUSED`, `503`
while the database is unavailable. Every `429` and `503` carries `Retry-After`.

A batch in which no item is `declared` is created `finalized`.

### 5.2 Upload: `PUT /v1/batches/{batch_id}/items/{index}/files/{path}`

One request per file listed in the item's `uploads`, authenticated with the
Source credential like every other call; there is no separate upload grant.
`{path}` is the declared file path. `Content-Length` is required and must equal
the declared `size`; `Content-Type` may carry the declared `media_type`, and its
value is not checked (the platform checks the bytes, below). The body is the
file's bytes in one request:
no multipart form, no chunked encoding, no resumption.

The platform streams the body into storage, computing the SHA-256 and counting
bytes as it goes, and stops the transfer as soon as the bytes exceed the
declared `size`. The object appears, at its custody key (§10), only once its
size, SHA-256 and media type are verified. There is no separate staging store:
a staged file is one in place and not yet admitted. Outcomes:

| Outcome | Response |
|---|---|
| Bytes staged; size, SHA-256 and detected media type equal the declaration | `204` |
| `Content-Length` absent | `411 LENGTH_REQUIRED` |
| `Content-Length`, or the bytes received, differ from the declared `size` | `400 SIZE_MISMATCH`; nothing is staged |
| SHA-256 differs from the declaration | `422 DIGEST_MISMATCH`; nothing is staged |
| Detected media type differs from the declaration | `422 MEDIA_TYPE_MISMATCH`; nothing is staged |
| Storage or the database does not answer during the upload | `503 UNAVAILABLE` with `Retry-After`; the file may be staged or not; repeating the whole request is safe either way |
| Batch finalized | `409 BATCH_FINALIZED` |
| Batch expired | `409 BATCH_EXPIRED` |
| Unknown batch or item, or a path not in the item's `uploads` (carried-over files included) | `404` (a `{batch_id}` or `{index}` that is not one, `400 INVALID_ARGUMENT`) |

The platform detects the media types whose leading bytes have a fixed signature:
`application/pdf` (its header within the first 1024 bytes), `image/png`,
`image/jpeg`, `image/gif`, `image/webp` and `image/tiff`. A declared type that it
detects must be the detected one; a declared type that it cannot detect, such as
`text/markdown`, stands unless the bytes begin with a type it detects (user ruling of 2026-11-19,
[#194](https://github.com/davidlinnnn/data-ingestion/issues/194)). The main
file's media type selects the Processing Profile (§3), so an adopted main-file
format without a signature is routed by the Source's declaration.

A repeated `PUT` of the same path changes nothing: a staged file already holds
the declared bytes. Files of one item, and of different
items, may be uploaded in parallel. A client that loses the connection repeats
the whole request. Uploads are accepted until the batch is finalized or expires
(§11); staged files of rejected or expired items are deleted (§6.2).

Changed on 2026-11-07: this endpoint replaces the storage-native upload grant
(presigned URL or SAS) that company policy excluded on 2026-10-30. The reasons
and the options compared are in the
[document submission guide](knowledge-platform-file-upload.md).

### 5.3 Finalize: `POST /v1/batches/{batch_id}/finalize`

No body. Response `202` with the batch and every item, admitted items carrying
`request_id` and `source_revision_id`. Repeating it returns the same batch with
the same requests; item statuses follow their requests (§5.4).
`409 BATCH_EXPIRED` for an expired batch; `422 ALL_ITEMS_REJECTED` when every
item of the batch ends rejected (the batch is still finalized and no request is
created). `503 UNAVAILABLE` with `Retry-After` when storage cannot say whether
the files are in place (§6.2); the batch stays open and nothing changes. A pause
does not block finalization (Q10.1e).

### 5.4 Batch: `GET /v1/batches/{batch_id}`

```json
{
  "batch_id": "bat_01J…", "state": "finalized",
  "created_at": "…", "finalized_at": "…",
  "counts": { "succeeded": 1, "processing": 1, "unchanged": 1, "rejected": 1 },
  "items": [ { "index": 0, "document_id": "A", "status": "processing", "request_id": "req_…" } ],
  "next_page_token": ""
}
```

Item statuses follow the item's own request; a batch is history, not the
document's current state.

### 5.5 Request: `GET /v1/requests/{request_id}`

```json
{
  "request_id": "req_01J…", "kind": "process", "state": "failed",
  "document_id": "A", "document_uid": "doc_…", "source_revision_id": "srv_…",
  "initiator": "source", "retry_of": null, "batch_id": "bat_…",
  "created_at": "…", "updated_at": "…", "terminal_at": "…",
  "error": { "domain": "kp-canonicalization", "reason": "PASSWORD_REQUIRED", "message": "…", "retryable": false,
             "metadata": { "cause": "source", "category": "source" }, "support_ref": "temporal:req_01J…/…", "occurred_at": "…" },
  "trace_id": "…",
  "details": { "attempt_id": "…", "seq": 2, "stage": "prepare", "progress": null }
}
```

Process states: `queued`, `processing`, `succeeded` (processing completed;
Canonical Acceptance, when it forms, commits with it, §3), `failed`. Delete states: `received`, `applied`,
`enforced`; a delete request is recorded `applied` (§8). Visible immediately after `202`, before
any workflow exists.

- A `process` request becomes `processing` with the first report of its current
  attempt (§7.3), and ends with the failure, or success at the last registered
  stage, that a report or the reconciler records. `terminal_at` is the
  report's `observed_at`, or the workflow's close time when the reconciler
  records it. `error` is the error block as the reporter sent it, or the
  reconciler's `WORKFLOW_ENDED_WITHOUT_RESULT` (§12), except that a failure
  whose `metadata.cause` is not `source` carries the fixed English `message`
  "Processing failed for a platform reason; the platform owner is alerted.": a
  platform failure's own message can be an exception's text. Its `reason`,
  `domain` and `support_ref` stay, for the platform owner.
- A `succeeded` request forms no Canonical Acceptance when its Document was
  deleted, its success carried no candidate or a `ref` that is not its
  revision's key, or its Processing Profile version was withdrawn (§3). The
  Source then sees the request `succeeded` and the Document as before: its
  readiness and `serving` do not move to that Source Revision, and it has no
  attention. Such a request is one that is `succeeded` with no
  `canonical_revision` of its `request_id`; #98's scan runs it again, at once
  for a withdrawn version, once per adoption for a missing or wrong candidate,
  never for a deleted Document.
- `details` is where the current attempt last reported, `null` before any
  report; it is internal: do not use it for status decisions.
- A Source sees the requests of its own Documents, platform refreshes included;
  another Source's request is `404`. A request is `404` 30 days after its
  `terminal_at` (§11), a delete request 30 days after its deletion was applied
  (§8); an active `process` request never expires. The record stays: removal is
  not built. Requires the submit permission, as §5.6 and §5.7 do.

### 5.6 Document: `GET /v1/documents/{document_id}`

Returns the current generation (Q10.1f):

```json
{
  "document_id": "hr:leave-policy", "document_uid": "doc_7f3…",
  "resource_id": "hr-all", "title": "Leave policy", "source_url": "https://…",
  "metadata": { "km_folder": "HR/Policies" },
  "readiness": "ready_stale", "since": "2026-10-15T09:12:00Z",
  "latest": { "source_revision_id": "srv_3", "source_version": "3", "request_id": "req_…" },
  "serving": [
    { "projection": "retrieval", "state": "ready", "source_revision_id": "srv_2", "source_version": "2" },
    { "projection": "llm-wiki",  "state": "ready", "source_revision_id": "srv_2", "source_version": "2" }
  ],
  "attention": [
    { "kind": "source_revision_rejected", "action_owner": "source", "source_version": "3",
      "message": "PDF could not be parsed; fix and re-upload", "since": "2026-10-15T09:12:00Z" }
  ],
  "deleted_at": null,
  "details": null
}
```

- The current generation is the Document not deleted; when every generation of
  the `document_id` is deleted, the one deleted last, with readiness `deleted`.
  It is `404` 30 days after its deletion was applied (§11). Another Source's Document is `404`.
- `resource_id` is the Source's own key of the Resource (ADR-0013).
- `details` is internal: do not use it for status decisions. It is `null`
  except for a method-version lag of a Document not deleted, when the
  Processing Profile version that made the current Canonical Revision is not
  the one adopted now for the media type that version was adopted for (no lag
  while that media type has no adopted version):
  `{"method_version_lag": {"canonical_revision_id", "processing_profile_version",
  "adopted_version"}}`. A lag affects neither readiness nor attention.
- Readiness reads the projections' serving facts (§7.4); until a projection
  reports, which needs #127's reader deployed with the content read of #268, every
  Document not deleted is `not_ready`, so an application follows a submission
  by its request's `state` (§5.5).
- `latest` is the Source Revision that finalization created last
  (`document.latest_source_revision_id`), and `request_id` its newest request
  that is not a platform refresh. It is not the current Canonical Revision
  (§3).
- `serving` has a row per required projection whose serving Build includes the
  Document in its current Resource (§7.4): `state` is `building` while the
  projection does not count toward readiness (§7.1), else `ready` when it serves
  the latest Source Revision and `stale` when it serves an older one.
  `source_version` is the one that Source Revision carries when the response is
  made, so it follows a rewrite of §6.4. A projection that serves nothing has no
  row.
- `since` is when the Document took its readiness: `deleted_at` for `deleted`,
  otherwise the moment the platform last recorded a change of readiness (§7.4),
  its creation before any.
- `attention` follows §7.2. Each entry carries `kind`, `action_owner`,
  `source_version` (of the latest Source Revision), an English `message` and
  `since`; `processing_failed`, `progress_stalled`, `status_unverified` and
  `skipped` also carry `track`. For
  `source_revision_rejected` and `processing_failed` `since` is the request's
  `terminal_at`, and the message the error block's for the first and the fixed
  platform message of §5.5 for the second, when canonical processing raises
  them; for `progress_stalled` and `status_unverified` `since` is the deadline
  that passed. The projections' entries follow §7.2. A deleted Document has no attention.

### 5.7 List: `GET /v1/documents`

Optional filters `resource_id`, `readiness`, `projection`; paginated. Without
filters it lists all the Source's documents, including `deleted` ones still
within retention. Each entry carries `document_id`, `document_uid`,
`latest.source_version`, `readiness` and `metadata`. Applications reconcile
deletions with this list.

```json
{
  "documents": [
    { "document_id": "hr:leave-policy", "document_uid": "doc_7f3…",
      "latest": { "source_version": "3" }, "readiness": "not_ready",
      "metadata": { "km_folder": "HR/Policies" } }
  ],
  "next_page_token": "…"
}
```

- Entries are in `document_id` order, then `document_uid` (a deleted
  generation and the current one share a `document_id`). Deleted ones count
  while within 30 days of `deleted_at`.
- `resource_id` is the Source's own key. `projection` keeps the Documents whose
  `serving` lists that projection.
- AIP-158 pages: `page_size` 0 or above 1000 is 1000; a `page_token` is opaque,
  and one this list did not return is `400`. `readiness` and
  `projection` apply to each page after it is read, so a page may hold fewer
  entries than `page_size`, none even, while more follow. Read until
  `next_page_token` is empty; stopping at the first page can miss matches.

### 5.8 Delete: `DELETE /v1/documents/{document_id}`

`202` with `{ "request_id": "req_…", "kind": "delete", "state": "applied" }`.
Requires the submit permission. A repeated call returns the same request, in
its state then, while no later generation of the `document_id` exists and the
deleted one is visible (§11); after that, and for a `document_id` the Source
never had, `404`. Once the `document_id` is declared again, a call deletes that
new generation: a client that retries a timed-out deletion does so before it
declares the Document again. The delete request is `404` 30 days after the
deletion was applied, `enforced` or not. §8 describes the stages.

- The deletion is applied in the transaction that records it, so the call
  returns `applied`, and `received` is never observed. A client follows the
  request to `enforced` with `GET /v1/requests/{request_id}` (§5.5), and
  treats any state it does not know as not yet `enforced`.
- Changed on 2026-11-24 (#98): the response showed `received`. ADR-0014 left
  nothing between recording the deletion and applying it.

## 6. Admission rules

### 6.1 Declaration, per item, first failure wins

1. Structure: valid `document_id` (1–256 of `[A-Za-z0-9-_.~:]`) not declared by
   an earlier item of the same request, exactly one `main` file and every other
   file's `role` `attachment`, unique relative paths (no leading `/`, no empty
   or `..` segment), a 64-character hexadecimal `sha256` per file (stored in
   lowercase, as the key of §10 uses it), when present exactly one `resources`
   value, a `source_version` string holding a non-negative integer of at most 18
   digits or an RFC 3339 date-time with an offset, valid `metadata` (§11) →
   `INVALID_ARGUMENT`; every file's `size` within the maximum file size (§11) →
   `FILE_TOO_LARGE`.
2. Main-file format supported: its media type has an adopted Processing Profile
   version (§3; pilot: PDF) → `UNSUPPORTED_FORMAT`.
3. Under `ordering: source_version`, `source_version` present →
   `SOURCE_VERSION_REQUIRED`.
4. Existing document (same `document_id`, not deleted) with a different
   `resources` value → `BINDING_CONFLICT`. An omitted value keeps the binding.
5. Placement: the Source may place documents into the Resource (created by it,
   or granted) → `RESOURCE_NOT_FOUND`; a new document with neither `resources`
   nor a default → `RESOURCE_REQUIRED`. An unavailable decision service fails the
   whole request with `503`.
   Superseded on 2026-10-26 by
   [#55](https://github.com/davidlinnnn/data-ingestion/issues/55): in v1 a Source
   may place documents only into Resources it created; the contributor grant is
   deferred. See the
   [#55 design record](knowledge-platform-canonical-consumption.md).
   Since 2026-11-14 (ADR-0013) the Resource is named by the Source's own key,
   registered beforehand; an unregistered key is `RESOURCE_NOT_FOUND`.
6. Order against the latest Source Revision (§6.3) → `STALE_SOURCE_VERSION`,
   `VERSION_CONFLICT`, or `INVALID_ARGUMENT` for the other kind of
   `source_version`.
7. Same content (§6.4) → `queued` with the active request, a new retry request,
   or `unchanged`.
8. Otherwise `declared`, with an upload entry (§5.2) for each file whose (path,
   digest) differs from the latest Source Revision; the others are
   `carried_over` (Q10.1d), each with its `custody_ref` fixed here from that
   Source Revision. A new document's `document_uid` is generated here.

Results decided at declaration (`unchanged`, `queued`, `rejected`) are final;
requests they create are committed with their outbox rows before `201`.

### 6.2 Finalization, per `declared` item

1. Document deleted since declaration → `DOCUMENT_DELETED`; created since
   declaration by another batch, so that its `document_uid` is not the declared
   one → `STALE_DECLARATION` (declare again).
2. Placement re-check → `RESOURCE_NOT_FOUND`. An unavailable decision service
   fails the whole request with `503 AUTHZ_UNAVAILABLE`, as at declaration
   (§6.1 rule 5; authorization design §4.3).
3. Every file in `uploads` is in place: its object exists in storage, asked
   before the transaction (§5.2 verified size, digest and media type before the
   object appeared) → `FILES_MISSING`.
4. Format re-check: the media type still has an adopted version (§3) →
   `UNSUPPORTED_FORMAT`. Order re-check against the then-latest Source Revision → `STALE_SOURCE_VERSION`,
   `INVALID_ARGUMENT` (§6.3)
   or `VERSION_CONFLICT`; same content → §6.4.
5. Otherwise: create the document on first submission (with the declared `document_uid`),
   create the Source Revision, record each staged file's `custody_ref` (§10;
   a carried-over file keeps the reference fixed at declaration),
   apply catalog fields and metadata,
   create a `process` request and its outbox row.

All admitted items commit in one transaction before `202`. Finalization writes
nothing to storage, so that commit alone admits an item. The hourly
cleanup takes batches finalized or expired at least one hour before, so that
uploads in flight have ended. It deletes the objects uploaded by items that
created no Source Revision (rejected, expired, or resolved by §6.4) and aborts
every upload left incomplete under the batch's keys. Admission never deletes
the objects of an admitted item. A batch record is not removed (§11) before its
cleanup.

### 6.3 Ordering

| `ordering` | Rule |
|---|---|
| `source_version` | Integer or RFC 3339 time, one kind per document: the other kind than the latest Source Revision's is `INVALID_ARGUMENT`. Lower than the latest → `STALE_SOURCE_VERSION`, whatever the content. Equal or higher with equal content → §6.4. Equal with different content → accepted only if the latest Source Revision's outcome is `rejected` (Q10.1b), else `VERSION_CONFLICT`. Higher with different content → new Source Revision |
| `arrival` | Finalization order decides; equal content → §6.4 |

Content equality is equality of the set of (path, `sha256`) pairs. Equal bytes in
another document are never merged.

### 6.4 Same content as the latest Source Revision

| Latest Source Revision | Result |
|---|---|
| Has an active `process` request | `queued` with that request (Q10.1h) |
| Outcome `failed` (platform cause), its last failure retryable, and no active request | New `process` request for the same Source Revision: `initiator: source`, `retry_of` the last failed request, no upload, counted against quota |
| Any other outcome, a failure that is not retryable included | `unchanged` |

The last failure is the newest failed request of the Source Revision that is not
a platform refresh; it is retryable unless its `error.retryable` is `false`.
Added on 2026-11-24 (#98): a failure that is not retryable fails again under the
same Processing Profile version, so resending it opened a request that could
only fail. The scan (§9) runs it once under each later adoption. Such a resend,
and one of rejected content, costs no intake token: the declaration takes one per
item (§11) and returns it when the item is `unchanged` for either reason (#98,
R4 of the canonical persistence scenarios). A declaration with too few tokens is
still `429`, as the tokens are counted before any item is decided.

`title`, `source_url` and `metadata` apply in all three cases.

Under `ordering: source_version`, an item whose `source_version` is higher than
the latest Source Revision's records it as that Source Revision's
`source_version`, in all three cases, and creates no Source Revision. From then
on §6.3 orders later items against the recorded version, and a response shows it
wherever it shows that Source Revision's `source_version`: `latest` (§5.6,
§5.7), attention entries (they describe the latest Source Revision), and each
`serving` row of that Source Revision, read when the response is built. It only
grows: a lower
version is rejected before §6.4 (§6.3), and an item rejected for any reason
records nothing. Under `ordering: arrival` no version is recorded.

Added on 2026-11-20 (#258): §6.3 made a higher version a new Source Revision
whatever its content, so the same files under a higher version were processed
again. Neither the design record's Q6a (equal digests are `unchanged`) nor Q6b
(a newer version creates a Source Revision) ruled on this combination; for equal
content the design record's ruling of 2026-11-20 takes precedence over Q6b.

### 6.5 Catalog fields and Source Metadata

Submitted `title` and `source_url` replace the current values. `metadata` replaces
the whole map; omitted keeps it; `{}` clears it. None of them creates a Source
Revision. A rejected item applies nothing. Metadata is returned only to the
owning Source and never reaches projections, agents or filters.

Superseded on 2026-10-31 by
[#76](https://github.com/davidlinnnn/data-ingestion/issues/96#issuecomment-6542094987):
metadata is no longer returned to the Source only. The serving layer returns it
with the document to everyone who can read the document, so a Source puts
nothing there that its readers may not see. The storage rules above are
unchanged, and the platform still does not interpret or filter on it.

## 7. Status

### 7.1 Readiness

Required projections are the Source's current `projections`. Only serving within
the document's current Resource counts. First match:

| State | Condition |
|---|---|
| `deleted` | Source Deletion applied |
| `withdrawn` | Governance withdrawal of the document or its latest Source Revision (#56) |
| `not_ready` | Some required projection serves no revision, or the Source requires none |
| `ready_stale` | All serve a revision, at least one older than the latest |
| `ready` | All serve the latest Source Revision |

Platform refreshes (`initiator: platform`) affect neither readiness nor
attention, whatever their outcome (§7.2). A projection serves the Source
Revision of the `included` fact its serving Build holds for the Document in the
Document's current Resource (§7.4), and keeps serving it while it writes a
newer one over it; a fact in another Resource, a `pending` one over nothing, or
one in a Build not `serving` counts for nothing.

Superseded on 2026-10-26 by
[#55](https://github.com/davidlinnnn/data-ingestion/issues/55): the scalar
readiness counts only projections whose backfill for the Source has completed. A
newly added projection does not count until its owner reports "backfill of Source
S complete at `profile_seq` P"; until then the document keeps its previous
readiness. A projection of the Source's first Knowledge Profile counts at once,
as the #55 validation modelled it; one added later counts once its owner reports
the backfill at a `profile_seq` not before the one that added it (§7.4). The
value is computed over the projections that count, so a Document whose
required projections all wait for their backfill is `not_ready`. `serving[]` (§5.6) carries each projection's state: `ready`,
`building` or `stale`. See the
[#55 design record](knowledge-platform-canonical-consumption.md).

Not in the pilot (user ruling, 2026-11-18,
[#56](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6982506436)): the pilot (MVP) supports Source Deletion only and builds no
governance withdrawal or reinstatement. No withdrawal record exists, so
readiness `withdrawn` and the `withdrawn` attention of §7.2 never occur; both
stay in the contract for the release that adds withdrawal:
[#97](https://github.com/davidlinnnn/data-ingestion/issues/97) keeps the two
values and builds no rule that produces them, and #78 routes no `governance`
attention. To take a document out of serving during the pilot, its Source
deletes it; a deletion cannot be undone (§8).

### 7.2 Attention

| Kind | Action owner | When |
|---|---|---|
| `source_revision_rejected` | `source` | Canonical processing rejected the latest Source Revision (`cause: source`) |
| `processing_failed` | `platform` | Canonical (`track: canonical`) or a required projection (`track: <projection>`) failed for the latest Source Revision, retries exhausted, no active request |
| `progress_stalled` | `platform` | A pending or running attempt passed its deadline |
| `status_unverified` | `platform` | A required pipeline lost liveness |
| `skipped` | set by owner | A required projection skipped the document |
| `withdrawn` | `governance` | Governance withdrawal |

Method-version changes and failed platform refreshes affect neither readiness
nor attention; the owner is alerted (#78). `withdrawn` does not occur in the
pilot (§7.1).

Canonical processing's attention (#97) reads the latest Source Revision and its
newest request that is not a platform refresh:

- `source_revision_rejected`: the revision's outcome is `rejected` (§3).
- `processing_failed` with `track: canonical`: its outcome is `failed` and that
  request is not `queued` or `processing`. A failed report comes after
  canonical processing's own retries (#80 retries Activities, not workflows).
- `progress_stalled`: that request is `queued` or `processing` and dispatched,
  with no report within the canonical pipeline's `start_deadline_s` of its
  dispatch, or none within `update_interval_s` of its last report (§7.3). A
  request still in the outbox is admission's own backlog and is not stalled.

A required projection's attention (#252) reads only the current attempt, in
that projection's serving Build, for the Document's current Canonical Revision
(DR C4), so a failure in a Build still building, or a dropped result of an
older revision, raises none:

- `processing_failed` with `track: <projection>`: that attempt's last report is
  `failed` for the latest Source Revision, and the projection does not serve
  that revision. The message is the fixed platform message of §5.5.
- `skipped`: the same, with `skipped`. The action owner is `source` with the
  error block's message when its `metadata.cause` is `source`, else `platform`
  with the fixed message.
- `progress_stalled` with `track: <projection>`: that attempt's last report is
  `pending` with none after it within the pipeline's `start_deadline_s`, or
  `running`, or `succeeded` at a stage that is not the pipeline's last, with
  none within `update_interval_s`. A projection has no dispatch,
  so its first report starts the clock. Canonical processing's entry carries
  `track: canonical`.
- `status_unverified` with `track: <projection>`: the projection's serving Build
  has sent no report of any kind within the pipeline's `update_interval_s`.
  Liveness is a Build's, as it is a pipeline's (not a Document's) in the
  admission design.

`since` is the platform's time of that last report for the first two, the
deadline that passed for the others.

### 7.3 Reports

Admission, canonical processing and each projection report through the round-3
status reporting contract (registered pipeline IDs, attempt reports,
AIP-193-style error blocks, serving facts). #97 builds canonical processing's
reports; the projections' are §7.4's, with the same registration and the same
`seq` rule within one attempt.

**Registration.** A reporter calls with its own service credential, which
`KP_PIPELINES` registers: a JSON object from the credential's SHA-256 hex digest
to `{"pipeline_id", "track", "stages", "start_deadline_s", "update_interval_s"}`.
`track` is what its failures show under: `canonical`, or a projection's name,
the value of the Source's `projections` (§7.4). No two pipelines share a
track. Several digests may name one
`pipeline_id`, so a credential is rotated with an overlap, and they carry the
same registration; the `api` refuses to start otherwise. Without
`KP_PIPELINES` the `api` starts, every report is `401` and no attempt is
`progress_stalled`. `stages` is the ordered stage list;
the two deadlines decide `progress_stalled` (§7.2). Canonical processing
registers as `kp-canonicalization` with `prepare`, `parse`, `enrich`,
`finalize` and, provisionally until the cluster-tier runs (§13), 1800 seconds
for both: the PROD burst may wait 25 minutes, and `enrich` reports nothing
between its start and its end.

**Intake.** `POST /report/v1/requests/{request_id}/status-reports` on the
platform API, under its own prefix because `/v1/` is the Source-facing surface
an ingress exposes; a call without a registered pipeline credential is `401`,
and a pipeline whose track is not `canonical` is `403`. The body is the report
of #129, all twelve fields present: `request_id` (that of the path), `attempt_id`
(the Temporal run ID), `seq` (an integer from 1, per attempt), `stages_version`,
`stage` (a registered stage), `state` (`pending`, `running`, `succeeded`,
`failed`), `progress` (`{done, total, unit}` or `null`), `message`,
`method_version`, `manifest_ref` (or `null`), `observed_at` (RFC 3339 with a
zone) and `error`, the error block exactly when `state` is `failed`. A body that
breaks this is `400` and changes nothing; that check comes before the track's
`403`. `skipped` is a projection's state (§7.4). The error block is AIP-193-style: `domain`, `reason`, `message` and
`retryable` are required, `metadata` (string values), `support_ref` and
`occurred_at` optional; admission reads only
`metadata.cause` (§3) and does not interpret domains, reasons or stages beyond
the last one.

**Candidate.** A thirteenth field, `candidate`, may be left out or `null`, so a
worker that predates it is still taken: `{"ref", "sha256", "size"}`, the
Canonical content object of the run. `ref` is its object key without the bucket,
which the deployment sets: `documents/{document_uid}/revisions/{canonical_revision_id}.json`,
where `canonical_revision_id` is `crv_` and the request id's 32 hex digits
(#57 scopes 3 and 4); any other `ref` forms no acceptance (§3). `sha256` is
lowercase hex and `size` in bytes; any other key is `400`. Admission reads it from the
success at the last registered stage only, for Canonical Acceptance (§3). The
workflow's result carries the same object as `candidate` next to `"outcome":
"complete"`, which the reconciler reads; a malformed one there counts as none.
The last registered stage stays `finalize`: mapping is not a fifth stage,
because old and new versions run side by side during an upgrade and a
different stage count would end a request too early or never.

**Current attempt.** Run IDs cannot be ordered, so reports are ordered within
one attempt only. The dispatcher records the run it started as the request's
`attempt_id`, from the start's answer, or from an already-started error's run
when the workflow exists (§9); the reconciler clears it when it sends a lost
workflow back to the outbox. Only the current attempt's reports count:

| Report | Answer |
|---|---|
| The current attempt's, `seq` above the last one taken (gaps are fine) | `202`; taken |
| The same as the last one taken, a resend | `200`; nothing changes |
| The current attempt's, any other report: a lower `seq`, or the last `seq` with another body | `409` with `{"attempt_id", "seq"}`, the current attempt and its last `seq` |
| Another attempt's | `409` with the current position (`seq` 0 before any report); not stored |
| Before the dispatcher has recorded the attempt | `503` `ATTEMPT_NOT_RECORDED` with `Retry-After`: the sender retries within its report budget |
| A request that does not exist or is not a `process` request | `404`; `202`, recording nothing, for a request ID that starts with `chk_` (the adoption gate's test workflow, §3) |

The `409` body is the bare position the sender reads, not an AIP-193 error; its
trace id is in `X-Trace-Id`. A `503` `ATTEMPT_NOT_RECORDED` is the normal race
with the dispatcher's commit and needs no alert.

The first report taken moves a `queued` request to `processing`; a `failed`
report, or a `succeeded` one at the last registered stage, ends it (§3, §5.5).
This rests on admission making every run: canonical processing uses no
workflow-level retry, and operators do not reset its workflows. A run made
outside admission, such as by a manual reset, is not the current attempt: its
reports are `409` and the request turns `progress_stalled`, while the
reconciler, which follows the workflow ID, still records its outcome when it
ends. No command records such a run; one is added when a reset becomes an
operator procedure.

Superseded on 2026-10-26 by
[#55](https://github.com/davidlinnnn/data-ingestion/issues/55): instead of a full
inclusion list per product version, projections report per-commit deltas of
inclusion facts keyed by (projection, Build, `document_uid`, `resource_id`) with a
Build-wide monotonic `fact_version`, plus repair snapshots on request. See the
[#55 design record](knowledge-platform-canonical-consumption.md).

### 7.4 Projection reports

A projection reports to the platform over HTTP, under the protocol of the
[#55 design record](knowledge-platform-canonical-consumption.md) (DR) §4 and §5:
the state of each of its Builds, its serving facts, a heartbeat per Build, its
attempts, and the completion of each Source's backfill. The platform keeps them
per projection, platform-wide like its feed cursor: a Build serves every tenant.
They are the mirror that readiness (§7.1), attention (§7.2) and Source
Deletion's judgment (#98) read. The pilot deployment holds one tenant, so a
Source is named by its `source_id` alone here until a deployment holds two.

**Identity.** A projection calls with its service credential, registered twice
under its name (DR C1): in `KP_AUTHZ_PEP_CREDENTIALS`, to read the Change Feed,
and in `KP_PIPELINES` (§7.3) with that name as its `track`. Its pipeline's two
deadlines decide its `progress_stalled` and `status_unverified`. A call without
a registered pipeline credential is `401`; canonical processing's is `403`. A
body that breaks the shapes below is `400` and changes nothing. A Build exists
once the projection reported its state; its other routes are `404` before.

| Route under `/report/v1/` | Body | Answers |
|---|---|---|
| `PUT builds/{build_id}` | the Build's state (below) | `200` `{"state", "repair_requested"}`; `409` `GATE_FAILED`, `BUILD_STATE` |
| `POST builds/{build_id}/registrations` | `{"facts": [...]}`, each to become `pending` | `200` `{"repair_requested"}`; `409` `SUPERSEDED`, `FENCED`, `BUILD_STATE` |
| `POST builds/{build_id}/facts` | `{"facts": [...]}`, each with `state` `included` or `removed` | `200` `{"fenced", "repair_requested"}`; `409` `BUILD_STATE` |
| `POST builds/{build_id}/heartbeats` | `{"count", "digest"}` | `200` `{"repair_requested"}`; `409` `BUILD_STATE` |
| `PUT builds/{build_id}/repair-views/{view_id}/pages/{page}` | a page of a repair view (below) | `200` `{"view", "repair_requested"}`; `409` `VIEW_DISCARDED`, `BUILD_STATE` |
| `POST builds/{build_id}/status-reports` | an attempt report (below) | `202` taken, `200` a resend, `409` `{"attempt_no", "seq"}` or `BUILD_STATE` |
| `PUT sources/{source_id}/backfill` | `{"profile_seq"}` | `204`; `404` for a Source without a Knowledge Profile; `400` for a `profile_seq` after the Source's |

A refusal is an AIP-193 error whose ErrorInfo `metadata` names what failed:
`{"gate"}`, `{"state"}`, `{"document_uid"}` or `{"reason"}`. The `409` of a status report is
the bare position, as in §7.3, except to a retired Build, where it is the
`BUILD_STATE` error: a client tells the two apart by the `error` member.

**Builds.** `build_id` is the owner's, unique within the projection. Its first
report creates the Build as `building`. A Build switches to `serving` by a
report that carries `switch_seq`, a number above every earlier switch of the
projection; `replaces`, the Build serving now (`null` when none serves); and
`feed_position`, the Change Feed position the Build has read to; with the
owner's `approval_ref` and `evidence_ref` (DR D2). The platform re-runs the
gates in this order and refuses the switch with the first that fails:
`replaces` names another Build than the one serving; `caught_up`, the oldest
feed entry after `feed_position` has waited more than 300 seconds (provisional
until #127 measures a reader); `coverage`, it serves fewer Documents than the
Build it replaces, counting on both sides the `included` facts and the
`pending` ones written over a revision still served (§7.1);
`removed_documents`, an `included` or `pending` fact of
a Document deleted, unknown, or bound to another Resource than the fact's. A
`feed_position` the feed has not reached is `400`, as a malformed one is; it
is read after `replaces` passed, and not at all for a late switch. A switch that
passes makes the replaced Build `retained` in the same step, so one Build of a
projection serves: of two switches sent at once the later fails `replaces`. A `serving` report
numbered at or below the last switch came late and changes nothing; its answer
carries the Build's state. A `retained` Build switches back by the same report,
which is a rollback (DR D2). `retired` is the owner's report that the Build's
data is gone (DR §4) and is final: every later registration, fact, heartbeat,
repair view page and status report to it is `409` `BUILD_STATE`. A Build reported in the state it is in
answers `200` with its state unchanged; a repeated `serving` or `retired`
report runs the recompute of readiness again (below), so it is a retry, not a
keepalive. Any other step, such as back to
`building`, is `409` `BUILD_STATE` with the state the Build is in.

**Facts.** A fact carries `document_uid`, `resource_id` (the full identifier the
Document state read answers), `source_revision_id`, `canonical_revision_id`,
`fact_version` (an integer from 1, monotonic within the Build, gaps allowed)
and `issued_at` (RFC 3339 with a zone: when the projection first created this
report, which the fence reads). A call carries 1 to 1000 facts. `build_id` is
at most 128 characters, `document_uid` and the revision IDs 64, `resource_id`
512.

- A registration records every fact as `pending`, or none, after the B5 check
  in the same transaction (DR §5.2, K1): each Document exists, is not deleted,
  is bound to the fact's Resource, and has the fact's Source Revision and
  Canonical Revision as its current ones (#251 records them). It locks the
  Documents in `document_id` order, as declaration and finalization do, and
  holds them until it commits, so Source Deletion's judgment, which locks the
  Document, comes before it or sees the `pending` fact. A failed check is `409`
  `SUPERSEDED` naming the first Document that failed: the projection drops the
  result and does not write. When that answer came to a registration sent
  more than once, an earlier send may have been recorded, so the projection
  then reports each key as for an abandoned write. A projection that abandons a registered write
  reports, with a new `fact_version`, what its store holds for the key:
  `included` with the revisions still stored, or `removed` when it holds
  nothing. A registration resent, or any fact whose `fact_version` is not
  above the one held, answers `200` and records nothing. A registration over
  an `included` fact keeps that fact's Source Revision as the one served until
  the write is confirmed, so the Document keeps counting as served while it is
  written, `ready_stale` when the write is of a newer Source Revision, and
  does not turn `not_ready` (user ruling, 2026-11-22); the fact is
  `pending` for every other reader, Source Deletion's judgment included.
- `included` and `removed` facts are taken one by one: the highest
  `fact_version` of a key, (Build, `document_uid`, `resource_id`), is kept, and an
  older one answers `200` and changes nothing.
- A `removed` fact is a tombstone kept 30 days. After that it counts as no
  fact, except that it stops a report at or below its version issued before it
  expired (DR §5.3). A stopped fact is listed in `fenced`, the other facts of
  the call are taken, and a repair is requested; a fenced registration is `409`
  `FENCED` and records nothing. A fenced fact is not sent again. Tombstones
  stay in the database after their 30 days, as do the facts and attempts of
  a retired Build and the attempts of earlier Canonical Revisions; their
  removal is #264, after the pilot. A repair gives each live tombstone it
  writes a fresh 30 days and leaves an expired one as it is (Repair views); an
  expired one fences only reports issued, and views captured, before it
  expired, but a report's `issued_at` has no age limit the platform enforces.

**Repairs and heartbeats.** Every `200` of a Build's state, registration, fact,
heartbeat or repair view report carries `repair_requested`: `null`, or `{"reason", "requested_at"}` while the platform
asks for a repair view of the Build. Reasons: `heartbeat_mismatch`,
`pending_expired`, `fenced`, `view_expired`, `view_fenced` (below) and
`writes_lost` (Lost writes, below). The request stays until a repair view is
installed; until then it
is information for the owner and refuses no report, and it shows the first
reason: a later one does not replace it, except `writes_lost`, which replaces
any other. The owner computes a heartbeat with
no report of the Build in flight; a report still on its way is a mismatch. A heartbeat carries `count` and `digest` over the
Build's store entries plus its unfinished registrations, a registration winning
for a key with both (DR §5.5). `digest` is 64 lowercase hex digits: the XOR of
the SHA-256 of each entry's `document_uid`, `resource_id` and
`canonical_revision_id` joined by the byte 0x1F, UTF-8; all zeros for none. The
platform computes the same over the Build's `included` and `pending` facts, and
requests a repair when either differs, or when a `pending` fact is older than
`PENDING_MAX`: 30 minutes, provisional until #127 measures a store write. It
must exceed the longest write, a liveness pause included.

**Repair views.** A repair view is the Build's whole state captured at one
moment (DR §5.4): every store entry as `included` and every registration whose
write has not completed as `pending`, a key with both listed both ways. The
owner may send one at any time; it sends one when `repair_requested` is set
and no view of the Build is in transfer, and before it reports a Build `serving`
(DR §5.4, review m8), which the platform does not check. A request is answered
by the view in transfer, except `writes_lost` (Lost writes, below): an owner
captures again only after a `409` `VIEW_DISCARDED` other than `superseded`. It sends the view in pages numbered from 1. Each page carries
the view's `captured_at` (RFC 3339 with a zone, by a clock within a minute of
the platform's), `watermark` (the highest `fact_version`
allocated in the Build at capture, 0 for none), `pages` (how many pages the view
has) and `entries`, 0 to 1000 of them. An entry carries `document_uid`,
`resource_id`, `state` (`included` or `pending`), `source_revision_id`,
`canonical_revision_id` and `fact_version`, the version last reported for the
entry, at most `watermark`. `view_id` is the owner's, at most 64 characters,
and names one capture. A page is `400` when it states another `captured_at`,
`watermark` or `pages` than the first page the platform took of the view, when
its `page` is above `pages`, or when its `captured_at` is more than a minute
ahead of the platform's clock.

- A Build has at most one view in transfer. A view captured after the Build's
  last one starts and ends any other in transfer. A page of a view captured at
  or before the last one is `409` `VIEW_DISCARDED`: `writes_lost` while a
  `writes_lost` request stands and no later view is in transfer, which asks for
  a fresh view (Lost writes, below); `superseded` otherwise, which asks for
  nothing.
- Pages arrive in any order and any number of times. The answer's `view` is
  `incomplete` until every page has arrived, then `installed`; a page of the
  installed view sent again answers `installed` and runs the recompute of
  readiness again.
- A view must be complete within 24 hours of `captured_at` (provisional until
  #127 measures a transfer; below the tombstones' 30 days). After that the
  view is discarded, by its next page, which answers `409` `VIEW_DISCARDED`
  `expired`, or by the Build's next registration, fact, heartbeat or status
  report, and a repair is
  requested, `view_expired`. The owner keeps its report retries within the same
  24 hours, from the report's `issued_at`, and then sends a repair view instead.
- When the last page arrives, each key's entry passes the expiry fence with its
  own `fact_version`, the view's `captured_at` standing for `issued_at`; for a
  key listed both ways, its `pending` entry. If any entry is stopped, the whole
  view is discarded: `409` `VIEW_DISCARDED` `fenced`, and a repair is
  requested, `view_fenced`.
- Otherwise the platform replaces the Build's mirror in one step, which a query
  sees before or after, never in part: a fact above `watermark` was reported
  after the capture and stays; every other key of the view takes the view's
  state and revisions; every other key the view lacks becomes `removed`, a
  tombstone of 30 days from now, except a tombstone already expired, which stays
  as it is and fences as before. Each written fact takes `watermark` as its
  `fact_version`, and a written `pending` fact's age toward `PENDING_MAX`
  starts at the install. A key listed both ways is `pending`, and the Source
  Revision of its `included` entry is the one it still serves. The repair
  request ends, and readiness is recomputed for every Document the Build holds
  a fact of.
- A discarded view's pages answer `409` `VIEW_DISCARDED` with the same reason
  when sent again. The owner then captures a fresh view, under a new `view_id`.

**Lost writes.** When the admission database loses committed writes (a
restore, a point-in-time restore, or a failover that loses commits; DR §5.6,
K2), operations declare it with `kp-admission writes-lost EVENT`, run by a Job
of the deployment repo once the api takes reports again: the window for erased
Builds, below, counts from the declaration. Until the Job has run, the
restored database carries no sign of the loss, so the runbook keeps Source
Deletion's judgment from running (for example, its CronJob stays suspended)
from the restore until the Job ends; where the Job falls among the restore's
other steps, such as reopening the read surface ([#57 scope 7](https://github.com/davidlinnnn/data-ingestion/issues/78#issuecomment-7086864591)),
is #78's runbook too. `EVENT` is a number from 1, above every earlier
declaration's, kept in the deployment repo (the database's own record of it may
be among the lost writes). The last declaration applied, run again, changes
nothing and exits 0; one with a lower number changes nothing and exits 1, and
an `EVENT` that is not a number from 1 exits 2. It
prints `{"applied", "builds"}`, whether it applied and how many Builds it asked,
and its log lines; the runbook checks `"applied": true` on its first run. The
gauge `kp_serving_builds_writes_lost` counts, per projection, the Builds still
asked; with two api pods each reports it, so it is read with `max`.

- It asks every Build not retired for a repair, `writes_lost`, and discards the
  Build's last view, in transfer or installed: that view's pages answer `409`
  `VIEW_DISCARDED` `writes_lost`, and so does a view captured at or before the
  declaration, by the platform's clock. A `writes_lost` request is answered only
  by a view captured after the declaration; every other request is answered by
  the view in transfer.
- The loss can erase Builds and reports. A Build first reported within its
  pipeline's `update_interval_s` after the declaration may be one it erased: it
  starts with a `writes_lost` request and refuses views captured at or before
  the declaration, as the Builds the declaration asked. An owner that reads a
  `writes_lost` request, or a `404` for a Build it reported, puts its Builds
  back in this order: it reports `building` each Build the platform no longer
  knows; it sends each Build it holds and has not retired a view; it sends
  again, in `switch_seq` order, each switch the platform does not show, with a
  `feed_position` read after its cursor was rewound (#78), and retries one that
  answers `400` or `GATE_FAILED` once it has caught up; only then it reports
  `retired` each Build retired since the restore point, so a switch sent again
  still names in `replaces` the Build the platform serves. It reports its
  backfill completions again.
- Source Deletion's judgment stays suspended until no Build not retired carries
  `writes_lost`, and for at least the longest `update_interval_s` of the
  registered projections' pipelines after the declaration, so an owner whose
  Builds were erased has reported them again (#98). A projection leaves
  `KP_PIPELINES` only once its Builds are retired (Liveness, below); a Build of
  one that left keeps the suspension until it is retired. Which events trigger
  the declaration, and the feed, cursor and block rewinds that come with it, are
  #78's runbook.

**Attempts.** A projection's attempt is for one unit: (Build, `document_uid`,
`canonical_revision_id`) (DR C4). Its report carries the fields of §7.3 without
`request_id`, plus `document_uid`, `source_revision_id`,
`canonical_revision_id` and `attempt_no`, a number the projection allocates
durably per unit and only increases. The highest `attempt_no` of a unit is its
current attempt; within it the `seq` rule of §7.3 holds (`202` taken, `200` a
resend, `409` with the position), and a lower `attempt_no` is `409` with the
current position. `attempt_id` is the owner's name of the run, such as its
workflow run ID; the platform keeps it and orders nothing by it. `state` also takes
`skipped`, and the error block is present exactly when the state is `failed`
or `skipped`. A dropped result (B5) is `failed` with the owner's reason, such
as `SUPERSEDED`, which the platform does not interpret.

**Backfill.** The platform records the `profile_seq` at which each projection
joined the Source's Knowledge Profile, none for those of its first one. The
owner reports a Source's backfill complete with the `profile_seq` it read; an
earlier one than recorded changes nothing. A projection counts toward the
Source's readiness once its report is at or after the `profile_seq` that added
it (§7.1).

**Readiness changes.** The platform stores each Document's readiness and the
moment it last changed, which is `since` (§5.6). It recomputes them after the
calls that can change them: a fact report, a Build switch or retirement, or an
installed repair view (for every Document the Builds hold a fact of), a backfill report and a Knowledge
Profile change (for the Source's Documents), finalization (for its Documents),
and a rebind (#205 calls the platform's recompute for the Documents it moves). Each Document in a transaction of its own, so a large
fan-out holds no long transaction: the database ends one at 60 seconds. The
recompute follows the report's own commit, so a call that ends in an error or
no answer is sent again: every report here is safe to resend, and the resend
finishes the recompute. An owner resends for at most 24 hours, then sends a
repair view instead (Repair views, above). The
recompute after a Build's state report, a backfill report or an installed
repair view, a heartbeat's comparison, and a repair view's replacement of the
mirror, run inside the call and grow with the Build or the Source. The
replacement is one transaction, which the database ends at 60 seconds, or at
30 seconds idle while the platform merges the view: a Build
too large for it never installs a view, and resending repeats the same
transaction; after lost writes that keeps Source Deletion's judgment suspended.
The sign is repair requests with no `kp_serving_repair_seconds` observation and
`503` answers to the view's last page (#99 measures it). Their duration is not measured: #99 measures it, and until then a
caller allows for a call that outlasts its timeout and resends. The
reports of one Build are taken one at a time. The readiness a query answers is
computed when it answers; only `since` comes from the stored moment.

**Liveness.** A Build's liveness signal is its last report taken, of any kind
(a refused one does not count, except a `FENCED` registration, a status
report's `409` and a `VIEW_DISCARDED` page), so each
Build not retired, `building` and `retained` ones too, reports at least a
heartbeat more often than its pipeline's `update_interval_s`, and a candidate
its owner gives up is reported `retired` once its data is gone. A Build not
retired with no report within that interval has lost liveness: the gauge `kp_serving_builds_without_liveness` counts them per
projection, a serving one shows `status_unverified` (§7.2), and Source
Deletion's judgment pauses while any exists (DR §5.6, #98). The interval is
the registered pipeline's, so a projection stays in `KP_PIPELINES` until its
Builds are retired (DR D1); a Build of one that left is not measured.

**Logs and metrics.** Each report's log line carries `projection` and
`build_id` (a backfill's carries `source_id` in its place), and as they apply
`document_uid`, `resource_id`, `fact_version`, `state`, `attempt_no`, `seq`,
`stage`, `result`, `reason` (a gate, an error block's reason, a repair's
reason) and a call's counts (`count`, `results`, `late_landings`); a repair view's page
also `view_id`, `page`, `pages` and `watermark`;
never an error message. Metrics: `kp_api_calls_total` by operation and status
(§7.3); `kp_serving_facts_total` by `projection` and `result` (`recorded`,
`older`, `fenced`, `superseded`); `kp_serving_repairs_requested_total` by
`projection` and `reason`; `kp_serving_repair_views_total` by `projection` and
`result` (`incomplete`, `installed`, `resent`, `expired`, `fenced`,
`discarded`, `superseded`); `kp_serving_repair_seconds`, a histogram by
`projection` of the time from a repair request to the installed view that
ended it (DR §9's repair latency); `kp_serving_late_landings_total` by `projection`, an
`included` fact report recorded for a deleted Document (DR §9; a repair view
is not counted); the gauge `kp_serving_builds_writes_lost` (Lost writes); and
the gauge above.

## 8. Source Deletion

| Stage | Meaning | Who | Target |
|---|---|---|---|
| `received` | Durable fact committed, `202` returned (the pilot records `applied` in the same transaction, §5.8) | #31 | Same call |
| `applied` | Agents can no longer find, read or cite the document's own content; readiness `deleted` | Serving-time block keyed by `document_uid` (#56, #76), recorded by #31 | 1 minute, *unmeasured* |
| `enforced` | Every required projection has removed the document and adjusted products derived from it (for example LLM-wiki pages) | Projection owners via #55; judged by #31 from their reports and serving facts | 10 minutes, *unmeasured* |

- Superseded on 2026-11-15 by [ADR-0014](../adr/0014-removal-by-projection-cleanup.md):
  there is no serving-time block in v1. `applied` means that admission has
  recorded the deletion: the status shows `deleted`, the catalog fields are
  cleared and the event is in the Change Feed. Content stops being served when
  the projections have removed it, which is `enforced`; until then agents may
  still find it. This replaces "Agents can no longer find, read or cite the
  document's own content" and "Serving-time block keyed by `document_uid`" in
  the `applied` row above. The same holds for a withdrawal and a rebind.
- The deletion reaches projections through the #55 handoff channel, carrying
  `document_uid`; each projection reports when it has finished.
  Superseded on 2026-10-26 by
  [#55](https://github.com/davidlinnnn/data-ingestion/issues/55): a document is
  `enforced` when no non-retired Build of any projection holds an included or
  pending serving fact for it; there is no per-projection completion report and
  no `delete_request_id` sent to projections. This also replaces "Every required projection"
  and "from their reports" in the `enforced` row above. See the
  [#55 design record](knowledge-platform-canonical-consumption.md).
- When deletion is applied, `title`, `source_url` and `metadata` are cleared;
  the `deleted` record keeps only identifiers, times and request IDs.
- Items of earlier batches finalized after `applied` → `DOCUMENT_DELETED`.
- A result arriving later ends its request but forms no Canonical Acceptance
  (§3), so it never restores the document; publishing a deleted document is
  ignored.
- A new submission of the same `document_id` after `applied` creates a new
  `document_uid`.
- The deleted generation is visible for 30 days (its delete request and
  `GET /v1/documents?readiness=deleted`), then `404`. Custody and derived data
  are purged at the same point (#57, #56).
- v1 offers no application-triggered immediate purge. For a security incident
  the application deletes the document and the security team requests an
  immediate purge through the #56 governance path.

How the pilot does it (#98):

- **`applied`, in the call.** One transaction locks the live Document, records
  the delete request `applied`, sets `deleted_at` (the time a Custody Purge,
  #267, counts from) and `delete_request_id`, clears `title`, `source_url` and
  `metadata`, and appends a `document_deleted` event of priority `narrowing`.
  It also ends each `process` request of the Document that no dispatcher has
  started: `failed`, `DOCUMENT_DELETED`, whose `cause` is `source`, so its
  message is shown. A request already started runs on and forms no acceptance
  (§3). A request whose outbox row a dispatcher holds at that moment counts as
  started; when that start fails, the dispatcher ends it the same way when it is
  next due.
- **`enforced`, by a CronJob.** `kp-admission enforce` runs every minute. For
  each applied deletion it locks the Document, as registration does (§7.4), and
  reads the facts that Builds not retired hold of it. With no `included` or
  `pending` fact left, the request becomes `enforced`, and `terminal_at` is that
  time. A registration either committed its `pending` fact before this read, or
  it finds the Document deleted and is refused (`409 SUPERSEDED`).
- **No judgment** while any Build not retired lacks liveness (§7.4), while
  `writes_unrepaired` lists a Build, or until the longest `update_interval_s`
  of the projection pipelines has passed since the last lost-writes
  declaration (§7.4, Lost writes). The run then judges none and says why. The
  deployment repo stops the CronJob from a database restore until the
  `writes-lost` Job has run (#78). The CronJob reads the `api`'s
  `KP_PIPELINES` and exits 2 when it names no pipeline: with none, no silent
  Build could suspend the judgment.
- **Alerting.** `kp_admission_deletions_unenforced{reason}` counts the
  deletions applied more than 10 minutes ago and not yet `enforced`: `held`
  (a Build still holds the Document), `liveness` or `writes_lost` (the judgment
  is suspended). Each held deletion past that time is logged with the
  projections and Builds that hold it. The CronJob writes the value to the
  database, and the `api` exports it, as with the adoption gauges (§3). While the
  CronJob does not run, the value is stale; a rule on
  `kp_admission_job_last_run_timestamp_seconds{job="enforce"}` (§9) shows it.
- **Measured** on 2026-11-24 (`docs/validation/98`): `applied` within 35 ms of
  1000 calls; one `enforce` run judged 1001 deletions in 0.8 s. The projections'
  share of `enforced` is not measured yet (#127).
- **Rebind.** No move between Resources exists in the pilot, so there is no
  move-out to judge. The rule for it is C3's: complete when no fact names the
  old Resource (`serving.held`).

## 9. Dispatch and durability

- The request and its outbox row commit in one transaction before `201` or
  `202`.
- Dispatchers (at least two) claim outbox rows with `FOR UPDATE SKIP LOCKED`,
  apply global and per-Source in-flight budgets with fair rotation and
  priority, and start the workflow with workflow ID = `request_id` and
  `REJECT_DUPLICATE`; `WorkflowExecutionAlreadyStarted` counts as success.
  In the transaction that marks the row dispatched, the started run, or the run
  already under that workflow ID, becomes the request's current attempt (§7.3).
  During a Temporal outage rows wait and retry with backoff.
- The reconciler (every 5 minutes) checks dispatched requests without a terminal
  outcome: running → left alone; closed → outcome recorded (§3); missing →
  re-dispatched with the same ID, the reason recorded and the current attempt
  cleared.
- A request of a withdrawn version (§3) does not wait for a result that would be
  discarded. A dispatcher that claims a queued one ends it, `failed` with
  `VERSION_WITHDRAWN`, and takes it out of the outbox. The reconciler
  terminates a running workflow of one and records the same. Neither changes the
  Source Revision's outcome, so the scan reruns it at once.
- **The scan** (`kp-admission scan`, a CronJob every 5 minutes, #98) reruns,
  refreshes and redoes Documents under the version adopted for their main
  file's media type. It replaces the redrive command and the refresh opened at
  each adoption (#57, 2026-11-22: nobody runs commands in a PROD pod). It skips
  a Document that is deleted, has an active request, or has no adopted version
  or a withdrawn one.
  For the others the first rule that holds decides:

  | # | The Document | The scan opens |
  |---|---|---|
  | 1 | The latest Source Revision's Canonical Revision is current, and the adopted version made it | Nothing |
  | 2 | It is current, another version made it, that version is withdrawn or in the latest adoption's refresh scope, and the latest Source Revision may be reopened | A request for it: `initiator: platform`, `low` |
  | 3 | The latest Source Revision has no Canonical Revision and may be reopened | A request for it: `initiator: operator`, `normal`, whatever the scope |
  | 4 | As 3 but it may not be reopened; the current revision, of an earlier Source Revision whose main file has the same media type, is a withdrawn version's or in the scope; that Source Revision may be reopened | A request for that Source Revision: `initiator: platform`, `low` |
  | 5 | Otherwise | Nothing; the current revision, if any, is still served |

  Whether a Source Revision may be reopened follows from the last request of it
  under the latest adoption, whoever made it. No state is kept besides the
  requests:

  | That request | Reopened |
  |---|---|
  | None | Yes |
  | Failed, retryable | When the interval since it ended has passed: 10 minutes after the first retryable failure in a row, 20 after the second, 40 after the third, 1 hour after each later one, with no count that stops it |
  | Failed with `VERSION_WITHDRAWN` | Yes, at once |
  | Failed, not retryable; rejected (`cause` `source`); succeeded with no Canonical Revision | Not before the next adoption |

  - The version that made the current revision is the Document's
    `current_adopted_version`. A withdrawn version's revisions are redone
    whatever a later scope says, until no Document is served by one. A scope of
    `none` stops refreshes only.
  - A run opens rule 3 first, then the redos of withdrawn versions, then
    refreshes, while fewer than 500 of the scan's requests wait for a
    dispatcher. The dispatcher's in-flight budgets then pace them; within one
    priority it takes the Source with the fewest in flight, then the oldest. A
    redo and a refresh are both `low`, so no refresh opens while a redo of a
    withdrawn version is planned or has not ended (ADR-0016: redos go first).
    Refreshes already queued when a version is withdrawn are not held back.
  - Every run reads each live Document, about five queries each. Its time at
    PROD volume is *unmeasured* (#99, #239).
  - Each request carries the adoption it was opened under. A platform request's
    end leaves the Source Revision's outcome (§3); no scan request counts
    against a quota.
  - The gauges, written by the CronJob and exported by the `api`:
    `kp_admission_reruns_retrying{reason}` (latest Source Revisions with at
    least 5 retryable failures in a row, by the last failure's reason, so that
    `PLATFORM_ERROR` and `WORKFLOW_ENDED_WITHOUT_RESULT` show apart from a
    service outage), `kp_admission_reruns_stopped{reason}` (those waiting for the
    next adoption), `kp_admission_documents_on_withdrawn{version}`,
    `kp_admission_documents_without_current{source_id}` (created more than an
    hour ago), `kp_admission_requests_overdue{adopted_version}` (dispatched
    more than an hour ago and not ended), and
    `kp_admission_job_last_run_timestamp_seconds{job}`. Alert rules are #78's.
  - A refresh scope that lists Documents (only those that used an affected
    component, from a run manifest) is not built: nothing produces such a list
    for a CronJob to read. `made_by` is the narrowest scope.
- Durability: the admission database is one PostgreSQL instance on a
  network-backed persistent volume, with its write-ahead log archived
  continuously to storage outside that volume (a pilot go-live condition).
  - The instance or its node fails: no `202` is lost. Admission answers `503`
    until the instance runs again; after a node failure that takes an operator
    action.
  - The volume is lost: the database is restored from the archive. Requests
    acknowledged within the archive interval (target: one minute) may be lost,
    and their Sources submit them again. Operations declare the loss (§7.4,
    Lost writes) before Source Deletion's judgment runs again.
  - Restore time is *unmeasured* until the restore drill (§13).

  Replication inside the cluster is a later deployment change and needs no code
  change. DEV/POC may run without the archive and is marked as not meeting this.
- Pilot pause: triggered by backlog depth, while the queued `process` requests
  that Sources made (`initiator: source`) number at least the deployment's
  threshold (none by default), so the scan's backlog never pauses intake;
  rejects new declarations only.

## 10. Workflow start input

Defined here, implemented by #80, aligned with the #91 manifest v2:

```json
{
  "request_id": "req_01J…",
  "document_uid": "doc_7f3…",
  "source_revision_id": "srv_3",
  "files": [
    { "path": "policy.pdf", "role": "main", "custody_ref": "s3://kp-custody/documents/doc_7f3…/files/bat_01J…/0/9f2c…", "sha256": "9f2c…", "size": 18342, "media_type": "application/pdf" }
  ],
  "adopted_version": "paper-pdf@1",
  "adoption_sequence": 7,
  "initiator": "source",
  "priority": "normal",
  "trace_id": "4bf92f3577b34da6"
}
```

`custody_ref` is `s3://{bucket}/{key}`; the bucket is the processing worker's
object store bucket, so source files and processing results share it.
Admission records it once, at finalization (§6.2), for the object the upload
wrote. Carried-over files, retries, the scan's requests and the start input copy
it unchanged. Readers split it into bucket and key and derive nothing from the
key.

The key of a source file is
`documents/{document_uid}/files/{batch_id}/{index}/{sha256}`: the batch item
that uploaded it and its digest in lowercase hex. Only that item's upload (§5.2)
writes under its keys. A document's source files, and the items processing
registers for it, sit under `documents/{document_uid}/`. That prefix is not
everything kept for a document: processing writes each request's Processing
Result, failure report and attempt records under `requests/{request_id}/`, so a
purge of one document also covers the `requests/` prefixes of that document's
requests (#57 owns the purge rule). Removing the files
of one Source Revision alone first checks the document's other Source
Revisions for references to the same objects. The key carries no tenant: a deployment serves
one tenant. Should one serve several, each tenant gets its own bucket and no
key gains a prefix (#57 scope 6, 2026-11-22), so stored references stay valid.

Processing side effects must be safe to repeat (the reconciler may re-dispatch).

## 11. Limits and retention

| Item | Value |
|---|---|
| Items per declaration | 50 (provisional) |
| Intake quota per Source | Token bucket of 50 declared items, refilled at 50 per minute (provisional). A declaration takes one token per item when it commits, and returns those of the items §6.4 answers `unchanged` after a rejection or a failure that is not retryable; with too few it is `429` and `Retry-After` is when there will be enough |
| `document_id` | 1–256 characters, `[A-Za-z0-9-_.~:]`, case-sensitive |
| `metadata` | ≤ 50 keys; key 1–64 of `[A-Za-z0-9_.-]`; value ≤ 512 characters; ≤ 8 KB total |
| Files per item, open batches per Source | Set in I2 configuration, *unmeasured* |
| Maximum file size | 50 MB, the PROD requirement ([#88](https://github.com/davidlinnnn/data-ingestion/issues/88#issuecomment-6633160435)); configurable per deployment |
| Upload | One `PUT` per file (§5.2), accepted until the batch is finalized or expires; a repeated `PUT` changes nothing |
| Open batch | Expires 24 hours after creation |
| Uploads not admitted | Removed within 2 hours after the batch is finalized or expires (*unmeasured*) |
| `Idempotency-Key` | 24 hours |
| Request | `404` 30 days after its terminal outcome; active requests never expire |
| Batch | `404` 30 days after all items are terminal, or after expiry |
| Deleted document | `404` 30 days after deletion is applied |
| Deletion targets | `applied` within 1 minute, `enforced` within 10 minutes (*unmeasured*); custody purge after 30 days. Since 2026-11-15 (ADR-0014) content stops being served at `enforced`, not at `applied` |

## 12. Error reasons

| Reason | Level | HTTP |
|---|---|---|
| `INVALID_ARGUMENT`, `TOO_MANY_ITEMS`, `SIZE_MISMATCH` | request | 400 |
| `UNAUTHENTICATED` | request | 401 |
| `PERMISSION_DENIED` | request | 403 |
| `NOT_FOUND` | request | 404 |
| `BATCH_EXPIRED`, `BATCH_FINALIZED` | request | 409 |
| `LENGTH_REQUIRED` | request | 411 |
| `ALL_ITEMS_REJECTED`, `IDEMPOTENCY_KEY_REUSED`, `DIGEST_MISMATCH`, `MEDIA_TYPE_MISMATCH` | request | 422 |
| `RATE_LIMITED` | request | 429 |
| `AUTHZ_UNAVAILABLE`, `ADMISSION_PAUSED`, `UNAVAILABLE` | request | 503 |
| `INVALID_ARGUMENT`, `FILE_TOO_LARGE`, `UNSUPPORTED_FORMAT`, `SOURCE_VERSION_REQUIRED`, `BINDING_CONFLICT`, `RESOURCE_NOT_FOUND`, `RESOURCE_REQUIRED`, `STALE_SOURCE_VERSION`, `VERSION_CONFLICT` | item, declaration | — |
| `INVALID_ARGUMENT`, `DOCUMENT_DELETED`, `STALE_DECLARATION`, `RESOURCE_NOT_FOUND`, `FILES_MISSING`, `UNSUPPORTED_FORMAT`, `STALE_SOURCE_VERSION`, `VERSION_CONFLICT` | item, finalization | — |

`SIZE_MISMATCH`, `LENGTH_REQUIRED`, `DIGEST_MISMATCH`, `MEDIA_TYPE_MISMATCH` and
`BATCH_FINALIZED` are returned by the upload endpoint (§5.2).

`ATTEMPT_NOT_RECORDED` (`503`) is the status report intake's answer to a report
that arrives before the dispatcher has recorded its attempt (§7.3).

`WORKFLOW_ENDED_WITHOUT_RESULT` (domain `admission.knowledge-platform`,
retryable) is a failed request's `error` when the reconciler finds its workflow
ended without an error block, such as terminated or timed out (§9).

Two more `error` reasons of that domain end a `process` request without changing
its Source Revision's outcome (§3): `DOCUMENT_DELETED` (not retryable,
`cause` `source`) when the deletion ended it before it started (§8), and
`VERSION_WITHDRAWN` (retryable) when its version was withdrawn before it ended
(§9).

`RESOURCE_NOT_EMPTY` (`409`) belongs to the Resource API (#85).

## 13. Deployment and validation

- One image, three roles: `api` (2 fixed replicas), `dispatcher` (≥ 2 replicas),
  CronJobs (reconciler every 5 minutes, declarative adoption every minute with
  `concurrencyPolicy: Forbid`, deletion enforcement every minute and the scan
  every 5 minutes, both with `concurrencyPolicy: Forbid`, batch expiry and
  upload cleanup hourly, retention daily).
- The `api` role is FastAPI on one uvicorn worker per replica, with no HPA and no
  worker-count setting: the company sizes a fixed pod count for the peak. This
  role's peak is the sum of its Sources' intake quotas (§11), estimated at a few
  requests per second for the PROD burst (#88; *unmeasured*). One replica is
  expected to carry it and the second is for availability. When a capacity run
  finds a replica near one full core at peak, add uvicorn workers before replicas,
  because every pod also carries a mesh sidecar. #78 revises these numbers from
  the capacity runs.
- Its own PostgreSQL database, deployed without an operator: one instance on a
  persistent volume, continuous write-ahead-log archiving and a scheduled base
  backup to object storage (§9). Custody belongs to #57; topology and
  configuration loading to #78. This is the pilot's database (user ruling,
  2026-11-17,
  [#78](https://github.com/davidlinnnn/data-ingestion/issues/78#issuecomment-6949497546)):
  before the PROD release admission moves to the company-managed MongoDB
  ([#239](https://github.com/davidlinnnn/data-ingestion/issues/239)), which
  rewrites §3, §9 and this item.
- The `api` that takes a report's `candidate` (§7.3) is deployed before a worker
  that sends one (#81). The report refuses unknown fields, so in the other
  order every last report is `400` and the reconciler ends each request with no
  candidate.
- Uploads are written to the custody bucket (§5.2, §10). Admission writes source
  files there and deletes those of the items that created no Source Revision,
  with the incomplete uploads under their keys (§6.2); it changes nothing else
  in the bucket.
- The `api` role carries upload bytes (§5.2): it streams each body into storage
  in parts and never holds a whole file in memory. On the upload route the
  ingress must allow bodies up to the maximum file size, pass the body through
  without buffering it first, and allow several minutes per request; #78 sets
  these values. Capacity runs include the PROD burst (#88) through the upload
  route.
- Status reports (§7.3) reach the `api` inside the cluster under `/report/`,
  which the ingress does not expose, as it does not expose `/read/` and
  `/authz/`. The `api` reads `KP_PIPELINES`; canonical processing's
  orchestration worker reads `KP_ADMISSION_URL` (the `api`'s in-cluster address)
  and `KP_ADMISSION_TOKEN` (its credential, from a Secret), and without the
  token logs a warning and reports without a credential. Report intake counts in
  `kp_api_calls_total{operation="report_status"}` by status, and logs each
  report with `request_id`, `attempt_id`, `seq`, `stage`, `state`, `pipeline`,
  its result and, on failure, the error's `reason`, never its message.
- **CI tier:** Testcontainers PostgreSQL and Temporal; failpoints around each
  commit and start; an adjustable clock; the prototype's 19 scenarios as
  acceptance tests.
- **Cluster tier** (before the pilot and after infrastructure changes): database
  pod kill, loss of the database's node, a restore drill from the archive
  (measures the restore time and the lost interval), API and dispatcher pod
  kills, a one-hour Temporal outage extrapolated to 24 hours, a backlog pause,
  capacity runs, and the longest wait before a canonical attempt's first report
  and between two of its reports under the PROD burst, which set the canonical
  pipeline's two deadlines (§7.3). All *unmeasured*.
- A full 24-hour Temporal outage test before production.
- **Pass criteria:** every `202` maps to exactly one workflow; no loss or
  duplication; convergence within one reconciler period; deleted documents never
  return; deletion meets its `applied` and `enforced` targets. The restore drill
  is the one exception to "no loss": it passes when the lost interval is within
  the archive interval, and the lost-writes declaration (§7.4) has run and every
  Build not retired has installed a view after it.

## 14. Implementation tickets

| Ticket | Scope | Depends on |
|---|---|---|
| I1 Admission core (#95, done) | §3 schema, outbox, dispatcher, reconciler, the one-active-request constraint, Temporal start (§9, §10) | — |
| I2 Batch API (#96) | §5.1, §5.3, §5.4, §6, idempotency, quota, the adoption record | I1, #113, #184, #204, #114 |
| I2b File upload (#194) | §5.2, the upload cleanup (§6.2), minimal SDK | I2 |
| I3 Status (#97) | §5.5–§5.7, canonical processing's report intake and request outcomes (§3, §7.3), readiness over no serving facts and canonical attention (§7) | I1, #55, #126 |
| I3a Canonical Acceptance record (#251) | `accepted`, the current Canonical Revision and its selection, `current_revision_changed`, the withdrawn versions, the candidate and `details` (§3, §5.5, §5.6, §7.3) | I3 |
| I3b Projection report intake (#252) | the projections' reports and serving facts, readiness's serving part, `status_unverified`, `skipped` (§7) | I3 |
| I3c Serving-fact repair (#260, done) | the repair view's intake, the replacement of a Build's mirror and the lost-writes declaration (§7.4, DR §5.4, §5.6) | I3b |
| I2c Declarative adoption (#261) | the adoption record's declaration, refresh scope and withdrawn versions, the gate, `apply-adoption` (§3) | I3a |
| I3d Serving-mirror retention (#264, after the pilot) | removal of a retired Build's facts, old attempts and expired tombstones (§7.4, DR §5.3) | I3c |
| I4 Deletion and retry (#98) | §5.8, §8, retry (§6.4), the scan and the withdrawn version's requests (§9) | I1, I2, I2c, I3, I3b, I3c, #55, #126 |
| I5 Validation harness (#99) | §13 tiers | I1–I4, #78 |

The dependencies follow the tracker's edges as of 2026-11-19, when #97 was split
into I3, I3a and I3b, without the
closed prototype #236; where the two differ, the tracker is current. The Resource API of §5.1 is #114 (done).
