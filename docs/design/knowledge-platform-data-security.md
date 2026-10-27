# Knowledge Platform 資料安全治理原則與 Agent Platform 邊界

[Define Knowledge Platform data-security governance principles and the Agent Platform boundary](https://github.com/davidlinnnn/data-ingestion/issues/87) 的設計結果。2026-10-26 至 10-27 與使用者以 grilling 第 A–G 組確認。

本文的依據如下：

- [資料安全面向 framework](../research/knowledge-platform-data-security-aspects-2026-10-20.md)；
- [治理研究](../research/knowledge-governance-context-layer-2026-10-17.md)及其 [retro](../research/knowledge-governance-retro-spike-2026-10-17.md)；
- [授權設計](knowledge-platform-authorization.md)（#85）；
- ADR-0007 與 ADR-0008。

身分機制另有一份研究：[agent 身分與使用者身分](../research/knowledge-platform-agent-user-identity-2026-10-26.md)。用語依 `CONTEXT.md`。

本文只定原則並指定負責的票，不選產品，也不實作控制。各控制由第 10 節列出的票實作。沿用 retro 的規則：原則依正式環境預期收到的資料來寫，MVP gate 只設在 pilot 實際會經過的資料流（A5）。公司事實還不知道的項目，照 #93 和 #85 的做法參數化，每一項都有負責人，帶回後代入（A4，第 9 節）。

## 1. 範圍與負責人

| 主題 | 負責 |
|---|---|
| 資料安全原則、16 面向處置、處理出口準則、Platform Security Baseline、Agent Platform 邊界契約 | 本文 |
| 授權介面、模型、引擎 | #85（已結案）、[授權設計](knowledge-platform-authorization.md) |
| enforcement：撤權、揭露、稽核紀錄的保留與揭露、委派證明 | #56 |
| 儲存、加密、備份、custody | #57 |
| 部署、權限、網路、維運流程 | #78 |
| serving 契約、consumer 與 agent 存取 | #76 |
| projection 的查詢與 materialization | #55 |
| 文件內容篩檢（惡意 payload、有害內容、敏感資料） | #107 政策、#105 與 #121 方法、#106 量測、#108 workflow 位置 |
| GAM 驗證 | #86（map 外） |
| agent 執行時的行為（prompt injection 防禦、工具控制、memory、模型選擇） | Agent Platform，不在本文範圍 |

## 2. 公司事實

以下由使用者在 2026-10-26 提供：

- **資料分級**（A1）：公司分 property、security C、security B、security A 四級。property 最寬鬆。員工日常工作文件預設是 C；B 以上和重大決策、製程機密有關。**C 以上只能送 on-prem API。**
- **平台會收的資料**（A2、D4）：PROD 收 C、B 和 A。B 是 R&D 文件；pilot 論文是 C。A 級要等主管核准 Platform Security Baseline 之後才收（第 8 節）。
- **網路**（B3）：公司網路沒有開放任何外部雲端 LLM API。公司內所有模型服務都是 on-prem，包括 K8s 上的 vLLM 和以 Docling 為基礎的小型 OCR 模型。開發先在公司網路外進行，GAM、公司 VLM、摘要 API 的串接進公司後再補。
- **推論服務**（B4）：別的 team 的摘要 API 和公司 VLM 都已確認四個條件：on-prem；不留存內容，或留存符合公司規定；不用於訓練；log 不含正文，或 log 存取受控。
- **特權存取**（D1）：公司有跳板機。從跳板機連 PROD DB 會留下 tSSO 登入紀錄。
- **agent 身分**（A3、F1）：公司原則是「agent 代表人做事」，A2A 和 MCP 呼叫會帶身分。規劃中，agent 身分用 K8s app 的 ServiceAccount token，使用者身分用 tSSO。驗證細節要進公司後才能確認。Agent Platform 對資料面還沒有定義，由本文提出準則（F3、F5）。

## 3. 決策

| # | 決策 |
|---|---|
| A4 | 公司事實未知時參數化，記下負責人和代入位置，不擋本票。 |
| A5 | 原則依 PROD 預期的資料來寫；MVP gate 只設在 pilot 實際經過的資料流。 |
| A6 | 產出是本文和 16 面向處置表；需要獨立 session 才能解的面向開新票。 |
| B1 | property 比 C 寬鬆。平台的 PROD 不收 property 級資料，不為它另訂規則；公開的 arXiv 語料屬於這一級。 |
| B2 | **v1 不設等級屬性。** 平台的底線是「所有內容一律視為 C 以上」。目前沒有任何處理規則會因 C、B 而不同：出口一律 on-prem，誰能讀由 Resource readers 決定。觸發條件有兩個：一是出現第一條依等級而異的處理規則；二是 A 級的公司規定和 C、B 不同（D4）。觸發時在 Resource 上加等級屬性，這是新增欄位，不破壞既有介面。 |
| B3 | 公司網路內的所有環境（DEV、pilot、STAGING、PROD）只送 on-prem 服務。外部雲端服務只能在公司網路外、以 property 級的公開資料做研究對照。 |
| B4 | 處理出口要登錄在第 5 節的出口表，符合四個條件才能接進 PROD。摘要 API 和公司 VLM 已確認，#91 Q30 的「DEV 只能送公開 arXiv」限制解除。 |
| B5 | 文件內夾帶的 secret 或 PII：平台不遮蔽，因為遮蔽會改寫原始證據。偵測列為 #107 的第 5 類「敏感資料」，方法由 #121 調查。初始模式是「記錄＋警示」。人事、客戶資料不在範圍內，PII 不另做處理。 |
| B6 | **偵測類控制分三種模式：記錄、警示、gate。** 偵測訊號從第一天就寫進 Processing Result 和稽核紀錄。模式是設定值，依「類別 × 環境」各自設定，每次變更都留下歷史。收緊時只要用已存的訊號重新判斷既有文件，不必重新處理。適用於 #107 的五個類別和面向 15 的大量讀取偵測。 |
| B7 | 第 8 節是給主管看的 Platform Security Baseline。它就是平台安全的驗收標準，之後逐版收緊。 |
| C1 | 所有衍生資料的敏感度和讀者都等同它的輸入（ADR-0007）。衍生資料包括摘要、Wiki、KG、chunk、embedding、索引項目、搜尋片段和引用。[Vec2Text](https://arxiv.org/abs/2310.06816) 從 embedding 精確還原了 92% 的 32-token 輸入，[OWASP LLM09:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM09_VectorAndEmbeddingWeaknesses.md) 也要求向量庫和備份比照原文保護。後果有三：向量庫和索引的保管比照原文（#57）；撤回和刪除走既有路徑（#55、#56）；v1 的 serving 不把原始向量交給 consumer。 |
| C2 | 計數、排名、facet、top-k、相關文件、自動完成、反向連結，都只在使用者可讀的範圍內計算。授權過濾放在查詢裡面（pre-filter），不先查後刪（post-filter）。 |
| C3 | serving 和 retrieval 結果的快取不跨使用者共用，除非快取 key 已含請求者可讀的 Resource 集合。撤權後的失效走 #56 的路徑。 |
| C4 | ADR-0007 中「逐文件讀者例外仍在 #56 討論」一句，同步為 ADR-0008 的結論：v1 不支援。 |
| D1 | 維運角色不隱含讀取權。維運人員讀內容要用自己的 tSSO 身分透過平台 API，走正常授權。直接連 DB 或 object store 只能走 break-glass：經跳板機（留 tSSO 紀錄）、限時、需核准、每次使用都稽核、事後複查。pilot 只要有 runbook。 |
| D2 | 平台內部 workload 依元件使用最小權限憑證：processing、projection、serving 各有自己的 K8s ServiceAccount、DB role 和 bucket 範圍，不共用超級帳號。這補上授權設計 Q3 的缺口：內部 workload 依部署設定授權，但不能拿到全部內容。 |
| D3 | 所有儲存都用儲存層加密，包括 Canonical、BM25 索引、向量庫和備份，照公司標準。這是磁碟層的設定，搜尋不受影響。不做應用層或欄位加密，因為它會讓搜尋失效。內容跨主機傳輸時走 TLS，包括送往 on-prem 推論服務的流量。v1 不做 per-tenant 金鑰。presigned URL 和憑證當 secret 處理，不寫進 log。 |
| D4 | 非 PROD 環境的資料：個人筆電、公司網路外和 public repo 只能用 property 級資料；公司內的 DEV 可用 property、C，以及少量取得測試特權的 B；STAGING 和 PROD 可用真實的 C、B、A 資料，A 級的前提見 B2 和第 8 節。 |
| D5 | 解析不可信檔案：v1 只做 D2 的最小權限、保留現有的 worker 資源上限（每個 worker 一個 parser、4 GiB），並遵守公司 K8s 的預設安全基準，不加 parser 專用的強化，也不上 gVisor 或 VM sandbox。觸發重新評估的條件有兩個：接入公司外部或未受信任提交者的來源；#107 第 1 類的偵測紀錄顯示出現了真實的攻擊檔。 |
| E1 | 平台不是 system of record。legal hold 和公司的文件保存義務由 Source 系統負責；平台跟隨 Source Deletion，也不得當作存檔系統使用。v1 不做 legal hold 機制。 |
| E2 | 稽核紀錄只記參照：ID、版本、`decision_id`、`trace_id`。不記 chunk 正文，預設也不記查詢文字。要記的事件有：釋出和拒絕、`relation_change`、break-glass 使用、篩檢命中與模式變更、出口表變更。保留期限照公司 log 標準。只有資安和 operator 角色能讀。 |
| E3 | serving 的讀取依 user 限速，等 P1 有了已驗證的 agent 身分後，再加上依 client 限速；超過就回 `429`。依 subject 記錄每天被釋出的文件數。大量抽取規則從「記錄」模式開始（B6），v1 不做 ML 異常偵測。限速的數值等 #88 的 PROD 讀取量出來再定。 |
| F1 | 身分機制分三階段（第 7.1 節）。v1 只認使用者（P0）；目標第一階段是使用者 ∧ 已驗證的 agent（P1）；目標狀態是換發的委派 token（P2）。 |
| F2 | agent 以自己的身分讀取（P3）要等 P1 到位才開放，而且只認 maintainer 明確授予的 client `reader` 關係。 |
| F3 | 釋出後的資料義務，見第 7.2 節。 |
| F4 | correlation 用 W3C Trace Context 的 `traceparent`（第 7.3 節）。 |
| F5 | 邊界契約寫進第 8 節，由使用者帶去和主管、Agent Platform infra team 談，不另開票。平台這一側的義務由 #76 照做，不必等契約談定。 |
| F6 | token 要限定 audience；跨服務呼叫要換 token，不得轉送。平台是第一個做到的服務（第 7.1 節）。 |

## 4. 16 個資料安全面向的處置

| # | 面向 | 處置 | 負責 |
|---|---|---|---|
| 1 | 身分與委派 | 已有負責票。#85 定了 E1；本文 F1 定三階段身分機制 | #85、#56、#76 |
| 2 | 存取控制與職責分離 | 已有負責票。read、place、manage 三種權限分開；`unavailable` 一律 fail-closed | #85、#56、#31 |
| 3 | 衍生資料洩漏 | 原則 C1–C3 | #55、#76、#56、#57 |
| 4 | 特權存取 | 原則 D1、D2 | #78、#56 |
| 5 | 撤權、撤回、刪除的傳播 | 已有負責票。F3 第 1 條讓撤權在 agent 端也能生效 | #56、#57、#32 |
| 6 | 保留、合法刪除、legal hold | 原則 E1。pilot 的期限見 [first-adoption](knowledge-platform-first-adoption.md)；PROD 的期限由 #57 和 data owner 訂定 | #57 |
| 7 | 資料分級與處理規則 | 對應公司分級（第 2 節）；原則 B2，含觸發條件 | 本文 |
| 8 | 處理過程的資料流出 | 原則 B3、B4，第 5 節出口表 | 本文；各出口由使用該出口的票登錄 |
| 9 | 文件內夾帶的敏感資訊 | 原則 B5、B6 | #107、#121、#106、#108 |
| 10 | 來源完整性與 provenance | 已有負責票 | #31、#76、#32 |
| 11 | 知識投毒 | 已有負責票（#85 已從這個角度審視） | #85 |
| 12 | 加密、金鑰、secret | 原則 D3 | #57、#78 |
| 13 | 隔離 | tenant 由 #56 負責；非 PROD 資料見 D4；parser 隔離見 D5 | #56、#78 |
| 14 | 稽核紀錄 | 原則 E2；新增 `actor_verified` 欄位（第 7.1 節） | #56、#113 |
| 15 | 濫用與大量抽取 | 原則 E3、B6 | #76、#56、#78 |
| 16 | 文件夾帶的惡意 payload 與有害內容 | 已有負責票；第 5 類「敏感資料」為本票新增 | #107、#105、#106、#108 |

## 5. 處理出口登錄表

公司網路內只接受 on-prem 服務（B3）。登錄的四個條件是：on-prem；不留存內容，或留存符合公司規定；不用於訓練；log 不含正文，或 log 存取受控。新的出口要先登錄並符合條件，才能接進 PROD。

| 服務 | 營運方 | 送出的內容 | 狀態 |
|---|---|---|---|
| 公司 VLM（Qwen3.8-27B，K8s vLLM） | 公司 | Picture Interpretation 的圖片裁切和整頁影像、公式區塊、沒有文字層的程式碼；Document Category 可能送正文和標題（[workflow v2](knowledge-platform-processing-workflow-v2.md) §4） | 四個條件已確認（2026-10-26） |
| 摘要 API（Document Summary） | 別的 team | 原生正文和標題 | 四個條件已確認（2026-10-26） |
| 以 Docling 為基礎的 OCR 和解析 | 平台內 | 不送出平台 | 不適用 |
| embedding 服務 | 未選定 | chunk 文字 | 選定前要先登錄並符合條件；選型由 #55 負責 |
| 篩檢模型（#105 的候選，例如 Prompt Guard 2、d3-mini；#121 的候選） | 未選定 | 文字或影像 | 由 #108 採用時登錄 |
| 雲端服務（OpenAI、Azure Prompt Shields 等） | 外部 | 不得在公司任何環境使用 | 只能在公司網路外、以 property 級資料做研究對照（B3） |

## 6. 偵測控制的模式

依 B6，下表是 Platform Security Baseline v1 的起點。#107 定案後，由 #107 填入各類別的模式。

| 控制 | 模式 | 誰決定 |
|---|---|---|
| #107 第 1–4 類（主動內容、隱藏文字、惡意指令或程式碼、有害內容） | 待 #107 決定 | #107 |
| #107 第 5 類「敏感資料」（secret、PII） | 記錄＋警示 | 本文 B5；#107 可以收緊 |
| 大量讀取（面向 15） | 記錄 | 本文 E3 |

## 7. Agent Platform 邊界契約

### 7.1 身分

產品比較、標準原文和風險對照，見 [agent 身分研究](../research/knowledge-platform-agent-user-identity-2026-10-26.md)。業界的共同做法是：代表使用者讀取時以使用者權限為上限，agent 只多一道粗粒度的閘門。#85 的 E1 和這個做法一致。

| 階段 | 判定 | 平台負責 | 需要別人提供 |
|---|---|---|---|
| **v1：P0 只認使用者** | `check(user, action, resource)`，不帶 actor | 驗證 tSSO 的簽章、`iss`、`exp`；有 `aud` 就一併驗。agent 自報的 client ID 只記進稽核紀錄，標為 `actor_verified=false`，不用來放寬任何判定 | 無 |
| **目標第一階段：P1 使用者 ∧ 已驗證的 agent** | E1：`check(user)` 為 allow，**而且** actor 是已登錄的 delegate | 以 TokenReview（同一 cluster）或 issuer 的 OIDC discovery 驗證 agent 的 projected ServiceAccount token，並驗 `aud`＝KP；把 `namespace/ServiceAccount` 對應到授權設計 Q16 登錄的 `client:<id>`；依 (user, client) 限速 | 每個 agent 一個專屬 ServiceAccount；projected token 的 audience 設為 KP，而且短效 |
| **目標狀態：P2 換發的委派 token** | 只接受 `aud`＝KP、`sub`＝user、`act.sub`＝agent 的短效 token（[RFC 8693](https://www.rfc-editor.org/rfc/rfc8693)） | 以 `sub` 為 subject、`act.sub` 為 actor；巢狀的 `act` 只記錄 | tSSO 提供 token exchange |
| **P3 agent 用自己的身分讀取** | `check(client)`，只看 client 自己的 `reader` | P1 到位後才開放（F2） | 同 P1 |

GAM（SpiceDB）沿用授權設計 G9 的兩段檢查，不需要額外能力。AuthZed 官方 AI agent 範例的 `reader->delegates` 寫法會讓 agent 拿到所有委託人可讀內容的聯集，不要採用。

**token 原則（F6）**：平台呼叫自己的下游時（例如 authz API），用平台自己的服務身分，絕不轉送使用者的 token（授權設計 Q12 已經是這樣）。tSSO 支援 `aud` 之後，平台只接受發給自己的 token。依據是 [MCP 授權規範](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)（server 只接受發給自己的 token，也不得把收到的 token 往下轉送）、[RFC 9700](https://www.rfc-editor.org/rfc/rfc9700) §2.3（token 要限定 audience），以及 Entra OBO、Okta Cross App Access 等主要廠商的換發做法。

### 7.2 釋出後的資料義務（F3）

| 方 | 義務 |
|---|---|
| Agent Platform | 1. 釋出的內容只在請求它的那個任務或 session 裡使用；v1 不得存進長期 memory，也不做跨任務快取。需要時重新讀取，重新讀取會再驗一次權限。<br>2. 只呈現給它代表的那個人；用自己身分讀取時（P3），只呈現給該 Resource 的讀者。<br>3. 不得用於訓練或 fine-tune，除非 data owner 核准。<br>4. 只送 on-prem 模型（公司 C 以上的規則）。<br>5. 每次呼叫帶 correlation（7.3）。 |
| Knowledge Platform | 1. 每次請求都驗權，無法判定時不揭露。<br>2. 每筆結果標註版本，以及「原文」或「生成」（#76）。<br>3. 撤權、撤回、刪除之後不再釋出（初始目標：1 分鐘內停止釋出，10 分鐘內完成）。<br>4. 記錄每一次釋出（E2）。 |

日後 Agent Platform 如果需要跨任務保存，再談有效期（`valid_until`）和重新驗證的機制，v1 不做。平台不保證追回已經釋出的內容；撤權在 agent 端能不能生效，靠的是第 1 條義務。

### 7.3 correlation

agent 在每次呼叫時帶 [W3C Trace Context](https://www.w3.org/TR/trace-context/) 的 `traceparent`。平台把它和釋出事件一起記錄，並回傳自己的 `trace_id`。平台內部的關聯鏈沿用 #78 定的欄位：`request_id` → `asset_key`／`source_revision_id` → `canonical_revision_id` → 產品版本。

## 8. Platform Security Baseline v1（提案，待主管核准）

這一節是寫給主管的。它列出平台目前保證什麼、還在收斂什麼，作為平台安全的驗收標準。之後每次收斂就改這一節並升版。A 級資料要等這一版獲得核准才收（D4）。核准時如果公司對 A 級另有規定，就觸發 B2，加上等級屬性。

**版本**：v1，2026-10-27。**狀態**：提案。

**平台保證**

1. **存取控制**：每次讀取都以使用者的 tSSO 身分驗權。無法判定時不揭露。看不到的文件，連存在與否都不透露。
2. **衍生資料**：摘要、Wiki、embedding、搜尋片段和計數，讀者都不會超過它的輸入；計數和排名只在可讀範圍內計算。
3. **資料不出公司**：內容只送 on-prem 服務，每個出口都要登錄並確認四個條件（不留存、不訓練、log 受控、on-prem）。
4. **撤權有效**：撤權、撤回、刪除之後不再釋出，初始目標是 1 分鐘內停止、10 分鐘內完成。agent 端則靠「不長期保存」的義務。
5. **維運不等於可讀**：維運人員沒有內容讀取權。直接存取資料庫要經跳板機、核准，每次都留紀錄。
6. **基礎防護**：各元件使用最小權限；儲存（含備份）加密；跨主機傳輸走 TLS。
7. **可稽核**：釋出、拒絕、權限變更、特權存取和篩檢命中都有紀錄；紀錄只存參照，不存內容。
8. **內容篩檢**：惡意 payload、有害內容、secret 和 PII、異常大量讀取都會偵測並記錄。每一類的模式（記錄、警示、gate）見第 6 節，逐步收緊。

**對 agent 的要求**（Agent Platform 義務，第 7 節）

- agent 代表人存取。平台以使用者權限為上限，agent 不會因此擴權。
- 釋出的內容只用在當次任務，不存進長期 memory，不拿去訓練，只送 on-prem 模型，只給它代表的那個人看。
- token 限定 audience；跨服務呼叫要換 token，不得轉送使用者的 token。
- 身分機制的收斂路徑：v1 驗使用者；接著驗 agent 身分（K8s ServiceAccount）；最後換發同時帶兩個身分的 token。

**平台不保證的事**

- 追回已經交給 agent 或使用者的內容。
- 偵測出所有 prompt injection 或所有敏感資料。偵測是分層降低風險，不是保證。
- 當作文件存檔系統使用。原件的保存與 legal hold 由 Source 系統負責。

## 9. 待帶回的公司參數

| 參數 | 代入位置 | 負責 |
|---|---|---|
| tSSO token 的 `aud`、TTL，以及有沒有 token exchange 或 introspection endpoint | 第 7.1 節：P0 的 `aud` 驗證、P2 的可行性 | 使用者帶回；代入 #76、#56 |
| agent 和平台是否在同一個 cluster；每個 agent 是否有獨立的 ServiceAccount | P1 的驗證方式 | 使用者帶回；代入 #76 |
| Agent Platform 是否規劃 token 換發的 gateway 或 sidecar | P2 | 使用者帶回 |
| 公司的儲存加密標準 | D3 | 使用者帶回；代入 #57、#78 |
| 公司的 log 保留標準 | E2 | 使用者帶回；代入 #56 |
| 公司的文件保存規定 | E1 | 使用者帶回；代入 #57 |
| 跳板機的核准流程細節 | D1 的 runbook | 使用者帶回；代入 #78 |
| 公司對 security A 的處理規定 | B2 的觸發條件；A 級接入前 | 使用者帶回 |
| 主管核准 Platform Security Baseline | 第 8 節；A 級接入；Agent Platform 契約 | 使用者 |
| Agent Platform infra team 同意第 7 節的義務 | 第 7 節 | 使用者 |
| 讀取限速的數值 | E3 | #88（PROD 讀取量）、#76 |

## 10. 交接

| 票 | 交接內容 |
|---|---|
| #56 | 衍生資料的敏感度（C1）；pre-filter 列入 enforcement 驗收案例（C2）；快取失效（C3）；operator 揭露與 break-glass 稽核（D1）；稽核內容、事件、保留和揭露（E2）；大量抽取偵測從記錄模式開始（E3、B6）；P1 的 E1 驗證（F1） |
| #57 | 向量庫和索引比照原文保管（C1）；儲存層加密含備份（D3）；legal hold 由 Source 負責，PROD 保留期限和 data owner 訂定（E1） |
| #78 | 元件最小權限（D2）；break-glass 經跳板機的 runbook（D1）；公司 K8s 安全基準和 parser 重新評估的觸發條件（D5）；TLS 和加密標準參數（D3）；讀取量指標（E3） |
| #76 | P0 驗 tSSO 和 `actor_verified`（F1）；依 user 限速、`429`（E3）；`traceparent`（F4）；不回傳原始向量（C1）；Agent Platform 義務和平台這一側的義務（F3）；P1 的 agent token 驗證（F1） |
| #55 | pre-filter（C2）；快取不跨使用者共用（C3）；embedding 服務選定前要先登錄出口（B4） |
| #107 | 第 5 類「敏感資料」，初始模式記錄＋警示（B5）；模式原則（B6）；篩檢模型的出口登錄（B4） |
| #113 | `actor` 在 v1 為選填；稽核紀錄加上 `actor_verified`（F1） |
| #86 | GAM 沿用 G9 的兩段檢查；不要採用 AuthZed 範例中會產生聯集擴權的寫法（第 7.1 節） |
| #121 | secret 和 PII 的地端偵測方法研究（B5） |
