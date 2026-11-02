# #134 Seam B: the whole paper-pdf@1 with the Document Summary

The DEV profile (`tests/profiles/paper-pdf-dev.yaml`) runs one paper through the real stack:
Temporal dev server, the RustFS S3 stand-in, `tools/fake_admission`, and one
`kp-processing worker` process per queue (`orchestration`, `inference`, `vlm`, `summary`). Both
external services are local stand-ins, so nothing leaves the machine: the VLM stand-in is
#133's (the canned answer after 3 s), and the summary stand-in serves the DEV mock
(`tests/summary.py`) under the provisional contract. Corpus paper index 20 (50 pages;
third-party, not in git) has pictures, formulas, code and tables; papers 1-19 run the same
scenarios, where a method without inventory items (no code or no formula in the paper) has no
enrichments.

## Scenarios and acceptance criteria

| # | Scenario | Acceptance criteria |
|---|---|---|
| S | Fresh bucket | exit 0; outcome `complete`; every method in `inventory.counts` has enrichments (all six for paper 20); `inventory.counts` has `document-summary`; the summary stand-in got exactly one request at `/v1/summaries` with exactly `document_uid` (the document's), `sections` (each `section_id`, `heading`, `text`; at least one, with text) and `max_sentences`; one summary enrichment with scope `document`, target `["#"]`, input the assembly, status `unverified`; one summary receipt, ok |
| C | A second request for the same document, same bucket | exit 0; no summary request and no external receipt; nothing new under `documents/`; every enrichment reused; statuses equal S's |

## Result (run a496c8, 2026-11-01)

Both pass; details in `evidence-20.json`.

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

## Result on papers 1-19 (2026-11-02)

S and C pass on every paper; details in `evidence-<index>.json`. Every summary was
`unverified`, its two mock sentences supported by the cited section and by word overlap.

| Paper | Pages | S wall clock | C wall clock | Methods without items | Sections | Native text chars | VLM requests |
|---|---|---|---|---|---|---|---|
| 1 | 28 | 34.4 s | 0.8 s | - | 54 | 71,097 | 19 |
| 2 | 22 | 13.0 s | 0.5 s | formula | 36 | 31,933 | 2 |
| 3 | 25 | 34.1 s | 0.6 s | - | 59 | 66,865 | 14 |
| 4 | 27 | 26.6 s | 0.7 s | - | 37 | 67,488 | 7 |
| 5 | 31 | 31.9 s | 0.9 s | - | 62 | 69,877 | 15 |
| 6 | 29 | 31.8 s | 0.8 s | - | 35 | 73,755 | 11 |
| 7 | 18 | 15.3 s | 0.5 s | - | 28 | 47,785 | 8 |
| 8 | 12 | 11.6 s | 0.4 s | formula | 36 | 34,483 | 3 |
| 9 | 28 | 53.3 s | 0.7 s | - | 59 | 64,846 | 30 |
| 10 | 30 | 30.0 s | 0.8 s | code, formula | 53 | 87,577 | 15 |
| 11 | 20 | 29.6 s | 0.6 s | - | 44 | 52,834 | 17 |
| 12 | 28 | 42.8 s | 0.8 s | code | 33 | 70,029 | 32 |
| 13 | 27 | 46.5 s | 0.8 s | - | 63 | 82,594 | 37 |
| 14 | 16 | 27.1 s | 0.5 s | - | 25 | 49,256 | 18 |
| 15 | 27 | 25.0 s | 0.7 s | code | 58 | 62,714 | 7 |
| 16 | 64 | 64.4 s | 1.7 s | - | 39 | 81,793 | 52 |
| 17 | 22 | 22.4 s | 0.6 s | - | 37 | 67,561 | 10 |
| 18 | 18 | 29.2 s | 0.7 s | - | 49 | 55,821 | 15 |
| 19 | 29 | 45.1 s | 0.8 s | code | 63 | 97,651 | 36 |

The largest summary request is paper 20's (136,201 characters); papers 1-19 send 31,933 to
97,651.

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
