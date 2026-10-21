# Atlan 官方來源調查：產品、公開架構與商業化

**調查日期：2026-10-17。狀態：探索研究，非採購建議、採用決策或本專案已承諾的產品路線。**

目的：盤點 Atlan 對外賣什麼、使用者如何取得價值，以及官方公開到什麼程度的架構與交付狀態。本筆記只研究 Atlan；與本 repo 的比較及產品取捨另作整合。

證據標記：**產品文件**表示有操作或概念文件，不等於實機驗證；**GA／Preview／Roadmap**僅在官方明示時使用；**行銷主張**與**研究推論**分開標示。所有網址皆於調查日查閱，官方文件未提供更新日的地方不自行推定日期。

## 1. 對外定位與產品組合

Atlan 現在主打 **The Context Layer for AI**，將既有的 catalog、governance、lineage，包裝成企業 AI 共用的 business context。官網提出 unify → bootstrap → collaborate/certify → activate 的流程，強調人與 agent 共用企業定義、關係與政策。這是截至調查日的**行銷定位**，不能沿用「只是 data catalog」的分類。[官網](https://atlan.com/)

| 產品表面 | 使用者完成的工作 | 證據及邊界 |
|---|---|---|
| Enterprise Data Graph | 連接資料平台，查 metadata、跨系統 lineage 與影響範圍 | 官網稱 80+ connectors；支援深度須逐 connector 驗證，不能解讀為所有來源都有同等 column lineage／query mining。[Connectors](https://atlan.com/connectors/)、[Data Lineage](https://atlan.com/data-lineage/) |
| Data Marketplace | 以業務語言發現資料產品，查看 owner、認證、freshness、lineage，申請存取 | 面向 consumer 的入口；也有 producer 發布與 steward 治理。存取核發可整合 Immuta、Jira、ServiceNow；資料庫實際 masking／access enforcement 不能一概歸給 Atlan 自己。[Data Marketplace](https://atlan.com/data-marketplace/) |
| Context Agents Studio | 從 query history、lineage、BI 使用訊號產生 descriptions、README、SQL Intelligence | 有目前三類 agent 的產品文件；只補缺漏，不任意覆寫既有內容。官網更多具名 agent 的敘事，不能全數視為 GA。[Studio](https://docs.atlan.com/product/capabilities/governance/context-agents-studio)、[目前 agents](https://docs.atlan.com/product/capabilities/governance/context-agents-studio/concepts/agents) |
| Context Engineering Studio（CES） | 為單一 use case 組裝 semantic context repository，測試、修正、部署 | 從 governed assets 組裝；概念文件列 Snowflake Cortex Analyst、Databricks Genie、dbt、Claude。Repo 參照來源，來源變動後需 regenerate。不是承諾所有發布目標都自動即時同步。[CES](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/what-is-context-engineering-studio) |
| Context Lakehouse | 將 context 當可查詢、可攜的基礎設施供人與 agent 使用 | 官網主張 graph＋Iceberg、vector retrieval、time travel、SQL／API／MCP。不能從此行銷頁推導所有操作都具有端到端 snapshot 或 transaction 保證。[Context Lakehouse](https://atlan.com/context-lakehouse/) |
| MCP／Conversational AI | 在原有 AI 工具或 Atlan／Slack／Teams 內查詢與維護 context | MCP 工具已有搜尋、lineage、glossary、治理與寫入表面；工具 availability 仍受 tenant flags 與底層功能限制。[MCP overview](https://docs.atlan.com/product/capabilities/atlan-ai/how-tos/atlan-mcp-overview)、[MCP tools](https://docs.atlan.com/product/capabilities/atlan-ai/references/mcp-tools) |

**研究推論：**Atlan 把同一份 metadata/context 的價值拆成 consumer 發現入口、steward 維護入口、engineer 整合入口、AI context 發布入口。這種產品切分比單純列出 storage／pipeline 元件更接近可對外銷售的方案；它不代表每個模組都必須由同一團隊從零實作。

## 2. 非結構化知識已經進入產品，不能當成空白市場

Atlan 已有 **Knowledge Folders／Knowledge Files** 操作文件：將 SOP、policy 等文件上傳成 catalog assets。FAQ 列 PDF、Markdown、YAML、JSON、TXT，單檔上限 10 MB；PowerPoint 要先轉 PDF。PDF 背景經模型讀取文字與圖表，但跨文件搜尋目前只匹配抽出的文字，不能靠圖意搜尋找到檔案。這些是**文件所述能力，GA 狀態未由該頁明示**。[Knowledge Folders](https://docs.atlan.com/product/capabilities/governance/knowledge-folders)、[格式與 PDF FAQ](https://docs.atlan.com/product/capabilities/governance/knowledge-folders/faq/knowledge-folders-faq)

有兩條處理路徑：把 knowledge file 連到既有 asset，讓 Description／README agent 以文件補強 metadata；或透過 agent template 產生 glossary terms 與 business rules，每個 term 附文件 citation。上傳本身不產生這些語意結果。Skill generation 還沒提供；file→讀取 agent→產出 term 的 lineage 也還未記錄，現階段是 term citation。[Extraction pipeline](https://docs.atlan.com/product/capabilities/governance/knowledge-folders/concepts/extraction-pipeline)

**Knowledge sources／agent templates 明示 Private Preview。**目前文件列 GitHub、Confluence、Knowledge Files，以及 custom MCP source；SharePoint、Google Drive 仍 coming soon。Knowledge source 是執行當下讀取的來源，與定期 crawl 成 catalog assets 的 connector 不同；外部存取以管理員提供的 credential 為界線，並非每個最終使用者的來源身份。[Knowledge sources](https://docs.atlan.com/apps/knowledge-sources)

目前 template 已提供 Business Graph Term Generator：文件→terms/categories，會引用來源、檢查重複並保留人工定義；sample run 不發布，full run 寫入 glossary。Knowledge Curator、Code & API-Spec Lineage、Skill/AOP Compiler 則列 coming soon。[Agent templates](https://docs.atlan.com/product/capabilities/governance/context-agents-studio/concepts/agent-templates)

明確限制：knowledge folders 目前沒有 folder-level ACL；能看 knowledge assets 的角色會看見 tenant 全部 knowledge folders/files。預設僅 Admin／API token 能上傳，其他角色可經 custom AuthPolicy 擴充。另有 knowledge file 無 freshness signal、長文搜尋依 workspace 是否開啟 semantic search 而異、大庫可能只讀到部分檔案等限制。[Folders and files](https://docs.atlan.com/product/capabilities/governance/knowledge-folders/concepts/knowledge-folders-and-files)、[Knowledge Files source](https://docs.atlan.com/apps/knowledge-sources/knowledge-files)

因此不能宣稱 Atlan 只管 structured metadata、沒有 PDF 或知識文件能力；也沒有足夠公開證據認定它已完成高保真文件處理、細粒度文件權限、版本衝突處理或完整知識衍生 lineage。

## 3. 公開架構：可確認元件，不能推測未公開的實作保證

官方架構是 cloud-first、single-tenant SaaS，可在 AWS／Azure／GCP 託管。客戶來源仍在自己的 infrastructure；需連私網來源時可放置 SDR（Temporal Worker、Dapr、connector code），連回 Atlan Temporal server。這是客戶端 runtime，不是整個平台 self-hosted 的證據。[Atlan architecture](https://docs.atlan.com/platform/references/atlan-architecture)

| 層 | 官方列出的實作 |
|---|---|
| API／Identity | Kong、Heracles core API、Keycloak、Heka／Calcite SQL gateway |
| Metastore／Search | Apache Atlas，Cassandra persistence，Elasticsearch index |
| Workflow | Temporal 為主要引擎；Argo Workflows 仍有 legacy workload，待遷移退場 |
| Lakehouse | Apache Iceberg、Polaris REST catalog、tenant 專用 object storage |
| AI retrieval | AI Gateway、TurboPuffer vector/full-text store、Cloudflare Workers AI embeddings |
| 支援服務／營運 | Kafka、Redis、PostgreSQL、Vault；共享 control plane 經 Argo CD／Helm 部署，Grafana 觀測 |

來源：[官方架構元件表](https://docs.atlan.com/platform/references/atlan-architecture)。這個表是公開部署剖面，沒有證明 metastore、search、lakehouse、vector index 之間的更新時序、一致性或重建協定。

**隔離不是每個客戶一套完全獨立的 Kubernetes control plane。**官方說 compute nodes／storage 實體隔離，服務、Cassandra、Elasticsearch、object storage、IAM role 隔離；底層 Kubernetes control plane 共享，使用 Loft virtual clusters 做邏輯隔離。[Resource isolation](https://docs.atlan.com/platform/references/how-are-resources-isolated)

AI 文件宣稱 gateway 有 tenant key／budget／rate limit，vector namespace 有 tenant isolation／CMEK，retrieval 沿用 Atlan 權限；conversational history 在 tenant database，AI observability 另保存 full prompt／completion 30 天。它也明說 metadata／prompt／output 不用來訓練 foundation models。這些是廠商文件聲明，非本調查的控制查核。[AI security](https://docs.atlan.com/product/capabilities/atlan-ai/concepts/security)

MCP 以 OAuth user 或 service token 執行，將身份交給下游 Atlan services 授權；有 tenant tool allowlist、可申請 read-only mode，service token 要綁定一個 persona。安全文件強調 metadata 路徑，不應拿「不把 underlying data 傳給 LLM」概括所有 Knowledge Files／PDF 或可選 data exploration 的處理。[MCP security](https://docs.atlan.com/product/capabilities/atlan-ai/references/mcp-security)

## 4. 商業包裝與如何讓使用者買單

可從官方文件確認的計費結構：asset entitlement 決定可 catalog／govern 的資產規模；Atlan 自己執行的 AI 工作另耗 **Flexi Credits**。tenant 有各自 credit pool，Guest seat 免費但其 AI 回答仍扣 pool；credit packs 依合約年重置、剩餘不遞延。Essential MCP 讀寫 context 不耗 credit，Advanced MCP 呼叫 Atlan AI 才耗。這不是完整報價單，不能自行推定每席費或平台年費。[How Flexi Credits work](https://docs.atlan.com/get-started/concepts/how-credits-work)、[Asset estimation](https://docs.atlan.com/get-started/references/asset-estimation)

| 公開計價單位 | 調查日公開 rate card |
|---|---:|
| Description | 10 credits／asset |
| README | 50 credits／asset |
| SQL Intelligence | 100 credits／object |
| Conversational Quick／Deep | 10／30 credits／answer |

追問另外計一個 answer；回答若再觸發 enrichment，工作費另加。Essential MCP 免費指不耗 Flexi Credits，不表示沒有平台合約。**未找到可支持當前正式美元定價、最低合約額或折扣的公開官方報價。**[Flexi Credits rate card](https://docs.atlan.com/get-started/references/credits-rate-card)

官網的進場路徑為 Context Workshop：盤點客戶 data／AI architecture、選 priority use case、建立 baseline，再做四週 Context Sprint，交付 working agent 與 accuracy results。這是**官方銷售方案敘事**，不是本調查確認的交付 SLA。[官網 FAQ](https://atlan.com/)、[Sales contact](https://atlan.com/forms/talk-to-sales-contact/)

**研究推論：**它賣的是「讓一個業務 AI use case 到可驗收狀態」，再以 enterprise governance／跨平台 context 支撐擴張；消費者可在 Atlan 入口、Slack／Teams 或既有 AI client 取得價值。功能清單服務於這個商業結果，並有資產規模與 AI 用量兩種擴張軸。

## 5. 客戶證據能支持什麼

- Workday 官方客戶 session 描述從人類可理解的治理，走向讓 AI 可用的 active semantic layer；可支持其客戶需求與使用方向，不能當成已量測準確率提升的證據。[Workday session](https://atlan.com/regovern-watch-center/workday-context-as-culture/)
- CME Group session 講數百萬 assets 的自動治理、lineage 與 business context；官網另刊客戶表示首年 catalog 1,800 萬 assets、1,300+ glossary terms。屬具名廠商刊載的客戶證詞，未做獨立稽核。[CME session](https://atlan.com/regovern-watch-center/cme-group-context-at-speed/)、[Context Lakehouse 客戶證詞](https://atlan.com/context-lakehouse/)
- Data Marketplace 頁刊 Virgin Media O2 表示一年 onboard 6,000 人、100 萬 views。這證明 Atlan 對外使用 adoption 作為成果敘事，但 views／onboarding 不能替代業務 ROI 或準確率。[Data Marketplace](https://atlan.com/data-marketplace/)
- Context Agents 頁刊 Mastercard 兩週為 30,000 assets 補文件的 rollout 敘事。官方描述有 steward certification，不能由此推論所有客戶皆已具備 generate-before-review 產品 workflow。[Context Agents](https://atlan.com/context-agents/)

## 6. 文件狀態差異與採購應查證項目

官方 maturity matrix 多數列的 as-of 是 **2026-07-08**，CES 列是 **2026-09-09**。它仍把 hosted MCP 列 Private Preview、unstructured ingestion 列 Roadmap／experimental；但目前 MCP overview 稱 hosted server 可供每個 tenant，另已有 Knowledge Folders 操作文件及 Private Preview knowledge source/template 文件。**這是官方來源時間與狀態不同步，不能挑有利的一頁當成全產品的交付事實。**CES 在 matrix 明示 GA、獨立模組且需 account team enable；Data Quality Studio Snowflake 是付費 add-on，其他 backend 狀態不同。[Feature maturity matrix](https://docs.atlan.com/get-started/references/feature-maturity-matrix)

其他差異：舊 matrix 稱 column description 未支援，現行 enrichment FAQ 說 Description agent 會處理 child columns，但 coverage 只算 parent、500 最熱門 parent 上限可能令尾端資產永遠沒被重跑觸及；知識來源 FAQ 仍把 custom MCP 列開發中，較具體 source reference 則列可用。需要以客戶 tenant 可配置的實際表面與最新 release／書面承諾驗證。[Enrichment FAQ](https://docs.atlan.com/product/capabilities/governance/context-agents-studio/faq/metadata-enrichment)、[Template FAQ](https://docs.atlan.com/product/capabilities/governance/context-agents-studio/faq/agent-templates)、[Knowledge sources](https://docs.atlan.com/apps/knowledge-sources)

未經本調查確認：實際報價、模組 entitlement、各 tenant feature flags、GA migration 時程、端到端 PDF fidelity／OCR／表格結構品質、衍生知識 freshness／withdrawal 保證、跨索引一致性、版本快照語意、實測 latency／SLA、完整部署／資料駐留合約與第三方安全稽核結果。這份調查不應據以宣布已具備或確定缺乏上述能力。
