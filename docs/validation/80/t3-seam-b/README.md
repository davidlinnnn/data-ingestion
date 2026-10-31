# #132 Seam B: the corpus paper with the most pictures, with local enrichment

Run 2026-10-31 on macOS arm64 (CPU only) with [run.py](run.py), on the #131 stack: Temporal CLI
dev server (Server 1.32.0), the RustFS S3 stand-in from `tests/s3/compose.yaml`,
`tools/fake_admission`, and one `kp-processing worker --queue orchestration|inference`
subprocess per task queue on the DEV profile (`tests/profiles/paper-pdf-dev.yaml`:
`docling-parse@1`, `picture-ocr@1`, `code@1`, `table-status@1`). Paper: corpus index 20,
`20-2505.03335v1.pdf`, 50 pages, the one with the most pictures in the census of all 20 papers
([census.py](census.py), counts in [census.json](census.json): 22 pictures, next 15 and 14;
also 38 code blocks and 9 tables; third-party, not in git).
Raw numbers: [evidence.json](evidence.json). The Processing Result quotes the paper, so the
evidence keeps statuses, counts and content digests only.

| Case | What ran | Result |
|---|---|---|
| A | Uninterrupted run, fresh bucket | Complete in 40.9 s: 10 parse groups, assemble, inventory, one `enrich_local` on the inference queue, finalize. 69 items, all with outcome records and none reused: 22 picture-ocr, 38 code, 9 table-status, all `unverified` (none `failed`, none `no_text`); 24 of 38 code items have quantized indentation. 18 reports, seq 1–18, enrich progress 0 → 69 of 69 items, the last pointing at the result. 184 objects added under `documents/`: the negative control that shows C's listing sees new objects |
| C | New request for the same document | Complete in 1.6 s; `enrich_local` returned 69 outcomes, all `reused: true`; no object added under `documents/`; every enrichment `reused: true` with the same status as A |
