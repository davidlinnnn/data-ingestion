# Q04 current acceptance matrix

Acceptance rows current through AU execution; AO, AP, AQ, AR and AT stop evidence independently verified. Machine authority:
`evidence/current-acceptance-matrix.json`. A proven row applies only to its exact
producer, profile, runtime and acceptance policy. Historical evidence cannot
silently qualify a changed execution path.

## Fixture delivery

| Fixture | Scope | Fresh | Restored | Exact replay | Full graph/oracle | Q04 fresh index |
| --- | ---: | --- | --- | --- | --- | --- |
| native | 51 pages | **proven** | **proven** | **proven** | **proven** | **proven** |
| WikiSkill `06` | 28 pages | **proven** | **proven** | **proven** | **proven** | **proven** |
| YOLO `07` | 15 pages, M policy | **proven** | **proven** | **proven** | **proven** | **proven** |
| AIMA `08` | original 99–110 | **proven** | **proven** | **proven** | **proven** | **proven** |
| ACL `09` | original 2–4 | **proven** | **proven** | **proven** | **proven** | **proven** |
| Keynote `10` | one page | **proven** | **proven** | **proven** | **proven** | **proven** |

AI passed Wiki06 and native fresh/restored/exact replay with 28/51 pages,
the strict v3 source-reviewed graph oracle, and document bytes equal to AH's
warm outputs. All 1,217 process/cgroup samples and terminal cleanup passed.
See [AI results](pod-topology-v34/first-window-evidence/RESULTS.md).

AJ passed current-v3 YOLO07, AIMA08, ACL09 and Keynote10 fresh/restored/exact
replay with full registered-page counts and exact frozen graphs. 07/08 documents
equaled AH warm output. All 772 process/cgroup samples and terminal cleanup
passed. See [AJ results](pod-topology-v35/first-window-evidence/RESULTS.md).

AK passed old native request rejection under a changed current-v3 profile,
followed by exact replay on the original route. The expected business failure
had `worker_method_mismatch`, zero registered pages and no processing result;
the original replay completed 51/51 pages. All 725 process/cgroup samples and
terminal cleanup passed. See [AK results](pod-topology-v36/first-window-evidence/RESULTS.md).

AL passed current-v3 native evidence-only new-request reuse: all 12 checked
group/assembly identities reused, seven OCR components reran, and new
processing/content-evidence identities retained the same exact output. All
849 process/cgroup samples and terminal cleanup passed. See
[AL results](pod-topology-v37/first-window-evidence/RESULTS.md).

AM stopped on a harness worker/parser method mismatch after native fresh; its
method-off request registered zero pages. AN used a new identity and an explicit
worker generation boundary. Native method-off then completed 51 pages with 12
new, disjoint group/assembly operations and the frozen method-off graph; exact
original-route replay retained the original processing result. All 1,128
process/cgroup samples and terminal cleanup passed. See
[AN results](pod-topology-v39/first-window-evidence/RESULTS.md).

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
sequence and recycle; AH later proved complete all-sample process attribution.
AJ now proves current-v3 fresh-output equality for AIMA. See
[Q results](pod-topology-v16/first-window-evidence/RESULTS.md).

ACL and Keynote retain their passes under their original producer/runtime
identities. AJ additionally proves applicability to the current v3 producer.
Q03 AIMA source/oracle evidence remains a historical reference; current lifecycle
execution, reuse and interruption behavior require requalification.

## Cross-cutting gates

| Gate | Current status | Boundary |
| --- | --- | --- |
| Immutable source/producer/profile/method/oracle binding | proven | Exact retained run identities |
| Stage-impact dependency projection | proven | Existing local audit; new producer changes need their own impact record |
| Six-fixture current-producer matrix | **proven** | AI proves native/Wiki; AJ proves 07–10 with current-v3 fresh/restored/exact replay and frozen graphs |
| Current AIMA continuation/four algorithms | **proven** | Q exact producer/runtime; four algorithms and eight continuation edges |
| Current evidence-only compatible reuse | **proven** | AL new native request reused 12 checked upstream operations, reran OCR and created new downstream identities |
| Real assembly/method invalidation | **proven** | AN new native method release invalidated all 12 checked group/assembly operations; method-off graph and original replay passed |
| Old request original route | proven | ACL window c re-read retained Keynote binding |
| Changed profile rejects old request | **proven** | AK changed profile rejected the exact old request; original-route replay retained its result |
| Current required-relationship interruption/retry/replay | **proven** | AS current native first-page evidence-child interruption, failed-plan publication, replacement worker recovery and exact replay; original producer/bundle, unchanged guards |
| Fixed warm sequence and request20 recycle | **proven** | AH proves sequence/recycle/resources; AI and AJ prove exact fresh-output equality for all four AH warm fixtures |
| Original ACL/Keynote bounded process resources | proven | Exact small-fixture producer/runtime only |
| Integrated operating bounds | **proven** | AH 1,349, AI 1,217 and AJ 772 complete v3 process/cgroup samples under unchanged guards, no resource stop |
| Active telemetry-loss guard | **proven** | AU stopped worker sampling at five registered native pages during active parsing; stale-sample guard canceled owned work, no complete registration, all-sample resources and cleanup passed |
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
- AI: one controlled current-v3 Wiki06/native matrix completed all six
  fresh/restored/exact replay trials. Each document matched AH warm bytes,
  with 28/51 registered pages, no failed Activity events, 1,217 complete
  process/cgroup samples and zero PSI/OOM/memory violations. The 102-entry
  terminal inventory passed independent hash/readback; workload exit and
  cleanup passed, AI PVC remains Bound, and the 32 held Deployments remain
  exact/off. See [AI results](pod-topology-v34/first-window-evidence/RESULTS.md).
- AJ: one controlled current-v3 07–10 matrix completed all twelve
  fresh/restored/exact replay trials. 07/08 documents matched AH warm output;
  09/10 matched the frozen complete-graph oracle. All 772 process/cgroup
  samples and unchanged guards passed. The 180-entry terminal inventory passed
  independent exact-set/hash/readback; owned runtime was removed, AJ PVC remains
  Bound, and all 32 held Deployments remain exact/off. See
  [AJ results](pod-topology-v35/first-window-evidence/RESULTS.md).
- AK: one controlled native fresh/changed-profile old-request/original replay
  sequence passed. The expected negative business result had one non-retryable
  failed Activity, `worker_method_mismatch`, zero registered pages and no
  processing result; original replay remained complete and byte-identical.
  All 725 process/cgroup samples, 61 terminal inventory entries and cleanup
  passed; AK PVC remains Bound and the 32 held Deployments remain exact/off.
  See [AK results](pod-topology-v36/first-window-evidence/RESULTS.md).
- AL: one controlled native fresh/evidence-only new request/original replay
  sequence passed. All 12 checked upstream operations reused for the new
  request, seven OCR components reran, and new processing/evidence identities
  retained the exact document and graph. All 849 process/cgroup samples,
  66 terminal inventory entries and cleanup passed; AL PVC remains Bound and
  all 32 held Deployments remain exact/off. See
  [AL results](pod-topology-v37/first-window-evidence/RESULTS.md).
- AM: one controlled method-off attempt stopped at its first invalidation
  group Activity with `worker_method_mismatch` because the harness retained
  the fresh warm parser. No method-off pages or replay were accepted; the
  terminal failure inventory and Bound PVC were retained. See
  [AM results](pod-topology-v38/first-window-evidence/RESULTS.md).
- AN: one new controlled native fresh/method-off/original replay sequence
  passed. Fresh and method-off each registered 51 pages in separate worker
  generations; the latter created 12 new disjoint group/assembly operations
  and matched the frozen method-off graph. Replay retained the original
  document and processing result. All 1,128 process/cgroup samples, 72
  terminal inventory hashes and cleanup passed; AN PVC remains Bound and
  all 32 held Deployments remain exact/off. See
  [AN results](pod-topology-v39/first-window-evidence/RESULTS.md).
- AO: all 11 pre-inference gates and fresh native (51 pages/seven OCR
  components) passed, but the next request stopped on a retained node PSI
  `full avg10=1.08` sample against the unchanged zero limit during its first
  parsing Activity. The interruption hook, recovery and replay were not
  reached. Temporal completed only with a failed business result after
  controller cancellation; failed-plan publication was absent. The 50-file
  terminal inventory, owned cleanup, retained Bound PVC and 32 exact/off held
  Deployments were independently checked. See
  [AO results](pod-topology-v40/first-window-evidence/RESULTS.md).
- AP: all 11 pre-inference gates passed, but unchanged node PSI stopped before
  any workflow or inference. The retained trigger read `full avg10=0.18`;
  a continuous external probe measured 20,218 microseconds of node full
  stall but none in its 68 visible cgroups near the stop. Pressure origin
  remains unknown. The 26-file terminal inventory, owned cleanup, retained
  Bound PVC and 32 exact/off held Deployments were independently checked.
  No relationship acceptance row passed. See
  [AP results](pod-topology-v41/first-window-evidence/RESULTS.md).
- AQ: all 11 pre-inference gates and fresh native (51 pages/seven OCR
  components) passed. During interrupted native, unchanged node/Pod PSI
  `full avg10=0.18` stopped the run after 51 pages and two components;
  the required child hook, recovery and replay were not reached. The new
  host-cgroup observer matched the dominant stall increments to AQ's own
  Pod/container path, while the precise process/allocator cause remains
  unknown. Temporal completed only with a failed business result after
  cancellation; no Activity failure event occurred. Its 1,269 continuous
  host samples, 50-file terminal inventory, owned cleanup, retained Bound
  PVC and 32 exact/off held Deployments were independently checked. No
  relationship acceptance row passed. See
  [AQ results](pod-topology-v42/first-window-evidence/RESULTS.md).
- AR: the diagnostic projected OCR source disagreed with the frozen input
  bundle producer map. Configuration failed before inference, workflow or
  object write. The new identity was consumed; owned runtime was removed,
  observer stopped and PVC retained Bound. See
  [AR results](pod-topology-v43/first-window-evidence/RESULTS.md).
- AS: one controlled native fresh/required evidence-child interruption/
  recovery/exact replay window passed with the original AH producer and
  bundle. The intended child was killed at `first_page_decoded`; the one
  failed Activity and incomplete business result were expected, failed-plan
  publication passed, and replacement worker recovery/replay each completed
  51 pages and seven OCR components with frozen document and graph digests.
  All 895 process/cgroup resource samples, 95 terminal inventory hashes,
  host observer and cleanup passed; AS PVC remains Bound and the 32 held
  Deployments remain exact/off. The optional OCR phase trace did not load
  because workload setup reset `PYTHONPATH`; AQ's precise stall phase remains
  unknown. See [AS results](pod-topology-v44/first-window-evidence/RESULTS.md).
- AT: active sampler-loss injection and owned cleanup occurred at five
  registered native pages, but the verifier rejected Temporal `COMPLETED`
  without decoding its failed business result. It exited nonzero before
  terminal qualification; raw failure export and PVC remain retained. See
  [AT results](pod-topology-v45/first-window-evidence/RESULTS.md).
- AU: one new controlled active telemetry-loss window passed. The worker
  sampler stopped while the next group parsed; the controller detected stale
  samples and canceled owned work. Temporal `COMPLETED` carried a failed
  business result (`activity_budget_exhausted`, 5/51 pages,
  `processing_complete=false`), and publication audit found no complete
  registration. Independent cancellation attribution, all 323 process/cgroup
  samples, 42 terminal inventory hashes, host observer and cleanup passed.
  AU PVC remains Bound and the 32 held Deployments remain exact/off. See
  [AU results](pod-topology-v46/first-window-evidence/RESULTS.md).

All historical failures, raw evidence, PVCs and prefixes remain retained. Q's
82 sealed inventory entries / 83 archive files passed independent verification;
owned runtime is removed, Temporal idle and all 32 held Deployments still off.
See [M results](pod-topology-v12/first-window-evidence/RESULTS.md),
[N results](pod-topology-v13/first-window-evidence/RESULTS.md) and retained A–L
records under `sentinel/` and `pod-topology-v*/`.

## Next execution

AS proves the required relationship interruption/recovery/replay gate; AU
proves active telemetry-loss fail-closed. Next are actual process and Pod
drain/recovery and the supported operating-bounds handoff to #44.
AQ's node/Pod pressure origin was localized, but its process/allocator cause
remains unknown because AS's optional phase hook did not load. Do not infer a
false guard trigger, increase memory or relax the zero limit. Correct the
descendant trace path and review any future diagnostic separately.
Each runtime needs a fresh
identity/prefix, unchanged guards, one controlled execution and no automatic
retry. #51 is not ready for integration or closure; ticket updates remain
unpublished drafts.
