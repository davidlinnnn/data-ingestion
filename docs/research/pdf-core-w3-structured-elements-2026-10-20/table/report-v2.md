# E0 table v2：完整來源表的正向交付核驗

保留v1全部檔案與凍結gold不變，追加人工核對10張完整分母但UNKNOWN的表。依主線裁定，不按gold把壓單格數列zip回多欄後算正確。

這10表共223個來源numeric word／cell值，全部在native及RAW／MAPPED保留相同值、符號與M／B單位及multiplicity，未發現這批的numeric字詞缺漏或多生。8表保留來源numeric row-major序列；P04p8 component表與P19p22 ablation表的numeric序列有移位。P03p7另有原頁正確的Ouyang2026引用年份，已另列而非誤算多生data point。

這是正向交付證據，不是223個value+row/column資料點正確：header與score vector壓成單格、row-header吞數字或合併多個設定，仍使explicit行列關係不完整。10表均維持UNKNOWN，不把它們算FAIL，也不宣稱PASS。

|表／頁|來源點數|numeric multiset完整|numeric序列保留|行列關係／RAW與MAPPED結論|
|---|---:|---|---|---|
|F-icml_efficientnet:table-009 p9|32|YES|YES|UNKNOWN／UNKNOWN|
|P-01-2608.27454v1:table-005 p20|15|YES|YES|UNKNOWN／UNKNOWN|
|P-03-2603.25158v5:table-003 p7|16|YES|YES|UNKNOWN／UNKNOWN|
|P-03-2603.25158v5:table-004 p8|12|YES|YES|UNKNOWN／UNKNOWN|
|P-04-2605.23904v2:table-002 p8|25|YES|NO|UNKNOWN／UNKNOWN|
|P-04-2605.23904v2:table-005 p14|30|YES|YES|UNKNOWN／UNKNOWN|
|P-12-2508.16153v2:table-003 p15|15|YES|YES|UNKNOWN／UNKNOWN|
|P-13-2601.01885v3:table-006 p27|32|YES|YES|UNKNOWN／UNKNOWN|
|P-19-2511.10395v1:table-004 p22|30|YES|NO|UNKNOWN／UNKNOWN|
|P-19-2511.10395v1:table-007 p26|16|YES|YES|UNKNOWN／UNKNOWN|

Native欄數與來源不符、數列壓單格的事實並未被當成每個source點都錯。反之，numeric words保留也不能當作每點row/column對象正確。原有5個有明確欄位錯配／圖表污染證據的FAIL維持；全252來源候選仍為RAW與MAPPED各5FAIL、244UNKNOWN、3OOS。175 IN_SCOPE只有14表具完整numeric來源分母，這次補核的是扣除4個既有完整分母FAIL後的10表；另一個FAIL是來源點數上界可證的partial oracle。

逐點候選位置、native cell text／row／col、每個source header的覆蓋或合併證據、source與native序列見 `manual-complete-gold-review-v2.json`。候選可能同值重複，不擅自指派來源對象。完整逐表v2見 `E0-results-v2.json`、`summary-v2.json`；v1結論／family數值仍見 [report.md](report.md)。
