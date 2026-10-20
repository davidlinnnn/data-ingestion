# W3b stage2：表格官方 cell-matching 單變量比較

來源已先封存；兩版使用同一份246 semantic-table oracle（267 leaf）。183 IN_SCOPE、3 OUT_OF_SCOPE、60來源定位UNKNOWN；IN_SCOPE共7484 numeric components。Adam來源只PDF wrapper，ANSWER_UNAVAILABLE，沒有被當0表。

E0用36篇已保存輸出；cellFalse為root成功的34篇／84interval／175原PDF頁。RAW以實際保存Markdown、官方table export與 markdown_it commonmark+table 真正render檢查；MAPPED使用原三規則mapper的實際HTML／Markdown／JSON，沒有新增表格重建規則。

| 版本／出口 | PASS | FAIL | UNKNOWN |
|---|---:|---:|---:|
| E0 RAW | 5 | 10 | 168 |
| E0 MAPPED | 5 | 10 | 168 |
| cellFalse RAW | 28 | 8 | 147 |
| cellFalse MAPPED | 30 | 8 | 145 |

這是每張表的Q13判定數量，沒有自創整體通過率。ordinary零錯；complex錯率不超過5%，未裁定或未排除多生不能假作通過。

## 按 family 與複雜度

| Family | E0 RAW P/F/U | cellFalse RAW P/F/U | cellFalse MAPPED P/F/U |
|---|---|---|---|
| ACL/EMNLP | 3/0/11 | 3/1/10 | 3/1/10 |
| ACM sigconf | 0/0/7 | 0/0/7 | 0/0/7 |
| CVPR/AAAI | 1/0/14 | 1/1/13 | 1/1/13 |
| ICML | 0/0/14 | 2/0/12 | 2/0/12 |
| IEEE conference | 0/1/3 | 0/0/4 | 0/0/4 |
| NeurIPS/ICLR | 1/1/2 | 1/0/3 | 1/0/3 |
| Pilot (layout pending) | 0/8/110 | 21/5/92 | 23/5/90 |
| Springer LNCS | 0/0/7 | 0/1/6 | 0/1/6 |

| Q13 | E0 RAW P/F/U | cellFalse RAW P/F/U | cellFalse MAPPED P/F/U |
|---|---|---|---|
| ordinary | 4/5/62 | 19/4/48 | 21/4/46 |
| complex | 1/5/106 | 9/4/99 | 9/4/99 |

## 修好、新壞與 UNKNOWN 遷移

RAW／MAPPED各確認3張 FAIL→PASS：P11 p8 Table2（B1/F1 tuple）；P13 p9 Table4、p26 Table6（TC數值落入MQ欄的 tuple錯配）。0張 PASS→FAIL。這不等於已證全量零退化：8張原 UNKNOWN→FAIL，前版不能判定，列為新確認阻擋／風險，不能計成已證新壞；FAIL→UNKNOWN也不是已證修好。

P13 p9 Table5 的v2「15 extra」是packed header對齊誤報，v4已UNKNOWN；cellFalse PASS屬UNKNOWN→PASS。P19 p25 Table6 的E0兩個值在Baseline label cell，關係未明，v4亦UNKNOWN；cellFalse MAPPED PASS，RAW父header AppWorld/BFCL變表外段落而UNKNOWN。兩案原QA抽樣固定、不拿新案例替換。

RAW另有P06 p7 Table2同類多行header loss，MAPPED保留標籤且PASS。它是輸出結構的可確認差異；人讀可能推斷，未據此自稱Q4語義阻擋。

## 錯率與來源／對齊界線

逐表確證 wrong/missing/extra tuple、可信來源N、來源未知點、target未知點、錯率下界／上界在per-table.csv及results/*-v4.json。未知extra的上界保留unresolved，不硬塞100%；可超100%的extra計數不截斷。來源分母不可信時不報精確比率。精確錯率分布只納入來源分母可信、所有tuple及extra完整可判的表；未確定的表不塞0或1，分family/Q13機器摘要另列。

MISSING tuple不等於數值字詞漏失；source數值在別的明確metric欄仍可形成錯配／多出tuple，machine記numeric_text_present與lexical_omission_claimed。數值只在packed row-label/header時關係不唯一，UNKNOWN，不把整串依gold zip回多欄算正確，也不全算漏。source caption只定位caption頁；來源physical extent或native text證據不全的absent值保留UNKNOWN，不憑該頁缺值宣稱跨頁漏。相同caption多subgrid可映多native item聯集，不能只取一半就報漏。

## QA與定位

獨立固定seed QA核了原9樣本全部201 numeric components：實際native均保義；RAW有1個header UNKNOWN，MAPPED9個正確。QA指出的packed-header false-extra與多行Markdown header loss已全量修scorer，v1/v2/v3保存，來源gold未變。新增解析修正以明確source/native header完整等同優先，避免MR和MRPC子字串混淆；沒有按文件例外。

cellFalse對照頁rawlayout全部相同（root page-scope-control），觀察到的native cell/grid差異定位table structure/cell matching至組裝階段；RAW父header丟失定位serializer／Markdown表格語法。只定位，不改模型／pipeline。不在本輪實作自訂數列重建。

## 產物與限制

results/E0-v4.json、cellFalse-v4.json含逐semantic table、逐point及兩出口完整證據；delivery/<variant>/<job>/<interval>/保存RAW table片段與實際rendered HTML、mapper三出口與delivery-audit。summary.json保留所有family/Q13、前後可判比較及UNKNOWN遷移；selfchecks.json含source hash、packed-header、multi-native union、RAW/MAPPED分歧等回歸檢查。

官方do_cell_matching=False有3張確證整表修好、更多UNKNOWN→PASS，但仍8 FAIL與大量UNKNOWN；可列官方候選，不能據此直接推薦無條件全開或宣稱36篇完整Q4已修好。圖內噪訊、公式和演算法不由此表格結果推論。
