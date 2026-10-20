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

Cross-Resource synthesis is not supported in v1; a topic needing documents with
different audiences uses one Resource covering the intended audience. There is no
short-term requirement for it. If one arises, evaluate and design a migration
then, starting from read-time intersection checks over the Materialization Input
Snapshot or an explicit publication decision by an owner with authority over all
inputs; per-section source filtering of synthesized text is not considered
reliable, and per-audience variants reduce to Resource-scoped materialization.

Confirmed on 2026-10-20 during the
[admission design grilling](https://github.com/davidlinnnn/data-ingestion/issues/31).
Whether the platform keeps a Corpus entity distinct from Resource is being decided
in [#55](https://github.com/davidlinnnn/data-ingestion/issues/55), with the
preliminary recommendation that a Resource serves as the Corpus in v1. Binding
change propagation and any future declassification authority belong to
[#56](https://github.com/davidlinnnn/data-ingestion/issues/56). This refines
[ADR-0006](0006-fixed-inputs-independent-projection-publication.md) without
changing independent projection publication.
