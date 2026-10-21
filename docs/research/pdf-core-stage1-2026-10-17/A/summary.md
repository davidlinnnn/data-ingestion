# A：公式／code 發現與交付

結論：**完整來源 coverage gate fail；保留有界機械接合成果，不進第二段公式／code推論。** 這不是模型準度失敗，也不是 SDK 能力不可能的證明。

本輪沿用固定版 cached S0：Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3；四份來源實際 physical pages 是 controls 1、WikiSkill 20–22、SEAL 2–4、DGM 51。輸入 PDF／S0 hashes、版本與原生 fragments 在 `inventory.json`。未以歷史 Docling 2.102／Core 2.96 的 baseline 冒充本輪 S0。

## 實作及實際控制

- `producer.py` 是唯一通用方法：盤點全部原生文字角色及純公式 picture envelope；保留整個 owner／descendants／原始 provenance，不以原生非空 text 或完整 charspan 當重建 display formula 的門檻。沒有特殊字元、文件 ID、答案字串或 confidence 選路。
- 固定 inventory SHA256：`8f1961552cd6574a5d6f29614b1f5c297362d6310d63140ceb096ae349cbd593`；先封存，再交隔離 evaluator 核對。Producer 不讀 source census、舊 oracle、人工目標或 bbox；只收到缺口類型與數量，沒有據此補 jobs。
- `controls.py` 實跑7項合成正控制、25項新協定負控制；另重跑完整既有23項結構負例，將唯一輸出重導本目錄。舊 adapter 的 role 限制只作歷史控制，不成為本輪要求；新協定允許單一 owner 的多個合法 paragraph／heading 等 blocks。輸出內的語意重複、錯字與錯序仍須來源評讀，不能靠 schema 判準度。
- `cached_mock_gate.py` 對全部79個可達原生 owner 組裝合法 mock 並實際走公開 serializer：WikiSkill18、DGM7、SEAL37、controls17。圖譜及非目標 literal 均不變。四個原先空文字的 SEAL display formulas、另1個 WikiSkill 空文字公式可交付；三個 controls picture-child formulas 由原3個 picture envelopes處理，不額外加分。
- `ordering_counterexample.py` 實際證明本方法的限制：原稿順序 `BODY < middle < TITLE`，單一混合 owner 回填會成 `BODY < TITLE < middle`。因此 producer 明列同頁多 fragment 未解，不因合法多 block 回應就接受。見 `ordering-counterexample.json`。

公開官方部分為固定 Core 型別驗證及 Markdown serializer extension；自訂部分為 discovery／ownership、whole-owner協定、來源 binding、既有 marker substitution。未修改 SDK，亦不把通用 API 協定稱為原生 CodeFormula 任務。

## 完整來源 gate

隔離 evaluator 看原稿全部8頁後封存 `../A-evaluator/source-census.json`，再比對上述固定 inventory；完整 oracle 留在 evaluator 目錄，不餵入 producer。它回饋的44個來源分組 spans：33個有完整 eligible envelope、7個表格內目標未發現、1個 caption 邊界未支援、3個圖內／混合 owner 僅部分 eligible。**44是來源分組單位，不是 calls；79是可達原生工作候選，也不是完整 calls 上限。**

155筆原生 owner inventory 中76筆未支援，包含被公開 stock serializer 隱藏的子項、furniture等；不能把76筆全當來源必要目標失敗，也不能把它們全排除。必要性由獨立來源契約決定。

原41項契約、完整新 census、保護正例、cross-page joins 的獨立對照證據在 evaluator 目錄，與本次 mock 分開。舊5項未準備工作沒有跳過：4個 display formula 接點成立；混合正文／Algorithm標題仍阻擋。局部成功不能抵銷表格／圖內必要內容漏送。

Evaluator另以7個未修改的歷史 payload涵蓋4個保護正例與4個cross-page joins，驗證目前固定 ownership 的逐字單次運輸及非目標／原生文件不變。這是 saved replay；3個 join payload 原本已有內部斷段且原樣保留，不能宣稱來源或段落回歸完整通過。普通陰性段落27個中24個完整 eligible，3個 caption邊界未支援。詳見 evaluator-only `saved-payload-replay.json` 與 `producer-coverage-comparison.json`；producer未讀這些答案。

## 停止及下一段

現有單 owner 方法尚無完整的表格／圖內／caption及混合 fragment ownership與閱讀順序方法，因此停在有證據的 fail，不新增 oracle bbox、文件特例、修值或第二套 renderer。這是目前唯一方法未通過，不代表一切通用方法不可能。

`results.json` 明列 `N_CF=null`、`N_3=null` 及 output／input／transport caps未就緒原因；79候選工作不冒充完整分母，不編造 token 預算。由主線先決定是否值得補通用 ownership／ordering 方法及跨元件表格涵蓋，再談固定推論。

完整計時由父 `../registration.json` 的A started_at／deadline起算，包含來源盤點、隔離評讀、實作及控制；結束時間另在 A/registration.json 封存。原稿與歷史 helper／oracle／產物保持只讀，所有新增檔案均在指定研究目錄。

未執行模型、API、安裝、holdout或第二／三段；機械 mock 成功不代表準度、成本改善或完整 profile 已可交付。
