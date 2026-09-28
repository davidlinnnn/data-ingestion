# S — Pod started; pre-inference source projection failed

Execution commit `78063af`, identity
`q04-warm-pod-cgroup-20260921-s`, ran once with no automatic retry. Outer
admission passed 48 samples over 60.39 continuous seconds with minimum available
node memory 7,901,798,400 bytes, zero node PSI and zero OOM.

The inactive objects were created, the Deployment identity gate passed, and one
worker Pod became Ready on the expected node with the pinned image. The first
Pod-local pre-inference command then failed while importing
`pod_preflight_s.py`: its dynamically loaded dependency
`pod_preflight_q.py` was absent from `/workspace`.

The source manifest proves the cause directly: it contains
`pod_preflight_s.py` and `pod_preflight_p.py`, but not
`pod_preflight_q.py`. Local tests had imported from the full checkout, which
masked the incomplete ConfigMap projection. No workflow, Activity, workload or
inference started. This stop is therefore an acceptance-harness source
projection defect, not a PSI, OOM, capacity, Temporal or ingestion failure.
Capacity during the intended warm sequence remains unknown.

Cleanup scaled the Deployment to zero, deleted the Pod with its UID
precondition, proved its emptyDirs absent, and removed the Deployment and both
ConfigMaps with UID preconditions. PVC
`q04-pod-cgroup-s-evidence-20260921-s`, UID
`eab1d381-3af7-40f6-ab3f-32bd4ef2957f`, remains Bound and retained. Final node
PSI/OOM were zero. An independent live check found no S runtime, all 32 held
Deployments exact and off, Temporal healthy and idle, and object health 200.

T adds the missing transitive preflight source and reconstructs the exact
projected workspace in a regression before importing its preflight. T has a new
identity, prefix, queues, Deployment and PVC. All resource, PSI/OOM, floor and
deadline gates remain unchanged.

Disposition: **FAIL_ACCEPTANCE_HARNESS_SOURCE_PROJECTION_WORKLOAD_NOT_STARTED**.
S proves no acceptance row and must not be retried. Q04 and #51 remain open. T
requires a new explicit authorization after S's fail-stop.
