# #153 事前登錄

**狀態：凍結（2026-11-02）。** 使用者已裁定範圍、補資料、門檻與重判結果（A1、B1、B4、C1–C3、R1–R4，見 §2.2）；標籤、切分、問題與評分程式都已備齊並寫入 `freeze.json`（各輸入檔的 SHA-256），此時尚未產生任何 d3 輸出（`d3_outputs_seen: 0`）。`run_d3.py` 在 hash 不符時拒絕啟動。

**重跑原則（使用者裁定）**：門檻依賴的東西一律重新產生，不沿用 Codex 產出的數字。W4b 的結果只當對照；#84 來源的 gold 全部重判（§2.1）。

沿用 #84 W4b 的流程（`docs/research/pdf-core-w4b-d3-2026-10-20/report.md` §2）：凍結問題、選擇、校準與門檻規則，只用 dev 選問法、校準、選門檻，test 每個模型只跑一次。和 W4b 不同的地方逐項標出。

## 1. 模型與 runtime

| 模型 | 固定 revision | 權重 |
|---|---|---|
| d3-nano | `vllm-sr/d3-nano@462efc366229ea268cf4eed3738b3fc4415e4817` | W4b 已下載、已對過 HF 的 LFS SHA-256 |
| d3-mini | `vllm-sr/d3-mini@bd0090dd758d32ba59ef5c749910a8e87fc4391f` | 同上 |
| d3-flash | `vllm-sr/d3-flash@67e03e1bc157961c582ee7c6a35d9b15fada3dec` | 本票下載到 `~/models/issue84/d3-flash/`，hash 記在 `weights-d3-flash.json` |

- flash 的這個 revision 和 W4b 抓過程式碼的 `13dc1cc8` 相比，只多了 `.eval_results/safeagents-judge-bench.yaml`。程式、權重與模型卡完全相同，所以 W4b 的遠端程式碼審閱（`remote-code-audit.md`）仍然適用。
- **官方用法**（flash 模型卡）：`AutoModel.from_pretrained(path, trust_remote_code=True)`，再呼叫 `model.system_one(state=…, questions=…, images=[…])`。
  - 問題型別：`choice`、`noul`、`score`。
  - 圖片最多讀 1.6 MP。
  - 不改 runtime、權重或 prompt renderer。
- **權重清單**：`weights_manifest.py` 把本機每個檔案對 Hub 該 revision 的檔案樹（LFS 檔對 SHA-256，其餘對 git blob SHA-1），結果在 `weights-d3-{nano,mini,flash}.json`；nano、mini 各 25／27 個檔案全部相符。flash 下載完成後同樣驗證。
- **環境**：獨立 venv，transformers 5.17.0（模型卡驗證的版本）、torch 2.14.0、torchvision 0.29.0，鎖檔是 `requirements.lock.txt`。
  - 和 W4b 的差異：W4b 用 transformers 5.20.0。
  - 控制組：nano 用 W4b 原題重跑 W4b 的 81 筆 dev（`run_d3.py --control`），和 W4b 存下的機率比對，差異寫進報告。這是換版本的負對照，不參與任何選擇。
  - **控制組結果（凍結前已跑）**：81 筆全部成功，Q1、Q2 分數和 W4b 存下的完全相同（最大差 0），沒有網路嘗試；p50 延遲 0.87 秒（W4b 1.03 秒）。這次的 runtime 可重現 W4b。
- **執行條件**：
  - MPS，BF16 backbone、FP32 readout，batch 1。
  - 一次只載一個模型，不和 docling 或其他模型同時跑。
  - 推論子程序設 HF 離線，並擋 socket，記錄網路嘗試次數。
  - 只在 Codex sandbox 外執行。
- **讀什麼分數**：choice 讀 `probabilities["faithful"]`，noul 讀 `noul`，**不讀 `confidence`**。HF 路徑的 confidence 是 1 − normalized entropy，見 `document-content-screening-methods-2026-10-23/d3-probe/part-a.md`。

## 2. 盤點與可評性

來源縮寫：
- T4 = `docs/validation/80/t4-accuracy/`
- T3 = `docs/validation/80/t3-accuracy/`
- AR = `~/archive/data-ingestion-wip-2026-10-21/untracked/docs/research/`
- LP = `AR/pdf-core-r1-method-2026-10-20/live-preflight/`
- W4b = `AR/pdf-core-w4b-d3-2026-10-20/gold.json`

「錯」只算真實模型或方法的錯，不含人工擾動。沒有輸出的項目狀態是 `failed`，不算 d3 要判的錯。

最終標籤（B1／B4 重判與 R1–R4 裁定之後；「正」含 minor）：

| 類別（`paper-pdf@1` 的輸出） | 判定單位 | 正 | 錯 | 錯例所在頁數 | 主要來源 | 判斷 |
|---|---|---:|---:|---:|---|---|
| formula LaTeX | 一個公式回答 | 162 | 58 | 31 | W4b W3 50（CodeFormulaV2，B4 重判）；T4 五輪不重複回答 170（Luna 107、Opus 72）。W4b R5 的 28 筆排除：裁圖是段落、對應的是行內數學，`paper-pdf@1` 不重建行內數學 | 可設門檻 |
| description | 一段圖意描述 | 414 | 37 | 28 | W4b 28（B4 重判）；T4 Luna r1／r2、Opus、Sol 共 99；B1 的 324 張圖（fixture 160＋round-1 prompt 重答 164）。2 個 UNKNOWN 排除 | 可設門檻 |
| 表格結構（`docling-parse`＋`table-status`） | 一張表的格線 | 30 | 29 | 24 | AR `per-table-final.json` E0 23 張＋`cellFalse` 36 張（B4 重判：舊標籤只比對值，不比對位置，8 張由 PASS 改 FAIL） | 可設門檻 |
| picture-ocr | 一張圖的 OCR 文字 | 15 | 14 | 10 | LP `round4-local-ocr`（#84 RapidOCR，B4 重判） | 可設門檻 |
| figure_type | 一個類型 | 319 | 5 | 5 | B1 的 324 張圖 | 只報 AUROC（C1） |
| chart_values | 一個數值點 | 506 | 36 | **1** | W4b 101；T4 Luna／Opus r1／r2、Sol，共 4 張圖的點；逐點結果用 t4 比對器在本機重算 | 只報 AUROC（A1）；36 個錯點全在同一頁，按頁 bootstrap 無意義，不做 C2 判定 |
| 生成的 caption | 一個 caption | 321 | 3 | 2 | B1 的 324 張圖 | **不可評**（R4）：錯誤率 0.9% 本身就是發現 |
| code（VLM 只在沒有字層時用） | 一個程式區塊 | — | — | — | W4b 40 | **不評**（A1），沿用 W4b 結果 |
| 閱讀順序 | 一頁 | — | — | — | 5 個事件 | **不評**（A1） |
| 文件摘要 | 一個句子 | — | — | — | #155 尚未產出 | **移交 #155**（A1） |

### 2.1 補資料與重判（B1、B4）

- **B1 圖片類**：
  - 盲評 144 份未判的 Luna fixture 回答，每份判 caption、description、figure_type 三欄。
  - Luna（`gpt-6-luna`）用 t4 第 1 輪的 prompt 與設定，重答同樣 144 張，一起盲評。這組錯例來自較弱的 prompt，報告會揭露。預估花費約 US$0.10。
  - 使用者抽查 20 個判定：10 個判錯的、10 個判對的。
- **B4 重判 #84 來源的 gold**：W4b formula 78 筆、W4b description 28 筆、表格 59 張、picture-ocr 29 張圖，共 194 筆。
  - 盲評時不看舊標籤。
  - 和舊標籤不一致的，全部交使用者裁定。
  - chart 在本機重算比對結果，使用者只看判錯的點。
- **盲評的執行方式**：判定者是 Claude Opus 5.5 子代理（effort high）。規則凍結在 `judging-rules.md`：
  - 公式沿用 t4 README 的規則；
  - description 沿用 #84 的 meaning-slice 規則；
  - caption、figure_type、表格、OCR 各一條；
  - 判定時只看裁圖、整頁與回答，不看模型名稱和舊標籤。

### 2.2 重判的執行結果與裁定

- 盲評共 27 批（`judging/batch-00…26.json`），1,138 筆有效裁決，每個需判的項目恰好一筆（`merge_verdicts.py` 檢查）。
- **判定規則的兩條修正**（batch-00 試評後、其餘批次前，記在 `judging-rules.md`）：粗體是字母樣式；裁圖是評判對象，W4b R5 行內數學排除。
- **打包程式的兩個錯誤**（我的錯，皆已修正並重判）：round-1 prompt 的 164 筆最初 crop／page 角色互換（66 個 task 重判）；又因角色互換，同頁的圖被併成一個 task，25 個 task 的圖和回答不對應、41 張圖沒送評（`repack_r1prompt.py` 重打包 66 個 task）。合併時以「packet 的圖必須等於項目的圖」丟掉 75 筆無效裁決。重判前看似「描述了同頁另一張圖」的 caption FAIL 幾乎都是這個錯誤造成的，不是模型的錯。
- **使用者裁定**（`judging/overrides.json`，規則本文不改）：
  - **R1**：公式只差粗體的 11 筆改為 minor（Y = 1）。理由：T4 的 170 筆 gold 與 #152 的狀態規則都不比對粗體，兩個來源要用同一把尺。
  - **R2**：其餘 25 筆 B4 不一致全部採用新裁決（公式真錯 10、表格 8、OCR 簡繁 2 改 FAIL、OCR 純符號空白 2 改 PASS、description 3）。
  - **R3**：B1 抽查 20 筆（10 FAIL、10 PASS，seed 153）由 Fable 5.1 代使用者複核，使用者只裁決有異議的；17 筆同意，3 筆 description 翻為 PASS（b1-0307 θ_t／θ′_t、b1-0418 Musique／Music、b1-0317 箭頭上下方向）：單一符號讀錯而關係不變，屬逐字 OCR，與其他評審對 b1-0294／0325／0352 的判法一致。此複核的獨立性低於人審，報告如實註明。
  - **R4**：生成的 caption 負例只有 3 個，報為不可評。

已知的重疊與洩漏：

- **公式**
  - T4 有 4 個公式和 W4b 是同一個來源單位（p03、p05 在 test，p07 兩個在 dev），但被判的是不同的回答。
  - T4 的 46 個公式曾用來調整 #152 的規則，所以拿它們算 `FORMULA_NATIVE_MISMATCH` 的成績會偏樂觀。d3 的問題本身沒有用這批資料調過。
  - 同一個公式可能有多個錯誤回答（46 個公式中，18 個至少有一個錯）。錯例彼此相關，所以信賴區間按來源頁做 bootstrap。
- **描述**：round 2 的 prompt 是看過 round 1 在同 18 張圖的失敗後才寫的。
- **我看過 W4b 的 test 錯例**（`ret/rev`、right-clicking）。所以問法只沿用 W4b 的原文，加上一句 t4 判定規則裡本來就有的通用規則，不為個案改寫。

## 3. 問題寫法

每類兩題：
- **Q1**：四選一 `choice`（faithful／minor_difference／meaning_changed／cannot_determine）。
- **Q2**：`noul`，問「是否忠實保義」。

criteria 用官方格式，也就是「選項 → 一句定義」。前導句和選項定義沿用 W4b `questions.json`。state 只放 `category` 和 `reconstruction`，不放 gold、理由或定位提示。

| 類別 | 圖片 | 問法 |
|---|---|---|
| formula | 公式裁圖 | W4b 原文，**加一句** t4 的判定規則：calligraphic、blackboard 或大小寫不同，算不同符號；`\text`／`\mathrm`／`\texttt`、空白、換行、句尾標點、`*` 與 `\star`、`\epsilon` 與 `\varepsilon`、`a/b` 與 `\frac{a}{b}` 都視為等價。這樣問題才和 gold 的判定標準一致 |
| code | 程式裁圖 | W4b 原文 |
| description | 整頁＋目標圖 | W4b 原文；加整頁圖，是因為我們的方法本來就同時送整頁和目標圖 |
| chart_values | 目標圖 | W4b 原文；一題判一個點，state 是「series、x、y」 |
| picture-ocr（新） | 目標圖 | "Judge the recognised text against the visible text in the picture. Every legible word, number and label must appear with the same characters; reading order and line breaks do not matter. A missing or misread item changes meaning." |
| 生成的 caption（新） | 整頁＋目標圖 | "Judge whether the generated caption is supported by the picture and its page. It need not copy the source caption; an entity, relation or claim the picture does not show changes meaning." |
| 表格（新） | 表格裁圖 | "Judge the table grid in state (Markdown, one row per line) against the table image; a caption line above the grid is not judged. Every cell value and its row and column position must agree, including header spans; spacing and number formatting with the same value are permitted." |
| figure_type（新） | 整頁＋目標圖 | "Judge whether the figure type in state (one of chart, diagram, photo, screenshot, table, other) fits the picture. A type the picture is not a plausible member of changes meaning; a mixed figure may carry the type of any of its parts." |

完整文字由 `make_questions.py` 從 W4b `questions.json` 產生，存成 `questions.json`。state 的 `category` 名稱：formula LaTeX、generated image description、reconstructed chart data point、recognised text、generated caption、table grid (Markdown)、figure type。W4b 的 description 只送裁圖；本輪 description、caption、figure_type 送整頁＋裁圖（方法本身的輸入）。圖片先縮到 ≤ 1.6 MP（LANCZOS，同 W4b；`prepare_inputs.py`），444 張中 131 張縮過。

## 4. 切分

- W4b 的 266 項保留原本的 dev／test。W4b 的 `split_group` 就是來源頁，dev 和 test 不共用來源頁。
- 新項目以**來源頁**分組（`build_split.py`，seed 153）：
  - 評分是逐類別獨立做的，所以 W4b 的切分只約束「W4b 在該頁判過的類別」：同一頁的其他類別（例如 OCR）自由分配。按整頁繼承時，OCR 的錯例會變成 dev 3／test 11，不符合 C1。
  - 其餘頁貪婪分配到讓每類 dev 和 test 的錯例數（相對該類總數）、再來是項目數，最接近的一邊；dev:test 約 1:1。
  - 和 W4b 約 3:7 不同：這次 dev 的負例最缺，所以改成 1:1。
- 同一類別裡，同一來源頁的所有回答（不同模型、不同輪次）都落在同一邊（已檢查：沒有任何「頁 × 類別」兩邊都有）。
- 切分結果（`split.json`，凍結後不重切）：

| 類別 | dev n／錯 | test n／錯 | C1 |
|---|---|---|---|
| formula | 110／29 | 110／29 | 門檻 |
| description | 186／18 | 265／19 | 門檻 |
| table | 29／15 | 30／14 | 門檻 |
| picture-ocr | 16／7 | 13／7 | 門檻 |
| figure_type | 162／2 | 162／3 | 只 AUROC |
| chart | 122／0 | 420／36 | 只 AUROC（dev 無錯例，問法依規則取 Q2） |
| caption | 162／1 | 162／2 | 不可評 |

## 5. 選擇、校準與門檻

每個「模型 × 類別」只用 dev：

1. **選問法**：比較 Q1 的 P(faithful) 和 Q2 的 P(yes) 在 dev 的 AUROC（correct 對 meaning_changed，minor 不算）。高者勝；平手或都算不出來，選 Q2。（同 W4b）
2. **校準**：做一次單調、正則化的 Platt 擬合，規格同 W4b `protocol.json`（a ≥ 0，L2 λ = 1，不搜尋超參數）。dev 只有單一類別時不擬合。
3. **verified 門檻**：同 W4b。在 dev 校準後的分數中，取「放行項目改義率 ≤ 2%」裡覆蓋最多的門檻。這只用來看有沒有希望；真正開放 verified 仍依 #83 的條件（每類 ≥ 300 項）。
4. **disputed 門檻（新）**：校準後的保義機率 ≤ t_d 就標 `disputed`。t_d 在 dev 上選，條件是「被標的項目裡真錯的比例 ≥ **P**」，再取抓到錯最多的那個；平手取較低的 t_d。**P = 0.80**（C3），和現行 formula 規則的精確率（6 標 5 中）同一水準。
5. **弱訊號的條件（新）**：test AUROC ≥ **0.75**（C2），而且按來源頁做 bootstrap（2,000 次、seed 153）的 95% 下界 > 0.5。
6. **可評的最低樣本（新）**：dev 和 test 各至少 **5** 個錯例（C1）才選門檻。不到 5 個但總錯例 ≥ 5 的，只報 AUROC 和信賴區間，不設門檻。更少的標「不可評」。

順序：三個模型的 dev 依序跑完（nano → mini → flash）。所有選擇、校準和門檻寫進 `selection/<model>/selection.json` 和 `test-launch.json` 後，才依序跑 test，每個模型一次，不重跑、不重選。

## 6. 公式的額外問題

在 test 的公式回答上，用現行狀態規則（含 #152 的字母樣式比對）算 `FORMULA_NATIVE_MISMATCH`，回報四件事：

- 規則抓不到的錯裡，d3 在 t_d 下抓到幾個；
- 規則和 d3 任一標記時，正確公式被標的比例；
- 規則和 d3 都標記時，正確公式被標的比例；
- 以上都附樣本數和 Wilson 95% 區間。

報告另列兩個後續候選（使用者裁定，數字出來後再決定是否開票）：`disputed` 之後重打 VLM 修正；以及 #159（CodeFormulaV2 和 VLM 的公平比較，擋 #135）的結果對本類結論的影響。

只有 T4 的公式有原生字層可以比對。W4b W3／R5 的公式若找不到原 PDF，不納入這一項，並註明。

## 7. 報告指標

- **AUROC**：用原始 safe score，附來源頁 bootstrap 的 95% CI。
- **ECE**：10 個等寬 bin，分校準前和校準後。
- **verified**：覆蓋率、放行項目的改義率，以及 Wilson 95% 上界。
- **disputed**：標記數、精確率、召回率、正確項目被標的比例，各附樣本數和 Wilson 95% 區間。
- **成本**：p50／p95 延遲、峰值 RSS、MPS driver 記憶體，以及含載入的整批時間。
- **公司 GPU**：只引用官方 MI325X 的數字，並註明 MPS 上選的門檻不能直接帶到其他 runtime。
- 0/0 記為 N/A，不記成 0%。

## 8. 分工與資料

- **d3 推論**：Claude 在 sandbox 外執行。
- **評分與校準程式**：Codex 寫（codex-delegate，過 plan gate；`MAPPING.md`、`SMOKE.md`），主線獨立驗證：`score.py`／`test_score.py` 98 個測試通過；`reproduce_w4b.py` 從 W4b 原始輸出重算，494 項全精度數字全部相符（最大誤差 8.5e-17），24 項只差顯示位數，皆列在 `SCORING.md`。`select` 需要 `test-counts.json`（test 各類錯例數，取自 gold，不看分數）才能套用 C1。
- **新判定**：盲評由 Claude Opus 5.5 子代理執行（effort high），判定規則凍結在 `judging-rules.md`；抽查見 §2.2。
- **不進 git**：裁圖、第三方論文文字、權重與 d3 原始輸出，放 `~/archive/data-ingestion-153-untracked/`。git 只放本文件、`freeze.json`、問題與規則、hash manifest、程式和報告。
