# B：單一模型 challenger 的有界比較建議

2026-10-18，Asia/Taipei。僅查官方文件與既有研究證據；未呼叫模型 API、讀取 credential、下載模型或載入權重。

**執行順序補充：** 本文件只查證模型候選；主線後續找到現有 evaluator 仍綁定當輪輸出。模型比較須等 [B 收斂計畫](plan-and-causal-review.md)的 evaluator／T03 離線 gate，不代表已可直接 live。

## 建議與可回答的問題

建議先暫停 C 的新推論，對 B 只登錄 **`gpt-6.1-sol` 一個 challenger**，沿用已完成的七次來源、prompt、semantic schema、parser、Core mapper 與 Markdown 輸出。這次回答：「相同輸入與交付契約下，較高能力／成本層級的通用 VLM 是否能消除大表漏列與公式意義錯誤，同時保留既有通過項目？」它不回答 Qwen3 等效性，也不能解決尚未成立的跨頁來源 grouping。

這是根據產品定位與既有失敗類型提出的**待驗假說**，不是官方聲稱該模型在本專案表格任務上必定較準。

## 已查證的公開模型身分

| 模型 | 官方已公布的可用能力 | 本輪處置 |
|---|---|---|
| `gpt-6-luna` | 公開 API model ID；image input、Chat Completions、low reasoning；Standard text input/output 為每百萬 tokens $0.10/$0.50 | 保留已完成基線，不為湊配對重跑。官方頁沒有另列可選的日期 snapshot。 |
| `gpt-6.1-sol` | image input、Chat Completions（不使用 tool calling）、low reasoning、structured outputs；Standard input/output $2/$10 | 唯一建議 challenger；僅換 `model`，其餘 request 設定不變。 |
| `gpt-6-astra` | image input、Chat Completions、low reasoning；Standard input/output $10/$50 | 有效但本輪不加入；若 Sol 失敗，不自動再往上追價。 |
| 公司 Qwen3-VL | 目前僅有部署系列與 OpenAI-compatible 的使用者資訊 | exact model ID、checkpoint／量化、server 版本、連線仍待實際確認；不把 OpenAI 結果當作其準度、GPU 效能或吞吐證據。 |

來源：[Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)、[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)、[Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)。以上是實際打開的官方頁面，不是從 Codex model inventory 推測 API ID。價格為查詢時 Standard 公開單價，帳戶 access／rate limit 未驗證。

官方 changelog 記錄 Luna／Sol 的圖像編碼修復於 2026-09-25、6.1 Sol 發布於 09-29；本專案最近 10-18 實測在修復之後，因此沒有證據把近期錯誤歸因於那個歷史 bug。[官方 changelog](https://developers.openai.com/api/docs/changelog)

## 固定比較範圍與成本

1. 登錄前核對完整來源／request hashes、parser controls、runtime 及模型支援的 request 參數；不要在這一步改 prompt、schema 或 serializer。新 request 的差異限定為 model 字串及因此必然改變的 request hash；採用公開 model ID，不捏造 immutable snapshot。
2. 保留相同七 targets：Memory-R1 p8 一張、SkillOpt p8 兩張、paper09 p17 兩張、WikiSkill p13 一張、WikiSkill p22 Table 7 一張。全部成功／失敗都留在評分，T04 同頁 atomic acceptance 不變。
3. 固定 high image detail、low reasoning、JSON object、store=false、32,768 completion cap／call、180 秒／call、總計 1,800 秒、concurrency=1、retry=0，最多七次。保留原輸入保留額與 completion 總額；有 usage 不明或資源停止時不繼續送後續 calls。語意失敗留檔，不逐例重試或修答案。
4. 原 470 數值／23 比較、兩張 collateral 與四組 table math 全部評讀；Core 與實際 Markdown 都要成立。每張複雜表 ≤5% 數值錯誤、必要 scope／conditions／critical comparisons／公式意義正確。已通過的 T01、T02、T05 不能退步到不合格。
5. 純按原先 Luna 實際 11,809 input＋12,432 completion tokens，以 6.1 Sol 單價估算約 $0.148；這只是**相同 token 數的示例**。新模型實際 reasoning／輸出 tokens、視覺 tokenization 與 latency 可能不同，不能當預測或硬支出上限。106,634 input reserve＋229,376 completion allocation 的價目算術約 $2.51；input reserve 是 heuristic，仍須以 provider usage 與原有超額停止機制為準。
6. 公布 provider model／fingerprint（若提供）、raw、finish reason、usage、每次 latency、解析／映射／輸出耗時與峰值記憶體。官方頁未提供可自行鎖定的日期 snapshot 時，不能把 alias 當 immutable weights。相同 `low` 名稱也不代表模型耗費相同 compute。

官方圖像文件說明 detail 影響 preprocessing，且不同模型的 resizing／計費規則可能不同。因此只能稱「相同傳入 crops 與應用設定的候選比較」，不能稱內部 pixel tensors 或純權重單變因已相同。這輪不另改 original detail，避免把模型與輸入策略同時改動。[Images and vision](https://developers.openai.com/api/docs/guides/images-vision)

## 停止規則與 B 完成界線

- 若 challenger 仍有重大漏列、條件錯綁或公式改義：結束這一輪模型比較，報告目前契約／候選的能力限制，回到取捨決策；不自動擴成模型搜尋、逐題 prompt tuning 或增加 renderer。
- 若七次全部符合門檻：只代表這些曝光 DEV 來源通過，取得後續固定外部回歸的資格，不是泛化證明或完整 B 驗收。
- **T03 跨頁 logical ownership／grouping 仍是獨立 B 必要 gate。** 七張 single-page crops 沒有它的上下文，換 API 模型不會自行新增來源關係。須先定義有來源依據、可泛用的交付方式，或將已證實的官方能力限制帶到明確需求取捨，不能在另一張表通過後宣稱 B 完結。
- 公開 benchmark 不能稀釋既有失敗；公司 GPU／vLLM、高頻 SLO、六份 sealed holdout 仍獨立。

本輪歷史依據：[固定七次結果](../pdf-core-fixed-seven-source-2026-10-18/report.md)、[七次 frozen contract](../pdf-core-eval-interfaces-2026-10-18/B/report.md)。T04 raw 只有 5/30 列、50 個數值且有 undeclared group；Table 7 E017 將 `c-1` 寫成 `c_{-1}`，均是 provider 來源／協定缺陷，並非新增 renderer 即能恢復。這個最近結果不支持「目前失敗仍全是測試程式的錯」的說法；早期 harness 問題須由另一份時間線另行歸因。

## 避免重複已走過的路

| 路徑 | 已有證據與限制 | 下一輪是否重跑 |
|---|---|---|
| Standard＋TableFormer V1/V2 | V1 accurate 為現有低成本 S0；V2 的 T02 試驗並非新候選空白 | 否；維持來源基線。 |
| Granite-Docling 258M | T02 全頁與完整 OTSL table crop 均已實測，仍有漏值與 scope／binding 缺陷 | 否。 |
| Granite Vision 4.1 4B | 相同 revision 的 CPU 有資源／timeout 問題；MLX component 接合已完成其他長表但數值／關係仍錯。Docling 2.132 原生 table stage 不直接接受 MLX/API engine；目前六 panel T02 尚非同任務覆蓋 | 不把換名字或補 task coverage 當全新方法；本輪不新增 plugin／CPU retry。 |
| dots.ocr＋MLX VlmPipeline | 12 頁完成，GPU 可用但來源公式／code／交付仍缺陷；整頁路徑與本輪單表 API 接點不同 | 否；不把已知不合格的整頁路徑重新包裝成本輪 challenger。 |

依據：[Granite-Docling 實測](../pdf-core-g2-round3-2026-10-14.md)、[Granite Vision 固定版來源與既有 CPU/MLX 結果](../pdf-core-next-table-path-notes-2026-10-17.md)、[dots MLX 實測](../pdf-core-g2-dots-mlx-2026-10-16.md)。這些是歷史研究結果，不能推論整個模型家族、公司 CUDA 或未測 checkpoint 都失敗。

未驗證帳戶 model access、未做新推論、未讀取或更改金鑰。推薦僅收斂到一個可檢驗的候選；沒有聲稱它已解決 B。
