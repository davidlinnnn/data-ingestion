# PDF-core 下一決策：最小保真接點的維護範圍

2026-10-16。承接 [Step 1](pdf-core-single-config-2026-10-16.md)。**建議只投入一次最多 2 小時、零模型的交付接點原型；不恢復 Paddle 建置或推論。** 需要使用者決定的是：是否接受維護一個固定版本的私有 raw capture 接點，以及有限的型別／座標映射。這是工程整合的範圍選擇，不是新模型候選已通過。

本輪完成來源查核與方案收斂，沒有執行原型、安裝、建環境、載入模型、推論、下載模型或讀取 PDF／holdout 內容。所有必含需求維持，G2 尚無完整合格配置。

## 方向與建議

| 方向 | 代價與限制 | 判斷 |
|---|---|---|
| 繼續擴充 Standard 的自訂全文 detector／context 修補 | 仍須解決漏偵測、內容錯誤、定位與組裝；先前已有失敗。 | 不建議擴張，容易增加使用者不希望維護的後處理。 |
| 立即恢復 Paddle 完整流程小型模型試驗 | 原生文字轉換與跨頁交付已有必要條件衝突，不能只靠換模型解除。 | **目前不執行。** 本輪曾考慮的八頁試驗已在建置前否決，沒有投入或核發該模型額度。 |
| **A′：原始輸出保全＋既有交付能力的零模型原型** | 接受一個私有接點的版本維護；只做明確映射，重用現有 continuation，不新增偵測或修字規則。 | **推薦，最多 2 小時，一個設計。** 只能回答交付接點是否值得繼續。 |
| 不接受這筆整合維護 | 保留目前有用元件與失敗結果，在此收束新增方法研究。 | 合理選擇；不能改稱需求已達成或 Docling／模型能力已到極限。 |

## 為什麼不直接跑下一個模型

固定 PaddleX source 在遇到 `\(...\)`／`\[...\]` 成對 delimiter 時，會先刪除該結果中所有 `$`，才轉換 delimiter。即使模型原文正確，混合 code／貨幣 literal 仍可能被改壞；`format_block_content=False` 不能關掉這個上游轉換。[固定 pipeline source](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py#L578-L595)。

Paddle 的 crop 合併、跨頁表格／heading 重整，也不能當成通用跨頁段落續接。原 Q4 要求正確處理跨欄／跨頁續接，既有 E13 亦有跨頁正例；只保留分離 fragments 不自動滿足它。**需求不強制只有一個原生 JSON item，但必要內容與續接關係必須正確。** 詳見[官方機制查核](pdf-core-next-method-decision-2026-10-16/official-route.md)。

因此，「官方流程＋檔案 glue，不處理其他接點」已有已知交付缺口。不能花模型推論預算期待它自行消失，也不能縮成只評 raw 而宣稱完整候選成功。

## A′ 的唯一假設

**H1：若在不可逆的文字轉換前保留原始 VLM 文字、明確 block 身分和幾何資訊，則可用有限的型別／座標映射，銜接既有 continuation／export，保留必要內容與來源關係，而不新增辨識器、內容修正或段落判斷規則。**

這與舊 context 重建不同：它不向模型要求改寫上下文，不修 identifier／prime／表格值，也不猜遺漏內容。它同樣不是一種新的辨識方法，不能解決 layout 沒發現的 code／formula 或 VLM 本身辨識錯誤。

靜態 source 找到的接點是 `_paddleocr_vl_assemble_parsing_results(...)`：同時收到 `blocks`、`vlm_results` 及 `(page_idx, block_idx)` 對應，之後才做上述轉換。可提出 instance subclass 在呼叫原方法前保存必要欄位的設計，無須修改 vendor 檔案。**這只是靜態可行性；目前沒有 Paddle runtime，未驗證真實 hook 可執行。** 批次內 IDs 也不等於完整來源頁身分；後續必須證明來源頁號、頁尺寸、座標系與跨批次唯一性可精確取得，否則不猜配。已轉換的舊 Result 不能被倒推成歷史原始 VLM 證據。

## 原型的完整邊界

| 項目 | 允許範圍／停止條件 |
|---|---|
| raw 與來源 | 明確 raw、block ID、來源頁、bbox、頁尺寸及座標系；缺少、重複或歧義即拒絕。不得用文字相似度、oracle 答案或人工指定連結掩蓋缺口。 |
| capture hook | 只設計一個版本固定、instance-scoped 的保存接點；本階段不安裝 Paddle 或聲稱已驗證即時 capture。若需要更多私有攔截或 vendor patch，停止這個方案。 |
| 映射與輸出 | 映成可工作的 Docling 型別／來源資訊，保存 source fragments，圖片 OCR／描述與來源 Markdown 分開。code／公式／正文的必要 literal 與關係須在主要交付中保留；sidecar 保存原文不能抵銷主要 Markdown 改壞內容。不得把 native label、額外 backticks 或單一 JSON item 新增成產品門檻。 |
| continuation | 重用 [既有 policy](../../src/pdf_processing/continuation.py) 的 `predict_merges()`，不改演算法、閾值或既有負例。它是有界幾何 policy，不是通用跨頁理解；既有 title 吸入風險保留評分。若缺必要 metadata 或既有規則不能通過必要控制，就停止，不另造 assembler。 |
| 資料與真值 | 使用預先寫明真值的合成 contract 和既有保留輸出；不讀新 PDF、不讀 holdout、不重寫舊 oracle／評分。合成 raw 只能證明接點；既有錯誤 raw 須仍呈現錯誤，不算被修好。 |
| runtime／變更範圍 | 使用既有 `docs/prototypes/pdf-checkpoint-prototype/.venv`（Docling 2.102.0／Core 2.96.0／IBM models 3.15.0，僅 metadata 已核對）；不跨 runtime 拼類別、不新增依賴、不建環境。程式只放研究原型目錄，不改 production 或 Canonical Acceptance。這不代表 Step 1 擬議的 2.132 配置已可執行。 |
| 投入 | **一次設計、最多 2 小時；0 模型載入、0 推論、0 安裝／建環境。** 逾時或突破上述邊界，保留失敗後停止，不換另一模型或追加 preflight 追進度。 |

授權後先固定控制與預期，先測現有 continuation／export；若它們已過不了必要控制，立即停止，省去 mapper 實作。通過才實作最小映射。控制須同時包含：

- code／正文的 `$`、`\(...\)`、`<tag>`、底線、縮排等 literal；有 delimiter 與裸公式都要保留內容，不靠逐題替換。
- 續接正例，以及下一段、caption／heading 阻擋、重疊、重複 ownership 和缺 raw binding 等負例；原負例不得為本輪調閾值。
- 既有真實輸出中的內容錯誤；不能因交付接點通過而變成準度通過。

## 原型完成後如何決定

**通過：** 只表示「明確 contract → typed working document → 未修改的 continuation／export」在列明控制下可行。仍須另行決定是否解除 Paddle 暫停，驗證實際 capture、layout／辨識、完整必要功能與成本；不自動取得後續模型授權。

**失敗：** 紀錄哪個接點需要超出範圍的維護，收束這條新方法工作；不生長成全文 parser／新 detector／調答案的後處理。既有 Standard 元件繼續保留為有用但不完整的基底。

即使原型通過，行內內容 discovery、模型辨識、複雜表格、OCR、heading、圖意／chart、實際即時 hook、公司 GPU／vLLM 與高頻 latency 仍未因此通過。

## 目前需要的決策

**建議接受 A′：最多 2 小時，測清楚這個有限接點是否可行，並接受它若採用就需要維護固定版本的私有介面。** 若不願承擔這個維護範圍，現在就收束新增方法研究，明列尚無滿足全部必含功能的配置。

需要這次決定，是因為使用者已要求避免大量自訂後處理並維持 Paddle 暫停；維護私有接點是具體的整合取捨，不能默認成單純調 Docling 參數。本輪只提出可審查方案。**Paddle 建置／實際整合與推論維持暫停，原型也尚未執行。**

[決策與來源核對紀錄](pdf-core-next-method-decision-2026-10-16/decision.json)保存待決狀態與證據身分。本輪不修改舊實驗結果、不建立新 session、不變更 production。
