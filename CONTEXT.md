# Enterprise AI Data Foundation

Shared language for the current high-level architecture discussion. Definitions
describe domain meaning; earlier mechanism-specific vocabulary remains in the
[historical design notes](docs/design/README.md).

## Domains and participants

**Enterprise AI Data Foundation**:
The umbrella data architecture for reusable enterprise knowledge and future
experience from applying that knowledge.

**Knowledge Platform**:
The Foundation's current design focus, spanning source integration through
governed publication of knowledge projections.
_Avoid_: ingestion platform, Foundation Platform

**Knowledge ingestion**:
The capability that acquires source information and prepares its reusable
canonical representation within the Knowledge Platform.

**External Consumer**:
An application, agent runtime, or reading experience outside the Knowledge
Platform that obtains its published knowledge through a governed interface.

**Source Owner**:
The party accountable for source content and its publication in the source
system, including adoption of proposed corrections or improvements.

**Agent Owner**:
The party accountable for an agent's behavior and adoption of changes to its
skills, memory, prompts, tools, or other operating methods.

**Tenant**:
A logical boundary for one organization or data-source owner using the
Knowledge Platform, currently bound one-to-one to a deployment. It is not part
of resource authorization policy: no grant or relation crosses it. If tenants
later share a deployment, tenant isolation is enforced in addition to resource
authorization.
_Avoid_: Resource, Corpus, access grant

## Knowledge and its use

**Source**:
A configured and governed external acquisition boundary through which the
Knowledge Platform discovers Documents.
In practice, a Source is typically one Data Owner knowledge-management
application, which submits Documents and manages its Resources and their
relationships within its scope. An application needing different restrictions
or projections registers multiple Sources. A Source bounds admission, not
consumption: reading across Sources is limited only by Resource readers.
_Avoid_: Document, end user

**Document**:
A logical knowledge object discovered through a Source, such as an SOP or a
business record, whose content can change over time. Its identity is distinct
from its name, physical location, and current file bytes. A Source identifies
each Document by its own stable identifier; after deletion, that identifier
denotes a new Document. Records before 2026-10-21 call it Asset.
_Avoid_: Asset, file, Source, current file bytes, filename, storage location

**Source Metadata**:
Key-value information a Source attaches to a Document for its own use. The
platform stores it and returns it only to that Source; it does not interpret,
index or disclose it.
_Avoid_: catalog metadata, filterable attribute, access policy

**Corpus**:
A platform-managed logical collection of Documents that defines a reusable knowledge
scope for multiple projections, such as Wiki and Retrieval. A Document may belong
to multiple Corpora; membership alone does not grant access. Explicit authorization
may target a Corpus as a Resource, subject to current governance.
In v1, precomputed products are materialized within one Resource (ADR-0007);
whether Corpus remains a separate entity is open in #55.
_Avoid_: ingestion batch, Source, Published View, access grant

**Source Revision**:
A captured observation of a Document's main file and required dependencies at a
particular source version or observation point. Its identity alone does not establish
its order relative to other observations.
_Avoid_: current source state, processing request

**Batch**:
A group of Documents submitted together and tracked through upload, aggregate
progress and per-item outcomes. Each item retains its own source identity, governance
relationships and result. Grouping does not determine Corpus membership or grant
access.
_Avoid_: Corpus, Resource, parser execution group

**Capture Package**:
The finite set of captured source artifacts comprising a main file and its
explicitly declared dependencies required for interpretation. Attachment identity
is scoped to the package; equal bytes across packages do not merge that identity.
_Avoid_: ingestion batch, arbitrary collection of hyperlinks

**Canonicalization**:
The interpretation and normalization of source observations into a reusable
representation with attributable evidence and processing origin.

**Processing Profile**:
A named, versioned specification of the processing capabilities and completion
requirements for preparing a canonical result for a declared supported use.
It is platform-owned and format-specific; method changes, including Enrichment
Methods, enter Canonical Knowledge only through a newly adopted version.
_Avoid_: profile (alone), caller-defined feature switches, Canonical Acceptance

**Knowledge Profile**:
A Source-level setting naming the Projection Types whose products that Source's
Documents go into, and therefore the projections Context Readiness waits for. It
contains no method versions, readers or grouping.
_Avoid_: Processing Profile, Corpus, access grant

**Canonical Knowledge**:
The governed, versioned representation of source-derived content and structure
that preserves the distinction between source evidence and derived interpretation
before consumer-specific specialization.
_Avoid_: index, chunk store, universal knowledge graph

**Canonical Revision**:
A distinguishable version of canonical knowledge with traceable source inputs
and processing origin. Once accepted, its content, structure/relationships,
source/evidence mappings and producing-method attribution remain fixed; a changed
result requires a new candidate and acceptance.

**Canonical Acceptance**:
In the initial document scope, a traceable determination that a complete candidate
from one Document's Capture Package meets the applicable, versioned representation,
evidence, quality, and governance criteria for agreed reuse as Canonical Knowledge.
Explicitly permitted limitations may accompany acceptance, which remains subject
to current access and lifecycle controls.
_Avoid_: processing completion, projection publication, verification of source truth

**Enrichment**:
Reusable derived understanding associated with canonical knowledge, such as OCR
reconstruction or image interpretation, with attributable producers and evidence.

**Enrichment Method**:
A versioned component of a Processing Profile that produces one kind of Enrichment
for a declared scope from its actual inputs.
_Avoid_: enrichment plugin, per-Source enrichment option

**Picture Interpretation**:
Enrichment generated from a picture, such as a caption, description, figure type
or chart values, each attributable to its producing method.
_Avoid_: image caption (ambiguous with Source Caption)

**Source Caption**:
Caption text present in captured source content and associated with a picture.
It is source content, not Enrichment.
_Avoid_: generated caption

**Document Summary**:
Enrichment interpreting a whole Document into a short summary whose statements
each cite their supporting Source Evidence. It is distinct from a summary or
abstract present in the source itself.
_Avoid_: abstract

**Document Category**:
Enrichment assigning a Document to platform-defined categories of document type,
paper type and topic. It never serves as an access or governance input.
_Avoid_: classification (reserved for access-policy classification)

**Source Reference**:
An explicit reference present in captured source content, such as an attachment
path, hyperlink, figure reference or bibliographic citation. Its original target
expression and any established target association are distinct, so retaining a
reference does not imply that its target has been resolved. Repeated attachment
references retain distinct revision-scoped locations and context even when they
resolve to the same fixed artifact in a Capture Package.
_Avoid_: Source Evidence, inferred semantic relationship

**Source Evidence**:
The source observations and locations supporting a represented fact or derived
interpretation. Actual location precision and support are explicit, and their
sufficiency is judged against the agreed reuse requirements.

**Evidence Lineage**:
The traceable relationship from a published result through its knowledge inputs
and processing origin to supporting Source Evidence.

**Materialization**:
The transformation of declared canonical knowledge inputs into a projection
product using an attributable method.

**Materialization Input Snapshot**:
The fixed set of Documents and exact Canonical Revisions selected as inputs to a
particular Materialization. Its references remain subject to current governance
and lifecycle controls.
_Avoid_: live corpus membership, latest revisions, access grant

**Projection Type**:
A family of knowledge products offered through a published interface, such as
Retrieval, Graph, or Wiki.

**Projection Definition**:
The specification of a projection's meaning, inputs, and transformation method.
_Avoid_: Published View, live output

**Published View**:
A governed knowledge product offered to External Consumers with its own
publication lifecycle.

**Published View Version**:
A distinguishable publication of a Published View whose inputs and producing
method can be traced.

**Governed Published Interface**:
The boundary through which an authorized External Consumer observes a Published
View and its permitted evidence, version, and availability information.

**Projection Status Report**:
A pipeline owner's report, in the platform's common status format, of a
projection pipeline's attempt progress and outcome and of which revisions its
published products serve. The owner remains authoritative; the platform does not
interpret owner-defined stages, error reasons or method manifests.
_Avoid_: Published View Version, platform-defined pipeline stages

**Context Readiness**:
What agents can currently read of a Document through the projections its Knowledge
Profile requires: the latest Source Revision, an older one, none yet, or nothing
because of deletion or withdrawal. Who must act is reported separately. It neither gates
publication nor grants access.
_Avoid_: Canonical Acceptance, projection input readiness, publication approval, access grant

**Projection Definition Owner**:
The party accountable for a projection's meaning and adoption of changes to its
definition or method.

**Published View Owner**:
The party accountable for a knowledge product's publication, withdrawal, and
replacement.

## Governance

**tSSO**:
The company's user-authentication authority, whose tokens establish user identity
for resource authorization.
_Avoid_: resource authorization decision, GAM

**GAM**:
The company's central resource-authorization service, governing relationships
between resources and users identified through tSSO and providing request-time
authorization decisions.
_Avoid_: user-authentication provider, tSSO

**GAM-compatible Authorization**:
An alternative resource-authorization mechanism using tSSO user identity and
conforming to the agreed GAM authorization meanings and supported scope.
_Avoid_: separate user identity system, API-shape compatibility alone

**Resource Service**:
The platform capability through which authorized maintainers manage resources,
their relationships and authorization-target bindings within a declared scope,
when the platform's built-in authorization is used. With GAM, maintainers manage
these relationships directly in GAM.
Knowledge-domain ownership and applicable policy authority remain distinct.
_Avoid_: new content/lifecycle authority, grant from registration alone

**Resource**:
A declared authorization target or scope, defined by an authorized owner, to
which document bindings and access policies apply. A Corpus may itself serve
this role; binding or membership alone grants no user access.
_Avoid_: mandatory Workspace entity, source-authorization override

**Source Policy Authority**:
The party entitled to define or change source access policy, held by the Source
Owner or an explicitly authorized delegate. Its authority is distinct from
submission permission and platform operation.

**Source Authorization Binding**:
The attributable association between a Document and the authoritative policy or
authorization target governing its access. The binding is not itself an access grant.

**Source Authorization Ceiling**:
The maximum audience permitted by the applicable source authorization policy.
Enterprise restrictions may narrow that audience.

**Effective Access Policy**:
The access conditions resulting from source authorization and all applicable
enterprise restrictions, including purpose, classification, and security domain.

**Protected Observation**:
Anything an observer can learn through a governed interface, including content,
existence, relationships, citations, summaries, and retrieval representations.

**Fail-Closed Governance**:
The absence of disclosure when the platform cannot establish that the relevant
access is permitted.

**Source Deletion**:
A Source's attributable statement that a Document no longer exists at the
source. It stops disclosure of that Document; it is neither governance
withdrawal nor Custody Purge, and omission from a submission never implies it.
_Avoid_: withdrawal, Custody Purge, omission from a batch

**Custody Purge**:
Destruction that makes the affected retained information unrecoverable in
platform custody, including its dependent copies.
_Avoid_: unpublication, tombstone, ordinary withdrawal

## Experience and improvement

**Knowledge Loop**:
The cycle of knowing, applying, learning, and improving through reusable
knowledge, observed execution, and accountable adoption of changes.

**Agent Trace**:
The execution records emitted by an agent runtime and its tools, whose format
and completeness may depend on the producing system.
_Avoid_: Canonical Agent Trajectory, verified outcome

**Canonical Agent Trajectory**:
A reusable representation of observed agent execution connecting task context,
actions, tool interactions, knowledge use, results, and available outcome or
feedback evidence.
_Avoid_: raw log, agent memory, generated success narrative

**Canonical Experience**:
The future canonical domain for reusable observations of AI and agent execution;
Canonical Agent Trajectories are a proposed core representation within it.
_Avoid_: agent memory, training dataset, Canonical Knowledge

**Knowledge Consumption Reference**:
A non-authorizing reference to the published knowledge actually observed during
an execution, preserving the connection to its version and permitted evidence.
_Avoid_: access grant, latest knowledge, copied content

**Improvement Candidate**:
An evidence-backed proposal to change agent behavior, a projection method or
product, a canonical processing method, or source content.
_Avoid_: approved change, verified source fact

## Review

**Architecture Direction Review**:
A review of problem framing, scope, responsibilities, principles, trade-offs,
and the questions to investigate in subsequent design.
_Avoid_: logical-contract endorsement, delivery approval

**Review Record**:
The record binding a candidate version and review scope to reviewer outcomes,
rationale, objections, and follow-ups.
