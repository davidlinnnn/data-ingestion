# PDF core G2：下一輪官方方法比較計畫

日期：2026-10-15（Asia/Taipei）。這是接續使用者「避免以大量後處理追逐準度」提醒的**提案**，不是新候選的執行登記或通過紀錄。本次未執行新推論、讀取 holdout 或修改正式程式。

## 目標與下一個問題

回到各任務的 Docling 元件／模型／方法選型，保留最低必要整合。下一個優先問題是：**官方 `VlmPipeline` 加暫用 remote VLM，能否以更少自訂處理，忠實交付全文中的公式與 code，並保住其他必要資訊？** 這是方法比較；不預設整頁 VLM 會勝出，也不預設所有文件都走它。

官方提供 end-to-end VLM 與 remote API 用法，但選定版本、模型參數及 response parser 必須相容；文件宣告不等於本案通過。[Vision guide](https://docling-project.github.io/docling/usage/vision_models/)／[API example](https://docling-project.github.io/docling/_generated/examples/vlm_pipeline_api_model/)

## 1. 先對齊缺口與判準，不增加模型呼叫

- 重用[既有逐任務紀錄](docling-pdf-core-g2-pipeline-start-2026-10-14.md)，整理 OCR、表格、圖片／chart、heading／order、公式／code 的已驗方法、實際範圍、失敗層與待驗候選；不重跑已足以判斷的配置。
- 將原稿內容保真、必要 Canonical 表示、官方 parser 損失與自訂 JSON 相容性分開。原 F14 並未因實驗 schema 而新增「每個 inline token 都必須是 typed segment」的要求；歷史嚴格契約結果保留，不回寫評分或把它直接升格為產品缺陷。[原 F14 解讀](pdf-core-g2-inline-2026-10-15.md)／[最近原始結果](pdf-core-g2-context-api-2026-10-15.md)
- 凍結目前自訂 planner／parser／回填版本作比較參考；不先開第二輪 adapter 修補。

交付：一張任務／方法／模型／品質／時間／缺口的決策表，及原需求與實驗契約的差異註記。

## 2. 官方 API 與 parser 預檢，不作新模型推論

先核對固定 Docling／Core stack 的實際 request body、prompt、生成上限、API 參數、輸出格式與官方組裝。用小型固定回應檢查一般文字、inline math、code 縮排，以及頁碼／bbox／圖片資訊是否保留；預檢範例不是辨識正確率證據。

`v2.102.0` 的 API engine／convert model 有自己的請求預設；Markdown／HTML 轉 document 的來源位置亦有侷限，不能因解析成功就宣稱精確 provenance。若必要資訊無法保留，先明列方法限制；需要新版才能解決時，先核對相容版本再決定是否占用候選名額，不能默默升版或另造複雜回填層。[Tagged engine](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/api_openai_compatible_engine.py)／[Tagged conversion model](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/vlm_convert/vlm_convert_model.py)／[Tagged pipeline](https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/vlm_pipeline.py)

交付：可執行／需相容性處置／不適用的判斷。若在此已證明不適用，不為湊推論結果而付費呼叫。

## 3. 預檢可行後，登記並執行一組官方方法候選

- 保留固定 Standard 結果作 baseline；既有段落 VLM 結果作已知方法參考。先沿用同一暫用 `gpt-6-luna`，避免同時換模型與方法。因上下文、prompt、輸出格式不同，不能把差異歸因單一變因。
- 沿用已曝光固定頁面與 41 個 selected logical work units，包含既有 36 項、五項未執行來源工作與四個 bounded 正例。逐頁請求數與跨頁必要範圍先按既有映射登記；不以模型願意輸出的項目縮小分母，也不擴成全部模型乘全部文件。
- 保留 raw response、官方 document、Markdown、來源對照與損失清單。內容正確／錯誤、拒絕、技術失敗、缺輸出分開，並檢查全文遺漏／重複、公式符號、code 字面值／縮排、順序及表格／圖片退化。原 selected scope 之外未完整標註的內容仍明示未驗，不能據此採為整份文件 producer。
- 記錄實際 API 請求量、client RTT、token 與端到端可觀測時間；不將歷史 36 次段落請求與較少頁面請求當成同工作量的直接速度排名。

交付：Standard／段落 VLM 既有證據／官方 VLM 新結果的有界比較，以及保留、淘汰或待公司模型補驗的決策。

## 停止與後續

沿用[既定最多三組配置、單一 challenger 與未啟用 holdout 規則](pdf-core-g2-eval-freeze-2026-10-15.md)。第一組已完成；本提案尚未登記第二組，剩餘名額不自動用完。完整正確輸入下仍有實質內容錯誤，就比較適用模型／方法或記錄需求缺口；不猜補 prime、識別字或 code 字面值，不新增逐案例外。一般化輸入／整合修正也須有跨案例證據並保住既有回歸。

只有存在可行候選，才 lock 方法並完成獨立來源標註、進入一次配對 holdout；公司 Qwen3／vLLM 及其他適用地端候選另依確切 model ID 和資源重驗。GPU 與高頻負載隨公司環境驗證，暫用 API 結果不替代它們。其他任務缺口留在同一決策表，不因優先解 inline 而消失。

本輪預計先交付步驟 1／2 的選型與可行性判斷；不能預先承諾官方 API 路徑適用或 G2 通過。
