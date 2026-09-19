# Q04 independent worker-cgroup preparation

Status: **offline preparation only**. This plan does not authorize applying the
manifest, creating a Pod or cgroup, starting a Workflow, running inference,
publishing results, or restoring any of the 32 held Deployments.

## Recommended topology

Use the existing `pdf-t09a-validation` Temporal and MinIO services, and create
one run-owned Activity Deployment on
`internal-a2a-vs6-local-worker2`. The deployment is
`q04-pod-cgroup-a-activities`, is rendered with `replicas: 0`, uses one container,
and is selected only by `q04-run=q04-pod-cgroup-a`. The controller and Workflow
worker remain outside this Activity container. The Activity worker therefore has
its own container cgroup while continuing to use Q04's existing single-Activity
submission order.

The immutable image is
`docker.io/library/pdf-t08-runtime@sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
The exact candidate producer is mounted read-only from
`q04-pod-code-a6501b471bd3193a`; the Q04 worker/telemetry harness is mounted
read-only from `q04-pod-harness-922b27bd25a33c18`. Their per-file hashes are in
`SOURCE-MANIFEST.json`, and `pod_topology.py` rebuilds the complete inactive
Kubernetes List byte for byte.

The initial queue pair is:

- Workflow: `q04-pod-cgroup-a-workflows`
- fixture-07 Activity: `q04-pod-cgroup-a-07`

No earlier worker polls either queue. A later six-fixture phase may reuse this
Deployment shape and immutable sources, but every additional fixture queue and
run identity must be frozen in its own reviewed runner. This preparation does
not authorize those runs.

The worker mounts disk-backed `emptyDir` volumes of 2 GiB at `/scratch`, 256 MiB
at `/q04-control`, and 512 MiB at `/tmp`. The Pod requests 3 GiB and is limited
to 4 GiB of ephemeral storage. The control volume receives only the exact run
config and worker-owned evidence. Source, models and object-store results do not
use it. The model cache remains the image's verified
`/experiment/PROTOTYPE-wipe-me/hf`; it is not a hostPath claim.

The Pod does not mount a service-account token. It runs as UID/GID 1000 with a
runtime-default seccomp profile; the container drops every Linux capability,
forbids privilege escalation, and keeps its root filesystem read-only. Only the
two named object-store credential keys are projected from `store-access`. The
future no-inference preflight must prove the pinned image, model cache and
mounted sources are readable as UID 1000 and that all writes stay inside the
three owned volumes. A failure stops before workflow submission.

## Resource contract

The container requests 4 GiB and has a 5 GiB hard limit. The acceptance sampler
guard remains **4 GiB**. These are distinct:

- crossing 4 GiB fails qualification and begins owned cleanup;
- the extra 1 GiB is only cleanup/observation headroom;
- reaching 5 GiB can still cause container OOM before graceful cleanup, so any
  `oom`, `oom_kill`, `oom_group_kill`, restart or exit 137 is a retained failure;
- a separate cgroup does not make model or PDF page-cache charges disappear.
  First-touch and reclaim may charge them to this container again.

Before any Pod is scaled above zero, observe for at most 180 seconds and require
60 consecutive seconds with VM `MemAvailable >= 4,831,838,208`, VM full PSI
avg10 equal to zero, VM `oom_kill=0`, healthy Temporal/MinIO, no running work on
the new queues, all 32 held Deployment UIDs unchanged at replicas/ready zero,
and no prior `q04-run=q04-pod-cgroup-a` Pod or CRI container. During work, stop
on VM full PSI avg10 above zero, any VM/cgroup OOM increment, Pod restart or UID
change, Activity cgroup `memory.current > 4,294,967,296`, or VM
`MemAvailable < 1,610,612,736`. No threshold is lowered and no failure retries.

The read-only snapshot found 12,526,280,704 memory bytes allocatable,
2,468,347,904 memory bytes already requested, 8,754,880,512 bytes
`MemAvailable`, PSI avg10 zero and VM OOM zero. It also found
1,962,694,664,192 ephemeral-storage bytes allocatable and zero existing
ephemeral-storage requests. One 4 GiB memory request plus one 3 GiB ephemeral
request therefore fits both scheduler dimensions on the current 12 GiB Docker
VM snapshot. The live admission guards remain required, so this is not a
capacity promise. No Docker RAM increase is currently required. If the same
admission cannot be re-established, do not apply or start the worker; return to
main to schedule a larger Docker VM or another Linux node.

## Fixed future runtime sequence

The following sequence is review material. It must be placed behind a new
explicit authorization and a new runner identity before any command is run.

1. Rebuild `WORKER.yaml` and `SOURCE-MANIFEST.json` with `pod_topology.render`,
   require exact equality with the committed files, and verify the image content
   ID remains `sha256:60b91ce18ac0ef8d4efdec17e79946278f44f62c9fc346b7e19214d8b8ad10ce`.
2. Repeat the admission checks above. Record coordinator, node, service, Secret
   and all 32 held Deployment UIDs. Do not read or print Secret values.
3. Apply the Kubernetes List while it still has `replicas: 0`. Record the new
   ConfigMap and Deployment UIDs, then scale only the exact Deployment UID to one.
   Before submission, prove the read-only-root and UID-1000 file contract with a
   no-inference preflight. Require one ready Pod, one container, restart count
   zero, the pinned image ID, `memory.max=5 GiB`, and fresh zero OOM counters.
4. Copy the run config into `/q04-control` and start exactly
   `/experiment/.venv/bin/python /q04-harness/worker.py` for fixture 07. The
   controller must retain the Pod UID, container ID, worker PID/start identity,
   config hash and queue names before submission. A remote-evidence adapter must
   copy the 250 ms stream back without interpolation; transport loss fails closed.
5. Run a Pod-local strict collector against the Activity container cgroup. Keep
   process PSS unknown on read/exit races and apply the confirmed-exit
   classification only under the policy frozen by `e99f180`. The live run must
   still prove cgroup readings, lifecycle exits, cleanup markers and the 4 GiB
   guard; retained historical evidence cannot substitute for this measurement.
6. Execute only fixture 07 fresh, restored with a new request, and exact replay.
   Reuse the retained source-review and graph oracle identities to avoid another
   visual review, but compare every new complete graph and source-evidence record.
7. For the later #51 drain gate, use the same Deployment and delete the exact old
   Pod with a UID precondition while an owned group is active. Require a new Pod
   UID, retained completed groups, retry only for the interrupted group, exact
   final graph, uninterrupted VM telemetry, and separate identity-bound cgroup
   streams covering each old/new Pod's live interval. Measure and retain the
   replacement gap; do not claim cgroup continuity after the old cgroup ceases
   to exist and before the replacement cgroup is created.

The existing Q04 process-mode runner cannot be used unchanged: its local
collector would measure the controller cgroup and its Pod mode assumes a shared
filesystem. Before runtime authorization, the new runner must stage the config
to `/q04-control`, stream worker/collector evidence back to the controller, and
bind controller-facing Temporal/MinIO access separately from the Pod's in-cluster
addresses. This is a required implementation gate, not runtime approval.

## Stop and cleanup

Every exit path stops submission first. It next patches the exact Deployment
from replicas one to zero with JSON Patch `test` operations for both its recorded
UID and `resourceVersion`; a failed test stops cleanup for review rather than
touching another object. Only after the Deployment is inactive does cleanup
terminate the exact worker identity and delete the recorded Pod with a UID
precondition, preventing the controller from replacing it. The runner then
requires:

1. no Pod with `q04-run=q04-pod-cgroup-a`;
2. `crictl ps --state Running --label io.kubernetes.pod.uid=<old UID>` returns no
   container on the recorded node;
3. `/var/lib/kubelet/pods/<old UID>/volumes/kubernetes.io~empty-dir/scratch` and
   the corresponding `control` directory are absent;
4. no running Workflow on the owned queue and no worker PID/start identity;
5. VM and cgroup OOM counters unchanged, Temporal/MinIO healthy, and all 32 held
   Deployment UIDs still at replicas/ready zero.

Delete the owned Deployment and immutable ConfigMaps only with recorded UID
preconditions after exporting their specs, logs, sample stream and cleanup
proof. Preserve object-store evidence and all historical reviewed-B artifacts.
Do not restore the 32 held Deployments.
