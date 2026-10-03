# Captured-source identity and authorization handoff

[Design index](README.md) · [Confirmed overall logical baseline](knowledge-platform-logical-design.md)

**Status:** Q1–Q7 confirmed on 2026-09-30; Q8/Q10 confirmed on 2026-10-02;
Q9 confirmed on 2026-10-03. Q1–Q10 are confirmed; the remaining detailed
source-handoff design is open. This document assembles the implications of the
[Q1–Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124) and
[Q6/Q7 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945), and
[Q4 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912631142), and
[Q5 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133), and
[Q8/Q10 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014), and
[Q9 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936) in
[Define captured-source identity and authorization handoff](https://github.com/davidlinnnn/data-ingestion/issues/53).
Issue records remain authoritative. Question numbers here belong to this ticket,
not the earlier overall-design interview.

## Confirmed decisions

### Q1 — Source authority and delegated submission

Register the governed Source and explicitly delegate submission on its behalf.
Distinguish original Source Owner accountability, capture/submission responsibility,
and authority to provide or confirm source-access policy. Roles may be co-located;
this does not prescribe separate services or a management UI. Upload authority
does not grant authority to broaden the source audience. A delegated llmwiki client
does not become the original Source Owner simply by forwarding files.

Q7 below selects the initial team/collection direction and responsible roles;
actual identities and delegation grants must be bound during adoption.

### Q2 — Stable logical Asset identity

Within a Source, use a trustworthy stable native identity to resolve an Asset when
available. Otherwise allocate an identity on explicit creation and require explicit
reuse for updates. Names, paths, URLs, storage locations and content digests do not
automatically define logical identity. Renaming, relocation and content updates can
preserve an Asset. Equal bytes across Sources do not automatically merge Assets;
physical byte deduplication remains a separate storage choice. Corpus membership
reuses the Asset identity and does not expand access.

Q4 below distinguishes source-version identity from processing requests. Detailed
metadata-only changes, observation ordering and reuse rules remain open.

### Q3 — Capture readiness and custody before admission

Before durable processing admission returns `202`, captured inputs must have fixed
immutable versions, integrity information, and accountable custody supporting
retrieval through the agreed queueing, suspension and retry period. Workers still
verify integrity on access. Platform custody or an explicitly approved equivalent
arrangement can satisfy this without necessarily copying bytes again.

A short-lived URL can be a renewable access mechanism over a durable object
identity and custody arrangement. An arbitrary local path, an unprotected expiring
URL, or fetching latest only when execution begins does not establish that guarantee.
The boundary does not require synchronous parsing/OCR and does not mean Canonical
Acceptance. Exact custody duration/release and withdrawal/purge handling remain open.

### Q4 — Source Revision versus processing request

An Asset identifies a logical document; its Source Revision identifies a captured
source version/observation. A processing request is a work order over selected
captured inputs and methods. Redelivery preserves the Source Revision. Admission
request deduplication applies; workflow/activity retries do not by themselves
create a new source version or deliberate processing request.

Method-only reprocessing retains the Source Revision and uses a new request. An
explicitly new source version/observation can have a new Source Revision even when
bytes are equal; ordinary re-upload alone does not establish a new source version.
An existing observation identity cannot be silently rebound to conflicting content.
Use reliable native source-version identity where available, otherwise an explicit
capture identity reusable on redelivery. Digests support integrity and possible
reuse, not source-version identity by themselves.

New source observations do not inherently require repeating all expensive work;
reuse requires compatible inputs/methods. Exact identity representation, ordering,
metadata-only changes, reuse rules and retained-identity lifetime remain open.

### Q5 — Trusted reader policy before normal admission

Normal ingestion admission requires a trustworthy, explicit reader policy whose
meaning the platform supports. Verify submitter identity and Source-scoped
authority separately from the document's permitted audience. Reader policies may
identify employee accounts or groups; exact directory mappings remain detailed
work. Upload authority does not permit broadening the source-authorized audience.

Carry attributable policy evidence or reference an explicitly authorized registered
Source default. Establish its responsible authority and applicability rather than
accept an arbitrary uploader assertion. Missing, untrustworthy or unsupported
required policy/authority causes normal admission to be rejected until corrected
and resubmitted. Valid inputs proceed automatically, without per-document human
approval. Current governance continues to apply after capture; the captured policy
is not a permanent access grant.

Policy representations, version/observation fields, change delivery, ordering and
freshness remain detailed work. This does not select an identity provider, protocol,
policy engine, quarantine service or approval queue.

### Q6 — Finite capture packages

A Capture Package comprises the main document and explicitly declared dependencies
required to interpret it. All included artifacts have fixed versions and integrity
information under the Q3 custody guarantee. A self-contained PDF/PPTX may be one
file; Markdown with required relative images includes those images. Ordinary
hyperlinks remain references, without automatic recursive acquisition. Q9 below
resolves required-image and missing-dependency handling. Package representation
and shared-attachment lifecycle remain open.

### Q7 — Initial team and document collection

Start with the engineering team responsible for the Knowledge Platform and a
controlled collection of technical/operations documents it maintains and is
allowed to ingest. The document-owning role retains content/publication
accountability. Capture/submission is delegated to an authorized program or
operating role. The designated data-access role supplies/confirms source policy;
platform operation alone does not confer that authority. This selects the pilot
boundary and roles, not named-person assignments or already-provisioned grants.

Make the document inventory and concrete identity/delegation bindings explicit
for adoption. Numeric workload, concurrency and resource targets remain with
[Set the first-adoption workload and operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54).

### Q8 — Explicit lifecycle changes from the controlled source

The accountable source/data role or an appropriately delegated program explicitly
submits captured content updates, platform-catalog display metadata changes,
reader-policy changes, confirmed source deletion and withdrawal through a
controlled interface. Each operation needs appropriate authority; submission
permission does not imply authority over all lifecycle operations.

Catalog-only display names/notes do not inherently re-run parsing/OCR. Policy
changes affect eligibility and dependent serving without requiring content
re-parsing. Confirmed deletion/withdrawal invokes urgent stop-disclosure handling
for its declared scope without waiting for ordinary rebuilding. Fetch failure or
omission from a batch does not establish source deletion. Ordering, acknowledgements,
recovery, missed-change detection and policy freshness remain detailed work.

### Q9 — Complete capture handoff across delivery methods and deployments

The common product input boundary is a finite, complete, fixed Capture Package,
with attributable Source/Asset/Source Revision identity and trustworthy policy
evidence at handoff. Acquisition transport, format interpretation and policy
interpretation have separate responsibilities. API requests need not embed file
bytes, and existing eligible artifacts in approved custody need no mandatory
second upload or copy.

Image references used as actual Markdown document content are required capture
dependencies by default. Preserve each image/document relationship, original
source reference and exact durable artifact/evidence binding. Ordinary text links
remain references without recursive crawling. Known missing required files prevent
normal processing admission; required-input failures found afterward produce an
explicit failure, not a silently complete result. The first slice does not accept
partial source packages. Other independently admitted documents may still succeed.

Capture readiness is distinct from semantic interpretation, processing completion,
Canonical Acceptance and projection publication. OCR/image understanding follows
the selected attributable profile; required enrichment must complete before
processing success. Retained image bytes alone do not establish understanding and
need not be stored as DB BLOBs. This does not expand qualified processing formats.

Use platform-issued direct upload as the common entry. Providers transfer bytes
directly to assigned storage locations and complete the manifest/finalization
flow; provider/adapter retries the transfer. Bounded provider-issued signed-GET
import is optional where sources benefit and network/security policy permits it;
the platform fetches/retries, with same-version renewal or explicit failure when
a grant expires. Persistent delegated source connections are optional integrations
for demonstrated needs. Do not require all three mechanisms initially or extend
the first slice to general live synchronization. The
[cloud-practice evidence](../research/attachment-handoff-cloud-practices-2026-10-02.md)
supports these mechanics and distinguishes them from detailed control choices.

Issuing an upload/import task does not establish Q3 processing admission. The
platform verifies completeness, exact retained versions, integrity and custody
before that boundary. A caller completion notification or object-created event
alone is insufficient. Neither reusable upload grants nor mutable object keys
may change already finalized inputs. Temporary access is not durable identity,
reader policy or a retention guarantee.

Organizations may run independent installations. Deployment operators configure
custody storage, platform identity/identity-provider integration, supported policy
interpretation, network boundaries, secret references and resource/retention limits.
Manage Source registrations and delegated grants as governed application data,
with self-service within verified authority, rather than requiring Helm edits or
redeployment for each Source. Possible Helm distribution remains deployment context,
not a selected packaging implementation. Source Owner/policy authority retains
content/audience accountability; a delegated provider/adapter handles delivery;
the platform validates readiness and enforces custody/current governance. These
roles do not require separate services or a generic plugin framework.

Source integrations must preserve authorization meaning in a supported policy
contract. Missing or unsupported required policy still rejects normal admission
under Q5. Submission, transfer and employee reading permissions remain distinct.
Policy/withdrawal changes need the explicit lifecycle channel after capture;
revoking source credentials alone does not enforce downstream governance.

Initial admission-scope planning prioritizes one pilot-qualified custody backend
and direct-upload/finalization, retaining the fixed-reference processing seam.
Exact APIs/status, finalization atomicity, manifest/policy schemas, numeric limits,
retention mechanisms and deployment packaging remain with the detailed design
owners. Necessary PDF-core changes follow versioned integration/migration rather
than changing target contracts to match existing implementation.

### Q10 — Governed retention of original captured inputs

Keep original Capture Packages for applicable reprocessing and evidence obligations;
completion of the first parse is not by itself a cleanup trigger. Processing
intermediates have a separate cleanup lifecycle. Accountable custody covers the
processing/acceptance handoff and protects adopted dependencies. Retention/deletion
follows explicit policy and applicable erasure obligations; this does not promise
indefinite retention. Approved equivalent custody can avoid another byte copy.
Exact durations, resource costs and cleanup/purge/reference-protection mechanisms
remain with operating-envelope, persistence and governance design.

## Markdown-image consistency check against merged research

The [feedback disposition](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966742941)
incorporates the merged [Docling capability research](https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md)
as corroborating evidence. No Q9/Q10 reversal is needed. Its Markdown case is
illustrative, not measured format qualification; its PDF page-checkpoint capture
and remote-inference base64 transport do not establish source-capture implementation
or an ingestion-API upload requirement. It supplies no new basis to reorder delivery
modes or retain every processing artifact forever.

The following is a design consistency walkthrough, not an accepted wire schema or
runtime test. Assume an authorized Source submission and trustworthy reader policy.
`procedure.md` at fixed artifact version M1 contains
`![Review flow](assets/flow.png)`; required image version I1 is explicitly bound in
the same captured source observation. M1/I1 are illustrative identifiers.

| Boundary | Required outcome |
|---|---|
| Fixed inputs and relationships | Each artifact has integrity/custody information. Preserve the Markdown image occurrence and original `assets/flow.png` target, bound to I1. Exact native line/block and attachment fields remain canonical/package design. |
| Readiness | Known missing I1, integrity mismatch or unestablished custody prevents normal processing admission. A required-input problem found later produces explicit failure. |
| Retry and source change | Retry uses M1/I1. A source-path replacement cannot silently change this package; a new captured observation follows the revision/update contract. |
| Interpretation and acceptance | Capture establishes input readiness. Processing follows the selected profile and preserves distinct source/OCR/generated origins. Canonical Acceptance is separate. |
| Q10 cleanup | First-parse completion alone cannot release M1/I1 or adopted evidence. Unadopted intermediates follow separate cleanup policy; adopted dependencies remain protected under applicable retention/erasure obligations. |
| Withdrawal during processing | An authorized withdrawal must not be undone by a late successful result. Current governance prevents renewed eligibility/disclosure; exact enforcement boundaries and propagation validation remain detailed design. |

The Source Owner/designated policy authority or appropriately delegated program
supplies an attributable lifecycle signal identifying affected Source/Asset/revision
scope. The platform verifies authority/scope, records/applies the governance change
and coordinates enforcement for canonical reads, evidence access and dependent
publication/serving. Projection owners retain their publication/serving obligations.
An expired URL, revoked storage credential or failed fetch is not itself a reliable
withdrawal/deletion signal. Signal receipt does not mean all dependent copies are
purged; physical purge follows its separate custody obligations. Ordering, freshness,
acknowledgements, missed-change recovery and enforcement validation remain open.

## Remaining source-handoff frontier

Q1–Q10 are confirmed, not a complete implementation-ready specification. Remaining
branches include source/metadata/policy change ordering and concurrency, policy
freshness and missed-change recovery, custody release, exact package validation,
shared attachments, PDF/PPTX walkthroughs and remaining Markdown representation
details. The example above checks consistency, not runtime format qualification. Detailed
transport/status/finalization, canonical representation and governance enforcement
continue with the existing linked design owners. This ticket remains open.

## Integration and ownership

The [wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52) makes
confirmed target contracts authoritative. Workflow/API differences become versioned
implementation migration or integration work, with validation at the map's existing
follow-through checkpoints. Measured resource configurations inform the operating
envelope within their qualified scope.

[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31)
owns transport, public request/status semantics and admission persistence/atomicity.
[Design canonical schema and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32)
owns the canonical representation and lifecycle contract. This source-boundary
decision supplies their identity, capture and authorization prerequisites.
