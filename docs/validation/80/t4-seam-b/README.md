# #133 Seam B: VLM enrichment against a real model

The DEV profile (`tests/profiles/paper-pdf-dev.yaml`, VLM component `openai/gpt-6-luna`) runs
one paper through the real stack: Temporal dev server, the RustFS S3 stand-in,
`tools/fake_admission`, and one `kp-processing worker` process per queue (`orchestration`,
`inference`, `vlm`). Corpus paper index 20 (50 pages; third-party, not in git). Only the 20
public corpus papers may be sent to the provider.

## Scenarios and acceptance criteria

| # | Scenario | Acceptance criteria |
|---|---|---|
| F | A local stand-in answers every request with the canned answer after 3 s; fresh bucket. Runs first: if it fails or needs more than 150 requests, nothing is sent to the real model | exit 0; every receipt ok; every latency >= 3 s; enrichment counts per method equal R's |
| R | The real model (`https://api.openai.com/v1`); fresh bucket | exit 0; outcome `complete`; no incomplete receipt; 0 < requests <= the request cap (`3 x items + 20`) |
| C | A second request for the same document, same bucket as R | exit 0; no VLM request; nothing new under `documents/`; every enrichment reused; statuses equal R's |

## Result (run 572808, 2026-11-01)

All three pass; details in `evidence.json`.

| | Wall clock | VLM requests | Latency min / median / max |
|---|---|---|---|
| F | 55.7 s | 38, all ok | 3.0 / 3.0 / 3.0 s |
| R | 128.9 s | 38, all ok | 3.0 / 5.1 / 53.5 s |
| C | 1.4 s | 0 | - |

- R sent 22 picture-interpretation and 16 formula requests. All 38 code blocks had a text
  layer, so the code fallback sent nothing.
- R used 69,243 prompt tokens and 40,829 completion tokens. At gpt-6-luna's standard price
  (US$0.10/M in, US$0.50/M out) that is about US$0.03.
- Statuses in R (per field for picture-interpretation): code 38 unverified; formula 13
  unverified and 3 disputed (`FORMULA_NATIVE_MISMATCH`); picture-interpretation 88
  unverified; picture-ocr 22 unverified; table-status 9 unverified.
- Of the 3 disputed formulas, 2 are real model deviations: a `·` read as `+` with an added
  `i=1`, and an added `i=1` and `x=`. The third is a box artifact: the formula box holds a list
  label "1.", so the text layer has a digit the formula lacks.
- F's 15 disputed formulas come from the canned latex, which matches none of the paper's
  formulas, so they show the check sees differences.
- F's wall clock was recovered from the admission reports. During the run, C's timer
  overwrote F's; `run.py` was fixed afterwards.

## Fixtures

`run.py` saves each provider response from R to
`tests/fixtures/vlm/<method>/<params_digest>.json`: the full response JSON only, never an image
or a request body. `tests/stages/test_enrich_vlm.py` feeds them to schema parsing and the status
rule. The company VLM's fixtures are re-recorded on the company network.

## Known limits

- The slowest response (53.5 s) came close to the 60 s total deadline. A long figure on a
  slower day may time out and be retried.
- Only one paper was recorded. It has no page without a text layer, so the code fallback has
  no real-response fixture.

## Run

```sh
env HF_HUB_OFFLINE=1 OPENAI_API_KEY=... .venv/bin/python docs/validation/80/t4-seam-b/run.py <corpus manifest> 20
```
