# Review correction: deployment deadline and direct test runner

The current deployment template and runbook now match actual defaults: Pod grace
60 s, SDK drain 30 s, child TERM 5 s and reap 5 s. Frozen T02 files were not changed.

A dedicated Kubernetes Pod used those exact settings and a test-only 90 s delay
before real publication. SIGTERM was sent to container PID 1 while publication was
blocked. The process exited in 31.26 s with exit code 0, after SDK cancellation,
parser reaping and empty Activity scratch. A normal replacement completed the
request on attempt 2 and its full output matched the retained native baseline.
This targeted test sends the same termination signal directly and preserves the
terminated Pod status; it is not an additional Pod-deletion experiment. Earlier
real Pod-deletion / active native drain evidence remains unchanged.

The entrypoint exits after SDK/child cleanup so asyncio cannot extend process
lifetime while joining a cancelled default-executor publication thread. The
mounted entrypoint hash was checked against the worktree and is in attribution.
The direct unittest invocation now executes all four tests, matching discovery.

Merged T04 cleanup remains an explicit integration gate: exercise active fresh OCR
and OCR publication cancellation, verify its process group is reaped and `ocr-*`
scratch removed within the same deadline. T05's current forced cleanup owns
`activity-*`; this report does not establish the combined guarantee.

No full-paper inference rerun was needed: parsing code and extraction methods are
unchanged by this deployment/runbook/runner correction. Mandatory reviewer recheck
of the delta remains pending.
