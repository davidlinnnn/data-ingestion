# #133 Seam B: VLM enrichment against a real model

The DEV profile (`tests/profiles/paper-pdf-dev.yaml`, VLM component `openai/gpt-6-luna`) runs
one paper through the real stack: Temporal dev server, the RustFS S3 stand-in,
`tools/fake_admission`, and one `kp-processing worker` process per queue (`orchestration`,
`inference`, `vlm`). Corpus paper index 20 (50 pages; third-party, not in git). Only the 20
public corpus papers may be sent to the provider.

## Scenarios and acceptance criteria

| # | Scenario | Acceptance criteria |
|---|---|---|
| F | A local stand-in answers every request with the canned answer after 3 s; fresh bucket. Runs first: if it fails or needs more than 150 requests, nothing is sent to the real model | exit 0; every receipt ok; every latency 3–4 s; enrichment counts per method equal R's |
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

`record.py` (all 20 papers, one real run each) saves each registered provider response to
`tests/fixtures/vlm/<method>/<params_digest>.json`: the full response JSON only, never an image
or a request body. `tests/stages/test_enrich_vlm.py` feeds them to schema parsing and the status
rule. The company VLM's fixtures are re-recorded on the company network.

The fixtures were re-recorded on 2026-11-01 after the #133 accuracy check
(`../t4-accuracy/README.md`) changed the picture-interpretation prompt and set
`reasoning_effort` "high" on both VLM methods. They were re-recorded again on 2026-11-02 for
#152, which added a letter-style rule to the formula prompt and the letter-style comparison to
the `disputed` check. R, C and F above ran with the earlier requests; the request changes do not
touch the Seam B mechanics they cover.

`record.py` results (`recorded.json`, #152): all 20 documents complete. Papers 1–12 ran first
(run `491fba`). The network dropped during that run, so every request from paper 13 on failed
with `CONNECTION`; papers 13–20 were run again (run `151724`). The failed requests were never
answered, so the spend estimate does not count them. There were 401 requests: 377 ok, 12
invalid and 12 unavailable. They used 541,892 prompt tokens and 460,401 completion tokens,
about US$0.28. The run saved 382 fixtures: 160 picture-interpretation and 222 formula. Two
older picture-interpretation fixtures stay: their pictures timed out this time.

- Papers 11, 12 and 14: the model did not answer one picture each within 60 s, three times.
  Those pictures' 4 fields ended `failed`/`SERVICE_UNAVAILABLE`, the documents completed, and
  the redrive markers were written and listed. The provider may still bill the cut requests;
  their tokens are unknown and not in the estimate.
- Paper 16: the model answered `{"latex": ""}` 12 times; 5 formulas ended `failed`/`EMPTY_OUTPUT`.
- Statuses over the 20 papers: formula 183 unverified, 34 disputed, 5 failed (before #152: 209,
  12, 1); picture-interpretation 640 unverified fields, 16 failed; code 182 unverified.

## Known limits

- With `reasoning_effort` "high", per-paper median latency ranges from 3.3 s to 21.7 s and
  three pictures reached the 60 s total deadline. A slower company VLM will hit it more often;
  the deadline and the effort are the two settings to weigh against each other.
- Every corpus code block has a text layer, so the code fallback has no real-response fixture.

## Run

```sh
env HF_HUB_OFFLINE=1 OPENAI_API_KEY=... .venv/bin/python docs/validation/80/t4-seam-b/run.py <corpus manifest> 20
```

Recording the corpus fixtures:

```sh
env HF_HUB_OFFLINE=1 OPENAI_API_KEY=... .venv/bin/python docs/validation/80/t4-seam-b/record.py <corpus manifest>
```
