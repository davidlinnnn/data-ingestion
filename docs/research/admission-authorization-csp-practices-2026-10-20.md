# Admission 授權、可見性與憑證範圍的業界實務

**研究日期：2026-10-19 至 2026-10-20（Asia/Taipei）。狀態：作為 #31 第一輪 grilling Q3 與第二輪 Q4–Q7 的決策依據；決議另記於 [admission 設計筆記](../design/knowledge-platform-admission.md)。**

背景：[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31)
在討論文件提交時，平台如何決定文件的讀者範圍（Resource binding）、提交與管理權限是否分開、錯誤回應如何避免洩漏存在性，以及 tenant／Source 是否由憑證推導。
本筆記只整理官方或可追溯的來源，並把「來源直接支持的事實」與「本平台的設計推論」分開。
CSP 的 index、data store、connection 或 shared drive 不視為本平台 Source／Resource 的同義詞。

**既有確認不重開：**#53 Q5（正常受理前須有可信 reader policy，缺少即拒收、無等授權狀態）、#53 Q12（binding 由有權者建立，caller 不能以任意放寬的目標作為授權證明）、10-18 的直接上傳／Valet Key 與 pilot service-account 決定。

## 1. Ingestion 時文件讀者如何指定

| 服務 | 寫入邊界的檢查 | 文件讀者如何決定 | 來源 |
|---|---|---|---|
| Amazon Q Business | 呼叫 `BatchPutDocument` 寫入指定 application／index | 呼叫者在 `accessConfiguration` 附 ACL；principal 為 USER 或 GROUP，存取為 ALLOW 或 DENY | [BatchPutDocument](https://docs.aws.amazon.com/botocore/latest/reference/services/qbusiness/client/batch_put_document.html) |
| Amazon Bedrock Knowledge Bases（custom data source） | 寫入指定 knowledge base／data source | “You provide a document's ACL through the `accessControlList` field on the document's `metadata`.” 官方另說明 “ACL awareness provides ACL-aware filtering, not authorization”，且 “cannot verify the authenticity of the user context you provide.” | [Document-level access controls](https://docs.aws.eu/bedrock/latest/userguide/kb-managed-ds-custom-acl.html) |
| Vertex AI Search | 匯入指定 data store | 匯入資料中的 `acl_info.readers.principals`（user 或 group）；每份文件最多 3,000 readers | [Data source access control](https://docs.cloud.google.com/generative-ai-app-builder/docs/data-source-access-control) |
| Azure AI Search push API（preview） | 寫入指定 index | 權限欄位 “just like any other document fields” 由呼叫者填入；`userIds: ["all"]` 表示 “Any user can access the document” | [Indexing ACLs using the push REST API](https://learn.microsoft.com/en-us/azure/search/search-index-access-control-lists-and-rbac-push-api) |
| Microsoft Graph connectors | `ExternalItem.ReadWrite.OwnedBy`：只能寫入 app 自己建立或被明確授權使用的 connection | App 為每個 external item 設定 ACL | [externalItem update](https://learn.microsoft.com/en-us/graph/api/externalconnectors-externalitem-update)、[permission 說明（第三方整理）](https://graphpermissions.merill.net/permission/ExternalItem.ReadWrite.OwnedBy) |

**來源直接支持：**
- 這些服務都在「寫入哪個容器」做一次授權檢查，ACL 由寫入者隨文件提供。
- Azure AI Search 明示呼叫者可把文件設為所有人可讀；Bedrock 明示其 ACL 功能是過濾而非授權，身分可信度由客戶應用負責。

**限制：**Q Business 與 Vertex AI Search 文件「未描述」寫入者能否指定這些 readers 的第二層檢查；這是未記載，不是官方明說不存在。

## 2. 動態容器、建立者與寫入權

| 服務 | 事實 | 來源 |
|---|---|---|
| Google Drive shared drive | 建立 shared drive 者自動成為 Manager | [Shared drive access levels](https://support.google.com/a/users/answer/12380484) |
| Google Drive shared drive | 加入檔案至少需要 Contributor | [Drive API roles](https://developers.google.com/workspace/drive/api/guides/ref-roles)、[Shared drive access levels](https://support.google.com/a/users/answer/12380484) |
| Google Drive shared drive | 檔案屬於組織而非個人；成員離開或帳號刪除後，其加入的檔案仍保留 | [Shared drives 說明](https://support.google.com/a/users/answer/7212025) |

| Google Drive | 自 2020-09-30 起，My Drive 的檔案只能有一個上層資料夾（包括 Drive API）；原本位於多處的檔案改為一個位置加上其他位置的 shortcut，Google 將此說明為簡化資料夾結構與分享模型 | [Shortcuts for Google Drive](https://workspaceupdates.googleblog.com/2020/03/shortcuts-for-google-drive.html)、[Simplifying folder structure and sharing models](https://workspace.google.com/blog/product-announcements/simplifying-google-drives-folder-structure-and-sharing-models) |

**來源直接支持：**由使用者動態建立的容器，建立者取得管理權；他人放入內容需要容器上的一般寫入角色，而非另一種專屬「綁定」權限。移除成員不會移除其已加入的內容。Drive 曾從多上層改為單一上層，以 shortcut 處理「出現在多處」的需求。

## 3. 資料寫入與管理權分離

| 服務 | 事實 | 來源 |
|---|---|---|
| Azure AI Search | *Search Index Data Contributor* 可匯入、更新、查詢 index 文件，但不能讀 index 定義；*Search Service Contributor* 可管理 index、indexer、data source 等定義，但不能存取 index 內容 | [Connect using roles](https://learn.microsoft.com/en-ca/azure/search/search-security-rbac) |

**限制：**上表 CSP 的 ACL 多掛在每份文件上，因此寫入文件的權限通常也能設定該文件 ACL；它們分離的是資料面與控制面，不是「寫文件」與「改讀者」。

## 4. Tenant isolation 與授權的關係

| 來源 | 事實 |
|---|---|
| [AWS SaaS Tenant Isolation Strategies](https://docs.aws.amazon.com/whitepapers/latest/saas-tenant-isolation-strategies/saas-tenant-isolation-strategies.html) | Tenant isolation 與一般安全機制分開；系統支援 authentication 與 authorization，但使用者通過驗證不代表系統已達成 isolation |
| [AWS SaaS Lens SEC 2](https://wa.aws.amazon.com/saas.question.SEC_2.en.html) | 將「防止跨 tenant 存取 tenant 資源」列為獨立的安全問題 |
| [Microsoft Entra claims validation](https://learn.microsoft.com/lt-lt/Entra/identity-platform/claims-validation) | 應檢查 token 的 `tid` 與資料所屬 tenant 相符；不得讓一個 tenant 的資料被另一個 tenant 存取；多 tenant app 須將 `iss` 與 `tid` 綁定 |

**來源直接支持：**tenant isolation 是授權之外的獨立邊界；tenant 由 token 決定並在資料存取時強制比對。

## 5. 不存在與無權限的錯誤回應

| 來源 | 做法 |
|---|---|
| [GitHub REST API troubleshooting](https://docs.github.com/en/enterprise-server@3.21/rest/overview/troubleshooting) | 存取 private resource 而未正確驗證時回 404 而非 403，避免確認 private repository 存在 |
| [Google AIP-211](https://google.aip.dev/211) | 先檢查授權再驗證請求；授權失敗一律回 `PERMISSION_DENIED`，訊息為 “Permission {p} denied on resource {r} (or it might not exist).”；若資源不存在而呼叫者有權讀取上層的 children，回 `NOT_FOUND`。AIP 認為「權限不足時先得到 NOT_FOUND」不直覺且增加除錯難度 |

**來源直接支持：**兩種主流做法都讓「不存在」與「存在但無權看到」無法區分；差別只在統一回 404 或統一回 403。

## 6. Tenant 與寫入範圍是否由憑證推導

| 類型 | 例子 | 範圍如何指定 | 來源 |
|---|---|---|---|
| Tenant | Microsoft Entra | Token 的 `tid` 決定 tenant | [Claims validation](https://learn.microsoft.com/lt-lt/Entra/identity-platform/claims-validation) |
| CSP 平台型 | Bedrock、Graph connectors、Azure AI Search | 目的容器在路徑中（例如 `/knowledgebases/{id}/datasources/{id}/documents`、`/external/connections/{id}/items`、index 名稱），再以 IAM 檢查 | [Bedrock Ingest API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html)、[externalItem update](https://learn.microsoft.com/en-us/graph/api/externalconnectors-externalitem-update) |
| 整合型 SaaS | GitHub App installation token | Token 只能存取該 installation 被授權的 repository；可再縮小範圍，但不能超出 installation | [create-github-app-token](https://redirect.github.com/actions/create-github-app-token) |
| 整合型 SaaS | Stripe | API key 決定帳號；平台代連結帳號操作時，以每個請求的 `Stripe-Account` header 指定 | [Making API calls for connected accounts](https://stripe.com/docs/connect/authentication) |

**來源直接支持：**tenant 由 token 決定是普遍做法。寫入範圍則有兩派：一個身分寫入多個容器的平台型 API 把容器放在路徑；一把憑證對應一個範圍的整合型 API 由憑證決定，需要代理多個範圍時才加選填 header。

## 對 #31 的設計推論

以下整節是**本平台的設計判斷**，不是 CSP 指定的標準。對應編號為 #31 第一輪 grilling 的 Q3 系列。

| 決策 | 依據 | 本平台選擇 | 與 CSP 的差異及理由 |
|---|---|---|---|
| Q3.1 受理檢查 | §1、§2 | 以 Source 為主體，檢查「S 可否把文件放進 R」；R 建在 S 底下或 R 的 maintainer 授權過 S | CSP 多數完全信任寫入者指定的 ACL；本平台需守住 #53 Q12，因此仍檢查 Resource 是否在 Source 的範圍內。Resource 為動態建立，故用 relation 判定而非平台設定清單 |
| Q3.3 兩種權限 | §3 | 提交權（Ingest API）與管理權（Resource API）分開，可在同一或不同憑證 | 本平台讀者掛在 Resource 而非文件，加上 Q3.4，只有提交權的憑證無法改變既有文件的讀者 |
| Q3.4 binding 變更 | §1（CSP 重送即覆蓋 ACL） | 重送不得改 binding；變更只走 Resource API | 刻意不同於 CSP，以保持 Q3.3 的權限分離 |
| Q3.5 撤銷 | §2 | 撤銷放入權只擋之後的提交；已放入的文件由 Resource maintainer 決定是否移除 | 與 Drive 行為一致 |
| Q3.7 錯誤回應 | §5 | 採 GitHub 做法：看不到一律 not found；呼叫者自身權限不足回 403 | 與 Protected Observation 一致；跨 tenant 自然歸入 not found |
| Q3.9 由憑證推導 | §4、§6 | API 不帶 tenant 與 Source；未來需要代理多個 Source 時，比照 `Stripe-Account` 加選填欄位 | 一把憑證對一個 Source，屬整合型模式 |
| Q3.12 Tenant 定義 | §4 | Tenant 不屬於 resource authorization；未來多 tenant 時作為授權之外的強制邊界 | 與 AWS SaaS 指引一致 |

## 7. 直接上傳的呼叫流程

| 服務 | 流程 | 來源 |
|---|---|---|
| Slack | `files.getUploadURLExternal` 取得 `upload_url` → 上傳 bytes → `files.completeUploadExternal`；未呼叫 complete 則上傳中止。原單次呼叫的 `files.upload` 已退役，官方理由是新方式更可靠，尤其是大檔 | [Changelog](https://docs.slack.dev/changelog/2024-04-a-better-way-to-upload-files-is-here-to-stay)、[completeUploadExternal](https://docs.slack.dev/reference/methods/files.completeUploadExternal) |
| OpenAI Uploads | Create Upload（宣告總 bytes，一小時後過期）→ Add Parts → Complete；完成時 bytes 數須與宣告相符 | [Uploads API](https://developers.openai.com/api/docs/api-reference/uploads) |
| Google Drive resumable | 初始化 session 取得 session URI → 上傳 bytes；最後一段完成傳輸 | [第三方整理](https://fast.io/resources/google-drive-resumable-upload.md)；正式文件前應改引 Google 官方文件 |

**來源直接支持：**直接上傳到 storage 的 API 普遍採「建立 → 上傳 → 完成」三步，OpenAI 並在完成時比對宣告值。

## 8. 上傳完整性檢查

| 來源 | 事實 |
|---|---|
| [Amazon S3: checking object integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity) | 支援 CRC-64/NVME、CRC-32、CRC-32C、SHA-1、SHA-256、MD5 等；S3 計算 checksum 與提供值比對並與物件一同保存 |
| [Amazon S3: presigned URLs](https://docs.amazonaws.cn/en_us/AmazonS3/latest/userguide/using-presigned-url.html) | SigV4 presigned URL 支援 SHA-256 等額外 checksum；SigV2 僅支援 MD5 |

**設計推論：**CRC 只偵測意外損毀，不能防止刻意替換；MD5／SHA-1 已有碰撞攻擊。因此採 SHA-256，並由平台在完成時自行驗證，不依賴 storage。

## 9. Idempotency

| 來源 | 事實 |
|---|---|
| [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests) | 保存第一次請求的狀態碼與 body，相同 key 回傳相同結果；參數不同時回錯誤；v1 API key 保存 24 小時；建議 V4 UUID |
| [IETF draft: Idempotency-Key header](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header) | HTTPAPI 工作小組草案（查閱時為 draft-07），尚非 RFC |
| [Bedrock IngestKnowledgeBaseDocuments](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html) | 以 `clientToken` 處理 request idempotency |

**設計推論：**與 Stripe 不同，本平台不保存 `503` 或 commit 前驗證失敗的結果，否則重試永遠得到相同的 `503`。

## 10. 外部版本號排序

| 來源 | 事實 |
|---|---|
| [Elasticsearch Index API: versioning](https://www.elastic.co:443/guide/en/elasticsearch/reference/6.4/docs-index_.html) | `version_type=external`：只有提供的版本號大於現存版本才寫入，否則版本衝突；適用於以外部資料庫為權威來源的同步 |

**設計推論：**本平台借用「較舊即拒」的排序防護，但不把外部版本號當作平台版本，因為平台有 Source Revision 與 Canonical Revision 兩層，且外部版本可能不存在或被重編。

## 11. 耐久受理與派送

| 來源 | 事實 |
|---|---|
| [AWS Prescriptive Guidance: transactional outbox](https://docs.aws.amazon.com/en_en/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) | 資料庫更新與 outbox 寫入在同一 transaction，解決 dual write；relay 可能重送，消費端須 idempotent |
| [Temporal: Workflow Id](https://docs.temporal.io/concepts/what-is-a-workflow-id)、[WorkflowIdReusePolicy](https://python.temporal.io/temporalio.common.WorkflowIDReusePolicy.html) | 同一 workflow ID 同時最多一個執行；`REJECT_DUPLICATE` 不允許重用已關閉 workflow 的 ID，拒絕時回 `WorkflowExecutionAlreadyStarted` |
| [PostgreSQL synchronous_commit](https://postgresqlco.nf/en/doc/param/synchronous_commit) | `on` 時 commit 等待同步 standby 回報已寫入耐久儲存；交易只在 primary 與所有同步 standby 同時損毀時遺失 |
| [Amazon RDS Multi-AZ](https://aws.amazon.com/rds/details/multi-az/) | 自動建立另一 AZ 的同步 standby 並自動 failover |
| [CloudNativePG: Replication](https://cloudnative-pg.io/docs/1.28/replication) | 以 `minSyncReplicas`／`maxSyncReplicas` 設定 quorum 同步複寫，operator 產生 `ANY q (...)`；所需 standby 不足時預設暫停寫入，以耐久性優先 |

## 12. 緩衝與流量控制

| 來源 | 事實 |
|---|---|
| [Azure Architecture Center: Queue-Based Load Leveling](https://learn.microsoft.com/azure/architecture/patterns/queue-based-load-leveling) | 在 task 與其呼叫的服務之間放置 queue 作為緩衝，平滑間歇性尖峰，並使收件與處理的故障互相隔離 |
| [PostgreSQL SELECT locking clause](https://www.postgresql.org/docs/current/sql-select.html) | `SKIP LOCKED` 可避免多個消費者存取 queue 型資料表時的鎖競爭 |

## 第二輪設計推論

以下為本平台設計判斷，對應 #31 第二輪 Q4–Q7。

| 決策 | 依據 | 本平台選擇 |
|---|---|---|
| Q4 提交流程 | §7 | 宣告 → 上傳 → 明確完成；SDK 包成一個呼叫 |
| Q4b 完整性 | §8 | SHA-256 加大小必填，平台完成時重算 |
| Q6 idempotency | §9 | 宣告用 `Idempotency-Key`，每 Source、24 小時；不保存 `503` |
| Q6b／Q6c 版本 | §10 | `source_version` 只作排序防護與來源證據，平台版本解耦 |
| Q7.1–Q7.3 受理與派送 | §11 | PostgreSQL＋outbox；workflow ID＝request ID；reconciler 補救 history 遺失 |
| Q7.2 耐久性 | §11 | RPO 0；pilot 上線前 CloudNativePG quorum 同步複寫 |
| Q7.4 緩衝 | §12 | Outbox 即 queue，dispatcher 控制預算與公平性 |

## 未查證或未採用

- Microsoft Graph `ExternalItem.ReadWrite.OwnedBy` 的範圍描述引自第三方整理站；正式文件撰寫前應改引 Microsoft Learn 的 permissions reference。
- Amazon Kendra 的 IAM action 分離未在本次查證，未列入依據。
- Google Drive resumable upload 的流程描述引自第三方整理，正式文件前應改引 Google 官方文件。
- 本筆記未驗證任何 live API 行為；所有結論來自查閱時的公開文件。
