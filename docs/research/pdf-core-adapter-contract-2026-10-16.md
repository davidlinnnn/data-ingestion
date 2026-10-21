# PDF-core A′ 原型前置驗證：停止，不擴張 adapter

2026-10-16。使用者在釐清「零模型＝不載入／呼叫模型，只測資料交付程式」後，以「OK, 請執行」接受[既定方案](pdf-core-next-method-decision-2026-10-16.md)。**已完成最先執行的 continuation 控制，24 項中 22 項通過、2 項必要關係錯誤；依事前停止條件，停止 A′，沒有實作 mapper 或私有 hook，也沒有繼續 export 測試。**

這是「重用既有交付規則不足以完成這個有限方案」的證據；不是新模型失敗，也不是 Docling 所有方法都不可行。G2 仍無滿足全部必含功能的完整配置。

## 實際執行了什麼

| 項目 | 實際執行／設定 |
|---|---|
| PDF pipeline | **未執行任何 PDF pipeline**；沒有解析 PDF、layout／OCR／VLM 推論。 |
| 被測元件 | 原樣呼叫專案既有 `src/pdf_processing/continuation.py` 的 `predict_merges()`，方法 `column-edge-continuation-v1`。這是本專案的有界續接 policy，不等於 stock StandardPdfPipeline 的完整能力。 |
| 官方相依元件 | IBM `ReadingOrderPredictor` 的既有純規則 merge helper；source 與 constructor 已確認不載 learned weights。 |
| Runtime | 既有 Docling 2.102.0／Core 2.96.0／IBM models 3.15.0；沒有建環境或安裝。不是 Step 1 擬議的 2.132 完整配置。 |
| 輸入／參數 | 先凍結明確的文字、label、page、bbox、尺寸、預期連結；以數學轉換轉成 BOTTOMLEFT 座標。演算法、threshold、既有負例均未改動。 |
| 執行次數 | 一輪固定 24 項控制；原有 11 個可用合成 unittest methods 原樣執行。兩者有覆蓋重疊，不能相加成 35 個獨立樣本。 |

控制與停止條件先寫入 controls.json (`pdf-core-adapter-contract-2026-10-16/continuation/controls.json`)，其 SHA-256 在執行前後核對一致。原始結果、runtime／source 身分及逐項不變量見 results.json (`pdf-core-adapter-contract-2026-10-16/continuation/results.json`)；執行細節見 [continuation 記錄](pdf-core-adapter-contract-2026-10-16/continuation/README.md)。

## 結果與失敗意義

| 控制 | 結果 | 意義 |
|---|---|---|
| 4 項應續接正例 | 4/4 通過 | 包含跨頁鏈、跨欄與同一行片段。 |
| 20 項不應續接負例 | 18/20 通過 | 仍有兩個誤接；不是只缺少來源 ID 或檔案包裝。 |
| 原有合成 unittest | 11/11 通過 | 既有測試未涵蓋兩個失敗情境，不能抵銷失敗。 |
| 原文不變／ID 存在／無 cycle／唯一 ownership | 全通過 | 結構合法仍可能把不相干內容連在一起。 |

兩個失敗的預期均是「不連接」，實際均輸出 `{"0": [1]}`：

1. **獨立新段，前段沒有句號。** 合成來源明確定義 `Method A uses a fixed schedule` 與下一頁的 `Results improve on the held-out set.` 為兩段；只因頁邊幾何符合、末字為小寫，就被接在一起。有句號的對照通過。這是合成反例，不是自然文件發生率的估計。
2. **高正文框吸入右側標題。** 從已保留且先前評讀的 SEAL `#/texts/34` 兩段 provenance／charspan，重建最小 policy 輸入；保留 native `text` label、原頁尺寸／bbox／文字，重現正文誤接右側 `Algorithm 1 ...` 標題。這是既有 fragment 的接點重放，並非重新解析 PDF 或實作自動 splitter。另把標題假設改成 `section_header` 的反事實對照通過，**不能當成原資料已被修好，或 Paddle 將來一定會給正確 label。**

24 項包含合成、既有測試等價控制、既有來源 fragment 與一項反事實對照；22/24 只是這組必要控制的結果，**不是模型準確率或泛化成績**。

## 停止與未執行範圍

既定方案只允許有限映射、重用未改動的 continuation／export；任一必要控制失敗即停止，不新增段落判斷規則。因此：

- 不調 continuation 規則、閾值或 label，不為這兩題補 heuristic。
- 不實作 mapper、raw capture subclass 或 vendor patch；不恢復 Paddle 建置／實際整合／推論。
- 新的 Markdown export、wrapped formula 映射、圖片 enrichment 分離、raw／來源綁定拒絕控制及真實 producer hook，均**未執行**。本輪不能報它們通過或失敗。
- 兩項舊 replay 測試因歷史 `/private/tmp` checkpoint 已不存在而未執行；沒有重造 fixture 或刪去這個限制。詳見逐項結果。

模型載入、推論、網路連線嘗試、安裝、建環境及 PDF／圖片／holdout 內容讀取均為 **0**。整個步驟在 2 小時上限內提前停止；純規則 runner 的毫秒級時間不代表 ingestion latency。舊實驗與 production 未變更。

**本輪結論：收束 A′，不自動換下一模型或擴張後處理。** 現有 Standard 元件仍可作有用基底，但尚無完整合格配置。若未來重開，必須提出能同時保留原正例與避免誤接的不同完整方法，另行決定其維護成本；本輪不替它開新試驗。

執行範圍及核對紀錄 (`pdf-core-adapter-contract-2026-10-16/execution.json`)記錄本次授權、停止結果、未執行項目與檔案身分；先前 pending 決策文件保留為當時提案，由本記錄承接。
