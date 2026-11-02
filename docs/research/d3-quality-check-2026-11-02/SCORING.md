# #153 scoring implementation and independent W4b check

Completed offline on 2026-11-02 before the 14:00 UTC stop point. The approved
phase 1 plan is preserved in `MAPPING.md`; its C1 input decision was resolved
by the required `--test-counts` argument. No inference, network access,
GitHub actions, commits, dependency changes or new #153 dataset evaluation
were performed.

## Result

**PASS: 98 synthetic/CLI tests; all required checks; all 494 full-precision
W4b comparisons.** Maximum absolute full-precision difference is
`8.500145032286355e-17`, from equivalent ECE floating-point summation.
Fitted parameters, dev thresholds, AUROCs, counts, coverage and risks match
their full-precision targets exactly. The adapter checked all 532 saved
outputs (81 dev and 185 test per model) against the gold IDs and extracted
scores from nested raw answers, checking the cached safe scores as well.

Of 654 comparisons, 630 match literally within the specified absolute
`1e-4` tolerance (counts, strings and nulls match exactly). The other 24 are
printed report numbers rounded to three decimals or one decimal percent.
**Those 24 are not labeled numeric matches.** Every one reproduces the
published display at its stated precision; both values and each cause are
listed below. There are **zero unexplained mismatches and zero UNKNOWNs**
in this reproduction. This checks scoring arithmetic, not model quality.

## Main-line commands and contract

All paths are caller arguments. `FROZEN_COUNTS` must be generated from gold
before inference, with schema `{"<model>": {"<category>": <integer count>}}`.
The count is test `meaning_changed`, including eligible runtime failures.
Missing selected model/category counts, negative/fractional/boolean counts,
and inconsistent test labels are input errors.

```sh
rtk .venv/bin/python docs/research/d3-quality-check-2026-11-02/score.py select "$DEV_ROWS" "$SELECTION" --test-counts "$FROZEN_COUNTS"
rtk .venv/bin/python docs/research/d3-quality-check-2026-11-02/score.py evaluate "$TEST_ROWS" "$SELECTION" "$METRICS"
rtk .venv/bin/python docs/research/d3-quality-check-2026-11-02/reproduce_w4b.py "$W_DIR" "$OUT_JSON"
```

`select` hashes exact dev JSONL bytes and exact frozen-count JSON bytes.
Its `models[model][category]` records the question, both dev AUROCs, nullable
Platt fit and state, `t_v`, `t_d`, C1 state, eligible/valid dev label counts,
and the frozen test changed count. Calibration has no hyperparameter search.
`evaluate` reads that selection without modifying it or refitting, hashes
the test input and selection, and checks the recorded test changed count.

Full-state metrics include per-label counts, raw AUROC and source-page CI
(2,000 attempts, seed 153, skip counts), raw/calibrated ECE, verified and
disputed receipts, conflicts, per-row statuses, C2, and formula combination
receipts. A receipt is `{k, n, value, wilson95}`; `value` and interval are
null when n=0. Verified risk also exposes `risk_upper95`. Disputed count
has its integer count plus a flag-rate receipt over all eligible rows.

In `auroc_only`, evaluation reports counts and raw AUROC/CI only.
In `not_evaluable`, it reports counts and the reason only. Selection may
still record a Platt fit in these reduced states, with both thresholds null.
A missing AUROC/CI makes C2 unknown (null), never a pass. Equal or overlapping
thresholds retain verified precedence and report their conflict count;
formula combination uses the explicit `p <= t_d` predicate even in a conflict.

The scorer does not launch inference or enforce a one-run scheduler.
The main line freezes selection before its single test inference/evaluation;
C2 and test scores never alter a dev choice or threshold.

## Reproduction method

`reproduce_w4b.py` imports the new statistical functions, never W4b code.
It joins embedded IDs to gold, validates splits/categories/questions,
stops on missing/extra/duplicate IDs, and maps only the approved row fields.
Gold reasons and third-party reconstructions are not copied. Dev fitting
and thresholds are recomputed from raw outputs; saved selections are
comparison targets. Launch/producer/dev-output hash receipts are checked.

Historical policy is explicit: **C1 bypassed**, no bootstrap/C2, and
**disputed iff raw <0.5 after verified precedence**. This is confined to the
reproduction adapter. The #153 scorer always uses the new calibrated t_d
and sample floor. The adapter parses both section 3 main and dev receipt
tables; it excludes the separate W4/VJev baseline table. Runtime, GPU and
calibrated-AUROC extras are outside the requested comparison.

Machine-readable evidence is in [reproduction.json](reproduction.json),
including every exact comparison value, source hashes and dependency versions.
The raw-results digest hashes each relative result filename plus a NUL byte
and its SHA-256 digest, in sorted model-directory order, dev then test,
with sorted filenames within a split. This traversal differs from the
phase 1 smoke traversal, whose digest algorithm/order is shown in its command.

| Check family | Comparisons | Result |
|---|---:|---|
| comparison | 100 | all match |
| evaluation | 196 | all match |
| receipt | 18 | all match |
| report | 160 | 136 literal matches; 24 explained display-rounding differences |
| selection | 180 | all match |

## All literal report differences above 1e-4

Rates below are normalized fractions (for example, 43.6% becomes 0.436).
Values in Markdown use up to 15 significant digits; exact JSON numbers
and absolute errors are in the machine-readable evidence. Each row below
fails the literal numeric tolerance but passes the printed-display check.

| Number | W4b printed value | Ours | Numeric match | Cause |
|---|---:|---:|---|---|
| report.test.d3-nano.formula.AUROC | 0.778 | 0.777511961722488 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.formula.ECE_before | 0.155 | 0.154528596334888 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.formula.risk | 0.083 | 0.0833333333333333 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-nano.formula.coverage | 0.436 | 0.436363636363636 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-nano.code.AUROC | 0.613 | 0.613333333333333 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.code.ECE_before | 0.182 | 0.182373791019174 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.code.coverage | 0.357 | 0.357142857142857 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-nano.description.ECE_before | 0.286 | 0.28569139386832 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.description.ECE_after | 0.145 | 0.144664863859585 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.description.coverage | 0.471 | 0.470588235294118 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-nano.chart.AUROC | 0.71 | 0.71044776119403 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-nano.chart.ECE_before | 0.237 | 0.236581644463514 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.formula.AUROC | 0.859 | 0.858851674641148 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.formula.ECE_after | 0.086 | 0.0861882890279755 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.formula.coverage | 0.455 | 0.454545454545455 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-mini.code.ECE_before | 0.393 | 0.39267229015875 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.code.coverage | 0.036 | 0.0357142857142857 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-mini.caption.ECE_before | 0.005 | 0.00480814313169717 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.description.AUROC | 0.333 | 0.333333333333333 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.description.ECE_before | 0.422 | 0.421564712932341 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.description.risk | 0.143 | 0.142857142857143 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-mini.description.coverage | 0.412 | 0.411764705882353 | no | display rounding to 1 decimal places in percent; display matches |
| report.test.d3-mini.chart.AUROC | 0.657 | 0.656716417910448 | no | display rounding to 3 decimal places; display matches |
| report.test.d3-mini.chart.ECE_before | 0.234 | 0.233540044965647 | no | display rounding to 3 decimal places; display matches |

## Complete reproduction table

The table retains every comparison, including nulls and provenance receipts.
A numeric match uses absolute error <=1e-4 without pre-rounding; integer
counts and nonnumeric values use exact equality. Report-display validation
is separate from this numeric-match column.

<details>
<summary>All 654 comparisons: number, W4b value, ours, match</summary>

| Number | W4b value | Ours | Match |
|---|---|---|---|
| receipt.d3-mini.launch_selection_sha256 | "cfaeef5fe513a546a27f1db37a6a335578b369d9c24dffa62f4620738d402af3" | "cfaeef5fe513a546a27f1db37a6a335578b369d9c24dffa62f4620738d402af3" | yes |
| receipt.d3-mini.producer.freeze.json | "336461e7b277447e9a49e9a8fd379c84c405db9214f2d22219f1175454f527b9" | "336461e7b277447e9a49e9a8fd379c84c405db9214f2d22219f1175454f527b9" | yes |
| receipt.d3-mini.producer.infer.py | "64109855eeeff8536529505335cd30482c726f0e55b6836ed1282f8687af51c8" | "64109855eeeff8536529505335cd30482c726f0e55b6836ed1282f8687af51c8" | yes |
| receipt.d3-mini.producer.supervise.py | "0e3df7e8df759a49d874c4ddc22ac2e9b74ffb97b6fdbc3fa8f33bfc378deba0" | "0e3df7e8df759a49d874c4ddc22ac2e9b74ffb97b6fdbc3fa8f33bfc378deba0" | yes |
| receipt.d3-mini.producer.calibrate.py | "9b8eb77181ac1419904b283ea8902564175535034d706ade72fea85993322601" | "9b8eb77181ac1419904b283ea8902564175535034d706ade72fea85993322601" | yes |
| receipt.d3-mini.producer.questions.json | "3d71e72f0ad4729c3a84fa419e3bc756887c48f985d2b721c4ccb7f1b46ab1aa" | "3d71e72f0ad4729c3a84fa419e3bc756887c48f985d2b721c4ccb7f1b46ab1aa" | yes |
| receipt.d3-mini.producer.protocol.json | "e3bf04022d41e067885ed39fa5608d1f5e37138678079e077db31d936a65f5b2" | "e3bf04022d41e067885ed39fa5608d1f5e37138678079e077db31d936a65f5b2" | yes |
| receipt.d3-mini.dev_file_count | 81 | 81 | yes |
| receipt.d3-mini.dev_hashes_equal | true | true | yes |
| selection.d3-mini.formula.question | "Q2" | "Q2" | yes |
| selection.d3-mini.formula.dev_n | 23 | 23 | yes |
| selection.d3-mini.formula.threshold | 0.896281683952962 | 0.896281683952962 | yes |
| selection.d3-mini.formula.dev_verified | 15 | 15 | yes |
| selection.d3-mini.formula.dev_changed | 0 | 0 | yes |
| selection.d3-mini.formula.dev_error_rate | 0 | 0 | yes |
| selection.d3-mini.formula.dev_AUROC.Q1 | 0.875 | 0.875 | yes |
| selection.d3-mini.formula.dev_AUROC.Q2 | 0.930555555555556 | 0.930555555555556 | yes |
| selection.d3-mini.formula.dev_label_counts.correct | 18 | 18 | yes |
| selection.d3-mini.formula.dev_label_counts.minor | 1 | 1 | yes |
| selection.d3-mini.formula.dev_label_counts.meaning_changed | 4 | 4 | yes |
| selection.d3-mini.formula.calibrator.state | "FIT" | "FIT" | yes |
| selection.d3-mini.formula.calibrator.a | 0.732502571782188 | 0.732502571782188 | yes |
| selection.d3-mini.formula.calibrator.b | 1.02267574560643 | 1.02267574560643 | yes |
| selection.d3-mini.formula.calibrator.objective | 6.87371831847644 | 6.87371831847644 | yes |
| selection.d3-mini.formula.calibrator.n | 23 | 23 | yes |
| selection.d3-mini.formula.calibrator.positives | 19 | 19 | yes |
| selection.d3-mini.formula.calibrator.negatives | 4 | 4 | yes |
| evaluation.d3-mini.formula.test_n | 55 | 55 | yes |
| evaluation.d3-mini.formula.valid | 55 | 55 | yes |
| evaluation.d3-mini.formula.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-mini.formula.source_page_groups | 20 | 20 | yes |
| evaluation.d3-mini.formula.AUROC_raw | 0.858851674641148 | 0.858851674641148 | yes |
| evaluation.d3-mini.formula.ECE_before | 0.204030474020268 | 0.204030474020268 | yes |
| evaluation.d3-mini.formula.ECE_after | 0.0861882890279755 | 0.0861882890279755 | yes |
| evaluation.d3-mini.formula.verified | 25 | 25 | yes |
| evaluation.d3-mini.formula.verified_changed | 1 | 1 | yes |
| evaluation.d3-mini.formula.verified_error_rate | 0.04 | 0.04 | yes |
| evaluation.d3-mini.formula.coverage | 0.454545454545455 | 0.454545454545455 | yes |
| evaluation.d3-mini.formula.label_counts.correct | 38 | 38 | yes |
| evaluation.d3-mini.formula.label_counts.minor | 6 | 6 | yes |
| evaluation.d3-mini.formula.label_counts.meaning_changed | 11 | 11 | yes |
| evaluation.d3-mini.formula.status_counts.verified | 25 | 25 | yes |
| evaluation.d3-mini.formula.status_counts.disputed | 18 | 18 | yes |
| evaluation.d3-mini.formula.status_counts.unverified | 12 | 12 | yes |
| evaluation.d3-mini.formula.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-mini.formula.risk_Wilson95.lower | 0.00709623350198726 | 0.00709623350198726 | yes |
| evaluation.d3-mini.formula.risk_Wilson95.upper | 0.195440637361937 | 0.195440637361937 | yes |
| comparison.d3-mini.formula.test_n | 55 | 55 | yes |
| comparison.d3-mini.formula.AUROC | 0.858851674641148 | 0.858851674641148 | yes |
| comparison.d3-mini.formula.ECE_before | 0.204030474020268 | 0.204030474020268 | yes |
| comparison.d3-mini.formula.ECE_after | 0.0861882890279755 | 0.0861882890279755 | yes |
| comparison.d3-mini.formula.verified | 25 | 25 | yes |
| comparison.d3-mini.formula.changed_in_verified | 1 | 1 | yes |
| comparison.d3-mini.formula.verified_error_rate | 0.04 | 0.04 | yes |
| comparison.d3-mini.formula.coverage | 0.454545454545455 | 0.454545454545455 | yes |
| comparison.d3-mini.formula.question | "Q2" | "Q2" | yes |
| comparison.d3-mini.formula.threshold | 0.896281683952962 | 0.896281683952962 | yes |
| selection.d3-mini.code.question | "Q2" | "Q2" | yes |
| selection.d3-mini.code.dev_n | 12 | 12 | yes |
| selection.d3-mini.code.threshold | 0.8292567865993 | 0.8292567865993 | yes |
| selection.d3-mini.code.dev_verified | 6 | 6 | yes |
| selection.d3-mini.code.dev_changed | 0 | 0 | yes |
| selection.d3-mini.code.dev_error_rate | 0 | 0 | yes |
| selection.d3-mini.code.dev_AUROC.Q1 | 0.666666666666667 | 0.666666666666667 | yes |
| selection.d3-mini.code.dev_AUROC.Q2 | 0.666666666666667 | 0.666666666666667 | yes |
| selection.d3-mini.code.dev_label_counts.correct | 9 | 9 | yes |
| selection.d3-mini.code.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-mini.code.dev_label_counts.meaning_changed | 3 | 3 | yes |
| selection.d3-mini.code.calibrator.state | "FIT" | "FIT" | yes |
| selection.d3-mini.code.calibrator.a | 0.370267066738983 | 0.370267066738983 | yes |
| selection.d3-mini.code.calibrator.b | 1.01499057583485 | 1.01499057583485 | yes |
| selection.d3-mini.code.calibrator.objective | 6.17809358382034 | 6.17809358382034 | yes |
| selection.d3-mini.code.calibrator.n | 12 | 12 | yes |
| selection.d3-mini.code.calibrator.positives | 9 | 9 | yes |
| selection.d3-mini.code.calibrator.negatives | 3 | 3 | yes |
| evaluation.d3-mini.code.test_n | 28 | 28 | yes |
| evaluation.d3-mini.code.valid | 28 | 28 | yes |
| evaluation.d3-mini.code.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-mini.code.source_page_groups | 4 | 4 | yes |
| evaluation.d3-mini.code.AUROC_raw | 0.8 | 0.8 | yes |
| evaluation.d3-mini.code.ECE_before | 0.39267229015875 | 0.39267229015875 | yes |
| evaluation.d3-mini.code.ECE_after | 0.17307902444128 | 0.17307902444128 | yes |
| evaluation.d3-mini.code.verified | 1 | 1 | yes |
| evaluation.d3-mini.code.verified_changed | 0 | 0 | yes |
| evaluation.d3-mini.code.verified_error_rate | 0 | 0 | yes |
| evaluation.d3-mini.code.coverage | 0.0357142857142857 | 0.0357142857142857 | yes |
| evaluation.d3-mini.code.label_counts.correct | 25 | 25 | yes |
| evaluation.d3-mini.code.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-mini.code.label_counts.meaning_changed | 3 | 3 | yes |
| evaluation.d3-mini.code.status_counts.verified | 1 | 1 | yes |
| evaluation.d3-mini.code.status_counts.disputed | 13 | 13 | yes |
| evaluation.d3-mini.code.status_counts.unverified | 14 | 14 | yes |
| evaluation.d3-mini.code.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-mini.code.risk_Wilson95.lower | 0 | 0 | yes |
| evaluation.d3-mini.code.risk_Wilson95.upper | 0.793450685622763 | 0.793450685622763 | yes |
| comparison.d3-mini.code.test_n | 28 | 28 | yes |
| comparison.d3-mini.code.AUROC | 0.8 | 0.8 | yes |
| comparison.d3-mini.code.ECE_before | 0.39267229015875 | 0.39267229015875 | yes |
| comparison.d3-mini.code.ECE_after | 0.17307902444128 | 0.17307902444128 | yes |
| comparison.d3-mini.code.verified | 1 | 1 | yes |
| comparison.d3-mini.code.changed_in_verified | 0 | 0 | yes |
| comparison.d3-mini.code.verified_error_rate | 0 | 0 | yes |
| comparison.d3-mini.code.coverage | 0.0357142857142857 | 0.0357142857142857 | yes |
| comparison.d3-mini.code.question | "Q2" | "Q2" | yes |
| comparison.d3-mini.code.threshold | 0.8292567865993 | 0.8292567865993 | yes |
| selection.d3-mini.caption.question | "Q2" | "Q2" | yes |
| selection.d3-mini.caption.dev_n | 6 | 6 | yes |
| selection.d3-mini.caption.threshold | null | null | yes |
| selection.d3-mini.caption.dev_verified | 0 | 0 | yes |
| selection.d3-mini.caption.dev_changed | 0 | 0 | yes |
| selection.d3-mini.caption.dev_error_rate | null | null | yes |
| selection.d3-mini.caption.dev_AUROC.Q1 | null | null | yes |
| selection.d3-mini.caption.dev_AUROC.Q2 | null | null | yes |
| selection.d3-mini.caption.dev_label_counts.correct | 6 | 6 | yes |
| selection.d3-mini.caption.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-mini.caption.dev_label_counts.meaning_changed | 0 | 0 | yes |
| selection.d3-mini.caption.calibrator.state | "UNFITTABLE_SINGLE_CLASS" | "UNFITTABLE_SINGLE_CLASS" | yes |
| selection.d3-mini.caption.calibrator.a | null | null | yes |
| selection.d3-mini.caption.calibrator.b | null | null | yes |
| selection.d3-mini.caption.calibrator.objective | null | null | yes |
| selection.d3-mini.caption.calibrator.n | null | null | yes |
| selection.d3-mini.caption.calibrator.positives | null | null | yes |
| selection.d3-mini.caption.calibrator.negatives | null | null | yes |
| evaluation.d3-mini.caption.test_n | 13 | 13 | yes |
| evaluation.d3-mini.caption.valid | 13 | 13 | yes |
| evaluation.d3-mini.caption.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-mini.caption.source_page_groups | 9 | 9 | yes |
| evaluation.d3-mini.caption.AUROC_raw | null | null | yes |
| evaluation.d3-mini.caption.ECE_before | 0.00480814313169708 | 0.00480814313169717 | yes |
| evaluation.d3-mini.caption.ECE_after | null | null | yes |
| evaluation.d3-mini.caption.verified | 0 | 0 | yes |
| evaluation.d3-mini.caption.verified_changed | 0 | 0 | yes |
| evaluation.d3-mini.caption.verified_error_rate | null | null | yes |
| evaluation.d3-mini.caption.coverage | 0 | 0 | yes |
| evaluation.d3-mini.caption.label_counts.correct | 13 | 13 | yes |
| evaluation.d3-mini.caption.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-mini.caption.label_counts.meaning_changed | 0 | 0 | yes |
| evaluation.d3-mini.caption.status_counts.verified | 0 | 0 | yes |
| evaluation.d3-mini.caption.status_counts.disputed | 0 | 0 | yes |
| evaluation.d3-mini.caption.status_counts.unverified | 13 | 13 | yes |
| evaluation.d3-mini.caption.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-mini.caption.risk_Wilson95 | null | null | yes |
| comparison.d3-mini.caption.test_n | 13 | 13 | yes |
| comparison.d3-mini.caption.AUROC | null | null | yes |
| comparison.d3-mini.caption.ECE_before | 0.00480814313169708 | 0.00480814313169717 | yes |
| comparison.d3-mini.caption.ECE_after | null | null | yes |
| comparison.d3-mini.caption.verified | 0 | 0 | yes |
| comparison.d3-mini.caption.changed_in_verified | 0 | 0 | yes |
| comparison.d3-mini.caption.verified_error_rate | null | null | yes |
| comparison.d3-mini.caption.coverage | 0 | 0 | yes |
| comparison.d3-mini.caption.question | "Q2" | "Q2" | yes |
| comparison.d3-mini.caption.threshold | null | null | yes |
| selection.d3-mini.description.question | "Q1" | "Q1" | yes |
| selection.d3-mini.description.dev_n | 11 | 11 | yes |
| selection.d3-mini.description.threshold | 0.8977581771154 | 0.8977581771154 | yes |
| selection.d3-mini.description.dev_verified | 8 | 8 | yes |
| selection.d3-mini.description.dev_changed | 0 | 0 | yes |
| selection.d3-mini.description.dev_error_rate | 0 | 0 | yes |
| selection.d3-mini.description.dev_AUROC.Q1 | 0.8 | 0.8 | yes |
| selection.d3-mini.description.dev_AUROC.Q2 | 0.7 | 0.7 | yes |
| selection.d3-mini.description.dev_label_counts.correct | 10 | 10 | yes |
| selection.d3-mini.description.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-mini.description.dev_label_counts.meaning_changed | 1 | 1 | yes |
| selection.d3-mini.description.calibrator.state | "FIT" | "FIT" | yes |
| selection.d3-mini.description.calibrator.a | 0.362333658333107 | 0.362333658333107 | yes |
| selection.d3-mini.description.calibrator.b | 1.78060254610821 | 1.78060254610821 | yes |
| selection.d3-mini.description.calibrator.objective | 3.24617527565136 | 3.24617527565136 | yes |
| selection.d3-mini.description.calibrator.n | 11 | 11 | yes |
| selection.d3-mini.description.calibrator.positives | 10 | 10 | yes |
| selection.d3-mini.description.calibrator.negatives | 1 | 1 | yes |
| evaluation.d3-mini.description.test_n | 17 | 17 | yes |
| evaluation.d3-mini.description.valid | 17 | 17 | yes |
| evaluation.d3-mini.description.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-mini.description.source_page_groups | 8 | 8 | yes |
| evaluation.d3-mini.description.AUROC_raw | 0.333333333333333 | 0.333333333333333 | yes |
| evaluation.d3-mini.description.ECE_before | 0.421564712932341 | 0.421564712932341 | yes |
| evaluation.d3-mini.description.ECE_after | 0.131933041511937 | 0.131933041511937 | yes |
| evaluation.d3-mini.description.verified | 7 | 7 | yes |
| evaluation.d3-mini.description.verified_changed | 1 | 1 | yes |
| evaluation.d3-mini.description.verified_error_rate | 0.142857142857143 | 0.142857142857143 | yes |
| evaluation.d3-mini.description.coverage | 0.411764705882353 | 0.411764705882353 | yes |
| evaluation.d3-mini.description.label_counts.correct | 15 | 15 | yes |
| evaluation.d3-mini.description.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-mini.description.label_counts.meaning_changed | 2 | 2 | yes |
| evaluation.d3-mini.description.status_counts.verified | 7 | 7 | yes |
| evaluation.d3-mini.description.status_counts.disputed | 7 | 7 | yes |
| evaluation.d3-mini.description.status_counts.unverified | 3 | 3 | yes |
| evaluation.d3-mini.description.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-mini.description.risk_Wilson95.lower | 0.0256796243447436 | 0.0256796243447436 | yes |
| evaluation.d3-mini.description.risk_Wilson95.upper | 0.513127829274319 | 0.513127829274319 | yes |
| comparison.d3-mini.description.test_n | 17 | 17 | yes |
| comparison.d3-mini.description.AUROC | 0.333333333333333 | 0.333333333333333 | yes |
| comparison.d3-mini.description.ECE_before | 0.421564712932341 | 0.421564712932341 | yes |
| comparison.d3-mini.description.ECE_after | 0.131933041511937 | 0.131933041511937 | yes |
| comparison.d3-mini.description.verified | 7 | 7 | yes |
| comparison.d3-mini.description.changed_in_verified | 1 | 1 | yes |
| comparison.d3-mini.description.verified_error_rate | 0.142857142857143 | 0.142857142857143 | yes |
| comparison.d3-mini.description.coverage | 0.411764705882353 | 0.411764705882353 | yes |
| comparison.d3-mini.description.question | "Q1" | "Q1" | yes |
| comparison.d3-mini.description.threshold | 0.8977581771154 | 0.8977581771154 | yes |
| selection.d3-mini.chart.question | "Q2" | "Q2" | yes |
| selection.d3-mini.chart.dev_n | 29 | 29 | yes |
| selection.d3-mini.chart.threshold | null | null | yes |
| selection.d3-mini.chart.dev_verified | 0 | 0 | yes |
| selection.d3-mini.chart.dev_changed | 0 | 0 | yes |
| selection.d3-mini.chart.dev_error_rate | null | null | yes |
| selection.d3-mini.chart.dev_AUROC.Q1 | null | null | yes |
| selection.d3-mini.chart.dev_AUROC.Q2 | null | null | yes |
| selection.d3-mini.chart.dev_label_counts.correct | 29 | 29 | yes |
| selection.d3-mini.chart.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-mini.chart.dev_label_counts.meaning_changed | 0 | 0 | yes |
| selection.d3-mini.chart.calibrator.state | "UNFITTABLE_SINGLE_CLASS" | "UNFITTABLE_SINGLE_CLASS" | yes |
| selection.d3-mini.chart.calibrator.a | null | null | yes |
| selection.d3-mini.chart.calibrator.b | null | null | yes |
| selection.d3-mini.chart.calibrator.objective | null | null | yes |
| selection.d3-mini.chart.calibrator.n | null | null | yes |
| selection.d3-mini.chart.calibrator.positives | null | null | yes |
| selection.d3-mini.chart.calibrator.negatives | null | null | yes |
| evaluation.d3-mini.chart.test_n | 72 | 72 | yes |
| evaluation.d3-mini.chart.valid | 72 | 72 | yes |
| evaluation.d3-mini.chart.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-mini.chart.source_page_groups | 2 | 2 | yes |
| evaluation.d3-mini.chart.AUROC_raw | 0.656716417910448 | 0.656716417910448 | yes |
| evaluation.d3-mini.chart.ECE_before | 0.233540044965647 | 0.233540044965647 | yes |
| evaluation.d3-mini.chart.ECE_after | null | null | yes |
| evaluation.d3-mini.chart.verified | 0 | 0 | yes |
| evaluation.d3-mini.chart.verified_changed | 0 | 0 | yes |
| evaluation.d3-mini.chart.verified_error_rate | null | null | yes |
| evaluation.d3-mini.chart.coverage | 0 | 0 | yes |
| evaluation.d3-mini.chart.label_counts.correct | 67 | 67 | yes |
| evaluation.d3-mini.chart.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-mini.chart.label_counts.meaning_changed | 5 | 5 | yes |
| evaluation.d3-mini.chart.status_counts.verified | 0 | 0 | yes |
| evaluation.d3-mini.chart.status_counts.disputed | 17 | 17 | yes |
| evaluation.d3-mini.chart.status_counts.unverified | 55 | 55 | yes |
| evaluation.d3-mini.chart.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-mini.chart.risk_Wilson95 | null | null | yes |
| comparison.d3-mini.chart.test_n | 72 | 72 | yes |
| comparison.d3-mini.chart.AUROC | 0.656716417910448 | 0.656716417910448 | yes |
| comparison.d3-mini.chart.ECE_before | 0.233540044965647 | 0.233540044965647 | yes |
| comparison.d3-mini.chart.ECE_after | null | null | yes |
| comparison.d3-mini.chart.verified | 0 | 0 | yes |
| comparison.d3-mini.chart.changed_in_verified | 0 | 0 | yes |
| comparison.d3-mini.chart.verified_error_rate | null | null | yes |
| comparison.d3-mini.chart.coverage | 0 | 0 | yes |
| comparison.d3-mini.chart.question | "Q2" | "Q2" | yes |
| comparison.d3-mini.chart.threshold | null | null | yes |
| receipt.d3-nano.launch_selection_sha256 | "2d0455a1f512a779c126e3dd9e762391c3e1dcac56dff0f8ebd8e6314a94e140" | "2d0455a1f512a779c126e3dd9e762391c3e1dcac56dff0f8ebd8e6314a94e140" | yes |
| receipt.d3-nano.producer.freeze.json | "336461e7b277447e9a49e9a8fd379c84c405db9214f2d22219f1175454f527b9" | "336461e7b277447e9a49e9a8fd379c84c405db9214f2d22219f1175454f527b9" | yes |
| receipt.d3-nano.producer.infer.py | "64109855eeeff8536529505335cd30482c726f0e55b6836ed1282f8687af51c8" | "64109855eeeff8536529505335cd30482c726f0e55b6836ed1282f8687af51c8" | yes |
| receipt.d3-nano.producer.supervise.py | "0e3df7e8df759a49d874c4ddc22ac2e9b74ffb97b6fdbc3fa8f33bfc378deba0" | "0e3df7e8df759a49d874c4ddc22ac2e9b74ffb97b6fdbc3fa8f33bfc378deba0" | yes |
| receipt.d3-nano.producer.calibrate.py | "9b8eb77181ac1419904b283ea8902564175535034d706ade72fea85993322601" | "9b8eb77181ac1419904b283ea8902564175535034d706ade72fea85993322601" | yes |
| receipt.d3-nano.producer.questions.json | "3d71e72f0ad4729c3a84fa419e3bc756887c48f985d2b721c4ccb7f1b46ab1aa" | "3d71e72f0ad4729c3a84fa419e3bc756887c48f985d2b721c4ccb7f1b46ab1aa" | yes |
| receipt.d3-nano.producer.protocol.json | "e3bf04022d41e067885ed39fa5608d1f5e37138678079e077db31d936a65f5b2" | "e3bf04022d41e067885ed39fa5608d1f5e37138678079e077db31d936a65f5b2" | yes |
| receipt.d3-nano.dev_file_count | 81 | 81 | yes |
| receipt.d3-nano.dev_hashes_equal | true | true | yes |
| selection.d3-nano.formula.question | "Q1" | "Q1" | yes |
| selection.d3-nano.formula.dev_n | 23 | 23 | yes |
| selection.d3-nano.formula.threshold | 0.90093911851593 | 0.90093911851593 | yes |
| selection.d3-nano.formula.dev_verified | 12 | 12 | yes |
| selection.d3-nano.formula.dev_changed | 0 | 0 | yes |
| selection.d3-nano.formula.dev_error_rate | 0 | 0 | yes |
| selection.d3-nano.formula.dev_AUROC.Q1 | 0.916666666666667 | 0.916666666666667 | yes |
| selection.d3-nano.formula.dev_AUROC.Q2 | 0.902777777777778 | 0.902777777777778 | yes |
| selection.d3-nano.formula.dev_label_counts.correct | 18 | 18 | yes |
| selection.d3-nano.formula.dev_label_counts.minor | 1 | 1 | yes |
| selection.d3-nano.formula.dev_label_counts.meaning_changed | 4 | 4 | yes |
| selection.d3-nano.formula.calibrator.state | "FIT" | "FIT" | yes |
| selection.d3-nano.formula.calibrator.a | 0.841742020696614 | 0.841742020696614 | yes |
| selection.d3-nano.formula.calibrator.b | 0.850524361371177 | 0.850524361371177 | yes |
| selection.d3-nano.formula.calibrator.objective | 6.63917192429307 | 6.63917192429307 | yes |
| selection.d3-nano.formula.calibrator.n | 23 | 23 | yes |
| selection.d3-nano.formula.calibrator.positives | 19 | 19 | yes |
| selection.d3-nano.formula.calibrator.negatives | 4 | 4 | yes |
| evaluation.d3-nano.formula.test_n | 55 | 55 | yes |
| evaluation.d3-nano.formula.valid | 55 | 55 | yes |
| evaluation.d3-nano.formula.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-nano.formula.source_page_groups | 20 | 20 | yes |
| evaluation.d3-nano.formula.AUROC_raw | 0.777511961722488 | 0.777511961722488 | yes |
| evaluation.d3-nano.formula.ECE_before | 0.154528596334888 | 0.154528596334888 | yes |
| evaluation.d3-nano.formula.ECE_after | 0.0960847652529126 | 0.0960847652529126 | yes |
| evaluation.d3-nano.formula.verified | 24 | 24 | yes |
| evaluation.d3-nano.formula.verified_changed | 2 | 2 | yes |
| evaluation.d3-nano.formula.verified_error_rate | 0.0833333333333333 | 0.0833333333333333 | yes |
| evaluation.d3-nano.formula.coverage | 0.436363636363636 | 0.436363636363636 | yes |
| evaluation.d3-nano.formula.label_counts.correct | 38 | 38 | yes |
| evaluation.d3-nano.formula.label_counts.minor | 6 | 6 | yes |
| evaluation.d3-nano.formula.label_counts.meaning_changed | 11 | 11 | yes |
| evaluation.d3-nano.formula.status_counts.verified | 24 | 24 | yes |
| evaluation.d3-nano.formula.status_counts.disputed | 12 | 12 | yes |
| evaluation.d3-nano.formula.status_counts.unverified | 19 | 19 | yes |
| evaluation.d3-nano.formula.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-nano.formula.risk_Wilson95.lower | 0.0231588152970433 | 0.0231588152970433 | yes |
| evaluation.d3-nano.formula.risk_Wilson95.upper | 0.258488021932107 | 0.258488021932107 | yes |
| comparison.d3-nano.formula.test_n | 55 | 55 | yes |
| comparison.d3-nano.formula.AUROC | 0.777511961722488 | 0.777511961722488 | yes |
| comparison.d3-nano.formula.ECE_before | 0.154528596334888 | 0.154528596334888 | yes |
| comparison.d3-nano.formula.ECE_after | 0.0960847652529126 | 0.0960847652529126 | yes |
| comparison.d3-nano.formula.verified | 24 | 24 | yes |
| comparison.d3-nano.formula.changed_in_verified | 2 | 2 | yes |
| comparison.d3-nano.formula.verified_error_rate | 0.0833333333333333 | 0.0833333333333333 | yes |
| comparison.d3-nano.formula.coverage | 0.436363636363636 | 0.436363636363636 | yes |
| comparison.d3-nano.formula.question | "Q1" | "Q1" | yes |
| comparison.d3-nano.formula.threshold | 0.90093911851593 | 0.90093911851593 | yes |
| selection.d3-nano.code.question | "Q2" | "Q2" | yes |
| selection.d3-nano.code.dev_n | 12 | 12 | yes |
| selection.d3-nano.code.threshold | 0.82006940383658 | 0.82006940383658 | yes |
| selection.d3-nano.code.dev_verified | 5 | 5 | yes |
| selection.d3-nano.code.dev_changed | 0 | 0 | yes |
| selection.d3-nano.code.dev_error_rate | 0 | 0 | yes |
| selection.d3-nano.code.dev_AUROC.Q1 | 0.518518518518518 | 0.518518518518518 | yes |
| selection.d3-nano.code.dev_AUROC.Q2 | 0.703703703703704 | 0.703703703703704 | yes |
| selection.d3-nano.code.dev_label_counts.correct | 9 | 9 | yes |
| selection.d3-nano.code.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-nano.code.dev_label_counts.meaning_changed | 3 | 3 | yes |
| selection.d3-nano.code.calibrator.state | "FIT" | "FIT" | yes |
| selection.d3-nano.code.calibrator.a | 0.38113747127633 | 0.38113747127633 | yes |
| selection.d3-nano.code.calibrator.b | 0.754890695246583 | 0.754890695246583 | yes |
| selection.d3-nano.code.calibrator.objective | 6.27527084307258 | 6.27527084307258 | yes |
| selection.d3-nano.code.calibrator.n | 12 | 12 | yes |
| selection.d3-nano.code.calibrator.positives | 9 | 9 | yes |
| selection.d3-nano.code.calibrator.negatives | 3 | 3 | yes |
| evaluation.d3-nano.code.test_n | 28 | 28 | yes |
| evaluation.d3-nano.code.valid | 28 | 28 | yes |
| evaluation.d3-nano.code.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-nano.code.source_page_groups | 4 | 4 | yes |
| evaluation.d3-nano.code.AUROC_raw | 0.613333333333333 | 0.613333333333333 | yes |
| evaluation.d3-nano.code.ECE_before | 0.182373791019174 | 0.182373791019174 | yes |
| evaluation.d3-nano.code.ECE_after | 0.118074527239858 | 0.118074527239858 | yes |
| evaluation.d3-nano.code.verified | 10 | 10 | yes |
| evaluation.d3-nano.code.verified_changed | 1 | 1 | yes |
| evaluation.d3-nano.code.verified_error_rate | 0.1 | 0.1 | yes |
| evaluation.d3-nano.code.coverage | 0.357142857142857 | 0.357142857142857 | yes |
| evaluation.d3-nano.code.label_counts.correct | 25 | 25 | yes |
| evaluation.d3-nano.code.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-nano.code.label_counts.meaning_changed | 3 | 3 | yes |
| evaluation.d3-nano.code.status_counts.verified | 10 | 10 | yes |
| evaluation.d3-nano.code.status_counts.disputed | 4 | 4 | yes |
| evaluation.d3-nano.code.status_counts.unverified | 14 | 14 | yes |
| evaluation.d3-nano.code.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-nano.code.risk_Wilson95.lower | 0.0178762130950729 | 0.0178762130950729 | yes |
| evaluation.d3-nano.code.risk_Wilson95.upper | 0.404150026795238 | 0.404150026795238 | yes |
| comparison.d3-nano.code.test_n | 28 | 28 | yes |
| comparison.d3-nano.code.AUROC | 0.613333333333333 | 0.613333333333333 | yes |
| comparison.d3-nano.code.ECE_before | 0.182373791019174 | 0.182373791019174 | yes |
| comparison.d3-nano.code.ECE_after | 0.118074527239858 | 0.118074527239858 | yes |
| comparison.d3-nano.code.verified | 10 | 10 | yes |
| comparison.d3-nano.code.changed_in_verified | 1 | 1 | yes |
| comparison.d3-nano.code.verified_error_rate | 0.1 | 0.1 | yes |
| comparison.d3-nano.code.coverage | 0.357142857142857 | 0.357142857142857 | yes |
| comparison.d3-nano.code.question | "Q2" | "Q2" | yes |
| comparison.d3-nano.code.threshold | 0.82006940383658 | 0.82006940383658 | yes |
| selection.d3-nano.caption.question | "Q2" | "Q2" | yes |
| selection.d3-nano.caption.dev_n | 6 | 6 | yes |
| selection.d3-nano.caption.threshold | null | null | yes |
| selection.d3-nano.caption.dev_verified | 0 | 0 | yes |
| selection.d3-nano.caption.dev_changed | 0 | 0 | yes |
| selection.d3-nano.caption.dev_error_rate | null | null | yes |
| selection.d3-nano.caption.dev_AUROC.Q1 | null | null | yes |
| selection.d3-nano.caption.dev_AUROC.Q2 | null | null | yes |
| selection.d3-nano.caption.dev_label_counts.correct | 6 | 6 | yes |
| selection.d3-nano.caption.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-nano.caption.dev_label_counts.meaning_changed | 0 | 0 | yes |
| selection.d3-nano.caption.calibrator.state | "UNFITTABLE_SINGLE_CLASS" | "UNFITTABLE_SINGLE_CLASS" | yes |
| selection.d3-nano.caption.calibrator.a | null | null | yes |
| selection.d3-nano.caption.calibrator.b | null | null | yes |
| selection.d3-nano.caption.calibrator.objective | null | null | yes |
| selection.d3-nano.caption.calibrator.n | null | null | yes |
| selection.d3-nano.caption.calibrator.positives | null | null | yes |
| selection.d3-nano.caption.calibrator.negatives | null | null | yes |
| evaluation.d3-nano.caption.test_n | 13 | 13 | yes |
| evaluation.d3-nano.caption.valid | 13 | 13 | yes |
| evaluation.d3-nano.caption.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-nano.caption.source_page_groups | 9 | 9 | yes |
| evaluation.d3-nano.caption.AUROC_raw | null | null | yes |
| evaluation.d3-nano.caption.ECE_before | 0.0100373496050978 | 0.0100373496050978 | yes |
| evaluation.d3-nano.caption.ECE_after | null | null | yes |
| evaluation.d3-nano.caption.verified | 0 | 0 | yes |
| evaluation.d3-nano.caption.verified_changed | 0 | 0 | yes |
| evaluation.d3-nano.caption.verified_error_rate | null | null | yes |
| evaluation.d3-nano.caption.coverage | 0 | 0 | yes |
| evaluation.d3-nano.caption.label_counts.correct | 13 | 13 | yes |
| evaluation.d3-nano.caption.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-nano.caption.label_counts.meaning_changed | 0 | 0 | yes |
| evaluation.d3-nano.caption.status_counts.verified | 0 | 0 | yes |
| evaluation.d3-nano.caption.status_counts.disputed | 0 | 0 | yes |
| evaluation.d3-nano.caption.status_counts.unverified | 13 | 13 | yes |
| evaluation.d3-nano.caption.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-nano.caption.risk_Wilson95 | null | null | yes |
| comparison.d3-nano.caption.test_n | 13 | 13 | yes |
| comparison.d3-nano.caption.AUROC | null | null | yes |
| comparison.d3-nano.caption.ECE_before | 0.0100373496050978 | 0.0100373496050978 | yes |
| comparison.d3-nano.caption.ECE_after | null | null | yes |
| comparison.d3-nano.caption.verified | 0 | 0 | yes |
| comparison.d3-nano.caption.changed_in_verified | 0 | 0 | yes |
| comparison.d3-nano.caption.verified_error_rate | null | null | yes |
| comparison.d3-nano.caption.coverage | 0 | 0 | yes |
| comparison.d3-nano.caption.question | "Q2" | "Q2" | yes |
| comparison.d3-nano.caption.threshold | null | null | yes |
| selection.d3-nano.description.question | "Q1" | "Q1" | yes |
| selection.d3-nano.description.dev_n | 11 | 11 | yes |
| selection.d3-nano.description.threshold | 0.895733907573652 | 0.895733907573652 | yes |
| selection.d3-nano.description.dev_verified | 9 | 9 | yes |
| selection.d3-nano.description.dev_changed | 0 | 0 | yes |
| selection.d3-nano.description.dev_error_rate | 0 | 0 | yes |
| selection.d3-nano.description.dev_AUROC.Q1 | 0.9 | 0.9 | yes |
| selection.d3-nano.description.dev_AUROC.Q2 | 0.8 | 0.8 | yes |
| selection.d3-nano.description.dev_label_counts.correct | 10 | 10 | yes |
| selection.d3-nano.description.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-nano.description.dev_label_counts.meaning_changed | 1 | 1 | yes |
| selection.d3-nano.description.calibrator.state | "FIT" | "FIT" | yes |
| selection.d3-nano.description.calibrator.a | 0.370588437313991 | 0.370588437313991 | yes |
| selection.d3-nano.description.calibrator.b | 1.61669366144572 | 1.61669366144572 | yes |
| selection.d3-nano.description.calibrator.objective | 3.25450824205124 | 3.25450824205124 | yes |
| selection.d3-nano.description.calibrator.n | 11 | 11 | yes |
| selection.d3-nano.description.calibrator.positives | 10 | 10 | yes |
| selection.d3-nano.description.calibrator.negatives | 1 | 1 | yes |
| evaluation.d3-nano.description.test_n | 17 | 17 | yes |
| evaluation.d3-nano.description.valid | 17 | 17 | yes |
| evaluation.d3-nano.description.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-nano.description.source_page_groups | 8 | 8 | yes |
| evaluation.d3-nano.description.AUROC_raw | 0.1 | 0.1 | yes |
| evaluation.d3-nano.description.ECE_before | 0.28569139386832 | 0.28569139386832 | yes |
| evaluation.d3-nano.description.ECE_after | 0.144664863859585 | 0.144664863859585 | yes |
| evaluation.d3-nano.description.verified | 8 | 8 | yes |
| evaluation.d3-nano.description.verified_changed | 2 | 2 | yes |
| evaluation.d3-nano.description.verified_error_rate | 0.25 | 0.25 | yes |
| evaluation.d3-nano.description.coverage | 0.470588235294118 | 0.470588235294118 | yes |
| evaluation.d3-nano.description.label_counts.correct | 15 | 15 | yes |
| evaluation.d3-nano.description.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-nano.description.label_counts.meaning_changed | 2 | 2 | yes |
| evaluation.d3-nano.description.status_counts.verified | 8 | 8 | yes |
| evaluation.d3-nano.description.status_counts.disputed | 0 | 0 | yes |
| evaluation.d3-nano.description.status_counts.unverified | 9 | 9 | yes |
| evaluation.d3-nano.description.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-nano.description.risk_Wilson95.lower | 0.071479212752109 | 0.071479212752109 | yes |
| evaluation.d3-nano.description.risk_Wilson95.upper | 0.590724569689831 | 0.590724569689831 | yes |
| comparison.d3-nano.description.test_n | 17 | 17 | yes |
| comparison.d3-nano.description.AUROC | 0.1 | 0.1 | yes |
| comparison.d3-nano.description.ECE_before | 0.28569139386832 | 0.28569139386832 | yes |
| comparison.d3-nano.description.ECE_after | 0.144664863859585 | 0.144664863859585 | yes |
| comparison.d3-nano.description.verified | 8 | 8 | yes |
| comparison.d3-nano.description.changed_in_verified | 2 | 2 | yes |
| comparison.d3-nano.description.verified_error_rate | 0.25 | 0.25 | yes |
| comparison.d3-nano.description.coverage | 0.470588235294118 | 0.470588235294118 | yes |
| comparison.d3-nano.description.question | "Q1" | "Q1" | yes |
| comparison.d3-nano.description.threshold | 0.895733907573652 | 0.895733907573652 | yes |
| selection.d3-nano.chart.question | "Q2" | "Q2" | yes |
| selection.d3-nano.chart.dev_n | 29 | 29 | yes |
| selection.d3-nano.chart.threshold | null | null | yes |
| selection.d3-nano.chart.dev_verified | 0 | 0 | yes |
| selection.d3-nano.chart.dev_changed | 0 | 0 | yes |
| selection.d3-nano.chart.dev_error_rate | null | null | yes |
| selection.d3-nano.chart.dev_AUROC.Q1 | null | null | yes |
| selection.d3-nano.chart.dev_AUROC.Q2 | null | null | yes |
| selection.d3-nano.chart.dev_label_counts.correct | 29 | 29 | yes |
| selection.d3-nano.chart.dev_label_counts.minor | 0 | 0 | yes |
| selection.d3-nano.chart.dev_label_counts.meaning_changed | 0 | 0 | yes |
| selection.d3-nano.chart.calibrator.state | "UNFITTABLE_SINGLE_CLASS" | "UNFITTABLE_SINGLE_CLASS" | yes |
| selection.d3-nano.chart.calibrator.a | null | null | yes |
| selection.d3-nano.chart.calibrator.b | null | null | yes |
| selection.d3-nano.chart.calibrator.objective | null | null | yes |
| selection.d3-nano.chart.calibrator.n | null | null | yes |
| selection.d3-nano.chart.calibrator.positives | null | null | yes |
| selection.d3-nano.chart.calibrator.negatives | null | null | yes |
| evaluation.d3-nano.chart.test_n | 72 | 72 | yes |
| evaluation.d3-nano.chart.valid | 72 | 72 | yes |
| evaluation.d3-nano.chart.failed_or_NOT_RUN | 0 | 0 | yes |
| evaluation.d3-nano.chart.source_page_groups | 2 | 2 | yes |
| evaluation.d3-nano.chart.AUROC_raw | 0.71044776119403 | 0.71044776119403 | yes |
| evaluation.d3-nano.chart.ECE_before | 0.236581644463514 | 0.236581644463514 | yes |
| evaluation.d3-nano.chart.ECE_after | null | null | yes |
| evaluation.d3-nano.chart.verified | 0 | 0 | yes |
| evaluation.d3-nano.chart.verified_changed | 0 | 0 | yes |
| evaluation.d3-nano.chart.verified_error_rate | null | null | yes |
| evaluation.d3-nano.chart.coverage | 0 | 0 | yes |
| evaluation.d3-nano.chart.label_counts.correct | 67 | 67 | yes |
| evaluation.d3-nano.chart.label_counts.minor | 0 | 0 | yes |
| evaluation.d3-nano.chart.label_counts.meaning_changed | 5 | 5 | yes |
| evaluation.d3-nano.chart.status_counts.verified | 0 | 0 | yes |
| evaluation.d3-nano.chart.status_counts.disputed | 20 | 20 | yes |
| evaluation.d3-nano.chart.status_counts.unverified | 52 | 52 | yes |
| evaluation.d3-nano.chart.status_counts.failed | 0 | 0 | yes |
| evaluation.d3-nano.chart.risk_Wilson95 | null | null | yes |
| comparison.d3-nano.chart.test_n | 72 | 72 | yes |
| comparison.d3-nano.chart.AUROC | 0.71044776119403 | 0.71044776119403 | yes |
| comparison.d3-nano.chart.ECE_before | 0.236581644463514 | 0.236581644463514 | yes |
| comparison.d3-nano.chart.ECE_after | null | null | yes |
| comparison.d3-nano.chart.verified | 0 | 0 | yes |
| comparison.d3-nano.chart.changed_in_verified | 0 | 0 | yes |
| comparison.d3-nano.chart.verified_error_rate | null | null | yes |
| comparison.d3-nano.chart.coverage | 0 | 0 | yes |
| comparison.d3-nano.chart.question | "Q2" | "Q2" | yes |
| comparison.d3-nano.chart.threshold | null | null | yes |
| report.test.d3-nano.formula.n | 55 | 55 | yes |
| report.test.d3-nano.formula.question | "Q1" | "Q1" | yes |
| report.test.d3-nano.formula.AUROC | 0.778 | 0.777511961722488 | no: display rounding |
| report.test.d3-nano.formula.ECE_before | 0.155 | 0.154528596334888 | no: display rounding |
| report.test.d3-nano.formula.ECE_after | 0.096 | 0.0960847652529126 | yes |
| report.test.d3-nano.formula.verified_changed | 2 | 2 | yes |
| report.test.d3-nano.formula.verified | 24 | 24 | yes |
| report.test.d3-nano.formula.risk | 0.083 | 0.0833333333333333 | no: display rounding |
| report.test.d3-nano.formula.coverage | 0.436 | 0.436363636363636 | no: display rounding |
| report.test.d3-nano.code.n | 28 | 28 | yes |
| report.test.d3-nano.code.question | "Q2" | "Q2" | yes |
| report.test.d3-nano.code.AUROC | 0.613 | 0.613333333333333 | no: display rounding |
| report.test.d3-nano.code.ECE_before | 0.182 | 0.182373791019174 | no: display rounding |
| report.test.d3-nano.code.ECE_after | 0.118 | 0.118074527239858 | yes |
| report.test.d3-nano.code.verified_changed | 1 | 1 | yes |
| report.test.d3-nano.code.verified | 10 | 10 | yes |
| report.test.d3-nano.code.risk | 0.1 | 0.1 | yes |
| report.test.d3-nano.code.coverage | 0.357 | 0.357142857142857 | no: display rounding |
| report.test.d3-nano.caption.n | 13 | 13 | yes |
| report.test.d3-nano.caption.question | "Q2" | "Q2" | yes |
| report.test.d3-nano.caption.AUROC | null | null | yes |
| report.test.d3-nano.caption.ECE_before | 0.01 | 0.0100373496050978 | yes |
| report.test.d3-nano.caption.ECE_after | null | null | yes |
| report.test.d3-nano.caption.verified_changed | 0 | 0 | yes |
| report.test.d3-nano.caption.verified | 0 | 0 | yes |
| report.test.d3-nano.caption.risk | null | null | yes |
| report.test.d3-nano.caption.coverage | 0 | 0 | yes |
| report.test.d3-nano.description.n | 17 | 17 | yes |
| report.test.d3-nano.description.question | "Q1" | "Q1" | yes |
| report.test.d3-nano.description.AUROC | 0.1 | 0.1 | yes |
| report.test.d3-nano.description.ECE_before | 0.286 | 0.28569139386832 | no: display rounding |
| report.test.d3-nano.description.ECE_after | 0.145 | 0.144664863859585 | no: display rounding |
| report.test.d3-nano.description.verified_changed | 2 | 2 | yes |
| report.test.d3-nano.description.verified | 8 | 8 | yes |
| report.test.d3-nano.description.risk | 0.25 | 0.25 | yes |
| report.test.d3-nano.description.coverage | 0.471 | 0.470588235294118 | no: display rounding |
| report.test.d3-nano.chart.n | 72 | 72 | yes |
| report.test.d3-nano.chart.question | "Q2" | "Q2" | yes |
| report.test.d3-nano.chart.AUROC | 0.71 | 0.71044776119403 | no: display rounding |
| report.test.d3-nano.chart.ECE_before | 0.237 | 0.236581644463514 | no: display rounding |
| report.test.d3-nano.chart.ECE_after | null | null | yes |
| report.test.d3-nano.chart.verified_changed | 0 | 0 | yes |
| report.test.d3-nano.chart.verified | 0 | 0 | yes |
| report.test.d3-nano.chart.risk | null | null | yes |
| report.test.d3-nano.chart.coverage | 0 | 0 | yes |
| report.test.d3-mini.formula.n | 55 | 55 | yes |
| report.test.d3-mini.formula.question | "Q2" | "Q2" | yes |
| report.test.d3-mini.formula.AUROC | 0.859 | 0.858851674641148 | no: display rounding |
| report.test.d3-mini.formula.ECE_before | 0.204 | 0.204030474020268 | yes |
| report.test.d3-mini.formula.ECE_after | 0.086 | 0.0861882890279755 | no: display rounding |
| report.test.d3-mini.formula.verified_changed | 1 | 1 | yes |
| report.test.d3-mini.formula.verified | 25 | 25 | yes |
| report.test.d3-mini.formula.risk | 0.04 | 0.04 | yes |
| report.test.d3-mini.formula.coverage | 0.455 | 0.454545454545455 | no: display rounding |
| report.test.d3-mini.code.n | 28 | 28 | yes |
| report.test.d3-mini.code.question | "Q2" | "Q2" | yes |
| report.test.d3-mini.code.AUROC | 0.8 | 0.8 | yes |
| report.test.d3-mini.code.ECE_before | 0.393 | 0.39267229015875 | no: display rounding |
| report.test.d3-mini.code.ECE_after | 0.173 | 0.17307902444128 | yes |
| report.test.d3-mini.code.verified_changed | 0 | 0 | yes |
| report.test.d3-mini.code.verified | 1 | 1 | yes |
| report.test.d3-mini.code.risk | 0 | 0 | yes |
| report.test.d3-mini.code.coverage | 0.036 | 0.0357142857142857 | no: display rounding |
| report.test.d3-mini.caption.n | 13 | 13 | yes |
| report.test.d3-mini.caption.question | "Q2" | "Q2" | yes |
| report.test.d3-mini.caption.AUROC | null | null | yes |
| report.test.d3-mini.caption.ECE_before | 0.005 | 0.00480814313169717 | no: display rounding |
| report.test.d3-mini.caption.ECE_after | null | null | yes |
| report.test.d3-mini.caption.verified_changed | 0 | 0 | yes |
| report.test.d3-mini.caption.verified | 0 | 0 | yes |
| report.test.d3-mini.caption.risk | null | null | yes |
| report.test.d3-mini.caption.coverage | 0 | 0 | yes |
| report.test.d3-mini.description.n | 17 | 17 | yes |
| report.test.d3-mini.description.question | "Q1" | "Q1" | yes |
| report.test.d3-mini.description.AUROC | 0.333 | 0.333333333333333 | no: display rounding |
| report.test.d3-mini.description.ECE_before | 0.422 | 0.421564712932341 | no: display rounding |
| report.test.d3-mini.description.ECE_after | 0.132 | 0.131933041511937 | yes |
| report.test.d3-mini.description.verified_changed | 1 | 1 | yes |
| report.test.d3-mini.description.verified | 7 | 7 | yes |
| report.test.d3-mini.description.risk | 0.143 | 0.142857142857143 | no: display rounding |
| report.test.d3-mini.description.coverage | 0.412 | 0.411764705882353 | no: display rounding |
| report.test.d3-mini.chart.n | 72 | 72 | yes |
| report.test.d3-mini.chart.question | "Q2" | "Q2" | yes |
| report.test.d3-mini.chart.AUROC | 0.657 | 0.656716417910448 | no: display rounding |
| report.test.d3-mini.chart.ECE_before | 0.234 | 0.233540044965647 | no: display rounding |
| report.test.d3-mini.chart.ECE_after | null | null | yes |
| report.test.d3-mini.chart.verified_changed | 0 | 0 | yes |
| report.test.d3-mini.chart.verified | 0 | 0 | yes |
| report.test.d3-mini.chart.risk | null | null | yes |
| report.test.d3-mini.chart.coverage | 0 | 0 | yes |
| report.dev.d3-nano.formula.AUROC_Q1 | 0.9167 | 0.916666666666667 | yes |
| report.dev.d3-nano.formula.AUROC_Q2 | 0.9028 | 0.902777777777778 | yes |
| report.dev.d3-nano.formula.question | "Q1" | "Q1" | yes |
| report.dev.d3-nano.formula.threshold | 0.9009 | 0.90093911851593 | yes |
| report.dev.d3-nano.formula.verified | 12 | 12 | yes |
| report.dev.d3-nano.formula.n | 23 | 23 | yes |
| report.dev.d3-nano.formula.risk | 0 | 0 | yes |
| report.dev.d3-nano.code.AUROC_Q1 | 0.5185 | 0.518518518518518 | yes |
| report.dev.d3-nano.code.AUROC_Q2 | 0.7037 | 0.703703703703704 | yes |
| report.dev.d3-nano.code.question | "Q2" | "Q2" | yes |
| report.dev.d3-nano.code.threshold | 0.8201 | 0.82006940383658 | yes |
| report.dev.d3-nano.code.verified | 5 | 5 | yes |
| report.dev.d3-nano.code.n | 12 | 12 | yes |
| report.dev.d3-nano.code.risk | 0 | 0 | yes |
| report.dev.d3-nano.description.AUROC_Q1 | 0.9 | 0.9 | yes |
| report.dev.d3-nano.description.AUROC_Q2 | 0.8 | 0.8 | yes |
| report.dev.d3-nano.description.question | "Q1" | "Q1" | yes |
| report.dev.d3-nano.description.threshold | 0.8957 | 0.895733907573652 | yes |
| report.dev.d3-nano.description.verified | 9 | 9 | yes |
| report.dev.d3-nano.description.n | 11 | 11 | yes |
| report.dev.d3-nano.description.risk | 0 | 0 | yes |
| report.dev.d3-nano.caption.AUROC_Q1 | null | null | yes |
| report.dev.d3-nano.caption.AUROC_Q2 | null | null | yes |
| report.dev.d3-nano.caption.question | "Q2" | "Q2" | yes |
| report.dev.d3-nano.caption.threshold | null | null | yes |
| report.dev.d3-nano.caption.verified | 0 | 0 | yes |
| report.dev.d3-nano.caption.n | 6 | 6 | yes |
| report.dev.d3-nano.caption.risk | null | null | yes |
| report.dev.d3-nano.chart.AUROC_Q1 | null | null | yes |
| report.dev.d3-nano.chart.AUROC_Q2 | null | null | yes |
| report.dev.d3-nano.chart.question | "Q2" | "Q2" | yes |
| report.dev.d3-nano.chart.threshold | null | null | yes |
| report.dev.d3-nano.chart.verified | 0 | 0 | yes |
| report.dev.d3-nano.chart.n | 29 | 29 | yes |
| report.dev.d3-nano.chart.risk | null | null | yes |
| report.dev.d3-mini.formula.AUROC_Q1 | 0.875 | 0.875 | yes |
| report.dev.d3-mini.formula.AUROC_Q2 | 0.9306 | 0.930555555555556 | yes |
| report.dev.d3-mini.formula.question | "Q2" | "Q2" | yes |
| report.dev.d3-mini.formula.threshold | 0.8963 | 0.896281683952962 | yes |
| report.dev.d3-mini.formula.verified | 15 | 15 | yes |
| report.dev.d3-mini.formula.n | 23 | 23 | yes |
| report.dev.d3-mini.formula.risk | 0 | 0 | yes |
| report.dev.d3-mini.code.AUROC_Q1 | 0.6667 | 0.666666666666667 | yes |
| report.dev.d3-mini.code.AUROC_Q2 | 0.6667 | 0.666666666666667 | yes |
| report.dev.d3-mini.code.question | "Q2" | "Q2" | yes |
| report.dev.d3-mini.code.threshold | 0.8293 | 0.8292567865993 | yes |
| report.dev.d3-mini.code.verified | 6 | 6 | yes |
| report.dev.d3-mini.code.n | 12 | 12 | yes |
| report.dev.d3-mini.code.risk | 0 | 0 | yes |
| report.dev.d3-mini.description.AUROC_Q1 | 0.8 | 0.8 | yes |
| report.dev.d3-mini.description.AUROC_Q2 | 0.7 | 0.7 | yes |
| report.dev.d3-mini.description.question | "Q1" | "Q1" | yes |
| report.dev.d3-mini.description.threshold | 0.8978 | 0.8977581771154 | yes |
| report.dev.d3-mini.description.verified | 8 | 8 | yes |
| report.dev.d3-mini.description.n | 11 | 11 | yes |
| report.dev.d3-mini.description.risk | 0 | 0 | yes |
| report.dev.d3-mini.caption.AUROC_Q1 | null | null | yes |
| report.dev.d3-mini.caption.AUROC_Q2 | null | null | yes |
| report.dev.d3-mini.caption.question | "Q2" | "Q2" | yes |
| report.dev.d3-mini.caption.threshold | null | null | yes |
| report.dev.d3-mini.caption.verified | 0 | 0 | yes |
| report.dev.d3-mini.caption.n | 6 | 6 | yes |
| report.dev.d3-mini.caption.risk | null | null | yes |
| report.dev.d3-mini.chart.AUROC_Q1 | null | null | yes |
| report.dev.d3-mini.chart.AUROC_Q2 | null | null | yes |
| report.dev.d3-mini.chart.question | "Q2" | "Q2" | yes |
| report.dev.d3-mini.chart.threshold | null | null | yes |
| report.dev.d3-mini.chart.verified | 0 | 0 | yes |
| report.dev.d3-mini.chart.n | 29 | 29 | yes |
| report.dev.d3-mini.chart.risk | null | null | yes |

</details>

## Validation

The final code check run completed at approximately 13:24 UTC.
Test and ruff caches/temporary fixtures were directed under this directory
for the final runs and removed afterward; bytecode generation was disabled.

| Command | Result |
|---|---|
| `.venv/bin/pytest docs/research/d3-quality-check-2026-11-02/test_score.py` | PASS: 98 tests in 2.84s |
| `.venv/bin/ruff check --no-force-exclude` on all three new Python files | PASS: All checks passed |
| `.venv/bin/ruff format --check --no-force-exclude` on those files | PASS: 3 files already formatted |
| `scripts/check` | PASS: lint, 72 files formatted, validation bug rules, pyright 0 errors / 0 warnings |
| Reproduction CLI against saved W4b inputs | PASS: 494 full-precision checks, 24 explained display differences, no UNKNOWN |

Tests were added at the approved seams in successive red/green slices.
Independent controls include a symmetric Platt optimum
`a=0.6748316143423994, b=0`, an unpenalized constant-score intercept, Wilson
reference values, hand-computed ECE, and a seed-153 bootstrap fixture with
994 skipped draws. A five-group fixture detects deduplicating sampled groups
(correct CI [0.35, 29/30]; the deduplicating mutation gives different bounds).
A selected-threshold fixture reaches equality t_d=t_v and proves the conflict
counter and formula/status distinction detect the overlap.

### Test list (46 functions; 98 parameterized cases)

- `test_auc_excludes_minor_and_uses_correct_positive`
- `test_auc_ties_empty_and_single_class`
- `test_question_ties_undefined_and_strict_near_tie`
- `test_platt_symmetric_reference`
- `test_platt_constant_score_unpenalized_intercept_and_minor_is_positive`
- `test_platt_nonnegative_slope_and_clamped_endpoints`
- `test_platt_single_y_class_and_empty_are_null`
- `test_verified_inclusive_boundary_and_maximum_coverage`
- `test_verified_exact_two_percent_is_admissible`
- `test_verified_duplicate_scores_and_no_admissible_are_null`
- `test_disputed_maximizes_changed_not_precision_and_exact_eighty_percent`
- `test_disputed_equal_changed_prefers_smaller_u`
- `test_disputed_empty_no_admissible_and_tied_values`
- `test_floor_boundary_branches`
- `test_wilson_known_values_and_zero_denominator`
- `test_ece_hand_computed_bins_and_minor`
- `test_bootstrap_source_groups_seed153_skip_count`
- `test_bootstrap_percentile_and_all_skipped`
- `test_weak_signal_exact_boundaries`
- `test_status_precedence_inclusive_bounds_nulls_and_conflicts`
- `test_metrics_failures_stay_in_denominators_and_minor_is_safe`
- `test_metrics_all_zero_denominators_and_null_calibration`
- `test_ordered_thresholds_no_conflict_and_negative_control_counts_overlap`
- `test_formula_rule_combination_correct_only_null_flags_failures_and_misses`
- `test_combination_formula_only_null_denominators_and_inclusive_boundary`
- `test_select_rows_records_both_aucs_fit_thresholds_and_frozen_test_count`
- `test_floor_blocks_thresholds_and_non_auc_reports`
- `test_floor_counts_gold_independently_of_failures_and_unfittable_dev`
- `test_evaluation_uses_frozen_fit_and_thresholds_without_mutation`
- `test_evaluation_rejects_inconsistent_frozen_test_count`
- `test_frozen_counts_missing_or_invalid_are_input_errors`
- `test_row_validation_rejects_malformed_inputs`
- `test_row_validation_required_fields_duplicate_ids_and_failed_null_scores`
- `test_cli_select_evaluate_hashes_partitions_and_selection_immutability`
- `test_raw_extraction_uses_faithful_and_noul_and_checks_cache`
- `test_w4b_join_missing_unknown_duplicate_stops`
- `test_w4b_converter_schema_group_and_no_gold_text_copy`
- `test_w4b_legacy_disputed_without_fit_and_verified_precedence`
- `test_reproduction_rounding_is_explained_but_not_called_numeric_match`
- `test_reproduction_cli_reads_raw_outputs_and_published_tables`
- `test_bootstrap_preserves_repeated_group_copies_in_percentiles`
- `test_unfittable_full_floor_never_uses_raw_disputed_fallback`
- `test_evaluation_auroc_uses_raw_even_when_calibrator_slope_collapses`
- `test_evaluation_rejects_inconsistent_selection`
- `test_cli_count_mismatch_and_input_overwrite_stop_without_output`
- `test_selected_equal_thresholds_report_conflicts_and_rule_uses_d3_predicate`

## Artifact hashes

| File | SHA-256 |
|---|---|
| score.py | 2af45383f12e0e929ed320deb937ae7d7e5318b6ad1939746117d13f316ff0ba |
| test_score.py | d309f35076832027109b84247f2bd8f23de1d4cda2af63d625cff7c76e1b34eb |
| reproduce_w4b.py | ee5d543787626ac535dd8568c562eafcbf4e690eb5d10b223cf59b1b63b049e6 |
| reproduction.json | a76bbf4f99c3714886616db9abaf23a8f7173de41ace61278ff211c5bcf141a1 |

## Limits and remaining work

No blockers remain for this coding task. All requested implementation files,
synthetic tests, historical reproduction and required completion checks passed.
W4b literals have the 24 explained rounding differences above; none is hidden
by changing the tolerance. New #153 data, inference quality, real runtime
failures, GPU behavior and the unrelated full test suite were not evaluated.
The main line supplies its frozen gold counts and dev/test rows; this report
makes no quality claim about unseen #153 outputs.
