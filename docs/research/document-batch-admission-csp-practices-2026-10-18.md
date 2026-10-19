# 單文件與多文件提交的 CSP API 實務

**研究日期：2026-10-18（Asia/Taipei）。狀態：保留官方來源調查與設計比較；已確認共同 `items[1..N]` 提交契約，詳細 API、範圍與受理原子性仍未定。**

背景：[Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31) 正討論是否同時提供單文件與批次提交，以及 batch 與 Corpus／Resource 的關係。本筆記只查四個服務例子；不把其知識庫、index、branch 或 storage container 視為本平台 Corpus／Resource 的同義詞。

**既有確認不重開：**batch 須報告逐項 outcomes 與 aggregate progress，不能把部分失敗冒充整體成功；HTTP validation、partial admission／atomicity 仍未定。這不預選 endpoint、batch entity 或 storage schema。[Overall Q7 handoff](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843539018)

**後續確認：**使用者同意共同提交契約接受 `items[1..N]`，單份是一個 item；Batch 提供分組與彙總，每份文件保留自己的身分、治理關聯與結果。決議記於 [admission 設計筆記](../design/knowledge-platform-admission.md#confirmed-single-and-batch-submission-contract-on-2026-10-18)。下方候選比較保留作為決策依據，不再把單份／多份共同契約列為未決；19 份合法、1 份無效時的部分受理問題仍未回答。

## 可支持的結論

官方 API 同時出現「同一 API 接一筆或多筆」與「單筆／bulk 分開 API」兩種設計；多筆操作可有逐文件結果，不代表整批交易。下表提供具體證據。

**本研究的設計推論：**batch 可以是一次提交／操作追蹤的分組，而文件仍保留自己的身分與業務關聯；但是否允許跨 Source、Corpus 或 Resource，是本平台的範圍與授權決策。CSP 的 batch 範例多綁一個原生目的地，不能直接證明跨範圍 grouping 已安全或必要。

## 四個官方例子

| 服務與 API 形狀 | 實際傳入內容 | 單次 request 的共同 scope | 狀態、部分失敗與重試界線 |
|---|---|---|---|
| **AWS Bedrock**：`PUT /knowledgebases/{knowledgeBaseId}/datasources/{dataSourceId}/documents`，`documents[]` 可接一筆或多筆。[Ingest API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html) | S3 data source 使用 S3 location；custom data source 可用 S3 location 或 inline text／bytes。不是一律只收 refs，也不是任意多檔 multipart upload。[Input restrictions](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion-add.html) | 一個 knowledge base＋一個 data source；每筆 `dataSourceType` 須與指定 data source 相符。[Ingest API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html) | `202` 帶逐文件 `documentDetails`，包含 identifier、status、reason、updatedAt；另可查文件狀態。`clientToken` 用於 request idempotency；不能只憑頂層 202 推定所有文件處理成功。[Ingest](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html)、[Get status](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_GetKnowledgeBaseDocuments.html) |
| **Azure AI Search**：同一 Documents Index／`IndexDocuments` 路徑可推一筆或多筆；最多 1,000 文件或 16 MB request payload，先到者為限。[Push input](https://learn.microsoft.com/en-us/azure/search/search-what-is-data-import)、[Limits](https://learn.microsoft.com/en-us/azure/search/search-limits-quotas-capacity) | 符合 index schema 的 **JSON documents**，每筆可指定 upload／merge／delete 等 action；不是把原始 PDF bytes 交給這個 API 自動解析。[Push input](https://learn.microsoft.com/en-us/azure/search/search-what-is-data-import) | 一個指定 index。業務資料可來自不同來源，但仍須符合該 index 的 schema。[Load an index](https://learn.microsoft.com/en-us/azure/search/search-how-to-load-search-index) | 全部成功為 HTTP 200，部分失敗為 207；response 含逐筆 key、status、statusCode／error。官方要求處理 207 的逐筆重試，而非把整批當作已全部成功。[Response semantics](https://learn.microsoft.com/en-us/azure/search/search-how-to-load-search-index)、[Retry example](https://learn.microsoft.com/en-us/azure/search/tutorial-optimize-indexing-push-api) |
| **Azure Document Intelligence**：單筆 `/{modelId}:analyze` 與批次 `/{modelId}:analyzeBatch` 分開。[Single analyze](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/analyze-document?view=rest-aiservices-v4.0%20%282024-11-30%29)、[Batch analyze](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/analyze-batch-documents?view=rest-aiservices-v4.0%20%282024-11-30%29) | 單筆可傳 `urlSource`／`base64Source`；批次傳 Blob container＋prefix，或 Blob file list；另指定 result container。批次分析現有 storage files，不是一次把所有 PDF bytes 放進該 batch JSON。 | 同一 endpoint／modelId；一份 input source selector 與 output container。這是分析工作與 storage 選取範圍，不是跨知識庫 publication 契約。[Batch request](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/analyze-batch-documents?view=rest-aiservices-v4.0%20%282024-11-30%29) | `202`＋Operation-Location；查 batch result 可得逐文件 succeeded／failed／skipped、錯誤及結果 URL。官方範例頂層 succeeded 同時包含失敗文件；不能把整體 job completion 當成所有文件成功。[Batch result](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/get-analyze-batch-result?view=rest-aiservices-v4.0%20%282024-11-30%29) |
| **GCP Discovery Engine v1**：`POST /v1/{parent}/documents` 建一筆；`POST /v1/{parent}/documents:import` 批次 import，回 long-running Operation。[Create](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/create)、[Import](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/import) | Import 可用 `inlineSource.documents[]` 或 `gcsSource` 等來源；GCS `dataSchema=document` 讀 JSONL Document，`content` 讀已存在的 GCS 檔案。Document content 也可含小型 inline rawBytes；GCS import 本身不負責先把本地檔案上傳進 GCS。[GCS source](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/GcsSource)、[Content](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents#Content) | `parent` 是一個 datastore branch。單筆／bulk 共用這個目的地，不是一個 request 任選多個 datastore。[Create／Import](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/import) | Import 可有成功子集；metadata 有 success／failure／total counts，完成 response 有 error samples 與 error destination。完整錯誤可寫到指定 GCS prefix。[Import contract](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/import)、[Error configuration](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/ImportErrorConfig) |

### 官方文件差異與 retry 注意事項

- **Bedrock 數量上限不作本平台設計依據：**查閱時 API Reference 的 array 定義是 1–10，User Guide 卻寫 API 最多 25。兩份官方文件不一致；本次只採信其可接單筆／多筆的形狀，未以 live API／SDK 驗證上限。[API definition](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_IngestKnowledgeBaseDocuments.html)、[User Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion-add.html)
- **Azure AI Search：**207 要檢查逐筆原因；可重試的暫時錯誤與需修正 payload／容量的錯誤不同。SDK 對整個 request 的自動重試，不等於自動替應用處理所有部分失敗。[Status/retry guidance](https://learn.microsoft.com/en-us/azure/search/search-how-to-load-search-index)、[207 retry example](https://learn.microsoft.com/en-us/azure/search/tutorial-optimize-indexing-push-api)
- **Document Intelligence：**逐文件結果可支援挑出失敗檔案重新送分析；這是依 file-list 與 result contract 得到的操作推論，不是從頂層 202 推導 request-level exactly-once，也不保證重送整批沒有副作用。[Batch request](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/analyze-batch-documents?view=rest-aiservices-v4.0%20%282024-11-30%29)、[Per-file results](https://learn.microsoft.com/en-us/rest/api/aiservices/document-models/get-analyze-batch-result?view=rest-aiservices-v4.0%20%282024-11-30%29)
- **Discovery Engine：**create 的既有 document ID 會得到 ALREADY_EXISTS；import 預設 INCREMENTAL 可更新既有 ID，FULL 則可能刪掉來源清單未包含的文件。這不是純粹換個 envelope 的同義 API；選擇性 retry 不應誤用 FULL。穩定 ID 有助 recovery，但不自行構成 exactly-once request。[Create](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/create)、[Import modes](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/projects.locations.collections.dataStores.branches.documents/import)、[Reconciliation modes](https://docs.cloud.google.com/generative-ai-app-builder/docs/reference/rest/v1/ReconciliationMode)

## 對本平台 API 的比較與後續選擇

以下整節是**設計判斷**，不是 CSP 指定的標準。

先區分兩件事：

1. **Byte transfer：**client 把每份文件／附件送到 storage。一次使用者操作選十份 PDF，不必表示十份 bytes 共用一個 HTTP request。
2. **Admission command：**client 提交一筆或多筆固定文件／package 描述與處理意圖。這可以批次化，仍不必把文件永久歸入同一 Corpus／Resource，也不必共用 parser 的執行或重試單位。

| 方案 | 優點 | 額外承擔與適用條件 |
|---|---|---|
| **同一 admission API，`items[1..N]`** | 一份 contract 同時表達單筆與多筆；client 不必維護兩種業務提交流程 | 仍須決定 envelope／item validation、共用 scope、逐項身分與結果、partial admission、回覆遺失和 selective retry；「同 endpoint」不免除這些工作 |
| **單筆與 batch 分開 API** | 可讓 bulk 有不同的來源清單、operation status 或較大工作負載；當兩者交付與觀測模式不同時清楚 | 若兩者只是 items 數量不同，容易重複契約與維護；應共用既有內部 admission 規則，避免結果語意分歧 |
| **只做單筆 API，client loops／有限 concurrency** | Server contract 最小，每項 acceptance／retry 容易定位 | Client 承擔分組狀態、節流與部分失敗；仍須供應已要求的逐項 outcomes／aggregate progress，client loops 本身不提供耐久的整批查詢契約 |

**比較結果與後續選擇：**沒有證據支持「一定要兩個 API」或「batch 一定是全有全無」。使用者已選擇共同 `items[1..N]` 契約；另外兩種方式保留作為比較背景。這項選擇未決定 partial admission、實際 HTTP routes 或跨範圍授權。

### Corpus／Resource 與 batch 的邊界

業務關聯可以跟著文件描述保留，不代表 server 必須讓任意 scope 混在同一 request。可選「整批同一已授權目的 scope」或「逐 item 明確 scope」；選擇應由 client 用例、授權與錯誤語意決定。CSP 的 single index／KB＋data source／datastore branch 只是其產品邊界，不能當作本平台要限制或允許跨 Corpus／Resource 的證明。

尤其要分開：批次命令的 grouping、每份固定 captured package、Source／Asset 身分、Corpus membership、Resource authorization binding，以及後續 projection 的多文件輸入。是否同批不是讀取 grant 或 publication 的替代條件。

## 下一輪只需收斂的選擇

- 已要求逐項 outcomes 與 aggregate progress；這批項目的關聯、觀測／更新時間與查詢方式如何呈現？是否需要平台耐久保存 grouping，不由 UI 一次選多檔或 items 陣列自行決定。
- 同一 request 是否需要不同 Corpus／Resource／Source scope？若需要，怎樣呈現逐項 authority／invalid item，而不讓一份錯誤文件抹掉其他已接受結果？
- 希望 invalid item 令整個 envelope 拒收，或只拒該項？這是 admission atomicity 的獨立選擇，不由 batch 一詞或 CSP API 名稱回答。

**限制：**只查官方文件，未建立 CSP 資源、送真實 API、量測延遲／吞吐或估服務成本；未替本平台選 batch size、endpoint 或跨範圍授權。這些服務的 202／operation status 不能證明本平台 durable acceptance、30-day query retention 或 Temporal outage 保護已實作。
