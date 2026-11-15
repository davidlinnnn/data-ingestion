# WeKnora Wiki: agent access, page identity and source titles (2026-10-28)

Input for #76 B1(c): result `title` and `source_url` come from the admission record at response time, not from a projection copy. This note gives evidence only and makes no recommendation.

**Status (2026-11-15):** written during the first round of #76 (2026-10-27 to 2026-10-31). That round was restarted on 2026-11-15, so the decision labels here (A1, B0 to B15) name questions of that round, not adopted decisions. The evidence stands on its own.

- Pinned commit: WeKnora default-branch HEAD `dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2` (2026-10-28). Nothing was built or run.
- Scope: extends `weknora-knowledge-platform-fit-2026-10-05.md` (pinned `bccb4b1`) without repeating its ingest, revision or retrieval analysis.
- **V** = read in source this session. **I** = inference.

## Summary

- V: Wiki is a first-class per-KB feature. LLM-generated pages live in `wiki_pages` with folders, slug links and revisions [1][2].
- V: External agents (MCP) get three read tools: `wiki_search`, `wiki_read_page` and `wiki_index`. In-product agents also get write tools and operations such as `wiki.list_folders` [5][7][21].
- V: **There is no filesystem-style ls, cat, glob or page listing by path.** Agents navigate by search, then slug, then `[[slug]]` links.
- V: The address is the **slug** `<type>/<name>`, unique per KB. Rename has no redirect [2][25].
- V: **When an agent reads a page, source titles come only from the stored `source_refs` string. Nothing is looked up live** [11].
- V: Ingest stores bare document IDs on purpose, so agents get no title [17].
- V: The human UI looks titles up live [20].
- V: A document title edit never reaches the wiki. Deletion cleanup is best-effort [23][24].

## Changes since the 2026-10-05 note

- V: The MCP wiki tools and the agent read/search code are almost unchanged. The diff covers annotations, KB-selector checks and an exported `WikiPageInScope`.
- V: New `@x-agent` annotations put these wiki operations into the in-product agents' `find_operations`/`run_operation` catalog [21][22]:
  - read: `list_folders`, `get_page`, `list_revisions`, `get_stats`, `list_issues`, `lint`
  - write: `create_folder`, `move_page`, `revert`, `rebuild_links`
- V: `GET /pages/*slug` now adds `in_link_titles`, resolved live from wiki rows [21].
- V: v0.8.3 adds cross-KB `POST /wiki-search` [27].

## Q1. Features and data model

| Table | Key fields (V) [2][4] |
|---|---|
| `wiki_pages` | `id` UUID, `knowledge_base_id`, `slug`, `title`, `page_type` (summary/entity/concept/index/synthesis/comparison), `status` (draft/published/archived), `content`, `summary`, `aliases`, `folder_id` plus cached `wiki_path`, `source_refs`, `chunk_refs`, `in_links`/`out_links` (slugs), `version`, `last_edit_source`, `updated_at`, soft `deleted_at` |
| `wiki_folders` | `id`, `parent_id`, `name`, materialized `path` |
| `wiki_page_revisions` | snapshots of superseded content, capped at 50 pipeline / 200 total |

- V: New pipeline pages start as `draft` and are published after the batch [18]. API and agent pages default to `published` [15].

## Q2. Agent-facing access

| Tool | Inputs | Output (V) | Limits / errors (V) |
|---|---|---|---|
| `wiki_search` (MCP, agent) [7][12][14] | `query` (POSIX regex; literal if invalid), `regex?`, `knowledge_base_ids?`, `limit` | Text: each `<page>` has the KB ID, `[[slug\|title]]`, type, aliases, summary and snippet. Data: `found_kbs` | Default 10, max 50. Ranking is title > slug > summary > content. Excludes only `archived`. Aliases aren't in the SQL predicate. Errors: no wiki in scope, KB out of scope, bad regex |
| `wiki_read_page` (MCP: `slug`, optional KB; agent: `slugs[]`) [7][10][11] | slug(s) | `<wiki_page>`: KB ID, `[[slug\|title]]`, type, aliases, `links_to`/`linked_from` (≤20 neighbour summaries), `<sources>`, summary, content. Data: `ambiguous_slugs`, `truncated_slugs`, `omitted_slugs` | Bodies share the output budget fairly (≥400 runes each). Overflow goes to `<omitted_pages>`. Ambiguous slugs return every match. Errors: "not found", or "none of its source documents are within the scope" |
| `wiki_index` (MCP) [7][16] | `knowledge_base_id`, `limit` | `{intro, groups[{type,total,items[{slug,title,summary,wiki_path,…}],next_cursor}]}` | Max 200 per type. The handler passes cursor `""`, so only the first window can be reached |
| `wiki.list_folders` (op) [21] | KB, `parent_id?` | Child folders, `page_count`, `has_children` | Up to 200. The only directory walk. Listing pages is not exposed |
| `wiki.get_page` (op) [21][28] | KB, `slug` | slug, title, type, status, summary, folder_id, version, updated_at | No content. Strings capped at 2,000 runes |
| `read_document` (MCP) [26] | `knowledge_id` from `<sources>` | Document metadata and chunks | The KB must be in the endpoint scope |

## Q3. Page identity

- V: The slug is unique per KB among live rows. Summary pages use `summary/<knowledge-uuid>`. Re-ingest prompts ask the LLM to reuse old slugs [1][2].
- V: `move_page` changes only `folder_id`. The path is a cache, not an address [2].
- V: `wiki_rename_page` [15][25]:
  1. Creates a new row with a new UUID; its version restarts at 1.
  2. Rewrites `[[old]]` and `[[old|` in inbound pages.
  3. Deletes the old row and its revisions.
- V: No alias or redirect is kept for the old slug.

## Q4. Source attribution

| Writer | Stored `source_refs` [3] | Agent read | UI |
|---|---|---|---|
| Ingest [17] | bare knowledge ID ("so the filename does not leak" into prompts) | `<source knowledge_id="…"/>`, no title [11] | live title per ID; a truncated ID if the doc is "deleted or is inaccessible" [20] |
| Agent write tools [19] | `id\|title` from the knowledge row at write time | snapshot title | snapshot title (no lookup) |

- V: `chunk_refs` are never shown to agents, and inline `[cNNN]` markers are stripped [11][15].
- V: The summary page title is copied at ingest as `<doc title> - Summary` [18].
- V: Deleting a document [23]:
  1. Writes a tombstone and scrubs pending ingest.
  2. Queues an LLM retract task that is given the doc title.
  3. Strips the ref and chunk refs, or soft-deletes pages that have no refs left.
  - Errors are only logged.
- V: `UpdateKnowledge` writes only the knowledge row, so a title edit never reaches the wiki [24]. I: Summary titles and `id|title` snapshots stay stale until a rewrite.
- V: Re-upload keeps the UUID (earlier note). Re-ingest swaps the document's contribution, and nothing is retracted at reparse time [23].

## Q5. Authorization

- V: HTTP reads require Viewer plus `KBAccessRead`. Writes require ownership plus `KBAccessWrite` [27].
- V: MCP [6][8]:
  - Every call goes through an allowlist and a rate limit.
  - Each configured KB is re-resolved at Viewer level. An unrestricted endpoint gets every KB the caller can list.
  - Image URLs in the output are rewritten only after a per-resource check.
- V: Agent `WikiScope` narrows silently by document or tag. A page passes if **any** source ID is allowed. Index and uncited pages are hidden under such a scope [9].
- V: The repository reads filter only by KB ID (search also by status) [13][14].
- I: There is no per-document ACL. A page with mixed sources comes back whole, including `id|title` refs to excluded documents.

## Q6. Freshness and labelling

- V: Agent page reads carry no `version`, `updated_at`, `status` or edit source. Draft pages are readable, because `GetBySlug` has no status filter [10][13].
- V: Only `wiki.get_page` and `list_revisions` (in-product) show version and status [21].
- V: The generated-content label is just the tool name and `page_type`.

## Facts that bear on B1(c)

- **For humans, WeKnora settled on a stored ID with a live title** [17][20]. The stated reason is keeping filenames out of generated text. I: This is close to (c), but the lookup lives in the UI.
- **Agents get no lookup** [11]: either no title or a write-time snapshot. I: A projection copy is missing or stale, which is exactly what (c) avoids.
- **Title edits don't propagate, and the summary title copies the document title** [18][24]. I: Any title-derived projection field needs an owner to refresh it or clear it.
- **Deletion cleanup happens projection-side and is best-effort** [23]. I: Under (c), a cleared record removes titles from results whatever the projection's lag.
- **Wiki reads show no source URL.** `Knowledge.source` (the URL for URL imports) appears only in `list_documents` [26].
- **The slug is the public ID and the UUID is internal. A rename breaks the slug without a redirect** [25].
- **Live lookup fails soft:** a deleted or forbidden document shows as a truncated ID [20]. I: This is precedent for clearing rather than erroring.

## Open points

1. The docs don't say whether leaving titles out of agent output is intended.
2. How well the LLM retract removes deleted-source text has not been tested.
3. The note didn't check how long soft-deleted page rows, which still hold title and content, are retained.
4. Runtime behaviour is unchecked: no MCP session was run.

## Sources

All code links are permalinks at the pinned commit.

1. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/website-docs/03-features/14-wiki.md#L130-L314>
2. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/wiki_page.go#L191-L342>
3. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/wiki_page.go#L839-L864>
4. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/types/wiki_page.go#L428-L461>
5. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/website-docs/03-features/08-mcp.md#L34-L60>
6. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/server.go#L131-L222> <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/resource_urls.go#L27-L31>
7. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/tools_wiki.go#L13-L187>
8. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/scope.go#L38-L272>
9. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/wiki_tools.go#L109-L319>
10. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/wiki_tools.go#L321-L449>
11. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/wiki_tools.go#L502-L750>
12. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/wiki_tools.go#L764-L1029>
13. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/repository/wiki_page.go#L343-L354>
14. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/repository/wiki_page.go#L1487-L1531>
15. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_page.go#L34-L95> <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_page.go#L439-L517>
16. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_page.go#L560-L622>
17. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_ingest_batch.go#L1396-L1419>
18. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_ingest_batch.go#L1997-L2037> <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/wiki_ingest.go#L2370-L2384>
19. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/wiki_source_refs.go#L12-L89>
20. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/frontend/src/views/knowledge/wiki/WikiBrowser.vue#L1345-L1393>
21. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/wiki_page.go#L160-L479> <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/handler/wiki_page.go#L607-L1271>
22. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/operations.go#L124-L132>
23. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/knowledge_delete.go#L180-L393>
24. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/application/service/knowledge.go#L840-L903>
25. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/tools/wiki_rename_page.go#L84-L150>
26. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/mcpserver/tools_retrieve.go#L281-L376>
27. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/router/routes_knowledge.go#L344-L394> <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/CHANGELOG.md#L26-L34>
28. <https://github.com/Tencent/WeKnora/blob/dacb9c2643bdfe7b3f95e0d96e1584513b27f3a2/internal/agent/operations/projection.go#L11-L27>
