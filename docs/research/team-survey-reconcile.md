# Reconcile the Team Survey with the Architecture Baseline

**Research ticket:** [#19 — Reconcile the team survey with the architecture baseline](https://github.com/davidlinnnn/data-ingestion/issues/19) (wayfinder:research)
**Date:** 2026-08-23
**Method:** Classify every architecture-shaping claim in the teammate survey against `CONTEXT.md` and the closed decisions on [Baseline the Enterprise AI Data Foundation target architecture](https://github.com/davidlinnnn/data-ingestion/issues/1). The survey is a secondary write-up; it is treated as a proposal to test, not as a primary source that can reopen a locked ticket by itself.

**Question under test:** Which claims confirm, challenge, gap-fill, or sit outside the locked Foundation baseline? Must any closed ticket be reopened? Must [Confirm architecture-level quality, security, and review invariants](https://github.com/davidlinnnn/data-ingestion/issues/14) or [Define structural fidelity accounting for projections](https://github.com/davidlinnnn/data-ingestion/issues/18) change?

**Source document:** [team-survey-reference-architecture.md](./team-survey-reference-architecture.md) on this branch. Title in the source: *Enterprise Knowledge Ingestion Platform: Reference Architecture, Canonical Knowledge Model, Governance, and Delivery Roadmap* (2026-08-22).

---

## 1. Answer

The survey **confirms the locked thesis** and does **not** move the Foundation / Knowledge Platform boundary. Closed tickets stay closed. No new architecture-shaping ticket is required before the review draft.

The source reads closer to the still-unrewritten `HLD.md` v0.3 prose than to the locked glossary. Apparent boundary moves collapse into four already-rejected forks plus one optional packaging question.

| Class | Disposition |
|---|---|
| Confirms | Use as rationale when rewriting the HLD. |
| Already-rejected forks | Record as explicit non-goals. Do not reopen. |
| Gaps | State as qualitative invariants on the HLD rewrite / [Confirm architecture-level quality, security, and review invariants](https://github.com/davidlinnnn/data-ingestion/issues/14). Do not reopen [Define governance normalization and enforcement invariants](https://github.com/davidlinnnn/data-ingestion/issues/11). |
| Out of scope | Leave on the map's Out of scope list. Delivery planning after Architecture Baseline Endorsement. |

Coordinated multi-view release is **optional packaging**, not a new consumer contract. [Define structural fidelity accounting for projections](https://github.com/davidlinnnn/data-ingestion/issues/18) keeps its current question; the survey is input, not a scope change. The survey author is not an accountable reviewer under [Set the architecture review acceptance criteria](https://github.com/davidlinnnn/data-ingestion/issues/2).

---

## 2. What the survey is

A vendor-neutral reference architecture for an enterprise knowledge platform. Its recommended design is a Canonical Knowledge Envelope (CKE): a stable contract for identity, metadata, provenance, policy, and versioning, with vector, graph, search, GraphRAG summaries, and wiki pages as derived projections.

Its success criterion matches the map destination:

> Can the organization reproduce, authorize, explain, update and delete every piece of knowledge delivered to an AI consumer, while retaining enough semantics to serve new consumer types without re-ingesting the enterprise?

It also contains physical design, vendor comparison, a twelve-month roadmap, FTE and ROM cost ranges, and a concrete OpenAPI. Those sit outside this baseline.

The survey's six contracts map onto locked layers without redrawing them:

| Survey contract | Locked baseline |
|---|---|
| Source | Source / Source Instance / Source Revision |
| Canonical Knowledge | Canonical Core + Enrichment Overlay + Canonical Element Address |
| Provenance | Canonicalization Attestation + connectable execution lineage |
| Governance | Governance Binding + Fail-Closed Governance + Policy Decision Service |
| Release | Published View Version + Aggregate Manifest + Materialization Input Manifest |
| Consumer Context | Published View interfaces for External Consumers; Governed Canonical Read is internal |

Canonical Experience is almost untouched, so the survey does not challenge [Define the Canonical Experience linkage contract](https://github.com/davidlinnnn/data-ingestion/issues/13).

---

## 3. Confirms

Use these as supporting rationale in the HLD rewrite. They do not change a locked decision.

| Survey claim | Locked home |
|---|---|
| Do not treat a vector database as the system of record. Embeddings are derived and model-volatile. | [Define the universal Canonical Knowledge contract](https://github.com/davidlinnnn/data-ingestion/issues/8); [Define standard materialization and consumer contracts](https://github.com/davidlinnnn/data-ingestion/issues/12) |
| One ingestion, many projections. Own the canonical contract, not a particular store. | [Reconcile the Foundation target and Knowledge Platform program boundary](https://github.com/davidlinnnn/data-ingestion/issues/3); [Validate central platform ownership across materialization](https://github.com/davidlinnnn/data-ingestion/issues/6) |
| Immutable raw snapshots. A parser upgrade must not overwrite prior evidence. | [Define identity, revision, overlay, and deletion semantics](https://github.com/davidlinnnn/data-ingestion/issues/9) |
| Deletes are explicit events, not silent disappearance. | `#9` Tombstone; [Define governance invalidation linearization and erasure lifecycle](https://github.com/davidlinnnn/data-ingestion/issues/17) (Tombstone is not erasure) |
| Immutable does not mean retain forever. Retention expiry and lawful deletion need unrecoverability (including crypto-shredding). | `#17` Legal Erasure Event / Retention Expiry Event then Custody Purge |
| Enforce again at query time. Store policy references, not flattened allow-lists. | [Define governance normalization and enforcement invariants](https://github.com/davidlinnnn/data-ingestion/issues/11) |
| Missing authorization metadata fails closed. | `#11` Fail-Closed Governance |
| Assertions need evidence, confidence, and time. A bare graph edge is not enough. | `#8` Enrichment Overlay; `#12` / [Define conflict rules for independently owned graph identities](https://github.com/davidlinnnn/data-ingestion/issues/15) (Graph units require evidence) |
| Deduplication must not delete source evidence. | `#9` Semantic Equivalence Attestation; identities are not merged |
| Preserve structure and locators (page, bounding box, row key, temporal range, structural path). | [Prototype the initial canonical kind and payload taxonomy](https://github.com/davidlinnnn/data-ingestion/issues/16) Source Evidence locator families; input to `#18` |
| Establish contracts before scale. Offer Vector / Retrieval first; Graph and Wiki later. | `#6` Wiki is not a default peer |
| Agents must not bypass the governed interface to hit an underlying index. | `#12` Published-View-only External Consumer access |
| W3C PROV for artifact lineage; OpenLineage for job/run lineage. | HLD §3.12: knowledge lineage and execution lineage are connectable. Standard selection is later design. |

---

## 4. Already-rejected forks

These look like boundary challenges. Each was already decided. Record them as non-goals in the HLD rewrite. Do not reopen the cited ticket.

### 4.1 One CKE bag versus the split envelope

The survey JSON puts content, structure, `entity_refs`, policy, quality, and `knowledge_release` on one knowledge unit.

The locked model keeps Canonical Core source-faithful; inferred understanding on a separately versioned Enrichment Overlay; policy on a Governance Binding; External Consumers on Published Views.

The survey's own layer table already splits raw evidence, knowledge units, semantics, governance, and projections. The conflict is the example schema, not the thesis. **Keep [Define the universal Canonical Knowledge contract](https://github.com/davidlinnnn/data-ingestion/issues/8).**

### 4.2 Content-hash identity versus execution identity

The survey wants `ku:sha256:...` and the invariant “same source version reprocessed twice yields the same canonical identity.”

The locked model creates a new Canonical Revision for each successful Canonicalization Execution even when content is equivalent. Reuse is only through a Semantic Equivalence Attestation. That preserves who wrote the revision and blocks silent identity merge.

Replay and reuse remain available through attestation. **Keep `#8` and `#9`.**

### 4.3 Enterprise entity spine

The survey treats `canonical-person:42`, an enterprise entity model, and `/v1/entities/{entity_id}` as canonical. That recreates the enterprise ontology office rejected by [Validate central platform ownership across materialization](https://github.com/davidlinnnn/data-ingestion/issues/6) and [Define conflict rules for independently owned graph identities](https://github.com/davidlinnnn/data-ingestion/issues/15).

The survey's own warning — keep source identities, treat resolution as inference, do not auto-merge — supports the locked rule. Graph Node identity stays definition-local. The only cross-view join an External Consumer is entitled to is Evidence Overlap.

**Keep `#15`. Do not open an entity-resolution ticket.**

### 4.4 Historical Published View as an External Consumer API

The survey makes `release_id` and `as_of` first-class on the consumer API.

[Define the Canonical Experience linkage contract](https://github.com/davidlinnnn/data-ingestion/issues/13) already ruled out historical Published View read for External Consumers. A Head is never a referent. Reproduce and audit use immutable Versions, internal Governed Canonical Read, and Authorization Decision Evidence.

**Keep `#13`.**

### 4.5 One Context Gateway OpenAPI over canonical units

“Applications must not query vector or graph stores directly” agrees with `#12`. A gateway as a physical serving pattern is later design.

The proposed `/v1/knowledge/search?mode=vector|graph|auto` that returns `knowledge_unit_id` collapses Published View access and Governed Canonical Read, and it violates the baseline non-goal of concrete API endpoints. Retrieval Mode remains a property of a Projection Definition, not a platform-wide search enum.

**Keep `#12`. Do not adopt the OpenAPI as an HLD contract.**

### 4.6 Wiki generated from a shared entity/assertion model

The survey generates wiki pages from enterprise entities and per-claim citations.

A Wiki Published Bundle is one Governed Observation Unit under a Knowledge Publisher, because a synthesis cannot safely omit an unauthorized claim. That model also depends on the rejected shared entity spine.

**Keep `#12`.**

---

## 5. Gaps that do not reopen tickets

State these in the HLD rewrite and in the `#14` walkthroughs. They fit existing contracts.

| Gap | How it fits |
|---|---|
| Purpose, consent, residency, and agent delegation in the authorization formula | Already inside Effective Access Policy as enterprise restrictions that may narrow, never widen, the Source Authorization Ceiling. |
| Embeddings are not automatically non-sensitive | An embedding is a Protected Observation / classified derived artifact. Hybrid placement must treat it as governed, not as safe-to-export metadata. |
| Retrieved content is untrusted input to generators (prompt injection) | Qualitative serving invariant for `#14`. It is not a new data-model primitive. |
| Coordinated multi-view Knowledge Release Manifest | Optional control-plane packaging of several Published View Versions. It must not become the External Consumer serving unit. Per-view independence from `#12` and `#2` scenario 4 stays: changing an embedding rematerializes only the affected Projection Definition. |

No new grilling ticket is required for coordinated release unless a later session chooses to make that packaging a baseline contract. This research does not so choose.

---

## 6. Out of scope for this baseline

These remain on the map's Out of scope list. They are useful later, not architecture-shaping now.

- Storage, index, catalog, and policy-engine product selection (Iceberg, lakeFS, Qdrant, Milvus, OPA, OpenFGA, Unity Catalog, and the rest of the comparison tables)
- Cloud / on-prem / hybrid deployment topologies
- Connector, CDC, and parser vendor choices
- Concrete OpenAPI paths and MCP tool names
- Twelve-month roadmap, team shape, and ROM cost ($1.2M–$15M+, 10–14 FTE)
- Numeric SLOs, RAGAS/BEIR evaluation programs, and capacity targets
- BI / SQL over canonical tables as an offered Projection Type (open registration can add one later; it is not a baseline offered type)
- Canonical Experience ingestion, materialization, and the Knowledge Improvement write path

---

## 7. Ticket outcomes

| Ticket | Outcome |
|---|---|
| Closed `#2`–`#13`, `#15`–`#17` | No reopen. No resolution edit. |
| [Set the architecture review acceptance criteria](https://github.com/davidlinnnn/data-ingestion/issues/2) | No fourth reviewer gate. The survey is evidence, not endorsement. |
| [Confirm architecture-level quality, security, and review invariants](https://github.com/davidlinnnn/data-ingestion/issues/14) | Question and bar unchanged. This ticket blocked `#14` until close. After close, `#14` applies the same bar to the rewritten HLD, using this reconcile as extra evidence. |
| [Define structural fidelity accounting for projections](https://github.com/davidlinnnn/data-ingestion/issues/18) | Question unchanged. Locator, hierarchy, parent, path, and ordinal claims are inputs to the existing fidelity axis. |
| [Baseline the Enterprise AI Data Foundation target architecture](https://github.com/davidlinnnn/data-ingestion/issues/1) | Destination and Out of scope unchanged. This ticket is a child; its gist belongs in Decisions so far. |

### HLD rewrite notes for later tickets

When `#14` (and any authorized HLD rewrite task) updates `HLD.md`, carry these as explicit non-goals or rationales:

- Non-goals: one-bag CKE as the durable contract; content-hash Canonical Element identity; Foundation entity-resolution spine; External Consumer time-travel / historical Published View API; global knowledge release as the serving unit; concrete Context Gateway OpenAPI.
- Rationales: query-time enforcement; rebuildable projections; tombstone versus Custody Purge; source-faithful Core versus inferred Overlay; Published-View-only External Consumer access.
- Qualitative additions: purpose / consent / residency as enterprise restrictions; embeddings as Protected Observations; retrieved text as untrusted generator input.

---

## 8. Sources used

- Teammate survey: [team-survey-reference-architecture.md](./team-survey-reference-architecture.md)
- Locked glossary: `CONTEXT.md` (working tree at time of classification; not part of this branch)
- Map and closed resolutions: [issue #1](https://github.com/davidlinnnn/data-ingestion/issues/1) and the tickets named above
