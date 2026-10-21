# PDF core G2 第三輪：繁中 recognizer 與 Granite-Docling CPU 比較

[Research index](README.md) · [G2 計畫](docling-pdf-core-g2-pipeline-start-2026-10-14.md) · [第二輪](pdf-core-g2-round2-2026-10-14.md) · [需求 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

2026-10-14（Asia/Taipei）。**已完成六次有界 CPU 推論。Granite-Docling-258M 可在本機 CPU 執行，所選英文兩段的順序改善、公式找回第二分支；但公式格式／註腳、複雜表格與繁中 OCR 仍未合格。** G2 尚未全面通過，沒有採用新正式 Processing Profile。

## 結果與採用判斷

固定 G1 原始 PDF／圖片、physical page、SHA、oracle 和門檻，不修改 production code、既有 baseline runtime 或原始來源。模型推論單 worker 依序執行，CPU 明確指定；沒有使用 MPS／MLX／CoreML／AUTO、GPU 或 remote API。

| 任務 | 本輪具名候選／範圍 | 結果與處置 |
|---|---|---|
| 圖片 OCR：G1-O01 | RapidAI PP-OCRv5 mobile／server ONNX recognizer；同一 685×230 中央 panel、原 v6 detector＋v2 classifier | mobile 五項僅二項正確、server 三項；兩者仍有 `統→统` 等錯字。未採用作此來源的直接替代。 |
| 公式：G1-E07 Eq2 | Granite-Docling-258M 官方 formula preset／`<formula>`；與第二輪完全相同的約120dpi crop | 兩個 case 分支完整度改善，`0 / Otherwise` 找回；但漏掉註腳 marker 2，condition 的 LaTeX／尾端 tag 仍錯。84 tokens、正常 EOS；此結果未合格。 |
| 閱讀順序：G1-O03 | 同 Granite 的完整掃描頁、官方頁面 prompt→DocTags→官方 parser | 選定兩段內容在允許正規化後相符，兩段相鄰，右欄 bullet 不再插入；僅所選範圍通過。整頁其他段落發現 `previous PLMs` 被改成 `previous LLMs`，不能採用為整頁來源保真已合格的 producer。 |
| 表格：G1-T02 | 同 Granite 的完整 SkillOpt physical p8，包括 Table2／Table3 與上下文 | 六區塊有分開輸出，但必要第三 metric 大量缺失、header 合併、mini-batch `8/16/32` 變成 `5/6/7`，panel(f) 重複；八個 critical comparison 都未獲接受。保留84點分母，未計完整全表 error%。 |
| 表格 task isolation：同 G1-T02 | 相同 Granite，第二輪完整 TABLE cluster 的原始144dpi crop＋官方 `<otsl>`，不切小 panel | 專門 table 任務仍漏 mini-batch32 整列、panel(c)全部15個 metric、panel(f)全部12個 metric；header 仍合併。不能作六 panel 表的修復，亦不能把外部 caption／來源回填視為已交付。 |

## OCR：模型宣稱支援繁中，不等於此來源已合格

Paddle 官方將 PP-OCRv5 mobile／server 列為支援繁中的 recognizer；本次用 RapidAI 自行發布、具版本路徑與 hash 的 ONNX 檔，未引入非官方轉檔或安裝新套件。mobile 16,631,306B，server 84,577,022B，下載與推論分開。版本 tag 不當作不可變 revision，實際 SHA 固定本次模型 bytes。[Paddle 官方 recognition module](https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html)、[RapidAI 整合說明](https://rapidai.github.io/RapidOCRDocs/main/blog/2025/05/30/rapidocr-%E9%9B%86%E6%88%90-pp-ocrv5_rec-%E6%A8%A1%E5%9E%8Bmobileserver%E8%AE%B0%E5%BD%95/)

這次 recognizer 比較比前兩輪更能隔離變因：輸入圖片 bytes、detector 框／scores、classifier 結果與 preprocessing mapping，皆與第二輪 fixed-panel-1x 相等。三個實際 ONNX sessions 都是 `CPUExecutionProvider`；4 intra-op／1 inter-op、batch1。錯誤已存在 raw recognizer，五個來源框均非空，並非 blank-filter 移除。

兩個內建字典都含全部 oracle 漢字，包括 `統／結`；字典與 CTC output class 數相符。因此不能把錯字歸因為詞彙缺漏，也不能做全域繁簡轉換後宣稱來源保真。兩個候選都未達五項通過，因此沒有額外跑 actual PictureItem scale3 分支。

[OCR 完整比較](pdf-core-g2-round3-2026-10-14/ocr/review.md) · 逐位置字串與來源 (`pdf-core-g2-round3-2026-10-14/ocr/selection-review.json`) · 固定來源檢查 (`pdf-core-g2-round3-2026-10-14/ocr/review.py`)

## Granite：小模型能跑，任務結果分開判斷

本次固定 `ibm-granite/granite-docling-258M` revision `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`。權重 515,093,104B，匿名下載13個必要檔案約20.063秒；所有 bytes hash 保存，LFS 檔與官方固定 revision hash 相符，使用獨立 cache，未改既有 baseline 模型。Docling2.102.0／Core2.96.0／Transformers5.8.1／Torch2.14.0；實際全部 parameters 驗證為 CPU FP32，4 intra-op／1 inter-op、batch1、compile=False、quantized=False、trust_remote_code=False。下載與 hash (`pdf-core-g2-round3-2026-10-14/vlm/download.json`)

模型卡明確提供 `<formula>`、`<code>`、`<otsl>` 與整頁 conversion 任務。本輪用官方 preset、engine 和 parser；直接 component probe 省略完整 pipeline lifecycle，不能等同正式 `VlmPipeline` 或 Standard enrichment 已接通。[固定 revision 模型卡](https://huggingface.co/ibm-granite/granite-docling-258M/blob/982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe/README.md)、[具體 API／parser 與範圍](pdf-core-g2-round3-2026-10-14/vlm/research.md)

公式輸入與第二輪 CodeFormulaV2 的 input PNG **byte 相同**，約120dpi，使用官方 `<formula>` prompt／postprocess；兩種模型的結果可作這個固定 crop 的比較，沒有暗中改 crop 或提高解析度。Granite 生成內容已包含 `1` 與 `0` 分支，但註腳 marker 2 消失、只保留 equation label `(2)`；條件文字有不平衡 `$`／混入 LaTeX。不只以「看得懂」作為可交付的公式內容。Engine 輸出 (`pdf-core-g2-round3-2026-10-14/vlm/seal-eq2/raw-output.json`) · 清理後公式 (`pdf-core-g2-round3-2026-10-14/vlm/seal-eq2/cleaned.txt`)

**另定位出一個 engine 清理缺陷**：離線用固定 tokenizer 解碼保存的 generated IDs，模型確有生成完整 `</formula>`／`</doctag>` 與 EOS；目前安裝的 Transformers engine 用 `text.rstrip(pad_token)` 清尾端，`rstrip` 把 pad token 當字元集合，連前一個 tag 的 `>` 也刪掉。這能精確重現保存的 engine output。公式後處理因此留下 `</formula`，不能歸因為模型未生成 closing tag 或 token budget 截斷。原始 IDs、未受該清理影響的 decode 與重現檢查另外保存，沒有修改官方套件；漏註腳、條件格式與表格漏值在清理前已存在，仍未通過。離線 decode 證據 (`pdf-core-g2-round3-2026-10-14/review/token-decode.json`) · [獨立來源核對](pdf-core-g2-round3-2026-10-14/review/review.md)

兩個全頁任務保留原 PDF physical page，按 scale2 render，直接送入官方 engine，未再乘2。prompt 為 `Convert this page to docling.`，明確 `skip_special_tokens=False`，4096-token 探測上限；公式上限512。三次皆正常 EOS，分別84／1673／1601個生成 tokens，未撞長度上限。engine metadata 的 num_tokens 含 input，不拿來當生成 tokens。

原始文字先保存，再用 `DocTagsDocument.from_doctags_and_image_pairs`／`DoclingDocument.load_from_doctags` 產生結構與 Markdown。解析成功不代表完整或正確；這次表格錯誤已存在 raw output。孤立圖片 parser 的 page1／pixel bbox 與原 PDF physical page／point 不同，來源 mapping 保留於 input.json，尚未實作正式回填。頁面輸出與其中較好看的表格不能直接送入 Canonical Acceptance。

公式／整頁 runner (`pdf-core-g2-round3-2026-10-14/vlm/probe.py`) · CPU 執行記錄 (`pdf-core-g2-round3-2026-10-14/vlm/observations.json`) · 英文 Markdown (`pdf-core-g2-round3-2026-10-14/vlm/english-scan-p1/document.md`) · SkillOpt Markdown (`pdf-core-g2-round3-2026-10-14/vlm/skillopt-p8/document.md`)

## 專門 OTSL table 任務補充

再以同一 model revision 比較 `<otsl>`：直接重用第二輪完整 TABLE cluster 的896×250 PNG（SHA `e15d7737e1fd4dc28dde61fd7845dc00a59cda731a521a6a8bebc39b3a9dfc9a`），不重裁、不放大。六 panel 標題／條件與全部84個 source numeric bbox 皆在 crop 內；caption 在外。此比較同時改變 task 與上下文，不稱為單一 prompt 的因果 ablation。

435個生成 tokens、EOS、未撞4096上限。輸出為沒有 opening wrapper 的 bare OTSL，依官方 `parse_otsl_table_content` 解析成一個 TableData，保存 adapter 與格式異常，不把多個 OTSL block 硬併；兩個 block 分開解析、bare OTSL 及非 OTSL 拒絕均有離線自檢。沒有捏造 producer bbox 或補上 caption 關係。

raw producer 已缺 mini-batch32 三個值、panel(c)五列15個 metric、panel(f)四列12個 metric，至少30個來源數值沒有必要 panel／setting 關係；不是 parser 才丟失。這是具體遺漏證據，不拿30／84冒充完整分類的全表 error%。完整 table task 記錄 (`pdf-core-g2-round3-2026-10-14/vlm/table-crop/README.md`) · OTSL raw (`pdf-core-g2-round3-2026-10-14/vlm/table-crop/run/output.txt`) · 結構結果 (`pdf-core-g2-round3-2026-10-14/vlm/table-crop/run/document.json`)

## 本機可行性與 latency

| 工作 | child wall 秒，包含 import／load／輸出 | predict_batch 秒 | sampled peak RSS GiB |
|---|---:|---:|---:|
| PP-OCRv5 mobile，固定 panel | 0.788 | OCR 含 engine load 0.398 | 1.183 |
| PP-OCRv5 server，同 panel | 0.793 | OCR 含 engine load 0.471 | 1.230 |
| Granite formula crop | 5.514 | 1.957 | 1.892 |
| Granite English full page | 27.115 | 24.087 | 3.030 |
| Granite SkillOpt full page | 29.155 | 26.192 | 2.649 |
| Granite 完整 Table2 crop，OTSL | 8.942 | 6.359 | 2.216 |

每個 child 啟動前 available memory 至少8GiB；180秒／6GiB sampled process-tree RSS 軟停止、0.25秒取樣。上述六次 exit0、無 timeout／guard。全頁 VLM 在這台 Mac CPU 可負擔單次小樣本；約24～26秒的 predict_batch 觀察也顯示不能直接假設高頻 ingest 的時效足夠。沒有推算整文件或 GPU 加速倍數，尚未定義／驗證高頻端到端 SLO。

Granite load timer 從 stage constructor 前開始，三次約1.431／1.105／1.146秒，包含 eager model load；與第二輪不涵蓋載入的重複 initialize() timer 不混比。predict_batch 包含 preprocessing／generation／decode；未拆純 generation。OS cache 未清空、各一次，不能叫 cold benchmark 或穩定 p95。

OCR 起初 enum 設定錯誤發生於推論前，失敗 runner／summary／log 已另存；不當成模型品質失敗或額外成功推論。來源檢查與研究可能重疊，推論 worker 沒有併跑，這些單次時間仍不是嚴謹的模型效能排名。

## 下一步與未解範圍

1. 保留 Standard／TableFormer ordinary-table 對照與 CodeFormulaV2 code-block 候選；不因 Granite 改善兩段順序就把全文 producer 全面替換。
2. OCR 應再驗具名繁中 recognizer 或 VLM region；公式要同時驗可用 LaTeX、註腳／inline 對齊及來源回填，不能只驗分支數。
3. 表格仍須通過六 panel、完整邏輯表、caption／條件與八個必要比較；較能分區的輸出也不可直接視為通過。保留每表≤5%及 critical comparison 門檻。Granite 這兩種 table 配置未修好來源，下一個 producer／分區方法須有新假設，不繼續盲試同一小模型。
4. 使用者已允許的暫用 OpenAI VLM API 可作下一比較，但確切 model ID／endpoint／已配置的環境變數名稱待提供，不請求在對話貼密鑰、不自行假設模型。公司 Qwen3／vLLM 候選用相同來源另驗，效果與 latency 不當作等效。

本輪未驗其他真實 OCR／公式／code、inline detector／回填、圖片分類／描述／chart、heading recovery、另外三張完整 G1 表、完整 Canonical 交付／Acceptance／恢復、remote API、公司 GPU 或高頻負載。人類未另行逐字認證本輪結果；所選來源由 Codex 交叉檢查。本機檔案未 commit／push；第一／二輪與 G1 原始證據保留。離線自檢 (`pdf-core-g2-round3-2026-10-14/review/check.py`) · 完整性核對 (`pdf-core-g2-round3-2026-10-14/verify.py`) · Artifact manifest (`pdf-core-g2-round3-2026-10-14/artifacts.json`) · 核對結果 (`pdf-core-g2-round3-2026-10-14/validation.json`)
