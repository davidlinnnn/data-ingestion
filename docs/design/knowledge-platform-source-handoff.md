# Captured-source identity and authorization handoff

[Design index](README.md) · [Confirmed overall logical baseline](knowledge-platform-logical-design.md)

**Status:** Q1–Q7 confirmed on 2026-09-30; Q8/Q10 confirmed on 2026-10-02;
Q9/Q11 confirmed on 2026-10-03; Q12–Q14 confirmed on 2026-10-05.
Q1–Q14 and the final source-facing handoff are confirmed. The user accepted the
independent spike disposition and source-facing resolution on 2026-10-05. Detailed
contracts continue with the named downstream owners. This document assembles the
implications of the
[Q1–Q3 decision record](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124) and
[Q6/Q7 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945), and
[Q4 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912631142), and
[Q5 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133), and
[Q8/Q10 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014), and
[Q9 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936), and
[Q11 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5968626647), and
[Q12/Q13 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520), and
[revised Q14 confirmation](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5992838620) in
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
Use reliable native source-version identity where it identifies the complete
captured observation, including required dependencies; otherwise use an explicit
capture identity reusable on redelivery. If the main file's native version is
unchanged but a required dependency changes, record a distinguishable new Source
Revision without rewriting the old observation. Retain the main file's native
version as source evidence where applicable. Digests support integrity and possible
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
resolves required-image and missing-dependency handling. Q14 scopes attachment
identity to the package and excludes initial global shared-attachment management.
Concrete package representation remains with canonical design.

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

### Q14 — Package-scoped attachment identity

Attachment identity belongs to its Capture Package/document-version scope. Preserve
each package's attachment references, exact artifact versions and source relationships.
Equal bytes, equal hashes or a reused source URL do not automatically merge identity,
authority or lifecycle across documents. Redelivery/retry of the same fixed input
preserves its identity under Q4/Q11. Exact ID fields and within-document occurrence
representation remain canonical design.

The first slice does not build a global shared-attachment catalog, cross-document
attachment-update feature or automatic cross-document deduplication. Revisit these
only for a concrete shared-management need or measured storage-cost case; they are
not mandatory later implementation work. Logical identity and physical storage
remain separate. Existing eligible artifacts in approved custody need no forced
second upload/copy; any actual reuse still preserves Q3/Q9/Q10 custody obligations.

Different IDs or copies do not create permission. A package still needs trustworthy
authorization covering required contents, and applicable scoped restrictions or
withdrawal still apply under Q5/Q12. Copying or relabeling cannot make unsupported
or untrustworthy policy acceptable.

For example, `document A / revision 1 / image 1` and `document B / revision 1 / image 1`
are distinct logical attachment references even when their bytes are equal. These
labels illustrate scope, not an ID format or wire schema. This accepted simplification
supersedes the [earlier unconfirmed shared-attachment proposal](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991924147).

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

## Source-facing handoff review — illustrative cases

These reviewed cases assemble the confirmed Q1–Q14 handoff. They are not
wire schemas, measured tests, a real pilot inventory or claims of runtime format
qualification. Source `S`, Asset/revision labels and artifact versions below are
illustrative. Actual identities/delegation and supported formats/profiles must be
established by their adoption/processing owners.

For every case, the controlled Source has an accountable Source Owner and an
authorized submitting program. The package needs an attributable supported policy
or authorization-target binding covering its required contents. Before processing
admission, validate fixed artifact versions, completeness, integrity information
and custody for the agreed queue/suspension/retry period. Q10 retention and current
governance continue afterward. Captured bytes do not prove semantic understanding,
Canonical Acceptance or publication.

| Example | Source identity and fixed package | Source-facing behavior to review |
|---|---|---|
| Paper PDF with embedded figures | `S / paper-A / pdf-r1`; `paper.pdf@F1` is the self-contained captured file | The embedded figures are already part of F1's fixed bytes. Capture does not need separate uploads of later extracted crops. Retry reads F1; renaming the catalog entry does not change the Asset. A genuine source update is another captured observation, not an overwrite of F1. Parsing, figure interpretation and canonical locators remain later boundaries. |
| SOP Markdown with a required image | `S / sop-A / md-r1`; `procedure.md@M1` plus its package-scoped `assets/flow.png@I1` reference | Missing required I1 prevents normal admission; ordinary hyperlinks do not trigger recursive capture. A second SOP using equal image bytes has its own logical attachment reference under Q14. Preserve each reference's source relationship and authorization basis; no global image catalog is required. The earlier Markdown walkthrough covers processing/withdrawal races. |
| Required-image-only update | Same Asset `sop-A`; main file remains `procedure.md@M1`, required image changes from I1 to I2 | M1/I1 and M1/I2 are distinguishable captured observations. The unchanged main-file native version alone cannot identify both packages as one Source Revision. Preserve the old observation; a new observation does not require a global image identity, another copy of eligible bytes, or unconditional full reprocessing. |
| Self-contained PPTX with an embedded diagram | `S / deck-A / pptx-r1`; `training.pptx@T1` contains the embedded diagram | Capture fixes T1 as one package artifact; it does not claim slide interpretation has succeeded. If a future case has a required external dependency, Q6/Q9 require its fixed package binding before normal admission. A revised deck gets a new source observation; method-only processing keeps T1. This example does not qualify the current PDF worker for PPTX. |

### Minimum information at the source boundary

This is a semantic checklist, not a required JSON field set or a requirement to
copy all policy data into each request. Valid governed references may carry the
applicable information.

| Information | What downstream owners may rely on |
|---|---|
| Identity and responsibility | Attributable Source, logical Asset and fixed Source Revision; a submitter with the relevant delegated authority. Filename, URL and hash alone do not establish logical identity or update order. |
| Complete captured inputs | Fixed main artifact and declared necessary dependencies, package-scoped attachment relationships, original source references, integrity information and accountable retrievable custody. |
| Policy authority and validity | Trusted policy authority/source and supported reader-policy or target binding; capture-time permission is not a permanent grant. Unsupported required policy is rejected. |
| Change intent and applicability | Explicit operation, affected scope and trustworthy ordering evidence or expected prior state; conflicts are visible and late results cannot restore withdrawn access. |
| Acknowledgement and responsibility | Durable receipt, governance application and evidence of the declared enforcement boundary have distinct meanings. Physical purge is separate. |
| Honest limitations | Known unsupported/missing inputs or unverifiable policy are explicit. Capture readiness, processing completion, Canonical Acceptance and each projection's publication remain distinct. |

### Lifecycle walkthrough

| Trigger | Required source-facing meaning | Detailed owner |
|---|---|---|
| First complete submission | Validate source/submit authority, fixed package and trusted policy before durable processing admission. The processing `202` promises accepted durable intent, not Canonical Acceptance. | Admission; canonical acceptance separately |
| Unchanged redelivery or execution retry | Preserve captured identities and versions. Apply request/change deduplication within the agreed contract; do not rebind the same identity to different content. | Admission command/request mechanics; canonical identity representation |
| New captured source observation | Retain the Asset where logical identity is unchanged. Identify the new observation and establish applicability; late arrival alone cannot make it current. | Canonical lifecycle with admission preconditions |
| Method-only reprocessing | Select the same retained Source Revision under a new deliberate processing request and fixed method/profile. Current custody and governance must still permit the work. | Admission and processing-profile integration |
| Catalog-only metadata update | Apply the authorized catalog change without inherently rerunning parsing/OCR. | Canonical lifecycle and admission commands |
| Policy or authorization-binding change | Authoritative-service policy changes follow the validity contract without resubmitting content. Platform-managed binding changes need appropriate authority and Q11 applicability. | Governance; canonical/admission binding representation |
| Confirmed deletion or explicit withdrawal | Require attributable authority and scope; a fetch failure or missing batch item is insufficient. Apply urgent governance without waiting for ordinary rebuilds; a late result cannot restore access. Distinguish received/applied/enforced outcomes and separate purge. | Governance with admission status, projection enforcement and persistence |

## Independent spike disposition — 2026-10-05

Two independent read-only reviews examined the fixed design checkpoint
`ff13f4d199507a469ad2438a83acf0c16eb3ad95`, the overall logical baseline and relevant
downstream decision ownership. They found no architectural conflict, unowned
essential source prerequisite or hard dependency cycle requiring a new decision.
The user accepted the following bounded disposition and source-facing closure.

| Finding | Incorporated disposition |
|---|---|
| A main file's native version may not identify its required dependencies | Q4 now explicitly covers the complete captured observation. The image-only update case above preserves M1/I1 and M1/I2 as distinguishable Source Revisions. Exact identifiers remain canonical design. |
| Expected-state success can be misread as source newness | Q11 already prohibits this interpretation. Carry the validation case below to admission and canonical design; it adds no new source principle or manual-approval requirement. |

### Downstream validation case — old capture with a refreshed precondition

A captures S1. B captures a genuinely later S2 and advances platform state to P2.
A then reads P2 and submits S1 with expected state P2. The platform-state comparison
may pass, but it does not establish source newness or justify making S1 current.
Refreshing a precondition alone cannot resolve source applicability. Require the
existing authoritative applicability/confirmation rules; expose a conflict if that
basis is missing. A delegated source program may perform supported reconciliation.

[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31)
owns the request/precondition response and validation;
[Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32)
owns current-selection/applicability semantics. Their detailed designs must show
that merely rereading platform state and resubmitting cannot silently promote the
old observation. This is a required validation scenario, not an executed test,
selected concurrency mechanism or requirement to fetch live-latest at execution.

## Source-facing resolution

The user confirmed Q1–Q14, the assembled source-facing cases and owner handoff,
and accepted the independent spike disposition on 2026-10-05. This resolves
[Define captured-source identity and authorization handoff](https://github.com/davidlinnnn/data-ingestion/issues/53)
at its source-facing decision boundary. No new source-facing question, service or
decision ticket is required by this review.

The separately confirmed unified lifecycle/status-query requirement remains with
admission/status, projection and governance owners; implementation phasing is open.
Detailed API/schema/TTL/storage choices below remain with existing downstream
owners. Resolution does not claim an implementation-ready specification or runtime
qualification. The wider Knowledge Platform map remains open.

## Integration and ownership

The [wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52) makes
confirmed target contracts authoritative. Workflow/API differences become versioned
implementation migration or integration work, with validation at the map's existing
follow-through checkpoints. Measured resource configurations inform the operating
envelope within their qualified scope.

| Detailed decision owner | Follow-through responsibility |
|---|---|
| [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31) | Public transport/status, upload finalization and command persistence/atomicity, deduplication/preconditions/conflict exposure; unified lifecycle query exposure/correlation and implementation phasing. |
| [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32) | Concrete identity/package/locator representation, canonical mapping/acceptance, version and lifecycle semantics. |
| [Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55) | Governed reads, projection handoff/status contributions, independent publication and reconciliation. |
| [Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56) | Concrete authorization applicability/validity, missed-change observation, lapse/recovery, cross-boundary enforcement and completion evidence. |
| [Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57) | Custody adoption/release, dependency protection, retention/purge and persistence mechanisms. No global shared-image domain is required by Q14. |
| [Set the first-adoption workload and operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54) | Pilot inventory/adoption requirements and numeric workload, capacity, retention, freshness and recovery targets with the relevant owners. |
| [Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72) | Qualified format/profile selection and versioned processing integration; source capture examples do not expand supported processing capabilities. |
