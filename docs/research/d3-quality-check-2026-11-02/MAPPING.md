# #153 scoring plan gate

Phase 1 only. The functions and tests below are proposed, not implemented or
passed. `SMOKE.md` records the executed raw-output mapping and dev AUROC check.
The English rules in the task govern; the freeze was read first, including
sections 4–7. No inference, network, GitHub, commits or dependency changes are
part of this work.

## Scope and seams

The change reaches only this directory:

- `score.py`: pure scoring functions and the two requested CLI subcommands.
- `test_score.py`: synthetic rows through those functions and CLI input/output.
- `reproduce_w4b.py`: read-only W4b conversion and independent comparison.
- `SCORING.md`: phase 2 reproduction table, test results and unresolved differences.
- `MAPPING.md` and `SMOKE.md`: this review gate and its executed evidence.

There are no production callers, exports, fixtures, dependencies or configuration
changes. The main line will call the CLI. The reproduction adapter will call the
same statistical functions, with W4b's explicitly different comparison policy.
It will not import or execute W4b's scorer or its scripts with write side effects.
No source text, gold reasons, reconstructed content, images or local absolute
paths will be copied into outputs. Input locations come from CLI arguments.

The public seams proposed for review are `select_question`, `fit_platt`,
`calibrate`, `verified_threshold`, `disputed_threshold`, `sample_floor`,
`bootstrap_auc`, `weak_signal`, `classify`, `evaluate_rows`, and the CLI.
`auc`, `ece`, `wilson` and `combined_with_rule` are pure statistical functions
shared by the CLI and the reproduction adapter. Tests observe their returned
values and CLI artifacts, without mocking SciPy or inspecting its call sequence.

## Blocking interface decision: C1 needs frozen test counts

`select DEV_ROWS.jsonl OUT_SELECTION.json` has no input containing test label
counts. It cannot distinguish, for example, dev changed=5/test changed=5 from
dev changed=5/test changed=0. These require different C1 states and different
threshold-selection behavior. The dev input SHA-256 cannot supply those counts.

The proposed pure selection function takes dev rows and frozen test
`meaning_changed` counts per model/category. Those counts must come from gold
before inference, without reading test scores. The CLI needs an approved way to
receive that metadata. The smallest proposed extension is a required
`--test-counts FROZEN_COUNTS.json` argument to `select`, containing only the
per-model/category test changed counts, with its SHA-256 recorded in selection.
This extension is **not authorized or implemented** at this gate. An equivalent
agreed input contract could keep the positional CLI unchanged.

Unknown test counts will never be guessed, treated as zero, or treated as a
pass. Deferring threshold selection until `evaluate` would violate the stated
dev-selection contract; selecting provisional thresholds without C1 would also
violate it. Phase 2 needs this interface decision alongside plan review.

## Row and reporting conventions proposed for review

- Partition strictly by `(model, category)`. `id` is unique within a model/split;
  the same item ID can occur for different models. Required identity and group
  fields are nonempty strings; labels are exactly `correct`, `minor`, or
  `meaning_changed`. Reject duplicate identities, wrong split, non-boolean
  `failed`/non-null `rule_flag`, and nonfinite/out-of-range probabilities.
- A nonfailed dev row supplies both finite `q1` and `q2`; a nonfailed test row
  supplies finite `score`. Null required scores on a nonfailed row are malformed
  input, not a fabricated probability or an implicit successful run. Failed rows
  may have null scores and never contribute scores to fitting or AUROC/ECE.
- Eligible rows mean all supplied, labeled rows, including runtime failures.
  C1 uses eligible gold counts, independently of inference success. Calibration
  uses all nonfailed dev rows, with `Y = int(label != "meaning_changed")`.
  Correct and minor are distinct in counts but both are positive for calibration.
- The full C1 state is named `thresholds`; the other states are exactly
  `auroc_only` and `not_evaluable`. The Platt fit in rule 3 can be recorded even
  when C1 prevents threshold selection. In `auroc_only`, report counts and raw
  AUROC/CI, with threshold-derived metrics and ECE unavailable. In
  `not_evaluable`, report counts and the reason, without an evaluability claim.
  No thresholds are selected or reported in either reduced state.
- Bootstrap groups are the source-page groups represented in the valid
  correct/meaning_changed AUROC population. Minor-only or failed-only groups do
  not enter that population. Sort group keys; start a fresh NumPy
  `default_rng(153)` for each model/category; draw exactly the number of distinct
  groups with replacement on each of 2,000 attempts, retaining all rows and
  repeated copies of every sampled group. Use linear-interpolated percentiles.
- Verified takes precedence when both threshold predicates hold, as ordered in
  rule 8. Count every simultaneous predicate match before assigning status.
  Rule 9's disputed metrics use the assigned disputed status; rule 10 uses its
  explicit d3 predicate `p <= t_d`, including a conflict if one occurs.
- For rule 9, failed rows remain in coverage, recall and false-flag denominators;
  their d3 flag is false. Formula combination metrics include rows with a known
  boolean `rule_flag`; null flags are excluded with their count disclosed.
  Known rule flags remain usable when d3 fails, with the d3 flag false.
- A rate receipt contains numerator `k`, denominator `n`, `value = k/n` or null,
  and its Wilson interval or null. For disputed count, also report its fraction
  of all eligible rows and that fraction's interval; the integer count itself
  has no probability interval. The verified risk upper bound is the upper end
  of the two-sided Wilson 95% interval, matching W4b's convention.
- Selection hashes the exact input JSONL bytes. Per model/category it records
  the question, both dev AUROCs, nullable fit, both nullable thresholds, C1 state,
  and dev eligible/valid counts by label. Evaluation reads that frozen selection
  without changing it or fitting anything. Test AUROC/CI and C2 never feed back
  into selection. If approved frozen test counts disagree with supplied test
  labels, evaluation must report the input inconsistency rather than silently
  changing the floor or thresholds.

These conventions make unspecified input and denominator details reviewable;
they do not add a new selection criterion or tune any threshold.

## Rule-to-function and mutation-test mapping

All test names below are planned tests in `test_score.py`. No test has run yet.

| Rule | Function and exact predicate | Test that must fail under the named mutation |
|---|---|---|
| 1: raw score / AUROC | W4b adapter reads Q1 from `result.answers.Q1.probabilities.faithful`, Q2 from `result.answers.Q2.noul`. Schema already carries these as `q1`, `q2` or selected `score`. `auc` uses only nonfailed `correct` and `meaning_changed`, positive=correct. AUROC is `P(s_correct > s_changed) + 0.5*P(equal)`; either class absent gives null. Do not clamp raw AUROC/ECE inputs. | `test_raw_extraction_uses_faithful_and_noul`: mutation reads confidence or sums faithful+minor. `test_auc_excludes_minor_and_uses_correct_positive`: mutation includes minor or reverses positive class. `test_auc_ties_empty_and_single_class`: mutation gives ties zero credit or returns 0 for undefined AUROC. |
| 2: select question | `select_question`: choose Q1 iff `A1 is not null and (A2 is null or A1 > A2)`; otherwise Q2. Compare exact values, without a tolerance. | `test_question_tie_and_both_undefined_choose_q2`: mutation tie→Q1. `test_question_defined_beats_undefined`: mutation treats null as a numeric AUROC. `test_question_strictly_better_even_near_tie`: mutation uses an approximate tie. |
| 3: Platt | `fit_platt`: on all valid selected dev rows set `x=logit(clip(raw,1e-6,1-1e-6))`; minimize `sum(logaddexp(0,a*x+b)-Y*(a*x+b)) + 0.5*a*a`, with `a >= 0` and unbounded, unpenalized `b`. SciPy L-BFGS-B starts at `(1, logit(mean(Y)))`. Reuse W4b numerical options `maxiter=1000, ftol=1e-12, gtol=1e-8`. One fit; no search. Fewer than two Y classes gives null. `calibrate` applies `expit(a*x+b)` or returns null for a null fit. Optimizer failure is explicit and supplies no thresholds. | `test_platt_symmetric_reference`: independently derived symmetric optimum detects mean-BCE instead of sum-BCE and a changed slope penalty. `test_platt_constant_score_unpenalized_intercept`: scores all 0.5, Y prevalence 3/4 require `a=0`, `b=log(3)`, p=0.75; mutation penalizes b. `test_platt_minor_is_positive`: mutation drops minor. `test_platt_nonnegative_slope_and_clamped_endpoints`: mutation removes bound/clamp. `test_platt_single_y_class_and_empty_are_null`: mutation uses raw label cardinality or fabricates identity calibration. |
| 4: verified threshold | `verified_threshold`: for each `t` in unique calibrated dev values form `V(t)={i:p_i >= t}`. Candidate admissible iff nonempty and `changed(V)/len(V) <= 0.02`. Maximize `(len(V), t)`; none gives null. C1 or null calibration prevents calling threshold selection. | `test_verified_inclusive_boundary_and_maximum_coverage`: mutation `>=`→`>` or maximizes threshold instead of coverage. `test_verified_exact_two_percent_is_admissible`: 49 safe and 1 changed, all selected, mutation `<=0.02`→`<0.02`. `test_verified_duplicate_scores_cannot_be_split`: mutation manufactures a subset within a tie. `test_verified_empty_or_no_admissible_is_null`: mutation returns 0 or 1 as a fallback. |
| 5: disputed threshold | `disputed_threshold`: for each unique calibrated dev `u`, `D(u)={i:p_i <= u}`; admissible iff nonempty and `changed(D)/len(D) >= 0.80`. Maximize `(changed(D), -u)`, and return u itself as `t_d`; no admissible set gives null. Never select on test or on raw scores. | `test_disputed_inclusive_and_exact_eighty_percent`: mutation `<=`→`<`, or precision `>=`→`>`. `test_disputed_maximizes_changed_not_precision`: mutation optimizes precision. `test_disputed_equal_changed_prefers_smaller_u`: mutation tie→larger u. `test_disputed_empty_no_admissible_and_tied_values`: mutation invents a threshold or splits equal scores. |
| 6: C1 | `sample_floor(d,t)`: `thresholds` iff `d >= 5 and t >= 5`; else `auroc_only` iff `d+t >= 5`; else `not_evaluable`. Here d and t count eligible `meaning_changed` labels in their respective splits. Thresholds stay null outside `thresholds`, regardless of apparent dev performance. | `test_floor_boundary_branches`: (5,5)→thresholds; (4,5),(5,4),(0,5),(4,1)→auroc_only; (2,2),(0,0)→not_evaluable. Mutations AND→OR, `>=5`→`>5`, or combined total used for full eligibility fail. `test_floor_blocks_both_thresholds_and_non_auc_reports`: mutation still selects either threshold or emits ECE. `test_floor_counts_gold_independently_of_failures`: mutation uses only scored rows. CLI floor-metadata test remains blocked on the input decision above. |
| 7: C2 / CI | `bootstrap_auc`: apply rule 1 to each group resample; skip class-deficient draws, count skips, do not redraw until 2,000 successes. CI is valid AUROCs' 2.5th and 97.5th percentiles; no valid draws gives null. `weak_signal` is true iff test raw AUROC is defined and `AUROC >= 0.75` and CI exists and `CI.lower > 0.5`; missing quantities give null/unknown rather than a pass. | `test_bootstrap_source_groups_seed153_skip_count`: two pure-label groups with multiple rows each; pin the deterministic skipped count and CI [1,1]. Mutations row-resampling, deduplicating repeated groups, seed change, or 2,000-success retries fail. `test_bootstrap_percentile_and_all_skipped`: mutation normal-approximation CI or fake [0,1] for undefined CI. `test_weak_signal_exact_boundaries`: (0.75,lower>0.5) passes; lower=0.5 and AUROC<0.75 fail; null CI is unknown. Mutation `>0.75` or `>=0.5` fails. |
| 8: status | `classify`: failed first; otherwise compute calibrated p using the frozen fit. `v = p is not null and t_v is not null and p >= t_v`; `d = p is not null and t_d is not null and p <= t_d`; conflict=`v and d`. Status is verified if v, else disputed if d, else unverified. Null thresholds disable their predicates. | `test_status_failed_precedence_and_inclusive_bounds`: mutation scores a failed row or uses strict threshold comparisons. `test_status_null_fit_or_thresholds_is_unverified`: mutation uses raw scores as calibrated scores. `test_status_conflict_count_and_verified_precedence`: mutation hides overlap or lets disputed win. `test_ordered_thresholds_have_no_conflict`: negative control plus an overlapping/equal threshold fixture proves the counter can detect conflicts. |
| 9: test metrics | `evaluate_rows`: label counts include all eligible test rows. AUROC/CI use rule 1/7 population; raw/calibrated ECE use nonfailed scores, Y=correct/minor, 10 equal-width bins with index `min(9,floor(10*p))`. ECE=`sum(n_bin*abs(mean(p)_bin-mean(Y)_bin))/n_scored`. Let N=all eligible, V=verified statuses, D=disputed statuses, C=all changed, S=all correct/minor. Coverage=`len(V)/N`; verified risk=`changed(V)/len(V)` with Wilson upper bound. Disputed count=`len(D)`; precision=`changed(D)/len(D)`; recall=`changed(D)/len(C)`; false-flag rate=`safe(D)/len(S)`. Every zero denominator is null. `wilson(k,n)` uses z=1.959963984540054, center `(k/n+z²/(2n))/(1+z²/n)` and half-width `z*sqrt((k/n)*(1-k/n)/n+z²/(4n²))/(1+z²/n)`, clipped to [0,1]. C1 suppressions above apply. | `test_metrics_failures_stay_in_coverage_recall_and_false_flag_denominators`: mutation excludes failures. `test_metrics_disputed_receipts_include_minor_as_safe`: mutation drops minor from the safe denominator. `test_metrics_all_zero_denominators_are_null`: mutation 0/0→0. `test_wilson_known_values`: Wilson(0,10)≈[0,0.2775328], Wilson(1,1)≈[0.2065493,1], Wilson(0,0)=null; mutation uses Wald or one-sided z. `test_ece_hand_computed_bins_and_minor`: [(0.1,correct),(0.19,changed)]→0.355; mutation per-row absolute errors. Also test p=0, p=1, exact bin edges, minor, empty input and null calibrated ECE. |
| 10: formula/rule combination | `combined_with_rule`: formula rows only; restrict to known rule flags. Let `d3 = not failed and p is not null and t_d is not null and p <= t_d`. Among changed rows with `rule_flag == false`, report caught k=`count(d3)`, n=all such rule misses, rate and Wilson CI. Among `label == correct` only, report OR k=`count(rule_flag or d3)` and AND k=`count(rule_flag and d3)`, each over n=all correct rows with known rule flags. Minor is excluded from these two denominators. Missing rule flags are not false. Empty denominators give null. | `test_formula_rule_missed_changed_caught_receipt`: mutation uses all changed as denominator. `test_formula_rule_or_and_correct_only`: truth-table fixture; mutation OR↔AND or includes minor. `test_formula_rule_null_flags_are_excluded_not_false`: mutation coerces null to false. `test_formula_rule_failure_and_threshold_boundary`: mutation drops a known rule flag when d3 fails or uses strict d3 `<`. `test_combination_formula_only_and_null_denominators`: mutation reports combination for other categories or 0/0→0. |

With unique candidate values, different verified thresholds necessarily select
different nonempty set sizes. Its higher-threshold coverage tie-break is retained
in the exact ordering but cannot be distinguished by a valid-input mutation test.
Equal calibrated values must stay together; that is the observable tie test.
For disputed selection, equal changed counts at different thresholds are possible
and the smaller-u tie-break is directly testable.

## Concrete threshold controls

- Verified: calibrated scores 0.8 for one changed item and 0.9 for 49 safe items
  must select 0.8, verifying all 50 at exactly 2% changed.
- Verified: a safe and changed item both at 0.8 give null, not a selected safe
  item fabricated by breaking the tie.
- Disputed maximum caught: (0.1,changed), (0.2,correct), and three
  (0.3,changed) items select 0.3, catching four at precision 4/5 rather than
  selecting 0.1 for its higher precision.
- Disputed tie: four changed at 0.1 and one correct at 0.2 select 0.1; both
  candidates catch four and are admissible, so the smaller u wins.
- Conflict detection: use a row satisfying both supplied thresholds, and a
  separate fixture with `t_d < t_v`. Do not assume threshold selection always
  produces strict separation; equality can occur, including when a bottom
  changed item is only 1/50 of a verified set.

## W4b comparison: similarities and every scoring difference

Read: `calibrate.py`, `evaluate.py`, `summarize.py`, `test_calibration.py`,
`test_evaluate.py`, `protocol.json`, gold fields, both models' saved selections,
both splits' raw outputs, `comparison.json`, and `report.md` section 3.

| Area | W4b behavior | #153 behavior / reproduction treatment |
|---|---|---|
| Raw extraction, rule 1 | Q1 faithful; Q2 noul. Cached in `safe_scores`. Minor excluded from AUROC, correct positive. | Same. Read nested raw answers independently and check their equality to cached scores; never take cached scores as the only evidence. |
| Question choice, rule 2 | Strict greater-than for Q1; exact tie/both undefined choose Q2. | Same, including the actual mini/code tie. |
| Platt, rule 3 | Summed BCE + 0.5*a²; nonnegative slope, unpenalized intercept; clipped logit; fixed initialization and optimizer options. Empty/single Y class is unfittable; optimization failure explicit. | Same numerical specification. New selection represents unavailable fit as null with a reason; W4b uses a state object with null a/b. No identity fallback. |
| Verified, rule 4 | Unique calibrated dev candidates; inclusive upper tail; empirical risk <=2%; largest set, then higher threshold. | Same mathematical selection. #153 additionally gates it on C1. |
| Disputed, rules 5/8 | After verified precedence, raw safe score <0.5 gives disputed, even without calibration. No learned t_d. | New dev-calibrated lower-tail threshold, precision >=0.80, maximize caught changed, smaller-u tie-break, applied inclusively. W4b comparison alone retains raw <0.5 and does not call disputed-threshold selection. |
| Sample floor, rule 6 | No C1. Any two-class valid dev set can fit and select verified. | New dev>=5 AND test>=5 changed floor. W4b reproduction explicitly bypasses C1; otherwise it would suppress all published verified thresholds. |
| Weak signal and uncertainty, rule 7 | Raw AUROC point estimate; no source-page bootstrap or C2 pass criterion. | New 2,000 group resamples, seed 153, skipped-count disclosure and percentile CI; C2 uses AUROC>=0.75 and lower>0.5. Omitted for historical W4b comparison. |
| Status, rule 8 | failed, verified, raw-disputed, unverified; no conflict counter. | failed, verified, calibrated-disputed, unverified; count simultaneous threshold predicates. Verified precedence is unchanged. |
| Metrics, rule 9 | Test labels/valid/failures, raw and calibrated AUROC, raw/calibrated ECE, verified count/changed/risk/Wilson two-sided CI, coverage and status counts. | Same shared raw AUROC/ECE/verified definitions. Add raw AUROC CI, verified upper-bound field, disputed precision/recall/false-flag receipts and intervals, conflicts, and C1 reporting restrictions. Calibrated AUROC, reliability-bin tables and runtime metrics are W4b extras, not requested #153 metrics. |
| Formula rule, rule 10 | No joint report. | New missed-changed/caught-d3 and OR/AND false-flag rates with Wilson intervals. Rule 10's false-flag denominator is strictly correct; rule 9's is correct OR minor. |
| Paths and receipts | Scripts bind their directory, fixed model list and fixed 81/185 counts; selection stores producer/dev-file hashes. Evaluation checks launch/freeze hashes. | CLI paths, dynamic model/category partitions, input-file SHA-256 and explicit counts. No production launching, model calls or runtime environment changes. Retain selection immutability during evaluation. |

The freeze's prose says below t_d and Wilson upper bounds; the governing English
rules require inclusive `<= t_d` and full disputed/combined Wilson intervals.
The freeze's chart-only-AUROC restriction is a main-line reporting decision;
the generic scorer implements the supplied English C1 rules without hardcoded
category eligibility exceptions. Runtime/cost/GPU reporting is outside this task.

The mapped gold counts explain why historical comparison must be explicit:

| Category | Dev changed | Test changed | C1 state under #153 |
|---|---:|---:|---|
| caption | 0 | 0 | not_evaluable |
| chart | 0 | 5 | auroc_only |
| code | 3 | 3 | auroc_only |
| description | 1 | 2 | not_evaluable |
| formula | 4 | 11 | auroc_only |

## Reproduction contract for phase 2

`reproduce_w4b.py W_DIR OUT.json` will join by embedded gold/result `id`, never
by file order or an inferred filename. Validate uniqueness, splits, categories,
question names, known labels, raw score domains and the absence of unknown or
missing IDs. A join mismatch stops the run; no nearest-ID guessing. W4b currently
has complete saved output coverage and zero runtime failures in both models.

Convert only the requested row fields. Map `split_group` to `group`, non-OK
runtime state to `failed`, set `rule_flag=null`, dev raw answers to q1/q2 and
test selected raw answer to score. Gold labels and groups come only from gold.
Recompute dev AUROCs, question choice, fit and verified threshold; saved selection
is a comparison target, never the source of fitted parameters. Check that the
recomputed question agrees with the one actually asked on saved test rows; if it
does not, report that test reproduction cannot use unavailable alternative
question outputs. Do not relabel a saved test score as a different question.

Compare each model/category's full-precision selection receipts: both dev AUROCs,
chosen question, valid/label counts, fit state/parameters/objective and threshold,
dev verified/changed/risk. Compare test n, AUROC, ECE before/after, verified count,
changed count, risk, coverage and Wilson bounds against saved evaluation metrics
and `comparison.json`. Check report section 3's main and dev receipt tables as
separate published targets. Do not include its W4/VJev baseline table in a W4b
reproduction claim.

Exact strings, counts and nulls must match. For finite numeric targets use
absolute error <=1e-4. Do not round our results before computing that error.
Report tables round AUROC/ECE to 3 decimals, dev AUROC/thresholds to 4 decimals,
and some rates to 1 decimal percent. Some literal published numbers consequently
differ from their full-precision source by more than 1e-4. Each such case must
be listed with both values and the specific display-rounding cause; do not
silently relax the tolerance or call the literal comparison a match. Separately
check that formatting the recomputed value at the report's printed precision
reproduces the published display. A full-precision mismatch needs an actual
diagnosis; UNKNOWN is never a pass.

`SCORING.md` will show number/source, W4b value, independently recomputed value,
match and any mismatch cause, plus the test list. OUT.json will contain numeric
receipts and sanitized provenance hashes, never gold explanatory text or paths
to the user's files. Reproduction outputs must not overwrite W4b inputs.

## Phase 2 execution after review

Resolve the C1 metadata contract, then implement one agreed seam/test at a time:
selection/calibration, thresholds/floor, test accounting/uncertainty, formula
combination, CLI, and historical conversion/comparison. Synthetic tests establish
the predicates independently of historical scores. CLI tests cover input hashing,
multiple model/category partitions, malformed/duplicate rows, preserved frozen
selection, and no test refitting or threshold movement.

Run `.venv/bin/pytest docs/research/d3-quality-check-2026-11-02/test_score.py`
and `scripts/check`. Also run ruff explicitly with `--no-force-exclude` on the
new Python files because project ruff configuration excludes docs. Use installed
tools directly; `uv run` is unavailable. Full inference, production GPU checks,
the unrelated whole test suite and Git operations are outside scope. The user's
90-minute wall-clock cap applies across both phases. The first recorded clock
reading was 2026-11-02 12:35:33 UTC, giving an outer deadline of 14:05:33 UTC;
this plan does not extend it across the review wait. Review waiting does not
authorize phase 2. Stop and report incomplete checks if the cap is reached.

**Gate status: waiting for user review. No phase 2 implementation has started.**
