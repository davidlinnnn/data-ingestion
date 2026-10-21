# PP-OCRv5 server 官方接點驗證 — 2026-10-20

**本輪於第一頁轉換觸發既定資源護欄而停止，準度結論仍為 `INCONCLUSIVE_RESOURCE_STOP`。沒有完成七頁比較，不能宣稱此配置通過、品質失敗或改善雙欄。**

模型已正確載入；一頁嘗試、零完整頁面結果、零頁面推論重試、零 API／VLM／GPU。其餘六頁回歸與六頁額外驗證均未啟動。依固定停止條件，不放寬預算、不另加候選，也沒有重跑 C10。

## 固定配置及實際載入

Docling2.132.0／Core2.99.0／Parse7.22.3、RapidOCR3.9.2／ONNXRuntime1.24.3；StandardPdfPipeline、PyPdfium、Heron固定revision，沿用官方 DEFAULT OCR選區與原生 assembly／ReadingOrder。CPU4、PyTorch inter-op1，layout float32／compile=False。TableFormer原設定保留，code／formula／picture enrichment關閉。

僅替換原R0的 det／rec權重及匹配的版本／大小metadata；配置逐欄斷言，其餘不變。這是 Docling公開模型路徑與RapidAI模型選擇參數的組合，**不是Paddle完整pipeline，也不是聲稱Docling內建具名preset**。

| 項目 | 實際載入 |
|---|---|
| Detection | `ch_PP-OCRv5_det_server.onnx`，88,118,768 bytes，SHA256 `0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad` |
| Recognition | `ch_PP-OCRv5_rec_server.onnx`，84,577,022 bytes，SHA256 `e09385400eaaaef34ceff54aeb7c4f0f1fe014c27fa8b9905d4709b65746562a` |
| Line orientation | 原 `ch_ppocr_mobile_v2.0_cls_mobile.onnx`，開啟；沒有替換或停用 |
| Execution providers | det／cls／rec皆只有CPUExecutionProvider |
| Dictionary | 模型自帶ONNX metadata：18,383字元，CTC decoder18,385；保存字典與hash |
| OCR settings | scale3、text_score0.5；det mean/std皆0.5、short-side736／min、thresh0.3、box_thresh0.5、unclip1.6、use_dilation=True；保留RapidOCR預設，未調參 |
| Batches | Docling OCR／layout／table batch1；**RapidOCR內部cls／rec batch6**，與原配置相同。兩層batch不同，不能由前者推論後者為1 |

實際模型URL與預期hash取自已安裝RapidAI3.9.2官方registry，下載後核對；不是從範例舊檔名猜出模型。版本tag不當作不可變內容識別，實際bytes由SHA鎖定。模型檔位於`<tmp>/pdf-core-v5server-20261020/`，不重複放進repo。

[Docling官方範例](https://docling-project.github.io/docling/_generated/examples/rapidocr_with_custom_models/)、[RapidAI3.9.2官方版本／大小參數用法](https://rapidai.github.io/RapidOCRDocs/v3.9.2/install_usage/rapidocr/how_to_use_ppocrv5/)。範例提供接點依據，不提供本資料集品質保證。

## 中止原因

| 觀測 | 數值 |
|---|---:|
| 啟動後首筆系統available memory | 12.76GiB |
| 最後一筆系統available memory | **7.982GiB** |
| 固定available floor | **8GiB** |
| sampled程序樹RSS峰值 | 8.70GiB |
| 固定程序樹RSS上限 | 12GiB，未觸發 |
| 初始化時間 | 1.762s |
| 本次parent總時間 | 9.450s；含imports／init／部分第一頁，不是頁面延遲 |

最後available為8,570,470,400 bytes，低於8,589,934,592 bytes下限。elapsed不到10秒，未觸發180秒階段／900秒profile時限，RSS也未達12GiB；因此可明確定位為**整台主機available-memory護欄**。`exit_code=-9`是監督程式主動停止程序組，沒有證據是系統OOM killer。

尚未寫出`result.json`／`document.json`／Markdown，沒有可供人工評讀的最終候選內容。監督取樣不指出是哪個神經子模型造成尖峰，不能歸因det或rec，也不能由一次受其他應用占用影響的主機餘裕，斷言48GiB Mac永遠無法執行此模型。

## 前置檢查與完整性

推論前沿用來源evaluator，C10正確12單位讀序／FULL_PAGE五個反轉的正負控制，以及部分行重複的正負控制通過。七頁來源、模型、runtime、runner、evaluator與額外六頁的hash在第一頁前凍結。

兩個檢查問題均透明保留：

1. Synthetic repeat-control fixture漏了必要`schema_name`；evaluator在registration前拒絕。補齊fixture，沒有更改評分器。
2. 第一次初始化後，OmegaConf的`enum_to_str`產生`PPOCRV5`／`SERVER`名稱，而觀測斷言預期`PP-OCRv5`／`server`值，因此在零頁面推論時停止。用離線小控制重現，改為紀錄原enum的`.value`，保留舊runner／registration與初始化log，再於第一頁前重新凍結。候選options／權重沒有改變。

所以共兩次初始化，但**僅一次頁面嘗試、沒有頁面推論重試**。原先準備給七頁成功結果的`analyze`／`render`／`verify.py`未執行，沒有製造不存在的比較圖或分數。實際資源中止改由`verify_resource_stop.py`核對與封存。六份歷史artifact seal逐檔查核保持不變；沒有production改動。

## 決策與後續邊界

- 本輪標記資源中止、準度未知，不能把此候選加到「已驗過且品質不合格」名單。
- C10仍是既有讀序正向對照，其重複內容缺陷與自訂分區性質未改變。
- 若續測這個候選，應先在主機有較充裕可用記憶體或隔離資源的環境，**重新登記同一配置與尚未完成的比較**；不能稱作本次已完成，也不以改圖片尺度／換mobile／放寬護欄默默開新變體。
- 如能完成七頁，仍須照原準度界線來源評讀；通過才進六頁，失敗即停止。此次未產生任何一般化品質或正式latency／吞吐量結論。

資源紀錄 (`V5/execution.json`)、實際模型配置 (`V5/actual-models.json`)、結果判定 (`resource-review.json`)、凍結配置 (`registration.json`)、[固定計畫](plan.md)。

零推論複核：`rtk proxy <tmp>/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-ocr-v5server-2026-10-20/verify_resource_stop.py`
