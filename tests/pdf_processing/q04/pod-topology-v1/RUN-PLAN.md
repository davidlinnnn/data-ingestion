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
read-only through the hash-named harness ConfigMap recorded in
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
at `/q04-control`, and 512 MiB at `/tmp`, plus the run-named 1 GiB RWO PVC at
`/q04-evidence`. The Pod requests 3 GiB and is limited to 4 GiB of ephemeral
storage. `/q04-control` receives only the private input bundle and capacity
record. All state and evidence records use `/q04-evidence`; parser scratch stays
on `/scratch`. Source, models and object-store results do not use the claim. The
model cache remains the image's verified
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
3. Atomically `create` the two immutable ConfigMaps, the run-named PVC and the
   Deployment while it still has `replicas: 0`. Record only UIDs returned by
   successful creates; an
   `AlreadyExists` response proves no ownership and stops the run. Then scale
   only the exact Deployment UID to one.
   Before submission, prove the read-only-root and UID-1000 file contract with a
   no-inference preflight. Require one ready Pod, one container, restart count
   zero, the pinned image ID, `memory.max=5 GiB`, and fresh zero OOM counters.
4. Require the claim to be Bound to a PV whose claim UID, namespace and node
   affinity match the created PVC and pinned node. Persist the PVC/PV/node and
   UID/GID/fsGroup recovery identity on the claim. Copy the fixed private
   fixture bundle and capacity record into `/q04-control`, then start exactly
   the `workload_argv` frozen in
   `RUNNER-MANIFEST.json`. The outer controller retains Pod UID, container ID,
   supervisor PID/start identity, capacity/config hashes and queue names before
   submission. The remote-evidence adapter copies only complete byte ranges
   from `/q04-evidence` and
   complete JSONL records; sequence, offset, digest, identity or transport-gap
   failure closes the run. Transport excludes the staged input bundle and runs
   independently of the 250 ms VM sampling loop. Every envelope verifies live
   supervisor PID/start ticks and adopted config digest, carries total byte
   extent plus EOF, and required files must be complete before PASS.
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
filesystem. `pod_workload.py` therefore runs the measurement controller and its
single-concurrency Activity worker inside the same worker Pod cgroup. The outer
runner talks only to the Kubernetes API, the worker2 VM view, and the coordinator
health probe. The Pod config independently binds Temporal to `temporal:7233` and
MinIO to `http://objects:9000`; it never inherits a controller-local endpoint.
The private bundle is copied explicitly, and incremental evidence is streamed
from `/q04-evidence` without a shared-filesystem assumption. The claim is the
durable source; the controller mirror and archive are verified exports.

## Implemented runner and fixed budget

The single-use runner is
`tests/pdf_processing/q04/sentinel/run_yolo_pod_cgroup_a.py`. Its new identity
is `q04-yolo-pod-cgroup-20260919-a`, phase `yolo-pod-cgroup-a`, object prefix
`q04/yolo-pod-cgroup-20260919-a/`, and local output
`/private/tmp/q04-yolo-pod-cgroup-20260919-a`. It accepts only fixture 07 and the
ordered modes fresh, restored with a new request, and exact replay. Parser
`max_requests=1`, one Activity at a time, the reviewed graph equivalence, the
250 ms Pod-local collector, the 4 GiB qualification guard and 5 GiB container
hard limit are fixed. No automatic retry is implemented.

The 1,500-second lease reserves at most 180 seconds for outer admission, 825
seconds total for Pod-local init plus all three modes, and the final 300 seconds
for evidence capture and cleanup. The remaining 195 seconds cover inactive
apply, bundle transfer, readiness and the no-inference UID-1000 preflight. The
runner stops new work when that envelope cannot be preserved. Every wait is
capped by the same absolute lease end. The Pod-local controller starts
cooperative drain inside its 825-second allocation; it does not add a second
grace period. Every record is committed by flush, file fsync, atomic replace and
directory fsync. The terminal manifest is written only after file/directory sync
and read back with the full inventory. If final controller export fails, the
runner still deletes the exact Pod and source objects and retains the PVC for
separately authorized read-only recovery.

This historical plan was executed once. `historical_exact_single_run_command`
in `RUNNER-MANIFEST.json` records that invocation, while
`exact_single_run_command` is now `null`. The consumed command, identity,
authorization digest and output path must not be reused. Importing the runner
or invoking `--offline-check` is local-only and cannot create Kubernetes
resources.

The consumed command historically performed the following mutable operations.
A newly reviewed future runner would require separate approval for any of them:
upload private immutable ConfigMaps, create its own evidence volume and inactive
Deployment atomically; scale only its recorded UID/resourceVersion from zero to
one; copy the private fixture bundle and
capacity record into the owned `emptyDir`; create new-prefix object-store
records and run the three workflows; then scale to zero and delete only the
recorded Pod, Deployment and ConfigMaps with UID preconditions. The PVC has no
owner reference and is never auto-deleted.
The earlier rejected server-side dry-run must not be retried. The local JSON
parse and client rendering checks are not Kubernetes schema or admission proof.

The three mode-level worker generations are normal start/stop phases inside one
unchanged Pod UID. They are not Pod recovery and are not the #51 drain proof.
Actual drain qualification requires deletion of the exact old Pod UID during an
active owned group, a distinct replacement Pod UID and separate old/new cgroup
streams. That later experiment remains outside this runner.

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
preconditions. Retain the exact PVC even when controller transport or archive
export fails. Re-read its UID and, once bound, its PV UID/node affinity before
claiming cleanup success. API unreachability or an unverifiable Pod/PVC identity
sets `NEEDS_INTERVENTION`; it does not assert that runtime stopped. A later
recovery window must mount the exact claim read-only on the recorded node,
record its permissions and UID/GID/fsGroup, run terminal-manifest inventory
readback, and copy evidence without starting Temporal or inference. Claim
deletion requires a separate destructive authorization. Preserve object-store
evidence and all historical reviewed-B artifacts. Do not restore the 32 held
Deployments.
