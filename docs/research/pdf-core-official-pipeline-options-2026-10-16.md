# PDF-core：Docling 官方 pipeline 與模型候選的界線

日期：2026-10-16。這是有界的來源盤點，不是新實驗結果。只讀取已安裝 Docling 2.132.0 的 Python 原始碼並核對官方固定版來源；沒有匯入推論模型、載入權重、安裝套件、建立環境、讀取 PDF／圖片／holdout 或呼叫模型 API。既有實驗是否覆蓋某組配置，應以既有報告與執行紀錄判定，不能從本筆記的「有官方支援」推成「已驗證有效」。

## 結論

可以驗證 Docling 其他官方模型與配置；不需要先開始 Paddle。把 Paddle 當成唯一下一步並不充分。PaddleOCR-VL 是 Paddle 的辨識 pipeline，Docling 2.132.0 提供的是**讀入已產生的單頁結果**的工具，並非 `VlmConvertOptions` 的原生模型 preset，也不執行 Paddle 的多頁 `restructure_pages()`。來源：[Docling 官方 importer](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/paddleocr_vl_utils.py#L4)。

PDF 的主要辨識方向是 `StandardPdfPipeline` 的元件組合，以及 `VlmPipeline` 的模型／輸出 parser 組合。其他名稱不都代表另一個能滿足全文要求的辨識方法。

既有證據已包含 Standard + Heron／TableFormer V1、V2／RapidOCR／CodeFormulaV2 的有界實測、Granite-Docling 258M 的真實官方 VlmPipeline CPU 實測、dots.ocr 的真實 VlmPipeline + MLX 12 頁及 2 次診斷，以及 generic `gpt-6-luna` + API engine + DocTags 的 low／medium 兩組固定 8 頁實測。新候選不撤銷舊結果，也不能推成目前已有完整合格 profile。覆蓋與限制見：[round 3](pdf-core-g2-round3-2026-10-14.md)、[inline](pdf-core-g2-inline-2026-10-15.md)、[dots MLX](pdf-core-g2-dots-mlx-2026-10-16.md)、[method selection](pdf-core-g2-method-selection-decision-2026-10-15.md)。

## Pipeline 身分

| 名稱 | 固定版的工作與適用範圍 | 對本需求的角色 |
| --- | --- | --- |
| `StandardPdfPipeline` + `PdfPipelineOptions` | PDF／影像的 layout、OCR、table structure、組裝及可選 enrichment；options 是配置，並非另一個 pipeline | 主候選家族；更換 layout、OCR、table、code/formula 元件是同一 pipeline 內的實驗 |
| `VlmPipeline` + `VlmPipelineOptions` | 對頁面執行 VLM，再按預期輸出格式選 DocTags、Markdown、Chandra HTML、DOTS JSON 等 parser；逐頁結果再串成文件 | 主候選家族；模型、engine、prompt、parser 必須一起固定 |
| `NativePdfPipeline` | 官方明確稱 model-free：取 PDF 內的 text cells／嵌入 bitmap；沒有 layout、OCR、table 模型，也沒有 reading order、heading、table 結構 | 可作 native text／速度診斷基線；不能當完整辨識候選 |
| `ExtractionVlmPipeline` | `DocumentExtractor` 依模板抽取指定實體／欄位；預設 NuExtract-2B，另支援 Granite Vision extraction prompt | 結構化欄位抽取，不能代替全文 canonical conversion；本需求目前延後內容 metadata 抽取，不優先 |
| `ThreadedStandardPdfPipeline` | 向後相容子類，直接繼承 Standard | 不是獨立模型／方法候選 |
| `LegacyStandardPdfPipeline` | 直接繼承 Standard，發出 deprecated warning | 不是可獨立比較的 legacy 演算法 |
| `SimplePipeline` | Word、PPTX、Markdown、HTML 等 declarative backend 的 conversion | 仍應在各自格式驗證，不能當 PDF 的替代 layout/VLM pipeline |
| `AsrPipeline`／`VideoPipeline` | 音訊／影片 | 不屬於這輪 PDF 模型比較 |

來源：[converter 的 format options](https://github.com/docling-project/docling/blob/v2.132.0/docling/document_converter.py)、[Standard](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py)、[VLM 實際接線](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/vlm_pipeline.py)、[Native options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L2326)、[extraction options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L1889)、[threaded alias](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/threaded_standard_pdf_pipeline.py)、[legacy alias](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/legacy_standard_pdf_pipeline.py)。

## 有意義的模型／engine／parser 組合

以下是固定版**已有接線**的部分代表，不是要求全部跑一遍。官方 preset 的模型 revision 多數預設 `main`，真正實驗仍須固定不可變 revision、engine 與套件版本。

| 家族或 preset | 模型身分與可用執行方向 | 結果路徑／限制 |
| --- | --- | --- |
| Standard layout | `layout_heron_default`／`layout_heron_101`，以及 `layout_egret_medium/large/xlarge`；Heron 預設另有 ONNX export，Egret 為 Transformers | layout 元件切換；不會因此改變成整頁 VLM，也不能保證找到所有 inline math/code |
| Standard code/formula | `codeformulav2`、`granite_docling` 的 code/formula stage | 對已選定區塊執行的 enrichment；不等於補出所有尚未辨識的 inline formula 或 code |
| `granite_docling` | `ibm-granite/granite-docling-258M`；Transformers、官方 MLX repo，亦有 API 路徑 | DocTags；官方 VlmPipeline 預設。已有實驗須沿用其正確身分，不可說未測 |
| `smoldocling` | `docling-project/SmolDocling-256M-preview`；Transformers、對應 MLX repo | DocTags；較小模型本身不代表超越已測 Granite，也不自帶跨頁正確性保證 |
| `glm_ocr` | `zai-org/GLM-OCR`（preset 名稱 0.9B）；MLX `mlx-community/GLM-OCR-bf16`、Transformers、vLLM/API | Markdown parser；可比較內容與速度，沒有區塊 bbox 輸出 |
| `lightonocr` | `lightonai/LightOnOCR-2-1B`；MLX `mlx-community/LightOnOCR-2-1B-bf16`、Transformers/API | Markdown parser；同上，不能獨自滿足細粒度來源定位 |
| `chandra_ocr2` | `datalab-to/chandra-ocr-2`，5.3B；MLX `mlx-community/chandra-ocr-2-oQ8` 要求 `mlx-vlm>=0.6.17`，另有 Transformers、vLLM、OpenAI-compatible 等 API 配置 | `CHANDRA_HTML` 專用 parser，含 bbox；有原生接線，但 weights 的 modified OpenRAIL-M 商用條件使其暫不排入本專案正式候選 |
| `dots_ocr`／`dots_mocr` | 固定版 repo 是 `rednote-hilab/dots.ocr`／`rednote-hilab/dots.mocr`；preset 預設 vLLM，另有 Transformers/API overrides | `DOTS_JSON` 專用 parser；不要把自訂 MLX 實驗說成官方 preset 已宣告 MLX export。已有 dots.ocr 實驗仍有效，須記錄其實際 repo／revision／engine |
| `nemotron_parse_v2` | `nvidia/NVIDIA-Nemotron-Parse-2.0`，官方稱 <1B；MLX `mlx-community/Nemotron-Parse-2.0-8bit` 要求 `mlx-vlm>=0.6.17`；Transformers>=5.6.1、vLLM>=0.20.0 | `NEMOTRON_PARSE_V2` 專用 parser，含 class、bbox、文字；較切合來源定位需求的新模型假說，尚未實測 |
| `mineru2_pro` | `opendatalab/MinerU2.5-Pro-2604-1.2B`；有 engine/version 約束 | `MINERU2` 專用 parser；官方有接線不撤銷本專案先前因商用授權排除的決定 |
| 其他已註冊 convert presets | `deepseek_ocr`、`granite_vision`、`pixtral`、`got_ocr`、`phi4`、`qwen`、`nanonets_ocr2`、`gemma_12b/27b`、`dolphin`、`falcon_ocr`、`unlimited_ocr` | 各有模型、engine、prompt、response format 約束；例如 `qwen` 的固定版身分是 Qwen2.5-VL-3B，不能等同公司 Qwen3 endpoint |

來源：[固定版 stage model presets](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py#L931)、[preset 註冊](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L1175)、[VLM engine 種類與責任](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/inference_engines/vlm/base.py#L34)。舊 `vlm_model_specs.py` 中單一常數／enum 的存在，不足以證明完整 two-stage pipeline 已接線；本筆記不把 `GRANITEDOCLING_2STAGE_TRANSFORMERS` 當成另一個已就緒的官方 pipeline。

有三個不能省略的限制：

- **模型 API 相容不代表輸出相容。** 公司 Qwen3 或暫用 OpenAI 可走官方 API engine，但 model ID、prompt、output format/parser 必須成立；不能改 model ID 後仍宣稱在測 Granite、GLM 或 Chandra 本身。暫用 OpenAI 的結果不能代表 Qwen3 準度或地端 latency。
- **一般 Markdown 的來源定位已知有限。** `_convert_text_page()` 對其產生的 item 設定頁號，但 bbox 與 charspan 都是零。GLM／LightOn 因而可回答辨識／速度問題，不能單獨回答區塊座標要求；若要補回，會另生整合成本。[實際程式](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/vlm_pipeline.py#L707)。
- **整頁不等於整份文件的語義續接。** `VlmPipeline` 先產生逐頁 document，再 concatenate；該接線本身沒有保證跨頁段落接對，更沒有保證所有 formula/code/table 都保真。必須用連續多頁與誤接負控制評分，不能加入原本失敗的自訂續接來掩蓋缺口。[逐頁組裝](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/vlm_pipeline.py#L312)、[concatenate 實作](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/base_pipeline.py#L112)。

模型授權須與 Docling 程式授權分開判斷。Nemotron Parse 2.0 官方模型卡標示 OpenMDW-1.1，並聲明可商用／非商用；Chandra OCR 2 官方模型卡列出修改版 OpenRAIL-M、營收範圍及較大商用部署另行授權等條件。這裡只記錄供候選篩選的官方聲明，不取代公司授權審查。[NVIDIA 模型卡](https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-2.0)、[Chandra commercial usage](https://huggingface.co/datalab-to/chandra-ocr-2#commercial-usage)。

## 建議的有界順序

1. **整頁 VLM 新候選：`VlmPipeline` + `nemotron_parse_v2`。** 先查 Mac MLX runtime／記憶體與固定 revision，合適才以一組配置跑既有開發樣本。它提供 class／bbox 與專用 parser，較一般 Markdown 切合來源定位需求；保留既有 Granite／DOTS／generic API 結果作參照。MLX 8bit 不能直接代表公司 GPU BF16 的準度／速度，跨頁、code/math 仍須照原要求評分。這是值得驗證的假說，不是已證明改善。
2. **Standard 只換一個 layout 候選：Egret medium 對固定 Heron baseline。** 用相同 backend、OCR、TableFormer、enrichment 與評分，回答已知遺漏是否受 layout 影響；CPU／既有 runtime 可行性先查，不同時擴張 OCR、table 與多個 Egret 尺寸。這是低整合成本的官方元件假說，未承諾改善。
3. **Paddle 保留為外部完整方法 challenger，另行啟動。** 若上述 Docling 官方方向無實質增益，且仍值得支付外部 runtime 與 importer 的成本，再用固定 Paddle 官方完整流程驗證。不能以我們的 adapter 控制失敗推論其模型準度，也不能以官方 importer 存在推論整體需求已滿足。

GLM-OCR／LightOnOCR 留作較後的內容／latency 比較；若沒有獨立需要回答的內容問題，不因為新增 preset 就全部跑。Chandra／MinerU 不因原生接線存在而重新跳過既有商用授權篩選。

這個順序是方法選擇建議；沒有啟動任何新實驗或解除 Paddle 暫停。停止條件維持固定評分、無樣本專用修字／閾值調整、內容與交付缺陷分列，並保留未開封 holdout。

## 可重查的本機來源

本次只讀根目錄：`/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling/`。以上 GitHub 固定版路徑對應同名檔案。重要接點為 `document_converter.py`、`document_extractor.py`、`datamodel/pipeline_options.py`、`datamodel/stage_model_specs.py`、`pipeline/vlm_pipeline.py`、`pipeline/base_pipeline.py` 與 `utils/paddleocr_vl_utils.py`。未以 import 方式建立 pipeline 或觸發任何模型初始化。
