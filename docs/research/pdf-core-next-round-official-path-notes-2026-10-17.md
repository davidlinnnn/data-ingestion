# 下一輪官方接點核對：Standard 原生 enrichment

2026-10-17。只讀固定 Docling 2.132.0 本機 source、歷史研究結果與模型 metadata；未開 PDF／圖片／holdout、未讀取或載入權重、未安裝／下載／推論或呼叫 API。本筆記只提供下一輪規劃依據。

## 建議：單一 S0＋CodeFormulaV2 官方完整路徑

保留剛完成的 S0：`StandardPdfPipeline`、Heron、selective RapidOCR、TableFormerV1 accurate、原生 reading order／assembly；只開 `do_code_enrichment=True`、`do_formula_enrichment=True`，用官方 `CodeFormulaVlmOptions.from_preset("codeformulav2")`。這是在 S0 仍缺的**真實 native gate→crop→模型→寫回→Markdown**接線上取新證據，並非重做舊 oracle crop。舊實測僅有兩張固定 crop、512-token cap：controlled code 成功、SEAL Eq2 漏 Otherwise 分支；沒有驗正式偵測、18% crop、完整回填或真實 DGM diff。[舊輪結果](pdf-core-g2-round2-2026-10-14.md)

最小完整來源預算可沿用原41項所在的 **8頁、4次 conversion**：controls1、WikiSkill20–22連續、SEAL2–4連續、DGM51。首個 controls smoke 計入一次，不另重跑。Wiki 三頁保留普通 prose／行內公式與跨頁正例，用來測 regression 和記錄原生 gate 未涵蓋的必要工作；不能因 enrichment 不處理便從41項移除。先不重跑三項 G1 的 table／image OCR／scan：本次單一變因並不改其模型或方法，也不能聲稱這些缺口已解決。11頁回歸若有別的明確目的，可由主計畫另行登錄，勿冒稱 code/formula 必要頁次。

本次只可決定「可否保留原生區塊 enrichment 進入組合」，**不能以此通過完整 G2**；全文行內公式、複雜表格、image-key supplement 仍是獨立缺口。[前輪結論](pdf-core-native-round-results-2026-10-17.md)

## 公開接點及不能跳過的限制

| 接點 | 固定2.132 source的實際行為 | 下一輪意義 |
|---|---|---|
| Pipeline options | Standard 建立 `CodeFormulaVlmModel`，複製 flags 至 `extract_code`／`extract_formulas`；不是使用舊 `CodeFormulaModel`。 | 不必寫 producer subclass 或新 pipeline。 [接線](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L662) |
| Native gate | 僅 `CodeItem`、label為 `FORMULA` 的 `TextItem`；普通段落不進入。 | native code/formula 誤分類、漏偵測和 inline math 都須記成 eligibility/coverage 缺口；不新造 gate 追答案。 [Stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L119) |
| Native crop | stage `images_scale=1.67`（約120dpi）、`expansion_factor=0.18`；基底只取 `prov[0]` bbox，expand後向page取圖。 | `CodeFormulaVlmOptions.scale=2` 不能直接宣稱是這個crop的有效scale；不採oracle bbox、相鄰context、union或人工分區。 [Stage常數](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L72)、[基底crop](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_model.py#L184) |
| Prompt／生成 | `_get_prompt`固定 `<code>`／`<formula>`；stage呼叫有效temperature0、`max_new_tokens=2048`、`skip_special_tokens=False`；官方 `elements_batch_size=5`。 | 不把舊512 cap搬成default；不聲稱batch1，需記錄每次實際batch長度。 [Stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L263) |
| 寫回 | stock cleanup後覆寫 `item.text`，code另寫language；不改`item.orig`、不增補inline span結構。批次例外被吞後可覆寫為空字串。 | native success 不能當完成；驗nonempty、原必要文字及typed/Markdown交付。應保留模型回應和失敗種類，勿補字。 [Stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L286) |
| 證據保存 | `CodeFormulaVlmModel.engine.predict_batch` 是公開 engine 方法，但 stage 只返回items，並不把raw掛回公開page predictions。 | 若需要raw/crop evidence，可在research runner對公開 `predict_batch` 做原樣透傳 observer，保存輸入圖、prompt、參數及回應；不改prepare/gate/private parser。須先以無模型 mock 證明observer不改inputs/outputs。若不採observer，應直說raw/crop未捕捉，不能補造。 |

公開 `DocumentConverter.initialize_pipeline(InputFormat.PDF)` 可先初始化；它不返回pipeline，但 `initialized_pipelines` 是公開字典。現行 codeformula engine 為eager初始化，因此不能把這一步稱零模型preflight。零模型驗證須用mock／source核對，不呼叫真正initialize。[Converter](https://github.com/docling-project/docling/blob/v2.132.0/docling/document_converter.py#L525)

## 模型與 runtime 的精確前提

- 既有 snapshot：`docling-project/CodeFormulaV2`，rev `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`；歷史 weight SHA256 `4b04e77af34c4e682a7ab1617628340d658f3c3dcd12456dd2a7fff805cf79d2`，630,993,616 bytes。既有manifest (`pdf-core-g2-round2-2026-10-14/models/codeformula-download.json`)。本次只以filesystem stat確認12項檔案存在且大小符合歷史manifest，**未重新讀權重做hash**；實際執行前再核對完整bytes hash。
- 固定上輪 Standard 2.132/Core2.99/Parse7.22.3/pdfium5.14 runtime，先 mock 檢查完整 converter/enrichment/export。現有 Transformers5.20 跑本checkpoint的實際相容性尚未驗；不能拿舊runtime已成功兩crop當新runtime相容保證。
- 明確選 `TransformersVlmEngineOptions(device="cpu", torch_dtype="float32", compile_model=False, quantized=False)`，4 intra-op、1 inter-op；不選 `AUTO_INLINE` 讓Mac自動改成未驗MLX。官方Transformers engine支援列表為CPU/CUDA/XPU，沒有MPS；不要把Mac GPU視為這組現成選項。[Engine](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/inference_engines/vlm/transformers_engine.py#L144)
- 用已存權重與repo命名artifacts目錄，offline、trust_remote_code=False；保留舊runtime、snapshot和oracle，不升級來回追分。CPU有界執行遇相容性阻擋便記錄，不對模型內容推論；機械修正可在推論前完成並重新freeze。
- 模型卡說明120dpi code／formula輸入及LaTeX／縮排code輸出；它沒有宣告普通段落inline偵測或跨頁重建能力。[模型卡](https://huggingface.co/docling-project/CodeFormulaV2/blob/ecedbe111d15c2dc60bfd4a823cbe80127b58af4/README.md)

## S0／S1 OCR差異的source澄清

原生2.132**實際queue連線**是 `preprocess → layout → OCR → layout_postprocess → table → assemble`，不能依 `stages=[preprocess, ocr, layout,...]` 清單順序解讀。`OcrMode.DEFAULT` 明確使用 `PDF_AWARE_LAYOUT_REGIONS`：以layout clusters為起點，再依PDF text／non-text排除、deduplicate OCR rects。因此更換Heron/Egret本來就可能改OCR輸入範圍與下游cells，並非OCR必然在layout之前。這可解釋前輪三頁cells差異的**可行機制**，仍不是每一處差異的已證實唯一根因；無需因此重跑整輪。[Queue wiring](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L790)、[OCR路由](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_ocr_model.py#L215)

## Remote API與fallback的界線

官方 `ApiVlmEngineOptions` 有 OpenAI-compatible `url`、`headers`、`params`、timeout、concurrency；Standard enrichment可使用這個engine，須 `enable_remote_services=True`。但**換engine不會換掉stage硬寫的 `<code>/<formula>` prompt或2048 cap**。若服務實際host的是CodeFormulaV2且接受此輸入協定，API serving是合理後續部署候選；公司通用Qwen3／暫用OpenAI不因OpenAI-compatible便獲得這套任務協定，不能原樣插入就稱可用解法。[API options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/vlm_engine_options.py#L201)、[API engine](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/inference_engines/vlm/api_openai_compatible_engine.py#L114)

全頁 `VlmPipeline + API + DocTags` 先前在2.102已實測low/medium：內容、DocTags grammar、bbox與原位inline交付仍失敗；不能說尚未試過，也不建議只換2.132再重跑同服務同prompt。[既有官方API比較](pdf-core-g2-method-selection-decision-2026-10-15.md)

本輪**不自動追加remote fallback**。若原生region enrichment無法成為可用元件，下一個真正的選擇是：接受另行設計的最小region API adapter／輸出協定（屬自訂擴充，需另外固定方法及回歸），或等待有官方任務協定的公司服務候選。不要恢復已失敗的大量context planner、段落重接或字串修復。Qwen3仍是公司VLM候選，OpenAI僅暫代介面／任務比較，品質和latency不等價。

尚未驗證新runtime相容性、完整native enrichment品質、公司API/GPU與高頻SLO；本次僅完成source規劃核對。
