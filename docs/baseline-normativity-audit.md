# Baseline Normativity Audit

**Document status:** Discussion aid, non-normative
**Audience:** Baseline authors and the three review constituencies
**Subject:** [ARCHITECTURE-BASELINE.md](../ARCHITECTURE-BASELINE.md) at the current working tree

> **Applied 2026-08-31.** The verdicts below were applied to the Baseline: §2
> now defines the provisional tier and its index, seed registrations moved to
> [docs/registries/foundation-seed-registrations.md](registries/foundation-seed-registrations.md),
> and §19/§24 were amended. Two reviewer deviations from the table below: §14.7
> and §16.4 were kept fully normative — their procedural content is small and
> deletion-safety-adjacent, so a provisional carve-out was not worth the
> reading complexity.

This audit asks one question per Baseline section: **does this content need to be
frozen now, or is it mechanism detail that should be validated by implementation
before it is frozen?** It proposes a normativity tier for every section. It does
not propose deleting any content, and it creates no requirements; the
Architecture Baseline remains the sole normative source.

---

## 1. The test

A contract belongs in the early, frozen baseline when at least one of these is
true:

1. **One-way door.** Retrofitting it after data exists is prohibitively
   expensive or impossible (identity schemes, policy propagation, evidence
   capture).
2. **Universal dependency.** Every later component builds on it, so ambiguity
   now multiplies cost later (the canonical boundary, ownership model,
   lifecycle axes).
3. **External obligation.** Law or enterprise security requires it regardless
   of architecture preference (erasure, retention, access ceilings).

A contract that passes none of the three is **mechanism**: it describes *how* an
invariant will be honored rather than *what* must remain true. Mechanism written
before implementation feedback tends to be revised, and in this Baseline every
revision of a normative section is a candidate re-review trigger (§24). The
proposal is therefore not to remove mechanism content but to hold it at a lower
freeze level until a first implementation validates it.

## 2. Proposed third authority level

Baseline §2 currently defines two authority levels. This audit proposes adding a
third:

> **Provisional mechanism contract.** Binding design intent for the named
> mechanism. Implementations MUST NOT contradict it silently, but it is expected
> to be revised from implementation feedback, and revising it does not by itself
> trigger re-review. Each provisional section names the validation event (for
> example, the first end-to-end Retrieval tracer bullet) after which it is
> either promoted to normative or revised.

This keeps every piece of existing thinking in the document while shrinking the
surface that endorsement freezes and that §24 guards.

## 3. Verdict summary

| Verdict | Meaning |
|---|---|
| **Normative** | Freeze now. Passes the test in §1. |
| **Split** | The stated invariant stays normative; the procedural or field-level detail in the same section becomes provisional. |
| **Provisional** | Whole section becomes a provisional mechanism contract, validated by a named implementation event. |
| **Seed data** | Content is registry contents, not architecture. Move to governed registry seed lists owned outside the frozen baseline. |

Approximate weight of the current Part II–III text: roughly half stays fully
normative, a third splits, and the remainder becomes provisional or seed data.

## 4. Section-by-section verdicts

### Part I — Document authority and framing (§1–§6)

| Section | Verdict | Rationale |
|---|---|---|
| §1–§4 Purpose, authority, scope, goals | Normative | Framing and boundary; cheap, load-bearing. §2 gains the third authority level proposed above. |
| §5 Non-goals and rejected forks | Normative | Rejected forks are one-way-door decisions in prohibition form; keeping them is nearly free and prevents re-litigation. |
| §6 Decision traceability | Normative | Meta-structure only. |

### Part II — Foundation baseline (§7–§9)

| Section | Verdict | Rationale |
|---|---|---|
| §7 Two canonical domains | Normative | Domain separation is a one-way door for both data models. |
| §8 Knowledge Consumption Reference | Split | Keep normative: non-authorizing nature, new Authorization Decision per dereference, inclusion in purge sets, no identity reuse (identity scheme + erasure obligation). Provisional: the per-type resolution behavior, Carry-Forward identity non-collapse detail, and post-purge reservation mechanics — this bridges to a *future* domain and will be revisited when Canonical Experience is designed. |
| §9 Five invariant families | Normative | This is exactly the content an early baseline exists to hold. All five pass the test. |

### Part III — Knowledge Platform target (§10–§18)

| Section | Verdict | Rationale |
|---|---|---|
| §10 Logical architecture and responsibilities | Normative | The separation-of-concerns core; directly resolves the current pipeline problem. |
| §11.1 Closed envelope, Core vs. Overlay | Normative | The canonical boundary itself; the single most expensive thing to retrofit. |
| §11.2 Identity and incarnation | Normative | Identity scheme; content-hash rejection and full-address qualification are one-way doors. |
| §11.3 Primitive logical fields | Normative | Identity, evidence, and governance fields must exist from the first byte written; already declared "logical fields, not a physical schema." |
| §11.4 Payload, evidence, artifact contracts | Split | Structure stays normative. The initial Source Evidence locator family list is seed data (already labeled "initial"; real connectors will extend it). |
| §11.5 Platform-attested writes | Normative | Trust boundary; retrofitting attestation after ungoverned writes exist is impossible. |
| §12.1 Registry model, three levels, five ancestors | Normative | Vocabulary governance is a one-way door; the closed ancestor fallback set is a deliberate compatibility contract. |
| §12.2 Initial Foundation Element Kinds | Seed data | Which kind maps to which ancestor will be revised by the first real connectors; it is registry content, not architecture. |
| §12.3 Initial Foundation payload contracts | Seed data | Field-level contracts ("cell: required value; optional row span…") are logical-design detail; freezing them pre-implementation invites churn and re-review cost. |
| §12.4 Owned Canonical Extension gate | Normative | Governance rule guarding the canonical boundary. |
| §13 Atomic validation and contract versioning | Normative | No-partial-revisions, immutable schema versions, and no in-place upgrades prevent unrecoverable canonical corruption. The validation checklist derives from §11–§12 and moves with them. |
| §14.1 Independent lifecycle axes | Normative | The decoupling that answers the pipeline problem; universal dependency. |
| §14.2 Append-only lineage and Head selection | Split | Keep normative: append-only DAGs, creation-is-not-selection, explicit zero Head, Head changes are linearizable, fenced, evidenced, auditable events. Provisional: the exact seven-item fence field list — validate against the first Control Plane implementation. |
| §14.3 Source and publication transition evidence | Split | Keep normative: typed evidence per Head kind, deletion requires authority, rollback fully accounted. Provisional: the exhaustive field enumerations of both evidence records. |
| §14.4 Revision Deltas and Element Correspondence | Split | Keep normative: every content transition is totally accounted; no correspondence from local-identity reuse (anti-silent-loss, §9.5). Provisional: the seven-case cardinality taxonomy and semantic-versus-selector predecessor mechanics — validate against the first canonicalizer that produces deltas. |
| §14.5 Overlay selection and relationship resolution | Split | Keep normative: no global Overlay Head, no implicit selection, no cross-producer confidence comparability by default, unresolved targets stay unresolved. Provisional: re-anchoring conditions and binding-advance mechanics. |
| §14.6 Asset Metadata selection | Provisional | The invariant that descriptive metadata never affects policy or canonicalization already lives in §11.2 and §15.1 and stays normative there. The dedicated selection-event machinery here is mechanism; validate when metadata-dependent projections first exist. |
| §14.7 Tombstone, retraction, restoration | Split | Keep normative: deletion propagation semantics and the atomicity of whole-Asset deletion safety (obligation-adjacent). Provisional: the procedural detail of partial-deletion successor revisions and restoration lineage. |
| §15.1 Policy authority and normalization | Normative | Ceiling-and-intersection, deny-overrides-permit, Native Policy Asset handling, no audience flattening: one-way doors plus external obligations. The clearest "must be early" section in the document. |
| §15.2 Protected Observations and derived policy | Normative | Evidence-intersection for derived objects is a one-way door; retrofitting it after derived data exists means rebuilding all of it. |
| §15.3 Policy Decision Service and linearization | Split | Keep normative: authoritative PDS, fail closed, no session grants or leases, epochs advance on every closure. Provisional: batch/stream semantics, cache-commit rules, and replica behavior — validate against the first serving implementation. |
| §15.4 Deletion and erasure operations | Normative | Legal obligation. The operation distinctions (Tombstone ≠ erasure, hold, purge, non-sensitive record) and the purge-set completeness definition are exactly what cannot be bolted on later. |
| §16.1 Projection Types, legality, ownership | Normative | The accountability model (Ontology Steward, Knowledge Publisher, owner split) answers the consumer-coupling problem; ownership retrofits are organizational one-way doors. The custom-materializer authorization shape is already explicitly deferred — keep that deferral. |
| §16.2 Complete Materialization Input Manifest | Normative | "Nothing outside the manifest influences output" is the foundation of rebuildability; the field list derives from it. |
| §16.3 Definition versions and dependency transitions | Split | Keep normative: adoption mints immutable versions, publishing a dependency is not adoption, the categorical comparability-affecting list. Provisional: reverse-dependency impact computation and attested-reuse mechanics. |
| §16.4 Publication fencing | Split | Keep normative: no late publication across any eligibility-closing event. Provisional: fence procedure detail. |
| §16.5 Published View identity and composition | Split | Keep normative: immutable versions, Aggregate Manifest composition, supersede-not-overwrite. Provisional: shard-placement rules for inferred multi-Asset units. |
| §16.6 Rebuildability and Rebuild Verification | Split | Keep normative: the §9.3 obligation — exact reproducibility while the closure is lawfully retained, and purge ends the obligation. Provisional: the entire Rebuild Verification workflow (purpose binding, erasure fencing of in-flight verification, verification-copy purge rules). This is the deepest speculative machinery in the document and has no near-term consumer; validate when a rebuild capability is first built. |
| §16.7 Publication Policy, Carry-Forward, Rollback | Split | Keep normative: staleness fails closed by default; rollback cannot resurrect closed eligibility. Provisional: Carry-Forward composition mechanics. |
| §16.8 Two-axis Coverage Report | Split | Keep normative: Axis 1 — every input accounted as covered, excluded-for-registered-reason, or unrepresentable; unaccounted input blocks publication (this is §9.5). Provisional: Axis 2 — the Structural Property taxonomy, standard profile table, preserve-witness rules, and absorption rules. Axis 2 is a genuinely novel gate that should be shaped by the first Retrieval and Graph materializers, not frozen before them. |
| §17.1 Retrieval | Normative | Nearest-term interface; the first tracer bullet exercises it end to end. |
| §17.2 Graph | Split | Keep normative: no shared identity space, no Foundation same-as, Evidence Overlap as the only cross-view join, no evidence-free nodes (identity-space prohibitions are one-way doors — cross-view identity can never be removed once consumers depend on it). Provisional: Identity Minting Rule determinism mechanics — validate with the first Graph Projection Definition. |
| §17.3 Wiki | Normative | Thin already; bundle-as-one-unit follows from §15.2. |
| §18 Access boundaries and observable semantics | Normative | The External Consumer contract boundary and Governed Canonical Read role list; consumer-facing promises must be stable. |

### Part IV — Acceptance and endorsement (§19–§24)

| Section | Verdict | Rationale |
|---|---|---|
| §19–§23 Gates and walkthroughs | Normative | Keep, with one adjustment: gate criteria that quote provisional sections should verify the *invariant*, not the provisional mechanism. |
| §24 Review Record and re-review | Normative, amend | Add: a change confined to provisional mechanism contracts or registry seed data does not trigger re-review; promotion of a provisional section to normative does. |

## 5. What this changes in practice

1. **Endorsement gets cheaper and more honest.** Reviewers endorse invariants
   they can actually verify from architecture reasoning, instead of implicitly
   endorsing mechanism they cannot evaluate without an implementation.
2. **Iteration stops fighting §24.** Today, correcting any frozen mechanism
   detail is a candidate re-review. Under the tier, mechanism corrections are
   ordinary engineering, and only invariant changes re-open review.
3. **The first tracer bullet becomes the validation event.** A Retrieval path
   end to end (Source Integration → Canonicalization → Canonical Knowledge →
   Retrieval Projection Definition → Published View → governed query) exercises
   §11, §13, §14.2–14.4, §15.3, §16.2, §16.4, §16.8 Axis 1, and §17.1 — after
   which each provisional section is promoted or revised from evidence.

## 6. Suggested next steps

1. Discuss and settle each verdict above (the Split rows deserve the most
   attention — the invariant/mechanism cut line inside each is a judgment
   call).
2. Amend Baseline §2 (third authority level) and §24 (re-review trigger), and
   tag each affected section with its tier.
3. Move §12.2 and §12.3 into governed registry seed documents.
4. Re-cut the review candidate commit. Note: amending §2 and §24 is itself a
   normative change, so it must land **before** endorsement — which is exactly
   why now, while the Review Record on issue #29 is still open, is the cheapest
   possible moment to make this adjustment.
