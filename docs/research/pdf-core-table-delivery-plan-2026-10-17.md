# 下一輪：表格辨識結果到主要 Markdown 的有界驗證

2026-10-17。**建議下一輪只回答：已保留正確數值關係的表格 VLM，能否透過少量公開資料映射，交付可用的結構表格、主要 Markdown 與來源連結？** 本文件完成規劃；尚未實作接合、載模型、呼叫 API、讀 PDF／圖片或開啟 holdout，也未解除 Paddle 暫停。不是正式 Processing Profile 或 Canonical Acceptance。

## 為何選這個問題

[E1](pdf-core-standard-enrichment-results-2026-10-17.md)已證明原生 CodeFormulaV2 接線可執行，但精確 literal／數學與內容歸屬仍有缺陷，不繼續針對這些個案調參。[既有 table API](pdf-core-g2-api-2026-10-14.md)則有完整六 panel **84/84 數值綁定、8/8 關鍵比較**的正面證據，尚未經 typed table／主要 Markdown／來源綁定驗證。先驗這段交付，比再產生一份未整合的 raw 更接近方案取捨。

這不是把舊 JSON context 的36次推論換名重跑，也不宣稱有新模型突破。新增假說是：**正確的表格關係可由公開 Docling Core 型別承載，且機械映射不需要內容修補。** 舊成功回應使用全頁圖片及指定 Table2 的 prompt，不能視為自動 native inventory 路由已通過；下一階段另外驗這個差別。

同一 Granite Vision4.1 checkpoint 早已做過 CPU timeout 與兩張其他表的 MLX GPU 實測 (`paper-pdf-granite-mlx-results-2026-10-11.md`)，不能當未試新模型。現版官方 table stage 亦沒有公開 MLX／API engine 接點，詳見[查證](pdf-core-next-table-path-notes-2026-10-17.md)。本輪不重試該 CPU 配置；T02 的 Granite MLX 任務覆蓋保留為次選，不與這輪混跑。

## 固定方法與自訂範圍

| 部分 | 本輪安排 |
|---|---|
| 主幹 | 沿用 S0：Docling2.132／Core2.99、StandardPdfPipeline、PyPdfium、Heron、selective RapidOCR v6 det／rec-small＋v2 cls、TableFormer V1 accurate、原生 reading order／assembly |
| 關閉 | code／formula enrichment、圖片 enrichment、heading recovery；不把 E1 的局部成功混入新組合 |
| Baseline | 重用已保存 S0 document／實際有效設定／資產身分；不是重設成 SDK defaults，不重跑整份論文 |
| 表格接合 | Standard 輸出後的**研究用接合**；從 native table inventory 選全部 table targets，以公開 Core 型別及 manipulation API 承載，不稱為官方內建 API table stage |
| 表示 | 每個邏輯表保留 source key；每個 panel 以 TableData／TableCell 保留原有 title、header、setting、printed values 與順序，可形成同一邏輯表下的多個子表；caption 只交付一次 |
| 輸出 | provider raw、映射後 Docling JSON、stock Markdown、source-key 對應與診斷分開保存；不寫自訂 Markdown renderer，不把 raw JSON 當主要 Markdown |
| 暫用 producer | 後續 live 階段使用已獲允許的 gpt-6-luna／OpenAI-compatible Chat Completions；它是暫用候選，不能冒稱在驗 Qwen3 或 Granite |

公開 `add_table` 支援 TableData、caption reference、provenance；`add_group` 與 `insert_item_before_sibling`／`replace_item` 等可操作文件樹。**存在 API 不保證多 panel 子樹替換已可行**，這正是離線 gate 要驗的內容；若不能用公開操作完成，就停止，而非改 private tree helper。[Core2.99 document source](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/document.py)、[stock Markdown serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)

本次 source 查核使用已安裝2.99／2.132原始碼；網頁鏡像未成功取回，不以它補充未讀到的行為。公開原始碼連結供重查，實驗前保存本機 source hash。

## 步驟一：不呼叫模型，先驗表示與寫回

投入上限 **90分鐘、0新推論、0安裝／下載、0production修改**。只在 research 目錄放最小 prototype 與檢查，重用既有 raw、S0 JSON 和評分器。

1. 固定輸入與版本 hash：舊 Table2 raw、S0 SkillOpt p8 JSON、原 G1 oracle。舊 raw 的84點正確是既有結論，不重新算成一次新的模型成功。
2. 將完整 raw 映射成公開 table 型別，維持六 panel、28 data rows、84個 printed values／metric 綁定與全部來源條件。不得補值、改精度、改字或用 oracle 選 header。
3. 在 S0 副本替換對應 table 的表示，保留 caption、前後正文／Table3及原始順序；匯出 stock Markdown、JSON reload 後再匯出。若拆成子表，caption 與條件不能遺漏、重複或錯掛。
4. 驗證無失效 reference／orphan／重複舊表；除預先宣告的 table 子樹及相關引用重編號外，其他來源 item 內容／位置／次序相同。不能因正常 ref reindex 就誤報正文改動，也不能只比數值而漏掉正文重複。
5. 以普通單 panel、重複 metric、缺欄、row 比 columns 多一格、越界／不存在來源、保存後 reload 等小型正負控制驗證 mapper。另將新 `targets` 封裝的合成合法回應走與 live 相同的 parser→mapper→export，並測漏 target、重複 key、未知 key 的拒絕。登錄與回應的 target key 集合必須完全相同且各一次；違反即整頁協定失敗，不部分採用。mapper 只驗格式與配對，不使用84點／28列等 oracle 數量判合法；格式合法但來源多寫／少寫的 row 或數值交由 source evaluator 評分，不能假裝在 ingest 已知答案。

**來源粒度必須誠實。** 舊回應沒有每個 panel 的 bbox；可保留確實成立的 page／native table envelope 及輸入 image hash，但不得合成 panel／cell 精確位置。source-key manifest 要標出「table envelope，非 panel/cell 精確定位」。離線使用已知 T02 對應是 replay，不能算自動 routing 證據。

舊 provider caption 少字面 `Table 2` 前綴的缺陷原樣保留在 raw。整合可引用 Standard 已抽出的原 source caption；若它本身不完整，記缺口，不能硬編表號或從 oracle 補出。此步通過只代表表示與交付可行，不代表舊模型輸出已無缺陷。

**Gate：**上述內容／關係與 stock export 均能保留，且不需要 private hook、另寫 renderer、修數值、人工逐 panel 配對、案例專用規則，才進步驟二。90分鐘內不能完成，保存具體阻礙與最小新增維護成本，停止本輪，不無限擴充 adapter。

## 步驟二：同一配置，兩頁端到端驗證

僅在步驟一通過及安全配置的 credential 可用後執行；不從歷史聊天擷取金鑰。實際送出前保存單一通用 prompt、JSON schema、有效參數、全部 native targets、影像 hash、identity／資產與完整來源範圍。不得根據第一次結果改 prompt 再跑。

| 固定案例 | 用途與判準 |
|---|---|
| Memory-R1 p8／G1-T01 | 普通表保護：既有6個值／3個比較維持正確，header、caption及來源關係保留 |
| SkillOpt p8／G1-T02 | 完整六 panel：固定84綁定分母，數值錯漏／錯配／額外值最多4點（≤5%），全部8項 critical comparisons 正確；panel、setting、metric、caption與條件均可解讀 |

**每頁一張144dpi全頁圖、一次 API request，普通表頁→複雜表頁，共2頁／最多2 requests。** 一個 request 包含該頁全部 native table targets 的 opaque key 與轉成輸入像素的 bbox；同一通用 prompt 要求依 target 回傳可見 panel／header／row／value。不以「Table2」等來源名稱選題、不手裁六個 panels、不傳 oracle 值或正確轉錄。SkillOpt S0 該頁已有兩個 table items，因此另一張表也是附帶工作，必須保存並檢查，不可靜默略過。

推論前清點兩頁的 targets，**合計上限8個**；超過就停在規劃差異，不能偷偷省略以符合預算。native target 漏整張表或 bbox／caption 不足以唯一綁定時，記 inventory／來源路由缺陷，不用人工補表來宣稱完整 pipeline 通過。

使用現有 installed client，endpoint 固定；image detail high、reasoning low、JSON object、max_completion_tokens8192、store false、TLS驗證、concurrency1、retry0、每request180秒。新通用 schema 至少有 `targets[{target_key, caption, conditions, panels[...] }]`；panel 內含原有 title／columns／rows，value為 printed string。8192含reasoning及可見輸出，非文字長度保證；token截斷／refusal／不合法 key 或 schema 為明確失敗，不自動重送。

API／映射／export 階段合計上限30分鐘；本機處理 sampled RSS上限12GiB、system available至少8GiB，觸線停該配置。若需要重新跑兩頁 Standard，也用原 S0 精確配置並計入本輪CPU模型與時間，不稱「零推論」。能以已存且hash吻合的 S0 doc／同pixel images重放時優先重用，清楚標成 cached-upstream end-to-end，不能稱 fresh conversion；這輪不做fresh/restored認證。沒有可用 credential 就只完成步驟一，步驟二明列未執行，不因此切換模型。

同時評 raw 與交付結果；原 frozen oracle 只在 inference 完成後由評分器讀取。以 table／panel／setting／metric 的完整綁定比對，並讀主要 Markdown 是否仍能解讀相同條件與比較；不以行列數或數字出現率替代。附帶另一張表及兩頁所有非 table 內容另做前後回歸，不擴大 T02 分母。client RTT、usage、映射／export時間分報，不算Qwen3/GPU latency或p95。

## 完成後的去留

- **離線映射即失敗：** 不再追加模型；交付接合本身的成本已超出本輪界線，提出具體型別／export／來源限制供決策。
- **raw 正確但交付失敗：** 問題在映射／export，不能歸咎模型或只報 raw 通過；停止此接合，不修 renderer。
- **live raw／路由失敗：** 固定配置不採用；保留完整失敗，不透過補值／逐題 prompt 挽救，也不重試 Granite CPU。
- **兩層均通過且普通表不退步：** 保留為「表格 API 接合可行」的開發證據；下一個候選是公司具名 Qwen3-VL／vLLM 上的同協定比較，不直接採用正式profile。

這兩頁是已曝光 DEV，不是泛化證據。完整 G1 表格覆蓋、未開封 holdout、公司CUDA／vLLM、併發／高頻 ingest及完整 canonical交付仍待後續資格驗證。code／inline公式與圖片 supplement 的必含缺口不因表格成功而抵銷；若還需新增 detector／內容修復才能覆蓋它們，必須另列實際成本，不能默默把本輪擴成通用文件後處理平台。
