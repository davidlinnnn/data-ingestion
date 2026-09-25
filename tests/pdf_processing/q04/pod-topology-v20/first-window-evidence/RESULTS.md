# U — 29-group workload passed; process attribution failed on one child exit

Execution commit `2a4f92b`, identity
`q04-warm-pod-cgroup-20260921-u`, ran once with no automatic retry. All admission
and pre-inference gates passed. The fixed sequence Wiki06 → YOLO07 → AIMA08 →
native → Wiki06 completed all 29 group requests. The parser stayed on PID 131
for requests 1–20, recycled once, and used PID 1836 for requests 21–29. All five
Temporal workflows completed; pending Wiki/native graphs were recorded as
measurement-only and were not promoted to fixture acceptance.

The resource qualification then failed closed because sample 1065 was process
incomplete. It observed short-lived `fresh_owned_child` PID 1887 complete in the
preceding sample, then `/proc/1887/stat` disappeared during the next identity
scan. That sample recorded exactly one matching `exit_observed`; PID 1887 was
absent from both before/after identity inventories, and the following sample was
complete. This is a sampler race at a normal child exit, not a workload failure.
The missing PSS remains unknown, so U does not pass complete process attribution.

All 1,438 cgroup samples were otherwise readable; the incomplete sample was not
the peak. Peak attribution was complete, maximum attribution cgroup memory was
2,458,259,456 bytes, worker telemetry maximum was 2,530,975,744 bytes, minimum
available node memory was 5,278,797,824 bytes, and node/cgroup full PSI and OOM
remained zero. No memory floor or deadline fired.

Cleanup stopped both parser generations, proved scratch absent, removed the
owned Deployment, Pod and ConfigMaps with UID preconditions, and retained PVC
`q04-pod-cgroup-u-evidence-20260921-u` (UID
`ea7691ec-d26b-4e6f-bef3-38b23039d776`) Bound. Post-cleanup PSI/OOM were zero
and object health was 200.

V retries a transient `/proc` identity disappearance exactly once before sealing
the sample. Only `FileNotFoundError`/`ProcessLookupError` identity exits qualify;
persistent errors, permission errors, changing inventories and incomplete peak
samples remain failures. No resource threshold changed.

Disposition: **FAIL_PROCESS_ATTRIBUTION_ONE_BOUNDED_CHILD_EXIT_SAMPLE**. U proves
the business sequence and recycle behavior, but the combined warm/resource row
remains unproven because process attribution is not complete.
