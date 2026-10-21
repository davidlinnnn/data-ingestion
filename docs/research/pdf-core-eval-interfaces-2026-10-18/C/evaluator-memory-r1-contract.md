# Memory-R1 Figure 6／7／8：來源限定的 evaluator 契約

2026-10-18。**只建立來源真值，不評 candidate，不提供 producer 路由或 prompt。** JSON 契約 (`evaluator-memory-r1-contract.json`)的 source SHA、圖例、有限數值分母及比較條件已固定；producer 不得讀取此檔或其中位置／數字。

來源為 SRC06 原始 PDF 的實體第 8 頁；先看既有 source-census 頁圖，再以既有 pinned pypdfium2 在本機 4x render 核對。PDF SHA256 `c206af4e792e9550f2aaec8a6c4d9b141d1ddcb587e781d7866870c8f3e4dd4f`；4x render SHA256 `b17540b21cfa8efcd1f7d407ffcb0038e81cce076eab81c9aaecab2f5204c883`。inspection crop／原圖 hash 與座標都只作 evaluator 可重現證據，不是 production bbox。沒有 VLM、API、模型、benchmark GT 或 holdout。

| 圖 | 固定評估內容 | 數值分母 |
|---|---|---:|
| F6 | 兩個 panel × F1／B1／J × Before RL／PPO／GRPO 的彩色上邊界座標 | 18 個估值 |
| F7 | 兩個 panel × PPO／GRPO × x=25／100／175 的曲線觀測 | 12 個估值區間 |
| F8 | F11 圖意、OCR、方法／percentile／accuracy–latency 關係；維持既定 scatter 範圍 | 0 個強制數值點 |

F6 的藍／紅／綠是堆疊顯示。觀測對象是每個顏色**上邊界的累積 y 座標**，不是紅／綠 band thickness，也不是把三個上邊界相加。所有 data values 都沒有印在 bars 上；18 個值均標 estimated，不能改標 printed。Score in %、F1／B1／J、兩個 Memory Manager panel、圖例及原 caption 必須保留。Y 軸截斷於約 15%，不能宣稱零起點；顯示範圍約 15–80，沿用 2% plot range，容許 1.3 percentage points。各 panel／metric 的 green top > red top > blue top，以及對應 GPT-4o-mini panel > Llama panel 的關係另外檢查，不能靠數值誤差容忍抵銷歸屬錯誤。

F6 的圖形足以凍結這些可觀測座標，但沒有提供原始實驗數字或疊圖生成公式。**不拿旁邊 Table 2 的值當 chart 的 printed GT**，也不要求重建不可見的 additive model。

F7 是 noisy continuous curves，並未宣稱拿到訓練 raw data。固定 x=25／100／175 是 evaluator 的有限 geometry landmarks；可接受有清楚 series 的估計點，或足夠細的曲線／polyline供 evaluator 插值。每個 landmark 以 source render 單一 x pixel 上可分辨的 red／blue ink 垂直區間表示，避免把陡峭線段／stroke width 變成假精確的單一 raw sample。比較是到來源 ink interval 的距離除以完整 plot height，最多 0.02（本 render 為 265 px，故額外 5.3 px，約 0.00809 reward）。reference ink interval 不是統計 confidence interval；沒有默默提高 geometry tolerance。

F7 的 literal y label 是 Training Reward，刻度 0.0／0.1／0.2／0.3；**不是百分比**。X 只印 0／50／100／150／200，沒有文字軸名；training progress／steps 可作有根據的解讀，不能說原圖印了 epochs 或 Training Steps。PPO 紅、GRPO 藍；panel 是 Llama-3.1-8B-Instruct 與 Qwen-2.5-7B-Instruct。x=25 的 GRPO > PPO、初期收斂較快、最後 reward 相近，以及 Answer Agent 使用 exact-match reward 的條件獨立保留。不能寫成 GRPO 每一步都較高、曲線單調，或最後完全相等。

F8 在 4x 原圖已能確認：Base 藍、Base + Reranker 橙、Memory-R1 (GRPO) 綠；circle=p50、triangle=p95。橫軸 Latency (s) 是 log scale，縱軸 Accuracy (%)；三個 panel 為 F1／B1／J。保留 Memory-R1 較高 accuracy、較低 p50／p95 latency，reranker 的額外 latency，以及同方法 p95 在 p50 右側、accuracy 相同的來源關係。p50／p95 不是 error bar 或不同模型。**不新增所有 scatter 點的數字抽取門檻。**

原 caption 與影像上的原文保留為 source evidence；OCR 輸出、生成描述、數值估計及 uncertainty 另經 image key／provenance 交付，不覆寫 caption。Source 可辨識但 candidate input／輸出 unreadable 的項目仍列 delivery failure；必要時保留 null／unreadable 與原因，不得猜值補通過。目前來源沒有預先排除的 unreadable landmark。

尚未做同 revision native crop 的結果驗收；native coverage、實際 request／budget、OCR／description／chart 輸出接合都由其他 gate 處理。F6 的 raw values／stack-generation 及 F7 的原始 samples 從圖中不可確證，已明確排除為隱含要求。
