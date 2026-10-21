# C1：Nemotron Parse 2.0 官方 VLM 候選計畫

日期：2026-10-17（Asia/Taipei）。僅規劃與靜態來源核對；沒有模型 import、權重下載／載入、推論、環境建立、安裝或 PDF／圖片／holdout 讀取。

## 假設與候選身分

C1 回答整套官方「模型＋parser」能否改善既有內容／來源位置缺口；不是把 MLX 量化結果當成公司 CUDA BF16 的效果或吞吐量。使用 `VlmPipeline`、`VlmConvertOptions.from_preset("nemotron_parse_v2", engine_options=MlxVlmEngineOptions())`，不接專案自訂 continuation，不換 OCR／TableFormer，也不增加修字／重建 parser。[Docling 固定版 preset](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py#L1313)

具名設定：**C1-nemotron-v2-mlx8-s2-native**。MLX repo 為 `mlx-community/Nemotron-Parse-2.0-8bit`；repo 自述來自 `nvidia/NVIDIA-Nemotron-Parse-2.0`，decoder 8-bit affine/group64，vision BF16，並非所有參數皆 8-bit。轉換卡未提供 parent 的不可變來源 SHA，因此只確認模型家族，不聲稱對應 NVIDIA 最新 snapshot。[轉換者模型卡](https://huggingface.co/mlx-community/Nemotron-Parse-2.0-8bit)

HF 檔案列表的 commit URL 暴露目標 SHA **`e7e89479657fb3631028ac12b6bc0d5a59ceafe4`**；其固定版檔案／metadata 此次因 web cache miss／受限網路無法取回。它是**待 preflight 核對的固定目標，尚非已封存且驗證的 checkpoint**。下一次先以 metadata-only 請求確認 SHA、config、processor、generation config、檔案清單及 hashes，再固定 `model_spec.engine_overrides[MLX].revision`；不可退回 `main`，取回失敗就記錄 runtime 未就緒。[MLX repo 檔案列表](https://huggingface.co/mlx-community/Nemotron-Parse-2.0-8bit/tree/main)、[觀察到的 commit URL](https://huggingface.co/mlx-community/Nemotron-Parse-2.0-8bit/commit/e7e89479657fb3631028ac12b6bc0d5a59ceafe4)

NVIDIA repo 此次觀察到 `b6742064f4a8cf22a10383ece5e7fbead355ac04`，僅作 parent 身分參照，不是上述轉換的已證明來源 revision。轉換 repo 的 license metadata 與 parent 的 OpenMDW-1.1 不同，正式部署應保留 parent 聲明，不以 conversion tag 取代來源條款。[NVIDIA 固定 commit](https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-2.0/commit/b6742064f4a8cf22a10383ece5e7fbead355ac04)

## 唯一配置與實際有效設定

| 項目 | C1 設定與驗證界線 |
| --- | --- |
| Pipeline／輸出 | `VlmPipeline`；`ResponseFormat.NEMOTRON_PARSE_V2` 官方 parser，完整 `ConversionResult`、Docling JSON、Markdown 均保存 |
| Backend／頁面 | `PyPdfiumDocumentBackend`；與固定新輪 baseline 同一 PDF 原始檔，`page_range` 為原文件 1-based inclusive；SEAL **p2–4 在一次連續三頁 conversion** 中處理，不拆檔／重編頁號；WikiSkill亦連續處理p20–22。完整來源以[主計畫](../pdf-core-native-round-plan-2026-10-17.md)的11頁為準 |
| Prompt | `</s><s><predict_bbox><predict_classes><output_markdown><predict_no_text_in_pic>` 原樣固定；不能改成通用 OCR prompt；圖片內文字仍未承諾涵蓋 |
| Render／輸入 | `images_scale=2.0`、`vlm_options.scale=2.0`、`max_size=None`，保留官方設定；實際逐頁 width/height/pixel hash 與 processor canvas 另記 |
| Decode | 官方 cap `max_new_tokens=9000`；`temperature=0`、`stop_strings=[]`；單請求、page batch 1、無 retry／prompt tuning／補跑選佳 |
| MLX 差異 | Docling 只傳 `max_tokens=9000`、`temp=0`，沒有傳一般 `extra_generation_config`；實際 mlx-vlm 使用 `temperature`，目前 greedy 依庫的預設 0 成立，不能聲稱非零值可由此設定 |
| Penalty／special tokens | MLX 呼叫沒有傳 repetition penalty；mlx-vlm 預設為 `None`，generation-config 載入白名單亦不含 penalty。**不得寫成 Transformers／vLLM 的 1.1 已生效**。`skip_special_tokens` 未傳，現有庫預設 False；類別／座標 token 須保留供 parser |
| 個別停止原因 | MLX engine 目前將自然結束留作 `unspecified`，也未把 iterator 的終止 metadata 向上完整傳遞；不能把這個值當 EOS 證據。輸出 cap 命中、截尾／不完整 envelope、錯誤皆單列，不能算成功 |

來源：[preset／engine overrides](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py#L1313)、[Docling MLX 實際呼叫](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/inference_engines/vlm/mlx_engine.py#L252)、[MLX 0.7.8 generation](https://github.com/Blaizzy/mlx-vlm/blob/v0.7.8/mlx_vlm/generate/ar.py)、[generation-config 白名單](https://github.com/Blaizzy/mlx-vlm/blob/v0.7.8/mlx_vlm/utils.py)、[MLX dispatch](https://github.com/Blaizzy/mlx-vlm/blob/v0.7.8/mlx_vlm/generate/dispatch.py)。以上 MLX 內容同時已讀取既有 runtime 的對應原始碼；公開 tag URL 為重查入口，未把尚未比對的 Git tag 當作 installed wheel 的獨立 hash 證明。

## 影像上限與公平比較

NVIDIA 建議最大輸入為 **寬1664×高2048**，最低建議1024×1280；其預設 control prompt包含 bbox/classes/Markdown。MLX handler 同樣把影像依比例縮小至 `(height2048,width1664)` 再置中補白，**不自動放大小圖**；Docling bbox parser 以相同 canvas 反算座標。[NVIDIA 模型卡](https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-2.0#inputs)、[MLX processor](https://github.com/Blaizzy/mlx-vlm/blob/v0.7.8/mlx_vlm/models/nemotron_parse/processing_nemotron_parse.py)、[Docling 座標轉換](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/nemotron_parse_utils.py#L113)

本輪保留 scale2 以避免同時改 render：Letter 頁約1224×1584、A4約1191×1684，通常低於上限；細小字可能未用滿 vision canvas，是已知取捨。橫式／超大頁會被 processor 縮小。若未來要測更高 render scale，必須另列設定且重跑對照；本輪不依逐頁錯誤調解析度。`max_size=2048` 只限制最長邊，不能代替1664×2048雙邊界，因此這輪不額外設它。[Docling `Page.get_image`](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/base_models.py#L528)

## 現有 runtime 與 preflight

只讀套件 metadata 得：`<tmp>/pdf-core-g2-dots-mlx-20261016/venv` 有 docling-slim2.132.0/Core2.99.0/Parse7.22.3、pypdfium2 5.14.0、mlx-vlm0.7.8、mlx0.32.4、Transformers5.20.0、Torch2.14.0、NumPy2.5.4、Pillow12.3.0。`mlx_vlm/models/nemotron_parse/` 靜態存在（config/model/language/vision/processor）；已高於 Docling MLX 最低0.6.17，但**檔案存在不等於模型 load／Metal／prompt／版本組合相容**。不默默安裝或用 Transformers CPU fallback；preflight失敗就記錄未就緒。來源為上述安裝目錄的 dist-info metadata 與 Python 文字，不是 model import。

下一次執行前依序：固定 metadata／processor與tokenizer → 檢查一致的配置、版本及 Metal → 先用公開純 parser 跑固定保真／bbox控制（非模型成績）→ 一次既有開發頁 smoke → 同一設定完成指定開發頁。pure parser 若有內容損失，列為已知交付失敗；只要有效輸入與VLM raw可保存，仍完成有界辨識比較，不把此項或舊續接失敗變成模型全面veto。只有runtime／capture／輸入不能成立才停止C1。smoke算11頁之一，不重跑。processor handler 目前會使用 task prompt 作 decoder seed；轉換卡0.6.12「prompt ignored」敘述不能覆蓋現有0.7.8程式行為，需在 smoke記錄實際 prompt/control tokens；不改 handler。[MLX decoder seed 接線](https://github.com/Blaizzy/mlx-vlm/blob/v0.7.8/mlx_vlm/models/nemotron_parse/language.py#L264)

## 證據、停止線與不可外推事項

- 公開結果接點 `result.pages[*].predictions.vlm_response` 保存完整 `text`、page_no、time、num_tokens、stop_reason、errors；連同 source/page/render/config 身分保存，再匯出完整 JSON／Markdown。這個欄位在官方 parser 讀取前就存在且保留，不需 override 私有方法。parser 的 `orig` 已是處理過的區塊文字，不能代替完整 raw。[公開模型欄位](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/base_models.py#L391)、[模型輸出存入 page prediction](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/vlm_convert/vlm_convert_model.py#L336)、[逐頁 parser 接線](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/vlm_pipeline.py#L455)
- 原生 parser 會清除特定 formatting tokens、把一般 Markdown攤平成文字；未認得類別回退 TEXT，沒有專門 CodeItem分支；Table以LaTeX轉換、Chart以Markdown table轉換。**raw、typed JSON、Markdown分開評分**，不能因 raw對就宣稱交付對，也不為了通過加自訂parser。跨頁原生逐頁concatenate仍須真實驗證。[完整 parser](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/nemotron_parse_utils.py)、[多頁接線](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/vlm_pipeline.py#L310)
- 建議停止預算：metadata/preflight最多30分鐘，計入主計畫共同準備2小時上限；模型load最多5分鐘；單頁range180秒，連續三頁range watchdog最多540秒，總C1模型階段最多45分鐘；達cap／timeout／incomplete保留原結果，不增cap重試。這些是研究資源界線，不是產品SLO。
- 依既有硬體紀錄為M5 Pro/48GiB：建議單worker、RSS20GiB停止、Metal allocator18GiB/cache256MiB、system available<8GiB停止，不關閉使用者程式／提高系統限制。上限須在實際load前核對可用記憶體；不夠就停止。舊DOTS的12GiB上限不盲套；轉換者報告別台32GB M2Pro約14.5GB峰值，只是風險參考，非本機實測。[既有硬體紀錄](../pdf-core-g2-dots-mlx-2026-10-16.md)、[轉換者量測](https://huggingface.co/mlx-community/Nemotron-Parse-2.0-8bit#measured-fidelity)
- 本輪只選此8bit設定，不擴BF16／4bit、prompt sweep或CUDA候選；若出現parser交付缺口，仍可界定模型raw內容改善，但完整需求判定照列不合格。預設`predict_no_text_in_pic`對NCCU圖片文字是此配置的已知路由限制，缺漏須列未提供，不能外推成模型所有OCR任務均失敗，也不為該頁改prompt。MLX latency不代表vLLM吞吐或高頻ingest容量。

未檢查權重、實際load與推論；目前只能稱「有靜態接線、待revision／執行前檢查的候選」，不能稱已兼容或已改善。
