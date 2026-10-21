# OCR crop ablation: full-page manual source review

Both arms fail the unchanged content requirements. B eliminates the observed cross-column mixed lines on this page, but loses the complete section heading, retains severe first-line OCR corruption, and retains an incorrect final reading order. This is a successful diagnostic intervention, not an acceptable complete parsing method.

Reviewed the full frozen source image and native original page text against both raw cell lists and complete DoclingDocument/Markdown outputs. Scope: the 11 body paragraphs, 1 section heading, 2 footnotes, and page number on original physical page 3 / fixture page 1. No model judge, new inference, output repair, reference change, or score-threshold change.

## Material findings

| Item | Source | A | B | Earliest confirmed boundary |
|---|---|---|---|---|
| P01 / P06 | Left review-article paragraph / right in-context-learning paragraph | Sentence interleaving in text item 1 | Both wordings retained separately; no mixed line | A raw OCR cells 3 and 4 already mix columns |
| P02 / P07 | Left survey-outline paragraph / right instruction-following paragraph | Sentence interleaving in text item 2 | Both wordings retained separately | A raw OCR cell 15 already mixes columns |
| H01 | `2 OVERVIEW` | Retained | **Entire section heading omitted** | B reader 007 receives the readable 210 × 36 px image (width × height), returns null boxes/text/scores; no heading cell exists downstream |
| P04 first line | `Background. Typically, large language models (LLMs) refer` | `Bs  a    ler` | `Bt ) at  a d, ee` | Both are already wrong in raw OCR; B reader 009 input shows the complete readable source line, but txts[0] is corrupted |
| Body order | Finish left column through P05, then P06 onward in right column | Invalid interleaving and early right-column content | **P06 immediately follows P01** | Final document fails to restore this part of column order; the subsequent [native ReadingOrder replay](downstream-findings.json) isolates the P01→P06→P02 geometric edges |
| Page number | `3` | Retained as document furniture; omitted by Markdown export | Missing in cells and document | B reader 001 receives a visible page number, returns null; this is a minor furniture loss |

B P04's corruption is not a new error class: A already corrupts the same first line. A correct body-paragraph count does not make either result acceptable. The destroyed P04 line carries the definition and name of the subject, not merely punctuation or spelling.

## Complete body, heading and furniture accounting

| ID | Source content | A assessment | B assessment |
|---|---|---|---|
| P01 | Related review articles and this survey's focus | Major cross-column interleaving with P06 | Wording retained, one occurrence |
| P02 | Organization of the remainder of the survey | Major cross-column interleaving with P07 | Wording retained, one occurrence |
| H01 | Section `2 OVERVIEW` | Present | **Missing** |
| P03 | Section introduction: terminologies, abilities and techniques | Retained | Retained |
| P04 | Background and definition of LLMs | **First line severely corrupted**; remainder retained | **First line severely corrupted**; remainder retained |
| P05 | Emergent abilities and introduction of three abilities | Retained | Retained |
| P06 | In-context learning | Major interleaving with P01 | Wording retained; **placed too early** |
| P07 | Instruction following | Major interleaving with P02 | Retained |
| P08 | Step-by-step reasoning | Retained | Retained |
| P09 | Key techniques introduction | Retained | Retained |
| P10 | Scaling | Retained | Retained |
| P11 | Training | Retained through this source page's ending | Retained through this source page's ending |
| F05 | Parameter-scale footnote | Complete, once | Complete, once |
| F06 | Meta-optimization footnote | Complete, once | Complete, once |
| PAGE | Page number `3` | Present in DoclingDocument | Absent |

There is no whole-body-paragraph omission or duplication in either arm. A has two mixed combined paragraphs instead of four independently usable ones; B loses the separate heading despite retaining all 11 body paragraphs.

B document order is `P01, P06, P02, P03, P04, P05, P07, P08, P09, P10, P11`. This confirms four wrong pairs: P06 comes before P02, P03, P04, and P05. P06 describes an ability before the left-column section introduction that introduces those abilities. Raw cell and pre-reading-order assembly order are not themselves the semantic acceptance criterion; the error remains in the final document and Markdown.

## Minor differences and false alarms

- Curly quotes become straight quotes, the bullet becomes a middle dot, italic/bold styling is largely absent, and footnote marker 5 can be superscript `⁵`. These are acceptable representation differences here.
- The page-number loss is recorded as minor furniture loss; the missing section heading is substantive source-content loss.
- Short raw lines `as follows.`, `by training on code [33, 47].`, `follows.`, and footnote ending `nism.` are present and correctly joined downstream. Anchor-based raw coverage undercounts must not be reported as their omission.
- A's 100% reference-character recall for mixed paragraphs is not sentence correctness: it also contains other-column text.
- Source footnote 5 actually says `no a formal consensus`; retaining that wording is not an OCR error.
- Reference metadata clarification: P01 starts a complete new paragraph (`We are also aware...`); the Introduction section continues from the previous page. The frozen `continues_from_previous_page` flag is overbroad and unused by the scorer; it does not alter reference text, paragraph count or ordering. P11 ends with `and` and continues on the next source page; that boundary is not an extraction omission.

## Decision

Keep the defect unacceptable and stop this ablation without further tuning. The experiment establishes that changing the crop intervention can eliminate this page's observed mixing, while the unchanged complete pipeline still fails. It does not justify deploying zero dilation or claim a fixed general method.

Evidence: [frozen reference](reference.json), [A amended score](A/score-schema-amended.json), [B score](B/score.json), [A document](A/document.md), [B document](B/document.md). The adjacent JSON records artifact hashes and each item assessment.

No new inference or speculative fix was run. This is one exposed clean raster page; null OCR output alone does not identify which detector/recognizer/filter substep caused the loss, and no generalization or latency SLO is established.
