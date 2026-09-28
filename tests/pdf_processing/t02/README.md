# T02 real-service acceptance

The test seam is the approved versioned request → real Temporal → shared object
store → internal parsed result or explicit failure. There are no store/worker mocks.
The local image and backing dev services are for bounded qualification only.

Run `fixtures.py <directory>` in the existing local Docling Python environment
(which already has reportlab). It creates one three-page native source with literal
expected text plus password/page/pixel/invalid/byte-limit fixtures. These are input
contract tests, not scanned or multilingual quality qualification.

The validation namespace is `pdf-t02-validation`. Instantiate the existing pinned
prototype storage/Temporal manifests into that fresh namespace by replacing only
the namespace. Do not alter the fixed files or reuse/delete retained evidence PVCs.
Then create ConfigMaps:

- `t02-package`: all Python files from `src/pdf_processing`.
- `t02-driver`: `deploy/pdf-processing/worker.py`, this folder's `verify.py`, and
  `deploy/pdf-processing/profiles/native-v1.json`.
- `t02-fixtures`: the generated small PDFs, excluding the 5 MiB byte-limit fixture.

Apply `k8s-validation.yaml` after confirming the cached runtime exists on its named
local node. Wait for **both** worker rollouts to finish before submitting; old and new
code may not share a queue during testing. Copy the small fixtures to coordinator
`/tmp/fixtures` and generate a 5 MiB zero-filled `too-many-bytes.pdf` there. The cached
image already contains the pinned 51-page native paper.

From the coordinator run the following, changing `--mode` in order:

```sh
/experiment/.venv/bin/python /driver/verify.py \
  --temporal temporal:7233 --workflow-queue t02-workflows --activity-queue t02-pdf \
  --endpoint http://objects:9000 --bucket t02 --prefix final \
  --out /tmp/t02-run --fixtures /tmp/fixtures --mode setup
```

1. `setup` uploads captured fixtures with MinIO versioning enabled; it saves the
   actual version IDs and content digests. Use a fresh prefix for a new independent
   run and set the Activity worker's matching prefix. Do not rerun setup over final
   evidence or substitute new versions into an existing request.
2. `invalid` checks eight permanent rejection cases, all with zero registered pages.
3. `native` processes both sources and checks complete source/evidence references,
   known literal text for the generated source, full historical 51-page JSON digest,
   and assembly's zero repeated inference. It also tests stable-ID input conflict.
4. Restart the Activity Deployment and wait until its previous Pod is gone; run
   `reuse`. Every operation must be reused with zero uploaded bytes and identical
   parsed-result references. Check the replacement Pod's `/scratch` is empty.

To preserve evidence, copy the coordinator output directory, record actual image IDs,
worker Pod UIDs and code hashes, and keep the raw object-store PVC. This tests fresh
worker replacement after completed requests, not in-flight Pod loss or graceful
warm drain. T03/S1/T05 own those independent failure/lifecycle gates.

Run static type checking against the pinned interpreter with Temporal/botocore SDK
sources supplied through an external type-check directory. Do not install tools into
the measured runtime (the full package inventory is part of the frozen method).
The full slice suite is invalid → native → replacement → reuse after final code fixes;
the existing T01 scan-restoration test also protects the modified fresh-child seam.

The review-required incompatible-method check uses a separate Activity Deployment
and queue (`t02-mismatch` in the recorded run) with a test-only profile whose declared
Docling package version is deliberately wrong. Keep its source prefix the same and
submit `--mode mismatch --activity-queue t02-mismatch`. The driver checks the typed
permanent failure and Temporal history's Activity attempt numbers. Never apply that
profile to the normal workers. `verify_attribution.py` checks stored accepted plans
against mounted producer files for the recorded `qualified` prefix.
