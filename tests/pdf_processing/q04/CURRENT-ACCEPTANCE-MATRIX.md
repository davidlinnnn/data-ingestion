# Q04 current acceptance matrix

This snapshot reconciles issue #51 through commit `6f16ec8`. The machine-readable
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
| AIMA `08` | original 99–110 | reusable | reusable | reusable | reusable | unproven |
| ACL `09` | original 2–4 | **proven** | **proven** | **proven** | **proven** | **proven** |
| Keynote `10` | one page | **proven** | **proven** | **proven** | **proven** | **proven** |

ACL is the accepted Option A graph: 134 items, six reviewed equations, equation 2
as `TextItem`, two required OCR results and exact fresh/restored/replay graph
equality. Keynote covers 44 items, all 27 reviewed textboxes, one required OCR
result and exact graph equality. Their process-resource and cleanup observations
remain bounded to those fixtures.

AIMA's Q03 full cases and trial D used the same 20 production hashes and directly
proved fresh/new-request reuse/exact replay/evidence variation, four structures,
localized dispositions and required-relationship interruption/retry/replay. This
is reusable evidence after an exact identity check. It does not create a Q04
fresh-index entry, warm result, resource envelope or Pod-loss result. Native,
WikiSkill and YOLO have not run under the integrated Q04 producer, so their R3
results remain supporting evidence only.

## Cross-cutting gates

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| Immutable source/producer/profile/method/oracle binding | **proven** | Static audit plus accepted Keynote/ACL run identities |
| Stage-impact and compatibility projection | **proven** | Executable local dependency audit |
| Six-fixture complete matrix | unproven | Two proven, one reusable, three not run |
| Corrected AIMA continuation and four algorithms | reusable | Q03 exact-identity scope; Q04 warm index absent |
| Evidence-only compatible reuse | reusable | Q03 actual Temporal/store case; never copy registrations |
| Real assembly/method invalidation | unproven | Local harness only |
| Old request remains on original route | **proven** | ACL window c re-read retained Keynote binding |
| Changed profile rejects old request | unproven | Local compatibility only |
| Required-relationship interruption/retry/replay | reusable | Q03 trial D owned-child case; no Pod-loss claim |
| Fixed warm sequence and recycle | unproven | R3 topology only |
| Bounded process resources for fixtures 09/10 | **proven** | Two small-fixture windows only |
| Integrated operating bounds | unproven | Larger fixtures, warm and recovery absent |
| Active telemetry-loss guard | unproven | Q04 runtime phase not run |
| Process drain/recovery | unproven | Q04 runtime phase not run |
| Pod drain/recovery | unproven | Owned Pod/shared-path topology missing |
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

The next proposed batch is [YOLO fixture 07](NEXT-RUNTIME-BATCH.md). It is the
smallest fixture with no reusable integrated run and adds table/cell, caption and
multi-page OCR coverage that the two completed small fixtures do not supply.
