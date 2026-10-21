# PDF-core 下一輪：官方 VLM 與 layout 元件的有界比較

日期：2026-10-17（Asia/Taipei）。狀態：**規劃完成，尚未啟動實驗。** 承接[官方路徑盤點](pdf-core-official-pipeline-options-2026-10-16.md)與使用者「規劃下一輪的目標及作法」。本次只查來源、套件 metadata、既有來源契約與評分紀錄；沒有安裝、建環境、下載／載入模型、推論、讀取 PDF／圖片／holdout 或修改 production。Paddle 維持暫停。

## 目的與本輪能作的決定

判斷 **Docling 原生模型／元件選擇，是否能改善已知內容、結構及來源定位缺口，並降低客製處理需求**。只比較兩個新候選，加一個必要的同版 baseline；不掃完整 model catalog，不接已失敗的自訂 continuation，不新增修字／parser／段落判斷演算法。

| ID | 配置 | 唯一要回答的問題 | 可以作出的結論 |
|---|---|---|---|
| **C1** | `VlmPipeline` + `nemotron_parse_v2` + MLX 8bit | 另一套官方模型、processor、prompt、parser 的整體方法，是否改善 formula／code／OCR／table／來源位置與關係？ | 整套方法的有界效益；不能把改善歸因到單一模型元件，也不能等同 NVIDIA BF16／公司 vLLM 成績。 |
| **S0** | 同版 `StandardPdfPipeline` + Heron default | 提供重新執行的共同 baseline。 | 本輪來源上的對照；不是把舊 2.102 結果挪成 2.132 成績。 |
| **S1** | 與 S0 相同，只改為 Egret medium preset | 替換 layout 模型及其官方 processor/config，能否減少漏區塊、誤分類、內容錯歸屬及下游順序錯誤？ | layout preset 替換的效果；不是所有模型輸入張量保持相同的權重 ablation。 |

本輪只決定「淘汰／保留為有界元件候選／值得規劃整合」。完整 Processing Profile、Canonical Acceptance、獨立泛化、公司 GPU／vLLM 與高頻 SLO 仍是後續資格。Standard 兩臂特意關 enrichment 以看清 layout 差異，不能列為已滿足所有必含功能的配置。

## 固定資料：11 頁，每配置一次

首先修正兩份不同的「八頁」清單不能混用：既有 **41 個來源單位**的正式 contract 對應 WikiSkill 20–22、SEAL 2–4、DGM 51、controls 1。若漏掉 WikiSkill 20／22 或 SEAL 2，就不能聲稱覆蓋全部 41 項。

| 來源 | 原檔 physical page，1-based | 目的／評分來源 |
|---|---|---|
| Controls | 1 | 受控 formula／code 正負例；計入原 41 項。 |
| WikiSkill `2608.27454v1` | **20–22，連續一次 conversion** | 原 41 項中的普通／inline math／跨頁段落與保護正例。 |
| SEAL `2506.10943v1` | **2–4，連續一次 conversion** | 原 41 項的公式、inline／跨頁 E13 及已知標題歸屬問題。 |
| DGM `2505.22954v1` | 51 | 原 41 項的真實 code、identifier、literal、縮排與 prose。 |
| SkillOpt `2605.23904v2` | 8 | **G1-T02** 完整六 panel Table 2；84 個數值綁定及 8 個 critical comparisons，與 41 項分開。 |
| NCCU 操作手冊 `SRC03` | 3 | **G1-O01** 截圖選定區域 5 項文字與順序／圖片歸屬，不宣稱全頁 OCR。 |
| 既有英文掃描 `SRC04` | 1（此 fixture 的第 1 頁） | **G1-O03** 兩段 16 行及跨欄干擾；原始頁標 3 不取代 fixture physical page。 |

**11 頁 × 3 配置 = 最多 33 個模型處理頁次；每配置 7 個連續範圍／單頁 conversion，共 21 次 conversion 呼叫。** 每頁仍可能有多個 OCR／layout／table 模型工作，另外計數；33 不是模型 forward 或 API 呼叫總數。Controls 首次 smoke 計在這 11 頁中，不另跑一次。沒有未計數的 context。

來源與評分權威：原41 項 contract (`pdf-core-g2-official-method-2026-10-15/review/contract.json`)、G1 cases (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)。沿用原 PDF 身分與 SHA，執行前核對實際檔案，不從模型輸出重選來源單位。表格 84 點、OCR 5 項、掃描 16 行都是原任務的子項，不能與 41 段落／工作單位合成一個總 accuracy。

全部都是已曝光開發／回歸來源。舊四個 validation 頁亦已被 DOTS 實測；本輪不重稱 unseen，不自動追加 confirmation。它們連同既有三個 context 頁若將來使用，須另列固定 retest 頁次。六份 holdout 保持未開封。本輪不擴 75 頁、551 頁 pilot 或其他格式測試。

## 固定方法與環境

三配置均以 Docling 2.132.0／Core 2.99.0／Parse 7.22.3／pypdfium2 5.14.0 為目標，顯式選 `PyPdfiumDocumentBackend`。同一原 PDF、同一頁範圍與 page render scale 2，保存實際輸入像素及來源座標。模型原生 resize／padding 可不同，須各自記錄，不能聲稱 processor tensors byte-identical。

| 項目 | C1 | S0／S1 共同設定 |
|---|---|---|
| 執行 | 現有 Mac MLX GPU；一個 resident worker、batch／concurrency 1 | 新隔離 CPU runtime；CPU FP32、4 threads、Torch inter-op 1；layout／OCR／table batch 1（不代表 pipeline 內部 stage 完全串行） |
| 模型身分 | `mlx-community/Nemotron-Parse-2.0-8bit`；固定目標 revision `e7e89479657fb3631028ac12b6bc0d5a59ceafe4`，**metadata／完整檔案尚待核對，不是已封存權重** | S0 Heron `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；S1 Egret medium `77ede7cc7bed96d853c58f319734803d6ea2ea5c`；均須核對完整模型／processor 檔案 |
| 官方設定 | `nemotron_parse_v2` prompt／`NEMOTRON_PARSE_V2` parser；cap 9000；有效 greedy temperature 0；保留類別／座標 special tokens；無額外 repetition penalty | Transformers layout、compile=False、score threshold 0.3；create_orphan_clusters=True、skip_cell_assignment=False、keep_empty_clusters=False |
| OCR／table | 不另接 RapidOCR／TableFormer；由 C1 原生方法產生輸出 | selective RapidOCR：原 PP-OCRv6 det／rec-small＋v2 cls，det／cls／rec=True、bitmap threshold 0.05、text score 0.5；ONNX intra 4／inter 1。TableFormer V1 accurate、cell matching=True，沿用原模型資產 hash／其餘設定 |
| Extras | 不另接 enrichment 或自訂 continuation | code、formula、picture classifier／description、chart extraction、heading hierarchy 均 off；同版原生 reading order／assembly，separators=True |
| 診斷／匯出 | 保存公開 `pages[*].predictions.vlm_response` raw，再保存 typed JSON 與 stock Markdown | parsed pages、page／picture images=True；保存公開結果中的 layout predictions、parsed cells、assembled items、原生 JSON 與 stock Markdown；不承諾有 pre-postprocessor raw boxes |

C1 的 decoder 是 8bit、vision 為 BF16；轉換卡沒有固定 parent SHA，因此不能稱為 NVIDIA 某一 BF16 snapshot 的已證明等價量化。現有 MLX engine 沒有把 Transformers／vLLM 的 repetition penalty 1.1 傳下去；`temp` 與庫 `temperature` 的命名差異，僅因目前預設 0 使本輪 greedy 成立。不得把 options JSON 當成有效參數證明。完整來源與實際呼叫界線見 [C1 技術筆記](pdf-core-native-round-2026-10-17/vlm-options.md)。

S0／S1 的完整相容依賴 lock 尚待建立；IBM models 必須滿足 `>=4.0.2,<5`，不能搬舊 3.15，也不原地修現有 MLX 環境的 Hub 2.2 衝突。先解析最小 PDF／local models／RapidOCR extras，取得單一 lock 後兩臂共用；不以 `[all]` 加入 office／chunking 等無關依賴。這是規劃中的準備工作，尚未安裝或宣稱 ABI 相容。

S0／S1 layout 實際讀取 `page.get_image(scale=1.0)`；輸出 images_scale=2 不代表 layout 也在 144dpi。可由公開接點取得的 OCR、layout、table 與 C1 processor 圖像尺寸／hash 分別保存，其餘標未捕捉。S0／S1 需核對相同來源／設定及可保留的 native／OCR cells；若 stage 前資料已不同，不能將後續差異純歸因於 layout。若公開結果無法還原當時 stage 輸入，則明列該層等價未確認，不宣稱所有內部 tensor／cells 相同。

## 執行順序與有界前置檢查

1. **登錄後才載模型。** 固定模型／processor 的不可變 revision、權重 hashes、完整 runtime lock、輸出選項、11 頁／來源 SHA、原 oracle refs、全部工作清單與資源上限。C1 固定 metadata 取回失敗則記「未就緒」，不退回 `main` 或悄換 checkpoint／精度。
2. **先驗機械性可執行。** 非模型 import／依賴、Metal、來源 render／實際 processor input、C1 raw 可保存、Standard 公開結果可保留、parser 可調用與來源座標轉換；oracle／答案／評分 bbox 不得餵模型。只檢查這三配置需要的接點，沿用既有控制，不建立新通用 preflight 框架。
3. **分開看 parser 限制。** C1 parser 的 Markdown flatten／code 型別限制已有靜態線索。pure parser 的內容損失須列交付 failure；只要有效輸入與原始輸出可保存，仍可完成這個有界辨識實測。不能再用舊自訂續接的失敗全面否決新模型，也不能把 raw 正確當成完整交付成功。C1 若接口／runtime 無法執行或 VLM raw 無法保存，停止該配置，不造私有 hook／新 parser。Standard 的 raw engine boxes 是局部變數、公開 layout predictions 可能已被更新；缺這層不阻擋整個 preset 比較，但不能細分 model／postprocessor 責任。
4. **先 C1，再 S0，最後 S1，依序單 worker。** 各配置只初始化一次，依固定順序 Controls → WikiSkill 20–22 → SEAL 2–4 → DGM 51 → SkillOpt 8 → NCCU 3 → scan 1。不每頁重載模型、不重跑 smoke、不補上下文。某一配置無法執行，不自動取消另一個獨立問題；S0／S1 若無完整配對，則不作完整因果比較。
5. **完成固定集後統一評分與去留。** 發現一般內容錯誤仍完成其餘固定頁，避免依結果選擇停止位置；不追加 prompt、model、scale、閾值或 best-of-N。環境／資源失敗則保留 partial／未嘗試狀態，所有單位留在原分母。

C1 預設 prompt 的 `<predict_no_text_in_pic>` 是此配置固有限制：NCCU 圖片文字是否出現仍記錄，缺少時標「此配置未提供／路由限制」，不能外推為模型所有圖片 OCR 任務均失敗。即使文字出現，也須依原 F08 契約評圖片 key／來源與 supplement 分離，不能直接灌入主要 Markdown 算完成。S0／S1 沒有獨立圖片 enrichment；相同地區分頁面 OCR 的實際輸出、圖片偵測與未實作的 supplement。

## 評分與可採用界線

C1 每個原來源單位按四層保存並評分：**實際 input／request → 未改動 VLM raw → 官方 typed document → stock Markdown**。S0／S1 保存公開可取得的 parsed cells、layout predictions／clusters、assembled items 與 Markdown；pre-postprocessor engine boxes／labels／scores 若沒有公開接點則標「未捕捉」，不以處理後結果冒充 raw，也不為此增加私有 hook。輸入、對應與型別正確不等於內容保真。

| 維度 | 評法 |
|---|---|
| 內容忠實 | 保留原詞、identifier、code literal／符號／縮排、數學關係及原明定等價；同義 LaTeX 可接受。一般字形 minor 沿既定容忍，不把 OpenAI/OpenAl 例外擴張到識別字／數值。 |
| 表格 | 完整 G1-T02、caption／六 panel／setting／metric 綁定與 8 項 critical comparisons；沿用每完整複雜表 ≤5% 規則，不能用84個數字字面命中代替正確關係，也不將未完整評讀的表報 error%。 |
| 結構／閱讀順序 | 原跨頁正例、跨欄正文順序、SEAL 標題歸屬及這11頁已有來源契約的新段／caption 等負例；保留正確邏輯關係，不要求特定 native label、額外 backticks 或單一 JSON item。僅存在於舊24項合成 continuation 控制、沒有這11頁來源對應的反例，不算新模型已覆蓋的自然負例，亦不作全面 veto。 |
| 定位／coverage | 對照已有來源 region 及 scope；分漏、重複、錯歸屬、座標合法、實際對齊。bbox 在頁內不等於定位正確；沒有可靠來源 oracle 的額外 layout 改善只列探索觀察。 |
| 表示／交付 | 必要 inline／display LaTeX 與 code 在主要 Markdown 的正確位置；圖片 OCR／生成描述與來源分開；raw 對而 parser／Markdown 壞仍列交付失敗。未啟用 enrichment 標未實作，不能豁免必含要求或說模型沒能力。 |
| 成本／完成性 | 初始化、render／processor、模型、parser／assembly／export、每範圍與逐頁時間，另列 crop／模型工作數、RSS／Metal 量測範圍。首個控制頁與後續頁分列，不清 OS cache、不稱嚴格冷啟動分布、不用單輪估 p95／vLLM／高頻SLO。 |

41 項以相同 contract 全列；保護原四個正例的**原有必要內容與交付**，不暗中改 rubric。每項結果分 pass／accepted minor／material／input failure／runtime failure／missing／unattempted；parser 空輸出、cap、timeout 或 native `success` 都不能讓缺失從分母消失。MLX `stop_reason=unspecified` 不能當作 EOS 證據；若無法證明自然完成，另標完成性未知，仍評已交付來源內容。

不新增「提升25%」這類任意總分門檻。報逐單位配對的**恢復、維持、新增退化**，按任務／來源分表，不把相異分母揉成總 accuracy。既有 41 項並非全頁 layout／table／heading inventory，沒有涵蓋的全文範圍明列未驗。

## 投入上限與停止規則

下列是下一次執行的**建議預算**，不是已投入時間、產品門檻或本次推論授權：

| 項目 | 上限 |
|---|---|
| 配置／推論資料 | C1、S0、S1 三組；11頁／組、33頁次。無自動 retry、額外 context、BF16／4bit／另一 Egret 尺寸。 |
| 共同準備 | 最多2小時，含 metadata／必要模型取得、隔離依賴 lock、capture與輸入檢查；超出就保存未就緒原因，不無限修環境。 |
| 模型階段 | C1最多45分鐘（初始化最多5分鐘）；S0／S1合計最多75分鐘（各初始化最多3分鐘）；全輪最多2小時。 |
| Conversion watchdog | 單頁範圍180秒；連續3頁範圍540秒。這是範圍總上限，不宣稱可硬性在每個內部頁180秒精準中止；另記實際逐頁資料。 |
| C1記憶體 | 單worker；取樣process-tree RSS上限20GiB、Metal allocator18GiB、cache256MiB，system available低於8GiB停止。啟動前須有容納預估峰值與餘裕的可用記憶體，否則延後／未執行，不關閉使用者程式。 |
| S0／S1記憶體 | 單worker，各取樣process-tree RSS上限12GiB；相同system available 8GiB停止線；不得與C1同時駐留。 |

上述RSS與Metal不是可相加的獨立記憶體；取樣峰值也不等於完整系統峰值。C1上限較舊DOTS高，是依模型路徑與其他機器的轉換者量測作研究預算，非本機實測需求。資源中止與辨識錯誤分開，不為跑完提高上限或切CPU／remote替代；若只有公司環境能跑，記錄需要補驗。

可證明的機械性方法／控制錯誤可修復並保留原失敗，前提是沒有改候選行為、來源真值／評分規則或新增模型呼叫。若 evaluator 有程式錯誤，保留舊版本與原分數，以同一修正版本重算所有保存輸出。模型已執行的輸入不為修 capture 重新推論；缺原始證據就標缺失。若要第二次實際推論，必須另列用途與預算，不暗扣成同一次。

## 最終交付與去留

交付一份配置／版本表、一份按來源／任務的配對結果表、必要成功／失敗原文及定位證據、時間／記憶體表，並給每個候選明確處置：

- **淘汰本配置：** 目標缺口沒有明確改善、不可執行，或只靠超出範圍的大量修補才能交付。保留實驗與未完成項，不自動換下一模型。
- **保留有界價值：** 某個事前列明的 material 缺口恢復，但另有退化或交付缺口；只說明適用任務，不能全域替換。
- **值得進一步整合：** 事前指定目標有實質恢復、原保護正例沒有 material regression，且能說明剩餘交付／維護成本。最多推薦一個下一階段候選；這仍不等於完整profile或G2通過。

下一個真正需要使用者的決策，是有證據後是否接受**具體的剩餘整合成本／公司補驗投入**。日常依賴 lock、固定來源核對與在既定預算內的工作不拆成多次批准。Paddle不因本輪失敗自動恢復，六份holdout不因有局部進步提前開封。

依據：[Docling固定版presets](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py)、[Standard](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py)、[layout stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/layout/layout_object_detection_model.py)、[NVIDIA模型卡](https://huggingface.co/nvidia/NVIDIA-Nemotron-Parse-2.0)、[Egret固定commit](https://huggingface.co/docling-project/docling-layout-egret-medium/commit/77ede7cc7bed96d853c58f319734803d6ea2ea5c)、[C1實際呼叫／parser及資源筆記](pdf-core-native-round-2026-10-17/vlm-options.md)、[舊續接原型停止結果](pdf-core-adapter-contract-2026-10-16.md)。

本文件是規劃，**不是已完成的實驗登錄或測試結果**；模型weights、單一相容依賴lock、實際輸入像素與行為相容性仍待執行階段固定／核對。
