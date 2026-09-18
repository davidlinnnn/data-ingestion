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

YOLO matrix A is a retained failed attempt, not an unrun row and not a partial
pass. Fresh completed three five-page capture groups, then the fixed 4 GiB shared
cgroup guard fired after assembly was scheduled while progress read `assembling`.
Complete delivery and every consumer oracle
remained unevaluated; restored and exact replay did not run; no fresh-index entry
was created. Cleanup passed with zero retry and all 32 historical Deployments
remaining closed. Fresh/restored/replay/full-graph rows therefore remain
`unproven`.

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
| Fixed warm sequence and recycle | unproven | R3 topology only |
| Bounded process resources for fixtures 09/10 | **proven** | Two small-fixture windows only |
| Integrated operating bounds | unproven | YOLO crossed the fixed shared-cgroup guard after assembly scheduling; larger fixtures, warm and recovery remain absent |
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

No runtime batch is currently authorized. The offline
[YOLO resource diagnosis](diagnosis/yolo-matrix-a/ANALYSIS.md) recommends one
fresh-only attribution calibration, still using the current guard, before another
full matrix. Its [measurement options](diagnosis/yolo-matrix-a/NEXT-MEASUREMENT.md)
do not authorize a run or a threshold change.
