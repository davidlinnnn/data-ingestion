# CodeFormulaV2 與 VLM 在同一批公式上的比較：技術報告（#159）

| 項目 | 內容 |
|---|---|
| 票 | #159（#80 的子票，擋 #135） |
| 量測日期 | 2026-11-07 |
| 狀態 | 量測與盲評完成；抽查與建議待使用者裁定（§9） |
| 受測方法 | `docling-project/CodeFormulaV2@ecedbe11`（docling 官方 formula stage）、`formula@1` 的 Luna（`gpt-6-luna`）、Claude Opus 5.5（上限） |
| 事前登錄 | `freeze.md`、`freeze.json`（凍結時 CodeFormulaV2 輸出 0 筆） |

## 摘要

#84 否決 CodeFormulaV2 時，沒有和 VLM 在同一批公式上比過。本票把它和 `formula@1` 的 VLM 放在 t4-accuracy 的同一批 46 個 display formula 上，以同一位盲評判定者、同一套規則判定。

| 方法 | 正確 | Wilson 95% | 主要錯誤 |
|---|---:|---|---|
| CodeFormulaV2，docling 官方裁圖（`cf-official`） | 29／45 | 0.50–0.77 | 字詞拼錯、上下標、邊距帶進相鄰文字（4 個） |
| CodeFormulaV2，`formula@1` 的裁圖（`cf-same`） | 34／45 | 0.61–0.86 | 字詞拼錯、打字機字體的 SE 讀成 `\mathbb{S}`、程式識別字 |
| Luna（`formula@1`，#152 之後） | 33／45 | 0.59–0.84 | 花體／黑板體字母、大小寫 |
| Opus 5.5（上限） | 44／45 | 0.88–1.00 | 1 個上下標 |

分母是 45：有一個公式四方都判 UNKNOWN（§5.6）。若依 t4 的裁定把它算成花體 C，四方是 29、35、34、44／46，Luna 和 Opus 與 t4 公布的數字相同。

- **CodeFormulaV2 沒有比 Luna 準**：
  - `cf-same` 對 Luna：只有一方對的公式是 8 比 7（符號檢定 p = 1.0）；
  - 官方裁圖更差：`cf-official` 對 Luna 是 8 比 12（p = 0.50），對 `cf-same` 是 2 比 7。
  - 三者都遠低於 Opus。
- **兩邊錯的地方不同**：
  - CodeFormulaV2 的錯多在 `\text` 裡的字詞拼錯（sore、compresion、pospose）和打字機字體；字母樣式只錯 1 個。
  - Luna 的錯一半以上是字母樣式與大小寫。
  - `cf-same` 和 Luna 同時錯的只有 4 個。
- **`FORMULA_NATIVE_MISMATCH` 對 CodeFormulaV2 仍然有效**：在 `cf-same` 上標 6 個，6 個都是真錯。在官方裁圖上，另外誤標 3 個正確的公式，原因都是邊距把方程式編號 `( 2 )` 帶了進來。
- **成本**：
  - 本機 CPU（docling 在 Mac 上只能用 CPU）每個公式中位數 22.3 秒。
  - 官方沒有公布 GPU 數字；社群在 NVIDIA L4 上量到約每個公式 1 秒。
  - 改用就要在公司部署 GPU worker。目前的 VLM 是公司以 API 提供的。

**建議（待裁定）：維持 `formula@1`（VLM）**。CodeFormulaV2 不更準，固定 prompt 也無法修正它的錯，換用還要多一套 GPU 部署。VLM 這條路的上限（Opus 44／45）高得多。CodeFormulaV2 的價值在於準度已知、可重現；若公司 VLM（Qwen3.8-27B）在 V10 測出的公式準度明顯低於 Luna，它是現成的備案。

---

## 1. 背景

- #84 結案（`docs/research/issue84-closure-decision-2026-10-20.md`）以「CPU 上每項約 140 CPU 秒、公式改義 25%」否決 CodeFormulaV2。那批是 #84 W3 的 50 個公式，和 VLM 用的 t4-accuracy 46 個公式不同，判定規則也不同。
- 使用者在 #153 裁定（2026-11-02）：用同一批公式和 `formula@1` 的 VLM 公平比較。本票擋 #135，這樣結果還能改變 `paper-pdf@1` 的公式方法（profile 尚未 released）。

## 2. 樣本與輸入

- **樣本**：t4-accuracy 的 46 個 display formula。每篇論文最多 3 個，seed 133，共 17 篇（`inputs.json`）。
- **輸入**：S3 stand-in 裡 t4-seam-b 真實執行留下的頁面圖（144 dpi）與來源 PDF。`prepare.py` 產生 `formula@1` 的裁圖與字層文字。
- **不進 git 的資料**：裁圖、PDF、字層文字與盲評 packet，放在 `~/archive/data-ingestion-159-untracked/`。
- **重現檢查**：對 Luna 的答案重算 `mismatch()`，得到的 6 個 `disputed` 和真實執行登錄的完全相同（`score.py` 每次計分都會檢查）。

## 3. 方法

### 3.1 四組答案

| 代號 | 輸入 | 來源 |
|---|---|---|
| `cf-official` | docling 官方裁圖：PyPdfium backend 從 PDF 重繪，scale 1.67（120 dpi），四邊各外擴 18% | 本票 `run_cf.py` |
| `cf-same` | `formula@1` 的裁圖（144 dpi，框不外擴） | 本票 `run_cf.py` |
| `luna` | 同上；`gpt-6-luna`、reasoning effort high、#152 的 prompt | t4-accuracy `targets.json` |
| `opus` | 同上；`claude-opus-5-5`、round 2 | t4-accuracy `responses/opus/` |

### 3.2 CodeFormulaV2 的官方用法

逐項出處見 `freeze.md` §4。重點如下：

- **模型**：revision `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`，是 2026-11-07 的 main，也是 #84 W3 用的版本。13 個檔案都和 Hub 該 revision 相符（`weights-codeformulav2.json`）。Idefics3 架構，約 0.3B 參數，BF16；授權 CDLA-Permissive-2.0。
- **呼叫方式**：用 docling 自己的 `CodeFormulaVlmModel`，設定 `CodeFormulaVlmOptions.from_preset("codeformulav2")`，preset 不改：
  - prompt `<formula>`，temperature 0，`max_new_tokens` 2048；
  - `stop_on_repetition` 開啟，`expansion_factor` 0.18；
  - 一篇論文的樣本公式一批。
- **引擎與裝置**：AUTO_INLINE 在 Apple Silicon 上只有模型有 MLX 版本時才用 MLX，CodeFormulaV2 沒有，所以選 Transformers。Transformers 引擎只支援 CPU、CUDA、XPU，所以本機跑在 CPU，4 threads。
  - docling 的 model catalog 對 Code & Formula stage 只列 Transformers 與 MLX 兩種引擎，CodeFormulaV2 的 MLX 是 ❌。
- **版本**：docling-slim 2.148.0。profile 釘的 2.132.0 早於 PR #4548（修正重複輸出的迴圈）。
  - 實際上 46 個公式都正常結束，重複停止沒有觸發任何一個，所以在這批公式上兩個版本的輸出相同。

## 4. 判定

- **規則**：`judging-rules.md`，沿用 t4-accuracy README 與 #153 的修正，再為邊距加兩條：方程式編號可有可無；公式以外的內容判 FAIL。
- **判定者**：Claude Opus 5.5 子代理，effort high，共 3 批：試評 6 張，之後兩批各 20 張。
  - 每張 sheet 是 `formula@1` 的裁圖，加上該公式所有不同的答案，以 A–D 標示、順序打亂。判定者看不到模型名、輸入種類，也看不到舊判定。
  - 46 張 sheet 共 165 個不同的答案。CodeFormulaV2 在兩種裁圖下有 16 個公式答案相同。
- **試評後的澄清**：LaTeX 能否編譯不判；字詞上的標點（`where:` 的冒號）視同結尾標點。兩條都和試評的判法一致，沒有判定因此改變。
- **和 t4 的一致性**：Luna 和 Opus 的答案這次在同一輪重判。46 個公式中，45 個的判定和 t4 `judgments.json` 完全相同；唯一不同的是 §5.6 的 UNKNOWN。
- **判定者留下的判斷題**（列入抽查參考）：
  - 兩個「公式」其實是程式識別字（`django__django`），雙底線寫成下標或 `\dots` 判 FAIL；
  - `\mathtt` 視同 `\texttt`；
  - `\big` 等括號大小不計；
  - 印刷上 θ 在基線（`πθ`）卻寫成 `\pi_\theta` 判 FAIL（Luna、Opus 都是，論文本身可能是筆誤）。

## 5. 結果

### 5.1 正確數

見摘要的表；數字在 `evidence.json`。沒有空答案（EMPTY 0）。

### 5.2 配對比較（只有一方對的公式數）

| 比較 | 前者對、後者錯 | 前者錯、後者對 | 精確符號檢定 p |
|---|---:|---:|---:|
| `cf-same` vs Luna | 8 | 7 | 1.0 |
| `cf-official` vs Luna | 8 | 12 | 0.50 |
| `cf-official` vs `cf-same` | 2 | 7 | 0.18 |
| `cf-same` vs Opus | 1 | 11 | 0.006 |
| `cf-official` vs Opus | 1 | 16 | 0.0003 |

`cf-same` 和 Luna：兩者都對 26、只有 `cf-same` 對 8、只有 Luna 對 7、都錯 4。如果有一個完美的選擇器，兩者合起來的上限是 41／45；但本票沒有量測任何實際的合併方式。

### 5.3 錯誤類型

| 類型 | `cf-official` | `cf-same` | Luna | Opus |
|---|---:|---:|---:|---:|
| `symbol`（讀成別的字元） | 8 | 7 | 4 | 0 |
| `script`（上下標） | 6 | 4 | 3 | 1 |
| `missing` | 5 | 5 | 0 | 0 |
| `extra`（不在公式裡的內容） | 4 | 0 | 1 | 0 |
| `structure` | 2 | 0 | 1 | 0 |
| `letter-style` | 1 | 1 | 4 | 0 |
| `letter-case` | 0 | 1 | 3 | 0 |

一個 FAIL 可以有多個類型。

`cf-same` 的 11 個錯：
- `\text` 裡的字詞拼錯 3 個（score → sore、compression → compresion、propose → pospose）；
- 打字機字體的 `SE` 讀成 `\mathbb{S}` 3 個；
- 程式識別字 2 個；
- 其他 3 個：`\setminus` 漏掉、黑板體的 1 寫成 `\mathbb{I}`、下標 j 寫成 i。

這些錯來自模型本身。CodeFormulaV2 的 prompt 固定是 `<formula>`，無法像 #152 那樣用 prompt 修正。

### 5.4 官方裁圖 vs `formula@1` 的裁圖

官方的 18% 邊距在這批公式上是負面的（29 vs 34）：
- 4 個公式帶進了相鄰文字或編造的整行（`extra`）；
- 方程式編號被抄成 `( 2 )`，造成 §5.5 的誤標。

docling 文件也提到，寬邊距可能帶進方程式編號或相鄰文字，所以開放 `expansion_factor` 讓使用者調整。若要用 CodeFormulaV2，應該改送 `formula@1` 的裁圖。docling 的 stage 會自己裁圖（`images_scale` 1.67 是類別常數），所以要像 `run_cf.py` 那樣直接呼叫模型。

### 5.5 `FORMULA_NATIVE_MISMATCH`（`formula@1` 的 `mismatch()`）

| | 標記 | 其中真錯 | 誤標正確 | 錯的總數 | 沒標到的錯 |
|---|---:|---:|---:|---:|---:|
| `cf-official` | 15 | 11 | 3 | 16 | 5 |
| `cf-same` | 6 | 6 | 0 | 11 | 5 |
| Luna | 6 | 5 | 1 | 12 | 7 |
| Opus | 2 | 0 | 1 | 1 | 1 |

另有 1 個標記落在 §5.6 的 UNKNOWN 上（`cf-official` 和 Opus 都是寫成一般 C 的答案）。

- #152 的字母樣式與數字檢查不依賴模型，CodeFormulaV2 的 LaTeX 也能比。在 `cf-same` 上標 6 個、6 個都是真錯，抓到 11 個錯中的 6 個。
- `cf-official` 的 3 個誤標都是結尾的 `( 2 )`。`mismatch()` 只去掉 `\tag{}`，字層這邊則會去掉結尾的方程式編號。若沿用官方裁圖，LaTeX 這邊也要去掉結尾的編號。
- 沒標到的錯以字詞拼錯和上下標為主，字層比對看不出來。

### 5.6 唯一的 UNKNOWN：p01-a5304a07488e

- 四個答案只差在開頭的 C 是不是花體。判定者放大 8 倍仍無法確定，四個答案都判 UNKNOWN。
- 字層的證據：這個 C 的字型是 `txsys`（newtx 的花體符號字型）。t4 在 #152 依這個證據裁定為花體。
- 依這個裁定，`cf-same` 和 Luna 對，`cf-official` 和 Opus 錯。待使用者裁定（§9 A1）。

## 6. 成本與風險

### 6.1 延遲

| 項目 | 數字 | 來源 |
|---|---|---|
| CodeFormulaV2，本機 CPU（M5 Pro，4 threads，BF16） | 每個公式中位數 22.3 秒、最大 31.3 秒；46 個共 1,113 秒 | 本票 `evidence.json`（批次時間除以批次大小） |
| CodeFormulaV2，GPU | **官方沒有公布** | docling 技術報告（arXiv 2408.09869、2501.17887）只量 layout、TableFormer、OCR；模型卡沒有效能數字 |
| CodeFormulaV2，NVIDIA L4（社群） | 100 個公式的 formula stage 共 98 秒（重複停止、邊距 0.18），約每個公式 1 秒 | docling issue #4539（社群使用者回報，非官方） |
| CodeFormulaV2，CPU i7-12700 FP32（社群） | 99 個公式 511 秒，約每個公式 5.2 秒 | docling PR #4548（外部貢獻者，已合併） |
| Luna（DEV，effort high，API） | 每篇論文的請求延遲中位數 3.3–21.7 秒（所有 VLM 方法合計） | t4-seam-b README |

### 6.2 PROD 量級（估計）

估計的依據：
- PROD 尖峰規格是 50 份 PDF／分鐘、持續 10 分鐘，canonical 要在 25 分鐘內完成；
- 20 篇論文共登錄 222 個公式，平均每篇 11 個。

所以一次尖峰約 5,500 個公式。

- **CPU**：每個公式 22 秒 × 5,500 ≈ 34 小時的 4-thread worker 時間。25 分鐘內做完要約 80 個這樣的 worker，不可行。
- **GPU**：以社群的 L4 數字（每個公式約 1 秒）估，約 1.5 小時的 L4 時間。25 分鐘內做完要 4 張以上，這還只是公式這一項。這是估計，不是公司 GPU 的量測。

### 6.3 部署與相依

| 項目 | 若改用 CodeFormulaV2 |
|---|---|
| 執行位置 | 模型在 worker 內推論（Transformers，CUDA）。CodeFormulaV2 是行程內的 GPU 資源，依 CODING_STANDARDS 要有自己的 task queue 與 worker。現行 VLM 是公司以 API 提供，沒有這類 GPU worker（#137）。 |
| docling | profile 的 docling-slim 2.132.0 沒有重複停止（#4548）。要升級，或在 method 裡自己停止並刪除重複的尾巴。 |
| 裁圖 | 不用 docling stage 的官方裁圖（§5.4），改送 `formula@1` 的裁圖，等於不走 docling 的 stage、直接呼叫模型。 |
| 可調整性 | prompt 固定，無法像 #152 那樣用 prompt 修正錯誤；只能換模型或加後處理。 |
| 授權 | CDLA-Permissive-2.0（模型卡）。 |

## 7. 建議與各選項要改的地方

| 選項 | 要改的地方 | 評估 |
|---|---|---|
| **A. 維持 `formula@1`（建議）** | 無。CodeFormulaV2 記為備案，觸發條件：V10 測出公司 VLM 的公式準度明顯低於 Luna（比較交 #83） | 準度相同、成本最低；PROD 準度仍取決於 V10 |
| B. 改用 CodeFormulaV2 | 新 method `formula@2`（本機推論，元件 `docling-project/CodeFormulaV2@ecedbe11`）；GPU task queue 與 worker；docling 升級或自寫重複停止；`d3-check@1` 的 `CHECKS` 加 `formula@2`，並在 CodeFormulaV2 的輸出上重驗 d3-mini 的門檻（#153 的 formula 門檻 0.445 是在含 #84 W3 CodeFormulaV2 答案的混合資料上校準的）；`FORMULA_NATIVE_MISMATCH` 可沿用；#135 前要先開實作票並讓它擋 #135 | 準度沒有提升，多一套 GPU 部署 |
| C. 兩者合用（VLM 主路徑，CodeFormulaV2 當第二意見） | B 的全部部署，加一條 LaTeX 等價比較規則（`P _ { k }` 對 `P_k` 這類格式差異要先正規化），不一致就標 `disputed` | 錯的地方互補（同時錯 4 個），但等價比較與誤標率都沒有量測；d3-mini 已經在當公式的第二意見（#153 強訊號） |

## 8. 限制

- **偏差有利於 Luna**：這 46 個公式曾用來調整 #152 的 prompt 與檢查，所以 Luna 的數字偏樂觀。CodeFormulaV2 沒有被調過，Opus 的答案也早於 #152。這一點修正了票上「對三方都一樣」的說法。
- **樣本小**：每個方法每個公式只有一個答案，46 個樣本的 Wilson 區間寬約 0.25。t4 觀察到 Luna 重錄時正確數差 1 屬於 run-to-run 變異。CodeFormulaV2 是 greedy decoding，可重現。
- **判定者和 `opus` 是同一個模型**：有自我偏好的風險，以隱藏模型名來降低。和 t4 判定 45／46 一致，這是判定穩定的證據，不是準確的證據；後者靠使用者抽查。
- 本機是 CPU 的 BF16。CUDA 上的數值可能有細微差異，未量測。

## 9. 待裁定（grilling）

- **A1**：p01-a5304a07488e 的 C 依字層字型算花體嗎？
- **A2**：抽查 10 個 `cf-official` 判定（5 FAIL、5 PASS，seed 159），頁面在 `~/archive/data-ingestion-159-untracked/spot-check.html`。
- **C1**：選項 A、B 或 C。
- **C2**：若選 A，備案的觸發條件與交接。

## 10. 重現

```sh
OUT=~/archive/data-ingestion-159-untracked
env AWS_ACCESS_KEY_ID=kpdev AWS_SECRET_ACCESS_KEY=kpdev-secret \
    .venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/prepare.py $OUT
uv venv --python 3.12 CF_ENV && VIRTUAL_ENV=CF_ENV uv pip install -r docs/research/codeformula-vs-vlm-2026-11-07/requirements.lock.txt
env HF_HUB_OFFLINE=1 scripts/heavy-lock codeformula-159 -- \
    CF_ENV/bin/python docs/research/codeformula-vs-vlm-2026-11-07/run_cf.py $OUT ~/models/issue159
.venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/score.py packet $OUT
# judges write $OUT/judging/verdicts-NN.json (judging-rules.md)
.venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/score.py merge $OUT
.venv/bin/python docs/research/codeformula-vs-vlm-2026-11-07/score.py score $OUT
```

檔案：`outputs.json`（CodeFormulaV2 的輸出與時間）、`judgments.json`（四方逐項判定）、`evidence.json`（彙總）、`freeze.json`（凍結時的 hash）。
