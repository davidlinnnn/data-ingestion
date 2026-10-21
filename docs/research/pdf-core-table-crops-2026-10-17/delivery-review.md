# Table crops：獨立交付審查

2026-10-17。六次 API 與 page assembly 全部完成後，才讀取本輪結果。只讀保存輸出，沒有新增 inference、oracle 或來源圖片讀取。

| 頁面 | 交付檢查 | condition visibility 待核對 |
|---|---|---|
| memory-r1-p8 | not delivered; whole page unaccepted | 0 |
| skillopt-p8 | not delivered; whole page unaccepted | 0 |
| paper09-p17 | not delivered; whole page unaccepted | 0 |
| wikiskill-p13 | passed | 0 |

六個 target 原始 content 另逐一重驗。兩個 target schema 通過；四個拒絕與 live 記錄一致：

| Target | Schema 結果 |
|---|---|
| memory-r1-p8-table0 | targets.0.panels.0.data: Value error, overlapping or duplicate cells |
| skillopt-p8-table0 | complete-cell schema passed; source accuracy separate |
| skillopt-p8-table1 | uncertainties: Extra inputs are not permitted |
| paper09-p17-table0 | targets.0.panels.0.data: Value error, overlapping or duplicate cells |
| paper09-p17-table1 | targets.0.panels.0.data.table_cells.5.end_col_offset_idx: Field required; targets.0.panels.0.uncertainties: Extra inputs are not permitted |
| wikiskill-p13-table0 | complete-cell schema passed; source accuracy separate |

映射成功頁面核對 graph／全部 references、非目標正文及順序、linked／standalone caption、來源 provenance、完整 physical cells、實際 Markdown 渲染的 cell literals／header ancestry、canonical 不變、source spans、JSON reload。四個合成拒絕控制涵蓋缺 cell、重疊、span mismatch 與未知 target。

Schema 拒絕不等於所有數值錯誤。尤其 SkillOpt collateral 的問題是 root 多出 uncertainties 欄位；本輪遵守凍結 strict contract 拒絕，沒有刪欄位後重新接受。來源數值品質需另外閱讀 raw 評分。

T05 若有交付，另核對原正文 Table 4 caption 僅出現一次；沒有自行建立 native link，也沒有把 standalone association 當成驗收失敗。真正缺漏 caption 並未由此審查補回。

Provider conditions 若沒有逐字出現在主要 Markdown，會列為待語義核對；不能只因已存入 bindings，就推論主要內容交付完整。這是可見性篩查，不是來源等價性裁決。數值與 critical comparisons 由另外的來源評分處理。

所有 frozen method／保存輸入輸出 hashes 前後一致。完整逐項結果見 `delivery-review.json`。
