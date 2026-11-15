# #210 paper-pdf@1: a whole code listing in code items

Run 2026-11-15 on this Mac with [run.py](run.py) (parse and inventory of the 21 papers, no VLM),
[heldout.py](heldout.py) (30 unseen arXiv papers) and [#199's run.py](../199/run.py) (the papers
with #84's 13 code units, end to end, Sonnet 5.5 as in #199).

## Verdict

**Every line of #84's 13 code listings is now in a code item, and code@1 reads all 13 with
operators and numbers exact (13/13, against 9/13 in #199).** No body text, caption, formula or
table joined a code item: 92 new code items on the corpus and 58 relabeled nodes on the held-out
papers, all read one by one, are all lines of monospaced listings (prompts, model transcripts,
shell steps).

| | #199 | #210 |
|---|---|---|
| Units whose gold characters all lie in a code item's box | 9 / 13 | 13 / 13 |
| Operators exact (workflow, #199's score.py) | 9 / 13 | 13 / 13 |
| Numbers exact (workflow) | 9 / 13 | 13 / 13 |
| CER median (workflow) | 0.42 % | 0.35 % |
| P-01 code 11, P-04 code 7, 8, 10: CER | 79, 76, 71, 81 % | 0.86, 0.36, 0.45, 0.30 % |
| Code items on the 21 papers | 185 | 277 |
| Items of other methods changed | — | 0 |
| Cost of the five papers end to end | US$1.86 | US$1.79 |

## The fix

The layout labels part of a listing `code` and the rest `text`, `list_item` or
`section_header`: the four #199 units are agent prompts typeset as verbatim blocks, where docling
saw the JSON tail as code and the numbered instructions above it as a list. The four pages show
the signal docling discards: every line of each listing is in the listing's monospaced font
(`LMMono9-Regular`), the body in a proportional one (`XCharter-Roman`), the box title in another
(`LMMonoLt10-Bold`).

`docling-parse@1`'s assembly ([pipeline.py](../../../src/kp_canonicalization/methods/docling_parse/pipeline.py)
`whole_listings`) now reads the source's text layer with PDFium and, from each code node whose
most common font is monospaced on its pages, walks the reading order both ways. Each `text`,
`list_item` or `section_header` node whose most common font is that same font becomes a code
node with its orig as text, and the walk stops at the first node that is not (another font, a
caption, formula, table or picture). Page headers and footers, which docling attaches to the
body, are skipped. A code node with several provenances (a paragraph docling merged across a page
break) becomes one code node per provenance, so the inventory, which reads a node's first
provenance, covers every page.

- **Monospaced is measured, not named.** A font is monospaced on a page when at least 5 of its
  runs (characters between spaces on one baseline, 5 or more steps, 4 or more distinct glyphs)
  exist and at least half of them advance evenly (each step within 4 % of the run's median). Font
  names vary (`SFTT0800`, `Inconsolatazi4`, `AAAAAC+LMMono9-Regular`, `NimbusMonL-Regu`), and
  PDF font flags are unset in these papers (`LMMono9-Regular` has FixedPitch off). On the 21
  papers the uneven-run share separates the fonts widely: monospaced fonts 0.667 to 1.0, the 167
  proportional ones at most 0.118. Steps come from character origins, not font sizes: Word
  output reports size 281, scaled TeX fonts size 1.
- **Why not the alternatives.** docling has no setting that changes how its layout model labels
  a block; another layout model is a new model (excluded by the ticket). Merging items by
  geometry alone would join body text that sits under a listing; the font says which lines
  belong to it. code@1's existing monospace test (MAD of letter widths) mislabels Times as
  monospaced on 8 of 176 corpus code nodes, because most Times lowercase letters share a width.
- **Not changed.** The inventory, code@1 and its prompt, inline code
  (`INLINE_CODE_NOT_RECONSTRUCTED`), `VERSION` (paper-pdf@1 is unreleased). No new model or
  dependency: PDFium was already loaded.

Three defects found while validating were fixed before the final run, each with a test:
docling puts the page footer inside the body (a listing across a page break stopped at it); a
split node appended at the end of `texts` put its enrichment out of document order (P-04 code 7
read its last line first); docling's charspan offsets are off by 2 where it joins a hyphenated
word, so a split now uses only the charspan lengths, from the end of orig.

## The 21 papers

[run.py](run.py) `run` ran prepare, parse, assemble and inventory in process, on #212's
file-backed store (copied), once with the parent commit's sources (`before`, docling-parse digest
`565aea…`, every object reused from #212) and once with this branch (`after`). `compare` matched
items by method, page and box, since a split renumbers the text refs after it
([inventory.json](inventory.json)).

| Paper | Code items before | after | Gained, by label before |
|---|---|---|---|
| 1 | 4 | 31 | 14 list items, 11 text, 2 headings |
| 4 | 16 | 52 | 20 list items, 11 text, 4 headings, 1 split |
| 7 | 4 | 7 | 3 text |
| 8 | 1 | 2 | 1 text |
| 9 | 3 | 5 | 2 text |
| 13 | 17 | 40 | 18 list items, 5 text |
| other 15 | 140 | 140 | — |

No item was lost and no other method's items changed. Each of the 92 new items was read: agent
prompts (papers 1, 4, 7, 9), a model transcript with `<think>` and `<tool_call>` lines (13), a
setup listing's `...` (8). The heading-labeled ones are lines such as `## Task` and
`Merge guidelines:` inside a prompt; the section headings next to the listings ("C.2.4 Success
merge: merge_success.md", in TeXGyreHeros) stay headings, and the body paragraph after each
listing stays text.

The 13 units ([codes.json](codes.json)): the share of each unit's gold characters that lie in a
code item's box, and code@1's output on the code items over the unit's regions, scored with #84's
metrics. The `before` column reproduces #199's workflow CER for all 13 units to the fourth
decimal, a check of the scorer.

## Held out

The rule was designed on the 21 papers, so [heldout.py](heldout.py) took 30 papers it had never
seen: the newest arXiv submissions of at most 40 pages, 3 each in cs.SE, cs.PL, cs.CL, cs.AI,
cs.LG, cs.CR, cs.DB, cs.DC, cs.MA and cs.HC (622 pages, none a corpus paper). Each was parsed with
the rule off and the rule then applied to the same assembly, so each node's label with and
without it comes from one parse ([heldout.json](heldout.json)).

- 70 code nodes without the rule; the rule relabeled 58 nodes in 3 papers (2611.14881, cs.PL: 8;
  2611.17323, cs.AI: 36; 2611.17313, cs.AI: 14), and split none.
- **0 false positives**, read one by one: LLM prompt templates (an MLIR prompt, an LLM-as-judge
  prompt between `"""` marks, a few-shot QA input with numbered passages). The two that looked
  borderline sit inside a listing: "linalg / EQUIV" lines next to "torch / EQUIV" lines docling
  had already labeled code, and a method list between a prompt's opening and its `'''`.
- **Positive control:** corpus paper 4 through the same path relabels 35 nodes and splits 1, as
  in the 21-paper run.
- **Negative control** (tests): a code node in Helvetica, with 5 Helvetica lines after it, takes
  no neighbour; the same lines in Courier pass the monospace test.

What the held-out set cannot show is recall: it has no gold, so a listing line the rule missed
there is not counted.

## End to end

#199's `run.py` ran papers 1, 3, 4, 7 (the corpus papers with code units) and W2 on the Temporal
workflow in a new OUT with #199's models. Its evidence is under [e2e/](e2e/); #199's own files
are unchanged. All five completed with rule `pass`; every code enrichment is `unverified` (none
failed), paper 1 with 31 and paper 4 with 52 of them. code@1 reads the text layer, so the new
items send no VLM request ([e2e/tokens.md](e2e/tokens.md)).

The e2e ran on commit `5c94490`, before the review fixes (charspan lengths, a stale font name,
an early return). The 21-paper inventory on the final code gives the same items, node labels and
code texts on every paper as on `5c94490` (docling-parse digests `f3aba8…` and `57a441…`), and
the held-out run the same 58 nodes, so the e2e result holds for the final code.

## Limits

- **A paper set in a monospaced body font.** Its body paragraphs next to a code node would become
  code. None of the 51 papers is one.
- **A node mixing a listing line and prose.** The most common font decides, so a node docling
  merged from a listing line and a longer monospaced sentence becomes code whole. Not seen.
- **A listing docling labels nowhere as code** stays text: the rule needs one code node to start
  from. P-01 page 24's LiveMathematicianBench prompt is one (not one of #84's units).
- Rotated pages are not handled differently: node boxes and PDFium centres are compared in page
  space, as code@1 already does.

## Run

```
A=~/archive/data-ingestion-wip-2026-10-21/untracked
M="$A/docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json"
OUT=~/archive/research/210-code
cp -c -R ~/archive/research/212-formula/store $OUT/store
git archive <parent commit> src | tar -x -C $BEFORE
scripts/heavy-lock 210-inventory -- env HF_HUB_OFFLINE=1 PYTHONPATH=$BEFORE/src:. .venv/bin/python \
    docs/validation/210/run.py run $OUT "$M" "$A" before
scripts/heavy-lock 210-inventory -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \
    docs/validation/210/run.py run $OUT "$M" "$A" after
PYTHONPATH=. .venv/bin/python docs/validation/210/run.py compare $OUT "$M" "$A"

PYTHONPATH=. .venv/bin/python docs/validation/210/heldout.py fetch ~/archive/research/210-heldout
scripts/heavy-lock 210-heldout -- env HF_HUB_OFFLINE=1 PYTHONPATH=. .venv/bin/python \
    docs/validation/210/heldout.py parse ~/archive/research/210-heldout "$M"

set -a; . ~/.config/kp-dev/anthropic.env; set +a
scripts/heavy-lock 210-e2e -- env HF_HUB_OFFLINE=1 .venv/bin/python docs/validation/199/run.py \
    $OUT/e2e "$M" "$A" ~/models/issue84/w4b-d3-models/d3-mini \
    ~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python 1 3 4 7 w2
# then move what run.py wrote under docs/validation/199 to e2e/ and git checkout docs/validation/199
```

OUT and `~/archive/research/210-heldout` (outside the repo) hold the stores, `before.json`,
`after.json`, the code text of each code node for review (`*-text.json`, `heldout.json`), the
held-out papers and the end-to-end run's S3 stand-in data, Temporal database and logs.

## Files

- [run.py](run.py): parse and inventory of the 21 papers, and the comparison.
- [heldout.py](heldout.py): the held-out fetch and parse.
- [inventory.json](inventory.json): per paper the items each method gained and lost.
- [codes.json](codes.json): the 13 units, before and after.
- [heldout.json](heldout.json): the held-out papers with their sha256, the counts and every
  relabeled node's page, label before and length.
- [manifest.json](manifest.json): each paper's sha256 and the sha256 of OUT/before.json and
  OUT/after.json.
- [e2e/](e2e/): what #199's `run.py` wrote for this run.
