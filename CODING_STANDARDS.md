# Coding standards

Judgement calls for writing and reviewing code in this repo. Mechanical rules live in
tooling: ruff and pyright (`pyproject.toml`) and `scripts/check-docs`.

## Language

Write code, identifiers, comments, docstrings, test names and log messages in English.
Refer to tickets and spec sections by number (`#129`) rather than by their titles.

## Vocabulary

Name things with the terms in `CONTEXT.md` (Processing Profile, Enrichment Method,
Processing Result, Enrichment Status, …), so code, docs and tickets share one language.

## Ports and tests

- Each external dependency (object store, admission, inference services, clock) sits
  behind a port: a `Protocol`, an in-process fake and the real adapter. The fake and the
  adapter pass one shared contract test.
- Tests observe behaviour at a seam: given inputs and port state, assert what was
  registered, returned or reported. Exercise the real library (docling, RapidOCR, boto3
  against the S3 stand-in) or swap a whole port for its fake.
- A service's own PostgreSQL database and Temporal itself have no fake: what they guarantee
  (constraints, row locks, workflow ID rules) is the behaviour under test, so tests run them
  for real (Testcontainers, the Temporal dev server).
- Mark tests that need Docker or a local socket (`s3`, `network`), so a run that
  has neither can deselect them.

## Comments and contracts

- A comment states, in one line, a why the code cannot show.
- A contract (docstring, port, schema) states obligations and observable semantics only.
  The spec names the extension points that are required, such as #108's insertion
  points; everything else waits for a ticket that asks for it.

## Temporal workers

- A worker's Activity slots match what its process can run at once. Work that holds a
  process-wide resource (a model, a lock, a GPU) gets its own task queue and a worker with
  that many slots, so waiting work stays visible in Temporal as backlog.
- Blocking work in an Activity runs through `stages.in_thread`: a cancelled Activity keeps its
  slot until the thread ends, so one worker never runs two parsers.
- Workflow code takes its parameters from Activity results, which Temporal records in history
  (prepare's `Plan.runtime`), not from module state that a later build could change.
- A worker hears of an Activity timeout or cancel only through a heartbeat response, throttled
  to 0.8 x the heartbeat timeout. A test of cancellation on a real worker sets a heartbeat
  timeout, and runs a negative control to show it can see the failure.
- An exception in workflow code does not fail the workflow: Temporal retries its task until a
  fixed build is deployed, so the workflow stays running and a test that awaits it hangs.
  Workflow code reads state it may not have set (a stage that fails before it starts) with a
  guard, and deployments alert on `temporal_workflow_task_execution_failed`.

## Platform API

- The `api` role runs one uvicorn worker per pod, so one thread serves every request of that
  pod. A handler is `async def` and awaits its I/O. A blocking call (boto3, any synchronous
  client) runs in a thread, for example with `asyncio.to_thread`; inline it stalls every
  request of the pod, health checks included (`docs/validation/113`: 284 requests per second
  with an awaited wait, 9.6 with the same wait blocking).
- A role that serves HTTP is operable from outside its process: a health route answered on
  the event loop, a counter per operation and outcome, and every failure visible as a status
  code or a metric. The log line of a failed call carries the trace id and the calling
  service's name.
- A response carries only what its caller may read. An exception's text, an internal endpoint
  or an object key stays in the platform's own records; a Source sees a platform failure as
  its reason code and `support_ref`, with a fixed message
  (`kp_admission.status.PLATFORM_FAILURE`).

## Logs and metrics

- A log line carries ids, counts and reason codes. Document text, prompts, model answers,
  file names and credentials stay out, on every route into the log: the Temporal SDK logs a
  failed Activity with its whole exception chain, so the text of an exception is log content.
- Reuse the metrics a library or the infrastructure already gives (Temporal's SDK metrics, the
  pod and namespace labels the cluster's Prometheus adds) before adding one. Add
  instrumentation for a business stage that nothing else shows, without build or deployment
  labels.

## Deployment

- The platform is cloud native: an image holds the dependencies of its own package only
  (admission ships without the parsing libraries), and a role keeps its durable state in the
  database or the object store, so a new pod starts fast and any pod serves any request. A
  heavy image, a slow start or state held in a pod is a finding.

## Validation evidence

- Check each acceptance criterion as a range with a lower bound (0 <= t <= limit), so a
  broken measurement fails instead of passing. Convert external timestamps with an
  explicit UTC zone.
- Pair a "never happens" claim with a negative control that shows the measurement can see it.
- Check presence against the expected set of keys (queues, tiers, metrics): a key that never
  appears must fail, not drop out of the check.
- Cache the expensive pipeline output of a corpus run, keyed by input and method digests, and
  score one document before the whole corpus, so a scorer fix reruns only the scoring.
