# English regression manual review

Source PNGs, frozen references, complete Canonical text arrays and Markdown were reviewed for ACL pages 1–2 and WikiSkill page 2. No new inference or frozen-data edits were performed.

| Page | R0 | R1, classifier disabled | T1 |
|---|---|---|---|
| ACL p1 | Major corruption: five BLEU values and a line of named citations | Both restored; remaining wrap/spacing defects are minor | Not evaluable: native OCR integration failed |
| ACL p2 | Left introduction continuation is garbled; `2 Our Method` heading lost | Words return, but heading is spliced inside the unrelated left-column sentence | Not evaluable: native OCR integration failed |
| WikiSkill p2 | No major OCR loss found | Complete native texts exactly identical to R0 | Not evaluable: native OCR integration failed |

ACL p1's U06 (left-bottom Introduction) → U08 (right-top continuation) is a **legitimate paragraph continuation**. The cross-column anchor flag is dismissed after source-page review; it is not a model error.

ACL p2's U03/U07 is different: raw cell 17 and `#/texts/17` in R1 read `performance of high-frequency words of the stu- 2 Our Method dent model. Our main contributions are as follows:`. The source places `2 Our Method` independently in the right column. It interrupts `stu-` + `dent` in the left sentence, so this remains a major cross-column error. Heading text presence alone does not mean correct preservation.

R1 improves independent upright-page recognition beyond the motivating page, but **does not qualify as the cross-column fix**. No newly introduced major failure was found on these three pages; existing detector mixing remains. R0/R1 both also repeat footer `5544` on ACL p2 (minor furniture duplication).

T1 produced no complete documents after `KeyError: 'text'` in the native Tesseract TSV adapter. Missing `tessdata/configs/tsv` under the custom data prefix is a concrete integration suspect, not an OCR-accuracy finding. Any later amended run needs a separate review artifact.

Reading order, figure internals, mathematical semantics and unseen/natural-scan generalization were not qualified. Source and output hashes and exact evidence references are saved in `manual-english-review.json`.
