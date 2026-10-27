# Serving-layer entry point: vendor and spec evidence (2026-10-27)

Input for #76 A1: one platform serving layer in front of the Retrieval and Wiki projections, or one external API per projection plus a shared SDK. Evidence only, no recommendation. **V** = read in a primary source fetched this session; **I** = inference by this note.

## Summary

- V: Every product checked exposes **one user-facing query API over many sources** [1][2][8][21]. Azure is per index, but the app sits in front [4].
- V: Engines filter **inside the query** on ACL copies made at index time. Permission changes reach results only after a re-sync [2][5].
- V: The engine is **not the trust anchor**. Kendra and Azure say the app must supply an authenticated identity [1][4].
- V: A **per-result check while serving** appears in Zanzibar (search results "require tens to hundreds of checks") and SpiceDB (post-filter with an over-fetch loop) [12][13]. No vendor search API documents a second check against a system of record.
- V: MCP requires tokens bound to the server's audience, forbids passthrough, and uses separate tokens upstream [20]. AgentCore Gateway follows this [22].
- I: The evidence does not cover separately owned projections that publish on their own, or checks against an admission record. Those are our requirements, not a vendor pattern.

## Q1. Entry point and filter location

| Product | Entry | Filter location | User representation | Post-check |
|---|---|---|---|---|
| Kendra [1] | One `Query` per index over many connectors | In query; per-doc ACL | `UserContext`: a token Kendra validates, or UserId/Groups strings | None |
| Q Business [2][3] | Chat / SearchRelevantContent over all sources | Retrieval; crawled ACL + User Store | Identity-aware SigV4 that the app's "trusted backend" builds: IdP token → CreateTokenWithIAM → `sts:identity_context` → AssumeRole | None |
| Azure AI Search [4][5][6] | Per-index `/docs/search`; agentic retrieve/MCP | In engine: filter "automatically appended" | Strings from the app, or the app's RBAC role **plus** the user's Entra token in `x-ms-query-source-authorization` | None; ACL failure → 5xx, "not a partially filtered result set" |
| Google Agent Search [7] | Search app/API | Not stated | One IdP per location; user OAuth/STS token | Not stated |
| Glean [8][9][10] | "a single search box", one chat surface, one MCP server | Query time, synced ACL; some live fetch | OAuth user token, or a global token + `X-Glean-ActAs` | Source "may enforce access again at click time" |
| Elasticsearch DLS [11] | Read APIs on secured indices | In engine, role query templated with `_user` | Elastic user/role | None |

Notes (V): Kendra says "User context filtering isn't an authentication or authorization control… It is up to your application…", and with no UserContext it "returns all documents" [1]. An early Azure preview returned everything when the user token was missing; that changed in Nov 2025 [5]. Q Business treats User Store edits as privileged because they can change who sees what [2]. Google allows 3,000 readers per document and sets access control only at data-store creation [7]. Elasticsearch DLS doesn't change scoring statistics, and aggregations can leak terms from inaccessible documents [11]. Glean MCP checks the token "before each tool invocation" [9].

## Q2. Second verification at response time

- V Zanzibar [12]: serving search results "often require tens to hundreds of checks". Clients use Expand to "build efficient search indices for access-controlled content". Zookies prevent the "new enemy" problem (an old ACL applied to new content).
- V SpiceDB [13][14]: you can pre-filter with LookupResources, which is "a heavy request… when more than 10k results are involved". For large sets, "we recommend postfiltering with CheckBulk". A post-filter must "iterate until we have a full page of accessible results". Its cost depends on candidate page size, and cursor pagination works better. Run all checks at one revision.
- V SpiceDB + LangChain [15]: retrieve by similarity, then check before the LLM. Metadata filtering "Cannot express relationship-based permissions" and has "No audit trail".
- V Azure [6]: native in-engine filtering "Improves performance versus post-query trimming".
- I: The vendors split the work. The engine pre-filter protects recall and top-k. A post-check against the authority covers changes the index has not yet absorbed, and it costs an over-fetch loop.

## Q3. Per-user rate limits and audit

- V Glean [16]: 30 rps per user token (search 5, chat 0.5) plus deployment caps. ActAs calls count toward "the impersonated users's quota".
- V Glean [9]: MCP activity logs record tool use for each server.
- V Google [17]: `SearchService.Search` writes DATA_READ (Data Access) audit logs. The page fetched does not say which principal is recorded.
- V MCP [18]: passthrough bypasses "rate limiting, request validation, or traffic monitoring, that depend on the token audience". Downstream logs then show "a different identity".
- V OWASP LLM08 [19]: keep "detailed immutable logs of retrieval activities".

## Q4. MCP authorization and gateways

- V [20]: The MCP server is an OAuth 2.1 resource server. Clients send an RFC 8707 `resource` naming the server's canonical URI. Servers "MUST validate that access tokens were issued specifically for them" and "MUST NOT accept or transit any other tokens". Upstream calls use "a separate token… MUST NOT pass through".
- V [18]: Passthrough is "explicitly forbidden" because it bypasses security controls, breaks the audit trail and breaks trust boundaries.
- V AgentCore [21][22]: "a single, secure access point". MCP targets are aggregated into "a unified virtual MCP server" behind one inbound authorizer. Each target gets its own outbound credential; the options include OAuth token exchange that "carries both the user's identity and the agent's identity". Passthrough is **not supported** for MCP server targets. AWS advises "separate gateways for different trust boundaries".

## Q5. One enforcement point vs. many

- V OWASP API1 [23]: check access in "every function that uses an input from the client to access a record".
- V OWASP API5 [24]: use a "consistent and easy-to-analyze authorization module… invoked from all your business functions", with deny by default.
- V OWASP LLM08 [19]: use "permission-aware vector and embedding stores". Shared stores risk "context leakage between users".
- V NIST 800-207 [25]: "The PDP/PEP cannot apply additional policies beyond its location in the flow of traffic". Zero trust moves "the PDP/PEPs closer to the resource".
- V Zanzibar [12]: one authorization system lets you build "a search index that respects access control and works across applications".

## Facts that bear on A1

- **One entry is the norm** [1][2][8][21]. I: In those products one owner holds both the surface and the stores. Our projections publish independently, so the norm shows feasibility but does not decide ownership.
- **Pre-filtering by the readable set** matches Kendra, Azure and LookupResources [1][5][13]. I: Our `list_resources` returns Resource IDs, likely far fewer than 10k. Not measured.
- **Index copies lag the authority** [2][5]. Our authorization §4.2 stops binding-change disclosure "on the E2 path". I: No vendor sells a post-check against an admission record, so whichever option we pick has to own it.
- **A post-check costs over-fetching** [13]. I: Keeping top-k stable needs over-fetch inside each projection, or an iterate-until-full loop at the entry.
- **The trust anchor is the caller of the engine** [1][4]. Azure's early default leaked everything without a user token [5]. I: With per-projection APIs, each projection is its own anchor and can repeat that mistake on its own.
- **No user-token forwarding** matches MCP [20] and AgentCore [22]. I: Under either option, projections receive a subject or constraints that the platform asserts.
- **Quotas are keyed on the end user** at Glean's single API [16]. I: With per-projection APIs, a caller could get N× the budget unless the quota is shared.
- **Fail closed:** Azure returns 5xx, not partial results [5], which matches our authorization §4.3.

## Open points not answered by primary sources

1. A cross-store serving layer where the stores are owned by separate teams that publish on their own.
2. A product that re-checks results against records other than the ACL authority, such as deletion, rebinding or copy lineage.
3. Whether Google Agent Search filters before or after ranking, and how it behaves with multiple stores [7].
4. Measured latency of post-filter loops at a given authorized ratio.
5. Whether a multi-backend gateway keeps quotas centrally (AgentCore pages fetched were silent).
6. Derived pages that a user may see only if they can read every source.

## Sources

1. https://docs.aws.amazon.com/kendra/latest/dg/user-context-filter.html
2. https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html
3. https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/making-sigv4-authenticated-api-calls.html
4. https://learn.microsoft.com/en-us/azure/search/search-security-trimming-for-azure-search
5. https://learn.microsoft.com/en-us/azure/search/search-query-access-control-rbac-enforcement
6. https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview
7. https://docs.cloud.google.com/generative-ai-app-builder/docs/data-source-access-control
8. https://docs.glean.com/connectors/connectors-power-glean
9. https://docs.glean.com/administration/platform/mcp/security
10. https://developers.glean.com/api-info/client/authentication/overview
11. https://www.elastic.co/docs/deploy-manage/users-roles/cluster-or-deployment-auth/controlling-access-at-document-field-level
12. https://storage.googleapis.com/gweb-research2023-media/pubtools/5068.pdf (Zanzibar, USENIX ATC '19)
13. https://authzed.com/docs/spicedb/modeling/protecting-a-list-endpoint
14. https://authzed.com/docs/spicedb/concepts/querying-data
15. https://authzed.com/docs/spicedb/integrations/langchain-spicedb
16. https://developers.glean.com/get-started/rate-limits
17. https://docs.cloud.google.com/generative-ai-app-builder/docs/audit-logging
18. https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices
19. https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/
20. https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization
21. https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-core-concepts.html
22. https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-outbound-auth.html
23. https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization
24. https://api-security.owasp.org/editions/2023/en/0xa5-broken-function-level-authorization/
25. https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-207.pdf
