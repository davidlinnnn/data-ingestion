# Enterprise AI Data Foundation

Shared language for the Foundation target architecture and its first delivery domain, the Knowledge Platform.

## Architecture domains

**Enterprise AI Data Foundation**:
The umbrella target data architecture spanning Canonical Knowledge and future Canonical Experience.

**Knowledge Platform**:
The first bounded architecture domain of the Foundation, from source integration through governed publication of knowledge projections.
_Avoid_: Foundation Platform, ingestion platform

**Knowledge Platform program**:
The delivery effort accountable for the Knowledge Platform domain.

**Knowledge ingestion**:
A capability inside the Knowledge Platform, not a separate platform.
_Avoid_: ingestion platform

**Canonical Knowledge**:
The source-faithful, versioned representation of enterprise knowledge that projections consume.
_Avoid_: index, chunk store, knowledge graph

**External Consumer**:
An application, agent runtime, or reading experience outside the Knowledge Platform that uses a governed published interface.

**Knowledge Consumption Reference**:
A persistable, non-authorizing name of one Governed Observation Unit of one Published View Version, together with any Canonical Element Addresses and Enrichment Overlay Versions copied from that unit's Evidence Lineage. It is not a minted token, a grant, a Head, or a snapshot of content. A Graph unit is a Graph Node or Graph Edge. Ingesting or publishing the reference in platform custody is a Protected Observation, and its Published View, Published View Version, and unit identities are never reused.
_Avoid_: consumption event, experience link, document revision retrieved, durable capability token

## Canonical model

**Source**:
A configured and governed external acquisition boundary through which the Knowledge Platform discovers Assets.
_Avoid_: source object, Asset

**Source Instance**:
The immutable identity of one concrete external tenant, repository, or equivalent security domain behind a Source configuration. Reconfiguring a connector never reassigns an existing Source Instance to a different external domain.

**Asset**:
A stable logical knowledge-object incarnation discovered within one Source Instance. It persists across Source Revisions and source deletion, but a reused native identifier creates a new Asset unless the Source proves continuity. A Non-Sensitive Erasure Record cannot prove continuity with a purged incarnation.
_Avoid_: current document, current row set

**Asset Metadata Version**:
An immutable, Asset-qualified complete version of mutable descriptive metadata such as title, domain taxonomy, and display properties. It is selected independently of Asset identity, never influences Canonicalization, and never participates in Effective Access Policy; access-affecting attributes belong in Governance Binding Versions.
_Avoid_: mutable Asset fields, Security Classification, policy metadata

**Asset Metadata Head**:
The Asset Metadata Version currently selected for one Asset, or explicit zero. A historical eligible version is not an arbitrary substitute for the selected Head.
_Avoid_: latest metadata, mutable Asset fields

**Asset Metadata Head Selection Event**:
The immutable linearizable compare-and-select decision that selects an Asset Metadata Head after fencing the prior selection event, candidate identity and digest, schema, attestation, eligibility, withdrawal, and Asset Metadata lineage Eligibility Epoch. It creates a new freshness boundary even when reselecting the same Version and requires no Revision Delta.
_Avoid_: metadata pointer update, metadata Revision Delta

**Source Revision**:
An immutable captured observation of one Asset at a source version or observation point, explicitly classified as present, deleted, or unavailable.
_Avoid_: current source state

**Source Revision Disposition**:
The explicit `present`, `deleted`, or `unavailable` meaning of a Source Revision. Empty content, denied or failed capture, and confirmed deletion remain distinct.

**Canonical Revision**:
The immutable result of one successful canonicalization execution against one Source Revision. Separate executions remain separate revisions even when their content is equivalent.
_Avoid_: mutable canonical document

**Canonicalization Execution**:
An attempt to produce one Canonical Revision from one Source Revision under a specified canonicalizer and canonical contract. A successful execution creates exactly one revision; a failed execution creates none.

**Revision Lineage**:
The append-only directed acyclic graph of immutable Revisions and their source-native ancestry or lifecycle-supersession relationships.
_Avoid_: mutable revision history, revision-number ordering

**Source Head**:
The eligible `present` Source Revision, or explicit zero, currently selected by the Control Plane as an Asset's active source state. A `deleted` or `unavailable` Source Revision is causal evidence, never itself Head.
_Avoid_: latest observed revision

**Canonical Head**:
The Canonical Revision, or explicit zero, currently selected by the Control Plane as an Asset's active canonical state. It is computed from Head Selection Events rather than stored as a mutable Asset field.
_Avoid_: current revision field

**Head Selection Event**:
An immutable, auditable, linearizable compare-and-select decision that selects a Source Head, Canonical Head, or Published View Head. It fences the expected prior Head and exact prior selection-event identity, candidate identity and digest or cause selecting zero, typed transition evidence, every applicable Eligibility Epoch, authority, actor, reason, and time. Reselecting the same object creates a new event and freshness boundary.
_Avoid_: pointer update, generic transition Delta

**Source Transition Evidence**:
The immutable Asset-qualified lineage-and-authority record required by Source Head selection. It binds the prior Head and selection event, candidate or zero, triggering Source Revision, Source Instance and Asset incarnation, disposition, capture and producer attestations, ancestry or observation order, continuity, and any deletion, reinstatement, or correction authority. It is not a source-content diff.
_Avoid_: Source Revision Delta, absence-as-deletion, source rollback

**Revision Delta**:
The immutable canonical content-transition artifact that totally and disjointly accounts for every predecessor and successor Element and Relationship. It records cardinality-valid additions, deletions, changes, splits, merges, and explicitly unresolved correspondences without modifying either Revision. A temporary zero Head caused by non-content ineligibility has no fabricated deletion Delta; its selector predecessor and the Delta's semantic predecessor remain distinct.
_Avoid_: inferred ID reuse, partial diff, generic Head transition Delta

**Element Correspondence**:
An explicit Revision Delta mapping between revision-scoped Canonical Elements. Reusing the same local element identity across Revisions does not establish correspondence.
_Avoid_: stable element ID

**Semantic Equivalence Attestation**:
A versioned proof that two distinct Revisions are equivalent for a declared semantic scope, contract, schemas, and digest algorithm. It may authorize new immutable reuse bindings but never merges Revision identities or silently refreshes old outputs.

**Tombstone**:
An immutable, lineage-scoped lifecycle record that names the deleting Source Revision, Delta edge, selected path, event time, and attributed reason for an Asset or revision-scoped canonical object. It preserves rather than removes the object's history.
_Avoid_: hard delete, deleted flag, legal erasure

**Invalidation Event**:
An immutable record that makes a dependency impact observable as staleness or closed eligibility and traces it to its cause, such as a Tombstone, Retraction Event, security change, or superseding input.
_Avoid_: silent cascade delete

**Retraction Event**:
An immutable, attributed withdrawal that atomically closes a Revision or Enrichment Overlay Version's eligibility, clears or replaces its selection, and invalidates dependants while preserving history.
_Avoid_: delete, overwrite

**Lifecycle Status**:
The orthogonal selectedness, freshness, eligibility, withdrawal, and presence facts of a versioned object. It is not a single mutually exclusive state.
_Avoid_: current/stale/invalid/retracted enum

**Canonical Core**:
The source-faithful facts already available in machine-readable form in a Source Revision. Reconstructed or interpreted understanding remains outside the Core.

**Canonical Element**:
A revision-scoped unit of source-faithful content or structure within an Asset. Its identity is meaningful only together with its Asset and Canonical Revision.

**Canonical Element Address**:
The fully qualified identity of a Canonical Element: its Asset, Canonical Revision, and revision-local element identity.
_Avoid_: bare element ID, global element ID

**Canonical Element Kind**:
A governed, namespaced classification of a Canonical Element with a declared standard ancestor for graceful degradation.
_Avoid_: free-form kind, closed universal enum

**Standard Canonical Element Ancestor**:
One of the five cross-family fallback meanings for a Canonical Element Kind: container, text, record, field, or media. It preserves minimum generic behavior when a consumer does not understand a more specific registered kind.
_Avoid_: universal content type, source-family kind

**Foundation Standard Registration**:
A Foundation-owned Canonical Element Kind or Typed Payload contract whose source-family semantics are reusable across multiple connectors and safe for External Consumers to depend on.
_Avoid_: vendor kind, domain ontology, projection registration

**Owned Canonical Extension**:
A governed vendor- or domain-specific Canonical Element Kind or Typed Payload registration with a unique namespace, named owner, Standard Canonical Element Ancestor, immutable payload schema, permitted attachment kinds, and Source Evidence requirements. It may not duplicate common contract fields, weaken the Canonical Core boundary, or prevent unknown consumers from falling back to its ancestor.
_Avoid_: Foundation standard, unregistered custom type, projection registration

**Canonical Relationship**:
An identified, typed, source-native association whose endpoints are fixed Canonical Element Addresses and may span Assets. Every cross-Asset assertion has a stable source-side relationship identity and locally owned source anchor, minted by the connector when the source supplies neither, plus type-defined symmetry and deduplication rules. Inferred semantic associations belong to materialization, not Canonical Knowledge.

**Relationship Resolution Binding**:
A versioned lifecycle mapping from an immutable cross-Asset Canonical Relationship assertion to the eligible target on a selected target lineage. It advances without rewriting the source-side Canonical Revision.
_Avoid_: automatic relationship retargeting

**Canonical Relationship Type**:
A governed, namespaced definition of a Canonical Relationship's semantics, directionality, valid endpoint kinds, and permitted payload schemas.
_Avoid_: free-form relationship type

**Enrichment Overlay**:
A stable, producer-attributed attachment stream for derived reusable understanding bound to one Canonical Revision. It is a first-class contract type but not a canonical envelope primitive.

**Enrichment Overlay Version**:
One immutable, separately versioned result in an Enrichment Overlay, with its own identity, creation time, Governance Binding, platform-attested producer and execution identity, complete dependencies, exact same-Revision targets, and a required Payload Binding.

**Overlay Selection Policy**:
A versioned rule that selects exact eligible Enrichment Overlay Versions for one Canonical Revision and purpose using their complete declared dependency footprints. Confidence values from competing producers are comparable only when both their schema and this policy define comparability. Re-anchoring creates a candidate version but never selects it implicitly.
_Avoid_: global Overlay Head, highest-confidence wins

**Payload Binding**:
The attachment of a validated value through its stable namespaced semantic payload type and immutable concrete payload schema reference.

**Typed Payload**:
A schema-validated value carrying source-family or extension semantics through a Payload Binding. Its stable semantic type is distinct from its immutable concrete schema version.
_Avoid_: metadata bag, type label

**Source Evidence**:
A binding from canonical knowledge to a Source Revision through one or more typed, schema-validated locators such as a page region, text span, record key or position, schema member, source-object reference, JSON Pointer, temporal range, or artifact region.
_Avoid_: provenance bag, stable identity inferred from source position

**Evidence Lineage**:
The complete immutable chain from a governed or derived unit through exact Canonical Element Addresses and Enrichment Overlay Versions to Canonical Revisions and Source Revisions, distinguishing Core evidence from Overlay-derived evidence.

**Artifact Reference**:
A governed reference to binary source material such as an image, audio object, video, or attachment. It carries artifact identity, an integrity digest, retrieval metadata, Source Evidence, and governance, but the digest is not a globally dereferenceable identity and the reference is not itself a Canonical Element.
_Avoid_: embedded binary

**Canonicalization Write Interface**:
The platform-controlled logical write boundary through which one Canonicalization Execution atomically submits Canonical Core for one Asset and Source Revision and receives platform-generated provenance.

**Canonicalization Attestation**:
The platform-generated immutable record that binds a Canonical Core write to its Asset, Source Revision, canonicalizer version, contract version, and execution identity.
_Avoid_: caller-declared origin

**Source Reference**:
A source-native locator whose target has not been resolved to a Canonical Element Address. It preserves the source fact without creating a dangling Canonical Relationship.
_Avoid_: unresolved relationship

## Governance

**Source Authorization Ceiling**:
The maximum audience permitted by the current source authorization policy. Enterprise policy may narrow this audience but never widen it.

**Effective Access Policy**:
The intersection of the Source Authorization Ceiling and all applicable enterprise restrictions, including purpose, consent, residency, classification, and security-domain constraints.
_Avoid_: normalized source ACL

**Protected Observation**:
Anything a principal can learn through a governed interface, including content, existence, discoverability, counts, relationships, inferred claims, snippets, summaries, citations, embeddings, and other retrieval representations.

**Fail-Closed Governance**:
The rule that content is not published or retrieved when its policy is stale, unresolved, unsupported, or unavailable for enforcement. Retention for audit remains permitted unless a Custody Purge has completed.

**Governance Binding**:
A versioned reference from governed knowledge to raw source-policy provenance, normalized ReBAC relationships, identity mappings, and applicable enterprise attributes and restrictions. It changes independently of canonical content and retains deny-overrides-permit semantics.
_Avoid_: embedded ACL

**Native Policy Asset**:
An Asset whose source authorization semantics cannot be represented faithfully by the normalized enterprise policy model. It may be published only by federation under the end-user identity when that path preserves the native semantics; otherwise it is excluded.
_Avoid_: approximately normalized Asset

**Policy Decision Service**:
The authoritative evaluator of Effective Access Policy for every Protected Observation. Projection-local permission data may optimize evaluation but is not authoritative.

**Enterprise Identity Spine**:
The governed mapping of source-native users, groups, guests, and service identities into enterprise principals while retaining source provenance. An ingestion identity never determines the audience of ingested knowledge.

**Source Security Domain**:
The source-native tenant or equivalent authorization boundary retained as policy provenance.

**Enterprise Security Domain**:
The governed authorization boundary that scopes enterprise principals and resources. Access across domains requires an explicit governed relationship.
_Avoid_: tenant

**Security Classification**:
A source-preserved and enterprise-normalized sensitivity attribute carried only by a Governance Binding Version. It may restrict Effective Access Policy but never grant access by itself and is not Asset Metadata.
_Avoid_: Canonical Element Kind, descriptive taxonomy, Asset Metadata

**Derived Governance Policy**:
The intersection of the Effective Access Policies of every evidence item supporting a derived object, followed by any additional producer or enterprise restrictions. It requires complete evidence lineage and can never broaden access.

**Governed Observation Unit**:
The smallest independently observable semantic unit for which Effective Access Policy is evaluated, such as a Retrieval Segment, graph node or edge, citation, snippet, or aggregate. An output that cannot safely omit an unauthorized unit is governed as a whole; a unit that is a structural reduction of evidence the principal may observe carries the Foundation-registered reduction reason.

**Security Invalidation Event**:
A governance or identity-mapping change that may make previously published or derived knowledge overexposed. It advances Eligibility Epoch and closes eligibility rather than merely marking staleness, so each affected Governed Observation Unit remains unavailable to every principal until every dependent Governance Binding and identity mapping is enforceably current.
_Avoid_: identity epoch

**Acquisition Authority**:
Permission for a connector identity to capture source content and policy. It grants neither that identity nor platform operators consumer access to the captured knowledge.

**Operational Custody**:
Least-privileged, auditable platform access required to operate retained knowledge. It is separate from consumer authorization.

**Authorization Decision**:
The immutable, Eligibility-Epoch-fenced Policy Decision Service allow or deny of one Protected Observation. Its commit is the read-side linearization point against Security Invalidation Events.
_Avoid_: request snapshot, cached ACL, session grant, identity epoch

**Authorization Decision Evidence**:
The explainable record of one Authorization Decision, including the principal, Protected Observation, Eligibility Epoch, relevant policy and identity versions, source-policy provenance, enterprise restrictions, decision reason, and evaluation time. Evidence that would re-identify a purged subject or purged content is itself in the purge set.

**Legal Erasure Event**:
An attributed lawful request that names retained objects and every evidence-dependent object of those objects. It immediately closes eligibility and remains incomplete until Custody Purge makes the set unrecoverable in platform custody.
_Avoid_: tombstone, hard delete, inaccessibility-as-erasure, automatic subject walk, in-place redaction

**Retention Expiry Event**:
An attributed, scheduled end of a retention obligation that uses the same eligibility-close-then-purge pipeline as a Legal Erasure Event and remains a distinct legal basis.
_Avoid_: scheduled tombstone, implicit TTL delete

**Legal Hold**:
A freeze that blocks Custody Purge and Retention Expiry Event destruction. It does not restore or preserve ordinary serving eligibility, and it does not grant consumer access.
_Avoid_: consumer hold access, hold-as-publication

**Custody Purge**:
The cryptographic or physical destruction that makes a retained object unrecoverable in platform custody. It completes a Legal Erasure Event or Retention Expiry Event; a Tombstone never performs it. Completion includes every platform-held copy.
_Avoid_: hard delete, tombstone, in-place Revision overwrite, complete-pending-backup

**Non-Sensitive Erasure Record**:
The control-plane record that a Legal Erasure Event or Retention Expiry Event completed, including time, admitting actor, legal basis, hold identifiers, and a non-reversible scope count. It is not a Published View or Governed Canonical Read result, and it must not identify the data subject or reconstruct purged content.
_Avoid_: retained Authorization Decision Evidence, identifying title, shadow copy, consumer erased stub

## Projections

**Projection Type**:
A governed registration of one published interface family, such as Retrieval, Graph, or Wiki. It declares the interface whose units are Governed Observation Units, the coverage scopes its Materialization Runs must account for, and a default Structural Reduction Profile. No Projection Type may publish semantic identity spanning Projection Definitions.
_Avoid_: ad hoc projection, closed Retrieval/Graph/Wiki universe, vector projection type, cross-definition identity space

**Projection Definition**:
A versioned specification of how Canonical Knowledge is transformed into one Projection Type. It is legal only if it consumes Canonical Knowledge alone, names both a Projection Definition Owner and a Published View Owner, and honors the same governance, lineage, and deletion-propagation obligations as a platform-standard definition. A definition that reconciles what other definitions say is an ordinary definition rematerializing from Canonical Knowledge, never an importer of another view's published units.
_Avoid_: pipeline config, use-case schema, Foundation Standard Registration, Owned Canonical Extension, projection-consuming projection

**Projection Definition Version**:
One immutable, owner-approved version of a Projection Definition that freezes its complete transitive set of exact output-influencing dependencies. A successor embeds its predecessor, every dependency change, reason, deterministic applicability scope, and whether each change is comparability-affecting. Publishing a successor dependency does not adopt it; adoption creates candidate lineage and never changes a serving Head by itself.
_Avoid_: mutable dependency bundle, generic projection version, latest model

**Structural Property**:
A Foundation-registered, ancestor-applicable aspect of Canonical Knowledge structure that a projection must account for. The initial set is containment, ordinal, and tabular-geometry.
_Avoid_: fidelity dimension, flatten-check, payload field, native relationship type, association

**Structural Reduction Profile**:
A versioned declaration, frozen into a Projection Definition version, of which Structural Properties it preserves versus reduces, each reduction naming a Foundation-registered reason. A silent definition copies its Projection Type's default profile when that definition version is authored; live lookup of the type default is not allowed.
_Avoid_: fidelity profile, flatten policy, fidelity score, run-time inherit

**Retrieval Mode**:
A retrieval technique that a Retrieval Published View supports over the same Retrieval Segments, such as lexical, dense, or hybrid. It is a property of a Projection Definition, never a separate Projection Type.
_Avoid_: keyword projection, vector projection, search projection

**Published View**:
The stable logical identity of one governed, addressable projection product that External Consumers may use.
_Avoid_: index, wiki site, knowledge graph

**Published View Version**:
An immutable, consumer-visible publication of one Published View, composed of an Aggregate Manifest, never overwritten in place, and declaring the Projection Definition identity, version, and platform-standard versus domain-owned status. It remains exactly rebuildable while its complete Reconstruction Closure is lawfully retained. Immutability forbids overwrite, not Custody Purge of its bytes or identifying composition; purging any required closure member ends the exact historical Version's rebuildability.
_Avoid_: latest run, live index overwrite

**Published View Head**:
The Published View Version, or explicit zero, currently selected by the Control Plane as a Published View's serving state. It is computed from Head Selection Events rather than stored as a mutable field.
_Avoid_: current index, current projection

**Publication Transition Evidence**:
The immutable shard-level transition manifest required by Published View Head selection. It binds prior semantic and candidate Aggregate Manifests, totally classifies shard membership as retained, added, removed, rematerialized, attested-reused, or carried-forward, and carries the required Runs, Coverage Reports, attestations, policy, Definition transition, impact selection, exact dependencies, and fences.
_Avoid_: generic transition Delta, pointer swap, unaccounted rollback

**Materialization Run**:
One execution of a Projection Definition against one Materialization Input Manifest, with no access to any Source. Its output may be selected into a Published View Version or left unselected as ineligible; it is never itself the External Consumer contract.
_Avoid_: published job, pipeline as the consumer unit

**Materialization Input Manifest**:
The complete immutable set of Canonical Revision addresses, Enrichment Overlay Versions, any declared Asset Metadata Version with its exact Head Selection Event, Governance Binding Versions, Relationship Resolution Bindings, Projection Definition Version, contract and schema versions, complete output-influencing technical dependencies, and Eligibility Epochs from which one materialization result is produced. Nothing outside the manifest may influence the result.
_Avoid_: Canonical Revision plus hidden dependencies

**Reconstruction Closure**:
The complete transitive set of lawfully retained artifacts required to execute and verify a digest-exact reproduction of one Published View Version: its Aggregate Manifest, exact Materialization Input Manifests, Projection Definition Version, expected Published Shard identities and digests, every declared Canonical Revision, Overlay, Asset Metadata Version and Head Selection Event, Governance Binding, relationship, contract, schema, model, runtime, executable artifact, and technical dependency that influenced output, and every value needed to eliminate output-affecting nondeterminism. Current serving eligibility is not part of the definition.
_Avoid_: currently eligible inputs, source fallback, best-effort dependency set

**Rebuild Verification**:
An attributed, purpose-bound, non-publishing Control Plane replay of a lawfully retained Reconstruction Closure under Operational Custody. It may read retained but currently ineligible dependencies, must reproduce the exact Published Shard bytes and digests and Aggregate Manifest composition, and creates a new audit identity without creating a new Published View Version. Its outputs are ineligible, never consumer-visible, and belong to the same purge set as their inputs. A Legal Erasure Event or Retention Expiry Event fences new and in-flight verification unless a separately authorized Legal Hold purpose permits it; Custody Purge cannot complete while any verification copy remains recoverable.
_Avoid_: Materialization Run rebuild mode, republish, semantic-equivalence check, serving restoration

**Publication Policy**:
A versioned rule, declared by the Published View Owner, that states whether dependency-stale Versions of that view may continue serving. It never overrides Fail-Closed Governance, and absent a declared policy a stale Version stops serving.
_Avoid_: implicit freshness, serve-latest

**Carry-Forward**:
The explicit reuse of a prior still-eligible Published Shard in a new Published View Version after a freshness-only fence-out, marked dependency-stale in the Aggregate Manifest and permitted only by Publication Policy and comparability.

**Rollback**:
A Head Selection Event that selects a still-eligible prior Published View Version. It cannot restore content or dependencies whose eligibility has closed.

**Eligibility Epoch**:
The fencing value of one eligibility-bearing dependency, advanced by every cause that closes that dependency, including Tombstone, Retraction Event, Security Invalidation Event, Legal Erasure Event, Retention Expiry Event, and technical withdrawal. A Head Selection Event or Authorization Decision is valid only if committed against the current epoch of every dependency it bound.
_Avoid_: check-then-publish, identity epoch, separate governance epoch, platform-global epoch

**Coverage Report**:
The required Materialization Run artifact accounting for every input in the scopes its Projection Type declares, each as covered, explicitly excluded for a registered reason, or unrepresentable with a reason, and for every applicable Structural Property of each covered input as preserved or declared-reduced. An unaccounted input or Structural Property makes the Run's output ineligible for publication.
_Avoid_: implicit omission, silent drop, self-declared exclusion reason, fidelity report, fidelity score

**Retrieval Segment**:
The Retrieval Published View's Governed Observation Unit: a shard-version-qualified passage carrying its own retrieval representations, its complete Evidence Lineage through Canonical Element Addresses and Enrichment Overlay Versions, and its Derived Governance Policy.
_Avoid_: chunk, vector segment, embedding-only record

**Graph Node**:
The Graph Published View's Governed Observation Unit: a typed node identified by its Graph Projection Definition together with a definition-local identity, carrying its Ontology Steward type, complete Evidence Lineage, Derived Governance Policy, and native-mapped versus definition-inferred distinction. A Canonical Element Address is evidence of a node, never its identity. No node exists without evidence, and the existence of a definition-inferred node is itself a Protected Observation at its evidence intersection.
_Avoid_: entity, real-world entity, shared entity, enterprise graph identity, address-keyed node, evidence-free steward assertion

**Identity Minting Rule**:
The part of a Graph Projection Definition that derives a Graph Node's definition-local identity from its evidence. It is deterministic within one definition version, so the same subject mints the same identity in every Published View Version of that view, and it promises nothing across definition versions. Because identity is derived from the evidence set, a reduced evidence set mints a different node rather than the same node with widened access.
_Avoid_: entity resolution rule, node key, stable global id, cross-view identity function, surviving-side collapse

**Graph Edge**:
The Graph Published View's other Governed Observation Unit: a typed edge identified by its Graph Projection Definition and a definition-local identity, with endpoints in that same definition, complete evidence, Derived Governance Policy, and a native-mapped versus definition-inferred distinction. A native-mapped edge includes assertion and both endpoint evidence and is held in the asserting Asset's shard; an inferred edge includes every contributing evidence item and both endpoint evidence, then follows the inferred-unit placement rule.
_Avoid_: inter-ontology link, shared edge, cross-definition identity edge, endpoint-keyed shard placement

**Evidence Overlap**:
The equality of Canonical Element Addresses or Enrichment Overlay Versions appearing in the Evidence Lineage of units published by different Published Views. It names the same cited canonical objects and is the only cross-view join an External Consumer is entitled to make. It never implies Graph Node equality, Graph Edge equality, or type agreement.
_Avoid_: cross-view identity, same-as index, entity resolution, shared identity space

**Wiki Published Bundle**:
The Wiki Published View Version's consumer-visible artifact: a synthesis document with a mandatory citation set, published under a Knowledge Publisher attestation. It is a single Governed Observation Unit, because a synthesis cannot safely omit an unauthorized claim.
_Avoid_: wiki site, unsourced page, claim-level redaction

**Published Shard**:
The immutable contribution of one Asset to one Published View Version. Sharding provides deterministic incremental composition and dependency cuts; it does not define policy scope. Each Governed Observation Unit is governed from its complete evidence intersection. A shard is superseded, never overwritten. A unit inferred from several Assets is held once in the lowest-ordered contributing Asset's shard, with every other contributor declared as a dependency.
_Avoid_: index partition, mutable segment file, replicated unit, non-Asset shard class

**Aggregate Manifest**:
The immutable composition of one Published View Version: the Published Shard identities and digests it comprises, with their contributing Materialization Runs and input-manifest digests. It marks every carried-forward shard as dependency-stale.
_Avoid_: monolithic rebuild, live shard swap

**Comparability-Affecting Change**:
A Projection Definition change that alters how a view's units compare with one another. Embedding space, segmentation semantics, ontology mapping, the Identity Minting Rule, and a preserve-versus-reduce change on an in-scope Structural Property are categorically comparability-affecting; a definition may add cases but never remove them.
_Avoid_: partial embedding-model migration, self-declared non-affecting embedding change, shard-by-shard re-key

**Governed Canonical Read**:
The internal interface through which Projection Definition Owners, Ontology Stewards, and Knowledge Publishers read Canonical Knowledge by Canonical Element Address, every read evaluated as a Protected Observation by the Policy Decision Service. It is not an External Consumer interface and is not Operational Custody.
_Avoid_: consumer canonical API, ungoverned canonical access, operator read, Canonical Experience read role

## Accountability

**Projection Definition Owner**:
The party accountable for semantic creation, change, dependency adoption, and deprecation of a Projection Definition. It may delegate execution but not decision accountability. For Graph it is the Ontology Steward; for Wiki it is the Knowledge Publisher.

**Published View Owner**:
The single party accountable for publishing, rolling back, discretionarily unpublishing, and retiring one Published View. For Wiki it is the Knowledge Publisher; for Graph it may differ from the Ontology Steward.

**Ontology Steward**:
The named party that is also Projection Definition Owner for one Graph Projection Definition. It is accountable for that definition's semantic claims, changes, dependency adoption, and deprecation; its Published View Owner may differ. A transfer requires a new Projection Definition Version and never rewrites historical attribution.
_Avoid_: Enterprise Ontology Steward, Domain Ontology Steward, entity resolution office

**Knowledge Publisher**:
The named accountable party that is both Projection Definition Owner and Published View Owner for one Wiki Published View. It owns synthesis rules, citation policy, semantic change, dependency adoption, publication, Rollback, and retirement. All three roles transfer together with a new Definition Version and atomic re-attestation of the serving Wiki Published Bundle.
_Avoid_: Wiki owner, content team

## Review

**Architecture Baseline Endorsement**:
The recorded state that the three review constituencies have all accepted one immutable repository commit containing both the Architecture Baseline and Narrative HLD as decision-complete for architecture.
_Avoid_: program approval, budget approval, production authorization, compliance certification

**Review Record**:
The GitHub issue bound to one immutable repository commit containing both companion documents that holds the acceptance criteria, required scenario walkthroughs, blocking objections, follow-ups, and three reviewer outcomes.

**Enterprise Architecture Reviewer**:
The accountable role that endorses document authority, boundaries, consistency, and architecture-level decision completeness.

**Security and Data Governance Reviewer**:
The accountable role that endorses governance and security invariants. If those offices are separate, both sign this single gate.

**AI Consumer Architecture Reviewer**:
The accountable role that endorses External Consumer contracts across the registered Projection Types and representative agent use cases.
_Avoid_: every product team
