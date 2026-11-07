# #159 事前登錄

**狀態：凍結（2026-11-07）。** 樣本、受測方法、執行設定、判定規則與評分程式都已寫好，SHA-256 記在 `freeze.json`。凍結時樣本內的 CodeFormulaV2 輸出是 0 筆。smoke 只用了樣本外的 2 個公式（p01-ba968bb91c87、p01-292027aca235），結果不計入。`run_cf.py` 在 `items.json`、自身或權重的 hash 不符時拒絕啟動。

凍結時沒有使用者裁定。下面的方法選擇都附理由，報告最後用 grilling 逐題確認；若使用者改了方法，重跑約 30 分鐘 CPU 加一輪盲評。

## 1. 問題

在 t4-accuracy 的同一批 46 個獨立公式上，CodeFormulaV2 的準度和 Luna、Opus 相比如何？若差距不大，換方法的成本與風險是什麼？

## 2. 樣本

- t4-accuracy 的 46 個 display formula：每篇論文最多 3 個，seed 133，共 17 篇（`docs/validation/80/t4-accuracy/run.py` `formula_targets`）。
- 每個公式的輸入：S3 stand-in 裡 t4-seam-b 真實執行留下的頁面圖（scale 2.0，即 144 dpi）與來源 PDF。
- `prepare.py` 產生：
  - `formula@1` 的裁圖（`methods.formula._crop`），
  - `formula@1` 比對用的字層文字（`_native_text`）。
- 裁圖、PDF 與字層文字放在 git 外。`inputs.json` 記錄每個公式的頁、框與三個 hash。
- **重現檢查（凍結前已跑）**：對 Luna 的 46 個答案重算 `mismatch()`，得到 6 個 `disputed`，和真實執行登錄的狀態完全相同。

## 3. 受測的四組答案

| 代號 | 方法 | 輸入 | 來源 |
|---|---|---|---|
| `cf-official` | CodeFormulaV2，docling 官方 formula stage | 官方裁圖：以 PyPdfium backend 從 PDF 重繪，scale 1.67（120 dpi），四邊各外擴 18% | 本票執行（主結果） |
| `cf-same` | 同上 | `formula@1` 的裁圖（頁面圖 144 dpi，框不外擴） | 本票執行（同輸入對照） |
| `luna` | `formula@1`，`gpt-6-luna`，reasoning effort high，#152 的 prompt | `formula@1` 的裁圖 | t4-accuracy `targets.json`（#152 後重錄） |
| `opus` | 同一個 method request 送 `claude-opus-5-5` | 同上 | t4-accuracy `responses/opus/`（round 2，effort max，#152 之前的 prompt） |

兩種裁圖都跑，原因是票的「輸入」寫「和 `formula@1` 相同的頁面圖裁切」，「執行」寫「依 docling 官方設定」。官方 stage 自己裁圖（120 dpi、18% 邊距），和 `formula@1` 的裁圖不同。若改用 CodeFormulaV2，上線時用的會是官方裁圖，所以主結果是 `cf-official`；`cf-same` 用來看準度差異是否來自輸入。

## 4. CodeFormulaV2 的官方用法與本次設定

| 項目 | 官方 | 本次 | 出處 |
|---|---|---|---|
| 模型 | `docling-project/CodeFormulaV2`，Idefics3，約 0.3B 參數，BF16 | revision `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`（2026-11-07 的 main，也是 #84 W3 用的版本）；13 個檔案全部和 Hub 該 revision 的 hash 相符（`weights-codeformulav2.json`） | HF 模型卡與 API |
| 輸入解析度 | 120 dpi | stage 的 `images_scale = 1.67` | 模型卡；docling 2.148.0 `code_formula_vlm_model.py` |
| 裁圖邊距 | 四邊各 18%（`expansion_factor` 預設 0.18） | 預設 | docling 文件 `docs/usage/enrichments.md`（v2.148.0） |
| 重複輸出 | 預設提早停止並刪除重複的尾巴（`stop_on_repetition=True`） | 預設 | 同上；docling PR #4548 |
| 推論 | preset `codeformulav2`：Transformers 引擎、`AutoModelForImageTextToText`、`bfloat16`、prompt `<formula>`、temperature 0、`max_new_tokens` 2048；一份文件的公式每 5 個一批 | preset 不改；每篇論文的樣本公式一批（最多 3 個） | docling 2.148.0 `stage_model_specs.py` |
| 引擎與裝置 | AUTO_INLINE：Apple Silicon 只有在模型有 MLX 版本時才用 MLX；CodeFormulaV2 沒有，所以用 Transformers。Transformers 引擎只支援 CPU、CUDA、XPU | 本機 CPU（smoke 已確認：`TransformersVlmEngine`、`cpu`） | `auto_inline_engine.py`、`transformers_engine.py`；model catalog 的 Code & Formula 表：Transformers ✅、MLX ❌ |
| 執行緒 | `AcceleratorOptions.num_threads` 預設 4；在 docling pipeline 裡，CPU 上的 layout stage 會呼叫 `torch.set_num_threads(4)` | 4 | `accelerator_options.py`、`object_detection/transformers_engine.py` |

**為什麼用 docling-slim 2.148.0，不用 profile 釘的 2.132.0**：

- 2.132.0 在 2026-10-01 發布。
- PR #4548 在 2026-10-04 合併，修正了 CodeFormulaV2 重複輸出到 `max_new_tokens` 的迴圈。
- 在 #4539 回報的那篇論文上，約 100 個公式裡有 13–14 個會進入這種迴圈。
- 改用 CodeFormulaV2 就必須帶這個修正，所以量測修正後的版本。
- 依該 PR 的說明，沒進入迴圈的公式輸出逐位元相同。`outputs.json` 同時記下引擎的原始輸出與 docling 寫入的文字，報告會列出哪些公式在 2.132.0 下會進入迴圈。

**環境**：

- 獨立 venv，鎖檔 `requirements.lock.txt`（docling-slim 2.148.0、transformers 5.22.2、torch 2.15.0）。
- `HF_HUB_OFFLINE=1`，權重從本機路徑載入。
- 以 `scripts/heavy-lock` 執行，不和其他模型同時跑。

## 5. 判定

- 規則凍結在 `judging-rules.md`：
  - 公式規則沿用 t4-accuracy README，加上 #153 的兩條修正（粗體是字母樣式、長串空白是 spacing）。
  - 為邊距新增兩條：裁圖印出的方程式編號可有可無；公式以外的內容（相鄰文字行等）判 FAIL。
- 判定者是 Claude Opus 5.5 子代理，effort high。
- 每個公式一張 sheet：`formula@1` 的裁圖，加上該公式所有不同的非空答案，以 A、B、C… 標示，順序用 seed 159 打亂。
  - 判定者看不到模型名、輸入種類、幾個方法給了相同答案，也看不到舊判定。
  - 空答案記為 `EMPTY`，不送判，算錯。
- **Luna 和 Opus 在同一輪重判**，讓四組答案由同一判定者、同一規則判。t4 的判定是兩個答案 A/B 並排，這次最多四個並排。
  - 和 t4 `judgments.json` 不同的判定，全部交使用者裁定。
- **試評**：先送 batch-00（6 張 sheet）。只有在試評之後、其餘批次之前可以修正規則，修正會記在 `judging-rules.md`，受影響的試評判定重判。
- **打包自我檢查**：寫出批次前，`score.py packet` 會確認：
  - 每個公式恰好出現在一張 sheet；
  - 每張裁圖的 hash 等於 `items.json` 的記錄；
  - 每個方法的答案恰好落在一個字母下。
- **抽查**：使用者看 10 個 `cf-official` 判定（5 FAIL、5 PASS，seed 159），以及所有和 t4 不同的 Luna／Opus 判定。

## 6. 指標（`score.py score`）

- 四組的正確數，附 Wilson 95% 區間；FAIL、UNKNOWN、EMPTY 各自計數。
- 配對比較：`cf-official` 和 `cf-same` 各自對 Luna、Opus，以及兩者互比。列出只有一方對的公式數，附精確雙尾符號檢定。
- 錯誤類型分布，類型的定義見 `judging-rules.md`。
- `FORMULA_NATIVE_MISMATCH`：拿 `formula@1` 的 `mismatch()` 比對每個答案和字層，再和判定交叉，看標到幾個真錯、標錯幾個對的、漏掉哪些錯。
- 延遲：本機 CPU 每項的延遲（批次時間除以批次大小）。公司 GPU 只引用官方數字；官方沒有公布 CodeFormulaV2 的 GPU 數字（§8）。

## 7. 決策

沒有事前設定換方法的門檻。維持 `formula@1`、改用 CodeFormulaV2 或兩者合用，由使用者在 grilling 裁定，依據是配對結果、錯誤類型與成本。

## 8. 已知限制

- **偏差不是對三方都一樣**：
  - 票上寫「46 個公式曾用來調整 #152 的規則，數字會偏樂觀，對三方都一樣」。
  - 實際上 #152 的 prompt 與字母樣式檢查是依 Luna 在這 46 個公式上的錯誤調的。CodeFormulaV2 沒有被調過，Opus 的答案也早於 #152 的 prompt。
  - 所以偏樂觀的主要是 Luna 的數字，比較會偏向 Luna。
- 每個方法每個公式只有一個答案。t4 觀察到 Luna 重錄時正確數差 1 屬於 run-to-run 變異。CodeFormulaV2 是 greedy decoding，在同一台機器上可重現。
- 判定者和 `opus` 是同一個模型，有自我偏好的風險；靠隱藏模型名來降低。
- **官方 GPU 數字**：vendor（IBM Research、docling-project）沒有公布 CodeFormulaV2 在 GPU 上的延遲。唯一的 GPU 數字來自社群回報：issue #4539，NVIDIA L4，100 個公式加重複停止後 98 秒。報告引用時會標明來源。
