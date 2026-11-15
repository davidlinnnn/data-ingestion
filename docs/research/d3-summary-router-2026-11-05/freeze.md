# #166 事前登錄：d3-flash 當 summary verify 的 router

**狀態：凍結（2026-11-05）。** 使用者 2026-11-05 已裁定以下事項：

- 證據改用 Section 文字，不用頁面圖（#166「方法」一節已更新）。
- A1 選選項 1：LLM 抓得到的錯，router 一個都不能放過。
- A2–A4 照建議（見 §4、§5）。

輸入、問題與程式都已備齊。各檔的 SHA-256 寫在 `freeze.json`，此時還沒有任何 d3 輸出（`d3_outputs_seen: 0`）。只要 hash 不符，`run_d3.py` 就拒絕啟動。流程沿用 #153（[freeze.md](https://github.com/davidlinnnn/data-ingestion/blob/research/153-d3-quality-check/docs/research/d3-quality-check-2026-11-02/freeze.md)）：問法和門檻只用 dev 選，test 只跑一次；與 #153 不同的地方列在 §8。

## 1. 模型與 runtime

- **模型**：`vllm-sr/d3-flash@67e03e1bc157961c582ee7c6a35d9b15fada3dec`。每次執行前，本機權重都要對過 `weights-d3-flash.json`（#153 已驗過，從 #153 複製過來）。
- **存取方式**：只經由 `POST /v1/systemone`，不在行程內載入模型。
  - 服務是模型套件的 `d3_server.py --device mps --batch-size 1`，port 8166（被佔用時拒絕啟動），每次執行產生新的 bearer key，HF 離線。
  - runtime 用 #153 的 venv（transformers 5.17.0）。
  - 請求一次只送一個，每個請求各自一次 forward。
- **heavy-lock**：整個執行包在 `scripts/heavy-lock 166-d3-flash -- …` 裡。
- **讀什麼分數**：Q1 讀 `probabilities["supported"]`，Q2 讀 `noul`（P(yes)）。不讀 `confidence`（理由同 #153）。

## 2. 資料、單位與切分

- **標註**：沿用 #155 frozen-1 的 t5b 產物（`accuracy-dev.json`、`accuracy-held-out.json`）。
  - 原句標「正」。
  - 植入句只取 t5b 的 `valid()` 判為有效的，標「錯」。
  - LLM 的判決沿用 t5b 的 `planted_supported`／`original_supported`，它們是和同一個 Section 的其他句子一起批次判的（D4）。
  - dev：50 原句、45 植入；held-out：100 原句、86 植入。
- **verify 單位**：frozen-1 裡每一次「第一次 verify」呼叫算一個單位：
  - 一個有句子的 Section，或一句 overview 句子（overview 每句單獨驗證）；
  - 句子取進入 verify 時的版本，也就是被 repair 之前的原文。
  - 共 703 個單位（dev 167、test 536）、1,072 句。
  - `build_inputs.py` 重建了每篇論文的 verify 呼叫數，含 repair 後的重驗，20 篇全部和 record 的 `steps.verify.calls` 相同。
- **切分**：照 t5b。dev 是第 2、4、6、16、20 篇，test 是其餘 15 篇。
- **請求**：每個不重複的（論文、Section 組合、句子）送一次請求，dev 404 個、test 905 個（`inputs-counts.json`）。範圍包含：
  - 單位句子；
  - 保留的最終句（標註原句和植入句的同批句子要用）；
  - 植入句；
  - 負對照。
- **負對照**（只在 dev）：45 句 Section 類的 dev 原句，各配上同一篇論文裡另一個有摘要目標的 Section（seed 166）。

## 3. 證據與問題

- **state**：`{category, paper_title, sections: [{heading, text}], sentence}`，內容和 D4 的 LLM verify 讀的一樣：論文標題，加上句子被驗證的那幾個 Section。不送圖片。
- **問題**（`questions.json`）：前導句改寫自 D4 的 verify prompt 規則（只對這些 Section 和標題判；改寫可以；文字沒寫或寫得不同的數字、因果、主體、範圍、比較都不算）。
  - **Q1**：`choice`，三個選項 supported／partly_supported／unsupported。
  - **Q2**：`noul`，問「每個主張都有支撐嗎」。
- **送法**：dev 的請求兩題都帶；test 只帶 dev 選中的那一題。

## 4. 選擇（只用 dev，`router.py select`）

1. **選問法**：比較 Q1 的 P(supported) 和 Q2 的 P(yes) 在 dev 上的 AUROC（原句對有效植入）。高者勝；平手選 Q2（同 #153）。
2. **`t_route`（A1 選項 1）**：分數 ≤ t 就標記。取「LLM 抓到的每個 dev 植入都被標」的最低 t，也就是這些植入的最高分。
3. **`t_route_alt`（A1 選項 2，只報告）**：最多放過 ⌊0.05 × 45⌋ = 2 個植入的最低 t。
4. **router 的規則（A2）**：一個單位裡只要有一句被標，整個單位就送 LLM；沒有就跳過。
5. **`t_d`（給 #161 的事後類別）**：
   - 照 #153 §5.2 的規格做 Platt 擬合：單調，a ≥ 0，L2 λ = 1，不搜尋超參數。
   - 再照 #153 §5.4 選門檻：校準後機率 ≤ t_d 就標；條件是 dev 上被標的項目裡真錯比例 ≥ 0.80；符合條件的門檻中取抓到錯最多的，平手取較低的。
6. **負對照只報告，不改變任何選擇**：報原句對錯配 Section 的 AUROC 和中位數。若 AUROC < 0.75，報告的結論寫成「d3 沒有可靠地讀證據」。

`selection.json` 和 `test-launch.json`（記 selection 的 hash）commit 之後才能跑 test，`run_d3.py test` 會檢查這一點。

## 5. Test（只跑一次，`router.py evaluate`）

`run_d3.py test` 只能執行一次。`--resume` 只送還沒有結果的項目，任何項目都不會送第二次。報告的指標：

- **AUROC**：附 2,000 次 bootstrap 的 95% 區間（seed 153）。分群用 verify 單位（A3）：原句和它的植入句共用同一個單位，同一單位的多筆案例一起抽。
- **在 `t_route` 和 `t_route_alt` 兩個門檻上**，各報以下數字，都附 Wilson 區間：
  - d3 recall；
  - **整體抓錯率**（保守）：植入句自己被標，而且 LLM 判它不受支撐；另報單位層級的版本（同批句子被標也算送 LLM）；
  - LLM 在被標植入句上的抓錯率；
  - 誤刪率：有 router 和只用 LLM 各一個；
  - 跳過的單位比例，Section 和 overview 分開；
  - frozen-1 裡被 LLM 標過的自然句子，還有多少會被送到 LLM；
  - 省下的 token。
- **跳過率對 recall 的曲線**：test 上每個出現過的分數都當一次門檻。
- **`t_d`**：
  - 標註集上的標記數、精確率、recall、正確句被標的比例。標註集裡錯句約佔 46%，比自然情況高很多，所以這裡的精確率會偏樂觀，報告要註明。
  - test 論文中已交付的句子有幾句被標，並對這些句子做盲評（§6）。
- **ECE**：10 個 bin，校準前、後各一個。
- **延遲**：每次請求在 client 端量到的 p50／p95／最大值，和 input tokens。dev 帶兩題、test 帶一題，分開報。換算 #88：每篇約 53.6 句，50 PDF/min 等於約 45 req/s。
- **token 模型**：用 20 篇論文各步驟的實際總量做最小平方擬合（不加截距）：
  - verify prompt = a·呼叫數 + b·字元數；
  - verify completion = c·呼叫數 + d·判的句數；
  - repair 同理。

  省下的量 = 被跳過單位的第一次 verify。跳過的單位也不會再 repair 與重驗，這部分另外列一行，因為「省下」它也等於放棄修正。

## 6. 已交付句子被標記的盲評（#166 的問題 3）

`flagged-delivered.json` 裡的句子交給 Claude Opus 5.5 子代理（effort high）盲評。若超過 60 句，以 seed 166 抽 60 句。

- **看什麼**：只看論文標題、Section 文字和句子，不看 d3 的分數。
- **規則**：D4 verify prompt 的原文。
- **輸出**：supported／unsupported，加一句理由。
- 這樣做的獨立性低於人審，報告會註明。

## 7. 對 vLLM-SR 本體的介面確認

- **時機**：test 跑完之後，在 `scripts/heavy-lock vllm-sr` 底下執行。
- **啟動指令**：`vllm-sr serve vllm-sr/d3-flash --engine --platform cpu --revision 67e03e1b… --max-num-seqs 1 --batch-window-ms 0 --dtype float32`。
- **送什麼**：5 個 test 項目：最低分、最高分，以及 3 個最接近 `t_route` 的。
- **比對**：答案形狀要相同，|Δ分數| ≤ 0.02。#161 用 d3-mini 量到的差是 0.0011。不量延遲。
- **前提**：Docker VM 記憶體 ≥ 44 GiB，因為 flash 的 FP32 權重約 34 GB。做不到就記為「未執行」並寫明原因，改引 #161 用 d3-mini 做過的同一介面確認。

## 8. 與 #153 的差異

- **證據**：證據是文字（state 裡的 Section），不送圖片。
- **錯誤來源**：錯誤是植入的（gpt-6-luna），不是模型真的寫錯；錯誤的比例也不是自然比例（見 §5 的 `t_d`）。
- **只量 d3-flash**：使用者已裁定模型。不跑 nano／mini，也沒有 runtime 控制組；權重和 runtime 都和 #153 的 flash 相同。
- **經由 HTTP**：透過 `d3_server.py`，不在行程內呼叫 `system_one`。
- **新規則**：`t_route` 是新的；bootstrap 改按 verify 單位分群，不是按來源頁。

## 9. 已知的洩漏與限制

- 探索資料時，我讀過 1 筆 held-out 原文（第 15 篇，S2 被改成 S3 的數字植入）。問題用 D4 的通用規則寫成，沒有為任何案例調整。
- 原句一律標「正」。#155 抽查時確認了 judge 的 1 筆誤刪是 judge 判錯；抽查中判為「植入太弱」的案例沒有逐筆紀錄，所以不做敏感度分析。
- 植入錯誤可能比自然錯誤容易抓。
- MPS 上選的門檻不能直接帶到 PROD runtime（ADR-0011：上 PROD 前要重驗）。
- 本票只量論文。Markdown、PPTX 的 Section 文字（特別是投影片的短句片段）分數分布可能不同，要重新校準。

## 10. 不進 git 的資料

`~/archive/research/166-d3-router/`：`items.json`、`units.json`、`cases.json`、`steps.json`（都含論文文字），以及 `runs/`、`flagged-delivered.json`。repo 裡只放計數、分數摘要和不含文字的指標。

## 11. 執行順序

```sh
.venv/bin/python docs/research/d3-summary-router-2026-11-05/build_inputs.py FROZEN OUT
.venv/bin/python -m pytest docs/research/d3-summary-router-2026-11-05/test_router.py
.venv/bin/python docs/research/d3-summary-router-2026-11-05/freeze.py FROZEN OUT      # commit
scripts/heavy-lock 166-d3-flash -- D3_PYTHON docs/research/d3-summary-router-2026-11-05/run_d3.py OUT dev --package PKG
.venv/bin/python docs/research/d3-summary-router-2026-11-05/router.py select OUT    # commit selection + launch
scripts/heavy-lock 166-d3-flash -- D3_PYTHON docs/research/d3-summary-router-2026-11-05/run_d3.py OUT test --package PKG
.venv/bin/python docs/research/d3-summary-router-2026-11-05/router.py evaluate OUT
```

FROZEN = `~/archive/research/155-summary/frozen-1`，OUT = `~/archive/research/166-d3-router`，PKG = `~/models/issue84/d3-flash`，D3_PYTHON = `~/archive/data-ingestion-153-untracked/d3-runtime/venv/bin/python`。
