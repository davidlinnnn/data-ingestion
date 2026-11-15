# WeKnora query-side API shapes: Retrieval and Wiki (2026-10-31)

Input for #76 B0 (result zones), B9 (Source Metadata), B10-B13 (filters). Evidence only.

**Status (2026-11-15):** written during the first round of #76 (2026-10-27 to 2026-10-31). That round was restarted on 2026-11-15, so the decision labels here (A1, B0 to B15) name questions of that round, not adopted decisions. The evidence stands on its own.

- Pinned commit `dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2`; nothing built or run. Wiki identity: see `weknora-wiki-agent-access-2026-10-28.md`. **V** = read this session; **I** = inference; brackets = sources below.

## Summary

- V: Four chunk-retrieval surfaces: HTTP `POST /knowledge-search` (multi-KB, reranked), HTTP `POST /knowledge-bases/{id}/hybrid-search` (one KB, raw recall), MCP `search_knowledge`/`grep_chunks`, in-product `search_knowledge`. All fill one flat `SearchResult` [5]; the envelopes differ.
- V: **Filter vocabulary: KB ids, document ids, KB-local tag ids (any-of).** No time, metadata, source-URL or title filter on search. Time, channel, file type and title filters exist only on document listing [5][15].
- V: A hit has chunk id, knowledge id, KB id, `score`, `match_type`, `chunk_type`, content. HTTP hits add title, filename, source, description, custom metadata, `source_locators`. **No tags, `updated_at` or version** [5].
- V: Title, source and metadata are copied from the SQL document row at query time; a hit with no row is dropped [12]. Tags are SQL relation rows resolved to document ids at query time. Tag and metadata edits write SQL only, no re-index [18].

## Q1. Request

| Surface | KB scope | Filters | Count | Modes / rerank |
|---|---|---|---|---|
| `POST /knowledge-search` [7][8] | `knowledge_base_id(s)`; 400 if KB ids, `knowledge_ids` and tag scopes are all empty | `knowledge_ids`; `tag_ids` (exactly one KB, else 400); `mentioned_items` tag scopes | `match_count` ≤200; no offset or cursor | disable-vector / disable-keyword flags; `rerank{enabled,model_id,top_k,threshold}`, default on [6] |
| `hybrid-search` [9] | path KB, optional `knowledge_base_ids` | `knowledge_ids`, `tag_ids` | `match_count`, default 50 | same flags; rerank only if sent |
| MCP `search_knowledge` [1][2] | `knowledge_base_ids` (ids or names), default all in endpoint scope | `knowledge_ids` 1-100 | `limit` 10, max 30 | `mode` hybrid/semantic/keyword; **no rerank** (nil reranker) |
| In-product tool [3] | `kb://N` handles, ≤10, inside the agent's pinned scope | document and tag scope pinned by agent config | `limit` ≤30 | same `mode`; reranker if configured (I) |
| Document listing [15] | path KB | `tag_ids` (OR), `keyword`, `file_type`, `parse_status`, `source`, `start_time`/`end_time` (`updated_at`), `folder_path` | `page`, `page_size` ≤1000 | n/a |
| Wiki `POST /wiki-search` [19][20] | 1-32 KB ids | none | `limit` | regex; no rerank |

- V: Tag scope on a document KB becomes a document-id list (`ListKnowledgeIDsByTagIDs`, "carrying any of") before retrieval [18][11]. FAQ KBs push the tag id into the index filter [5][11].

## Q2. Response

| Surface | Envelope | Per-hit fields (V) |
|---|---|---|
| `knowledge-search` [8] | `{success, data[], meta.rerank}` | `SearchResult`: `id`, `knowledge_id`, `knowledge_base_id`, `chunk_index`, `content`, `score`, `match_type`, `chunk_type`, `knowledge_title/filename/source/channel/description`, `knowledge_custom_metadata` (text), `metadata`, `source_locators`, `chunk_metadata`, `image_info` [5] |
| `hybrid-search` [9] | `{success, data[]}`; `meta` only with rerank | same struct |
| MCP / in-product [4] | text plus `Data{results[], count, mode, requested_mode, kb_counts, display_type}` | smaller row: `chunk_id`, `knowledge_id`, `knowledge_base_id`, `knowledge_title`, `knowledge_metadata`, `match_snippet`, `score`, `match_type`, `chunk_type`; **no filename, source or locators** |
| `POST /wiki-search` [19] | `{success, data[]}` | `WikiSearchHit`: `id`, `knowledge_base_id`, `slug`, `title`, `page_type`, `aliases`, `summary`, `match_snippet`; no score |

- Score (V): one `score`, rank-based after fusion, not a similarity; `match_type` 0 vector / 1 keyword [5][9].
- Attribution (V): `knowledge_source` is the URL for URL imports; locators carry page, bbox, quote, `source_hash` (HTTP only) [5].
- Version and time (V): none on search hits [5][19].
- Highlighting (V): `match_snippet` on agent and wiki rows only [4][19].
- Generated vs source (V): only `chunk_type` (`text`, `summary`, `table_summary`, `image_caption`, `faq`, ...) and wiki `page_type`; no flag [5].
- Diagnostics (V): `meta.rerank{applied, outcome, candidate_count, result_count, top_score}` with a fixed outcome enum (`all_below_threshold`, `no_candidates`, ...) [6]. Agent data adds `mode_fallbacks`, `partial_failures` [3].

## Q3. Tags and metadata at upload

| Field | Set via | Reaches hits | Filterable | Update |
|---|---|---|---|---|
| title | file name (`fileName` overrides) [14][17]; `PUT /knowledge/{id}` [16] | `knowledge_title`, live | list `keyword` | SQL only [18] |
| tags | upload `tag_ids`: KB-local tag ids, created separately, unique name per KB [14][22] | **no** | search `tag_ids`, list `tag_ids` | replace set; no re-index [18] |
| `metadata` | upload form JSON, string map [14] | `metadata` on HTTP hits [12] | no | no update API |
| `custom_metadata` | **not on upload**; `PUT /knowledge/{id}` only [16] | flattened `key: value` text [13][12] | no | ≤20 keys, key ≤64, value ≤1000, scalars; a summary refresh is queued [18] |
| source URL | set by URL import, not an upload field [13] | `knowledge_source` (HTTP) | list `source` = channel, not URL [15] | n/a |

- V: A code comment calls `custom_metadata` "deliberately separate" from `metadata`, which holds "internal ingestion state and IDs". The upload form writes uploader values into that map, and the duplicate check reads `datasource_id` and `external_id` from it [13][17].

## Q4. Errors and empty results

| Case | Behaviour (V) |
|---|---|
| `knowledge-search`, unreadable KB or document | silently dropped; no target left = `data: []`, 200 [11]. I: an unknown KB id is kept under the caller's tenant; outcome not traced |
| `knowledge-search`, no hits | 200, empty `data`, `meta.rerank.outcome` says why [6][11] |
| `hybrid-search`, unknown or unreadable KB | not found = 404, forbidden = 403 [10] |
| bad body, empty query, `match_count` >200, bad rerank | 400 [8][9] |
| MCP, unknown or out-of-scope KB | one message for both [2] |
| MCP, document id | two messages: "not found" vs "outside this endpoint's scope"; empty or >100 `knowledge_ids` is a tool error [2] |
| MCP / agent, no hits | success, text "No matching chunks", `count: 0` [3] |
| MCP / agent, every KB search failed | **error, not empty** ("not evidence that they lack the answer") [3] |
| `wiki-search`, unknown or unauthorised KB | same 404; auth runs before the wiki-enabled check [20] |
| `wiki-search`, non-wiki KB, bad regex, >32 KBs | 400; no hits: `data: []` [20] |
| listing, bad `sort_by` or time | 400 naming the field [15] |

## Q5. Common vs product-specific in code

- V: One `SearchResult` serves all chunk hits. Identity (`id`, `knowledge_id`, `knowledge_base_id`, `score`, `chunk_type`) shares one flat object with product detail (`image_info`, `source_locators`, FAQ and graph fields) [5].
- V: The in-product catalog picks a model-visible subset by `x-agent` struct tags and returns `Projected{data, meta, truncated}` [5][21]: an allow-list over the shared struct.
- V: Agent tools return text plus a `data` map; `display_type` (e.g. `search_results`) names the payload shape [4].
- V: Wiki hits are a separate struct. HTTP envelopes vary: `{success,data,meta}`; `{pages}` with errors as `{error}` on single-KB `GET /wiki/search` [8][19].

## Facts that bear on #76 B0-B13

- **B0.** No zone split exists. De-facto common fields: ids, `score`, `chunk_type`, content or snippet [5][4]. `display_type` is the payload discriminator.
- **B1(c), B9.** Title, source, description and custom metadata are filled from the row per query; a missing row drops the hit [12]. Custom metadata is flattened to text, losing types [13]. Uploader `metadata` shares a map with ingestion keys and reaches hits [12][17]. Neither is filterable.
- **B10-B12.** Many KBs per search, three behaviours for unreadable ones: silent drop [11], one uniform message (MCP KB selectors) [2], 404 (`hybrid-search`) [10], uniform 404 (`wiki-search`) [20]. MCP splits "not found" from "out of scope" for documents [2]. `tag_ids` needs exactly one KB [8], near B12's singular `source_id`.
- **B11 empty lists.** MCP rejects empty `knowledge_ids` [2]; HTTP only when every scope field is empty [8].
- **B13 tags.** KB-local ids, many-to-many, any-of only, no all-of, no name matching [18][22]. Not returned on hits. A document-KB tag change needs no re-index [18]; I: FAQ KBs index the tag id and would [5].
- **Paging, freshness.** Search has no offset or cursor [8][9]; no hit carries version or `updated_at` [5]. The only diagnostic is the rerank meta [6].

## Open points

1. Unknown KB id in `knowledge-search`: final status untraced.
2. URL-import and manual-create paths not read for title and tags.
3. FAQ-KB tag filtering read at request level only.
4. Whether HTTP hits should expose ingestion `metadata` is undocumented. No runtime call was made.

## Sources

1. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/tools_retrieve.go#L15-L410>
2. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/scope.go#L38-L313>
3. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/search_knowledge.go#L24-L548>
4. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/search_knowledge.go#L985-L1151>
5. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/search.go#L18-L291>
6. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/rerank.go#L8-L117>
7. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/session/types.go#L108-L123>
8. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/session/qa.go#L890-L1026>
9. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/knowledgebase.go#L331-L459>
10. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/kb_access.go#L28-L81>
11. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/session_knowledge_qa.go#L438-L976>
12. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/knowledgebase_search_results.go#L213-L389>
13. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/knowledge.go#L97-L285>
14. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/knowledge.go#L296-L440>
15. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/knowledge.go#L1043-L1186>
16. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/knowledge.go#L2347-L2424>
17. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/knowledge_create.go#L98-L229>
18. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/knowledge.go#L840-L1076>
19. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/wiki_page.go#L1086-L1215>
20. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_page.go#L1255-L1327>
21. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/operations/projection.go#L19-L60>
22. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/tag.go#L9-L79>
