# Knowledge Platform PDP 提供方式：雲端與企業搜尋／RAG 平台的授權實務研究

**研究日期：2026-10-26（Asia/Taipei）。狀態：官方文件調查與條件式分析；尚未作出 PDP 模式決議。**

問題來自 [#85](https://github.com/davidlinnnn/data-ingestion/issues/85)：Knowledge Platform 持有多個 Source（應用）送入的文件，每份文件屬於恰好一個 Resource，readers 定義在 Resource 上；Retrieval search 必須依使用者可讀範圍過濾，規模上看約 10M 文件、每日約 10k 更新。比較三種 PDP 提供方式：

1. **公司中央授權服務 GAM（Zanzibar 式 ReBAC）**：平台 PEP 呼叫 GAM。
2. **平台內建引擎**（如 OpenFGA／SpiceDB），語意對齊 GAM；使用者透過 Resource Service 管理 relations；PEP 呼叫內部 authz API。
3. **平台不持有 policy**：只定義 PDP API，由各 Source／應用自行運行 policy engine。分兩個子型：**3a live callback**（每個請求／每個候選呼叫外部 PDP）與 **3b ACL／relationship sync**（外部系統的權限被拉入或推入平台，在平台本地執行）。

本筆記只整理官方文件可證實的事實與由此得出的工程推論，不替代 GAM 能力確認或治理決議。標 **UNVERIFIED** 者未在官方頁面確認。

## 結論與適用條件

以下是**條件式判斷**，不是選型決議：

- **對大量文件的 search／list：** 調查到的所有企業搜尋／RAG 產品，都把 ACL（或可解析成 ACL 的 principal 資料）同步進索引或其旁邊的 principal store，在查詢引擎內過濾；沒有任何一家在文件中提供「客戶自備 PDP callback」做 search 過濾。這等於本研究的 3b，或 1／2 搭配本地化的授權索引。若 Retrieval 需要在 10M 文件規模做 pre-filter，證據不支持以 3a 作為**唯一**過濾機制。
- **Live 檢查只出現在兩種位置：**(a) 對少量候選做**事後**驗證（Bedrock Managed Knowledge Base、Amazon Quick 的 real-time ACL verification），前提仍是先以同步過的 ACL pre-filter；(b) 整個檢索直接委託給來源系統（Google federated search、Microsoft 365 Copilot federated connectors、Azure 的 remote SharePoint knowledge source），此時來源也負責搜尋本身，不再是平台索引。若想用 3a 補足撤銷即時性，證據支持「3b pre-filter ＋ 3a 對 top-k post-check」的組合，而不是逐文件 live 過濾。
- **單一物件檢查（open document、取原文、API route）：** 外部 PDP 逐請求呼叫是成熟模式（Kubernetes webhook、Envoy ext_authz、API Gateway Lambda authorizer、Trino OPA、AuthZEN Access Evaluation），通常附 TTL cache 與明確 failure policy，預設多為 fail-closed。若平台只需在讀取單份文件時詢問 Source 的 PDP，3a 有現成的規範與實作先例。
- **若 Source 必須保有 policy 權威：** 產品的做法是「權威留在來源、平台以 connector 同步並在本地執行」，配合 identity mapping（外部帳號 → 平台 IdP 身分）與 external groups。這是 3b，而非 3a。平台要付出的成本是同步新鮮度、identity 對應正確性與缺資料時的預設行為。
- **缺 ACL 的預設值是關鍵差異：** 較新產品（Bedrock Managed KB、Amazon Quick S3、Azure AI Search 2025-11 之後）把缺 ACL 或缺 user context 視為不可見並 fail-closed；較舊產品（Kendra、Q Business、Elastic connectors DLS）視為公開。本平台的 Fail-Closed Governance 與前者一致；若採 3b，同步缺漏的處理必須明確定義為不可見。
- **AuthZEN 1.0 只解決 PDP 介面形狀，不解決 search 規模與一致性：** 它有 batch evaluation 與 resource search（含分頁），但沒有 decision TTL、沒有 consistency token，並明言 search 不保證完整與原子快照。若以 AuthZEN 定義 3 的 PDP API，仍需平台自訂 freshness／validity 與 list 規模契約。

以上是依產品文件推得的工程判斷；不是「CSP 禁止 live callback」，也不是「sync 方案沒有撤銷延遲」。

## A. 企業搜尋／RAG 產品如何取得與執行權限

### A1. 權限資料位置與查詢時執行

| 產品（狀態） | 權限資料放哪 | 查詢時如何執行 | 來源 |
|---|---|---|---|
| **Amazon Bedrock Managed Knowledge Base**（2026-06-17 GA；ACL 功能本身的 GA／preview 標示 UNVERIFIED） | Connector 抓取 allow／deny users、allow／deny groups，與內容一起 ingest；group membership 從各來源爬取後存在服務內部。Email 是唯一使用者識別，「no alias resolution or cross-identity-provider mapping」。Custom source 由 `IngestKnowledgeBaseDocuments` 逐文件提供 ACL。 | 兩階段：**Pre-retrieval filtering**（以爬取的 ACL 過濾）＋ **Real-time ACL verification**（「makes a real-time call to the data source to verify that the user still has access to each returned document」），支援 SharePoint、OneDrive、Google Drive、Confluence、Box、Zendesk、Salesforce 等；ServiceNow 僅部分支援，需客戶在 ServiceNow 內安裝 verifier endpoint；S3 與 Custom 不支援（客戶提供的 metadata 就是 source of truth）。Deny 優先。 | [ACL awareness](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-acl.html)、[ACL-aware retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve-acl.html)、[Custom ACL](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-ds-custom-acl.html)、[GA 公告](https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-bedrock-managed-knowledge-base/) |
| **Amazon Quick**（Q Business 後繼） | Confluence KB 每次 crawl 同步 ACL；使用者需一次性登入 Confluence。 | 先以同步 ACL 對向量檢索結果 pre-filter 產生候選，再用使用者自己的 Confluence credential「verify access to each candidate document in real time」。AWS blog：pre-filter 必要，因為「real-time API calls for every document in the index would be too costly at scale」。 | [Confluence KB ACL](https://docs.aws.amazon.com/quick/latest/userguide/confluence-kb-acl.html)、[AWS ML blog 2026-10-07](https://aws.amazon.com/blogs/machine-learning/rethinking-access-control-for-rag-with-amazon-quick-and-amazon-bedrock/) |
| **Amazon Q Business**（不再接受新客戶，只修 bug／安全） | Connector 將 ACL「along with the document itself」index；User Store 映射 users／groups；identity crawler 爬來源 principals 進 User Store，只有啟用 ACL crawling 時可用。Custom 文件經 `BatchPutDocument` 帶 `AccessConfiguration`。 | 文件只說「filter chat responses based on the end user's access」；pre／post 位置 UNVERIFIED。未找到查詢時呼叫來源的文件。 | [可用性變更](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/qbusiness-availability-change.html)、[Connector authorization](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html#connector-authorization)、[Principal store](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/principal-store-hiw.html)、[AccessConfiguration](https://docs.aws.amazon.com/amazonq/latest/api-reference/API_AccessConfiguration.html) |
| **Amazon Kendra**（2026-06-30 進入 Maintenance Mode，2026-07-30 停收新客戶） | ACL 與文件一起 ingest（`AccessControlList`，allow／deny，最多 200 entries）；群組以 `PutPrincipalMapping` 或 IAM Identity Center 解析。 | Query 帶 `UserContext`（token 或 UserId＋Groups）或 `_user_id`／`_group_ids` attribute filter。官方明言「User context filtering isn't an authentication or authorization control」，完整文件存取仍由原始 repository 執行。 | [可用性變更](https://docs.aws.amazon.com/kendra/latest/dg/kendra-availability-change.html)、[User context filter](https://docs.aws.amazon.com/kendra/latest/dg/user-context-filter.html)、[Index access control](https://docs.aws.amazon.com/kendra/latest/dg/create-index-access-control.html)、[PutPrincipalMapping](https://docs.aws.amazon.com/kendra/latest/APIReference/API_PutPrincipalMapping.html) |
| **Amazon Bedrock Knowledge Bases（經典）** | 無原生 ACL；應用以 metadata 欄位存 user／group。 | Retrieve 的 metadata filter（equals、in、listContains、andAll／orAll 等）。AWS Architecture blog 以 Verified Permissions（Cedar）當 PDP，由 middleware「dynamically construct the metadata filter」，Bedrock 在向量相似度搜尋前套用；blog 稱之為「filter-level (logical) isolation, not IAM-enforced」。 | [Metadata filters](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-config.html#kb-test-config-filters)、[ML blog](https://aws.amazon.com/blogs/machine-learning/access-control-for-vector-stores-using-metadata-filtering-with-knowledge-bases-for-amazon-bedrock/)、[Architecture blog 2026-06-22](https://aws.amazon.com/blogs/architecture/secure-multi-tenant-rag-with-amazon-bedrock-and-verified-permissions/) |
| **Google Vertex AI Search／Agent Search／Gemini Enterprise**（data source access control 標示 Preview） | 逐文件 `acl_info.readers[].principals[]`（`user_id`／`group_id`，每文件最多 3,000 readers）；`externalEntityId` 給不在 IdP 中的第三方身分；`idpWide` 代表全 IdP 使用者。Identity mapping store 將外部身分對應 IdP 使用者／群組（巢狀群組須攤平）。ACL 需在建立 data store 時啟用，一次性設定。IdP 為 Google Identity 或 Workforce Identity Federation。 | 以 IdP 識別搜尋者再判斷存取；pre／post 位置 UNVERIFIED。另有 **Federated search 模式**：直接向來源查詢，SharePoint 的結果「based on the user's permissions instead of the app's permissions」；代價是查詢字串送至第三方、品質可能較低。 | [Data source access control](https://docs.cloud.google.com/generative-ai-app-builder/docs/data-source-access-control)、[Document REST](https://docs.cloud.google.com/gemini/enterprise/docs/reference/rest/v1alpha/projects.locations.collections.dataStores.branches.documents)、[Identity mapping](https://docs.cloud.google.com/gemini/enterprise/docs/identity-mapping)、[Identity](https://docs.cloud.google.com/gemini/enterprise/docs/identity)、[Connectors 介紹](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/introduction-to-connectors-and-data-stores)、[SharePoint federated](https://docs.cloud.google.com/gemini/enterprise/docs/connect-sharepoint-online) |
| **Azure AI Search：security trimming（GA）** | 應用自行把 principal ID 字串存入 filterable 欄位；官方說「The principal is just a string」，服務不提供填寫該欄位的機制。 | 應用每次查詢附 `search.in` filter（引擎內 pre-filter）；呼叫者群組由應用解析。官方推薦給自訂身分系統或 push-model index。 | [Security trimming](https://learn.microsoft.com/en-us/azure/search/search-security-trimming-for-azure-search)、[Document-level access overview](https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview) |
| **Azure AI Search：原生 document-level access control（全部 preview，現行 `2026-08-01-preview`）** | 索引內帶 `permissionFilter: userIds｜groupIds｜rbacScope` 的 filterable 欄位；ADLS Gen2 indexer 在 ingestion 時計算有效 ACL；SharePoint indexer 擷取 ACL；Push API 可自帶（每欄最多 1000 值，須為 Entra object ID）。 | 查詢帶 `x-ms-query-source-authorization` 使用者 token，服務「dynamically constructs security filters… automatically appended to any filters」（引擎內 pre-filter）；群組在查詢時經 Microsoft Graph 展開。另有 remote SharePoint knowledge source 直接呼叫 SharePoint，「Governance remains fully in SharePoint」。 | [Query-time enforcement](https://learn.microsoft.com/en-us/azure/search/search-query-access-control-rbac-enforcement)、[ADLS indexer](https://learn.microsoft.com/en-us/azure/search/search-indexer-access-control-lists-and-role-based-access)、[Push API](https://learn.microsoft.com/en-us/azure/search/search-index-access-control-lists-and-rbac-push-api)、[SharePoint ACL](https://learn.microsoft.com/en-us/azure/search/search-indexer-sharepoint-access-control-lists) |
| **Microsoft Graph／Copilot connectors（synced）** | 每個 `externalItem` 的 `acl` 為必填（grant／deny；user、group、everyone、externalGroup）；非 Entra 群組以 connection 擁有的 external groups 表示，成員可為 Entra 使用者／群組或巢狀 external group，由 connector 負責保持同步。 | 在 Microsoft Search 內依儲存的 ACL 修剪；內部 pre／post 機制未說明（UNVERIFIED）。Federated connectors（MCP-based）則即時取資料、不 index，「The source system enforces all permissions」。 | [externalItem](https://learn.microsoft.com/en-us/graph/api/resources/externalconnectors-externalitem)、[acl](https://learn.microsoft.com/en-us/graph/api/resources/externalconnectors-acl)、[Manage items](https://learn.microsoft.com/en-us/graph/connecting-external-content-manage-items)、[External groups](https://learn.microsoft.com/en-us/graph/connecting-external-content-external-groups)、[Federated connectors](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/federated-connectors-overview) |
| **Glean** | Indexing API 每份文件帶 `permissions`（`allowedUsers`、`allowedGroups`、`allowAnonymousAccess`、`allowAllDatasourceUsersAccess`；只有 grant）；users／groups／memberships 另經 `/indexuser`、`/indexgroup`、`/indexmembership` 推入獨立 identity store，非同步處理。 | 「Glean applies the permission snapshot that was mirrored during crawling and incremental updates」；pre／post 位置 UNVERIFIED。Live 只出現在 live-retrieval 路徑（例如 Salesforce live fetch 以使用者自己的 OAuth 呼叫 Salesforce）。 | [Document permissions](https://developers.glean.com/api-info/indexing/documents/permissions)、[Permissions overview](https://developers.glean.com/api/indexing-api/permissions-overview)、[Connectors about](https://docs.glean.com/connectors/about)、[Salesforce](https://docs.glean.com/connectors/native/salesforce/about) |
| **Elastic connectors DLS（beta）／Elasticsearch DLS（GA）** | Content sync 在文件寫入 `_allow_access_control`；另一個 access control sync 把每個使用者的身分清單寫入隱藏的 `.search-acl-filter-<INDEX>`。 | Middleware 讀取使用者身分文件，為每個使用者建立 API key，其 role descriptor 帶 DLS query template；Elasticsearch 以 role query 執行（「Documents that don't match the role query are never returned」）。 | [Connector DLS](https://www.elastic.co/docs/reference/search-connectors/document-level-security)、[DLS overview](https://www.elastic.co/docs/reference/search-connectors/es-dls-overview)、[E2E guide](https://www.elastic.co/docs/reference/search-connectors/es-dls-e2e-guide)、[ES DLS](https://www.elastic.co/docs/deploy-manage/users-roles/cluster-or-deployment-auth/controlling-access-at-document-field-level) |

### A2. 新鮮度、缺資料與失敗行為、外部 PDP

| 產品 | 權限變更新鮮度 | 缺 ACL／缺 user context／來源不可達 | 客戶自備 PDP callback | 不應外推的結論 |
|---|---|---|---|---|
| Bedrock Managed KB | Group membership「as fresh as the last sync」，real-time check 補足兩次 sync 間的變更；大群組傳播可能落後；ACL 變更「eventually consistent」。[ACL awareness](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-acl.html)、[Retrieval](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-test-retrieve-acl.html) | 「ACL-aware retrieval fails closed」：group resolution 失敗、real-time verification timeout、內部錯誤都不回傳受影響文件；缺 permissions 視為 restricted；沒有 `userContext` 時 ACL 來源回 0 筆。Real-time denial 後不 backfill。 | 無；ServiceNow verifier 是在來源系統內，由 AWS 定義。 | 官方明言「ACL-aware filtering, not a security boundary」，服務不驗證使用者身分。Real-time 只用於少量回傳文件，不是對全索引 live 過濾。 |
| Amazon Quick | 同步 ACL＋real-time 檢查。 | Confluence API 不可用時回錯誤，「does not fall back to cached permissions」。S3 KB：沒有 ACL 的文件不 ingest。[S3 ACL](https://docs.aws.amazon.com/quick/latest/userguide/s3-acl.html) | 無。 | Live 檢查用的是來源自己的 API 與使用者 credential，不是平台定義的 PDP API。 |
| Q Business | 每次 crawl 更新 ACL；排程可 hourly 到 monthly 或 cron。[Sync run](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html#connector-sync-run) | 無 ACL 的文件視為公開；S3 connector 對 ACL 檔未列出的 prefix 開放給所有使用者（[S3 user management](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/s3-user-management.html)）；關閉 ACL crawling 後內容對所有 application 使用者可見（[AWS blog](https://aws.amazon.com/blogs/machine-learning/enable-or-disable-acl-crawling-safely-in-amazon-q-business/)）。來源不可達時的查詢行為 UNVERIFIED。 | 無（UNVERIFIED 的缺席）。 | 產品已停收新客戶；fail-open 預設不代表現行 AWS 建議。 |
| Kendra | 隨 re-crawl 更新；`PutPrincipalMapping` 非同步，以 `OrderingId` 防止舊值覆蓋。 | 無 ACL 的文件為公開；查詢不帶 user context 時「returns all documents」（fail-open）。 | 無（UNVERIFIED 的缺席）。 | 官方自稱不是授權控制。 |
| Bedrock KB（經典） | 由應用自行更新 metadata。 | 由應用決定；filter 缺漏即無過濾。 | 模式上可由應用先問外部 PDP（Verified Permissions），再轉成 pre-filter。 | PDP 回傳的是**過濾條件**，不是逐文件 callback；隔離屬邏輯層。 |
| Google Agent Search | Identity sync 預設 30 分鐘（範圍 30 分鐘到 7 天）、incremental 預設 3 小時；incremental 不同步 identity 與刪除；STREAMING 標示尚未支援；SharePoint「real-time sync」（Preview）不同步 identity。[DataConnector](https://docs.cloud.google.com/gemini/enterprise/docs/reference/rest/v1/DataConnector)、[SharePoint data store](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/ms-sharepoint/set-up-data-store) | 未記載（UNVERIFIED）。公開需明確設 `idp_wide`。[Custom connector](https://docs.cloud.google.com/gemini/enterprise/docs/connectors/create-custom-connector) | 無；live 選項是 federated search（由來源執行搜尋）。 | Federated 模式把搜尋本身交給來源，不能當作「平台索引＋外部 PDP 過濾」的先例。 |
| Azure AI Search（原生） | 「only reflected in search results after that metadata is synchronized to the index」；ADLS Gen2 需 resync／resetdocs；SharePoint indexer 自 `2026-05-01-preview` 起逐次增量取 item 級變更，但父層繼承變更仍需 resync；Push 需重新 ingest。 | 不帶 user token 只回公開文件（2025-11 起；更早的 preview 會回全部）；**「If ACL evaluation fails (for example, the Graph API is unavailable), the service returns 5xx and does not return a partially filtered result set.」** 超過每檔 ACL entry 上限的權限「might not be enforced」。 | 無（UNVERIFIED 的缺席）；只有 Entra token 模型或應用自建字串 filter。 | Preview，無 SLA、不建議 production。查詢時呼叫 Graph 只是展開群組成員，不是外部 PDP 決策。 |
| Graph／Copilot connectors | Microsoft 自建 connector 預設每日 full crawl、每 15 分鐘 incremental；「Incremental crawls don't pick up ACL changes」。敏感資料建議 event-based sync。[Confluence Cloud](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/confluence-cloud-deployment) | `acl` 為必填；省略時的伺服器回應 UNVERIFIED。每使用者 external group membership 超過 10,000 時查詢回 400。 | 無（UNVERIFIED 的缺席）。 | 「不要把 external group 成員展開到每個 item 的 ACL」是 Microsoft 的規模建議，表示 group 與 item ACL 應分開同步。 |
| Glean | 依 connector：例如 Salesforce share／identity 約每小時；SharePoint 無 webhook 時最長約 24 小時、`Sites.Selected` 約 72 小時。Permission freshness 與 identity freshness 分開定義。[SharePoint FAQ](https://docs.glean.com/connectors/native/sharepoint/security/faq)、[Key terms](https://docs.glean.com/connectors/key-terms) | SDK 測試會拒絕缺 `permissions` 的文件；未知或空群組永遠不匹配。省略時的伺服器預設與來源不可達行為皆 UNVERIFIED。[SDK permissions](https://developers.glean.com/libraries/indexing-sdk/permissions) | 無（UNVERIFIED 的缺席）。 | 「Glean 查詢時做 real-time permission check」未在官方文件確認。 |
| Elastic | Access control sync 依 cron 排程；權限變更後需更新或重建 API key，因此延遲等於 sync 間隔加上 key 生命週期。[Scheduling API](https://www.elastic.co/guide/en/elasticsearch/reference/current/update-connector-scheduling-api.html) | **無 access control 欄位的文件不受限制（fail-open）**；欄位存在但為空則無人可見。 | 無；authorization 就是 role query。 | ES DLS 的計分、aggregation 會洩漏不可見文件的統計資訊，屬於 Protected Observation 風險。[Limitations](https://www.elastic.co/docs/deploy-manage/security/limitations) |

## B. 平台呼叫客戶自備授權端點（3a 先例）

| 平台 | 呼叫模型 | List／filter 怎麼處理 | Timeout 與失敗語意 | 不應外推的結論 |
|---|---|---|---|---|
| **Kubernetes authorization webhook** | 每個請求 POST `SubjectAccessReview`；有 decision cache：authorized TTL 預設 5m、unauthorized 30s。Structured `AuthorizationConfiguration`（v1.32 stable）可設 `cacheAuthorizedRequests`、`matchConditions`（CEL）。[Webhook](https://kubernetes.io/docs/reference/access-authn-authz/webhook/)、[Authorization](https://kubernetes.io/docs/reference/access-authn-authz/authorization/)、[kube-apiserver flags](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/) | `list` 以 resource type＋verb 授權，可附 label／field selector；只回 allow／deny，官方說 get、list、watch 在資料存取上等價。未見 authorizer 可從 list 結果中逐物件剔除的文件（推論，UNVERIFIED 的明文）。 | `timeout` 必填、上限 30s；`failurePolicy` 必填、無預設（`Deny` 或 `NoOpinion`）；全部 authorizer 無意見時拒絕。 | 先例是 coarse-grained API 授權，不是逐文件過濾；TTL cache 代表撤銷可延遲最多 5 分鐘。 |
| **Envoy ext_authz** | 每請求 gRPC／HTTP check；Envoy 本身不提供 decision cache。[Filter](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_filters/ext_authz_filter) | 不處理；單一 request 決策。 | `failure_mode_allow` 預設 false（fail-closed）；timeout 預設 200ms；錯誤狀態預設 403。[Proto](https://www.envoyproxy.io/docs/envoy/latest/api-v3/extensions/filters/http/ext_authz/v3/ext_authz.proto) | 200ms 預算是給單一請求；乘以候選數就不可行。 |
| **Trino OPA access control** | 「Trino contacts OPA for each query」；無 decision cache。[OPA access control](https://trino.io/docs/current/security/opa-access-control.html) | 未設 `opa.policy.batched-uri` 時「one request to OPA for each object」；設定後一次送 `filterResources`，OPA 回允許的索引。Row filter 與 column mask 由 OPA 回傳**條件**，Trino 當作額外 WHERE 執行。 | 文件未述；原始碼中無法連線、非 2xx、無法解析都拋例外，沒有 fail-open 路徑（[OpaHttpClient](https://raw.githubusercontent.com/trinodb/trino/master/plugin/trino-opa/src/main/java/io/trino/plugin/opa/OpaHttpClient.java)）。HTTP timeout 預設 UNVERIFIED。 | Batch 過濾的對象是 catalog／schema／table 等 metadata 清單，不是千萬筆資料列；資料列層級靠 PDP 回傳的條件。 |
| **Apache Kafka custom authorizer** | `authorize()` 是同步 API，Javadoc：「designed for use with locally cached ACLs」，因在 request thread 上執行，應避免會阻塞的遠端通訊。[Authorizer.java](https://raw.githubusercontent.com/apache/kafka/trunk/clients/src/main/java/org/apache/kafka/server/authorizer/Authorizer.java)、[Kafka ACL docs](https://kafka.apache.org/42/security/authorization-and-acls/) | `authorize(ctx, List<Action>)` 批次逐項判斷；過濾時拒絕不記 log。 | 由實作決定。 | 介面本身要求本地 cache，等於明示不建議每請求遠端 PDP。 |
| **Apache Ranger** | Plugin 啟動時從 Ranger Admin 下載 policy、在記憶體建 engine、預設每 30s 非同步 poll。[Ranger blog](https://ranger.apache.org/blogs/integrating_applications.html)、[Hive plugin config](https://github.com/apache/ranger/blob/master/hive-agent/conf/ranger-hive-security.xml) | Row filter 與 masking 以結果形式回給應用注入查詢。[Row-level filtering](https://cwiki.apache.org/confluence/display/RANGER/Row-level+filtering+and+column-masking+using+Apache+Ranger+policies+in+Apache+Hive) | Admin 不可達時「continue to use last known version of policies」；本地 cache 檔只在啟動且無 policy 時載入。[PolicyRefresher](https://raw.githubusercontent.com/apache/ranger/master/agents-common/src/main/java/org/apache/ranger/plugin/util/PolicyRefresher.java)。新的 remote PDP（`POST /v1/authorize`）建議 fail-closed，但 embedded plugin 仍是 Java 的優先整合方式。 | 這是「pull policy 到 PEP 本地」，最接近 3b；撤銷延遲約等於 poll 間隔。 |
| **Amazon API Gateway Lambda authorizer** | 每請求呼叫 Lambda，結果可 cache：`authorizerResultTtlInSeconds` 預設 300、上限 3600、0 為關閉。[CreateAuthorizer](https://docs.aws.amazon.com/apigateway/latest/api/API_CreateAuthorizer.html)、[Lambda authorizer](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html) | Cache 的 policy 套用到整個 API，官方提醒 policy 須適用所有 resource／method；HTTP API 可把 `$context.routeKey` 加進 identity source 做 per-route cache。[Output](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-output.html)、[HTTP API](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-lambda-authorizer.html) | Deny→403、Unauthorized→401、其他錯誤→500；HTTP API authorizer 回應 timeout 10,000ms。[HTTP API quotas](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-quotas.html)。REST API authorizer timeout UNVERIFIED。 | 是 route 層級決策；cache key 若過粗會錯誤套用授權。 |

**共通點：** 有預設值的地方都是 fail-closed（Envoy、Trino、API Gateway、Ranger remote PDP 建議）；Kubernetes 強制明確選擇。List 的處理方式只有四種：type 層級 coarse 決策（K8s）、批次逐項檢查（Trino batched、Kafka、AuthZEN `/evaluations`）、PDP 回傳過濾條件（Trino／Ranger row filter、Bedrock KB 經典＋Verified Permissions）、反向查詢（見 C2）。

## C. 標準與授權引擎的 list 能力

### C1. OpenID AuthZEN Authorization API 1.0

Final 於 2026-01-11 發佈（OIDF 2026-01-12 公告，81 票贊成）。[Spec](https://openid.net/specs/authorization-api-1_0.html)、[公告](https://openid.net/authorization-api-1-0-final-specification-approved/)

| 有標準化 | 沒有標準化（3 的 PDP API 仍需自訂） |
|---|---|
| Access Evaluation（§6）：subject、action、resource、可選 context；decision 為必填 boolean，另有自由形式 `context`。 | 決策 cache／validity TTL：無欄位；唯一 caching 文字是 metadata（§11.9）。 |
| Access Evaluations 批次（§7）：結果依請求順序；`evaluations_semantic` 為 `execute_all`（預設）、`deny_on_first_deny`、`permit_on_first_permit`。 | Consistency token（Zanzibar zookie 類）：無。 |
| Search APIs（§8，1.0 Final 內）：Subject／Resource／Action search；分頁 `page.token`、`page.limit`、`next_token`、可選 `count`／`total`。 | Search 完整性：結果應為可允許的實體但「this outcome is not guaranteed」；transitive search 只是 RECOMMENDED；「Pagination does not guarantee an atomic snapshot」；`total` 不保證一致。 |
| Discovery（§9）：`/.well-known/authzen-configuration`，只有 `access_evaluation_endpoint` 必填。 | Policy 語言、架構、狀態管理（§2 明列 out of scope）：沒有 policy 管理，也沒有 relationship 寫入。 |
| Transport（§10）：HTTPS JSON binding 為必要；其他 binding 留待未來 profile。 | 結果數量上限、延遲 SLO：只有一般性的 DoS／rate-limit 建議（§11.7）。 |

**Interop 證據：**[Interop 總覽](https://authzen-interop.net/docs/intro)列出 Todo、API Gateway、Search（Identiverse 2025）、IdP 等情境。Todo 情境以批次 `evaluations` 為清單中每個 todo 各做一次判斷（[Todo 1.1](https://authzen-interop.net/docs/scenarios/todo-1.1/)）；Search 情境以 resource search 回答「Erin 可以看哪些記錄」，資料只有 20 筆記錄、6 個使用者，且頁面未提分頁、上限或一致性（[Search scenario](https://authzen-interop.net/docs/scenarios/search/)）；API Gateway 情境是 route 層級的單次 evaluation（[API Gateway](https://authzen-interop.net/docs/scenarios/api-gateway/)）。**沒有證據顯示 AuthZEN 曾在大型文件集的搜尋過濾規模上做過 interop。**

### C2. ReBAC 引擎的 list 能力（選項 1／2 的背景）

| 來源 | 事實 | 不應外推的結論 |
|---|---|---|
| OpenFGA | ListObjects 預設 deadline 3s、最多 1000 筆，逾時回傳已找到的部分結果；定位為「access-aware filtering on small object collections」。[Relationship queries](https://openfga.dev/docs/interacting/relationship-queries)。Search-with-permissions 指引：結果少時「先搜尋再 BatchCheck」；可存取物件多時「consume `GET /changes` 建本地索引，搜尋後再 check」；ListObjects 只適合約 1000 筆以內，部分清單無法排序。[Search with permissions](https://openfga.dev/docs/interacting/search-with-permissions) | OpenFGA 自己的大規模建議就是 3b 形狀（變更流同步到搜尋端），不是逐筆 live check。 |
| SpiceDB | LookupResources 支援 cursor，但超過 10k 結果是「heavy request」，建議改用 CheckBulkPermissions post-filter 或 Materialize。[Querying data](https://authzed.com/docs/spicedb/concepts/querying-data)。一致性模式含 `minimize_latency`（讀取預設）、`at_least_as_fresh`（ZedToken）、`at_exact_snapshot`、`fully_consistent`。[Consistency](https://authzed.com/docs/spicedb/concepts/consistency) | 10M 文件規模的 search 過濾需要物化或本地索引，不論 PDP 在 GAM 或平台內建。 |
| Zanzibar | USENIX ATC 2019：在 ACL 變更中維持 external consistency，以 zookie 確保評估快照「at least as fresh」於內容變更；p95 低於 10ms。[Google Research](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/)、[Paper](https://www.usenix.org/system/files/atc19-pang.pdf) | Zookie 語意與 Leopard 索引細節取自官方論文的搜尋摘要，原文未能逐字抽取（UNVERIFIED wording）。GAM 是否提供 zookie 或 list／lookup API 未知。 |

## D. 綜合分析

### D1. Search／list 與單一物件檢查用的是不同模式

| 用途 | 證據中的做法 | 例子 |
|---|---|---|
| 大量文件 search／list | 權限資料在索引內或旁邊，由查詢引擎 pre-filter；PDP（若有）輸出的是過濾條件或同步資料，而不是逐文件決策。 | Azure AI Search、Kendra、Q Business、Google Agent Search、Graph connectors、Glean、Elastic DLS；Bedrock KB＋Verified Permissions；OpenFGA `/changes` 本地索引；Trino／Ranger row filter |
| Top-k 候選事後驗證 | 先 pre-filter，再對少量回傳結果呼叫來源；失敗時 fail-closed、不 backfill。 | Bedrock Managed KB、Amazon Quick |
| 單一物件或單一請求 | 每請求呼叫外部 PDP，搭配短 TTL cache 與明確 failure policy。 | K8s webhook、Envoy ext_authz、API Gateway Lambda authorizer、AuthZEN Access Evaluation |
| 整個檢索委託來源 | 來源用使用者身分執行搜尋與權限判斷。 | Google federated search、Copilot federated connectors、Azure remote SharePoint knowledge source |

### D2. 3a 與 3b 的成本（證據＋工程推論）

| 面向 | 3a live callback | 3b ACL／relationship sync |
|---|---|---|
| 延遲 | 每個候選一次外部呼叫；Envoy 單請求 timeout 預設 200ms，乘以候選數後無法作為 pre-filter。AWS 明言對索引內每份文件做 real-time 呼叫「too costly at scale」。 | 查詢時在本地引擎過濾；Azure 提到首次 ACL 查詢因權限解析較慢。 |
| N 個外部依賴 | 每個 Source 的 PDP 都在查詢關鍵路徑上；跨 Source 的 Retrieval 要同時等最慢的那個（推論）。 | 依賴移到同步管線；查詢路徑只依賴平台本身與 identity 解析。 |
| 可用性耦合 | 誠實的 fail-closed 意味著任一 Source PDP 故障，該 Source 的文件從結果中消失或整個請求失敗（Bedrock Managed KB、Quick、Azure 5xx 的做法）。 | 同步中斷時繼續以最後一版權限服務（Ranger「last known version」）；風險轉為撤銷延遲。 |
| 撤銷新鮮度 | 最即時；但 K8s／API Gateway 等實作加上 TTL cache 後，實際延遲為 cache TTL（預設 5 分鐘）。 | 等於同步間隔加處理時間：Google identity 預設 30 分鐘、Glean 部分 connector 每小時到 72 小時、Microsoft incremental crawl 不帶 ACL 變更、Elastic 加上 API key 壽命。 |
| 缺資料語意 | 由外部 PDP 回答，平台只需定義錯誤時的處理。 | 必須明確定義「無 ACL＝不可見」；舊產品（Kendra、Q Business、Elastic）預設公開，是已知風險。 |
| 規範 | AuthZEN 已有 evaluation／batch／search 介面，但沒有 TTL 與一致性。 | 沒有通用標準；各產品自訂 ACL schema（Graph `acl`、Google `acl_info`、Bedrock `accessControlList`、Glean `permissions`）。 |

### D3. 讓 policy 權威留在客戶系統、由平台執行的做法

- **Connector 同步 ACL＋另同步 identity／groups：**幾乎所有產品都把文件 ACL 與群組成員分開同步，並在查詢時解析群組（Q Business identity crawler、Kendra `PutPrincipalMapping`、Graph external groups、Glean `/indexmembership`、Bedrock Managed KB 爬取 group membership）。Microsoft 明確建議不要把群組展開到每個 item 的 ACL。
- **Identity mapping：**Google identity mapping store 與 `externalEntityId`、Q Business User Store、Graph「必須轉換成 Entra 使用者」。Bedrock Managed KB 反其道而行，只用 email、不做 alias 對應，並把 email 對應錯誤列為客戶責任。
- **Source of truth 宣告：**Bedrock Managed KB 對 S3／Custom 來源明說「customer-provided metadata is the source of truth」，因此不做 real-time 驗證。這正是 3b 的責任劃分：Source 擁有 policy 權威，平台忠實執行最後一次收到的版本。
- **一次性設定：**Google（`aclEnabled`）、Quick（ACL 設定）、Q Business（ACL crawling 啟用後不可關閉）都把 ACL 模式設為建立時決定、不可事後切換，避免已索引內容的授權語意中途改變。

**對三個選項的對照（工程推論，非決議）：**選項 1 與 2 若要支撐 10M 文件的 Retrieval pre-filter，都需要把 relationship 狀態物化到搜尋端（OpenFGA `/changes`、SpiceDB Materialize 的指引）；差別在於 GAM 是否提供 changes／watch 或 lookup 能力（未知）。選項 3 若只採 3a，沒有產品先例支撐 search 過濾；若採 3b，則與業界主流相同，但平台要定義 ACL／identity 同步契約、新鮮度 SLO 與缺資料語意。3a 可作為 3b 之上的 top-k post-check 或單文件讀取檢查。

## 不應外推的結論

- 「Bedrock Managed KB／Quick 有 real-time 檢查」不代表它們以 live callback 過濾整個索引；real-time 只作用於 pre-filter 後的候選，且呼叫的是來源系統自己的 API，不是客戶依平台規範實作的 PDP。
- 「沒有產品提供客戶自備 PDP callback」是本次文件調查的缺席結果，各產品標註為 UNVERIFIED；不能當作「技術上不可行」。
- K8s、Envoy、API Gateway 的 webhook 先例是單一請求或 route 層級的授權，不能拿來證明逐文件搜尋過濾可行。
- AuthZEN resource search 的 interop 只有 20 筆記錄規模，且規格明說不保證完整與快照一致；不能當作 search-scale 的證據。
- Azure AI Search 原生 document-level access control 與 Google data source access control 仍是 preview；其行為（含 fail-closed 細節）在 GA 前可能改變。
- 「各產品都 fail-closed」不成立：Kendra、Q Business、Elastic connectors DLS 對缺 ACL 都是 fail-open。
- 官方多處自稱 ACL 過濾「not a security boundary」或「isn't an authentication or authorization control」（Bedrock Managed KB、Kendra），意思是使用者身分必須由上游驗證；不能把索引內過濾視為完整的授權系統。

## 未確認事項（UNVERIFIED）

- Bedrock Managed KB ACL 功能本身的 GA／preview 標示；2026-09 的 `CheckIngestedDocumentAcl`／`GetIngestedDocumentAcl` API 只見於搜尋摘要。
- Q Business、Kendra、Google、Microsoft Graph connectors、Glean 的過濾發生在檢索前或後；以及來源不可達時的查詢行為。
- Glean 是否在查詢時做 real-time permission check。
- Microsoft 365 Copilot federated connectors 的 GA 狀態。
- Kubernetes authorizer 不能逐物件過濾 list 結果的明文（目前是依 per-request 模型推論）。
- Trino OPA HTTP client timeout 預設、API Gateway REST API authorizer timeout。
- Zanzibar 論文中 zookie 與 Leopard 的逐字說明。
- GAM 是否提供 lookup／list、changes／watch 或 consistency token；這決定選項 1 能否支撐 Retrieval pre-filter，需向 GAM 團隊確認。
