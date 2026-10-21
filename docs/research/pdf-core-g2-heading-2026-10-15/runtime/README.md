# Isolated official heading-stage runtime

Runtime: `/private/tmp/pdf-core-g2-heading-20261015/venv/bin/python` (Python 3.12).

Official packages: `docling-slim==2.132.0`, `docling-core==2.99.0`, `docling-parse==7.22.3`. This installs neither the `docling` meta-package nor model packages. The venv occupies about 340 MiB; the isolated pip cache about 75 MiB. No model weights were downloaded. The old prototype venv and its model cache were not modified.

Recreate using the [exact lock](requirements-lock.txt) in a new scratch venv:

```sh
rtk /Users/david/.local/share/uv/python/cpython-3.12-macos-aarch64-none/bin/python3.12 -m venv /private/tmp/pdf-core-g2-heading-reproduce/venv
rtk /private/tmp/pdf-core-g2-heading-reproduce/venv/bin/python -m pip install --cache-dir /private/tmp/pdf-core-g2-heading-reproduce/pip-cache -r docs/research/pdf-core-g2-heading-2026-10-15/runtime/requirements-lock.txt
rtk /private/tmp/pdf-core-g2-heading-reproduce/venv/bin/python -m pip check
```

From the repository root, use a **new output directory**; final evidence must remain immutable:

```sh
rtk /private/tmp/pdf-core-g2-heading-20261015/venv/bin/python docs/research/pdf-core-g2-heading-2026-10-15/runtime/bounded_run.py --output /private/tmp/pdf-core-g2-heading-reproduce/wikiskill --pdf docs/fixtures/agent-self-evolution-pilot-2026-10-11/01-2608.27454v1.pdf --document docs/research/pdf-core-g2-heading-2026-10-15/inputs/wikiskill/document.json --pages 28 --no-outline-ablation
rtk /private/tmp/pdf-core-g2-heading-20261015/venv/bin/python docs/research/pdf-core-g2-heading-2026-10-15/runtime/bounded_run.py --output /private/tmp/pdf-core-g2-heading-reproduce/controls-p1 --pdf docs/fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf --document docs/research/pdf-core-g2-heading-2026-10-15/inputs/controls/runs/controls-p1/document.json --pages 1
```

The guard needs host process-list access for `psutil`; sandbox-only process enumeration fails on this macOS host. It records runner hashes before starting children, sets offline model-cache variables to scratch locations, checks ≥8 GiB available memory, holds `/private/tmp/data-ingestion-pdf-qualification.lock`, and kills/reaps its own process group on timeout, RSS excess or monitor failure. Worker children run through `rtk proxy`. The 180-second execution timer excludes lock wait; 50-ms process-tree RSS sampling is a soft stop.

`heading_stage.py capture-fresh` writes the full normalized old document, every native `SegmentedPdfPage`, and outline JSON before calling the official stage on a deep copy. `reload` is a separate process using only those persisted stage inputs. It asserts byte-identical document JSON and Markdown plus preserved PDF font-cell types. Neither mode invokes a conversion pipeline or ML model.

Canonical evidence directories:

- `wikiskill-final/`: 28 pages, default signals and no-outline ablation.
- `controls-p1-final/`: physical page 1 only, no outline, default signals.
- `runtime-evidence.json`: installed/tagged source comparison, final artifact hashes, frozen runner hashes, package versions and posthoc invariant checks.
- `source/`: exact tagged sources; installed copies match the five runtime files byte for byte.

Attempt trace: `wikiskill-initial-import-failure/` records the initial pre-PDF import failure and sandbox monitor rejection. `attempts/wikiskill-assert-run/` and `attempts/controls-p1-assert-run/` retain earlier successful executions. One earlier successful WikiSkill run was overwritten by the font-assert rerun before attempt preservation was requested; its 1.9275-second summary remains in the tool transcript, and is not used for final measurements. The final directories were created fresh after both runner files were frozen and are the sole cited execution evidence.

Skipped full-pipeline/recovery claims and custom correction logic. Scratch runtime removal would require recreating the venv from the lock; all persisted stage inputs remain in the repository.
