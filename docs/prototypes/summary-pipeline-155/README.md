# PROTOTYPE: #155 summary pipeline probe (throwaway)

Question: does the LLM half of the in-platform Document Summary (sections → map →
verify → repair → reduce, decisions B1, B2, B4 on #155) work through the existing
`OpenAIChat` transport against Anthropic's OpenAI-compatible endpoint, and what does it
cost in time, tokens, rewrites and drops on real corpus papers?

No Temporal, no S3, no receipts. `probe.py` reuses `document_summary.request()` for the
sections and `OpenAIChat` unchanged for every call. Run instructions are in its docstring.
Its outputs hold paper text and stay out of git.

## Run (2026-11-03)

Model `claude-sonnet-5-5` through `https://api.anthropic.com/v1/chat/completions`,
`response_format` json_schema strict, thinking at the model default. Papers from the
#80 validation corpus (#134 Seam B assemblies), run one after another, 4 chunks and 8
calls in flight.

| Paper | Native chars sent | Sections | Chunks | Wall time | Section sentences kept / rewritten / dropped | Overview kept / rewritten / dropped |
|---|---|---|---|---|---|---|
| 2 (shortest) | 28,416 | 29 | 4 | 56 s | 24 / 2 / 0 | 5 / 0 / 0 |
| 4 (median) | 58,376 | 34 | 11 | 83 s | 45 / 4 / 0 | 7 / 0 / 0 |
| 20 (longest) | 106,380 | 46 | 16 | 113 s | 75 / 7 / 0 | 11 / 1 / 0 |

Tokens per paper, all calls:

| Paper | Calls (map / verify / repair / reduce) | Prompt tokens | Completion tokens |
|---|---|---|---|
| 2 | 4 / 33 / 2 / 1 | 61,417 | 9,878 |
| 4 | 11 / 60 / 4 / 1 | 164,376 | 25,373 |
| 20 | 16 / 104 / 8 / 1 | 336,433 | 31,168 |

Latency per call, p50 / max: map 5–8 s / 11.4 s, verify about 2 s / 9.6 s,
repair 3–10 s, reduce 7–9 s. No call failed or returned invalid JSON.

## Answers

- **B4 holds.** `OpenAIChat` needs no change: strict json_schema answers parse on the
  first try for all 274 calls.
- **B3's budget is generous.** The longest paper finishes in about 2 minutes against a
  900 s budget; the margin is for queue contention, which this probe does not have.
- **Verify dominates cost:** about 70% of prompt tokens. One judge call per sentence,
  each carrying its section's text.
- **Repair works on the cases seen:** 14 of 158 sentences (9%) were rewritten, none
  dropped. The rewrites fix real overreach (an added "held-out", a "no difference"
  claimed for two reward types when the text gives it for one, a related-work item the
  text never criticises).
- **Not answered here:** whether the judge misses unsupported sentences. Zero drops is
  consistent with a good map step and with a lenient judge alike; that needs the blind
  evaluation in #155's acceptance criteria.

## Observed, for the implementation

- Section sentences run long (40–70 words) because the map prompt asks for the most
  important facts per sentence.
- Rewrites tend to copy the source wording and grow longer.
- The reduce step returned 12 sentences against a target of 13 ("at most").
- Appendix headings that are prompt examples ("Model Output:") get summaries, as A10
  allows.
