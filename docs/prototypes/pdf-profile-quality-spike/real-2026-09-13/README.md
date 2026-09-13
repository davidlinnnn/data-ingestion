# THROWAWAY S2 real-source diagnostic

This follows the original S2 commit `12ac5a2` and preserves its synthetic evidence. Start with [VERDICT.md](VERDICT.md). Parent investigation: https://github.com/davidlinnnn/data-ingestion/issues/35.

To repeat using the original source bytes locally:

```sh
./run.sh /absolute/path/to/pdf-s2-candidates-2026-09-13
python3 analyze.py
```

Requires the immutable local Linux image identified in `run.sh`; it includes the pinned runtime and models. Source PDFs mount read-only; Docker networking is disabled. `prepare.py SOURCE_DIR` records the initial hand-transcribed plan but should not be rerun to overwrite the committed plan during comparison. Exact matching ignores whitespace only; `summary.json` preserves and explains invalid/confounded probes.

Full source PDFs are not copied or committed. Full parsed outputs, crops, rendered pages and run logs remain in ignored `local/` because redistribution terms were not assessed. Hashes of these local files are in `EVIDENCE.json`; rerunning creates them from the original source hashes. Only bounded expected excerpts, scores, provenance, runtime metadata and reproducibility code are committed.

Source location used for this run: `/Users/david/work/data-ingestion/docs/fixtures/pdf-s2-candidates-2026-09-13`. Candidate URLs and SHA-256 hashes are embedded in `plan.json`. The executable run does not contact those URLs or download missing models.
