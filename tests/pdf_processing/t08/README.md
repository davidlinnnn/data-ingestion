# T08 explicit-queue rollout qualification

Seam: a versioned captured-source request through real Temporal Activities and
checked object storage to an attributable complete result or explicit failure.
Baseline commit: `765d5483a61f8648f015e2f7f5538c54b62b6198` (T07 integrated).
This ticket adds rollout routing, not HTTP admission, NATS, a status database,
canonical acceptance, or SDK Worker Versioning.

## Reproduction

The retained local cluster, T04 deployment specs, qualified synthetic fixtures at
`/private/tmp/pdf-integration-fixtures`, and Linux ARM64 runtime/model cache are
prerequisites. All mutations stay in `pdf-t08-validation`, bucket `t08`, prefix
`rollout`, and content-addressed `t08-v1-*` / `t08-v2-*` queues. Do not rerun setup
against another task's namespace or change prior T06/T07 registrations.

1. Run `python3 tests/pdf_processing/t08/setup.py`. This creates isolated local
   Temporal SQLite/PVC and MinIO/PVC infrastructure from the retained specs.
2. The pinned runtime OCI manifest is
   `sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
   The retained containerd tag is `docker.io/library/pdf-checkpoint-prototype:linux-v2`
   on `internal-a2a-vs6-local-worker2`. Add the distinct T08 alias without replacing
   that tag using `ctr -n k8s.io images tag` inside that node, with destination
   `docker.io/library/pdf-t08-runtime@sha256:<the manifest digest>`.
   Kubernetes's runtime config imageID is a different digest; do not substitute it
   for the OCI manifest. No new package/model image upgrade is claimed here.
3. Run `python3 tests/pdf_processing/t08/releases.py`. It creates immutable package
   and release ConfigMaps and paused Deployments for both versions. The exact
   package, profile, limits, models, bucket/prefix, image and every queue are frozen.
   v2 changes actual required picture OCR render scale from 3 to 4. Both releases
   intentionally use the same pinned runtime/model bytes with different profiles.
4. Ensure coordinator `/tmp/t08-code` exists, then run
   `python3 tests/pdf_processing/t08/run.py`. The host process acquires
   `/private/tmp/data-ingestion-pdf-qualification.lock` with `fcntl.flock` for the
   entire experiment, reports contention, and releases in `finally`. No inference,
   rollout fault or formal resource measurement runs without this lock. Only T08
   Pods are deleted. T09a shares the same lock; no settings/evidence are copied back.
5. Inspect `evidence/results`, controller observations and `evidence/VERDICT.md`.
   Results retain request/source object versions, hashes, full resolved profile,
   producer hashes, actual task queues and attempts. Full documents, checkpoint
   bytes, text, source images and OCR crops stay in local MinIO.

The synthetic native multiple-picture fixture is sufficient for the routing gate.
It does not requalify T06's papers/book pages, formulas, languages or geometry.
The v3 required OCR/evidence completion barrier is exercised. Prior full typed
content, furniture/PictureItem children, six ACL equations (including TextItem eq2),
and region-specific representation uncertainty contracts remain unchanged.
T06's AIMA association/order limitation remains unqualified.

## Bounded matrix

The [predeclared phased scenario](SCENARIO.md) is authoritative for the final run.
It limits simultaneous Pod footprint while preserving mixed real OCR workers and
both Workflow populations. Stages drain only after all accepted executions finish;
the controller restores required workers before accepting later work.

- Submit old work before any old Workflow/Activity worker polls; then start only
  Workflow/preflight so parsing is queued before its compatible worker starts.
- Complete that accepted request with its frozen old release and read checked
  final/evidence references.
- Submit another old request, observe and immediately SIGSTOP a real active native parser stage, start the new
  release and force-delete only the old parsing Pod. The old queue's replacement
  must finish a later Activity attempt; the new worker cannot consume that queue.
- Submit new-method and old-method requests in the predeclared phases with both
  Workflow and OCR populations present. The
  new method reuses compatible old parsing/assembly while creating current
  request-bound OCR/evidence/final results.
- Delete an old parsing Pod gracefully with its real native child paused, record Pod
  retirement time under the 60s grace, and require eventual complete delivery.
- Reject missing/tampered routes and accepted request-ID reuse under another method.

The harness observes actual Temporal scheduling/history and runtime output; it does
not mock parsing, OCR, storage, Activities or Workflow execution. Timing of a
native-stage observation is bounded controller evidence, not a claim of a precise
neural instruction being interrupted. Failures and exploratory runs must be labeled,
never promoted to passing evidence. The local cluster is not production HA.

Limits remain provisional: source100MiB/pages100/pixels20M, native hard540s,
preflight30s, one Activity slot per stage Pod, sequential groups/components per
request, SDK drain30s/Pod60s/TERM5s/reap5s. Splitting queues permits concurrency
across requests; it does not establish calibrated aggregate capacity. #44/#45 own
sustained isolation and calibrated operating bounds; #46 still consumes T08 and T09b.

Qualification scheduling reservations are 256Mi for each retained warm parser and
64Mi for the other stage/Workflow Pods, all with the inherited 5Gi memory limit.
The inherited 256Mi-per-Pod reservation exhausted schedulable space when both
seven-Pod releases coexisted in this shared local cluster; that trial was stopped
and excluded. These smaller reservations permit this bounded fixture experiment;
they are not measured production reservations or a recommended aggregate limit.
#44/#45 retain ownership of calibrated resource settings.

The controller holds the host flock through retrying cleanup API calls and waits
for every owned worker Pod to disappear. Forced loss additionally checks the old
container is absent from the node runtime's running-container inventory. No
scenario Worker is hosted by the coordinator. If the host process is forcibly
killed, a host file lock alone cannot guarantee remote quiescence: stop new trials,
reacquire the recovery lock and reconcile owned remote resources before proceeding.
The operator must not equate an API timeout or client exit with worker termination.
