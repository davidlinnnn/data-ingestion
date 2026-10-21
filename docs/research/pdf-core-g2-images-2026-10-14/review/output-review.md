# Independent image output review

2026-10-14. Offline source-quality review against the frozen G1 oracles. This checks the saved fixed-crop component outputs; it does not establish Docling gate behavior, Canonical mapping or production acceptance.

| Configuration | Case | Bounded source-quality result |
|---|---|---|
| SmolVLM-256M CPU float32, default few-sentence prompt, cap 200 | S05 | Required meaning not delivered |
| Same SmolVLM configuration | S07 | Required meaning not delivered |
| gpt-6-luna direct HTTP, source-grounded relation prompt | S05 | Frozen selected diagram checks satisfied |
| Same API relation prompt | S07 | Frozen selected screenshot checks satisfied |
| gpt-6-luna direct HTTP, structured chart prompt | C03-C06 | All13 fixed observations and critical checks satisfied |

## SmolVLM: content failure and cleanup are separate

S05 says only that the image is a table with text/icons. It misses the three knowledge layers, four ordered steps, every required source relation, conditional update, immutable raw and never-reset wiki. Calling this workflow graphic a table is also incorrect. S07 says only that there is a page and blue boxes; it misses navigation, headings/link association and the selection/direct-link instruction. Neither satisfies required image meaning.

Raw generations ended on EOS token 49279 after 15 and 40 generated tokens, below cap 200. The complete `<end_of_utterance>` exists in decoded-before-engine-cleanup.txt. Engine and description-stage output retain the partial `<end_of_utteranc`. The generic semantic text was already present before cleanup; missing relations cannot be attributed to cap truncation or that partial tag. The partial tag is a separate defect introduced between raw decoding and engine/stage delivery.

## API: real-source meaning

S05 preserves all three layers and paths/roles, all four agents in order and all five frozen relation groups: Step 1->Step 2->Step 3->Step 4->Step 1; skills->Inference and Inference->raw; raw->Maintainer and Maintainer->wiki; all three skill/wiki/raw inputs to Proposer; conditional better-only skill update and wiki-log update by gating. It preserves reversible/conditional skills, never-reset wiki and immutable/permanent/write-once raw. Its generated interpretation is separate from visible_text, and it invents no source caption or unsupported state/action.

S07 identifies the application-selection interface and preserves 首頁>我的專區>應用系統, the two headings, B5A:個人簡要自述, and right-side selection/direct-link entry alternatives. It describes possible UI use and explicitly says the post-click result is not shown. No completed click or later outcome is invented. visible_text and generated interpretation are separate.

## API: four controlled charts

| Case | Fixed observations | Numeric errors | Source meaning and tolerance |
|---|---:|---:|---|
| C03 | 2 | 0 | A 10%, B 20%, exact printed labels; B>A |
| C04 | 6 | 0 | Blue 0/50/100 and Orange 100/50/0 by Step 1/2/3; all estimated; normalized linear-axis error 0; source equality and endpoint comparisons retained |
| C05 | 3 | 0 | Step 1/2/3 ->1/10/100; all estimated; log10 axis and factor 10 interpretation explicit; normalized log-axis error 0 |
| C06 | 2 | 0 | A about 25%, B about 75%, estimated; each 0 percentage-point error; category association and larger-B comparison retained |

C06 places percentage semantics in value strings such as `about 25%` while its separate unit field is null. This preserves source meaning. A later numeric mapper needs to handle this representation; the reviewer did not rewrite provider output. No sector percentage is falsely labeled printed. Clipped-title uncertainties refer to existing input crop edges and do not reclassify a required data region as ambiguous.

The checker uses the fixed 2 + 6 + 3 + 2 = 13 source points and retains each chart's existing rules. Seven in-memory mutation controls are rejected: wrong printed value, Blue/Orange swap, linear midpoint on a log axis, estimated-as-printed, pie A/B swap, unequal 52/48step2 tie within numeric tolerance, and invented log percentage unit. Inclusive 2% linear/log and 2 pp pie boundary examples pass, while just-outside values fail. Numeric checks do not replace manual comparison of tie wording, factor 10 meaning, directions or conditions.

## Evidence and boundary

`output-review.json` records each source check and exact output snapshot. `chart-checks.json` contains per-point values, associations, error/tolerance and control outcomes. `check_chart_outputs.py` is offline and reads provider files without mutation. Native layout crop coverage remains a separate prior review.

Both configurations use the same frozen images, but their prompts and output contracts differ. This is a comparison of the named configurations, not evidence that model identity alone caused the difference. The four charts are original controls, not real-document chart accuracy evidence. No inference was repeated and no whole-pipeline acceptance is claimed.
