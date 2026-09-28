# W runtime result

W (`q04-warm-pod-cgroup-20260921-w`) ran once from commit `7d18e41`
with no automatic retry. All 11 pre-inference gates passed. The complete
`06 → 07 → 08 → native → 06` sequence finished: 29 group requests, one
request-20 parser recycle, five completed Temporal executions, and complete
page/component registration for every trial.

The combined warm/resource gate did not pass. Four of 1,425 process samples
were incomplete. Sample 1111 is a bounded confirmed child exit; samples 711
and 1065 observed child births between the before/after process scans, and
sample 745 observed a child exit plus a disappearing `/proc` read. The
sampler's earlier repair retried only direct `proc_identity` disappearance, so
these three process-set transitions remained unclassified and
`process_attribution_complete=false`. The candidate then failed with
`ValueError: process attribution incomplete`.

This is an acceptance-telemetry failure after successful ingestion, not an
Activity or workflow failure. Node and cgroup full PSI stayed at 0.00,
`oom_kill` stayed zero, available memory never fell below 5,319,372,800 bytes,
and the observed cgroup maximum was 2,501,464,064 bytes. No memory floor or
deadline stopped the workload.

Cleanup passed. The owned Deployment, Pod and ConfigMaps were removed with UID
fencing; the evidence PVC `q04-pod-cgroup-w-evidence-20260921-w` remains Bound
with UID `a901b221-e59a-4619-bca5-3b10c1149eef`; all 32 held Deployments remain
off. W does not prove the combined warm/resource acceptance row and must not be
counted as a Q04 pass.

