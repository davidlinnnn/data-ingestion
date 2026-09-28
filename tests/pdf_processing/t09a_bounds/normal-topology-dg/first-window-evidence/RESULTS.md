# DG: functional pass; acceptance fails on post-workload node PSI

DG ran once with fresh identity `t09a-bounds-20260928-dg`, fresh prefix,
all 32 recorded Deployments active, and the approved native object candidate
(request 768MiB, limit 1GiB, `Recreate`). There was no automatic retry.

| Check | Result |
| --- | --- |
| Admission and pre-inference | PASS; 11/11 gates |
| Wiki06, YOLO07, AIMA08, native51, restored Wiki06 | All five `processing_complete=true` |
| Full document/checks vs accepted AI/AJ references | Exact equality for all five |
| Temporal histories | Five completed workflows; no Activity failure, timeout, or cancellation event |
| Warm lifecycle | 29 groups, recycle at request 20, two parser identities, post-recycle completion |
| Worker resource gate | PASS; 1,289 complete samples, max 2,902,298,624 bytes, no PSI/OOM violation |
| Object service | max 732,614,656 bytes; avg10 0; cumulative full PSI +974us; max/OOM delta 0 |
| Outer VM during workload | No avg10/OOM stop; minimum observed available 2,946,998,272 bytes |
| Outer VM after workload exit | **FAIL**; full PSI avg10 reached 0.18 |
| Final acceptance | **FAIL**; candidate rolled back |

## Stop cause and timing

The fifth workflow completed at 08:40:46Z. The workload process exited normally
with code 0 at `1790584851.185964`. The terminal worker sample at
`1790584852.763393` still had full PSI avg10 0 and no OOM. The outer controller
then observed full PSI avg10 0.18 at `1790584858.7565372`, 7.57 seconds after
workload exit, while 5,251,751,936 bytes remained available and OOM stayed zero.

The direct trace records `iptables` tasks entering `psi_memstall_enter` through
page reads in all three `kube-system/kindnet-*` Pod cgroups immediately before
the averaged trigger. Node attribution records a 29,204us node-full interval
and 43,297us in `kindnet-p8ghw`'s cgroup. A later Python task in the node init
cgroup entered through `swap_read_folio`. Direct trace loss is zero. This proves
the rejecting pressure was outside the Q04 worker and object-service cgroups.
Whether the kindnet work was caused by DG Pod cleanup or periodic reconciliation
is unknown.

The unchanged VM guard therefore signalled the inner runner during final Pod
health/cleanup. That interruption explains `KeyboardInterrupt()` and the
runner's `owned Pod cleanup or final health proof failed`; it did not cause a
business or Activity failure. The object observer never saw positive avg10,
max, or OOM. Its +974us cumulative stall is retained as telemetry under the
approved object policy and did not stop DG.

## Tool correction and cleanup

The trace process ended normally and Docker removed its `--rm` container. The
controller then treated Docker's lowercase `error: no such object` as an error
because its absence check was case-sensitive. The one-line correction normalizes
stderr before matching. This secondary tool error does not change the VM-guard
failure.

Independent checks pass: all 32 Deployments are off with no owned Pods,
Temporal is idle, object health is 200, exact 128MiB/512MiB/RollingUpdate is
restored, the original object PVC UID remains Bound, the DG evidence PVC remains
Bound, and the trace container/private instance are absent. The fresh prefix is
retained with 914 objects. Historical prefixes and PVCs were not changed.

## Decision required before another runtime

Do not rerun DG unchanged. The evidence supports one narrow acceptance-boundary
proposal: keep the VM PSI/OOM/floor guard fatal through successful workload exit,
terminal worker sampling, and worker-child cleanup; after those three durable
proofs exist, continue node PSI attribution as telemetry while final Kubernetes
object deletion and health checks remain mandatory. Object avg10/max/OOM, worker
PSI/OOM, memory floors, deadlines, output equality, recycle, telemetry-loss and
cleanup gates remain unchanged.

That proposal changes when the VM PSI predicate is fatal, so it requires an
explicit acceptance decision. If approved, use a new DH identity/prefix, one
controlled run, fail-stop and no automatic retry. Until then #44 remains open,
#45 remains blocked, #51's accepted scoped history is unchanged, and the native
object candidate is not retained.
