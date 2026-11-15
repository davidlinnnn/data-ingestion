# #212 paper-pdf@1: identifier lines that the layout labels as formulas

Run 2026-11-15 on this Mac with [run.py](run.py) (parse and inventory of the 21 papers, no VLM)
and [#199's run.py](../199/run.py) (paper 16 end to end, Sonnet 5.5 as in #199).

## Verdict

**Fixed.** The 35 SWE-bench ids that docling labels as formulas on page 25 of paper 16 are now
text lines in the canonical document, with the text layer's characters. In paper 16's end-to-end
rerun no formula is `failed`, `formula@1` sent no invalid request and page 25 sent none at all,
and all 60 ids on the page appear verbatim in the assembly's text. On the 21 papers, these 35
are the only items no longer sent to `formula@1`, and the other 222 send the same request as
before: the real formulas get #199's input, and t4's verdicts on them stand.

Two counts in the ticket differ from the records:

- **Page 25 of paper 16 has 35 formula-labeled ids, not 44.** 44 is the paper's whole formula
  count in #199 (`papers/16.json`): 9 real formulas on page 22 and the 35 ids. The page lists 60
  ids; docling labels the other 25 as list items or text.
- **t4's 46 formulas hold two of these ids, not one:** p16-e1d8a234b6b9 (`django__django-12143`,
  #199 FAIL: empty answer) and p16-35fa058a6093 (`sphinx-doc__sphinx-9698`, #199 PASS: Sonnet
  answered with `\text`).

## The change

`docling-parse@1`'s assembly writes a formula node whose text layer (`orig`) is one identifier
as a text item whose `text` is its `orig`
([pipeline.py](../../../src/kp_canonicalization/methods/docling_parse/pipeline.py),
`IDENTIFIER`). The inventory lists only nodes labeled `formula`, so these lines never reach
`formula@1`. The inventory code is unchanged.

Why the native parse and not the formula prompt:

- The line has no math, so it is body text. Its characters come from the text layer verbatim; a
  model's `\text{django\_\_django-12143}` is escaped LaTeX, not the source characters.
- No request at all: no VLM request, no d3 check, no `failed` item. A prompt change would still
  send 35 VLM and 35 d3 requests for paper 16 and depend on the model answering.
- docling leaves a formula node's `text` empty (the decoded LaTeX belongs there), so dropping the
  item from the inventory alone would leave an empty formula in the canonical document.

The rule: after an optional list bullet (`·` or `•`) and whitespace, the whole text layer is one
token of ASCII letters, digits and `_ . / -` that has a run of three letters and joins two
letters or digits with `_ . / -`. Spaces, operators, parentheses or non-ASCII characters keep the
node a formula; so does a lone word or run-together subscripts (`softmax`, `xij`), and so does
short math such as `x-1`, which has no three-letter run. The code review found the first version
of the rule, without the joining character, too broad: it would have turned `xij` into text with
no status. The rule left matches a math display only if its text layer is a single hyphenated
or dotted word such as `log-sum-exp`, as text without a status; none of the 257 items is one. The test is `test_a_formula_whose_text_layer_is_one_identifier_becomes_a_text_line`
([test_parse.py](../../../tests/stages/test_parse.py)); it builds the document by hand and asserts
no docling layout result (PR #168).

**Side effect:** the document summary reads text items. The text of paper 16's section B.2
("SWE-bench Tasks") now holds all 60 ids instead of 25, and its summary target went from 1
sentence to 2.

## Parse and inventory of the 21 papers

`run.py` ran prepare, parse, assemble and inventory in process on `paper-pdf@1.yaml`, without
the VLM: once on the code before the change (`before`, `docling-parse@1` module digest
`6cb4374d…`, the one #199 ran) and once after it (`after`, `565aeae5…`). Both runs used the
final script; `before` reused the parse it had cached under the old digest. The figures below are
the second round, after the code review narrowed the rule; the first round gave the same counts.
[inventory.json](inventory.json) holds the comparison.

| Check | Predicate | Result | Negative control |
|---|---|---|---|
| Same papers and items as #199 | `before` formula items per paper = #199's `inventory_counts` | 21 of 21 papers equal, 257 items | — |
| Items no longer sent to `formula@1` | `before` items whose target is not an `after` item | 35, all on page 25 of paper 16, all `· <instance id>` | `before` has them: the comparison sees them |
| No new formula item | `after` items not in `before` | 0 | the same difference the other way round finds the 35 |
| Real formulas unchanged | per kept item, the `formula@1` request digest equals `before`'s | 222 of 222 | — |
| The same request as #199 | the digest names a response t4-seam-b recorded (`tests/fixtures/vlm/formula`), which #199's workflow sent for every corpus formula item | 187 of 187 corpus items (W2's 35 come from t5c's replay, not this folder) | the item's bbox moved 1 pt: 0 of 222 recorded |
| Page 25's ids in the canonical text | each id in page 25's text layer (pypdfium2, not docling; 60 ids) is a substring of a page-25 node's `text` | `after`: 0 missing | `before`: 35 missing, the formula-labeled ones |

No removed item is a real formula: the rule matches nothing else in the 257. The nearest item
outside it is a page-50 formula of paper 20 whose text layer is `|I| i i i`, which stays a
formula. In `after`, page 25's ids sit in `list_item` and `text` nodes.

## Paper 16 end to end

#199's `run.py` ran paper 16 on the Temporal workflow in a new OUT, with #199's models (Sonnet
5.5 for the VLM methods and the summary, local d3-mini) and its relaxed runtime. The script
writes its evidence beside itself; those files are under [e2e/](e2e/), and #199's own are
unchanged. `run.py e2e` then read the Processing Result, its inventory and assembly and the
receipts from the S3 stand-in of this run ([e2e.json](e2e.json)) and of #199's
([e2e-199.json](e2e-199.json)), the negative control.

| | #199 | #212 |
|---|---|---|
| Outcome, rule `pass` | complete, pass | complete, pass |
| Inventory items | 123 | 88 |
| Formula statuses | 19 `unverified`, 1 `disputed` (d3), 24 `failed EMPTY_OUTPUT` | 8 `unverified`, 1 `disputed` (d3) |
| `formula@1` requests | 69: 20 ok, 49 invalid | 9: 9 ok, 0 invalid |
| `formula@1` input tokens | 27,000 | 3,688 |
| d3 requests | 31 | 20 |
| Inventory items on page 25 | 35 formulas, 1 table | 1 table |
| Requests for page-25 items | 60 `formula@1`: 11 ok, 49 invalid | 0 |
| Page 25's 60 ids in the assembly's text | 25 (35 missing) | 60 |
| Cost | US$0.56 | US$0.46 |

The 9 formulas left are page 22's real ones. #199's record is
[../199/papers/16.json](../199/papers/16.json); #212's is [e2e/paper-16.json](e2e/paper-16.json).

## t4's 46 formulas

- **The 44 real formulas keep #199's verdicts (43 PASS, the p01 calligraphic C FAIL).** Each one
  is still a formula item, and its `formula@1` request has the same digest before and after the
  fix and is one t4-seam-b recorded (44 of 44), as #199's was: the model gets the same input.
  Paper 16's real formula, p16-80a4d936a5d2, ran again: same request, PASS, an answer #199 had
  already judged ([e2e/accuracy.json](e2e/accuracy.json)). The first round's rerun gave the same.
- **The two ids are no longer formulas.** #199's scorer finds no formula enrichment for them and
  counts them FAIL (`found: false` in e2e/accuracy.json). Its "alone" column still sends t4's old
  formula request, which the workflow no longer sends: p16-e1d8a234b6b9 again got an empty answer
  there, and p16-35fa058a6093 a new answer, left unjudged (`pending_judgments: 1`). In the
  canonical document both are text items whose text is the source line:

  | Label | Text in the assembly | t4's Luna answer |
  |---|---|---|
  | p16-e1d8a234b6b9 | `· django__django-12143` | `\text{django\_\_django-12143}` |
  | p16-35fa058a6093 | `· sphinx-doc__sphinx-9698` | `\texttt{sphinx-doc\_\_sphinx-9698}` |

## Run

```
A=~/archive/data-ingestion-wip-2026-10-21/untracked
M="$A/docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json"
OUT=~/archive/research/212-formula
# before: on the parent commit's methods/docling_parse/pipeline.py; after: on this branch
scripts/heavy-lock 212-inventory -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \
    docs/validation/212/run.py $OUT "$M" "$A" before
scripts/heavy-lock 212-inventory -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \
    docs/validation/212/run.py $OUT "$M" "$A" after
PYTHONPATH=. .venv/bin/python docs/validation/212/run.py compare $OUT

set -a; . ~/.config/kp-dev/anthropic.env; set +a
scripts/heavy-lock 212-e2e -- env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/199/run.py \
    $OUT/e2e "$M" "$A" ~/models/issue84/w4b-d3-models/d3-mini \
    ~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python 16
# then move the files run.py wrote under docs/validation/199 to e2e/ and restore #199's
PYTHONPATH=. .venv/bin/python docs/validation/212/run.py e2e $OUT/e2e e2e
PYTHONPATH=. .venv/bin/python docs/validation/212/run.py e2e ~/archive/research/199-e2e/pilot2 e2e-199
```

OUT (`~/archive/research/212-formula`, outside the repo) holds the file-backed store of the
parse runs, `before.json` and `after.json` (with the paper text of each formula item), and the
end-to-end run's S3 stand-in data, Temporal database and logs.

## Files

- [run.py](run.py): parse and inventory of the 21 papers, the comparison, the end-to-end check.
- [inventory.json](inventory.json): per paper, the formula items before and after, the removed
  items, request and recording counts; page 25's ids.
- [manifest.json](manifest.json): each paper's sha256 and the sha256 of OUT/before.json and
  OUT/after.json.
- [e2e.json](e2e.json), [e2e-199.json](e2e-199.json): paper 16's Processing Result in this run
  and in #199's, as `run.py e2e` read them.
- [e2e/](e2e/): what #199's `run.py` wrote for this run: `paper-16.json`, `accuracy.json`,
  `tokens.json`, `tokens.md`, and `manifest.json` with the hashes of the paper, profile, d3
  package, gold, request objects and raw outputs.
