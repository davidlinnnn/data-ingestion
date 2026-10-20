| Knowledge type  n              | Reward   |
|--------------------------------|----------|
| domain procedure 58 69.2       |          |
| library api usage 33 79.2      |          |
| mathematical method 28 80.7    |          |
| tool workflow 19 68.4          |          |
| file format knowledge 17 82.4  |          |
| debugging heuristic 8 70.0     |          |
| data cleaning procedure 7 85.7 |          |
| evaluation protocol 3 66.7     |          |

Table 12: Per-label average evolved reward (%). Left: knowledge-type labels. Right: task-type labels. Counts are over tasks bearing each label (multi-label).

| Task type  n           | Reward   |
|------------------------|----------|
| analysis 24 69.0       |          |
| calculation 20 72.8    |          |
| transformation 18 88.9 |          |
| detection 15 80.0      |          |
| implementation 15 80.0 |          |
| optimization 12 80.0   |          |
| extraction 11 63.6     |          |
| repair 8 45.0          |          |
| planning 8 57.5        |          |
| simulation 7 71.4      |          |
| debugging 6 76.7       |          |
| classification 6 83.3  |          |
| generation 5 100.0     |          |
| verification 5 80.0    |          |
| search 4 25.0          |          |
| formatting 3 100.0     |          |
| ranking 1 0.0          |          |

curated-skill baseline of 40 . 3%, with six tasks flipping from 0 to 1. Second, Repairmode tasks account for most reversals in which the evolved skill falls below the stronger baseline, including crystallographic-wyckoff (evolved 0 . 55 vs. curated 1) and latex-formula-extraction (evolved 0 vs. no-skill 1). Third, Finance &amp; Economics contains the highest concentration of zero-reward tasks across all three conditions, consistent with the tied domain result in Table 1.

Table 13: Per-task rewards for all 89 tasks. No skill / Curated skill / Evolved are the rewards of the corresponding condition; dashes mark missing runs, counted as 0 in all averages. Non-integer rewards are shown to two decimal places.

| Task                | Dom.   | Mode   |   No skill |   Curated skill |   Evolved |
|---------------------|--------|--------|------------|-----------------|-----------|
| MOCK transport only | MOCK   | MOCK   |          0 |               0 |         0 |

Continued on next page

Table 13 (continued)

| Task                | Dom.   | Mode   |   No skill |   Curated skill |   Evolved |
|---------------------|--------|--------|------------|-----------------|-----------|
| MOCK transport only | MOCK   | MOCK   |          0 |               0 |         0 |

Continued on next page

Table 13 (continued)

| Task                | Dom.   | Mode   |   No skill |   Curated skill |   Evolved |
|---------------------|--------|--------|------------|-----------------|-----------|
| MOCK transport only | MOCK   | MOCK   |          0 |               0 |         0 |