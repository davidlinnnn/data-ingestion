# 按 family 的結構證據

E0 all36/715; E1 only actually processed pre-registered items. Formula source units are frozen outer blocks, not independent equations.

Matched/source-known ratios are conditional locator/role evidence, not visually verified precision. UNKNOWN is not a miss or a pass. Tables are adjudicated individually.

F／C／A 欄為 eligible role 候選匹配數／已知來源頁單位（括號為全部來源單位）；不是人工驗證的 precision。E1 欄為真正處理、已知來源頁單位的 RAW exact／near／error，MAPPED 另列於 JSON；非 Q31／Q33 裁決。圖片欄是 main-figure caption-link 候選。

|family（篇／頁）|F 候選／已知（來源）|C 候選／已知（來源）|A 候選／已知（來源）|E1 F exact／near／error|E1 C exact／near／error|表已證偵測／IN|表 FAIL／UNKNOWN／OOS（兩出口）|主圖link候選／IN；未知|
|---|---|---|---|---|---|---|---|---|
|ACL/EMNLP（5/86）|29/29（45）|17/20（20）|0/0（10）|0/1/0|0/0/0|28/29|4/27/1|22/32；3|
|IEEE conference（2/10）|0/0（4）|0/0（0）|0/0（0）|0/0/0|0/0/0|5/5|0/5/0|5/5；1|
|ACM sigconf（2/20）|25/27（29）|0/0（0）|0/0（0）|1/14/10|0/0/0|10/10|0/10/0|9/10；3|
|CVPR/AAAI（2/22）|4/4（5）|0/0（0）|0/0（0）|0/2/2|0/0/0|11/14|0/17/0|10/12；3|
|ICML（3/39）|9/9（17）|0/0（0）|0/0（1）|0/1/3|0/0/0|7/14|0/24/0|12/13；2|
|NeurIPS/ICLR（9/238）|35/35（48）|19/26（29）|0/1（6）|0/8/2|1/2/0|24/33|1/65/0|27/32；7|
|Springer LNCS（2/20）|1/1（3）|0/0（0）|0/0（0）|0/1/0|0/0/0|6/6|0/13/2|8/8；0|
|general arXiv（2/24）|33/35（152）|3/3（3）|0/0（0）|0/9/0|3/0/0|0/0|0/5/0|0/0；4|
|Pilot-other/unknown（6/167）|43/45（70）|6/11（11）|0/0（2）|1/2/0|0/4/2|37/49|0/57/0|31/38；6|
|general arXiv (article; template uncertain)（3/89）|8/9（14）|9/10（15）|0/1（2）|0/0/0|0/3/6|10/15|0/21/0|20/45；10|

完整 RAW／MAPPED、subfigure、raster bbox 及表格分母資料見 family-summary.json；人工阻擋清單與最終抽查另見主報告及 formula-code/report.md。所有零分母欄不作準度結論。

## 已確認阻擋（RAW／MAPPED同數）

E1公式為最終50個near/error block中的Q31；code為literal／log Q4，algorithm為靜態Q33，沒有執行runtime。E0表格及圖片另列，不與E1相加成Profile錯誤率。P13p8表／圖同一根因不重複當全域事件。零件數不是全篇驗收通過。

|family|E1公式／已審block|E1 code Q4|E1 algorithm Q33|E0表Q13|E0圖Q4|
|---|---|---|---|---|---|
|ACL/EMNLP|0/1|0|0|4|1|
|IEEE conference|0/0|0|0|0|0|
|ACM sigconf|6/22|0|0|0|0|
|CVPR/AAAI|1/4|0|0|0|0|
|ICML|4/4|0|0|0|1|
|NeurIPS/ICLR|4/10|2|0|1|0|
|Springer LNCS|0/1|0|0|0|0|
|general arXiv|0/7|0|0|0|0|
|Pilot-other/unknown|0/1|3|0|0|0|
|general arXiv (article; template uncertain)|0/0|1|1|0|0|
