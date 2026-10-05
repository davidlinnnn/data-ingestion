# A3: node PSI guard stop during first execute group

Executed commit `2bfa48c`, identity `t09b-calibration-20260928-a3`.
One controlled diagnostic execution; no retry. Object and worker resource settings
were unchanged. The approved A3 exception recorded object Pod
`memory.events.max` as a boundary signal rather than stopping on that signal alone;
OOM, positive full PSI, memory floors and deadlines remained fatal.

## Acceptance matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| 11 pre-inference gates | PASS | `pod-pre-inference-gates.json` |
| A2 startup/evidence race repair | PASS | evidence mirror established before the guarded stop; controller export completed |
| Object max-event diagnostic | MEASURED, NOT ACCEPTED | Pod-local max 277→382; container max delta 0; 1 GiB limit unchanged |
| Object OOM / full PSI | PASS | all OOM counters 0; maximum object full PSI avg10 0 |
| Fresh workflow | FAIL | stopped during first fixture 06 execute group |
| Business ingestion | FAIL | `failed / activity_budget_exhausted`, `processing_complete=false`, zero registered pages |
| Restored / exact replay | NOT RUN | fresh workflow did not pass |
| Group/concurrency baseline | NOT ACCEPTED | no complete fresh result |
| Cleanup and evidence sealing | PASS | controller forensic export complete; supervisor absent; 32 Deployments off; PVC retained |

## Stop cause and ordering

The fresh workflow started and its prepare Activity completed, producing a 28-page
plan. The first execute group then launched parser PID 131. Worker evidence shows
the parser at `RapidOcrModel` while the worker cgroup rose to about 1.57 GiB.

At epoch `1790609323.2098482`, the outer controller observed node full PSI avg10
`0.18`, available memory `4204961792`, and no VM OOM. It recorded
`outer VM runtime PSI guard breached` and signalled the runner. The worker observed
the same PSI value about 30 ms later; it subsequently reached
`checkpoint_commit` while sealing the interruption path. Temporal received the
cancel request at `2026-09-28T15:28:43.492028803Z` and completed the workflow with
the failed business result at `15:28:43.510794428Z`.

Therefore the causal classification is:

1. model loading coincided with real node-level memory stalls;
2. the unchanged outer node PSI guard initiated interruption;
3. supervisor/worker cleanup cancelled the in-flight Activity;
4. Temporal completed successfully as an execution record, but its business
   result was failed and is not ingestion success.

The Activity did not independently fail first. The object max-event exception
worked as intended: max events increased by 105 while object full PSI and OOM
remained zero, and the run continued until the separate node PSI guard fired.

## Attribution limits

Node attribution recorded 10–12 ms full-stall deltas in several half-second
windows before the stop, but cgroup PSI accounted for only a small fraction of
the node total. The trace captured allocation stalls from Python processes,
`kswapd`, `runc`, Docker, Temporal and filesystem threads near the trigger. This
establishes host-wide reclaim/allocation pressure, but does not identify one
process as the sole cause. It also does not prove the workload would complete if
the node PSI gate were relaxed.

The retained object service was at its 1 GiB boundary and the worker parser was
loading OCR models under the required 32-service topology. Both contributed to
the capacity context. Available memory above the configured floor and zero OOM
do not invalidate the PSI measurement.

## Cleanup

The repaired failure path produced a complete forensic export. Supervisor stop,
transport stop and terminal cleanup were proven. All 32 held Deployments were
restored to zero replicas with no owned Pods remaining. The trace container is
absent. The A3 evidence PVC remains Bound with UID
`287f80f7-564f-4557-b532-0b18f781df90`. Object Deployment/PVC/Pod identity and
768 MiB request / 1 GiB limit / Recreate settings remained unchanged.

## Next decision

Repeating A3 unchanged is not useful: the first OCR model load is expected to
cross the same zero-tolerance node PSI rule. Do not disable the 32-service
topology or assume more memory is required.

The next useful experiment is one diagnostic A4 with a fresh identity and prefix:
retain OOM, memory floor, worker cgroup, deadline and cleanup stops; record node
full PSI rather than aborting on the first positive avg10 sample; do not treat the
run as accepted solely because it completes. This would determine whether the
observed stalls are a bounded model-load transient or persist through the full
workflow. Changing that stop rule remains an explicit acceptance-policy decision.
