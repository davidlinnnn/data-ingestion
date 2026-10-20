Table 5 | Distribution of accepted skill updates across evolution iterations, grouped by model (top) and benchmark (bottom). Percentages indicate the proportion of accepted updates that occur during each stage of evolution.

| Category Early (Iter 0–1) Mid (Iter 2–4) Late (Iter 5–7)   |
|------------------------------------------------------------|
| By Model                                                   |
| Qwen-3.5-4B 39% 39% 21%                                    |
| Qwen-3.5-9B 52% 30% 19%                                    |
| Qwen-3.6-27B 43% 40% 17%                                   |
| Gemma-4-31B 52% 37% 11%                                    |
| Gemini-3.5-Flash 50% 46% 4%                                |
| By Benchmark                                               |
| LiveMath 44% 42% 14%                                       |
| SealQA 39% 33% 28%                                         |
| SpreadSheet 41% 48% 11%                                    |
| OfficeQA 58% 26% 16%                                       |
| ALFWorld 55% 34% 10%                                       |

over a large repository of historical Treasury bulletins. Tasks require synthesizing evidence across long contexts and multi-page financial tables. Following the setup in Yang et al. (2026), the agent is provided with pre-parsed oracle reference pages as initial document evidence in the prompt, while retaining access to local text-processing tools (glob , grep , read) to search, cross-reference, and inspect full Treasury bulletin files on disk. ALFWorld (Shridhar et al. , 2021) is an interactive textbased embodied environment where an agent solves multi-step household tasks (e.g., picking and placing objects, heating or cooling items) by outputting text actions to a simulator. Unlike static QA benchmarks, ALFWorld tests sequential decision-making, spatial reasoning, and error recovery from simulator feedback.

Table 6 | Benchmark statistics, data splits, interaction modes, and available environment tools.

|                                  | Benchmark Interaction Train Val Test Environment Tools   |
|----------------------------------|----------------------------------------------------------|
|                                  | LiveMath Single-Step 35 18 124 None (Direct Reasoning)   |
| SealQA Multi-Step 16 10 85       | web_search ,  read_file                                  |
| SpreadSheet Multi-Step 80 40 280 | bash                                                     |
| OfficeQA Multi-Step 50 24 172    | glob ,  grep ,  read                                     |
|                                  | ALFWorld Multi-Step 39 18 134 Admissible Actions         |

Table 6 summarizes the sample counts across training, validation, and test splits, interaction modes, and available tools for each benchmark evaluated in our experiments. All task splits and available toolsets are strictly matched with prior work (Alzubi et al. , 2026; Yang et al. , 2026). For tool setup, LiveMath operates as a single-step reasoning benchmark without external tools, where the model generates final answers directly; SealQA equips the agent with web search (using Google Search API) and file reading for multi-step factual retrieval (we use the July, 2026 version of SealQA for all experiments); SpreadSheet provides a bash shell tool for Python code execution and table manipulation; OfficeQA provides local text-search utilities for multi-step Treasury bulletin navigation; and ALFWorld provides an interactive simulator action space for multi-step embodied decision making.

Evaluation robustness with small validation sets Following established setups in prior work (Alzubi et al. , 2026; Yang et al. , 2026), benchmark validation splits are relatively small, which can introduce evaluation noise into gating decision. To account for this variability, all reported scores represent the average test performance across three independent runs of the entire evolutionary pipeline, with paired bootstrap significance testing (detailed in Appendix C).

## C. Implementation Details

To provide diagnostic feedback for the Wiki maintainer, we apply a stratified sampling strategy (Tsample,𝑘 ⊂ Ttrain,𝑘) at each iteration 𝑘. Specifically, the system samples up to 8 traces per iteration, stratified into a maximum of 5 failing traces (to perform root-cause analysis of errors) and up to 3 passing traces (to identify effective strategies and prevent regressions in working behaviors). Each individual execution log is capped at 15,000 characters prior to injection into the prompt.

Statistical significance testing We perform paired bootstrap significance tests with 1 , 000 iterations for each benchmark. In each bootstrap iteration, task instances are sampled with replacement from the test split Dtest to construct a bootstrap evaluation set of size |Dtest|, from which candidate accuracy scores and pairwise performance margins are computed. To evaluate overall cross-benchmark performance, we conduct stratified macro-average bootstrap resampling: in each iteration, task instances are resampled independently with replacement within each benchmark, and we calculate macro-average accuracy by assigning equal weight to all benchmarks.

We determine top-performing methods in our evaluation tables as follows. Methods are initially ranked by their observed performance (or macro-average performance across benchmarks). A topranked method 𝑀 ∗ is the sole top performer if and only if it achieves a statistically significant gain over all competing methods at 𝑝 &lt; 0 . 05. If 𝑀 ∗ is not statistically distinguishable (𝑝 ≥ 0 . 05) against one or more lower-ranked methods, no single method is declared the sole top performer. Instead, all methods whose performance is not statistically distinguishable from 𝑀 ∗ (𝑝 ≥ 0 . 05) are grouped into a top-tier statistical tie (and bolded accordingly).

## D. Baseline Details and Optimizer API Call Analysis

## D.1. Baseline Methods

Trace2Skill (Ni et al. , 2026) Trace2Skill employs a three-stage pipeline centered on parallel trace analysis and hierarchical merging. It evaluates the current skill on training tasks and dispatches parallel success analysts and error analysts to extract effective strategies from passing tasks and diagnose root causes of failures. The resulting structured patches are recursively consolidated via a hierarchical merge operator into a single patch set. The consolidated patches are applied to the skill document and accepted based on validation performance.

EvoSkill (Alzubi et al. , 2026) EvoSkill frames skill evolution as a search over a frontier of candidate programs. In each iteration, it samples training tasks via a round-robin category schedule and executes rollouts. EvoSkill feeds only failure traces to the proposer alongside a flat feedback history of past proposal outcomes. The proposer generates candidate skill modifications that are materialized into SKILL.md files, scored on a validation split, and added to a bounded frontier of top-performing programs.

SkillOpt (Yang et al. , 2026) SkillOpt implements a six-stage ReflACT pipeline (Rollout, Reflect, Aggregate, Select, Update, Evaluate) for iterative skill optimization. In each epoch, the system rolls out the agent on training tasks and reflects on full execution traces, including both successes and failures, to generate candidate patches. These patches are hierarchically aggregated and selected to update a single monolithic skill document, which is accepted or rejected based on validation performance.

## D.2. Optimizer API Call Complexity

In this section, we analyze optimizer API call complexity, denoted by C, across self-improving agent frameworks. We define one evolution iteration as rolling out the agent on the full training split Dtrain once (𝑁train = |Dtrain| training task instances), processed in minibatches of size 𝐵 (𝐵 ≤ 𝑁train). Table 7 summarizes the per-iteration optimizer API call complexity for WikiSkill and prior methods.

Table 7 | Comparison of optimizer API call complexity per evolution iteration across selfimproving agent frameworks. 𝑁train = |Dtrain| denotes the number of training tasks, 𝐵 denotes the batch size, 𝑇ReAct denotes the number of interactive ReAct reasoning turns used by the Skill Proposer agent in WikiSkill, 𝐾opt denotes the number of reflection and merging calls per step in SkillOpt, and 𝑐 denotes the reduction-tree branching factor in Trace2Skill. WikiSkill uses 𝐵 = 𝑁train across all datasets. In full-batch mode, WikiSkill's optimizer call count is independent of training set size 𝑁train, requiring 1 + 𝑇ReAct optimizer calls per iteration.

|             | Framework Per-Iteration Formula Complexity   |                             |
|-------------|----------------------------------------------|-----------------------------|
| Trace2Skill | 𝑁t 𝑁train +                                 | O                          |
|             |  1 + 1 𝑐 − 1  𝑁train 𝐵 + 1  2𝑁train 𝐵       |  𝑁train + 𝑁train 𝐵  𝑁train |
| EvoSkill    |                                              | O  𝐵                      |
| SkillOpt    | 𝐾o 𝐾opt · 𝑁train 𝐵                           | O  𝑁train 𝐵               |
| WikiSkill   | (1 + 𝑇ReAct) 𝑁train 𝐵                        | O  𝑁train 𝐵               |

WikiSkill For each batch of size 𝐵, the Wiki Maintainer requires one LLM call to analyze sampled traces Tsample,𝑘 and consolidate pattern pages into the intermediate wiki 𝑊  
𝑘 ′ 𝑊  
𝑘 . The Skill Proposer then runs as an autonomous multi-turn ReAct agent, executing interactive tool calls over 𝑇ReAct reasoning turns (roughly 10 ≤ 𝑇ReAct ≤ 20 across our experiment runs), where each ReAct turn requires 1 LLM call. When processing training data in batches of size 𝐵, completing one full iteration over 𝑁train tasks requires 𝑁train 𝐵 steps:

<!-- formula-not-decoded -->

In our experiments, we set the batch size to the full training size (𝐵 = 𝑁train) across all datasets. In this full-batch setting ( 𝑁train 𝐵 = 1), CWikiSkill = 1 + 𝑇ReAct. Because 𝑇ReAct does not depend on 𝑁train , WikiSkill's optimizer API call complexity is O (1) with respect to training set size. Specifically, each iteration requires 1 + 𝑇ReAct optimizer LLM calls, regardless of the number of training instances. While this constant call complexity may incur higher inference cost on some datasets, the additional computation is accompanied by consistent performance gains over prior skill-evolution methods across our evaluation.

EvoSkill EvoSkill partitions training tasks into minibatches of size 𝐵. For each minibatch, EvoSkill uses one Proposer LLM call for error diagnosis and one Generator LLM call for skill updates. Processing