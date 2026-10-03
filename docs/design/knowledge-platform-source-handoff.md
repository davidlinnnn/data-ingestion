# Captured-source identity and authorization handoff

[Design index](README.md) · [Confirmed overall logical baseline](knowledge-platform-logical-design.md)

**Status:** Q1–Q7 confirmed on 2026-09-30; Q8/Q10 confirmed on 2026-10-02.
Q9 and the remaining detailed source-handoff design are open. This document assembles the implications of the
[Q1–Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124) and
[Q6/Q7 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945), and
[Q4 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912631142), and
[Q5 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133), and
[Q8/Q10 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014) in
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
hyperlinks remain references, without automatic recursive acquisition. Package
representation, missing-dependency outcomes and shared-attachment lifecycle remain
open.

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

### Q10 — Governed retention of original captured inputs

Keep original Capture Packages for applicable reprocessing and evidence obligations;
completion of the first parse is not by itself a cleanup trigger. Processing
intermediates have a separate cleanup lifecycle. Accountable custody covers the
processing/acceptance handoff and protects adopted dependencies. Retention/deletion
follows explicit policy and applicable erasure obligations; this does not promise
indefinite retention. Approved equivalent custody can avoid another byte copy.
Exact durations, resource costs and cleanup/purge/reference-protection mechanisms
remain with operating-envelope, persistence and governance design.

## Next frontier — proposed, not confirmed

The [Q8/Q10 confirmation and Markdown-image clarification](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014) records the
accepted decisions and the remaining Q9 proposal. Q9 is not yet confirmed.

| Question | Decision to resolve |
|---|---|
| Q9 | Required image dependencies, attachment-reference/capture handoff, required-package failures and whether to allow partial source packages |

For Q9, recommend treating image references used as actual Markdown document
content as required dependencies by default. Authorized capture resolves and fixes
needed bytes before normal durable processing admission, or validates already
supplied bytes. Ordinary text hyperlinks remain references. Canonical processing
consumes the fixed package and preserves image/document relationships, original
source references and durable artifact/evidence bindings. Governed artifact custody
can retain the bytes without placing them in the metadata DB or fetching the live
URL again. OCR/image understanding follows the selected attributable profile; a
required enrichment must complete before processing success.

The missing-dependency rule is still a proposal: known required-image gaps prevent
normal admission until corrected; problems discovered after admission produce an
explicit failure rather than silently complete output. Detailed package/image
schemas remain open.

The initial [attachment-transport proposal](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953922681)
preferred a registered source-storage connection. Following the user's concern
about onboarding independent Source Owners, the
[revised recommendation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5955412525)
**supersedes that unaccepted default; Q9 remains unconfirmed**. The
[cloud-practice evidence](../research/attachment-handoff-cloud-practices-2026-10-02.md)
separates official AWS/GCP mechanics from this platform recommendation.

Prefer platform-issued direct-upload authorization as the general handoff path.
An authorized submitter requests a bounded upload session; the platform grants
access to assigned object locations in platform-controlled storage. The provider
transfers bytes directly to storage and submits the document/attachment manifest.
The platform verifies completeness, exact stored versions, integrity and custody
before processing admission. This avoids per-provider storage credentials and
proxying all bytes through the application API. Source registration, delegated
submission and trustworthy reader policy remain required; self-service onboarding
must still establish those authorities.

Provider-issued, version-bound signed GET URLs are an optional bounded import path.
They avoid storing broad long-lived provider credentials, but require permitted
network reachability, bounded fetch validation/authorization and a clear expiration
or same-version reissue outcome. A signed URL is neither durable artifact identity
nor a retention/reader-policy guarantee. Persistent cross-account/federated access
remains an opt-in integration for ongoing acquisition or approved source-side
custody; it still needs trust/resource grants and does not become a prerequisite
for every submission. Admission design selects the pilot's needed mechanisms;
do not require multiple adapters merely for symmetry.

Upload/import session creation is distinct from accepting ready processing inputs.
Finalize only after the platform verifies required artifacts and binds exact
object versions/generations or equivalent immutability with accountable custody.
A caller's completion notification or an object-created event alone is insufficient.
Do not assume an upload URL is one-use or that later writes cannot change its key.
Public endpoints/status, finalization atomicity and any HTTP `202` changes remain
admission design; the confirmed Q3 processing-admission guarantee is preserved.

All supported paths converge on the same fixed Capture Package. This proposal does
not select a cloud vendor or introduce recursive crawling/general live connectors.
Video objects illustrate transport needs, not a promise of video processing.
Supported types, size/cost limits and cleanup remain explicit design work. Required
image and missing-dependency rules above still await the user's Q9 answer.

The [final recommendation under the deployment premise](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966660481)
incorporates the user's expectation that separate organizations may operate their
own installations with heterogeneous sources and permissions. Possible Helm
packaging is context, not a selected delivery contract. **This remains a proposal.**

The reusable product boundary is the complete fixed Capture Package with
attributable Source/Asset/revision identity and trusted reader-policy evidence.
Acquisition transport, format interpretation and policy interpretation remain
separate responsibilities. Canonical processing and projections consume governed
inputs without acquiring source-specific credentials or refetching changing URLs.
Prefer direct upload as the common entry; enable bounded signed-GET import where
needed and permitted, and add connectors for demonstrated source integration needs.
Already eligible artifacts in approved custody need no mandatory duplicate upload.

Each deployment operator configures the installation's custody storage, platform
identity/identity-provider integration, supported policy interpretation, network
boundaries, secret references and resource/retention limits. Recommend managing
Source registrations and delegated grants as governed application data, with
self-service within verified authority, rather than editing Helm values or
redeploying for each Source. Source Owner/policy authority retains content and
audience accountability; a delegated provider/adapter performs capture or delivery;
the platform verifies authority/readiness and enforces custody/current governance.
These roles do not imply separate services or a generic plugin framework.

Heterogeneous authorization cannot be assumed automatically interchangeable.
Source integrations must preserve meaning in a supported policy contract; missing
or unsupported required policy still rejects normal admission under Q5. Transport
permission never substitutes for reader policy. Withdrawal/policy changes continue
through the explicit lifecycle channel even after source credentials are revoked.

Recommend one pilot-qualified custody backend and the direct-upload/finalization
path for initial admission-scope review, retaining the fixed-reference processing
seam. Add other acquisition mechanisms only for demonstrated needs. This is not a
new implementation order or a change to the qualified PDF core. API/status and
finalization atomicity, manifest/policy schemas, retention limits and deployment
packaging remain detailed design; necessary implementation changes follow the map's
versioned integration/migration checkpoints. Required Markdown dependencies and
failure rules above remain part of Q9 awaiting explicit user confirmation.

Subsequent branches include change ordering and policy freshness, custody release,
concrete package validation, and reviewed PDF, Markdown and PPTX examples. Format
design does not expand the PDF core's qualified support.

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
