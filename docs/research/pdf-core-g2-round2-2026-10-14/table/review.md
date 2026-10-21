# G2 第二輪：TableFormerV2 CPU stage 比較

2026-10-14，Asia/Taipei。**既有 TableFormerV2 能在本機 CPU 完成兩張表的推論，但不能修好 G1-T02 的六個 panel。** G1-T01 普通表的六個數值及三個關鍵比較仍正確。本輪不採用 V2 作為複雜表修復配置，也不宣告完整表格能力或 G2 通過。

## 範圍與固定輸入

這是兩次獨立 table stage 執行，不重新跑 layout，也不生成整份文件。直接重用第一輪完整 `conversion-result.json` 保存的 TABLE cluster、原生文字 cells、原 physical page 8 與原 PDF/hash。G1-T02 是 SkillOpt **p8 Table 2**，不是舊實驗的 p7 Table 1；舊 p7 結果只作歷史證據，沒有冒充本次比較。[第一輪](../../pdf-core-g2-local-cpu-2026-10-14.md)／[舊 V2 結果](../../paper-pdf-table-v2-results-2026-10-11.md)

| Case | 來源／完整 TABLE cluster | Source oracle | 本輪輸入核對 |
|---|---|---|---|
| G1-T02 | SkillOpt `04-2605.23904v2.pdf`，physical p8，cluster 6，127 個原 cells | 六 panel、28 個設定列、84 個數值、8 個關鍵比較 | 84 個數值的來源 bbox 全部在原 cluster 內；實際裁圖目視確認六 panel 完整，沒有另外切 panel |
| G1-T01 | Memory-R1 `11-2508.19828v5.pdf`，physical p8，cluster 9，15 個原 cells | 兩種 PPO reward method、六個數值、3 個關鍵比較 | 六個數值的來源 bbox 全部在原 cluster 內；實際裁圖目視確認 |

原 PDF SHA-256 分別為 `87f7f0f323b1671e9202b3ebb1596e909e507c71ecd1b360b0075a5ee1727fe3`、`c206af4e792e9550f2aaec8a6c4d9b141d1ddcb587e781d7866870c8f3e4dd4f`。[G1 原始 oracle](../../../fixtures/pdf-core-g1-2026-10-14/cases.json)／[T02 輸入](skillopt-p8/source.json)／[T01 輸入](memory-r1-p8/source.json)

## 模型、runtime 與資源

使用既有 temporary candidate 與既有 TableFormerV2 cache，沒有下載、安裝或改套件。模型 snapshot `51559fad3946873e26a6f9b8e912f948e8745bef`；權重 209,735,468 bytes，SHA-256 `8a640f1e6d4c69769e8bb968bfe29596559817bf165441e1dd5c69186663aa25`，與 retained Hugging Face download metadata 的 commit／LFS hash 相符。[method](method.json)／[retained download](../../paper-pdf-table-v2-2026-10-11/download.json)

- Runtime：Docling／slim 2.124.0、core 2.96.0、IBM models 4.0.3、parse 7.16.0、torch 2.14.0。
- 第一輪為 Docling 2.102.0、IBM models 3.15.0、parse 6.2.0。**不只模型改變，因此不宣稱單一模型造成品質或速度差異**；原 cluster cells 固定，但空 cell 的 backend fallback 由本輪 parse 執行。
- 官方 `TableStructureModelV2.predict_tables()`，matching=true，CPU F32；intra-op／interop、OMP／MKL／OpenBLAS 都為 1，單 worker 依序、batch=1。
- 144dpi table crop，官方 preprocessing resize 至 448×448；T02 原 crop 896×250，T01 為 424×88。這個候選會改變原表格的長寬比，未另外比較其他 resize。
- 沿用官方 512 個新增結構 tokens 上限，沒有修改 generation、matching 或 decoder；逐次保存 raw ids、EOS、bbox、OTSL 及 table cells。
- 每 child 180 秒／6 GiB sampled child-tree RSS stop，250ms 抽樣。首次 supervisor 使用的 bundled Python 缺 `psutil`，在建立 child 前失敗；改用既有 prototype venv，沒有重跑模型或安裝依賴。[startup failure](startup-failure.json)／[runner](run.py)

## 執行結果

| Case | Child wall | Sampled tree peak RSS | 純 generate | 新 tokens／EOS | 結果格網 |
|---|---:|---:|---:|---|---|
| G1-T02 | 4.187s | 1.201 GiB | 0.817s | 157／有，尾端 nl | 13×11、134 cells，93 非空 |
| G1-T01 | 3.147s | 0.867 GiB | 0.173s | 16／有，尾端 nl | 3×4、12 cells，全部非空 |

兩次 exit 0、reaped、無 timeout／memory stop；兩次 EOS 都在 512 上限之前出現。T02 不能歸因於輸出 token 上限截斷。Child wall 包含 import／setup／載入，不是正式 service latency 或整頁 pipeline benchmark。[observations](observations.json)／[T02 generation](skillopt-p8/generation.json)／[T01 generation](memory-r1-p8/generation.json)

## 品質核對

**T01：本次 stage 內容與條件綁定通過。** Method、F1／B1／J 與方向標記正確；J-based row 是 `33.69 / 23.36 / 63.58`，EM-based row 是 `41.05 / 32.91 / 57.54`，兩個 method 沒有合列。六個數值及三個 G1 critical comparison 全部逐項核對。這是 stage 結果，沒有重新生成 caption attachment 或 Markdown，不等同整頁或 Canonical Acceptance。[逐項 review](review.json)／[T01 table](memory-r1-p8/table.json)

**T02：producer stage 本身仍有必需結構與數值歸屬錯誤。** 完整輸出已讀取，並與固定 source crop 核對；下表使用 0-based output row／column。

| 問題 | 來源預期 | V2 實際輸出 |
|---|---|---|
| 合併 panel 與 metric header | 六個獨立 panel，各自 Setting／SearchQA／Spreadsheet／LiveMath | row0/col0 橫跨 8 欄，合併 `(a)` 與 `(b)`；row1/col1 是 `SearchQA Spreadsheet LiveMath` |
| panel a 相鄰值混合 | 100% train：SearchQA 84.1、LiveMath 70.5 | row6/col1 是 `86.1 84.1`；row6/col3 是 `67.0 70.5` |
| panel b 缺設定與 metric 綁定 | mini-batch 8／16 SearchQA 87.1／87.0 | rows2–6/cols4–5 為空；設定列與 SearchQA 無法恢復 |
| panel c 合列 | full epoch SearchQA 87.2 | row6/col7 是 `56 full epoch`、col8 是 `86.5 87.2` |
| panel d 合列與遺失 | lr=4、lr=8 是獨立設定，LiveMath 56.5／66.9 | row10 label `lr=2 lr=4`、row11 `lr=4 lr=8`；這兩列 LiveMath 為空 |
| panel e 缺 metric | constant：87.3／80.7／62.1，另有 cosine／linear | 只有 row9/col4 `constant`；對應 panel metric columns 大量空白 |
| panel f 合列 | slow-update 10 的 LiveMath 65.3 | 65.3 附在 row10 的 `10 20` 混合設定 |

八個 critical comparison 都有保存判定：七個因缺值／合列無法成立，另一個 40%／80% SearchQA 的 86.1 tie 雖可看見，metric header 合併仍不能接受。**沒有完成 84 個數值的逐點錯誤分類，故不提供錯誤率，也不拿數字出現率當通過率。** 全表 84 點是 source denominator；上述必要關係反例已足以拒絕這個配置。[T02 table](skillopt-p8/table.json)／[critical review](review.json)／[本輪原 crop](skillopt-p8/table-crop-144dpi.png)

## 保留與下一步

T01 作普通表 control，保留 V2 可在 CPU 運行的證據；T02 不把這套 V2 配置採用為修復方案。下一個值得比較的方向是能處理多個 panel 的結構辨識／分區方法或 table VLM；若採分區，仍須保留整個邏輯 Table 2 的 panel、caption、條件及 84 點分母，不能只挑個別 panel 宣稱通過。本輪沒有再做主觀調參或提高 token 上限，因已出現正常 EOS 且必要關係仍錯。

已核對 source／第一輪 provider／registry 全部未變、runner hash 與 method 一致、snapshot 權重 hash 一致；保存 original-check 與 assertion-based review。未碰 src、第一輪、G1、GitHub 或 production config。[originals check](originals-check.json)／[validation](review.json)

未測 GPU、VLM/API、其他三張 G1 表、per-panel segmentation、完整 PDF 組裝／恢復及高頻負載；不能由兩次 stage wall time 推估 production SLO。
