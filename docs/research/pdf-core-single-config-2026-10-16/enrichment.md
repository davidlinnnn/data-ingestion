# 單一 Standard 配置：enrichment 的證據界線

2026-10-16。Step 1 的唯讀收斂；沒有模型載入、推論 API、安裝、下載、Paddle 工作或 holdout PDF 內容讀取。既有輸出與原評分不變。本文不重置先前三組配置預算。

**目前無法由既有證據組出一條可直接進入完整推論驗證、且覆蓋所有必含能力的 Standard enrichment 路徑。** 可保留的單一路線是 **Standard 的原生 block enrichment＋圖片分類**；它只是比較基底，缺少可信的全文行內公式發現／重建／原位交付，以及若干圖片、圖表能力。不能把已拒絕的 paragraph/context 方法重新命名成完整候選，也不能把歷輪局部最佳輸出拼成尚未執行過的成品。[現行 retro 結論](../../reviews/pdf-core-retro-closure-2026-10-16.md)、[原選型判斷](../pdf-core-g2-method-selection-decision-2026-10-15.md)

## 可保留的單一路線及未填滿的必要欄位

| 能力 | Step 1 可提出的配置／身份 | 現有證據與不可擴張的範圍 |
|---|---|---|
| 已辨識的 code blocks | 原生 `CodeFormulaVlmModel`；`docling-project/CodeFormulaV2@ecedbe111d15c2dc60bfd4a823cbe80127b58af4`。比較基底可設 `do_code_enrichment=True`、`do_formula_enrichment=False`；native stage 依前兩旗標覆寫 extract 欄位。 | 歷史 component 實測為 CPU FP32、4 threads／interop 1、batch 1、`quantized=False`、`compile_model=False`、`trust_remote_code=False`、prompt `<code>`、cap **512**，受控七行 code 有局部成功。**不是完整 stage 選取或全文成功證據。** installed 2.132 stage 實際固定 generation/output token cap **2048**、temperature 0、`skip_special_tokens=False`，兩者不能混稱同配置；若採原生 stage，2048 應登記為未跑過的完整配置參數。[歷史方法](../pdf-core-g2-round2-2026-10-14/models/controlled-code/method.json) |
| 獨立／多行公式 | **必含仍未解；不能以 code-only 基底視為完成。** 不採此 checkpoint 作已合格公式方法。 | 同 revision／512 cap 對 SEAL Eq2 漏第二 branch；Granite-Docling formula 比較也有 marker／表示缺陷。舊 API 固定區域有局部成功，但不是已完成的原生 Standard integration。[歷史 formula 方法](../pdf-core-g2-round2-2026-10-14/models/seal-eq2/method.json)、[任務盤點](../pdf-core-g2-official-method-2026-10-15/coverage.md) |
| 全文 inline math／code | **沒有可鎖定的方法與完整參數。** 不啟用舊 custom context candidate1 作完整 challenger，也不以「只有偵測到錯才 fallback」填空。 | native gate 不掃普通正文中的數學／code。舊字元 gate 只在 28 個普通 items 選 11 個；不是 recall 證明。後續遍歷 body 的 planner 增加候選，仍無法覆蓋未產生的來源單位，並有 5 個 selected logical work units 未建立 scope。API candidate1 的 prime、identifier、code literal／indentation 實質錯誤保留。[inline](../pdf-core-g2-inline-2026-10-15.md)、[context 候選](../pdf-core-g2-context-candidate-2026-10-15.md)、[36 筆結果](../pdf-core-g2-context-api-2026-10-15.md) |
| 圖片分類（可選、偏好開啟） | `do_picture_classification=True`；`docling-project/DocumentFigureClassifier-v2.5@f859dfbff5c9916cd996942d4b0db7fa25808220`；Transformers CPU FP32、4 threads／interop 1、batch 1、compile false。 | 12 crops 的 broad families 有界成功，可保留。分類不是品質判定，也不能用 other／低分或 filter 直接免除必要 OCR、圖意或 chart 工作。[實測方法](../pdf-core-g2-images-2026-10-14/classifier/method.json)、[圖片結果](../pdf-core-g2-images-2026-10-14.md) |
| 圖片 OCR／圖意描述 | **必要能力未有完整合格 producer。** 正文 caption 保留原位；圖片 OCR 與生成描述以 image key 存同版 supplement，不灌入 source Markdown。 | RapidOCR 繁中圖內文字仍有漏句／繁簡字形；API literal OCR 4/5 strict。`SmolVLM-256M-Instruct@7e3e67edbbed1bf9888184d9df282b700a323964` 預設描述漏必要關係，不復跑該預設。暫用 `gpt-6-luna` 的圖意兩圖有界成功，但 direct HTTP 的 schema／prompt 與官方描述接點未完成等價整合。[圖片結果](../pdf-core-g2-images-2026-10-14.md)、[OCR 任務盤點](../pdf-core-g2-official-method-2026-10-15/coverage.md) |
| Chart 資料與關係 | **必要能力未有可鎖定完整原生配置。** 不因分類器可辨 chart 就設 native extraction 已驗。 | `gpt-6-luna` direct HTTP 四張受控 charts 的 13 點及關係有界成功，但 percent string／unit-null 到 typed supplement 還有接點缺口；原生 Granite Vision chart stage 沒有模型品質實測。Granite Vision 舊 table CPU timeout 不是 chart 能力失敗。[圖片／chart 結果](../pdf-core-g2-images-2026-10-14.md) |

上述 `do_formula_enrichment=False` 只描述可保留比較基底的執行狀態，**不是放棄 F13、將必含改可選，或宣告完整配置成立**。必含公式、圖片／chart 空缺必須在主配置標成 blocking gaps。

## 官方接點核對：模型可換，不代表偵測與交付已解

唯讀查核現有 Docling 2.132.0 source；這些是介面事實，不把歷史 2.102／Core 2.96 的內容結果回算成新版已驗。

- [`StandardPdfPipeline` 原生接點](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L665)先依 `do_code_enrichment`／`do_formula_enrichment` 設定同一個 CodeFormula stage，再接其他 enrichments。[`CodeFormulaVlmModel.is_processable`](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L119)只接受 `CodeItem` 或 `FORMULA` `TextItem`；它**不是普通段落 inline detector**。
- 同一 stage 可透過 unified VLM runtime 使用 Transformers／MLX／API，但 `_get_prompt` 實際回 `<code>`／`<formula>`，`__call__` 自行設 2048 cap／temperature 0。僅把 `model_spec` 換成通用 VLM 或 OpenAI-compatible endpoint，不會自動取得合適任務 prompt、全文 inline discovery 或保真輸出契約。[stage source](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L137)
- [原生 crop base](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_model.py#L174)使用 `prov[0]`、擴張 bbox、該頁 crop；CodeFormula 類別的 `images_scale=1.67`、`expansion_factor=0.18`。`CodeFormulaVlmOptions.scale=2.0` 不可誤報為這個 base 真正取圖的尺度。這個路徑沒有本案的多 provenance 拼接、picture parent/child union 或跨頁 target/context 組裝。
- 原生 code/formula 更新 `item.text`；不把 `item.orig`、模型 raw 與 source provenance 混成同一份來源文字。stage 會移除特定 closing tags／EOS、`lstrip`，並可在 engine exception 後寫入空字串，故保留 raw 與完成性紀錄仍必要。這是失敗／交付對賬，不能偵測所有語意錯誤。[寫回 source](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L191)
- [`PictureDescriptionApiOptions`](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L874)有官方 OpenAI-compatible URL／headers／params／prompt／timeout／concurrency 接點；[stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/picture_description/picture_description_api_model.py)透過 `api_image_request` 送圖。原生資料寫入 `meta.description`，不是独立的圖片 OCR／typed chart 資料契約。area threshold 預設 0.05、class filters 可跳過工作；它們不等於必要圖片已覆蓋。[base](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/picture_description_base_model.py)
- [native chart gate](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/chart_extraction/granite_vision.py#L113)只看分類 top class 是否 `bar_chart`／`pie_chart`／`line_chart`；三種 native task `<chart2csv>`／`<chart2summary>`／`<chart2code>` 不等同圖片 literal OCR、通用圖意描述或還原作者原始程式碼。

## 為何不復活舊 VLM 組合

暫用 hosted 模型身份始終是 **`gpt-6-luna`**。圖片六次比較為 low reasoning、high image detail、JSON object、6144 completion cap、順序一次；段落／context 比較為 strict segments JSON、4096 cap。公司只知 Qwen3 VLM family，沒有 exact checkpoint／serving／GPU 成功證據；不能把 OpenAI 改名當 Qwen3 品質或 latency 資格。[圖片 request](../pdf-core-g2-images-2026-10-14/api/g1-s05/request-description.json)、[inline API](../pdf-core-g2-inline-api-2026-10-15.md)

完整段落曾改善 E14 六處／E13 十一處公式與 prose，但仍有其他 prime、下標與 code literal 錯誤；整頁 official DocTags low／medium 亦有真實內容錯誤及 out-of-page boxes。higher reasoning 修一例卻退化原正例，無法作無條件全域替代。cross-page 段落原先使用歷史 continuation-v3；成功不能證明新 inline／跨頁發現。[方法比較](../pdf-core-g2-method-selection-decision-2026-10-15.md)

來源定位至少須保留 physical page、原 PDF 座標、crop/canvas transforms、target 的完整 charspan、多 fragment 與 provider identity。舊回填有 exact hashes／ownership／scope guards，卻只證明結構來源計帳；SEAL32 等錯誤仍能通過。原生未發現內容、hidden formula children、混合正文／caption、錯 reading order 都不能靠「回填成功」補足。曾提出的 token guard 又錯擋 2/4 既有正例，已否決，不重新調到通過。[邊界與回歸](../pdf-core-g2-inline-boundary-2026-10-15.md)

另外，perfect-provider 的 [DOTS parser/export 控制](../pdf-core-g2-preflight-2026-10-16/parser/parser-findings.md)證明 wrapped formulas 可被重複加 delimiter、recognized HTML tags 可先改掉 inline code literal；七個 global export settings 沒有普遍保真解。這些是特定 DOTS mapping 的接點證據，**不擴張成所有 Standard native Text／CodeItem 均有同樣缺陷**，也不靠換模型期待已遺失 literal 自動恢復。

## Step 1 的最小決策缺口

**不能交付「已鎖定、只差跑一次」的完整 enrichment 配置；可交付的是具名比較基底及明確 no-go／unresolved 欄位。** 若下一階段要投入，首先須有一個相較已拒絕配置的新、可說明的假設，同時交代以下三件事：

1. 全文必要 inline／display formula／code 的 discovery scope 從何而來，包括未 emit 與 picture 內內容；不能以文字字元 gate 或模型 uncertainty 冒充已證明的 recall。
2. 固定哪一個具名 producer 與 raw 契約、如何經最小官方接點保真交付；若只有大量自訂 detector／graph repair／猜內容後處理才能填滿，就明記該方案不符合目前收斂方向，而非先跑模型追分。
3. 公司 Qwen3 exact identity 與服務能力是正式部署資格；暫用 OpenAI 僅能提供其自己的結果。是否值得做新有界研究必須與已耗用預算分開，不能藉此重啟盲選模型。

這不是要求使用者現在替我們選模型或放寬必要功能。Paddle 建置、整合與新推論維持暫停；本文件沒有排入新推論或新增後處理。

未驗新完整配置、公司 GPU／vLLM、完整 provenance／Canonical handoff 或高頻 latency；現有有界成功不足以宣稱完整 Processing Profile 可採用。
