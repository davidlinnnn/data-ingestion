# CQ: protection contract invalidated before workload launch

One controlled attempt, preparation bee73bd plus reviewed timeout fix44be657.
The helper applied memory.low805,306,368 bytes (768MiB) to all seven exact
object ancestors; memory.min/max and existing guards were unchanged.

At07:43:46.165562 UTC the first sample confirmed protection on all six levels
visible inside the node. At07:44:42.803418 UTC the Burstable ancestor first read0;
other levels remained768MiB. At07:44:57.440138 the real runner rejected this with
`object memory.low contract changed`. The reset occurred about56.64s after the
first sample, before workload launch. This is an intervention/setup failure,
not ingestion failure, an Activity timeout, or demonstrated insufficiency of768MiB.
No workflow or parser workload was started; no Temporal business result exists.

The systemd manager reports MemoryLow=0 for that exact Burstable slice.
Kubelet v1.34.3 is installed. The upstream v1.34 QoS manager performs a one-minute
reconciliation of QoS cgroups. The timing and affected layer are consistent with
manager reconciliation overwriting a raw cgroup write, but this run did not trace
the writer. **The specific writing process is unproven.** Logs in the reset
interval contain no entry that identifies the writer. Do not call it proved kubelet
attribution or change the guard to tolerate a lost ancestor.

Source: [Kubernetes QoS manager](https://raw.githubusercontent.com/kubernetes/kubernetes/v1.34.0/pkg/kubelet/cm/qos_container_manager_linux.go),
`periodicQOSCgroupUpdateInterval` and `UpdateCgroups`. This source is v1.34.0;
the exact installed patch implementation was not verified from remote source.

| Acceptance item | CQ result |
| --- | --- |
| Four local rollback/sibling/timeout checks; offline and actual image imports | Passed |
| Standards review | 0 findings |
| Spec review | 1 timeout/remote-writer issue fixed; re-review0 |
| Eleven pre-inference gates | Passed |
| Effective protection persists to workload launch | Failed: Burstable low reset0 |
| Five fixtures /29groups /recycle /full output equality | Not executed |
| Object full PSI / exact-target PSI calls | 0 /0; not a workload qualification |
| Cleanup and independent original-low readback | Passed |

528 object samples,max gap0.258351s,max object115,957,760 bytes. No automatic retry.
`verify_failure.py` replays the retained ancestor reset through the actual runner
and confirms it rejects before launch; this check passes. It also verifies no
Temporal outcomes and successful restoration. `verify_cleanup.py` independently
confirmed every surviving journaled ancestor returned to its original low,32
Deployments0/no owned Pods, object512Mi/Ready/health200, worker/observer/tracers
absent, private trace instances absent, and evidence PVC Bound. Missing old Pod/
container paths are recorded in restoration evidence. Historical PVCs/prefixes
remain intact. No permanent configuration or production change was made by CQ.

Raw evidence: `/private/tmp/t09a-bounds-20260927-cq`,
`/private/tmp/t09a-bounds-object-20260927-cq`,
`/private/tmp/t09a-normal-topology-20260927-cq`.

## Next bounded step

Do not repeat CQ or launch another full workload with raw-only memory.low writes.
First correct ownership of the temporary policy: evaluate the systemd runtime
MemoryLow interface for the manager-owned slice, snapshot both manager property
and kernel value, and require agreement through at least two one-minute QoS
reconciliation intervals before starting inference. Restore both representations.
This is a proposed setup correction, not a proven fix; if the manager still resets
it, retain a write-level trace rather than repeatedly reapplying the value.
No busy writer loop, kubelet disabling, new cluster, larger hard cap, or relaxed
PSI criterion is justified. Test the correction locally before a new identity.

#44 remains open and#45 blocked;#51 remains historically closed. CQ adds no new
functional acceptance. The ticket update remains a local draft.
