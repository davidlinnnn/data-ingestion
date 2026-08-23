# Enterprise AI Data Foundation — Knowledge Loop

This Mermaid diagram is an editable discussion aid derived from
[`HLD.md`](../../HLD.md) and the screenshot in
[`knowledge-loop.png`](knowledge-loop.png).

[`ARCHITECTURE-BASELINE.md`](../../ARCHITECTURE-BASELINE.md) remains the sole
normative source. A diagram change is a proposal until the coordinated
documents adopt it.

```mermaid
flowchart TB
    SOURCES["External Sources<br/>Documents · SaaS · APIs<br/>Tables · Images · Audio · Video"]

    subgraph KP["KNOW · CURRENT TARGET — KNOWLEDGE PLATFORM"]
        direction LR

        SI["Source Integration<br/>Capture content<br/>Policy provenance<br/>Artifacts + change"]
        CZ["Canonicalization<br/>Parse + reconstruct<br/>Preserve structure<br/>Platform attestation"]
        CK["Canonical Knowledge<br/>Source-faithful Core<br/>Enrichment Overlays<br/>Versions + lineage<br/>Governance Bindings"]
        MAT["Materialization<br/>Canonical-only input<br/>Immutable manifests<br/>Coverage + fencing"]
        PV["Published Views<br/>Retrieval<br/>Graph<br/>Wiki<br/>Future registered types"]
        GPI["Governed Published Interfaces<br/>Policy · version · lineage<br/>Freshness · eligibility"]

        SI --> CZ --> CK --> MAT --> PV --> GPI
    end

    CONSUMERS["APPLY · CONSUMER VALUE<br/>Multimodal RAG<br/>Graph RAG<br/>LLM Wiki<br/>Agents + Copilots<br/>Enterprise Search<br/>AI / Agent Execution"]

    SOURCES --> SI
    GPI --> CONSUMERS

    subgraph FUTURE["LEARN + IMPROVE · FUTURE DIRECTION — CANONICAL EXPERIENCE"]
        direction LR

        EC["Experience Capture<br/>Knowledge used<br/>Models · prompts · tools<br/>Outcomes + feedback"]
        CE["Canonical Experience<br/>Separate canonical domain<br/>Compatible governance<br/>Reusable observations"]
        PQ["Policy + Privacy + Quality<br/>Consent and residency<br/>Quality curation<br/>Training eligibility"]

        EVAL["Evaluation + Learning<br/>Analytics + evaluation<br/>Curated training data<br/>Failure analysis"]
        KS["Knowledge Quality Signals<br/>Missing · stale · conflict<br/>Retrieval gaps<br/>Repeated corrections"]

        AIS["Improved AI Systems<br/>Models + prompts<br/>Agent policies<br/>Tool strategies"]
        KC["Accountable Knowledge Curation<br/>Normal Source / Canonical<br/>lifecycle only"]

        EC --> CE --> PQ
        PQ --> EVAL --> AIS
        PQ --> KS --> KC
    end

    CONSUMERS -.->|"Future capture + Knowledge Consumption Reference"| EC
    AIS -.->|"AI improvement"| CONSUMERS
    KC -.->|"Knowledge improvement through normal Source / Canonical lifecycle"| CZ

    class CK,PV key
    class EC,CE,PQ,EVAL,KS,AIS,KC future

    classDef key stroke-width:2px,font-weight:bold
    classDef future stroke-dasharray:5 4
    style KP stroke-width:2px
    style FUTURE stroke-dasharray:7 5
```

## Reading guide

- **Know:** source understanding is performed once and preserved as governed,
  source-faithful Canonical Knowledge before consumer specialization.
- **Apply:** Multimodal RAG, Graph RAG, LLM Wiki, agents, copilots, and search are
  External Consumers. Their value is delivered through Governed Published
  Interfaces.
- **Learn:** future Experience Capture may preserve what knowledge, models,
  prompts, and tools participated in an execution, together with outcomes and
  feedback.
- **Improve:** experience may improve AI systems or produce accountable
  knowledge-quality signals. Knowledge changes return through normal Source or
  Canonical lifecycle events; they do not mutate Canonical Knowledge directly.

## Editing guardrails

Keep these boundaries intact unless the Architecture Baseline is deliberately
being reconsidered:

1. External Sources and External Consumers remain outside the Knowledge
   Platform.
2. External Consumers use Published View interfaces only; Governed Canonical
   Read is not a consumer interface.
3. Materialization consumes Canonical Knowledge and does not re-access or
   re-parse a Source.
4. Canonical Experience is a separate future canonical domain, not part of the
   current Knowledge Platform target.
5. A Knowledge Consumption Reference records what governed unit was observed;
   it is not a grant or a new read path.
6. AI and knowledge improvement paths retain policy, lineage, versioning, and
   accountable ownership.
