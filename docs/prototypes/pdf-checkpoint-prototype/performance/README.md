# PDF checkpoint performance diagnosis

Throwaway backend experiment. Read [REPORT.md](REPORT.md) for measured conclusions. This extends the [Kubernetes recovery experiment](../k8s/VERDICT.md); it does not replace or alter its fault evidence.

## Question and feedback loop

Explain the previously measured 112.25 s workflow versus 50.08 s native process without conflating orchestration, enrichment, checkpoint output, and process lifetime. `/diagnosing-bugs` was applied as a falsifiable performance investigation, not a correctness bug or a production optimization request.

Fast historical accounting:

```sh
python3 docs/prototypes/pdf-checkpoint-prototype/performance/trace_accounting.py
```

The initial five-page real-parser smoke test was followed by three repeated trials per fixture/variant. `run_matrix.py` is resumable and preserves successful trials in its index. `analyze.py` reproduces the compact report statistics without Docker.

## Runtime and scope

Use the exact existing `pdf-checkpoint-prototype:linux-v2` image from the K8s runbook, digest `sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`. No package/model/platform identity guards are removed. The same Linux baseline artifacts are copied to `/reference`; macOS artifacts cannot stand in for them.

`entry.py` wraps the original adapter with timings. It retains the original parsing, page checkpoint format and guarded restoration. Each subprocess starts a new converter; the explicitly labeled warm variant instead keeps a converter in one sequential subprocess. Warmup is separate, output/state are fresh per request, and restoration still runs in a fresh process. Warm direct execution is a feasibility experiment, not a validated concurrent or crash-recoverable warm-worker implementation.

The matrix compares native 51 pages (groups of five) and scanned two pages (groups of one), separately:

- Whole conversion and JSON/Markdown export, without enrichment.
- Identical grouped parsing, checkpoint storage, assembly, final export and fidelity checks, executed directly.
- The same grouped activity implementation through real Temporal, one activity at a time, no retries in these normal-path trials.
- Direct grouped execution with a warm converter, same durable output/fidelity checks.

Both whole/grouped produce the same final document, but grouped additionally persists internal page checkpoints. This is a deliberate product-cost difference, not equal internal output scope. Component image OCR is excluded from all matrix variants; historical OCR evidence is reported separately.

## Local experiment setup

Inspect Docker context, Kubernetes context and nodes first. Only use confirmed disposable local infrastructure. The measured namespace was `pdf-checkpoint-performance` on the existing local kind worker `internal-a2a-vs6-local-worker2`; do not apply these manifests to an unrelated context. `storage.yaml`, `temporal.yaml` and `bench.json` select that node and therefore need an explicit local-node adjustment elsewhere.

Create the namespace, then a `store-access` Secret with random disposable `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` keys. Generate values into temporary files and use `kubectl create secret generic --from-file`; never print the credentials or commit them. Apply the three manifests, wait for object store and Temporal readiness, then copy this prototype tree's `performance/` directory to `/experiment/performance` in Pod `bench`. Copy the previously exported Linux `baseline/` directory as `/reference`.

The resource ceiling is 5 GiB memory per bench Pod. CPU is not quota-limited (`cpu.max = max 100000`); model libraries use the existing four-thread configuration. Run one matrix at a time. This is a shared local Docker VM, not dedicated benchmark hardware.

```sh
kubectl -n pdf-checkpoint-performance exec bench -- \
  /experiment/.venv/bin/python performance/run_matrix.py
```

The output root is `/experiment/PROTOTYPE-wipe-me/performance-matrix`. Each successful grouped trial reads back hashed diagnostics, checks the complete final JSON against the Linux baseline, and removes only its own fresh S3 prefix to bound scratch usage. Export results before deleting the namespace.

For publication polling attribution, prepare frozen **real** accepted parser output on the host, copy it into the bench Pod as `/pub-fixture`, then run:

```sh
python3 docs/prototypes/pdf-checkpoint-prototype/performance/prepare_publication_fixture.py
kubectl -n pdf-checkpoint-performance exec bench -- \
  /experiment/.venv/bin/python performance/publication.py
```

This paired ablation publishes actual files through real MinIO and conditional registration/readback. It isolates a one-second polling wait versus awaiting completion; it is not a second end-to-end parser benchmark. Export `/experiment/PROTOTYPE-wipe-me/performance-publication` too.

## Evidence and cleanup

Compact measurements live in `evidence/`; large whole-document outputs and process logs are kept in ignored `../PROTOTYPE-wipe-me/performance-evidence/`. `analyze.py` reads the compact matrix. Stage timings can overlap; only interval unions are counted as wall coverage. Linux `ru_maxrss` is converted from KiB to bytes during analysis; a warm process's high-water mark is cumulative, not a per-request allocation measurement.

Delete only the dedicated namespace after evidence export:

```sh
kubectl delete namespace pdf-checkpoint-performance --wait=true
```

Retain the original K8s evidence, existing kind cluster, cached images and unrelated namespaces. These files are not production infrastructure or canonical schema decisions.
