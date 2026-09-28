# T06 bounded handoff qualification

**PASS for the declared internal delivery contract and sampled scope.** AIMA's
non-contiguous derivative paragraph/note association remains explicitly unqualified.
This is not canonical acceptance, universal PDF quality, production HA or throughput
qualification. No LaTeX recognition was added.

## Runtime evidence

Real local Kubernetes, Temporal and MinIO were used, with the pinned Linux runtime
and models. [runtime.json](runtime.json) records exact source revisions/object
versions, profile, limits, dependency versions and SHA-256 of every package module.
The source policy binds processed derivative bytes to original PDF bytes and
physical page mappings, and checks mapped page pixels before publishing evidence.
Sources, full parsed text, source page images and crops remain local; only metadata
and hashes are committed.

| Gate | Result |
|---|---|
| WikiSkill original physical 4, 5, 8 | Complete durable handoff; full 188-cell table check passed. |
| YOLO original physical 3, 5 | Complete handoff; 60 cells preserved using the exact S2 source-specific disposition for 15 U+0002/discretionary-spacing cells. No global character substitution. |
| AIMA physical 86, 87, 104 | Full typed per-page content, CodeItem instruction sequence/caption, footnotes and readable source preserved; representation uncertainty retained. Association limitation below. |
| ACL physical 2–4 | All prior source-audited typed text/captions and selected body order preserved; same-item left→right continuation checked. Six reviewed equations delivered, including TextItem eq2; minus/overbar observations remain explicitly unconfirmed. No table on these selected pages. |
| Keynote-export PDF page 1 | 27 complete source textboxes checked across split typed children; readable diagram source preserved. No native PPTX or graph-edge extraction claim. |
| Independent uninterrupted conversion | All five full document JSON values equal reconstructed delivery, with no normalization. [fresh-comparison.json](fresh-comparison.json) |
| Actual Activity Pod replacement | Different Pod UID, same pinned image; every final/evidence reference readable. All five accepted requests reuse every page-group, assembly and OCR registration and return identical final registrations. [replacement.json](replacement.json), [controller](replacement-controller.json) |
| Required evidence failure | Duplicate review IDs, invalid original page, oversized original render, unmatched reviewed region, and regionless parser formula each fail permanently on attempt 1. Distinct reviewed equations sharing one item and client filename `original.pdf` both succeed correctly. [review-failures.json](review-failures.json) |
| Legacy | v1 remains `parsed_ready` with processing incomplete; v2 synthetic multiple/none/blank/rotated cases, attribution and reuse passed. [legacy.json](legacy.json) |
| Traditional Chinese supplement | Existing NCCU physical page 3: real required OCR recovers both reviewed anchors, with checked source/result attribution and durable v3 source. Other historic TC evidence is unchanged; no broad language claim. [tc-supplement.json](tc-supplement.json) |
| Static/focused checks | Typecheck: 0 errors/warnings. Complete 10-test unittest suite passes, including scanned fresh-process restoration, five T04 checks and four T05 real-subprocess checks. Two-axis review/recheck recorded in [REVIEW.md](../REVIEW.md). |

[summary.json](summary.json) records exact request/workflow/operation identities;
[quality-comparison.json](quality-comparison.json) records prior-source-audited
comparison scope. [manifest.json](manifest.json) binds all retained evidence files.

## AIMA derivative limitation

Joining non-contiguous original pages 86, 87 and 104 into one PDF can affect native
Docling's cross-page paragraph assembly. Delivered `#/texts/73` joins original
page 87's final paragraph (charspan `[0,282]`) with page 104's margin note (charspan
`[283,301]`). Both exact text segments, actual type, page-region provenance and
readable mapped source remain present. The full raw document is not rewritten.

Per-page content comparison uses those charspans; sorting AIMA's item inventory
checks membership, not body order. **This paragraph/note association and AIMA total
body order are unqualified.** Uninterrupted equality does not approve an upstream
association error. The generic consumer note-association disclaimer must not be
read as a positive association claim. Use source evidence/charspans; a consumer
requiring faithful paragraph association needs a targeted contiguous-context or
separate-page check. ACL multicolumn order is a separate passed gate.

## Corrections retained in the record

Initial v3 red test failed with `invalid_request` before implementation; it passed
after v3 was implemented. Exploratory scorers were corrected for YOLO's already
reviewed source-font/discretionary-spacing cells, wide representation regions,
slide textboxes split over multiple items, and AIMA cross-page charspan projection.
None of those corrections normalizes stored text or claims mathematical equivalence.

Review found and fixed original-page pre-render pixel guards, accidental removal of
multiple reviewed occurrences sharing a ref, and regionless labelled formulas.
A final scratch-path inspection found the possible `original.pdf` name collision;
fixed separate paths and a real-service negative/positive harness verified it.
All real final deliveries were regenerated on that final producer; unchanged
independent parser baselines were reused only for comparison after the path fix.
The host's default Python lacked PDFium, and a default offline npm cache lacked
Pyright; reruns used the existing pinned Python dependencies and cached checker.
These environment misses are not passed test runs.

Future required LaTeX enrichment must join the completion barrier. Scanned/historical
repair, faulty text-layer repair, untested languages/geometries, whole-book behavior,
canonical adoption, shared GC and production operating budgets remain out of scope.
