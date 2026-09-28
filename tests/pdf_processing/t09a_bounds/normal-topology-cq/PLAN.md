# CQ: one reversible workingset-protection window

Base:6268645. CP proved exact MinIO workingset read/wait PSI before controller
cancellation, without hard-limit/OOM events. CQ changes only temporary memory.low:
768MiB along the exact object cgroup and ancestors through the Docker parent.
This is one hierarchical allowance, not additional memory per level. memory.min
stays zero, object and Pod memory.max stay 1Gi during the trial. Existing sibling
protection must be zero. Journal original values before writes; restore on partial
setup failure, runner cleanup and outer fallback; independently read back cleanup.

Use existing kind, all32 normal-topology Deployments temporarily active, same
producer/bundle/full [06,07,08,native,06] sequence,29 groups and request20 recycle.
Retain all guards, deadlines and full document/checks JSON oracle. Fresh CQ identity,
prefix and PVC; one execution, fail-stop, no automatic retry. Prior user approval
covers this temporary intervention and normal-topology trial.

Prediction: protecting the object workingset reduces its reclaim/read-wait PSI.
Protection may shift pressure to siblings; VM/worker guards remain authoritative.
A pass is bounded evidence, not proof of universal capacity or a permanent policy.
Failure is classified using retained samples and exact target PSI call traces.

Afterwards restore every written memory.low to its original value, all32 off,
object512Mi Ready/healthy, no owned worker/observer/tracer. Retain PVC/prefix and
historical evidence. No ticket closing or permanent default change in this trial.

Required local checks: applied-write failure rollback, hierarchy/readback/sibling
rejection, complete offline contract and runtime-image imports. Two-axis code
review against6268645 precedes runtime. Existing interruption path is unchanged.
