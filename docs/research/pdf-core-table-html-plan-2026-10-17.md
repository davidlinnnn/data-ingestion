# 下一輪：官方 HTML 表格匯入與單頁表格覆蓋

2026-10-17；規劃完成，未實作、載模型、安裝、呼叫API、讀PDF／圖片或開啟holdout。承接[兩頁live結果](pdf-core-table-live-results-2026-10-17.md)。

**下一輪目標：收斂一條能保留單頁表格的表頭、列維度、合併關係與數值的交付路徑。** 現在的數值正確已有正面證據，但單一`setting`欄位的自訂協定沒有承載原始`Method／Setting／Component`。不再只為這幾個字加特例；比較一個通用表示方法：

`S0 native table inventory → 同一VLM回傳table HTML → 官方HTML backend → 公開TableData → 原文件／stock Markdown`。

這是新的**表示／parser組合假說**，不是新模型，也不是已通過的官方完整PDF pipeline。官方有公開`DocumentConverter.convert_string(..., InputFormat.HTML)`，HTML backend能建立TableCell spans／headers；把API結果綁回原PDF仍是研究接合。[固定版converter](https://github.com/docling-project/docling/blob/v2.132.0/docling/document_converter.py)、[HTML backend](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/html_backend.py)、[查證筆記](pdf-core-table-html-source-notes-2026-10-17.md)

## A：先驗官方表示接點，不呼叫模型

**上限90分鐘、0API requests，不做內容修正或自製parser／renderer。** 只在research目錄實作最小探針。現有S0 runtime缺`beautifulsoup4`，故先處理官方HTML所需最小依賴並保存鎖定版本／前後清單；不升級既有Docling／Core／Torch。若有衝突，隔離新research runtime或停止並記成本，不把套件缺件算模型失敗。

使用與論文數字無關的合成正負控制，一次檢查：

- 普通表的原始左欄標題，以及兩個獨立列維度能否保留。
- 多層表頭、相同metric出現在不同父表頭、rowspan／colspan，是否仍能明確綁定。
- 真正空白cell、來源缺值標記、零值／小數精度，是否有區別。
- 同一physical cell內的成對測量值、各自角色與共同cell身分，是否保留；不把它強拆成無來源關係的數字。
- `<s>`／`&`等literal的正確escaping與未escape反例；不容許內容被當tag吞掉後仍宣稱通過。
- 非法span、未知／重複／漏target、不完整表格回應，是否被拒絕或明列失敗；不能把官方parser的clamp／寬容修補當作來源保真。

必須走實際公開HTML入口、typed JSON保存／reload、stock Markdown及來源重綁。檢查的是內容／header關係，不要求Markdown重現PDF視覺排版：複雜span在JSON保留，主要Markdown至少要能解讀完整列／欄條件，精細結構可透過同版table key取得。不能把全部內容只藏在HTML artifact而宣稱主要Markdown通過。

**Gate：**若需要改private HTML backend、發明通用tree repair、事後補表頭／數值，或另寫Markdown renderer才能交付，就在這裡停止；保存具體失敗與最小新增維護成本，這輪不送模型。HTML convert成功本身不構成gate通過。

## B：同一配置，一次驗四種單頁表格

A通過後，固定一份通用prompt／schema與程式hash再推論。保留target-key JSON外殼及caption／conditions，將自訂flat rows改成表格HTML；HTML直接表示可見headers／cells／spans，不列出論文名稱或預期答案。

| 固定DEV案例 | 來源頁 | 問題 | Frozen數值點／關鍵比較 |
|---|---:|---|---:|
| G1-T01 Memory-R1 Table2 | p8 | 普通表保護、左欄header | 6／3 |
| G1-T02 SkillOpt Table2 | p8 | 六panel、重複setting、共同caption | 84／8 |
| G1-T04 paper09 Table6 | p17 | 三層表頭、旋轉row stubs、三個列維度 | 300／5 |
| G1-T05 Wiki Table4 | p13 | 合併表頭、row groups、同cell成對值 | 80／7 |

合計**4頁、4個frozen logical tables、470個數值綁定、23個關鍵比較**。這是開發覆蓋，不是獨立validation；不挑成功的panel或rows。SkillOpt同頁Table3與其他頁的全部native table targets也屬附帶工作，必須保存、評讀，但不加入470分母。

**主幹與模型維持不變：** StandardPdfPipeline2.132／Core2.99、PyPdfium、Heron、RapidOCR v6 det／rec-small＋v2 cls、TableFormer V1 accurate；code／formula／picture enrichment關閉。VLM仍為暫用gpt-6-luna，整頁144dpi、detail high、reasoning low、JSON object、max_completion_tokens8192、store false、concurrency1、retry0、每request180秒。輸出格式是本輪唯一主要方法變更，不做模型／prompt grid search，不手裁或旋轉特定table來追分。

**最多4次API requests，每頁一次；一組完整配置。** 輸出cap同前輪，不因截斷重試或加大預算。推論前清點4頁全部native targets，預算上限12個；若被切成太多碎片或缺整張表，記inventory缺陷，不人工合併gold boxes。整個新S0準備＋API／mapping／export上限45分鐘，sampled process-tree RSS12GiB、available至少8GiB；每個新單頁S0 conversion另設180秒界線。

Memory-R1及SkillOpt兩頁有已登錄的同版S0 baseline，可重用並核hash；T04、T05需新增兩個同設定S0頁面，不能說全cached或全fresh。兩個舊頁亦作前輪JSON方法的回歸比較，不需要重呼叫舊方法。model-free的完整request建構檢查、來源圖可讀性與hash、全部targets、模型／套件／parser身分都須在送出前完成。

原數值門檻維持每表分開：T01零錯；T02最多4/84、T04最多15/300、T05最多4/80，且各表所有critical comparisons均須成立。header／condition／note及成對值角色關係獨立檢查，不能用總數值正確率抵銷。既有正例新增漏字、改值、錯掛或正文重複阻止採用；不得在看結果後改oracle、補字或挑內容fallback成通過。

producer只讀固定source image、native inventory、協定，不能讀oracle。推論前僅使用獨立metadata清單挑頁／登錄，不再列印整份cases內容；source evaluator在所有固定推論完成後才讀gold。逐項評provider raw→官方parser→typed／Markdown，區分模型錯、parser損失、結構未承載、runtime失敗與未執行。兩個舊DEV頁不能提供盲測或泛化證據。

## 本輪邊界與完成條件

**不納入G1-T03跨三頁的Table13（p27–29）。** 五張G1表總共七頁；目前inventory拒絕多頁provenance，逐頁API也沒有logical table continuation協定。它需要另一個明確的跨頁表示／來源綁定gate，不默默擴成本輪的自訂續接工程。未驗T03就不能宣稱所有G1表格或完整table能力合格。

- A失敗：停止模型投入，帶官方parser／stock Markdown的具體限制與維護代價回來。
- B數值或來源關係失敗：保留固定結果，不靠內容修補或下一組prompt追同一份資料；不升級單頁table配置。
- A、B通過且舊正例不退步：鎖定這個單頁table研究配置，結束本地兩頁微調循環；後續才安排跨頁T03與公司具名Qwen3-VL的同協定驗證。

不測公司GPU／vLLM、高頻吞吐，不開holdout／Paddle。來源精細panel／cell定位仍未由table HTML產生，不能捏造；code／inline公式與圖片supplement仍是獨立必要缺口。此輪最多只能收斂**單頁表格方法**，不能由它推論完整Canonical Acceptance。
