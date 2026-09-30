# Remaining process-cold coverage

Predeclared on 2026-09-30; not runtime evidence. Retain group 5, one active child,
all accepted sources/profiles/models, required component OCR and full-output
oracles. Existing normal-path three matched pairs already cover Wiki06 as the
first request. This slice adds only the missing first-request fixture cases.

## Controlled cells

| Cell | Fixture order | Fresh workers | Parse groups |
| --- | --- | ---: | ---: |
| PC1 | YOLO07, AIMA08, native51 | 3 | 17 |
| PC2 | native51, YOLO07, AIMA08 | 3 | 17 |
| PC3 | AIMA08, native51, YOLO07 | 3 | 17 |

Stop the preceding worker with verified parser/scratch cleanup before starting
its successor. Each worker receives one business workflow; fresh request IDs and
cell-specific prefixes prevent complete-output reuse. Each fixture therefore
has n=3 process-cold observations, with rotated order to expose order effects.
No host/page-cache flush; report cache conditions as uncontrolled. Report median
and range only, never p95, an SLA or fully cold storage/model conditions.

Each cell is independently admitted under existing cluster/namespace, resource,
OOM/floor/PSI and runtime deadlines. No deadline increase. PC2/PC3 are planned
successful replicates, not retries. Any failure stops the batch for diagnosis;
no automatic retry. Preserve historical prefixes/PVCs. Declare and restore the
same 32-Deployment window used by the retained controller.

## Reuse and necessary local checks

Reuse baseline_window/PolicyRun, attributed collector, T09b Host, worker storage
instrumentation, existing preflight/projection, remote mirror and outer controller.
The coordinator must explicitly compose AttributedCandidateRun with PolicyRun;
do not assume rebinding q04_runtime.Run changes an already-defined parent class.

Only adapt sequence, serial worker transitions and evidence expectations: 17
groups, three worker/parser generations, no automatic recycle before each fresh
shutdown, three ledgers and stopped markers. Keep parser max_requests=20 as a
budget even though no individual process reaches it. Existing historical warm
runner and evidence remain unchanged. Do not reuse normal warm-proof semantics
that assert cross-request parser continuity.

Before PC1 admission, execute the actual rendered preflight imports/scope gate,
verify full argv and projected source, test serial stop/start order and failure
cancellation/cleanup, validate complete-output expectations for all three fixtures,
and reconcile all three worker ledgers. Review the final launch contract. A
passing --help/import-only test is insufficient (RA1 regression).

## Measurements and limits

Export per-request Temporal workflow/queue/activity timings including all 4/9/7
required OCR components (YOLO/AIMA/native), sampled whole-Pod peak, stage events,
all application reads/publications and scoped server HTTP traffic. Quiescent
inventory counts registered payload, total prefix and orphan attempts separately.
Compare with the existing warm observations while preserving attempt attribution.
Inclusive activity time is not exclusive parse/publication time; read-chunk and
publication-input maxima are not total retained/native buffering. These two gaps
need their own justified measurement, not an implied pass from this cold slice.

This plan does not resolve conditional concurrency or close #45. Final bounds
consolidation and that requirement remain explicit pending work.
