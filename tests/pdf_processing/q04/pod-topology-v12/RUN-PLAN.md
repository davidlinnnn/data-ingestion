# One M controlled window

Authorized by the user's same-session continuation on 2026-09-20. Use existing
kind-internal-a2a-vs6-local / pdf-t09a-validation / worker2, exact held 32 Deployment
UIDs at zero and preserve every historical PVC/prefix. New identity
q04-yolo-pod-cgroup-20260920-m, prefix q04/yolo-pod-cgroup-20260920-m/.

Freeze source and review first. Recheck live identity/health and unchanged outer
admission. Start two persistent Python lanes before the workload/collector; keep
them alive through measurement. Capture their readiness before inference. The
VM lane and evidence lane use existing programs, schemas, sample cadence and
identity fences. Any channel failure stops the window without reconnect/retry.

Unchanged: 4.5GiB/60s outer admission, 3GiB/60s case admission, 1.5GiB available
floor, node full PSI zero, OOM unchanged, cgroup 4GiB sampled guard / 5GiB limit,
1s measurement gap, 2s evidence pulls / 5s receipt gap, 1500s total / 825s workload
/ 300s cleanup. The attribution classifier and process completeness are unchanged.

Replace readinessProbe exec with the identical startupProbe: it must pass before
Pod Ready, and performs no further exec during attribution. All actual runtime
guards remain unchanged.

Run fixture 07 fresh -> restored -> exact replay only while preceding checks pass.
On any failure seal/export with J's strict forensic path; retain original failure,
stop both channels, remove owned runtime with UID fences, retain M/historical
PVCs, verify idle health and 32 held Deployments. Do not rerun M.

Only M's workload process tree disables THP, with mandatory readback and an
immutable evidence record before init. This is a runtime experiment for L's
direct reclaim; its cause remains unproven. Record node compaction and allocation
counters in every outer sample. Never modify global sysfs.
