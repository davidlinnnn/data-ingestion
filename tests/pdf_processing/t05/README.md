# T05 supervised warm parsing qualification

The confirmed main seam remains versioned request → Temporal → object-store
registrations. Warm memory is an optimization, not recovery state. Native capture
uses one sequential converter. Assembly and preflight remain fresh interpreters.

The supervisor is a deep module at the optional `Execution.child_runner` seam;
it hides correlated transport, hard/local-progress deadlines and process reaping.
`Processing` owns one parser for its single Activity slot. Fresh diagnostic execution
is still explicit (`PARSER_MODE=fresh`), never silent fallback. There is no store or
public completion-policy change. T03 owns store hardening; T04 owns final enrichment.

## Running

Create an isolated namespace from the retained prototype storage/Temporal manifests,
then use `k8s-validation.yaml` and ConfigMaps `t05-package`, `t05-driver`, and
`t05-fixtures`, following the T02 runbook. Driver includes the T02 `verify.py`, current
worker and pinned native profile. Do not reuse old requests across producer changes.
Use the T02 driver with queues `t05-workflows` / `t05-pdf`, bucket `t05`, prefix
`qualified`, output `/tmp/t05-run`: setup, invalid, native. Copy `case.py` into
coordinator `/tmp/case.py`; `python tests/pdf_processing/t05/inject.py <case>` submits
and injects an external signal at a reported native stage. Distinct names preserve
independent evidence. `crash-*`, `hang-*`, `pod-*`, `drain-*`, `exhaust-*` select cases.
Controller polling failure is not a passed injection; retain and label failed runs.

Local focused protocol suite (real child processes, no model inference):
`PYTHONPATH=src python3 -m unittest discover -s tests/pdf_processing/t05`.
It checks SIGTERM resistance, correlation/method mismatch, hard budget despite
continuous progress and cancellation-before-cleanup. Those small cases complement,
not replace, the real-service tests.

## Provisional operating configuration

- Native only; one active parser; recycle after 100 completed group requests.
- Startup 120 s, local no-progress 180 s, hard parse 540 s from frozen T02 limits.
- Temporal policy remains 12 min attempt, 40 min total, three attempts with finite
  backoff. A SIGKILL is `child_killed_or_oom` (exit alone cannot establish actual OOM).
- SDK drain 30 s stops polling before allowing current work to finish/register.
  After grace + 5 s, a stuck worker forcibly stops its parser (TERM 5 s, KILL/reap
  5 s), removes local Activity scratch and exits. K8s grace is 60 s.
- Parser progress only advances on correlated readiness or native stage transitions;
  parent Temporal heartbeat is never counted as native progress. A silent stage can
  consume its configured allowance, but cannot run indefinitely.
- Result diagnostics carry readiness, correlation, last local progress time, child
  PID, restart/recycle count, prior termination reason and peak RSS with units.
- Requests cancelled by Temporal reap the native child before temporary directories
  exit. Publication threads may outlive coroutine cancellation; worker shutdown is
  the final isolation limit. Conditional store registration protects late writes;
  T03 supplies stronger lost-ack/race verification.

These are bounded test settings, not calibrated deployment SLAs. T09a owns sustained
long/cross-profile memory isolation and T09b group/concurrency tuning. No automatic
shared object garbage collection or canonical delivery is added.

For TERM-escalation qualification only, add `sitecustomize.py` to the driver
ConfigMap and set the Activity worker `PYTHONPATH=/driver:/app` and
`T05_IGNORE_TERM=1`. This changes native child signal disposition; the worker's
asyncio handler still performs normal SDK drain. Test-only local progress 8 s,
TERM 1 s and reap 3 s make a short stopped-child case finite. **Remove these
settings for full-paper validation:** a real table stage exceeded 8 s and correctly
exposed that experimental budget as unsuitable for the full native workload.

Diagnostic field semantics: `pid` / `request_id` / `ready` describe the current
request; `exit_code` / `termination_reason` retain the last terminated child.
`forced_kill` resets for each new request; consult the retained exit reason/code
and external signal controller when attributing an earlier escalation. `restarts`
counts process starts including the initial spawn. These are diagnostics, not
checkpoint completion or a statement that a running child has exited.
