# T02 native PDF processing

This slice delivers `parsed_ready`: complete internal parsing and assembly, **not**
processing completion, selected OCR completion, or canonical acceptance. The caller
uses the versioned request through `PDFProcessing` on the Workflow queue and supplies
an explicitly configured Activity queue. There is no HTTP admission or public task
identity/deduplication promise here.

## Interface

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
integrity and exact profile/producer/limits. This deliberately conservative policy is
not selective OCR-only compatibility or rollout routing; T07/T08 own those changes.
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
is an `emptyDir`. The warm lifecycle and stronger late-writer races remain T05/T03.

## Bounded initial settings

Default preflight: 100 MiB source, 100 pages, 20 million rendered pixels per page at
scale 1; positive integer overrides are operator configuration. The measured local
validation uses a tighter **4 MiB** byte limit. These are provisional bounds, not
quality, memory, latency or production support promises.

Preflight child deadline 30 s; parsing/assembly child deadline 540 s. Activity
start-to-close 12 min, schedule-to-close 40 min, heartbeat 15 s, at most 3 attempts
with 2–10 s retry backoff. Local children have hard deadlines; true no-progress
supervision is a later warm-lifecycle concern. The deployment drains for 15 s inside
30 s Pod termination grace, then cancels and reaps unfinished fresh children.
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

The executable local validation manifest and instructions are under
`tests/pdf_processing/t02`. Its image tag, node pin, dev Temporal and local MinIO
credentials are explicitly test-only; they do not qualify production HA, IAM or
worker-version upgrades.

## Extension rules

T03/T04/T05 may extend internal contracts after T02. Preserve immutable existing
registrations; incompatible shape changes get a new contract version. `parsed_ready`
never becomes downstream delivery merely by renaming it: required OCR and final
processing validation must finish first. #32 decides canonical mapping/acceptance and
retention ownership; #31 decides HTTP admission/status and infrastructure durability.
