# Captured-source identity and authorization handoff

[Design index](README.md) · [Confirmed overall logical baseline](knowledge-platform-logical-design.md)

**Status:** Q1–Q7 confirmed on 2026-09-30; Q8/Q10 confirmed on 2026-10-02;
Q9/Q11 confirmed on 2026-10-03; Q12/Q13 confirmed on 2026-10-05.
Q1–Q13 are confirmed. The detailed source-handoff design is open. This document assembles the implications of the
[Q1–Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124) and
[Q6/Q7 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945), and
[Q4 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912631142), and
[Q5 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133), and
[Q8/Q10 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014), and
[Q9 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936), and
[Q11 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5968626647), and
[Q12/Q13 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520) in
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
metadata-only changes and reuse mechanisms remain open; Q11 establishes ordering
and conflict principles while their concrete representation remains detailed work.

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
reuse requires compatible inputs/methods. Q11 establishes change-applicability and
conflict principles. Exact identity/order/precondition representation, metadata-only
changes, reuse rules and retained-identity lifetime remain open.

### Q5 — Trusted reader policy before normal admission

Normal ingestion admission requires a trustworthy, explicit reader policy whose
meaning the platform supports. Verify submitter identity and Source-scoped
authority separately from the document's permitted audience. Reader policies may
identify employee accounts or groups, or use a trusted authorization-target binding
under Q12. This does not require copying an enterprise employee directory; exact
identity/policy mappings remain detailed work. Upload authority does not permit
broadening the source-authorized audience.

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
omission from a batch does not establish source deletion. Q11 establishes ordering
and conflict principles. Q12/Q13 below establish continued-authorization trust and
acknowledgement meanings.
Detailed ordering mechanisms, change recovery, freshness bounds and public exposure
remain with the downstream owners. Changes inside an authoritative policy service
follow Q12; they do not require resubmitting the captured content.

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
Platform-managed authorization-binding changes and explicit withdrawal need the
governed lifecycle channel after capture. Changes inside an authoritative policy
service follow Q12's validity contract. Revoking source storage credentials alone
does not enforce downstream governance.

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

### Q11 — Duplicate, delayed and conflicting changes

Identify each change and its affected scope. Within the agreed deduplication
contract, redelivery must not apply the same change twice, and one change identity
cannot be rebound to conflicting payloads. Establish applicability using trustworthy
source-order evidence or an explicit expected prior platform state. Arrival/completion
time, ordinary timestamps, names and hashes alone do not establish source order or
authority. Source Revision identity does not imply a sortable sequence.

An expected-state check prevents accidental overwrite but does not prove which source
content is newer. If applicability cannot be established, expose a conflict for
authoritative confirmation/resubmission. A delegated adapter may resolve supported
cases automatically; routine human approval is not required. The authorized submitter
can be a script, adapter or application acting within its Source-scoped grants; two
competing submissions may be two runs of that same program. Capturing source inputs
is distinct from observing the platform state used as an update precondition.

Apply these rules by affected content, metadata and governance scope. A valid
historical observation must not become the latest known source observation merely
because it arrived later. Canonical Acceptance and eligible-version selection keep
their separate rules. Late content/results cannot restore superseded reader policy
or withdrawn access; unrelated newer content must not suppress an applicable
restriction. Current governance and fail-closed obligations remain in force.

For example, A captures S1 and transfers slowly; B captures a genuinely later S2 and
hands it off first. Trustworthy source ordering prevents S1's later arrival from
replacing S2 as the latest known source observation. Without such ordering evidence,
A and B may both submit conditional updates expecting platform state P1: once B
changes that state, A's precondition fails and requires reconciliation. S1/S2/P1 are
illustrative labels, not an accepted schema or evidence of order by themselves.

Temporal supplies durable execution/retries; domain applicability rules remain
part of the contract. Exact identifiers, order/precondition fields, atomic application,
deduplication windows and conflict responses remain detailed design. No global counter
or numeric freshness bound is selected. Q12/Q13 establish the trust and
acknowledgement principles below.

### Q12 — Trusted authority and continued authorization validity

Each Source declares an accountable policy authority, authoritative policy source,
and evidence/update/confirmation obligations. The Source Owner defines policy or
explicitly delegates that responsibility. Policy ownership, management interface,
decision evaluation and enforcement are separate responsibilities. The platform
does not require a copy of every employee account. The source-authorized audience
remains the ceiling; platform operation or upload authority cannot broaden it.

An authorized actor must establish or change the attributable binding between an
Asset and its authorization target. Space is one possible target, not a mandatory
model; a relation such as membership and an action such as read are distinct.
Corpus membership grants no additional access. Callers cannot supply an arbitrary
permissive target or decision service as proof of authority.

Separate authorization decisions from enforcement. Deployments may use GAM or a
compatible authorization service through a trusted common decision contract.
Compatibility includes decision meaning, applicability and validity, not just API
shape. Source policy remains source-controlled regardless of the management UI's
location. No concrete GAM capability, protocol, SDK or policy engine is qualified
or selected here.

People and workload identities both require authorization. Background processing
and materialization use scoped work permissions. Operations on behalf of a user
must preserve verified user authority and delegation; broader background grants
must not widen that user's access. Authentication credentials do not establish
permission, and read permission does not confer policy/lifecycle management rights.
Checks belong at the applicable admission, management, read and artifact boundaries;
this does not require per-employee checks inside every parser/OCR step or a remote
GAM call for every workload check.

The platform defines common governance obligations; Canonical and projection
owners enforce them at their boundaries. Each projection retains its product API
and may add restrictions without expanding the source-authorized audience. Content,
existence, summaries, citations, attachments and protected status require applicable
authorization. Mixed-source products require sufficient lineage and enforceable
restrictions; detailed derivation rules belong to governance design.

Use authorization decisions only within their applicable scope and validity.
Distinguish a trusted denial from unavailable or unverifiable authorization. Without
a trustworthy basis, stop the affected disclosure; unrelated authorized work need
not stop. Re-establish trustworthy authorization before restoring access. An
applicable platform withdrawal cannot be undone by a provider allow result or a
late processing result. Fixed captured inputs are not permanent grants.

Policy/membership changes inside the authoritative service need not resubmit or
reparse content; observe them through the selected validity contract. Platform-managed
document/target binding changes and explicit withdrawal follow the controlled
lifecycle channel and Q11 applicability rules. Exact scopes/delegation proofs,
provider trust, cache/freshness bounds, missed-change detection, outage/recovery and
enforcement tests remain detailed design. No instantaneous global revocation or
numeric validity guarantee is implied.

### Q13 — Governance acknowledgement and completion meanings

Distinguish durable receipt and responsibility for a request, application of its
governance state, and evidence that the declared enforcement boundary is satisfied.
Report incomplete portions explicitly. Receipt alone cannot mean every downstream
interface has applied a restriction. Physical custody purge has a separate
completion condition and evidence; stopping disclosure does not prove deletion.

Temporal supplies durable execution/retry/recovery. Each domain owner supplies
the relevant completion facts. This does not prescribe three endpoints/status
enums, a synchronous global barrier, or a new status service. The existing
processing-admission `202` promise is unchanged. Admission owns public exposure;
governance owns enforcement scope/timing/validation; governance and persistence
own detailed purge obligations and mechanisms.

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
purged; physical purge follows its separate custody obligations. Q11 establishes
ordering/conflict principles; Q12/Q13 establish authorization trust and
acknowledgement meanings. Detailed mechanisms, numeric freshness bounds, public
exposure, missed-change recovery and enforcement validation remain open.

## Unified lifecycle/status design requirement

The user also accepted the [unified lifecycle/status-query scope amendment](https://github.com/davidlinnnn/data-ingestion/issues/31#issuecomment-5991846818)
on 2026-10-05. It supersedes the earlier deferral of cross-projection aggregation.
The admission/status owner holds that decision; this source ticket supplies Q13's
acknowledgement meanings. Implementation phasing remains undecided. A unified query
does not select a new service/database, one workflow, simultaneous publication or
a universal knowledge-serving API. Domain facts retain their Canonical/projection
owners; protected status remains subject to governance.

## Proposed next round — Q14 (unconfirmed)

The [Q14 proposal](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991924147)
asks how the first slice handles two documents sharing a required image when their
audiences or source authorities differ. The recommendation is complete-package
authorization coverage under supported attributable policy, rejection when required
restrictions cannot be preserved, and explicit per-reference version/authority and
withdrawal scope. Physical sharing must not merge logical rights or release another
document's required retained input. Standalone attachment Assets, per-fragment
masking and a generic policy-composition engine are not assumed. The user has not
accepted this recommendation; it is not part of Q1–Q13.

## Remaining source-handoff frontier

Q1–Q13 are confirmed. Before the final source-facing review, complete illustrative
PDF/PPTX handoff cases alongside the Markdown/image case, and resolve the policy,
withdrawal and dependency boundaries for shared attachments. Assemble one reviewed
handoff showing identity, fixed artifacts/relationships, integrity/custody, policy
authority/validity, operation/scope/applicability and acknowledgement meanings.
Illustrative cases are not runtime format qualification. This ticket remains open.

Concrete APIs/status, ordering/deduplication mechanisms and finalization atomicity
belong to admission; package/identity/locator representation belongs to canonical
design; validity/lapse/recovery and enforcement validation belong to governance
with operating targets from the envelope owner; custody release/reference protection
and purge mechanisms belong to persistence with governance. These named downstream
decisions do not all need to be resolved within the source-facing ticket.

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

[Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55)
owns projection handoff/status contributions and independent publication semantics.
[Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56)
owns cross-boundary authorization validity, enforcement and completion evidence.
[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57)
owns custody/reference protection and persistence mechanisms, using targets from
[Set the first-adoption workload and operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54).
