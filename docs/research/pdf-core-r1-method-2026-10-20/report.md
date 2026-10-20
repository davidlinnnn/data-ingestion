# R1：來源群組接合方法的有限工程結論

2026-10-20。結論：**METHOD_REGISTERABLE，僅限已列明 DEV 範圍的離線接合方法；live_ready=false。** 本輪結束，不自動增加方法、時間或推論。這不是 A/C 品質通過，更不是 #84 Processing Profile 合格。

使用者批准一次最多 8 小時、零新推論的來源群組方法工程。04:31:09Z 開始；最後證據檢查與封存時間另見 completion.json，保守按經過時間計費，沒有等待扣除或重設。未下載模型、未呼叫 API、未讀 holdout、未改 SDK 或歷史封存。

## 方法與實測

重用保留的 StandardPdfPipeline 輸出與原始頁面像素，沒有重新執行 pipeline。A 按 native provenance 建立頁面連通群組，每個 leaf text owner 明確 keep 或 consume；公開 Core insert/delete 能處理跨 parent 重建。C 保留原圖 key/crop，整頁只作獨立 context；來源文字重建、crop OCR、context OCR、generated description/chart 分開負責。重建 caption 必須使用本輪公開 serializer extension；並非 stock Markdown export 已自動修好。沒有 padding、字串修補、文件 ID 選路或續接猜測。

| 證據 | 結果與界線 |
|---|---|
| 方法與同來源原子組裝控制 | 19/19；包含未知/重複 owner、跨版本、唯讀 context、非目標保持、caption 邊、回應到達順序 |
| A 保留輸入 | 8 頁、4 群組；44 個必要目標與 27 個 ordinary negatives 的頁面像素覆蓋、41 個 legacy source units 均有交代；不是 44 個內容全部正確 |
| C 保留輸入 | 55 頁、29 張 native pictures、14 個 picture-context groups；19 個評讀來源群組完成對應；原 caption 錯字及部分 crop 範圍問題沒有被品質宣告抹除 |
| 真實跨 parent 反例 MOCK | SEAL p4 的 11 個來源 refs 可重建 algorithm，保留非目標與圖；MOCK 由評讀側提供，不是模型正確率 |
| 真實圖與標題反例 MOCK | SEAL p2 含標題共 17 處數學可進主要 Markdown，保留圖與 caption；不是模型發現率 |
| 實際交付 | 兩個 bundle 搬移後 JSON reload、Markdown bytes 重現、圖檔 decode 通過；錯 revision、缺圖檔拒絕 |
| 舊證據回歸 | tests/pdf_research/check.py 完整 109 個控制/測試通過；五套歷史 manifest 與 17 個方法 hash 未改 |

初版 stock caption escaping、typed caption reachability、Core normalized image identity、heading math、預設 JSON 圖片內嵌失敗，均保存在 attempt01–05。修正是同一方法的公開接點工程；沒有隱藏失敗或重新封存舊結果。原始 JSON digest 與 Core export projection digest 分開保存，避免把 clamp 後的幾何當作原始 bytes。

## 完整候選工作量與停止線

單列 A/C component 會得到 32 次，但 C context OCR 不能修復主要來源 caption。因此按所有 native-picture 所在來源群組，統一增加來源重建責任，不按已知錯字挑頁：去重後增加 11 次，共 **15 次 source reconstruction + 28 次 C component = 43 次遠端候選請求**，另有 **29 個本機 crop OCR 工作**。每個 source job 最多 3 頁，沒有整份 PDF 全頁 VLM。

實際 placeholder 請求共 39,649,342 bytes，最大 2,770,332 bytes；含重複任務輸入共 108,757,374 pixels。這些不是 tokens、費用或 latency。completion cap 合計 475,136 只是預算上限提案，尚未以實際 tokenizer 驗證。候選 concurrency=1、retry=0、best_of=1、180s/request、3600s/batch 也只是有限執行提案，不是正式 SLO 或已授權批次。

**不得直接啟動 43 次。** 先選定精確模型與 endpoint/runtime 能力、完成各 job token reservation/maximal-response 預檢、補齊新增 C 來源重建的評讀與非目標 QA 規約、完成 envelope 到 bounded runner 的接點。四項均列入 planning/jobs.json 的 blocking_live_preconditions；不得用這次 MOCK 或 hash check 代替。

## 保留與限制

保留此方法作下一個有限模型實驗的可登錄接合候選；停止 R1 工程。原 A/C 模型內容問題、B T04 語意綁定失敗及雙欄/OCR 問題仍在，不因此批准正式部署。新增來源工作的完整語意評讀尚未就緒。連到 footnote 的內容重建目前拒絕，既有 footnote 保留；含特殊 Markdown fence 的 code 未全面驗證。來源精度是誠實的 page envelope，加上保留原 bbox/charspan，沒有捏造 glyph/cell 座標。

重跑唯讀證據檢查：`/private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-r1-method-2026-10-20/check.py`。方法控制：同一 Python 執行 `-B -m unittest discover -s docs/research/pdf-core-r1-method-2026-10-20 -p 'test_*.py'`。檢查不更新 seal、不產生模型輸出。
