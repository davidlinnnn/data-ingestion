# CG: bounded normal-topology mixed sequence passed

CG ran once under the unchanged formal guards, all 32 recorded Deployments
active, the same fixed [06,07,08,native,06] sequence, actual OCR launch-policy
fix and a temporary observed 1Gi object limit. It reused CD's unchanged input
bundle. The only diagnostic change from CD was tracing actual
`psi_memstall_enter` callers with live task/cgroup identity instead of broad
MinIO D-state stacks. No production or acceptance threshold changed between
the failed CD and successful CG runs.

All five workflows completed their required work, passed local reviewed
checks, and produced full document JSON equal to the accepted AI/AJ fresh
references. The complete reviewed checks also compare equal with no fields
removed. This closes the raw phase record's explicitly pending output-equality
check through a separate retained comparison; it does not rewrite that record.
`canonical_accepted=false` remains the bounded v3 contract's value: this is not
a universal quality claim or a claim that old and new producer identities match.

The exact sequence processed 29 group requests with one recycle after request20,
using parser PIDs131 and1836. Later groups and the final document completed.
The workload measurement evaluated 1,441 continuous samples with no memory,
OOM or full-PSI avg10 violation. The outer controller recorded 1,503 samples,
maximum gap0.442s, minimum VM available2,849,722,368 bytes and maximum worker
cgroup2,608,893,952 bytes. The object observer recorded2,224 samples, maximum
memory.current734,961,664 bytes, zero max events and zero full-PSI total increase.
These are observations of this bounded window, not file/page/pixel ceilings or
permanent sizing guarantees.

The function tracer captured373 memory-stall entries in the VM and none
attributed to the exact target object container. Its buffers reported no
lost events and it exited cleanly. It therefore did not capture the immediate
caller of the historical object PSI failures. CD's failed event remains valid;
one successful CG window does not prove those intermittent failures resolved.

The runner exited0, durable terminal status was PASS_CANDIDATE, and all cleanup
markers passed. Independent checks found all32 Deployments at0/0 with no owned
Pods, object512Mi/Ready, CG worker absent, evidence PVC Bound, and all CD/CE/CF/CG
tracer containers/private instances absent. Historical evidence and prefixes
were retained. No automatic retry occurred.

| Scope | Result |
|---|---|
| Exact command, source/import/runtime contracts | Passed |
| Admission and 11 pre-inference gates | Passed |
| All five required-work results and reviewed checks | Passed |
| Full JSON equality to accepted fresh references | 5/5 passed |
| 29 group requests, request20 recycle, post-recycle completion | Passed |
| Formal memory/OOM/PSI and sample continuity | Passed in CG |
| Durable evidence and independent restoration | Passed |
| Earlier object PSI immediate caller / intermittent reliability | Unresolved |
| Sustainable permanent object setting and universal input ceilings | Not established |
| #44 closure | Not justified by this single success |

Recheck with `python3 tests/pdf_processing/t09a_bounds/normal-topology-cg/verify_results.py`.
Raw evidence remains in `/private/tmp/t09a-bounds-20260927-cg`,
`/private/tmp/t09a-bounds-object-20260927-cg`, and
`/private/tmp/t09a-normal-topology-20260927-cg`.
