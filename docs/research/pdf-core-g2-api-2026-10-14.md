# PDF core G2：GPT-6 Luna 暫用 API 比較

[Research index](README.md) · [G2 計畫](docling-pdf-core-g2-pipeline-start-2026-10-14.md) · [第三輪 CPU](pdf-core-g2-round3-2026-10-14.md) · [需求 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

2026-10-14（Asia/Taipei）。**四次暫用 API 比較已完成；SkillOpt Table2 的84個數值綁定與8項關鍵比較均保留，英文選定兩段的內容與順序亦正確。公式保留兩分支與可見註腳標記，OCR 保留全部繁中漢字，但仍有輸出格式／標點與整合範圍的限制。** 這支持繼續評估針對特定任務的 VLM 路徑；尚未選定正式 Processing Profile，G2 未全面通過。

## 執行身份與範圍

使用者明確提供暫用候選：`https://api.openai.com/v1/chat/completions`／GPT-6 Luna。官方文件確認 API ID 為 `gpt-6-luna`、支援圖片輸入與 Chat Completions。請求及回應均使用此 ID；回應沒有提供可據以固定權重的 immutable snapshot，因此不宣稱已 pin 模型 weights。[官方模型頁](https://developers.openai.com/api/docs/models/gpt-6-luna)

只比較四個 G1 固定任務，沿用第三輪相同 image bytes：NCCU 中央 panel、SEAL Eq2 約120dpi crop、英文 scan 全頁144dpi、SkillOpt p8 全頁144dpi。表格 prompt 指定可見 Table2／完整 caption，不包含 Table3；不傳入 oracle 的預期值、正確轉錄或評分答案。這是具名模型＋prompt＋JSON parser 的 producer 比較，與 Granite 的 DocTags／OTSL 配置不同，不能歸因為只換模型。

httpx0.28.1、concurrency1、各一次、無自動 retry，TLS 驗證開啟、不跟 redirect、不讀 proxy env；固定官方 endpoint。圖片以 Base64 PNG、`detail=high` 送出；`reasoning_effort=low`、`response_format=json_object`、`store=false`；OCR／公式 `max_completion_tokens=2048`，英文／表格6144。此 token 預算含 reasoning 及可見輸出，並非只算輸出文字。[官方 Chat API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[官方 vision guide](https://developers.openai.com/api/docs/guides/images-vision)

四次皆 HTTP200、`finish_reason=stop`、無 refusal、JSON object 可解析，未因 token／timeout 失敗。request description 保存 prompt、參數、來源 SHA、可重建的 body hash；PNG、provider response、request ID、usage、client round trip 皆保存。credential 僅從隱藏 TTY prompt 進入執行記憶體，不寫入程式、環境檔、報告或 ticket，錯誤回應具遮罩處理。request description 中的圖片 placeholder 並非實際送出的字串。[Runner](pdf-core-g2-api-2026-10-14/run.py) · [執行記錄](pdf-core-g2-api-2026-10-14/observations.json) · [官方介面研究](pdf-core-g2-api-2026-10-14/research.md)

## 逐任務結果

| 案例 | 結果 | 採用範圍與保留缺口 |
|---|---|---|
| G1-O01，圖片 OCR | 五項內容／位置保留，繁中「統／結／簡」等漢字正確。原文 `"連結"` 被改成 `「連結」`；既有檢查只接受空白／引號寬度正規化，嚴格逐項為4/5。 | 不默默擴大 oracle 的 quote 規則，也不改回應再評分。保留為高品質 region OCR 候選，標點差異仍可見；未驗 actual PictureItem／完整圖片、同版 image artifact 回填。 |
| G1-E07，公式 Eq2 | 兩個 case、條件、equation label `(2)` 及 footnote marker2 保留，marker 指向 performance；未編造 crop 外的註腳內容。 | `\footnotemark[2]` 是 LaTeX macro，尚未驗 Markdown math renderer 支援／render；brace／dollar 檢查不能取代實際渲染。只支持固定 crop 的來源重建，不代表 detector、inline discovery、footnote body／anchor 或 Canonical 交付合格。 |
| G1-O03，英文 scan | 兩段16個 source lines 在既有允許正規化後相符且相鄰，右欄 bullet 不插入。額外 spot-check 的 `previous PLMs` 亦保留。 | 選定範圍通過；未將整頁其他文字、註腳關係及未見頁面全部評成通過。 |
| G1-T02，六 panel Table2 | 84/84 source numeric bindings 與 printed strings 正確、0 unmatched extra、無重複 panel／header 問題；全部8項 critical comparison 成立，caption body／三項條件語義保留。 | caption 欄位漏了字面 `Table 2` 前綴，已明列而不補字再評分。這張表提供數值與關係重建的可行證據；schema／Markdown／來源連結及其他 G1 表仍待驗，未採用全頁 producer 或正式 profile。 |

完整84點以 `(panel, setting, metric)` 作對應，逐個與 frozen oracle 比較；不是搜集相同數字後計數。缺值／錯值／重複綁定／不明 metric 不擴大分母，八個必要比較另算。獨立來源 review 又逐一目視28列／84個 printed strings，確認原始精度與條件綁定，未把 Table3 的值當 Table2。表格評分器以設定錯置、重複列、額外值、同組數值對調 metric、critical value 改錯五個負例驗證，英文另測跨欄插入會被拒絕；synthetic oracle 候選只存在離線 self-check 記憶體，不曾放進 API prompt。[評分器](pdf-core-g2-api-2026-10-14/review/evaluate.py) · [完整逐點結果](pdf-core-g2-api-2026-10-14/review/results.json) · [來源交叉核對](pdf-core-g2-api-2026-10-14/review/review.md) · [逐任務 verdict](pdf-core-g2-api-2026-10-14/review/verdict.json)

## 時間與資源的可比範圍

| 任務 | client round trip 秒 | prompt tokens | completion tokens，含 reasoning | reasoning tokens |
|---|---:|---:|---:|---:|
| NCCU panel | 9.218 | 334 | 453 | 299 |
| SEAL Eq2 | 9.748 | 211 | 359 | 237 |
| 英文整頁 | 16.212 | 2493 | 1822 | 201 |
| SkillOpt p8 Table2 | 15.925 | 2613 | 1931 | 348 |

總計5651 prompt／4565 completion tokens，其中1085 reasoning；四次各一個樣本，client 重用同一 HTTP client，未另外作 warm/cold、p95 或持續併發。時間含網路／遠端排隊／模型與服務處理，無法拆出純 inference、GPU placement 或 serving queue；不和本機 predict_batch 秒數混作 GPU 加速倍數，也不當作高頻 ingest 的端到端 SLO。官方文件沒有在本次查閱的 sizing table 中明列 Luna 的確切 patch／縮放規則，保留 `high` 設定，不假設等於原圖每個 pixel 都進入模型。

## 公開來源與首次審查

首次執行在建立 process 前被 automatic approval review 拒絕，理由為影像被判作未經具體授權的敏感外送。當時沒有 API request，也沒有輸入 credential。完成公開來源檢查後，以同一明確 API 動作重新審查並獲准，才執行這四次；沒有改用其他管道繞過拒絕，沒有剩餘權限阻擋。

SEAL／SkillOpt 官方 arXiv PDF 均重新公開下載、HTTP200，SHA 與 G1 固定來源一致。LLM survey v1 亦相同；scan 的兩頁 embedded RGB 分別與公開原稿 p3／p5 的144dpi render 逐 pixel 相等，實際 API 只用固定 scan p1。NCCU 是公開操作手冊中的一般系統導航 panel，來源僅含 UI labels／指示與 generic link，無個人姓名、帳號／ID 或實際自述；選定 crop 與本機 Image35 原始解碼 pixels 相等。官方 URL 可由 web 讀取，但本次直接 GET403，因此未宣稱重新取得的 NCCU PDF bytes hash 相符。[公開論文 SHA](pdf-core-g2-api-2026-10-14/source-checks/public-arxiv.json) · [OCR／scan 來源證據](pdf-core-g2-api-2026-10-14/source-checks/ocr-order-findings.md)

## 對執行方向的影響

建議保留 Standard 的 native／layout／普通表與已可行的 code 小模型，繼續驗證 **針對必要區域的 VLM 重建與回填**。這次表格84點與公式分支／註腳的改善，提供比繼續盲試相同小模型更具體的路徑；不據此把所有 PDF 頁面都改走大 VLM。任何 selective routing 都還要驗來源 inventory／required-work，不能只憑 confidence 保證發現所有錯誤。

這次直接 HTTP probe **沒有驗 Docling API engine 整合**：目前安裝的 engine 會加入 temperature，與此模型 `low` reasoning 的參數規則可能衝突。下一個接點驗證須固定真正的 request options／schema／parser，接回原 PDF page／bbox、Markdown 與 supplement，並測空值／截斷／錯誤不得冒充完成。這不是生產程式修復，也沒有升級或修改現有套件。

公司交付仍為地端開源 VLM／vLLM，Qwen3 只是既有候選。公司候選要對相同來源、相同必要比較另驗品質、API 相容、latency／GPU 與高頻負載。暫用 OpenAI 的效果與耗時都不轉移成 Qwen3 的證明；確切公司 model ID／GPU 資料仍待使用者補充。

其他真實 formula／code／inline、圖片圖意／chart、heading、跨頁表及其餘完整 G1 表、完整 Canonical／Acceptance／恢復與551頁 pilot 均未在此四次 API 比較完成。G1、前三輪輸出維持原樣，不改 oracle、不放寬必要門檻，也不將整體 G2 標成通過。

[離線完整性核對](pdf-core-g2-api-2026-10-14/verify.py) 另驗四個 request 可重建為記錄的 body hash、來源 PNG bytes 未變、response／parsed JSON 一致、無 credential pattern，以及前幾輪 payload 維持原 hash；見 [artifact manifest](pdf-core-g2-api-2026-10-14/artifacts.json) 與 [validation](pdf-core-g2-api-2026-10-14/validation.json)。本機檔案尚未 commit／push。
