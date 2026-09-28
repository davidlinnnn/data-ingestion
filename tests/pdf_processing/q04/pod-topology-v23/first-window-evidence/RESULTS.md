# X runtime result

X (`q04-warm-pod-cgroup-20260921-x`) ran once from commit `59ef005` with no automatic retry. All 11 pre-inference gates passed. The complete `06 → 07 → 08 → native → 06` sequence finished: 29 group requests, one request-20 parser recycle, five completed Temporal executions, and complete page/component registration for every trial.

The combined warm/resource gate did not pass. One of 1,466 samples lost PID 646 to a normal exit while reading `/proc`; its PSS is unknown. Adjacent identity-complete samples and the exact exit event bounded the transition, so cgroup resource qualification remained complete, but exact process attribution correctly remained false. The sampler did not retry because its transient allowlist omitted the emitted `cgroup_process_read_incomplete` reason. This is an acceptance-telemetry defect after successful ingestion, not a capacity, Activity, workflow, deadline or supervisor failure.

Node and cgroup full PSI stayed at 0.00, `oom_kill` stayed zero, available memory never fell below 5,322,141,696 bytes, and the observed outer cgroup maximum was 2,481,577,984 bytes. No threshold is changed for Y; Y adds only the missing reason to the existing one-retry, process-absence-only rule.

Cleanup passed. The owned Deployment, Pod and ConfigMaps were removed with UID fencing; the evidence PVC `q04-pod-cgroup-x-evidence-20260921-x` remains Bound with UID `45ede38a-e520-41b5-b6a2-6ab573a97e8b`; all 32 held Deployments remain exact and off. X does not prove the combined warm/resource acceptance row.
