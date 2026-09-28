# CP: one mixed-workload attribution window

Base:189e0b5; predecessor CG. New identity/prefix/queues/PVC use CP. Producer,
bundle, full [06,07,08,native,06] sequence,29 requests,request20 recycle, output
oracle and all existing resource/deadline guards are unchanged. No automatic retry.

CO did not reproduce CD: no global reclaim occurred in its idle/read control.
CP restores the missing real producer workload and adds ancestor-local memory
limits/events, PSI, reclaim/refault and VM counters to the existing250ms object
observer. Existing direct psi_memstall_enter/task-cgroup tracing is retained.
The additional fields are diagnostic; they do not relax or replace formal guards.

Predictions: target charge stalls with ancestor events indicate a limiting
cgroup; read/wait stacks and VM scan/refault growth without local events support
reclaim/read-wait pressure; no target event means the intermittent mechanism
remains unproven even if functional output passes. No new production fix is claimed.

Run once on existing kind with all32 historical Deployments active and temporary
object1Gi. Fail-stop and retain the first trigger. Afterwards all32 off, object512Mi,
owned worker/observer/tracer absent; retain PVC/prefix. Compare complete document
and checks JSON against accepted AI/AJ fresh references only if full work finishes.

Local validation: runner manifest/exact argv/source projection/inactive topology,
new real-sampler ancestor regression, CP activation-timeout replay, and two actual
subprocess interruption checks pass. Review against189e0b5 precedes runtime.
