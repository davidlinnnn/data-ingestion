# PaddleOCR-VL 零推論接合：獨立覆核

日期：2026-10-20。範圍：唯讀核對本輪 probe、合成 fixture、原始 JSON／Markdown／rendered HTML、來源 ledger 與已安裝的官方 table merge 原始碼；本次覆核沒有重跑 probe、推論、安裝或修改原始證據。本檔是覆核說明，不覆寫 `results.json`、probe 或 registration。

**結論：完整官方 Result／磁碟匯出與部分來源保留接合成立；尚不能宣告完整方法滿足 #84，亦未由此證明模型品質。** 執行的是實際 `PaddleOCRVLResult` 與未改官方 `restructure_pages` 的 unbound method（`self=None`），沒有建立 pipeline／載入模型。

## 已成立的行為與反例

| 面向 | 獨立覆核結論 |
|---|---|
| 表格正控制 | 相同表頭、不同資料列合成一張表，重複表頭被移除。但 merged HTML 全放到第一頁，第二頁保留空 table；Docling importer 拒絕該空 table，成功匯入的表僅帶第一頁 provenance。這不是逐資料點跨頁來源交付成功。 |
| 相同資料列刪除 | 兩個頁片段各含一筆相同但各自存在的資料列，合併後僅剩一筆。官方 `detect_table_headers()` 同時比較 `td`／`th`，把相同前綴資料列也計入 header count，再由 `perform_table_merge()` 省略。合法重複觀察的 multiplicity 未保留。 |
| 不相關表格誤接 | fixture 指定為兩張獨立表，表頭 A/B 與 C/D 不同仍被合併。這證明該負例未被阻止；不能擴張為「所有不同表頭皆不得續接」，因真實多 panel 表可能換表頭。 |
| 圖片覆寫 | 不同頁的相同 bbox 產生相同原生路徑，共用輸出目錄時第二張覆寫第一張，兩份 Markdown 都指向該路徑。 |
| 圖片包裝與搬移 | 只修改 export view 的資產路徑、以頁 namespace 匯出後，三個 assets 的 key／路徑唯一、原 provider serialization 不變；搬移後 byte/hash 讀回，foreign revision 與缺圖控制被拒絕。這是資產包裝證據，尚非完整 Canonical caption／OCR／chart supplement 交付。 |
| 座標與聚合 | 原始逐頁 importer 保留 source page 3／4 與各自 pixel canvas；來源 ledger 明示本合成控制的 144dpi、無旋轉／unwarp 與 point mapping。Core concatenate 重新編成頁 1／2，因此仍需 ledger 回到原頁，不能誤稱 source page number 原樣保留。 |

證據：[table-controls.json](paddle/table-controls.json)、[Paddle 結果](paddle/results.json)、[Docling 結果](docling/results.json)、[資產清單](paddle/relocated-bundle/assets.json)、[來源 ledger](docling/source-ledger.json)。具體測試接線見 [paddle_probe.py](paddle_probe.py) 與 [docling_probe.py](docling_probe.py)。官方來源為本輪 registration 鎖定的 PaddleX 3.7.2 `layout_parsing/merge_table.py`：`detect_table_headers` 比對所有前綴列、`perform_table_merge` 跳過 header count，`can_merge_tables` 依寬度／列欄數接受候選。

## 原始指標須另行解讀

1. **Docling 主 Markdown 的圖內 OCR／chart content 指標是 false negative。** `docling/results.json` 的 `image_content_in_docling_primary_markdown`／`chart_content_in_docling_primary_markdown` 使用未 escape 的精確 substring。實際 [p3.md](docling/p3.md) escape underscores；[stock-render.html](docling/stock-render.html) 明確顯示 `DERIVED_IMAGE_OCR_ONLY` 與 `DERIVED_CHART_DATA_ONLY`，原始 [p3.json](docling/p3.json) 亦保留相同 text nodes。因此不能宣稱二者未出現在 stock 主內容；二者實際混入主內容。
2. **Native numbered formula 的 delimiter 指標是 false negative。** `native_display_bare_formula_delimited=false` 搜尋 `$$E = mc^2$$`，但實際 [document.md](paddle/relocated-bundle/document.md) 輸出 `$$E = mc^2 \tag*{(7)}$$`：式號與 delimiter 均保存。不能以此判缺 delimiter；本輪也未測「沒有式號的 bare formula」。舊 converter component 的其他案例不可冒稱為本輪完整 Result 案例。
3. **Paragraph 精確字串未命中不是語意失敗證據。** `native_paragraph_continuation_reconstructed=false` 只檢查一個跨頁 fragment 是否成為單一精確字串；兩個來源 fragment 都仍存在。既定要求允許不改義的 reflow，不強制單一字串或特定 typed label。可確認的是官方 concatenate 僅串接頁面 Markdown，沒有提供 logical paragraph continuation relation；完整跨頁能力仍未證實，不能據此判模型漏段。

上述保留原始結果，須以本覆核／adjudication 說明測量限制，不刪除或悄悄改寫原指標。

## 完整方法的阻擋與普通接合工程

- Plain algorithm 的 `#` 在本輪 CommonMark 中成為 heading、`<tag>` 被當 HTML 而不顯示；stock fenced code 的 literal 也改寫。失敗依據是實際消費內容／縮排，**不是單因沒有 backticks 或某種 typed inline label**。
- 分開的 inline formula 未回到正文關係；跨頁表格的語意續接、資料 multiplicity 與逐資料點來源仍有缺口；native 主 Markdown 直接含 chart 衍生 HTML，stock 主內容另含圖內 OCR。圖內 OCR 被 native 固定 options 隱藏，不代表已提供可發現、同版綁定的 supplement。
- 圖片 namespace／component key、來源 ledger、原 provider 保存、artifact 路徑與缺依賴拒絕，屬可沿既有契約實作的普通接合工程。本輪只證明有界控制，不宣稱完整 mapper 或 custody 已完成。
- 新增語意續接、表格辨識／去重或 inline ownership 演算法則是方法工程；不可包裝成機械 mapping，也不能以 raw JSON 留存取代必含能力。

## 未測範圍

本輪 fixture 含 `$5`／inline dollar math，但沒有 `\(...\)`／`\[...\]` 輸出，也沒有執行上游模型輸出 normalization；已知該 normalization 可能移除混合區塊美元 literals 的風險**未測、未解決**。沒有測模型準度、pipeline constructor、實際 Paddle layout／VLM crops、方向校正、GPU／MLX、效能／負載或 holdout。

合成合法 provider 輸出只證明接合行為及反例；不得當成 Paddle layout／VLM 品質成績。圖片搬移目前證明本包的檔案 bytes／hash 及有限負控制，不能擴張成完整 Canonical consumer、runtime 恢復或跨 revision 身分系統驗收。
