# Historical reviewed YOLO fixture-07 candidate window

This is the retained plan for the consumed `yolo-reviewed-b` execution. That run
ended `FAIL_ATTRIBUTION_CONTRACT_NOT_PROMOTED`; this document records main's visual review
of pages 2→3 and 8→9 and integrates the exact fixture-local equivalence bundle
into the next candidate consumer. It does not change the historical reference,
reclassify the retained graph/resource failures, create a general normalization
rule, or authorize runtime.

The window is limited to fixture 07 on all original pages 1–15 and the fixed
sequence fresh, restored with a new request, and exact replay of the fresh
request. The candidate state changes only `parser_budgets.max_requests` from 20
to 1, so the warm parser is recycled after each five-page group. Group size,
concurrency, source, producer, method, 4 GiB ceiling, OOM/PSI guards and the
250 ms collector remain fixed. This is a window-local resource hypothesis; its
high-water trend does not prove retention and does not predict a pass.

The adapter delays `fresh-index.json` and final `phase-complete.json` until all
three cases pass the fixture-local graph/oracle checks and every retained 250 ms
cgroup reading is complete, at or below 4 GiB, includes zero-valued `oom`,
`oom_kill`, and `oom_group_kill` counters and zero full PSI avg10, and the final
sample contains both `owned_cleanup_finished` and `post_cleanup_sample`.
Process PSS attribution remains a separate signal. A sample with an exited PID
stays process-attribution incomplete and keeps its PSS unknown; it may preserve
cgroup qualification only when the adjacent samples prove the same process
identity, the same cgroup, bounded timing, an exact exit event, no PID reuse,
and complete cgroup readings. Missing or denied reads, unknown descendants,
peak-sample gaps and identity ambiguity fail closed. A failure retains the
pending index and evidence but does not integrate the fresh row. There is no
automatic retry.

Before promotion, the adapter also inspects the accepted result for each mode:
all three must retain the same three five-page operations, and fresh must show
recycle/restart counts 1, 2, 3 with a different parser PID for each adjacent
group. The collector must also observe each exact parser identity exit before
assembly. `termination_reason=request_recycle` alone is insufficient, and a
warm parser present at assembly fails the contract. A handoff marker is required
only when a live warm parser actually survives into a handoff. Restored and
exact replay must reuse the same operations without new parser work. This check
enforces the unchanged sequential, one-activity worker contract rather than
treating `max_requests=1` as sufficient evidence.

The 1,500-second process-mode lease retains the existing admission gates and
budgets: at most 180 seconds outer observation, 60 continuous seconds at 4.5 GiB
and PSI=0, 3 GiB per-case admission for 60 seconds, 825 seconds workload and the
last 300 seconds for cleanup. All 32 historical Deployments must keep their
reviewed UIDs at replicas=0/ready=0; the launcher never restores them.

Do not execute this consumed identity again. The command that launched it is
historical evidence and is intentionally omitted. Any future live proof needs a
new phase, remote root, prefix, output, lock and explicit authorization bound to
the corrected process-attribution policy.

At launch, the remote root, prefix, phase, output, capacity, reservation,
release, runner, log and lock identities were required to be absent. The run
stopped without a retry and returned its resource result to main. Any future
fixture-07 proof should use a dedicated cgroup or Linux host if main rejects the
observed 8.844 MiB margin, rather than extending lifecycle tuning. Other
fixtures require their own reviewed resource policy and authorization; this
configuration must not be copied into the remaining batch implicitly.
