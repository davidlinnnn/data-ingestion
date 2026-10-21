# G2 evaluation freeze: primary-source guidance

Date: 2026-10-15. Scope: evaluation design only; no inference, tuning, new guard, or accuracy threshold. The recommendations below are project choices informed by the sources, not results or requirements established by those sources.

## Findings from primary sources

- **Repeated test feedback is tuning.** Optimizing a selection criterion on a finite sample can overfit it and bias performance estimates, even beyond model training. scikit-learn also prohibits using test data to make model choices. [Cawley and Talbot, JMLR 2010](https://jmlr.org/papers/v11/cawley10a.html), [Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html).
- **Dependent examples need grouped splits.** To measure generalization to unseen groups, every validation example must come from a group absent from training. The domain determines what a group is; stratified group splitting attempts to preserve class proportions while keeping groups together. Stratification does not remove small-sample uncertainty. [Grouped cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data).
- **A random seed is reproducibility, not independence.** `GroupShuffleSplit` accepts domain-specific groups; its sizes count groups rather than rows, and successive test sets can overlap. [GroupShuffleSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html).
- **Model selection needs its own evaluation boundary.** Selecting settings and reporting performance on the same data produces optimistic estimates. Nested cross-validation separates inner selection from outer evaluation when evaluating an entire search procedure. [Nested versus non-nested cross-validation](https://scikit-learn.org/stable/auto_examples/model_selection/plot_nested_cross_validation_iris.html).
- **Abstention trades coverage for error.** Geifman and El-Yaniv define coverage as the fraction accepted and selective risk as loss among accepted predictions. Both matter; the paper's statistical guarantees assume independently sampled data and do not automatically apply to this document corpus. [Selective Classification for Deep Neural Networks, §2](https://proceedings.neurips.cc/paper/2017/file/4a8423d5e91fda00bb7e46540e2b0cf1-Paper.pdf).
- **The metric is a task decision.** scikit-learn advises choosing a metric meaningful for the use case and treating decision-threshold selection as tuning. [Decision-threshold tuning](https://scikit-learn.org/stable/modules/classification_threshold.html).
- **Tiny denominators need cautious reporting.** NIST warns that normal-approximation intervals can be inaccurate with small samples or few failures and gives exact binomial intervals. Such intervals require a suitable binomial sampling model; correlated crops are not automatically independent trials. [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

## Proposed G2 choices to freeze before another run

1. **Record prior exposure.** All cases whose outputs influenced earlier prompts, guards, normalization, or acceptance decisions remain development/regression evidence. A later random split cannot make them untouched test data. Keep the rejected generic token guard and its false abstentions as historical evidence, not a candidate to tune on the same anchors. This applies the selection-bias guidance above to prompt and rule choices, even without changing model weights.
2. **Freeze group identity before assignment.** One originating document/work group contains its versions, duplicate downloads, pages, crops, and derived renders. Record a broader source/template family when shared provenance or layout creates dependence. Use that broader family as the split unit if claiming generalization to unseen families; otherwise label the narrower claim explicitly. Group definitions and document hashes belong in the manifest. This is the project's application of grouped splitting, not a prescribed scikit-learn taxonomy.
3. **Separate development, validation, and untouched holdout roles.** Assign whole groups once; persist the assignment, inclusion/exclusion rules, and any seed. Select prompts/rules on development or validation only. If no unexposed groups exist, report that limitation and obtain fresh groups before claiming held-out generalization. Do not reshuffle to obtain a better score. Nested grouped evaluation is a later option if evaluating a search procedure becomes necessary, not required work for this freeze.
4. **Freeze the scorecard and labels.** Define correctness against the source, source-positive and negative-control rubrics, scoring unit, and handling of unknown truth before outputs. Report the same cases for every frozen candidate, with counts and per-group outcomes. Use these explicit denominators:

   | Measure | Frozen definition |
   | --- | --- |
   | Coverage | Accepted outputs / all eligible cases |
   | Selective error | Incorrect accepted outputs / accepted outputs; undefined when none accepted |
   | Positive recovery | Correct accepted outputs on source-positive cases / all source-positive cases |
   | False abstention | Abstained source-positive cases / all source-positive cases |
   | Negative-control failure | Unsupported accepted outputs / all negative-control cases |

   Keep crashes, timeouts, missing outputs, and unavailable sources in named outcome categories; never silently remove them. Freeze whether technical failures count toward a separate availability measure and positive recovery. These additional G2 measures are project choices; coverage and selective error follow the cited selective-prediction definitions.
5. **Freeze interpretation, then stop.** Record candidate/model/prompt/guard versions, parser and normalization settings, annotation rubric, and scorecard revision. Keep known-positive regression protection visible alongside negative-control safety. Do not invent a numeric promotion threshold from four positive anchors. Report exact numerators, denominators, distinct groups, and unsupported strata; any confidence interval must state its sampling assumptions. A holdout result that motivates a change becomes development feedback for the next cycle, which needs a new unexposed holdout.

No corpus sufficiency, independence, runtime behavior, or model quality was established by this source review.
