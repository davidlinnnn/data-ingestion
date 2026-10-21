# S0 OCR 裁圖消融：混行消失，但方法仍不合格

2026-10-19，Asia/Taipei。**本輪完成原定 1＋15 次 reader 對照後停止，沒有追加推論或調參。**分離裁圖使本頁原始跨欄混句從 3 個降為 0，但新增整個標題漏失、保留既有首行錯誤翻轉與辨識破損，且官方閱讀順序仍錯。**不採用本次零膨脹策略作正式配置；本輪終局為 `DIAGNOSED_NOT_ACCEPTED`，不是修復通過。**

公開同步：[#84 結果](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6266104601)，已逐值核對發佈內容。

這裡 A／B 僅指 OCR 大圖／分離圖兩組，與 #84 的 A／B／C 能力分支不同。A／B／C 的既有終局、正式模型身分與資格、R1／R2／R3 待選狀態均未改變。

## 範圍與凍結

| 項目 | 本輪實際執行 |
|---|---|
| 來源 | `scan-pages-3-5.pdf` physical page 1，真實論文 `2303.18223v1` 原頁 3 的已曝光清晰 raster fixture；非自然噪聲掃描 |
| 原配置 | Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3；S0 `StandardPdfPipeline`＋PyPdfium 的保存 Heron 結果；RapidOCR 3.9.2／ONNXRuntime CPU，PP-OCRv6 det_small／rec_small＋mobile_v2 cls |
| 固定設定 | CPU4／interop1；OCR scale 3、use_det／use_cls／use_rec 全 true、text_score 0.5；原生 reader 有效設定兩組逐值相同，cls_thresh 0.9 |
| A 大圖 | 原保存 NumPy，1608×2211 pixels（寬×高），1 次 reader；必須重現原 S0 才允許 B |
| B 分離圖 | 同一 NumPy 的整數座標切片，由既有 `dilation=0` 幾何重播的 15 個區域決定；15 次 reader。來源尺度與色彩不變，沒有額外調整引擎設定；內部縮放與 padding 仍由原生 reader 自動決定 |
| 接合 | 原生 `RapidOcrModel.__call__` 執行 quad→TextCell 映射；之後原生 PDF／OCR merge、layout postprocess、table 無表早退、PageAssemble、ReadingOrder、DoclingDocument、Markdown 重播 |
| 不執行 | 0 API／VLM、0 重試、0 新 Heron 推論、0 表格模型推論、0 下載或升版、0 SDK 檔案修改、0 輸出修字、0 holdout 存取 |
| 上限 | 各組含 imports／初始化／證據保存最多 180 秒；sampled process-tree RSS 12 GiB、執行可用記憶體至少 8 GiB、啟動至少 10 GiB，共享 lock 與既有監督 |

本輪是**快取 layout 的元件消融與官方下游重播**。實驗 runner 暫時指定固定 OCR 區域並提供保存像素，沒有把內部框合併方法當成公開設定，亦沒有改正式產品流程。小圖會改變引擎內部縮放與上下文，因此結果支持裁圖介入有效，不能單獨定罪某個神經網路或保證跨文件修復。

身分與原假說：[registration.json](registration.json)、[原邊界追蹤](../pdf-core-ocr-boundary-trace-2026-10-19/report.md)。可讀產物：[A Markdown](A/document.md)、[B Markdown](B/document.md)。

## 結果與完整內容判準

來源先凍結為 **11 正文段落、1 左欄標題、2 註腳及 1 頁碼**；本頁沒有合法跨欄標題。評讀涵蓋全頁，不能只以 `foror` 消失、框不過中線或字元召回率判定正確。[凍結參照](reference.json)、[全文人工核對](manual-review.md)

| 指標／內容 | A 大圖 | B 分離圖 |
|---|---:|---:|
| Reader 呼叫 | 1 | 15 |
| 原始 OCR cells | 114 | 115 |
| 確認跨欄混合文字行 | **3** | **0** |
| 最終文件跨欄混合文字區塊 | **2** | **0** |
| 整段正文漏失／重複 | 0／0 | 0／0 |
| `2 OVERVIEW` 標題 | 正確保留 | **整個遺失** |
| Background 定義首行 | **嚴重毀損，既有缺陷** | **同類嚴重毀損，仍未解** |
| 最終正文閱讀順序 | 不合格，混段且跨欄接續 | **仍不合格；P06 提前，4 對錯序** |
| 頁碼 `3` | 文件保留；Markdown 排除 furniture | OCR 即遺失，列次要缺失 |
| 終局 | 不合格，重現原缺陷 | 不合格，診斷介入有效但不能部署 |

其餘 10 個正文段落、P04 第二行至末行與兩註腳在 B 均保留一次。P11 原頁本來就以 `and` 結尾、接續下頁，不計漏失。引號、字體、項目符號與上標等義差異沿用既有容忍；整個標題、定義首行及四對正文錯序屬重大偏差。Anchor 分數僅供定位，短末行的低覆蓋假警報已逐項目視解除，沒有拿它當 CER 或合格率。

## 因果定位

### 1. 大圖混行在文字辨識之前已形成

A reader 001 的 detector 後處理框 indices **3、4、15**（零起算）已橫跨約 21–1417／1440 pixels 的預處理圖寬，對應左右欄的獨立來源句；實際 recognizer 輸入與這三張 detector 裁圖逐像素一致。它們沒有被 classifier 實際翻轉。**混行已存在於 detector 後處理與裁圖邊界，非 recognizer 讀完後或 Markdown 才串接。**

配合前輪證據，鏈條為：Heron 原始候選不跨欄 → Docling 預設膨脹／連通區合併產生大裁圖 → 此輸入下 RapidOCR detector 形成跨欄文字框 → recognizer 辨識已混合的圖。

本輪保存的是後處理 quad 與實際裁圖，沒有追神經網路的原始 probability map；不能再指認是 detector 權重或 DB 後處理哪個閾值造成。

### 2. 分離圖的標題漏失發生在文字偵測

B reader **007** 收到完整、清楚的 `2 OVERVIEW`，尺寸 **210×36**（寬×高），預處理前後像素相同。原生 detector 回空，沒有後續文字裁圖、分類或辨識，最終 boxes／texts／scores 全 null；worker log 保存 `The text detection result is empty`。這不是辨識後因低分被濾掉。

[實際標題輸入](B/trace/images/53180bec48f9e0c1401ab24b107e3e087db11bfb4c957673372ce8b69f1826a4.png)、[空結果](B/trace/reader-007/result.json)。頁碼 reader 001 亦回空。尚不能區分小圖上下文、內部縮放與偵測門檻的影響；本輪不追加 padding 搜尋。

### 3. Background 首行有獨立、既有的方向誤判

原圖為正向且完整的 `Background. Typically, large language models (LLMs) refer`：

| 組別與行 | Classifier | 實際行為 | 辨識輸出 |
|---|---|---|---|
| A reader001 index39 | 180°，0.9755 > 0.9 | 像素確認精確翻轉 180° 後送 rec | `Bs  a    ler`，rec score 0.61771 |
| B reader009 index0 | 180°，0.9540 > 0.9 | 像素確認精確翻轉 180° 後送 rec | `Bt ) at  a d, ee`，rec score 0.52257 |

兩個辨識分數皆高於 text_score 0.5，錯字被保留。**這是兩組都存在的缺陷，不是 B 新引入。**本輪已定位錯誤旋轉，但未做關閉 classifier 的對照，不能聲稱關掉就一定辨識正確。

分類前：

![B 原生文字裁圖，正向](B/trace/images/8b8432ad99ee764e320f03b040526d28cece1d0232ba5f1146690a56e937825d.png)

送入辨識器：

![B 分類器旋轉後，倒置](B/trace/images/fee946e50c39677403e48c03491c77a34eb9d6b0ec4ada649dbad9c473f1c5ed.png)

### 4. 分欄段落正確後，ReadingOrder 仍建立錯誤連邊

B 的官方 OCR merge 只重編 109 個 cell index；**115 個 cell 的文字、座標、信心及清單順序皆不變**。Layout postprocess 與 PageAssemble 保留獨立的左右欄段落，沒有再混段。其清單仍是來源 cell 的儲存順序，這一步不以語意順序驗收。

最終 ReadingOrder 的 `_init_l2r_map` 因 P01／P06 的輸入 CID 相鄰、垂直 IoU **0.84937 > 0.8**、且 raster PDF 沒有向量分隔線，建立 P01→P06 的左右接續。`_init_ud_maps` 再將 P02 的前置節點沿此關係改為 P06，形成 **P01→P06→P02**。未改規則的原生幾何重播與保存文件順序逐值相同。

因此 B 的最終順序仍為 `P01, P06, P02, P03, P04, P05, P07, P08, P09, P10, P11`，P06 錯放在 P02／P03／P04／P05 之前。這是獨立的閱讀順序接點，不能只換 OCR 就假定會解決。[完整下游證據](downstream-findings.json)

## 成本

| 實測，秒 | A 大圖 | B 分離圖 |
|---|---:|---:|
| 整個 worker，含 imports／初始化／保存 | 7.389 | 9.237 |
| OCR 模型初始化 | 0.168 | 0.114 |
| 有觀測與證據保存的 OCR 區段 | **4.291** | **6.211** |
| Reader 原生回報 det／cls／rec 合計 | 3.978 | 5.274 |
| 原生回報 detector | 0.779 | 2.107 |
| 官方下游含頁面準備／組裝／輸出 | 0.200 | 0.198 |
| Sampled peak process-tree RSS | 2.447 GiB | 3.849 GiB |

B 的觀測 OCR 區段約增加 **45%**；這次拆圖沒有帶來省時。兩組都有證據保存成本，且是各一次觀測；原生 elapsed 不涵蓋空輸出的完整耗時，不能當純模型精密 benchmark。這些數字**不是完整 StandardPdfPipeline ingest latency、p95、吞吐 SLO、GPU 或公司部署表現**。1＋15 是 reader 呼叫，不是神經網路 forward 次數。

[A 成本](A/execution.json)、[B 成本](B/execution.json)、[機器可讀分析](analysis.json)。

## 評讀器修正與證據有效性

啟動前 13 項零模型測試及官方下游完整逐值重播通過；但評讀器初版只遍歷公開 JSON alias `$ref`，漏了 SDK 原生 `cref`。A 推論後、B 尚未開始時發現：原始 cells 評讀有效，文件評讀錯為空。**A 的 boxes／texts／scores／cells／DoclingDocument／Markdown 都已完整重現舊 S0，資料收集仍有效，沒有重跑 A。**

最小修正只支援官方兩種 reference key 並拒絕矛盾值，新增真實原生／alias 非空及全份等價控制；參照、模型、裁圖、閾值及判準未變。原程式、註冊檔與初次評讀全部保留；註冊以具名 amendment 更新，確認 A 已收集的 **251 檔**雜湊不變，再開始 B。修正後共 14 項零模型控制（6 capture＋8 scorer）通過。這揭露了初始 preflight 的真實序列化覆蓋缺口，不能把修評讀器當模型品質改善。

- [原註冊](registration-before-evaluator-schema-amendment.json)與[具名修正／A 封存](evaluator-schema-amendment.json)。
- [A 原文件評讀，無效版本](A/score.json)與[A 最終評讀](A/score-schema-amended.json)；[B 最終評讀](B/score.json)使用相同新版 evaluator。
- 凍結 reference 的 P01 `continues_from_previous_page` metadata 過寬；P01 是新段落，只有 Introduction 章節承接前頁。此欄未參與評分，正文、段落數與順序均未改；已在人工核對澄清。

## 決策與停止

三個原假說都有具體邊界證據：裁圖介入能消除本頁混行；OCR 內有偵測空結果與錯誤方向翻轉；下游另有閱讀順序問題。**保留這項偏差不可接受，拒絕本次零膨脹配置，停止本輪。**沒有因結果失敗再開第三種裁圖、padding、prompt、關 cls、升版或替代引擎。

後續若續驗，應先把官方 OCR 元件選擇與 pre-OCR／ReadingOrder 的可維護接點分開取捨。Tesseract 或單純關 classifier 都還只是未驗假說，不能因此宣稱完整配置可合格。本輪只交付原因與方法限制；未驗其他頁面、回歸集、GPU／高頻 ingest，也未解決或重啟 #84 其他分支。

唯讀重播：以既有 pinned Python 執行 `analyze.py --check`，核對凍結身分、原像素、16 次呼叫、錯誤翻轉、兩組同配置及保存分析；不載入推論模型、不覆寫資料。所有產物最終雜湊見 `artifact-seal.json`。
