# English regression manual review — corrected T1

Source PNGs, frozen references, complete Canonical text arrays and Markdown were reviewed for ACL pages 1–2 and WikiSkill page 2. No inference or frozen-data edits were performed by this reviewer. The initial environment-invalid review is preserved separately.

| Page | R0 | R1: classifier disabled | T1: corrected native Tesseract |
|---|---|---|---|
| ACL p1 | Major corruption: five BLEU values and a citation line | Both restored; remaining wrap/spacing defects are minor | Prose/numeric magnitudes preserved; `+0.47` becomes `十 0.47`, plus a few name/spacing glyph defects |
| ACL p2 | Left continuation is garbled and `2 Our Method` lost | Heading is inserted inside the unrelated left sentence | Prose collision fixed and heading separate; included inline variable expressions regress substantially |
| WikiSkill p2 | No major body OCR loss found | Complete native texts exactly identical to R0 | Body preserved; footer `2` becomes `NR` |

ACL p1 U06 → U08 is a **legitimate paragraph continuation**, including T1. Its source-text cross-column flag is dismissed, not counted as model failure.

ACL p2 U03/U07 is a true unrelated-column collision. R1 writes `performance of high-frequency words of the stu- 2 Our Method dent model. Our main contributions are as follows:`. T1 correctly separates the intact left continuation (`#/texts/29`) and `2 Our Method` (`#/texts/33`). The cross-column prose gain is supported by an independent page, not just the motivating case.

T1 has a material regression on included inline-math body units:

- U10 / `#/texts/36`: source `X = (x_1, x_2, ..., x_n)` becomes `X = (21, £o,...,Lp)`.
- U11 / `#/texts/37`: source decoder expression becomes `Hgec = |(Haee.1], |Haec.2|,.--;[Haec,m||`.

These alter identifiers/grouping. They are not equivalent subscript formatting and cannot be silently removed from the denominator after output. Only the predeclared figure-label unit U01 and standalone formula U13 are excluded. Thus **T1 fixes the observed prose collision, but is not a complete, regression-free document profile**. A later formula stage may need to address these included regions; this review does not establish that it can.

Minor disclosures include `+`→`十` in the ACL abstract, `Gulçehre`→`Gulgehre`, footnote-marker substitution and page-footer errors. These are explicit output differences, never text-repair rules. Literal mathematical operator preservation is not claimed.

The first T1 attempt failed because the custom data prefix omitted the vendor `configs/tsv` file. Its seven attempts and review remain in `T1-environment-invalid` and `manual-english-review-environment-invalid.*`. The corrected run is an explicit environment amendment with seven extra jobs, not zero retry.

Reading-order quality and unseen/natural-scan generalization remain unqualified. Source and current output hashes plus exact evidence references are in `manual-english-review.json`.
