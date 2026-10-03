# Enterprise AI Data Foundation

A proposed architecture for reusable enterprise knowledge and future experience
from applying that knowledge. The **Knowledge Platform** is the current design
focus: understand governed Sources, preserve Canonical Knowledge, and publish
independently evolving views for consumers.

This repository contains a **user-confirmed Knowledge Platform logical baseline**,
a separate proposed Architecture Direction Review package, and an independently
qualified PDF processing core. Detailed platform contracts and implementation
remain in progress; PDF-core qualification is not whole-platform readiness.

## Start here

Start with the [Knowledge Platform logical design](docs/design/knowledge-platform-logical-design.md)
and [overall review](docs/design/knowledge-platform-overall-review.md) for the confirmed
2026-09-28 responsibilities and handoff. The [active wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52)
owns the remaining decisions and integration checkpoints. The following direction
package provides background and retains its separate proposed status.

1. [HLD.md](HLD.md) — problem framing, full Knowledge Loop, current scope,
   responsibilities, scenarios, and trade-offs.
2. [ARCHITECTURE-BASELINE.md](ARCHITECTURE-BASELINE.md) — proposed boundaries and
   principles, explicit open design questions, and direction-review criteria.
3. [Review brief](docs/reviews/architecture-direction-review.md) — the candidate
   package, walkthrough prompts, and pending reviewer outcomes.
4. [CONTEXT.md](CONTEXT.md) — the current conceptual glossary.

Use the [documentation guide](docs/README.md) to distinguish confirmed logical
decisions, proposed direction material, historical evidence, and implementation.

## Problem and direction

The existing shared ingestion pipeline has accumulated consumer-specific
preparation alongside source acquisition and understanding. The working diagnosis
is that consumers cannot reuse the intermediate knowledge and evolve their
methods independently enough. The HLD identifies the operational examples needed
to validate that diagnosis.

The proposed architecture separates reusable source understanding from projection
methods and publication. Retrieval, Graph, and Wiki illustrate different knowledge
products that can consume Canonical Knowledge while retaining their own meaning,
ownership, product-operation semantics, and lifecycle. Applications and agents
own application-level query orchestration, additional ranking, context assembly,
tool use, and their application behavior.

## Knowledge Loop

![Knowledge Loop: current Knowledge Platform and future experience improvement paths](docs/diagrams/knowledge-loop.png)

The [editable Mermaid diagram](docs/diagrams/knowledge-loop.md) shows current
design scope with solid lines and future experience paths with dashed lines.
It is a conceptual architecture, not an implementation status or service topology.

- **Know:** turn governed source observations into reusable Canonical Knowledge
  and Published Views.
- **Apply:** applications and agents use published knowledge and authorized tools.
- **Learn:** future processing organizes Agent Traces into reusable Canonical
  Agent Trajectories within Canonical Experience.
- **Improve:** evaluation informs changes to agents, projection methods or
  products, canonical processing methods, or source content. Each change returns
  through its owner's normal lifecycle.

For example, an agent can propose a better SOP based on execution evidence. The
Source Owner validates and publishes the revision in the source system; ordinary
Source Integration then brings it into the knowledge lifecycle.

## What this review agrees

Reviewers are asked to align on the problem, scope, responsibilities, principles,
trade-offs, and next investigations. Source fidelity, governance, lineage,
independent evolution, and accountable improvement remain central.

Exact canonical schemas, identity and lifecycle protocols, publication units,
replay guarantees, trajectory contracts, and technology choices are subsequent
design work. [Open questions](ARCHITECTURE-BASELINE.md#7-open-design-questions)
make those decisions visible without selecting their answers prematurely.

The next progression is direction alignment, focused design validation, reviewed
logical contracts, and then physical design and delivery planning. Dates,
budgets, and implementation sequence remain to be planned.

## Candidate and design history

The direction package is preserved in this design checkpoint. Its
[review brief](docs/reviews/architecture-direction-review.md) retains pending
reviewer outcomes; publishing this checkpoint does not establish a new formal
direction-review record or change the confirmed logical-design scope.

The [previous GitHub review record](https://github.com/davidlinnnn/data-ingestion/issues/29)
belongs to candidate
[`babda22`](https://github.com/davidlinnnn/data-ingestion/commit/babda22bfc0eeb06bed5a6af7d94717f648c5265)
and its former contract-completeness scope. It does not cover this revised
package. Earlier evidence keeps its original version and attribution.

The [design-note index](docs/design/README.md) preserves the earlier detailed
Baseline, rationale, rejected options, and taxonomy examples as non-normative
material for later design. The [scope review memo](docs/reviews/hld-stage-scope-review.md)
explains this change in review stage. Historical normative wording in those
materials does not create requirements for the current candidate.

The [architecture exploration map](https://github.com/davidlinnnn/data-ingestion/issues/1)
remains the index of earlier decisions and investigations. The repository uses
[GitHub Issues](docs/agents/issue-tracker.md) for issues and resulting specifications.
