# T10 bounded release runbook

This package delivers #46's Processing Completion seam on the selected #45
group5/single-parser configuration. It targets `dev`. The release verdict and
evidence are in `tests/pdf_processing/t10/`; historical #43/#44/#45 evidence
remains under its original paths and object prefixes.

## Preconditions and ownership

Read `tests/pdf_processing/t09b/SUPPORTED-CONFIGURATION.md` and
`SUPPORTED-BOUNDS.json`. The 100MiB/51-page/20M-pixel limits are rejection limits,
not a promise that every input below them meets the resource envelope. Quality
support is the accepted bounded corpus/profile evidence. Generic `selected-native-v1`
does not create source-reviewed quality or relationship claims for new PDFs.

The qualified runtime is ARM64, four CPU threads, one Activity process containing
six explicit stage queue workers and one shared parser.
Activity startup retains #44's per-supervisor Linux THP-disable/readback policy,
inherited by child exec; node sysfs is never modified. Run **one business request
at a time**, with one active Activity replica across releases. The process lock
serializes stage execution; it is not an admission service or a capacity claim.
Concurrent submissions, fleet admission and capacity targets belong to #31/#52/#54.
Do not activate six independent parser Pods using the legacy `workers.yaml`.

Before starting or replacing any runtime, inventory cluster context, nodes,
Deployments, live Pods/containers, shared Temporal open executions, PVCs, object
service placement/UID/digest, bucket versioning and current object capacity.
Keep previous workers quiescent. For the qualified local topology, admission
requires VM MemAvailable >=4.5GiB for 60 seconds with no full PSI; retain the
existing inner 3GiB parser admission and its 60-second wait. During work retain
the 1.5GiB VM floor, 4GiB sampled worker guard, 5GiB hard worker limit, one parser,
zero worker full PSI/OOM, and existing object/node PSI policy. Sample at 250ms,
reject gaps over one second, and stop owned runtime immediately on a fatal guard.
The manifests' small scheduling requests do not reserve these VM budgets.

Storage and Temporal are existing services. This package creates no shared PVC,
service, bucket, lifecycle policy, GC, RBAC or production HA topology. A namespaced
Secret supplies `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`; do not put values
in manifests or evidence. Operator credentials require versioned source writes,
conditional publication, list/read/version access in the selected retained scope.

## Build, render, start

Build from a verified immutable base with the accepted Python/package/model cache.
`Dockerfile` adds current `src/pdf_processing`, worker, bootstrap and operator to
that base; it performs no dependency installation or model fetch. `DOCLING_RUNTIME`
must be pinned, and the resulting deployed image must use its manifest digest.
The qualified cached base/candidate digests are recorded in the release evidence.
For an offline classic Docker build, use a temporary context containing only
`src/pdf_processing` and `deploy/pdf-processing`; do not send private fixture or
historical evidence bundles as a build context. Dockerfile.dockerignore provides
the same restriction for BuildKit.

```sh
rtk docker build --build-arg DOCLING_RUNTIME="$DOCLING_RUNTIME" -f deploy/pdf-processing/Dockerfile -t pdf-core:candidate .
rtk env python deploy/pdf-processing/release.py \
  --profile deploy/pdf-processing/profiles/selected-native-v1.json \
  --image "$IMAGE_DIGEST" --namespace "$NAMESPACE" --name pdf-core \
  --bucket "$BUCKET" --prefix "$FRESH_PREFIX" \
  --temporal "$TEMPORAL_ADDRESS" --endpoint "$OBJECT_ENDPOINT" \
  --secret store-access > release.json
rtk kubectl apply -f release.json
```

The renderer is read-only and creates an immutable ConfigMap and two Deployments
at **zero replicas**. Save `route.json` from the ConfigMap with the release.
Its content-addressed binding freezes source producer hashes, method/profile,
limits, bucket/prefix, all seven queues and image digests. Activity bootstrap
checks the exact accepted Python, platform, package map and all 17 local model
artifacts before polling. Missing/mismatched bytes fail startup; do not enable
online downloads to conceal the mismatch. A new profile/image produces a new
route, not a mutable update of an accepted route.

For a source-reviewed derivative, capture its retained original into the release's
`sources/` prefix with Enabled versioning, verify its digest against the review,
and bind that returned artifact in `content_evidence.reviews[*].original_source`.
Preserve the original revision, original-page map, regions and historical reference.
The renderer rejects a reviewed original outside the release prefix. The request
artifact separately captures the derivative; never replace it with the whole book.

After preconditions and monitoring are satisfied, scale the generated Workflow
Deployment to one, then the Activity Deployment to one. Check startup logs for
`bootstrap_verified` and the expected immutable image/container identity. K8s
container Ready alone does not prove bootstrap or queue polling. Each stage
validates its queue, role, image and full release binding.

## Submit and retrieve

Set `CLIENT_POD` to the generated active Activity Pod, using its namespace on
every kubectl command. Copy the input PDF and request with `kubectl cp`; its
`/release/route.json` and Secret environment already supply the selected binding.
Run `/app/manage.py` with the image's `/experiment/.venv/bin/python`. These commands form the internal integration seam;
they do not implement HTTP authentication, upload policy or Canonical Acceptance.

```sh
rtk kubectl -n "$NAMESPACE" exec "$CLIENT_POD" -- /experiment/.venv/bin/python /app/manage.py --route /release/route.json capture --pdf /tmp/input.pdf
rtk kubectl -n "$NAMESPACE" exec "$CLIENT_POD" -- /experiment/.venv/bin/python /app/manage.py --route /release/route.json submit --request /tmp/request.json --workflow-id "$WORKFLOW_ID"
rtk kubectl -n "$NAMESPACE" exec "$CLIENT_POD" -- /experiment/.venv/bin/python /app/manage.py --route /release/route.json status --workflow-id "$WORKFLOW_ID"
rtk kubectl -n "$NAMESPACE" exec "$CLIENT_POD" -- /experiment/.venv/bin/python /app/manage.py --route /release/route.json export --workflow-id "$WORKFLOW_ID" --out /tmp/result
```

Capture requires Enabled versioning, writes a unique source key and returns
`key/name/version_id/sha256`. Put this captured reference into a v3 request with
`completion: required_evidence_v1`, `profile: native-v1`, a stable `request_id`
and meaningful `source_revision`. See `HANDOFF.md` and the actual evidence examples.
Use a new Workflow ID for each execution; duplicate Workflow IDs are rejected.
An exact request replay with another Workflow ID reuses checked registrations;
changing `request_id` creates different operation identities. Never silently
substitute newer source bytes, models or profile when recovering an old request.

Status preserves progress, error category/code, observed timestamps, step reuse,
child summaries and the final processing-result reference. A terminal Temporal
execution can still report `status: failed`; inspect Processing Completion.
Export refuses incomplete results and reads every exported adopted artifact via
the registry and byte digest checks. It emits summary, final manifest, assembled
document, selection, typed content evidence, relationships when required, parsed
result/plan, OCR/crops and `retained-references.json`. These are internal evidence
and mappings for downstream work, not public projections of checkpoints.

## Rollout, loss and restart

Pause submissions, wait for the old release's executions and active stage work to
finish, scale both old Deployments to zero, and prove their Pods and actual old
containers/children are absent before activating the next release. Recreate,
30-second drain and 60-second Pod termination grace preserve the tested overlap
budget. Same-profile new-image and source-reviewed-profile releases get distinct
queues; old queued executions remain on their original route. Retain that route
and image for recovery. To resume a stranded old route, first quiesce the current
release, then reactivate the old route; never run a second parser alongside it.

For unexpected worker loss, Temporal retries the stage under retained Activity
timeouts/retry policy. Already registered group work remains reusable. Payload
uploaded without registry publication is an orphan, not a complete result. Only
the checked final processing-result registration marks completion. Do not edit
registrations or adopt an unregistered late attempt manually.

PID1 restart may retain `emptyDir`; startup and shutdown clean only this worker's
owned `preflight-*`, `activity-*`, `ocr-*` directories and stop owned children.
Pod replacement discards its scratch volume. Shared retained artifacts survive.
Other scratch paths are not interpreted as owned work and are not deleted.

For a planned object-service Pod replacement, quiesce PDF workers and executions,
record Deployment/Pod/container/PVC identities, stop the exact old observer,
delete only the observed Pod with a UID precondition, retain the Deployment/PVC,
wait for the replacement, restart its exact-cgroup observer, and resolve all
adopted references again. The bounded local replacement check is 120 seconds.
No node loss, disk loss or production HA guarantee follows from this check.

## Failure containment and retention

Fatal resource/telemetry errors fence activation, scale owned PDF Deployments to
zero and physically stop only their exact containers. Preserve source versions,
registry entries, payloads, manifests and raw evidence, including failures.
Terminate only the qualification's owned executions if required; do not terminate
other users' workflows. Verify owned Pods/containers/children and observers absent.
Never delete historical namespaces, PVCs or prefixes as cleanup.

Use existing `Store.inventory` for bounded read-only registered/unregistered bytes,
orphan estimates and capacity status. No automatic deletion is authorized by that
report. Physical PVC/MinIO capacity and object-version retention require separate
checks: inventory counts are not disk availability. Custody/adopted-reference
retention belongs to #31/#32; #57/#52 carry migration decisions. Keep original
captured sources and all adopted references until those owners define and verify
their retention policy. Canonical projections must not expose internal checkpoints.

Release approval remains bounded to this topology, corpus, method and guards.
#52 and related tickets own production capacity, storage/backend migration,
node/disk/HA, cost and fleet policy. #31/#32 own HTTP admission and canonical
mapping/validation. T10 does not close parent #33 or publish to `main`.
