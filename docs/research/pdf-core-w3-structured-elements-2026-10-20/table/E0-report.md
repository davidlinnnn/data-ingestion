# E0 table：RAW／MAPPED 逐表結果

36 篇保存輸出已評；來源 gold 沿全域封存 v2，沒有以輸出修 gold。未跑 conversion／模型。

|family|來源表|IN／OOS／定位未知|已證偵測／IN對齊未知|RAW FAIL／UNKNOWN／OOS|MAPPED FAIL／UNKNOWN／OOS|
|---|---:|---:|---:|---:|---:|
|ACL/EMNLP|32|29／1／2|28／1|4／27／1|4／27／1|
|ACM sigconf|10|10／0／0|10／0|0／10／0|0／10／0|
|CVPR/AAAI|17|14／0／3|11／3|0／17／0|0／17／0|
|ICML|24|14／0／10|7／7|0／24／0|0／24／0|
|IEEE conference|5|5／0／0|5／0|0／5／0|0／5／0|
|NeurIPS/ICLR|66|33／0／33|24／9|1／65／0|1／65／0|
|Pilot-other/unknown|57|49／0／8|37／12|0／57／0|0／57／0|
|Springer LNCS|15|6／2／7|6／0|0／13／2|0／13／2|
|general arXiv|5|0／0／5|0／0|0／5／0|0／5／0|
|general arXiv (article; template uncertain)|21|15／0／6|10／5|0／21／0|0／21／0|

沒有將 UNKNOWN 當 PASS；本輪沒有證成整表 PASS。來源共252候選，175 IN_SCOPE、3 OOS、74定位未知；其中138表有來源文字／多點值與標籤／原圖對 native 的唯一偵測證據，37個 IN_SCOPE 的native對齊仍未知。這是確認量與未知量，不把37算漏偵測，也不計虛假的100% detection rate。

必須區分：175個IN_SCOPE只是來源表存在與頁碼可定位；其中只有14表（ordinary9／complex5）有完整可信numeric分母。其餘可有trusted子集，但不能用子集誤差宣稱整表通過。另有1個complex表用來源點數保守上界確證FAIL；無法補齊的gold仍不更動。

|確證表（各自裁決，不平均）|類別／來源分母|確證錯誤下界|RAW／MAPPED|
|---|---|---|---|
|P-06-2606.14239v2:table-015 p27|complex／50|17（錯率至少34.0%）|FAIL／FAIL|
|P-11-2508.19828v5:table-001 p8|ordinary／6|2（錯率至少33.3%）|FAIL／FAIL|
|P-13-2601.01885v3:table-001 p8|complex／上界87|6（錯率至少6.9%）|FAIL／FAIL|
|P-13-2601.01885v3:table-003 p9|ordinary／8|2（錯率至少25.0%）|FAIL／FAIL|
|P-13-2601.01885v3:table-005 p26|ordinary／8|2（錯率至少25.0%）|FAIL／FAIL|

這五表共29個確證 tuple 錯誤下界（20 missing＋9 extra），不是完整誤差總數；其他點的未知仍保留。P06 複合表有完整50點來源分母，僅右側17個 Reward tuple 已缺於對應欄，17/50=34%已大於5%，足以FAIL；不把另33點宣稱全對。三個ordinary表各有至少一個原圖確證錯誤即不符零錯規則。

另P13p8 Table2被下方Figure4條圖合併：native tables/1 row15 metric欄2–7至少6個不同cell納入Figure4數字。凍結來源cell只含format/color/multirow命令，沒有未知或產生數字macro；連backbone標籤內數字一起數，共87個numeric token可當保守來源點數上界，因此6/87=至少6.9%已超過5%。這是FAIL_WITH_PARTIAL_ORACLE，沒有把兩個未知model-label候選改成gold。stage由image零推論replay證實：較寬table11勝過table9，picture panels合成picture13後被cross-type overlap刪除，圖表混入表框。見 `P13-chart-contamination.json`。

其餘四表的錯誤在 native cells/grid 已存在；表框涵蓋原圖完整表格，但多欄數值被塞到 row-header 或鄰欄。定位到 native table structure／TableFormer 重建出口，無證據宣稱 reading-order／serializer 是這些 tuple 錯配的首因。mapper保留原格位，不能修好這些關聯。

RAW官方逐表export共238個native表，237個完整export字串可在保存Markdown找到；EfficientNet tables/0另保留出口不一致待解。RAW expanded grid有73表、677次同native cell額外曝光，MAPPED每cell ref單次；這些曝光含headers，不能直接當677個錯誤來源資料點。RAW與MAPPED共同的numeric關聯失敗和serializer重複風險分開報。

11,095等W2 mapper leaf/item量不當W3表格語義分母。未解析巨集／表頭、無numeric表、multi-value cell語義或唯一對齊不足均保留UNKNOWN。沒有用列數／欄數不符就將每點都算錯；全header壓成一格且無法確定值的對象者也不算全對。

逐表、逐點、rows/cols/header證據與分子／分母見 `E0-results.json`；原圖與native ref、兩出口片段見 `E0-visual-adjudication.json`；全部native表出口與span曝光見 `delivery-audit.json`。

輸入沿R3/V3_B已保存的官方JSON；P10／P20先前raw baseline→Core的79／143個bbox座標clamp另存summary的provenance欄，不視為模型改善。本mapper直接讀JSON、不新增clamp；五個確證失敗在P06／P11／P13，沒有依這兩篇的clamp作裁定。36篇逐篇表（含零來源表也不當PASS）另見 `summary.json`。
