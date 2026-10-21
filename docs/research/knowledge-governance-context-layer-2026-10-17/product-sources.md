# Enterprise knowledge／context governance：產品官方證據

查閱日期：**2026-10-17（Asia/Taipei）**。僅使用 Atlan、Microsoft、Databricks 官方產品文件與 release notes；未操作付費 tenant，也未執行 enforcement／品質／撤回實測。以下區分「文件描述的產品行為」「明列成熟度」與「對本產品的推論」。

## 核心發現

企業產品已把治理延伸為：**誰對這個用途的知識負責、哪些來源適用、如何證明整理結果可用、交付後如何觀察及修正，以及使用／留存／停止使用的限制**。這些不等同於 ACL。另一方面，catalog 裡有政策、certificate 或 lineage，也不能推定每個讀取路徑都已執行相同控制；以下官方文件提供了具體反例。

## Atlan：權威來源、可維護語意與用途驗證

| 官方證據與適用範圍 | 可確認的行為／限制 |
|---|---|
| [Knowledge folders and files](https://docs.atlan.com/product/capabilities/governance/knowledge-folders/concepts/knowledge-folders-and-files) | Content owner 選擇權威文件版本，形成 curated gold layer，而非自動複製所有 drive／wiki。今天 agent run 產出 glossary terms＋business rules；skills／ontologies 是方向，Knowledge Synthesis Agent 標為 **Coming soon**。文件權限目前套 tenant entity-type；沒有 folder-level ACL，Purpose policies 尚不適用這類資產。 |
| [Extraction pipeline](https://docs.atlan.com/product/capabilities/governance/knowledge-folders/concepts/extraction-pipeline) | Asset enrichment 只讀明確連結的文件，用連結界定文件適用範圍。抽取 term 可引用來源文件；但官方明說這是 term provenance，**不是 knowledge-file lineage**：哪個 agent 讀過文件、哪些 term 由其衍生，仍屬計畫。Sample run 可先看候選，不能推成所有正式更新都必須人工批准。 |
| [Knowledge Folders FAQ](https://docs.atlan.com/product/capabilities/governance/knowledge-folders/faq/knowledge-folders-faq) | 有 PDF／Markdown／YAML／JSON／文字操作文件，每檔上限 10 MB。PDF 背景理解圖文、換版重解析；搜尋仍只匹配抽取文字，圖意需開檔才可讀。這些是具體操作／限制，不足以單獨證明全 tenant GA。 |
| [Feature maturity matrix](https://docs.atlan.com/get-started/references/feature-maturity-matrix) | 此頁自稱 availability authority：CES 列 **GA、2026-09-09**；core catalog／certification 列 GA。可是 unstructured ingestion／knowledge folders 一列仍是 **Roadmap／experimental、2026-07-08**，與較新操作文件並存，故 knowledge-files 的 tenant availability 仍須確認。Hosted MCP 列 Private preview、自架 MCP GA；不能以 MCP how-to 一概寫成 hosted GA。Data Contracts 列 Private preview 且無獨立 enforcement engine，需連 DQ rules；native Product Score 是 metadata completeness，不是內容正確率。 |
| [Add certificates](https://docs.atlan.com/product/capabilities/discovery/how-tos/add-certificates)、[Set up playbooks](https://docs.atlan.com/product/capabilities/playbooks/how-tos/set-up-playbooks) | Verified／Draft／Deprecated／No certificate 是可供使用者辨識與篩選的狀態，可附理由；playbook 能依規則批次更新 certificate。**推論：**這證明產品提供信任訊號與自動化，不證明每個 Verified 都經人工逐件審核或已驗明所有主張。 |
| [Purposes](https://docs.atlan.com/product/capabilities/governance/access-control/concepts/what-are-purposes)、[Create a purpose](https://docs.atlan.com/product/capabilities/governance/access-control/how-tos/create-a-purpose) | 這裡的 Purpose 是依 tag 決定資產範圍、附加 metadata／data policies 的機制；explicit deny 優先。有 tag／Purpose 而沒有 policy 時，只是 virtual collection，並未限制存取。不能將此術語直接等同每次 agent 呼叫都驗證「業務使用目的」。 |
| [Automate data governance](https://docs.atlan.com/product/capabilities/governance/stewardship/how-tos/automate-data-governance) | 可選 approval workflows／autoapproval／activity logs；管理外部來源存取可能經 Jira／ServiceNow／webhook 交由來源端執行。文件另列 **API／SDK／CLI、playbook 等批次更新不觸發這些 governance workflows**。因此「有審批流程」不能代替全入口 enforcement 證據。 |
| [Query without shared credentials](https://docs.atlan.com/product/capabilities/insights/how-tos/query-without-shared-credentials) | 預設查詢使用 shared connection credential；BYOC 改用個人來源憑證。可另啟用來源政策套用；啟用後該 connection 的 Atlan data policies 停用。必須依具體 connector／authentication 路徑判斷，不能把 catalog policy 當成來源端全工具授權。 |
| [What is CES?](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/what-is-context-engineering-studio) | Context Repo 依**一個 use case**組合 linked governed assets、語意模型與 instructions；官方建議按具體工作而非只有部門名稱定範圍。以 business questions／verified answers 評估、修正來源語意或 instructions、重生後再測試並部署；來源更新需 regenerate，不宜寫成已證明跨所有 consumer 即時同步／撤回。 |
| [Enterprise context layer guide](https://docs.atlan.com/agents/how-tos/build-an-enterprise-context-layer) | Domain owner 仲裁同名異義、負責定義與例外；guide 描述版本／certification contributor、timestamp、accuracy score，以及事件紀錄。它明說 context overlay **不取代 data-layer access policy**；production Observe 目前僅 Snowflake Cortex deployments。這是產品導入／治理指引，不是所有 target 的等效資格證明。 |
| [MCP security](https://docs.atlan.com/product/capabilities/atlan-ai/references/mcp-security) | OAuth 以使用者權限執行，API token 使用 service identity；可要求 read-only mode。Tool calls／失敗／denial 有結構化紀錄，arguments／responses 先遮罩；metadata 變動進 asset history。Retention 沿中央 observability pipeline，非獨立 MCP 設定。這裡描述 hosted MCP 行為，其可用性仍依 maturity／tenant enablement 判斷。 |

**未查證成既定能力：**這批 Atlan 文件沒有提供足以採納的、跨所有 knowledge／CES 路徑一致的「effective-from／effective-to 到期自動停止使用」或完整文件衍生物撤回／清除契約。不能由 upload date、modified time、certified status、一般 retention 建議推得此能力；這不是宣稱產品完全沒有這些功能。

## Microsoft Purview／Copilot：可讀、可供 AI 處理、可留存是不同控制

| 官方證據與日期 | 可確認的行為／限制 |
|---|---|
| [Copilot data protection architecture](https://learn.microsoft.com/en-us/microsoft-365/copilot/microsoft-365-copilot-architecture-data-protection-auditing) | 將來源權限、sensitivity labels／encryption、DLP、audit／retention 分開描述。這是 Microsoft 365 路徑的產品架構，不證明任意外部 RAG app 自動取得相同控制。 |
| [DLP for Copilot](https://learn.microsoft.com/en-us/purview/dlp-microsoft365-copilot-location-learn-about)（頁面更新 2026-10-05） | 帶指定 sensitivity label 的文件／email 可被排除出內容處理，**引用仍可能顯示**；與完全禁止存在性披露不同。敏感 prompt 阻擋、排除外部 email 明列 **preview**；直接附在 prompt 的檔案內容不在此 DLP 掃描覆蓋。政策更新最多四小時；Office session 中途加 label 下次開檔才執行。這些具體邊界不能當成即時撤回保證。 |
| [Audit logs for Copilot and AI applications](https://learn.microsoft.com/en-us/purview/audit-copilot)（頁面更新 2026-08-26） | Audit schema 包含 user／app／agent／version、AccessedResources、resource policy／status 與時間等資訊；可用來追查誰透過什麼 consumer 使用了哪些資源。Microsoft apps 與 non-Microsoft apps 的計費／啟用要求不同；稽核紀錄不是回答品質評估，也不應預設記錄具備完整重現材料。 |
| [Manage Microsoft 365 Copilot with Purview](https://learn.microsoft.com/en-us/purview/ai-m365-copilot) | 透過特定 cloud-attachment retention-label policy，可保留 **Copilot 引用當時的文件版本**。這是另外設定的版本保全能力，不是「有 citation URL 就永久有該版證據」。 |
| [Retention for Copilot and AI apps](https://learn.microsoft.com/en-us/purview/retention-policies-copilot) | Retention／deletion 涵蓋 prompts／responses；其他 AI apps 另有 collection-policy 前提。隱藏 mailbox 副本、eDiscovery、legal hold 與後台刪除時間影響實際留存；畫面消失不等於永久刪除，hold 可阻止 purge。不能把 interaction retention 當成原文件或所有衍生產物同時刪除。 |

**產品啟示（推論）：**「人能開原文」與「agent 可以把它加入 context」可以是不同的允許行為；citation、摘要、檔案內容及 audit evidence 也可能有不同披露／保留規則。這需要明示適用路徑與理由，不能只有一個看似共用的 access badge。

## Databricks Unity Catalog／MLflow：資料依賴、使用 trace 與品質評估分開治理

| 官方證據與日期 | 可確認的行為／限制 |
|---|---|
| [Lineage in Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/data-lineage)（更新 2026-09-29） | 對符合條件的 Databricks queries 自動捕捉 table／column lineage，用於影響分析、追因與敏感資料流。外部資產需註冊與關係設定；path／UDF 等有明確缺口。Catalog Explorer 與 lineage system tables 的保留範圍也不同；不能宣稱有一張圖就完整捕捉所有來源、consumer 與時間。 |
| [Model service/provider lineage](https://docs.databricks.com/gcp/en/data-governance/unity-catalog/ai-gateway-service-lineage)（更新 2026-09-29） | 可追服務定義中的 primary／fallback models 與 inference tables。官方明說**不捕捉 runtime 呼叫該服務的 workloads／agents，或其經該服務存取的資料**；因此 service graph 與 runtime usage trace 不能互相替代。這個引用是 GCP 文件，不推定所有 cloud 同時同範圍交付。 |
| [Build evaluation datasets](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/build-eval-dataset)、[Evaluation dataset reference](https://docs.databricks.com/aws/en/mlflow3/genai/eval-monitor/concepts/eval-datasets) | 將真實 traces／專家回饋形成可版本化、有 lineage 與 Unity Catalog 治理的 eval dataset；inputs 必填、expectations 可選。固定案例可比較版本、避免回歸。是 agent／application 品質評估，不能取代 source fidelity 或證明所有 future outputs 正確。 |
| [Store OTel traces in Unity Catalog](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/trace-unity-catalog)、[July release notes](https://docs.databricks.com/aws/en/release-notes/product/2026/july#mlflow-trace-storage-in-unity-catalog-is-now-generally-available) | **2026-07-16 GA**，不是沿用四月 Public Preview 狀態。Trace tables 有明確 schema／table permissions；能讀 table 的人可讀該 table 內所有 experiments traces。特定 region／配置限制仍適用；個別 trace 刪除須操作底層 rows，不能假設 UI/API delete 支援相同範圍。 |
| [Govern and redact traces](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/govern-redact)（更新 2026-09-15） | 可在 export 前遮罩，或事後對已保存 traces 建遮罩資料集並限制 raw access。官方明說 trace redaction **只改紀錄，不改 agent 實際收到／回傳的內容**。示範 retention pipeline 的 auto-TTL 永久清除時間不保證，嚴格期限需另一種已說明處理方式。 |
| [Unity Gateway](https://docs.databricks.com/aws/en/ai-gateway/)、[August release notes](https://docs.databricks.com/aws/en/release-notes/product/2026/august#unity-gateway-is-now-generally-available) | **2026-08-04 GA**，管理經其路由的 AI services／traffic、usage／cost／access；同一 release 明列 **service policies、agent services 仍 Beta**。不能以 Gateway GA 推得每個 guardrail／service 都 GA，或未經 Gateway 的第三方 agent 流量也受控制。 |

## 對目前 Knowledge Platform 的使用方式

以下是證據導出的**產品檢查問題，不是本次新增的必做功能或技術選擇**：

| 要分清的治理問題 | 應能拿出的產品證據 |
|---|---|
| 誰是來源權威、哪個用途適用 | Source Owner 與 topic maintainer 的責任不同；來源適用範圍、原因與衝突處置可追查。維護者不能因掛名就改寫來源政策。 |
| 哪個版本在什麼時間適用 | 區分 source revision、business effective period、accepted／published version、目前資格與 freshness；不可用 updated-at 一個值代替全部。若有效期間會決定可否使用，須另確認語意與執行，不能只加 metadata。 |
| 哪種品質已被證明 | 分開 source／轉換保真、綜合主張的支持度、consumer 任務品質與 metadata 完整度。Certificate／LLM score 不能互相代替。 |
| 從哪裡來、被誰用到 | 分開 source evidence、衍生依賴 lineage、consumer usage trace、產品 eval；明示未覆蓋的路徑。 |
| 允許何種使用、何時停止 | 人類讀取、agent context、摘要、引用、download／export、retention／purge 是可不同的動作；若限制不同，回傳可觀察理由與目前狀態。 |
| 如何持續改善 | 用真實任務與固定 evidence 定義 expected results；品質回報能連回責任 owner／修正版本。合格一般更新保持自動發布，不將外部產品的審批 UX 移植成逐文件人工批准。 |

本次證據不更改已確認 Q1–Q5：內部長期共用、topic／domain owner 主導、來源支持且缺口／衝突透明、合格更新自動發布、人類瀏覽／搜尋／閱讀查證為主並供既有 agents 使用。完整 human UI 仍依 [#79](https://github.com/davidlinnnn/data-ingestion/issues/79) 在實際 core MVP 驗收後設計；serving／adapter 與治理機制仍由 [#76](https://github.com/davidlinnnn/data-ingestion/issues/76)／[#56](https://github.com/davidlinnnn/data-ingestion/issues/56) 決定，並保留 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84) 新需求與 qualification 的區別。

未取得 tenant、報價／合約或做跨工具實測；availability、控制覆蓋與刪除／撤回時效必須按具體版本、connector、consumer 與配置驗證，不能宣稱三家提供相同保證。
