# Enterprise AI Data Foundation
## Architecture Baseline
### Knowledge Platform as First Delivery Domain

**Document status:** Candidate architecture baseline
**Audience:** enterprise architecture, security and data governance, and AI consumer architecture reviewers

> **Companion document**
>
> [HLD.md](HLD.md) provides explanatory framing for strategy, scope, rationale, and future direction. This Architecture Baseline is the sole normative source for the coordinated documents. If the documents conflict, this Baseline governs.

---

# Part I — Document Authority and Framing

> **Authority: document framing.** This part defines how to interpret and scope the baseline. Any binding requirement in this part explicitly names the normative authority level to which it belongs.

## 1. Purpose

This document is the decision-complete target architecture reference for the **Enterprise AI Data Foundation** and its first bounded delivery domain, the **Knowledge Platform**. It explains the logical contracts, responsibilities, trust boundaries, and consumer-observable behavior preserved by later logical and physical designs.

It is not an implementation plan. It does not choose physical schemas, APIs, products, vendors, storage engines, deployment topologies, delivery increments, or numeric service levels.

The architecture addresses a recurring enterprise problem: heterogeneous sources are repeatedly acquired, parsed, governed, and transformed by isolated AI solutions. That duplication creates inconsistent source interpretation, fragmented policy enforcement, incomplete lineage, silent information loss, and projections that cannot be rebuilt without returning to the source.

The target pattern is:

> **Canonicalize reusable source knowledge once; publish many independently governed projections.**

## 2. Authority levels

This Baseline has three explicit authority levels:

1. **Normative Foundation baseline.** Binding architecture-shaping invariants shared by Foundation domains. These requirements use **MUST** and **MUST NOT**.
2. **Normative Knowledge Platform target.** Binding logical architecture for the first delivery domain. It baselines the full target, not an MVP or delivery sequence.
3. **Provisional mechanism contract.** Binding design intent for a mechanism that honors a normative invariant. An implementation MUST NOT silently contradict a provisional contract, but the contract is expected to be revised from implementation feedback. Revising a provisional passage within its invariants does not by itself trigger re-review; promoting one to normative authority does (§24).

Provisional passages are marked in place. Everything in Parts II and III not so marked carries the enclosing Part's normative authority. The provisional passages and their validation events are:

| Provisional passage | Validation event |
|---|---|
| §8 per-type referent forms, resolution behavior, post-purge reservation | Canonical Experience domain design |
| §14.2 Head Selection Event verified-field enumeration | First Retrieval tracer bullet |
| §14.3 transition-evidence field composition | First Retrieval tracer bullet |
| §14.4 correspondence case taxonomy and predecessor mechanics | First canonicalizer producing Revision Deltas |
| §14.5 re-anchoring and resolution-advance conditions | First Enrichment Overlay producer |
| §14.6 Asset Metadata selection machinery (entire section) | First metadata-dependent Projection Definition |
| §15.3 batch, stream, cache, and replica mechanics | First governed serving implementation |
| §16.3 impact-selection computation and attested-reuse mechanics | First Projection Definition version transition |
| §16.5 inferred-unit shard placement | First Graph Projection Definition |
| §16.6 Rebuild Verification workflow | First rebuild capability design |
| §16.7 Carry-Forward composition mechanics | First Publication Policy implementation |
| §16.8 Axis 2 structural-reduction machinery | First Retrieval and Graph materializers |
| §17.2 Identity Minting Rule mechanics | First Graph Projection Definition |

The **first Retrieval tracer bullet** is one end-to-end path from Source Integration through Canonicalization, Canonical Knowledge, one standard Retrieval Projection Definition, publication, and governed query.

Registry seed content — the initial Foundation Element Kinds, payload contracts, and Source Evidence locator families — is governed registry data under §12.1, maintained in [docs/registries/foundation-seed-registrations.md](docs/registries/foundation-seed-registrations.md). It is not frozen baseline text, and a seed change that satisfies every §12 gate does not trigger re-review.

Broader future direction for Canonical Experience and the Knowledge Loop is in the companion [Narrative HLD](HLD.md). That explanatory direction creates no Foundation or Knowledge Platform requirements.

The normative parts are an architecture baseline only. Endorsement does not authorize funding, delivery, production, or final security or compliance certification.

## 3. Scope and boundary

The Knowledge Platform boundary is consistent in every view:

```text
External Sources
      │
      ▼
┌──────────────────────────────────────────────────────────────────┐
│ Knowledge Platform                                               │
│                                                                  │
│ Source Integration → Canonicalization                             │
│                    → Canonicalization Write Interface             │
│                    → Canonical Knowledge → Materialization        │
│                                          → Published Views        │
│                                                                  │
│ Cross-cutting: lifecycle, policy, lineage, registries, audit     │
└───────────────────────────────────┬──────────────────────────────┘
                                    │
                                    ▼
                    Governed Published Interfaces
                                    │
                                    ▼
                           External Consumers
```

External source systems are inputs, not platform components. Consumer applications, agent runtimes, reading experiences, query behavior, reasoning, context construction, and generation are outside the Knowledge Platform.

The Knowledge Platform owns source integration, knowledge ingestion and canonicalization, Canonical Knowledge, materialization mechanisms, governed publication and internal access interfaces, and the cross-cutting Control Plane.

## 4. Goals

> **Non-normative traceability goals.** These goals explain the outcomes traced by the binding requirements in Parts II and III; they create no independent requirement.

The target architecture is intended to:

- preserve source-faithful multimodal content, structure, policy provenance, and lineage in durable Canonical Knowledge;
- decouple source evolution from projection evolution;
- keep each Published View Version exactly reproducible without Source access while its complete Reconstruction Closure is lawfully retained;
- enforce source and enterprise policy at canonical read, materialization, publication, and query boundaries;
- make change, deletion, denial, and lineage observable without leaking protected information;
- admit independently owned projection semantics without weakening platform invariants;
- provide stable Knowledge-side references that a future Canonical Experience domain can record.

## 5. Non-goals and rejected forks

The baseline does not define workflow or messaging products, storage engines, query engines, databases, deployment patterns, parser or model vendors, embedding models, concrete schemas, endpoint definitions, OpenAPI or MCP contracts, retry algorithms, retrieval tuning, numeric SLOs, roadmaps, staffing, or cost.

It is not a threat model, a final compliance certification, a delivery RACI, or an authorization for production.

The following architecture forks are explicitly rejected:

- a one-bag Canonical Knowledge Envelope or extensible property bag as the durable canonical contract;
- content-hash identity for Canonical Elements or Canonical Revisions;
- a Foundation-wide or enterprise entity-resolution or semantic identity spine;
- External Consumer time travel or a historical Published View interface;
- a global knowledge release as the serving unit;
- a concrete Context Gateway OpenAPI over canonical units for External Consumers;
- source re-parsing by a projection or External Consumer;
- session grants or bounded leases that authorize future Protected Observations;
- treating a Tombstone as legal erasure;
- treating vector representation as a Projection Type rather than a Retrieval Mode.

Under the **Normative Knowledge Platform target**, a coordinated release that packages several Published View Versions MAY exist for operational convenience. It MUST remain optional packaging: each view retains its identity, owner, policy, lifecycle, and serving contract, and the package MUST NOT become a global serving unit.

## 6. Decision traceability

The architecture ties each major decision to a problem or constraint:

- the closed canonical envelope and registries address incompatible source representations without lowest-common-denominator flattening;
- append-only revisions, complete deltas, manifests, and evidence lineage address auditability and replay ambiguity;
- differentiated projection ownership addresses the fact that graph meaning and synthesis truth are domain accountabilities;
- fail-closed policy evaluation addresses source-policy diversity and asynchronous governance change;
- immutable Published View Versions and publication fencing address late work, silent overwrite, and unsafe rollback;
- two-axis Coverage Reports address both silent omission and silent structural reduction;
- closed graph identity spaces prevent one owner from imposing semantic identity on another;
- explicit erasure operations separate logical lifecycle history from legal unrecoverability.

Decision evidence forms a three-layer chain:

1. this Baseline maps contract families to architecture goals, problems, and constraints;
2. the [architecture wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/1) points to the authoritative decision and research tickets; and
3. the Review Record binds one immutable repository commit containing this Baseline and [HLD.md](HLD.md) to the five required walkthroughs and the three reviewer outcomes.

---

# Part II — Enterprise AI Data Foundation Baseline

> **Authority: normative Foundation baseline.**

## 7. Two canonical domains

The Foundation contains two separate canonical domains:

- **Canonical Knowledge** represents what the enterprise knows from governed external sources.
- **Canonical Experience** may represent what the enterprise can learn from AI and agent execution.

The domains MUST remain logically separate. Each MUST canonicalize reusable data before downstream specialization. They MUST use compatible capability categories for versioning, lineage, policy, lifecycle, provenance, observability, and artifact management, but this requirement MUST NOT be interpreted as one shared physical service or one shared data model.

Cross-domain lineage and policy semantics MUST be compatible. The only Knowledge-side linkage promised by this baseline is the Knowledge Consumption Reference in §8.

## 8. Knowledge Consumption Reference

A **Knowledge Consumption Reference** is a persistable, non-authorizing address bundle copied by an observer from the Governed Observation Unit it actually observed. The Knowledge Platform does not mint a token, grant, event, or special envelope.

A complete reference has:

1. a required consumption referent: Published View, Published View Version, and the Governed Observation Unit identity inside that Version; and
2. optional lineage referents: Canonical Element Addresses and Enrichment Overlay Versions copied from that unit's Evidence Lineage.

A stored reference is not a grant. Every dereference is a new Protected Observation requiring a new Authorization Decision. A platform-held reference, and any copied address, digest, Artifact Reference, Source Evidence, or bytes that can re-identify its subject, MUST be included when a Legal Erasure Event or Retention Expiry Event names that subject's purge set. Semantic Equivalence Attestation MUST NOT retarget a stored reference or authorize reuse after Custody Purge.

Ingesting or publishing a Knowledge Consumption Reference in platform custody is itself a Protected Observation of the referenced object's existence. Published View, Published View Version, and Governed Observation Unit identities MUST never be reused.

> **Provisional mechanism contract (§2).** The remainder of this section — per-type referent forms, resolution behavior, and the post-purge non-reuse reservation mechanism — is provisional. **Validation event:** Canonical Experience domain design.

For Retrieval, the unit identity is shard-version-qualified. For Graph, it names a Graph Node or Graph Edge. For Wiki, it names the Wiki Published Bundle. A later registered Projection Type MUST follow the same rule. Carry-Forward does not collapse identity: the same Retrieval Segment appearing in two Published View Versions yields two consumption references. A Head is never a referent.

Consumption referents resolve only through Published View interfaces and only while current serving eligibility, Publication Policy, and Fail-Closed Governance allow. Tombstone, Retraction Event, Security Invalidation Event, erasure-pending, erasure-complete, and impermissible dependency staleness are unavailable. Historical Published View Version resolution is not an External Consumer interface.

Lineage referents resolve only through Governed Canonical Read and only for its named roles. Tombstoned addresses may remain historically resolvable under a new Authorization Decision; erasure-pending and erasure-complete MUST return unavailable with no identifying stub.

After Custody Purge, the platform MUST retain only a non-identifying reservation sufficient to prevent reuse; it MUST NOT retain the raw address as that reservation.

## 9. Binding cross-cutting invariant families

The following five families are binding across all legal Knowledge Platform paths.

### 9.1 Governance and leakage

- Source authorization MUST be the access ceiling.
- Effective Access Policy MUST intersect that ceiling with enterprise restrictions, including purpose, consent, and residency.
- Materialization and query MUST fail closed.
- Every Protected Observation, including an embedding or existence claim, MUST receive a Policy Decision Service decision committed against current Eligibility Epochs.
- Every derived object MUST carry the intersection of all evidence policies plus any additional restrictions.
- External Consumers MUST use Published View interfaces only.

### 9.2 Lineage

Every published Governed Observation Unit MUST carry complete Evidence Lineage through fully qualified Canonical Element Addresses and exact Enrichment Overlay Versions to Canonical and Source Revisions. Canonical Core writes MUST be platform-attested.

### 9.3 Rebuildability

Every Published View Version MUST remain digest-exactly reproducible without Source access while its complete Reconstruction Closure is lawfully retained in platform custody. Current serving eligibility does not weaken that obligation. Rebuild Verification MUST be purpose-bound, non-publishing, and fenced from erasure and expiry. Custody Purge of any required closure member ends the affected historical Version's rebuildability obligation because rebuilding it afterward is forbidden.

### 9.4 Deletion propagation

Source deletion MUST create lineage-scoped Tombstones and close dependent eligibility. Security Invalidation Events MUST advance affected Eligibility Epochs and stop serving until enforcement is current. Legal Erasure Events and Retention Expiry Events MUST close eligibility before Custody Purge makes all platform-held copies unrecoverable. A Tombstone MUST NOT be treated as erasure.

### 9.5 Canonicalization quality

The five-primitive envelope and validated Typed Payloads MUST preserve source fidelity without lowest-common-denominator flattening. The Coverage Report MUST gate both address-level coverage and declared structural reduction. Undeclared reduction is a defect. Every canonical content-state transition MUST have a Revision Delta that totally accounts for predecessor and successor Elements and Relationships; non-content selection changes use their required typed transition evidence instead.

---

# Part III — Knowledge Platform Target Architecture

> **Authority: normative Knowledge Platform target.**

## 10. Logical architecture and responsibilities

```text
External Sources
      │
      ▼
Source Integration
      │  captured content, source policy, artifacts, disposition
      ▼
Canonicalization
      │  source-faithful revision candidate
      ▼
Canonicalization Write Interface
      │  platform-attested atomic Canonical Revision
      ▼
Canonical Knowledge
      │  Core + separately versioned Enrichment Overlays
      ▼
Materialization Runs
      │  immutable manifests, fencing, Coverage Reports
      ▼
Published View Versions
      │  Retrieval | Graph | Wiki | registered future types
      ▼
Governed Published Interfaces
      │
      ▼
External Consumers

Control Plane: identities, registries, Heads, epochs, policy, lineage,
               invalidation, publication, erasure, and audit
```

### 10.1 Source Integration

Source Integration owns configured acquisition boundaries, Source Instances, discovery, capture, change and deletion evidence, source-native identifiers, source policy provenance, and Artifact References. It MUST distinguish confirmed deletion from empty content, denial, timeout, and other unavailability.

It does not own canonical semantics, projection semantics, or consumer behavior.

### 10.2 Canonicalization

Canonicalization owns source parsing, reconstruction, normalization, and atomic creation of source-faithful Canonical Revisions. It alone may write Canonical Core through the Canonicalization Write Interface.

It MUST NOT embed retrieval segmentation, embedding choices, graph ontology, or synthesis strategy in Canonical Knowledge.

### 10.3 Canonical Knowledge

Canonical Knowledge is the durable, versioned contract between source understanding and projection semantics. It owns the closed canonical envelope, Core, Enrichment Overlays, source evidence, governance references, and canonical lineage.

### 10.4 Materialization and publication

Materialization transforms declared Canonical Knowledge inputs into independently versioned Published Views. It owns execution mechanism, validation, coverage, policy derivation, lineage propagation, and publication fencing. It MUST NOT access or re-parse a Source.

Published View Owners own Head selection, rollback, and retirement. The platform may immediately close eligibility for safety, policy, deletion, or withdrawn dependencies; it MUST NOT fabricate owner publication as the remedy.

### 10.5 External Consumers

External Consumers own query formulation, retrieval strategy, ranking and blending, graph traversal and path planning, reading experience, context construction, tool use, reasoning, and generation. They MUST NOT reconnect to enterprise sources or parse them independently.

Retrieved text and other published content MUST be treated as untrusted input to generators. Publication eligibility and authorization do not make content safe instructions; prompt-injection and content-trust controls remain consumer responsibilities.

### 10.6 Control Plane

The Control Plane owns lifecycle decisions and their auditability: registry versions, execution identity, Revision Lineage, Head Selection Events, Revision Deltas, Overlay selection, Governance and Relationship Resolution Bindings, manifests, epochs, invalidation, publication state, and erasure state.

It coordinates what is eligible and selected. It does not decide graph meaning, synthesis truth, or application reasoning.

## 11. Canonical Knowledge logical contract

### 11.1 Closed envelope and Core boundary

The canonical envelope has exactly five primitives:

1. **Asset**
2. **Source Revision**
3. **Canonical Revision**
4. **Canonical Element**
5. **Canonical Relationship**

Enrichment Overlay, Artifact Reference, Source Evidence, Payload Binding, and Governance Binding are first-class contract types but MUST NOT be treated as additional envelope primitives.

**Canonical Core** contains source-faithful facts already available in machine-readable source form. Examples include native text, native tables, alt text, hyperlinks, explicit hierarchy, source-explicit ordering, raw spans, and geometry.

Reconstructed or interpreted understanding MUST be an **Enrichment Overlay**, including OCR text, visual table reconstruction, generated image descriptions, inferred hierarchy, inferred reading order, and competing transcriptions. The deciding test is whether the value adds judgment not explicit in the source; use of a model alone does not decide the boundary, and decoding or format conversion alone does not force an Overlay.

An Enrichment Overlay has a stable stream identity. Each Enrichment Overlay Version MUST have an immutable version identity, exactly one bound Canonical Revision, fully qualified same-Revision targets, a required Payload Binding, platform-generated producer and run attribution, creation time, a Governance Binding reference, and complete dependencies. It MAY carry complex derived structure in its Typed Payload and schema-defined confidence, but MUST NOT mint Canonical Elements or Canonical Relationships. Cross-Asset inferred semantics belong to materialization.

### 11.2 Identity and incarnation

A Source Instance is one immutable external tenant, repository, or equivalent source security domain. Reconfiguration MUST NOT reassign a Source Instance to another external domain.

An Asset is one permanent source-object incarnation within one Source Instance. Mutable descriptive Asset-level metadata MUST be independently versioned and MUST NOT influence Effective Access Policy or Canonicalization. Access-affecting source and enterprise attributes, including Security Classification, belong exclusively in Governance Binding Versions. Reuse of a source-native identifier creates a new Asset unless the Source proves continuity. Multi-source Assets are prohibited; composition across sources occurs in materialization.

A Source Revision is an immutable captured observation with an explicit `present`, `deleted`, or `unavailable` Source Revision Disposition. A confirmed deletion requires authoritative evidence and a guarded decision.

A Canonical Revision identity denotes one successful Canonicalization Execution. Every successful execution MUST mint a new, Asset-qualified identity even if its output is semantically or byte-equivalent to an earlier result. Failed executions mint none. Identity MUST NOT be derived from a content hash or reused.

A Canonical Element identity is revision-local. Its fully qualified Canonical Element Address is:

```text
(Asset identity, Canonical Revision identity, revision-local Element identity)
```

Every relationship endpoint, Overlay target, citation, Evidence Lineage reference, and canonical locator MUST use that full address. A bare Element identity MUST NOT cross a Revision boundary.

### 11.3 Concise primitive contracts

The following are logical fields, not a physical schema or API:

- **Asset:** permanent Asset identity, governed Asset kind, Source Instance and source-object references, current Governance Binding reference, independently versioned Asset Metadata, and optional identity-level Payload Binding. It has no mutable current-revision field.
- **Source Revision:** Asset-qualified identity, Source Revision Disposition, source-native or connector-minted version reference, capture time, integrity digest, capture attestation, Governance Binding reference, and Artifact References.
- **Canonical Revision:** Asset-qualified execution identity, exactly one Source Revision address, canonical contract version, Canonicalization Attestation, creation time, integrity digest, governance manifest, Elements, and Relationships.
- **Canonical Element:** revision-local identity, registered Element Kind, required Payload Binding, optional same-Revision parent address, conditional source-explicit ordinal, one or more Source Evidence locators, Governance Binding reference, and Artifact References.
- **Canonical Relationship:** revision-local identity and declaring Revision, registered Relationship Type, fully qualified endpoints, Source Evidence, Governance Binding reference, and optional Payload Binding.

A Canonical Relationship is a source-native assertion. It MAY span Assets, but both immutable endpoints MUST exist when it is created. It MUST NOT float to a Head or silently retarget. An unresolved external target is a typed Source Reference, not a dangling Relationship.

Every cross-Asset assertion MUST also have a stable source-side relationship identity and locally owned source anchor, plus the Relationship Type's symmetry and deduplication rules. The connector mints the stable identity or anchor when the source does not supply one. These are source facts distinct from the revision-local canonical identity.

### 11.4 Payload, evidence, and artifact contracts

A Payload Binding has exactly:

- a stable namespaced semantic payload type;
- an immutable payload schema reference;
- the value that validated against that schema.

A payload is typed only when the registry recognizes its type and schema, permits that attachment position, and validation succeeds. Asset MAY carry an identity-level Payload Binding; Canonical Element and Enrichment Overlay Version require one; Canonical Relationship MAY carry one. Source Revision and Canonical Revision have closed metadata and MUST NOT accept arbitrary payloads.

Source Evidence binds an Element, Relationship, Overlay, or Artifact Reference to one Source Revision through one or more typed, schema-validated locators. The initial locator families are registry seed data maintained in [docs/registries/foundation-seed-registrations.md](docs/registries/foundation-seed-registrations.md). Record position is Revision-scoped and MUST NOT establish stable identity.

An Artifact Reference carries artifact identity, media type, integrity digest, byte size, governed logical retrieval reference, Source Evidence, and Governance Binding reference. Binary bytes MUST NOT be inlined in the canonical envelope. The digest verifies integrity and MUST NOT be treated as a globally dereferenceable identity. A source-exposed image, audio object, video, or attachment becomes a Canonical Element only when it is meaningful source structure; that Element references the Artifact Reference for bytes.

### 11.5 Platform-attested writes

Canonical Core MUST be writable only through a platform-controlled Canonicalization Write Interface. The Control Plane binds each execution to one Asset, one Source Revision, writer identity, canonicalizer identity and version, canonical contract version, and execution identity.

The platform creates an immutable Canonicalization Attestation containing the attestation identity, Source and Canonical Revision addresses, writer-service identity, canonicalizer identity and version, contract version, execution identity, and issuance time. A caller MUST NOT submit or override its origin. The baseline requires authoritative immutable attestation; it does not require a cryptographic signature.

Model-assisted canonicalization receives no broader Core rights. Reconstructive or interpretive output uses the Enrichment Overlay write path. Materialization has read-only access to Canonical Knowledge.

## 12. Governed registries and initial taxonomy

### 12.1 Registry responsibilities

Element Kinds, Relationship Types, Typed Payload schemas, and Source Evidence locator schemas MUST be governed, namespaced, versioned registrations. Every registration and every immutable schema version MUST name an accountable owner. Every specialized Element Kind MUST declare exactly one Standard Canonical Element Ancestor. Every payload schema version MUST declare its permitted attachment kinds. Unknown registrations, schemas, or attachment positions MUST be rejected.

A Relationship Type declares owner, semantics, directionality or symmetry, valid endpoint kinds, and permitted payload schemas.

Registration has three levels:

1. **Standard Canonical Element Ancestors** provide cross-family fallback.
2. **Foundation Standard Registrations** provide reusable source-family kinds and payload contracts safe for multiple connectors and consumers.
3. **Owned Canonical Extensions** contain vendor- or domain-specific meaning in owned namespaces and degrade through one declared ancestor.

The five and only initial Standard Canonical Element Ancestors are:

- `container`
- `text`
- `record`
- `field`
- `media`

The ancestor set is the initial closed fallback vocabulary. The registered Element Kind set remains extensible.

### 12.2 Initial Foundation Element Kinds

The initial Foundation Element Kind registrations are registry seed data under §12.1, maintained in [docs/registries/foundation-seed-registrations.md](docs/registries/foundation-seed-registrations.md). Each binds to one of the five Standard Canonical Element Ancestors and passes every §12 gate; the set is expected to be revised by the first real connectors.

The boundary rules remain normative: page and spatial coordinates remain Source Evidence. Foreign keys remain Canonical Relationships. Vendor concepts remain Owned Canonical Extensions. Generated transcripts and descriptions remain Enrichment Overlays.

### 12.3 Initial Foundation payload contracts

The initial Foundation payload contract registrations are registry seed data under §12.1, maintained in [docs/registries/foundation-seed-registrations.md](docs/registries/foundation-seed-registrations.md). Field-level contents are expected to be revised by the first real connectors and consumers.

The content constraint remains normative: these payloads MUST contain source-family facts only. Identity, provenance, location, governance, and artifact metadata already present in common contracts MUST NOT be duplicated.

### 12.4 Owned Canonical Extension gate

An Owned Canonical Extension MUST have:

- a unique owned namespace and named owner;
- exactly one Standard Canonical Element Ancestor;
- a stable semantic payload type and immutable schema version;
- explicit permitted attachment kinds;
- explicit Source Evidence requirements;
- no duplicate common contract fields;
- no weakening of the Canonical Core versus Enrichment Overlay boundary;
- a passing fallback behavior for consumers that understand only the ancestor.

An ownerless, orphaned, unregistered, or incorrectly promoted extension MUST be refused.

## 13. Atomic validation and contract versioning

A Canonical Revision is the atomic validation boundary. Before accepting it, the platform MUST validate:

- unique revision-local identities;
- registered kinds, types, schemas, and attachment positions;
- Payload Binding conformance;
- existing, same-Revision, acyclic parents;
- non-conflicting source-explicit sibling ordinals;
- Source Evidence binding and Artifact Reference resolvability;
- Relationship endpoint existence and type constraints;
- attestation consistency;
- required Governance Bindings.

Any failure MUST reject the entire Canonical Revision with object-level errors. Partial Canonical Revisions are forbidden.

Each Enrichment Overlay Version validates independently and atomically: its targets, target kinds, payload, producer and execution attestation, dependency footprint, and governance references MUST conform. Failure does not invalidate Core, but the Overlay Version MUST remain unpublished.

Each Canonical Revision declares exactly one canonical contract version. Mixed envelope versions and in-place upgrades are forbidden. Re-canonicalization under a newer contract creates a new Canonical Revision. Published schema versions are immutable. Consumers and materializers MUST declare supported contract and schema versions and fail explicitly rather than silently discard unknown envelope fields.

## 14. Revision, selection, and dependency lifecycle

### 14.1 Independent lifecycle axes

Source content, native structure, native relationships, artifacts, or canonical source metadata changes create a Source Revision and may lead to a Canonical Revision. Re-canonicalization because of canonicalizer, contract, schema, or defect correction creates a new Canonical Revision against the existing Source Revision.

Descriptive Asset-level changes create an Asset Metadata Version. Derived understanding changes create an Enrichment Overlay Version. Governance changes, including Security Classification changes, create a Governance Binding Version. Adopting an output-influencing model, ontology, synthesis, or technical dependency creates a new Projection Definition Version and may lead to new materialization and publication lineage. None of those changes rewrites canonical content.

Capture retries with the same source-native revision identity and digest are idempotent. A new source-native revision identity remains a new Source Revision even when its digest matches.

### 14.2 Append-only lineage and Head selection

Source and Canonical Revision Lineage MUST be append-only directed acyclic graphs. Source-native ancestry is preserved; when unavailable, the platform records immutable observation sequence rather than inferring order from wall-clock time. Canonical derivation names exactly one Source Revision; lifecycle supersession is a separate edge.

Revision creation never implies selection. Source Head, Canonical Head, and Published View Head are computed from immutable Head Selection Events, not mutable fields.

An Asset has at most one Source Head and at most one Canonical Head. Zero Head is an explicit selected state, not a missing pointer or invitation to infer "latest."

Each Head Selection Event MUST be a linearizable, fenced, evidenced, attributed, and auditable compare-and-select decision.

> **Provisional mechanism contract (§2).** The exact verified-field enumeration below is provisional; the fenced linearizable-decision requirement above is normative. **Validation event:** first Retrieval tracer bullet.

It atomically verifies:

- the expected prior Head value, including explicit zero, and exact prior Head Selection Event identity;
- the exact candidate identity and digest, or exact cause selecting zero;
- the identity and digest of the required typed transition evidence;
- candidate eligibility and withdrawal state;
- every selector and dependency Eligibility Epoch bound by the operation;
- platform validation of the transition evidence; and
- actor authority, attributed reason, and time.

Prepared evidence authorizes nothing by itself. A failed fence, authority check, validation, or compare-and-select creates no selection event. Reselecting the same object always creates a new Head Selection Event and freshness boundary. Every dependant on selected state MUST bind the exact selection event as well as the selected object and Eligibility Epoch, so an `A → B → A` cycle cannot make old work current.

There is no universal transition Delta. Source Head uses Source Transition Evidence, Canonical Head uses Revision Delta when a canonical content-state transition exists, and Published View Head uses Publication Transition Evidence. A zero selection caused only by eligibility closure or owner unpublication references that event rather than fabricating content deletion.

### 14.3 Source and publication transition evidence

Source Head selects only an eligible `present` Source Revision or explicit zero. A `deleted` or `unavailable` Source Revision remains immutable causal evidence and is never itself Head.

> **Provisional mechanism contract (§2).** The field-level composition of the two evidence records below is provisional. Normative regardless: each Head kind carries typed, immutable, platform-validated transition evidence; selecting zero for deletion or unavailability requires an explicit guarded decision; historical replay is not Source rollback; and rollback is fully accounted rather than pointer movement. **Validation event:** first Retrieval tracer bullet.

**Source Transition Evidence** is an immutable, Asset-qualified lineage-and-authority record rather than a source-content diff. It binds the expected prior Head and selection event, selected candidate or zero, triggering Source Revision identity and digest, Source Instance and Asset incarnation, disposition, capture and producer attestations, transition class, native ancestry or immutable observation order, continuity evidence, and any deletion, reinstatement, or false-deletion-correction authority. Timeout, denial, failed capture, or other absence does not change Source Head by itself. Selecting zero for unavailability or authoritative deletion requires an explicit guarded lifecycle decision under declared source-selection policy.

Historical replay is not Source rollback. Restoration after deletion requires a new reinstating Source Revision or explicit correction of a proven false deletion. Native locator reuse without continuity proof remains a new Asset incarnation.

**Publication Transition Evidence** is an immutable shard-level transition manifest binding the prior semantic Published View Version and candidate Version through their exact Aggregate Manifests. It totally accounts for shard membership as retained, added, removed, rematerialized, attested-reused, or carried-forward, and binds the required Runs, two-axis Coverage Reports, Semantic Equivalence Attestations, Publication Policy, Projection Definition Version transition declaration, impact selection, exact dependencies, and eligibility fences.

Rollback is fully accounted rather than treated as pointer movement: shards leaving the selected set are removed, shards re-entering from the prior Version are added with their original immutable evidence, and identical membership is retained. After safety or owner unpublication, a replacement selection compares-and-selects from zero while its Publication Transition Evidence compares the candidate with the last selected nonzero Version in that lineage; only first publication uses an empty semantic baseline. Only the Published View Owner may publish, roll back, discretionarily unpublish, or retire. An eligibility-closing event may atomically clear Head through the platform safety path but selects no replacement and fabricates no owner decision.

### 14.4 Revision Deltas and Element Correspondence

Revision Delta is reserved for canonical content-state transitions. Initial selection compares empty state with the candidate; supersession or rollback compares the semantic predecessor Canonical Revision with the candidate; genuine whole-Asset deletion compares the selected Canonical Revision with empty state; and reinstatement after genuine deletion compares empty state with the new Revision.

> **Provisional mechanism contract (§2).** The predecessor-selection mechanics in the next paragraph and the correspondence case taxonomy below are provisional. Normative regardless (§9.5): every canonical content transition is totally accounted, local identity reuse creates no correspondence, no eligibility closure fabricates a deletion Delta, and unresolved correspondence blocks automatic re-anchoring, deletion inference, and automatic publication. **Validation event:** first canonicalizer producing Revision Deltas.

A Canonical Head clear caused by Retraction, withdrawal, or another non-content eligibility closure references that event and MUST NOT fabricate an all-deleted Revision Delta. On recovery from a temporary clear, the Head selector compares from zero while the Revision Delta compares against the last selected nonzero Canonical Revision on the chosen lineage. Selector predecessor and semantic predecessor MUST therefore be explicit and distinct.

Every Revision Delta MUST immutably, totally, and disjointly account for every predecessor and successor Element and Relationship:

- unchanged `1→1`;
- modified `1→1`;
- split `1→N`;
- merged `N→1`;
- deleted `1→0`;
- added `0→1`;
- explicitly unresolved.

Each mapping records reason and producer or algorithm version. Local Element identity reuse creates no continuity. Element Correspondence exists only through the Delta. Unresolved or incomplete correspondence MUST block automatic re-anchoring, deletion inference, and automatic publication. A selected canonical candidate MUST be eligible and derived from the current Source Head.

Canonicalization Execution produces ordinary Revision-to-Revision Deltas. During guarded authoritative whole-Asset deletion only, the Control Plane MAY atomically emit a platform-validated one-sided deletion Delta from the selected Canonical Revision's immutable object inventory. This grants no authority to author ordinary canonical diffs. The Delta, Tombstone, eligibility closure, and affected zero-Head selections MUST linearize as one safety transition.

A Semantic Equivalence Attestation MAY prove equivalence between distinct Revisions for an explicit scope, contract and schema versions, digest algorithm, and attestor. Reuse is legal only when that scope covers every input on which the Projection Definition depends and a rebound or re-derived two-axis Coverage Report passes. The attestation MAY authorize a new immutable reuse binding, but MUST NOT merge identities, refresh an old Published View silently, retarget a reference, or reuse purged data.

### 14.5 Overlay selection and relationship resolution

There is no global Overlay Head. A versioned Overlay Selection Policy selects exact eligible Enrichment Overlay Versions for one Canonical Revision and purpose from complete dependency footprints. Selection is frozen into the Materialization Input Manifest.

Confidence values from different Overlay producers MUST NOT be ranked as globally comparable unless both the Overlay schema and the Overlay Selection Policy define their comparability.

> **Provisional mechanism contract (§2).** The re-anchoring and resolution-advance conditions below are provisional. Normative regardless: re-anchoring never selects implicitly, and split, merged, deleted, or unresolved targets remain unresolved rather than guessed. **Validation event:** first Enrichment Overlay producer.

Automatic re-anchoring is allowed only when every dependency maps unchanged `1→1` and producer, model, schema, and re-anchor rule remain eligible. Re-anchoring creates a new candidate Overlay Version and never selects it implicitly. Split, merge, modification, deletion, unresolved mapping, or incomplete dependencies require recomputation or accountable confirmation.

A Relationship Resolution Binding maps an immutable cross-Asset Canonical Relationship assertion to an eligible target on a selected target lineage. It MAY advance through unambiguous Element Correspondence without rewriting the source-side Revision. Split, merge, deleted, or unresolved targets MUST remain unresolved rather than guessed.

The source-side relationship MUST be re-canonicalized only when the source assertion itself changes; advancing a resolved target does not rewrite Canonical Core.

### 14.6 Asset Metadata selection and dependency

> **Provisional mechanism contract (§2).** This entire section is provisional. Normative regardless: descriptive Asset Metadata never influences Canonicalization or Effective Access Policy (§11.2, §15.1), no consumer uses it implicitly, and eligibility closure on a metadata dependency propagates like every other closure (§9.4). **Validation event:** first Projection Definition that declares Asset Metadata as an input.

An Asset Metadata Version is an immutable, Asset-qualified complete version with immutable identity and digest, schema version, producer and provenance attestation, creation attribution, eligibility, and withdrawal state. Updates mint versions. Each Asset has at most one selected Asset Metadata Head; zero Head is explicit, and a historical eligible version is not an arbitrary substitute.

A dedicated immutable Asset Metadata Head Selection Event performs a linearizable compare-and-select. It atomically verifies the expected prior Metadata Head and prior selection event, candidate ownership, identity and digest, schema compatibility, attestation, eligibility and withdrawal, and current Asset Metadata lineage Eligibility Epoch, then records candidate, actor, reason, and time. Asset Metadata selection requires no Revision Delta. Reselecting the same Version creates a new selection event.

A Projection Definition MAY declare Asset Metadata as an input only when descriptive fields affect output or presentation. A dependant Materialization Input Manifest MUST bind the exact Asset Metadata Version, current Eligibility Epoch, and exact Asset Metadata Head Selection Event. Published Shards and Evidence Lineage preserve that dependency, and an Aggregate Manifest MUST keep it reconstructable through its Run and input-manifest references. No consumer may use Asset Metadata implicitly.

An ordinary Asset Metadata selection leaves the predecessor eligible but marks every declared dependant dependency-stale. Serving then follows Publication Policy. Retraction, withdrawal, applicable Tombstone, Legal Erasure Event, or Retention Expiry Event closes eligibility, advances the Asset Metadata lineage Eligibility Epoch, and immediately makes every dependant Run, shard, Published View Version, and Protected Observation unavailable. Publication Policy cannot override that closure. A security relabel is a Governance Binding change and follows Security Invalidation Event rules, never this metadata lifecycle.

### 14.7 Tombstone, retraction, and restoration

A Tombstone is immutable and records the deleting Source Revision, Delta edge, selected lineage path, event time, and attributed reason. It preserves history and MUST NOT mutate other branches.

For partial deletion, a successor Canonical Revision omits deleted objects, its Delta accounts for every deleted Element, descendant, and Relationship, and object Tombstones make the transition explicit. For authoritative whole-Asset deletion, acceptance of the deleted Source Revision MUST atomically create the Asset Tombstone, close prior canonical eligibility, clear Canonical Head, and install an invalidation barrier. Safety MUST NOT wait for an empty deleting Canonical Revision.

A Retraction Event atomically closes a Revision or selected Overlay Version's eligibility, clears or replaces selection, and invalidates dependants without deleting history or silently falling back.

A proven restoration creates a new Source Revision with explicit reinstatement lineage. Native locator reuse without continuity proof creates a new Asset incarnation. Corrections are append-only events.

Selectedness, freshness, eligibility, withdrawal, and presence are orthogonal facts. A non-deletion Source, Canonical, Overlay, Governance, or Relationship Resolution Head or selection advance marks every dependant dependency-stale and needing evaluation; it does not by itself close eligibility. Ineligible or retracted objects are unavailable. Ordinary staleness MAY serve only under explicit Publication Policy. Historical address resolvability is separate and remains governed by current policy, retention, hold, and erasure.

## 15. Governance, authorization, and erasure

### 15.1 Policy authority and normalization

The **Source Authorization Ceiling** is the maximum audience allowed by current source policy. The **Effective Access Policy** is the intersection of that ceiling with every applicable enterprise restriction, including purpose, consent, residency, classification, domain, and further owner restrictions. Enterprise policy MAY narrow and MUST NOT widen source authorization.

An Enterprise Security Domain is a hard authorization scope. Access across Enterprise Security Domains MUST require an explicit governed relationship; shared infrastructure, identity mapping, or source visibility MUST NOT imply cross-domain access.

Every Governance Binding Version MUST retain:

- raw source-policy provenance;
- normalized ReBAC relationships;
- source and enterprise security-domain context;
- enterprise identity mappings and attributes;
- classification, purpose, consent, residency, and other restrictions;
- deny-overrides-permit semantics.

Governance Binding Versions change independently of canonical content. Connector or ingestion identity confers Acquisition Authority only and MUST NOT define the audience. Operational Custody MUST NOT confer consumer access. Published Views have no implicit administrator bypass. Break-glass or legal-hold inspection MUST use a separate, purpose-bound, time-limited, audited Control Plane workflow and does not create ordinary consumer authorization.

Source labels MUST be preserved and may map to enterprise classifications. Classification may restrict but MUST NOT grant. Unresolved principals, mappings, encrypted labels, or unsupported constructs MUST fail closed.

Security Classification and every access-affecting source or enterprise attribute MUST live in Governance Binding Versions. Asset Metadata is descriptive only and MUST NOT grant, restrict, or otherwise participate in calculating Effective Access Policy.

A source whose policy cannot be faithfully normalized is a **Native Policy Asset**. It MAY publish only through federation under the end-user identity when that path preserves the native semantics; otherwise it MUST be excluded. Connector-level visibility and anonymous links MUST NOT be flattened into a consumer audience or interpreted as enterprise-public permission.

Source owners own source authorization policy. Security and Data Governance own enterprise mappings, classifications, restrictions, and native-policy approval. The Knowledge Platform owns normalization, identity integration, policy evaluation, enforcement, and auditability. Projection and Published View owners MAY add restrictions and MUST NOT remove them.

### 15.2 Protected Observations and derived policy

A Protected Observation is anything a principal can learn, including content, existence, discoverability, counts, relationships, inferred identity, inferred claims, snippets, summaries, citations, and embeddings or other retrieval representations.

The smallest independently observable semantic unit is a Governed Observation Unit. If an output cannot safely omit an unauthorized part, the whole output is one unit.

Every derived or compound unit MUST carry complete Evidence Lineage and a Derived Governance Policy equal to the intersection of every supporting evidence item's Effective Access Policy, followed by any additional producer or enterprise restriction. A projection MUST NOT widen access. Native-mapped Graph Edges include their assertion evidence and both endpoint evidence. Definition-inferred Graph Edges include every contributing item and both endpoint evidence. A Wiki Published Bundle is governed as one inseparable unit.

### 15.3 Policy Decision Service and read-side linearization

The Policy Decision Service is authoritative for every Protected Observation on Published View and Governed Canonical Read paths. Projection-local policy data is an optimization only.

The read-side linearization point is the commit of an immutable Authorization Decision for one Protected Observation. Each commit MUST observe the current Eligibility Epoch of every dependency of that observation, including affected Asset lineage, any Asset Metadata lineage whose descriptive content the observation carries, Governance Binding lineage, Enterprise Identity Spine, technical dependencies, and Published View Version. Asset Metadata remains a content dependency, not policy input. Unknown currency is not current.

Each observation requires a new commit. Cached policy results MAY be input to a new commit only when all exact policy and identity versions and every dependency epoch still match. A request snapshot, time-bounded lease, session grant, pre-authorized URL, or CDN decision MUST NOT authorize future observations.

Every cause that closes an eligibility-bearing dependency—including a Tombstone, Retraction Event, Security Invalidation Event, Legal Erasure Event, Retention Expiry Event, or technical dependency withdrawal—MUST advance that dependency's Eligibility Epoch. Epochs are per dependency, not platform-global or split by cause.

A Security Invalidation Event is a governance or identity change that may make prior output overexposed. It denies every principal on affected units until enforcement is current; unaffected units MAY continue serving. A pure access grant is not a Security Invalidation Event and need not advance an epoch. Security invalidation does not require content re-ingestion.

> **Provisional mechanism contract (§2).** The batch, stream, cache, and replica mechanics in the next paragraph are provisional. Normative regardless: every observation requires a fresh Authorization Decision commit against current Eligibility Epochs, a governance currency gap is never silently skipped, and mismatched versions or epochs never produce an allow. **Validation event:** first governed serving implementation.

In a batch, an already committed observation may finish; later observations require new decisions. On a stream, an ordinary item-level deny MAY omit that item. A currency gap or Security Invalidation Event affecting a remaining item MUST pause or terminate the stream with an attributable governance reason; it MUST NOT be silently skipped. A cache or replica with mismatched versions or epochs produces a miss or denial, never an allow.

Every allow, deny, and fail-closed outcome MUST have Authorization Decision Evidence sufficient to explain principal, observation, dependency epochs, policy and identity versions, source provenance, enterprise restrictions, reason, and evaluation time, subject to erasure.

### 15.4 Distinct deletion and erasure operations

The following operations MUST remain distinct:

- **Tombstone:** closes selected-lineage serving eligibility while preserving history and retained bytes. Historical resolution may remain possible under a new Authorization Decision.
- **Legal Erasure Event:** an attributed lawful request naming retained objects and every evidence-dependent object; it immediately closes eligibility and remains incomplete until Custody Purge completes.
- **Retention Expiry Event:** the same eligibility-close-then-purge lifecycle under a distinct attributed retention basis.
- **Legal Hold:** blocks Custody Purge and retention destruction. It does not restore ordinary serving eligibility or grant access.
- **Custody Purge:** cryptographic or physical destruction that makes every platform-held copy in the named set unrecoverable.
- **Non-Sensitive Erasure Record:** a non-consumer control-plane record of completion containing time, admitting actor, legal basis, hold identifiers, and a non-reversible scope count.

The purge set MUST include Source and Canonical Revisions, Asset Metadata Versions, Enrichment Overlay Versions, Published Shards, identifying Aggregate Manifest composition, Reconstruction Closure members, Rebuild Verification copies, artifacts, caches, replicas, backups, platform-held Knowledge Consumption References, and Authorization Decision Evidence when their evidence or content would re-identify a named object. A Wiki Published Bundle is purged as one unit. Subject-wide discovery is an attributed Control Plane review that produces the named set, not an automatic graph walk.

Redaction creates a successor Source or Canonical Revision through the ordinary append-only lifecycle; it MUST NOT edit immutable history in place. Published View immutability forbids overwrite but MUST NOT prevent Custody Purge of bytes or identifying composition.

Erasure or expiry is incomplete while any platform-held copy remains recoverable, including a backup awaiting normal expiry. After completion, Published View interfaces and Governed Canonical Read MUST return unavailable with no content or identifying stub. A Non-Sensitive Erasure Record MUST NOT identify the subject or reconstruct content. Re-ingest of the same source-native identity after purge creates a new Asset incarnation.

## 16. Materialization and publication contract

### 16.1 Projection Types and legal definitions

Projection Types are open by governed registration. The initial standard types are **Retrieval**, **Graph**, and **Wiki**. A registration MUST name an owner, define its Published View interface and Governed Observation Units, declare Coverage Report scopes, define a default Structural Reduction Profile, and identify the Structural Properties its interface can express. No Projection Type may publish semantic identity spanning Projection Definitions.

A Projection Definition is legal only when it:

- consumes Canonical Knowledge alone and has no Source access;
- names a Projection Definition Owner and Published View Owner;
- declares all semantic and technical dependencies;
- honors the same governance, lineage, coverage, fencing, and deletion-propagation obligations.

An external execution path meeting those gates still requires exception review. The authorization shape of a custom-materializer runtime principal is explicitly deferred to later logical design; exception approval is not a Canonical Knowledge read grant, and no such runtime may operate until its governed, address-qualified input path is approved. Re-parsing a Source or publishing without owners is invalid.

The Knowledge Platform owns type contracts, standard implementations, execution, validation, versioning, enforcement, lineage, and deletion propagation. It owns the standard Retrieval definition. It does not own graph meaning, Wiki truth, or application-specific retrieval semantics.

The Projection Definition Owner owns semantic creation, change, and deprecation. The Published View Owner owns publication, Rollback, and retirement.

For each Graph Projection Definition, the Ontology Steward and Projection Definition Owner MUST be the same accountable party; its Published View Owner MAY differ. For each Wiki Published View, the Knowledge Publisher, Projection Definition Owner, and Published View Owner MUST be the same accountable party. Wiki is an offered type, not a required default peer of Retrieval. Co-location means one accountable organizational principal, not necessarily one person.

Delegation is execution-only. Every approval, attestation, and Head Selection Event MUST record both acting principal and accountable party. Accountability transfer is immutable, explicitly accepted, prospective, and never rewrites history. A new Graph Ontology Steward requires a new Projection Definition Version. Wiki transfers all three roles together; transfer, the new Definition Version, and the new Knowledge Publisher's re-attestation of the serving Wiki Published Bundle MUST commit atomically or ownership remains unchanged.

Graph publication and definition lifecycles remain independent. Rollback to a still-eligible Version requires no renewed semantic approval while its Projection Definition Version remains active. Published View retirement does not deprecate a Projection Definition, and definition deprecation does not retire or unselect an already-serving eligible Head.

### 16.2 Complete Materialization Input Manifest

A Materialization Run is a function only of its Projection Definition and complete immutable Materialization Input Manifest. Nothing outside the manifest may influence output.

The manifest MUST name:

- every Canonical Revision address;
- exact eligible Enrichment Overlay Versions selected by policy or governed override; an override MUST pass the same eligibility and epoch checks and MUST NOT hand-pin an ineligible version;
- when the Projection Definition declares descriptive metadata as an input, the exact Asset Metadata Version, its Eligibility Epoch, and the Asset Metadata Head Selection Event that selected it;
- Governance Binding Versions;
- Relationship Resolution Bindings;
- Projection Definition identity and version;
- canonical contract, payload, locator, and relationship schema versions;
- every model, ontology, synthesis, and technical dependency version;
- the current Eligibility Epoch of every eligibility-bearing dependency.

Before execution, platform validation MUST prove that the manifest is complete and conforms exactly to its Projection Definition Version; substituted, additional, or omitted output-influencing dependencies are invalid. Standard Retrieval consumes exactly one Canonical Revision per Run. Graph and Wiki MAY consume many. Every custom Projection Definition MUST declare its input cardinality. Every type MUST accept only eligible Revisions and at most one selected Revision per Asset lineage.

### 16.3 Projection Definition versions and dependency transitions

Adopting any successor embedding, ontology, synthesis, model, runtime, executable artifact, or other dependency that can influence output MUST mint a new immutable Projection Definition Version. That Version freezes the complete transitive set of exact output-influencing dependency identities and versions. The Projection Definition Owner approves adoption; a producer or platform executor may publish a dependency or prepare a candidate but cannot adopt it. Publishing a successor dependency alone changes no definition, staleness, serving state, or Head.

Every successor Projection Definition Version MUST embed a transition declaration naming its predecessor, every direct and transitive dependency added, removed, or replaced, the attributed reason, deterministic applicability scope, and whether each change is comparability-affecting. Embedding space, segmentation semantics, ontology mapping, Identity Minting Rule, and preserve-versus-reduce change on an in-scope Structural Property are always comparability-affecting. A definition MAY add stricter cases but MUST NOT remove these. Missing, inconsistent, or unprovable scope or classification defaults to comparability-affecting whole-view impact.

> **Provisional mechanism contract (§2).** The impact-selection computation and attested-reuse mechanics in the next two paragraphs are provisional. Normative regardless: adoption mints immutable Projection Definition Versions, publishing a dependency is never adoption, the categorical comparability-affecting list stands, an unprovable narrower set defaults to whole-view impact, and an owner never excludes an exact reverse reference. **Validation event:** first Projection Definition version transition.

Impact selection is computed from exact reverse dependencies:

- a changed or withdrawn dependency affects every Projection Definition Version that names it directly or transitively;
- every Run, Published Shard, and Published View Version whose immutable manifest binds it is affected;
- a newly introduced dependency uses the successor Definition Version's declared applicability scope; and
- when the platform cannot prove a narrower complete set, the affected set is the entire Published View.

The owner MAY broaden impact but MUST NOT exclude an exact reverse reference. Every comparability-affecting transition rematerializes every shard under the successor Definition Version; Carry-Forward and Semantic Equivalence Attestation reuse are forbidden. For a validated non-comparability transition, every affected shard MUST be rematerialized. An unaffected still-eligible shard MAY receive a new immutable reuse binding only under a Semantic Equivalence Attestation covering the complete definition delta and changed dependency set, with the two-axis Coverage Report rebound or re-derived. This is attested reuse, not Carry-Forward.

Adoption creates candidate lineage only. After required rematerialization or attested reuse passes manifest validation, eligibility fencing, and Coverage Report gates, the platform MAY assemble a new Published View Version under the successor Definition Version. Only the Published View Owner may select it. Definition deprecation blocks new Runs and new Head selections under that definition but does not unselect an already-serving eligible Head.

Withdrawal closes the exact dependency version's eligibility, advances its Eligibility Epoch, and immediately makes every bound Run, shard, Published View Version, Aggregate Manifest, and Protected Observation ineligible. Publication Policy cannot override withdrawal, and late work MUST fail its fence. Recovery requires an owner-approved successor Definition Version, validated impact selection, required rematerialization or permitted attested reuse, a new immutable Published View Version, and a Published View Owner Head Selection Event. The platform selects no replacement and fabricates no retirement decision.

### 16.4 Publication fencing

A Run captures dependency epochs before execution and MUST atomically revalidate every exact dependency before publication. A pre-execution failure aborts with no output. A completed Run that fails the fence remains audit-visible but unselected and ineligible. Late work MUST NOT publish across a Tombstone, Retraction Event, Security Invalidation Event, erasure event, or dependency withdrawal.

A technical dependency withdrawal follows §16.3. It MUST NOT silently overwrite or semantically relabel a live Published View.

A Tombstone MUST close every Published View Version containing the affected Asset's shard, including previously selected Versions, and every shard carrying a Canonical Relationship into the tombstoned Asset. An Element Tombstone closes eligibility of its shard rather than creating ordinary staleness. Reconstruction of a safe Version remains the Published View Owner's act.

### 16.5 Published View identity and composition

A Published View is the stable logical projection product. A Published View Version is immutable, consumer-visible, and selected only by a Head Selection Event.

Each Version MUST declare its Projection Definition identity and version and whether the definition is platform-standard or domain-owned. It is composed by an immutable **Aggregate Manifest** naming exact Published Shard identities and digests, contributing Runs, input-manifest digests, and every carried-forward shard.

A Published Shard is one Asset's immutable contribution and is superseded rather than overwritten.

> **Provisional mechanism contract (§2).** The shard-placement rules in the next paragraph are provisional. **Validation event:** first Graph Projection Definition.

A native cross-Asset Graph Edge is placed in the asserting Asset's shard, and its Relationship Resolution Binding is a declared dependency of that shard. A definition-inferred multi-Asset unit is stored once in the lowest-ordered contributing Asset's shard, with all other contributors as dependencies.

### 16.6 Rebuildability and Rebuild Verification

Every Published View Version MUST remain exactly rebuildable while its complete Reconstruction Closure is lawfully retained in platform custody, whether or not the Version is selected or serving-eligible. Lawful retention requires an applicable retention basis or Legal Hold, including bounded custody needed to complete an accepted erasure or expiry workflow.

The Reconstruction Closure is the complete transitive set required to execute and verify the historical result without Source access:

- the Aggregate Manifest and expected Published Shard identities and digests;
- every exact Materialization Input Manifest and Projection Definition Version;
- every Canonical Revision, Enrichment Overlay Version, Asset Metadata Version and selection event when used, Governance Binding Version, Relationship Resolution Binding, contract and schema version, model, runtime, executable artifact, and technical dependency that influenced output; and
- every declared value required to eliminate output-affecting nondeterminism.

Nothing outside that closure may influence reproduction. A hidden runtime, seed, model artifact, ordering input, or undeclared dependency is a rebuildability defect.

> **Provisional mechanism contract (§2).** The Rebuild Verification workflow in the next two paragraphs is provisional. Normative regardless (§9.3, §15.4): a Published View Version remains exactly reproducible while its closure is lawfully retained, verification output is never consumer-visible, and Custody Purge cannot complete while any verification copy remains recoverable. **Validation event:** first rebuild capability design.

Historical replay is an attributed, purpose-bound, non-publishing **Rebuild Verification** under Operational Custody, not a Materialization Run. It MAY read retained but currently ineligible closure members for that authorized purpose, but its output is ineligible, never consumer-visible, has a new verification-attempt audit identity, and joins the same purge set as its inputs. Success requires exact Published Shard bytes and digests and exact Aggregate Manifest composition; semantic or contract equivalence is insufficient. It grants no serving eligibility, restoration, Rollback, consumer access, or Head selection.

Acceptance of a Legal Erasure Event or Retention Expiry Event MUST reject new verification and stop in-flight verification before it creates recoverable output. A separately authorized Legal Hold purpose is the only exception; it does not restore serving or make verification output publishable. Custody Purge MUST NOT complete while any verification copy remains recoverable.

Purging any required closure member ends the exact rebuildability obligation for the affected historical Version because post-purge reconstruction is forbidden. In a mixed-Asset Version, every evidence-dependent shard and identifying Aggregate Manifest composition is purged; independent shards outside the purge set MAY remain rebuildable while their own closures remain lawfully retained. Survivors do not redact or mutate immutable history. They may enter a successor Version only through a newly validated Aggregate Manifest, normal coverage and eligibility gates, a legal rematerialization or reuse path, and Published View Owner Head selection.

After purge, the Non-Sensitive Erasure Record and non-identifying identity-nonreuse reservation MUST NOT retain exact manifests, raw addresses, per-object digests, dependency lists, or other evidence that identifies the subject or reconstructs purged content or composition.

### 16.7 Publication Policy, Carry-Forward, and Rollback

Dependency staleness fails closed by default. A stale Version MAY serve only under an explicit versioned Publication Policy from its Published View Owner. That policy MUST NOT override Fail-Closed Governance or permit service through eligibility-closing events.

> **Provisional mechanism contract (§2).** The Carry-Forward composition mechanics in the next paragraph are provisional. Normative regardless: staleness fails closed absent an explicit Publication Policy, no policy overrides an eligibility-closing event, and Rollback never resurrects closed eligibility. **Validation event:** first Publication Policy implementation.

Carry-Forward is permitted only for freshness fence-outs. A Version MAY compose the last still-eligible shard, marked dependency-stale in its Aggregate Manifest, when Publication Policy permits and definition versions are comparability-compatible. Carry-Forward MUST NOT apply to eligibility loss or to a shard that failed either Coverage Report axis.

Rollback is a Head Selection Event selecting a still-eligible prior Published View Version. It MUST NOT resurrect content or dependencies whose eligibility has closed.

Embedding space, segmentation semantics, ontology mapping, Identity Minting Rule, and preserve-versus-reduce changes are categorically comparability-affecting. They require a complete new Version across all shards. A definition MAY add further comparability-affecting cases but MUST NOT remove these.

### 16.8 Two-axis Coverage Report gate

Every Materialization Run MUST produce one Coverage Report as a hard publication gate.

**Axis 1 — address-level coverage.** Every input in the Projection Type's declared scopes MUST be classified as covered, explicitly excluded for a Foundation-registered reason, or unrepresentable with a reason after Standard Ancestor degradation was attempted. Required scopes are:

- all Canonical Element Addresses for every type;
- all Enrichment Overlay Versions for every type;
- native Canonical Relationship types and instances for Graph;
- citations for Wiki.

An unaccounted input blocks publication. A Graph definition MUST declare every observed native Relationship Type as mapped or `explicitly-unmapped`; an unresolved target is a Relationship Resolution Binding gap, not a mapping. An unmapped or unresolved relationship MUST NOT be inferred automatically.

> **Provisional mechanism contract (§2).** Axis 2 below — the Structural Property taxonomy, standard profiles, preserve-witness rules, absorption rules, and the per-occurrence gate — is provisional. Normative regardless (§9.5): undeclared structural reduction is a defect, and a Run that cannot account for declared structure does not publish. Axis 1 above remains fully normative. **Validation event:** first Retrieval and Graph materializers.

**Axis 2 — structural reduction.** Every applicable occurrence among covered Core Elements MUST be reported as preserved or declared-reduced under the frozen Structural Reduction Profile. When a Projection Definition does not declare a profile, it MUST copy its Projection Type default into that definition version at authoring; live lookup of the type default is forbidden. Undeclared or contradicted reduction blocks the Run.

Initial Foundation-registered, ancestor-applicable Structural Properties are:

- containment: each `parentAddress` pair;
- ordinal: each covered parent with two or more source-explicit ordered children;
- `tabular-geometry`: each covered field carrying row span, column span, or header scope.

Initial Foundation-registered reduction reasons are `interface-linearization`, `synthesis-reduction`, `definition-omitted-structure`, and `absorbed-into-parent-unit`. Definitions MUST NOT mint their own properties or reasons.

The standard profiles are:

| Structural Property | Retrieval | Graph | Wiki |
|---|---|---|---|
| containment | `interface-linearization` | preserve | `synthesis-reduction` |
| ordinal | `interface-linearization` | out of scope | `synthesis-reduction` |
| `tabular-geometry` | `interface-linearization` | out of scope | `synthesis-reduction` |

Retrieval and Wiki MUST NOT claim preserve. Graph MAY declare `definition-omitted-structure` for containment. Preserve means the published interface exposes named Governed Observation Units that witness the occurrence; merely using structure as transform input is insufficient, and a preserve claim for a property the interface cannot express fails the Run. For Graph containment, the witness is a steward-typed Graph Edge whose evidence includes both addresses. The platform MUST NOT mint a containment edge.

The platform may infer `absorbed-into-parent-unit` only when a `field` child is not its own published unit and its address appears on a unit that also evidences its parent. Object-to-field and row-to-cell may absorb. Table-to-row, section-to-paragraph, collection-to-object, and aggregation of text, media, or records MUST NOT.

The structural gate is per occurrence with per-shard rollups. Overlay-internal structure is outside this axis; Overlay Version coverage remains on Axis 1. Semantic Equivalence reuse MUST carry a valid two-axis Coverage Report.

A reduced Governed Observation Unit carries the registered reason when its evidence is observable to the principal. The complete report is visible to the platform and Projection Definition Owner and, as applicable, the Ontology Steward or Knowledge Publisher. The Published View Owner receives eligibility and reason codes, not protected addresses. Version-level counts are not an External Consumer contract because counts and existence are Protected Observations.

## 17. Standard Published View interfaces

Every published unit MUST expose its stable unit identity, Published View Version context, Projection Definition version, freshness and eligibility semantics, complete Evidence Lineage, Core-versus-Overlay contribution, and Derived Governance Policy. The Policy Decision Service remains authoritative at observation time.

### 17.1 Retrieval

Retrieval publishes shard-version-qualified **Retrieval Segments**. A Segment contains a passage, supported lexical, dense, vector-similarity, or hybrid Retrieval Modes, relevant layout or spatial evidence, exact Canonical Element Addresses and Enrichment Overlay Versions, and Derived Governance Policy.

Segmentation and retrieval representation are materialization responsibilities. Query rewriting, strategy, blending, reranking, context assembly, and generation belong to External Consumers. Enterprise search is an External Consumer of Retrieval, not a separate Projection Type.

### 17.2 Graph

Graph publishes Governed Observation Units as Graph Nodes and Graph Edges. It does not publish a traversal or query engine. Every Node and Edge MUST carry an Ontology-Steward-governed type and declare whether it is native-mapped or definition-inferred.

Every Node and Edge identity is qualified by its Graph Projection Definition and a definition-local identity. A Canonical Element Address is evidence, never semantic identity.

> **Provisional mechanism contract (§2).** The Identity Minting Rule determinism mechanics in the next paragraph are provisional, except its final sentence: that a reduced evidence set mints a different identity rather than widening the old unit's policy is a normative governance requirement. **Validation event:** first Graph Projection Definition.

The definition's deterministic Identity Minting Rule derives Node identity from its evidence within one definition version. It promises stable diffing across Published View Versions of that definition version and promises nothing across definition versions. A reduced evidence set MUST mint a different identity rather than widen the old unit's policy.

A Graph Edge is likewise definition-qualified, typed by its Ontology Steward, bound to endpoints from the same definition, and distinguished as native-mapped or definition-inferred. Native-mapped edges carry assertion evidence and use the asserting Asset's shard. Definition-inferred units cite every contributing evidence item and use the inferred-unit placement rule in §16.5.

No shared identity space, required mapping, Foundation `same-as`, conflict detector, or cross-view identity index exists. The platform neither compares nor gates independently owned definitions on their agreement. Ontology Steward claims bind only their definition. A reconciliation graph is an ordinary owned Graph Projection Definition that rematerializes from Canonical Knowledge and mints its own identities; it MUST NOT import another Published View's units.

The Foundation does not mandate merged-node modelling or separate endpoint nodes plus an inferred edge. That choice belongs to the Graph Projection Definition and its Ontology Steward.

**Evidence Overlap**—equality of fully qualified Canonical Element Addresses or Enrichment Overlay Versions in Evidence Lineage—is the only cross-view join an External Consumer may assume. It implies shared cited evidence, not Node equality, Edge equality, or type agreement.

No Graph Node may exist without evidence. The existence and type of a definition-inferred unit are Protected Observations governed at the full evidence intersection.

### 17.3 Wiki

Wiki publishes one **Wiki Published Bundle** per Published View Version: a synthesis document with a mandatory citation set and Knowledge Publisher attestation. The entire Bundle is one Governed Observation Unit because omission of an unauthorized claim could leave inferable residue and invalidate its attestation.

Synthesis and citation policy are materialization responsibilities. Reading-product presentation, navigation, context assembly, and generation are External Consumer responsibilities.

## 18. Access boundaries and observable semantics

External Consumers MUST use standardized Published View interfaces only. They receive no Canonical Knowledge interface, historical-version time-travel promise, Coverage Report contents, canonical-unit API, or Control Plane erasure record.

**Governed Canonical Read** is an internal, Canonical-Element-Address-qualified interface for exactly these roles:

- Projection Definition Owner;
- Ontology Steward;
- Knowledge Publisher.

Each read is a Protected Observation evaluated against that principal's Effective Access Policy. Published View Owner, platform operator, Operational Custody, External Consumer, and future Canonical Experience are not added as read roles.

Published View interfaces MUST make version, source evidence, Evidence Lineage, policy outcome, freshness, and eligibility semantics observable without revealing unauthorized details. Consumers MUST be able to distinguish:

- a new immutable Version from an in-place change, which is forbidden;
- ordinary staleness permitted by Publication Policy from policy or deletion ineligibility;
- a denied observation from an empty successful result where safe;
- a stream termination or pause caused by governance currency;
- deletion or retraction unavailability from normal freshness;
- a rebuilt definition version from an older Version;
- a structural-reduction reason carried by an observed unit.

External Consumers MUST NOT receive platform-wide or Version-level protected counts merely to explain those states.

---

# Part IV — Architecture Acceptance and Endorsement

> **Authority: normative Knowledge Platform target.** These criteria define decision-complete architecture endorsement.

## 19. Review constituencies and outcomes

Three independent gates MUST pass:

- **Enterprise Architecture Reviewer:** authority levels, boundaries, responsibility completeness, consistency, traceability, and decision completeness.
- **Security and Data Governance Reviewer:** policy provenance, normalization limits, enforcement, revocation and deletion, lineage, audit, and trust boundaries. If security and data governance are separate offices, both sign this single gate.
- **AI Consumer Architecture Reviewer:** External Consumer contracts, projection-type responsibility split, and observable lifecycle semantics across representative Retrieval, Graph, Wiki, and agent use cases.

Roles are accountable review roles, not named people or a delivery RACI. Any constituency may block only on its published criteria.

Gates endorse normative content. A provisional mechanism contract (§2) is reviewed for consistency with the invariants it serves, not endorsed as frozen; a reviewer may block on a provisional passage only when it contradicts a normative invariant.

Each criterion outcome is:

- **pass**;
- **pass-with-follow-up**, allowed only for detail already outside this baseline and never for architecture-shaping ambiguity;
- **fail**.

An unresolved blocking objection means the baseline is not endorsed.

## 20. Enterprise architecture gate

All criteria MUST be verifiable; missing any one is a fail:

- the normative Foundation baseline and normative Knowledge Platform target are explicitly separated in this Baseline, and broader future direction is confined to the Narrative HLD and creates no requirements;
- Foundation, Knowledge Platform, External Sources, and External Consumers have one consistent boundary;
- layer responsibilities, data lifecycles, and interfaces have no gap or overlap;
- every architecture-shaping decision is resolved or explicitly deferred without blocking the next design phase;
- diagrams, prose, principles, and terms agree;
- architecture decisions are traceable to a goal, problem, or constraint.

## 21. Security and data governance gate

All criteria MUST be verifiable; missing any one is a fail:

- source policy, classification, ownership, and tenancy are preserved and traceable;
- normalization limits, and constructs that cannot be losslessly normalized, have an explicit handling path;
- every canonical, materialization, publication, and query path enforces governance;
- permission change, revocation, deletion, and tombstones invalidate Published Views and stop leakage on query paths;
- lineage, version, audit accountability, and trust boundaries are explicit;
- the Architecture Baseline states required controls and invariants; it does not pretend to be a threat model or final compliance certification.

## 22. AI consumer architecture gate

All criteria MUST be verifiable; missing any one is a fail:

- External Consumers have standardized Published View interfaces only; Governed Canonical Read exists as a governed internal interface, not an External Consumer interface;
- responsibility boundaries are explicit for Retrieval, Graph, and Wiki as an offered Projection Type that cannot exist without a Knowledge Publisher; Wiki is not required as a default peer of Retrieval;
- consumers can obtain version, source, lineage, policy, and freshness;
- consumers must not re-connect to or re-parse enterprise sources;
- rebuild, change, deletion, and denied-access semantics are observable;
- the coordinated companion documents do not promise concrete APIs, products, numeric SLOs, or retrieval tuning.

## 23. Required logical scenario walkthroughs

Contract completeness is judged primarily from this Baseline. [HLD.md](HLD.md) provides evidence for strategy, scope, rationale, and cross-document consistency. Prototypes and implementation evidence are not required. The Review Record MUST walk:

1. **New source revision:** a new Source Revision passes Source Transition Evidence, platform-attested canonicalization, canonical Revision Delta and immutable selection checks, and publication fencing into at least two materializations; Retrieval and Graph suffice.
2. **Permission revocation or deletion:** a governance change or deletion advances affected Eligibility Epochs, closes dependent eligibility, defeats cache and in-flight future observations, and prevents every Published View and query path from disclosing the data.
3. **Result trace:** a consumer follows a published unit's Evidence Lineage through exact Canonical Element Addresses and Enrichment Overlay Versions to its Canonical Revision and originating Source Revision.
4. **Projection dependency change:** owner adoption of a changed embedding, ontology, synthesis, or other output-influencing dependency mints a successor Projection Definition Version, selects the complete affected set from exact reverse dependencies, performs required rematerialization or permitted attested reuse, produces a new Published View Version, and never silently overwrites a live Version.
5. **New consumer onboarding:** a new External Consumer uses a registered Published View interface without implementing source integration, source parsing, or canonicalization.

## 24. Review Record, endorsement, and re-review

Each candidate repository commit containing both [ARCHITECTURE-BASELINE.md](ARCHITECTURE-BASELINE.md) and [HLD.md](HLD.md) MUST have one GitHub issue titled:

```text
Architecture baseline review — <version/commit>
```

Architecture Baseline Endorsement means that one immutable repository commit containing both companion documents is decision-complete enough for later logical design and for physical design that remains outside this baseline. The **Review Record** binds that commit, these criteria, the five walkthroughs, the three outcomes, blocking objections, and non-blocking follow-ups.

Each accountable reviewer records pass, pass-with-follow-up, or fail, with date and rationale as a traceable comment. Only when all three gates endorse may the Review Record be marked **Architecture Baseline Endorsed**.

A contract change that affects the Narrative HLD MUST update both companion documents in the same repository commit.

A later commit containing either companion requires a new review when it changes:

- system or responsibility boundaries;
- canonical or publication contracts;
- governance, security, or lifecycle invariants;
- normative architecture principles;
- consumer-observable behavior.

Pure narrative or copy edits require re-review only when they alter a boundary, promise, normative principle, or consumer-observable meaning. Non-semantic diagram changes do not require re-review.

A change confined to provisional mechanism contracts (§2) or registry seed data requires no new review while it does not contradict a normative invariant. Promoting a provisional passage to normative authority requires a new review of the affected gates.
