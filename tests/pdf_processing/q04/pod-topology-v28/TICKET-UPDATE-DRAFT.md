Q04 AC ran once with new identity `q04-warm-pod-cgroup-20260922-ac`; no automatic retry occurred.

The sampler repair changed process read order so deepest owned descendants are read first. Its regression tests, projected-workspace preflight, offline exact-command check, and two independent code reviews passed. The earlier signal-based prototype was rejected before runtime because it could strand or signal the wrong process; none of that design remains.

Runtime results: all 11 pre-inference gates passed. All five Temporal workflows completed with `processing_complete=true`, registering 28/15/12/51/28 pages. The original 29-group warm sequence completed and parser PID 130 recycled once at request 20 to PID 1835. There was no node or cgroup PSI, OOM, memory-floor, deadline, Activity, supervisor, or ingestion failure. Minimum node available memory was 5,241,487,360 bytes; outer/inner cgroup maxima were 2,520,711,168 / 2,554,904,576 bytes. The peak sample had complete process attribution.

Q04 still does not pass. During controlled terminal cleanup, worker PID 111 exited while process sample 1399 read it. The exact exit and cgroup continuity are proven, but that sample's worker PSS is unknown; the unchanged all-sample `process_attribution_complete` gate correctly failed. The workload returned 1 and was not retried.

Cleanup passed: owned Deployment, Pod, and ConfigMaps are absent; all 32 held Deployments remain exact and off. Evidence PVC `q04-pod-cgroup-ac-evidence-20260922-ac` is retained Bound with UID `3599cdcb-dfb1-41fc-8aec-1bac4df0584b`.

Next: implement and review terminal worker/sampler synchronization that preserves continuous independent cgroup observation and never treats unknown PSS as complete. Do not rerun AC unchanged. #51 is not ready to close.
