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

[Captured-source handoff](knowledge-platform-source-handoff.md) records the
confirmed Q1–Q13 decisions, including complete capture inputs, deployment-neutral
delivery, change-ordering/conflict principles, authorization trust and governance
acknowledgement meanings. Shared-attachment boundaries and the final source-facing
case review remain open. The [logical design](knowledge-platform-logical-design.md)
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
