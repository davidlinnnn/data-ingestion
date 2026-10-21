# G2 圖片分類：官方合約與 chart gate

查證日：2026-10-14。範圍限 Docling `2.102.0`／Core `2.96.0` 的分類與 chart gate；本筆研究只讀官方來源、已安裝原始碼及小型模型設定，未下載權重、未執行 inference。

## 固定模型與必要檔案

官方模型為 `docling-project/DocumentFigureClassifier-v2.5`，MIT，Google EfficientNet-B0 衍生的 **26 類**分類器。官方 live API 的 `main` 在查證時解析為 **`f859dfbff5c9916cd996942d4b0db7fa25808220`**，`lastModified=2026-04-01T07:41:07.000Z`。應固定此完整 revision；Docling `2.102.0` 的預設仍為可變的 `main`。[官方固定模型卡](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/README.md) · [官方模型 API](https://huggingface.co/api/models/docling-project/DocumentFigureClassifier-v2.5?blobs=true) · [Pinned preset](https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/stage_model_specs.py#L963)

| 檔案 | bytes | SHA-256 | 證據方式 |
| --- | ---: | --- | --- |
| `config.json` | 2,522 | `dbed0349fb8b12fad95d8ff7f43b062c40971e06d9d957b25e90d91dfd3bd77e` | 固定 revision 實際小檔案 bytes |
| `preprocessor_config.json` | 377 | `118dc069572036346fbacc3e15586089d3f8a9aaf9036c0c54b4666236a28032` | 固定 revision 實際小檔案 bytes |
| `model.safetensors` | 16,378,200 | `6bf1e44d6bce316dcade6eb9929d8f8d23b6e8d9d29062b3b4011cff87c7c3cd` | 官方 API 的 LFS SHA-256，未驗實際權重 bytes |
| `model.onnx`（替代 engine） | 16,940,439 | `27ffc48c27ae4e12c99b6f6de0dd730005245e47b70dd0c1339e62cbac3ec4c0` | 官方 API 的 LFS SHA-256，未驗實際權重 bytes |

最小 Transformers snapshot 為前三檔，共 **16,381,099 bytes**；ONNX 檔不屬此路徑必要檔。共同 engine 明確要求 `preprocessor_config.json` 存在，之後用 `AutoImageProcessor`、`AutoConfig` 與 `AutoModelForImageClassification` 載入本機目錄。[固定 config](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/config.json) · [固定 preprocessing](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/preprocessor_config.json) · [共用 loader](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/common/hf_vision_base.py#L75) · [Transformers loader](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/image_classification/transformers_engine.py#L99)

## 輸入、前處理與輸出

- Stage 啟用時接受 `PictureItem`；crop scale 為 `2`。圖片先轉 RGB，engine input 是 `ImageClassificationEngineInput(image=PIL.Image)`。[Stage](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/picture_classifier/document_picture_classifier.py#L65)
- 模型 config architecture 是 `EfficientNetForImageClassification`；前處理檔的 processor type 為 `ViTImageProcessor`，不可因此把模型當成 ViT。resize 224×224、rescale `1/255`、mean `[0.485, 0.456, 0.406]`、std `[0.47853944, 0.4732864, 0.47434163]`；model config 宣告 `float32`。[Config](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/config.json) · [Preprocessing](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/preprocessor_config.json)
- Transformers engine 對 logits 做 softmax，依 confidence 遞減排序；預設 `top_k=None` 回傳所有類別。類別依 `config.id2label` 的 **數字 ID** 對應，不能按字母重排。[Engine](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/image_classification/transformers_engine.py#L157) · [Label loader](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/common/hf_vision_base.py#L93) · [top_k 合約](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/image_classification/base.py)
- Stage 寫入 `PictureItem.meta.classification.predictions[]`，每筆包含 `class_name`、`confidence`、`created_by="DocumentPictureClassifier"`；預設亦保留 deprecated classification annotation。[Stage 寫回](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/picture_classifier/document_picture_classifier.py#L174)

26 個 ID 的完整順序：`logo, photograph, icon, engineering_drawing, line_chart, bar_chart, other, table, flow_chart, screenshot_from_computer, signature, screenshot_from_manual, geographical_map, pie_chart, page_thumbnail, stamp, music, calendar, qr_code, bar_code, full_page_image, scatter_plot, chemistry_structure, topographical_map, crossword_puzzle, box_plot`。沒有 literal `unknown` 或 `no-text` 類別。[固定官方 config](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/config.json)

## 原生 chart gate

`do_chart_extraction=True` 自動使 classifier enabled；enrichment 順序為 classifier → picture description → chart extraction。[Pinned pipeline](https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/base_pipeline.py#L153)

Chart stage 只接受啟用狀態下、具有 `PictureMeta.classification` 的 `PictureItem`，取 `get_main_prediction()` 後檢查 class name 是否為 **`bar_chart`、`pie_chart`、`line_chart`**。它不檢查 confidence 閾值、不看次佳類別，也不根據 OCR 文字量判定。`scatter_plot`、`box_plot`、`flow_chart`、`other` 或自訂未知字串皆不進入原生 chart stage。[Pinned gate](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/chart_extraction/granite_vision.py#L98)

Core `2.96.0` 的 `get_main_prediction()` 選最高的非 `None` confidence；相同分數保留先出現者；若所有 confidence 都是 `None`，選第一筆。因此低 confidence 的 chart 主分類仍通過 gate，高 confidence 的非 chart 主分類則不通過。正常 classification 要求至少一筆 prediction；缺少分類直接不通過 gate，不會 fallback 至未知類別。[Pinned Core selection](https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/items/picture/meta.py#L22)

**評估含義（由上列程式推論）**：須保留所有來源 crop、完整預測與是否通過 gate；分類成 `other`、無文字或低分都不能作為省略必含圖意的理由。已知真實 bar/line/pie 若主分類錯誤，原生 chart coverage 會先被 classifier 擋住；應與 chart 數值品質分開記錄。

## 版本核對與 readiness

已安裝路徑為 `docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages`。以下檔案已讀取官方 tagged raw source，與已安裝 bytes 比對 SHA-256，全部相同：

| 官方 tag／path | SHA-256 |
| --- | --- |
| Docling `v2.102.0` `models/stages/picture_classifier/document_picture_classifier.py` | `8505f656a80885bad37d789b4248e7b53c9721363ba345afe611637435cc35fb` |
| Docling `v2.102.0` `models/stages/chart_extraction/granite_vision.py` | `29d99b1c772956274e722eb2ed31e1b5be7184cdfe766376248587564c3b4040` |
| Docling `v2.102.0` `models/inference_engines/image_classification/transformers_engine.py` | `0f8cdaccfc771ae625d0ebfa5b72bacbb6641129df0d7843c81c7afb17711803` |
| Docling `v2.102.0` `models/inference_engines/common/hf_vision_base.py` | `c330f67a699ba6af51dde5ab24bdfbbd57c11f2e72d528831506ac7a0deb70bc` |
| Docling `v2.102.0` `datamodel/picture_classification_options.py` | `2eed1a0671ebcb8d55b57948563bcd08dab48f8b9d3332d24babdf6c3a8d8a5b` |
| Docling `v2.102.0` `datamodel/stage_model_specs.py` | `f7fa539b2b3c8681d9bb28df67d338c7909149edb828facfbbad88b4e83ff055` |
| Docling `v2.102.0` `pipeline/base_pipeline.py` | `7134d76feb598357106ccd3c45ec9f7530fe3ef5297eafa15a179f8d3279d906` |
| Core `v2.96.0` `types/doc/items/picture/meta.py` | `05baf3ddc8d5f88c6b7a2620ef3c930c1733ddd810d004ec602ac9062e833b8e` |

分類 CPU smoke 的 source/model contract 已足夠固定；需取得上述三檔、核驗實際 bytes 後才可標示模型就緒。此研究未驗 runtime import、記憶體、速度、分類品質，亦未取得／執行 chart VLM。模型卡整體 accuracy 不代表本 repo 的來源品質。[官方模型卡](https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5/blob/f859dfbff5c9916cd996942d4b0db7fa25808220/README.md)

## 補充：SmolVLM 圖意 CPU 候選

**可作兩張圖、每張最多 200 新 tokens 的 CPU 圖意 smoke 候選**，這是依模型大小與官方 CPU 路徑的可行性推論，並非速度／品質結論。官方 repo `HuggingFaceTB/SmolVLM-256M-Instruct` 在查證時固定為 `7e3e67edbbed1bf9888184d9df282b700a323964`，Apache-2.0；單檔權重 513,028,808 bytes，官方 LFS SHA-256 為 `74dea5904032e5ae99a2e0eef5179e6ac0f1dedc3ab0c7c2a5d4d387c843203e`。官方 model card 範例具 CPU 分支。[官方 API](https://huggingface.co/api/models/HuggingFaceTB/SmolVLM-256M-Instruct?blobs=true) · [固定模型卡](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct/blob/7e3e67edbbed1bf9888184d9df282b700a323964/README.md)

Transformers snapshot 可限 repo 頂層的 `model.safetensors`、`config.json`、`generation_config.json`、`preprocessor_config.json`、`processor_config.json`、`chat_template.json`、`tokenizer.json`、`tokenizer_config.json`、`special_tokens_map.json`、`added_tokens.json`、`merges.txt`、`vocab.json`，共 517,886,646 bytes；不要整 repo 連同各種 ONNX 變體下載。此為保守檔案集合，未宣稱每個 tokenizer 備用檔案都不可省略。[官方 file metadata](https://huggingface.co/api/models/HuggingFaceTB/SmolVLM-256M-Instruct?blobs=true)

Pinned `smolvlm` preset 的 prompt 是 `Describe this image in a few sentences.`，scale `2.0`，area threshold `0.05`；stage 固定 `max_new_tokens=200`、temperature `0.0`，結果寫為 description。官方模型 architecture 為 `Idefics3ForConditionalGeneration`／`model_type=idefics3`；preset 正確指定 `AUTOMODEL_IMAGETEXTTOTEXT`，installed Transformers `5.8.1` 的對應也確實是 generation class。[Pinned preset](https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/stage_model_specs.py#L1369) · [Pinned stage](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/picture_description/picture_description_vlm_engine_model.py#L109) · [固定模型 config](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct/blob/7e3e67edbbed1bf9888184d9df282b700a323964/config.json) · [Transformers mapping](https://github.com/huggingface/transformers/blob/v5.8.1/src/transformers/models/auto/modeling_auto.py)

需要記錄的路徑限制：

- 明確指定 Transformers + CPU，使用上述固定 revision；AUTO_INLINE 在 MPS 上可選 MLX。沿用 preset 的 generation class；自行改成 generic `AutoModel` 會載入無 generation 介面的 base model。[Engine selection](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/auto_inline_engine.py#L71) · [Model class loader](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/transformers_engine.py#L178)
- Preset 宣告的 `EngineModelConfig.torch_dtype="bfloat16"` 沒有被 `VlmModelSpec.get_engine_config()` 傳入回傳值；loader 讀的是 engine option 或 `extra_config["torch_dtype"]`。CPU smoke 若明確使用 `engine_options.torch_dtype="float32"`，須記為 dtype 變因；至少保存實際 `model.dtype`，不要把 preset 宣告當成實際 dtype。[Config propagation](https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/stage_model_specs.py#L224) · [Dtype loader](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/transformers_engine.py#L201)
- Stage 捕捉 generation exception 後回傳空字串以對齊 batch；smoke 不能只看 exit code，須要求非空 description 並保留錯誤 log。前處理預設含 image splitting，最長邊 resize 2048、每 tile 512；兩張圖並不保證只有兩個 vision tile。[Stage error handling](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/picture_description/picture_description_vlm_engine_model.py#L152) · [固定 image processor](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct/blob/7e3e67edbbed1bf9888184d9df282b700a323964/preprocessor_config.json)

以上 description stage、Transformers VLM engine、AUTO_INLINE source 與官方 `v2.102.0` bytes 相同；Transformers auto mapping 與官方 `v5.8.1` bytes 相同。本研究未實測載入／generation，未下載 SmolVLM 權重，沒有已證實的此 checkpoint loader blocker。
