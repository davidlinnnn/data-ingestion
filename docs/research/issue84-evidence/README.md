# #84 research evidence — index and storage

Evidence for [#84](https://github.com/davidlinnnn/data-ingestion/issues/84) (first PDF core delivery), collected 2026-10-13 → 2026-10-20. The closure decision is in [`../issue84-closure-decision-2026-10-20.md`](../issue84-closure-decision-2026-10-20.md).

## What is committed

**Merged into `dev` (slim, user decision 2026-10-20):** the closure decision record, this evidence folder with its manifests, and the Markdown reports and plans of each research round (`*.md` up to one level inside each round directory). This is 368 files, about 9.6 MB.

**Full curated evidence:** commit [`2524a1a5`](https://github.com/davidlinnnn/data-ingestion/tree/2524a1a50d7f05dc8e33f2a1831d7bdcf5344774/docs/research) on branch `research/issue84-pdf-core` (3,030 files, about 143 MB). It adds scripts, registrations, review records, summary JSON and small figures, and is what the #84 decision record links to. Keep that branch.

Per user decision U5, nothing larger was committed: text files ≤ 2 MB and images ≤ 300 KB, from the top two levels of each round directory. Third-party papers (arXiv PDFs and LaTeX sources) are not committed; their URLs and SHA-256 are in each round's `jobs.json` / `corpus` manifest.

## What is not committed

| Manifest | Category | Where the bytes are |
|---|---|---|
| [`local-only-A-manifest.json`](local-only-A-manifest.json) | A — kept for reuse by #82/#83: final-config E0 Docling outputs, LaTeX and arXiv-HTML gold sets, adjudication page images, live API raw responses and receipts | Local machine, original paths under `docs/research/` |
| [`archived-C-manifest.json`](archived-C-manifest.json) | C — raw outputs of earlier exploration rounds (2026-10-13 → 10-20 morning) and the superseded round-2 heading variant | Local archive `~/archive/issue84-research-raw/` (same relative paths) |
| [`deleted-B-manifest.json`](deleted-B-manifest.json) | B — superseded and reproducible outputs, deleted with user approval: ablation variants V1/V2/V4, `do_cell_matching=False`, CodeFormulaV2 E1 runs, mock/relocation bundles | Deleted. Regenerate from the pinned configurations in each round's registration |

Model weights (VJev-Vision, vllm-sr d3-nano/d3-mini; Apache-2.0) live outside the repo at `~/models/issue84/`; revisions and hashes are in the W4/W4b reports.

Every manifest entry records path, size and SHA-256. The local full-mode guard (`tests/pdf_research/check.py`, not in this branch) references some archived paths and needs the archive path to re-verify.

## Round index (2026-10-20)

| Round | Directory | Topic |
|---|---|---|
| R1 | `pdf-core-r1-method-2026-10-20/` | Cross-owner source-group method (zero inference) |
| A/C live | `pdf-core-r1-method-2026-10-20/live-preflight/{round3-luna,round4-local-ocr,round5-strict,round6-sol}` | Luna attempts 1–2, local OCR, Sol ceiling |
| W2 | `pdf-core-w2-native-coverage-2026-10-20/` + `-round2/3/4-` | Native paper layout coverage, 36 papers / 715 pages; decision record in round 4 |
| W3 | `pdf-core-w3-structured-elements-2026-10-20/` | Formula / code / table / image accuracy |
| W3b/W3c | `pdf-core-w3b-2026-10-20/` | arXiv-HTML gold, table cell matching, code native-first, cheap signals |
| W4 / W4b | `pdf-core-w4-decision-gate-2026-10-20/`, `pdf-core-w4b-d3-2026-10-20/` | Decision models (VJev-Vision, d3-nano/mini) as a quality gate |
