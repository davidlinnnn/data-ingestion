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

## Knowledge and its use

**Source**:
A configured and governed external acquisition boundary through which the
Knowledge Platform discovers Assets.
_Avoid_: Asset, individual document

**Asset**:
A logical knowledge object discovered through a Source, such as an SOP or a
business record, whose content can change over time. Its identity is distinct
from its name, physical location, and current file bytes.
_Avoid_: Source, current file bytes, filename, storage location

**Corpus**:
A platform-managed logical collection of Assets that defines a reusable knowledge
scope for multiple projections, such as Wiki and Retrieval. An Asset may belong
to multiple Corpora without membership granting additional access.
_Avoid_: ingestion batch, Source, Published View, access grant

**Source Revision**:
A captured observation of an Asset at a particular source version or observation
point.
_Avoid_: current source state, processing request

**Capture Package**:
The finite set of captured source artifacts comprising a main document and its
explicitly declared dependencies required for interpretation.
_Avoid_: ingestion batch, arbitrary collection of hyperlinks

**Canonicalization**:
The interpretation and normalization of source observations into a reusable
representation with attributable evidence and processing origin.

**Canonical Knowledge**:
The governed, versioned representation of source-derived content and structure
that preserves the distinction between source evidence and derived interpretation
before consumer-specific specialization.
_Avoid_: index, chunk store, universal knowledge graph

**Canonical Revision**:
A distinguishable version of canonical knowledge with traceable source inputs
and processing origin.

**Canonical Acceptance**:
A determination that a candidate canonical result meets the applicable
representation, evidence, quality, and governance criteria for reuse as Canonical
Knowledge. Acceptance remains subject to access and lifecycle controls.
_Avoid_: processing completion, projection publication, verification of source truth

**Enrichment**:
Reusable derived understanding associated with canonical knowledge, such as OCR
reconstruction or image interpretation, with attributable producers and evidence.

**Source Evidence**:
The source observations and locations supporting a represented fact or derived
interpretation.

**Evidence Lineage**:
The traceable relationship from a published result through its knowledge inputs
and processing origin to supporting Source Evidence.

**Materialization**:
The transformation of declared canonical knowledge inputs into a projection
product using an attributable method.

**Materialization Input Snapshot**:
The fixed set of Assets and exact Canonical Revisions selected as inputs to a
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

**Projection Definition Owner**:
The party accountable for a projection's meaning and adoption of changes to its
definition or method.

**Published View Owner**:
The party accountable for a knowledge product's publication, withdrawal, and
replacement.

## Governance

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
