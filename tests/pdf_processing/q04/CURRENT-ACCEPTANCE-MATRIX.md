# Q04 current acceptance matrix

Current through Z execution `f83d1db`; machine authority:
`evidence/current-acceptance-matrix.json`. A proven row applies only to its exact
producer, profile, runtime and acceptance policy. Historical evidence cannot
silently qualify a changed execution path.

## Fixture delivery

| Fixture | Scope | Fresh | Restored | Exact replay | Full graph/oracle | Q04 fresh index |
| --- | ---: | --- | --- | --- | --- | --- |
| native | 51 pages | unproven | unproven | unproven | unproven | unproven |
| WikiSkill `06` | 28 pages | unproven | unproven | unproven | unproven | unproven |
| YOLO `07` | 15 pages, M policy | **proven** | **proven** | **proven** | **proven** | **proven** |
| AIMA `08` | original 99–110 | **proven** | **proven** | **proven** | **proven** | **proven** |
| ACL `09` | original 2–4 | **proven** | **proven** | **proven** | **proven** | **proven** |
| Keynote `10` | one page | **proven** | **proven** | **proven** | **proven** | **proven** |

YOLO M (`d1701d3`) passed all three modes with 15 pages and four required OCR
components, approved two-pair graph equivalence, `max_requests=1`, THP-disabled
workload descendants and 1,021 complete process samples. This is bounded fixture07
acceptance, not the original request20 cross-document warm qualification.

AIMA Q passed all three modes with 12 pages, nine OCR components, 615-item
oracle, four algorithms, eight continuation edges, adopted source-pixel image
supplements and equal full graph/document digests. Its 949 attribution samples
were complete, and three captures plus native assembly restore used one warm
parser PID. This is bounded fixture08 acceptance; it does not prove the original
29-group cross-document request20 sequence. See
[Q results](pod-topology-v16/first-window-evidence/RESULTS.md).

ACL and Keynote retain their passes under their original producer/runtime
identities. Applicability to the current lifecycle producer is **unproven**.
Q03 AIMA source/oracle evidence remains a historical reference; current lifecycle
execution, reuse and interruption behavior require requalification.

## Cross-cutting gates

| Gate | Current status | Boundary |
| --- | --- | --- |
| Immutable source/producer/profile/method/oracle binding | proven | Exact retained run identities |
| Stage-impact dependency projection | proven | Existing local audit; new producer changes need their own impact record |
| Six-fixture current-producer matrix | unproven | Native/Wiki and ACL/Keynote lifecycle applicability remain open |
| Current AIMA continuation/four algorithms | **proven** | Q exact producer/runtime; four algorithms and eight continuation edges |
| Current evidence-only compatible reuse | unproven | Q03 proof belongs to its original execution path |
| Real assembly/method invalidation | unproven | Native runtime not run |
| Old request original route | proven | ACL window c re-read retained Keynote binding |
| Changed profile rejects old request | unproven | Local compatibility only |
| Current required-relationship interruption/retry/replay | unproven | Q03 historical owned-child proof, not current lifecycle/Pod recovery |
| Fixed warm sequence and request20 recycle | unproven | Q proves four AIMA requests on one parser; original 29-group sequence/recycle unrun |
| Original ACL/Keynote bounded process resources | proven | Exact small-fixture producer/runtime only |
| Integrated operating bounds | unproven | M proves fixture07 and Q proves fixture08; remaining fixtures and request20/drain are open |
| Active telemetry-loss guard | unproven | Q proves normal continuity; no injected sampler-loss abort ran |
| Process drain/recovery | unproven | Current runtime phase not run |
| Pod drain/recovery | unproven | UID-fenced terminal cleanup proven; in-flight Pod loss/recovery not run |
| Supported-bounds report to #44 | unproven | Depends on remaining rows |

## Stop-cause and evidence record

- H: dropped rejecting sample and `worker-1.log` cleanup crash repaired in I.
  Recovered history indicates PSI cancellation; true Activity budget exhaustion
  is not demonstrated. The exact original trigger row remains unavailable.
- I: scratch/durable transport classification failure; evidence recovered.
- J/K: business cases complete but process attribution incomplete. Root runc
  initializer reads were traced to repeated execs, including readiness probes.
- L: persistent observer lanes and startup-only probe made all 290 process
  samples complete; real node PSI then stopped fresh. Concurrent THP allocation
  and direct reclaim are observed, but THP causality is not proven.
- M: all three bounded fixture07 cases and unchanged resource gates passed.
- N: completed AIMA business result, then consumer graph rejection and incomplete
  measurement contract. No PSI/OOM/deadline trigger; no automatic retry.
- P: all three AIMA content cases completed, but one process membership transition
  left PSS unknown; final qualification correctly failed.
- Q: repaired warm continuity and exact before/after process observation passed
  all AIMA business, oracle, resource, telemetry and cleanup gates.
- R: outer admission passed, then an acceptance-harness early-bound P Deployment
  default rejected the correctly created R Deployment before scale-up. No Pod,
  workflow, Activity or inference started; R proves no acceptance row. See
  [R results](pod-topology-v17/first-window-evidence/RESULTS.md).
- S: outer admission, Deployment identity and Pod readiness passed. Pod-local
  pre-inference then failed because the projected workspace omitted the
  transitive `pod_preflight_q.py` engine. No workflow, Activity or inference
  started; S proves no acceptance row. See
  [S results](pod-topology-v18/first-window-evidence/RESULTS.md).
- T: all pre-inference gates passed and the first Wiki06 workflow completed
  28/28 pages and 21/21 Activities without PSI, OOM, memory-floor or deadline
  stop. The warm phase then stopped at the consumer's full-graph review gate,
  before the remaining sequence or request-20 recycle. This is a harness scope
  mismatch; no warm row passed. See
  [T results](pod-topology-v19/first-window-evidence/RESULTS.md).
- U: the complete 29-group sequence and request-20 recycle ran successfully, but
  one of 1,438 process samples lost a short-lived child during `/proc` identity
  enumeration. Its PSS is unknown, so complete process attribution and the
  combined warm/resource row remain unproven. No PSI, OOM, memory-floor or
  deadline stop occurred. See
  [U results](pod-topology-v20/first-window-evidence/RESULTS.md).
- V: all 11 pre-inference gates passed, then init rejected a stale bundle
  harness binding before workflow, Activity, parser or inference. Read-only PVC
  recovery sealed the exact failure and cleanup. V proves no acceptance row.
  See [V results](pod-topology-v21/first-window-evidence/RESULTS.md).
- W: all 11 pre-inference gates and all five Temporal workflows completed the
  29-group sequence and request-20 recycle. Three of 1,425 process samples
  remained unclassified because the sampler did not retry before/after
  process-set churn. PSI, OOM, memory-floor and deadline guards did not fire;
  the combined warm/resource row remains unproven. See
  [W results](pod-topology-v22/first-window-evidence/RESULTS.md).
- X: all 11 pre-inference gates and all five Temporal workflows completed the
  29-group sequence and request-20 recycle. One of 1,466 samples lost a child
  during `/proc` reading. The exit was bounded for cgroup qualification, but the
  sampler omitted `cgroup_process_read_incomplete` from its safe transient retry
  allowlist, so exact process attribution failed. PSI, OOM, memory-floor and
  deadline guards did not fire. See
  [X results](pod-topology-v23/first-window-evidence/RESULTS.md).
- Y: all 11 pre-inference gates and all five Temporal workflows completed the
  29-group sequence and request-20 recycle. Five process exits were classified;
  two more exact exits remained unclassified because the compact collector
  summary omitted the retained failed-resample observations. PSI, OOM,
  memory-floor and deadline guards did not fire. See
  [Y results](pod-topology-v24/first-window-evidence/RESULTS.md).
- Z: ten of 11 pre-inference gates passed. `workload_imports` rejected a runtime
  manifest whose inner measurement scope was incorrectly bound to the outer
  runner authorization digest. No workflow, Activity, inference or object write
  started. Cleanup passed and the retained PVC is Bound. See
  [Z results](pod-topology-v25/first-window-evidence/RESULTS.md).

All historical failures, raw evidence, PVCs and prefixes remain retained. Q's
82 sealed inventory entries / 83 archive files passed independent verification;
owned runtime is removed, Temporal idle and all 32 held Deployments still off.
See [M results](pod-topology-v12/first-window-evidence/RESULTS.md),
[N results](pod-topology-v13/first-window-evidence/RESULTS.md) and retained A–L
records under `sentinel/` and `pod-topology-v*/`.

## Next execution

Z did not start the workload because its runtime manifest used the outer runner
digest for the narrower inner measurement scope. AA binds that scope to its
canonical digest and exercises the exact projected `workload_imports` gate in a
regression test. The failed-resample classifier, thresholds and the
one-run/no-automatic-retry policy remain unchanged. AA uses a new run identity,
prefix and PVC.

#51 is not ready for integration/closure. Ticket updates remain unpublished drafts.
