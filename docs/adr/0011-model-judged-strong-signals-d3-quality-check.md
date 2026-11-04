# Let a calibrated decision model's judgement be a strong signal: the d3 Quality Check for formulas and tables

The [workflow v2 record](../design/knowledge-platform-processing-workflow-v2.md)
§4 and §7 made `disputed` the result of deterministic strong signals only (a
formula's numbers and operators against the native text layer, a summary
sentence without a supporting section) and fixed that weak signals are recorded
but never change status. This decision adds a third kind of strong signal: a
Quality Check, which judges another Enrichment Method's output after enrichment
with the decision model `vllm-sr/d3-mini` (revision
`bd0090dd758d32ba59ef5c749910a8e87fc4391f`) and contributes contradictions and
signals to that output's Enrichment Status. For formulas and tables, a
calibrated faithfulness probability at or below the category's threshold `t_d`
is a contradiction (`FORMULA_D3_UNFAITHFUL`, `TABLE_D3_UNFAITHFUL`), so the
item becomes `disputed`; the shipped rule checks keep their place and either
kind of contradiction is enough. For picture OCR the probability is a weak
signal only. Captions, descriptions, figure types and chart values get no
check. No check produces `verified`; its opening conditions stay with #83.

The check (#161) runs as its own method, `d3-check`, after enrichment and before
finalize, on its own `d3` task queue against the service the LLM/d3 provider
team runs with vLLM Semantic Router (`POST /v1/systemone`). Its items target the
same document nodes as the methods they judge and take the judged outcome
record as an input, so the reuse key (ADR-0010) reuses a judgement exactly when
the judged output and the check are unchanged. The request (questions, state,
image preparation), the calibration parameters and `t_d` are constants of the
check's package, so a new threshold is a new check version and reruns only the
check and finalize, never the judged method; the status rule's code does not
change, because it already turns any contradiction into `disputed`. Thresholds
hold for one runtime: the pinned revision, BF16 and one request per forward
(batching off). Before the profile goes to PROD, the thresholds are rechecked
on the deployed service as part of #83's retest on the company models. When the
service gives no answer after retries, the check degrades: the judged item
keeps the status its own method gives it, its signals record that the check did
not run, an alert fires, and the existing service-unavailable redrive later
fills in the judgement. Whether a profile runs the check is decided only by
its method list: a profile without `d3-check` needs no d3 service and gives the
result it gives today; there is no runtime switch, so a status always means
the same thing under one profile version.

The evidence is the #153 measurement, registered before the test split was
read ([report](https://github.com/davidlinnnn/data-ingestion/blob/research/153-d3-quality-check/docs/research/d3-quality-check-2026-11-02/report.md)).
On the held-out test, d3-mini ranked wrong formulas below right ones with AUROC
0.932 (95% page-bootstrap interval 0.818-1.000) and, at the threshold chosen on
dev, marked 24 formulas of which 22 were wrong (Wilson interval 0.74-0.98),
catching 22 of 29 errors. Of the 5 errors the shipped formula rule misses on the
#152 subset, it caught 4, and it marked none of the 64 correct formulas there.
Tables: AUROC 0.982, 13 marked, all wrong, 13 of 14 errors caught. Picture OCR
ranked well (AUROC 0.905) but had 13 test items, too few to change status on.
The user ruled each category, the model and the failure mode on 2026-11-04.

The trade-off: a model's judgement is less explainable than a rule and can be
wrong on a correct item. In the worst case the measurement allows, about one
`disputed` formula in four is correct; it is sent for review or redone, and its
content is never removed. Rejected alternatives: keeping the score as a weak
signal only, which leaves every error the rules miss `unverified` and gives
consumers no change; and calling d3 inside each judged method, which would make
every threshold change a new version of that method and rerun its
vision-language model. What consumers do with a `disputed` formula or table,
and a second, more expensive judge for marked items, are not decided here.
