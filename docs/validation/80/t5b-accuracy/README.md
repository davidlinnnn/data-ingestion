# #155 C1: how well the summary's verify step catches unsupported sentences

`run.py` measures the verify step of the Document Summary (#155) with planted errors. It works
on the kept sentences of the Seam B run on the frozen prompts (`../t5b-seam-b/`, run
`frozen-1`, 2026-11-04):

1. A seeded random sample (seed 155) of kept sentences is drawn, from Section summaries and
   the overview alike.
2. gpt-6-luna rewrites each sampled sentence with exactly one factual error. The program
   assigns the error types in rotation: number, causation, subject, scope, comparison. A
   sentence without a digit never gets the number type.
3. The planted version goes through the production verify request,
   `document_summary.verify_request`, on Claude Sonnet 5.5. It is batched with the rest of its
   Section's kept sentences (D4), or judged alone against its cited Sections for an overview
   sentence. The unaltered batch is judged the same way.

- **Caught**: the planted sentence is judged unsupported.
- **False drop**: an original sentence is judged unsupported.

Invalid plants are counted but kept out of the catch rate. A plant is invalid when gpt-6-luna
left the sentence unchanged, or refused the task (the answer starts with "I can't").

## Result

| | Held-out (15 papers) | Dev (papers 2, 4, 20, 16, 6) |
|---|---|---|
| Sample (pool of kept sentences) | 100 (776) | 50 (290) |
| Invalid plants (planter refusals) | 14 | 5 |
| Catch rate | **80 / 86 = 93.0 %** (95 % Wilson 85.6–96.8 %) | 41 / 45 = 91.1 % (79.3–96.5 %) |
| False-drop rate | **1 / 100 = 1.0 %** (0.2–5.4 %) | 1 / 50 = 2.0 % (0.4–10.5 %) |
| Judge cost | US$1.09 | US$0.79 |

Caught by error type, held-out: number 9/10, causation 23/24, subject 20/21, scope 15/18,
comparison 13/13. Dev: number 3/4, causation 13/13, subject 11/11, scope 8/10, comparison 6/7.
Scope widening ("in every setting", "across all settings") is missed most often.

The 6 held-out misses, as word diffs:
- **Scope widened (3):** "in every setting" and "across all settings" added to a sentence, and
  "non-parametric" dropped from "non-parametric CBR".
- **Near-synonym swap:** "agent" → "worker".
- **Weak number plant:** "per-trajectory" → "per-task". The sentence's only digit is in a
  method name.
- **Added consequence:** "thereby lowering their scores" appended to a 44-word sentence.

The false drop: the judge accepted every figure in the sentence, but called its "OfficeQA gives
smaller gains" a generalisation the text does not state.

## Spot check (the user reviews it)

`spot-check-held-out.json` and `spot-check-dev.json` live under the Seam B output directory,
`~/archive/research/155-summary/frozen-1/`, outside the repo because they hold paper text. Each
holds every missed planted error, every false drop, and every sentence the pipeline rewrote or
dropped in that set's papers (C1), filled with random cases up to 30:

- held-out: 50 items (43 pipeline rewrites/drops, 6 missed plants, 1 false drop)
- dev: 30 items (24 pipeline rewrites/drops, 4 missed plants, 1 false drop, 1 random case)

## Reproduce

```
set -a; . ~/.config/kp-dev/anthropic.env; . ~/.config/kp-dev/openai.env; set +a
.venv/bin/python docs/validation/80/t5b-accuracy/run.py ~/archive/research/155-summary/frozen-1 \
    held-out 100 1 3 5 7 8 9 10 11 12 13 14 15 17 18 19
.venv/bin/python docs/validation/80/t5b-accuracy/run.py ~/archive/research/155-summary/frozen-1 \
    dev 50 2 4 20 16 6
```

`--rescore` in place of N scores the saved `accuracy-SET_NAME.json` again without a request.
The invalid-plant rule was added this way, after the first scoring counted the planter's
refusals as missed errors (catch rate 91/99 held-out).
