# T08 — PASS for the declared phased rollout gate

The internal captured-source → real Temporal/Kubernetes Activities → checked
shared storage seam passes for the predeclared [phased scenario](../SCENARIO.md).
This is not all-stage simultaneous population, resource-capacity, production HA,
PDF quality expansion or final packaging qualification. `canonical_accepted` stays
false. Both tested releases submit **request version 3**, including required OCR
and durable source evidence; release labels v1/v2 are not request schema versions.

| Acceptance requirement | Measured evidence |
|---|---|
| Frozen Workflow and every independently deployed Activity route | [Routes](routes.json) bind explicit Workflow/prepare/group/assembly/select/OCR/finalize queues, immutable image digest, full profile/producer/model/limit/store fingerprints. Required evidence remains inside finalize. All seven scheduled Activities per one-page/two-picture request use the exact declared stage queues in the result histories. |
| Genuine queued Workflow and Activity work | [Before workers](queued-before-workers.json) has an accepted queued Workflow and no scheduled Activities. [Before parser](queued-before-parser.json) proves group work scheduled and unstarted on the exact old queue. [Queued result](results/queued.json) completes under the old release with both required OCR outputs and source evidence. |
| Old in-flight work and replacement | [Loss controller](loss-controller.json) observes and pauses a real LayoutModel child, force-deletes only its Pod, verifies runtime container exit and replaces the old Workflow Pod. [Result](results/loss.json) completes parsing on **attempt 2**, using the frozen old queues/profile. The replacement Workflow Pod UID differs from the lost worker; its recorded history/run continues. |
| Graceful drain and retry | [Drain controller](drain-controller.json): paused active native child, **31.54 seconds** to old Pod disappearance, runtime container confirmed stopped. [Result](results/drain.json) completes on **group attempt 2**. Pod60/SDK30/TERM5/reap5 settings remain. Pod observation time is not an independent child-cleanup timestamp or SLA. |
| New method and compatible reuse | [New request](results/new.json) changes actual required OCR scale **3→4**, reuses the exact original group/assembly operations, executes two newly bound OCR outputs and registers distinct parsed/selection/evidence/final bindings. [Comparison](results/comparison.json) checks exact shared operations, disjoint request-bound enrichments and readable original artifact hashes. |
| Actual mixed compatible workers | Both Workflow workers and both independently deployed OCR workers coexist. Fresh Temporal poller identities match the **current Pod names/UIDs** on all four exact queues [before](results/new-before-pollers.json) and [after](results/new-after-pollers.json) the new-method request, and [before](results/mixed-before-pollers.json)/[after](results/mixed-after-pollers.json) the old-method request. [New population](new-method-population.json), [old population](old-method-population.json). Each method finishes while the other release's OCR worker polls. |
| Attribution and isolation | Results retain exact source digest/object version/revision, route ID, full resolved profile, package hashes, actual OCR model hashes, stage queues and attempt numbers. All source reads remain inside the frozen `t08/rollout/` scope. Checked original registrations remain readable; no T06/T07 input/registration was modified. |
| Explicit failures, no latest fallback | [Missing](results/missing.json), [malformed](results/malformed.json), [inconsistent route](results/inconsistent.json), [unavailable release](results/unavailable.json), and [accepted request ID under another method](results/conflict.json) fail explicitly. The unavailable release is rejected before submission. No SDK Worker Versioning alternative was introduced. |
| Safe phased drain and retirement | The controller awaits every known result and requires zero open executions before stopping a stage population; admission/reset is fenced during its absence. It restores required workers before later acceptance. Final checked comparison reports zero open executions. Cleanup retains the host flock through API errors until all owned Pods and tracked force-deleted containers are absent. Images/models/immutable configurations and shared artifacts remain retained. |
| Checks and review | [Full suite](full-suite.log): **10 tests pass**, including scanned fresh-process restoration; focused OCR/supervision suites pass. [Typecheck](typecheck.log): **0 errors/warnings**. Independent Standards and Spec reviews and correction rechecks have no outstanding findings: [review](../REVIEW.md). |

The exact pinned runtime OCI manifest is
`sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
Both releases intentionally use the same image/package/model bytes; the measured
new method is a real OCR configuration change. This does **not** qualify a separately
installed OCR/model/package upgrade. [Runtime](runtime.json) and [manifest](manifest.json)
bind source hashes, mounted immutable configurations, profiles and evidence files.

The successful first matrix remains in `rollout-results`; the two cached-method
cases were repeated with stronger before/after poller checks and are the final
new/mixed results. Native parsing was not repeated in that supplementary window.
[Excluded trial history](exploratory-history.json) and [exploratory notes](EXPLORATORY.md)
preserve initial red, timing-race, scheduling-stall and transport-interrupted trials.
Those are not passing resource or rollout measurements. Their existence does not
establish a sole transport-failure cause or a production population limit.

Only this one-page synthetic native fixture is newly qualified here. T06 typed
content/graph/furniture/PictureItem children, actual types/provenance/captions,
six ACL equations including TextItem eq2, region-specific uncertainty and AIMA
association/order limitations remain as previously bounded. No T09a evidence fix
was imported during this task. Main must reconcile that producer delta separately.
Pre-T07 checkpoints without checked sidecars are not automatically imported.

Qualification reservations (group256Mi/other64Mi, inherited 5Gi limits), one slot,
group size and processing budgets are provisional. #44/#45 own calibration and
#46 still consumes this ticket plus T09b. HTTP/NATS admission, public status DB,
canonical adoption, LaTeX and shared-artifact garbage collection remain outside scope.
