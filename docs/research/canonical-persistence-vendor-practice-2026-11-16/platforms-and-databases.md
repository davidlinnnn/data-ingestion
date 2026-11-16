# Persisting parsed document content: data platforms, pipeline vendors, database vendors

Research date: 2026-11-16. Primary sources only (official docs, vendor engineering blogs, the PostgreSQL wiki). Quotes are short and verbatim from the page fetched on that date. This file reports practice and vendor advice; it makes no recommendation.

## Summary

| Product | Where parsed content lives | DB holds content or pointers | Lifecycle mechanism | Source |
|---|---|---|---|---|
| Databricks `ai_parse_document` | `VARIANT` column in a Delta table (Parquet files + transaction log on cloud object storage); page images in a Unity Catalog volume (files) | Table holds the parsed JSON itself; images are files in a volume, referenced by `image_uri` | Every write is a table version; `DELETE` + `VACUUM` (default 7-day threshold) to physically remove; `REORG ... APPLY (PURGE)` with deletion vectors | docs.databricks.com (ai_parse_document, delta, delta-vacuum, gdpr-delta, volumes) |
| Databricks FILE type (Beta) | Bytes in a volume; row holds a reference | Pointer (`uri`, `size`, `content_type`, `checksum`) | Same as Delta | docs.databricks.com/aws/en/ldp/tutorial-file-pipelines |
| Snowflake `AI_PARSE_DOCUMENT` | Returned as a JSON string / VARIANT in a query; source files stay in stages (internal or external S3/GCS/Azure); docs show no persisted-result pattern | Function output is content (images inline as base64); source files referenced via FILE / directory tables | Not stated for results | docs.snowflake.com |
| Unstructured (platform) | Whatever destination is chosen: 28 connectors, including S3, Delta Tables in S3, MongoDB, PostgreSQL, Elasticsearch, OpenSearch, vector DBs | DB destinations receive element rows/documents with text (images as `image_base64` in metadata) | `record_id` lets the connector do "intelligent document overwrites" (MongoDB); nothing on deletion | docs.unstructured.io |
| LlamaIndex / LlamaCloud | Framework: docstore of `Node` objects (MongoDB, Redis, Firestore, Postgres variants, ...); LlamaParse: vendor-side cache | Docstore holds chunk content | LlamaParse caches files / parsed results 48 h then deletes; indexed data kept for the agreement term | developers.llamaindex.ai |
| docling-serve | Not a system of record: results held in a scratch dir / Redis for a TTL, or pushed to S3/Azure via presigned targets | n/a | Single-use results, 300 s removal delay, RQ results TTL 4 h, Ray metadata TTL 7 d | github.com/docling-project/docling-serve |
| MongoDB | Documents up to 16 MiB; GridFS above that; vendor blog advises blobs in object storage with metadata + reference in MongoDB | Both offered; blog advises pointers for blobs | TTL index: single date field, background deletion every 60 s; versioning by app (store versions, flip a "latest" field) | mongodb.com/docs, mongodb.com/company/blog |
| PostgreSQL | `text`/`jsonb`/`bytea` via TOAST (1 GB per value) or large objects (4 TB); wiki lists trade-offs both ways | Both possible; wiki gives pros/cons for each | No native row TTL found; partition `DROP`/`DETACH` for bulk deletes, otherwise `DELETE` + VACUUM | postgresql.org/docs, wiki.postgresql.org |
| Elasticsearch | `_source` stores the original JSON | Content | Not covered here | elastic.co |
| Amazon S3 | Objects | n/a | Lifecycle expiration by prefix, tags, size; days since creation rounded to next midnight UTC; asynchronous; 1,000 rules per bucket | docs.aws.amazon.com |
| MinIO | Objects | n/a | ILM expiry by days, `--prefix`, `--tags`, noncurrent-version expiry; scanner-based, asynchronous; community repo archived, source-only | docs.min.io, github.com/minio/minio |

---

## A. Data platforms

### Databricks `ai_parse_document`

- Output type: "The output is of `VARIANT` type." — https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document
- Output schema (summarised from the page's schema block): `document.pages`, `document.elements` (each with `id`, `type`, `content`, `confidence`, `bbox`, `description`), `error_status`, `metadata`. Same URL.
- Images: `imageOutputPath` — "Save rendered page images to a Unity Catalog volume for reference or multi-modal RAG applications." Each page carries `image_uri`: "Path to saved page image (if enabled)". So the images are files in a volume, and the parsed `VARIANT` holds a path. Same URL.
- Limits: "Documents are limited to a maximum of 500 pages, exceeding this limit results in errors." "There is a maximum file size limit of 100 MB." Same URL.
- Inputs: files must be "a binary type column in a DataFrame or Delta table." Same URL.
- Persisting the output: the function page gives no persistence guidance. Databricks' own tutorials do write it to tables:
  - IDP tutorial: the parsed temp table holds output that "converts raw PDF bytes into a structured VARIANT containing document elements, layout metadata, and file information"; raw PDFs are read from a volume (`/Volumes/samples/sec/contracts/`). — https://docs.databricks.com/aws/en/generative-ai/agent-bricks/idp-pipeline-tutorial
  - FILE-type pipeline tutorial (Beta): a `parsed_contracts` materialized view keeps `path` and a `parsed` column, "a structured `VARIANT` containing document elements, layout metadata, and text". For source files, "the table row stores only a lightweight `FILE` reference (`uri`, `size`, `content_type`, `checksum`)". — https://docs.databricks.com/aws/en/ldp/tutorial-file-pipelines
  - Engineering blog (2026-04-16): "you treat the VARIANT output as a flexible bronze/silver representation", then project it into Delta columns; "Documents land directly in Unity Catalog Volumes and tables". — https://www.databricks.com/blog/building-databricks-document-intelligence-and-lakeflow
- RAG pipeline guidance: "raw source data should be ingested and stored in a target table" because "This approach ensures data preservation, traceability, and auditing." "Chunks and metadata are stored in a Delta table that backs an AI Search index", because "Storing metadata alongside embeddings in the same Delta table enables efficient filtering during retrieval." The page does not say where parsed (pre-chunk) documents live. — https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag

### What a Delta table is, and its lifecycle

- Physical form: Delta "extends Parquet data files with a file-based transaction log for ACID transactions and scalable metadata handling." "Databricks stores all data and metadata for Delta Lake tables in cloud object storage." — https://docs.databricks.com/aws/en/delta/
- Versioning: "Each write to a Delta Lake table creates a new table version." Same URL.
- Volumes vs tables: "Volumes are Unity Catalog objects that enable governance over non-tabular datasets." "Use tables when you want to work with tabular data in Unity Catalog." — https://docs.databricks.com/aws/en/volumes/
- Physical deletion: "`VACUUM` removes all files from the table directory that are not managed by Delta"; "The default threshold is 7 days." "If you run `VACUUM` on a Delta table, you lose the ability to time travel back to a version older than the specified data retention period." — https://docs.databricks.com/aws/en/sql/language-manual/delta-vacuum
- Per-record deletion: example `DELETE FROM bronze.users WHERE user_id = 5`; Delta "retains table history, including deleted records, for 30 days"; after removing versions "the data is still retained in cloud storage" until VACUUM; with deletion vectors, "run `REORG TABLE ... APPLY (PURGE)` to permanently delete underlying records." — https://docs.databricks.com/aws/en/security/privacy/gdpr-delta

### Snowflake `AI_PARSE_DOCUMENT`

- Output: "By default the function returns the JSON as a string, so use PARSE_JSON to read the fields in SQL." — https://docs.snowflake.com/en/sql-reference/functions/ai_parse_document
- Input: "A FILE object that specifies the document to parse, stored in a Snowflake stage." Same URL.
- Images: with `extract_images`, image data is "Image data encoded as a base64 string" in an `images` array, i.e. inline in the result, not written to a stage. "AGENTIC mode supports up to 2,000 images per document." Same URL.
- Limits: "Maximum file size of 104857600 bytes exceeded." / "Maximum number of 2000 pages exceeded." "The function processes documents stored on internal or external stages." Default output: "AI_PARSE_DOCUMENT returns the content in Markdown format." — https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document
- Persistence: neither page shows storing parsed results in a table; the example table stores file references built with `TO_FILE`. Same URL.
- Column size limits: "A VARIANT value can have a maximum size of up to 128 MB of uncompressed data", "in practice, the maximum size is usually smaller because of internal overhead." — https://docs.snowflake.com/en/sql-reference/data-types-semistructured . VARCHAR: "limited to a maximum of 134217728 bytes (128 MB)"; default "16777216". — https://docs.snowflake.com/en/sql-reference/data-types-text
- Source files: "Both external (external cloud storage) and internal (i.e. Snowflake) stages support unstructured data." "Directory tables store a catalog of staged files in cloud storage." "The FILE data type represents a file stored in an internal or external stage." — https://docs.snowflake.com/en/user-guide/unstructured-intro

## B. Document-pipeline vendors

### Unstructured

- Destinations (28 on the overview page): Astra DB, Azure AI Search, Azure Blob Storage, Couchbase, Databricks Volumes, Delta Tables in Amazon S3, Delta Tables in Databricks, Elasticsearch, Google Cloud Storage, IBM FileNet, IBM watsonx.data, Kafka, Milvus, MongoDB, MotherDuck, Neo4j, OneDrive, OpenSearch, Pinecone, PostgreSQL, Qdrant, Redis, S3, Snowflake, Teradata Database, Teradata Vector Store, VAST, Weaviate. Described as: "the transformed and analyzed data is securely and efficiently transferred to a storage system for future use", "often to a vector database". — https://docs.unstructured.io/ui/destinations/overview
- Output shape: partitioning yields "a list of *document elements*"; "Every element has a type; an element_id; the extracted text; and some metadata." Images: `image_base64` is "A Base64 representation of the detected image or table". — https://docs.unstructured.io/ui/document-elements
- PostgreSQL: "The minimum viable schema for Unstructured contains only the fields `id`, `element_id`, `record_id`, `text`"; metadata columns follow the naming convention (e.g. `points JSONB`, `page_number TEXT`). Element-level rows (inferred from `element_id`, not stated). Nothing on deletion. — https://docs.unstructured.io/ui/destinations/postgresql
- MongoDB: "Unstructured recommends that all documents in the target collection have a field named `record_id`"; "Unstructured can use this field to do intelligent document overwrites." "Without this field, duplicate documents might be written". — https://docs.unstructured.io/ui/destinations/mongodb
- S3: setup only (bucket URI, `s3:PutObject`); output format not described on the page. — https://docs.unstructured.io/ui/destinations/s3
- Delta Tables in S3: "Initially, one Parquet (`.parquet`) file per file in the source location"; "Avoid directly modifying, adding, or deleting Parquet data files or the `_delta_log` folder" ("This can lead to data loss or table corruption"). — https://docs.unstructured.io/ui/destinations/delta-table

### LlamaIndex / LlamaCloud

- Framework docstore: "Document stores contain ingested document chunks, which we call `Node` objects." MongoDB backend "persists data as `Node` objects are ingested"; also Redis, Firestore, Couchbase, Tablestore, AlloyDB, Cloud SQL for PostgreSQL. Nothing on images. — https://developers.llamaindex.ai/python/framework/module_guides/storing/docstores/
- LlamaParse (hosted): "Files uploaded for Parse or Extract are cached for 48 hours to avoid duplicate processing costs, then deleted." "Set `do_not_cache=true` on a request to skip caching entirely." Indexed data (parsed content, embeddings, metadata) "is retained separately, for the duration of your agreement to support retrieval" and "is deleted only when you request deletion or upon contract termination or expiration." — https://developers.llamaindex.ai/llamaparse/general/enterprise-readiness/data-privacy-security/
- Parse v1 cache: "caches parsed documents for 48 hours before permanently deleting them." — https://developers.llamaindex.ai/python/cloud/llamaparse/features/cache_options/
- Image output page: fetch failed (404 at the redirected URL).

### docling-serve

- Results are transient: `DOCLING_SERVE_SCRATCH_PATH` "will be used as scratch workspace, e.g. storing the results before they get requested"; `DOCLING_SERVE_SINGLE_USE_RESULTS` default `true`; `DOCLING_SERVE_RESULT_REMOVAL_DELAY` default `300`, "the delay before results are removed from the task registry"; `DOCLING_SERVE_ENG_RQ_RESULTS_TTL` default `14400`, "Time To Live (in seconds) for RQ job results in Redis"; `DOCLING_SERVE_ENG_RAY_TASK_METADATA_TTL` default `604800`. Optional artifact storage (S3/Azure) returns presigned URLs: `DOCLING_SERVE_ARTIFACT_STORAGE_PRESIGN_TTL_SECONDS` default `3600`. — https://github.com/docling-project/docling-serve/blob/main/docs/configuration.md
- No statement about a durable system of record.

## C. Database vendors

### MongoDB

- Size limit and why: "The maximum BSON document size is 16 mebibytes." "The maximum document size helps ensure that a single document cannot use an excessive amount of RAM or, during transmission, an excessive amount of bandwidth. To store documents larger than the maximum size, MongoDB provides the GridFS API." — https://www.mongodb.com/docs/manual/reference/limits/
- GridFS: "a specification for storing and retrieving files that exceed the BSON-document size limit of 16 MiB"; default chunk "255 KiB"; "GridFS does not support multi-document transactions." "If your files are all smaller than the 16 MiB BSON Document Size limit, consider storing each file in a single document instead of using GridFS. Use the BinData data type". "In some situations, storing large files may be more efficient in a MongoDB database than on a system-level filesystem." — https://www.mongodb.com/docs/manual/core/gridfs/
- Versioning advice (GridFS page): "you can store multiple versions of each file and specify the current version of the file in the metadata. You can update the metadata field that indicates "latest" status in an atomic update after uploading the new version of the file, and later remove previous versions if needed." Same URL.
- Bloated documents: "Storing data fields that are related to each other but not accessed together can create bloated documents that lead to excessive RAM and bandwidth usage." "use document references to separate fields that aren't returned together." — https://www.mongodb.com/docs/manual/data-modeling/design-antipatterns/bloated-documents/
- Vendor engineering blog (MongoDB Senior Solutions Architect, 2025-10-30): "Avoid storing binary large objects (BLOBs) such as images, videos, audio files, or other large media directly inside MongoDB documents." "store such large files in object storage (e.g., AWS S3, Azure Blob Storage, Google Cloud Storage) or use MongoDB's GridFS if you want to keep everything within MongoDB. In these approaches, you store only the metadata and a reference (URL or ObjectId) in the document." On large strings: "Storing them in MongoDB can quickly bloat your documents, increase memory usage, and degrade query performance." — https://www.mongodb.com/company/blog/technical/cost-optimization-with-optimal-document-size
- RAG/multimodal library (blog, 2025-07-16): "PDFs are then turned into single-page images and stored in S3." "it indexes the embeddings using Atlas Vector Search and provides a reference back to S3." — https://www.mongodb.com/company/blog/product-release-announcements/introducing-mongodbs-multimodal-search-library-for-python
- TTL indexes: "special single-field indexes that MongoDB can use to automatically remove documents from a collection after a certain amount of time or at a specific clock time." "The background task that removes expired documents runs *every 60 seconds*." "The TTL index does not guarantee that expired data is deleted immediately upon expiration." Per pass: "The process deletes 50000 documents from the current index." "If a document does not contain the indexed field, the document will not expire." "Compound indexes do not support TTL". Only the primary deletes. The page does not mention GridFS. — https://www.mongodb.com/docs/manual/core/index-ttl/

### PostgreSQL

- PostgreSQL wiki, BinaryFilesInDB. For in-DB: "Security and access control are simplified", "Files saved into a primary database will stream to standby replicas automatically", "Backups are easier there is no need to track external files". Against: "Performance hit storing files in database.", "Memory requirements higher, for Database", "Backups can take significantly longer", "Access to files to external applications is complicated." For filesystem + reference: "Performance accessing binary file skips DB access layer."; against: "External files and database can get out of sync". — https://wiki.postgresql.org/wiki/BinaryFilesInDB
- TOAST: triggered "when a row value to be stored in a table is wider than `TOAST_TUPLE_THRESHOLD` bytes (normally 2 kB)"; values limited "to 1 GB (2^30 - 1 bytes)"; out-of-line chunks of "about 2000 bytes", each "stored as a separate row in the TOAST table"; "an UPDATE of a row with out-of-line values incurs no TOAST costs if none of the out-of-line values change." Test noted: "the main table contained only about 10% of the entire data". — https://www.postgresql.org/docs/current/storage-toast.html
- jsonb: "Although storing large documents is practicable, keep in mind that any update acquires a row-level lock on the whole row." "Consider limiting JSON documents to a manageable size in order to decrease lock contention among updating transactions." — https://www.postgresql.org/docs/current/datatype-json.html
- Large objects: "allows values up to 4 TB in size, whereas TOASTed fields can be at most 1 GB." — https://www.postgresql.org/docs/current/lo-intro.html ; "breaks large objects up into 'chunks' and stores the chunks in rows in the database." — https://www.postgresql.org/docs/current/lo-implementation.html
- Row TTL: no native row TTL found in the official docs checked. The documented bulk-removal mechanism: "Bulk loads and deletes can be accomplished by adding or removing partitions"; "Dropping an individual partition using `DROP TABLE`, or doing `ALTER TABLE DETACH PARTITION`, is far faster than a bulk operation. These commands also entirely avoid the `VACUUM` overhead caused by a bulk `DELETE`." — https://www.postgresql.org/docs/current/ddl-partitioning.html

### Elasticsearch

- "Do not disable the `_source` field, unless absolutely necessary." Disabling it loses "The ability to reindex from one Elasticsearch index to another, either to change mappings or analysis". Synthetic source: "Both modes return the same content, which differs from the document that was sent at index time." No statement found on `_source` as primary store vs an external store. — https://www.elastic.co/docs/reference/elasticsearch/mapping-reference/mapping-source-field

## D. Object-storage lifecycle

### Amazon S3

- Filters: "You can specify a filter by using the object size, the object key prefix, one or more object tags, or a combination of filters." "A filter can have only one prefix, and zero or more tags." "An S3 Lifecycle configuration can have up to 1,000 rules per bucket. This limit is not adjustable." — https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html
- Timing: "Amazon S3 calculates the time by adding the number of days specified in the rule to the object creation time and rounding up the resulting time to the next day at midnight UTC." Same URL.
- Versioned buckets: Expiration on the current version adds a delete marker; `NoncurrentVersionExpiration` "permanently delete[s] noncurrent versions"; `NewerNoncurrentVersions` 1 to 100. Same URL.
- Execution: nonversioned — "Amazon S3 queues the object for removal and removes it asynchronously". "There may be a delay between the expiration date and the date at which Amazon S3 removes an object. You are not charged for expiration or the storage time associated with an object that has expired." Tags: "S3 Lifecycle evaluates objects against tag-based filters daily"; "If the triggering tag is no longer present when the action executes, the expiration does not proceed." "You can't use a bucket policy to prevent deletions or transitions by an S3 Lifecycle rule." — https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html

### MinIO

- `mc ilm rule add`: `--prefix` "Restrict the management rule to a specific object prefix."; `--tags` "One or more ampersand `&`-delimited key-value pairs describing the object tags to use for filtering objects"; `--expire-days` "The number of days to retain an object after being created."; `--noncurrent-expire-days` "The number of days to retain an object version after becoming *non-current*". No edition note. — https://docs.min.io/community/minio-object-store/reference/minio-mc/mc-ilm-rule-add.html
- Processing: "The scanner is a low-priority process that yields to higher-priority workloads." (so expiry can lag the rule period). — https://docs.min.io/community/minio-object-store/administration/object-management/object-lifecycle-management.html (the community page's text names "MinIO AIStor lifecycle management")
- Community edition status: "THIS REPOSITORY IS NO LONGER MAINTAINED."; archived "on Apr 25, 2026"; "The MinIO community edition is now distributed as source code only."; licensed under "GNU AGPLv3". — https://github.com/minio/minio

## Not found / unverified

- Databricks: no official statement on where parsed (pre-chunk) documents should live in the RAG cookbook page; the function page gives no persistence guidance (tutorials and blog do show Delta tables).
- Snowflake: no documented pattern for persisting `AI_PARSE_DOCUMENT` results; no image-to-stage output option found (images are inline base64).
- Unstructured: S3 destination output format and file naming not documented on the destination page; no deletion semantics on any destination page checked.
- LlamaParse image output page: fetch failed (404). Where LlamaCloud stores parsed docs/images internally: not stated.
- docling-serve: nothing on durable persistence.
- MongoDB: no Atlas Architecture Center page found that states "content in MongoDB, images in S3" for document processing; the evidence is two vendor blog posts. TTL page does not say whether TTL applies to GridFS collections.
- PostgreSQL: native row TTL not found (absence, not a quoted statement).
- Elasticsearch: no statement on `_source` as system of record vs an external store.
- MinIO: which ILM filters are present in the current source-only community build was not verified beyond the community `mc` reference page.
