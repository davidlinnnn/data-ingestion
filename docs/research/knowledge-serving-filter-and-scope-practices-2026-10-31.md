# Serving-layer filters, scope and metadata: vendor and spec evidence (2026-10-31)

Input for #76 B9-B15. Evidence only. **V** = read in a primary source; **I** = inference. Complements `knowledge-platform-serving-layer-csp-practices-2026-10-27.md`.

**Status (2026-11-15):** written during the first round of #76 (2026-10-27 to 2026-10-31). That round was restarted on 2026-11-15, so the decision labels here (A1, B0 to B15) name questions of that round, not adopted decisions. The evidence stands on its own.

## Summary

- V: Authorization and caller filters are separate inputs or mechanisms: Kendra `UserContext` beside `AttributeFilter` [3]; Azure appends its security filter to the caller's `filter` [12]; Elasticsearch takes the role query from the role [27]. Azure also documents the app writing the user string into the filter itself [11].
- V: No vendor documents a caller filter widening authorization. Only Azure states the composition ("automatically appended") [12]; Kendra does not [3][5]. I: AND everywhere.
- V: Missing authz input returned everything in Kendra [5] and early Azure previews; Azure now returns public documents only [12].
- V: Tag filters are typed, declared in the index first, with any-of / all-of operators [1][9][13]. Most engines are case-sensitive; Azure's cure is a normalizer [13][15][19][29].
- V: Malformed filters give 400-class errors [1][18][19][26][32]. No source documents uniform not-found for unreadable references or existence-leak handling.
- V: One scope per call is the norm (Kendra, Azure, Q Business, Pinecone) [3][8][11][33]; Vertex and Glean default to all [19][23].
- V: Result metadata goes to every reader; no "private to uploader" attribute [3][11]. Only Elasticsearch warns of facet-count leakage [27].
- V: MCP's tools spec says nothing on filters or scope; input validation errors are `isError` results [35].

## Q1. Authorization scope vs caller filters

| Product | Authz input | Caller filter | Composition |
|---|---|---|---|
| Kendra [3][5] | `UserContext` (token, or user, groups, data-source groups) | `AttributeFilter` | Not stated. Service "doesn't do user authentication". App may instead put `_user_id` / `_group_ids` in the attribute filter. |
| Q Business [8] | No user field in the request body | `attributeFilter` | I: service ACL, then caller filter |
| Azure [11][12] | Token header `x-ms-query-source-authorization`, or principal string the app writes | `filter` (OData) | Service builds the security filter and appends it to incoming filters; ACL match types are OR'd inside it |
| Vertex [19][22] | End-user IdP identity; no request field documented | `filter` | Widening not addressed [22] |
| Glean [23] | No user field in the search request | `facetFilters`, `datasourcesFilter`, `exclusions` | Not stated |
| Elasticsearch DLS [27] | Role query attached to the role | Search query | "in conjunction with" privileges. Roles OR'd; a role without DLS disables DLS |

- I: Only app-side merges can widen: Kendra's attribute route and Azure's string filter put both in one expression [5][11].

## Q2. Tag / attribute semantics

| Product | any / all | Case | Types and limits | Declare and change |
|---|---|---|---|---|
| Kendra [1][2][6][7] | `ContainsAny` / `ContainsAll` on StringList | Not stated | String, StringList, Long, Date. 500 fields per index; string 1-2048; list default max 10; depth 2, 10 per list, else `ValidationException` | Create via `UpdateIndex`; type immutable; values via `BatchPutDocument` |
| Q Business [9][10] | `containsAny` / `containsAll` | Not stated | Date, Number, String, StringList; 50 attributes, no delete or rename | Map to index field first; type immutable |
| Azure [11][13][14][15] | `any` / `all`, `search.in` | Case-sensitive; normalizer opt-in | 16 MB request; "hundreds" of clauses is the risk; `search.in` no list cap | Existing field cannot become filterable; `mergeOrUpload` updates one field |
| Vertex [19][20][21] | `ANY("x")` | "case-sensitive" | Field must be indexable | `struct_data` must match schema or `INVALID_ARGUMENT` |
| Glean [23][24][25] | One filter's values OR; list of filters AND; `facetFilterSets` OR (both = bad request) | Custom metadata names case-insensitive | TEXT, INT, DATE; INT not faceted | Custom properties: full re-upload per change. Custom Metadata API: separate update |
| Qdrant, Pinecone [29][31][32][33] | match-any; `$in` up to 10,000 | Qdrant case-sensitive | Pinecone 40 KB metadata per record | Qdrant: payload index before ingest |

## Q3. Error semantics

| Case | Documented |
|---|---|
| Unknown field | Kendra: attributes "must exist in your index" [1], error not stated. Vertex: unrecognizable filter -> `INVALID_ARGUMENT` [19]. Azure, Glean, Q Business: not stated |
| Malformed / too complex | Kendra `ValidationException` (HTTP 400) [1]. Azure 400 with message [18]. Glean 400, 422 "Invalid Query" [26]. Pinecone 400 for array filter value [32]. Q Business 400 with `fields`, `reason` [8] |
| Missing target | Kendra `ResourceNotFoundException` (400) [3]. Q Business 404 [8]. Azure 404 [18] |
| Unauthorised target | Kendra `AccessDeniedException` (400) [3]. Q Business 403 [8]. Azure 403 [18] |
| Empty filter | Vertex: empty string = no filter [21]. Glean: missing `datasourcesFilter` = all [23]. Empty list: not documented |
| Authz fails | Azure 5xx, no partial result [12] |
| MCP | Input validation = `isError: true` result for the model to retry; unknown tool or malformed request = JSON-RPC error [35] |

I: Uniform 404 for unreadable references is stricter than any documented API; Q Business and Azure separate 403 from 404 [8][18].

## Q4. Scoped search

| Product | Scope | Default |
|---|---|---|
| Kendra [3] | One `IndexId` | Required |
| Q Business [8] | `contentSource`: one retriever | Required |
| Azure [11] | One index in the URL | Required |
| Vertex [19] | `dataStoreSpecs`: zero, one or many; per-store `filter` | Empty = all stores (blended); with several, `order_by` etc. fail with `INVALID_ARGUMENT` |
| Glean [23] | `datasourceFilter` or `datasourcesFilter` | Missing = all |
| Pinecone [33] | Each operation targets one namespace | Not described |

## Q5. Custom metadata on results

- V: Kendra returns all attributes by default; `RequestedDocumentAttributes` narrows [3]. Q Business returns `documentAttributes` [8]. Glean returns `customData` [23]; Custom Metadata visibility not stated [25]. Vertex returns `struct_data` [20]. Pinecone needs `includeMetadata` [34].
- V: No per-uploader privacy. Azure `retrievable: false` hides a field from everyone and "isn't a content-obfuscation or field-level security mechanism" [11].

## Q6. Facets and counts under trimming

- V: Elasticsearch: aggregations can expose terms and counts from inaccessible documents [27].
- V: Azure facets come from the current results and per-shard top-N, so counts can be off [15].
- V: Kendra, Glean, Vertex return per-value counts [4][19][23]; none says if they are ACL-trimmed..

## Cost of filtering inside the query

- V: Azure `preFilter` (default) guarantees k results, but at 1M vectors with a selective filter is about 7x slower than `postFilter`, which may return fewer than k [17]. Qdrant: naive filtered HNSW fragments and recall collapses past a threshold [30].
- V: Azure says in-engine filtering "improves performance versus post-query trimming" [16]; Elasticsearch filter clauses are cacheable [28].
- I: In-engine filtering is a recall and latency choice; an egress re-check after the engine needs over-fetch.

## Facts that bear on #76 B9-B15

- **B9:** V: engines return attributes to every reader; filterable attributes are separate, declared, typed fields [2][10][13][21]. I: opaque metadata apart from typed tags (B13) matches that.
- **B10:** V: separate inputs are the norm [3][12][27]. V: missing authz returned everything in Kendra and early Azure [5][12]. I: rejecting the request is stricter than either.
- **B11:** V: only Azure documents "append" [12]; 400 for malformed filters is universal [1][18][19][26]; empty means "no filter" in Vertex and Glean [21][23], so the 400 on an empty list is a deliberate divergence. I: uniform 404 has no precedent. For MCP, return 400s as `isError` results [35].
- **B12:** V: required single scope matches Kendra, Azure, Q Business, Pinecone [3][8][11][33]; default-all is Vertex and Glean [19][23].
- **B13:** V: any_of / all_of = `ContainsAny` / `ContainsAll`, `any` / `all` [1][13]. V: case-sensitive by default, normalisation is the cure [13][15]. V: Kendra list default 10, 2048 chars [6]. V: Glean splits full re-upload from separate metadata update [24][25]; Azure cannot make an existing field filterable [13]. I: write-time normalisation and a declared tag field avoid both.
- **B14:** V: one scope per call is common; none treats it as a security boundary (Kendra `DataSourceGroups` is ACL input [5]). Vertex multi-store blending disables features [19].
- **B15:** V: Vertex has one IdP per location [22]. Routing by data owner: no source.

## Open points

1. Elasticsearch status for missing or unauthorised indices: not verified.
2. Kendra: `UserContext` + `AttributeFilter` composition, case, unknown-attribute error not stated; unknown-field error also not stated for Azure, Glean, Q Business.
3. Facet and count behavior under ACL (Kendra, Azure, Vertex, Glean): undocumented.
4. Existence-leak handling for filters: no source.
5. Vertex REST pages too long; proto used [19]. Kendra and Q Business are closed to new customers [3][8]. Weaviate and Elasticsearch multi-target behavior not checked.

## Sources

1. https://docs.aws.amazon.com/kendra/latest/APIReference/API_AttributeFilter.html
2. https://docs.aws.amazon.com/kendra/latest/dg/custom-attributes.html
3. https://docs.aws.amazon.com/kendra/latest/APIReference/API_Query.html
4. https://docs.aws.amazon.com/kendra/latest/dg/filtering.html
5. https://docs.aws.amazon.com/kendra/latest/dg/user-context-filter.html
6. https://docs.aws.amazon.com/kendra/latest/APIReference/API_DocumentAttributeValue.html
7. https://docs.aws.amazon.com/kendra/latest/dg/quotas.html
8. https://docs.aws.amazon.com/amazonq/latest/api-reference/API_SearchRelevantContent.html
9. https://docs.aws.amazon.com/amazonq/latest/api-reference/API_AttributeFilter.html
10. https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/doc-attributes.html
11. https://learn.microsoft.com/en-us/azure/search/search-security-trimming-for-azure-search
12. https://learn.microsoft.com/en-us/azure/search/search-query-access-control-rbac-enforcement
13. https://learn.microsoft.com/en-us/azure/search/search-filters
14. https://learn.microsoft.com/en-us/azure/search/search-query-odata-search-in-function
15. https://learn.microsoft.com/en-us/azure/search/search-faceted-navigation
16. https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview
17. https://learn.microsoft.com/en-us/azure/search/vector-search-filters
18. https://learn.microsoft.com/en-us/rest/api/searchservice/http-status-codes
19. https://github.com/googleapis/googleapis/blob/master/google/cloud/discoveryengine/v1/search_service.proto
20. https://github.com/googleapis/googleapis/blob/master/google/cloud/discoveryengine/v1/document.proto
21. https://docs.cloud.google.com/generative-ai-app-builder/docs/filter-search-metadata
22. https://docs.cloud.google.com/generative-ai-app-builder/docs/data-source-access-control
23. https://gleanwork.github.io/open-api/specs/final/client_rest.yaml
24. https://developers.glean.com/api-info/indexing/datasource/custom-properties
25. https://developers.glean.com/api-info/indexing/custom-metadata/overview
26. https://developers.glean.com/api/client-api/search/search
27. https://www.elastic.co/docs/deploy-manage/users-roles/cluster-or-deployment-auth/controlling-access-at-document-field-level
28. https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-bool-query
29. https://qdrant.tech/documentation/concepts/filtering/
30. https://qdrant.tech/articles/filterable-hnsw/
31. https://qdrant.tech/documentation/concepts/indexing/
32. https://docs.pinecone.io/guides/search/filter-by-metadata
33. https://docs.pinecone.io/guides/index-data/indexing-overview
34. https://docs.pinecone.io/reference/api/2025-10/data-plane/query
35. https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/server/tools.mdx
