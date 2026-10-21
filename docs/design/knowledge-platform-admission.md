# Knowledge Platform admission design notes

Active design for [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31),
within the existing Knowledge Platform wayfinder map. Rounds 1–5 are
confirmed; the current contract is the
[admission specification](knowledge-platform-admission-spec.md). Later rounds
revise earlier ones, and each round lists what it superseded.

## Confirmed delivery direction on 2026-10-18

The user reaffirmed platform-issued **direct upload** and requested that future
design-principle documentation explain the **Valet Key pattern**: the platform
first establishes the submitter's authority, then delegates access to specific
storage resources for limited operations and a limited period.

The client transfers file bytes to platform-designated storage. The platform
retains responsibility for the delivery authorization, capture verification,
durable processing admission and governed use of retained data. Source Owner
accountability and source authorization ceilings remain in force.

The user emphasized enterprise Authentication and Authorization (AA) for the
handoff of sensitive data, together with a bounded implementation that reuses
existing capabilities. This confirmation selects neither a storage product nor
a presigned URL, SAS, token format, endpoint, grant lifetime or revocation policy.

## Client clarification on 2026-10-18

The user clarified that the intended integration client is the Data Owner's
system calling the platform API. Submissions reference the document's Resource
binding; the [confirmed admission rules](#confirmed-admission-decisions-on-2026-10-19-and-2026-10-20)
govern which references are accepted, and GAM or compatible authorization governs
subsequent data access. A human may trigger the source system; this alone does
not establish that the platform must authorize the operation as that human.

The existing source-handoff contract supports delegated programs and workload
identities. Submission authority and authority to establish a document's
Resource binding must both be trustworthy; merely supplying a Resource ID does
not establish permission to use that binding or broaden the source audience.

The pilot decision below establishes platform-managed service-account tokens.
The existing controlled manual pilot client does not require a separate
per-person submission permission system.

The user subsequently identified an existing company mechanism called PAT for
system identity, distinct from tSSO for people, while noting that its details are
uncertain. The company PAT's expansion, protocol, token lifetime, validation and
revocation capabilities have not been verified. Integration with that mechanism
is deferred by the pilot decision below. See the
[CSP authentication and operations investigation](../research/service-client-authentication-csp-practices-2026-10-18.md).

## Confirmed pilot service-account authentication on 2026-10-18

The user selected a bounded pilot approach: Knowledge Platform configuration
manages the client service accounts and the platform issues a fixed service-account
token to each Data Owner system. In this pilot discussion, PAT refers to that
platform-managed credential; it does not claim compatibility or integration with
the existing company PAT service. Exact token encoding and lifetime are not
selected by this decision.

The purpose is to make system submission usable with low operating effort while
prioritizing data access control. Company PAT integration, OAuth token exchange,
managed identity and federation remain follow-up topics rather than prerequisites
for the pilot. The research is retained for that revisit. This is not a selection
of the production authentication mechanism.

Keep the pilot's submission boundary small:

- Identify each client service account separately and limit its submission
  authority to the configured Sources and permitted operations. A valid token
  does not grant permission to read all data or manage authorization policy.
- Establish trustworthy document-to-Resource bindings within delegated authority;
  arbitrary caller-supplied Resource IDs cannot broaden the source audience.
- Retain an operator path to disable or replace a client's credential through
  configuration, with credential values protected from source control and logs.
  A credential-management UI, self-service issuer and automatic rotation service
  are not required by this pilot decision. Configuration propagation and any
  effect on previously issued upload grants remain admission-design details.

Data access control retains first priority. The pilot's built-in authorization
is designed in [#85](https://github.com/davidlinnnn/data-ingestion/issues/85),
the production GAM track in [#86](https://github.com/davidlinnnn/data-ingestion/issues/86),
and governance enforcement across canonical data and published views in
[#56](https://github.com/davidlinnnn/data-ingestion/issues/56). Admission
consumes and enforces the applicable contract, including the trusted Resource
binding; it does not create a second reader-authorization system or waive
governed access for the pilot.

Platform API authentication and the temporary storage grant used for direct
upload retain distinct purposes. The confirmed direct-upload / Valet Key
direction remains in force; this decision does not choose presigned URL versus
another storage mechanism. The remaining admission contract is still open.

## Confirmed single and batch submission contract on 2026-10-18

The user confirmed one shared submission contract accepting `items[1..N]`;
a single-document submission contains one item. Batch supplies grouping and
aggregate progress while every document retains its own identity, governance
relationships and result. Corpus membership and Resource bindings belong to the
individual document's governed relationships, not to its incidental batch.

This selects the common contract, not separate single/bulk processing pipelines.
The numeric maximum, exact routes and fields, batch/item operation identifiers,
cross-Source or cross-authorization-scope admission rules, and persistence remain
open. An item represents a complete captured document package, which can include
required attachments rather than exactly one file.

Partial admission was decided on 2026-10-19; see
[Partial admission](#partial-admission-q2). Independent outcomes after admission
remain required. Neither this agreement nor the batch
research chooses inline bytes, external-location import, the finalization trigger
or the storage-grant mechanism.

## Confirmed admission decisions on 2026-10-19 and 2026-10-20

Grilling round 1 for #31. The industry evidence and the separation between
source-supported facts and platform design inferences are recorded in the
[admission authorization research](../research/admission-authorization-csp-practices-2026-10-20.md).
Question numbers refer to that round.

### Design target (Q1)

Design the contract and the admission/dispatch mechanism to production
requirements; the pilot implements the same mechanism. The only staged
difference is the first-adoption Q22 rule: during processing-side outages
(Temporal, workers, models) the pilot may pause new admissions and ask clients
to retry later, while production durably accepts and processes later. Capacity
figures remain marked as unmeasured.

### Partial admission (Q2)

- Request-level errors, such as failed authentication, a malformed request or an
  exceeded item limit, reject the whole request.
- Item-level errors reject only that item; the other items are admitted. The
  response lists a result for every item: a request ID for each admitted item and
  a reason for each rejected item.
- If every item is rejected, the request fails and no Batch is created.
- v1 offers no all-or-nothing option. The client resubmits corrected items in a
  new submission.

### Sources, tenants and credentials (Q3.2, Q3.3, Q3.3a, Q3.9)

- A Source is typically one Data Owner knowledge-management application; the
  platform does not model a separate application layer. An application needing
  different restrictions registers multiple Sources.
- Pilot onboarding is one-time platform configuration: register one or more
  Sources and issue their credentials. Automated Source registration is deferred.
- Submitting (Ingest API) and managing relations (Resource API) are distinct
  permissions. A credential may hold either or both; separate credentials are
  recommended when an application runs separate components. The submit
  permission includes read-only list/get of Resources visible to its Source.
- Each credential belongs to exactly one Source and each Source to one tenant.
  Requests carry neither a tenant nor a Source; both are derived from the
  credential. Admission records, Sources, Assets and Resources store the tenant
  ID from the start. A future credential acting for several Sources would add an
  optional Source selector that defaults to the credential's Source.
- This refines the 2026-10-18 pilot wording: holding a credential grants nothing
  by itself; authority comes from the relations held by its Source.

### Resource binding at admission (Q3.1, Q3.4, Q3.5, Q3.10a)

Each item is checked in order:

1. Structural tenant check: the Source's tenant equals the credential's tenant.
2. The credential belongs to Source S and holds the submit permission.
3. S may place documents into each referenced Resource R: R was created under
   S, or R's maintainer granted S.

- Items reference only existing Resources; a submission never creates a
  Resource. Sources create and manage Resources, their readers and their grants
  dynamically through the Resource Service; the platform does not configure
  individual Resources.
- A Source may set a default Resource. Resources specified by an item replace the
  default. A new Asset with neither is rejected.
- For an existing Asset, an omitted Resource keeps the current binding, the same
  Resource is admitted, and a different Resource rejects the item as a binding
  conflict. Binding changes go only through the Resource API, with permission on
  both the current and the new Resource.
- If S's permission is revoked between declaration and finalization, the item is
  rejected at the finalization re-check. A revocation after `202` does not undo
  admission: it blocks later submissions, documents already placed remain until
  R's maintainer removes them, and reads follow current policy.
- Multiple audiences in v1: for a union, the Source creates one Resource whose
  readers cover both audiences; for an intersection, a Resource representing the
  intersection. Appearing in several knowledge scopes is not supported in v1,
  because a projection's knowledge scope corresponds to one Resource
  ([ADR-0007](../adr/0007-derived-product-readers-within-input-intersection.md);
  revised on 2026-10-20 from the earlier Corpus-membership suggestion). Uploading
  the same document twice is discouraged; if used, the copies are distinct Assets
  managed independently.

### Authorization availability and error visibility (Q3.6, Q3.7, Q3.7a)

- If the authorization decision service is unavailable, the whole request fails
  with a retryable error (`503` with `Retry-After`) and nothing is admitted. There
  is no pending-authorization state. The decision service is therefore an
  admission dependency in both pilot and production. Safe retry requires the
  idempotency design, which remains open.
- Anything whose existence is protected and is not visible to the caller returns
  not found: a nonexistent Resource, another Source's Resource without a grant,
  another tenant's Resource, and status lookups of another Source's requests.
  Insufficient permissions of the caller's own credential return `403`. A
  distinct "visible but not permitted" Resource error is reserved for future
  relations.
- Every error carries a trace ID. The admission record stores the internal reason
  (does not exist, not granted, revoked, other tenant) and the decision ID and
  time, visible only to platform operators. Only "does not exist" may be told to
  the caller; other reasons are routed to the Resource maintainer or not
  disclosed. The operator disclosure procedure belongs to #56.

### Submitter attribution (Q3.8)

An item may carry an optional `uploaded_by` tSSO identity asserted by the
Source. It is recorded only, marked as Source-asserted, and is neither used for
authorization nor proof that the person acted. Verified end-user submission is
deferred.

### Contract assumptions shared with #85 (Q3.10)

1. Resources are referenced by opaque IDs.
2. Items carry `resources[1..N]`; v1 limits this to one.
3. Readers are defined on Resources; items carry no reader list.
4. Admission consumes one decision per check: allow, deny or unavailable.

If a decision in #85 violates any assumption, #31 is explicitly reopened.

### Glossary (Q3.11, Q3.12)

`CONTEXT.md` updates the Source entry to describe the application role and the
Tenant entry to state that tenants are not part of resource authorization policy
and would be enforced as a separate boundary if tenants later share a
deployment. The multi-tenant isolation design is recorded as pending in #56.

Round 2 below resolves the submission flow, upload grants, idempotency,
versioning and the acceptance store.

## Confirmed admission decisions on 2026-10-20 (round 2)

Rounds 4 and 5 revised parts of this round; see
[Superseded during rounds 4 and 5](#superseded-during-rounds-4-and-5).

Grilling round 2 for #31. Evidence is recorded in the
[admission authorization research](../research/admission-authorization-csp-practices-2026-10-20.md)
(sections 7–12).

### Submission flow (Q4, Q4a)

1. Declare: the client submits items with Asset IDs, expected files, their
   SHA-256 digests and sizes, and `resources`.
2. The platform runs the Q3.1 checks and rejects failing items early. Passing
   items receive upload locations and grants; nothing is admitted yet.
3. The client uploads the files directly to platform storage.
4. The client calls finalize explicitly.
5. The platform verifies completeness, digests and fixed versions and re-checks
   Resource permissions.
6. Durable admission, then `202` with per-item request IDs.

An SDK wraps the three client calls into one operation. Automatic finalization
when all declared files arrive is a later optimization. v1 and the pilot offer no
inline content mode; inline content would be added, with a size limit, only if a
pilot client cannot use the SDK.

### Integrity information (Q4b)

Every declared file carries a SHA-256 digest and its size. The platform
recomputes the digest at finalization and rejects only that item on mismatch.
When storage supports it, the digest is signed into the upload grant, but the
platform does not rely on storage enforcement. The admission record stores the
platform-verified digest as the artifact's integrity information.

### Upload grants and sessions (Q5, Q5a, Q5b)

- One short-lived grant per declared file, limited to its staging location and
  declared size (and digest where supported). Default lifetime is one hour;
  grants may be reissued while the session is open. The concrete form is a
  storage-native presigned URL or SAS, chosen with the storage product.
- An upload session not finalized within 24 hours expires: its items are not
  admitted and staged files are deleted. Finalizing an expired session fails
  explicitly.
- Revocation does not chase grants already issued. It stops new grants and makes
  finalization fail; bytes uploaded with a still-valid grant stay in staging and
  are deleted on expiry. Staging is separate from retained custody; finalization
  moves admitted files into custody with fixed versions. The user accepted this
  bounded bearer delegation for the pilot.

### Idempotency and unchanged content (Q6, Q6a)

- Declaration accepts an `Idempotency-Key`, scoped per Source and kept for 24
  hours. The same key and body replays the original result, a different body
  returns `422`, and a request still in progress returns `409`. Results of `503`
  or validation failures before commit are not stored, so retries re-execute.
  Finalization and grant reissue are idempotent without a key.
- If every artifact digest of an Asset's package equals the currently admitted
  version, the item result is `unchanged`: no new Source Revision and no
  reprocessing, counted as success in Batch aggregates. A changed attachment
  creates a new Source Revision; equal bytes in another Asset are not merged.
  Intentional reprocessing is not a resubmission; it is a platform-driven
  refresh with a new request ID (see round 3 and accepted constraints 5 and 6
  of #31).

### Version ordering (Q6b, Q6c)

- An item may carry an optional `source_version` representing the version of the
  whole package, as an integer or RFC 3339 time used consistently per Source.
  Newer creates a Source Revision; equal with equal digests is `unchanged`; equal
  with different digests is rejected as a version conflict; older is rejected as
  stale. Without it, finalization order decides. Finalization is serialized per
  Asset.
- Platform Source Revision and Canonical Revision IDs are platform-generated
  opaque IDs, decoupled from `source_version`, which serves only as an ordering
  guard and source evidence. Results return both. Re-baselining after a Source
  renumbers its versions is deferred.

### Acceptance store and dispatch (Q7.1–Q7.6)

- The admission record and an outbox row are written in one PostgreSQL
  transaction; `202` follows the commit. Not adopted: starting Temporal before
  `202`, which would make admission unavailable during a Temporal outage and
  violate the 24-hour requirement; and a separate broker, which would create a
  dual write and is not needed for the current throughput and single consumer.
- Durability requirement: an admission acknowledged with `202` survives a single
  node failure (RPO 0); admission may return `503` during failover. DEV/POC may
  run a single instance and is explicitly marked as not meeting the requirement.
  Before pilot go-live, run CloudNativePG with three instances and quorum
  synchronous replication; this is a pilot go-live condition. No managed
  PostgreSQL service exists in the company today. Provisioning and operation are
  handed to #78 and coordinated with #57.
- The dispatcher starts the Temporal workflow with the request ID as workflow ID
  and `REJECT_DUPLICATE`, treating `WorkflowExecutionAlreadyStarted` as success.
  During a Temporal outage outbox rows wait and are dispatched with backoff.
- A request marked dispatched is not complete until processing reports a terminal
  outcome. A reconciler checks dispatched requests without a terminal outcome:
  a running workflow is left alone, a closed workflow has its outcome recorded,
  and a missing workflow (for example after Temporal history loss) is
  re-dispatched with the same workflow ID and the reason recorded. Processing side
  effects must therefore be safe to repeat; that belongs to the processing owners.
- The outbox is the durable buffer (Queue-Based Load Leveling). The dispatcher
  applies global and per-Source in-flight budgets, rotates fairly across Sources
  and reserves a priority field; dispatchers claim rows with
  `FOR UPDATE SKIP LOCKED`. A broker is introduced only if throughput exceeds the
  database or company policy requires one. The pilot pause rule from Q1 is
  triggered by backlog depth.
- Intake quota per Source: a token bucket of 50 declared items per minute, at
  most 50 items per request (provisional), exceeding requests rejected whole with
  `429` and `Retry-After`; open-session limits remain unmeasured; per-Source
  overrides are configuration. Processing throughput and latency belong to a
  separate specification.
- The canonical-to-projection handoff (events, change log or polling) belongs to
  #55; #31 owns only the correlation from requests to downstream processing and
  publication outcomes. NATS is not part of #31.

Round 3 below covers status, readiness, knowledge profiles and platform-driven refresh.

## Confirmed admission decisions on 2026-10-20 (round 3)

Rounds 4 and 5 revised parts of this round; see
[Superseded during rounds 4 and 5](#superseded-during-rounds-4-and-5).

Grilling round 3 for #31 covers status, readiness, knowledge profiles and
platform-driven refresh. The first draft was revised the same day after an
expert design review and a usability review from the application team's point
of view; only the final decisions are recorded here, and the superseded points
are listed at the end of this section. Industry evidence is in the
[research note](../research/admission-authorization-csp-practices-2026-10-20.md)
§13–§16.

### Item status (Q8.1)

- Admission item states are `rejected`, `expired`, `unchanged`, `queued`,
  `processing`, `succeeded` and `failed`. `succeeded` means processing completed,
  not Canonical Acceptance.
- Sessions are `open`, `finalized` or `expired`. Batches report counts per
  status. Terminal states are retained for 30 days.
- An `unchanged` item returns the document's current readiness.

### Knowledge Profile (Q8.2a, R6, R2)

A Knowledge Profile is a Source-level setting shared by all Assets of that
Source. In the pilot it has one part:

```yaml
projections: [retrieval, llm-wiki]   # Projection Types whose products the Source's Assets go into
```

- It determines which projections readiness waits for. It contains no versions,
  readers or grouping.
- Projection selection is live: required projections follow the current
  setting. An added projection backfills the Source's existing documents; a
  removed projection stops counting for readiness. What happens to its existing
  products belongs to #55.
- The pilot has one canonical processing profile per file format, selected by
  format. Features such as figure handling are decided by the pipeline per
  document. The profile catalog belongs to #72, with implementation in #80. If several selectable profiles
  appear later, a `processing` entry can be added; changing it would trigger a
  platform refresh like a version adoption.
- There is no per-document override. Documents that need different projections
  or restrictions use another Source.
- Which canonical data each projection consumes, and how it groups them, belongs
  to #55 under #58 Q9 and ADR-0007. #55 also decides the mixed case where one
  Source submits into another Source's Resource and their profiles differ; that
  document's readiness follows its own Source's profile.
- A Source is an admission boundary, not a consumption boundary. Search and
  reading across Sources are limited only by Resource readers. The physical
  index layout belongs to the Retrieval owner and #55; a Source is not a
  physical partition requirement, and tenant isolation only matters if tenants
  later share a deployment.
- **Registration:** #31 defines the admission-relevant registration fields and
  their meaning: Source ID, credential binding, inbound quota and
  `projections`. Selecting an unregistered projection is rejected when the
  configuration is set. The configuration format, Helm values and loading belong
  to #78, with the recommendation of declarative configuration, secret
  references only, schema validation at startup, and Resources still managed
  through the Resource API. Credential issuance belongs to #85.

### Versions (R0a–R0c)

| Layer | Example | Decided by |
|---|---|---|
| Knowledge Profile | `projections: [retrieval, llm-wiki]` | Source |
| Adopted version | `pdf-standard@2`, `retrieval@4`, `llm-wiki@5`, each with a component manifest | Each owner |
| Run record | The resolved components a run actually used | Each pipeline, per run |

- Sources do not pin versions in the pilot.
- Every run records a resolved component manifest with immutable identifiers:
  component kind (parser, OCR, VLM, embedding, LLM, prompt), name, version or
  digest, and a configuration hash. Mixed use, such as fallback OCR on some
  pages, is recorded at element level. Owners keep the manifests; their formats
  belong to #80 and #55. Status reports carry only `method_version` and
  `manifest_ref`.
- Current selection compares adopted versions only, never component versions.
  Readiness measures freshness by Source Revision only.

### Current canonical revision (R1a, R1d, R1e)

- **Eligible:** accepted, still governance-eligible, and produced under an
  adopted version. Experiment runs are never eligible.
- **Order:** the newer Source Revision (round 2 ordering), then the higher
  adoption sequence, then the existing selection on a tie. The adoption sequence
  is counted per Source and increases when an owner adopts a new canonical
  version.
- Canonical processing owns this rule and reports the current revision as its
  serving fact (P10).
- When the current revision is withdrawn, selection does not fall back to an
  older Source Revision.
- Under the push model, round 2 Q6b/Q6c supersedes the canonical Q13/V08 rule
  that preserves a conflict when source order is unknown: with `source_version`
  an older capture is rejected as stale; without it, finalization order decides.
  Canonical Q8's "no single global current pointer" is narrowed to a default
  current revision per Asset; exact-revision references remain valid. The
  canonical notes record this supersession.

### Platform-driven refresh (R2, R4, R12, R13, R1c)

- When an owner adopts a new version, the platform refreshes the affected
  documents automatically. The owner declares the affected scope, using run
  manifests to target only documents that used an affected component.
- Applications never reprocess or re-upload for version changes. A content
  change, uploaded as a new version, is the only application action.
- Each refresh is a new request with fixed resolved profile versions (accepted
  constraints 5, 6 and 8) and targets the current Source Revision. It records
  its initiator (`platform` or an operator) and the adoption sequence, does not
  count against the Source's inbound quota, and runs at lower priority than daily
  submissions through the same outbox (Q7.4, #54 V04).
- The pilot does not expose `reprocess` to Sources; constraint 6 is satisfied by
  internal reprocessing through a new request.
- **Every refresh is invisible to agents and users:**
  1. The previous result keeps serving until its replacement is accepted and
     published.
  2. Method changes affect neither readiness nor attention.
  3. A failed refresh leaves the previous result serving and alerts the owner
     (#78).
  4. Daily submissions keep priority.
  5. Queued and running requests keep compatible workers (constraint 8).
  6. Exact-revision references stay resolvable within retention (ADR-0003).
- How each projection switches, per document or as a whole index (for example
  after an embedding-model change), belongs to #55 and the projection owners.

### Readiness and attention (Q8.2, Q8.2b, Q8.2c, R7a, R7c, R9, R11)

Status separates two questions.

**`readiness`: what agents can read.** Required projections are the
Knowledge Profile's `projections`. The first matching state applies:

| State | Condition | Suggested display |
|---|---|---|
| `withdrawn` | The Asset is withdrawn, or its latest Source Revision is withdrawn | Black |
| `not_ready` | Some required projection serves no revision of the document | Yellow |
| `ready_stale` | Every required projection serves a revision, but at least one serves an older Source Revision than the latest | Blue |
| `ready` | Every required projection serves the latest Source Revision | Green |

**`attention[]`: who must act.** Each item has `kind`, `action_owner`
(`source`, `platform` or `governance`), an English `message`, `since`, and
`source_version` or `support_ref` where applicable. Items refer to the latest
Source Revision or the current serving state and clear when superseded.

| Kind | Action owner | When |
|---|---|---|
| `source_revision_rejected` | `source` | Canonical processing rejected the latest Source Revision |
| `product_failed` | `platform` | A required projection failed for the current Source Revision and its retries are exhausted |
| `progress_stalled` | `platform` | A pending or running attempt passed its deadline |
| `status_unverified` | `platform` | A required pipeline lost liveness; readiness uses the last known serving facts |
| `skipped` | Set by the owner | A required projection skipped the document, for example an unsupported format |
| `withdrawn` | `governance` | Governance withdrawal; disclosure follows #56 |

- A method-version lag or a failed method upgrade affects neither readiness nor
  attention. It is visible only in `details`, and the owner is alerted.
- Readiness does not gate publication and grants no access (Q8.2c).
  Projections publish independently; only governance withdrawal blocks access.
  Consumers that need consistency filter at serving time (`min_readiness`, #76
  with #55). Coordinated cross-projection cutover is deferred.
- **Rebind (R7c):** only serving within the document's current Resource counts.
  Until the new Resource's products include the document, readiness is
  `not_ready` or `ready_stale`. Removal from the previous Resource follows the
  #56 revocation path; ordinary update targets are not a disclosure grace period
  (#54 Q7).

### Status response and queries (Q8.5, Q8.7, R5, R10)

```json
{
  "asset_id": "leave-policy",
  "asset_key": "ak_7f3…",
  "readiness": "ready_stale",
  "since": "2026-10-15T09:12:00Z",
  "latest":  { "source_revision": "S3", "source_version": "3" },
  "serving": [
    { "projection": "retrieval", "source_revision": "S2", "source_version": "2" },
    { "projection": "llm-wiki",  "source_revision": "S2", "source_version": "2" }
  ],
  "attention": [
    { "kind": "source_revision_rejected", "action_owner": "source", "source_version": "3",
      "message": "PDF could not be parsed; fix and re-upload", "since": "2026-10-15T09:12:00Z" }
  ],
  "details": { "_note": "internal; do not use for status decisions" }
}
```

- `details` holds internal facts such as the current canonical revision,
  adoption sequence, method versions, attempts and stages. Monitoring uses only
  `readiness` and `attention`. Projection identifiers are the same everywhere.
- **Entry points:** `request_id`, `asset_id` (unique within the Source),
  `asset_key` (platform-generated) and `resource_id` (paginated, filterable by
  readiness and projection). Inputs never include `source_id` or the tenant.
  Admission results return `asset_key`.
- **Visibility:** status is queried only with Source credentials, from the
  application's backend; tSSO is intended for agents consuming knowledge (#76).
  A Source sees only the Assets it submitted, including through `resource_id`;
  which Assets a Resource contains is Resource management (#85). Owner-supplied
  free text (stage labels, messages, error metadata, reasons, progress units)
  must not reveal other documents.
- **Principle for any later tSSO-facing status view:** status is a Protected
  Observation, so a caller sees only readable documents and only `readiness`,
  without attention details or error blocks; unreadable documents return 404.
  Details belong to #56.

### Status reporting contract (Q8.3, R7b, R7d, R7e)

| Item | Contract |
|---|---|
| Reporters | Admission, canonical processing and each projection pipeline, each with its own service identity and a registered pipeline ID |
| Registration | Pipeline ID, owner team, support contact, start deadline, expected update interval, ordered stage list (`id` plus English `label`) with `stages_version`, and a resynchronization obligation |
| Attempt reports | `attempt_id`, `seq`, `stages_version`, `stage`, `state` (`pending`, `running`, `succeeded`, `failed`, `skipped`), optional `progress` (`done`, `total`, `unit`), optional English `message`, `method_version`, `manifest_ref`, `observed_at`, and an error block on failure |
| Ordering | Reports are ordered by `attempt_id` and `seq`; an out-of-order report is rejected with the current position instead of being ignored |
| Serving facts | Reported once per published product version as a manifest of included Assets with their Source and Canonical Revisions, within the product's scope (Resource). The platform expands it per document. Facts remain valid until replaced |
| Not started | The platform shows `pending` until the upstream handoff |
| Staleness | Only pending or running attempts past their deadline or interval become `progress_stalled`. Liveness is checked per pipeline, not per document |
| Retries | `retryable` means the owner retries automatically; exhausted retries become `product_failed` |
| Authority | Owners are authoritative. The platform keeps the latest state and bounded history, and can request a full resynchronization of serving facts |
| Interpretation | The platform interprets `state`, `retryable`, timing and serving facts. It does not interpret stages, error reasons or manifests |

### Error block (Q8.4)

Failed reports carry an error block modeled on AIP-193 `ErrorInfo`: `domain`
(the pipeline ID), `reason` (`UPPER_SNAKE_CASE`, one code per kind of error),
English `message`, `retryable`, `metadata`, `support_ref` (the owner's run or
trace ID) and `occurred_at`. Pipeline registration records the owner team and
support contact, so an application routes an incident by `domain`.

### Correlation (Q8.6)

The chain is `request_id` (equal to the workflow ID) → `asset_key` /
`source_revision_id` → `canonical_revision_id` → the published product version
that includes it, plus `batch_id`, a per-call `trace_id`, the reporter's
`attempt_id`, and the initiator and adoption sequence for refreshes. Every
status response carries these IDs. #31 is the single definition of these
fields, and #78 MVP observability uses them.

### Phasing (Q8.8)

| Phase | Scope |
|---|---|
| Now | The contract, including readiness rules and profile handling |
| Pilot | Reporters for admission, canonical processing, LLM-wiki and Retrieval; the user coordinates the LLM-wiki and Retrieval owners |
| Later | Other projections join without API changes |

The pilot target of 10 minutes from durable acceptance to searchable (#54 Q8 and
Q10) is measured by #78.

### Glossary (Q8.10, R8)

`CONTEXT.md` gains **Knowledge Profile**, **Context Readiness** and
**Projection Status Report**, and carries the round-1 **Tenant** and **Source**
entries onto the admission branch.

### Derived product readers and Corpus

- Derived product readers are recorded as
  [ADR-0007](../adr/0007-derived-product-readers-within-input-intersection.md),
  which now also states that withdrawal timing after a narrowing rebind follows
  #56.
- Whether the platform keeps a Corpus entity distinct from Resource belongs to
  #55. The preliminary recommendation is that a Resource serves as the Corpus in
  v1, while Materialization Input Snapshots remain.

### Superseded during round 3

- Q8.2a: "selected pipelines consume all accepted canonical data of that
  Source" and "existing documents adopt a profile change through reprocessing"
  (replaced by R2, R6 and #55 ownership of input scope).
- Q8.2b: target revision defined as the latest admitted revision, and the
  `blocked` and `unknown` states (replaced by R1a, R9 and R7a).
- Q8.9: a Source-facing `reprocess` command whose result becomes the target
  (replaced by R1c and R12).
- `reasons[]` (replaced by `serving[]` and `attention[]`, R11).

### Resolved in rounds 4 and 5

The items left open at the end of round 3 are decided in
[rounds 4 and 5](#confirmed-admission-decisions-on-2026-10-21-rounds-4-and-5).

## Confirmed admission decisions on 2026-10-21 (rounds 4 and 5)

Round 4 (Q9) fixed the API, document identity, deletion, retry, retention, the
workflow handoff, deployment and validation. Round 5 (Q10) checked the whole
rule set against concrete scenarios and a logic prototype, and split the
implementation. Industry evidence is in the
[research note](../research/admission-authorization-csp-practices-2026-10-20.md)
§17. The current contract, written for implementers, is the
[admission specification](knowledge-platform-admission-spec.md); this section
records the decisions and their reasons. Rounds 1–3 call the logical object
**Asset**; from round 4 it is **Document** (Q9.2b).

### Resources and routes (Q9.1, Q9.1b, Q9.1c)

- The upload session and the Batch are one `batch` resource with states
  `open`, `finalized` and `expired`. A batch is the history of one submission;
  a document's current truth is read from the document.
- Routes: `POST /v1/batches` (declare, `201`), `POST /v1/batches/{batch_id}/grants`
  (reissue upload grants), `POST /v1/batches/{batch_id}/finalize` (`202`),
  `GET /v1/batches/{batch_id}`, `GET /v1/requests/{request_id}`,
  `GET /v1/documents/{document_id}`, `GET /v1/documents` and
  `DELETE /v1/documents/{document_id}`.
- Conventions: `/v1` path versioning, snake_case JSON, RFC 3339 UTC times,
  AIP-158 pagination, AIP-193 errors, `Idempotency-Key` only on
  `POST /v1/batches`, and plain sub-paths (`/finalize`, `/grants`) rather than
  AIP-136 colon methods.
- Together these give a Source create, read, update (re-declaration) and delete
  for its documents. There is no `PATCH`.

### Document identity (Q9.2a–Q9.2c)

- `document_id` is assigned by the Source, unique within the Source, stable
  across versions, and the document's URL address: 1–256 characters from
  `[A-Za-z0-9-_.~:]`, case-sensitive. The same `document_id` updates the
  document; a different one is a different document.
- `document_uid` is generated by the platform. Deleting and recreating a
  `document_id` creates a new `document_uid`, following the Kubernetes name/uid
  split and AIP-148.
- The platform never infers a replacement. Deletion is explicit, and omission
  from a batch never deletes. v1 has no full-snapshot reconciliation and no
  rename (a rename is a create plus a delete). Applications reconcile with
  `GET /v1/documents`.
- One name, Document, is used in documents and in the implementation.

### Item fields and catalog information (Q9.2, Q9.3)

- An item has `document_id`, `files[]` (`path`, `role` `main` or `attachment`,
  `sha256`, `size`, `media_type`), optional `source_version`, `resources`,
  `uploaded_by`, `metadata`, `title` and `source_url`. Exactly one file has role
  `main`; paths are unique within the item. An unsupported main-file format is
  rejected at declaration (`UNSUPPORTED_FORMAT`); `media_type` is verified at
  finalization.
- Item results carry `index`, `document_id`, `document_uid`, `status`,
  `request_id`, `source_revision_id` and `error`.
- `title` and `source_url` are used by the platform for citations and display.
  Whether content is `unchanged` is decided at declaration, so an unchanged item
  needs no upload; its `title`, `source_url` and `metadata` still apply without
  reprocessing. A rejected item, for example a stale version, applies nothing.

### Source Metadata (Q9.2d, Q9.2e)

- `metadata` is an opaque string map for the Source's own use: at most 50 keys,
  keys of 1–64 characters from `[A-Za-z0-9_.-]`, values of at most 512
  characters, 8 KB in total. Each submission replaces the whole map; an omitted
  map keeps the current one and `{}` clears it. It creates no Source Revision
  and no processing.
- It is returned only to the submitting Source, in document reads and lists. It
  is not passed to projections or agents, is not filterable, is deleted with the
  document, and must not hold sensitive data.
- v1 has no filterable attributes; that question belongs to #55 and #76.
  Applications that want to filter results may post-filter with their own
  metadata.

### Identifiers in serving results (Q9.2f, Q9.2g)

- Serving results carry `source_id`, `document_id`, `document_uid`, `title` and
  `source_url`, disclosed like the content itself (to readers only). An
  application compares `source_id` with its own, then joins on `document_id`.
- The Source ID is a readable fixed string chosen at registration and given to
  the application with its credential. Source-facing inputs still never carry
  it. There is no `document_uid` filter on lists. This is a handoff to #76.

### Source Deletion (Q9.4)

- `DELETE /v1/documents/{document_id}` returns `202` and a delete request. The
  request is `received`, then `applied` (serving is blocked, by #56), then
  `enforced` (the required projections' serving facts no longer include the
  document; #31 judges this). Custody Purge is separate (#56, #57). Targets and
  the purge timing are in Q10.4–Q10.8.
- Readiness becomes `deleted` once deletion is applied. It is distinct from
  governance `withdrawn`, stays visible for 30 days and then returns `404`.
- Late processing results never restore a deleted document. Items declared
  before the deletion are rejected at finalization with `DOCUMENT_DELETED`.
  Recreating the `document_id` gives a new `document_uid`.
- Submit permission is enough to delete. A repeated `DELETE` returns the same
  delete request.
- Ownership: #31 owns intake, the durable fact, status and the enforcement
  judgement; propagation uses the #55 handoff channel and product removal
  belongs to #55; stopping disclosure belongs to #56; purge to #56 and #57.

### Corpus and Resource (Q9.5)

- In v1 a Resource is the Corpus. A rebind through the Resource API creates no
  processing request; #55 schedules any missing projection work.
- Deleting a non-empty Resource returns `409 RESOURCE_NOT_EMPTY`; there is no
  force option. Revisit if #55 separates Corpus from Resource.

### Failure attention (Q9.6)

`product_failed` is renamed `processing_failed`. It covers canonical processing
and the required projections, carries a `track` field, and the canonical owner
reports `cause: source | platform`. A `source` cause becomes
`source_revision_rejected`.

### Retry and platform redrive (Q9.7, Q9.7a, Q10.1h)

| Situation | What happens |
|---|---|
| Canonical processing failed for a platform reason (`processing_failed`) | The application may re-declare the same digests. This creates a new request for the same Source Revision: no upload, counted against quota, initiator `source`, linked to the failed request. It may also wait for the platform |
| Content was rejected (`source_revision_rejected`) | Re-declaring the same bytes returns `unchanged` with the attention unchanged. The Source must submit fixed content |
| The same content is already queued or processing | Re-declaring returns that active request (`queued`); no new request (Q10.1h) |
| The platform fixed the cause | Operators run a redrive: bulk re-runs for documents whose latest Source Revision is still platform-failed and has no active request, with no quota and at low priority. "Redrive" is an internal term |

At most one queued or processing request exists per (`document_uid`,
`source_revision_id`), enforced by a database unique constraint, so application
retries and redrives never run the same version twice.

### Retention (Q9.8)

- A request returns `404` 30 days after its terminal outcome.
- A batch returns `404` 30 days after all its items are terminal, or 30 days
  after it expired.
- An `Idempotency-Key` is kept for 24 hours.
- A deleted document returns `404` 30 days after deletion is applied.

### Workflow start input (Q9.9)

The start input is `request_id`, `document_uid`, `source_revision_id`, the files
(custody reference, `sha256`, `size`, `media_type`, `role`, `path`), the adopted
version and adoption sequence, the initiator, the priority and `trace_id`. #31
defines it and #80 implements it, aligned with the #91 manifest v2. Custody
belongs to #57, staging to #31 and Temporal to #78.

### Deployment (Q9.10)

One image with three roles: `api` (scaled by HPA), `dispatcher` (at least two
replicas, claiming with `SKIP LOCKED`) and CronJobs (reconciler every 5 minutes,
batch expiry hourly, retention daily). Admission has its own CNPG database.
Staging belongs to admission and custody to #57. The cluster topology belongs to
#78.

### Validation plan (Q9.11)

- **CI tier:** Testcontainers PostgreSQL and Temporal, failpoints at each commit
  and start boundary, and an adjustable clock for expiry and retention.
- **Cluster tier,** before the pilot and after infrastructure changes: kill the
  CNPG primary, kill API and dispatcher pods, a one-hour Temporal outage
  extrapolated to 24 hours, a backlog pause, and capacity runs. All sizing
  figures are marked unmeasured.
- A full 24-hour Temporal outage test runs before production, not before the
  pilot.
- **Pass criteria:** every `202` maps to exactly one workflow; nothing is lost or
  duplicated; status converges within one reconciler period; deleted documents
  never return.

### Scenario check and logic prototype (Q10.1)

The final scenario check found three corrections, seven rule gaps and eleven
missing scenarios. A
[logic prototype](https://github.com/davidlinnnn/data-ingestion/blob/prototype/31-admission-rules/docs/prototypes/admission-rules.prototype.html) models the rules
as a pure state module and runs 19 scenarios (135 steps) that cover all cases.
It first found one more gap (Q10.1h); after the fix every step passes.

**Corrections.**

- Fifty-one items in one declaration is a malformed request: `400
  TOO_MANY_ITEMS`. `429` is only for the rate limit.
- Readiness becomes `deleted` when deletion is applied, not when `202` returns.
- A batch reports its own items as history; current state is read from
  `GET /v1/documents`.

**New rules.**

- **Q10.1a:** an item is `declared` between declaration and finalization, then
  `queued`, `rejected` or `expired`.
- **Q10.1b:** the same `source_version` with different content is accepted only
  when that version was rejected (`source_revision_rejected`); otherwise it is a
  `VERSION_CONFLICT`.
- **Q10.1c:** each Source registers `ordering: source_version | arrival`. The
  default is `source_version`, under which `source_version` is required;
  `arrival` lets finalization order decide (for example manual uploads).
- **Q10.1d:** only changed files are uploaded. A file whose path and digest equal
  the latest Source Revision's is carried over from that document's custody;
  #57 must protect carried-over files.
- **Q10.1e:** a pilot pause rejects only new declarations (`503` with
  `Retry-After`). Open batches can still be finalized, so uploaded bytes are not
  wasted.
- **Q10.1f:** `GET /v1/documents/{document_id}` returns the current generation.
  A deleted earlier generation stays visible for 30 days through its delete
  request or `GET /v1/documents?readiness=deleted`.
- **Q10.1g:** the scenario table below replaces the round-5 draft.
- **Q10.1h:** content equal to the latest Source Revision while a request for it
  is queued or processing returns that request. This applies at declaration and
  at the finalization re-check.

| # | Scenario | Platform behaviour | Prototype |
|---|---|---|---|
| 1 | One batch: A new, B attachment changed, C unchanged with a new title, D `.xls` | `201`; A and B `declared` (B uploads only the attachment); C `unchanged` with the title applied; D `UNSUPPORTED_FORMAT` | 1 |
| 2 | Declaration times out; same key resent; same key, different body; key reused after 24 h | Replay; `422 IDEMPOTENCY_KEY_REUSED`; after expiry a new batch whose items are `unchanged` | 2 |
| 3 | Finalization times out and is repeated | The same result and request IDs | 2 |
| 4 | Lookup right after `202` | The request is `queued` even with no workflow yet | 3 |
| 5 | Attachment-only update | A new Source Revision (source-handoff validation case 1) | 1, 5 |
| 6 | Batch progress | Counts per item status; the batch is history | 1 |
| 7 | Platform failure, application retries twice, redrive runs | One retry request; the second retry returns it; redrive skips the document | 4 |
| 8 | Content rejected, then a fix under the same version | Old version keeps serving (`ready_stale`); resending the same bytes is `unchanged`; the fix is accepted | 5 |
| 9 | Stale version, version conflict, missing version, arrival ordering | `STALE_SOURCE_VERSION`; `VERSION_CONFLICT`; `SOURCE_VERSION_REQUIRED`; accepted (source-handoff validation case 2) | 6 |
| 10 | 51 items; too many declarations | `400 TOO_MANY_ITEMS`; `429 RATE_LIMITED` with `Retry-After` | 7 |
| 11 | Pilot pause | New declarations `503`; open batches still finalize | 8 |
| 12 | Authorization service down; grant revoked between declaration and finalization | `503 AUTHZ_UNAVAILABLE`, nothing admitted; the item is rejected at finalization | 9 |
| 13 | Missing upload, digest mismatch, all items rejected, batch expiry | Only that item is rejected; `422 ALL_ITEMS_REJECTED` with no batch; `409 BATCH_EXPIRED` | 10 |
| 14 | Binding conflict; another Source's document or Resource | `BINDING_CONFLICT`; `404`; `RESOURCE_NOT_FOUND` | 11 |
| 15 | Two sync processes send different and equal versions | Later finalization rechecks order: the older is stale; equal content returns the active request | 12 |
| 16 | Owner adopts a new version | Platform refresh; readiness unchanged; a failed refresh alerts only the owner | 13 |
| 17 | Source deletes C, then recreates it | `202`; `deleted` after apply; earlier-declared item `DOCUMENT_DELETED`; repeat returns the same request; new `document_uid` | 14 |
| 18 | Deletion while processing | The late result is recorded but never restores the document | 15 |
| 19 | Rebind | No processing request; `not_ready` until the new Resource's product includes it | 16 |
| 20 | A projection is added | `not_ready` until backfill | 17 |
| 21 | Agent result | `source_id`, `document_id`, `document_uid`, `title`, `source_url` | 18 |
| 22 | After 30 days | Request and batch `404`; the document remains; a deleted document `404` | 19 |

### Deletion follow-up (Q10.3–Q10.8)

- **Q10.3:** the user confirmed on 2026-10-21 that applications must be able to
  delete documents: a document that no longer exists must stop being found, and
  content that seriously violates security principles must leave the platform
  quickly. Accepted constraint 6 of #31 defers cancelling, modifying and deleting
  **tasks**; that still holds. Source Deletion deletes a **document** through a
  new delete request and cancels no running request. Document deletion is
  required #31 scope.
- **Q10.4:** v1 has only ordinary deletion. An application cannot trigger an
  immediate Custody Purge; custody and derived data are purged 30 days after
  deletion is applied, when the `deleted` record disappears.
- **Q10.5:** deletion has targets, both unmeasured and validated by I5:

  | Stage | What the application sees | Target |
  |---|---|---|
  | `received` | `202`, after the deletion fact is committed | Same call |
  | `applied` | Agents can no longer find, read or cite the document's own content; readiness is `deleted` | 1 minute |
  | `enforced` | Every required projection has removed the document and adjusted products derived from it, for example LLM-wiki pages | 10 minutes |
  | Custody Purge | Retained bytes and derived data are erased | 30 days |

  `applied` is reached by a serving-time block keyed by `document_uid` (#56 and
  #76), without waiting for index removal.
- **Q10.6 and Q10.6a:** each projection owner adjusts products derived from a
  deleted document, such as LLM-wiki pages that combine several documents,
  within the `enforced` target. The deletion reaches projections through the #55
  handoff channel with its `document_uid`, and each projection reports when it
  has finished; #31 judges `enforced` from those reports and the serving facts.
  The one-minute target covers the document's own content; derived products are
  covered by the ten-minute target.
- **Q10.7:** when deletion is applied, `title`, `source_url` and `metadata` are
  cleared, because a title can itself be sensitive. The `deleted` record keeps
  only identifiers, times and request IDs.
- **Q10.8:** for a security incident, the application deletes the document
  (unreadable within a minute) and the security team requests an immediate
  purge through the #56 governance path, with a dedicated role, approval and
  audit, like Microsoft Purview priority cleanup. An application-triggered purge
  is reconsidered only if needed.

### Source-handoff and canonical integration checks

| Check | How the admission rules satisfy it | Scenario |
|---|---|---|
| Attachment-only update | Content identity is the set of (path, digest) pairs; a changed attachment is a new Source Revision and only that file is uploaded | 5 |
| V08 old capture with a refreshed precondition | Ordering is checked at declaration and again at finalization; the API has no precondition field, so nothing but a newer `source_version` (or later arrival) can make a capture current | 9, 15 |
| V09 withdrawal, invalidation and cleanup | Late results never restore a deleted document; governance withdrawal stays with #56; carried-over files are protected by #57 | 18 |
| V10 redelivery and competing candidates | The workflow ID is the request ID; repeated finalization and re-declaration return the same request; a retry is a new request for the same Source Revision; candidate selection stays with canonical processing (R1a) | 3, 7, 15 |
| P01 fixed source and candidate identity | The start input fixes the Source Revision, file digests and adopted version; equal bytes in different documents are not merged | 1 |
| P07 processing completion versus acceptance | `succeeded` means processing completed; rejection reaches the Source as `source_revision_rejected` from canonical facts | 8 |
| P08 method update | A refresh is a new request with fixed versions and the previous result keeps serving | 16 |
| P10 current eligibility and status | Status exposes layer-owned facts; a result arriving after deletion is recorded without restoring eligibility | 18 |

### Implementation tickets (Q10.2)

| Ticket | Scope | Depends on |
|---|---|---|
| I1 Admission core | PostgreSQL schema, outbox, dispatcher, reconciler, the one-active-request constraint, Temporal start | #78, #80, #91 |
| I2 Batch API | Declaration, upload grants, finalization, staging to custody, idempotency, quota, `unchanged`, catalog fields and metadata, a minimal SDK | I1, #85, #57 |
| I3 Status | Report intake, readiness and attention, document, request and batch queries | I1, #55, #80 |
| I4 Deletion and retry | `DELETE`, the `deleted` state and enforcement judgement, application retry, redrive | I1, I3, #55, #56 |
| I5 Validation harness | The CI and cluster tiers | I1–I4, #78 |

The prototype's model is the starting point for the rules in I2 and I4. The SDK
becomes its own ticket only once the pilot client's language is known.

### Superseded during rounds 4 and 5

- Accepted constraint 6 of #31 is clarified, not replaced: it defers task
  cancellation, modification and deletion, which remain deferred; document
  deletion is required scope (Q10.3).
- The inherited "Assets without Corpus membership": replaced by Q9.5.
- Q2 "no Batch is created" when every item is rejected: true at declaration
  (`422`, no batch); at finalization the batch is finalized and no request is
  created.
- Q5 upload sessions: merged into the batch (Q9.1b).
- Q6a `unchanged`: now also requires that the latest Source Revision is not
  platform-failed and has no active request (Q9.7, Q10.1h).
- Q6b optional `source_version` with finalization order as the fallback:
  replaced by the per-Source `ordering` setting, and an equal version may replace
  a rejected one (Q10.1b, Q10.1c).
- Q8.1 item and session states: items gain `declared`; sessions are batches.
- Round 3 readiness and attention: readiness gains `deleted`; `product_failed`
  becomes `processing_failed`.
- Q8.5 and Q8.6 `asset_id` and `asset_key`: renamed `document_id` and
  `document_uid`.
- The round-3 status reporting contract's "exhausted retries become
  `product_failed`": they become `processing_failed`.

## Principle for later architecture documentation

Authorize delivery before delegating data transfer. Use the Valet Key pattern
to grant the client narrowly scoped, time-limited access to the required storage
resources. Establish complete, fixed and governed captured inputs before durable
processing admission. Delivery permission, processing authority and permission
to read published knowledge remain distinct.

Direct upload describes the path of file bytes. Presigned URLs, SAS and other
supported capabilities describe how storage authorizes that transfer; they are
mechanism choices within the delivery direction.

## AA mechanism under discussion

The existing company direction uses tSSO for user identity and GAM or
GAM-compatible authorization. Submission authority, reader access and
policy-management authority have separate meanings. The confirmed requirements
leave detailed token integration, check locations, validity and revocation
behavior to the owning design decisions. For the pilot, the service-account
credential issuer is Knowledge Platform as confirmed above; the company PAT
integration and protocol remain deferred.

A candidate minimal implementation authorizes a grant through the platform,
issues a temporary capability for a designated upload target, and checks current
submission authority and capture readiness at finalization/admission. It would
correlate the grant recipient, Source/Asset context, target and admission outcome
for audit. The Resource-binding re-check at finalization is confirmed below
(Q3.5); the remaining check schedule and mechanism are proposals awaiting
discussion.

Presigned URLs are bearer capabilities: possession can permit use within their
scope and validity. Grant-issuance attribution alone does not prove who actually
sent every byte. Round 2 (Q5, Q5b) accepts this bounded delegation with
one-hour grants, a finalization re-check and separate staging; withdrawal stops
admission rather than bytes already in transit. Expired sessions and staged data
are handled by Q5a.

## References

- [Inline content and storage-reference ingestion](../research/document-inline-reference-ingestion-2026-10-18.md) — delivery trade-offs and Bedrock evidence; no additional input mode selected.
- [Single and multiple-document admission: CSP API investigation](../research/document-batch-admission-csp-practices-2026-10-18.md) — evidence for the confirmed shared `items[1..N]` contract; detailed routes and scope remain open; partial admission is decided above.
- [Admission authorization, visibility and credential scope: industry practices](../research/admission-authorization-csp-practices-2026-10-20.md) — evidence for the round 1–5 decisions (Q3–Q10).
- [Valet Key pattern, Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/valet-key)
- [Confirmed source delivery and finalization direction](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L157)
- [Original cloud-practice investigation and decision history](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/research/attachment-handoff-cloud-practices-2026-10-02.md)
- [Confirmed company AA requirements](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6230755901)
- [Source authorization and enforcement-boundary handoff](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520)
- [S3 presigned URL scope, bearer semantics and reuse](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
