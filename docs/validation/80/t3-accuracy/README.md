# #132 accuracy of the local enrichment methods

Run 2026-10-31 on macOS arm64 (CPU only) with [run.py](run.py), against the #84 gold kept
outside git (it quotes third-party papers). Thirteen pilot papers ran through the real stages
in process (prepare, parse, assemble, inventory, enrich_local) on the DEV profile
(`tests/profiles/paper-pdf-dev.yaml`); method digests are in [evidence.json](evidence.json).
Bars were set before the run (user ruling 2026-10-31): synthetic samples exact, corpus not below
#84. Each bar also requires the full sample (358 items in 18 images, 13 units, 15 tables), so a
broken measurement fails. The synthetic layer runs in CI: `tests/stages/test_accuracy.py`.

| Method | Sample | Result | #84 baseline | Bar | Pass |
|---|---|---|---|---|---|
| picture-ocr | 18 images, 358 expected text items (#84 image gold, pilot papers 01, 03, 10, 11, 17); every image matched an inventory item | 304 literal matches | 304 (round 4, same items) | full sample, ≥ baseline | yes |
| code | 13 units comparable on a fixed source region (#84 code oracle; 10 pilot, 3 W2) | raw CER median 0.18 % (max 10.2 %); operator sequence exact 13/13, number sequence exact 13/13 | CER median 3.65 %; numbers exact 11/13 | full sample, 0 ≤ median ≤ 3.7 %, no exact sequence lost | yes |
| table-status | 15 tables with a decided #84 E0 verdict (6 PASS, 9 FAIL) | 15/15 matched by page and box, every cell identical | the adjudicated E0 output | full sample, cell-identical | yes |

How each is scored:

- **picture-ocr**: #84's `score_ocr_v2` unchanged (NFKC, whitespace removed, literal match,
  disjoint spans) on the OCR lines the item registered. Every item agrees with the baseline
  (304 pass in both, 54 fail in both). The method reads the registered picture image at
  images_scale 2.0; a separate probe on the same gold boxes gave 305 at 2x and 300 at 3x and 4x,
  so the 3x re-render of the v1 helper was not adopted.
- **code**: the method runs on the union box of the unit's regions on each page; CER, operator
  and number sequences use #84's `metrics.compare`. Calibration: the same scorer applied to
  #84's own native text reproduces #84's per-unit CER on all 13 units
  (`baseline_rescored_cer`). The gain over #84 comes from one change: character x positions
  use PDFium's loose (advance) boxes instead of ink boxes, so narrow glyphs such as `):` no
  longer read as separated by a space. The worst unit (P-03 code 9, 10.2 %) spans two pages.
- **table-status**: the method delivers docling's grid, so accuracy is inherited when the grid
  equals the one #84 adjudicated; all 15 do, with box overlap 1.0.

Limits: the OCR and table samples are those #84 adjudicated, not the whole corpus (#83 widens
them). The code scores measure the method on #84's fixed regions, not the layout that finds code
blocks: one unit (P-04 code 7, pages 23–24) is only partly covered by inventory code items (its
page-23 lines and most of its page-24 lines fall outside them), so in the pipeline part of that
listing arrives as ordinary text. Layout labels belong to the native parse (docling-parse@1).
