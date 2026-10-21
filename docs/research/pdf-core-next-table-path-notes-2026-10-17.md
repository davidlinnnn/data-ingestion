# 下一輪表格路徑查證：Granite Vision

2026-10-17；規劃查證，未載模型、下載權重、讀取 PDF／圖片、執行推論或開啟 holdout。

**不建議把「Granite Vision＋MLX」包裝成下一個全新官方 native table method。** 同一模型的 CPU 與 MLX 研究接合都已實測；目前六 panel 的 G1-T02 是新任務覆蓋，但不是新模型／引擎假說。這條路可保留為具體 coverage gap，不能因新一輪改套件或換名稱而重置歷史失敗。

## 固定版元件與實際限制

本機 Docling-slim 2.132.0 原始碼與[固定版來源](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/table_structure/table_structure_model_granite_vision.py)顯示：

| 項目 | 實際實作 |
|---|---|
| Pipeline | StandardPdfPipeline 的 table stage；不是整頁 VlmPipeline |
| 模型 | `ibm-granite/granite-vision-4.1-4b@dd48e97503de471803850df70843cf9eb5da8712` |
| 公開 options | `GraniteVisionTableStructureOptions` 只有 kind，沒有 engine／API URL／model ID／dtype／generation cap 參數 |
| 引擎 | 直接 `AutoModelForImageTextToText`；支援 CPU／CUDA，固定 BF16；未允許 MPS／MLX，`enable_remote_services` 僅接受 False |
| 輸入 | 上游 TABLE／DOCUMENT_INDEX cluster，`page.get_image(scale=1.0, cropbox=cluster.bbox)`；沒有自動切六個 panel 的保證 |
| 任務 | processor chat template＋`<tables_otsl>`；每頁全部有效 table crops 一批生成 |
| 解碼 | `max_new_tokens=tokenizer.model_max_length`、`use_cache=True`；其他採 checkpoint generation defaults，不能逕稱固定 greedy |
| 表示 | decode 後 `parse_otsl_output`，產生 row／column spans 與 cell text；cell bbox=None，保留整個 table cluster 的位置 |
| 觀測 | raw 只進 native DEBUG log，公開 table prediction 保存解析結果；沒有通用 VLM engine raw-response 欄位 |

現有 checkpoint 的 tokenizer model_max_length 為約 1e30 sentinel，不能當實用 token 預算；公開 options 無法改成有限 cap。Transformers 5.20 的 native granite4_vision 已可用，固定 Docling helper 在 >=5.8 關閉 remote-code；不能抄舊 `trust_remote_code=True` 造成新版相容風險。[options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py)、[helper](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/granite_vision_utils.py)、[OTSL parser](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/otsl.py)

IBM 的[目前模型卡](https://huggingface.co/ibm-granite/granite-vision-4.1-4b)提供 MLX-VLM 與 vLLM >=0.21.0／OpenAI-compatible 服務方式，並定義 `<tables_json>`、`<tables_html>`、`<tables_otsl>`。**模型可用這些引擎，不等於上述 Docling table stage 可直接換引擎。** Generic OpenAI 模型只能驗 API 接點／另一候選；不能作這個固定 Granite checkpoint 的效果或 latency 證據。當前卡片亦不能反證歷史 checkpoint 的 adapter bytes 已是最新合併形態。

## 不可遺忘的既有結果

- CPU 與上游比較 (`paper-pdf-table-upstream-results-2026-10-11.md`)：同 revision，兩份 shard 合計 7,994,565,368 bytes；SkillOpt **p7 長表**先觸發 8GiB guard，後續固定 12GiB／1thread 在 600 秒逾時；AZR 未開始。部分已生成內容已有數值錯誤。這與目前 **p8 Table2 六 panel** 不同，不能稱 T02 已驗過，也不能稱 CPU 從未試過。
- MLX GPU 實測 (`paper-pdf-granite-mlx-results-2026-10-11.md`)：同原始 BF16 checkpoint，MLX-VLM0.7.6／MLX0.32.3／Transformers5.14；temperature0、8192 tokens、600秒、12GiB RSS／Metal guard。SkillOpt p7／AZR p9 完成，wall143.177／63.970秒、Metal peak8.513／8.287GiB；數值、增量、欄位關係仍失敗。它是公開 MLX caller-prepared tensors＋官方 OTSL parser 的研究接合，並非未修改 Docling native table stage。
- [Granite-Docling258M](pdf-core-g2-round3-2026-10-14.md)已測過目前 T02 全頁與完整 table crop OTSL，仍漏值／綁定；不能與 Granite Vision4.1-4B 混稱。TableFormerV2 亦已測 T02，不建議再換名重跑。

## 建議去留

**本輪先不安排 blind CPU retry、不新增 MLX table plugin、不假設 API 可插入 native table stage。** 若之後專門補 Granite Vision 對六 panel 的遷移覆蓋，可獨立預登錄一次完整 T02 crop 的 MLX component test，重用固定原 checkpoint／官方 prompt／OTSL parser，沿用既有資源界線；應明標「新任務覆蓋、研究接合」，不是新 native pipeline。這需要另一個明確目標，優先度低於尚未驗且具真正新假說的官方方法。

即使補這項，完整判準仍為原 G1-T02 (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)：六 panel、28 data rows、84 numeric bindings、8 critical comparisons、caption／condition／header 歸屬；錯配、漏值、額外值計原分母，最多 4/84 numeric errors 且全部 critical comparisons 通過。禁止人工 panel crops、oracle 內容送 producer、逐案例 prompt 修正、只驗 rows×cols 或數字存在。成功也僅補此 table component 的證據，不能補 code／inline formula、整份 Canonical Acceptance 或高頻 SLO。
