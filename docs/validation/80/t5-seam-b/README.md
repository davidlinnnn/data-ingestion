# #134 Seam B: the whole paper-pdf@1 with the Document Summary

The DEV profile (`tests/profiles/paper-pdf-dev.yaml`) runs one paper through the real stack:
Temporal dev server, the RustFS S3 stand-in, `tools/fake_admission`, and one
`kp-processing worker` process per queue (`orchestration`, `inference`, `vlm`, `summary`). Both
external services are local stand-ins, so nothing leaves the machine: the VLM stand-in is
#133's (the canned answer after 3 s), and the summary stand-in serves the DEV mock
(`tests/summary.py`) under the provisional contract. Corpus paper index 20 (50 pages;
third-party, not in git) has pictures, formulas, code and tables.

## Scenarios and acceptance criteria

| # | Scenario | Acceptance criteria |
|---|---|---|
| S | Fresh bucket | exit 0; outcome `complete`; each of the six enrichment methods has enrichments; `inventory.counts` has `document-summary`; the summary stand-in got exactly one request at `/v1/summaries` with exactly `document_uid` (the document's), `sections` (each `section_id`, `heading`, `text`; at least one, with text) and `max_sentences`; one summary enrichment with scope `document`, target `["#"]`, input the assembly, status `unverified`; one summary receipt, ok |
| C | A second request for the same document, same bucket | exit 0; no summary request and no external receipt; nothing new under `documents/`; every enrichment reused; statuses equal S's |

## Result (run a496c8, 2026-11-01)

Both pass; details in `evidence.json`.

| | Wall clock | Summary requests | VLM requests |
|---|---|---|---|
| S | 55.8 s | 1 (ok) | 38 (ok) |
| C | 1.3 s | 0 | 0 |

- Enrichments in S: code 38 unverified; formula 1 unverified, 15 disputed
  (`FORMULA_NATIVE_MISMATCH`: the canned latex matches none of the paper's formulas);
  picture-interpretation 88 unverified fields; picture-ocr 22 unverified; table-status 9
  unverified; document-summary 1 unverified.
- The request carried 59 sections and 136,201 characters of native text. The real API's input
  limit is unknown; a document this size is the case to ask the other team about.
- The mock's two sentences were supported once by the cited section and once by word overlap.

## Run note

The first attempt used #133's fixed ports (Temporal 7244, fake_admission 8091) while another
session's stack held them: the request started on that session's Temporal, whose workers
failed it at prepare (the paper was not in their bucket). The harness now uses its own ports
(Temporal 7254, fake_admission 8101, stand-ins 8102 and 8103) and refuses to start when any is
taken.

## Run

```sh
env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/80/t5-seam-b/run.py <corpus manifest> 20
```
