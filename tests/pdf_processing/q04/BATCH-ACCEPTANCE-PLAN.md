# Q04 batch acceptance plan

This is a reviewable batch sequence, not runtime authorization. It retains the
candidate producer-manifest SHA-256
`a6501b471bd3193a7b0e890b386174a022aa9f1b63dca6432ae85e14b9f5af3d`,
the 4 GiB/PSI/OOM guards, serial execution, no retry and all 32 historical
Deployments closed. Time allocations are budgets, not completion guarantees.
Any failed admission, guard, oracle, cleanup or identity check stops the batch;
there is no automatic fix or rerun.

## Gate order and evidence

| Gate | Fixture/modes | Reusable review material | New evidence required under candidate producer | Readiness |
| --- | --- | --- | --- | --- |
| 1 | YOLO 07 fresh → restored/new request → exact fresh replay | Fixed PDF, 15-page reference graph, six-table/60-cell audit, captions and four OCR oracles | Complete graph/delivery, reuse and exact-fresh-replay identities, 250 ms attribution, observed handoff, no warm/fresh overlap and cleanup | **Executable now** through `yolo-lifecycle-a`; offline gate passes |
| 2 | ACL 09, then Keynote 10, each three modes | ACL six-equation/TextItem-eq2 review; Keynote 27-textbox/source-geometry review | New profile/release, complete graph/source evidence and three-mode records under the candidate producer | **Not executable yet**: existing accepted runners bind the prior producer; candidate staging/argv manifests are absent |
| 3 | AIMA 08, three modes | Q01/Q02/Q03 reviewed pages 99–110, four algorithms, continuation/symbol dispositions and historical runtime | New candidate producer graph, restored comparison and exact fresh replay | **Not executable yet**: candidate fixture runner/manifest is absent |
| 4 | WikiSkill 06, three modes | Full graph/reference, table-cell/span and caption oracle | New candidate producer graph, restored comparison and exact fresh replay | **Not executable yet**: candidate fixture runner/manifest is absent |
| 5 | Native 51-page paper, three modes | Fixed reference graph, full source/quality review and required OCR selections | New candidate producer graph, restored comparison and exact fresh replay | **Not executable yet**: candidate fixture runner/manifest is absent |

A gate starts only after the prior gate passes and its cleanup/health evidence is
complete. Exact replay always uses that fixture's exact fresh request, plan,
registrations and artifacts. Restored always uses a distinct request ID and the
fresh captured source artifact. No prior accepted request is reinterpreted.

## Capacity budget

Each phase owns a new root, prefix, run ID, reservation and output. Every phase
allows at most 195 seconds for reservation/staging/init, at most 180 seconds for
outer admission (60 continuous seconds at 4.5 GiB and PSI=0), and reserves its
last 300 seconds for cleanup. Its workload budget includes three separate
60-second/3-GiB per-case admissions.

Historical figures size the budget only: T09a R3 measured fresh/replay at
74.30/2.02 seconds for WikiSkill, 46.17/2.03 for YOLO, 42.18/2.03 for AIMA,
20.08/2.02 for ACL, 16.09/2.02 for Keynote and 118.44/4.03 for native. The prior
Q04 three-mode windows consumed 283.697 seconds for ACL and 264.340 seconds for
Keynote. Restored timing is producer- and cache-dependent and is not inferred
from replay.

| Phase | Setup + outer ceiling | Workload budget, including per-case admission | Cleanup reserve | Phase upper limit |
| --- | ---: | ---: | ---: | ---: |
| YOLO lifecycle gate | 375 s | 825 s | 300 s | 1,500 s |
| ACL candidate matrix | 375 s | 525 s | 300 s | 1,200 s |
| Keynote candidate matrix | 375 s | 525 s | 300 s | 1,200 s |
| AIMA candidate matrix | 375 s | 600 s | 300 s | 1,275 s |
| WikiSkill candidate matrix | 375 s | 675 s | 300 s | 1,350 s |
| Native candidate matrix | 375 s | 825 s | 300 s | 1,500 s |

The six-phase batch ceiling is 8,025 seconds (133 minutes 45 seconds). This is a
scheduling cap, not a promise that the batch will complete. Only the first
1,500-second phase is currently executable and eligible for immediate approval.
The remaining 6,525 seconds stay outside runtime scope until their fixed runner,
identity, manifest and offline gate exist and are reviewed.

## Later lifecycle and failure gates

These rows are dependencies after all six fixture matrices, not part of the
currently executable runtime scope:

| Gate | Dependency and missing preparation |
| --- | --- |
| Compatibility/invalidation/old-request | Requires the candidate native fresh index and a fixed candidate runner for `evidence`, `invalidation` and `old-request`; must prove compatible reuse and rejection without reinterpreting old requests. |
| Warm lifecycle and telemetry loss | Requires candidate fresh indexes for Wiki→YOLO→AIMA→native→Wiki, request-20 recycle and a callback-bound telemetry-loss runner. Local next-capture rebuild is already tested; three-mode reuse must not be described as runtime rebuild evidence. This remains a #51 gate. |
| Required-work interruption | Q03 interruption evidence remains historical. A candidate runner must bind failure-before-publication, retry/replay ownership and the lifecycle producer before new runtime credit is claimed. |
| Owned-Pod drain | Missing owned Deployment/image, labels and UID fencing, shared candidate bundle/state/evidence mounts, replacement readiness and old-container/emptyDir observation. No Deployment may be created under this plan. |

## Immediately approvable scope

The only immediately approvable runtime is the already fixed
[`yolo-lifecycle-a` window](candidate/yolo-lifecycle-v1/VALIDATION-PLAN.md). A
single authorization covers its fresh, restored and exact-fresh-replay cases;
there is no per-case confirmation.

Suggested authorization text:

> I authorize one 1,500-second process-mode `yolo-lifecycle-a` window at the
> reviewed candidate commit, limited to fixture 07 fresh, restored/new request
> and exact fresh replay. Use the fixed root, prefix, runner and manifests in
> `VALIDATION-PLAN.md`; keep the 4 GiB, admission, PSI, OOM, attribution and
> cleanup thresholds unchanged. Stop on any failure with no retry. Keep all 32
> historical Deployments closed. Do not run later fixture, lifecycle,
> interruption or Pod-drain gates, and do not publish, merge or close #51.

Before any broader one-shot batch authorization, gates 2–5 must each have a
fixed identity, candidate staging manifest, exact argv, deadline/cleanup wrapper
and passing offline validation committed together. Once those artifacts exist,
one later authorization may cover their serial execution with stop-on-first-
failure semantics; separate confirmation per fixture should not be requested.
