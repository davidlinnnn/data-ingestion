# #174 事前登錄：d3 summary router v2（d3-flash 下限）

**狀態：凍結（2026-11-08）。** 使用者 2026-11-07 的裁定見 #174：B1 本機 d3-flash 當下限，B2 容忍 5%，B3 閘門 30%，B4 #135 等本票；自然錯誤由 Claude Fable 5.1 盲判代替人工複核，不確定的決策同樣交 Fable 協助。

各檔的 SHA-256 在 `freeze.json`，此時沒有任何 d3 輸出（`d3_outputs_seen: 0`）。流程沿用 #166（[freeze.md](../d3-summary-router-2026-11-05/freeze.md)）：選擇只用 dev，held-out 只跑一次。與 #166 不同的地方列在 §9。

## 1. 模型與 runtime

- **模型**：`vllm-sr/d3-flash@67e03e1bc157961c582ee7c6a35d9b15fada3dec`，權重對過 `weights-d3-flash.json`（同 #166）。
- **存取**：只經由 `POST /v1/systemone`，服務是模型套件的 `d3_server.py --device mps --batch-size 1`，port 8174，每次執行新的 key，HF 離線，runtime 是 #153 的 venv（transformers 5.17.0）。
- **heavy-lock**：每次執行包在 `scripts/heavy-lock 174-d3-flash -- …` 裡；held-out 的 Seam B 同樣拿 heavy-lock。
- **分數**：每題都是 `noul`，讀 P(yes)；不讀 `confidence`。

## 2. 資料與切分

- **dev**：#155 frozen-1 全部 20 篇，直接用 #166 的 inputs（`~/archive/research/166-d3-router`），去掉 #166 的負對照。703 個 verify 單位、1,072 句單位句子，其中 LLM 標過 67 句；t5b 標註 150 句原句、131 句有效植入（`inputs-dev.json`）。
- **held-out**：20 篇新的論文，§7。
- **verify 單位與路由**沿用 #166：單位是 frozen-1 每一次第一次 verify 呼叫；單位裡任一句分數 ≤ t，整個單位送 LLM。
- **請求**：每個不重複的證據（論文標題加 verify 讀的 Section）一個請求，668 個；每句每題一個 question，句子寫在 question 裡，證據只放在 state。

## 3. 自然錯誤複核（`review.py`）

- **候選**：dev 是 LLM 標過的 67 句單位句子，加 #166 盲評判為不受支撐的 15 句已交付句子；held-out 是 LLM 標過的單位句子。
- **誘餌**：同數量、LLM 沒標過的單位句子，seed 174 隨機抽。
- 候選和誘餌一起打亂、以盲 id 分 8 包，同一證據的句子同包。每包交一個 Claude Fable 5.1 子代理（effort high），prompt 同 #166 的盲評（[blind-prompt.md](../d3-summary-router-2026-11-05/blind-prompt.md)），套 D4 verify 規則原文；評審看不到 d3 分數，也不知道哪些是候選。
- **確認的自然錯誤** = 被判為不受支撐的候選（`confirmed.json`）。誘餌的不受支撐比例報告為評審嚴格度的參考，不改變任何標註。
- 門檻規則只用「LLM 標過且確認」的錯誤；#166 盲評的 15 句是 LLM 沒抓到的，只用於描述性的 AUROC。
- dev 的複核在 `format.json` 之前 commit；held-out 的在 `evaluate` 之前 commit。

## 4. 問題組與格式（`questions.json`）

- 前導規則改寫自 D4 verify：只對 Section 和標題判，改寫可以。
- **G**：每個主張都有支撐嗎（#166 的 Q2，句子移到 question 裡）。yes = 正確。
- **針對性問題**，yes = 有這類錯誤：
  - **C**：Section 沒寫的因果、理由、目的或效果；
  - **S**：把例子、條件、特定情境、子集或傾向擴大成一般情形；
  - **Q**：加、刪或改限定詞與語氣（只、全部、必須、可能、might 等）；
  - **E**：把性質、動作、結果或數字歸給不同的主體。
- 原計畫的 N（數字與比較）不放：#166 的 G 對植入的數字與比較錯誤已經 recall 100%，省下 1/6 的 MPS 時間。
- **合併規則**：G = P_G；T = 1 − max(P_C, P_S, P_Q, P_E)；M = min(G, T)。分數越高越像正確。
- **state 格式**：JSON（`{category, paper_title, sections}`，同 #166）或純文字（`Paper title: …`，每個 Section 一段 `Section: 標題` 加內文）。

## 5. 執行（`run_d3.py`）

| run | 資料 | 題目 | 格式 |
|---|---|---|---|
| `fmt-json`、`fmt-text` | dev 的格式子集：候選、t5b 原句與植入，共 358 句（`format-subset.json`） | G | 各自 |
| `dev` | dev 全部 1,264 句 | G、C、S、Q、E | `format.json` 選中的（須已 commit） |
| `test` | held-out 全部 | 選中規則用到的題 | 選中的；`selection.json`、`test-launch.json` 須已 commit，`test-launch` 記 selection 與 held-out 請求的 hash |

每個 run 只執行一次；`--resume` 只送沒有結果的請求。

## 6. 選擇（只用 dev，`router.py`）

1. **格式**：格式子集上 G 的 AUROC（確認的自然錯誤與有效植入，對 t5b 原句）。純文字要比 JSON 高至少 0.01 才選純文字，否則 JSON。
2. **門檻（B2）**：n = 確認且 LLM 標過的 dev 自然錯誤數，允許 k = ⌊0.05n⌋ 句落在被跳過的單位裡。每個規則取「最多放過 k 句」的最低 t（`route_threshold`），也就是跳過最多單位的 t。
3. **規則**：三個規則中跳過率最高者；差距 1 個百分點以內取較簡單的（G、T、M 依序）。
4. **閘門（B3）**：選中規則在 dev 的跳過率 ≥ 30% 才建 held-out。沒過就寫報告結案，不建 held-out。
5. 植入錯誤的 recall、整體抓錯率和誤刪只報告，不參與選擇。

`selection.json` commit 後才建 held-out；`test-launch.json` 在 held-out 請求建好後 commit。

## 7. held-out 語料

- **來源**：arXiv API，首次提交 2026-07-01 到 2026-10-31，依提交日期由新到舊。三個分層的數量同原語料（skill／tool／程序 8、memory 6、較廣的 agent 演化 6），查詢式記在 `heldout-corpus.json`。
- **依序收下**符合以下條件的論文：不在原 20 篇裡、沒被前一個分層收下、PDF 10–50 頁、有文字層（每頁平均 ≥ 1,000 字元）。Seam B 的 summary 失敗的論文記錄後由同分層的下一篇遞補。
- 論文只放在 `~/archive`；repo 只記 arXiv id、版本、頁數與 SHA-256。
- **摘要與標註**：t5b-seam-b（DEV profile，Claude Sonnet 5.5）跑 20 篇；t5b-accuracy 抽 100 句植入（gpt-6-luna）並判決，規則同 frozen-1 的 held-out。API 費用上限 USD 15。
- 摘要程式是目前的 dev（含 #164 的 repair 重送）；verify prompt 與 frozen-1 相同。

## 8. held-out 指標（`router.py evaluate`）

在選中的規則與 `t_route` 上，都附 Wilson 區間：

- 跳過的單位比例，Section 與 overview 分開；
- **確認的自然錯誤（LLM 標過）仍送到 LLM 的比例**；
- 植入錯誤的 d3 recall、整體抓錯率、只用 LLM 的抓錯率；誤刪（有 router／只用 LLM）；
- AUROC：自然錯誤對原句、植入對原句；全部錯誤的 bootstrap 區間（按單位分群，2,000 次，seed 153）；
- 省下的 token（#166 的 token 模型重新擬合在 held-out 的 20 篇上）；
- 曲線：每個單位最低分當一次門檻，跳過率對自然錯誤仍送到 LLM 的比例。

## 9. 與 #166 的差異

- dev 是全部 20 篇；held-out 是新論文。
- 自然錯誤經複核，並且是選門檻的主要依據；植入錯誤降為只報告。
- 門檻容許放過 5%，不再取「一句都不能放過」的極值。
- 問題組多了四個針對性問題與三種合併規則；比了兩種 state 格式。
- 請求改成每個證據一個請求（ultra 的 state-once 形狀）；flash 每題仍各自一次 forward。
- 不做 `t_d`（#166 已否定 (b)）、不做負對照（#166 dev 的 AUROC 1.000）。

## 10. 已知的洩漏與限制

- **問題組參考了 #166 看過的錯誤**：#166 test 的 3 句漏網與 15 句盲評錯誤的類型，影響了 C、S、Q、E 的寫法。這些論文現在都在 dev，所以 dev 的數字偏樂觀，held-out 才算數。
- **評審都是 Claude**：verify 是 Sonnet 5.5，複核是 Fable 5.1；沒有人工複核。
- **LLM 的判決有雜訊**：#164 量到同一個 judge 重跑會翻掉一些判決，所以「LLM 抓得到」本身不穩定。
- **flash 的負結果不代表 ultra**；門檻、分數分布、負載、延遲都不能帶到 ultra 或 PROD（ADR-0011）。
- 只量論文。

## 11. 不進 git 的資料

`~/archive/research/174-d3-router-v2/`（dev 與 held-out 的 requests、units、cases、steps、複核包與判決、`runs/`）與 `~/archive/research/174-heldout/`（論文 PDF、Seam B 與 t5b-accuracy 的輸出）。repo 只放計數、分數摘要和不含文字的指標。

## 12. 執行順序

```sh
.venv/bin/python $D/inputs.py dev OUT
.venv/bin/python $D/review.py pack OUT dev
.venv/bin/python $D/router.py subset OUT
.venv/bin/python -m pytest $D/test_router.py
.venv/bin/python $D/freeze.py OUT                                              # commit
scripts/heavy-lock 174-d3-flash -- D3_PYTHON $D/run_d3.py OUT fmt-json --package PKG
scripts/heavy-lock 174-d3-flash -- D3_PYTHON $D/run_d3.py OUT fmt-text --package PKG
.venv/bin/python $D/review.py tally OUT dev                                    # commit
.venv/bin/python $D/router.py format OUT                                       # commit
scripts/heavy-lock 174-d3-flash -- D3_PYTHON $D/run_d3.py OUT dev --package PKG
.venv/bin/python $D/router.py select OUT                                       # commit; gate
# gate passed: held-out corpus (§7), then
.venv/bin/python $D/inputs.py heldout RUN SET OUT
.venv/bin/python $D/review.py pack OUT heldout
.venv/bin/python $D/router.py launch OUT                                       # commit
scripts/heavy-lock 174-d3-flash -- D3_PYTHON $D/run_d3.py OUT test --package PKG
.venv/bin/python $D/review.py tally OUT heldout                                # commit
.venv/bin/python $D/router.py evaluate OUT
```

D = `docs/research/d3-summary-router-v2-2026-11-08`，OUT = `~/archive/research/174-d3-router-v2`，PKG = `~/models/issue84/d3-flash`，D3_PYTHON = `~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python`。
