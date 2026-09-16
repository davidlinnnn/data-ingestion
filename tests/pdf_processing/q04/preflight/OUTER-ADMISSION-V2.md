# Q04 outer capacity-owner admission v2

This procedure applies only to a future, separately authorized runtime window.
It does not authorize a workflow, inference, service pause or retry. Historical
trial-C runner and evidence remain immutable; a future runner must use new phase,
capacity, reservation, output and log paths.

## Continuous qualification

Use `outer_admission.observe_capacity` before starting a worker or submitting a
workflow. The current proposed outer policy is:

| Field | Value |
| --- | ---: |
| Available memory | at least 4,831,838,208 bytes (4.5 GiB) |
| Full memory PSI avg10 | exactly 0 |
| Required continuous interval | 60 seconds |
| Maximum observation interval | 180 seconds |
| Sampling interval | 1 second |
| Maximum telemetry age or gap | existing active limit, currently 3 seconds |
| Coordinator cgroup ceiling | existing active limit, currently 3 GiB |
| Cleanup reserve | existing approved value, currently 300 seconds |

A low-memory or positive-PSI sample resets the continuous interval. Every sample
before and after a reset remains in the append-only JSONL evidence. Passing samples
on opposite sides of a reset are never added together. A sample at the exact
monotonic observation deadline may complete the interval; no later sample is read.

The following conditions reject immediately: new VM or cgroup OOM, unavailable,
incomplete, stale, future-dated or over-gap telemetry, cgroup ceiling violation,
coordinator identity drift, or reservation/ownership drift. They do not wait for
recovery. A future runner must make its identity callback verify the expected
coordinator UID and the live reservation holder PID/create-time pair on every
sample. Both adapters must use bounded local reads only; they must not perform an
unbounded network call. The helper rechecks the monotonic deadline after identity
verification and after sampling, and it does not start sampling if identity
verification used the remaining observation or lease budget. Loss of `kubectl
exec` is also failure, never admission success.

## Lease accounting

Observation time is part of the overall approved capacity lease. The helper derives
both its observation deadline and latest workload start from a monotonic clock. At
entry, the lease must still fit:

```text
60-second qualification + minimum workload budget + cleanup reserve
```

At success, the entire declared minimum workload budget and cleanup reserve must
remain. If not, admission rejects without launching work. The maximum 180-second
observation bound never extends a lease. For example, a 1,200-second lease with an
825-second workload bound and 300-second cleanup reserve permits at most 75 seconds
before workload start. Using the full 180-second observation would require at least
1,305 seconds plus setup and cleanup-verification margin. Main and the capacity
owner must approve those values for each new run.

## Future runner adapter

The future versioned runner supplies real adapters at the helper seam. It must open
a new evidence file in exclusive mode and flush every recorded sample:

```python
from outer_admission import OuterAdmissionPolicy, observe_capacity
from telemetry import sample

policy = OuterAdmissionPolicy(
    available_bytes=4_831_838_208,
    continuous_seconds=60,
    observation_seconds=180,
    sample_interval_seconds=1,
    max_sample_gap_seconds=capacity["max_sample_gap_seconds"],
    max_cgroup_bytes=capacity["max_cgroup_bytes"],
    expected_vm_oom_kill=approved_vm_oom_baseline,
    expected_cgroup_oom_kill=approved_cgroup_oom_kill_baseline,
    minimum_work_seconds=approved_workload_bound,
    cleanup_seconds=capacity["cleanup_seconds"],
)

with evidence_path.open("x", buffering=1) as stream:
    def record(row):
        stream.write(json.dumps(row) + "\n")
        stream.flush()

    summary = observe_capacity(
        policy,
        lease_ends_at=capacity["ends_at"],
        sample=sample,
        verify_identity=verify_current_identity_and_reservation,
        record=record,
    )

# Only this return path may start the worker and submit the first workflow.
start_authorized_workload(summary)
```

`OuterAdmissionRejected` is a terminal outcome for that attempt. The runner records
its reason and retained samples, enters owned cleanup, releases its reservation and
exits nonzero. It does not call the workload adapter again.

## Waiting versus retry

The bounded observation is one pre-work admission attempt. Resetting the qualifying
clock after an ordinary memory/PSI miss is waiting inside that attempt; no request,
workflow, worker or inference exists yet. It is not a workflow retry. Once a
workflow begins, the unchanged per-case 60-second admission and active guards still
apply, and any workflow failure remains non-retryable in the authorized window.

The 32 historical Deployments remain main-owned at zero. This helper contains no
Kubernetes scale or restore operation and grants no permission to change them.
