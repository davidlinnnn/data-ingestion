# PDF-core：準度、延遲與算力的配置取捨

**目前狀態入口（2026-10-20）：**查詢 component 已測／未測範圍、回歸、終局或下一動作，先讀[#84 最新狀態與決策矩陣](pdf-core-issue84-final-decision-2026-10-18.md#目前-component-狀態2026-10-20)。本文件保留 2026-10-17 的配置盤點與事前方案；下文「本輪」「目前」「最新」均指該日期，不是新的推論授權或目前能力結論。後來結果只在狀態入口彙整，不在此複製當前矩陣。

2026-10-17。使用者確認目標為 **Standard 主流程＋必要元件的 VLM 增強**，以完整必要功能、可接受 minor 誤差及增量成本共同選型。這份文件整合 F01–F22 證據，取代只追單一表格分數的下一步安排；沒有宣布正式 Processing Profile 或 G2 合格，也不回寫歷史實驗結果。

本輪已確認：一般 OCR 字形／排版小錯可接受；複雜表每張最多 5% 數值錯誤，全部關鍵比較與必要表頭／條件歸屬仍須正確；公式／code 允許等義表示，重大漏文、運算或識別字改義仍不接受。這些是有來源答案的驗證判準，不能冒充 ingest 時的自動語意正確判斷。新高頻場景的典型頁數、單份完成時間、常態／尖峰量尚未定，先量測相對 Standard 的增加成本，再提產品預算；180 秒研究 timeout 不是 SLO。

既有 pilot 目標保留：任意10分鐘最多5份、24小時最多10份，持久受理後10分鐘內可搜尋；初批20份1小時內可搜尋，Wiki另依24小時目標。這些未被「新高頻SLO尚未定」取消，亦未由本輪table API比較完成驗證。

**本輪已完成：** F01–F22盤點、caption零模型控制，以及[四頁六張表crop實測](pdf-core-table-crops-results-2026-10-17.md)。不採用本輪crop＋完整座標JSON配置：輸入tokens少42.1%，輸出tokens多52.1%，串行請求時間117.13→210.78秒；T04 raw數值295/300、無遺漏但結構重疊，T01普通表退化，T05完整交付通過。這是有界方法取捨，沒有完整合格profile。

## 建議主幹及方案去留

| 方案 | 優點／實際證據 | 代價或問題 | 本次取捨 |
|---|---|---|---|
| Standard：Heron＋RapidOCR＋TableFormer V1 | 專用模型可本機 CPU 執行；原生 assembly 已成功續接四個真實跨頁段落並保存兩頁來源 | 多欄掃描順序、複雜表關係、行內公式／code 及完整圖片 supplement 未解 | 保留為同版比較主幹，不把 enrichment off 當完整配置 |
| Standard 改 Egret／TableFormer V2 | 有局部分類或文字恢復 | 未使必要任務整體通過，另有分類／輸出退化；Egret runtime cache 不同，不能排名速度 | 不取代目前主幹 |
| 原生 CodeFormulaV2 | 可以恢復部分公式結構與 code 縮排 | 實測 identifier／operator／literal 改字、鄰近標題混入；不處理普通段落中的全部 inline 內容 | 不全域啟用，也不依已知答案只開成功案例 |
| 每頁 VlmPipeline：Granite-Docling／dots.ocr／Nemotron | 可同時觀察文字、數學及版面；本機 MLX GPU 已能實跑部分模型 | 各已測配置仍有原始內容或 parser／定位／交付缺陷，逐頁生成成本明顯 | 保留歷史比較，不作預設主流程；沒有否決模型整個家族 |
| Generic API＋DocTags | 接 API 與官方 parser 的路徑明確 | low／medium 已測，增加 reasoning 未解必要缺口且有回歸 | 不重新調 reasoning 追同一組來源 |
| VLM HTML table→官方 importer | 可以使用既有 backend | row group 變全域 header、literal rendering 缺陷在零模型 gate 已重現 | 本配置停止；不另造 HTML 修復框架 |
| VLM 完整 cells→公開 Core＋serializer | 前輪T01/T02完整表示成功；新crop T04讀值295/300且無遺漏；T05交付通過 | 新crop仍座標重疊／越界，普通表回歸，生成量與本次延遲增加；caption重複已用ownership控制避免 | 保留公開接合；停止目前每格完整座標JSON配置的追加推論 |
| 圖片／chart 的 task-specific VLM | 兩張真實圖意與四張受控 chart 有正面內容證據 | 實際 chart 分布、圖片 inventory、同版 typed supplement／image keys 及公司模型未完整驗 | 優先保留為 component VLM 候選，分類不作豁免必要工作的依據 |

證據：[原生比較](pdf-core-native-round-results-2026-10-17.md)、[CodeFormula](pdf-core-standard-enrichment-results-2026-10-17.md)、[Direct cells](pdf-core-direct-cell-results-2026-10-17.md)、[圖片](pdf-core-g2-images-2026-10-14.md)、[HTML gate](pdf-core-table-html-results-2026-10-17.md)、[官方 API 比較](pdf-core-g2-method-selection-decision-2026-10-15.md)、[retro 範圍校正](../reviews/pdf-core-retro-closure-2026-10-16.md)。

研究主幹固定 Docling-slim2.132.0／Core2.99.0／PyPdfium；Heron `8f39ad3c…` CPU FP32、compile off、threshold0.3；RapidOCR PP-OCRv6 det_small／rec_small＋mobile_v2 cls，selective OCR、bitmap threshold0.05、text score0.5；TableFormer V1 accurate、cell matching=True；CPU4／interop1、batches1。已完成相容的80套件 runtime；不沿用舊草案的「環境尚缺套件」。144dpi 是保存頁圖與本次 table API 圖片，不能當每個 native stage 的真實輸入尺度。

Heading 官方規則、DocumentFigureClassifier-v2.5 與四方向校正可保留為小成本候選，但需要同版完整整合與來源回歸。官方 enrichment 確實按 CodeItem、FORMULA、PictureItem 執行，不能據此承諾普通段落中的所有公式／code 已被發現。[官方 enrichment](https://docling-project.github.io/docling/usage/enrichments/)。這個查核不把滾動文件新增的 tuning options 當成 pinned 2.132 已驗能力。

## 全部需求盤點

「局部可用」表示指定來源／stage 有正面證據，不表示整份功能完成。F15/F16/F22 延後，F10 可選且偏好啟用，其餘18項必含。

| ID | 功能／目前路徑 | 最新證據與剩餘缺口 | 處置 |
|---|---|---|---|
| F01 | 全文文字／Standard native＋selective OCR | 曾完成75頁 baseline 與有限來源評讀；仍有掃描漏句／錯序 | 局部可用，全文回歸仍需做 |
| F02 | 版面、順序／Heron＋原生 assembly | 四個跨頁段落已通過；多欄 scan interleaving、SEAL title/body 歸屬仍錯 | 保留原生 assembly，順序缺口未解 |
| F03 | 章節／官方 heading recovery | 舊 checkpoint stage replay：9正文＋4書籤附錄正確；無 outline 附錄、title 角色失敗 | 同版 PyPdfium＋必要 inputs／語意 parent 尚待整合 |
| F04 | 表格結構／V1 baseline＋component VLM | 前輪T04大量遺漏；本輪crop讀值改善但30行dimension重疊，普通表也退化；T03跨頁尚未由此路徑驗 | crop配置不晉升，不增加個案repair |
| F05 | 表格比較語意 | 前輪T01/T02/T05共18個比較成立；本輪T02關係8/8、T04 raw算術5/5，但不能當完整結構交付 | 每表判斷；不額外要求全部critical端點零錯，也不平均掉結構失敗 |
| F06 | 頁／圖／表來源影像 | 有實際 render、bbox crops 及 artifact 保存；完整 inventory、多 fragment 與恢復未驗 | G3 仍需完整同版交付 |
| F07 | 原文 caption | linked refs可保留；T05重複已經離線控制及新crop實際交付避免，來源缺漏仍未解 | 保留baseline ownership及standalone／未知關聯 |
| F08 | 圖內 OCR／RapidOCR | NCCU S0 有5項文字及 minor 字形差異；尚無 image-key supplement，其他控制有漏指示 | 專用 OCR 保留；工作覆蓋與交付未完成 |
| F09 | 掃描／混合 OCR | selective 保留 native；四方向＋逆映射控制成功；多欄順序仍錯 | 不用全頁 OCR 覆蓋良好 native 文字；同版方向整合待驗 |
| F10 | 圖片分類／FigureClassifier-v2.5 | 6來源12crops broad family 相符，約0.1秒/crop | 可選、偏好開；不以 top class／confidence 漏掉必含圖意或 chart |
| F11 | 圖意／crop API | 兩張真實圖片保留必要流程／UI 關係；Smol 預設失敗 | 保留 component VLM；完整圖片覆蓋、公司模型／交付待驗 |
| F12 | bar/line/pie 數據／crop API | 四張受控圖13點與關鍵關係通過；pie unit typed mapping 尚缺 | 真實 chart、漏分類及同版結構待驗 |
| F13 | 全文公式 LaTeX | CodeFormula 部分 display 成功；另有改義，普通段落 inline 不可由原生 label 保證覆蓋 | 尚無完整方法；這是全配置的核心缺口 |
| F14 | code／偽碼／inline | 部分結構恢復；literal 改字及鄰文混入；既有 context API 也未全過 | 尚無完整保真方法；不加 backticks／可執行性新門檻 |
| F15 | 表單／KV | 不新增抽取；已 emitted 內容依 F20 保留 | 延後 |
| F16 | 指定 schema 抽取 | 不新增 metadata／研究事實抽取 | 延後 |
| F17 | 基礎 metadata／明確 title | 上游值可保留；正文 title 和章節角色仍有缺口 | 不另加通用 LLM metadata 抽取 |
| F18 | lineage／來源 | 四跨頁、座標逆轉換、whole-table envelopes 有界通過 | 不造 cell bbox；完整 revisions／來源映射仍需 G3 |
| F19 | 狀態／診斷 | 前輪整頁T04 HTTP200、stop、uncertainties=[] 仍大量漏文 | required-work／失敗必須顯式；正常返回不算語意通過 |
| F20 | 完整 provider／mapping | Q39 與各輪 raw 保存有證據；完整 group diagnostics／未知欄位／fresh-restored 尚缺 | G3，不能以 raw-only 補必含語意 |
| F21 | 主要 Markdown＋同版補充結構 | 公開extension保留literals，本輪T05完整交付；其他三頁未接受，圖片key與公式/code原位仍缺 | 維持主 Markdown＋結構/supplement，不塞生成圖意進原文 |
| F22 | core chunking | 由需要的 projection 自行實作 | 延後 |

需求依據：[能力與驗證計畫](docling-pdf-core-capability-validation-plan-2026-10-14.md)。補充證據：[heading](pdf-core-g2-heading-2026-10-15.md)、[方向／OCR](pdf-core-g2-orientation-2026-10-15.md)、[context API](pdf-core-g2-context-api-2026-10-15.md)。

## 已完成的 caption 離線工作

[Ownership 報告](pdf-core-caption-ownership-2026-10-17/report.md)完成6個合成情境、1個不完整 grid 拒絕控制與 T05 保存回應重播。T05 caption 由2次變1次；原正文、表格 cells、非目標內容／reference／順序／來源均保留，70個 frozen artifacts／helpers hashes 前後一致。

最小政策是不把 provider caption 自動新增成 source caption，既有 native link／正文由 baseline 保管。Provider observation 完整保留，未知歸屬明示。沒有文字 dedup，也沒有憑相同字串猜 attachment。真正未被 baseline 擷取的 caption 仍未補回；「沒有 native link」本身不是新增的產品失敗條件。這是新研究政策，舊失敗結果保留。

## 成本比較方式

| 既有執行 | 實際量測 | 能支持的判斷 |
|---|---|---|
| S0 Standard，11頁／7ranges | worker32.03秒，初始化11.29秒；7個 conversion 合計18.67秒 | 輕量主幹的研究基線；非完整 enrichment 或 warm p95 |
| C1 Nemotron，原生11頁請求 | worker230.62秒，5/7range success | 已測整頁配置成本明顯且仍有缺口；不同工作覆蓋，不能當等品質加速比 |
| E1 CodeFormula，8頁／10regions | worker55.72秒；4ranges合計51.59秒 | 專用小模型也有生成成本且品質不全過；不以模型大小推定低延遲 |
| 完整 cell JSON，4頁6targets | 4 API calls合計117.13秒，13,707 input／18,930 completion tokens | 大量輸出本身有成本；包含 T04 失敗，不是合格完整表的預算 |
| 本輪完整body crops，同4頁6targets | 6 API calls合計210.78秒，7,934 input／28,800 completion tokens | 輸入減少、輸出與本次延遲增加；T04讀值改善但結構失敗，不能作等品質GPU加速比 |
| 圖意／chart component API | 圖意10.13–12.06秒／crop；chart4.64–7.33秒／crop | 任務與輸出長度不同；不能從6個來源推 p95 或公司 GPU 成本 |

API時間包含網路／provider queue，無法分離遠端 GPU compute。Completion tokens 包含 reasoning／其他非可見輸出；不能只數 JSON 長度。公式 `T_document = queue + critical_path(parse, enrich, serialize, persist)` 中的並行路徑要實際量測；sum(request RTT) 只代表本次串行工作量。並行可縮短完成時間，並不自動減少 total compute。

後續每個完整配置同時報：必要目標發現／送出覆蓋率、被跳過的目標、minor／material、原本正確內容回歸、實際 calls／tokens／crop pixels、cold/warm 時間、記憶體、queue與總文件延遲。0／1／多個增強目標的文件分開看；之後有足夠代表性重複與公司資源資料，才談 p50/p95、GPU seconds／文件和穩定 throughput。尚無品質合格候選，不先宣稱 Pareto 最佳點。

## 本輪唯一新推論：六張完整 native table crops

**已執行完畢，結果見[完整報告](pdf-core-table-crops-results-2026-10-17.md)。** 下列為執行前凍結的方法與界線，沒有新增下一輪名額。

前置檢查已讀四頁全部6個 native targets（1＋2＋2＋1），視覺確認各表體、表頭與表內條件在 bbox 內，不以 oracle 拆 panel／rows。所有 caption 均在 body bbox 外；5個已有 native links，WikiSkill caption 原位在 body。圖面共1,499,164 pixels，是舊四張整頁7,955,748 pixels的18.84%；requests從4增6，schema重複與完整 T04 輸出可能抵銷輸入節省。

固定方法：保留相同 S0 artifacts／144dpi、不 resize；一表一請求、所有6張都測。暫用同一 `gpt-6-luna`／high image detail／low reasoning／JSON object／max_completion_tokens65536／store false。輸出仍用完整 cell 協定；caption 固定空字串，只辨識表體可見內容／條件，外部原文由 baseline 保存。這是自訂 component adapter，不是把 generic API 原樣塞入 CodeFormula 或宣稱官方內建 table API。

上限6 calls、1個配置、concurrency1、retry0、每request180秒、live階段30分鐘、RSS12GiB／available至少8GiB。沿用原合成輸出預算，不因來源失敗加 token cap。原四頁470個數值、23個 critical comparisons 及 caption／條件／非目標內容檢查不變；附帶表格也要保留，不加入成功分母。

所有請求結束後才讀 oracle。每頁先合併全部原 target keys，再一次 mapping，避免公開 ref 重編號導致後續 target 錯置。錯誤 response／目標漏失／不完整 grid 讓該頁明確失敗；不增加輸入、重試或修值。品質仍重大漏失即停止目前 producer 的調整；若只提高品質但變慢，保留品質／成本兩個事實，不稱作速度勝出。舊 T04 生成較少內容，不能要求完整新輸出一定比它快才算有價值。

本實驗只測「table component」的選取粒度，沒有實作只挑困難表格的 confidence router。原生結構完整並不保證數值／歸屬正確，任何未來 selective trigger 必須同時驗 false negatives 與省掉的工作。普通正文 inline 公式／code 的 discovery 尚未解，不能靠不送 VLM 達成低延遲後聲稱功能全含。

## 後續決策順序

依本輪結果，停止目前每格完整座標JSON配置的追加推論，不plugin化或再換三個prompt。表格若再投入，先零模型比較較精簡、避免重複座標的通用協定與公開Core映射，再決定是否值得固定新推論；這尚未驗證，不是逐表修欄位。其餘必要方法以全文inline公式／code的可達性與圖像supplement為優先，提出具名輸入／輸出／路由方法前不盲跑模型。不同任務允許不同模型，Qwen3是公司候選，不是唯一指定解。

當有涵蓋必要工作的固定組合，再做一份真實整合輸出與配對成本回歸，之後才 lock／未曝光確認與 G3/G4。公司 Qwen3 完整 model ID／serving／GPU 未知，正式公司品質／延遲不能由 OpenAI 代替。Paddle 完整流程、GLM/LightOn 等未驗路徑保留候選身分，不因 catalog 存在就排入本輪；6份 holdout 不開封。

官方接點查核：[enrichment](https://docling-project.github.io/docling/usage/enrichments/)、[serializer extension](https://docling-project.github.io/docling/concepts/serialization/)、[pinned options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py)。API限制查核：[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)、[output token 計數](https://developers.openai.com/api/docs/guides/token-counting)。沒有以滾動文件的新功能覆蓋歷史配置或省略應驗整合。
