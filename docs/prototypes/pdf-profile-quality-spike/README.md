# S2 PDF profile quality — THROWAWAY

Question: can the pinned Docling/RapidOCR baseline preserve predeclared English, Traditional Chinese and mixed content through direct native/scanned/mixed parsing and independent crop recognition?

Issue: https://github.com/davidlinnnn/data-ingestion/issues/35. Baseline: `85925faa5b6167ee6e750fd02a0f3930d7ed8089`. This is a direct executable extraction-quality spike, not Temporal integration, a production selection policy, or a throughput benchmark.

## Run

Use the baseline prototype's pinned Python 3.12 environment and already acquired model cache. No model download is needed; Hugging Face runs offline. From this directory:

```sh
/path/to/baseline/.venv/bin/python spike.py prepare --preserve-aspect --output rerun
/path/to/baseline/.venv/bin/python spike.py measure --cache /path/to/baseline/PROTOTYPE-wipe-me/hf --output rerun
```

Preparation requires macOS STHeiti Medium (font hash recorded). Recognition can use the checked-in PDF/PNGs elsewhere without generating or installing the font. The PDF includes a subset for native rendering; the standalone system font is not copied. Before interpreting a different machine, record its model/runtime identities and render the PDF to check glyphs.

`artifacts-aspect` is the visually checked, corrected fixture and primary evidence. Its manifest freezes expectations before recognition. `artifacts` preserves the rejected preliminary fixture/run: anisotropically stretched scans and a CID font with missing rendered native glyphs. Preliminary results are diagnostic evidence about fixture construction, not legitimate general language-quality conclusions. No threshold was changed after either run.

The exact-line checker requires all declared lines in order after whitespace removal, with no Traditional/Simplified folding or error tolerance. This is a **provisional diagnostic criterion**, not a user-reviewed production quality requirement. Both the criteria and corpus representativeness need review before #41 adopts profiles.

Source PNG recognition is an ideal-input diagnostic: it uses source image bytes rather than inferred production component crops. The native page's PNG is a separately rendered control, not its embedded PDF representation. Passing it does not validate crop selection, coordinate transforms or general page OCR quality.

All conversion runs call uninterrupted `DocumentConverter` directly; there is no checkpoint restoration, regrouping or custom parsing adapter in this spike. Full Docling JSON and Markdown preserve the untouched outputs. Therefore this does not independently requalify the option-3 adapter's fidelity; that remains the fixed #30 baseline and subsequent integration gates.
