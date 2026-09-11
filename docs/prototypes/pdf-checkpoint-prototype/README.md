# PDF checkpoint backend experiment (THROWAWAY)

This is a real Python/Docling experiment for `docs/design/pdf-checkpoint-prototype-brief.md`.
It is not production code and its JSON is not a Canonical Knowledge schema.
See [VERDICT.md](VERDICT.md) for the original local measurements. The subsequent
[Kubernetes extension verdict](k8s/VERDICT.md) records real Pod-loss/shared-storage
results, overhead and remaining limits; [its runbook](k8s/README.md) reproduces that gate.

## Run the reconstruction gate

From the repository root (Python 3.12, `uv`, network access for initial packages/models):

```sh
uv sync --locked --project docs/prototypes/pdf-checkpoint-prototype
uv run --no-sync --project docs/prototypes/pdf-checkpoint-prototype python docs/prototypes/pdf-checkpoint-prototype/run.py
```

The second command downloads the fixed 51-page source PDF and exact model snapshots,
creates a two-page raster-only derivative, then runs baseline, capture/crash, and
fresh-process reconstruction for both PDFs. It compares **every** output JSON field.
Each run gets a fresh directory under `PROTOTYPE-wipe-me/reproduction-*`.
Conversion runs offline after model acquisition. Models, fixtures and large outputs
remain local/ignored. The raster fixture is a synthetic scan, not a noisy physical scan.

The captured machine's dependency versions, CPU configuration, model snapshot and
file digests are in `evidence/native-method.json`; `uv.lock` pins dependencies.
`prepare_models.py` acquires exact commits and sets the local Hugging Face refs that
the unchanged Docling configuration uses. Execution validates all model-file digests.
The method comparison deliberately rejects runtime/platform/package differences;
a different machine is a **new experiment**, not a compatible checkpoint restore.

## Inspect the actual capture/replay boundary

```sh
P=docs/prototypes/pdf-checkpoint-prototype
$P/.venv/bin/python $P/experiment.py capture $P/fixtures/llm-survey-2303.18223v1.pdf --out $P/PROTOTYPE-wipe-me/my-capture --crash-before-assembly
# Expected exit 73, after durable completion manifest and before document assembly.
$P/.venv/bin/python $P/experiment.py restore $P/fixtures/llm-survey-2303.18223v1.pdf --checkpoint $P/PROTOTYPE-wipe-me/my-capture --out $P/PROTOTYPE-wipe-me/my-replay
```

Use fresh `--out` paths. The low-level CLI is intentionally not an idempotency API.
`--start/--end` select original page numbers. `--checkpoint-only` saves page artifacts
without document assembly. `--crash-after-page N` exits a parsing child immediately
following that page's file persistence. On **restore**, `--crash-before-assembly`
is a historical flag name: it exits **after assembly, before document output persistence**
(exit 74). Logs identify the exact failure point.

`evidence/checkpoint-sample/page-0005.json` plus its PNG are a complete individual
page sample. The entire 51-page checkpoint and documents are retained in ignored
scratch on the experiment machine. `evidence/native-complete.json` lists their digests.
A single page sample cannot assemble the whole document.

## Sizing and Temporal

```sh
P=docs/prototypes/pdf-checkpoint-prototype
$P/.venv/bin/python $P/sizing.py
uv venv $P/.temporal-venv --python 3.12
uv pip install --python $P/.temporal-venv/bin/python -r $P/temporal-requirements.txt
```

Sizing measures groups of 1, 5 and 10 on source pages 1–10, each group in a new process.
This is a bounded CPU sizing experiment, not a production throughput benchmark.

The Temporal harness uses the original measured `PROTOTYPE-wipe-me/native-capture-v2`
and `native-baseline` directories. After a new `run.py` run, copy its native-capture
and native-baseline directories to those two locations **in a fresh scratch tree**,
or update `METHOD` and the baseline path in `recovery.py` for that experiment.

In one terminal, start an isolated server:

```sh
P=docs/prototypes/pdf-checkpoint-prototype
temporal server start-dev --ip 127.0.0.1 --port 7239 --ui-port 8249 --db-filename $P/PROTOTYPE-wipe-me/temporal-reproduction.db
```

In another terminal:

```sh
P=docs/prototypes/pdf-checkpoint-prototype
PDF_PROTOTYPE_RUN=my-new-run PDF_PROTOTYPE_STORE="$PWD/$P/PROTOTYPE-wipe-me/my-new-store" $P/.temporal-venv/bin/python $P/recovery.py
```

Use a fresh run prefix and store for each fault trial. It runs a five-page-group
workflow with injected failures, then a second workflow that must reuse all outputs.
The local filesystem is outside the parsing child processes, but **is not a proven
Kubernetes/shared artifact store**. The harness is sequential and uses local atomic
hard-link registration; it makes no concurrent-race or object-store claim.
Large artifacts never enter Workflow history. History carries paths and references.

`ocr_component.py` runs real RapidOCR on `#/pictures/0` from the resulting parsed
version. It verifies cached crop pixels against coordinates, re-renders the same
source region at 216 DPI, and records source/result/component/model/crop references.
The original transcription mistake and its separate correction are preserved in
`evidence/ocr-reference-initial.json`, `evidence/ocr.json` and
`evidence/ocr-evaluation.json`. Final runs use the corrected `ocr-reference.json`.

## Code map

- `experiment.py`: two thin pipeline subclasses, explicit checkpoint contract, stage guards and measurement.
- `compare.py`: lossless full-document comparison.
- `fixtures.py`, `prepare_models.py`, `run.py`: captured inputs and repeatable execution.
- `sizing.py`: bounded group-size measurements.
- `recovery.py`: real Temporal Activities, immutable-output registration/reuse and fault injection.
- `ocr_component.py`, `evaluate_ocr.py`: actual component OCR and transparent reference re-scoring.
- `summarize.py`: consolidates measured final Temporal evidence.

Stop the development server with Ctrl-C when finished. Do not delete scratch before
preserving any evidence you need. No production code or canonical schema is changed.

Performance diagnosis: [matched direct/Temporal and cold/warm measurements](performance/REPORT.md) explain the normal-path cost without attributing the whole slowdown to Temporal.
