# PDF core G2：官方方法比較與本輪採用判斷

2026-10-15（Asia/Taipei）。承接使用者要求：以 Docling 元件／模型／方法選型為主，避免大量後處理；自主完成至真正需要投入取捨的決策點。使用者另確認 **OpenAI 可作 Qwen3-VL 暫代服務，公司部署資訊不阻擋本輪**；實際模型仍如實記為 `gpt-6-luna`。

**本輪結論：保留 Standard 與已證實有用的小模型作比較基底；不採用三組開發配置中的任何一組作完整 challenger，不進入 holdout／G3。** 官方 remote VLM 接點確實能執行，但目前模型輸出、原生格式交付與來源位置仍未滿足必要條件。提高推理強度改善部分來源內容，同時造成既有正例退化與約兩倍 client 時間，不能視為全域改善。這不代表 Docling 所有組合已達準度上限。

## 已一次完成的工作

1. [逐任務選型表](pdf-core-g2-official-method-2026-10-15/coverage.md)：16項任務、14個模型／方法身份，區分實測、歷史有界結果與只查到官方能力。OCR、表格、圖片、heading／order、公式／code及交付缺口都保留。
2. [官方接點預檢](pdf-core-g2-official-method-2026-10-15/preflight/results.md)：真實 `DocumentConverter → VlmPipeline → ApiVlmEngine → Core parser/assembly`，只用 mock 取代網路。DocTags 可保留 synthetic 公式／code／表／圖／座標，故選它作新比較；所測 MD／HTML 表示有資訊損失，沒有據此否定所有 HTML encoding。
3. [第二組登記](pdf-core-g2-official-method-2026-10-15/registration.json)：固定 Docling2.102.0／Core2.96.0、官方 DocTags 路徑、API及 `low`；8次真實請求，四份來源、41個固定來源工作單位，包括原先五項未執行內容。
4. [第三組登記](pdf-core-g2-official-medium-2026-10-15/registration.json)：最後一個預算名額，只將 `reasoning_effort` 改為 `medium`。8張實際輸入PNG完全相同，完整request唯一差異亦只有此欄；prompt、來源標準、parser與影像尺度不變。沒有逐案改 prompt、修答案或重跑挑成功。

兩組皆是**真正官方 pipeline**，不是將 direct HTTP probe 稱為 Docling 整合。API runtime 原生 `params` 覆寫 `temperature:null`、8192 completion cap、`store:false`；16次皆HTTP200、正常stop，沒有拒絕或撞cap。前後兩組方法與舊36個段落請求的工作範圍不同，不能當單變因速度／準度排名。[第二組獨立核對](pdf-core-g2-official-method-2026-10-15/api-verification.json)／[第三組獨立核對](pdf-core-g2-official-medium-2026-10-15/verification.json)

## 相同來源上的結果

| 指標 | 官方 DocTags＋low | 相同配置＋medium |
|---|---:|---:|
| 實際請求／固定來源單位覆蓋 | 8／41項全部嘗試 | 8／41項全部嘗試 |
| Raw來源評分：pass／minor／material | 33／2／6 | 36／2／3 |
| F13完整公式表示與原位交付（18項適用單位） | 4／18 | 6／18 |
| F14內容與區塊交付（7項適用單位） | 6／7 | 4／7 |
| 四個原正例：內容意思保留 | 4／4 | 3／4 |
| 四個原正例：原有必要交付保留 | 2／4 | 2／4 |
| 有超過0–500範圍座標token的頁面 | 8／8 | 4／8 |
| 保存的官方JSON：頁外bbox | 66 | 23 |
| Client RTT合計／中位秒 | 131.32／18.36 | 269.49／34.33 |

這些分母與層次不能加總成統一成功率。Raw評分的新rubric與舊自訂JSON契約的25／5／6不同；舊評分／原始資料保持不變。F13／F14子集合也會重疊，未包含全部幾何及Canonical條件。**來源有輸出不等於忠實交付。** [Low來源評分](pdf-core-g2-official-method-2026-10-15/review/results.md)／[Medium來源評分](pdf-core-g2-official-medium-2026-10-15/review/results.md)

具體採用障礙：

- Low把 `ReflACT` 寫成 `RefACT`；真實 DGM code 更換識別字、字面內容並漏行。四個新執行的SEAL display equations找回主要數學，但都漏掉原方程式編號。
- Medium修好該方法名、找回E14六處數學，仍改寫DGM code，另將原 `LM_theta` 改為 `L_M`，以及把theta prime改成theta下標t；這些不是型別排版問題。
- 部分模型DocTags的巢狀方式未依預期grammar，官方組裝把行內片段拆成獨立區塊；原始回應有公式仍不足以交付完整段落。Medium另有正確raw公式在原生parser遇到literal `<s` 時被截斷；code中的HTML entity亦被原樣保留，沒有猜補或解碼修復。
- 模型產生的座標仍有超界；保存JSON的頁外bbox與Markdown export的clamp警告分開記錄，不能稱為精確有效來源位置。跨頁E13的單一邏輯段落仍未完成。

所有41項保留在分母，四個原有正例按同一原判準核對。較高Raw通過數不能抵銷原正例退化、F13／F14交付損失及來源位置失敗。

## 保留哪些、停止哪些

建議保留 **Standard／Heron、TableFormer V1 accurate、具名模型的selective RapidOCR、偏好啟用的小classifier** 作比較基底。CodeFormulaV2僅保留已有code區塊的有界證據；新版heading recovery、方向校正及其他任務也保留各自已驗範圍。這不是全功能已合格 Processing Profile。

停止對這三組配置追加特例／prompt／後處理追分；不採用單一全域token guard，不猜補公式／code，不把結構合法或native `success`當Canonical Acceptance。傳輸負例另證明原生helper可吞錯後回空而pipeline仍稱success，因此實際run另保存並核對HTTP、非空內容與stop reason；這是完成性檢查，不是內容修補。

沒有因本輪失敗換框架、刪除F13／F14或要求每次人工批准。沒有部署、變更正式 `src`／profile、修改套件、開啟六份holdout或宣稱GPU／高頻驗證。

## 收斂後的投入決策

**建議下一輪改驗文件專用模型的原生輸出，而非繼續要求同一通用VLM生成DocTags。** 優先方向是 dots.ocr 原生layout JSON＋固定版本官方VlmPipeline；PaddleOCR-VL原生結果＋官方匯入為備選。優先順序依官方接點與客製成本選擇，不是未實測的準度排名。[官方短名單、版本與資源限制](pdf-core-g2-official-method-2026-10-15/next-cycle-options.md)

目前真正需要決定的是：是否投入新的文件專用模型驗證週期及所需執行資源，或在此收束並明記G2尚有必含能力缺口。原本三組配置預算已用完；沒有自行登記第4組或把新週期當作重新計數的調參迴避。若擴大模型搜尋，先補與六份holdout隔離的validation，既有曝光案例繼續作開發／回歸，不用holdout選方法。[既定protocol](pdf-core-g2-eval-freeze-2026-10-15.md)

使用者已允許OpenAI作Qwen3-VL替身，因此公司model ID／endpoint不是本輪阻擋；但要比較另一個專用checkpoint，仍必須實際執行該checkpoint，不能由OpenAI代證其品質。公司部署資料、GPU及高頻目標是後續正式環境驗證事項。[已修正的交接清單](pdf-core-g2-official-method-2026-10-15/company-validation.md)

## 時間、成本與證據限制

本輪新增16次真實推論，client RTT合計400.80秒。Low 35,440 tokens，medium 51,939 tokens；reasoning已包含在completion，沒有重複加總。按2026-10-15公開標準token費率估算合計約 **US$0.0250**，不是已核對帳單。Medium時間約2.05倍、token費率估算約1.98倍，單次8頁配對觀察不足以推算production SLO或GPU速度。[Low usage](pdf-core-g2-official-method-2026-10-15/usage.json)／[Medium usage](pdf-core-g2-official-medium-2026-10-15/usage.json)／[官方費率](https://developers.openai.com/api/docs/models/gpt-6-luna)

Observer沿用的安全遮罩regex在兩組SEAL p2各誤遮罩一次普通文字 `task-specific`。官方pipeline使用未改動的原回應，保存的sanitized response／raw DocTags則有此遮罩；精確replay差異另核對。該處在41個選定單位以外，不作模型錯誤、不從parsed結果偽造還原原始HTTP。其餘三份來源的保存回應可精確重放官方結果；所有歷史評分／輸出保留。

驗證僅針對固定41來源工作，沒有聲稱八頁其餘內容全數合格或整個corpus的準確率。完整Canonical交付／恢復與高頻／GPU資格仍未驗，G2尚未全面通過。

[結論已寫回 #84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6196380818)，原正文及44項功能列未變，issue維持OPEN；[exact readback](pdf-core-g2-official-method-2026-10-15/ticket-update.json)與[整體驗證](pdf-core-g2-official-method-2026-10-15/validation.json)保存本輪核對。
