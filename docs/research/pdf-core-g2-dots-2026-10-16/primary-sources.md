# G2 dots.ocr：固定來源與 CPU／原生 parser 可行性

研究日期：2026-10-16（Asia/Taipei）。這份文件是下一輪執行前的第一手來源核對；未下載模型權重、未安裝環境、未執行模型，也未讀取任何 custody holdout PDF。來源程式碼可執行不等於內容品質合格，parser 接點存在不等於 F13／F14 通過。

## 結論與最小執行路徑

**dots.ocr 可以做不改模型原始碼的 CPU 可行性探測，但不應假設目前 Mac 的完整頁面推論可負擔。** 模型的 vision 實作提供 eager 路徑；FlashAttention 是可選匯入，未安裝時會退到 eager。相反地，這個固定 revision 的 vision SDPA 強制選 `EFFICIENT_ATTENTION`，不能把一般 PyTorch 的「SDPA 支援 CPU」直接套用在此分支。[模型 vision source][vision]

建議先完成固定 Docling parser／輸出契約預檢，再用小張、少字的合成圖做 CPU kernel 與載入 smoke。若通過，再依實測記憶體及生成速度決定是否跑已曝光的 regression 頁；不把縮小圖 smoke 當作整頁品質證據。若 CPU 代價過高，保留原模型、官方 native JSON 與官方 parser 路徑，移到公司 GPU／vLLM，不以 OpenAI 輸出冒稱 dots.ocr。[官方 repository 指向的 CPU 操作說明][cpu-note]也特別指出 CPU 很慢、先用小圖少字；該說明是 upstream issue comment，非本機性能量測。

## 候選身分與下載下限

從 Hugging Face 第一方 API 讀到的固定模型 revision 是 `c0111ce6bc07803dbc267932ffef0ae3a51dc951`；模型 ID `dots-studio/dots.ocr`，更新時間 `2025-10-31T08:49:31Z`。`rednote-hilab/dots.ocr` 是舊命名，應記錄實際解析後的 ID 及 revision，不能只保存浮動 `main`。[模型 metadata API][metadata]

| 項目 | 固定資料 |
|---|---|
| 完整模型參數 | 3,039,179,264，metadata 分類全部 BF16 |
| 第一個 safetensors shard | 4,292,758,192 bytes；SHA-256 `ea1d532184f3adf5cbcfcc00b2cf5b2abfa6fe182768a3ae63d441a9b5fc99ac` |
| 第二個 safetensors shard | 1,785,673,544 bytes；SHA-256 `26ab1ec6c8b4e4116befbd59af42159f1dbcb0ad0c045a15e890bb2f6e8b0dae` |
| 兩個 shard 下載合計 | **6,078,431,736 bytes，約 5.66 GiB**，不含 tokenizer／程式碼等檔案 |
| Tensor index `metadata.total_size` | 6,078,358,528 bytes，這是 tensor 大小，不是 shard 檔案大小 |
| 模型名稱的 1.7B | 指 LLM foundation，不是完整 vision＋language 模型大小 |

檔案大小與 LFS SHA 來自 metadata API；tensor 大小來自[固定 index][index]；1.7B 的定義來自[固定 model card][card]。因此不能用「1.7B × 2 bytes」估算完整權重記憶體。載入／執行還需要 activation、KV cache、tokenizer、runtime 與載入暫存，6.08 GB 只是權重規模。

模型卡標示 MIT，但同一 revision 另附 `dots.ocr LICENSE AGREEMENT`。該檔明示商用及企業地端部署許可，也有補充使用條件；其第 1.6 條指定衝突時 MIT 優先。記錄應包含這個分發檔，不能寫成只看 badge 就已完成公司授權審查。本文件不新增法律結論，也不因這個來源身分紀錄阻止技術 smoke。[固定分發 license][license]

## 模型 config／實際程式碼的 CPU 邊界

固定 `config.json` 是 `DotsOCRForCausalLM`／`dots_ocr` custom code，`transformers_version` 記為 `4.51.0`；這是序列化時版本，並非本文件已驗證的最低或唯一支援版本。LLM 有 28 層、hidden size 1536；vision 有 42 層、12 heads、patch size 14、spatial merge 2，預設 BF16、vision attention `flash_attention_2`。[模型 config][config]

`DotsOCRForCausalLM` 繼承 Transformers `Qwen2ForCausalLM`，載入時建立 `DotsVisionTransformer(config.vision_config)`。模型本體沒有強制 `.cuda()`；model card 的 demo 將 inputs 移到 CUDA，是範例選擇，不是核心 forward 的硬依賴。[模型 language source][language]

| 路徑 | source fact | 執行含意 |
|---|---|---|
| vision `eager` | PyTorch matmul／softmax；FlashAttention 不存在時的原生 fallback | 可先測 CPU；attention 仍為平方級記憶體 |
| vision `eager_v2` | source 已提供，按每張 image 的序列分段計算 | 可由 config 選用，無需改 source；單張圖不會消除平方級 attention |
| vision `sdpa` | `with sdpa_kernel(SDPBackend.EFFICIENT_ATTENTION)` | CPU 可用性不能假設；不要選此路徑作第一個 CPU smoke |
| vision `flash_attention_2` | try/import；缺套件則改 eager | 不需要為 dots.ocr CPU smoke 安裝 flash-attn |
| vision forward dtype | 預設 `bf16=True`，把 pixel tensor 轉 BF16 | 單純把全模型載成 FP32 會與 Conv2d 權重 dtype 不一致；不改 forward 的首選是 BF16 載入並測 CPU kernel |

以上逐項依[固定 vision source][vision]；注意這是 **dots.ocr**，不能推廣成 dots.mocr 也無 flash-attn 硬依賴。

最小 direct-Hugging-Face 設定草案如下，這只是規劃，未在本研究中執行：

```python
config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)
config.vision_config.attn_implementation = "eager_v2"
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    config=config,
    attn_implementation="eager",  # Qwen2 language attention
    torch_dtype=torch.bfloat16,
    device_map="cpu",
    trust_remote_code=True,
)
```

`model_path` 必須指向上述固定 revision 的完整 snapshot。`vision_config.attn_implementation` 是[官方 remote config 已提供的欄位][configuration]；設定它不改權重或 source。頂層 `attn_implementation` 影響 language model，不能假設它同時改到 vision 的同名普通欄位。這個 direct HF smoke 必須標記成模型可行性探測，不能冒稱已執行完整官方 Docling pipeline。

記憶體判斷應依實際預處理 grid。若單張圖有 `N = grid_h × grid_w` 個未 merge vision patches，12 heads 的 BF16 attention score 單一張量約 `12 × N² × 2 bytes`，其 FP32 softmax 暫存還會增加需求。例：336 × 448 pixels 對應 24 × 32 = 768 patches，該 score 約 13.5 MiB；約 2 megapixels 的輸入則可到數 GiB 的單一 score。這是依 source shape 的估算，不是 RSS 測值或可安全用滿記憶體的保證。`eager_v2` 對單圖仍有相同主要平方項。[vision source][vision]

## Docling v2.132.0：固定版本與原生接點

GitHub tag `v2.132.0` 解析為 commit **`5c349dd696d81c67fe29c378a4fdff08e28090bd`**；下列來源連結使用該 commit。[tag API][tag]

| 元件 | 已確認來源行為 |
|---|---|
| Core dependency | `docling-core>=2.98.0,<3.0.0`；該 commit `uv.lock` 鎖為 **2.99.0**，不代表使用者環境已安裝此版 |
| `dots_ocr` preset | repo `rednote-hilab/dots.ocr`、`ResponseFormat.DOTS_JSON`、`trust_remote_code=True`、max new tokens 24000、scale 2.0 |
| 預設 engine | vLLM；Transformers override 是 BF16／AutoModelForCausalLM／chat prompt |
| OpenAI-compatible API | preset 提供 API model name／max_tokens，這是運送 dots 真實輸出的接口，不是 OpenAI 替代 dots checkpoint |
| Transformers 限制 | preset source 註解指出 <=4.57.x；5.x 會輸出錯誤整頁 bbox，vLLM 路徑不受這個已知問題影響 |

依[固定 pyproject][pyproject]、[固定 lock][lock]與[preset source][preset]。既有 2.102/Core 2.96 結果不能當作這個新 parser 的品質證據。應在新隔離 runtime 固定實際依賴，不升級或改寫舊 evidence 環境。

官方 Transformers engine 還在執行時對舊 repo ID 檢查 `transformers<5`。它的 dots language attention 固定 `_attn_implementation="sdpa"`，載入 model 的固定參數沒有轉交通用 `config`／`vision_config`／attention kwargs；公開 options 也沒有 vision eager_v2 欄位。因此**不能把上方 direct HF 的 eager_v2 設定宣稱是原生 Docling options**。不用 patch 的原生 CPU 候選，是 `quantized=False`、BF16、CPU、`compile_model=False`、trust remote code，讓原始 vision flash 設定在無 flash-attn 環境走 source 已存在的 eager fallback，language 保持原生 SDPA；是否能載入／生成仍要 smoke 實測。[engine][engine]、[engine options][engine-options]

特別注意 engine 的 dots 身分檢查列的是舊 `rednote-hilab` ID；改成新 `dots-studio` 名稱不應被當成允許使用 Transformers 5 的方法。應直接鎖定 4.x，驗證真實 repo revision，保留 guard 的用意。[engine source][engine]

## Native JSON parser 的可驗證契約與風險

`VlmPipeline` 的 `DOTS_JSON` 分支原生呼叫 `parse_dots_json`；parser 接受 JSON array，每個元素包含 bbox／category／text，11 類包括 Formula、Table、Picture。bbox 是 **模型輸入圖像像素**，傳入 `model_image_size` 後才換算成 PDF page points，座標原點為 TOPLEFT。Table 走 HTML table 匯入，Formula 轉公式 label，整段 fenced code 可轉 CodeItem，連續 Caption 會做鄰近關聯；不能推論它已解決跨頁語義。[pipeline][pipeline]、[parser][parser]

這個 parser 會清掉 array 前綴、截掉最後不完整物件後補 `]`，或在無有效 JSON 時回傳空頁。未知 category 會退成 TEXT、缺 bbox 的元素會被略過；空／部分 DoclingDocument 不能獨自證明模型完成。驗證必須保留原始輸出、finish reason、JSON 完整性與解析前後內容差異，不讓 tolerant parser 隱藏 truncation／漏項。[parser source][parser]

原生 pipeline 由 `compute_qwen2vl_image_size` 推定模型圖像大小，預設 factor 28、min_pixels 200704、max_pixels 2500000；但固定模型 `preprocessor_config.json` 是 min_pixels **3136**、max_pixels **11289600**。在低於 200704 或高於 2500000 pixels 的情況，若實際 processor 沒有覆寫成 Docling 推定值，兩者可不一致。這是目前 source 可見的契約差異，不是已量測的 bbox 錯誤。小圖 CPU smoke 必須另記實際 image_grid_thw／resize；若只測模型，不能直接拿這個小圖去證明 pipeline 來源座標正確。[size helper][resize]、[固定 preprocessor][preprocessor]

目前 GitHub master 已轉向 dots.mocr 的例子，requirements 列 Transformers 4.56.1；這只能提供版本選型線索，不能把 mocr demo／新 checkpoint 當成固定 dots.ocr 的驗證。舊固定 model card 的 vLLM 範例基於 0.9.1，現在 repository 宣告 vLLM 0.11.0 起已內建 Dots OCR。實際公司部署仍需固定 image／vLLM／checkpoint revision 並做真實輸出回歸，不直接使用浮動 latest。[固定 model card][card]、[固定 repository README][repo-readme]、[固定 requirements][requirements]

## 待執行證據與停止條件

1. 原生 parser 控制案例：公式、code、HTML table、caption、bbox 轉換與 malformed／截斷輸出。通過只記 parser 契約，不能記模型準度。
2. 載入前 kernel probe：BF16 Conv2d／矩陣運算、相容 Transformers 4.x、remote source imports；若失敗先記原因，不修改模型 source 配合機器。
3. 有資源餘裕才載入固定兩個 shard，跑小圖一次，記 load time、生成速度、峰值 RSS、token 截斷與實際預處理尺寸。
4. 可負擔才跑已曝光 regression 與新獨立 validation；六份 custody holdout 保持未讀。prompt／模型設定在評分前固定，不針對錯字或答案修補。
5. 若 CPU 超時／記憶體達停止線，結論為「本機路徑不可負擔」，不把停止判作模型品質失敗；轉公司 GPU／vLLM 同 checkpoint 驗證。

本文件沒有模型推論成績、Mac latency 保證或正式配置推薦。授權與資源安排沿用主流程；本研究不自行下載、部署或新增待驗候選。

[metadata]: https://huggingface.co/api/models/dots-studio/dots.ocr?blobs=true
[card]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/README.md
[index]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/model.safetensors.index.json
[config]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/config.json
[configuration]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/configuration_dots.py
[language]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/modeling_dots_ocr.py
[vision]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/modeling_dots_vision.py
[preprocessor]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/preprocessor_config.json
[license]: https://huggingface.co/dots-studio/dots.ocr/blob/c0111ce6bc07803dbc267932ffef0ae3a51dc951/dots.ocr%20LICENSE%20AGREEMENT
[cpu-note]: https://github.com/studio-dots-ai/dots.ocr/issues/1#issuecomment-3148962536
[tag]: https://api.github.com/repos/docling-project/docling/git/ref/tags/v2.132.0
[pyproject]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/pyproject.toml
[lock]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/uv.lock
[preset]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/datamodel/stage_model_specs.py
[pipeline]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/pipeline/vlm_pipeline.py
[parser]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/utils/dots_utils.py
[resize]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/utils/vlm_utils.py
[engine]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/models/inference_engines/vlm/transformers_engine.py
[engine-options]: https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/datamodel/vlm_engine_options.py
[repo-readme]: https://github.com/studio-dots-ai/dots.ocr/blob/36d7248878f181c6257dc1cbd799ae940970444f/README.md
[requirements]: https://github.com/studio-dots-ai/dots.ocr/blob/36d7248878f181c6257dc1cbd799ae940970444f/requirements.txt
