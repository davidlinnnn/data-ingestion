# Inline content 與 storage reference ingestion

**研究日期：2026-10-18（Asia/Taipei）。狀態：AWS 官方機制調查；未新增本平台輸入模式或改變已確認 direct upload。**

問題：[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31) 討論 Bedrock `IngestKnowledgeBaseDocuments` 的 inline content／S3 location，是否代表 client 自己準備 S3，再讓知識平台取檔？

## AWS 的實際意思

| 形式 | Client 提交什麼 | 適用的 Bedrock data source |
|---|---|---|
| **Inline content** | JSON 直接帶文字，或以 Base64 表示文件 bytes 並附 MIME type；官方有 inline PDF 例子。這個 request 本身攜帶內容。 | Custom data source 支援；S3 data source 不支援 inline content。 |
| **S3 location** | 內容已在可存取的 S3 object，request 帶 S3 URI；custom 形式另可標示 bucket owner account。服務依權限讀取既有物件。 | Custom 與 S3 data source 都支援。 |

來源：[Direct-ingestion input restrictions／examples](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion-add.html)、[DocumentContent](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_DocumentContent.html)、[CustomS3Location](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_CustomS3Location.html)。

**因此「client 已有 S3，服務獲准後讀取」是可用情境，但不是強制每個 client 自建 bucket。**官方流程允許指定本帳號或不同帳號的 S3 location；重點是該物件已存在及存取設定成立。`IngestKnowledgeBaseDocuments` 是 ingestion，不是替 client 執行 S3 upload 的 API；AWS 也明示直接 ingestion 不會把相應變更自動回寫來源 S3。[Direct ingestion](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion-add.html)、[Relationship to S3 sync](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion.html)

## 誰有權呼叫、誰有權取 bytes

- 呼叫 direct-ingestion API 的 IAM principal 需要相應 Bedrock actions，並可限制到指定 knowledge base。[Caller permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion-prereq.html)
- Knowledge Base service role 的 S3 讀取權限是另一層：官方列出所需 `s3:ListBucket`／`s3:GetObject`，應限制到所需 buckets／prefixes；服務使用角色取得資料，不要求把 client 的 S3 access key 放進每筆 ingestion request。[Service-role permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-permissions.html)
- 跨帳號 S3 access 還需要 bucket 端的 resource policy 配合；若物件由適用的 customer-managed KMS key 加密，需安排 service role 的 decrypt 權限與 key policy。僅知道 URI 或有 Bedrock API permission，不會憑空獲得 S3／KMS access。[Cross-account and KMS policies](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-permissions.html)

這說明 reference ingestion 還包含受控的服務讀取能力，不只是 JSON 多一個 `uri` 欄位。具體資料位置、account、role 與 key policy 要相容；本次未替本平台採 AWS IAM、cross-account onboarding 或 KMS 架構。

## URI 不等於固定、可持續取回的 captured input

S3 `GetObject` 預設取得 current version，明確 `versionId` 才識別指定版本。Bedrock `CustomS3Location` 的文件提供 URI／bucket owner 欄位，不能由此推定 Bedrock 已承諾本平台要求的 Source Revision、固定 capture manifest、長期 custody 或每次 retry 都讀同一版本；本研究沒有驗證其 version-pinning 行為。[S3 GetObject version behavior](https://docs.aws.amazon.com/AmazonS3/latest/API/API_GetObject.html)、[CustomS3Location schema](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_CustomS3Location.html)

本平台在 processing `202` 前已要求固定完整 Capture Package、integrity 與可取回 custody；已在核准 custody 的 artifacts 不強制重新 upload／copy。這是 **#53 的既有契約**，不是從 Bedrock 的 S3 URI 或 202 推導出來。[Capture before admission](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L52)、[Existing artifacts／finalization](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L157)

## 值得借鏡的設計與取捨

以下是**工程判斷，尚未採納新模式**：

| 路徑 | 主要價值 | 需要承擔的工作 |
|---|---|---|
| Inline bytes 進平台 API | 小型、自含內容可以少一個 client storage 步驟 | API 承擔內容傳輸、大小／timeout／重試；收到完整 bytes 後仍要建立固定 capture 與 custody，不能省略 admission 驗證 |
| Reference to existing approved storage | 避免已有文件再經 client／API 傳一次；讓內容位置與處理命令分開 | 驗可讀版本、integrity、完整依賴、權限與 custody；需處理授權失效、物件替換／刪除與重試 |
| 已確認 platform-issued direct upload | Client 把 bytes 送到平台指定 storage，之後引用已驗證的 captured inputs | 平台管理 upload grant、finalization 與 custody；這本身已把大 bytes 傳輸和 admission command 分開，不必因 AWS inline 例子再新增同樣能力 |

最值得借用的是「一份文件描述可以指向內容，傳輸路徑與 ingestion command 分開」的介面思路；不是直接複製 AWS data-source 模型，也不是要求所有 caller 使用 S3。若另有 client 已管理可核准的固定物件，才比較 by-reference 的具體整合價值。Inline、external reference 是否需要成為額外入口，仍由本平台用例與責任邊界決定。

**限制：**只查官方文件與既有本平台契約；未建立 bucket／role／KMS、未發真實 ingestion request、未測 cross-account、物件覆寫或權限撤銷。沒有新增 endpoint、選 storage provider、改變 batch partial-admission 決策或宣稱 Bedrock 與本平台 acceptance 等價。
