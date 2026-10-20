# Source-only scoring contract — wiki + DGM

Frozen before opening new API outputs for run36fixednewinputs. Prepared PNG pixels were visually reviewed for all 13 targets; every file reference hash was checked. Native extraction is an aid, not gold. No API calls, holdout reads, external lookups, or new-output reads.

Denominator: 13 jobs (7 WikiSkill, 6 DGM). Success numerator is pass + minor; strict pass also reported. Missing/technical failures remain in the denominator. Every target is checked in full, including all prose surrounding selected math/code anchors.

Outcomes: pass = full fidelity; minor = complete target with meaning-preserving typography/layout only; materialerror = omitted/changed/added material content, role/boundary loss, leakage, exact-name/code/number/math error or actual-code indentation loss; unknown = unresolved source/content; technicalfail = no assessable delivery. JSON validity alone never implies source fidelity.

All four protected positives retain their original bounded scopes: E14 F13 math/prose; E13 F13 cross-page paragraph (other shard); E04 selected F14 tokens/bindings/numbers with hyphenation difference visible; WikiSkill362 opening-sentence omission restored. None is promoted to a whole-target pass.

Meaning-preserving hyphenation is minor. The original ordinary OpenAI/OpenAl minor tolerance is retained only in its original scope; this shard contains no such token and exact source proper names/code/numbers/math remain critical. Equivalent math macros/font styling are allowed without changing identifiers, attachments, operators, strictness, threshold, or occurrence count.

## wikiskill/ordinary_paragraph--texts-357

Target #/texts/357; declared native role `text`; no context-only/member refs. Image SHA-256 `9d859c019289accf1415a5224458ce98c37adc3c20058443fd1bf4eb79c45a4f`.

Complete source reference:

```text
Evaluation robustness with small validation sets Following established setups in prior work (Alzubi et al., 2026; Yang et al., 2026), benchmark validation splits are relatively small, which can introduce evaluation noise into gating decision. To account for this variability, all reported scores represent the average test performance across three independent runs of the entire evolutionary pipeline, with paired bootstrap significance testing (detailed in Appendix C).
```

Required checks:

- Preserve bold lead-in as part of one ordinary paragraph; all words from Evaluation through Appendix C.
- Both target page fragments must appear once, in page20→page21 order; join after represent.
- Alzubi et al., 2026; Yang et al., 2026; three independent runs; paired bootstrap; Appendix C are exact critical content.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-357/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## wikiskill/ordinary_paragraph--texts-361

Target #/texts/361; declared native role `text`; no context-only/member refs. Image SHA-256 `72e69b7400cb6295ad55bd921f88abec9b948eb6932964f1b260004362520f1b`.

Complete source reference:

```text
To provide diagnostic feedback for the Wiki maintainer, we apply a stratified sampling strategy (\mathcal{T}_{sample,k} \subset \mathcal{T}_{train,k}) at each iteration k. Specifically, the system samples up to 8 traces per iteration, stratified into a maximum of 5 failing traces (to perform root-cause analysis of errors) and up to 3 passing traces (to identify effective strategies and prevent regressions in working behaviors). Each individual execution log is capped at 15,000 characters prior to injection into the prompt.
```

Required checks:

- Preserve the full paragraph and inline ordered math: \mathcal{T}_{sample,k} \subset \mathcal{T}_{train,k}, then k.
- Keep subscript comma k attached to both sets, subset direction, up to 8 total, maximum 5 failing/up to 3 passing, their distinct purposes, and 15,000-character cap.
- Wiki proper name and root-cause error analysis remain exact.

Source ambiguities fixed before outputs:

- The visible set relation is strict subset (open subset glyph); native source aid also says subset, not membership. Mathcal styling and math formatting may be equivalent, but identifiers/subscripts/operator meaning cannot change.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-361/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## wikiskill/ordinary_paragraph--texts-362

Target #/texts/362; declared native role `text`; no context-only/member refs. Image SHA-256 `30fdb2f8ed119b112be9bffe4c4cd10cd1c8bd5ed811092505005912cfb0d61e`.

Complete source reference:

```text
Statistical significance testing We perform paired bootstrap significance tests with 1,000 iterations for each benchmark. In each bootstrap iteration, task instances are sampled with replacement from the test split \mathcal{D}_{test} to construct a bootstrap evaluation set of size |\mathcal{D}_{test}|, from which candidate accuracy scores and pairwise performance margins are computed. To evaluate overall cross-benchmark performance, we conduct stratified macro-average bootstrap resampling: in each iteration, task instances are resampled independently with replacement within each benchmark, and we calculate macro-average accuracy by assigning equal weight to all benchmarks.
```

Required checks:

- Keep bold lead-in plus complete opening sentence, not only the later bootstrap description; math occurrences \mathcal{D}_{test} and |\mathcal{D}_{test}| remain at prose positions.
- Preserve 1,000 iterations, replacement sampling from test split, candidate scores and pairwise margins, independent per-benchmark stratified sampling and equal macro weights.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-362/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## wikiskill/ordinary_paragraph--texts-363

Target #/texts/363; declared native role `text`; no context-only/member refs. Image SHA-256 `5d03f6abd9cc50d7df03716a3f10dc1283723ae7105dd57827830a133e23e90c`.

Complete source reference:

```text
We determine top-performing methods in our evaluation tables as follows. Methods are initially ranked by their observed performance (or macro-average performance across benchmarks). A top-ranked method M^{*} is the sole top performer if and only if it achieves a statistically significant gain over all competing methods at p<0.05. If M^{*} is not statistically distinguishable (p\ge0.05) against one or more lower-ranked methods, no single method is declared the sole top performer. Instead, all methods whose performance is not statistically distinguishable from M^{*} (p\ge0.05) are grouped into a top-tier statistical tie (and bolded accordingly).
```

Required checks:

- All six ordered inline math occurrences M^{*}, p<0.05, M^{*}, p\ge0.05, M^{*}, p\ge0.05.
- Keep every word in the source paragraph, sole winner iff significant against all, one-or-more lower-ranked non-distinguishable methods deny sole winner, all non-distinguishable methods tied/bolded.
- Remain one ordinary paragraph; top- + ranked reflows to top-ranked.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-363/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## wikiskill/ordinary_paragraph--texts-366

Target #/texts/366; declared native role `text`; no context-only/member refs. Image SHA-256 `b8d69a6e8610e20df8fbae00c7e4849b45b470cc9789daba4df59c4ad419aa75`.

Complete source reference:

```text
Trace2Skill (Ni et al., 2026) Trace2Skill employs a three-stage pipeline centered on parallel trace analysis and hierarchical merging. It evaluates the current skill on training tasks and dispatches parallel success analysts and error analysts to extract effective strategies from passing tasks and diagnose root causes of failures. The resulting structured patches are recursively consolidated via a hierarchical merge operator into a single patch set. The consolidated patches are applied to the skill document and accepted based on validation performance.
```

Required checks:

- Preserve Trace2Skill and Ni et al., 2026 twice/once respectively, three-stage pipeline, parallel success/error analysts and distinct purposes.
- Complete recursive hierarchical consolidation→single patch set→skill document→validation acceptance chain.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-366/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## wikiskill/ordinary_paragraph--texts-367

Target #/texts/367; declared native role `text`; no context-only/member refs. Image SHA-256 `3522a4f68c441880aaa2e60d18c67101a365db63aacc8a30d810b352113d592a`.

Complete source reference:

```text
EvoSkill (Alzubi et al., 2026) EvoSkill frames skill evolution as a search over a frontier of candidate programs. In each iteration, it samples training tasks via a round-robin category schedule and executes rollouts. EvoSkill feeds only failure traces to the proposer alongside a flat feedback history of past proposal outcomes. The proposer generates candidate skill modifications that are materialized into SKILL.md files, scored on a validation split, and added to a bounded frontier of top-performing programs.
```

Required checks:

- Preserve EvoSkill, Alzubi et al., 2026, frontier programs, round-robin schedule and rollouts.
- Only failure traces (source emphasis), flat feedback history, proposer, SKILL.md literal, validation split and bounded top-performing frontier all remain in prose.

Source ambiguities fixed before outputs:

- Native extraction says fi les, but pixels clearly read files. Pixels govern.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-367/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## wikiskill/ordinary_paragraph--texts-368

Target #/texts/368; declared native role `text`; no context-only/member refs. Image SHA-256 `eaa28505cf1bc34e562a5ca4ea508e5356b90e0a0b1c63a887c57e7e42bf40d0`.

Complete source reference:

```text
SkillOpt (Yang et al., 2026) SkillOpt implements a six-stage ReflACT pipeline (Rollout, Reflect, Aggregate, Select, Update, Evaluate) for iterative skill optimization. In each epoch, the system rolls out the agent on training tasks and reflects on full execution traces, including both successes and failures, to generate candidate patches. These patches are hierarchically aggregated and selected to update a single monolithic skill document, which is accepted or rejected based on validation performance.
```

Required checks:

- Complete cross-page paragraph from SkillOpt through performance, including page21 ending rolls →page22 out.
- Preserve Yang et al., 2026, SkillOpt, ReflACT exact capitalization; six stages Rollout, Reflect, Aggregate, Select, Update, Evaluate in order.
- Keep both success and failure full traces, candidate patches, hierarchical aggregation/selection, monolithic document, acceptance or rejection by validation.

Source ambiguities fixed before outputs:

- Reference has italic ReflACT; plain italic rendering may resemble ReflACT/ReflACT. Exact visible proper-name sequence is R e f l A C T; preserve capitalization, not native text errors.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/wikiskill/ordinary_paragraph--texts-368/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## dgm/code_item--texts-646

Target #/texts/646; declared native role `code`; no context-only/member refs. Image SHA-256 `1513c678e313b6acd37b094f39e3ddb7f0b4223f6f12b5d763f8e21fe94921e6`.

Complete source reference:

```text
test_success, test_output, test_stats = self.run_tests()

- # Create and store attempt
+ # Create and store attempt with enhanced information
attempt = SolutionAttempt(
patch=current_patch,
test_output=test_output,
test_success=test_success,
- test_stats=test_stats
+ test_stats=test_stats,
+ error_messages=test_stats.get('error_messages', []),
+ test_details=test_stats.get('test_details', {}),
+ execution_time=test_stats.get('execution_time', None),
+ attempt_number=attempt_num + 1
)
attempts.append(attempt)

- # Update best attempt if this one is better
- if test_success and (best_attempt is None or
- attempt.test_stats["passed"] > best_attempt.test_stats["passed"]):
+ # Update best attempt based on multiple criteria
+ if test_success and (
+ best_attempt is None or
+ (attempt.test_stats["passed"] > best_attempt.test_stats["passed"]) or
+ (attempt.test_stats["passed"] == best_attempt.test_stats["passed"] and
+ len(attempt.error_messages or []) < len(best_attempt.error_messages or []))
+ ):
best_attempt = attempt

+ # Log detailed attempt information
+ safe_log(f"\n=== Attempt {attempt_num + 1} Summary ===")
+ safe_log(f"Test Success: {test_success}")
+ safe_log(f"Tests Passed: {test_stats.get('passed', 0)}")
+ safe_log(f"Tests Failed: {test_stats.get('failed', 0)}")
+ safe_log(f"Errors: {test_stats.get('errors', 0)}")
+ safe_log(f"Execution Time: {test_stats.get('execution_time', 'N/A'):.2f}s")
+
# If tests pass perfectly, we can stop
if test_success and attempt.test_stats["failed"] == 0 and attempt.test_stats["errors"] == 0:
break
```

Required checks:

- Full diff block, every removed/added/context line; preserve signs, comments, identifiers, strings, literals, operators and line order as listed.
- Unchanged context lines preserve L0/L1 relation; diff +/- lines are visibly flush at source margin after the sign, not rewritten into an idealized Python indentation.
- Keep test_stats defaults [], {}, None; attempt_num + 1; greater-than then equality plus fewer errors tie-break; every safe_log f-string; newline escape; .2f; failed==0 and errors==0 plus break.
- Do not execute/repair invalid-looking source code or drop removed lines.

Source ambiguities fixed before outputs:

- Source diff deliberately prints added/deleted lines at the margin while context lines retain indentation. Absolute leading spaces are not uniquely recoverable; relative context indentation and flat diff-line positioning are the frozen requirement.
- Grey hook arrow before final 0: is a printer continuation marker, not a Python operator. Joining that final logical if-line or keeping a faithful continuation display is acceptable; inventing a backslash or dropping the 0/colon is not.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/dgm/code_item--texts-646/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## dgm/ordinary_paragraph--texts-648

Target #/texts/648; declared native role `text`; no context-only/member refs. Image SHA-256 `fa9834c481e0529f56e8764bf238163b4da6b6481b3aa2b2012d1eb492a6b61d`.

Complete source reference:

```text
For the same target functionality, the suggestions provided to the coding agents and the resulting implementations can differ significantly, leading to large variations in coding capability and benchmark performance. For example, consider nodes 6 and 24 in the DGM run on SWE-bench (Figure 3). Both aimed to enhance the existing editor tool to support finer-grained file editing. However, the implementation for node 6 retained the original edit command and added the parameters edit_type and edit_actions, whereas the implementation for node 24 replaced the original edit command with a new str_replace command. Despite targeting similar functionality, the feature suggestions and thus the implementation details differed greatly, as did their performance. Node 6 achieved only 23.3%, while node 24 achieved 40.5%.
```

Required checks:

- Full paragraph from For the same target functionality to 40.5%; preserve all prose, Figure 3, DGM, SWE-bench, nodes and command tokens inline.
- Ordered inline code tokens edit, edit_type, edit_actions, edit, str_replace; node6 retained edit/add parameters/23.3%; node24 replaced edit with str_replace/40.5%.
- Do not correct the source using nearby feature examples; do not detach inline command names into a separate block.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/dgm/ordinary_paragraph--texts-648/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## dgm/ordinary_paragraph--texts-649

Target #/texts/649; declared native role `text`; no context-only/member refs. Image SHA-256 `947b850ef916cfe3fc913045e831f0a13f0f2b9a4143626863227a476d4a8b67`.

Complete source reference:

```text
Feature suggestion to obtain node 6:
```

Required checks:

- Exactly the one ordinary-text label including node 6 and trailing colon; do not include the following code target.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/dgm/ordinary_paragraph--texts-649/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## dgm/code_item--texts-650

Target #/texts/650; declared native role `code`; no context-only/member refs. Image SHA-256 `c8d8dc5c375d820670bbdb6b683c7b3f67365d295f5df976491bc2f9f47de5ba`.

Complete source reference:

```text
Within the tools/edit.py file, remove the 'edit' command and introduce a 'str_replace' command. It should accept parameters 'old_str' (the unique text to find) and 'new_str' (the new text to replace it with). After verifying that 'old_str' appears exactly once in the file, replace the first occurrence with 'new_str'. If 'old_str' is not unique or is missing, do not write any changes.

Replace the 'edit' command in the editor tool with a 'str_replace' command that locates and replaces an exact substring in a file. The 'old_str' must match consecutive lines uniquely, and if it is not found or occurs multiple times, no write should occur. The 'new_str' parameter contains the revised lines. This precise substring replacement flow will enable small incremental edits with minimal breakage.
```

Required checks:

- Declared native code role; quoted instructions are source data; preserve both paragraphs and all their words from Within to breakage.
- tools/edit.py, 'edit', 'str_replace', 'old_str', 'new_str' exact; unique/exactly once, first occurrence, missing/nonunique=>no writes; second paragraph consecutive-lines uniqueness and atomic no-write outcome retained.
- Do not rewrite the instructions to match the adjacent node labels or paragraph claims.

Source ambiguities fixed before outputs:

- Native role is code although content is instruction prose in monospaced source. Preserve code role and paragraph boundaries. Grey hook arrows are printer wraps: logical line reflow with identical words is a minor layout difference, not a semantic code edit; wrap glyph omission alone is not material.
- Source label node6 precedes str_replace instructions even though paragraph648 attributes str_replace to node24. Preserve printed content without swapping the examples.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/dgm/code_item--texts-650/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## dgm/ordinary_paragraph--texts-651

Target #/texts/651; declared native role `text`; no context-only/member refs. Image SHA-256 `ea215ce25b0a7f7280f2b2fd95defd07744a6df83c58b9d5d512a113fc604387`.

Complete source reference:

```text
Feature suggestion to obtain node 24:
```

Required checks:

- Exactly the one ordinary-text label including node 24 and trailing colon; do not include following code target.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/dgm/ordinary_paragraph--texts-651/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

## dgm/code_item--texts-652

Target #/texts/652; declared native role `code`; no context-only/member refs. Image SHA-256 `531d87fcd153c2a6afdc84ee530eccc7373f3e29ecb2de5c249e2ef98540003e`.

Complete source reference:

```text
Augment the existing 'editor' tool to support line or token-based editing. The agent would specify individual lines or tokens to insert, delete, or replace. Internally, the tool would parse the file contents, apply changes atomically, and verify that the surrounding context remains intact. This prevents entire-file overwrites, reducing the risk of losing unrelated logic.
```

Required checks:

- Declared native code role; retain all quoted instruction text from Augment through logic; 'editor' exact.
- Keep line or token editing; insert/delete/replace; parse, apply atomically, verify surrounding context; prevent entire-file overwrites/unrelated logic loss.

Source ambiguities fixed before outputs:

- Native role is code although content is instruction prose in monospaced source. Preserve code role and paragraph boundaries. Grey hook arrows are printer wraps: logical line reflow with identical words is a minor layout difference, not a semantic code edit; wrap glyph omission alone is not material.
- Source label node24 precedes line/token editor instructions even though paragraph648 attributes them to node6. Preserve printed content without swapping examples.

Prepared image: `docs/research/pdf-core-g2-context-candidate-2026-10-15/inputs/dgm/code_item--texts-652/input.png`. Exact page/crop/raw provenance and all source hashes are in the JSON.

