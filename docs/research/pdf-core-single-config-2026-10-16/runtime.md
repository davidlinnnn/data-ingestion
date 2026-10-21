# 單一配置的 runtime 與官方接口查核

日期：2026-10-16。範圍僅為 Step 1 的靜態選型；未安裝套件、建環境、讀取 holdout、載入模型、呼叫 API 或執行 PDF conversion。查核使用兩個既有 Python 3.12.13 環境的 distribution metadata、已安裝原始碼及既有實驗的模型身分紀錄。這份筆記不建立新的品質或效能證據。

## 建議與可執行狀態

提案統一使用 **Docling-slim 2.132.0／Docling Core 2.99.0／docling-parse 7.22.3／pypdfium2 5.14.0** 的 released SDK 家族，以 `StandardPdfPipeline` 搭配**單一 `PyPdfiumDocumentBackend`**。選這個家族是因為同版已有正式 heading hierarchy、統一 VLM enrichment 及 chart API；不把較新原始碼拼回 2.102.0。以上是待鎖定的 runtime 基線，**不是目前已經能執行的完整配置**。[同版 options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py)、[Standard pipeline](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py)

既有較新環境實際裝的是 `docling-slim==2.132.0`，沒有名為 `docling` 的 distribution；Python 的 `docling` namespace 仍由 slim 提供。不能因先前 `VlmPipeline` 的 API/stub 實驗能跑，就宣稱 `StandardPdfPipeline` 所需 local models 均已備妥。

| 項目 | 既有 baseline 環境 | 既有 2.132 MLX 環境 | 本提案的處理 |
|---|---|---|---|
| Docling／slim | 2.102.0／2.102.0 | slim 2.132.0；完整 distribution 未裝 | 使用 2.132.0 SDK，不混版 |
| Core／Parse | 2.96.0／6.2.0 | 2.99.0／7.22.3 | 使用 2.99.0／7.22.3 |
| pypdfium2 | 5.13.0（舊實驗紀錄） | 5.14.0 | 使用 5.14.0，實際 backend 新增回歸 |
| IBM models | 3.15.0 | **缺少** | 2.132 的 `models-local`／`standard` metadata 要求 `>=4.0.2,<5`；不能複製 3.15.0 |
| Torch／torchvision | 2.14.0／0.29.0 | 2.14.0／0.29.0 | metadata 範圍可接受；import、ABI 與真模型執行尚未驗證 |
| Transformers | 5.8.1 | 5.20.0 | 5.20.0 符合 2.132 macOS 所列範圍；不等於所有 stage 實測相容 |
| Accelerate | 1.15.0 | **缺少** | local-model extra 要求 `>=1.0.0,<2`；inline-VLM extra 要求 `>=1.2.1,<2` |
| RapidOCR／ONNX Runtime | 3.9.2／1.24.3 | **均缺少** | 明確 ONNX OCR 路徑須另外鎖版；不依 auto engine 選擇 |
| Hugging Face Hub | 1.31.0（舊紀錄） | **2.2.0** | 2.132 local-model metadata 要求 `>=0.23,<2`，目前不符 |
| pandas／rtree／scipy／NumPy／Pillow | 舊實驗各自固定 | 3.0.6／1.4.1／1.18.1／2.5.4／12.3.0 | 存在；尚無整體 import／執行證據 |

選定 extras 的 metadata 檢查也顯示目前缺少 `httpx`、`einops`、`timm`、`peft`、`qwen-vl-utils`、`open-clip-torch` 等依賴，另有 office／CLI 依賴；**不因此全部安裝**。後續僅解析本配置實際需要的 extra／import graph，產生單一相容的完整 lock。`websockets==17.2` 不符 service-client extra 的 `<17`；若不使用該服務客戶端，這不是 PDF／API inference 的必要依賴。未在此任意指定未驗證的 transitive versions。

metadata 來源是 `<tmp>/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_slim-2.132.0.dist-info/METADATA`；舊環境套件／資產紀錄見 baseline method (`docs/research/pdf-core-g2-local-cpu-2026-10-14/runs/nccu-p3-native/method.json`)。

## 單一 backend 與 heading 的明確取捨

`PdfFormatOption` 的 2.132 **預設** backend 是 `ThreadedDoclingParseDocumentBackend`，因此提案必須顯式指定 `PyPdfiumDocumentBackend`，不能只寫「default PDF」。選擇依據是已封存的實際輸入檢查：`DoclingParseDocumentBackend` 在 validation-02 p1／p12 有黑色遮蔽，同版 PyPdfium 的相同來源可讀。這只支持選擇待驗 backend；不證明 PyPdfium 的全文、table cell 或 code 辨識品質。[format option](https://github.com/docling-project/docling/blob/v2.132.0/docling/document_converter.py#L270)、[既有 render preflight](../pdf-core-g2-preflight-2026-10-16.md)

同版 PyPdfium 可提供 `get_document_outline()` 和 `get_segmented_page()`，後者保存 `textline_cells`、頁面 geometry，`char_cells`／`word_cells` 留空。`StandardPdfPipeline` 接受這個官方 PDF backend；它在 assembly 前取得 outline，reading order 之後執行 heading hierarchy。[backend source](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/pypdfium2_backend.py#L587)、[assembly source](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L1047)

建議 heading 設定：`enabled=True, use_bookmarks=True, use_numbering=True, use_style=True, use_font_style=False`，並設 `generate_parsed_pages=True`，否則 style 會靜默跳過。保留同版 default `style_size_tolerance=0.05`，不依已看過的標題調參。PyPdfium 產生的是 generic `TextCell`，未供應 `PdfTextCell.font_name`，因此 **style 僅有 cell height 的字級代理，沒有 bold／italic 字型證據**；顯式關閉 font-style 分支以準確描述配置。書籤及編號仍可用；沒有訊號的 heading 維持既有 level。這些是靜態可用性，F03 品質仍須真實文件驗證。[heading options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L1923)、[style implementation](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/heading_hierarchy/heading_hierarchy_model.py#L269)

不設文件特例 backend fallback。舊 2.102／DoclingParse 的 native CPU 結果保留為歷史基線，不能直接轉成新 SDK／PyPdfium 的通過紀錄。

## 各元件可固定的身分與邊界

| 元件 | 同版官方接口／提案值 | 證據與必要限制 |
|---|---|---|
| Layout | `LayoutObjectDetectionOptions.from_preset("layout_heron_default")`；Heron `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；明確 Transformers／CPU，`compile_model=False` | 2.132 的 default 是 Heron RT-DETR R50；舊 `LayoutOptions` 已 deprecated。immutable asset 可沿用，**新 layout engine 品質及執行尚未驗證**。不改 Egret／ONNX 候選 |
| Table | `TableStructureOptions(mode=ACCURATE, do_cell_matching=True)`；TableFormer V1；`docling-project/docling-models@fc0f2d45e2218ea24bce5045f58a389aed16dc23` | 官方 V1 downloader 指向 `v2.3.0`；執行時給固定 artifacts。新版 IBM models 相容性未驗證；同版程式明確將 MPS table execution 改成 CPU。TableFormer crop scale 固定 2.0 |
| OCR | 明確 `RapidOcrOptions(backend="onnxruntime", lang=["ch"], force_full_page_ocr=False, bitmap_area_threshold=0.05, text_score=0.5)`；三個既有 ONNX 資產固定 bytes | 不用 `OcrAutoOptions`，不以 environment availability 改路線。RapidOCR 同一次只用第一個語言；`ch` 不等於繁中已驗收。det／cls／rec path 與 recognizer keys 必須鎖定並核對，否則禁止自動下載／改模型 |
| Code | `CodeFormulaVlmOptions.from_preset("codeformulav2")`，僅 code enabled；模型 immutable snapshot 由已封存 method 紀錄綁定 | native stage 可走統一 engine，包括 API，但固定 prompt 是 `<code>`，只選已標記 `CodeItem`。不能把 generic API 換入當作已驗證替代；也不提供 inline code 偵測 |
| Formula | `do_formula_enrichment=False` 在目前可辯護的基線；不代表需求降級 | 同一官方 stage 只選 `FORMULA` item；不會發現行內公式。既有 formula 缺口不得用開啟 flag 假稱解決，必須在主提案列為阻擋完整配置的必含缺口 |
| Picture／chart | 同版有 `DocumentPictureClassifierOptions`、`PictureDescriptionVlmEngineOptions`、`ChartExtractionVlmEngineOptions` 及 API engine | 有接口不是完成選型。chart 開啟會自動啟用 classifier；native chart stage 只處理 main classification 為 `bar_chart`／`pie_chart`／`line_chart` 的圖片。diagram／其他圖種沒有因此涵蓋 |

以上模型／接口來源：[layout presets](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py#L1011)、[table stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/table_structure/table_structure_model.py#L35)、[OCR options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L350)、[code/formula stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L70)、[common enrichment wiring](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/base_pipeline.py#L205)、[chart stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/chart_extraction/granite_vision.py#L42)。immutable model bytes 的既有來源為 baseline method (`docs/research/pdf-core-g2-local-cpu-2026-10-14/runs/nccu-p3-native/method.json`)。

既有 OCR asset SHA-256：

| 資產 | SHA-256 |
|---|---|
| `PP-OCRv6_det_small.onnx` | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` |
| `PP-OCRv6_rec_small.onnx` | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` |

## 設定不能替代實際 engine-input 檢查

本機提案明確 CPU、4 threads、layout／table／OCR batch 1、一次一份文件；`images_scale=2, generate_page_images=True, generate_picture_images=True, generate_parsed_pages=True`。這是有界比較基線，不是高頻 ingest 的正式吞吐量選型。API inference 在獨立遠端服務的 GPU 上執行，不受 local `AcceleratorOptions(device=CPU)` 限制；`enable_remote_services=True` 僅在登錄實際遠端 enrichment 後開啟。[Standard initialization](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L602)、[VLM engine options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/vlm_engine_options.py#L201)

需特別區分三個 scale：PDF page output 的 `images_scale`、stage option 中宣告的 `scale`、實際裁圖的 pixel bytes。2.132 的 `CodeFormulaVlmOptions.scale` 預設 2.0，但 `CodeFormulaVlmModel` 的 native crop 由 class `images_scale=1.67`、`expansion_factor=0.18` 控制；程式未讀該 option 的 scale。`BaseItemAndImageEnrichmentModel` 依 class scale 對 provenance bbox 裁圖。因此不得用 options JSON 宣稱真實 code crop 為 scale 2；必須在後續 preflight 攔截實際 engine input 核對。[code/formula class](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L70)、[crop implementation](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_model.py#L180)

## 原始碼身分與後續門檻

本次七個主要已安裝 source 的 SHA-256 均與 `docling-slim==2.132.0` distribution RECORD 相符：

| 相對 site-packages 路徑 | SHA-256 |
|---|---|
| `docling/datamodel/pipeline_options.py` | `befb3a4cf311fc9b3c551a97f15f1fe7b15f3f11c9e0338afd4f6a8f04821120` |
| `docling/datamodel/stage_model_specs.py` | `8b6a1513f9360e6b3e4b6e78c5b623908a4b4449f0d000f2fefd921e35607703` |
| `docling/pipeline/standard_pdf_pipeline.py` | `595185558770730dd59b0dc766d15f42eec4d531dd36f50d8a151c5446762846` |
| `docling/backend/pypdfium2_backend.py` | `2806889ebaa983891513c9709b478b2a91b13b888d6881586de464e48848c192` |
| `docling/models/stages/table_structure/table_structure_model.py` | `184a68adba5b7230713e1d58fdfba38f7e5bf6e4b7a2a50866efe9bf9942cf86` |
| `docling/models/stages/heading_hierarchy/heading_hierarchy_model.py` | `fc55f4b281138f5f43da04f7b55ac854b1a4316fb4b82e3830b0a114742d4b4e` |
| `docling/models/stages/chart_extraction/granite_vision.py` | `5a6a607569f47b6662ea36c6e14c30725ebfb50073f7a53d4061e5b3a8fc39db` |

後續必須先通過：最小依賴的相容 lock／import preflight；所有模型 asset 的固定身分／bytes；新 backend 的 text／heading／table 回歸；每個實際 crop 的輸入檢查；native output → Markdown＋補充結構的交付控制。這些門檻未過前不成立「單一完整配置」，也不執行新推論。Paddle 保持暫停。

本次未檢查 kernel、模型品質、CUDA／vLLM 或吞吐量。主要風險是 runtime dependency 修正與 backend 更換均可能改變結果，必須保留原基線並重新驗證。
