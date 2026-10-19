# Source system 呼叫 Knowledge Platform API 的身分驗證研究

**研究日期：2026-10-18（Asia/Taipei）。狀態：保留的官方文件調查與操作成本分析；pilot 已選平台核發 service-account token，尚未選定公司 PAT／CSP 整合。**

問題來自 [Admission #31](https://github.com/davidlinnnn/data-ingestion/issues/31)：主要提交者是 Data Owner 的系統，是否為每個來源系統發一組固定 token，或使用更容易長期操作的替代方案？本筆記比較 system-to-system authentication，不替代文件讀取的 GAM／GAM-compatible authorization。

**環境資訊：**使用者確認公司有稱為 PAT 的系統身分機制，與人的 tSSO 身分區分；詳細能力尚不確定。此處不推定 PAT 的全名、token 格式或是否採 OAuth。若其生命週期已由公司管理，即使使用長效 token，也可能比平台另發一套 key 更省維運；這仍是未驗證的後續整合選項。

**後續 pilot 決議：**使用者選擇先由 Knowledge Platform config 管理並核發各 client 的 service-account token，延後公司 PAT 整合；data access control 保持第一優先，由既有治理 ticket 負責。確切決議與保留邊界見 [admission 設計筆記](../design/knowledge-platform-admission.md#confirmed-pilot-service-account-authentication-on-2026-10-18)。以下比較保留作為後續參考，不再把 PAT 調查當成 pilot 前置條件。

## 結論與適用條件

以下是研究階段的**條件式設計判斷**；pilot 採用上方連結的後續決議，正式整合選型仍待回訪：

- 保留每個來源系統與環境的穩定 client identity；credential 可以輪替，不必讓身分隨 token 改變。不要把同一組 production credential 共用到 development。
- **已有公司 machine-to-machine 身分服務：**先比較重用其既有應用身分能力；若支援 `client_credentials` 亦可評估，通常比平台另管一套發證與驗證流程划算。使用者已指出 PAT，具體協定與操作能力仍待確認。
- **已具備相容的 managed identity／federation：**通常可減少日常 secret 配送與輪替；前提是部署環境、trust 設定與本 API 的驗證都已支援。
- **沒有既有 M2M 能力、系統數量少：**平台管理的 opaque API key 可以是第一個整合候選；仍需 owner、限制範圍、安全交付、輪替與停用。不為一個上傳入口新建 OAuth server 或跨雲 federation。

這是依既有能力與操作負擔作的條件式比較；不是「CSP 都禁止 key」，也不是「固定 key 永久免維護」。平台目前選擇先簡化 pilot 接入；下列官方事實不替正式整合選型。

## CSP 官方實務及其界線

| Provider | 官方建議／能力 | 不應外推的結論 |
|---|---|---|
| AWS | 存取 AWS 的 workloads 優先使用 IAM roles 與 temporary credentials；外部工作負載可用 Roles Anywhere，以 X.509 憑證取得暫時 AWS credentials。[IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)、[Roles Anywhere setup](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/getting-started.html) | Roles Anywhere 仍要設定 CA／trust anchor、role／profile、憑證與 private key；credential helper 更新 session 不等於替你更新底層憑證。[Credential helper](https://docs.aws.amazon.com/rolesanywhere/latest/userguide/credential-helper.html) |
| Azure | 應用 credential 優先 managed identity；可用可信外部 identity federation 時再評估；否則建議 certificate 優於 client secret。`client_credentials` 支援 secret、certificate、federated assertion。[App credential guidance](https://learn.microsoft.com/en-us/entra/identity-platform/security-best-practices-for-app-registration)、[Client credentials flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow) | Managed identity 適用於支援相應信任與 Entra authentication 的目標；custom API 仍要驗證與授權 caller。Secret-backed OAuth 仍需保管與輪替 bootstrap secret；certificate 仍有 private-key／renewal 工作。[Workload authorization](https://learn.microsoft.com/en-us/entra/architecture/authorize-applications-resources-workloads) |
| GCP | 在 Google Cloud 上使用 attached user-managed service account；外部 workload 優先評估 Workload Identity Federation，避免長期 service-account key。[Attached identity](https://docs.cloud.google.com/docs/authentication/set-up-adc-attached-service-account)、[WIF](https://docs.cloud.google.com/iam/docs/workload-identity-federation) | WIF 依賴既有外部身分、issuer／subject trust 與權限設定；原有 IdP secret／certificate 仍可能存在，只是不用再加入一把 Google service-account key。[WIF credential practices](https://docs.cloud.google.com/iam/docs/best-practices-for-using-workload-identity-federation#use_workload_identity_federation_to_reduce_the_number_of_credentials_that_require_rotation) |

### 「支援 key」與「推薦預設」分開

- Azure AI Search 實際支援 key authentication，且預設啟用；兩組 admin keys 可交替使用完成輪替。但其 production best practice 建議改用 Entra RBAC，對繼續使用 key 有明確風險與環境限制。[Azure AI Search API keys](https://learn.microsoft.com/en-us/azure/search/search-security-api-keys)
- AWS API Gateway **usage-plan API keys 不應用作 authentication／authorization**；官方指向 IAM、Lambda authorizer 或 Cognito 等機制。AWS access key 用於簽署 AWS requests，也不能直接等同本平台自訂的 opaque bearer key。[Usage-plan guidance](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-api-usage-plans.html)、[IAM authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- GCP 現行文件區分 standard API key（不驗 principal）與 service-account-bound authorization key（類似長期 access token）；後者對建立／管理 Google Cloud resources 的 APIs 不建議用於 production。不能概括成所有 GCP API keys 都不帶身分。[GCP API key types](https://docs.cloud.google.com/docs/authentication/api-keys)

上述是各服務自己的安全契約，不能拿某一產品的 key 功能，直接證明本平台任意 token 設計已合格。

## Native CSP resource access 不等於本平台 HTTP API authentication

本平台必須明確選擇接受的 issuer／credential、caller identity 與權限映射；這是由下列整合前提得出的**設計推論**：

- AWS API Gateway 要啟用 `AWS_IAM`、驗 SigV4，且 caller 要有相應 `execute-api` permission，才形成 IAM 保護的 custom route；一般 HTTP server 不會因 caller 擁有 AWS credentials 就自動驗證它。[HTTP API IAM integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)
- Entra 保護自有 API 要設定自己的 application permissions／app roles，由 API 驗證適用 token 並授權；不是拿一個給 Microsoft Graph 的 token 呼叫任何 API。[Custom API application permissions](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-client-creds-grant-flow#application-permissions)
- Google 的 access token 主要供 Google APIs；custom service 可明確採 Google-signed ID token，設定並驗證正確 audience、簽章、issuer、期限，再將 principal 對應自己的權限。[Token types](https://docs.cloud.google.com/docs/authentication/token-types)、[Custom API validation](https://docs.cloud.google.com/endpoints/docs/openapi/service-account-authentication#configuring_your_api_to_support_authentication)

因此未來回訪整合時，優先查驗已有哪個可重用的 company workload identity／gateway，不為採 CSP 名詞而搬動本平台或建立新 IdP。

## 操作成本比較

以下整表是**工程判斷**，不是 CSP 的成本承諾。比較假設同樣保留每個系統／環境的身分、最小權限與稽核；client credential 不共用成所有來源的一把 master key。

| 候選 | 初次 onboarding | 日常輪替／停用 | 依賴與操作負擔 |
|---|---|---|---|
| 平台發 opaque API key | 註冊 client、核准 Source／operation scope、安全交付 key；server 管理 verifier／停用狀態 | 由平台和 client owner 配送新 key、驗證切換、撤舊 key；可設短暫雙 key overlap。停用生效需計入 API instances／cache | 無額外 token endpoint；平台自己負責 credential lifecycle、保護與事故處理。少量 client 初期最直接，數量增加後配送工作累積 |
| 既有 IdP `client_credentials`＋secret | 註冊 client 與本 API audience／permissions，配送 secret；client 接 SDK／token cache | 仍要換 secret；停用 minting credential 不應被當作已收回全部 issued tokens | 多 token issuer／discovery／signing-key 依賴，但若公司已有整套流程，增量工作可小；若要新建 IdP，優勢未必成立 |
| 既有 IdP `client_credentials`＋certificate | 類似上列，另配置 certificate／private-key custody | Certificate renewal、private-key protection、雙 credential 過渡與撤銷；不需要把 private key 當 shared password 傳到 token endpoint | 可利用既有 PKI／vault 自動化；沒有既有能力時，比一個 secret 更重。不是「沒有 credential lifecycle」 |
| 已支援的 managed identity／federation | 配置 workload identity、trust／subject／audience、permissions 與 API 驗證 | 平台可自動管理部分 credentials；仍要維護 trust、issuer、grant、底層 workload／IdP 或 cert 的生命週期 | 已有相容 runtime 時日常負擔低；跨平台 federation 初期整合與除錯成本較高，refresh 仍依賴相關 identity services |

API key 的 verifier、hashing、雙 key overlap 或停用 cache 是本平台可能的實作建議，不是 AWS／Azure／GCP 對本平台規定的 schema；pilot 決議選定平台核發方式，未選定這些實作細節。

### Rotation、revocation 與 outage 不可混同

- Entra 文件明示停用 application 會阻止新 token，但既有 access tokens 仍可到期前有效；OAuth secret 改成可輪替，不能推導所有已發 token 同時作廢。[Application deactivation](https://learn.microsoft.com/en-us/entra/identity/enterprise-apps/deactivate-app-registration)
- Google ID token 有自己的期限且不能撤銷；若採此路徑，要另定本 API 的 client 停用／權限生效邊界，不能只依賴撤掉發證憑據。[Token types](https://docs.cloud.google.com/docs/authentication/token-types)
- AWS 也區分發證與已發 role sessions；可透過 session permissions／revoke-sessions 處理，且需考慮政策傳播。Roles Anywhere 的憑證撤銷不是所有已發 session 的瞬時清除。[Temporary-session access](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_control-access_disable-perms.html)、[Revoke role sessions](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_revoke-sessions.html)

**本平台的操作判斷：**IdP／STS 中斷時，已取得且仍可驗證、適用的 token 可能提供剩餘有效期間；取得新 token／key 更新仍可能失敗。離線 JWT 驗證也有 signing-key refresh 與本地權限狀態的依賴，不能保證無限離線。Secret／certificate／signing-key 輪替應有 overlap、到期告警與停用演練，重用公司現有工具，不先造新控制面。

短期 token 本身也不保證立即終止已接受的長 HTTP upload、已發出的 storage grant 或已受理 workflow。須另外定義並驗證各邊界的 check 時機、有效期與停止／續跑行為；本次不選 instant revocation 或每個 chunk 都查 GAM。

## 保留的 Source／Resource 權責

- #53 已確認 Source 註冊與明確 submission delegation，可委派給 authorized program。驗 caller 的 Source-scoped submit authority，與未來文件讀者 audience 分開；身分驗證成功不等於有所有 Source 的寫入權。[Source Q1／Q5／Q7](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L26)
- Resource 可隨提交引用，但 document→Resource binding 要由有權責 actor 建立、可歸責，不能由任意參數擴權；Source Authorization Ceiling 持續適用。[Source Q12](https://github.com/davidlinnnn/data-ingestion/blob/9be8021a25a39545c28af8f420c3750a7ce21859/docs/design/knowledge-platform-source-handoff.md#L272)
- tSSO user authentication 與 GAM／compatible reader access 是已確認公司要求；pilot workload credential 由平台核發，正式公司 PAT 整合仍待回訪。Data Owner 管理其有權責範圍內的 document→Resource／user→Resource，並非取得所有來源政策權威。[#56 confirmed requirements](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6230755901)

## 未來回訪公司 PAT 整合時的查驗事項

這些是後續研究清單，不阻擋本次 pilot 決議；pilot 自身的停用與授權邊界仍需在 admission 設計中定義。

1. 既有 PAT 是直接供 API 驗證的 token，還是取得另一個 access token 的 credential？由哪個既有 gateway／SDK／服務驗證，是否支援本平台用途、系統識別、期限、輪替與停用？tSSO 的 user-login 能力不自動回答這題。
2. 第一個 source system 在哪裡執行，已有什麼 managed／federated identity 或 secret／certificate 管理？先驗現成能力，不要求全部 client 使用三家 CSP。
3. 系統數量、credential owner 與輪替頻率；停用新 API requests、upload grants 與既有已受理工作各需要何種生效邊界？沿用 #31／#56 決策，不靠 token 名稱推定。

**限制：**查閱當日官方文件與既有確認契約；未接公司 tSSO／GAM／PAT、未取得 client 環境資料，未做 IAM／IdP outage、credential rotation 或端到端撤權實測。以上能力與成本比較不是 production qualification 或新增 MVP gate；pilot 選型另記於 admission 設計筆記，沒有修改 GitHub 決策。
