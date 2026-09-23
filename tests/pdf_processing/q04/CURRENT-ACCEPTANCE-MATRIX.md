# Q04 current acceptance matrix

Current through AH execution and independent terminal verification; machine authority:
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
29-group cross-document request20 sequence. Later warm runs completed that
sequence and recycle, but complete all-sample process attribution and
fresh-output equality remain unproven. See
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
| Fixed warm sequence and request20 recycle | unproven | AH proves the sequence, recycle, exact v3 warm graphs and resources; required cross-mode fresh-output equality remains pending |
| Original ACL/Keynote bounded process resources | proven | Exact small-fixture producer/runtime only |
| Integrated operating bounds | **proven** | AH v3 producer/runtime: 1,349 complete process/cgroup samples, unchanged guards, no resource stop |
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
- AA: all 11 pre-inference gates and all five Temporal workflows completed the
  29-group sequence and request-20 recycle. One of 1,307 samples retained the
  higher first cgroup reading when a fresh child exited; its complete retry and
  adjacent complete sample prove the exact exit, but the classifier lacked this
  shape. PSI, OOM, memory-floor and deadline guards did not fire. See
  [AA results](pod-topology-v26/first-window-evidence/RESULTS.md).
- AB: all 11 pre-inference gates and all five Temporal workflows completed the
  29-group sequence and request-20 recycle. Its sole raw incomplete sample was
  safely classified as an exact confirmed exit, and no unclassified cgroup
  transition remained. The exited child's PSS is still unknown, so the adopted
  complete-process-attribution gate correctly failed after business completion.
  PSI, OOM, memory-floor and deadline guards did not fire. See
  [AB results](pod-topology-v27/first-window-evidence/RESULTS.md).
- AC: deepest-owned-first sampling was exercised once; that single result does
  not prove it eliminated AB's race. All 11 pre-inference gates, all five
  workflows, the 29-group sequence, request-20 recycle, cgroup qualification,
  and peak process attribution passed. During
  controlled terminal cleanup, worker PID 111 exited while sample 1399 read
  its process files. The exact exit is classified, but its PSS is unknown, so
  the unchanged all-sample process-attribution gate failed. No PSI, OOM,
  memory-floor, deadline, Activity, supervisor, or ingestion failure occurred.
  See [AC results](pod-topology-v28/first-window-evidence/RESULTS.md).
- AD: the terminal synchronization succeeded within the unchanged attribution
  gap and eliminated AC's terminal worker race. All business, recycle, peak,
  cgroup, and cleanup evidence passed, but three fresh-child exits and the
  request-20 warm-parser recycle overlapped process snapshots. Their PSS remains unknown, so the all-sample
  process-attribution gate correctly failed. See
  [AD results](pod-topology-v29/first-window-evidence/RESULTS.md).
- AE: ten of 11 pre-inference gates passed, but a generated acceptance adapter
  misspelled the authorized capacity key. No workload started; cleanup passed.
  See [AE results](pod-topology-v30/first-window-evidence/RESULTS.md).
- AF: all 11 pre-inference gates and all five workflows completed the 29-group
  sequence and request-20 recycle. One of 1,420 samples overlapped the birth of
  a fresh child because the lifecycle lock covered exit/reap but not creation.
  Its exact PSS is unknown, so the unchanged all-sample attribution gate failed.
  No PSI, OOM, memory-floor, deadline, Activity, supervisor, or ingestion
  failure occurred. See
  [AF results](pod-topology-v31/first-window-evidence/RESULTS.md).
- AG: all 11 pre-inference gates, all five workflows, the 29-group sequence,
  request-20 recycle, all 1,425 process/cgroup samples, unchanged resource
  guards, terminal evidence and cleanup passed. Its reviewed contract retains
  required Q04 fresh-output equality as pending, so the complete warm row is
  not promoted. The raw cleanup field
  `terminal_stop_proven=false` means the controller did not initiate a stop
  after natural success; exit code zero, `cleanup-complete.json`, the terminal
  manifest and absent owned runtime prove terminal cleanup. See
  [AG results](pod-topology-v32/first-window-evidence/RESULTS.md).
- AH: all 11 pre-inference gates and five v3-bound Temporal workflows passed.
  Wiki06 (twice), YOLO07, AIMA08 and native matched their frozen exact graph
  digests; native registered 51 pages. The 29-group sequence, request-20
  recycle, and all 1,349 process/cgroup samples passed unchanged guards.
  The 93-entry terminal inventory passed independent hash/readback checks;
  workload exit was zero, owned Pod/Deployment/ConfigMaps were removed, the
  evidence PVC remains Bound, and all 32 held Deployments remain exact/off.
  Required standalone fresh-output equality, restored and replay modes remain
  unproven, so the complete warm row is still not promoted. See
  [AH results](pod-topology-v33/first-window-evidence/RESULTS.md).

All historical failures, raw evidence, PVCs and prefixes remain retained. Q's
82 sealed inventory entries / 83 archive files passed independent verification;
owned runtime is removed, Temporal idle and all 32 held Deployments still off.
See [M results](pod-topology-v12/first-window-evidence/RESULTS.md),
[N results](pod-topology-v13/first-window-evidence/RESULTS.md) and retained A–L
records under `sentinel/` and `pod-topology-v*/`.

## Next execution

AH extends the integrated-resource, sequence and recycle proof to the exact
v3 continuation producer and adds strict native/Wiki06 graph acceptance in a
real warm workflow. Required standalone fresh-output equality still blocks the
complete warm row. The next runtime work is the v3 fresh/restored/exact-replay
matrix, including fresh-output comparison with AH before moving to the
separately specified current process interruption/retry/replay gate. Native/Wiki06 fixture acceptance,
changed-profile rejection, Pod interruption/recovery and telemetry-loss
injection also remain open. Any next runtime must use a new identity, retain
the unchanged guards and run once without automatic retry.

The retained AG documents now have a strict no-inference comparison record:
Wiki06 changes from 490 to 496 text nodes and native from 1,119 to 1,145, while
their source-region multisets remain equal. This is a graph/assembly difference,
not a missing-source finding. Re-running the same current producer before a
source review would deterministically stop at the same Q04 graph gate and would
not advance acceptance.

The AG native source review rejected that v1 graph: five of its six
many-to-many components joined text across intervening PDF columns; the remaining
component was a duplicate picture label. The other native and Wiki06 splits
were pending review at that point. Later replay of the pre-merge elements
isolated the six invalid v1 edges. No general split/merge normalization is
accepted. See
[AG source-review result](pod-topology-v32/first-window-evidence/SOURCE-REVIEW-RESULT.md).

A versioned v2 continuation candidate blocked those six invalid native joins.
Offline full-document captures retained exact source fragments; native had
32 ordered one-to-two text splits and Wiki06 six. All 38 splits and their
graph bindings were source-reviewed, and a fixture-specific exact graph
oracle was frozen with fail-closed mutation checks. Six-fixture offline
projection then found v2 incorrectly split a valid AIMA continuation across a
narrow page-margin picture. V3 restores that AIMA join and produces the same
native/Wiki06/YOLO document bytes as the reviewed v2 or AG outputs; ACL and
Keynote full graphs equal their references. The v3 exact oracle is frozen for
native/Wiki06. No current-producer runtime row is promoted: fresh, restored,
exact replay and the affected warm sequence still need a new controlled
execution. See [v3 offline result](diagnosis/continuation-v3/OFFLINE-RESULT.md).

#51 is not ready for integration/closure. Ticket updates remain unpublished drafts.
