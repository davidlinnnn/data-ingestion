# PDF core G2：dots.ocr 原生格式與本機可行性驗證

日期：2026-10-16（Asia/Taipei）。承接使用者「OK, 進行下一階段的模型驗證」。本輪只選 dots.ocr，原三組配置的 no-go 與原始評分保留；未增加逐案 prompt／答案修補，也未開啟六份 custody holdout。

**本機階段已完成；dots.ocr 真實整頁 CPU 推論在 180 秒界線停止，尚無模型準確率結論。** 模型已成功載入，取樣峰值 process-tree RSS 為 9.07 GiB，未觸及 12 GiB 上限；沒有完成輸出，不能當成辨識失敗或計算準確率。官方原生 parser 與完整 mock pipeline 另已實測：正確的 code block／LaTeX 可保留，但合法行內 code 包含 HTML tag 時會被改寫。該交付缺口與 CPU 時間結果各自保留，本輪不採用完整 challenger。

## 本輪邊界與實際版本

- 固定 checkpoint：`dots-studio/dots.ocr@c0111ce6bc07803dbc267932ffef0ae3a51dc951`。完整模型 3,039,179,264 parameters；兩份 BF16 safetensors 共 6,078,431,736 bytes。模型卡的 1.7B 指語言模型部分。
- 隔離 runtime：`/private/tmp/pdf-core-g2-dots-20261016/venv`；Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3／Transformers 4.51.3／Torch 2.14.0。`pip check` 通過；不改 baseline 2.102 環境。
- 原生 preset `dots_ocr`／DOTS_JSON；公開模型原始碼、prompt、JSON parser 均未 patch。CPU 明確 BF16、4 threads、batch 1、compile／quantization 關閉，保留官方 vision 無 flash-attn 時的 eager fallback。
- 先登記一個新模型週期，新增獨立 validation；完整候選預檢不合格後，另明確登記一次 CPU feasibility probe，僅回答模型能否在本機原設定執行，不當作第二組品質配置或完整 challenger。

[階段登記](pdf-core-g2-dots-2026-10-16/phase-registration.json)／[CPU probe 登記](pdf-core-g2-dots-2026-10-16/cpu-probe-registration.json)／[實際 runtime lock](pdf-core-g2-dots-2026-10-16/requirements-runtime-lock.txt)／[官方來源研究](pdf-core-g2-dots-2026-10-16/primary-sources.md)

## 已實際完成的原生接點驗證

1. **官方 parser component**：輸入固定 synthetic dots JSON，核對公式的 `<s`／上下標／編號、code 字面內容／縮排、rowspan 表格、picture crop、caption、頁碼與像素座標換算。這些是正確輸入能否交付的控制案例，沒有把它們當模型準度。
2. **真正 `DocumentConverter → VlmPipeline → API engine → DOTS_JSON parser`**：僅 mock HTTP transport，兩頁資料經原生處理；保留實際影像尺寸、官方 prompt、token cap、document 與 Markdown。兩次早期 mock setup 失敗另存，不算模型失敗；沒有真實 API 請求。
3. **獨立 11-case parser／CommonMark 核對**：預設 Markdown export 將 inline LaTeX 底線及 code 中的 `<` 額外 escape。官方 `escape_underscores=False, escape_html=False` 可保留已是合法 Markdown 的輸出，但不能保證來源 literal 在模型未正確 escape 時仍保持；不能全域套用至其他 producer。
4. **確定的原生內容損失**：合法 Markdown `Use \`<b>bold</b>\` literally.` 在 parser 被當 HTML，code 字面值變成 `**bold**`。完整 mock pipeline 也重現，兩種 export 設定都不能修好。沒有加入猜字串補丁。
5. **截斷負例**：官方 parser 可容忍缺少最後 `]` 的 JSON 並交付已解析項目。實驗完成性判準必須另核對原始 JSON、stop reason、非空與缺件，不能只看 native `success`。

[原生 component 結果](pdf-core-g2-dots-2026-10-16/preflight/results.json)／[完整 mock pipeline 結果](pdf-core-g2-dots-2026-10-16/pipeline-preflight/results.json)／[獨立核對](pdf-core-g2-dots-2026-10-16/preflight-review.md)

## 相容性、座標與 CPU 前置證據

Docling 的固定 preset 明列 Transformers 5.x 會產生不正確整頁 bbox，因此本輪使用 4.51.3。新舊 repo 名稱不能用來繞過版本限制。官方 v2.135 首次加入 dots inline formatting；對 v2.135 到目前 v2.139 的 released source 核對仍能看見上述 HTML-in-code 分支問題，沒有為此盲目升版。新版本這一項是 source 核對，未冒稱已安裝執行。

實際固定 processor（未載入模型權重）處理 controls 頁面 1190×1684 PNG，得到 grid `[1,120,84]`／1176×1680 pixels，與 Docling 原生推定相同。小圖與大於2.5MP的輸入則存在 min/max pixels 契約差異；這次正常頁面相符不能外推所有尺寸或模型預測 bbox 正確。

BF16 CPU Conv2d、eager attention、language SDPA 的小張量實測通過。該正常頁面含 10,080 個未 merge patches；單一 BF16 attention scores 張量約2.44GB，FP32 softmax 暫存約4.88GB，還有約6.08GB權重與其他 runtime／activation。這些是 source shape 估算，**不是完整模型 RSS 實測，也不是 GPU sizing 結論**。

[實際 processor](pdf-core-g2-dots-2026-10-16/processor-preflight.json)／[CPU kernel 實測](pdf-core-g2-dots-2026-10-16/cpu-kernels.json)／[資源 guard 自檢](pdf-core-g2-dots-2026-10-16/cpu-probe-selfcheck.json)

## 真實 checkpoint 的 CPU 執行

兩個 safetensors 已完整下載並符合官方 LFS SHA-256，總大小 6,078,431,736 bytes；下載及核對合計 1026.17 秒，未超過事先登記的 1200 秒。本輪沒有以其他 VLM 代替 dots.ocr。

第一次 native 啟動在載入前失敗：Docling 的 artifacts 目錄 `rednote-hilab--dots.ocr` 讓 Transformers 4.51.3 dynamic-module 的相對匯入把 `.` 解讀為 package 分隔。失敗原樣保留於 `cpu-probe-attempt01`，沒有進入模型推論。修正只把相同的已核對檔案 hardlink 到固定 revision 的 HF snapshot 快取，並將官方 `artifacts_path` 設為 `None`；原生下載 resolver 在 offline 模式取得該 snapshot。模型 source／權重／prompt／圖片設定未改，也未增加輸出修補。

修正前後的 runner SHA、原因與成功的 native snapshot／class import 自檢另存於 setup repair。初版 `execution-inputs.json` 保留不改，對應其 runner 副本 `cpu-probe-attempt01/run.py`；不是將一次模型結果重試後隱藏。真正的完整頁面推論仍僅允許一次、180 秒及 sampled process-tree RSS 12 GiB 上限。

| 實際觀察 | 結果與界線 |
|---|---|
| 本機與配置 | Apple M5 Pro／48 GiB RAM／18 physical cores，macOS 26.4 arm64；本輪僅使用4個CPU threads。不是全機所有核心、MPS或其他最佳化配置的比較，當時其他工作負載也未控制 |
| 載入 | 成功；3,039,179,264 parameters，全部 CPU／BF16。原生 vision 在無 flash-attn 時退到 eager；config 仍保留原序列化字串 `flash_attention_2`，不能據此誤稱 CPU 使用了 FlashAttention |
| 權重載入函式耗時 | 0.369 秒；有快取／memory mapping，不代表權重全部 resident、冷啟動完成或整頁延遲 |
| 實際輸入 | 既有已曝光 controls PDF physical p1，Docling 渲染 1191×1684，scale 2；未縮小輸入以迎合 CPU |
| 最後階段 | `model_inference`；`predict_batch` 未返回，沒有 raw response 或 document。未插入逐 token observer，因此不知道已生成多少 token，不把沒有回傳說成零 token |
| 整體探測 | 180.058 秒後依既定 timeout 終止並回收自有程序；包含初始化／頁面準備時間，不是量到完整 inference latency |
| 記憶體 | 載入前 available 約14.48 GiB；2792筆樣本中 process-tree RSS 峰值9,738,256,384 bytes（9.07 GiB），未觸及12 GiB停止線。這是取樣RSS，不是完整memory footprint或GPU VRAM sizing |
| 有效推論次數 | 1次啟動、0次完成；另有1次載入路徑失敗，未進入推論。無自動重試、無新 validation／holdout 推論 |

結論是**這個固定原生 CPU 設定未通過本輪180秒可行性預算**，不是整個 dots 模型 family 不可用，也不是記憶體不足或模型品質不合格；沒有證明所有 CPU 配置都無法完成。沒有延長預算、改解析度、降低 token cap、改量化或追加猜答案的後處理。因本輪停止條件已達，後續同 checkpoint 的品質比較轉公司 GPU／vLLM。停止後的獨立[程序檢查](pdf-core-g2-dots-2026-10-16/process-cleanup.json)確認沒有本次探測程序殘留。

[權重下載核對](pdf-core-g2-dots-2026-10-16/weights.json)／[下載停止控制](pdf-core-g2-dots-2026-10-16/download-control.json)／[載入環境修正](pdf-core-g2-dots-2026-10-16/setup-repair.json)／[真實 CPU 執行紀錄](pdf-core-g2-dots-2026-10-16/cpu-probe/execution.json)

## 新增 validation，保留原 holdout

獨立 source-only curator 先排除既有原作／引用，再固定兩份公開原作的 v1 與 SHA；每份選首頁及其餘頁依文件 hash 排序第一頁，**抽頁先於讀內容、標註先於模型結果**。共四個評分頁，12個正例來源單位（11含行內公式段落、1個含圖像參數的 code block）及10個普通文字負例。60個行內公式 occurrence 是段落子項，不重複增加分母。

固定頁未含獨立 display equation；此型態、一般 text-only code、繁中、SOP、scan 等仍明記未驗。兩份有目的選取的原作不足以支持 production accuracy。原八頁／41單位繼續作曝光回歸，六份 holdout 不讀內容、不換名稱、不重新切分。

[來源與抽頁說明](pdf-core-g2-dots-2026-10-16/validation/sources.md)／[來源契約](pdf-core-g2-dots-2026-10-16/validation/source-contract.json)／[來源自檢](pdf-core-g2-dots-2026-10-16/validation/verification.json)

## 採用與後續界線

現階段沒有完整 dots challenger，沒有修改 F13／F14、正式 Processing Profile、`src` 或 Canonical Acceptance。模型品質、parser 內容損失與本機資源結果分開；不能把空輸出／超時／未執行記為準確率，也不能因 parser 邊界就宣稱模型 family 已達上限。

本機正常頁面已超過本輪時間界線，**下一個必要資源是實際部署 dots.ocr 的公司 GPU／vLLM**，沿用本輪固定 revision。需要服務的 model ID、OpenAI-compatible base URL、這台電腦是否可連線，以及金鑰的環境變數名稱（若需驗證）；若只能在公司執行，可把此已固定的 corpus／runtime 邊界帶到公司，不需要重新挑樣本。OpenAI 暫代 Qwen3 的授權不能代證 dots 品質。

GPU 階段先確認實際模型身分、原生 JSON、完成性與座標，再保留模型原始輸出、DoclingDocument 和 Markdown 三層差異，以既有八頁／41來源單位作曝光回歸、四個新 validation 頁作獨立比較。已知 parser 行內 code 缺口仍須報告；在找到可保真的官方接點之前，這只能是模型品質調查，不能升格完整 challenger，也不開六份 holdout。若仍有必要內容缺陷，回到方法／模型取捨，不追加逐題字串修正。

目前建議配置不變：保留 Standard 與已有有界證據的小模型作比較基底；dots.ocr 維持待 GPU 驗證的文件專用候選，尚未推薦取代主要流程。公司 GPU 加速、高頻 ingest 吞吐、latency 與真正 Qwen3 品質都沒有由這次 CPU 結果代證。

本輪舊143筆payload與原freeze／明確setup修正的對照、JSON與報告連結核對，見[完整性檢查](pdf-core-g2-dots-2026-10-16/verification.json)及[本輪證據manifest](pdf-core-g2-dots-2026-10-16/artifacts.json)；其通過只指證據完整性，不是模型或G2通過。

尚未完成模型品質比較、獨立 holdout、公司 GPU、高頻負載或完整 Canonical 交付；G2 尚未通過。
