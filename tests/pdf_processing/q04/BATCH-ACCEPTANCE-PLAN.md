# Q04 batch acceptance plan

This is one reviewable executable batch, not runtime authorization. It retains the
candidate producer-manifest SHA-256
`a6501b471bd3193a7b0e890b386174a022aa9f1b63dca6432ae85e14b9f5af3d`,
candidate `inputs.json` SHA-256
`67eba79d6125c536ab728edb4f7d8ee070d8aead49384f4afc3a48c78267d420`,
the 4 GiB/PSI/OOM guards, serial execution, no retry and all 32 historical
Deployments closed. Time allocations are budgets, not completion guarantees.
Any failed admission, guard, oracle, cleanup or identity check stops the batch;
there is no automatic fix or rerun.

## Gate order and evidence

| Gate | Fixture/modes | Reusable review material | New evidence required under candidate producer | Readiness |
| --- | --- | --- | --- | --- |
| 1 | YOLO 07 fresh → restored/new request → exact fresh replay | Fixed PDF, 15-page reference graph, six-table/60-cell audit, captions and four OCR oracles | Complete graph/delivery, reuse and exact-fresh-replay identities, 250 ms attribution, observed handoff, no warm/fresh overlap and cleanup | **Executable** through the retained `yolo-lifecycle-a` runner |
| 2 | ACL 09, then Keynote 10, each three modes | ACL six-equation/TextItem-eq2 review; Keynote 27-textbox/source-geometry review | New profile/release, complete graph/source evidence and three-mode records under the candidate producer | **Executable after gate 1 PASS + cleanup**, through the fixed candidate phase adapter |
| 3 | AIMA 08, three modes | Q01/Q02/Q03 reviewed pages 99–110, four algorithms, continuation/symbol dispositions and historical runtime | New candidate producer graph, restored comparison and exact fresh replay | **Executable after gate 2 PASS + cleanup**, through the fixed candidate phase adapter |
| 4 | WikiSkill 06, three modes | Full graph/reference, table-cell/span and caption oracle | New candidate producer graph, restored comparison and exact fresh replay | **Executable after gate 3 PASS + cleanup**, through the fixed candidate phase adapter |
| 5 | Native 51-page paper, three modes | Fixed reference graph, full source/quality review and required OCR selections | New candidate producer graph, restored comparison and exact fresh replay | **Executable after gate 4 PASS + cleanup**, through the fixed candidate phase adapter |

A gate starts only after the prior gate passes and its cleanup/health evidence is
complete. Exact replay always uses that fixture's exact fresh request, plan,
registrations and artifacts. Restored always uses a distinct request ID and the
fresh captured source artifact. No prior accepted request is reinterpreted.

## Capacity budget

Each phase owns a new root, prefix, run ID, reservation and output. Reservation
acquisition and identity prechecks precede the lease. Once the lease starts,
staging/init plus outer admission may use at most 375 seconds in total; 195
seconds is the planning allocation for staging/init when outer admission uses
its full 180-second ceiling, not an independently enforced deadline. Outer
admission still requires 60 continuous seconds at 4.5 GiB and PSI=0. Every
phase reserves its last 300 seconds for cleanup. Its workload budget includes
three separate 60-second/3-GiB per-case admissions.

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
scheduling cap for the six leases, not a promise that the batch will complete.
Each prelease identity/reservation check is independently capped at 300 seconds,
so an all-pass normal wall-clock ceiling is 9,825 seconds. The outer controller
sends SIGINT at a prelease or lease deadline and permits one final 300-second
cleanup envelope. Each launcher runs in an owned local process group. The first
30 seconds allow cooperative cleanup; if the launcher remains, the controller
terminates the group and uses the rest of the envelope for the reviewed remote
cleanup. The 300 seconds bound those two steps together; they are not 300
seconds of cooperative waiting before termination. Before cleanup mutation, the
controller verifies the remote setup claim and reservation against the retained
token, phase, coordinator UID, PID and start ticks inside the same remote program
before cleanup begins. It releases only that same reservation. Because the batch
stops at its first failure, the absolute controller ceiling is 10,125 seconds.
The per-phase roots, prefixes,
outputs, argv and hashes are fixed in
[`preflight/candidate-batch-a/MANIFEST.json`](preflight/candidate-batch-a/MANIFEST.json).

## Later lifecycle and failure gates

These rows are **not ready** dependencies after all six fixture matrices and
are not part of the executable batch runtime scope:

| Gate | Dependency and missing preparation |
| --- | --- |
| Compatibility/invalidation/old-request | Requires the candidate native fresh index and a fixed candidate runner for `evidence`, `invalidation` and `old-request`; must prove compatible reuse and rejection without reinterpreting old requests. |
| Warm lifecycle and telemetry loss | Requires candidate fresh indexes for Wiki→YOLO→AIMA→native→Wiki, request-20 recycle and a callback-bound telemetry-loss runner. Local next-capture rebuild is already tested; three-mode reuse must not be described as runtime rebuild evidence. This remains a #51 gate. |
| Required-work interruption | Q03 interruption evidence remains historical. A candidate runner must bind failure-before-publication, retry/replay ownership and the lifecycle producer before new runtime credit is claimed. |
| Owned-Pod drain | Missing owned Deployment/image, labels and UID fencing, shared candidate bundle/state/evidence mounts, replacement readiness and old-container/emptyDir observation. No Deployment may be created under this plan. |

## Single approvable scope

The batch entrypoint is `sentinel/run_candidate_batch.py`. It launches the
retained [`yolo-lifecycle-a` window](candidate/yolo-lifecycle-v1/VALIDATION-PLAN.md)
first. Only a zero exit plus acceptance, cleanup, held-service and reservation
evidence unlocks ACL. The same check serially unlocks Keynote, AIMA, WikiSkill
and native. There is no per-fixture confirmation and no retry or fix-and-resume.

The exact invocation after one new authorization is:

```sh
cd /private/tmp/q04-acceptance
export Q04_APPROVAL_REFERENCE='<verbatim later authorization>'
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:src:tests/pdf_processing/q04 \
/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_candidate_batch.py \
  --execute --owner 'main session' \
  --approval-reference "$Q04_APPROVAL_REFERENCE"
```

The fixed repository working directory and `PYTHONPATH` include the repository
root so the module-based offline gate and subprocess entrypoints resolve the
same reviewed package graph.

The single offline gate is:

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:src:tests/pdf_processing/q04 \
/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  -m tests.pdf_processing.q04.yolo_lifecycle_offline_suite
```

It performs no cluster access or inference. It checks all six fixed identities,
the candidate/staging hashes, exact measurement argv, deadline wrappers, serial
unlock rules, exact replay/new-request contracts and the existing lifecycle,
collector, cancellation and cleanup regressions.

Suggested authorization text:

> I authorize one process-mode `candidate-batch-20260919-a` execution at the
> reviewed commit, using the fixed manifest and 8,025-second aggregate lease
> budget. Run YOLO 07, ACL 09, Keynote 10, AIMA 08, WikiSkill 06 and native in
> that order, each fresh, restored/new request and exact fresh replay. Require
> each prior phase to pass and clean up before starting the next; stop on the
> first failure with no retry or repair. Keep all admission, PSI, OOM, active,
> attribution and cleanup thresholds unchanged and all 32 historical
> Deployments closed. Do not run compatibility/invalidation, warm/telemetry,
> interruption or Pod-drain gates, and do not publish, merge or close #51.
