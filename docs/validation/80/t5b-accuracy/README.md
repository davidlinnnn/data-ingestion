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

## #164: reason before verdict (measured, reverted)

The spot check's 4 wrong verdicts (2 false drops, 2 pipeline drops) all had a reason that ended
"actually supported" with `supported` false. #164 tried putting `reason` before `supported` in
`VERIFY`, so the model would reason before it decided. `--rejudge` judged the same plants again
twice: once with the frozen order as a control for judge noise (the judge runs at the default
temperature), and once with reason first.

| | Held-out base | control | reason first | Dev base | control | reason first |
|---|---|---|---|---|---|---|
| Catch rate | 80/86 = 93.0 % | 80/86 | **76/86 = 88.4 %** (79.9–93.6 %) | 41/45 | 40/45 | 40/45 |
| False drops | 1/100 | 0/100 | 1/100 | 1/50 | 0/50 | 0/50 |
| Answers with the reason first | | 0/205 | 205/205 | | 0/105 | 105/105 |
| Judge cost | | US$1.12 | US$1.12 | | US$0.82 | US$0.78 |

Compared with the control, reason first newly missed 5 held-out plants and newly caught 1. The
control, compared with the base, moved 2 each way. Held-out scope errors fell to 12/18 caught,
from 15/18 (base) and 16/18 (control). In the 5 new misses, the judge restates what the
Section says and concludes that the sentence "summarizes accurately", but never sees the one
word the plant changed: "all" added twice, "LLMs" → "AI systems", "CBR" → "RAG", and "across
all settings" added. With the verdict first, its reason names that word.

The 4 wrong verdicts:
- **The 2 false drops** (held-out paper 1, dev paper 6) are judged supported in the control
  too, so judge noise alone flips them. Reason first adds a new held-out false drop (paper 1).
- **The 2 pipeline drops** (paper 8 §5.1.3, paper 6 §F) are still unsupported in the control.
  Reason first judges both originals supported. It also judges supported the original of
  paper 6 §3.4, which the spot check rated a correct drop.

Since the catch rate fell, `VERIFY` keeps the frozen order (supported, then reason), as #164
asks, and frozen-1's verify prompt still holds for the numbers above. The other change of #164
alters only how degenerate repair answers are handled. A repair answer that is not a sentence
(fewer than three words), or that has quotes but no sentence, is now sent once more. If it is
degenerate again, the sentence is dropped without a second verify. Of frozen-1's 67 repairs, 2
were degenerate. Paper 6's `x` would be sent again. Paper 15's `""` would be sent again only
if it came with quotes, and frozen-1's summaries do not keep the answers' quotes. This change
has unit tests and was not run against the model.

## Reproduce

```
set -a; . ~/.config/kp-dev/anthropic.env; . ~/.config/kp-dev/openai.env; set +a
.venv/bin/python docs/validation/80/t5b-accuracy/run.py ~/archive/research/155-summary/frozen-1 \
    held-out 100 1 3 5 7 8 9 10 11 12 13 14 15 17 18 19
.venv/bin/python docs/validation/80/t5b-accuracy/run.py ~/archive/research/155-summary/frozen-1 \
    dev 50 2 4 20 16 6
```

#164's runs judge the saved plants again: the control as below, and `reason-first` the same
way with `VERIFY`'s `reason` moved before `supported`:

```
.venv/bin/python docs/validation/80/t5b-accuracy/run.py ~/archive/research/155-summary/frozen-1 \
    held-out-control --rejudge=held-out 1 3 5 7 8 9 10 11 12 13 14 15 17 18 19
.venv/bin/python docs/validation/80/t5b-accuracy/run.py ~/archive/research/155-summary/frozen-1 \
    dev-control --rejudge=dev 2 4 20 16 6
```

`--rescore` in place of N scores the saved `accuracy-SET_NAME.json` again without a request.
The invalid-plant rule was added this way, after the first scoring counted the planter's
refusals as missed errors (catch rate 91/99 held-out).
