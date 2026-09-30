# A2: object Pod memory-boundary stop after preflight

Executed commit `9808c04`, identity `t09b-calibration-20260928-a2`.
One controlled execution; no retry and no acceptance threshold change.

All 11 pre-inference gates passed, including the Deployment/Pod identity paths
repaired after A1. The object-service guard then stopped the run. Its generic
message `object-service Pod/container memory contract changed` refers here to
an event-counter change, not a changed resource limit.

At the first violating sample (1790607685.9454863 UTC epoch seconds), object Pod
memory.current was exactly 1073741824 bytes. Its local max counter rose from 193
to 241; container-local max stayed zero, both limits stayed 1 GiB, all OOM counters
stayed zero, and object/node PSI full avg10 were zero. The Pod memory.stat reported
755748864 file bytes, 285433856 anonymous bytes and 27115520 kernel bytes.

Linux defines max events as attempted crossings of memory.max that trigger
reclaim; they are distinct from OOM. File memory includes filesystem cache.
Source: https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files
This supports classifying a Pod-level max/reclaim boundary event. It does not
prove that every file byte was reclaimable, identify which request caused the
crossing, or establish sufficient inference capacity. The existing zero-delta
max-event gate correctly stopped this run under its current criteria.

## Startup evidence discrepancy

The outer cleanup summary says supervisor/workflow/inference NOT_STARTED because
the guard fired before the controller installed its incremental evidence mirror.
Read-only recovery from the retained PVC disproves the supervisor classification:

- supervisor ownership: 1790607685.5252912;
- init exit: zero;
- coordinator ownership: 1790607686.0100503;
- worker readiness: 1790607688.0433624;
- worker storage ledger: zero bytes; terminal workload/cleanup markers absent.

Temporal's query for the unique A2 workflow task queue returned no executions.
Thus supervisor/init/worker startup occurred, but no workflow execution was found
and no Activity storage calls were recorded. Do not treat the outer NOT_STARTED
summary as proof. There is a startup/guard race in the evidence and graceful-stop
path; this must be repaired before another runtime. Inference was not accepted.

## Cleanup and remaining work

The controller restored all 32 held Deployments to zero replicas and no owned
Pods. A2 Pod/Deployment/ConfigMaps were removed with identity checks. Its Bound
evidence PVC was retained (UID 54b4701d-8705-498b-a1be-ffa63f8b765a). The native
trace stopped locally and remotely; object Pod, PVC and resource settings remained
unchanged. No object restart, cache flush, memory increase or gate relaxation.

Raw evidence remains in the three A2 /private/tmp run directories and the PVC.
Selected evidence and a read-only post-stop PVC archive are retained here.
The archive is recovery evidence, not a successful terminal seal.

Next: repair the startup/guard ownership race and verify its failure path locally.
Then review whether the accepted max-event gate is appropriate for this retained
cache-heavy service; changing it is an acceptance-policy decision requiring
explicit approval. Do not simply repeat A2 or increase memory to obtain a pass.
#45 remains open: no baseline performance, group/concurrency comparison or recovery
cost has been accepted. The prior diagnostic zombie caveat remains unchanged.

## Follow-up repair

The T09b adapter now treats supervisor ownership and complete transport identity
as separate startup milestones. While coordinator ownership is still being
published, the node/cgroup runtime guard remains active and the object-service
qualification waits for the evidence mirror. Once the mirror exists, any earlier
object event is still observed and stops the run. Failure cleanup uses confirmed
supervisor startup for owned stop and classification, so this A2 timing is
`START_CONFIRMED / INCOMPLETE`, never `NOT_STARTED`.

The regression test replays the retained A2 PVC archive, removes coordinator
ownership to reproduce the 65 ms partial-identity window, and verifies the
classification. This is a local repair only; it did not launch or accept another
runtime and did not change the max-event gate.
