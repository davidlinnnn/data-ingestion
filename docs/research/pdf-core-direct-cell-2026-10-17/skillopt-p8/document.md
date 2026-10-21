(a) Training set size

Table 2 Hyperparameter analysis for the text optimizer. Each panel changes one scalar or scheduling factor from the default setting unless noted. Panel (a) fixes the split to 4:1:5 train/selection/test; the 1-example, 20%, 40%, and 80% rows use subsets of the training partition, and the 100% row reuses the completed 4:1:5 split-ratio run. Panel (b) sweeps the reflection mini-batchsize B m ; panel (c) sweeps the rollout batchsize B .

| Setting    |   SearchQA |   Spreadsheet |   LiveMath |
|------------|------------|---------------|------------|
| 1 example  |       81.0 |          47.5 |       59.1 |
| 20% train  |       84.1 |          69.0 |       65.9 |
| 40% train  |       86.1 |          73.5 |       64.8 |
| 80% train  |       86.1 |          77.6 |       67.0 |
| 100% train |       84.1 |          78.0 |       70.5 |

(b) Mini-batchsize

|   Setting |   SearchQA |   Spreadsheet |   LiveMath |
|-----------|------------|---------------|------------|
|         1 |       85.9 |          75.4 |       60.5 |
|         2 |       86.3 |          77.1 |       54.8 |
|         4 |       86.9 |          75.4 |       64.5 |
|         8 |       87.1 |          77.5 |       61.3 |
|        16 |       87.0 |          77.9 |       61.3 |
|        32 |       86.9 |          77.5 |       58.9 |

(c) Batchsize

| Setting    |   SearchQA |   Spreadsheet |   LiveMath |
|------------|------------|---------------|------------|
| 8          |       85.1 |          76.8 |       58.1 |
| 24         |       86.4 |          77.1 |       62.9 |
| 40         |       87.1 |          77.5 |       61.3 |
| 56         |       86.5 |          76.8 |       56.5 |
| full epoch |       87.2 |          75.0 |       53.2 |

(d) Learning rate

| Setting   |   SearchQA |   Spreadsheet |   LiveMath |
|-----------|------------|---------------|------------|
| lr=1      |       85.5 |          77.5 |       62.1 |
| lr=2      |       86.7 |          77.5 |       60.5 |
| lr=4      |       86.5 |          78.2 |       56.5 |
| lr=8      |       87.0 |          73.6 |       66.9 |
| lr=16     |       86.8 |          78.2 |       65.3 |

(e) Learning-rate scheduler

| Setting   |   SearchQA |   Spreadsheet |   LiveMath |
|-----------|------------|---------------|------------|
| constant  |       87.3 |          80.7 |       62.1 |
| cosine    |       87.1 |          77.5 |       61.3 |
| linear    |       87.2 |          72.9 |       62.9 |

(f) Slow-update samples

|   Setting |   SearchQA |   Spreadsheet |   LiveMath |
|-----------|------------|---------------|------------|
|         5 |       86.8 |          76.4 |       64.5 |
|        10 |       86.4 |          74.3 |       65.3 |
|        20 |       87.1 |          77.5 |       61.3 |
|        40 |       86.9 |          75.4 |       54.8 |

Table 3 Component ablations for learning-rate form, rejected buffer, and epoch-wise slow/meta update. Light-blue rows mark the default setting within each component group; the learning-rate group uses the default lr=4 setting. Bold values mark the best measured result within that group and benchmark. The without-rejected-buffer row uses the matched no-buffer ablation setting.

| Component          | Setting                            |   SearchQA |   SpreadsheetBench |   LiveMath |
|--------------------|------------------------------------|------------|--------------------|------------|
| Learning-rate form | lr=4 (default)                     |       87.1 |               77.5 |       61.3 |
| Learning-rate form | dynamic lr                         |       85.8 |               71.8 |       54.0 |
| Learning-rate form | without lr                         |       84.6 |               75.7 |       57.3 |
| Rejected buffer    | with rejected buffer               |       87.1 |               77.5 |       61.3 |
| Rejected buffer    | without rejected buffer            |       85.5 |               72.9 |       58.9 |
| Slow/meta update   | meta skill and slow update         |       87.1 |               77.5 |       61.3 |
| Slow/meta update   | without meta skill                 |       85.1 |               75.7 |       58.1 |
| Slow/meta update   | without meta skill and slow update |       86.3 |               55.0 |       59.7 |

GPT [35] and Qwen [36 , 37]. The benchmark suite is intentionally diverse—it spans single-round QA (SearchQA, DocVQA, LiveMathematicianBench MCQ), multi-turn tool loops with up to 24 tool calls (OfficeQA), multi-round codegen with up to 30 turns and a real openpyxl/pandas runtime (SpreadsheetBench, default mode=multi), and persistent embodied interaction with up to 50 steps per episode (ALFWorld). Dataset-backed runs use deterministic train/selection/test splits derived from the same dataset seed (split \_ seed = 42); the selection split is used only to accept or reject candidate skill edits, and all reported scores are computed on the disjoint held-out test split. The reported numbers thus measure generalization, not validation-set fit.

Default optimizer hyperparameters. Unless noted, SkillOpt uses four epochs, rollout batch size 40 per step, reflection minibatch size 8 (with 16 analyst workers running reflections in parallel and a merge batch size of 8), textual learning rate Lt = 4 with cosine decay (floor Lt = 2, configurable schedules: constant, linear, cosine, autonomous), held-out validation gating (strictly greater than the current selection score—ties are rejected), slow update with 20 sampled tasks per epoch comparing previous-epoch and current-epoch skill, an optimizer-side meta skill that summarizes accepted/rejected patterns into teacher-only guidance, the patch edit mode (the alternative is rewrite\_from\_suggestions), and an optional rejected-edit buffer of recent failed proposals. Teacher reflection is allowed up to three refinement rounds per minibatch. Both teacher and student calls default to a medium reasoning effort. For benchmarks with tightly bounded training pools (LiveMathematicianBench: 35 training items per epoch with rollout batch 200; ALFWorld: 39 training tasks with 140 selection and 134 test environments), per-benchmark configs scale the batch sizes accordingly while keeping the same gate, scheduler, and slow/meta-update machinery. Additional benchmark, baseline, and optimizer-protocol details are in Appendix C .