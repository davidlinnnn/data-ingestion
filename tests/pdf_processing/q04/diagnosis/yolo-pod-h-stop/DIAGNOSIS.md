# H stop diagnosis (new execution session)

H remains failed. This report adds read-only recovery evidence; it does not alter
H's runner, raw first-window evidence, PVC, object prefix or acceptance status.
The controller's exact rejecting sample remains unavailable. A separate retained
worker sample does preserve positive node PSI near the stop.

## Proven sequence (UTC 2026-09-19)

| Time | Evidence | Meaning |
| --- | --- | --- |
| 16:48:41.969624 | Temporal event 1 | Fresh workflow starts. |
| 16:48:42.077755 | event 7 | Prepare Activity completed. |
| 16:48:42.087937 | event 11 | Group 1–5 scheduled; 180s start/schedule-to-close and 15s heartbeat timeout. |
| 16:48:49.051700–49.554673 | recovered worker samples | Parser ready, RapidOcrModel then checkpoint_commit progress; retained transport had only earlier LayoutModel trace. |
| 16:48:50.157763 | original controller last saved sample | Node PSI 0; exact following rejecting sample was discarded. |
| 16:48:50.228794 | recovered attribution sample 276 | Cgroup full avg10=0.18, total=71,325 microseconds; positive Pod-local stall also observed. |
| 16:48:50.330704 | recovered worker samples | Node full avg10=0.54; available=6,709,325,824; cgroup current=1,733,328,896; VM OOM=0. |
| 16:48:50.570531 | recovered cancel_requested callback marker | Inner failure cleanup invokes owned cancellation. |
| 16:48:50.571493 | event 12, identity 108@H Pod | Matrix process requested workflow cancellation. |
| 16:48:50.584761 | event 16 | Outstanding Activity cancellation requested. |
| 16:48:50.584771 | event 17 | Workflow COMPLETED with business status failed, activity_budget_exhausted, zero registered pages. |
| 16:48:50.832424 | recovered final worker sample | Node full avg10=0.54; available=6,963,240,960; VM OOM=0. |
| 16:48:54.103233 | recovered worker-1/stopped.json | Parser and scratch absent; no sampler errors. |
| 16:48:54.315641 | recovered workload-exit.json | Matrix rc=1, timed_out=false, forced=false, automatic_retry=false. |

The recovered `fresh-07/failure.json` and `workload.log` identify the primary
inner trial exception as `ValueError: VM PSI pressure` from telemetry.check_sample.
`q04_runtime.retain_failure` calls cancel_owned before worker-stop. The recovered
cancel outcome succeeds; worker-stop records CancelledError, while final phase
cleanup has no errors and the worker ultimately writes stopped.json. The original
outer-cleanup records its own VM PSI rejection and confirmed supervisor stop;
workload-transport.log shows KeyboardInterrupt inside supervisor process.wait,
then NotADirectoryError inside cleanup_markers.

Consequently node PSI caused the inner trial abort and cancellation; the outer
PSI guard independently stopped the supervisor, whose SIGINT propagation
interrupted the ongoing matrix cleanup. The supervisor's bad worker-* glob then
prevented cleanup-complete.json and terminal sealing. Exact relative times of
the two guard decisions and outer signal are unknown: H did not record them.
The original 272 transported attribution samples ended before this positive
worker sample. The recovered PVC contains 293 samples: cgroup full avg10 first
became positive at 50.228794 (.18), reached .87, and accumulated 113,087 us total
stall. Its cgroup OOM counters stayed zero. Therefore the pressure was not only
an observation outside the workload cgroup. This still does not identify the
stalling task or establish the exact outer rejecting sample; the attribution
summary is incomplete and cannot qualify process-resource bounds.

There is no Activity failed/timed-out event in the exact history and the whole
workflow lasted 8.615 seconds. `processing_workflow.py` catches ActivityError and
maps a cause without ApplicationError details to activity_budget_exhausted;
cancellation of the outstanding Activity follows this generic fallback path.
That business code is not evidence of budget exhaustion. No producer change is
made in this acceptance-tool repair: changing the frozen producer would require
separate identity review. History lacks a completed group Activity, regardless
of parser checkpoint progress.

## Competing explanations and limits

1. **Tool ordering:** exact loop replay rejects but saves nothing on H; moving
   write+flush before guard preserves the same rejection. Confirmed.
2. **Mixed directory/log glob:** real worker-1 directory plus worker-1.log raises
   NotADirectoryError on H; restricting to directories seals a failed interrupted
   workload without changing its return status. Confirmed.
3. **Activity timeout:** predicts timeout/failure history before cancellation;
   absent. Rejected for this window.
4. **Inner PSI abort plus outer interruption:** predicts VM PSI primary failure,
   matrix cancellation, interrupted cleanup, eventual stopped marker. All found.
   Exact interleaving of guard reads/signals remains unknown.
5. **Memory insufficiency or unrelated VM pressure:** both can coexist with free
   memory and no OOM. No attribution of node stall to a specific task, reclaim,
   model I/O or other VM workload is established. Neither is selected as root
   cause; no capacity guarantee or kind-replacement conclusion follows.

## Guard purpose and measurement

| Check | Measurement / scope | Existing policy |
| --- | --- | --- |
| Outer admission | Docker node /proc/meminfo, /proc/pressure/memory, /proc/vmstat | 4.5 GiB available, zero full avg10, unchanged OOM continuously 60s within 180s observation |
| Inner admission | worker /proc measurements, same VM scope | 3 GiB available, zero PSI for 60s |
| Runtime VM safety | MemAvailable and node full avg10; not Pod-specific | 1.5 GiB floor, zero full avg10, unchanged OOM |
| Worker cgroup qualification | /sys/fs/cgroup/memory.current, memory.events | 4 GiB sampled qualification; 5 GiB container hard limit; OOM/kill rejected |
| Attribution | 250ms process PSS/lifecycle and cgroup memory.pressure/stat/events | complete samples, <=1s gaps, owned lifecycle and all-sample 4 GiB gate; raw PSI is attribution, not a substitute for node guard |
| Evidence transport/storage | receiver time gaps; PVC logical usage and filesystem free | 2s pulls, 5s receipt limit; 128 MiB reserve in 1 GiB evidence claim |
| Runtime deadlines | capacity and supervisor wall/monotonic clocks | 1500s window, 825s workload, 300s outer cleanup; supervisor reserves up to 180s inside workload for drain |
| Trial/Activity/parser | workflow execution capped by trial 180s and window; recorded Activity 180s/15s; parser startup120/no-progress180/terminate5/reap5 | no outer automatic retry; frozen Temporal policy allows max 3 Activity attempts, no retry observed in H |

PSI measures stalled-time percentages, not allocated bytes. avg10 is a trend,
not the current instant; raw total microseconds supports interval deltas. Cgroup
PSI covers tasks in that cgroup, unlike system /proc PSI. These facts explain why
nonzero PSI and MemAvailable/no-OOM observations are not contradictory.
Sources: [Linux PSI](https://docs.kernel.org/accounting/psi.html),
[cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html).

## Decision for I

Keep the existing kind node, image, frozen producer, reviewed fixture oracle,
max_requests=1, queues isolated, deadlines and every acceptance threshold.
Change the measurement harness: persist rejecting and terminal samples before
validation; include node and cgroup pressure raw text plus cgroup memory.stat in
the same controller sample; record sampling start/end and controller/supervisor
signal times; filter cleanup directory discovery and prove terminal sealing.
Use unique I identity, prefix and retained PVC. This changes the diagnostic
information available without claiming that the environment will pass. Stop on
first failure, do not retry. If PSI recurs, a complete sample and sealed cleanup
make the failure classifiable; node task-level cause may still remain unknown.
