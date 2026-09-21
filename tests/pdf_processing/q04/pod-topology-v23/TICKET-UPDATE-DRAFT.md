Q04 X ran once with no automatic retry. All 11 pre-inference gates passed, and
all five workflows completed the original `06 → 07 → 08 → native → 06`
sequence: 29 group requests, one request-20 parser recycle, complete page and
component registration.

The acceptance result is still **not passed**. One of 1,466 process samples lost
PID 646 to a normal exit while reading `/proc`. Adjacent complete samples and the
exact exit event bounded the transition, but exact PSS remained unknown. The
sampler did not retry because `cgroup_process_read_incomplete` was missing from
the existing transient retry allowlist. This was an acceptance-telemetry failure
after successful ingestion. Node and Pod cgroup full PSI stayed at 0.00, all OOM
counters stayed zero, minimum available memory was 5,322,141,696 bytes, and no
memory floor or deadline fired.

The repair adds only that missing reason to the one-retry path. Retry still
requires process absence (`FileNotFoundError`/`ProcessLookupError`), preserves
both observations, and may not reduce memory, PSI or OOM evidence. No resource
threshold changed. Local regression, projected-workspace, launch-contract,
interrupt and cleanup tests pass; both spec and standards reviews found no
issues. Y is prepared under a new identity/prefix/PVC for one controlled run.

X cleanup passed: owned Deployment, Pod and ConfigMaps are absent; evidence PVC
`q04-pod-cgroup-x-evidence-20260921-x` remains Bound with UID
`45ede38a-e520-41b5-b6a2-6ab573a97e8b`; all 32 held Deployments remain exact and
off. Historical evidence and object prefixes remain intact.
