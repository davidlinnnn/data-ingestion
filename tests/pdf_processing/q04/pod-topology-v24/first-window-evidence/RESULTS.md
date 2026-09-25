# Y runtime result

Y (`q04-warm-pod-cgroup-20260921-y`) ran once from commit `eb97a0d` with no automatic retry. All 11 pre-inference gates passed. The complete `06 → 07 → 08 → native → 06` sequence finished: 29 group requests, one request-20 parser recycle, five completed Temporal executions, and complete page/component registration for every trial.

The combined warm/resource gate did not pass. Seven of 1,501 samples retained unknown PSS during normal process exits. Five were already classified as bounded exits. Sample 1043 covered warm parser PID 131 recycling to PID 1836; sample 1499 covered worker PID 112 exiting during terminal cleanup. In both cases the conservative retry was also incomplete, but the retained first/retry observations plus adjacent complete samples prove the exact exiting identity with no PID reuse. The compact collector summary omitted those retry observations, so the classifier could not evaluate them. Exact PSS remains unknown and is not substituted.

Node and cgroup full PSI stayed at 0.00, OOM counters stayed zero, available memory never fell below 5,196,533,760 bytes, and the observed outer cgroup maximum was 2,527,735,808 bytes. No threshold changes for Z. Z only retains the failed-resample evidence in the compact summary and classifies the already supported exact-exit shapes; permission failures, changed identities, retry-time births and unattributed peaks still fail closed.

Cleanup passed. The owned Deployment, Pod and ConfigMaps were removed with UID fencing; evidence PVC `q04-pod-cgroup-y-evidence-20260921-y` remains Bound with UID `2afaaf1b-c6be-4844-9900-f5771b5f50d7`; all 32 held Deployments remain exact and off. Y does not prove the combined warm/resource acceptance row.
