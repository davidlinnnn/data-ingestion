# T10 / #46 acceptance audit

Baseline: `origin/dev` / `cf29cae13b5b84a0f859ac35e2586427e7d1a24b` (PR #66 merged).
Initial audit 2026-10-01, before implementation. Historical files are immutable.
Selected group5 / one active parser; no resource, quality or capacity widening.

| #46 criterion | Existing evidence | Missing deliverable | Necessary new verification |
| --- | --- | --- | --- |
| 1. Consistent images, routing, Kubernetes, bootstrap, recovery | T08 routes and exact queue/image/model binding; T09b SUPPORTED-CONFIGURATION and SUPPORTED-BOUNDS | Buildable release bundle, selected limits, source/model bootstrap, runbook | Build/image inventory; rendered manifests and actual worker startup; same candidate profiles/queues |
| 2. Same candidate evidence; changed/uncovered interactions | T08 phased rollout; Q01/Q02/Q03 quality; #44 resource/lifecycle; #45 matched group/cold/recovery | Hash reconciliation and release evidence index | New packed-worker routing + complete result/reuse; selected assembly/finalization loss and late publication; no repeated full calibration |
| 3. Existing summaries/inventory/capacity path usable | Processing progress/error/reuse timestamps, parser summaries; Store.inventory; T09b ledgers | Operator commands and actual examples | Query running/completed/failed work, read final manifest, run bounded inventory; provider/PVC capacity separately |
| 4. Actual store conditional write/visibility/bounded failover | T03 conditional race/lost ACK/late attempt; original MinIO Pod/PVC replacement | Current topology/config record and production gate ownership | Fresh-prefix real-store race/visibility/lost ACK and Pod replacement with PVC retained; node/disk/HA explicitly untested |
| 5. Input/result, mapping seam, retention handoff #31/#32 | Request v3 / required_evidence_v1; checked typed content, OCR/relationships/evidence; canonical_accepted=false | Runnable submission/retrieval and examples; named ownership/dependencies | Resolve complete result and adopted-reference inventory; preserve unknown representation/quality outcomes |
| 6. Scratch cleanup and retained references | #43/#44/#45 restart/drain/recycle; checked references; emptyDir | Packed-worker cleanup and retention instructions | Restart new worker and resolve references; local owned scratch cleanup; no shared GC |
| 7. Bounded verdict/release/runbook; later dependencies | #33 separates processing completion, Canonical Acceptance and projection delivery; #52 owns design/migration | Final verdict and release package | Full local regression once, scoped typecheck, two-axis review; no main publication or parent closure |

T09b's premerge OPEN wording is a historical snapshot. #45 is closed after PR #66.
#52/#54 own platform envelope; #31/#32/#57 own integration/migration/custody decisions.
No whole-book, generic PDF, scan-first, two-parser, SLA or production-HA claim.

Final reconciliation: all seven deliverables and necessary uncovered interactions
are satisfied within the declared bounds. See [VERDICT.md](VERDICT.md) for each
criterion, measured guards, retained failures and baseline test limitations;
`evidence/RELEASE.json`, `RESULTS.json` and `INDEX.json` bind the package, actual
handoff examples and immutable raw evidence. The historical rows above remain the
initial pre-implementation audit rather than being rewritten as retrospective proof.
