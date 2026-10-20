# 三組配置後的下一輪投資選項

2026-10-15。官方第一手來源短名單；**不是第4組登記，也沒有新增推論、安裝或放寬預算。** 若本輪三組仍沒有完整合格方法，建議停止追加 generic VLM 的 DocTags prompt／後處理，讓使用者決定是否投入另一輪「文件專用模型＋官方原生輸出」驗證。這不是所有模型已窮盡或 Docling 準度上限已到；Granite-Docling-258M／CodeFormulaV2 的既有有界失敗保留，MinerU 依已明示的商用考量排除。

## 兩條尚未在本案實測的路徑

| 優先方向 | 與強迫通用 VLM 產生 DocTags 的差異 | 官方接點／版本與實際限制 |
|---|---|---|
| **1. dots.ocr 原生 layout JSON → 官方 VlmPipeline** | 模型本身面向文件 layout／順序／內容；原生輸出含 bbox、類別與文字，公式用 LaTeX、表格用 HTML，其餘用 Markdown。不是請 GPT 模仿另一模型的特殊 token grammar。[官方模型卡](https://huggingface.co/dots-studio/dots.ocr) | 已核對 **Docling v2.132.0** 有 `dots_ocr` preset、`ResponseFormat.DOTS_JSON` 與專用 parser 分支；不是目前實測的2.102 stack。Preset仍寫 `rednote-hilab/dots.ocr`，其官方HF頁現轉址 `dots-studio/dots.ocr`，執行前須固定真實 repo／revision與相容 lock。Source另明示 Transformers 5.x 可能產生錯座標、vLLM路徑不受同一問題影響；優先公司 GPU／vLLM，CPU可行性與本機時間均未驗，不能只換model字串即跑。[固定tag preset](https://raw.githubusercontent.com/docling-project/docling/v2.132.0/docling/datamodel/stage_model_specs.py)／[固定tag pipeline](https://raw.githubusercontent.com/docling-project/docling/v2.132.0/docling/pipeline/vlm_pipeline.py) |
| **2. PaddleOCR-VL 原生流程 → saved JSON → DoclingDocument** | 先由 Paddle 自己的 layout／區域辨識流程產生結果，再走官方匯入；不是 Standard 裡把TableFormer flag改成Paddle，也不是將OpenAI回應冒充Paddle。[Paddle官方流程](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html) | Docling **moving main** 的真實範例 `paddleocr_vl_result_to_docling.py` 呼叫 `parse_paddleocr_vl_result`；只匯入已產生的單頁結果，範例本身不執行模型，針對 PaddleOCR-VL1.6／PaddleX3.7.2 schema。**本次未確認最早可用release，不聲稱2.102／2.132已具此converter。** 原生單頁像素座標、無Paddle多頁重組等價、JSON不含圖像bytes，仍須驗來源映射／圖片交付。[官方範例](https://raw.githubusercontent.com/docling-project/docling/main/docs/examples/paddleocr_vl_result_to_docling.py)／[官方adapter](https://raw.githubusercontent.com/docling-project/docling/main/docling/utils/paddleocr_vl_utils.py) |

Paddle的候選 checkpoint **`PaddlePaddle/PaddleOCR-VL-1.6`** 已有官方模型卡；不是沿用舊名稱猜出版本。官方文件列出CPU與GPU路徑，但此Mac的CPU安裝、記憶體與時效未驗，不能由支援清單推定可負擔。依原約定先做可負擔的CPU有界smoke，不適合再移公司GPU。上述兩條的官方模型卡分別標示MIT／Apache-2.0；此處未另做公司法務適用判定。[Paddle模型卡](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6)

## 建議與真正的決策

**建議只選第一條開下一個有界週期，Paddle保留替代，不同時展開兩條。** 這個優先順序是工程取捨：dots已有固定tag的原生VlmPipeline／parser，較適合先檢驗能否減少自訂接點；不是來源準確率排名。Paddle adapter則已有明確的多頁／圖片／algorithm映射邊界，尤其不能從「可匯入公式」推論全文inline與code縮排已符合F13／F14。

下一輪先做模型專屬格式／參數／parser無推論預檢，確認保留必要inline LaTeX、code字面值／縮排與來源，再登記**一個**具名模型／方法，以固定8頁、41個來源單位及四個既有正例比較。失敗、缺件與旁支退化保留；必要內容仍錯就記no-go，不加猜字串補丁。不看holdout挑方法，也不以文獻benchmark取代本案原稿核對。

若三組固定預算已用完，需使用者決定的是：**授權一個新的專用文件模型驗證週期與必要資源，或在此收束並記錄G2尚有必含能力缺口。** 停止不代表已達需求，也不默默刪F13／F14。當前OpenAI作Qwen3-VL暫代已獲允許，公司資訊不是本輪proxy比較的阻擋；但測試另一個專用checkpoint，須真正執行該checkpoint，OpenAI不能代證其品質或效能。

若啟動新週期並擴大模型搜尋，先補與六份custody holdout隔離的validation群組；既有八頁繼續作開發／回歸，不改稱未見資料。不得用holdout挑模型，也不藉新週期名稱直接重設本輪三組預算。

本文件只查官方文件／tagged source／模型卡，未下載權重、驗CPU／GPU或新增API請求；尚未有任何新候選的本案準度或latency證據。
