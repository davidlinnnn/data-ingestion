# Stock CPU baseline evidence

All seven frozen-source probes completed with unchanged model/source/runner
hashes and live ONNX `CPUExecutionProvider` only. This is diagnostic evidence;
semantic qualification is performed separately. Stock Docling 2.102.0/Core
2.96.0 runs in the existing Python 3.12 environment, CPU four threads, layout/
OCR/table batch one, classification enabled by the library default, and the
same explicitly pinned cached Chinese PP-OCRv6 model set on every page.

| Probe | Case | Elapsed seconds including child lifecycle | Sampled tree peak GiB | Native / OCR / merged cells |
| --- | --- | ---: | ---: | ---: |
| controls-p3-full | G1-C08, 0° | 8.142 | 3.202 | 0 / 117 / 117 |
| controls-p4-full | G1-C09, 90° | 6.293 | 3.209 | 0 / 116 / 116 |
| controls-p5-full | G1-C10, 180° | 6.047 | 3.198 | 0 / 117 / 117 |
| controls-p6-full | G1-C11, 270° | 6.075 | 3.275 | 0 / 118 / 118 |
| controls-p7-selective | G1-C12 | 4.543 | 2.231 | 5 / 4 / 9 |
| controls-p7-full | G1-C12 | 4.564 | 3.233 | 5 / 9 / 9 |
| controls-p8-full | G1-C13 | 4.537 | 3.203 | 0 / 9 / 9 |

Each job holds the shared qualification lock. Guards require 8 GiB available
before launch, sample process-tree RSS every 0.25 seconds with a 6 GiB stop,
and kill/reap the child process group after 180 seconds or a monitor failure.
No guard fired. These sampled measurements are not SLO qualification or an
exact continuous memory peak.

`run.py` and `frozen-inputs.json` were frozen before inference. Within each
`runs/<probe>/`, `conversion-result.json` is the complete serialized provider
result saved before JSON/Markdown export; `document.json` and `document.md`
are unchanged stock exports. `producer.json` saves effective constructor
parameters, resolved configuration, live sessions and embedded-dictionary
identity. `raw-ocr-calls/*.raw.json` saves detections, classification and
recognition before blank/confidence filtering; matching `.output.json` and
`.png` retain filtered provider output and exact OCR input. `cell-merge.json`
retains native cells before OCR, OCR cells before fusion and merged cells.
Full options, package/model hashes and stage timing remain in `method.json`,
`metrics.json` and `events.jsonl`.

Run the saved-evidence integrity check without model inference:

```sh
rtk docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -B docs/research/pdf-core-g2-orientation-2026-10-15/baseline/validate_evidence.py
```

It verifies all seven completed jobs, CPU/provider/options constraints,
pre-export/export document equivalence after provider schema parsing, raw
array consistency, physical pages and frozen input hashes. Its
`evidence-inventory.json` lists exact text instances and coordinates, candidate
same-text source cells, and picture/caption relationships. Exact-text duplicate
groups are empty in these final documents; this is not a normalized or semantic
duplicate verdict. [Language/model interpretation](language-path-note.md) and
[render-coordinate rounding](coordinate-note.md) are recorded separately.

No new recognizer was downloaded; no independent holdout, broad OCR language
coverage, whole-page semantic transcript or production mapper was qualified.
