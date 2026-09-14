# T09a authorized capacity window (R3)

Issue #44 remains open because AIMA source-quality gates remain unqualified.
This round changes only qualification harnesses and evidence. Production parser,
profile, methods, association policy, and resource limits are unchanged.

The user authorized temporarily scaling the existing activities, workflows,
objects, and temporal Deployments in pdf-t03-validation through
pdf-t07-validation to zero. The controller checks original UID, full spec and
replicas; checks Temporal open work before and after stopping workers; keeps the
shared flock until own Pods and all-node CRI containers are absent and original
services and workers are restored. Restoration checks actual MinIO and Temporal
health before starting workers. PVCs and stored data are preserved.

Run `20260914-0b537d0-b` passed capacity admission but the preflight rejected an
invalid source key before parsing. The historical R2 verifier used
`final/r2-sources/`; production requires `final/sources/`. The real source reader
rejected the captured key and accepted identical bytes at the accepted prefix.
R3 corrects that harness key and freezes the verifier hash. The failed window
was cleaned up and all original replicas restored before run c began.

R3 copies the R2 runners so historical evidence and seals remain unchanged.
Each run uses new queues, requests, controller files, and a frozen release.
The private raw records remain under `/private/tmp/t09a-r2-20260914/` and the
window directories; committed exports contain metadata and hashes, with literal
credential environment values redacted.

The 3 GiB / 60-second admission threshold is a test prerequisite, not a supported
memory envelope. Results apply to this fixed serial configuration with the
specified twenty Deployments paused. AIMA algorithm typing/caption/representation
and the original-page-103/104 paragraph association remain open even when full
JSON equality and durable evidence checks pass.

Final phase matrix and restoration evidence are recorded alongside this report.

After the successful active-telemetry-loss guard, run c's immediate drain
admission rejected nonzero full PSI (`avg10=0.01`) despite 3.37 GiB available
and no new OOM. No drain request was submitted. The window restored all original
replicas. Window d resumes only the missing drain/full-suite work, uses the same
frozen run c and its baselines, and requires fresh admission and a new Keynote
preflight. Unique trial names preserve the rejected drain and earlier results.

## Final matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| Fresh native + five supplementary fixtures | PASS | Six complete durable results; no restart/OOM |
| Warm sequence and planned recycle | PASS | Wiki → YOLO → AIMA → native → Wiki; 29 group requests; same Pod; request-20 recycle; all full typed JSON equal fresh |
| New request with old compatible groups | PASS | All 11 prior native groups reused; new complete result equals fresh |
| Exact accepted-request replay | PASS | Six requests; unchanged final identities; every registered step reused |
| Active telemetry-loss guard | PASS | Real observer rejected loss during recorded page-6 TableStructureModel stage; owned runtime quiesced; only guard workflow terminated |
| First drain admission | REJECTED | Post-guard full PSI avg10=0.01; no drain request submitted; original environments restored |
| Resumed drain/replacement | PASS | Five pages retained; 6–10 attempt 2; all other groups attempt 1; full result equals fresh; old runtime/scratch absent |
| Full regression suite | PASS | 10 tests, 30.581 seconds |
| Scoped type check | PASS | Zero errors/warnings |
| Restoration | PASS | All 20 original replicas ready; service health; own Pods/CRI absent on all nodes; lock available |
| AIMA source quality | OPEN | Algorithm typing/caption/representation and paragraph/margin association remain unqualified |

The first source-key failure and the post-guard pressure rejection remain in the
matrix as failures; neither is rewritten as successful inference. The intentionally
failed guard trial is interpreted through `guard-cleanup.json`, which proves the
expected failure and cleanup, rather than as a successful document run.

The highest sampled cgroup usage across run c was 2.452 GiB. During the uninterrupted
warm sequence, minimum sampled VM MemAvailable was 1.583 GiB, with one Pod UID,
zero restarts, and unchanged global OOM counter 28. The drain's old Pod disappeared
32.1 seconds after deletion; old/new maximum sample gaps were 1.01/1.05 seconds.
These are observations for this isolated capacity arrangement, not a general
supported resource envelope. Full PSI was nonzero during the intentional guard
and correctly prevented immediate admission of another workload.

Metadata exports retain accepted profile/limits/producer details, deduplicated
actual native methods, workflow histories, parser lifecycle observations, OCR
execution metadata, controller records, and private-raw hashes. The final seal
covers only R3 files. Historical T09a/R2 evidence is preserved unchanged.
