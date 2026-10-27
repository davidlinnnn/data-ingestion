# Knowledge Platform design checkpoint

[Documentation guide](../README.md)

The current [wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52)
started with source-to-publication system design. The user confirmed the overall
logical decision on 2026-09-28 after Q1–Q25 and independent spike incorporation.
The map's standing charter, authority and working-method notes are in
[map notes](knowledge-platform-map-notes.md).

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

[First-adoption workload and operating envelope](knowledge-platform-first-adoption.md)
was confirmed on 2026-10-11 after Q1–Q22 and final validation/handoff review. It selects
a research-team paper pilot about AI agent self-evolution: manual controlled submission,
20 initial text-layer PDFs, two weeks and up to 50 active papers. The document preserves
the chosen arrival, freshness, concurrency, recovery and retention targets; background
ingestion is decoupled from online retrieval/fetch. The independent pilot has no existing
production data/traffic takeover or migration obligation. Pilot processing outages may
pause new admissions while protecting accepted work; production must support bounded,
durable task buffering when safe admission remains possible. V01–V08 define the approved
validation scenarios and observations. Required inventory, source-policy bindings, named
roles, resources/costs and runtime evidence remain explicit gated handoffs to the existing
design owners. Targets may be revised and revalidated for production; confirmed data and
governance contracts retain their authority. This is design confirmation, not measured
platform capability or implementation readiness.

[Knowledge Platform admission design notes](knowledge-platform-admission.md)
record the #31 admission decisions (rounds 1–5) and their reasons, including the
direct-upload direction and Valet Key principle. The
[admission specification](knowledge-platform-admission-spec.md) states the
current contract for implementers: API, admission rules, status, Source
Deletion, dispatch, limits and validation. Its rules are modelled in the
[admission rules prototype](https://github.com/davidlinnnn/data-ingestion/blob/prototype/31-admission-rules/docs/prototypes/admission-rules.prototype.html). The
storage product and grant mechanism remain open.

[PDF processing workflow v2](knowledge-platform-processing-workflow-v2.md)
records the #91 decisions (Q1–Q32): the stage graph, Activity and per-item
durability units, the two failure tiers, Enrichment Methods and their status
rule, the Processing Result handed to Canonical, admission integration and the
V1–V6 validation work. Inference call rules and capacity remain with #93.

[Authorization: decision interface, model and pilot provider](knowledge-platform-authorization.md)
records the #85 decisions (Q1–Q20): Resource-level relations with the document
binding held by the platform, the `check` and `list_resources` interface, the
pilot PostgreSQL provider with a post-MVP move to SpiceDB, the pilot Resource
Service API, credential issuance and the GAM requirements list for #86.

[Canonical consumption and publication](knowledge-platform-canonical-consumption.md)
records the #55 decisions (A–E, G1–G9, J1, K1–K2): the Change Feed, the inclusion
rule and readiness, rebind and cross-Source copies, Builds and commit-by-commit
publication, serving facts with registration before write, snapshot-then-stream
repair and the deletion predicate, with simulation evidence for each rule.

[Data-security governance](knowledge-platform-data-security.md) records the #87
decisions (rounds A–G): the company classification mapped with no classification
attribute in v1, on-prem-only processing egress with a registered egress list,
derived data as sensitive as its inputs, privileged access, encryption and
isolation principles, record/warn/gate detection modes, the P0→P1→P2 identity
path and the Agent Platform data obligations, and the manager-facing Platform
Security Baseline v1.

[Internal product strategy](knowledge-platform-internal-product-strategy.md)
records the confirmed 2026-10-17 internal product direction, owner handoffs and
company identity/authorization requirements (tSSO, GAM or GAM-compatible, data-owner
Resource management). Read it with the governance research it cites; it adds no
MVP gate and selects no provider.

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
