# Native PDF processing workers

The core retains v1 `parsed_ready`, v2 required picture OCR completion, and v3
required source-evidence completion. All successful results keep canonical
acceptance false. New rollout-managed work uses the [explicit release routing
contract](#explicit-compatible-worker-rollouts-t08) below; the historical
`PDFProcessing` type remains available on its retained queues.

## Legacy submission interface

Submit a dictionary with `request` and `activity_queue`. The request contains:

- `version: 1`, a bounded `request_id`, and a `source_revision` observation reference.
- `profile: native-v1`.
- `artifact`: `key`, non-null S3 `version_id`, lowercase SHA-256 `sha256`, and PDF
  basename `name`. The configured bucket and prefix define the authorized storage
  scope; source keys must be under `<prefix>/sources/`. Enable object versioning when
  capturing sources. The worker never follows an arbitrary URL or a current version.

The immutable request plan stores source, resolved profile/runtime/model identities,
producer hashes, five-page sequential groups, page dimensions, limits and creation
time. A repeated internal request ID must describe the same request. Reuse checks
integrity and exact profile/producer/limits. Accepted request IDs retain that exact requirement. New request IDs can reuse
compatible parsing/assembly under T07; explicit release routing is described below.
Large method inventories and document bytes remain in object storage.

`PDFProcessing.progress` and its final return expose `registered_pages`, stage,
registered/reused operations, observation timestamps, durations, storage measurements
and bounded errors. Child heartbeat means wrapper liveness, not durable completion
or native inference progress. Only validated registered group completion increments
pages. `parsed_result` resolves a versioned `parsed-result.json` registration with
plan, source, assembly and group/evidence references. Group registrations retain
hashed checkpoint JSON and visual bytes; assembly retains full Docling JSON/Markdown.
Temporal history is the durable invocation summary; this is not a request-status DB.

Permanent input, method incompatibility and integrity errors stop immediately.
Storage and parser failures have finite Activity retry budgets. Missing input version,
password requirement, invalid PDF, digest and configured size/page/pixel violations
fail before inference. Confirmed bad registration does not silently become a miss.
No shared artifacts are automatically deleted. Scratch uses `TemporaryDirectory`;
process cancellation/deadline kills and reaps its process group. Pod-local scratch
is an `emptyDir`. Warm native parsing is supervised by T05; stronger late-writer races remain T03.

## Bounded initial settings

Default preflight: 100 MiB source, 100 pages, 20 million rendered pixels per page at
scale 1; positive integer overrides are operator configuration. The measured local
validation uses a tighter **4 MiB** byte limit. These are provisional bounds, not
quality, memory, latency or production support promises.

Preflight child deadline 30 s; parsing/assembly child deadline 540 s. Activity
start-to-close 12 min, schedule-to-close 40 min, heartbeat 15 s, at most 3 attempts
with 2–10 s retry backoff. Warm native parsing uses a provisional 120 s startup
allowance, 180 s local no-progress allowance and the frozen 540 s hard deadline.
The current deployment uses **30 s SDK drain inside 60 s Pod termination grace**.
SDK shutdown stops polling, then cancels unfinished Activities at the drain limit.
A separate 35 s shutdown wait bounds a stuck SDK shutdown; parser TERM/reap adds
at most 5 s + 5 s, leaving 15 s within Pod grace for scheduling and cleanup.
After child cleanup the entrypoint exits explicitly, so cancelled thread-backed
publication cannot extend lifetime via asyncio's default-executor shutdown.
Unregistered late outputs remain unfinished; process exit never declares success.
One Activity slot runs at once. T09 calibrates these values together.

## Runtime and deployment

The checked-in `profiles/native-v1.json` is the actual T01 Linux ARM64 runtime pin:
Docling 2.102.0, CPU four threads, parsing OCR disabled, page/picture images scale 1,
tables enabled. Its full package/model/platform inventory is compared by the parser.
It is not a portable promise for another image or architecture. Build the Dockerfile
from repository root with `DOCLING_RUNTIME` set to an immutable digest of the qualified
runtime. It copies only the processing package, entrypoint and profile. Do not install
new packages into that runtime during deployment.

Run the same image in separate Deployments with `WORKER_ROLE=workflow` and `activity`,
separate `TASK_QUEUE` values, and `TEMPORAL_ADDRESS`. Only Activity workers need
`OBJECT_ENDPOINT`, `OBJECT_BUCKET`, `OBJECT_PREFIX`, `MODEL_CACHE`, `PROFILE_FILE`,
AWS credentials via the normal provider chain, and optional JSON `LIMITS`.
Workflow code does not import or initialize Docling, model caches, or object storage.
Both roles handle SIGTERM; mount bounded `emptyDir` scratch on `/scratch` and inject
credentials through your cluster's secret mechanism.

Use `workers.yaml` as the current deployment template: replace its image digest,
namespace, service addresses and Secret name with reviewed environment values.
It explicitly records the 60/30/5/5 second Pod/drain/TERM/reap configuration.
The executable local qualification manifest is under `tests/pdf_processing/t05`.
Its image tag, node pin and development credentials are test-only. The T02 manifest
is frozen historical evidence, not the deployment recipe for current warm workers.

Changing these budgets requires updating Pod grace and revalidating shutdown.
Current cleanup owns both `activity-*` and `ocr-*` scratch and reaps supervised
native and fresh OCR children. The [merged lifecycle gate](../../tests/pdf_processing/integration/evidence/VERDICT.md)
records bounded active-OCR/publication shutdown and replacement evidence.

## Extension rules

T03/T04/T05 may extend internal contracts after T02. Preserve immutable existing
registrations; incompatible shape changes get a new contract version. `parsed_ready`
never becomes downstream delivery merely by renaming it: required OCR and final
processing validation must finish first. #32 decides canonical mapping/acceptance and
retention ownership; #31 decides HTTP admission/status and infrastructure durability.

## Explicit compatible-worker rollouts (T08)

For new rollout-managed requests use `PDFRolloutProcessing` and
`pdf_processing.routing.submission(request, release_id, retained_releases)`. Select an exact
maintainer-published release; there is no `latest` lookup. The returned submission
includes the immutable manifest and adds its `routing_id` to the captured request.
Start the Workflow on `release['queues']['workflow']`. Validate the selected release
against the retained deployment inventory before accepting new work. A missing
release/image/model or unprovisioned queue is unavailable routing, not permission
to substitute a newer method. A temporarily absent Pod on an already retained
release is recoverable queued work; retain and restore that release's workers.

`routing.release(binding, images, prefix)` builds the explicit version-1 manifest.
`retained_releases` maps exact release IDs to manifests whose images, models and
configuration the submitting operator has retained. An unknown ID is rejected as
`routing_unavailable` before any Workflow is submitted. The binding contains SHA-256 fingerprints of the complete profile, producer map,
limits and model inventory, plus exact bucket/prefix. `images` maps `workflow`,
`prepare`, `group`, `assembly`, `select`, `component_ocr` and `finalize` to retained
immutable image digests. Every queue name includes the whole release identity.
No independently deployed stage falls back to a shared latest queue. Required
source evidence is produced inside `finalize`; it is not a separately deployed
Activity in this baseline. A future split needs its own explicit stage/queue.

Each stage Deployment uses the existing entrypoint with `ROUTING_FILE`,
`WORKER_IMAGE` (matching the Pod image), `TASK_QUEUE`, and Activity `WORKER_STAGE`.
Keep the manifest/profile/package immutable. The Workflow worker checks its queue,
image declaration and package. Every Activity worker additionally checks full
profile/producer/limits/models/store bindings and refuses another stage, release
or request-plan binding. The parser/OCR's existing runtime/model verification
remains in force. Runtime image enforcement belongs to deployment provenance:
`WORKER_IMAGE` is an operator declaration, not a container introspection mechanism.
Build the package and entrypoint into an immutable image in normal deployment;
qualification uses immutable ConfigMaps over the pinned runtime and records both.

The historical `PDFProcessing` type and no-`ROUTING_FILE` worker mode remain available
for retained legacy queues. Never place that legacy mode on a rollout-managed
queue. T07 accepted requests still require their exact old profile/producer/limits;
they cannot be imported into a T08 worker by adding a routing ID. Keep their old
images/config/models and queues until they meet retirement criteria. T07 checked
compatibility sidecars are mandatory for reusable native checkpoints; pre-T07
registrations are not automatically imported.

### Old-worker retirement

A successful Kubernetes rollout is not retirement authorization. For each release:

1. Fence **new** submissions to that release in the internal submitting operator's
   published inventory. Preserve its manifest and accepted request IDs. The internal
   seam has no public admission/status DB; the operator must enforce this fence.
2. Inspect Temporal for all open executions on its exact Workflow queue, including
   queued Workflow tasks, pending/retrying Activities, timers, cancellation/drain and
   replacement work. Retain workers for every stage while any such execution exists.
   Check all submitters and repeated observations after fencing; visibility is
   eventually consistent and one empty list is not a transactional proof.
3. Require every accepted execution to reach a checked complete result, explicit
   terminal failure or deliberately handled cancellation. Verify registered results
   remain readable and no unfinished required OCR/evidence is reported complete.
   For interrupted workers wait for child/scratch cleanup or confirmed Pod exit;
   recover on the **same** queues, image/model/config. Account for late publication.
4. Only then drain polling via normal SIGTERM and remove old replicas. Retain the
   release artifacts for any supported retry/reset/replay or restoration window.
   A reset after physical retirement requires restoring that exact release first;
   never reset onto the new release. Define that support/retention window explicitly.
5. Do not garbage-collect shared checkpoints, source/evidence bytes or canonical
   consumer artifacts as part of worker retirement. Their lifecycle is separate.

See the [T08 runbook](../../tests/pdf_processing/t08/README.md) for the executable
isolated rollout and bounded evidence. Existing 12min/40min/15s/3-attempt Activity
budgets apply; a missing Activity worker eventually yields explicit budget failure.
A Workflow worker itself must remain available for accepted queued executions and
for publishing terminal outcomes. T08 does not establish an outage SLO or calibrated
aggregate memory/concurrency limits; #44/#45 and final packaging #46 remain separate.
