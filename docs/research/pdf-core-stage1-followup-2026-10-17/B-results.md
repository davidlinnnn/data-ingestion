# B 固定六次 compact-table 比較結果

日期：2026-10-17。**六次真實 API 呼叫已完成；精簡協定顯著減少本輪輸出用量，但完整表格交付未通過。保留元件候選，第三段完整配置仍未放行。**

Matt review 後已修正評分器，使用同六筆保存回應完成離線重評；下表結論不變。最新機器報告為 新版評分 (`B/rescore-v2/evaluation.json`)與交付／失敗診斷 (`B/rescore-v2/postrun-review.json`)，原報告保留。

## 方法與執行

主線執行 `B/live-registration.json` 的唯一凍結配置：cached StandardPdfPipeline S0、Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3、原四頁全部六張 native table body crops、144 DPI、不補邊或縮放。模型為 OpenAI `gpt-6-luna`、Chat Completions、image detail high、reasoning low、store false、JSON object；每次 completion cap 32,768。這是自訂精簡表格協定＋公開 Core 接合的元件研究，不是新的官方 Docling pipeline，也不代表公司 Qwen3 的成績。

六筆 HTTP 200，finish_reason 均為 stop；沒有 retry、超額、截斷或額外 probe。全部請求完成後才開啟來源評分契約及評讀新輸出。四筆 target 通過結構檢查，兩筆未通過；同頁必要 target 不完整便不映射，因此四頁中兩頁完整保存並讀回。

首次本機啟動在 sandbox 的 `psutil.children()` 權限檢查停止，實際請求與 target attempts 都是零。紀錄保留於 `B/live-launch-sandbox-no-requests/`；確認程序監測權限後沿同一凍結配置執行六次，沒有放寬資源界線或重抽模型答案。

## 品質與交付

| 主案例 | 原始內容核對 | 實際交付 | 判定 |
|---|---|---|---|
| T01 普通表 | 6／6 數值、3／3 關鍵比較 | Typed 與實際 rendered Markdown 均為 6／6；來源 caption 一次、非目標內容／來源保持 | 通過 |
| T02 六 panel 表格 | 84／84 數值、8／8 關鍵比較、panel／header 核對通過 | Typed 與實際 rendered Markdown 均為 84／84；原 caption 與 4:1:5／training-subset 等條件保留 | 通過 |
| T04 多層表頭／多列維度 | **僅位置診斷** 299／300 數值、5／5 比較關係；其中 25.38 被讀成 28.53 | 無 accepted typed／Markdown；grid 的第二列 14 格，其餘 13 格，Category 子表頭錯位、Model／其他 spans 亦不一致 | 未通過結構與表頭歸屬 |
| T05 分組／paired values | **僅 raw 宣告 scope 診斷** 80／80 數值、7／7 比較、20／20 paired cells | 無 accepted typed／Markdown；Category 的 rowspan 覆蓋位置輸出空字串而非 null；section 完整寬度 spans 與 category row roles 亦未保存 | 未通過凍結協定／交付 |

T04 的 1／300 數值錯誤本身落在既有 5% 容忍內，沒有因此改成零錯標準；其阻擋是表頭／條件歸屬與非法結構。T05 的 raw 內容診斷正確也不等於已交付。未將空字串改 null、補齊／平移 ragged header、猜 spans 或回填 roles；未產生修補後的成功文件。

保留原 **470 數值／23 比較**分母。不能把 T04 的位置診斷與 T01／T02 的有效語意綁定混算成完整準確率；實際主案例 typed／Markdown 交付涵蓋 90 個正確數值及 11 個比較，另外兩個主案例仍未交付。

兩張 collateral 另列，不增加主分母：SkillOpt Table 3 的 24／24 數值核對正確並隨該頁保存；paper09 Table 7 的 90／90 數值核對正確、target 結構合法，但同頁主表失敗，所以整頁不採用。MEMGPT／MemGPT、Adversarial／原文 Adversial 等字形差異依既有 minor 原則記錄。

## 用量與延遲

比較對象為上一輪相同六張 crop、同模型 alias／low reasoning 的完整 TableData JSON；原輪 completion cap 為 65,536，本輪為 32,768，兩輪均未撞 cap。

| 指標 | 上一輪完整 cell JSON | 本輪 compact grid |
|---|---:|---:|
| 請求數 | 6 | 6 |
| Input tokens | 7,934 | 8,144 |
| Completion tokens，已含 reasoning | 28,800 | 7,869 |
| 整輪 live 時間 | 210.84 秒 | 107.78 秒 |

本輪 completion tokens 減少 **72.7%**，整輪時間減少約 **48.9%**；input 增加 210 tokens。這是單次 DEV 實測，不能推成穩定吞吐／p95 或把全部時間差歸因於協定。尤其 SkillOpt collateral 本次 52.19 秒，上一輪 15.12 秒，即使其 completion 從 1,860 降為 628；遠端排隊／服務變動未知。

本輪各 request HTTP roundtrip：4.30、8.97、52.19、19.07、12.71、10.39 秒。兩頁 mapping 分別約 3.3／10.3 毫秒，serialize／reload／save 約 33.4／17.2 毫秒。API worker 的記憶體樣本保存在 `B/live/resource-samples.json`；這不是遠端模型的 GPU 記憶體或算力。

時間與用量包含失敗 target；未把它們排除以美化結果。上游 Standard 為 cached，本輪 107.78 秒不含新 PDF／OCR／TableFormer 基線，也不是文件 ingest 端到端 SLO。

## 主線去留

精簡 grid 的 token 優勢已有正面證據，T01／T02 也保住內容與真實交付；它可以留作候選。但本輪不足以選為正式複雜表格配置：模型仍會產生矛盾的 grid／span／role，T04 的語意表頭也未成立。

下一個問題應是：在既有 minor 容忍與維護成本界線下，是否存在一個小而通用的表示／模型接點，能穩定生成合法結構；不要再用逐表修值、移欄或大量補洞推升這份 DEV 分數。需要重訂方法時另作登錄與確認，本輪六次已結束，不追加 prompt 重試。

## 證據與評分更正

- `B/live/observations.json`、`execution.json`、`page-assembly.json`：實際呼叫、usage、時間與交付狀態。
- `B/rescore-v2/evaluation.json`：修正後四案例完整分母、raw／typed／實際 rendered Markdown 分數。T01／T02 Markdown 欄現在正確記為 6／84。
- `B/rescore-v2/postrun-review.json`：修正後實際 rendered Markdown、失敗 raw 診斷、collateral、原 caption／非目標內容保持與成本比較。
- `B/evaluation.json`、`B/postrun-review.json`：原報告保留；評分器與原報告的版本／雜湊另存 `B/evaluator-archive/v1/manifest.json`。
- `B/live-integrity.json`：方法核對、142 個歷史產物未變及 credential pattern scan。
- `B/evaluation-correction.json`：保存評分器更正理由與舊報告。原候選與 oracle 均未變；T05 的 null header 須依其已宣告 spans 讀取，不能直接當作名為 None 的表頭；ref reindex 後以內容／來源 signature 核對保存，不能以舊 self_ref 判斷。

本次修正關閉 Matt review (`docs/reviews/pdf-core-b-script-review-2026-10-17/review.md`) 的三項缺陷：T01 計入全部 panels、額外與重複數值及各 panel 表頭；T05 依 supplement 的明示 row-group 區間核對每列，不能從前一 section 默認延伸；paired cell 結構改檢查共同實體格與角色順序，數值錯誤另依既有 ≤5% 與關鍵比較門檻判定。`3.1 / 1.6 → 3.2 / 1.6` 的 1／80 錯誤可以通過；拆成兩格或反轉 Proposed／Accepted 順序仍失敗。舊的 literal-pair 精確比對只留作診斷。

複核亦補上 T02 重複 panel 的缺值比較處理，並核對實際 rendered section 標籤，避免 Markdown 的錯誤分組條件被正確 supplement 掩蓋。合法分拆普通表的 rows 至兩個 panels 仍可通過，沒有把多 panel 一律當錯誤。T04／T05 額外 panels 不再被忽略；目前不提供這兩種複雜表的一般多 panel 自動通過路徑，T04 完整 rendered 評分亦待後續方法成立後補齊。

測試紀錄 (`B/rescore-v2/test-log.txt`)為 **35／35 通過**（13 evaluator、22 runner）；完整性核對 (`B/rescore-v2/verification.json`)確認 35 個 live 檔案、142 個歷史產物、frozen producer 與原報告未變。重評用量及時間沿用原六次，不是新推論；來源條件仍須人工 review，`content_pass` 不等於 ingest 時可自動證明完整 Canonical Acceptance。修正後獨立複核 (`docs/reviews/pdf-core-b-script-review-2026-10-17/fix-review.md`)與 diff (`B/rescore-v2/changes.diff`)另存。中途離線預檢報告亦保留在 `B/evaluator-archive/v2-precheck/`，不作最新結論。

未讀 holdout、未做新本機模型推論、GPU／公司 Qwen3／vLLM 或高頻負載驗證；本次只有已曝光 DEV 的六次元件比較。完整配置與第三段仍未放行。

## 後續離線契約審核

[表示契約審核](contract-audit.md)已另立 `grid-spans-v2-padding`，只處理明示 span 內的精確空字串 padding。原六筆回應的離線 replay 現有五個 target／三頁可交付，T05 為 typed／Markdown 80／80，T01／T02 無 material 回歸；T04 仍失敗。此新方法沒有推論新答案，也沒有回頭改判上表原 v1 結果。45 個控制測試與三頁第二 process 讀回通過；因 T04 仍需猜移欄才可解，停止本輪 B 的追加推論，完整 B／第三段不放行。接續 A 的公式／code ownership／coverage，再處理 C 的同版圖片接合。
