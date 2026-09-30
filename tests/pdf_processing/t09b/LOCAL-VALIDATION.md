# T09b local measurement slice

## Latest controlled result: A12 selected-setting instrumentation passed

See `a12-evidence/RESULTS.md`. All five exact-output workflows, 29 groups,
request-20 recycle, two parser generations and 9,563 traffic attempts passed.
Largest returned read chunks are now measured; full retained/native buffering
remains a separate limitation. Cleanup and the retained Bound PVC were verified.
The six counted matched cells now also retain complete Temporal queue/Activity
timing reports, including every required OCR Activity. The timing summarizer's
focused regression passes and rejects retries in normal-path statistics.

The next matched recovery trial now has a local adapter in `recovery_trial.py`.
It reuses Q04's complete trial/cancellation path without editing historical Q04
files, waits for 10 durable pages and the next active group, and checks exact
retained operations and attempt-2 ranges 11–15 (group 5) / 11–20 (group 10).
Its replacement loop records node PSI under the existing A4 runtime telemetry
policy while retaining OOM, memory floor and replacement deadline checks.
The actual async trial hook is exercised locally: restoring the old first-group
comparison fails with query count 1 instead of 2 (premature drain). The fixed
hook and complete T09b suite pass: 46 tests in 7.94 seconds, using the existing
`/private/tmp/t09b-sdk-venv/bin/python` and repo `src` on PYTHONPATH.
This is not a recovery runtime result: coordinator/source projection, outer
scope, terminal reconciliation and two-worker ledger export still need wiring
and review before the first matched interruption is admitted.

## Latest controlled result: B5 group-10 diagnostic passed

See `b5-evidence/RESULTS.md`. B5 completed all five exact-output workflows,
16 groups and one parser generation without recycle. Temporal business results
and 10,016/10,016 traffic attempts reconcile. There was no OOM; object full PSI
avg10 remained 0.00. B5 is `PASS_DIAGNOSTIC_ONLY` and completes the final
A11→B5 matched normal-path pair. Full buffering/checkpoint and recovery coverage
remain before ticket closure.

## Previous controlled result: A11 group-5 diagnostic passed

See `a11-evidence/RESULTS.md`. A11 completed all five exact-output workflows,
29 groups, the request-20 recycle and two parser generations. Temporal business
results and 9,563/9,563 traffic attempts reconcile. There was no OOM; object
full PSI avg10 remained 0.00. A11 is `PASS_DIAGNOSTIC_ONLY` and supplies the A
side of the final A→B matched pair. A fresh group-10 B cell remains.

## Previous controlled result: A10 trace reader validation stop

A10 passed all 11 pre-inference gates and again reached the native workflow.
The trace child process remained alive, but its reader raised `ValueError` and
the outer controller interrupted the workload. A10 is not a group-5 replicate.
The safe diagnostic now records which fixed processing stage failed, without
retaining raw MinIO trace data. A fresh identity is required.

## Previous controlled result: A9 trace collector stop

A9 passed all 11 pre-inference gates. The 06, 07 and 08 workflows completed,
then the native MinIO trace collector ended while the `native` workflow was
active. The outer controller interrupted the supervisor and sealed cleanup;
A9 is incomplete and is not a group-5 replicate. The retained diagnostic only
reported a generic collector failure, so the collector now reports its
sanitized exception type and child exit code. A fresh identity is required.

## Previous controlled result: A8 stopped before workload

See `a8-evidence/RESULTS.md`. A8 passed capacity admission but its preflight
wrapper referenced an A7 file absent from the projected Pod workspace. No
workflow, object write or inference started, so A8 is not a group-5 replicate.
Cleanup restored held workloads to zero and retained the evidence PVC. The
wrappers now read projected base templates directly, and the regression runs
them from the rendered workspace. The next group-5 cell needs a fresh identity.

## Previous controlled result: A7 group-5 diagnostic passed

See `a7-evidence/RESULTS.md`. A7 completed all five exact-output workflows with
29 groups, one parser recycle and two parser generations. Traffic and resource
qualification passed and cleanup restored held workloads off. This completes the
B4→A7 matched order; one fresh A→B normal-path pair remains.

## Latest controlled result: B4 group-10 diagnostic passed

See `b4-evidence/RESULTS.md`. B4 passed all 11 gates, completed the fixed
06/07/08/native/06 sequence with exact full outputs, reconciled 10,016 client
calls to server attempts, and shut down cleanly. Its 517.67-second duration is
the second valid group-10 observation. B4 remains `PASS_DIAGNOSTIC_ONLY`; the
next cell is the matched group-5 baseline, followed by the remaining planned
comparison, recovery and final-bound work.

## Latest controlled result: B3 stopped before inference

See `b3-evidence/RESULTS.md`. B3 passed admission and ten pre-inference gates,
but the projected candidate window imported a B2-only contract that was absent
from its B3 source projection. No workflow, object write or inference started.
This is an identity-projection defect, not an A/B measurement. Cleanup restored
held workloads off and retained the evidence PVC. A projected-workspace regression
now exercises the exact B3 import chain; the next group-10 cell uses a fresh
identity and is not a B3 retry.

## Latest controlled result: B2 group-10 diagnostic passed

See `b2-evidence/RESULTS.md`. The single B2 execution passed all 11 gates,
completed the 06/07/08/native/06 sequence with exact full outputs, reconciled
10,016 client calls to server attempts, passed resource gates and shut down
cleanly. Group size 10 used 16 groups and one parser generation without recycle;
its 520.27-second runner duration is effectively level with A6's 524.75 seconds
in this first unmatched comparison. B2 is `PASS_DIAGNOSTIC_ONLY`; matched-order
repetitions, complete buffering/checkpoint measurement, recovery comparison and
final-bound revalidation remain before #45 acceptance.

The earlier B1 command invoked the inner runner without its required outer
controller and stopped at admission before Kubernetes resources or inference.
That harness invocation error was not retried or reused; B2 used a fresh identity
through the reviewed outer controller.

## Latest controlled result: A6 group-5 diagnostic passed

See `a6-evidence/RESULTS.md`. The single A6 execution passed 11 gates, completed
the 06/07/08/native/06 sequence with exact full outputs, reconciled all 9,563
client calls to server attempts, passed process/resource gates and shut down
cleanly. The post-run verifier path and expected-404 accounting defects are fixed;
31 local regressions pass. A6 is `PASS_DIAGNOSTIC_ONLY`: group-size comparison,
complete buffering/checkpoint measurement, recovery comparison and final-bound
revalidation remain before #45 acceptance.

## Latest controlled result: A5 business sequence passed, terminal acceptance incomplete

See `a5-evidence/RESULTS.md`. The single A5 execution passed all 11 gates and
completed the fixed 06/07/08/native/06 sequence with 28/15/12/51/28 registered
pages, 29 groups and one parser recycle. Controlled worker shutdown then failed
inside the acceptance helper before the measurement contract, traffic and
terminal evidence were finalized, so A5 is not accepted.

Retained process evidence excludes early worker exit and PID reuse. The old
helper discarded stderr, so its exact failed assertion is unknown. The in-Pod
worker path now publishes/fences on Linux start ticks and preserves helper
diagnostics. Thirty local regressions pass, and a bounded Linux check with the
actual helper proved graceful stop, mismatch rejection and forced cleanup. A5
cleanup left all 32 held Deployments off and retained its Bound evidence PVC.

## Prior controlled result: A3 stopped at node full PSI

See `a3-evidence/RESULTS.md`. The single A3 diagnostic at `2bfa48c` passed all
11 pre-inference gates and confirmed that the repaired evidence race is active in
the real entrypoint. Recording object Pod max events instead of stopping on them
allowed the fresh workflow to begin: prepare completed for 28 pages and the first
execute group reached `RapidOcrModel`.

The unchanged outer node guard then observed full PSI avg10 `0.18` and initiated
interruption. VM/object OOM counters stayed zero and available memory stayed above
the floor. Temporal completed with the business result
`failed / activity_budget_exhausted`; this is not ingestion success. Failure
evidence sealed completely, all 32 Deployments returned off, no owned Pod or trace
container remains, and the A3 PVC is retained. Restored/replay and the calibration
comparison remain unexecuted.

## Prior controlled result: A2 stopped at object Pod max events

See a2-evidence/RESULTS.md. The fresh A2 execution at 9808c04 passed all 11
pre-inference gates, then stopped when the object Pod local max counter increased
under its unchanged 1 GiB cap. All 529 object samples retain zero OOM counters.
This was one execution, with 26 local regressions passing beforehand; no retries,
cache flushes, resource changes or threshold relaxation followed.

Read-only PVC recovery showed supervisor/init/worker startup despite the outer
NOT_STARTED summary. No Temporal executions were found on A2's unique workflow
queue. The startup/guard evidence race is an unresolved tooling defect, and
recovered artifacts are not a successful terminal seal. Controller cleanup
restored all 32 Deployments off and retained the A2 Bound evidence PVC.

## Current result: A1 attempted, diagnosed, cleaned up

See a1-evidence/RESULTS.md. The controller was executed once at 0f8cf8f after
local regression, review and actual native-trace lifecycle validation. Capacity
admission passed; historical Python keyword defaults caused the created Deployment
identity check to fail before workflow/inference. The default-binding root cause
is repaired and covered by the real failing checker regression; all 26 tests pass.
No runtime retry occurred. A1 evidence/manifests remain frozen, and 32 historical
Deployments are restored off. Older pending/status sections below are historical.

## Remote ledger export

T09b now has a failure-aware remote mirror using the existing DH transport.
The baseline worker ledger is newline-framed during incremental export, and its
ledger/summary are required for successful finalization. The preflight and source
projection include this actual module. A subprocess test executes the generated
remote snapshot twice: a partial ledger line is withheld, then appended intact
when completed; missing terminal evidence cannot finalize as success.

Twenty-three tests passed before review. Both review axes identified the same
incorrect assumption: two parser generations do not mean two worker processes.
The coordinator launches one worker and recycles its parser internally. The
success requirements now correctly name worker-1 only; the focused export test
passes after the fix. Existing run reconciliation still discovers any additional
worker directories. No historical runner or cluster resource was changed.

The outer controller still needs to select this mirror, own trace markers and
enforce final reconciliation. Export support alone is not an executed baseline.

## Managed trace and run reconciliation

TraceSession now owns the local native-trace process and reader, streams only
sanitized records, rejects premature exit/malformed output, waits for distinct
readiness/final marker IDs and bounds shutdown. Its caller must issue markers at
the actual workload boundaries, poll health during work, and supply a finite
remote timeout; terminating local kubectl does not prove remote process cleanup.

reconcile_run and the reconciliation CLI's --state/--phase/--trace mode require
storage ledgers from every discovered worker generation, including failed ones,
and successful boundary markers in retained server records. Marker traffic is
excluded. Missing worker ledgers, incomplete lifecycle evidence or interrupted
calls cannot pass through a selected subset of successful ledger files.

Twenty-two local tests pass, including real subprocess trace startup/shutdown,
sanitization and malformed early exit. Both Standards and Spec reviews found
zero actionable defects in this slice. This does not yet wire the outer runtime
caller, remote evidence export or final acceptance; baseline remains unstarted.

## Pod supervisor and preflight integration

The fresh T09b supervisor now invokes baseline_window.py with the A1 identity and
integration manifest, retaining the historical 825-second workload contract,
drain and terminal cleanup engine. The preflight retains DH capacity/resource
checks and validates the actual measured entry points and fresh scope. A local
probe against the retained DB input bundle passed its import/profile/scope checks;
this is not the full in-Pod pre-inference gate set.

Two launch defects were reproduced and fixed: PYTHONSAFEPATH=1 suppressed the
script directory needed by the new worker/coordinator, and the projected source
omitted host_be/host_bc dependencies. Explicit script-relative imports and the
required projection entries fix these without disabling safe-path. Tests now
reconstruct the actual projected filesystem and launch all four entry points
from outside the checkout, plus check scope/argv and missing cleanup markers.
Historical files remain unchanged. Twenty local tests pass; diff check passes.

Follow-up Standards review found no documented-standard violations but identified
one correctness defect: the preflight could resolve the old q04/pod_workload.py
because q04 preceded t09b on sys.path. Both preflight and coordinator now retain
t09b precedence; the projected regression asserts the resolved supervisor path
after importing both entry points and passes. Spec review found no additional
defects in this partial integration; outer runtime admission remains incomplete.

The isolated validation environment additionally installed pypdfium2 5.13.0 and
Pillow 12.3.0 for coordinator import checks; this changes no project dependency
or runtime image. Full outer admission/trace lifecycle/export and complete
buffer/checkpoint accounting remain pending. No Kubernetes resource was changed
and no PDF baseline ran in this step.

## Current status: correlated traffic and publication buffers

Validation: 17 tests passed together; the additional streaming-collector test
passed with the existing native-trace test. The final reconciliation changes
also passed both focused tests. Standards review found no documented-standard
violations; Spec review found tagged observer calls falsely rejected as unknown.
That defect is fixed and covered, while genuinely unknown tagged calls still fail.

The native collector now streams sanitized JSONL rather than accumulating verbose
raw trace output. Each row is flushed; malformed/error/empty streams fail and
already collected rows remain available. This is a collector entry point, not yet
an outer-supervisor readiness or termination guarantee. A fresh GitHub #45 read
timed out; no GitHub update was published during this slice.

The actual boto3 probe now matches each of four SDK calls to native MinIO HTTP
accounting by call ID; exact 16/4096-byte readback and cleanup passed. Evidence is
in boto-correlated-evidence. SDK fault regression verifies the same correlation
ID survives retries. Traffic reconciliation rejects missing attempts, incomplete
reads, unmatched calls and incomplete ledgers, including calls interrupted before
their finish event. Its CLI accepts all worker ledgers and sanitized server JSONL.

Publication measurement records unique live bytes supplied to Store.publish,
including concurrent calls and alias deduplication. It does not measure retained
GET buffers or native/parser allocations. This is a partial buffering observation,
not complete buffering attribution. Pod memory remains the aggregate bound.

Runtime baseline has not started. Remaining launch work is the fresh outer
integration, managed native trace readiness/stop/export, complete buffering scope
and the final preflight/cleanup review. Earlier sections below are historical
slice records; their pending lists describe the state at those times.

## Known-size native accounting result

The fresh 16/4096-byte diagnostic succeeded with exact readback and ten observed
HTTP 200 trace calls. GET tx exactly matches each payload; mc pipe uses multipart
upload and PUT rx includes additional bytes. See known-size-evidence/RESULTS.md
and retained sanitized result.json. No PDF workload or Deployment mutation occurred.
This closes native-counter availability and the known-size mc calibration only.
The actual boto3 path, observation completeness under interruption, buffering and
the complete outer runtime contract are still pending. Do not label baseline ready.

## Native trace and coordinator follow-up

Fourteen local tests pass. `baseline_window.py` selects T09b Host in the existing
DB measurement engine, preserving its complete-output oracle and group-5 contract;
the entry point is included in the inactive source projection. The outer supervisor
still needs a fresh integration manifest and complete launch wiring.

Bounded read-only probes against the existing MinIO container used a unique missing
object HEAD request. Nonverbose/path-filtered probes produced no records; a verbose
12-second probe produced two records with request/response fields and callStats
rx, tx, duration and timeToFirstByte. Only field types were returned; headers and
bodies were discarded. The missing object returned the expected error. Trace ended
with timeout exit 124, not a workload failure. No objects or workloads were created.

`minio_trace.py` retains only records within a bucket/prefix boundary, validates
integer byte counts, removes query/header/body data, and retains failed HTTP status.
Its local test covers 404 accounting, prefix isolation and missing counters. This
establishes the available schema, not end-to-end completeness or byte semantics:
successful known-size read/write calibration, observer separation, trace readiness/
loss detection and orderly stop reconciliation are still required. Duration remains
raw until units are verified. Counters are server HTTP callStats, not TCP packet
bytes or application-only payload sizes. Buffer measurement also remains pending.

## Host and source projection follow-up

Thirteen local tests pass. `t09b_host.py` targets the measured worker consistently
for launch, graceful signal and force-stop identity checks, retaining the existing
lifecycle lock. A local command-capture test verifies full worker argv and both
cleanup paths. `topology.py` renders a distinct inactive A1 Pod/PVC/prefix using
the accepted DB resource builder and includes all measurement source files. The
projection test reconstructs ConfigMap mount contents and compares them with the
actual worker/modules; replicas remain zero. No manifest was applied.

Read-only cluster inspection found the existing object Pod healthy and the
installed `mc admin trace` supports JSON, prefix filtering, request/response byte
filters and request tracing. Prefer validating that native source over writing a
transport proxy. Its JSON byte fields and completeness still need a bounded probe;
help output is capability discovery, not traffic evidence. Do not persist verbose
authorization headers or source payloads in measurement output.

Still pending: coordinator selection of the T09b host, complete preflight/outer
guard launch wiring, native trace validation, and buffering observations. The
rendered topology alone cannot start a qualified baseline. Existing cluster and
main branch were not changed.

## Measured worker lifecycle follow-up

The new `t09b/worker.py` preserves the `q04/worker_bc.py` lifecycle and adds the
shared Store wrapper, Activity interceptors, exclusive ledger and reconciliation.
The sampler checks ledger sink failures; incomplete storage coverage cannot yield
a successful worker exit. Historical worker files and production code are unchanged.

Eleven tests pass. The new lifecycle test invokes this actual runner with local
Temporal/parser/storage doubles: two profile Workers share one measured Store,
each Activity has its own attribution, first-sample readiness is reached, a stop
signal drains the Worker contexts in reverse order, and cleanup plus storage
summary are written. This is not a real Temporal or Pod execution.

The Pod source projection and coordinator must select this worker and include
storage_measurement.py, storage_ledger.py and worker_measurement.py on its import
path along with the existing Q04 harness. That launch-contract work is pending;
do not run DH unchanged or mark T09b baseline ready. Actual transport-attempt
bytes, in-flight buffer measurement and matched instrumentation overhead remain
unresolved. Application payload observations alone cannot close those #45 gates.

## Durable interruption follow-up

Ten tests pass, including an actual subprocess exiting with os._exit inside
the client call. `Ledger` exclusively creates its output, flushes/fsyncs each
start before the SDK call and each finish after completion/body close. Reconcile
rejects unmatched/duplicate records, changed call identity, malformed tails,
empty evidence and pending calls. A complete ledger means operation coverage,
not successful business output or complete wire measurement.

The shared-Store seam in `q04/worker.py` creates Store once before a loop of
profile Workers. `install_store(store, sink)` must run once before that loop;
each Worker receives the returned interceptor. Do not install per profile.
The runtime owner must close the ledger after Activities stop, then reconcile
the retained file. Ledger fsync overhead is included in timed runs and must be
matched across candidates; this mechanism has not been benchmarked in the Pod.

No runtime source projection is wired yet. Transport-byte and buffering sources
remain outstanding; the launch is not baseline-ready. Current code adds no cluster
operations and leaves historical runners intact.

## SDK and worker adapter follow-up

Eight tests now pass using `/private/tmp/t09b-sdk-venv/bin/python -B -m unittest
discover -s tests/pdf_processing/t09b -p 'test_*.py' -v`. This isolated environment
contains boto3 1.40.24, botocore 1.40.76 and temporalio 1.23.0. No project runtime
dependencies or cluster resources were changed.

The loopback HTTP test uses the actual SDK: a 503 response causes two server-side
PUT payloads for one submitted application payload; the SDK reports one retry.
A truncated GET produces an incomplete record retaining only bytes actually
returned to the caller. The first test expected only IncompleteReadError; observed
botocore raises ResponseStreamingError on this transport. The test now accepts
both SDK truncation classifications without changing the measurement behavior.
Server shutdown and thread exit are checked.

`worker_measurement.install(processing, emit)` supplies an opt-in Temporal Worker
interceptor, to pass as `interceptors=[...]`. It wraps the existing S3 client before
polling and scopes every Activity by workflow/run/activity/attempt. SDK-interface
tests cover prepare/group/assembly/OCR/finalize and cancellation context cleanup.
These are interceptor invocation tests, not a live Temporal worker execution.

Still pending: connect this adapter and a durable sink to the new runtime launch,
reconcile interrupted operations, measure transport-attempt bytes and buffering,
and review the complete runtime contract. The loopback server proves the counting
distinction; it does not supply a production wire-traffic collector. Baseline has
not started. The previous slice record below is retained as historical context.

2026-09-28: six focused unittest cases pass with:

```sh
python3 -B -m unittest discover -s tests/pdf_processing/t09b -p 'test_*.py' -v
```

`storage_measurement.py` wraps the S3 client used by both Store and direct
Processing.read_source calls. Explicit request/activity/attempt context follows
asyncio.to_thread. Bodies retain their original context even when closed later;
observer traffic is separate. Success, failed PUT, partial GET, SDK retry count,
and unknown transfer sizes are distinguished. Records contain no payloads or
credentials. No changes were made to the production producer or historical runners.

The tests cover concurrent attribution, missing scope, context restoration on
failure, partial-read cleanup, repeat close, observer exclusion and refusal to
invent wire-byte totals from SDK retries. A grouping-aware verifier compares the
entire document/checks and requires business completion; missing pages or OCR
content fail. No output fields are normalized away.

This is not yet an integrated collector: the worker must install the wrapper and
scope every Activity, including prepare and enrichment, and stream records to its
retained evidence volume. A killed process may leave an unclosed read without a
terminal event; runtime reconciliation must reject incomplete measurement, never
treat absent events as zero. Raw threads do not inherit ContextVars automatically.
The measured body covers the existing read/close call sites, not arbitrary SDK
stream methods. The existing Store aggregate remains unchanged and must not be
used for per-request attribution under concurrency.

Outstanding before baseline admission:

1. Add an independently checked transport-attempt measurement source, including
   partial/failed transfers; the new wrapper reports application delivery only.
2. Measure in-flight buffering and unique checkpoint denominators without counting
   verifier/inventory reads as workload traffic.
3. Integrate into a fresh T09b launch contract, include all stages and retain
   interrupted measurement evidence. Verify real SDK behavior and cleanup locally.
4. Review the concrete source projection, topology window, deadlines, resource
   guards and cleanup before the first baseline. No runtime or topology change
   has been performed in this slice.

The checked prototype and q04-local Python environments lack boto3. These tests
use a deterministic client double and are not an actual SDK/network proof.
No dependencies were installed and no transport completeness claim is made.
