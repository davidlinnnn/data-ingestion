# THROWAWAY — native paper and selected book-chapter diagnostic

Continuation of S2 #35 under the user's revised v1 scope. Earlier synthetic and real-scan verdicts remain unchanged historical evidence. Start with [VERDICT.md](VERDICT.md).

```sh
./run.sh /absolute/path/to/pdf-s2-candidates-2026-09-13
python3 analyze.py
```

The source directory must contain `user-selected/` with the three exact original PDFs listed in [plan.json](plan.json). Only eight selected pages are passed to Docling individually. The 1,151-page book is never converted in full. Docker uses the existing immutable Linux image in `run.sh`, a read-only source mount, separate outputs, 4 CPU / 5GiB cap and no network. All 17 baseline model hashes are checked before inference.

`prepare.py` encodes the original visual plan; do not overwrite the fixed plan to accommodate results. Full source PDFs are neither copied nor committed. Source crops, renders and full third-party parsed outputs stay ignored under `local/`; hashes are retained in `EVIDENCE.json`. They can be regenerated from matching source bytes. Committed material is restricted to bounded excerpts, expectations, scores, model identities, code and findings.

The checked-in script uses plain uninterrupted Docling with OCR off and manual figure crop OCR controls. It is not a production selection engine, Temporal integration, canonical publication, formula enrichment or whole-corpus quality benchmark.
