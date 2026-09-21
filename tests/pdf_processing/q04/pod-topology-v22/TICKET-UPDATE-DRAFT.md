Q04 warm runtime W (`q04-warm-pod-cgroup-20260921-w`) ran once without retry.
All pre-inference gates passed and all five Temporal workflows completed the
original 29-group sequence, including the request-20 parser recycle. The run
still failed the combined qualification because three transient process-set
changes remained unclassified in otherwise continuous telemetry.

This was not a PSI, OOM, memory-floor, deadline, Activity, or ingestion failure.
Node/cgroup full PSI and OOM counters stayed zero; minimum available memory was
5,319,372,800 bytes and maximum observed cgroup use was 2,501,464,064 bytes.
Cleanup is proven, the W evidence PVC is retained, and all 32 held Deployments
remain off.

The telemetry repair now retries a whole sample for process-set churn while
preserving the first observation and refusing promotion across lower memory,
PSI/OOM regression, permission failure, or ambiguous membership changes. X is
the new unique fail-stop, no-retry runtime identity. #51 remains open pending
that result.
