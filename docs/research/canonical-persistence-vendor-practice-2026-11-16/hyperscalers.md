# Where hyperscaler document-processing products persist parsed content

Research date: 2026-11-16. Primary sources only (official docs, API references, architecture-center pages, vendor-owned sample repositories). Every claim carries a verbatim quote and its URL. This file reports practice only; it does not recommend a design.

Question: after parsing/OCR/layout/enrichment, where does the parsed, normalized content persist as the system of record: (a) object storage, (b) database rows/documents, (c) only inside a search/vector index, (d) a mix. And how do versioning, retention/TTL and per-document deletion work.

## Summary table

| Product | Where parsed content lives | DB holds content or pointers | Lifecycle mechanism | Source |
|---|---|---|---|---|
| AWS Textract (async) | Service-owned bucket for 7 days by default; customer S3 if `OutputConfig` is set | No DB | 7-day service retention; customer bucket lifecycle is the customer's | [api-async](https://docs.aws.amazon.com/textract/latest/dg/api-async.html) |
| AWS Bedrock Data Automation | Customer S3 only (async): JSON plus Markdown, CSV, figure crops, rectified page images | No DB; JSON holds `s3://` URIs to crops and page images | None stated by the service | [bda-output-documents](https://docs.aws.amazon.com/bedrock/latest/userguide/bda-output-documents.html) |
| AWS Bedrock Knowledge Bases | Chunk text + vectors in the vector store (customer-provisioned or KB-created); extracted images in customer S3 "multimodal storage destination" | Vector store holds chunk text; image payload in S3, referenced by a supplemental URI | Incremental sync removes deleted docs from the vector store; S3 lifecycle rule recommended only for transient data path | [kb-data-source-sync-ingest](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html), [kb-multimodal-create](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-multimodal-create.html) |
| AWS Kendra / Q Business | Inside the service-owned index (c) | n/a (index is the store) | Sync modes delete from index; Q Business deletion safeguard; `BatchDeleteDocument` | [Q connector-concepts](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html), [Kendra quotas](https://docs.aws.amazon.com/general/latest/gr/kendra.html) |
| AWS GenAI IDP Accelerator (guidance) | Results as JSON files in S3 output bucket (d) | DynamoDB tracking table holds status; content-vs-pointer not stated | `DataRetentionInDays` (default 365) for documents and tracking records; DynamoDB TTL for notifications | [guidance page](https://docs.aws.amazon.com/solutions/accelerated-intelligent-document-processing-on-aws/), [configuration.md](https://github.com/aws-solutions-library-samples/accelerated-intelligent-document-processing-on-aws/blob/main/docs/configuration.md) |
| AWS DynamoDB guidance (generic) | Large values in S3, identifier in DynamoDB (d) | Pointers | Application must clean orphaned S3 objects | [bp-use-s3-too](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-use-s3-too.html) |
| Azure AI Search knowledge store | Customer Azure Storage: Table (tables), Blob JSON (objects), Blob images (files) (a, or a+Table) | Table projections hold content rows; objects/files hold payload | Updated on re-run; indexer never deletes projections; owner deletes | [knowledge-store-concept-intro](https://learn.microsoft.com/en-us/azure/search/knowledge-store-concept-intro) |
| Azure AI Search enrichment cache | Customer Blob + Table, one per indexer | Cache, "isn't a backup" | Lifecycle bound to the indexer; deleted with it | [enrichment-cache-how-to-manage](https://learn.microsoft.com/en-us/azure/search/enrichment-cache-how-to-manage) |
| Azure Document Intelligence | Service temp storage 24 h; batch writes `*.ocr.json` per document to customer Blob | No DB | 24-h auto-delete; `Delete Analyze Result`; batch `overwriteExisting` flag | [data-privacy-security](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/document-intelligence/data-privacy-security), [batch-analysis](https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/batch-analysis) |
| Azure Content Understanding | Microsoft-managed storage up to 24 h; returned as JSON | No DB | 24-h auto-delete; `Delete Result` | [data-privacy](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/content-understanding/data-privacy) |
| Azure Arch Center: document classification | Source files in Blob; content + embeddings in AI Search index; Cosmos DB as metadata store (d) | Cosmos DB: type, location, page range (pointers) | Not stated (lifecycle policies mentioned for cost) | [automate-document-classification-durable-functions](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/automate-document-classification-durable-functions) |
| Azure Arch Center: PDF forms | JSON result files in Data Lake Storage and extracted data in Cosmos DB (both) | Cosmos DB holds the extracted field data (content) | Not stated | [automate-pdf-forms-processing](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/automate-pdf-forms-processing) |
| Azure Arch Center: content processing | Blob for source, intermediates and final structured outputs; Cosmos DB for results, scores, history (both) | Cosmos DB holds "processed results" (content) | Not stated | [multi-modal-content-processing](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/idea/multi-modal-content-processing) |
| Google Document AI | Online: response only, not persisted. Batch: Document JSON (optionally sharded) to customer GCS | No DB | Batch input deleted after processing, failsafe TTL 1 day | [security](https://docs.cloud.google.com/document-ai/docs/security), [DocumentOutputConfig](https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/DocumentOutputConfig) |
| Google Document AI Warehouse | Was a managed document repository; shut down 2025-01-16; migration target named as Cloud Storage | n/a | Deprecated | [release notes](https://docs.cloud.google.com/document-warehouse/docs/release-notes) |
| Vertex AI Search (layout parser) | Inside the service-owned data store; exportable via `getProcessedDocument` (c) | n/a | Parser changes apply to new imports only; no re-parse | [parse-chunk-documents](https://docs.cloud.google.com/generative-ai-app-builder/docs/parse-chunk-documents) |
| Vertex AI RAG Engine | Corpus in RagManagedDb (Google-managed Spanner in a Google tenant project) or customer vector DB | Vector DB; whether chunk text is stored there: not stated | Delete file / delete corpus operations; effect on vectors not stated | [use-ragmanageddb-with-rag](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/use-ragmanageddb-with-rag), [manage-your-rag-corpus](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/manage-your-rag-corpus) |
| Google Arch Center: RAG with AlloyDB | Raw data in GCS; embeddings in AlloyDB; where parsed chunks persist: not stated | Embeddings, prompts, config | GCS Object Lifecycle Management suggested for cost | [rag-capable-gen-ai-app-using-vertex-ai](https://docs.cloud.google.com/architecture/rag-capable-gen-ai-app-using-vertex-ai) |

## AWS

### Amazon Textract (asynchronous operations)

- Default store is service-owned and short-lived: "Results of asynchronous calls are encrypted and stored for 7 days in a Amazon Textract owned bucket by default, unless you specify an Amazon S3 bucket using an operation's `OutputConfig` argument." — https://docs.aws.amazon.com/textract/latest/dg/api-async.html
- Customer-owned copy: "With `OutputConfig` enabled, you can set the name of the bucket the output will be sent to, and the file prefix of the results, where you can download your results." — same page
- Retrieval window: "Results can be retrieved only up to 7 days of job initialization time." — same page
- Size: results are paged: "The default value for `MaxResults` is 1,000." — same page
- Versioning/deletion: nothing stated beyond the 7-day window.

### Amazon Bedrock Data Automation (BDA)

- Output goes to customer S3: "Async InvokeDataAutomationAsync API: JSON output for Async API is S3 only." — https://docs.aws.amazon.com/bedrock/latest/userguide/bda-output-documents.html
- Files alongside JSON: "JSON+files … gives you a text file for the overall text extraction, a markdown file for the text with structural markdown, and CSV files for each table that's found in the text. Figures located inside a document will be saved as well as figure crops and rectified images. These outputs are located in `standard_output/{{logical_doc_id}}/assets/` in your output folder." — same page
- The JSON references images by URI, not inline: table/figure entities carry `"crop_images":["s3://bucket/prefix.png", …]` and pages carry `"asset_metadata":{"rectified_image":"s3://bucket/prefix.png", …}` — same page
- Status call returns a location: "If the job is complete, it returns "Success" along with the S3 location of the results." — https://docs.aws.amazon.com/bedrock/latest/userguide/bda-using-api.html
- Retention/versioning/deletion: not stated in the pages read.

### Amazon Bedrock Knowledge Bases

- Parsers store extracted figures as files in customer S3: "These parsers can also extract these figures, charts, tables, and images and store them as files in an S3 destination that you specify during knowledge base creation. During knowledge base retrieval, these files can be returned in the response or in source attribution." — https://docs.aws.amazon.com/bedrock/latest/userguide/kb-advanced-parsing.html
- Multimodal storage destination: "configure the **Multimodal storage destination** by specifying an Amazon S3 bucket where processed files will be stored for retrieval. Knowledge Bases will store images parsed into a single Amazon S3 bucket with a folder created .bda for easy access." — https://docs.aws.amazon.com/bedrock/latest/userguide/kb-multimodal-create.html
- Chunk text lives in the vector store, mapped by field: "`<text-field>` - Field name for storing text content"; "`<metadata-field>` - Field name for storing metadata" — same page (OpenSearch Serverless example)
- Per-document deletion via sync: "Each time you add, modify, or remove files from your data source, you must sync the data source so that it is re-indexed to the knowledge base. Syncing is incremental, so Amazon Bedrock only processes added, modified, or deleted documents since the last sync." and table row "Document deleted | The document is removed from the vector store." — https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html
- Versioning: a changed document is replaced, not versioned: "Content or metadata changed | The document is re-ingested (re-parsed, re-chunked, re-embedded, and re-indexed)." — same page
- S3 lifecycle used only for transient data, and explicitly not for the persisted images: "Amazon Bedrock stores transient data in your multimodal storage destination and attempts to delete it after processing is completed. We recommend applying a lifecycle policy on the transient data path…" and "Do not apply lifecycle policies to the entire bucket or to the "aws/" prefix, as this will delete your multimodal content and cause retrieval failures." Prefix: `aws/bedrock/knowledge_bases/{{knowledge-base-id}}/{{data-source-id}}/transient_data`, expiry 1 day. — https://docs.aws.amazon.com/bedrock/latest/userguide/kb-multimodal-troubleshooting.html
- Size limits: "Maximum 1.5 GB per video file, 1 GB per audio file (Nova Multimodal Embeddings), or 1.5 GB per file (BDA)"; "Maximum 15,000 files per job (Nova Multimodal Embeddings) or 1,000 files per job (BDA)" — same page
- Whether sync-on-delete also removes the document's extracted images from the multimodal storage bucket: not found.

### Amazon Kendra and Amazon Q Business

- Content lives in the service index; quotas cap extracted text per file: "Extracted text size | Each supported Region: 5 Megabytes | No | The maximum extracted text size, in MB, from a file that can be ingested." and "File size | … 50 Megabytes" — https://docs.aws.amazon.com/general/latest/gr/kendra.html
- Q Business sync modes and deletion: "**New, modified, or deleted content sync** – Sync only new, modified, and deleted documents." and the deletion safeguard: "If the number of documents to be deleted exceeds the configured threshold percentage, the delete phase will be skipped during a sync job, and no documents will be deleted from the index." — https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html
- Field size: "All fields and attributes have a size limit of 2048 characters." — same page
- Status: "Amazon Q Business is no longer open to new customers." — same page
- Whether deleted content is purged from backups/caches: not found.

### AWS guidance for intelligent document processing

- Accelerated IDP guidance: "Final results and evaluation reports are stored as JSON files in the Amazon S3 output bucket." and "The AWS AppSync API maintains document status in the DynamoDB tracking table" — https://docs.aws.amazon.com/solutions/accelerated-intelligent-document-processing-on-aws/
- Retention parameter in the vendor-owned sample repo: `DataRetentionInDays` — "Set retention period for documents and tracking records (default: 365 days)"; for notifications "DynamoDB TTL removes it afterwards" — https://github.com/aws-solutions-library-samples/accelerated-intelligent-document-processing-on-aws/blob/main/docs/configuration.md (read first 100,000 of ~146,650 characters; the rest not read)
- Whether the tracking table holds content or pointers: architecture doc does not state it — https://github.com/aws-solutions-library-samples/accelerated-intelligent-document-processing-on-aws/blob/main/docs/architecture.md
- IDP on AWS (AgentCore) guidance: "The Lambda function creates a tracking job in Amazon DynamoDB" and "Throughout processing, the Orchestrator tracks document progress and updates job status in Amazon DynamoDB. Upon completion, processed documents are stored in Amazon S3 for downstream processing and integration." — https://docs.aws.amazon.com/solutions/intelligent-document-processing-on-aws/

### DynamoDB large-item guidance (the size limit that drives the split)

- "Amazon DynamoDB limits the size of each item that you store in a table to 400 KB … You can also store the item as an object in Amazon Simple Storage Service (Amazon S3) and store the Amazon S3 object identifier in your DynamoDB item." — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-use-s3-too.html
- Stated cost of the split: "DynamoDB doesn't support transactions that cross Amazon S3 and DynamoDB. Therefore, your application must deal with any failures, which could include cleaning up orphaned Amazon S3 objects." — same page
- Alternatives offered on the same page: compression ("the downside is that the compressed attribute values are not useful for filtering") and vertical partitioning into an item collection.

## Azure

### Azure AI Search knowledge store

- Physical form and owner: "Physically, a knowledge store is Azure Storage, either Azure Table Storage, Azure Blob Storage, or both. Any tool or process that can connect to Azure Storage can consume the contents of a knowledge store. There's no query support in Azure AI Search for retrieving content from a knowledge store." — https://learn.microsoft.com/en-us/azure/search/knowledge-store-concept-intro
- Projection roles: "`tables` project enriched content into Table Storage. Define a table projection when you need tabular reporting structures for inputs to analytical tools…"; "`objects` project JSON document into Blob storage. The physical representation of an `object` is a hierarchical JSON structure that represents an enriched document."; "`files` project image files into Blob storage. A `file` is an image extracted from a document, transferred intact to Blob storage." — same page
- Usage table: Objects are "Used when you need the full JSON representation of your data and enrichments in one JSON document."; Files are "Used when you need to save normalized, binary image files." — https://learn.microsoft.com/en-us/azure/search/knowledge-store-projection-overview
- Relatedness by URL: "You could project the text to tables and the images to binary files, and both tables and objects have a column/property containing the file URL." — same page
- Lifecycle (overwrite, no versions): "any edits will be overwritten on the next pipeline invocation, assuming the document in source data is updated." — concept-intro page
- Deletion is not propagated: "Although an indexer creates and updates structures and content in Azure Storage, it doesn't delete them. Projections continue to exist even when the indexer or skillset is deleted. As the owner of the storage account, you should delete a projection if it's no longer needed." — concept-intro page; and "They won't be deleted when the indexer or the search service itself is deleted." — projection-overview page
- Size limits: points to Table storage limits: "check … Scalability and performance targets for Table storage to make sure your data requirements are within Table storage documented limits." — projection-overview page

### Azure AI Search enrichment cache (preview)

- "It preserves content between runs so that only changed skills and documents require reprocessing. It isn't a backup of skillset outputs, indexer state, or indexed documents." — https://learn.microsoft.com/en-us/azure/search/enrichment-cache-how-to-manage
- Why: "Although caching is billable (it uses Azure Storage), the overall cost of enrichment is reduced because the costs of storage are less than image extraction and AI processing." — same page
- Where: "Physically, the cache is stored in a blob container and tables in your Azure Storage account, one per indexer." — same page
- Lifecycle: "The indexer manages the cache lifecycle. If you delete an indexer, you also delete its cache." — same page
- Per-document invalidation: "When you reset a document, the indexer invalidates the cache for that document." — same page

### Azure Document Intelligence

- Service retention: "The service stores submitted input data and analyze results for 24 hours after an analysis operation completes. Document Intelligence automatically deletes both after this retention period. To delete the data earlier, call the Delete Analyze Result API." — https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/document-intelligence/data-privacy-security
- Batch writes to customer Blob, one file per input: "The results are available at `resultUrl`, which is created by combining `resultContainerUrl`, `resultPrefix`, `input filename`, and `.ocr.json` extension." — https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/batch-analysis
- Batch limits and retention: "The maximum number of document files that can be in a single batch request is 10,000." and "Batch operation results are retained for 24 hours after completion. … The input documents and respective result files remain in the storage containers provided." — same page
- Overwrite rather than version: "Set the `overwriteExisting` Boolean property to `False` and prevent overwriting any existing results for the same document." — same page

### Azure Content Understanding

- "Input documents, intermediate representations, and final results are written to secure Microsoft-managed storage and retained for up to 24 hours. After that, they're automatically deleted." and "Use the `Delete Result` operation to delete data associated with a request before the 24-hour retention period ends." — https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/content-understanding/data-privacy
- No persistent store for results is offered by the service; persistence is the caller's.

### Azure Architecture Center references

- Document classification (Durable Functions): "The *metadata store* activity function saves the document type, location, and page range information for each document in an Azure Cosmos DB store." and "The function writes the embeddings and associated content to a vector-enabled index in AI Search and adds a correlation ID to each search document so that search results map back to the corresponding document metadata in Azure Cosmos DB." Alternative: "Azure SQL Database is another persistent storage option for document metadata and information." Why Cosmos: "To facilitate global distribution, this solution stores metadata in Azure Cosmos DB." — https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/automate-document-classification-durable-functions
- PDF forms processing: "It creates a JSON data file that contains the response data and stores the file to a third container in Data Lake Storage." and "The forms processing logic app sends the processed data to Azure Cosmos DB" — Cosmos DB is "used to store the extracted insights from each PDF document. The information is utilized by Power BI" — https://learn.microsoft.com/en-us/azure/architecture/ai-ml/architecture/automate-pdf-forms-processing
- Content processing (Content Understanding): "stores processed results, confidence scores, schema mappings, and historical processing data for audit trails and continuous improvement in Azure Cosmos DB" and "uses Azure Blob Storage to store source documents, intermediate processing artifacts, and final structured outputs for reliable data persistence and retrieval." — https://learn.microsoft.com/en-us/azure/architecture/ai-ml/idea/multi-modal-content-processing
- Cosmos DB item size: "Maximum size of an item | 2 MB (UTF-8 length of JSON representation)"; "Large document sizes up to 16 MB are supported with Azure Cosmos DB for MongoDB only." — https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits

## Google Cloud

### Document AI

- Online vs batch: "Online (synchronous) requests let you send a single document for processing." / "Batch (asynchronous) requests let you send multiple documents in a single request." Batch operation metadata "points to the Cloud Storage bucket where the processed results are stored." "Batch processing allows a maximum of 1,000 files per request." — https://docs.cloud.google.com/document-ai/docs/send-request
- Output config: `gcsOutputConfig` "Output config to write the results to Cloud Storage."; `gcsUri` "The Cloud Storage uri (a directory) of the output."; `shardingConfig` "Specifies the sharding config for the output document." with `pagesPerShard` and `pagesOverlap`. — https://docs.cloud.google.com/document-ai/docs/reference/rest/v1/DocumentOutputConfig
- Sharded output is recombined client-side: Toolbox can "Combine fragmented Document JSON files from Batch Processing into a single "wrapped" document." — https://docs.cloud.google.com/document-ai/docs/handle-response
- Service retention: online data "is processed in memory, encrypted in flight, and not persisted to disk"; batch: "the stored document is typically deleted immediately after the processing", with a failsafe TTL of one day. — https://docs.cloud.google.com/document-ai/docs/security

### Document AI Warehouse

- "Document AI Warehouse is deprecated and will no longer be available on Google Cloud after January 16, 2025." and "To safeguard your data, migrate any documents currently saved in Document AI Warehouse to an alternative like Cloud Storage." — https://docs.cloud.google.com/document-warehouse/docs/release-notes
- What it stored: its REST `Document` resource offers a raw-document union of a Cloud Storage path or inline bytes (from search result summary of https://docs.cloud.google.com/document-warehouse/docs/reference/rest/v1/Document; page itself not opened — unverified).

### Vertex AI Search (Agent Search) layout parser

- Parsed and chunked documents are held by the data store and exported by API: "Getting parsed documents in JSON can be helpful if you need to upload the parsed document elsewhere." (`getProcessedDocument` with `PARSED_DOCUMENT` or `CHUNKED_DOCUMENT`) — https://docs.cloud.google.com/generative-ai-app-builder/docs/parse-chunk-documents
- No re-versioning on parser change: "the updated parser settings only apply to new documents imported to the data store." / "Documents already in the data store are not re-parsed with the new settings." — same page
- Limits: "The OCR processor can parse the first 500 pages of a PDF file. Pages beyond the 500 limit aren't processed." — same page
- Effect of document delete/purge on processed output: not found.

### Vertex AI RAG Engine

- RagManagedDb: "an enterprise-ready vector database used to store and manage vector representations of your documents"; "a Google-managed Spanner instance that's provisioned in a Google-tenant project" — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/use-ragmanageddb-with-rag
- Alternatives: Vector Search, Pinecone, Weaviate, Feature Store; for those "you are responsible for the lifecycle and scalability of your vector database." — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/vector-db-choices
- Corpus: "A corpus, also referred to as an index, is a collection of documents or source of information." Operations include "Delete a file from the RAG corpus". "Concurrent operations on corpora aren't supported." — https://docs.cloud.google.com/vertex-ai/generative-ai/docs/rag-engine/manage-your-rag-corpus
- Whether chunk text is stored in RagManagedDb, and what file deletion removes: not stated.

### Google Cloud Architecture Center

- RAG with AlloyDB: "Data is uploaded to a Cloud Storage bucket"; "The function stores the embeddings in an AlloyDB for PostgreSQL" (pgvector); AlloyDB row: "Vectorized embeddings of the data used for RAG." Where parsed chunks persist: not stated. Object Lifecycle Management suggested for storage cost. — https://docs.cloud.google.com/architecture/rag-capable-gen-ai-app-using-vertex-ai
- A Google reference stating GCS vs BigQuery vs Firestore for parsed Document JSON: not found.

## Not found / unverified

- Bedrock KB: whether sync-on-delete also deletes that document's extracted images under the `aws/` prefix of the multimodal storage destination.
- BDA: any service-side retention or versioning of outputs.
- Kendra / Q Business: purge of deleted content from backups or caches.
- GenAI IDP Accelerator: whether the DynamoDB tracking table holds extracted content or only pointers; S3 lifecycle settings (last ~46,650 characters of configuration.md not read).
- Document AI: exact Cloud Storage output path layout and shard naming (handle-response page read; batch-processing page not opened).
- Document AI Warehouse `Document` REST reference: not opened; raw-document field description taken from a search summary only.
- Vertex AI Search: effect of `documents.delete` / `purge` on processed (parsed/chunked) output.
- Vertex AI RAG Engine: whether chunk text lives in RagManagedDb; deletion semantics for vectors when a file or corpus is deleted.
- Google reference architecture naming BigQuery or Firestore as the store for parsed documents.
- Azure Architecture Center pages: no retention, TTL or per-document deletion guidance found.
