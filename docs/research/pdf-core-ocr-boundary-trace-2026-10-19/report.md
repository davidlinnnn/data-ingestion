# S0 雙欄混句：OCR 輸入邊界追蹤結果

2026-10-19，Asia/Taipei。公開摘要：[#84 結果](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6264942470)。**已取得缺少的邊界證據，原缺陷真實重現；沒有修正或放寬判準。**Heron 原始框分在左右兩欄，Docling 的 OCR 區域膨脹／連通區合併把它們合成單一跨欄裁圖，RapidOCR 原始回覆即含跨欄文字行。後續分群、去斷詞再產生 `foror`。這輪只診斷，不開下一模型比較。

使用者明確授權這項追蹤；它獨立於仍待選擇的 R1／R2／R3，沒有啟動 R1 的 8 小時工程提案。

## 凍結方法與執行

| 項目 | 實際範圍 |
|---|---|
| 來源 | 既有 `scan-pages-3-5.pdf` 的 physical page 1；真實論文原頁 3 的清晰 raster fixture，無新增噪聲／旋轉。SHA `7856cfe6127948d506ca5fad750e915134be362b5e1436c70b378f42a6fda2a0` |
| Pipeline | 原 S0：Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3，StandardPdfPipeline／PyPdfium |
| 模型／設定 | Heron `8f39ad3c…` CPU FP32、threshold 0.3、compile off；RapidOCR v6 det_small／rec_small＋v2 cls；DEFAULT／PDF-aware layout regions；TableFormer V1 accurate。CPU4／interop1／batch1。與原有效 options 相等，只有原停用 chart supported_engines 的集合次序作比對正規化 |
| 唯一新 conversion | 1 次、1 頁、0 retry、0 API／VLM；無模型下載、套件升級、SDK 檔案修改或輸出修字 |
| 觀測 | 引擎 detection 輸出／轉換後原始 clusters、OCR dedup 前後框、實際 reader NumPy／PNG、reader boxes／texts／scores、PDF merge 前後 cells、layout postprocess、assembly 合行。Detection 輸出已過 threshold，非原始 logits；reader 邊界不是每個神經網路的 tensor／forward trace |
| 資源上限 | 整個 worker 含初始化最多 180 秒；sampled tree RSS 12 GiB、可用記憶體至少 8 GiB、啟動至少 10 GiB；重用 Zombie-safe 監督與共享 lock |
| 實際成本 | worker／監督 8.9346 秒，初始化 1.7814 秒，conversion／保存 4.5671 秒；sampled peak tree RSS 3,260,252,160 bytes，約 3.04 GiB |

[registration.json](registration.json)、[execution.json](live/execution.json)、[conversion.json](live/conversion.json)、[analysis.json](analysis.json)保存精確身分與成本。不是 p95、正式吞吐或完整 Profile 的效能證據。

## 邊界證據與已排除的假說

| 階段 | 真實觀測 | 可作的結論 |
|---|---|---|
| [Heron detections／原始 clusters](live/trace/layout-clusters-001.json) | 22 個候選：8 左、14 右，含重複角色候選；沒有框跨過頁面中央。兩欄最小水平間距約 10.68 PDF points | 對本頁可排除「Heron 原始框已將左右欄畫成同一框」。22 不是獨立段落／來源數 |
| [Docling OCR dedup](live/trace/ocr-dedup-001.json) | 預設 `dilation_size=20`；把框 rasterize 到頁面座標遮罩、膨脹，再取 connected-component 外接框，22 個候選合為 **1 框 `(38,19,574,756)`** | 跨欄 OCR 區域在送 reader 前已形成。20 是膨脹核尺寸，不是兩側各加 20；mask 使用 PDF page units，而非實際 OCR 高解析 pixels |
| [實際 OCR 裁圖](live/trace/ocr-engine-001.png) | 寬 1608 × 高 2211、scale 3；[原始 NumPy](live/trace/ocr-engine-001.npy) 與 PNG pixels 相同，尺寸對應 `(536×737)×3` | 真正送給 RapidOCR 的是一張含左右兩欄的大圖，沒有假用事後重製裁圖 |
| [RapidOCR 原始回覆](live/trace/ocr-engine-001.json) | 共 114 行；index=3（零起算，即第 4 行）同時含左欄 `or LLMs … either` 與右欄 `mally introduced by GPT-3 … language`；quad 亦橫跨兩欄 | 文字在 reader 回覆就已混合，不是 JSON mapper／Markdown 才混句；未捕捉內部 detector／recognizer 各自 tensor，不能再單獨歸因某個 neural 子階段 |
| OCR／PDF merge | [前](live/trace/ocr-cells-before-merge-001.json)／[後](live/trace/ocr-cells-after-merge-001.json) 114 cells 逐值相同 | 此步沒有引入該混句 |
| [Layout postprocess](live/trace/layout-after-postprocess-001.json)／[assembly](live/trace/assembly-lines-002.json) | cluster 3 納入左右欄與跨欄 cells；原生合行將 `for-` 後接 `or LLMs`，形成 `foror` | 下游固定／擴大已錯的 cell 邊界；普通 dehyphenation 不是唯一根因，末端排序不能可靠復原 |

本輪確認的是**框合併引入跨欄輸入，以及此輸入下 reader 真實混句的完整鏈條**。尚未跑更小裁圖的 OCR，所以不能宣稱這個改動單獨就會修復所有文字或閱讀順序。

## 零推論幾何對照

使用同一組 22 個已保存候選框、同一 pinned `BaseOcrModel._deduplicate_rects`，只在離線函式重播比較預設 20 與 0；沒有回填模型或改正式常數。

| 離線膨脹值 | 輸出框數 | 跨欄框 |
|---|---:|---:|
| 20，與本次實際輸入逐值相同 | 1 | 1 |
| 0，純幾何反事實 | 15 | 0 |

**0 只是一個定位用對照，不是推薦部署參數。**它會同時改變邊界 padding、框數與工作量；15 不代表已驗證的正確段落或正式 jobs 預算。沒有針對 15 框做 OCR，也沒有品質／latency／一般文件回歸，不能把它寫成修復通過。

## 觀測可信度與執行前檢查

- 真實 [check.py](check.py) 重播原生 `PageAssembleModel.sanitize_text` 與保存 cluster：原 S0 exit 1（paragraph integrity false、`foror` true），S1 exit 0（只代表此段落完整性，不代表完整 reading order）；本輪 fresh S0 仍 exit 1，重現同一缺陷。
- 五項零推論 [tests](test_capture.py) 通過：reader 的原 input／kwargs／result identity／單次呼叫、原生空結果、patch 復原、凍結紅／綠控制、真實 dedup generator 單次消耗與同值輸出。
- 本輪 parsed cells、postprocessed layout、assembled page、provider document **逐值等於原 S0**；主要 Markdown **UTF-8 bytes 完全相同**。這支持觀測沒有改變此案例輸出，不外推所有可能輸入。
- 執行前審查修正了空 reader 欄位的觀測例外，以及原始 asset hash 可能被新雜湊覆寫的檢查漏洞；均在首個模型執行前完成。取得 lock 後才建立 live 目錄的改動另保留 [registration-prelaunch-v1.json](registration-prelaunch-v1.json)，沒有推論重試。
- 原模型、SDK／runtime、來源、舊輸出及有效 options 在前後通過雜湊／版本核對。臨時 observer 在 child 的 finally 復原，SDK 檔案未改。
- 唯讀重播：使用既有 pinned Python 執行 `analyze.py --check`，會核對凍結身分、實際 pixels／來源鏈、幾何對照及原輸出相等；不重跑模型、不覆寫 analysis。

## 官方版本／方法取捨

對照[官方調查](../docling-reading-order-official-research-2026-10-19.md)，本次證據讓後續方向收窄：

1. **不推薦為此缺陷單純升級 2.140.0。**[v2.140.0 原始碼](https://github.com/docling-project/docling/blob/v2.140.0/docling/models/base_ocr_model.py#L511)仍使用 20-point dilation／connected components；[#4748](https://github.com/docling-project/docling/pull/4748)只移除完全被包含的重複框，不會拆開已形成的這一個寬框。這是 source audit，不是假裝已跑新版本，亦不保證整個新版輸出與舊版相同。
2. **不把 DEFAULT→LAYOUT_REGIONS 當新解法。**兩者共用此 dedup；本例無文字層、全頁 bitmap，沒有已確認的欄分離機制。FULL_PAGE 仍提供雙欄大圖，也不直接針對這個成因。
3. 若續做官方元件對照，優先比較 **OCR engine 的欄／行分割行為**，保留 Heron／來源／其他設定；官方 `TesseractCliOcrOptions` 可作單一待登錄候選。Pinned [Tesseract CLI stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/ocr/tesseract_ocr_cli_model.py#L387)以 TSV 的局部 boxes 建立 cells，[options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L602)有 page segmentation 設定；這只是針對分割層的候選理由，不保證修好。本機目前沒有 Tesseract binary／tesserocr／EasyOCR；本輪沒有安裝或推論，也沒有新增已核准模型名額。
4. 原生改進若要直接保留 layout 欄界，應處理 **pre-OCR 區域合併政策**，不是客戶端猜字。該政策目前是內部常數／方法，不能包裝成已存在的公開開關；不在本輪 patch SDK 或自動啟動 A/C 工程。

**本輪終局：DIAGNOSED／DEFECT_REPRODUCED，非 FIXED／QUALIFIED。**此偏差仍不可接受。交付邊界證據與具體方法取捨後停止；下一個模型／版本比較仍須具名配置、來源／回歸範圍與資源上限，不追加 prompt、padding 或修字迴圈。A/B/C 既有終局、封存 holdout、正式公司模型／GPU／高頻 qualification 均未改變。
