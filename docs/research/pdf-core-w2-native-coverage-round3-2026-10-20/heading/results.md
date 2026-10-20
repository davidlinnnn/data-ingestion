# 官方 heading 全因子結果

已完成 36 篇；待輸入 0 篇。fixed 為 reference 非正確→正確；new_bad 為 reference 正確→非正確。

| bookmark/number/style | correct | level error | strict missing | role error | ambiguous | baseline fixed / new bad | all-rules fixed / new bad |
|---|---:|---:|---:|---:|---:|---:|---:|
| b0-n0-s0 | 177 | 254 | 33 | 1 | 2 | 0 / 0 | 33 / 232 |
| b0-n0-s1 | 6 | 425 | 33 | 1 | 2 | 5 / 176 | 2 / 372 |
| b0-n1-s0 | 318 | 113 | 33 | 1 | 2 | 181 / 40 | 16 / 74 |
| b0-n1-s1 | 277 | 154 | 33 | 1 | 2 | 181 / 81 | 0 / 99 |
| b1-n0-s0 | 352 | 79 | 33 | 1 | 2 | 175 / 0 | 33 / 57 |
| b1-n0-s1 | 293 | 138 | 33 | 1 | 2 | 177 / 61 | 2 / 85 |
| b1-n1-s0 | 392 | 39 | 33 | 1 | 2 | 232 / 17 | 16 / 0 |
| b1-n1-s1 | 376 | 55 | 33 | 1 | 2 | 232 / 33 | 0 / 0 |

描述性最低退化候選：b1-n0-s0。未採用或部署。

三個主要結構命令 section/subsection/subsubsection 見上表；paragraph/subparagraph run-in 仍在 JSON all_source_command_counts 另列。strict missing 只代表 title 匹配失敗，不等於內容漏失。

## 按家族

### ACL/EMNLP

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 43 |
| b0-n0-s1 | 2 | 30 | 71 |
| b0-n1-s0 | 23 | 2 | 22 |
| b0-n1-s1 | 23 | 19 | 39 |
| b1-n0-s0 | 33 | 0 | 10 |
| b1-n0-s1 | 33 | 10 | 20 |
| b1-n1-s0 | 37 | 2 | 8 |
| b1-n1-s1 | 37 | 6 | 12 |

### IEEE conference

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 9 |
| b0-n0-s1 | 0 | 6 | 15 |
| b0-n1-s0 | 9 | 0 | 0 |
| b0-n1-s1 | 9 | 0 | 0 |
| b1-n0-s0 | 9 | 0 | 0 |
| b1-n0-s1 | 9 | 0 | 0 |
| b1-n1-s0 | 9 | 0 | 0 |
| b1-n1-s1 | 9 | 0 | 0 |

### ACM sigconf

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 17 |
| b0-n0-s1 | 0 | 8 | 25 |
| b0-n1-s0 | 17 | 0 | 0 |
| b0-n1-s1 | 17 | 0 | 0 |
| b1-n0-s0 | 17 | 0 | 0 |
| b1-n0-s1 | 17 | 0 | 0 |
| b1-n1-s0 | 17 | 0 | 0 |
| b1-n1-s1 | 17 | 0 | 0 |

### CVPR/AAAI

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 9 |
| b0-n0-s1 | 0 | 6 | 15 |
| b0-n1-s0 | 9 | 1 | 1 |
| b0-n1-s1 | 9 | 1 | 1 |
| b1-n0-s0 | 0 | 0 | 9 |
| b1-n0-s1 | 0 | 6 | 15 |
| b1-n1-s0 | 9 | 1 | 1 |
| b1-n1-s1 | 9 | 1 | 1 |

### ICML

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 16 |
| b0-n0-s1 | 2 | 21 | 35 |
| b0-n1-s0 | 3 | 13 | 26 |
| b0-n1-s1 | 3 | 15 | 28 |
| b1-n0-s0 | 0 | 0 | 16 |
| b1-n0-s1 | 2 | 21 | 35 |
| b1-n1-s0 | 3 | 13 | 26 |
| b1-n1-s1 | 3 | 15 | 28 |

### NeurIPS/ICLR

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 35 |
| b0-n0-s1 | 1 | 36 | 70 |
| b0-n1-s0 | 20 | 3 | 18 |
| b0-n1-s1 | 20 | 17 | 32 |
| b1-n0-s0 | 35 | 0 | 0 |
| b1-n0-s1 | 35 | 6 | 6 |
| b1-n1-s0 | 35 | 0 | 0 |
| b1-n1-s1 | 35 | 6 | 6 |

### Springer LNCS

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 7 |
| b0-n0-s1 | 0 | 7 | 14 |
| b0-n1-s0 | 7 | 0 | 0 |
| b0-n1-s1 | 7 | 1 | 1 |
| b1-n0-s0 | 0 | 0 | 7 |
| b1-n0-s1 | 0 | 7 | 14 |
| b1-n1-s0 | 7 | 0 | 0 |
| b1-n1-s1 | 7 | 1 | 1 |

### general arXiv

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 6 |
| b0-n0-s1 | 0 | 5 | 11 |
| b0-n1-s0 | 6 | 0 | 0 |
| b0-n1-s1 | 6 | 0 | 0 |
| b1-n0-s0 | 6 | 0 | 0 |
| b1-n0-s1 | 6 | 0 | 0 |
| b1-n1-s0 | 6 | 0 | 0 |
| b1-n1-s1 | 6 | 0 | 0 |

### Pilot-other/unknown

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 79 |
| b0-n0-s1 | 0 | 44 | 123 |
| b0-n1-s0 | 64 | 18 | 33 |
| b0-n1-s1 | 64 | 21 | 36 |
| b1-n0-s0 | 45 | 0 | 34 |
| b1-n0-s1 | 45 | 10 | 44 |
| b1-n1-s0 | 76 | 1 | 4 |
| b1-n1-s1 | 76 | 4 | 7 |

### general arXiv (article; template uncertain)

| rules | baseline fixed | baseline new bad | level errors |
|---|---:|---:|---:|
| b0-n0-s0 | 0 | 0 | 33 |
| b0-n0-s1 | 0 | 13 | 46 |
| b0-n1-s0 | 23 | 3 | 13 |
| b0-n1-s1 | 23 | 7 | 17 |
| b1-n0-s0 | 30 | 0 | 3 |
| b1-n0-s1 | 30 | 1 | 4 |
| b1-n1-s0 | 33 | 0 | 0 |
| b1-n1-s1 | 33 | 0 | 0 |

