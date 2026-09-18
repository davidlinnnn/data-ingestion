# Q04 current acceptance matrix

This snapshot reconciles issue #51 through the YOLO result commit `ccdf81a`. The machine-readable
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
| YOLO `07` | 15 pages | unproven | unproven | unproven | unproven | unproven |
| AIMA `08` | original 99–110 | unproven | unproven | unproven | unproven | unproven |
| ACL `09` | original 2–4 | **proven** | **proven** | **proven** | **proven** | **proven** |
| Keynote `10` | one page | **proven** | **proven** | **proven** | **proven** | **proven** |

ACL is the accepted Option A graph: 134 items, six reviewed equations, equation 2
as `TextItem`, two required OCR results and exact fresh/restored/replay graph
equality. Keynote covers 44 items, all 27 reviewed textboxes, one required OCR
result and exact graph equality. Their process-resource and cleanup observations
remain bounded to those fixtures.

YOLO matrix A and attribution B are retained failed attempts, not unrun rows or
partial passes. Both crossed the fixed 4 GiB shared-cgroup guard during assembly
before complete delivery or consumer-oracle evaluation. Attribution B's complete
250 ms peak samples show that owned anonymous warm-parser and fresh-child memory
drove the growth, with both processes still live after cancellation. Its required
controller `cancel_requested` marker was absent, so the attribution contract
remains incomplete and cannot establish acceptance or a sizing limit. Its
complete synchronized samples do prove that warm-parser/fresh-child overlap was
already present before cancellation and at the first guard breach. A separate
local lifecycle candidate now reaps the idle warm parser and holds its shared
ownership lock through the fresh assembly child; it has not run. Restored and
exact replay did not run; no fresh-index entry was created. Cleanup passed with
zero retry and all 32 historical Deployments remaining closed.
Fresh/restored/replay/full-graph rows therefore remain `unproven`.

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
| Six-fixture complete matrix | unproven | Two proven; four Q04 fixture rows remain open |
| Corrected AIMA continuation and four algorithms | reusable reference | Equal source/producer/method; distinct Q04 profile/harness runtime gates remain open |
| Evidence-only compatible reuse | reusable | Q03 actual Temporal/store case; never copy registrations |
| Real assembly/method invalidation | unproven | Local harness only |
| Old request remains on original route | **proven** | ACL window c re-read retained Keynote binding |
| Changed profile rejects old request | unproven | Local compatibility only |
| Required-relationship interruption/retry/replay | reusable | Q03 trial D owned-child case; no Pod-loss claim |
| Fixed warm sequence and recycle | unproven | Lifecycle candidate invalidates the old request-20 PID/recycle sequence; revised behavior is local-only |
| Bounded process resources for fixtures 09/10 | **proven** | Two small-fixture windows only |
| Integrated operating bounds | unproven | Pre-cancel YOLO overlap is diagnosed and a local candidate removes it; no candidate runtime bound exists |
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
measurement contract. Its [lifecycle diagnosis](diagnosis/yolo-attribution-b/ANALYSIS.md)
uses complete samples to establish warm-parser/fresh-child overlap before
cancellation and at the initial guard breach. The fixed
[`q04-yolo-lifecycle-v1` candidate](candidate/yolo-lifecycle-v1/IMPACT.md) has a
separate producer/bundle identity, local ownership and cleanup tests, and a
[fresh→restored→replay plan](candidate/yolo-lifecycle-v1/VALIDATION-PLAN.md).
Main-session candidate review is next. No runtime batch, retry, pure marker
calibration or threshold change is currently authorized.
