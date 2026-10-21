# Knowledge Platform admission specification

The buildable contract for
[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31).
The decisions and their reasons are in the
[admission design notes](knowledge-platform-admission.md) (rounds 1–5, with
question numbers such as Q9.4). This document states only the current result.
The rules in §6 are also modelled in the
[admission rules prototype](https://github.com/davidlinnnn/data-ingestion/blob/prototype/31-admission-rules/docs/prototypes/admission-rules.prototype.html), whose
19 scenarios pass. Domain terms follow `CONTEXT.md`.

Sizing figures marked *unmeasured* are provisional until the cluster-tier
validation (§13) measures them.

## 1. Scope

In scope: document submission through batches, direct upload, durable
admission, dispatch to Temporal, request and document status, Source Deletion,
application retry and platform redrive, retention, and the validation plan.

Out of scope here, with owners:

| Topic | Owner |
|---|---|
| Resource API, grants and authorization decisions | #85 (pilot), #86 (GAM) |
| Stopping disclosure, governance withdrawal, protected status | #56 |
| Custody, retained bytes, Custody Purge | #57 (purge with #56) |
| Canonical processing and the workflow implementation | #80, with the #91 manifest v2 |
| Projection consumption, the handoff channel, product removal | #55 |
| Serving results and filtering | #76 |
| CNPG, Temporal, configuration loading, topology, observability | #78 |

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
| `default_resource_id` | Optional |
| quota overrides | Optional overrides of §11 |

Requests never carry a tenant or Source; both come from the credential.

## 3. Resources and data model

Logical records; the physical schema is I1's.

| Record | Key fields | Notes |
|---|---|---|
| `batch` | `batch_id`, `source_id`, `state` (`open`, `finalized`, `expired`), `created_at`, `expires_at`, `finalized_at` | The history of one submission |
| `batch_item` | `batch_id`, `index`, `document_id`, `document_uid`, `status`, `request_id`, `source_revision_id`, `error`, declared files and catalog fields | §5.1 statuses |
| `document` | `document_uid`, `source_id`, `document_id`, `resource_id`, `title`, `source_url`, `metadata`, `deleted_at`, `delete_request_id` | Unique (`source_id`, `document_id`) among documents not deleted |
| `source_revision` | `source_revision_id`, `document_uid`, `source_version`, `files` (`path` → custody reference, `sha256`, `size`, `media_type`, `role`), `outcome` (`pending`, `accepted`, `rejected`, `failed`) | One per distinct content |
| `request` | `request_id`, `kind` (`process`, `delete`), `document_uid`, `source_revision_id`, `state`, `initiator` (`source`, `operator`, `platform`), `retry_of`, `batch_id`, `priority`, `adoption_sequence`, `trace_id`, timestamps, `error` | `request_id` equals the Temporal workflow ID |
| `outbox` | `request_id`, `available_at`, `attempts`, `dispatched_at` | Written in the same transaction as the request |
| `idempotency_key` | (`source_id`, key), body hash, stored response, `created_at` | 24 hours |

Constraints:

- At most one `process` request in `queued` or `processing` per
  (`document_uid`, `source_revision_id`): a partial unique index (Q9.7a).
- Finalization and re-declaration are serialized per document (row lock on the
  document).
- `source_revision.outcome` is set by canonical processing outcomes of
  Source-initiated and operator requests; platform refreshes (`initiator:
  platform`) never change it (round 3 R2).

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
  "trace_id": "4bf92f3577b34da6"
}
```

- Item errors inside results use `{ "reason": "…", "message": "…" }`.
- Protected things the caller cannot see return `404`; a missing permission of
  the caller's own credential returns `403` (Q3.7).

## 5. Endpoints

### 5.1 Declare: `POST /v1/batches`

Header `Idempotency-Key` (optional, recommended). Body:

```json
{
  "items": [
    {
      "document_id": "hr/leave-policy",
      "source_version": "3",
      "title": "Leave policy",
      "source_url": "https://km.example/hr/leave-policy",
      "resources": ["res_hr_all"],
      "uploaded_by": "tsso:alice",
      "metadata": { "km_folder": "HR/Policies", "owner_team": "hr-ops" },
      "files": [
        { "path": "policy.md", "role": "main", "sha256": "9f2c…", "size": 18342, "media_type": "text/markdown" },
        { "path": "assets/flow.png", "role": "attachment", "sha256": "1ab0…", "size": 220114, "media_type": "image/png" }
      ]
    }
  ]
}
```

Response `201`:

```json
{
  "batch_id": "bat_01J…",
  "state": "open",
  "expires_at": "2026-10-22T09:00:00Z",
  "items": [
    { "index": 0, "document_id": "hr/leave-policy", "document_uid": "doc_7f3…", "status": "declared",
      "uploads": [ { "path": "assets/flow.png", "method": "PUT", "url": "https://…", "expires_at": "2026-10-21T10:00:00Z" } ],
      "carried_over": ["policy.md"] }
  ]
}
```

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
error), `422 IDEMPOTENCY_KEY_REUSED`, `409 IDEMPOTENCY_IN_PROGRESS`,
`429 RATE_LIMITED`, `503 AUTHZ_UNAVAILABLE`, `503 ADMISSION_PAUSED`, `503`
during database failover. Every `429` and `503` carries `Retry-After`.

A batch in which no item is `declared` is created `finalized`.

### 5.2 Reissue grants: `POST /v1/batches/{batch_id}/grants`

Body `{ "items": [ { "index": 0, "paths": ["assets/flow.png"] } ] }`; an empty
body reissues every grant not yet used. Only for `open` batches; returns the same
`uploads` shape. Each grant allows one `PUT` of one file to its staging
location, limited to the declared size (and digest where storage supports it),
valid for one hour.

### 5.3 Finalize: `POST /v1/batches/{batch_id}/finalize`

No body. Response `202` with the batch and every item, admitted items carrying
`request_id` and `source_revision_id`. Repeating it returns the same response.
`409 BATCH_EXPIRED` for an expired batch; `422 ALL_ITEMS_REJECTED` when every
item of the batch ends rejected (the batch is still finalized and no request is
created). A pause does not block finalization (Q10.1e).

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
  "error": { "domain": "canonical.pdf-standard", "reason": "OCR_UNAVAILABLE", "message": "…", "retryable": false, "support_ref": "run-…" },
  "trace_id": "…",
  "details": { "_note": "internal; do not use for status decisions" }
}
```

Process states: `queued`, `processing`, `succeeded` (processing completed; not
Canonical Acceptance), `failed`. Delete states: `received`, `applied`,
`enforced`. Visible immediately after `202`, before any workflow exists.

### 5.6 Document: `GET /v1/documents/{document_id}`

Returns the current generation (Q10.1f):

```json
{
  "document_id": "hr/leave-policy", "document_uid": "doc_7f3…",
  "resource_id": "res_hr_all", "title": "Leave policy", "source_url": "https://…",
  "metadata": { "km_folder": "HR/Policies" },
  "readiness": "ready_stale", "since": "2026-10-15T09:12:00Z",
  "latest": { "source_revision_id": "srv_3", "source_version": "3", "request_id": "req_…" },
  "serving": [
    { "projection": "retrieval", "source_revision_id": "srv_2", "source_version": "2" },
    { "projection": "llm-wiki",  "source_revision_id": "srv_2", "source_version": "2" }
  ],
  "attention": [
    { "kind": "source_revision_rejected", "action_owner": "source", "source_version": "3",
      "message": "PDF could not be parsed; fix and re-upload", "since": "2026-10-15T09:12:00Z" }
  ],
  "deleted_at": null,
  "details": { "_note": "internal; do not use for status decisions" }
}
```

### 5.7 List: `GET /v1/documents`

Optional filters `resource_id`, `readiness`, `projection`; paginated. Without
filters it lists all the Source's documents, including `deleted` ones still
within retention. Each entry carries `document_id`, `document_uid`,
`latest.source_version`, `readiness` and `metadata`. Applications reconcile
deletions with this list.

### 5.8 Delete: `DELETE /v1/documents/{document_id}`

`202` with `{ "request_id": "req_…", "kind": "delete", "state": "received" }`.
Requires the submit permission. A repeated call returns the same request. §8
describes the stages.

## 6. Admission rules

### 6.1 Declaration, per item, first failure wins

1. Structure: valid `document_id` (1–256 of `[A-Za-z0-9-_.~:]`), exactly one
   `main` file, unique paths, valid `metadata` (§11) →
   `INVALID_ARGUMENT`.
2. Main-file format supported (pilot: PDF, Markdown, PPTX) →
   `UNSUPPORTED_FORMAT`.
3. Under `ordering: source_version`, `source_version` present →
   `SOURCE_VERSION_REQUIRED`.
4. Existing document (same `document_id`, not deleted) with a different
   `resources` value → `BINDING_CONFLICT`. An omitted value keeps the binding.
5. Placement: the Source may place documents into the Resource (created by it,
   or granted) → `RESOURCE_NOT_FOUND`; a new document with neither `resources`
   nor a default → `RESOURCE_REQUIRED`. An unavailable decision service fails the
   whole request with `503`.
6. Order against the latest Source Revision (§6.3) → `STALE_SOURCE_VERSION` or
   `VERSION_CONFLICT`.
7. Same content (§6.4) → `queued` with the active request, a new retry request,
   or `unchanged`.
8. Otherwise `declared`, with grants for files whose (path, digest) differs from
   the latest Source Revision; the others are `carried_over` (Q10.1d).

Results decided at declaration (`unchanged`, `queued`, `rejected`) are final;
requests they create are committed with their outbox rows before `201`.

### 6.2 Finalization, per `declared` item

1. Document deleted since declaration → `DOCUMENT_DELETED`.
2. Placement re-check → `RESOURCE_NOT_FOUND`.
3. Every file to upload present in staging → `FILES_MISSING`.
4. Recomputed SHA-256 equals the declaration → `DIGEST_MISMATCH`; detected media
   type matches → `MEDIA_TYPE_MISMATCH`.
5. Order re-check against the then-latest Source Revision → `STALE_SOURCE_VERSION`
   or `VERSION_CONFLICT`; same content → §6.4.
6. Otherwise: create the document on first submission (new `document_uid`),
   create the Source Revision, move staged files into custody (carried-over files
   reference the existing custody objects), apply catalog fields and metadata,
   create a `process` request and its outbox row.

All admitted items commit in one transaction before `202`. Staged files of
rejected or expired items are deleted.

### 6.3 Ordering

| `ordering` | Rule |
|---|---|
| `source_version` | Integer or RFC 3339 time, one kind per Source. Lower than the latest → `STALE_SOURCE_VERSION`. Equal with equal content → §6.4. Equal with different content → accepted only if the latest Source Revision's outcome is `rejected` (Q10.1b), else `VERSION_CONFLICT`. Higher → new Source Revision |
| `arrival` | Finalization order decides; equal content → §6.4 |

Content equality is equality of the set of (path, `sha256`) pairs. Equal bytes in
another document are never merged.

### 6.4 Same content as the latest Source Revision

| Latest Source Revision | Result |
|---|---|
| Has an active `process` request | `queued` with that request (Q10.1h) |
| Outcome `failed` (platform cause) and no active request | New `process` request for the same Source Revision: `initiator: source`, `retry_of` the last failed request, no upload, counted against quota |
| Any other outcome | `unchanged` |

`title`, `source_url` and `metadata` apply in all three cases.

### 6.5 Catalog fields and Source Metadata

Submitted `title` and `source_url` replace the current values. `metadata` replaces
the whole map; omitted keeps it; `{}` clears it. None of them creates a Source
Revision. A rejected item applies nothing. Metadata is returned only to the
owning Source and never reaches projections, agents or filters.

## 7. Status

### 7.1 Readiness

Required projections are the Source's current `projections`. Only serving within
the document's current Resource counts. First match:

| State | Condition |
|---|---|
| `deleted` | Source Deletion applied |
| `withdrawn` | Governance withdrawal of the document or its latest Source Revision (#56) |
| `not_ready` | Some required projection serves no revision |
| `ready_stale` | All serve a revision, at least one older than the latest |
| `ready` | All serve the latest Source Revision |

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
nor attention; the owner is alerted (#78).

### 7.3 Reports

Admission, canonical processing and each projection report through the round-3
status reporting contract (registered pipeline IDs, attempt reports ordered by
`attempt_id` and `seq`, AIP-193-style error blocks, serving facts per published
product version). The transport is chosen with #55's handoff channel in I3.

## 8. Source Deletion

| Stage | Meaning | Who | Target |
|---|---|---|---|
| `received` | Durable fact committed, `202` returned | #31 | Same call |
| `applied` | Agents can no longer find, read or cite the document's own content; readiness `deleted` | Serving-time block keyed by `document_uid` (#56, #76), recorded by #31 | 1 minute, *unmeasured* |
| `enforced` | Every required projection has removed the document and adjusted products derived from it (for example LLM-wiki pages) | Projection owners via #55; judged by #31 from their reports and serving facts | 10 minutes, *unmeasured* |

- The deletion reaches projections through the #55 handoff channel, carrying
  `document_uid`; each projection reports when it has finished.
- When deletion is applied, `title`, `source_url` and `metadata` are cleared;
  the `deleted` record keeps only identifiers, times and request IDs.
- Items of earlier batches finalized after `applied` → `DOCUMENT_DELETED`.
- Results arriving later are recorded but never restore the document; publishing
  a deleted document is ignored.
- A new submission of the same `document_id` after `applied` creates a new
  `document_uid`.
- The deleted generation is visible for 30 days (its delete request and
  `GET /v1/documents?readiness=deleted`), then `404`. Custody and derived data
  are purged at the same point (#57, #56).
- v1 offers no application-triggered immediate purge. For a security incident
  the application deletes the document and the security team requests an
  immediate purge through the #56 governance path.

## 9. Dispatch and durability

- The request and its outbox row commit in one transaction before `201` or
  `202`.
- Dispatchers (at least two) claim outbox rows with `FOR UPDATE SKIP LOCKED`,
  apply global and per-Source in-flight budgets with fair rotation and
  priority, and start the workflow with workflow ID = `request_id` and
  `REJECT_DUPLICATE`; `WorkflowExecutionAlreadyStarted` counts as success.
  During a Temporal outage rows wait and retry with backoff.
- The reconciler (every 5 minutes) checks dispatched requests without a terminal
  outcome: running → left alone; closed → outcome recorded; missing →
  re-dispatched with the same ID and the reason recorded.
- Redrive (operator command): for every document whose latest Source Revision is
  platform-failed with no active request, create a `process` request with
  `initiator: operator`, low priority, no quota.
- Platform refresh after an owner adopts a version: one `process` request per
  affected document's current canonical revision, `initiator: platform`, the
  adoption sequence recorded, low priority, no quota.
- Durability: a `202` survives a single node failure (CNPG, three instances,
  quorum synchronous replication; a pilot go-live condition). DEV/POC may run one
  instance and is marked as not meeting it.
- Pilot pause: triggered by backlog depth; rejects new declarations only.

## 10. Workflow start input

Defined here, implemented by #80, aligned with the #91 manifest v2:

```json
{
  "request_id": "req_01J…",
  "document_uid": "doc_7f3…",
  "source_revision_id": "srv_3",
  "files": [
    { "path": "policy.md", "role": "main", "custody_ref": "custody://…", "sha256": "9f2c…", "size": 18342, "media_type": "text/markdown" }
  ],
  "adopted_version": "md-standard@2",
  "adoption_sequence": 7,
  "initiator": "source",
  "priority": "normal",
  "trace_id": "4bf92f3577b34da6"
}
```

Processing side effects must be safe to repeat (the reconciler may re-dispatch).

## 11. Limits and retention

| Item | Value |
|---|---|
| Items per declaration | 50 (provisional) |
| Intake quota per Source | Token bucket, 50 declared items per minute (provisional) |
| `document_id` | 1–256 characters, `[A-Za-z0-9-_.~:]`, case-sensitive |
| `metadata` | ≤ 50 keys; key 1–64 of `[A-Za-z0-9_.-]`; value ≤ 512 characters; ≤ 8 KB total |
| Files per item, file size, open batches per Source | Set in I2 configuration, *unmeasured* |
| Upload grant | 1 hour, reissuable while the batch is open |
| Open batch | Expires 24 hours after creation |
| `Idempotency-Key` | 24 hours |
| Request | `404` 30 days after its terminal outcome; active requests never expire |
| Batch | `404` 30 days after all items are terminal, or after expiry |
| Deleted document | `404` 30 days after deletion is applied |
| Deletion targets | `applied` within 1 minute, `enforced` within 10 minutes (*unmeasured*); custody purge after 30 days |

## 12. Error reasons

| Reason | Level | HTTP |
|---|---|---|
| `INVALID_ARGUMENT`, `TOO_MANY_ITEMS` | request | 400 |
| `UNAUTHENTICATED` | request | 401 |
| `PERMISSION_DENIED` | request | 403 |
| `NOT_FOUND` | request | 404 |
| `BATCH_EXPIRED`, `IDEMPOTENCY_IN_PROGRESS` | request | 409 |
| `ALL_ITEMS_REJECTED`, `IDEMPOTENCY_KEY_REUSED` | request | 422 |
| `RATE_LIMITED` | request | 429 |
| `AUTHZ_UNAVAILABLE`, `ADMISSION_PAUSED`, `UNAVAILABLE` | request | 503 |
| `INVALID_ARGUMENT`, `UNSUPPORTED_FORMAT`, `SOURCE_VERSION_REQUIRED`, `BINDING_CONFLICT`, `RESOURCE_NOT_FOUND`, `RESOURCE_REQUIRED`, `STALE_SOURCE_VERSION`, `VERSION_CONFLICT` | item, declaration | — |
| `DOCUMENT_DELETED`, `FILES_MISSING`, `DIGEST_MISMATCH`, `MEDIA_TYPE_MISMATCH` | item, finalization | — |

`RESOURCE_NOT_EMPTY` (`409`) belongs to the Resource API (#85).

## 13. Deployment and validation

- One image, three roles: `api` (HPA), `dispatcher` (≥ 2 replicas), CronJobs
  (reconciler every 5 minutes, batch expiry hourly, retention daily).
- Its own CNPG database; staging storage belongs to admission; custody to #57;
  topology and configuration loading to #78.
- **CI tier:** Testcontainers PostgreSQL and Temporal; failpoints around each
  commit and start; an adjustable clock; the prototype's 19 scenarios as
  acceptance tests.
- **Cluster tier** (before the pilot and after infrastructure changes): CNPG
  primary kill, API and dispatcher pod kills, a one-hour Temporal outage
  extrapolated to 24 hours, a backlog pause, capacity runs. All *unmeasured*.
- A full 24-hour Temporal outage test before production.
- **Pass criteria:** every `202` maps to exactly one workflow; no loss or
  duplication; convergence within one reconciler period; deleted documents never
  return; deletion meets its `applied` and `enforced` targets.

## 14. Implementation tickets

| Ticket | Scope | Depends on |
|---|---|---|
| I1 Admission core | §3 schema, outbox, dispatcher, reconciler, the one-active-request constraint, Temporal start (§9, §10) | #78, #80, #91 |
| I2 Batch API | §5.1–§5.4, §6, staging to custody, idempotency, quota, minimal SDK | I1, #85, #57 |
| I3 Status | §5.5–§5.7, §7, report intake | I1, #55, #80 |
| I4 Deletion and retry | §5.8, §8, retry (§6.4), redrive and refresh commands (§9) | I1, I3, #55, #56 |
| I5 Validation harness | §13 tiers | I1–I4, #78 |
