# Knowledge Platform design checkpoint

[Documentation guide](../README.md)

The current [wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52)
started with source-to-publication system design. The user confirmed the overall
logical decision on 2026-09-28 after Q1–Q25 and independent spike incorporation.

- [Logical system design](knowledge-platform-logical-design.md): confirmed
  responsibilities, Corpus and revision behavior, workflows and detailed owners.
- [Overall design review](knowledge-platform-overall-review.md): contract outlines,
  failure walkthroughs, persistence alternatives and follow-through checkpoints.
- [Independent spike](../reviews/knowledge-platform-overall-spike-2026-09-28.md):
  the reviewed historical snapshot, clarifications and subsequent confirmation.

- [Canonical representation and acceptance](knowledge-platform-canonical-design.md):
  Q1–Q9 confirm acceptance, source/projection responsibilities, evidence precision,
  parser-output disposition, accepted-revision immutability, rule-based selection
  and post-acceptance invalidation. Q10–Q11 establish new Canonical Revisions for
  adopted Enrichment and automatic reprocessing after scoped platform method adoption.
  Q12–Q13 confirm attachment-change reuse and historical acceptance versus source-target
  applicability. Q14 adds shared-Corpus knowledge organization and interlinking to
  the three-format cases. Revised Q14 uses conceptual consumer walkthroughs here;
  executable checks address only decision-critical Canonical unknowns. Wiki/Retrieval
  implementation and effectiveness validation belong to Projection. Q15 fixes
  references to locations within exact revisions without promising automatic
  cross-revision component matching. Q16 preserves necessary structure while allowing
  validated, traceable textual Enrichment for diagram meaning; a structured flow model
  is not universally required. Q17 treats changed-content source support as an
  existing acceptance check: whole-document reprocessing is permitted, compatible
  artifact reuse remains optional, and no separate locator-migration mechanism is
  required. Q18 stops acceptance when an effective withdrawal already covers the
  candidate; late processing success cannot create a new accepted result, and later
  authorization restoration requires reevaluation. Q19's multiple exchange-format
  proposal is withdrawn: define one schema with version identification first, and
  address future schema migration only for a concrete change. The complete logical
  contract and validation plan received [final confirmation](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6096650145)
  on 2026-10-10.

- [Canonical contract and three-format cases](knowledge-platform-canonical-contract-draft.md):
  confirmed first-version logical structure, illustrative three-format cases,
  PDF reconciliation, capability boundaries and research-disposition tables. Q23 confirms
  capability boundaries and conditional requirements, keeping method/profile selection
  with Processing and product adoption with Projection. Integration/validation
  handoff completeness was confirmed on 2026-10-10; native dependencies are unchanged.
  Q20 confirms distinct in-document attachment occurrences
  sharing one fixed package artifact. Q21 confirms the six information groups,
  exact-candidate validation/acceptance records and minimal duplication principles.
  Q22 confirms the three-format question/answer baselines for necessary meaning
  and Source Evidence. Q24 confirms redelivery, distinct reprocessing candidates and
  rule-based selection. The draft assembles lifecycle handoffs and V01–V11 mapping
  validation procedures; they are not runtime results. Q25 confirms revision-scoped
  references, source-appropriate locator/index conventions and necessary unknown/no-content
  distinctions. Three complete same-schema candidates, a populated provider-field
  disposition example and attachment/method updates passed final whole-contract
  review on 2026-10-10. The provider schema roundtrip passed; mapping and consumer
  runtime remain unrun. Formal wire encoding and implementation follow the remaining
  design inputs and specification handoffs.

[Historical ADR reconciliation](../reviews/knowledge-platform-historical-adr-reconciliation-2026-10-09.md)
records the inventory through Canonical Q25 and retrospective ADRs 0004–0006;
original decision dates and later recording dates remain distinct. The inventory
was included in the confirmed final review on 2026-10-10.

[Captured-source handoff](knowledge-platform-source-handoff.md) records the
confirmed Q1–Q14 decisions, including complete capture inputs, deployment-neutral
delivery, change-ordering/conflict principles, authorization trust, governance
acknowledgement meanings and package-scoped attachment identity. Initial global
shared-attachment management and automatic cross-document deduplication are excluded.
The source-facing decision was resolved on 2026-10-05 after the illustrative
PDF/Markdown/PPTX cases, owner handoff and independent spike. The incorporated
clarification covers attachment-only changes; admission/canonical design own the
old-capture/refreshed-precondition validation case. The [logical design](knowledge-platform-logical-design.md)
also carries the accepted unified lifecycle/status-query requirement; implementation
phasing is undecided. Concrete mechanisms, numeric freshness/retention targets,
storage selections and detailed APIs remain with their named owners. This checkpoint
records progress and does not constitute an implementation-ready spec.
Decision details remain in the linked issues; the map remains their index.

## Earlier direction and candidate history

The [HLD](../../HLD.md) and [Architecture Baseline](../../ARCHITECTURE-BASELINE.md)
provide the proposed direction package. Its [review brief](../reviews/architecture-direction-review.md)
retains pending outcomes; the [scope review memo](../reviews/hld-stage-scope-review.md)
explains why detailed mechanisms were removed from that review's commitments.

Earlier detailed contracts, rationale and rejected alternatives remain available
at the immutable [prior Baseline](https://github.com/davidlinnnn/data-ingestion/blob/babda22bfc0eeb06bed5a6af7d94717f648c5265/ARCHITECTURE-BASELINE.md),
[prior glossary](https://github.com/davidlinnnn/data-ingestion/blob/babda22bfc0eeb06bed5a6af7d94717f648c5265/CONTEXT.md),
and [seed registrations](https://github.com/davidlinnnn/data-ingestion/blob/babda22bfc0eeb06bed5a6af7d94717f648c5265/docs/registries/foundation-seed-registrations.md).
Their original normative wording applies to that historical candidate, not to
undecided mechanisms in this map. The root [CONTEXT.md](../../CONTEXT.md) is the
current glossary.
