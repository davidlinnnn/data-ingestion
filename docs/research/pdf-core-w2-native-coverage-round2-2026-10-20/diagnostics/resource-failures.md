# 六篇 RSS stop：metadata-only 定位

P03／P06／P10／P16／P18／P20 都只有 `conversion.json` 的 `rss_stop`、`retries=0`；沒有完整 `result.json`，因此不能進行 layout／reading-order／merge 重播。stage 為 **UNKNOWN**。`worker-00.log` 在 P02 成功後沒有 P03 的細部 stage；`worker-19.log` 在 P05 成功後只留下 `RapidOCR returned empty result!`，它不能證明 RSS 發生在 OCR，更不能定位頁碼。未做 isolated fresh-process 比較，不能證實或排除跨篇累積 retained state，更不能宣稱模型 memory leak。

以原 PDF、pypdfium2 的 `get_size`、`count_chars`、`get_objects`、`PdfImage.get_px_size` 檢查，沒有 rasterize 或 image decode。[完整逐頁資料](resource-pdfs.json)、[可重現程式](resource_pdf.py)。

| 論文 | PDF 頁數／尺寸 | 單頁最多 image pixels（加總） | 單頁最多文字字元／page objects | scale 2 每頁 RGBA 理論量 |
|---|---|---:|---:|---:|
| P03 Trace2Skill | 25；全頁 595.276 × 841.890 pt | 3,067,632（p2；2916×1052 圖） | 4,595／428 | 7.65 MiB |
| P06 SelfEvoSkill | 29；全頁 612×792 pt | 415,523（p2；17 張小圖） | 5,109／913 | 7.40 MiB |
| P10 ReasoningBank | 30；全頁 595.276×841.890 pt | 7,195,933（p10） | 詳見逐頁 JSON | 7.65 MiB |
| P16 Darwin Gödel Machine | 64；全頁 612×792 pt | 11,956,356（p61） | 詳見逐頁 JSON | 7.40 MiB |
| P18 Agent0 | 18；全頁 612×792 pt | 7,775,980（p2） | 詳見逐頁 JSON | 7.40 MiB |
| P20 Absolute Zero | 50；全頁 612×792 pt | 13,631,488（p2） | 詳見逐頁 JSON | 7.40 MiB |

六篇皆未發現異常超大實體頁。P03／P06 未見單張超大圖片；後四篇有較大的嵌入圖片，是否導致失敗仍 UNKNOWN。P03／P06 頁面 scale 2 RGBA 理論總和約 191.2／214.5 MiB；這只是像素算術，不含模型、中間 tensors、backend、OCR、table tensors、快取，不是 RSS 預測，也不能由此排除單一 stage 的大量配置。

前兩篇 metadata 診斷頁（只檢查 metadata 與原 text layer，尚非目視；不是失敗類型代表頁）：

- P03 p2：3.07 Mpx pipeline overview 圖；p1：15 張圖、1.06 Mpx；p4：`Table 1 | Main spreadsheet results`；p6：Table 2／3／4 caption 候選；p7：Table 5 與 Figure 4／5 caption 候選。
- P06 p2：17 張小圖、Figure 1；p4：11 張小圖、Figure 2、913 個 page objects；p1：468×468 單圖；p7：Table 1／2 caption 候選；p8：Table 3 caption 候選。

表格 caption 字串亦可能是正文引用，不能當作已識別的 table 框或失敗 stage。

RSS-stop 這一類只選 **5 張代表頁**：P20 p2、P16 p61、P18 p2、P18 p7、P10 p10，依單頁嵌入圖片像素總和排序；僅代表輸入規模，未證明是實際被殺所在頁。所有 216 個失敗文件頁面 metadata 另完整保存，`metadata_inspected_pages` 是查閱索引，不計為代表頁。

`execution.json` 0.1 秒程序樹 RSS 取樣：

| 論文 | 進入篇時首筆 RSS GiB | 文件期間峰值／最後一筆 GiB |
|---|---:|---:|
| P03 | 2.095 | 8.002 |
| P06 | 2.100 | 8.013 |
| P10 | 2.078 | 8.117 |
| P16 | 2.534 | 8.029 |
| P18 | 2.197 | 8.017 |
| P20 | 1.919 | 8.230 |

這些是各篇執行時 **同一 worker 生命週期的 process-tree RSS**，不是扣除前篇 retained state 的獨立 allocation peak。8 GiB 是 guard 門檻；取樣與終止有時間差，最高實際取樣 8.230 GiB，不能宣稱程序從未超過 8 GiB。逐筆時間與數值以 `execution.json` 及 `resource-pdfs.json.rss_samples` 為準。

## 官方 runtime／render 規模選項候選（未執行）

本輪 actual options 為 `images_scale=2`、`generate_page_images=True`、`generate_picture_images=True`、`generate_parsed_pages=True`、三個 stage batch 都 1、`queue_max_size=100`。

1. `queue_max_size` 可調小限制 inter-stage buffer；官方說明其目的是 backpressure／記憶體控制。這是較小變動候選，但未證明兩次 RSS stop 來自 queue。[固定版本 options](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:2263>)。
2. `images_scale` 可降低所保存 page/picture images 的尺度；`generate_page_images`、`generate_picture_images`、`generate_parsed_pages` 可減少保留資料。但會失去本輪回放／評讀依賴的 artifact，不能直接套用本次研究；須先決定產品保存契約。[官方 options](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:2148>)、[keep_images](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/pipeline/standard_pdf_pipeline.py:602>)。關掉 export flags 不等於完全停止 render：preprocessing 仍固定要求 scale 1 頁圖，再按 images_scale 取圖。[官方 preprocessing](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/page_preprocessing/page_preprocessing_model.py:98>)。
3. `ocr_options.scale` 控制 OCR crop render 尺度（官方預設 3），與 `images_scale` 是不同選項；改它可能影響嵌圖內文字覆蓋，不可無驗證宣稱安全。[官方 OCR option](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:246>)、[RapidOCR crop render](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/ocr/rapid_ocr_model.py:684>)。本次僅核對既有 baseline 如何運作，未新增 OCR 實驗。
4. `ocr_batch_size`／`layout_batch_size`／`table_batch_size` 目前均為 1，不能再減小；`document_timeout` 僅控制逾時，不是記憶體上限。未發現 PdfPipelineOptions 中可直接配置 RSS ceiling 的選項，本輪 8 GiB 仍依外部 guard。[官方 batch options](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:2220>)、[timeout](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:1355>)。

沒有重跑 conversion、沒有將任何候選變更套進 baseline；資源失敗根因仍 UNKNOWN。
