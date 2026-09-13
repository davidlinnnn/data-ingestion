# Predeclared phased rollout scenario

The earlier 14-Pod trials are unqualified after transport stalls. This replacement
scenario preserves explicit versioned Workflow and six Activity queues per release.
It qualifies the following bounded coexistence pattern, not simultaneous polling
by every stage of both releases or a production capacity limit.

1. Retain both immutable release manifests, images, package/profile ConfigMaps and
   models. Fence all submissions except this controller's named cases. Reconcile
   abandoned exploratory executions explicitly; their outcomes are not acceptance.
2. Submit v1-release queued work with no workers. Prove the Workflow is queued.
   Start only its Workflow/preflight workers, prove group work is scheduled and
   unstarted on its exact v1 group queue, then start its remaining workers. Require
   v3 complete and checked source/result attribution.
3. Submit a new accepted v1 request, pause its actual active native child inside
   the observation probe, start the v2 Workflow population, and lose the v1 group
   Pod plus replace the v1 Workflow Pod. The v1 group replacement uses the exact
   old release. Require a later Activity attempt and v3 complete. Both Workflow
   populations coexist while accepted old work recovers.
4. With both Workflow populations retained, submit old-release work and gracefully
   delete its Pod after pausing the actual active native child. Require bounded
   Pod/container retirement and eventual later-attempt completion on the old route.
5. Await every known Workflow result and inspect all open executions in isolated
   Temporal. Only with **zero open executions** and admission still fenced may the
   five non-OCR v1 Activity stages temporarily drain. No running/retrying Workflow
   history can then schedule them later. Their images/models/configurations remain
   retained; resets are not admitted while their workers are stopped.
6. Keep the real v1 OCR worker and both Workflow workers polling while all six v2
   Activity workers run. Submit the new-method request. Require exact v2 profile
   and OCR-scale/model attribution, reused original compatible parsing/assembly,
   new request-bound selection/OCR/evidence/final results and v3 complete. Snapshot
   the actual old/new polling Pod populations.
7. Again await all results and require zero open executions. Drain only the five
   non-OCR v2 stages; keep its OCR worker and both Workflow workers. Restore every
   required v1 stage **before** accepting the mixed-population old-method request.
   Require correct old-route completion with actual new OCR workers present.
8. After every accepted request has finished, retain both prepare workers for the
   negative matrix: malformed/missing/inconsistent routes, unavailable release,
   and an accepted request ID presented under the other method. No latest fallback.
9. Check original registered artifact bytes, compare cross-release identities,
   record complete histories/attribution and require zero open executions. Then
   drain all owned workers under the shared host flock. Cleanup retries API/runtime
   errors while holding the lock; force-deleted container IDs remain tracked until
   runtime absence is observed. Coordinator hosts clients only.

During phases 6 and 7 the mixed Activity populations are real independently deployed
OCR workers from both releases. Each release executes its required OCR with the
other release's worker polling concurrently. This does not claim simultaneous
inference from both releases, concurrency calibration, or all 14 Pods at once.
Every separately deployed stage still executes through its explicit release queue;
there is no architecture switch to SDK Worker Versioning or a latest-worker queue.

The temporary stage absences are safe only under the controlled zero-open-execution
and admission/reset fence above. An empty queue, idle Activity or successful rollout
command alone would not establish that safety. Production retirement must apply the
broader checks in the deployment runbook and retain images/models for the supported
replay/reset window. T08 does not retire shared object-store artifacts.
