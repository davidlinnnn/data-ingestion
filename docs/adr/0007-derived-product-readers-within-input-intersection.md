# Limit derived product readers to the intersection of their input readers

A precomputed derived product, such as an LLM-wiki page or a knowledge-graph
node synthesized from several documents, must not be readable by anyone who
cannot read every one of its inputs. Otherwise a reader of document A could
observe part of document B through the synthesis, violating the Source
Authorization Ceiling, Protected Observation and Fail-Closed Governance.
Query-time generation that first restricts inputs to the requester's readable
documents, such as Retrieval with answer generation, satisfies this by
construction.

In v1, precomputed products are materialized within one Resource: a projection's
knowledge scope (corpus or bundle) corresponds one-to-one to a Resource, so all
inputs share the same readers and the product uses that Resource's readers. Reader
changes on the Resource therefore apply to the product directly. When an input is
rebound to another Resource or withdrawn, the products whose Materialization
Input Snapshot includes it are rebuilt or withdrawn.

This relies on every input in a Resource having exactly that Resource's readers:
no per-document reader exceptions (still open in #56) and no differing source
ceilings among Sources that submit into the same Resource. If either is
introduced, Resource-scoped materialization no longer guarantees the intersection
and must be re-evaluated. When a rebind narrows an input's audience, removing it
from the previous Resource's products follows the #56 revocation path; ordinary
rebuild or update targets are not a disclosure grace period. Admission status
counts only products in the document's current Resource.

Cross-Resource synthesis is not supported in v1; a topic needing documents with
different audiences uses one Resource covering the intended audience. There is no
short-term requirement for it. If one arises, evaluate and design a migration
then, starting from read-time intersection checks over the Materialization Input
Snapshot or an explicit publication decision by an owner with authority over all
inputs; per-section source filtering of synthesized text is not considered
reliable, and per-audience variants reduce to Resource-scoped materialization.

Confirmed on 2026-10-20 during the
[admission design grilling](https://github.com/davidlinnnn/data-ingestion/issues/31).
[#55](https://github.com/davidlinnnn/data-ingestion/issues/55) decided on
2026-10-26 that the Resource is the Corpus in v1, with no separate Corpus entity
or membership. Binding
change propagation and any future declassification authority belong to
[#56](https://github.com/davidlinnnn/data-ingestion/issues/56). This refines
[ADR-0006](0006-fixed-inputs-independent-projection-publication.md) without
changing independent projection publication.

Amended on 2026-10-26 by
[#55](https://github.com/davidlinnnn/data-ingestion/issues/55). A Source binds
Documents only to Resources it created, so the precondition of no differing source
ceilings among Sources that submit into the same Resource holds in v1. A Document
may instead be copied into another Source: the copy is a new Document of the
destination Source that references the original's accepted Canonical Revision, and
its readers are the destination Resource's readers intersected with the original's.
A Resource containing copies therefore no longer has every input carrying exactly
its readers, and Resource-scoped materialization alone no longer guarantees the
intersection. A precomputed product that includes a copy supplies it with a
per-page check at query time: a page is served only to users who can read all of
its sources, including each copy's original. See the
[#55 design record](../design/knowledge-platform-canonical-consumption.md).
