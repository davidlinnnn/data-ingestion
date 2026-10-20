# Docling Usage 全覽與第一個 PDF core delivery 功能決策清單

[Research index](README.md) · [第一版逐項決策票 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

日期：2026-10-13（Asia/Taipei）。**狀態：功能盤點與待決策清單；未採納新功能、版本、模型、Canonical schema 或 pilot 範圍。** 使用者要求先完整列功能，再逐項決定第一個 PDF core delivery 要包含哪些。這份文件補齊官方 Usage 的閱讀範圍，對照既有 survey；每項納入決定仍待確認，不能把舊版的 retain/defer 結論直接當成這次的答案。

## 1. 閱讀範圍與版本邊界

從使用者提供的 [Model catalog][catalog] 實際導覽列辨識出 **15 個 Usage 頁面**，已讀完每頁正文、表格、程式範例與限制，沒有無法讀取的頁面。API server landing 也計入，而非只讀三個子頁。下表的「內容」是閱讀索引，後面的矩陣才是功能與輸出的判讀。

| # | 已讀官方頁面 | 正文涵蓋範圍 |
|---|---|---|
| U01 | [Advanced options][advanced] | 模型預抓／離線、remote opt-in 與各 API 類型、影像尺度、table matching／mode、reading-order separators、NativePdfPipeline、heading recovery、PPTX charts、iWork、JSON image reimport、HTML image fetching、檔案／頁數限制、binary stream、progress callbacks、CPU threads |
| U02 | [Supported formats][formats] | 全部一般與 schema-specific 輸入格式、PowerPoint OMML equations、全部輸出格式 |
| U03 | [Audio & video][audio] | 安裝／FFmpeg、ASR、timestamp 輸出、RAG 範例、video frames／diarization／timeout、Whisper backend 與各 preset、限制 |
| U04 | [Enrichment features][enrichments] | code、formula、picture classification／description、formula crop／repetition、local／API、usage metadata、custom enrichment 入口 |
| U05 | [PDF heading levels][headings] | bookmarks／numbering／style 優先序、backend 差異、OCR 限制、relative levels、全部 options、serve 設定、對既有 document 套用 |
| U06 | [Vision models][vision] | VLM conversion、chart enrichment、local／remote engines、模型比較、dots formatting、MinerU／dots captions、Chandra rich HTML／bbox／錯誤行為 |
| U07 | [Model catalog][catalog] | 所有 stage／model family／preset／engine／device 表、範例與未完成項目 |
| U08 | [GPU support][gpu] | standard batching、OCR GPU、VLM server concurrency、hardware／benchmark 範圍 |
| U09 | [MCP server][mcp] | local conversion、remote serve、explicit local fallback、agent/framework 入口 |
| U10 | [Agent skills][skills] | bundled usage skill、安裝／discover／manual registration、CLI／SDK／extraction／RAG／service／slim references |
| U11 | [Jobkit][jobkit] | local／Kubeflow／Ray jobs、conversion options、HTTP／S3／Drive／GCS source-target、credentials 路徑 |
| U12 | [API server][serve] | SDK／serve／Jobkit／MCP 分工、HTTP／async 基本使用與 engine 概念 |
| U13 | [Deployment][deployment] | CLI／Compose、設定優先序、subprocess、Local／RQ／KFP／Ray、GPU、UI cache、Kubernetes／sticky sessions／model cache 入口 |
| U14 | [REST API][rest] | sync／async convert、file／URL／base64、poll／WebSocket／result、auth、Python client、options、response/status、picture config 遷移 |
| U15 | [Managed service][managed] | 代管方式、API 相容主張、IBM watsonx 服務入口 |

「Usage 全部」指這 15 頁；不宣稱遞迴讀完所有連出的 Examples、Reference、model cards、GitHub repository 或整個網站。為釐清 canonical output 另讀 [DoclingDocument][document] 與 [Confidence scores][confidence]；與舊調查互相印證之處保留既有 tagged-source 證據。

版本證據分三層：

- **已發佈 PDF baseline**：#70 調查與 [fe1b283 profile][profile] 的 Docling `2.102.0`／Core `2.96.0`。這是歷史已發佈實作身份，不宣稱目前本地 checkout 等於該 commit。
- **舊 survey 的另一比較版本**：Docling `2.132.0`／Core `2.99.0`。其當時 latest-stable 觀察不能當成今天的 latest，也不代表已升級。
- **這次 moving-doc 觀察**：2026-10-13 官網正文。未逐項證明新增文字的 first-release；標為「需選版驗證」的能力不保證 pinned baseline 可用。API server／Deployment／REST 三頁還明載從 **docling-serve v1.21.0** 同步，與 #70 曾檢查的 serve `v1.36.0` 不能混用。這次沒有選定新版套件。

## 2. PDF 與 canonical output 功能矩陣

以下把「可表示」、「會產生」、「baseline 有開」、「品質已驗證」分開；有 schema 欄位或 CLI flag 不等於處理結果已適合 Canonical Acceptance。baseline 欄取自 [#70 survey][previous]、[published profile][profile] 與 [2026-10-12 handoff][handoff]，不是本次重新執行 inference 的結果。

R01–R20 是本研究的分類編號；決策票另以 F01–F22 拆分，逐項決定以決策票為準。所有 R 項均 **待逐項決定**。採納時選擇：**必要輸出**、**有條件必要**（明定條件）、**非阻塞附加輸出**（失敗仍有明確 outcome）、或 **本次不提供**。同一列可拆成不同層級；例如「保留表格影像」和「可拿數值作跨文比較」不能以一個 checkbox 合併。

| ID／能力 | Docling 可產生／保留的輸出 | published baseline／舊證據 | 本次需決定的交付語意與限制 |
|---|---|---|---|
| R01 原生文字、段落、標題、列表、閱讀順序 | typed items、body/groups 與 parent/child refs；body tree 的順序表示 reading order。[Document][document] | 已使用 standard PDF layout＋native text，含本 repo continuation/order method | 必須涵蓋哪些文字／list nesting／多欄順序；缺字、重複、錯序的可接受範圍。不要把新的 `NativePdfPipeline` 視為既有 selected-native-v1 的同名替代 |
| R02 頁首頁尾、footnote、caption、bibliography 等原始內容與關聯 | label／content layer／refs；原始 caption 與 generated description 不同。[Document][document]、[舊能力證據][previous] | 有界 fixtures 保留部分 graph／caption 關係；不代表全部來源皆完整 | 哪些項目及原始關聯必要；未可靠連結時保留 standalone／unknown，不能猜成引用解析或作者 metadata |
| R03 Heading 層級 | `SectionHeaderItem.level`；bookmark → numbering → style，逐 heading 決定；不需額外模型。[Heading levels][headings] | `2.102.0` 無該 hierarchy stage；舊觀察輸出皆 level 1 | 是否需要可靠 section path。style 需 retained parsed cells；OCR 無 font weight/slant；無訊號不會補出正確層級。對既有 document 可只跑 numbering，並非必須重跑全部 layout |
| R04 整頁／scan OCR | page text／位置；Auto、Tesseract、EasyOCR、RapidOCR、macOS Vision、Surya 等選擇。[Catalog][catalog] | native profile 關閉 page OCR；不同於 R05 | 是否包含 scanned／混合 PDF、語言、旋轉／低品質掃描；選 engine、語言與 full-page 行為後才有可驗收的契約 |
| R05 圖內文字 OCR | 來源 picture crop 的文字、boxes、scores、no-text／failure outcome | repo 已獨立要求每個 emitted PictureItem 的 RapidOCR；此為 repo operation，不是官方 picture-description flag。[Profile][profile]、[handoff][handoff] | 是否保留目前範圍、擴及漏偵測圖／其他區域；OCR 完成不等於 diagram 理解，也不能以未產生 PictureItem 宣告來源沒有圖 |
| R06 表格結構與 cell 內容 | rows／columns／cells／spans；TableFormer fast/accurate、matching；另有 Granite table method。[Catalog][catalog]、[advanced][advanced] | pinned TableFormer V1 ACCURATE＋matching 有輸出；#72 對 general table-dependent 分析保留 uninterpreted | 分開選「保存觀察」與「可比較數據」。後者須檢查 header→value、model／metric／condition、units、notes、spans、跨頁續表；參數或模型名稱不提供正確性保證 |
| R07 圖片、頁影像、表格 crop | pixels 與 page／region ref；有 page image 時可依表／圖 provenance crop。[舊 source audit][previous] | page／picture images 已開；獨立 table artifact 尚非既定承諾 | 需哪些可檢視 artifact、解析度、座標原點與保留關係；不要只存會過期的 URL，或把 crop 可生成等同已持久保存 |
| R08 圖片分類 | `meta.classification` 類別／分數，例如圖表、diagram、照片。[Enrichments][enrichments] | pinned 已有，profile 關閉 | 分類僅供顯示還是決定後續工作；誤分類及未處理項目需可見，不能因分類器漏判就省略必要輸出 |
| R09 圖片描述／視覺理解 | VLM generated description；local 或 API；來源 caption 另留。[Enrichments][enrichments] | pinned 已有 local/API，profile 關閉；#70 並未證明其為最高價值功能 | 是否要求內容摘要、diagram 關係或其他指定語意；模型描述須保留 producer／prompt／source crop／uncertainty，不自動升格為來源事實 |
| R10 Chart 數據 | chart classification＋結構化 chart data；當前 VLM pipeline 可另做 chart enrichment。[Vision][vision]、[舊 tagged audit][previous] | pinned 有 local chart model，但關閉；新版 API／engine seam 與 pinned 不同 | 要數值／系列／axes／單位，還是只描述外觀；分類、資料解析、數值正確性是不同失敗點，需具體 source oracle |
| R11 Code／pseudocode | code item 的原始觀察；optional enrichment 重建文字並標註 `code_language`。[Enrichments][enrichments]、[舊 audit][previous] | enrichment 關閉；原生 code label／text 仍可能存在 | 選保留原樣、可讀重建或更強語意需求；enrichment 不保證 executable patch／演算法等價，重建不能覆蓋唯一原始證據 |
| R12 Formula | 原始 formula item／crop；optional LaTeX reconstruction，可供 HTML 顯示。[Enrichments][enrichments] | pinned 已有但關閉；label 存在不等於精確公式 | 是否要求符號、上下標、矩陣、編號與 LaTeX fidelity；crop margin／generation repetition 會影響結果，不能把產生 LaTeX 當成數學等價驗證 |
| R13 表單、field、key-value、rich cells | Core 有相關集合；特定 VLM 路徑也可產生 checkbox／radio／fillable value、rich table content。[舊 Core audit][previous]、[Vision][vision] | 舊 retained fixtures 的 form/key-value 集合空，field collections 的 comparator 覆蓋不足 | 要保存 populated 原始結構，還是保證 PDF 自動辨識；兩者不同。Chandra 不會只憑視覺距離推論 key-value 關係 |
| R14 Schema-driven facts／metadata | `DocumentExtractor` 依要求的 template/schema 取得欄位；是 extraction 路徑，不等於普通 converter。[Agent skill index][skills]、[舊 tagged audit][previous] | pinned 已有 extractor；未選入 PDF profile | 若要 author/title/reference resolution／指定研究事實，需逐欄定義與 source attribution；schema 存在、valid JSON 或 bibliography text 都不證明事實正確 |
| R15 Alternative whole-page VLM conversion | rendered page → DocTags／Markdown／HTML 等 → DoclingDocument。[Vision][vision] | pinned 有 VLM pipeline；未採用為 selected parser | 這是方法選擇，可影響 R01–R14；需自己的 method identity／baseline／recovery，不能當成開啟所有 optional features 的總開關 |
| R16 細粒度來源定位與處理身份 | document/item provenance、可用 bbox／page／graph refs；repo 可另綁 Source Revision、artifact digest、method/model/options。[Document][document]、[handoff][handoff] | 已有有界證據；並非完整 canonical schema | 下游引用要精確到 page、block、cell 或更細；模型未提供 word/cell 座標時不能偽造。每個衍生輸出須能回到支持它的 evidence |
| R17 信心、錯誤、partial／unsupported outcomes | ConversionResult confidence／errors／status；各頁及整份 grades。[Confidence][confidence]、[REST][rest] | 舊調查保留 quality/canonical acceptance 未通過的界線 | 所需欄位與失敗 disposition；`table_score` 官網仍明載未實作，不能拿來替代 table gate；producer confidence 不是來源真實性或 Canonical Acceptance |
| R18 原始結構化結果與人讀輸出 | JSON 為 DoclingDocument 的 lossless serialization；另有 Markdown／HTML／text／DocTags／DocLang／dclx／WebVTT／LaTeX／chunks JSONL。[Formats][formats] | baseline 寫 JSON／Markdown；非所有 exporter 都已整合 | 決定 handoff 的必要 artifacts 與 authoritative representation；JSON lossless 指 DoclingDocument，不是 source PDF 無遺漏；LaTeX export 圖片為 placeholder |
| R19 Chunking／Retrieval-ready 輸出 | chunked JSONL 可選 chunker/tokenizer/limit；hierarchical、hybrid、line-based 等既有 Core 能力。[Formats][formats]、[舊 audit][previous] | 未成為 PDF canonical processing 必要 stage | 是否作附加出口，或交給 Materialization；不要把特定 consumer 的 token chunk schema 默認成 Canonical Knowledge |
| R20 模型特有 rich output 與未知欄位保留 | dots emphasis／inline groups、MinerU captions、Chandra links／math／rich cells／explicit molecule metadata 等路徑限定能力。[Vision][vision] | 不保證 pinned package、baseline adapter 或所有 export 皆支持 | 哪些真實語意要採納，哪些只保留 provider raw artifact；圖內 child content 不一定出現在預設 Markdown，無法可靠 linked 的 caption 必須保持未連結 |

### 模型選擇的證據不能替代 output 選擇

當前 [Model catalog][catalog] 的 family 涵蓋 layout（Heron／Egret）、OCR、TableFormer／Granite table、picture classifier、VLM convert、picture description、code/formula。catalog 也標出 object-detection table method 尚在開發，layout-v2 已 legacy；TableFormer 的 MPS 被停用。`AUTO_INLINE`／Transformers／MLX／API／vLLM 的可用性依模型及平台而不同。

這些名稱是實作候選，不是第一版必須逐個採納的功能。尤其 MinerU preset 沒有自動啟用 image/chart analysis 或跨頁 table merge；新的模型輸出不能假定與 native checkpoint、caption 關係或座標精度相同。[Catalog][catalog] [Vision][vision]

## 3. Usage 內其餘功能：也列出，但分清交付層

下列能力已閱讀，不能因為不在 PDF inference matrix 就視為漏掉。其是否屬於 pilot delivery 同樣待決定；使用不同格式、deployment 或 API 並不自動增加 canonical 內容功能。

| ID／類別 | 完整範圍摘要 | 對第一個 PDF delivery 的決策意義／限制 |
|---|---|---|
| X01 非 PDF 輸入 | Office OOXML、legacy Office／RTF、ODF、EPUB、Pages／Numbers／Keynote、Markdown／AsciiDoc／LaTeX、HTML／XHTML／MHTML、CSV、images、audio/video／WebVTT、BoxNote、email、AFP；DocLang XML／archive、USPTO／JATS／XBRL、EBCDIC、Docling JSON。[Formats][formats] | 格式清單不是格式品質保證；legacy Office/RTF 需 LibreOffice，iWork 需 extra，EBCDIC 要 record layout。可明定本次 PDF-only，而不是宣稱全格式已交付 |
| X02 Audio／video | Whisper transcription、segment timestamps；video frame sampling 與 optional diarization；native／MLX／experimental S2T。[Audio][audio] | 須 FFmpeg／extras；無 word timestamps／SRT，audio-only ASR 無 diarization。video 逾時可回 partial result；可選 native/cloud-independent backend 不等於已具我們的 evidence contract |
| X03 Office／iWork 原生語意 | PPTX／Keynote／Numbers 原生 chart data、caption；PPTX OMML→LaTeX；iWork notes／furniture／sheet selection／rich cells 與限制。[Advanced][advanced] [Formats][formats] | 原生 chart data 不等於 PDF chart inference；rendering 有額外依賴與樣式損失，不得把另一格式能力算成 PDF 已有能力 |
| O01 模型與執行設定 | prefetch／offline artifact path、remote opt-in、image scale、byte/page 限制、streams、threads。[Advanced][advanced] | 逐項選出的功能需綁 package/model/config identity 與 resource envelope；允許拉 weights 和允許傳送 source data 是不同控制 |
| O02 進度與完成狀態 | document／phase／page／enrichment callbacks；頁可亂序完成，page 100% 後仍可能有 enrichment。[Advanced][advanced] | 對外完成狀態需等必要工作與 durable results，不可只看 page bar；callback 也不是 durable checkpoint |
| O03 GPU／batching／serving | standard 每 stage batching、OCR backend GPU、VLM endpoint concurrency。[GPU][gpu] | 文件量測有固定硬體／資料條件，不能搬成我們的 pilot throughput；換 CPU/GPU 或遠端 engine 不直接證明 output 等價 |
| O04 Reimport／image references | Docling JSON reimport 預設忽略 local-file image refs；trusted SDK 可 explicit local fetch，CLI 無該選項。HTML remote images 另有 explicit fetch 與 address/redirect 邊界。[Advanced][advanced] | 若選 export→reload 作 handoff，要測 pixels／size／refs 是否仍在；不要只測 JSON 可 parse |
| O05 MCP | agent tools 可 local convert 或委派 serve；local fallback 必須明開。[MCP][mcp] | 是消費／操作入口；不會自動使 PDF 功能變成 canonical output，也不能把 fallback 默認成同一 producer |
| O06 Agent skills | package 內 usage skill 教 CLI、SDK、extraction、RAG、service、slim 安裝；可 symlink 隨 package 更新。[Skills][skills] | 是開發者使用輔助，不是新增的文檔推論輸出；本次未安裝或執行其 instructions |
| O07 Jobkit | local／Kubeflow／Ray job execution；HTTP、S3、Drive、GCS import/export。[Jobkit][jobkit] | 是批次執行與連接器；不等於 repo 的 Source capture、Temporal recovery、Canonical Acceptance 已有相同契約 |
| O08 API server／REST | Python client／HTTP；URL/base64/file；sync/async、poll/WebSocket/result；選格式、OCR/table/pipeline/enrichments；JSON 或 ZIP。[API][serve] [REST][rest] | 可以選服務界面，不必隨之換掉品質／recovery 契約。task success、conversion partial_success、processing completion、Canonical Acceptance 需分開 |
| O09 Deployment | Local、RQ、KFP／Ray；CLI／Compose／Kubernetes examples；API key、models cache、GPU、worker 設定。[Deployment][deployment] | 部署範例不是持久性驗證；部分 replicas 要 sticky sessions，demo UI artifacts 約 10 小時清除，RQ 需要實際 worker。不保證既有 checkpoint 可移植 |
| O10 Managed service | IBM watsonx 代管 endpoint，文檔主張與 self-hosted REST 相容。[Managed][managed] | 是營運選項；沒有測 provider version／limits／retention／實際結果，不因此選定 SaaS 或改變資料去向 |

## 4. 與之前 survey 的差異

| 比較面 | 之前實際涵蓋 | 本次補充／應改正的理解 |
|---|---|---|
| 2026-09-11 [canonical-processing note][initial] | PDF／Markdown／PPTX、DoclingDocument、table/headings/enrichments、Kubernetes/serve，建議可替換 adapter | 原本就不是只有 PDF 五個開關；仍是研究與擬議評估，並非 canonical adoption |
| 2026-10-02/03 [#70 note][previous] | pinned/latest capability、enabled/retained/qualified、stage remote seams／memory/protocol、canonical handoff、retained-output probes、治理／成本／跨格式使用情境 | 已相當廣泛，但不是逐頁 Usage exhaustive-read。大量缺口本來已記錄，不應因這次重讀就說成「以前完全沒 survey」 |
| 幾乎所有 PDF 功能 | #70 已包含 native order、tables、images、page vs picture OCR、classification/description/chart、code/formula、heading、VLM、schema extraction、unknown fields、confidence/export/chunking | 本次主要把可供決策的輸出粒度拆開，**不沿用 #70 的 retain/defer ranking 當作使用者新選擇** |
| 現行 Usage 廣度 | 舊 note 對 ecosystem/non-PDF 多是摘要 | 補齊 15 頁 read inventory；尤其 agent skills、Jobkit connectors、managed service、video frames/diarization、JSON reimport、native no-model pipeline、progress、model-specific rich output |
| 細節與限制 | 舊 heading/picture API／chart source audit 已辨識版本差異 | 現行 docs 可補充 heading 對既有 document 使用、formula repetition/crop、VLM native-caption/bbox 限制；這些不是都證實為 pinned 可用，也未一律證明在舊 survey 之後才新增 |
| 文件中的不一致 | 舊報告已提醒 moving docs | enrichments 主表只列四種，但 Vision／REST 有 chart；formats 的 video 摘要偏重 audio，Audio & video 正文還有 frames/diarization；模型列表／示例／API docs 未必同步同版。需用採納版本的 source/schema 收斂，不能取聯集就宣稱單一版本全部支持 |
| 現行第一版範圍 | [#72 handoff][handoff] 採用 restricted mechanism-comparison／body-explicit results；general table-dependent analysis 與 universal enrichments 不在第一版 | 這是正在被使用者要求重新檢視的決策背景，不是本次新清單的預選答案；新 confirmation 前保留原紀錄及 #80–#83 的來源關係 |

## 5. 逐項確認後應產生的 delivery target

建議決策票以這份完整 catalog 為附件，逐項填 R01–R20；X/O 項另外確認是否影響同一 delivery。**所有新增／變更仍待確認，沒有預設必須全部啟用或必須維持縮小範圍。** 每項被選功能要有以下一筆完整紀錄：

| 決策欄位 | 應記錄什麼 |
|---|---|
| 支援用途與輸入 | 哪個 pilot 任務需要；native／scan／mixed PDF、語言、頁數／資料限制 |
| 輸出承諾 | 明確 item/field/artifact/關聯；原始 observation、derived reconstruction、interpretation 分開 |
| 必要程度 | 必要／有條件必要／非阻塞附加／本次不提供；條件寫成可判定規則 |
| 失敗 disposition | failed、not-attempted、unsupported、no-content 等不同結果；必要能力缺失如何影響完整 candidate |
| 驗收證據 | source-reviewed oracle、正例／失敗或不支援案例、graph/lineage、fresh/reuse/recovery 保留；不能只驗 JSON 欄位存在 |
| Method 與交付影響 | 選版／model／config、是否改 checkpoint、新 artifact／mapper／consumer／resource qualification；確認後再改 #80–#83 或另開必要實作票 |

這是決策格式建議，不是新增一套框架。先確定「第一個 delivery 必須產生什麼可重用結果」，再選最小實作方法；保留完整候選的 Canonical Acceptance 與 Source Evidence 要求。[CONTEXT](../../CONTEXT.md) [既有 handoff][handoff]

## 6. 未做與證據風險

本次沒有跑模型、重做 corpus benchmark、驗證新服務 endpoint、安裝套件、升級 profile、修改 ADR／既有結論或作交付採納。沒有把過去有界 fixture 的通過外推到全部 20 篇或所有 PDF。研究 note 與 Usage 的完整閱讀，不能替代選定功能之後的版本確認、adapter preservation、source fidelity 及 pilot end-to-end 驗收。

[advanced]: https://docling-project.github.io/docling/usage/advanced_options/
[formats]: https://docling-project.github.io/docling/usage/supported_formats/
[audio]: https://docling-project.github.io/docling/usage/processing_audio_media/
[enrichments]: https://docling-project.github.io/docling/usage/enrichments/
[headings]: https://docling-project.github.io/docling/usage/heading_levels/
[vision]: https://docling-project.github.io/docling/usage/vision_models/
[catalog]: https://docling-project.github.io/docling/usage/model_catalog/
[gpu]: https://docling-project.github.io/docling/usage/gpu/
[mcp]: https://docling-project.github.io/docling/usage/mcp/
[skills]: https://docling-project.github.io/docling/usage/agent_skills/
[jobkit]: https://docling-project.github.io/docling/usage/jobkit/
[serve]: https://docling-project.github.io/docling/usage/api_server/
[deployment]: https://docling-project.github.io/docling/usage/api_server/deployment/
[rest]: https://docling-project.github.io/docling/usage/api_server/rest_api/
[managed]: https://docling-project.github.io/docling/usage/api_server/managed/
[document]: https://docling-project.github.io/docling/concepts/docling_document/
[confidence]: https://docling-project.github.io/docling/concepts/confidence_scores/
[initial]: docling-canonical-processing.md
[previous]: docling-capabilities-vs-pdf-core-2026-10-02.md
[profile]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/profiles/selected-native-v1.json
[handoff]: ../handoffs/paper-pdf-profile-2026-10-12/decision.md
