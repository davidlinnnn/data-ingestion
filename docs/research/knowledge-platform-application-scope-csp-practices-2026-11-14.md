# Application scope and user entitlement: CSP and authorization-engine practices

**Research date: 2026-11-14. Status: kept survey of vendor documentation and standards. It supports a direction that is recorded and not adopted, [authorization design §12](../design/knowledge-platform-authorization.md#12-application-scope-a-direction-not-adopted).**

## Question

A knowledge platform ingests documents from a knowledge-management system, grouped into spaces. That system already keeps "which user can read which space" in the company's central authorization service. Several agent applications built on the platform serve those documents to users, and each application may be allowed only some of the spaces. The proposed rule:

```text
a user U, through application A, may read a document in space S
only if  U can read S   (the knowledge-management system's relations)
    and  A is allowed for S   (a setting the platform owns)
```

Five questions follow from it:

1. Is "effective permission = the user's permission ∩ the application's scope" established practice for delegated access, and how do vendors treat access with no user present?
2. Who administers the application half, and at what granularity?
3. Where is the intersection computed: in the policy engine, or by the enforcing service?
4. How is it applied to search and retrieval, where a list is filtered?
5. Which pitfalls do the vendors document?

## Method

An agent survey read primary sources on 2026-11-14: vendor documentation, RFCs and IETF drafts. Every quotation below was read on the live page, with the page's date where the page shows one; what could not be opened is listed under "Could not verify". Seven quotations were read a second time on the same day and matched: Microsoft Graph Selected permissions [4], GitHub Apps [29] and RFC 9700 §2.3 [43].

## Answer

Yes, this is established practice for delegated (on-behalf-of) access, and several vendors state it as a rule. Microsoft Graph's `*.Selected` permissions are the closest match to the proposed design: an application gets a role on a container (site, list, item or file), stored in the resource system as an (application, resource, role) tuple, and in delegated mode SharePoint "intersect[s]" it with the user's own permissions. GitHub, Snowflake, Databricks, Azure AI Search, AWS and RFC 9700 state the same two-sided bound. Every vendor also has an app-only mode, where the app's own grant alone decides, and labels it higher risk. Commercial products compute the intersection at the enforcing service, which receives both identities on one request. Zanzibar-style engines offer an in-schema intersection (`&` in SpiceDB, `and` in OpenFGA) or caller-combined checks; OpenFGA's agent docs recommend a batch check. For RAG, the app is bound to data stores or containers and per-user ACL trimming runs inside the retrieval engine. Documented pitfalls: defaults when the app scope or user token is missing (they differ), stale ACL snapshots, user identity asserted by the app but never verified, and audit records that must carry both identities.

## Comparison table

| System | User half: store, owner | App half: store, owner, granularity | Where the intersection is computed | App-only mode | Sources |
|---|---|---|---|---|---|
| Microsoft identity platform / Graph (delegated) | The resource's own RBAC/ACL (e.g. SharePoint, Exchange); resource owner/admin | Entra consent grant (`oauth2PermissionGrant`) → `scp` claim; the user or an admin consents; per API permission (e.g. `Files.Read.All`) | Resource server checks `scp` and the user's own rights | Application permissions (app roles), admin consent only | [1][2][3] |
| Graph `Sites.Selected` / `*.SelectedOperations.Selected` | SharePoint permissions | (app ID, resource, role) tuple stored in SharePoint; an admin consents to the scope and "delegat[es] management" to resource owners; site collection, list, list item/folder, file | Inside SharePoint: "calculated and then intersected" | Same scopes in application mode; the app's record alone decides | [4] |
| Teams resource-specific consent | Team/chat membership | Per installed team, chat or meeting; installer (team owner/member) | Teams/Graph | App-only RSC, granted only by admins or resource owners | [5] |
| M365 Copilot declarative agents; Copilot Studio | SharePoint/Graph ACLs, semantic index | Agent manifest or knowledge config written by the agent maker; sites, folders, files, ≤5 Teams chats, mailbox folders, Dataverse tables | Copilot retrieval: searches the configured sources "that a user has access to" | Maker-provided credentials; embedded files visible to "any user who can access the agent" | [6][7][8][9] |
| Azure AI Search (permission filters, preview) | ACL/RBAC/label metadata synced into the index from the source | Azure RBAC role on the index (e.g. Search Index Data Reader); Azure admin; whole index | Search engine; one request carries two tokens (`Authorization` + `x-ms-query-source-authorization`) | Token omitted → only public docs; admin `x-ms-enable-elevated-read` | [10][11] |
| AWS trusted identity propagation, S3 Access Grants | Access Grants to Identity Center users/groups; S3 admin | IAM role policy of the app (e.g. `s3:GetDataAccess`) + Identity Center application scopes; AWS admin | Receiving AWS service, from one identity-enhanced session carrying both | Plain IAM role session | [12][13][14] |
| Amazon Q Business (incl. data accessors) — closed to new customers | Document ACLs crawled into the index + User Store | Application ↔ data sources; data accessor `filterConfiguration` by `_data_source_id` + an end-user subset; customer admin | Inside Q (`SearchRelevantContent`) | — | [15][16] |
| Bedrock Managed Knowledge Base (ACL-aware) | Allow/deny users and groups crawled with app-only (2LO) connector credentials | Which KB the app calls (IAM); granularity not verified | KB filters on the user context the app supplies; optional real-time recheck at the source | The app supplies the identity; the KB "does not authenticate end users" | [17] |
| Bedrock AgentCore Gateway + Policy (Cedar) | OAuth claims in the inbound JWT | Cedar policies per gateway/tool target; platform admin; per tool | One Cedar decision per tool call at the gateway | Outbound 2LO client credentials | [18][19] |
| Verified Permissions (Cedar) for RAG | Cognito groups in the JWT | AVP policies; the app turns the decision into a KB metadata filter | App middleware combines them | — | [20][21] |
| Gemini Enterprise / Vertex AI Search | `acl_info` readers per document; the IdP identifies the user | App ↔ data stores (many-to-many), per-app/per-store IAM (2026-09-28), Jira project action filters; admin | Search service | Not documented on the pages read | [22][23][24] |
| Google Credential Access Boundaries | Service account IAM | Boundary set by the token holder/broker; per bucket, optional object/folder condition | Google STS/Cloud Storage (an "upper bound") | — | [25] |
| Google Workspace domain-wide delegation | — | OAuth scopes per client ID; super admin | Scopes are the only bound | Is the app-only mode: access to "all of your users" | [26][27] |
| GitHub Apps | Repo/org permissions | Installation with "select repositories" + app permissions; org owner/repo admin | GitHub: "both the user and app" | Installation access token, attributed to the app | [28][29][30] |
| Snowflake restricted caller's rights | Caller's role privileges | Caller grants on the executable owner's role; administrators; object, schema/db/account (inherited), privilege | Snowflake engine | Owner's rights | [31] |
| Databricks Apps | Unity Catalog permissions | App scopes; `CAN MANAGE` users add them, workspace admins can restrict them | Databricks platform | App service principal shared by all users | [32] |
| SpiceDB / AuthZed | Relationships | Can be modelled; the official agent example derives agent access from the user | Either in-schema `&` or caller; caveats add request context | — | [33][34][35][36] |
| OpenFGA / Auth0 FGA | Tuples | Agent/task tuples; contextual tuples per request | In-model `and`, or a caller batch check of user and agent | — | [37]–[42] |

## Q1. Is "user ∩ app scope" established? What about app-only?

- Microsoft Graph: "in a delegated scenario, the privileges that an app has to act on behalf of a user is determined by the Microsoft Graph permissions that the app has been granted *and* the user's own permissions." App-only: "Application permissions are highly privileged … the delegated permission model is the recommended approach whenever it meets the application's requirements." [3] (updated 2026-09-04)
- Entra: "Both the client and the user must be authorized separately to make the request"; with application permissions, "The application is able to access any data that the permission is associated with." [1] (updated 2026-06-25)
- `*.Selected`: "In the delegated scenario, both the application and user permissions are calculated and then intersected, which means that the application can never exceed the user's permissions, and the user can never exceed (through the application) the consented application permissions." "Application only scenarios have no user present and are considered higher risk." [4] (updated 2026-02-26)
- GitHub: "A GitHub App user access token only has permissions that both the user and the app have … a user access token can only access resources that both the user and app can access." [29]
- Snowflake: "the caller must already have the SELECT privilege on the table and the caller grant must allow the stored procedure to run with the SELECT privilege." [31]
- Databricks: "Databricks blocks access to any functionality outside the approved scopes, even if the user has permission." [32] (updated 2026-11-12)
- RFC 9700 §2.3: privilege restriction "prevents clients from exceeding the privileges authorized by the resource owner. It also prevents users from exceeding their privileges authorized by the respective security policy." [43] RFC 8693 §1.1: under impersonation A "is indistinguishable from B"; "With delegation semantics, principal A still has its own identity separate from B." [44]

## Q2. Who administers the app half, and at what granularity?

- Resource owner: for `*.Selected`, an admin's consent means "delegating management of resource permissions to the owners of that resource". Access needs consent, a `POST …/permissions` grant and a matching token. [4] App-only Teams RSC is granted only by "administrators or resource owners". [5]
- Tenant admin: picks "Allow all or Allow specific data sources" for a Q data accessor [16]; sets Snowflake caller grants [31]; assigns Gemini apps and data stores per principal (2026-09-28) [24].
- App maker: a Copilot Studio agent "searches only the folder or site URL you register, and its subfolders." [7]
- App installer: GitHub org owners, or repo admins limited to "the repositories that they administer." [30]

Granularity ranges from a whole store or index (Azure, Gemini, Q), through containers (site, list, repository, Jira project, bucket), to single files (`Files.SelectedOperations.Selected`).

## Q3. Where is the intersection computed?

- At the resource, in one evaluation, with both identities on the request: SharePoint `*.Selected` [4]; Azure AI Search, where "Document visibility requires both: The calling application's RBAC role (Authorization header). The user identity carried by x-ms-query-source-authorization." [11]; AWS, where "The token represents both the identity of the application (the IAM principal itself) as well as the directory user's identity." [13] AWS also says each receiving service decides whether to use the user context: "the called AWS service determines if resource authorization is based on the user … or … on the role." [14]
- Cedar at a gateway: "Policies use Cedar … [on] OAuth claims like username, role, or scope"; "Cedar policies evaluate every agent-to-tool request at the gateway before execution, with a default-deny posture where forbid always wins over permit." [19]
- Zanzibar-style engines support intersection in the schema: SpiceDB's `&` includes "only … subjects that were found in **both** relations/permissions" [33], and OpenFGA's `and` holds "if the user is in all the sets of users" [38]. Their agent guidance, though, combines checks in the caller or derives the agent's access from the user:
  - OpenFGA: "If you want to check for both user and agent permissions, perform a batch check call." [40] Its task-based guide says "This means two separate checks: one to verify the user has access to a resource", while `can_call` "requires both that the task has been granted access" and an agent link. [41]
  - SpiceDB's agent schema, `view = reader + edit + reader->delegates + writer->delegates`, derives the agent's access from the user and has no agent grant to intersect. [34]
  - Request context: SpiceDB caveats return a conditional result when "required context is missing" [35]; OpenFGA contextual tuples "exist only for the duration of the request" (max 100). [39]
- App-side combination, with a warning attached: the AVP RAG middleware "converts that policy decision into a metadata filter", and the pattern "is not a substitute for hard tenant isolation." [21]

## Q4. Search / RAG

- Bind the app to data stores, then trim by user. Gemini: "An app must be connected to a data store in order to use the data from it" [23]; access control "limits the data that users can view in your search app's results." [22]
- Q data accessor: "The ISV will only have access to the data from the specified data source id", applied as `documentAttributeFilter` on `_data_source_id`. [16]
- Azure: the engine builds the security filter, which is "automatically appended to any filters that might come in with the query." [11]
- Bedrock: "Pre-retrieval filtering" plus "Real-time ACL verification", which "catches permission changes that occurred between syncs." [17]
- SpiceDB: pre-filter ("ask SpiceDB 'which documents can this user access?'") for a large corpus where users see a small share; post-filter (`CheckBulkPermissions`) for a small corpus with broad access. [36] Auth0 FGA post-filters: the backend "fetches relevant documents from a vector database and then makes a permission check call." [42]
- Cedar: "Listing is similar to resource creation — you authorize against a container resource", i.e. "all-or-nothing at the container level." [20]

## Q5. Pitfalls

- **Confused deputy.** MCP: servers "MUST validate that access tokens were issued specifically for them as the intended audience" (2026-07-28 [45]) and "MUST NOT pass through the token it received from the MCP client" (2025-11-25 [46]). AWS lists as an anti-pattern "Failing to propagate user identity context … every call runs with the agent's permissions." [18] Maker credentials "could lead to oversharing." [9]
- **No user present.** With end-user credentials enforced, "agents triggered by scheduled or autonomous events … fail due to missing credentials." [9] OBO: "*Roles* remain attached to the principal (the user) and never to the application." [47]
- **Identity propagation.** Entra OBO [47]; AWS `CreateTokenWithIAM` + `AssumeRole` `ProvidedContexts` [13][14]; RFC 8693 `act`/`may_act`, "Prior actors … are informational only" [44]; Transaction Tokens carry "user identity, workload identity and authorization context throughout the Call Chain" (draft -11, 2026-07-30) [48]. Bedrock: "ACL awareness is not authorization … your application is responsible for authenticating users and passing verified identity context." [17]
- **Staleness.** Azure: changes "are only reflected … after that metadata is synchronized" [10]; Bedrock: "Group memberships are as fresh as the last sync" [17]; SpiceDB ZedTokens protect "against the New Enemy Problem" [35a]; DWD changes "can take up to 24 hours" [26].
- **Auditing both identities.** CloudTrail logs the role plus `onBehalfOf.userId` [14]; GitHub shows the user "along with the app's identicon badge" [28]; (`sub`, `act`) "provide essential information for auditing" [49].
- **Default when a relation is missing (varies).** Closed: `*.Selected` "would initially have no access" [4]; AgentCore Policy default-deny [19]; Bedrock "fails closed" [17]; Azure returns "only public documents" without a user token, after earlier previews "returned all documents" (changed Nov 2025) [11]. Open: Q data accessor with no data source id "will have access to all the data sources" [16]; GitHub tokens without `repositories` cover all granted repos [30]; both Copilot Studio credential modes are on "By default" [9].

## Contradictions and open points

- Engine or caller? No source makes the in-engine intersection mandatory. OpenFGA documents both ways, and SpiceDB's agent example does not intersect at all. Commercial products compute it at the resource, but there one service holds both halves, unlike the proposed split-owner setup.
- Ingest app-only, enforce per user: Bedrock connectors crawl with 2LO [17]; Graph connector agents "require Microsoft Graph application permissions" [3].
- Not every app scope narrows access. M365 embedded files are visible to anyone who can reach the agent [6], and maker credentials replace the user's rights instead of intersecting with them [9].
- Q Business is "no longer open to new customers" [15]. Azure AI Search ACL enforcement is preview [10].
- draft-oauth-ai-agents-on-behalf-of-user-02 (an individual draft) expired 2026-02-27. No `draft-ietf-oauth-*` WG draft targets agents. The adjacent WG drafts are identity-chaining-17, transaction-tokens-11 and identity-assertion-authz-grant-06. [49][50]

## Could not verify

All UNVERIFIED:
- Older Microsoft wording "least-privileged intersection of the delegated permissions … and the privileges of the currently signed-in user": not on the current [1] or [3].
- S3 Access Grants grant granularity (bucket/prefix/object): page not opened.
- "SearchRelevantContent only retrieves data the end users have access to": search summary only, not on [16].
- Outbound section of the AWS Security Blog post on AgentCore user authorization context (2026-08-19): page truncated.
- Bedrock "IAM can't condition on metadata filters" and AgentCore Policy "LOG_ONLY is the default": search summaries only.
- MCP 2026-07-28 security-considerations subpage not opened; the passthrough sentence is cited from 2025-11-25.
- Gemini Enterprise: handling of documents without ACLs, and ACL refresh cadence: not on the pages read.
- OpenFGA task-based `can_call` DSL: not shown on the page.
- A June 2026 OAuth WG recharter covering agents: claimed only by an individual draft.

## Sources

[1] https://learn.microsoft.com/en-us/entra/identity-platform/permissions-consent-overview
[2] https://learn.microsoft.com/en-us/entra/identity-platform/delegated-access-primer
[3] https://learn.microsoft.com/en-us/graph/permissions-overview
[4] https://learn.microsoft.com/en-us/graph/permissions-selected-overview
[5] https://learn.microsoft.com/en-us/microsoftteams/platform/graph-api/rsc/resource-specific-consent
[6] https://learn.microsoft.com/en-us/microsoft-365-copilot/extensibility/knowledge-sources
[7] https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-add-sharepoint
[8] https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-privacy
[9] https://learn.microsoft.com/en-us/microsoft-copilot-studio/configure-no-maker-authentication
[10] https://learn.microsoft.com/en-us/azure/search/search-document-level-access-overview
[11] https://learn.microsoft.com/en-us/azure/search/search-query-access-control-rbac-enforcement
[12] https://docs.aws.amazon.com/singlesignon/latest/userguide/trustedidentitypropagation-overview.html
[13] https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-grants-directory-ids.html
[14] https://docs.aws.amazon.com/singlesignon/latest/userguide/trustedidentitypropagation-identity-enhanced-iam-role-sessions.html
[15] https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/connector-concepts.html
[16] https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/data-accessors-granting-permissions.html
[17] https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-acl.html
[18] https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentsec02-bp01.html
[19] same as [18] (Policy section); https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/key-features-and-benefits.html
[20] https://docs.cedarpolicy.com/bestpractices/bp-authorization-patterns.html
[21] https://aws.amazon.com/blogs/architecture/secure-multi-tenant-rag-with-amazon-bedrock-and-verified-permissions/ (2026-06-22)
[22] https://docs.cloud.google.com/generative-ai-app-builder/docs/data-source-access-control
[23] https://docs.cloud.google.com/gemini/enterprise/docs/apps-data-stores
[24] https://docs.cloud.google.com/gemini/enterprise/docs/release-notes
[25] https://docs.cloud.google.com/iam/docs/downscoping-short-lived-credentials
[26] https://developers.google.com/workspace/guides/create-credentials
[27] https://knowledge.workspace.google.com/admin/apps/control-api-access-with-domain-wide-delegation (updated 2026-11-10)
[28] https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-with-a-github-app-on-behalf-of-a-user
[29] https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
[30] https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party ; https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation
[31] https://docs.snowflake.com/en/developer-guide/restricted-callers-rights
[32] https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth
[33] https://authzed.com/docs/spicedb/concepts/schema
[34] https://authzed.com/learn/spicedb-schema-examples/ai-agents
[35] https://authzed.com/docs/spicedb/concepts/caveats ; [35a] https://authzed.com/blog/spicedb-secures-authorization-for-ai (2026-07-27)
[36] https://authzed.com/docs/spicedb/integrations/pinecone
[37] https://openfga.dev/docs/use-cases/ai-agent-authorization
[38] https://openfga.dev/docs/configuration-language
[39] https://openfga.dev/docs/interacting/contextual-tuples
[40] https://openfga.dev/docs/modeling/agents/agents-as-principals
[41] https://openfga.dev/docs/modeling/agents/task-based-authorization
[42] https://auth0.com/ai/docs/intro/authorization-for-rag
[43] https://www.rfc-editor.org/rfc/rfc9700.html
[44] https://www.rfc-editor.org/rfc/rfc8693.html
[45] https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
[46] https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
[47] https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow
[48] https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/
[49] https://datatracker.ietf.org/doc/html/draft-oauth-ai-agents-on-behalf-of-user-02
[50] https://datatracker.ietf.org/wg/oauth/documents/
