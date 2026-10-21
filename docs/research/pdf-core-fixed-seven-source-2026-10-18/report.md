# B 固定七次比較與 C 來源收斂

2026-10-18，Asia/Taipei。**已完成七次真實 API 比較、固定來源評讀，以及 C 的單一官方 OCR 模式候選／55 頁 CPU 實測。兩個候選均未晉升，完整 Processing Profile 仍未合格。** 本輪沒有逐例補字、裁圖特例、prompt 重試、SDK 修改或正式 ingest 程式變更。

## B：實際交付品質

沿用凍結的 Standard 來源、七個 crop/request bytes、semantic header paths／named dimensions／section membership 協定，以及公開 Core mapper／既有 literal Markdown serializer。這是研究用的 component 接點，不是 Docling 官方內建的 JSON-table VLM pipeline，也不是整頁 `VlmPipeline`。

| 固定目標 | Core＋實際 rendered Markdown 結果 | 判定 |
|---|---|---|
| T01，Memory-R1 p8 | 6/6 數值、3/3 比較 | 通過 |
| T02，SkillOpt p8 全六 panels | 84/84 數值、8/8 比較；各 panel／setting 綁定正確 | 通過 |
| SkillOpt 同頁 collateral | 24/24 數值，Component／Setting 保留 | 通過 |
| T04，paper09 p17 | Provider 僅交付 5/30 列、50 個數值欄位，且引用未宣告的 `gpt` group；strict parser 拒絕 | 不交付，300 個必要數值仍在分母 |
| paper09 同頁 collateral | raw target 雖合法，但必要 sibling 失敗，整頁不交付 | 90 個必要數值仍在獨立交付分母 |
| T05，WikiSkill p13 | 80/80 數值、7/7 比較；兩個 aggregation sections 與 20 個原始 paired cells 均保留 | 通過 |
| Table 7，WikiSkill p22 | 3/4 math groups 等義；E017 將來源分母 `c-1` 寫為 `c_{-1}` | 重大數學意義錯誤 |

T04 的 0/300 指「未交付」，不是聲稱 300 個 raw 值全算錯。不能移除這張失敗表、接受它的 sibling，或把其他表的正確值拿來攤平錯誤。原 470 數值／23 比較、兩張 collateral 與四組 table math 的分母均保留。T03 的 264 數值／7 比較／3 missing marks 未納入這七次，也仍未解。

[完整評讀](evaluation.json)、[逐點 worksheets](worksheets/)、[原始執行紀錄](../pdf-core-eval-interfaces-2026-10-18/B/live/execution.json)皆已保存。評讀先人工核對來源意義與 scoped bindings，再以 evaluator-only 程式填入每點的實際 Core ref／anchor、raw pair、typed text、rendered text 與比較結果。Markdown 透過 markdown-it 轉 HTML 後讀取表格，不拆 raw pipe，也沒有替換舊 grader。

四份已交付文件的原始 text multiset、正文閱讀順序、非目標表格資料、來源 caption ownership 及 native table envelopes 均核對保留。`texts[]` 的儲存順序在部分文件因 reindex 改變，body 閱讀順序並未改變；standalone caption 沒有 native link 也不是來源遺失。見 [preservation checks](non-target-verification.json)。

## B：設定與增量成本

| 項目 | 實際／固定設定 |
|---|---|
| Runtime | Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3；凍結 runtime/source hashes 前後核對 |
| 比較模型 | 暫用 OpenAI `gpt-6-luna`，Chat Completions；high image detail、low reasoning、JSON object、store=false |
| 呼叫 | 7/7，concurrency=1、retry=0；全部 HTTP 200、finish=stop、usage 可用 |
| 預算 | 每次 180 秒／32,768 completion tokens；全輪 1,800 秒／229,376 completion tokens；input reserve 106,634 |
| 實際 tokens | 11,809 input＋12,432 completion，無 cached input；completion 已含 provider 回報的 reasoning tokens |
| 實際時間 | 整輪 88.110 秒；HTTP 合計 87.944 秒；單次中位數 12.792 秒，約 5.11–22.07 秒 |
| 本機成本 | runner sampled peak own RSS 153,305,088 bytes；四頁 assembly 合計約 0.124 秒 |
| Upstream | 本輪重用已鎖 cached Standard baseline；沒有把這 88 秒稱為 fresh 完整 ingest latency |

沒有依未確認價格推算美元。這是七次單次樣本，不能視為 p95、正式 SLO 或公司 Qwen3／vLLM 效能。

## C：官方模式改善了什麼

完整紀錄見 [C 來源收斂報告](../pdf-core-c-source-closure-2026-10-18/report.md)。

- 兩個官方 PDF backend 在原 caption bbox 都讀到未出現在圖面的額外文字；換 backend 尚無修復證據。
- 僅改一個官方設定：既有 RapidOCR 的 `ocr_options.mode` 從 `AUTO` 改為 `FULL_PAGE`；模型、backend、Heron layout、TableFormer 及其餘 options 不變。
- 固定 13 文件／55 頁／19 ranges 全部 fresh CPU conversion 成功，29 個 native pictures。Supervisor 正常退出，無重試。
- ReasoningBank Figure 5 原文 caption 的必要意義已恢復；剩餘 MaTTS 大小寫、WebArena-Shopping 斷行連字號差異依既有 minor 容忍接受。
- SEAL 的 `RL Outer Loop Iteration t` 已完整存在 canonical 正文，**但仍在 native picture crop 之外，沒有 picture-child 關聯**。這是圖像增強的輸入邊界問題，不是整份 canonical 把標題丟掉。
- 相同 44 頁／12 ranges 的 conversion 時間：S0 80.820 秒、FULL_PAGE 117.880 秒，單次觀測約 +45.9%。55 頁合計 146.717 秒；含初始化／監督約 151.273 秒，sampled tree RSS 約 5.36 GB。

全頁 OCR 對此 caption 有效，但既有圖框限制仍在；55 頁 conversion success 與結構差異盤點也不等於 55 頁逐字／語意正確率。因此未把全頁 OCR 改為全量預設，未開 C 的 29 個 component OCR／58 個遠端 enrichment jobs。

NCCU screenshot 全圖 literal blocks／UI 關係，以及 timeline 的 45 模型、19 個黃色標籤、完整年／月份軸與確定連線已補入 [evaluator addendum](../pdf-core-c-source-closure-2026-10-18/evaluator-full-image-contracts.json)。不清楚的小 logo 字、無個別連線的精確月份明列 source uncertainty，沒有借外部日期補答案。這是單一 annotator 的兩次來源視覺核對，不宣稱獨立人工 adjudication。

## 配置取捨與停止點

1. **保留 S0 作低成本實驗基線**：StandardPdfPipeline＋PyPdfium、Heron CPU FP32、RapidOCR selective/AUTO、TableFormer V1 accurate＋cell matching；不代表完整 Profile 已驗收。
2. **保留 B 接點，候選不晉升**：新表示確實可承載 multi-panel、aggregation scope 和 paired cells，但模型仍有大表漏列與數學誤讀；不是再加 renderer 或逐例修補就能視為成功。
3. **FULL_PAGE 保留為有證據的備選配置**：改善 native-text 污染且增加 CPU 成本；尚未驗證能通用選擇這條備援的 routing rule。
4. **C 依凍結來源 gate 停止增強**：後續需要處理跨 owner 的來源上下文／圖像邊界。既有 full-owner 實驗不能解決所有跨 owner 情況，不能將同一方案重跑當新候選。
5. B 下一個有價值的比較是換模型後重用同一凍結協定與來源，保留 T04／E017 失敗；不是修這兩筆答案。C 下一個決策是附來源的跨 owner／同頁上下文是否納入圖像增強輸入，以及它的額外成本。這些均未在本輪擴跑。

已到原計劃的明確停止點：候選尚未符合必要門檻，故未啟動 OmniDocBench 60 頁外部回歸。A mapper／頁級 fallback、Paddle、六份 sealed holdout、公司 GPU／Qwen3／vLLM 和高頻負載仍未啟動。

## 執行驗證與金鑰

B 的 13 項 controls、pre/post dry-run 通過；evaluator 另以實際儲存 Markdown 的數值竄改測試確認會拒絕交付／渲染不一致。Supervisor v2 的八項回歸通過，本輪 55 頁也乾淨退出。舊 C 的 159 來源檔／61 引用 hashes 與 15 負控制仍通過；原快照和錯誤紀錄均未回寫。

使用者授權的金鑰已存至 repo 外、0600 的私人設定檔，zsh 新 shell 會在尚無該環境變數時載入 `OPENAI_API_KEY`。已核對新 shell 與私人設定一致；研究產物掃描未發現金鑰值。CPU worker 不繼承該金鑰。沒有 GitHub 發佈、commit、push 或 production 修改。
