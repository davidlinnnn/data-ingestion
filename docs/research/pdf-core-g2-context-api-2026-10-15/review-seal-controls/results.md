# Independent new-output review: SEAL and controls

**18/23 strict full-target passes, 3 minor role/structure misses, 2 material math errors.** All 23 source targets are gradable and all 23 outputs are usable; no unknowns or context leakage. Complete visible content and mathematical meaning survive on 21/23.

Frozen source contract SHA256: `825be8ee51991187d439ad4c28549746dd6ec7927ea9c8cec347e5aff9c643bb`. Every actual input PNG was inspected before outputs; the parent confirmed the contract was frozen before the first HTTP request. No rubric retune, response patch, model call or holdout read.

| Source | Pass | Minor | Material | Unknown | Technical |
| --- | ---: | ---: | ---: | ---: | ---: |
| SEAL | 10 | 2 | 2 | 0 | 0 |
| Controls | 8 | 1 | 0 | 0 | 0 |

## Concrete misses

- **SEAL32 — material:** source image shows `LM` with subscript theta-prime followed by possessive apostrophe-s. Output math is `\mathrm{LM}_{\theta}`: the prime is absent. Output additionally turns italic prose words `action` and `reward` into math segments. Its prose words are complete, but the model identity changes.
- **SEAL49 — material:** source reward term uses the unsubscripted self-edit name `SE`; output is `r(S_E,\tau,\theta_t)`, changing the argument into S subscript E. The gradient and other theta/N/M terms survive.
- **SEAL28 — minor:** complete paragraph, but the standalone self-edit name `(SE)` stays inside one text segment instead of the frozen required math role.
- **SEAL30 — minor:** both page fragments, all prose and the critical `\theta' \leftarrow \mathrm{SFT}(\theta,\mathrm{SE})` are faithful. Standalone `SE` after “generates a self-edit” is typed text rather than math. The historical bounded F13 positive label is unchanged; this new strict typed-role result is recorded separately.
- **Controls14 — minor:** `Inline code: ` is correctly typed text and `items[i] <= limit` correctly typed code. The output block is `code`, as the native request demands; the visible source is a paragraph with inline code. This source/native structural mismatch was declared before outputs.

## Boundaries, math and code

Controls12 returns exactly the one-line comment and excludes context-only item13. Controls13 excludes context-only comment12 and returns exactly six body lines, with indentation `[0,4,4,8,0,4]`; `else:` aligns with the outer `if`, `emit("ok")` is doubly nested, and operators/quotes are exact. Controls14 preserves its two source segment roles.

All 3 formula controls pass: matrix rows `[1,-2]` and `[3,4]`; fraction denominator is the whole `x+1`; cases are `x^2` when `x>=0`, `0` when `x<0`, with the correct zero boundary. The ordinary control preserves inline `y=x^2+1`; instruction-like source text is transcribed as data.

23/23 comply with the requested native block role; 22/23 match source block roles; 20/23 preserve frozen source typed-segment roles. Of 11 jobs with required math, 9 preserve mathematical meaning. Strict faithful delivery is 18/23, not an anchor-only score.

## Complete per-job assessment

| Source | Target | Status | Full source pass | Complete review |
| --- | --- | --- | --- | --- |
| seal | ordinary_paragraph--texts-21 | pass | yes | All sentences, citations, names and the page-2/page-3 continuation through may also be viable are complete. Source wording question–answer and §C preserved; prose wraps accepted. |
| seal | ordinary_paragraph--texts-23 | pass | yes | Complete Test-Time Training paragraph, all citations and names, gradient-updates, TTT efficiency and final continued-pretraining clause preserved. |
| seal | ordinary_paragraph--texts-24 | pass | yes | Complete paragraph from Reinforcement Learning for LLMs through weight updates; citations and self-edit data clause preserved. |
| seal | ordinary_paragraph--texts-25 | pass | yes | Complete Meta-Learning paragraph, including all seven sentences, citation groups, Schmidhuber/Irie, Hu et al. and parametrize updates. No words missing across wraps. |
| seal | ordinary_paragraph--texts-26 | pass | yes | Complete Self-Improvement paragraph with all citation groups and final external-data sentence. Source compound self- at line end plus training is preserved as self-training under accepted reflow. |
| seal | ordinary_paragraph--texts-28 | minor | no | All complete prose, punctuation/citations (none), outer/inner loops and final meta-learning sentence present. Source self-edit identifier SE survives as visible text, but the frozen required math role is absent. |
| seal | ordinary_paragraph--texts-30 | minor | no | Both source fragments are fully transcribed in order, including questions and associated answers join, few-shot context/query distinction, §3.2, and theta-prime left-arrow SFT(theta,SE). Standalone SE after generates a self-edit is carried in text instead of its frozen math role. |
| seal | ordinary_paragraph--texts-32 | material | no | All prose words survive, but model identity is materially wrong: source LM with theta-prime subscript becomes LM with theta-only subscript. Italic prose action and reward become math segments; source SE is in text. |
| seal | ordinary_paragraph--texts-45 | pass | yes | Exact bounded continuation are sampled from—and, crucially, rewards are computed using—the current model. No reconstruction from surrounding paragraph or formula. |
| seal | ordinary_paragraph--texts-46 | pass | yes | Complete GRPO/PPO and ReST paragraph, all citation numbers/order and rejection sampling + SFT quoted phrase present. ReST superscript EM is correct. |
| seal | ordinary_paragraph--texts-47 | pass | yes | Complete ReST EM procedure paragraph, E-step/M-step clauses and objective (1) under binary reward preserved. Discretionary candi-/date line break accepted. |
| seal | ordinary_paragraph--texts-49 | material | no | All prose and other math survive, including gradient, theta_t occurrences and N/M. Reward argument changes self-edit identifier SE into subscripted S_E, a different mathematical object. |
| seal | ordinary_paragraph--texts-52 | pass | yes | Complete where paragraph, including p_{theta_t}, y_s^(i,j), ordinal superscripts, SE_ij, C_i, r=0, equation references, ReST^EM, stop-gradient clause and Alg.1. LaTeX roman styling differences preserve meaning. |
| seal | ordinary_paragraph--texts-53 | pass | yes | Complete five-sentence teacher-student paragraph, [66], separate teacher and final student-improvement clause preserved. |
| controls | formula_envelope--pictures-0 | pass | yes | Matrix equality preserved as a two-row/two-column bracketed matrix: row1 [1,-2], row2 [3,4]. Negative sign and positions exact. |
| controls | formula_envelope--pictures-1 | pass | yes | g(x) equals one over the entire x+1 denominator. Upright math styling matches source; denominator grouping preserved. |
| controls | formula_envelope--pictures-2 | pass | yes | Two-case left-braced f(x) preserved: x squared when x>=0; zero when x<0. Branch order, exponent and zero boundary correct. |
| controls | ordinary_paragraph--texts-1 | pass | yes | Exact complete toy-source paragraph including warning it does not prove real-document quality. |
| controls | ordinary_paragraph--texts-4 | pass | yes | Exact surrounding prose plus one typed math segment y=x^2+1; exponent and inline sentence punctuation preserved. |
| controls | code_item--texts-12 | pass | yes | Exact one-line comment target only. Context-only six-line body excluded; bbox equals comment target rectangle. |
| controls | code_item--texts-13 | pass | yes | Exact six target body lines, operators, quotes and nesting. Indent spaces [0,4,4,8,0,4]; else aligns with outer if. Context-only comment excluded. |
| controls | code_item--texts-14 | minor | no | Exact complete visible content with text Inline code: followed by code items[i] <= limit. Typed source segment roles are preserved. Native requested code block is returned, so source paragraph/inline-code block structure is still mismatched. |
| controls | ordinary_paragraph--texts-15 | pass | yes | Exact complete printed instruction and [1] citation; source is transcribed as data. |

The four unprepared formulas and mixed paragraph/title item34 remain required source opportunities. They are separately recorded in `unprepared-scope.json`; none is intrinsic source ambiguity. Overall selected logical scope remains **41 = 36 prepared + 5 unprepared**, with formula-envelope members counted once.

Skipped: model reruns, response patches, prompt changes, and holdouts. Risk: native role compliance and valid JSON alone do not establish source faithfulness.
