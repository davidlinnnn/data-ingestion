# Q02/Q03 local regression recovery (#68)

This entry point checks the eight modules identified by #68 without starting
Temporal, object storage or Kubernetes workloads. Each module runs in a separate
interpreter to avoid historical `fixtures`/`oracle` import collisions. Failures,
zero-test imports, timeouts, skipped tests and expected failures fail the run.
The `current` scope adds Q02 compatibility, Q01 identity, the recovery check,
and every local T04/T05/T09b/T10 `test_*.py` module. It is the complete #68 current
regression scope, not all historical PDF qualification suites.

## Environment

Use the existing qualified image `pdf-t10-core:20261001-c`, immutable local image
ID `sha256:7f7ff771e4411544d43a9fd60c6b6c0e6b2280351373f7ed47f28fa849082924`.
Verify the tag before running; obtain the retained image from its operator if it
is absent. This local image ID is not a public registry download location.
`regression.py` also rejects different Python/package versions:
Python 3.12.13, docling 2.102.0, docling-core 2.96.0, temporalio 1.23.0,
psutil 7.2.2, pypdfium2 5.13.0, Pillow 12.3.0, reportlab 5.0.1, boto3 1.40.24.
Do not install test dependencies into the measured parser runtime. An independent
private environment with these exact existing versions can run the Python entry
point directly. Do not use `-O`: the historical source-integrity checks use asserts.

## Private inputs from a fresh checkout

The operator supplies private files outside the checkout; no PDF, extracted
source text, model or credential is distributed in this repository. Access to
the retained store and the private source-oracle bundle is a prerequisite.
Keep a portable private copy of these three files before retiring that storage:

| Bundle filename | Required SHA-256 | Retained source |
| --- | --- | --- |
| `baseline-document.json` | `7cbc44478d4a3d2f60256f6f92828b2396b1b932579436546e3d32b6f601f564` | Exact Q01/Q02 baseline, recovered below |
| `source.pdf` | `b06c0b87e45b4fe37d3efa3797e6e978b9c884489ff7207fb220e958cfca0980` | Private Q44 bundle `fixtures/08.pdf`, the 12-page derivative, not `originals/08.pdf` |
| `source-oracle.json` | `ae3176eb987341243a90dc0fb4a476be3286f2f63c56196c8706f8067788ae7c` | Private Q44 bundle `oracles/aima-code.json`; four source transcripts independently hash-checked by the frozen Q02 oracle |

The retained Q44 bundle used here is `/private/tmp/q44-inputs-warm-20260928-db`.
That path is an observed location, not an assurance of permanent retention. Ask
the private bundle custodian for those exact bytes if unavailable; do not derive
new oracle transcripts from current parsed output. All three files can instead
be supplied from any private directory with the same hashes. The runner binds
`Q02_BASELINE`, `Q02_SOURCE_PDF` and `Q02_SOURCE_ORACLE` for itself and child tests.
Those environment variables also support running individual historical modules.

The original baseline path is gone. The retained Q03 seeded document permits an
exact byte recovery with the pinned Docling model, without PDF inference:

- Endpoint (inside the existing cluster): `http://objects:9000`, bucket `t09a`.
- Key: `q03-matrix-20260916-d/523b8aacb1ea41679a84457b65f4c1ec/corrupt_page/attempts/6d20bad6-6194-46fb-80c3-e6667c7881aa/document.json`.
- Immutable version: `b897923a-c3b2-460b-b792-ae7afc6eec11`.
- Stored bytes: 507924; SHA-256 `f0f576f3bcc6df04306597ef80368112d1269f9459fc552fb8402c245a0aabca`.
- Recovered bytes: 551189; SHA-256 equals the original baseline above.

Download that exact version using the operator's existing S3 credentials/provider
chain. For example, an authenticated private S3 client can execute this read-only
retrieval (set the endpoint to the accessible retained store, never print secrets):

```python
import boto3
from pathlib import Path
s3 = boto3.client('s3', endpoint_url='http://objects:9000')
raw = s3.get_object(Bucket='t09a',
    Key='q03-matrix-20260916-d/523b8aacb1ea41679a84457b65f4c1ec/corrupt_page/attempts/6d20bad6-6194-46fb-80c3-e6667c7881aa/document.json',
    VersionId='b897923a-c3b2-460b-b792-ae7afc6eec11')['Body'].read()
with Path('/private/output/stored-document.json').open('xb') as output:
    output.write(raw)
```

Inspect the current context/pod identity before using any existing cluster client.
The recovery performed for #68 used read-only GET through the existing
`pdf-t09a-validation/coordinator` Python client; it created no workload and wrote
no store objects. With `stored-document.json` in a private bundle directory:

```sh
Q68_INPUTS=/absolute/private/bundle
rtk docker image inspect pdf-t10-core:20261001-c --format '{{.Id}}'
rtk docker run --rm --network none \
  --entrypoint /experiment/.venv/bin/python \
  -v "$PWD:/workspace:ro" -v "$Q68_INPUTS:/inputs" -w /workspace \
  pdf-t10-core:20261001-c -B tests/pdf_processing/q03/recover_baseline.py \
  /inputs/stored-document.json /inputs/baseline-document.json
```

`recover_baseline.py` checks the stored digest before parsing, checks the exact
recovered digest before writing, and refuses to replace an existing output.
It round-trips the retained Q03 Docling serialization to Q01's original
`model_dump(mode='json')` plus `json.dumps(indent=2)` bytes. No successor/A12
output or refreshed oracle is used. Missing versions or digest failures are
missing-evidence/integrity failures, never a passing substitute.

## Run

Set `Q68_INPUTS` to the three-file private directory and `Q68_RESULTS` to an
existing private parent directory. Run from the fresh checkout root; the output
child must not already exist. Source and inputs are mounted read-only:

```sh
Q68_INPUTS=/absolute/private/bundle
Q68_RESULTS=/absolute/private/results
rtk docker run --rm --network none \
  --entrypoint /experiment/.venv/bin/python \
  -v "$PWD:/workspace:ro" -v "$Q68_INPUTS:/inputs:ro" \
  -v "$Q68_RESULTS:/results" -w /workspace \
  pdf-t10-core:20261001-c -B tests/pdf_processing/q03/regression.py \
  --fixtures /inputs --out /results/affected --scope affected
```

For `--scope current`, additionally mount the unchanged private Q44
`inputs.json` at `/private/tmp/q44-inputs-warm-20260928-db/inputs.json:ro`.
T09b's existing wiring check reads this manifest to construct guarded commands;
it does not execute them. Use a new output directory:

```sh
Q44_BUNDLE=/absolute/private/retained-q44-bundle
rtk docker run --rm --network none \
  --entrypoint /experiment/.venv/bin/python \
  -v "$PWD:/workspace:ro" -v "$Q68_INPUTS:/inputs:ro" \
  -v "$Q44_BUNDLE/inputs.json:/private/tmp/q44-inputs-warm-20260928-db/inputs.json:ro" \
  -v "$Q68_RESULTS:/results" -w /workspace \
  pdf-t10-core:20261001-c -B tests/pdf_processing/q03/regression.py \
  --fixtures /inputs --out /results/current --scope current
```

The observed manifest SHA-256 was
`6d3b7f5ffd761d2a581b2708c45676e9655905f88389a1363244305e2ffc5ca2`.
Logs remain private; `summary.json` lists every selected module, test count,
return code and log location. The checked-in #68 result contains only metadata
and log seals. Existing Q03/Q04 `run_suite.py` entry points remain historical;
`q03/test_q03_combined.py` additionally requires the twelve original Q01 page
checkpoints and is outside #68's eight-module/current scope. Their private files
were not recovered here. This is an explicit coverage boundary, not a skip or a
claim that every historical suite passes. Prior cluster qualification remains
identity-specific and unchanged.

## Dependency contract

The retained Q01/Q02 → Q03 producer comparison still proves equal group/assembly
projections and changed downstream projections. It now uses both retained
inventories rather than silently treating current continuation-v3 as Q03.
Separate current-producer checks prove that continuation changes invalidate
group/assembly and that representation-only changes preserve parser/selection/
OCR projections while invalidating evidence/finalize. Q02's operation-contract
checks still cover parser/method invalidation; accepted old requests cannot be
reinterpreted using the new relationship policy. Direct downstream dependency
projections do not themselves include continuation: upstream operation IDs carry
that invalidation, as described in `../q04/STAGE-IMPACT.md`.
