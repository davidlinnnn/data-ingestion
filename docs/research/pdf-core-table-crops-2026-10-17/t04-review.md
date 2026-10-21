# T04 / collateral Table7: post-call review

All six requests completed before this evaluation read the frozen oracle. No producer output, candidate input, frozen method, or acceptance threshold was changed.

| Item | Raw content result | Typed / main Markdown result |
|---|---|---|
| Table6 / G1-T04 | 295/300 numeric literals correct; 0 missing; 0 extras; all 5 critical arithmetic comparisons hold | Entire page rejected; no accepted delivery |
| Table7 / collateral | 90/90 numeric literals correct; three model groups and nine method rows identifiable | Entire page rejected; no accepted delivery |

Table6's numeric error rate is **1.67%**, within the established 5% tolerance when considered alone. The blocker is structural: model family occupies column 0, while both model variant and method occupy column 1 across all 30 data rows. The response declares 32 rows although cells extend to exclusive row 33. Its grid has 30 overlapping positions, two gaps, and 12 out-of-bounds positions. The printed Model header spans two stub columns and three header rows; the response assigns one column and two rows. A row-count correction alone would not resolve these defects.

All 30 row identities remain readable from the literal model/method labels and row extents, so raw numeric diagnostics are reported fairly instead of treating every number as wrong. This diagnostic association does not establish a valid typed grid. Eight metric header paths are literal matches; two use `Adversarial` instead of the source's `Adversial`. Treating that spelling change as minor permits identifying all ten metric paths and does not change the structural rejection.

The five wrong numeric literals are `15.79 → 17.79`, `25.38 → 42.58`, `3.39 → 6.39`, `2.46 → 6.46`, and `23.18 → 21.08`. Their full source bindings are recorded in `evaluation-t04-points.json`.

Table7 has a header cell with no `end_col_offset_idx` and an incorrect exclusive end row of 9. Category and metric headers overlap on row 1; the complete cells alone produce eight overlapping positions. The response also puts `uncertainties` at panel level, outside the frozen schema. Its 90 values are a separate collateral diagnostic and do not enlarge T04's denominator. The initial 144dpi manual comparison draft misread 13 source values; an evaluation-only 288dpi rendering of the original PDF corrected the manual reference, confirming 90/90. The draft is retained as `evaluation-t04-draft-before-source-zoom.json`; candidate inputs and the frozen oracle were unchanged.

Both requests correctly keep provider captions empty. The saved native baseline has separate caption links for Table6 and Table7, including METEOR/SBERT and F1/BLEU-1 (%) context. The whole-page rejection prevents claiming that those captions or values were delivered in accepted Markdown.

The crop method improved numerical completeness over the preceding full-page response but did not qualify this producer protocol. Further case-specific index repairs would hide the demonstrated structural failure. No additional inference, output repair, or accepted artifact was created.
