# Q04 AF result

AF ran once as `q04-warm-pod-cgroup-20260922-af`; it was not retried. All 11 pre-inference gates passed. All five Temporal workflows completed with `processing_complete=true`: Wiki06 28 pages, YOLO07 15, AIMA08 12, native 51, then Wiki06 28 again. The fixed 29-group sequence and request-20 recycle completed, with equal first/last Wiki06 graph digests.

The combined warm/resource row did **not** pass. One of 1,420 samples (index 440) observed the process set change from eight to nine members while fresh child PID 585 was being created after PID 524 exited. The existing lifecycle handshake protected completion and reap but not process creation. The new child's exact PSS during that sample is unknown, so `process_attribution_complete=false` and the gate correctly stopped after business completion. No PSI, OOM, memory-floor, deadline, Activity, supervisor, or ingestion failure occurred.

The implementation now takes the same bounded lifecycle lock around fresh subprocess creation and ownership registration. Regression tests cover birth exclusion, lock timeout without spawn, cancellation, double cancellation after successful spawn, and double cancellation racing a failed spawn. AF will not be rerun unchanged; AG uses a new identity and unchanged resource thresholds.

Cleanup passed: persistent channels closed; terminal worker stop and cgroup OOM state were proven; owned Deployment, Pod, and ConfigMaps were deleted with UID preconditions. PVC `q04-pod-cgroup-af-evidence-20260922-af` remains Bound with UID `cd87dd44-a79f-4b38-9082-688a078527d6`.
