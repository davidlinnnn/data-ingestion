# Enterprise AI Data Foundation
## Narrative High-Level Design
### Knowledge Platform as First Delivery Domain

**Document status:** Explanatory companion
**Audience:** strategy and delivery stakeholders

> **Companion document**
>
> [ARCHITECTURE-BASELINE.md](ARCHITECTURE-BASELINE.md) is the sole normative source for the coordinated documents. This HLD explains the strategy, scope, rationale, target value, and future direction behind that Baseline. If the documents conflict, the Architecture Baseline governs.

---

# 1. Purpose and reading guide

This HLD explains why the **Enterprise AI Data Foundation** exists, why the existing knowledge ingestion pipeline is reaching its architectural limits, how the **Knowledge Platform** establishes the knowledge-side foundation, and how that work supports a longer-term Knowledge Loop.

The narrative runs in four movements:

1. **Background** — what the enterprise has already built and why (section 2);
2. **Problem** — why that architecture is reaching its limits, and why LLM-Wiki and Graph capabilities force the issue now (section 3);
3. **Vision** — the long-term Knowledge Loop the Foundation serves (section 4);
4. **Current scope** — the problem being solved now, the architectural answer, and its target value (sections 5 through 7).

Read this document to understand:

- how the existing shared ingestion pipeline came to couple source understanding with consumer-specific preparation;
- why adding LLM-Wiki and Graph capabilities requires an architectural evolution rather than more pipeline stages;
- the role of Canonical Knowledge in separating knowledge creation from knowledge serving;
- the target journey from external Sources to governed use;
- the value expected for Retrieval, Graph, Wiki, agents, governance, and rebuildability;
- the future direction for Canonical Experience and improvement loops; and
- the handoff from architecture explanation to architecture review and later delivery planning.

This is an explanation, not an architecture reference or an implementation plan. It summarizes outcomes without redefining contracts. The [Architecture Baseline](ARCHITECTURE-BASELINE.md#part-i--document-authority-and-framing) contains the binding boundaries, lifecycle rules, policy semantics, validation rules, publication controls, and review criteria.

Target delivery in this HLD describes capability and value only. It does not set a roadmap, sequence, dates, staffing, budget, backlog, concrete APIs, vendors, deployment choices, costs, or numeric service levels. In particular, the mapping from today's pipeline to the target architecture in section 6.5 describes where responsibilities live, not a migration plan.

---

# 2. Background: how the enterprise got here

## 2.1 The enterprise knowledge landscape

Enterprise knowledge is spread across documents, structured records, business systems, SaaS platforms, APIs, images, diagrams, tables, audio, and other multimodal Sources. For AI systems to create durable value, that information must become systematically discoverable, understandable, reusable, governed, traceable, and improvable — rather than re-derived from scratch by every application.

Nearly every AI solution needs the same upstream work: source acquisition, change detection, parsing, structural reconstruction, policy interpretation, versioning, and provenance. The strategic question has never been whether to share that work. It is **where the shared work should stop, and what durable asset it should produce**.

## 2.2 What the team built: one shared ingestion pipeline

Over the past several years the organization answered the first half of that question well. Rather than letting every application integrate Sources on its own, the team built a shared knowledge ingestion pipeline that acquires source content, parses it, and extracts modalities such as text, tables, images, and layout.

Because downstream consumers need prepared knowledge rather than parsed source content, the same pipeline progressively took on consumer-specific preparation as well:

- modality-specific transformation and enrichment;
- retrieval-oriented chunking;
- embedding generation;
- summarization;
- other logic tailored to particular agents and applications.

Each addition was locally reasonable: the pipeline was the one place that already understood the source content, so it was the natural place to prepare that content for the next consumer.

## 2.3 What that achieved, and what it deferred

The shared pipeline avoided the most visible failure mode: many teams each building their own connectors and parsers, producing duplicated processing and incompatible interpretations of the same content. Source acquisition and parsing happen once, and consumers receive ready-to-use artifacts.

What the pipeline deferred is an architectural boundary between **understanding a source** and **preparing that understanding for one consumer**. Its durable outputs are consumer-specific artifacts: chunks, vectors, summaries, and indexes. The reusable source understanding produced along the way — content, structure, layout, modality context, provenance — exists only transiently inside a pipeline run.

That deferral has one structural consequence:

> **The only way for a new consumer to reuse the pipeline's source understanding is to add its own preparation logic to the pipeline itself.**

Every new downstream knowledge consumer therefore grows the ingestion flow. That is exactly what has happened, and it is where the current problem begins.

---

# 3. Problem: the ingestion pipeline is reaching its architectural limits

## 3.1 Observable symptoms

As consumers accumulated, the pipeline came to couple parsing, knowledge extraction, representation, indexing, and consumer-specific preparation into one flow. The symptoms are now visible in daily work:

- **Every new consumer adds logic to ingestion.** There is nowhere else for consumer preparation to go, so the ingestion layer absorbs it.
- **Consumer technique changes become ingestion changes.** A new chunking strategy, embedding model, or summarization approach must be scoped, scheduled, and reprocessed inside a flow shared with every other consumer.
- **All consumers share one change and failure domain.** A defect or change in one consumer's preparation stage can disrupt ingestion for consumers that have nothing to do with it.
- **Consumer-facing outputs have no independent lifecycle.** A pipeline stage has no owner, no independent version, and no serving state that can be published, rolled back, or retired on its own.
- **Operational questions get harder to answer.** Which consumer artifact came from which source revision under which version of which preparation logic — and what exactly must be reprocessed after a given change — requires reconstructing pipeline history rather than reading a contract.

The pipeline is increasingly difficult to maintain, evolve, and operate — not because any single stage is wrong, but because of everything the single flow is being asked to hold.

## 3.2 Root cause: five concerns fused into one flow

The pipeline currently couples five separable concerns:

```text
Acquisition
     ↓
Source understanding          (parsing, structural reconstruction,
     ↓                         modality extraction)
Knowledge representation      (what was understood — today only
     ↓                         transient, inside a run)
Consumer-specific preparation (chunking, embedding, summarization,
     ↓                         enrichment for one consumer)
Index and serving preparation
```

These concerns change for different reasons and at different rates. Acquisition changes when Sources change. Source understanding changes when formats and parsers improve. Consumer preparation changes when a consumer's technique changes. Serving preparation changes when serving needs change.

Because there is **no durable knowledge representation in the middle**, everything downstream of parsing is coupled to everything upstream of serving. The pipeline fuses two questions that have different owners, lifecycles, and guarantees:

> **Knowledge creation:** What information and structure does the Source provide?

> **Knowledge serving:** How should a particular consumer retrieve, relate, synthesize, or present that knowledge?

## 3.3 Two failure modes, one root cause

It is worth naming both ways this architecture problem manifests, because the enterprise has now seen each of them:

- **Many pipelines** — each consumer builds its own ingestion. The result is duplicated source processing, incompatible interpretations of the same content, fragmented governance and lineage, and derived products that cannot be rebuilt without returning to a Source. This is the failure mode the shared pipeline was built to avoid.
- **One monolithic pipeline** — all consumers share one ingestion flow. The result is the coupling described above: shared change and failure domains, consumer logic accreting in the ingestion layer, and no independent consumer lifecycles. This is the failure mode the enterprise is in now.

The failure modes are mirror images with a single root cause: **the absence of a durable canonical knowledge layer between source understanding and consumer specialization**. Without that layer, reuse can only happen by duplicating the understanding work or by coupling to the flow that performs it.

## 3.4 Why LLM-Wiki and Graph make the evolution necessary now

The planned LLM-Wiki and Graph / GraphRAG capabilities could, mechanically, be added as more pipeline stages — one stage for entity and relationship extraction, another for topic synthesis. That path is exactly what should be rejected, because these capabilities are not "more of the same preparation." They introduce properties a pipeline stage structurally cannot provide:

- **Independently owned semantics.** A graph's ontology and meaning belong to an accountable Ontology Steward; a wiki's synthesis and citation policy belong to an accountable Knowledge Publisher. A pipeline stage has no accountable owner and no decision path for what its output means.
- **Independent change cadences.** An ontology moving from one version to the next, or a synthesis strategy change, has nothing to do with a source revision arriving or an embedding model upgrade. A single flow forces these unrelated lifecycles into one reprocessing and release decision.
- **A many-to-one shape.** A wiki page and a graph neighborhood synthesize across many assets. The pipeline's per-document, per-run stage shape does not naturally express products that must be derived from an evolving corpus.
- **Rebuild without re-ingest.** When an ontology or synthesis strategy changes, its products must be re-derived from preserved source understanding. In the current pipeline, "re-derive" and "re-parse" are the same operation, so every consumer-side change threatens a full re-ingestion.
- **Governance at the right units.** Graph nodes and edges, and a synthesized wiki page, must be governed as their own observable units with complete evidence lineage. Per-artifact policy stamping inside a pipeline does not compose into those units.
- **Accountable publication and rollback.** What a live wiki or graph serves is a publication decision that must support rollback and retirement. A pipeline has no unit of publication to select or roll back.

Adding Wiki and Graph into the existing flow would therefore multiply the coupling in section 3.2 — and every consumer added after them would multiply it again. The conclusion:

> **This is a separation-of-concerns problem, not a capacity problem. Canonical knowledge creation and consumer-specific knowledge serving are different concerns with different owners, lifecycles, and guarantees — and the current pipeline fuses them.**

The rest of this document places that conclusion in the enterprise's long-term strategy (section 4), scopes what is being solved now (section 5), and explains the architectural answer and its value (sections 6 and 7).

---

# 4. The long-term vision: Know → Apply → Learn → Improve

The architectural evolution is not only a fix for pipeline bloat. It is the first step of a longer-term strategy in which knowledge is treated as a continuously reusable and improvable enterprise asset rather than a by-product of individual applications.

The long-term value of the Foundation is a **Knowledge Loop**:

```text
Know → Apply → Learn → Improve
```

**Know** means turning governed source information into durable Canonical Knowledge and useful Published Views.

**Apply** means people, applications, and AI systems using those Published Views in retrieval, reasoning, reading, and operational work.

**Learn** means observing what happened during AI and agent execution: which knowledge was used, what tools and actions were involved, what outcome followed, and what feedback was received.

**Improve** means using governed evidence from that experience to strengthen both AI systems and enterprise knowledge.

```text
┌──────────────────────────────────────────────────────────┐
│ Knowledge Platform                                       │
│ Canonical Knowledge → Materialization → Published Views  │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
                 Governed Published Interfaces
                             │
                             ▼
                    External Consumers
                             │
                             ▼
              Future Canonical Experience
                             │
                             ├── AI improvement
                             └── Knowledge improvement
```

The loop contains two complementary improvement paths, elaborated in section 8: an **AI improvement loop** asking how AI systems can perform better, and a **knowledge improvement loop** asking how enterprise knowledge itself can become better. The objective is broader than retrieval-augmented generation or any individual AI application: it is to let the organization systematically learn from the use of its own knowledge.

The loop rests on two foundational canonical assets:

- **Canonical Knowledge** — what the enterprise knows, independent of source format, parser, retrieval mechanism, or any one application;
- **Canonical Experience** (future) — what the enterprise can learn from how AI systems behaved and performed, independent of any one agent framework or evaluation system.

They are separate reusable assets whose lineage can be connected. The Baseline defines the [two canonical domains](ARCHITECTURE-BASELINE.md#7-two-canonical-domains) and limits the current Knowledge-side bridge to the [Knowledge Consumption Reference](ARCHITECTURE-BASELINE.md#8-knowledge-consumption-reference).

The vision matters for the current decision because it sets a requirement no pipeline stage can meet: knowledge must exist as a **durable, governed, consumable asset** — not as transient state inside a processing flow.

---

# 5. What we are solving now: the Knowledge Platform

The **Knowledge Platform** is the first bounded architecture domain of the Enterprise AI Data Foundation. It covers source integration through governed publication of knowledge projections. Knowledge ingestion is one capability inside that domain — deliberately no longer the domain itself.

This is the program's current architecture and delivery positioning. It is explicitly not a statement about implementation maturity, completion, production readiness, or the order in which capabilities will be delivered.

The current focus is the knowledge-side lifecycle:

```text
External Sources
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│ Knowledge Platform                                       │
│ Source Integration → Canonicalization                    │
│                    → Canonicalization Write Interface    │
│                    → Canonical Knowledge                 │
│                    → Materialization → Published Views   │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼
                 Governed Published Interfaces
                             │
                             ▼
                    External Consumers
```

This scope addresses the problem in section 3 directly: it introduces the durable canonical layer the current pipeline lacks and gives consumer-specific preparation an accountable home outside the ingestion flow. It is the knowledge-side foundation of the loop in section 4, not the whole loop. The detailed boundary and responsibilities are defined in the Baseline's [scope](ARCHITECTURE-BASELINE.md#3-scope-and-boundary) and [logical architecture](ARCHITECTURE-BASELINE.md#10-logical-architecture-and-responsibilities).

Future Canonical Experience remains outside the Knowledge Platform boundary. Keeping the domains separate allows the program to focus on governed knowledge capability while retaining a coherent long-term direction for versioning, lineage, policy, lifecycle, provenance, observability, and artifact management.

---

# 6. The architectural answer: separate knowledge creation from knowledge serving

The target architecture answers section 3 with one structural move: place versioned, governed **Canonical Knowledge** between source understanding and every form of consumption, and make each consumer-facing product an independently owned projection of it.

> **Understand governed source knowledge once, preserve it as Canonical Knowledge, and publish independently governed views for different forms of use.**

```text
External Sources
      │
      │  governed acquisition and source change
      ▼
┌──────────────────────────────────────────────────────────────┐
│ Knowledge Platform                                           │
│                                                              │
│ Source Integration                                           │
│        ↓                                                     │
│ Canonicalization              ─┐                             │
│        ↓                       │  knowledge creation:        │
│ Canonicalization Write         │  "what does the Source      │
│ Interface                      │   provide?"                 │
│        ↓                       │                             │
│ Canonical Knowledge           ─┘                             │
│        ↓                                                     │
│ Materialization               ─┐  knowledge serving:         │
│        ↓                       │  "how should a consumer     │
│ Published Views               ─┘   use it?"                  │
└───────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
             Governed Published Interfaces
                                │
                                ▼
                     External Consumers
```

The two halves change for different reasons. Knowledge creation changes when Sources, formats, and understanding improve. Knowledge serving changes when consumer techniques, ontologies, and synthesis strategies improve. Canonical Knowledge is the durable contract that lets each evolve without dragging the other along — the boundary the current pipeline never had.

## 6.1 External Sources

External Sources remain outside the Knowledge Platform. The platform crosses a configured and governed acquisition boundary to discover and capture Assets, Source Revisions, artifacts, and policy provenance. A Source is an input boundary, not a platform component.

Source and enterprise access attributes, including Security Classification, travel through versioned Governance Bindings. Mutable Asset Metadata is a separate descriptive lifecycle for facts such as title, domain taxonomy, and display properties. It neither determines access nor changes Canonical Knowledge; a Published View uses it only when its Projection Definition declares that dependency.

## 6.2 Knowledge creation: Source Integration through Canonical Knowledge

The Knowledge Platform interprets source content and structure into source-faithful, versioned Canonical Knowledge. It preserves reusable multimodal information, evidence, lineage, and governance context **before** any particular consumer strategy is applied.

This is the decisive difference from the existing pipeline: the understanding produced by parsing and modality extraction stops being transient state inside a run and becomes a durable, addressable, governed asset. Derived understanding can remain distinct from source-faithful facts, allowing both to evolve with attributable lineage. The Baseline defines the detailed [Canonical Knowledge logical contract](ARCHITECTURE-BASELINE.md#11-canonical-knowledge-logical-contract).

## 6.3 Knowledge serving: Materialization, Published Views, and governed interfaces

Materialization turns declared Canonical Knowledge inputs into independently owned and versioned Published Views. Retrieval, Graph, and Wiki provide the initial interface families; future types can be registered without changing the boundary — which is how the platform absorbs new consumers without growing an ingestion flow.

Each Published View is consumed through its Governed Published Interface. Views retain separate identities, ownership, lifecycle, policy, and serving semantics. A coordinated package can group several view versions for operational convenience, but it remains optional packaging rather than a global serving unit.

Projection semantics and publication remain separate decisions. An accountable Projection Definition Owner adopts each immutable definition version and its complete output-influencing dependency set; an accountable Published View Owner selects an eligible immutable Published View Version. A dependency producer or platform executor can prepare candidates but cannot silently change what a live view means or serves.

The detailed publication model lives in the Baseline's [materialization and publication contract](ARCHITECTURE-BASELINE.md#16-materialization-and-publication-contract).

## 6.4 External Consumers

External Consumers include applications, agent runtimes, enterprise search, and reading experiences. They use Governed Published Interfaces and own query formulation, retrieval strategy, ranking, graph traversal, presentation, context construction, reasoning, tool use, and generation.

Published knowledge remains untrusted input when used by a generator. Authorization and publication indicate that content is eligible to be observed; they do not turn source-derived text into safe instructions. Consumers retain responsibility for prompt-injection and content-trust controls.

## 6.5 Where today's pipeline responsibilities live in the target

Everything the existing pipeline does keeps a home in the target architecture — but split along the creation/serving boundary rather than fused in one flow:

| Existing pipeline responsibility | Target home |
|---|---|
| Source connectivity, acquisition, change detection | Source Integration |
| Parsing, structural reconstruction, modality extraction | Canonicalization, producing Canonical Knowledge |
| Reusable derived understanding (for example OCR recovery, reusable image or table understanding) | Enrichment attached to Canonical Knowledge with attributable producers |
| Retrieval chunking and embedding generation | Retrieval Projection Definitions |
| Entity, relationship, and graph extraction | Graph Projection Definitions, owned by an Ontology Steward |
| Summarization and topic synthesis | Wiki Projection Definitions, owned by a Knowledge Publisher |
| Consumer- and agent-specific preparation | The relevant Projection Definition, or the External Consumer itself |

Each row on the serving side becomes an independently owned, versioned, rebuildable, and rollbackable Projection Definition instead of a pipeline stage. This mapping states where responsibilities live; sequencing, cutover, and delivery planning are out of scope for this document and follow architecture endorsement.

---

# 7. Target capability and value outcomes

The Knowledge Platform creates shared capability while leaving consumer-specific behavior and semantic ownership in the right places. These are target outcomes, not delivery increments. Each outcome removes one of the specific limits named in section 3.

## 7.1 Retrieval

Retrieval Published Views make governed passages available for lexical, dense, vector-similarity, or hybrid retrieval while retaining source evidence and lineage. Consumer applications can choose query rewriting, blending, reranking, and context assembly without embedding those choices in Canonical Knowledge.

Against section 3: a chunking or embedding-model change becomes a new Projection Definition Version and a rematerialization of one view from Canonical Knowledge — not a change inside a shared ingestion flow that risks every other consumer. This supports enterprise search, retrieval-augmented applications, and agents from the same source-understanding foundation. See the Baseline's [Retrieval interface](ARCHITECTURE-BASELINE.md#171-retrieval).

## 7.2 Graph

Graph Published Views support independently owned graph meanings, typed nodes and edges, evidence-backed claims, and governance at observable graph units. Different Graph definitions can serve different domains without forcing one enterprise-wide semantic identity.

For each Graph definition, its Ontology Steward is also its Projection Definition Owner, while a different Published View Owner can independently decide publication, rollback, and retirement. Graph consumers can traverse and reason over a governed published product while its semantic claims remain attributable to the relevant Ontology Steward.

Against section 3: an ontology change is a definition-owner decision with its own version, rematerialization, and rollback path — decoupled from source re-ingestion and from every other consumer's lifecycle. This is precisely the property that could not be achieved by adding graph extraction as a pipeline stage. See the Baseline's [Graph interface](ARCHITECTURE-BASELINE.md#172-graph).

## 7.3 Wiki and reading experiences

Wiki Published Views support governed synthesis with citations and accountable publication. Reading-product presentation, navigation, and interaction remain External Consumer concerns.

The Knowledge Publisher is the accountable Projection Definition Owner and Published View Owner for a Wiki: synthesis meaning, release, rollback, and retirement therefore have one decision path, while the platform only executes and validates. This separates synthesis accountability from presentation, and it allows a reading experience to evolve without changing Canonical Knowledge.

Against section 3: synthesis across many assets becomes a governed, many-to-one projection with an accountable publication decision — a shape the per-document pipeline could not express. See the Baseline's [Wiki interface](ARCHITECTURE-BASELINE.md#173-wiki).

## 7.4 Agents and AI applications

Agents can use one or more Published Views without implementing source integration, parsing, or canonicalization. Stable view and lineage context helps an agent or application explain what governed knowledge informed its work.

Against section 3: a new agent or application consumes existing governed views — or registers a new Projection Definition — instead of adding preparation logic into the ingestion layer. The current Knowledge-side bridge for future execution lineage is the Knowledge Consumption Reference. It records the identity of what was actually observed without becoming a grant or introducing a new read path.

## 7.5 Governance and trust

Governance travels with knowledge from source acquisition through publication and observation. This creates a consistent place to preserve source-policy provenance, apply enterprise restrictions, explain access outcomes, and respond to permission change, deletion, retention, and erasure.

The intended value is not merely central policy storage. It is consistent enforcement across canonical reads, materialization, publication, and query while preventing protected content or even protected existence from leaking through alternate paths. Effective Access Policy is evaluated for each observable unit from Governance Binding evidence and its full evidence intersection; descriptive Asset Metadata is not a policy authority.

Against section 3: policy is evaluated at the governed units consumers actually observe — retrieval segments, graph nodes and edges, wiki bundles — instead of being stamped onto pipeline artifacts and re-derived per consumer. The Baseline defines the [governance, authorization, and erasure model](ARCHITECTURE-BASELINE.md#15-governance-authorization-and-erasure) in detail.

## 7.6 Rebuildability, change, and lineage

Canonical Knowledge and complete immutable dependency records make a Published View Version exactly reproducible without returning to a Source while its full Reconstruction Closure is lawfully retained. A purpose-bound Rebuild Verification can prove the historical bytes and composition without publishing them. Custody Purge deliberately ends rebuildability where required inputs or identifying composition must become unrecoverable.

Source change, canonical content change, metadata change, projection change, policy change, deletion, and withdrawal remain distinguishable. Source, Canonical, and Published View Head selections carry state-specific transition evidence, so replay, rollback, safety unpublication, and genuine deletion cannot be confused. Adopting an output-influencing projection dependency creates a new Projection Definition Version with a declared impact and rematerialization or attested-reuse path; publishing the dependency alone changes no live view.

Against section 3: "re-derive" and "re-parse" stop being the same operation, and the operational questions that today require reconstructing pipeline history — which artifact came from which source revision under which logic version, and what must be reprocessed — become readable from immutable contracts. Consumers can observe meaningful freshness and availability states, while operators and reviewers can trace a published result back through Canonical Knowledge to the originating Source Revision. The governing lifecycle is summarized by the Baseline's [cross-cutting invariants](ARCHITECTURE-BASELINE.md#9-binding-cross-cutting-invariant-families) and detailed in its [revision lifecycle](ARCHITECTURE-BASELINE.md#14-revision-selection-and-dependency-lifecycle).

---

# 8. Future Canonical Experience and the complete Knowledge Loop

Canonical Experience is future direction, not part of the current Knowledge Platform target. It represents a separate canonical domain for reusable observations of AI and agent execution.

Potential observations include task context, model interactions, knowledge use, tool calls, actions, outputs, outcomes, feedback, and evaluation. These observations can contain confidential source-derived content, user data, sensitive tool output, failures, and low-quality behavior. Capture alone does not make them suitable for training or evaluation; future architecture needs explicit policy, privacy, quality, and curation boundaries.

```text
AI and Agent Execution
          │
          ▼
Future Experience Capture
          │
          ▼
Canonical Experience
          │
          ▼
Policy, Privacy, and Quality Curation
          │
          ├── Evaluation and Analytics
          ├── Curated Training Data
          └── Knowledge Quality Signals
```

The future domain can use compatible capability categories with Canonical Knowledge while retaining separate semantics and data models. Detailed Canonical Experience contracts, materializations, retention rules, and delivery choices remain future architecture work.

## 8.1 AI improvement loop

The AI improvement path asks:

> **How can AI systems perform better?**

```text
┌──────────────────────┐
│ Knowledge Platform   │
│ Published Views      │
└──────────┬───────────┘
           │
           ▼
Governed Published Interfaces
       │
       ▼
AI / Agent Execution
       │
       ▼
Future Canonical Experience
       │
       ▼
Evaluation and curated learning
       │
       ▼
Improved models and agents
```

Experience can support evaluation, analytics, failure analysis, and governed training-data curation. It also makes it possible to ask which governed knowledge, model, prompt, and tools participated in an execution without collapsing knowledge and experience into one domain.

## 8.2 Knowledge improvement loop

The knowledge improvement path asks:

> **How can enterprise knowledge itself become better?**

```text
┌──────────────────────┐
│ Knowledge Platform   │
│ Published Views      │
└──────────┬───────────┘
           │
           ▼
Governed Published Interfaces
       │
       ▼
External Consumers
       │
       ▼
Future Canonical Experience
       │
       ▼
Knowledge Quality Signals
       │
       ▼
Accountable Knowledge Curation
       │
       ▼
Improved governed knowledge
```

Signals can include missing knowledge, stale results, conflicting sources, repeated corrections, weak retrieval coverage, or areas that repeatedly require excessive cross-source reasoning. These signals inform accountable curation; they do not rewrite Canonical Knowledge in place. Improvement returns through normal source or canonical lifecycle events with preserved lineage.

## 8.3 The Knowledge-side bridge

The **Knowledge Consumption Reference** is the existing normative Knowledge-side bridge between an observed Published View unit and possible future Canonical Experience. It can preserve which governed unit was actually observed and selected evidence references from that unit.

This future narrative adds no identity, resolver, read role, or serving promise. It does not extend access from Canonical Experience into Canonical Knowledge. Any future end-to-end lineage design builds from the Baseline's existing reference and governance boundaries.

---

# 9. Relationship to architecture review and delivery planning

The two companion documents serve different purposes:

- **ARCHITECTURE-BASELINE.md** is the sole normative source and the primary evidence for contract completeness.
- **HLD.md** explains background, problem, strategy, scope, rationale, target value, future direction, and cross-document consistency.

Within the Baseline, frozen invariants are distinguished from provisional mechanism contracts: binding design intent that implementation feedback — starting with the first Retrieval tracer bullet — validates before it is frozen. Endorsement freezes the invariants; provisional passages are reviewed for consistency with them, not endorsed as final. The tier definitions and index live in the Baseline's authority levels section.

Architecture review binds one immutable repository commit containing both companions. The Baseline defines the review constituencies, acceptance gates, and five required logical scenario walkthroughs. The Review Record stores the executed walkthrough evidence, blocking objections and follow-ups, and each reviewer's outcome: pass, pass-with-follow-up, or fail.

See the Baseline's [review model](ARCHITECTURE-BASELINE.md#19-review-constituencies-and-outcomes), [required walkthroughs](ARCHITECTURE-BASELINE.md#23-required-logical-scenario-walkthroughs), and [Review Record rules](ARCHITECTURE-BASELINE.md#24-review-record-endorsement-and-re-review).

Endorsement establishes a decision-complete architecture baseline. It does not authorize funding, production, or final security or compliance certification. Later logical design, physical design, and delivery planning follow separately and can make choices that remain within the endorsed boundaries. That is also where the evolution from the existing ingestion pipeline is planned: this HLD explains why the evolution is necessary and where responsibilities land, while sequencing and cutover belong to delivery planning.

When a Baseline contract changes an architecture promise summarized here, the same repository commit updates both companions. The existing re-review triggers continue to apply; a pure narrative or copy edit prompts re-review only when it changes a boundary, architecture promise, normative principle, or consumer-observable meaning.
