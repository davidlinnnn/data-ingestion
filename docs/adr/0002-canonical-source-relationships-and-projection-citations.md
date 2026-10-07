# Preserve source relationships in Canonical and product citations in projections

Canonical preserves reusable document structure, source locations and explicit
Source References with their resolution results; projections connect their own
statements, chunks/hits and knowledge organization to the exact Canonical inputs
and Source Evidence they used. This lets Wiki and Retrieval share source-side
information while retaining responsibility for the products they generate.
Logical component links do not require a graph database or a universal knowledge
graph, and preserving an unresolved source reference does not establish its target.

Confirmed on 2026-10-06 in the [Q4 decision record](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6015964591).
The [canonical design checkpoint](../design/knowledge-platform-canonical-design.md#q4-canonical-relationships-and-projection-citations)
records the boundary, its evidence limits and subsequent source-location decisions.

The [Q14 clarification](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6038695041) on 2026-10-07
uses shared-Corpus organization, interlinking, differences and incremental updates
to validate this boundary. The [confirmed scope revision](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6038854471)
limits this ticket to conceptual Wiki/Retrieval walkthroughs, with executable checks
only for decision-critical Canonical unknowns lacking sufficient evidence. Consumer
implementations, including reduced Wiki/RAG prototypes, stay outside this ticket;
Projection owns their implementation and effectiveness validation. This avoids
mixing model/prompt/product choices into a Canonical contract decision.
