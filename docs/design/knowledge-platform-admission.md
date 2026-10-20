# Knowledge Platform admission design notes

Active design for [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31),
within the existing Knowledge Platform wayfinder map. Confirmed choices below
are inputs to the continuing design; the admission contract remains open.

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
  intersection; for appearing in several knowledge scopes, Corpus membership
  rather than binding. Uploading the same document twice is discouraged; if used,
  the copies are distinct Assets managed independently.

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
  creates a new Source Revision; equal bytes in another Asset are not merged;
  method-only reprocessing is outside submission.

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

### Still open

- Status definitions and the unified status query, including correlation IDs
  across request, processing, Canonical Acceptance and projection publication.
- Exact routes and field names.

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
- [Admission authorization, visibility and credential scope: industry practices](../research/admission-authorization-csp-practices-2026-10-20.md) — evidence for the Q3 decisions.
- [Valet Key pattern, Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/valet-key)
- [Confirmed source delivery and finalization direction](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L157)
- [Original cloud-practice investigation and decision history](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/research/attachment-handoff-cloud-practices-2026-10-02.md)
- [Confirmed company AA requirements](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6230755901)
- [Source authorization and enforcement-boundary handoff](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520)
- [S3 presigned URL scope, bearer semantics and reuse](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html)
