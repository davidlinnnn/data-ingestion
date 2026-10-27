# Knowledge Platform 的 agent 身分與使用者身分：委派讀取的業界做法與標準

**研究日期：2026-10-26（Asia/Taipei）。狀態：研究輸入，不是決策。** 承接 [#87](https://github.com/davidlinnnn/data-ingestion/issues/87) 範圍第 3 項（委派 token 與 agent 身分、agent 以自身身分讀取）與 [#85 授權設計](../design/knowledge-platform-authorization.md)的 E1 規則。所有來源於 2026-10-26 查閱；標 **UNVERIFIED** 者未能在官方頁面直接確認。

本文不重複以下研究：搜尋過濾與 ACL 同步（[PDP 模式研究](knowledge-platform-pdp-modes-csp-practices-2026-10-26.md)）、Source 系統的 service credential（[service client authentication](service-client-authentication-csp-practices-2026-10-18.md)）、資料安全面向與邊界表（[資料安全面向](knowledge-platform-data-security-aspects-2026-10-20.md)）。

前提：v1 必須驗證 tSSO 使用者 token，並以它做資料存取控制；agent 身分驗證不是 v1 必要項，但要先收斂一個「agent 身分＋使用者身分」的目標機制。本文假設 agent 以 workload 形式部署（例如 Kubernetes），並分析兩種委派做法：agent 沿呼叫鏈帶著使用者 token，以及換發限定 audience 的委派 token。

## 結論

- **代表使用者讀取時，調查到的產品都以使用者權限為上限，agent 端只加一道粗粒度的閘門。** 這道閘門是註冊、管理者同意、scope 或資料來源範圍，沒有產品再拿 agent 自己的文件層級 grant 取交集。E1（`check(user)` 允許，且 client 已註冊為 delegate；client 自己的 `reader` 不參與）與業界做法一致。
- **agent 以自己的身分讀取時，各家都要求明確授權給 agent 帳號，並記錄 agent。** 風險在讀到的內容被展示給誰：Atlassian 有一筆紀錄：automation 中的 agent 把觸發者無權檢視的 Confluence 頁面連結放進結果（點開是 403，頁面存在與標題已經外露）；Glean 的 service credential 模式讓「每個呼叫者都拿到同一組權限」。KP 能管 grant 與紀錄；內容展示給誰，要寫進與 Agent Platform 的契約。
- **若把同一個使用者 token 沿 agent → tool → KP 轉送，會與 MCP 授權規範及 OAuth 安全 BCP 衝突。** MCP 規定 server 只能接受發給自己的 token，且不得把收到的 token 往下轉送；RFC 9700 要求 access token 限定 audience。衝突的程度取決於 tSSO token 的 `aud` 怎麼設，這點尚未確認。較安全的替代是以 RFC 8693 token exchange 換成 `aud`＝KP、帶 `act`（agent）的短效 token；同一信任域內也可以用 Transaction Tokens。
- **agent 專屬的 OAuth 規範還沒有定案。** WSO2 的 on-behalf-of 草案已過期，actor profile／actor chain 都是個人草案，WIMSE 的 AI agent 文件剛成為 WG 文件。現在能依賴的是 RFC 8693、8707、9700，以及 workload identity：Kubernetes projected ServiceAccount token、SPIFFE。
- **GAM（SpiceDB）可以原生表達委派，但 AuthZed 官方範例的寫法會擴權。** 它以 `reader->delegates` 授權給 agent，agent 因此取得「所有委託人可讀內容的聯集」，與本次請求代表的是誰無關。E1 以 `subject=user` 判定、另外檢查 actor，避開了這個問題。維持 G9 的兩段檢查即可，不需要 GAM 提供額外能力。
- **v1 只驗 tSSO 時，E1 的 delegate 檢查實際上無法執行，因為 client id 是 agent 自己報的。** v1 應把 actor 記為「未驗證」，並把「KP 驗證 `aud`＝KP 的 agent workload token」列為下一階段的前提。

## A. 產品比較

| 產品 | 代表使用者時的存取規則 | agent 怎麼識別 | agent 自身身分的背景讀取 | 稽核歸屬 |
|---|---|---|---|---|
| **Microsoft Entra Agent ID／Microsoft 365 Copilot** | 使用者權限 ∧ agent 被授予的 delegated scopes。「The application isn't able to access anything the signed in user couldn't access.」Copilot「only surfaces organizational data to which individual users have at least view permissions」。 | Agent identity blueprint（範本）與 agent identity（實例）；以 managed identity／FIC 取得 T1，再拿使用者 token Tc 做 OBO。Tc 的 `aud` 必須是 blueprint，送錯 audience 的 token 會被拒（`AADSTS50013`）。 | App-only：用 application permissions（app roles），只有管理者能同意；可讀該權限涵蓋的全部資料。另有 agent's user account（`agentIDuser`）。 | Sign-in log 有 `agentSignIn` 類型；audit log 以 `agentType` 標示 agent 參與（`initiatedBy`／`performedBy`）。 |
| **Google Agent Identity／Gemini Enterprise** | User-delegated authority 走 3-legged OAuth（Preview）；搜尋結果依使用者 ACL（見 PDP 模式研究）。 | 每個 agent 一個 SPIFFE ID（`spiffe://…/resources/SERVICE/…`）與 IAM principal；access token 與 agent 的 X.509 憑證綁定（mTLS，經 Agent Gateway 另加 DPoP）。 | 「agent's own authority」：以自己的 principal 存取 Google Cloud 服務，靠 IAM 授權。 | 「When an agent acts on a user's behalf, logs show both the agent's and user's identities.」 |
| **Amazon Q Business data accessor**（Q Business 已停收新客戶） | 管理者設定 accessor 可用的資料來源（全部或指定）與可用的使用者；身分經 IAM Identity Center trusted token issuer 帶入。結果依使用者 ACL 過濾，此說法來自 AWS blog，API 文件未明寫（**部分 UNVERIFIED**）。等同使用者 ∧ accessor 設定。 | ISV 的 IAM role ARN＋tenant ID。 | 未提供，只支援 `SearchRelevantContent`。 | CloudTrail（細節 UNVERIFIED）。 |
| **Amazon Bedrock AgentCore Identity** | Workload access token「contain both user identity and agent identity」，以 user–agent 組合限定 token vault 中的 credential。 | Workload identity；Runtime 先驗證 inbound JWT 的 `iss`／`sub`，再換發 workload access token。 | 2-legged OAuth（M2M）。 | AWS 明示風險：`GetWorkloadAccessTokenForUserId`「does not verify」userId，建議改用 JWT 路徑，並在 CloudTrail 記錄 IAM principal 與 userId 的對應。 |
| **Glean**（agent identity 為 beta） | 預設「runs under the identity of the user who invokes it」。 | 呼叫者身分，或管理者掛上的 service credential。 | Service credential 模式下「Every invoker gets the same credentials and permissions」，不與呼叫者取交集。 | 「Actions are authored by the agent's own account; the triggering user or schedule is logged separately.」 |
| **Salesforce Agentforce**（**UNVERIFIED**：help 頁面需 JS 載入，只看到搜尋摘要） | Employee agent 以登入使用者的 execution context 執行，受其 profile、permission sets、sharing 限制。 | Service agent 是專用的 agent user（Einstein Agent User profile，沒有密碼）。 | Service agent 以 agent user 的權限讀取；啟用 credential-based user verification 時改以登入的網站使用者身分。 | 未查到官方說明。 |
| **Atlassian Rovo** | 「User's account」模式下，agent 擁有使用者的全部權限；在 automation 中則用**建立 automation 的人**的權限。 | User's account 或 Agent's account（由管理者授權）。 | Agent's account 有自己的權限，官方建議 automation 使用這個模式。 | User's account 模式記在使用者或 automation 建立者名下；Agent's account 模式記在 agent 名下。[AUTO-2337](https://jira.atlassian.com/browse/AUTO-2337)／[ROVO-837](https://jira.atlassian.com/browse/ROVO-837)：結果含觸發者無權檢視的頁面連結（只發生在 automation，Rovo Chat 不會），官方稱「intended behaviour」；要求改為「intersecting permissions」的 feature request 仍在 Gathering Interest。 |
| **Okta Cross App Access／MCP Enterprise-Managed Authorization** | 使用者身分 ∧ IdP 管理者為 (agent app, resource app) 設定的政策。IdP「evaluates administrator-defined policies for the token exchange request」。 | 以 RFC 8693 從 IdP 換得 ID-JAG，再以 RFC 7523 jwt-bearer 向 resource 端 AS 換 access token。 | MCP 另有 OAuth Client Credentials 擴充（stable 2026-07-28）。 | Okta System Log 細節 **UNVERIFIED**。 |
| **Auth0 for AI Agents** | RAG：向量庫先取候選，再逐份向 FGA 檢查，「only sends the authorized documents to the LLM」。 | Token Vault 代為保管第三方 token（細節未直接讀到）。 | Async authorization（CIBA）處理需要人核准的動作。 | 未查到。 |

**觀察：**

1. 委派讀取 = 使用者權限 ∧ agent 層級的粗閘門，是一致的做法。閘門可以放在 IdP（Okta、Entra 的同意與 scope）或資源端（Q 的 accessor 設定），E1 的 delegate 註冊屬於資源端這一型。
2. 兩個公開的擴權案例（Rovo automation、Glean service credential）都出在「agent 用某個固定身分讀取，再把結果給另一個人看」。
3. 有提供 agent 身分的產品，都會同時記錄 agent 與使用者（Entra、Google、Glean、AgentCore）。

## B. 標準與規範的原文

**MCP Authorization（現行版本 2026-07-28；2025-11-25 版措辭相同）**

- 「MCP servers **MUST** validate that access tokens were issued specifically for them as the intended audience」「MCP servers **MUST** only accept tokens that are valid for use with their own resources.」「MCP servers **MUST NOT** accept or transit any other tokens.」
- 「If the MCP server makes requests to upstream APIs … The access token used at the upstream API is a separate token … The MCP server **MUST NOT** pass through the token it received from the MCP client.」
- Security Best Practices 把 token passthrough 定為 anti-pattern，列出四類風險：繞過以 audience 為依據的控制（rate limit 等）；稽核無法分辨 client，下游記錄的身分也錯置；「an attacker compromising one service can use the token to access other connected services」；日後難以加上控制。緩解措施只有一句：「MCP servers **MUST NOT** accept any tokens that were not explicitly issued for the MCP server.」
- 適用範圍：授權在 MCP 中是 OPTIONAL，而且只規範 HTTP transport。不過上面列的風險與 transport 無關。

**RFC 8707／RFC 9700：** 「The authorization server SHOULD audience-restrict issued access tokens to the resource(s) indicated」。RFC 9700 §2.3：「access tokens SHOULD be audience-restricted to a specific resource server」。RFC 8707 的安全考量說明，audience-restricted token 被合法出示給某個 resource 之後，該 resource 無法再拿去別處使用；多 audience 的 bearer token 則在每個 audience 都有效。

**RFC 8693 Token Exchange：** 區分 impersonation（「A is given all the rights that B has」）與 delegation（「principal A still has its own identity separate from B」）。`act` claim 用來表達委派已發生，並標出目前的 actor。存取控制「MUST only consider the token's top-level claims and the party identified as the current actor」，巢狀 `act` 只供參考。`may_act` 則宣告「one party is authorized to become the actor and act on behalf of another party」。

**Identity Assertion JWT Authorization Grant（ID-JAG，draft-ietf-oauth-identity-assertion-authz-grant-04，2026-05）：** Okta XAA 與 MCP Enterprise-Managed Authorization 擴充都以它為基礎，由企業 IdP 集中決定哪個 app 可代表哪個使用者存取哪個 resource。

**Transaction Tokens（draft-ietf-oauth-transaction-tokens-11，WG Consensus: Waiting for Write-Up，尚非 RFC）：** 用途是「maintain and propagate user identity, workload identity and authorization context throughout the Call Chain within a trusted domain」。Txn-Token 帶 `sub`、`req_wl`（申請的 workload）、盡量窄的 `scope`，以及請求脈絡 `rctx`／`tctx`，`aud` 是整個信任域。這正好對應「同一 K8s 信任域內的多跳呼叫」。

**A2A 1.0 §7：** credential 由 client 依 Agent Card 的 `securitySchemes`「out-of-band」取得；server「MUST authenticate every incoming request」；授權「implementation-specific」。A2A 沒有規定使用者身分怎麼跨 agent 傳遞。

**AI agent 專屬草案：** draft-oauth-ai-agents-on-behalf-of-user 是個人草案，已過期。draft-mcguinness-oauth-actor-profile、draft-mw-oauth-actor-chain 都是 2026-10 的個人草案。draft-ietf-wimse-aims-00（WG 文件，Informational）只提出最佳實務。draft-ietf-oauth-identity-chaining-17 已送 IESG，處理跨信任域的情境。

**Workload identity：**

- Kubernetes projected ServiceAccount token 可以指定 `audience` 與 `expirationSeconds`；kubelet 在 token 超過 TTL 的 80% 或 24 小時時輪替。
- 自建服務驗證 token 時，官方推薦 TokenReview API：「invalidates tokens that are bound to … Pods … when those objects are deleted」。若改用 OIDC discovery 驗證，token 要到過期才失效。不論用哪一種，「Your application should always define the audience that it accepts」。Issuer discovery（`/.well-known/openid-configuration`、`/openid/v1/jwks`）讓叢集外的系統也能驗證。
- SPIFFE JWT-SVID：「The `aud` claim MUST be present」；也是 bearer token，「susceptible to replay attacks」，建議縮短 `exp`。

**Sender-constrained tokens：** RFC 8705（mTLS）與 RFC 9449（DPoP）把 token 綁在持有者的金鑰上，偷到 token 也無法單獨使用。RFC 9700 §2.2.1 建議採用。Google Agent Identity 已預設 mTLS＋DPoP。

## C. 在 GAM（SpiceDB）中表達 E1

AuthZed 的 [AI agents 範例](https://authzed.com/learn/spicedb-schema-examples/ai-agents)寫法是 `relation agent: ai_agent` 掛在 `user` 上，文件的 `permission view = reader + … + reader->delegates`。這是聯集：一個服務多名使用者的 agent，可以讀到所有委託人可讀內容的總和，而且檢查時不知道這次是代表誰。若 KP 以 `subject=client` 去問這個 permission，就是擴權。

三種寫法：

1. **兩段檢查（現行 G9，建議沿用）：** `check(resource#read@user)` 交給 GAM；`client` 是否為 delegate，由平台設定判斷。delegate 檢查與 Resource 無關，所以 `list_resources` 只多一次判斷，不是每個 Resource 各一次。GAM 只要能把 user 當 subject（G1、G2）。
2. **delegate 註冊放進 GAM：** 例如 `definition platform { relation delegate: client }`，以第二次 check 判斷。好處是撤銷集中在 GAM，也可以用 SpiceDB 的 relationship expiration 做到期；代價是要依賴 GAM 的寫入稽核（G6）。
3. **使用者層級同意（對應 `may_act`）：** `definition user { relation delegate: client }`，表示「Alice 允許 agent X 代理她」，同樣是第二次 check。只有在需要「使用者自行授權特定 agent」時才需要。

若日後要讓某個 agent 只能代理部分 Resource，應另設關係（例如 `delegate_scope: client`），以 `check(user) ∧ check(client, delegate_read)` 判定，不要重用 client 的 `reader`，以維持 E1「自身 grant 與委派分開」的語意。單次 check 的原生寫法要建立「user–agent 組合」物件並逐對寫入 tuple。這是推論，未實測，也要 GAM 支援自訂 schema，目前不值得。

## D. KP 的模式選項

| 模式 | 判定 | 需要 tSSO 提供 | 需要 K8s／Agent Platform 提供 | 需要 GAM 提供 | 解決 | 仍未解決 |
|---|---|---|---|---|---|---|
| **P0 只認使用者**（v1） | `check(user)`；actor 是自報的，只記錄 | 可驗的 token（JWKS、`iss`、`exp`；`aud` 待確認） | 無 | G1、G2 | 未登入讀取；使用者權限上限 | 無法歸屬到 agent；無法停用單一 agent；持有 token 者就等於使用者；E1 的 delegate 檢查形同虛設 |
| **P1 使用者 ∧ 已驗證的 agent**（E1） | P0 ＋ 驗證 agent workload token，並對應到已註冊的 `client:<id>` | 同 P0 | 每個 agent 一個 ServiceAccount（不共用）；projected token 的 `aud`＝KP、短效；KP 能呼叫 TokenReview 或取得 issuer JWKS | 同 P0（或第 C 節寫法 2） | 歸屬（user＋agent）；未註冊 agent 一律拒絕；可依 (user, client) 設配額；只偷到使用者 token 的人無法冒充 agent | 使用者 token 仍在多個服務間流動，可被重放；「token 屬於哪個 agent」沒有密碼學綁定，已註冊的 agent 之間可以互相拿 token 用 |
| **P2 換發的委派 token** | 只接受 `aud`＝KP、`sub`＝user、`act.sub`＝agent 的短效 token（RFC 8693；信任域內可用 Txn-Token） | Token exchange endpoint；以 `actor_token` 驗證 agent；`may_act` 或等效政策 | Agent 或 gateway 在呼叫前換 token | 同 P1 | Passthrough 與跨服務重放；user–agent 綁定；IdP 集中控管「誰可代理誰」；符合 MCP 規範 | 換到的 token 在 TTL 內仍可被重放，可再加 DPoP／mTLS；大量抽取仍需配額 |
| **P3 agent 自身身分**（背景工作） | `check(client)`，只看 client 自己的 `reader` | 不需要 | 與 P1 相同的 workload 身分 | 能把 client 當 subject（G2） | 背景工作不必借用使用者 token | 內容被展示給無權的人（Rovo、Glean 的教訓），要靠契約約束；需要明確的 grant 審核 |

**風險對照**（✓ 解決／◐ 部分／✗ 未解決）：

| 風險 | P0 | P1 | P2 | P3 |
|---|---|---|---|---|
| 權限擴大 | ✓ 以使用者為上限 | ✓ | ✓ | ◐ 依 grant；展示給他人則 ✗ |
| Confused deputy（agent 拿別人的 token 或越權 token 呼叫 KP） | ✗ | ◐ | ✓ 有 `aud` 與 `act` | ◐ |
| 使用者 token 被轉送後重放 | ✗ | ◐ 還需要 agent 憑證 | ✓ 短效＋限定 `aud`（加 DPoP 更完整） | 不適用 |
| 歸屬（人或 agent） | ✗ | ✓ | ✓ | ✓（只有 agent） |
| 大量抽取 | ◐ 只能依使用者設配額 | ✓ 可依 (user, client) | ✓ | ✓ 可依 client |
| 撤銷 | 使用者 token 到期才失效 | ＋可即時取消 agent 註冊（每次請求都檢查）；TokenReview 在 Pod 刪除後立即失效 | ＋IdP 可停止換發；短 TTL | 撤銷 grant 後，下一次判定即生效 |

## E. 建議的收斂路徑

**v1（pilot）：P0**

- KP 負責：驗證 tSSO（簽章、`iss`、`exp`；tSSO 若有設 `aud` 就驗）；`subject=user`。Request 中的 client id 只記錄並標為 `actor_verified=false`，**不**用來放寬任何判定。KP 對內的呼叫（PEP → authz API）用 KP 自己的服務身分，使用者只以資料欄位帶過去（Q12 已是如此）。KP **不**把收到的使用者 token 轉送給任何下游。
- 紀錄欄位：`subject`、`actor`（自報值）、`actor_verified`、驗證方式、token 的 `jti` 或雜湊、`trace_id`、`decision_id`。
- P3 在 v1 不開放：沒有經過驗證的 agent 身分，`client` 的 `reader` 無法安全地使用。

**目標第一階段：P1**

- Agent Platform 提供：每個 agent 一個專屬 ServiceAccount；projected token 的 `audience` 設為 KP、短效；agent 與 Agent Owner 的對應關係。
- KP 負責：以 TokenReview（同叢集時優先）或 OIDC discovery 驗證 workload token，並驗 `aud`；把 ServiceAccount 對應到 `client:<id>` 與 delegate flag；套用 E1；依 (user, client) 設讀取配額（處理 #87 面向 15）。
- 這時才開放 P3，條件是 `client` 有明確的 `reader` grant，而且契約寫明：以 agent 身分讀到的內容，不得展示給沒有該 Resource 讀取權的人。

**目標狀態：P2**

- tSSO（身分提供者）提供：RFC 8693 token exchange，以 agent 的 workload token 作為 `actor_token`，發出 `aud`＝KP、帶 `act` 的短效 token；集中控管哪個 agent 可代理（`may_act` 或等效政策）。同一信任域的多跳呼叫，可評估 Transaction Tokens。
- KP 負責：只接受 `aud`＝KP 的 token；以 `sub` 作為 subject、`act.sub` 作為 actor；巢狀 `act` 只記錄、不參與判定（RFC 8693）。
- 平台安全基線可以把「token 要限定 audience；跨服務必須換發、不得轉送」列為原則，KP 是第一個套用的服務。

**轉送使用者 token 的風險（不誇大）：** 「agent 代表人行事」本身與標準一致；風險在機制。若把同一個 bearer token 轉送到每個 tool、A2A、MCP server：

- 若 tSSO token 的 `aud` 不是 KP，KP 若以 MCP server 身分接受它，就不符合 MCP 規範；
- 任何經手 token 的 agent 或 tool 一旦被攻破，就能拿它存取所有接受 tSSO 的服務（MCP 列出的 trust boundary 風險）；
- KP 無法從 token 判斷是哪個 agent 送來的。

若 tSSO 對每個服務發出限定 `aud` 的 token，衝突就小很多；實際設定待向身分團隊確認。較安全的替代是 P2；在 P2 就緒之前，P1 可以補上歸屬與停用單一 agent 的能力。

## 待確認

- [ ] tSSO token 有沒有 `aud`？是否每個服務一個 audience？TTL 多長？有沒有 token exchange 或 introspection endpoint？
- [ ] Agent 與 KP 在不在同一個叢集（TokenReview 還是 OIDC discovery）？每個 agent 是否有獨立的 ServiceAccount？
- [ ] Agent Platform 是否已計畫 gateway 或 sidecar 來換 token（類似 Entra 的 SDK sidecar、Google 的 Agent Gateway）？

## 來源

所有來源於 2026-10-26 查閱。

**產品**

- Microsoft：[Agent OBO flow](https://learn.microsoft.com/en-us/entra/agent-id/agent-on-behalf-of-oauth-flow)、[Permissions and consent](https://learn.microsoft.com/en-us/entra/identity-platform/permissions-consent-overview)、[OBO flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)、[Agent ID logs](https://learn.microsoft.com/en-us/entra/agent-id/sign-in-audit-logs-agents)、[Copilot privacy](https://learn.microsoft.com/en-us/copilot/microsoft-365/microsoft-365-copilot-privacy)
- Google：[Agent Identity overview](https://docs.cloud.google.com/iam/docs/agent-identity-overview)
- AWS：[Q Business data accessor](https://docs.aws.amazon.com/amazonq/latest/qbusiness-ug/data-accessors-granting-permissions.html)、[TTI blog](https://aws.amazon.com/blogs/machine-learning/authenticate-amazon-q-business-data-accessors-using-a-trusted-token-issuer)、[AgentCore workload access token](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/get-workload-access-token.html)
- Glean：[Agent identity](https://docs.glean.com/administration/agent-identity/overview)
- Salesforce（**UNVERIFIED**，只看到搜尋摘要）：[Agent Execution Context and Data Access by Type](https://help.salesforce.com/s/articleView?language=en_US&id=ai.agent_execution_data.htm&type=5)、[Configure Service Agent Access](https://help.salesforce.com/s/articleView?language=en_US&id=ai.agent_user.htm&type=5)
- Atlassian：[Rovo agent accounts](https://support.atlassian.com/studio/docs/understand-rovo-agent-accounts/)、[AUTO-2337](https://jira.atlassian.com/browse/AUTO-2337)、[ROVO-837](https://jira.atlassian.com/browse/ROVO-837)
- Okta：[Cross App Access for AI agents](https://support.okta.com/help/s/article/understanding-cross-app-access-with-okta-for-ai-agents)
- Auth0：[Authorization for RAG](https://auth0.com/ai/docs/intro/authorization-for-rag)

**MCP 與 A2A**

- MCP：[Authorization 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)、[Security considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations)、[Security best practices（2025-11-25，含 token passthrough）](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)、[Versioning](https://modelcontextprotocol.io/specification/versioning)、[ext-auth](https://github.com/modelcontextprotocol/ext-auth)、[Enterprise-Managed Authorization](https://github.com/modelcontextprotocol/ext-auth/blob/main/specification/stable/enterprise-managed-authorization/2026-07-28/enterprise-managed-authorization.mdx)
- [A2A specification 1.0](https://a2a-protocol.org/latest/specification/)

**RFC 與 IETF 草案**

- [RFC 8693](https://www.rfc-editor.org/rfc/rfc8693.html)、[RFC 8707](https://www.rfc-editor.org/rfc/rfc8707.html)、[RFC 9700](https://www.rfc-editor.org/rfc/rfc9700.html)、[RFC 8705](https://www.rfc-editor.org/rfc/rfc8705.html)、[RFC 9449](https://www.rfc-editor.org/rfc/rfc9449.html)
- [Transaction Tokens](https://datatracker.ietf.org/doc/draft-ietf-oauth-transaction-tokens/)、[ID-JAG](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-assertion-authz-grant/)、[Identity chaining](https://datatracker.ietf.org/doc/draft-ietf-oauth-identity-chaining/)、[On-behalf-of user for AI agents（已過期）](https://datatracker.ietf.org/doc/draft-oauth-ai-agents-on-behalf-of-user/)、[WIMSE WG 文件](https://datatracker.ietf.org/wg/wimse/documents/)、[WIMSE AIMS](https://datatracker.ietf.org/doc/draft-ietf-wimse-aims/)、[actor profile](https://datatracker.ietf.org/doc/draft-mcguinness-oauth-actor-profile/)、[actor chain](https://datatracker.ietf.org/doc/draft-mw-oauth-actor-chain/)

**Workload identity**

- Kubernetes：[Configure service accounts](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)、[Service accounts（TokenReview 建議）](https://kubernetes.io/docs/concepts/security/service-accounts/)、[Managing service accounts](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/)
- [SPIFFE JWT-SVID](https://github.com/spiffe/spiffe/blob/main/standards/JWT-SVID.md)

**SpiceDB／AuthZed**

- [Schema（`&`、caveats）](https://authzed.com/docs/spicedb/concepts/schema)、[AI agents schema example](https://authzed.com/learn/spicedb-schema-examples/ai-agents)、[How SpiceDB Secures Authorization for AI](https://authzed.com/blog/spicedb-secures-authorization-for-ai)

**Repo 內**

- [#85 授權設計](../design/knowledge-platform-authorization.md)、[ADR-0008](../adr/0008-resource-level-authorization-relations.md)
