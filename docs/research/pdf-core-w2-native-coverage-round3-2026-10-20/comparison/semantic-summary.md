# 官方選項的語意修好／新壞

單位是經頁圖確認的來源事件，不是自動告警。V1 的完整輸出差異都經核對；V2 的 330 個凍結指標差異全部按來源 identity 覆蓋，另逐一回查 26 個已知 baseline 來源事件。沒有把刪掉 metadata 告警當成語意修復。

| 變體 | 完整修好 | 新增阻擋 | 原事件部分改善但未修好 |
| --- | --- | --- | --- |
| V1 separators=False | 1 | 3 | 0 |
| V2 Egret medium | 3 | 13 | 1 |
| V3 bookmark-only | 175 個標題 | 0 個標題 | 不適用 |

V2 的 3 個完整修好含原 24 件的 2 件（Image Transformer p5、P16 p25），以及本輪差異核對新發現的 P03 p5–6。SkillRL p24 的一個 duplicate instance 改善，但 p22–23 的同根因重複仍在，只算部分改善。SICA p13 native 順序改善卻整框被轉 picture 而 Markdown 仍缺，不算整體修好。V3 標題單位不同，不能與正文事件加總。

## 按 family

| 變體 | family | 完整修好 | 新增阻擋 | 部分改善 |
| --- | --- | --- | --- | --- |
| V1 | ACL/EMNLP | 0 | 0 | 0 |
| V1 | ACM sigconf | 0 | 0 | 0 |
| V1 | CVPR/AAAI | 0 | 0 | 0 |
| V1 | ICML | 0 | 1 | 0 |
| V1 | IEEE conference | 0 | 0 | 0 |
| V1 | NeurIPS/ICLR | 1 | 0 | 0 |
| V1 | Pilot-other/unknown | 0 | 2 | 0 |
| V1 | Springer LNCS | 0 | 0 | 0 |
| V1 | general arXiv | 0 | 0 | 0 |
| V1 | general arXiv (article; template uncertain) | 0 | 0 | 0 |
| V2 | ACL/EMNLP | 0 | 0 | 0 |
| V2 | ACM sigconf | 0 | 1 | 0 |
| V2 | CVPR/AAAI | 0 | 1 | 0 |
| V2 | ICML | 1 | 1 | 0 |
| V2 | IEEE conference | 0 | 0 | 0 |
| V2 | NeurIPS/ICLR | 1 | 4 | 1 |
| V2 | Pilot-other/unknown | 1 | 5 | 0 |
| V2 | Springer LNCS | 0 | 0 | 0 |
| V2 | general arXiv | 0 | 0 | 0 |
| V2 | general arXiv (article; template uncertain) | 0 | 1 | 0 |

## 按失敗類型

| 變體 | 類型 | 完整修好 | 新增阻擋 | 部分改善 |
| --- | --- | --- | --- | --- |
| V1 | caption_splice | 0 | 0 | 0 |
| V1 | duplication | 0 | 0 | 0 |
| V1 | formula_mapping_omission | 0 | 0 | 0 |
| V1 | furniture | 0 | 0 | 0 |
| V1 | picture_delivery_omission | 0 | 0 | 0 |
| V1 | reading_order | 1 | 3 | 0 |
| V2 | caption_splice | 2 | 7 | 0 |
| V2 | duplication | 0 | 0 | 1 |
| V2 | formula_mapping_omission | 1 | 0 | 0 |
| V2 | furniture | 0 | 1 | 0 |
| V2 | picture_delivery_omission | 0 | 3 | 0 |
| V2 | reading_order | 0 | 2 | 0 |

## 逐來源事件與頁碼

| 變體 | 判定 | family | 類型 | 論文 | 頁 | 來源事件 |
| --- | --- | --- | --- | --- | --- | --- |
| V1 | FIXED | NeurIPS/ICLR | reading_order | P-02-2603.02766v1 | 1 | p02-first-author-attribution-order |
| V1 | NEW_BAD | ICML | reading_order | P-18-2511.16043v1 | 18 | v1-p18-table17-conditions-separated |
| V1 | NEW_BAD | Pilot-other/unknown | reading_order | P-10-2509.25140v2 | 23 | v1-p10-prompt-order-p23 |
| V1 | NEW_BAD | Pilot-other/unknown | reading_order | P-10-2509.25140v2 | 24,25 | v1-p10-datasets-prompt-interruption-p24-p25 |
| V2 | FIXED | ICML | caption_splice | F-icml_imagetransformer | 5 | imagetransformer-figure2-breaks-body-sentence |
| V2 | FIXED | NeurIPS/ICLR | formula_mapping_omission | P-16-2505.22954v1 | 25 | p16-task-ids-formula-role-p25 |
| V2 | FIXED | Pilot-other/unknown | caption_splice | P-03-2603.25158v5 | 5,6 | incidental-p03-table3-breaks-reporting-clause-p5-p6 |
| V2 | NEW_BAD | NeurIPS/ICLR | picture_delivery_omission | P-07-2504.15228v2 | 14 | sica-p14-overseer-export-suppression |
| V2 | NEW_BAD | NeurIPS/ICLR | reading_order | F-iclr_adam | 9 | v2-adam-algorithm2-split-update |
| V2 | NEW_BAD | Pilot-other/unknown | caption_splice | P-19-2511.10395v1 | 4,5 | v2-agentevolver-figure3-breaks-constructing |
| V2 | NEW_BAD | Pilot-other/unknown | caption_splice | P-19-2511.10395v1 | 8,9 | v2-agentevolver-figure6-breaks-components |
| V2 | NEW_BAD | ACM sigconf | caption_splice | F-acm_ngcf | 1,2 | v2-ngcf-figure1-breaks-result-clause |
| V2 | NEW_BAD | Pilot-other/unknown | picture_delivery_omission | P-03-2603.25158v5 | 23 | v2-p03-analyst-example-picture-delivery-p23 |
| V2 | NEW_BAD | NeurIPS/ICLR | reading_order | P-16-2505.22954v1 | 24 | v2-p16-polyglot-constraint-tail-order-p24 |
| V2 | NEW_BAD | NeurIPS/ICLR | picture_delivery_omission | P-16-2505.22954v1 | 23,24 | v2-p16-self-improve-prompt-picture-delivery-p23-p24 |
| V2 | NEW_BAD | ICML | caption_splice | P-18-2511.16043v1 | 7 | v2-p18-table5-breaks-effectiveness-clause-p7 |
| V2 | NEW_BAD | CVPR/AAAI | caption_splice | F-cvpr_resnet | 11 | v2-resnet-table12-breaks-bydoingso |
| V2 | NEW_BAD | general arXiv (article; template uncertain) | furniture | P-04-2605.23904v2 | 7 | v2-skillopt-page7-footer |
| V2 | NEW_BAD | Pilot-other/unknown | caption_splice | P-15-2610.05923v1 | 3,4 | v2-vera-figure3-breaks-verifiers-clause |
| V2 | NEW_BAD | Pilot-other/unknown | caption_splice | P-01-2608.27454v1 | 11,12 | v2-wikiskill-figure3-breaks-pattern-count |
| V2 | PARTIAL | NeurIPS/ICLR | duplication | P-05-2602.08234v2 | 22,23,24 | skillrl-colspan-markdown-duplicates |

頁圖、完整前後片段與逐 identity 理由：`V2-semantic-all-records.json`、`V2-semantic-all-groups.json`、`V2-all-baseline-group-checks.json`。V1 詳見 [V1-supplementary-heading-review.md](V1-supplementary-heading-review.md) 與 [V1-supplementary-trace-review.md](V1-supplementary-trace-review.md)。

這不是 V2 全文逐字驗收，凍結 oracle 對作者、表格、短句、數學與部分框內內容仍有盲點。未把未被自動抓到當成沒有錯誤。建議維持 Heron＋separators=True，採 B-only heading；本輪不做 per-document 例外或額外數值調整。
