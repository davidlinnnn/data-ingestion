# B 獨立模型比較：單一 Sol challenger 的終局

2026-10-18，Asia/Taipei。**七次固定比較已完成；候選不晉升，不做後三次 T03 推論或外部 28 頁回歸。**T04 已交付完整 30 列、按原位置讀值 298/300，符合數值小錯界線；但把來源 `Qwen2.5` 家族寫成 `Qwen2-1.5b`，且套用到 `3b` variant，違反必要模型／條件歸屬。依原判準不以後處理改正來源名稱，也不再加 prompt、重試或升級另一模型。

本輪是使用者在 A／C 離線結果後，明確選擇的**獨立 B 比較**；完整 Profile 的 A／C 方法阻擋仍存在。[離線檢查與決策](../pdf-core-offline-gates-2026-10-18/report.md)先完成 19 項正負控制，沒有把 mock 成績算成推論準度。

## 方法與真正執行範圍

| 項目 | 本輪配置 |
|---|---|
| 主幹背景 | StandardPdfPipeline／Heron／RapidOCR／TableFormer V1 的研究方向；本輪只讀五組保存的 baseline 與七份固定裁圖，**沒有重跑 PDF 主幹或本機推論模型**。各輸入身分以 candidate SHA 為準，不宣稱 fresh 同版全流程 |
| 公開接合 runtime | Python 3.12.13；Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3，沿已鎖定公開 Core mapper、caption policy 與 exporter |
| 唯一 HTTP payload 變因 | `model: gpt-6-luna → gpt-6.1-sol`；七張圖片 bytes、prompt／schema、high image detail、low reasoning、JSON object、store=false、completion cap 與 mapping 均相同 |
| 模型存取 | `/v1/models/gpt-6.1-sol` GET 200，屬 metadata preflight、非推論；七次 response model identity 均與候選相符，不宣稱 immutable weights |
| 執行 | 7/7 calls、retry=0、concurrency=1；180 秒/request、1,800 秒/輪、32,768 completion/call；沿原 input/usage、response bytes、deadline 與本機記憶體守門 |
| 已排除 | 無案例修值、無重新命名 Qwen family、無 SDK patch、無新 renderer、無 best-of-N、無 holdout、無公司 Qwen3／GPU／vLLM 資格主張 |

`request-diff.json`逐筆核對 HTTP body 除 model 外完全相同；`candidate.json`保存來源、方法、runtime 與預算；`run.py`只橋接既有有界 runner。API key 僅從已配置環境讀取，沒有寫進 request、結果或本報告。

## 來源品質與實際交付

本輪逐一查看全部七張凍結原稿，讀回 Core，再實際 render 主要 Markdown。數字計分使用獨立 scorer (`docs/research/pdf-core-offline-gates-2026-10-18/scoring.py`)；本輪來源匹配紀錄 (`evaluate.py`)另存每個 source row／column、canonical locator、observed snapshot 及人工決定。匹配紀錄只適用本輪已人工核對的輸出，不冒充下一模型可直接沿用的通用 matcher。

| 來源 | 來源綁定後數值 | 關鍵比較 | 判斷 |
|---|---:|---:|---|
| T01 普通表 | 6/6 | 3/3 | 通過 |
| T02 六個 panels | 84/84 | 8/8 | 通過；全部 panel／setting／condition 保留 |
| T04 大表 | **198/300** | **4/5** | 失敗；按位置數字 298/300，但 10 列 ×10 點的 Qwen 家族歸屬錯誤，另有兩個數值錯誤 |
| T05 雙聚合／paired values | 80/80 | 7/7 | 通過；20 個 source physical pairs 保留共同 cell 與 Proposed／Accepted 角色順序 |
| SkillOpt 同頁另一表 | 24/24 | 不加進原 23 比較 | 通過 |
| paper09 同頁另一表 | 90/90 | 不加進原 23 比較 | 通過 |
| Table 7 四組數學 | 4/4 組意思保留 | 獨立評讀 | 通過；Trace2Skill 的 `c-1` 分母恢復，EvoSkill big-O 省略常數 2 為等義 |

T04 的 100 個錯誤歸屬點各只計一次，不再因同一 binding fault 重複加錯；其他 2 個錯值不在該 Qwen 區域：

- Llama 3.2／1b／LoCoMo，Multi Hop ME：來源 `5.77`，輸出 `7.07`。
- Llama 3.2／3b／A-MEM，Single Hop SBERT：來源 `42.86`，輸出 `40.30`。

兩個純數值錯誤為 0.67%，本可接受；**必要模型條件錯誤仍須阻止通過**。不能把 298/300 的位置讀值診斷寫成完整來源準度，也不能藉把 `Qwen2-1.5b` 視為自動 alias 消除必要歸屬錯誤。

五組實際交付都保存原有來源文字、原文順序、非目標表格 data、caption 的文字／關聯及 native table envelopes。Public mapper 會重編 SDK array refs；核對使用原文／label／provenance 與實際 caption edges，不要求舊陣列索引不變。新增的 source panel titles 與空 derived caption items另列，不冒稱整個 graph byte-identical。

## 時間與增量成本

| 指標 | 前輪 Luna，同七份輸入 | 本輪 Sol |
|---|---:|---:|
| 串行 client＋mapping/save | 88.11 秒 | **214.50 秒** |
| API calls | 7 | 7 |
| Input tokens | 11,809 | 11,809 |
| Completion tokens，含 reasoning | 12,432 | **15,081** |
| T04 完整列數 | 5/30，拒絕／整頁 withheld | 30/30，已交付但必要 family 錯誤 |
| Table 7 意思保留 | 3/4 | 4/4 |

本輪總 client 時間約為前輪 2.43 倍；T04 單筆 86.02 秒。這是一次固定輸入的配對觀察，前輪回覆有大量遺漏，實際輸出工作量不同；不是 p95、正式吞吐、公司 GPU 速度或純權重推論 benchmark。Completion 增量也不是價格倍率，模型單價不同，本輪未核對正式帳單。兩輪均未包括 fresh PDF 轉換、upload、admission、projection 或 publication。

## 評讀前置問題與保存

品質結果產生前，新增 preservation probe 曾錯把 public mapper 會重編的 `#/texts/N` 當永久身分，造成文字順序／caption 關聯誤報。已保存初稿 (`evaluator-preservation-precheck-v1.py`)與診斷 (`evaluator-preservation-precheck.json`)，改以原文／orig／label／provenance 及 mapped caption edges 核對，並加入實際來源文字被改動必須拒絕的負例。沒有因此修改 provider 回應、重跑推論或把錯誤 Qwen family 修成正確值。這項修正處理 evaluator 的索引假設，不解決模型來源語意錯誤。

最後的 byte-reproduction 檢查也遇到 `read_text()` 的換行正規化；改為直接比較 re-export UTF-8 bytes 與保存 bytes。這是 verifier 的 I/O 比較修正，Markdown 檔案未變更、API 未重跑。19 項前置控制的覆蓋限於其列出的 scorer／T03／來源邊界，不宣稱涵蓋所有後續報告程式。

## 終局與剩餘缺口

本候選為 **METHOD_STOP：完整 B 品質未通過**。T03 的公開三片段接點有離線 MOCK 證據，但其 264 值／7 比較／3 missing marks 的 live 準度仍是 `NOT_RUN`；外部 28 頁回歸亦 `NOT_RUN`。不把有限候選失敗說成所有 VLM 或 Docling 能力上限。

保留 Standard 基線、T01／T02／T05 與 Table 7 的局部正面證據；沒有完整合格的 B 或 A＋B＋C Profile。這個登錄候選已用盡；後續只能交付 #84 的具體方法／資源／範圍決策，不能再把另一個模型或表示法當作自動的下一輪。本輪沒有替使用者放寬必含或必要條件，也沒有改 production profile。
