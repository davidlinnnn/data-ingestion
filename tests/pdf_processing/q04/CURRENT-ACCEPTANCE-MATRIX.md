# Q04 current acceptance matrix

This snapshot reconciles issue #51 through the candidate batch executed from
M execution commit `d1701d3` (earlier rows retain their exact identities). The machine-readable
authority is `evidence/current-acceptance-matrix.json`. “Proven” means direct Q04
evidence for the exact bounded row. “Reusable” means earlier direct evidence can
be carried forward only while all stated identities and behavior remain equal.
“Unproven” includes rows with useful local or R3 support but no current runtime
acceptance.

## Fixture delivery

| Fixture | Scope | Fresh | Restored | Exact replay | Full graph/oracle | Q04 fresh index |
| --- | ---: | --- | --- | --- | --- | --- |
| native | 51 pages | unproven | unproven | unproven | unproven | unproven |
| WikiSkill `06` | 28 pages | unproven | unproven | unproven | unproven | unproven |
| YOLO `07` | 15 pages, M policy | **proven** | **proven** | **proven** | **proven** | **proven** |
| AIMA `08` | original 99–110 | unproven | unproven | unproven | unproven | unproven |
| ACL `09` | original 2–4 | **proven** | **proven** | **proven** | **proven** | **proven** |
| Keynote `10` | one page | **proven** | **proven** | **proven** | **proven** | **proven** |

ACL is the accepted Option A graph: 134 items, six reviewed equations, equation 2
as `TextItem`, two required OCR results and exact fresh/restored/replay graph
equality. Keynote covers 44 items, all 27 reviewed textboxes, one required OCR
result and exact graph equality. Their process-resource and cleanup observations
remain bounded to those fixtures.

YOLO matrix A, attribution B, and lifecycle A are retained failed attempts.
Lifecycle A completed all 15 fresh pages and four required OCR components, then
failed the fixed full-graph gate. Offline source review explains the complete
delta as two table-interrupted cross-page paragraphs that the attested
conservative continuation method preserves as two nodes each. Merging only
those two reviewed pairs makes all nine graph collections equal; table cells,
captions, links, and other content are unchanged. This is packaged as an
inactive, fixture-local source-reviewed equivalence candidate. Separately, the
complete 250 ms stream fails the unchanged 4 GiB gate at one group-3 warm-parser
sample. Neither candidate changes the runtime result. Restored and exact replay
did not run; no fresh-index entry was created. Cleanup passed with zero retry
and all 32 historical Deployments remaining closed.
Fresh/restored/replay/full-graph rows remain `unproven`.

AIMA's executable identity reconciliation confirms equal source bytes, 20-file
producer, method and relationship semantics. It also finds a different full
profile/release, source object identity and Q04 consumer/oracle harness. Q03's
four structures, localized dispositions and interruption/retry/replay therefore
remain reusable historical reference evidence, but do not satisfy Q04
fresh/restored/replay/full-graph rows or create a Q04 fresh-index entry. Native
and WikiSkill have not run under the integrated Q04 producer. YOLO ran but stopped
before acceptance, so its R3 result remains supporting evidence only.

## Cross-cutting gates

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| Immutable source/producer/profile/method/oracle binding | **proven** | Static audit plus accepted Keynote/ACL run identities |
| Stage-impact and compatibility projection | **proven** | Executable local dependency audit |
| Six-fixture complete matrix | unproven | Two proven; YOLO fresh failed the graph gate, its later modes did not run, and three other fixture rows remain open |
| Corrected AIMA continuation and four algorithms | reusable reference | Equal source/producer/method; distinct Q04 profile/harness runtime gates remain open |
| Evidence-only compatible reuse | reusable | Q03 actual Temporal/store case; never copy registrations |
| Real assembly/method invalidation | unproven | Local harness only |
| Old request remains on original route | **proven** | ACL window c re-read retained Keynote binding |
| Changed profile rejects old request | unproven | Local compatibility only |
| Required-relationship interruption/retry/replay | reusable | Q03 trial D owned-child case; no Pod-loss claim |
| Fixed warm sequence and recycle | unproven | Candidate fresh observed handoff/no overlap, but graph/resource gates failed; inactive max_requests=1 candidate invalidates request-20 evidence |
| Bounded process resources for fixtures 09/10 | **proven** | Two small-fixture windows only |
| Integrated operating bounds | unproven | All 397 samples are complete; group-3 warm parse has the sole 4,403,523,584-byte violation, with no fresh-child overlap |
| Active telemetry-loss guard | unproven | Q04 runtime phase not run |
| Process drain/recovery | unproven | Q04 runtime phase not run |
| Pod drain/recovery | unproven | R3 method/topology is reusable; integrated native Pod drain and owned topology remain required |
| Supported-bounds report to #44 | unproven | Depends on remaining runtime rows |

The accepted ACL old-binding check proves that an original request still resolves
under its original prefix/profile/release. It does not replace the planned native
changed-profile rejection and original-profile replay. Likewise, Q03 interruption
evidence remains valid only while the required-relationship execution path stays
unchanged; it proves an owned evidence child, not Pod loss.

All earlier failures remain in `sentinel/` and its README. PSI rejections,
precheck failures, argument-validation failures and graph-review failures are not
relabelled by the later passes. `quality_accepted=false` and
`canonical_accepted=false` remain explicit; this matrix adds no LaTeX, canonical
schema or general PDF-quality claim.

The attribution-B window remains a retained failure with an incomplete
measurement contract. Lifecycle A proves that the fixed candidate removes the
warm/fresh overlap, while its graph and resource gates remain failed. Its 202
active guard samples peaked at 4,273,446,912 bytes; the complete 250 ms stream
observed one 4,403,523,584-byte sample during the third sequential warm-parser
group. The shared PID had zero recycles and increasing RSS high-water. The
inactive fixture-window resource candidate changes only `max_requests` from 20
to 1. A future gate must check all complete samples against the unchanged 4 GiB
limit and require both cleanup markers on the final sample. No integrated
resource bound is accepted.

Main accepted the exact two-pair equivalence bundle and the window-local
`max_requests=1` resource candidate for the **next fixture-07 candidate only**.
The new [reviewed inactive manifest](candidate/yolo-reviewed-v1/MANIFEST.json),
[run plan](candidate/yolo-reviewed-v1/RUN-PLAN.md) and
[`yolo-reviewed-b` offline manifest](preflight/yolo-reviewed-b/OFFLINE-MANIFEST.json)
bind a new identity, fresh/restored/exact replay, and the final all-sample gate.
This preparation does not alter the historical reference or failures and does
not authorize runtime, a threshold change, another fixture, or Deployment
restore. Automatic retry remains disabled. A separate explicit single-run
authorization for the exact scope digest is required.

The authorized `yolo-reviewed-b` run remains
`FAIL_ATTRIBUTION_CONTRACT_NOT_PROMOTED`; its evidence and pending index were not
promoted. The subsequent [offline reconciliation](candidate/yolo-reviewed-b-fail/OFFLINE-RECONCILIATION.md)
keeps sample 726 process PSS unknown while allowing a narrowly proven PID-exit
transition to preserve only cgroup continuity. It also requires each
`max_requests=1` parser identity to exit before assembly instead of treating a
termination label as proof. This harness correction is offline evidence, not a
retroactive PASS or authorization to rerun.


## H repair and I diagnostic window (2026-09-20 execution session)

The [session handoff](pod-topology-v8/SESSION-HANDOFF.md) adds evidence without
promoting any fixture or cross-cutting row. H's discarded controller sample and
worker-log cleanup defects are repaired in version I. Recovered H history and
worker/cgroup traces classify its business failure as PSI-triggered cancellation,
not demonstrated Activity deadline exhaustion.

One I run from 41a8816 passed all 11 pre-inference gates and registered five YOLO
pages, then failed the transient scratch/durable evidence transport contract.
Restored/replay did not start. Failed-workload terminal sealing and separate
read-only recovery of 38 inventory entries succeeded, while automatic export
remains failed. Owned runtime was removed, all 32 held Deployments stayed off,
and all historical PVC UIDs were retained. See [results](pod-topology-v8/first-window-evidence/RESULTS.md).

The existing machine-readable acceptance statuses remain unchanged: I adds no
accepted fresh index or supported operating bound. The remaining transport repair
must precede a separately identified follow-up window; I was not retried. #51
remains open; [ticket text](pod-topology-v8/TICKET-51-UPDATE-DRAFT.md) is a draft for
main, not a published update.


## J transport repair and diagnostic window (2026-09-20)

Repair commit `2619844` passed 114 tests and two independent reviews. One J run
passed 11 pre-inference gates and the fresh/restored/exact-replay YOLO case checks
(each business result complete, 15/15 pages), but failed the unchanged attribution
contract: 54/1,023 rows incomplete. The fresh index remains pending; no existing
machine-readable acceptance status or supported operating bound is promoted.

Scratch transport and automatic failed-window export are now runtime-proven:
115 receipts within the five-second gate; 77 sealed inventory entries and archive
verified before owned runtime removal. Node/cgroup PSI and OOM guards stayed zero.
Process-read PermissionError/coverage races are the observed blocker; exact cause
and missing PSS remain unknown. See the [J handoff](pod-topology-v9/SESSION-HANDOFF.md)
and [results](pod-topology-v9/first-window-evidence/RESULTS.md). All 32 held
Deployments stay off, historical PVC UIDs/prefixes remain, no retry occurred.
#51 stays open; [ticket text](pod-topology-v9/TICKET-51-UPDATE-DRAFT.md) is unpublished.

## K–M reconciliation (2026-09-20)

K retained the recurring kubelet readiness exec and failed9/1,021 attribution
rows despite three complete business cases. Diagnostic probes identified the
root runc initializer by the exact failed command hash. L replaced the repeated
exec with startup-only checks plus persistent runtime mount checks. All290 L
process samples were complete, but real node PSI stopped fresh before any page.
See [L results](pod-topology-v11/first-window-evidence/RESULTS.md).

M passed all three fixture07 cases and all1,021 complete attribution samples,
unchanged4GiB/zeroPSI/zeroOOM gates, archive verification and cleanup. See
[M results](pod-topology-v12/first-window-evidence/RESULTS.md). This supersedes
only the07 current unproven row above; preceding prose describes retained failed
attempts. The07 policy stays max_requests=1, two reviewed paragraph pairs and
workload-tree THP disabled. The THP cause of L remains unproven.

ACL/Keynote remain proven under their original producer/runtime identities;
applicability to the four-file lifecycle producer change is not assumed. Native,
Wiki,AIMA, fixed request20 warm sequence, invalidation/old-profile rejection and
active telemetry/process/Pod recovery remain open. No integrated resource bound
or overall Q04/#51 PASS is declared. All32 held Deployments remain off and all
historical evidence/PVCs/prefixes remain.
