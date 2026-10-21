# C：來源診斷、全圖評讀補齊與官方 FULL_PAGE 比較

2026-10-18，Asia/Taipei。**一個官方 OCR-mode 變因改善 ReasoningBank 原始 caption，仍未解決 SEAL 的 native 圖框邊界。C 增強維持停止。**

## 先重現與定位

`source_trace.py` 的 `--check-baseline` 對兩個既有缺陷確實失敗：SEAL title 不在 picture bbox、ReasoningBank caption 含鄰文／重複。它是可重跑的 source-only 紅燈，不載入模型。

接著對同一 PDF／頁碼／native provenance 比較 `PyPdfiumDocumentBackend` 與官方預設 `ThreadedDoclingParseDocumentBackend` 的 segmented cells、矩形取文及最後 canonical 文字，見 `source-trace.json`。兩者都在 caption 區域讀到圖面上看不到的 `Better memory mechanism enables ...`／`Scaling yields better memory curation.`；PyPdfium 又有 bounded extraction 交錯／重複。這支持 native-text 路徑污染，並非只在最終 Markdown renderer 產生錯誤。

第一次 source probe 因 threaded backend 的 top-left frame 與 canonical bottom-left bbox 不同而拒絕；改用公開 `to_top_left_origin(page_height)` 後才採用最終 evidence。這是無模型的診斷修正，沒有重試推論或修改原 bbox。

SEAL title 原本就是另一個 section-header owner，位於 picture 上邊界以外。已有 Egret layout 候選也未納入此 title；本輪沒有重跑該失敗候選，亦未以 image scale／area filter 冒充框外內容恢復。

## 唯一候選與完整範圍

`registration.json` 在推論前固定 19 ranges／55 頁、全部來源 hashes、程式與資產、有效 options、預算及停止條件。Runtime 為 Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3、Python 3.12.13。

| 元件 | 本輪候選 |
|---|---|
| Pipeline／backend | StandardPdfPipeline／PyPdfium |
| Layout | 原 Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`，CPU FP32、threshold=0.3、compile=false |
| OCR | 原 RapidOCR PP-OCRv6 det_small／rec_small＋mobile_v2 cls；ONNX Runtime、text_score=0.5 |
| **唯一 options 變因** | `ocr_options.mode=AUTO → FULL_PAGE`；deprecated `force_full_page_ocr` 是其衍生欄位，不是第二個變因 |
| Table | 原 TableFormer V1 accurate、cell matching=true |
| 其他 | CPU4／interop1，batch=1、image scale=2、page/picture images on；code/formula、heading、classification、description、chart enrichment off |
| 預算 | 單一候選、concurrency=1、retry=0，1,500 秒／tree RSS 12 GiB／available 至少 8 GiB、啟動至少 10 GiB |
| 執行隔離 | 模型與資產均為本機鎖定版本，HF offline；worker 移除 OPENAI_API_KEY，不呼叫 API |

候選只是官方 `OcrMode.FULL_PAGE` 的正常用法；沒有 SDK patch、手工修 caption、來源圖號 routing、特殊 bbox 或文字正規化回填。

Producer 的 preflight 只核對 evaluator addendum 的 SHA 以封存 custody，不解析答案；converter 的輸入只包含原 PDF、固定頁段與 options。這是 exposed DEV 比較，不宣稱盲測。

## 結果

`execution.json`：19/19 ranges、55/55 頁 conversion success；exit 0，supervisor status=completed，無 retry。使用已回歸的 v2 `tree_rss` 容忍正常程序退出，AccessDenied 仍不當成功。

| 項目 | 實際觀測 |
|---|---|
| 全部 55 頁 conversion 合計 | 146.717 秒 |
| 初始化＋監督合計 | 151.273 秒 |
| Sampled peak tree RSS | 5,360,189,440 bytes |
| Native pictures | 29 |
| 新 remote／VLM／component enrichment calls | 0 |
| 相同 44 頁／12 ranges conversion | 原 S0 80.820 秒；本輪 117.880 秒，約 +45.9% |

時間為相同硬體與頁段的兩次順序實驗，不是重複 latency 分布或正式 SLO；其餘 11 頁原先使用 cache，本輪則全部 fresh，不混為 fresh 完整流程成本。

**ReasoningBank Figure 5：來源 caption 必要意義恢復。** 可讀到完整 Figure 5／WebArena-Shopping／不同 memory mechanisms／k=5／BoN 所有五條 trajectories／Pass@1 隨機選一條的內容。MaTTS 大小寫與斷行連字號差異屬既有 minor 容忍。評讀將候選與完整來源句比較，沒有只檢查「污染句消失」便判通過。

**SEAL Figure 1：圖像輸入邊界仍失敗。** Canonical 正文現在完整保留 `RL Outer Loop Iteration t`，但 section-header bbox 與 native picture bbox 仍分開，public `get_image()` 產生的圖片仍缺標題。見 實際 native crop (`candidate-seal-figure1.png`) 和 `comparison.json`。它不是整份 canonical 的 title 遺失，也不能聲稱後續只看 crop 的 OCR／description 看到了 title。

固定 55 頁均完成 source SHA／status／頁碼／輸出 integrity 比較；同時保存全部 text/table/picture counts、table shapes 和 cell-string 差異。這些差異會受 OCR 分詞、合併影響，**不直接當作數值準度或語意退步**。本輪不宣稱 55 頁全文逐字正確，也不以 conversion success 推定回歸無問題；僅已知 SEAL 的必要來源 gate 就足以阻擋候選晉升。

## 評讀缺口與後續界線

全圖 evaluator addendum (`evaluator-full-image-contracts.json`)補齊 NCCU screenshot 的 11 個完整 literal blocks／UI 關係，以及 timeline 的 45 模型、19 個黃色 open-source 標籤、全部年份／月份軸與可確定的連線。原頁與 native crop 已做兩次視覺核對；沒有獨立人工 annotator。模糊 logo 細字和缺個別連線的精確月份保留不確定，不從外部歷史知識補日期。

舊 source-contract-index、coverage、29 個 crop/image keys、58 個候選 request 及原 runner gate 都保留不可變。本 addendum 是後續 evaluator 記錄，沒有將舊 source phase 回寫為通過，也沒有把本輪 FULL_PAGE 輸出假接到原 image keys。

**停止決定：FULL_PAGE 不作全量預設，保留為 caption/native-text 路徑的候選；C 的 component OCR／description／chart 尚未啟動。** 下一個需要釐清的是：圖外但已保存的原生 title／同頁上下文，是否透過有 provenance 的跨 owner 輸入供圖像增強使用。既有 full-owner 方法對跨 owner 有限制，不能假設重用即可成功。若開新輪，須先凍結通用輸入方法與增量 pixels/tokens/calls，再驗證，而不是追加逐圖 crop padding 或文字修補。
