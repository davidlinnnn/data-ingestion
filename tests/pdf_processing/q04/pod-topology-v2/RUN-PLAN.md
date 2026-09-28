# Q04 YOLO fixture 07 Pod/PVC window C

Status: **offline prepared; runtime not authorized**.

## Fixed identity and scope

- Runner: `run_yolo_pod_cgroup_c.py`; run identity
  `q04-yolo-pod-cgroup-20260919-c`; output
  `/private/tmp/q04-yolo-pod-cgroup-20260919-c`.
- Kubernetes context `kind-internal-a2a-vs6-local`, namespace
  `pdf-t09a-validation`, node `internal-a2a-vs6-local-worker2`.
- Inactive Deployment `q04-pod-cgroup-c-activities`, immutable candidate
  ConfigMaps named by source-set hashes, and new retained 1 GiB PVC
  `q04-pod-cgroup-c-evidence-20260919-c`.
- Object prefix `q04/yolo-pod-cgroup-20260919-c/`, workflow queue
  `q04-pod-cgroup-c-workflows`, activity queue `q04-pod-cgroup-c-07`.
- Fixture 07 only, in order: fresh, restored, exact replay. No automatic retry.
  The fixed input bundle remains `/private/tmp/q04-inputs-yolo-lifecycle-v1`;
  its `inputs.json` hash is recorded in the runner manifest. The complete
  producer and harness file hashes are recorded in `SOURCE-MANIFEST.json`.
  The candidate method and oracle are compatibly reused, while its internal
  phase, state paths, outer run, Kubernetes objects, PVC, queues, object prefix
  and execution identity all use the new `c` scope.

## 1,500-second lease

Outer admission observes for at most 180 seconds and requires 60 continuous
seconds at or above 4,831,838,208 available bytes, PSI full avg10 zero, VM OOM
kill zero, fixed node/boot identity, healthy idle T09a, and the 32 held
Deployments still at zero. Each case retains its separate 3 GiB/60 second
admission. The workload budget is 825 seconds and the final 300 seconds are
reserved for cleanup. The Pod cgroup guard is 4 GiB, its hard limit is 5 GiB,
the VM runtime floor is 1.5 GiB, and resource sampling remains 250 ms.

## Mandatory pre-workload gates

The Pod must retain the exact Deployment/ReplicaSet/Pod UID chain, node,
restart count zero and container ID. The image spec must be the fixed
`docker.io/library/pdf-t08-runtime@sha256:8ffa...` repository manifest.
Committed local OCI and CRI evidence binds that single-platform manifest to
config `sha256:60b...` and platform `linux/arm64`. Kubernetes `imageID` is
accepted only as a typed representation proved by that chain; wrong repo,
manifest, config, platform, or an unbound bare digest fails closed.

No PDF is copied, no object prefix is populated, and no workflow or inference
starts until readiness, image identity, PVC identity/mount permissions, frozen
model/package checks and the no-inference preflight pass. Any failure stops the
workload path and enters cleanup without retry.

## Evidence and cleanup

The controller mirrors allowlisted evidence incrementally and verifies the
terminal archive, source attribution, complete graph, fresh/restored/replay
oracles and exact replay. Cleanup uses UID-fenced scale/delete, 60-second Pod
termination, CRI and emptyDir absence, and deletes only this run's Deployment
and ConfigMaps. The new PVC is retained with its exact PVC/PV identity. The old
empty PVC and all 32 held Deployments remain untouched. Uncertain cleanup is
`NEEDS_INTERVENTION`; force deletion is forbidden.

The preflight B `FAIL_IMAGE_ID_CONTRACT` and the first window's readiness
failure remain immutable historical results with different cause boundaries.
This plan does not reinterpret either run.
