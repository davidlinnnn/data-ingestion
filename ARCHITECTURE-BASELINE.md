# Enterprise AI Data Foundation
## Architecture Baseline for Direction Review

**Status:** Proposed high-level direction; reviewer outcomes pending

**Related confirmed work:** the [Knowledge Platform logical design](docs/design/knowledge-platform-logical-design.md)
records the separately confirmed overall decisions from 2026-09-28. This direction
package retains its own review scope; its open questions do not reopen those
confirmed decisions. Detailed work follows the [active wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52).

**Scope:** Knowledge Platform, with future Canonical Experience context

## 1. Purpose and authority

This document states the proposed scope, responsibilities, conceptual boundaries,
and principles to align before detailed design. [HLD.md](HLD.md) explains the
problem, rationale, value, and representative scenarios. [CONTEXT.md](CONTEXT.md)
provides the glossary.

This Baseline is the reference for the current review scope. The direction and
principles in §§3–6 are proposed for agreement. The questions in §7 are explicitly
unresolved, and §8 defines what reviewers are being asked to judge. Direction
agreement does not make detailed logical contracts decision-complete.

Earlier contracts are preserved in [non-normative design notes](docs/design/README.md).
They contain historical normative and provisional wording, but do not constrain
this candidate unless a principle is stated here. Later adoption of a mechanism
requires a design decision supported by its use case and validation.

## 2. Problem and intended outcomes

The existing project diagnosis is that source understanding and consumer-specific
preparation are coupled in a shared ingestion flow. The proposed response is a
durable canonical knowledge boundary and independently evolving projections.
The [HLD evidence table](HLD.md#2-current-situation-and-evidence) records the
operational examples still needed to validate that diagnosis.

The intended outcomes are reusable source understanding, independently owned
knowledge products, enforceable governance, traceable results and change impact,
and a foundation for later learning from agent execution. These outcomes are
qualitative; numeric targets and delivery increments are subsequent work.

## 3. Scope and conceptual boundaries

| Area | Position in this review |
|---|---|
| Source Integration through governed knowledge publication | Current Knowledge Platform design focus |
| Agent Trace capture, Canonical Agent Trajectories, experience curation and evaluation | Future direction; review their relationship to knowledge, without approving their detailed design |
| Agent behavior, application query strategy, business tool execution | External Consumer responsibility |
| Source content and source-system publication | Source Owner responsibility |
| Technology selection, schemas, APIs, runtime topology, migration and delivery plans | Subsequent design and planning |

Canonical Knowledge and Canonical Experience are distinct domains with different
meanings and lifecycles. Compatible evidence and governance concepts may connect
them; a shared physical service or data model is not assumed.

External Consumers obtain the knowledge offered by this platform through
Governed Published Interfaces. Consumer applications are not given a general
canonical-data interface as part of this direction. Internal access needs remain
a governed platform design question.

An agent may separately interact with business systems through their authorized
operational interfaces. This includes performing a task or proposing an SOP
revision. These actions neither grant canonical write authority nor bypass the
Source Owner's adoption and publication process.

## 4. Responsibilities and conceptual relationships

| Responsibility | Accountable architectural home |
|---|---|
| Source discovery, capture, change and deletion evidence, policy provenance | Source Integration |
| Reusable interpretation of source content and structure; attribution of processing | Canonicalization and Enrichment |
| Durable source-derived knowledge, evidence, versions, and processing origin | Canonical Knowledge |
| Transformation into projection products from canonical inputs | Materialization under a Projection Definition |
| Projection meaning and adoption of method changes | Projection Definition Owner |
| Semantics of declared projection product operations, such as ranked retrieval | Projection and its Definition Owner |
| Publication, withdrawal, and replacement of knowledge products | Published View Owner, subject to platform governance controls |
| Policy enforcement, lineage, quality visibility, lifecycle coordination, and audit | Cross-cutting Knowledge Platform responsibilities |
| Application-level query/tool orchestration, additional ranking/traversal over published interfaces, context assembly, and agent behavior | External Consumers and their owners |

The conceptual chain is **Source → source observation → Canonical Knowledge →
projection product → governed consumption**. An Asset distinguishes a logical
source object from its observations. Source Revision, Canonical Revision, and
Published View Version distinguish changes at different stages without prescribing
identity encoding, execution cardinality, or transaction boundaries.

Materialization uses retained canonical inputs and declared producing-method
dependencies. It does not reconnect to or re-parse Sources. Source capture and
policy integration remain platform responsibilities; governance may still need
source-native policy evaluation.

Source content and derived interpretation remain distinguishable and attributable.
The exact representation of native content, OCR, reconstructed structure, and
other enrichment is deliberately open.

Retrieval, Graph, and Wiki are representative Projection Types. They provide
retrievable knowledge, evidence-backed relationships, and cited synthesis,
respectively. Their owners define product meaning; the platform preserves common
governance and lineage obligations. This review neither requires a universal
ontology nor fixes graph identity, Wiki publication granularity, or a closed type
registry. Semantic and publication accountability are explicit without requiring
a particular organizational co-location.

## 5. Architectural principles

These principles are the proposed commitments for direction review. The specific
protocols that realize them remain open where identified in §7.

1. **Separate source understanding from consumer specialization.** Reusable
   knowledge is preserved before projection-specific preparation. Source,
   processing, projection, and consumer changes can have distinct lifecycles.
2. **Preserve source fidelity and processing origin.** Represented knowledge
   retains relevant source evidence and structure. Derived interpretation is
   attributed and distinguishable from source assertions. Unsupported content,
   uncertainty, and material processing loss are visible rather than silently
   treated as success.
3. **Govern every disclosure.** Source authorization is the access ceiling;
   applicable enterprise restrictions may narrow it. Capture or operational
   custody confers no consumer access. Derived output cannot broaden the audience
   allowed by its supporting evidence. Protected content and existence remain
   protected; when access cannot be established, disclosure fails closed.
4. **Make governance changes effective across dependencies.** Revocation,
   confirmed deletion, and withdrawal affect dependent publication and serving.
   Late processing and rollback cannot restore access that has been closed.
   Ordinary freshness differs from authorization eligibility. Source-change
   detection and the required consistency boundary must be resolved before
   governed serving is implemented.
5. **Distinguish withdrawal from erasure.** Removing content from serving does
   not destroy retained copies. Applicable erasure and retention obligations
   cover dependent data and platform-held copies, including caches and backups.
   Legal holds and operational custody do not grant ordinary consumer access.
6. **Preserve lineage and accountable version changes.** Published results are
   traceable through knowledge inputs to source observations and the methods that
   produced them. Creation or evaluation does not imply publication. A new result
   does not silently change the meaning or provenance of an earlier publication.
   Version history does not override lawful erasure obligations.
7. **Support regeneration from retained inputs.** Projections can be regenerated
   without reconnecting to Sources when their required inputs and producing
   capabilities remain lawfully available. Traceable regeneration, retained-output
   recovery, and byte-exact replay are separate capability levels; this direction
   does not promise universal byte-exact replay.
8. **Adopt improvements through accountable lifecycles.** Observed experience
   can motivate changes, but capture, canonicalization, evaluation, and adoption
   are distinct responsibilities. Experience does not directly rewrite canonical
   history or confer publication authority. Published content remains untrusted
   input for agent instruction-following; consumer content-trust controls still
   apply.

These principles retain governance intent while leaving its implementation open.
External legal or enterprise obligations continue to apply independently of this
document; a future design must identify the obligations relevant to its Sources
and consumers rather than infer certification from this review.

## 6. Future experience and improvement boundary

A Knowledge Consumption Reference conceptually identifies the published knowledge
actually observed, including version context and permitted evidence. Storing a
reference does not authorize later access. Its precise address format, retention,
and resolution behavior remain open.

Future experience canonicalization organizes observed execution into reusable
Canonical Agent Trajectories. It preserves available task context, actions,
knowledge use, results, and outcome evidence while distinguishing observations
from inferred explanations. Capture and downstream reuse remain governed by
purpose, policy, privacy, and quality.

An Improvement Candidate returns to its target's responsible lifecycle:

| Target | Return boundary |
|---|---|
| Agent skills, memory, prompts, tools, or models | Agent Owner's evaluation and adoption |
| Projection method or published product | Projection definition and publication responsibilities |
| Canonical processing or enrichment method | Processing responsibility, producing new attributable results |
| SOP or other source content | Source Owner publication, followed by Source Integration |

The [SOP walkthrough](HLD.md#73-learn-from-executing-an-sop) illustrates these
boundaries. A source correction changes the source observation; a method
correction can reinterpret retained source inputs. Experience-derived material
can become source content through accountable publication, with evidence and
policy retained. It is not automatically authoritative because an agent produced it.

## 7. Open design questions

These questions are part of the candidate, not hidden exceptions. The suggested
participants and validation inputs guide the next design conversation; they do
not assign named people or create an implementation backlog.

| ID | Question | Suggested participants and validation input |
|---|---|---|
| Q1 | Does the canonical boundary resolve the reported coupling? | Platform and consumer owners: one method-change and one onboarding example, including current impact and intended improvement |
| Q2 | What canonical representation and version granularity preserve multimodal evidence and support useful reuse? | Source, processing, and consumer owners: native and scanned SOPs, tables, structured records, and partial processing failures; compare envelope, enrichment, identity, and atomicity choices |
| Q3 | Which projections need regeneration, historical-output recovery, or exact replay? | Projection and platform owners: retained-input availability, model/runtime control, nondeterminism, retention cost, and consumer requirements |
| Q4 | What is the required revocation effect, and how is it enforced? | Security, governance, source, and serving owners: policy-change detection, unsupported native semantics, cache/replica/stream behavior, lineage, and erasure obligations |
| Q5 | What publication units, ownership arrangements, and quality checks fit each product? | Projection and publication owners: Retrieval, Graph, and Wiki examples; compare dependency tracking, composition, rollback, loss visibility, and organizational responsibilities |
| Q6 | What can be preserved reliably from agent execution? | Agent and future experience designers: traces with tool failures and retries, outcome availability, knowledge references, evidence gaps, and purpose restrictions; no universal trajectory schema assumed |
| Q7 | Can improvement be attributed and routed to the right owner? | Source, processing, projection, and agent owners: the same SOP failure caused separately by source content, parsing, synthesis, and tool use |
| Q8 | Which contracts are required for initial adoption and interoperability? | Platform and consumer owners: serving needs, internal canonical access, graph semantics, extension needs, and coexistence with the existing pipeline |

Q1 informs direction alignment. The remaining questions inform focused design
work after alignment. Any answer that changes an agreed responsibility or
principle returns to direction review; mechanism choices that preserve the
agreed direction proceed through the relevant logical-design review.

## 8. Architecture Direction Review

The review asks whether the problem and proposed direction are coherent enough
to guide the next design work. It does not require all logical contracts to be
complete or require the future experience platform to be implemented.

| Review perspective | Criteria for this stage |
|---|---|
| Enterprise architecture | Problem and evidence gaps are explicit; scope and responsibilities are coherent; alternatives and trade-offs are visible; open questions have a useful next validation step |
| Security and data governance | Authorization, evidence, derived disclosure, revocation, retention, and erasure responsibilities are preserved; unsupported semantics and consistency questions are exposed; no source or canonical access is implied by observing experience |
| AI consumer architecture | Retrieval, Graph, Wiki, and agent scenarios have clear value and responsibility boundaries; business tool actions are distinguished from knowledge access; all four improvement paths have an accountable return point |

Walk the HLD scenarios for a consumer-method change, source update or revocation,
and the SOP improvement loop. Explain responsibilities, information flow, and
unresolved choices. Detailed Head events, manifests, epoch protocols, and
trajectory schemas are not prerequisites for these conceptual walkthroughs.

Each perspective records **aligned**, **aligned with follow-ups**, or **changes
needed**, with reviewer, date, rationale, objections, and follow-ups. Unresolved
problem or boundary disagreement requires changes. A documented mechanism
question may remain open when the principle and next investigation are clear.
Direction is agreed only when all three perspectives align and no blocking
objection remains. These are review perspectives, not a staffing plan.

The [draft Review Record](docs/reviews/architecture-direction-review.md) identifies
the package and pending outcomes. When a GitHub Review Record is established,
it binds one immutable commit containing the HLD and this Baseline. Previous
candidate records and walkthrough evidence retain their original version and
scope; they do not automatically apply to this package.

After alignment, resolve the highest-impact design questions with focused
examples or prototypes, review the resulting logical contracts, and plan physical
design and delivery. Direction agreement is not funding, production, or final
security/compliance approval.
