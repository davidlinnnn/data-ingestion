# Knowledge Platform 治理責任：retro 與 bounded spike

**日期：2026-10-17。狀態：對研究建議的修正與可行性證據；不是 final agreement、技術選型或新增 MVP gate。使用者已補明 tSSO＋GAM／GAM-compatible 為公司要求，平台預計提供內建相容 AA；具體能力、相容範圍及首個 agent client 尚待界定／驗證。**

結論：**Knowledge Platform 應對自己處理、發布與披露的知識負責；不能承接整個 agent 的行為保證。** 合理的產品承諾是：在選定來源、用途與 consumer 範圍內，提供可歸責的來源與整理成果，按必要品質及目前政策發布／交付，揭露已知限制，能停止不合格的新披露，並留下可查證的邊界事件。來源真實性、業務裁決、模型行為與工具副作用各有其他 owner。

依據仍為 [active map #52](https://github.com/davidlinnnn/data-ingestion/issues/52) 與 owner 最新決策；local HLD 不作目前設計 authority。Q1–Q5 已確認產品方向不變：內部共用產品、知識整理／驗證／發布、主題 owner 主導、合格更新自動發布、人類 browse／search／read／查證、既有 agents 共用知識。

## 已補明的公司身分與授權要求

使用者確認 user authentication 沿用 tSSO；GAM 管理 resource 與 user（tSSO token 身分）的授權關係，可支援 request-time 判權。公司政策要求接 GAM，或使用 GAM-compatible 同類機制。Knowledge Platform 預計提供內建相容 AA，供未直接接 GAM 的小型應用使用，身分仍沿用 tSSO。這將「是否需要企業身分／授權整合」從未決問題改為硬性要求；內建資源授權也屬預期產品能力。

目前未決的是：內建 AA 是否也管理小型應用的業務資源、API／SDK 相容程度、首版模式分期，以及真實 token／resource binding／decision validity／失效與 outage 能力。不能將使用者對服務角色的說明當作已取得 SDK、協定或 runtime 證據。詳細產品承接見[公司身分與授權要求及 PF09](../design/knowledge-platform-internal-product-strategy.md#公司身分與授權要求)。

使用者提出 data owner 透過 Resource Service 定義自己管理的 Resource，建立 `document → resource` 與 `user → resource` 存取關係，讓被授權 User 1／2／3 可存取 scope 內文件。Workspace 只是例子，Resource 可直接等於 Corpus，不強制新增獨立容器。明示 resource grant 與文件關係共同決定資格；membership 單獨不憑空授權，也不突破 Source Authorization Ceiling。依目前產品用途，本稿先按讀取理解 access，管理／修改授權等操作另定。

責任維持受控的 resource／關係與 authorization-target binding，知識 domain owners 保有內容／生命週期真相，每項政策權威寫入來源明確。共用 Corpus identity 不自動混合知識更新與撤權的生效語意；多重歸屬、grant 合併與外部業務資源仍未定。為保留 scope 內文件可讀的體驗，建議在文件關係／grant 變更時阻擋來源不相容變更，或先取得來源授權；此處置尚未採納。現在政策與撤回仍須在 request 適用邊界 enforce。詳細情境見[Resource 授權需求](../design/knowledge-platform-internal-product-strategy.md#data-owner-定義-resource-與授權情境)；模型未實作或驗證此新增 resource 情境。

## Retro：前一輪應修正什麼

[前一輪研究](knowledge-governance-context-layer-2026-10-17.md)列出的面向有用，但「第一個 Agent 接入應具備的最小範圍」容易把研究分類變成整包新需求。標示尚未採納，仍不足以消除範圍誤讀。

| 處置 | 原建議的問題 | 修正後的承諾 |
|---|---|---|
| 保留 | 證據、目前資格、版本、撤回不是新發現，已有 map owner | 重用 #32／#53／#55／#56／#57／#76，不另造治理系統或重複關票條件 |
| 縮小 | 「來源權威／有效期／任務適用性」容易被理解為平台能自動決定何者為真 | 表達有權責來源實際提供的資訊；未知保持未知。只有所選操作必要的條件缺失，才阻擋該操作；研究論文無業務有效期不必全面封鎖 |
| 縮小 | 「衝突交 owner 裁決」可能迫使研究 owner 選一篇論文為真 | owner 決定發布處置及適用說明；可以保留未解差異，不必消除所有矛盾 |
| 縮小 | 「purpose／memory／training policy」容易演變成通用 policy engine | 第一個 consumer 只選定實際資料路徑與適用限制；可信政策／設定才有權力，caller 自述用途不是授權 |
| 改寫 | 「client 不把內容當提權指令」像在保證模型永遠不受 injection 影響 | 來源內容不能授予新資格；consumer／工具在實際執行處維持限制。攻擊測試只覆蓋 selected client 已暴露的能力，不能宣稱全面免疫 |
| 縮小 | 「delivery audit」容易被寫成已收到、已送入模型或已造成決策 | 區分選取、釋出、客戶端確認及 model-request 參照；平台只聲明實際觀測事件，不預設全 prompts／trajectory |
| 縮小 | incident handling 容易變成自動隔離、完整調查圖與全域撤回平台 | 先有具權限操作路徑與 runbook，能停供、定位受影響成果、修正／重測、受控恢復；可先人工操作 |
| 延後／拒絕保證 | 假設未來會有 SOP 操作、training、永久 memory、多 consumer 協商，就一律建置 | 具名用例出現才擴大；現有適用限制仍須執行。拒絕「追回所有已消費 bytes」「偵測所有注入／矛盾」等保證 |

完整人類 UI 仍依 [#79](https://github.com/davidlinnnn/data-ingestion/issues/79) 在實際 core MVP 實作與驗收之後，不由本研究新增 reverse blocker。也不縮減 #84 的必要 PDF 內容要求。

## 哪些是 Context Layer 的責任

「共同責任」須拆出實際執行點，不代表 KP 可以用註記把自身義務交出去。

| 問題 | KP 直接負責 | 外部權責／執行點 | 可行性與目前界線 |
|---|---|---|---|
| 來源權威、用途、適用期 | 保留可信來源、來源角色、歸責及已知限制，區分原文／OCR／生成解讀 | Source／policy authority 提供政策；主題 owner 維護用途與發布說明 | 資訊表達可承接；不能自行判定來源真理或企業 precedence |
| 整理結果的品質與證據 | 依所選 Processing Profile／Canonical／projection 條件驗收，保存確切輸入、方法、引用與 coverage；必要失敗不能發布 | 內容與產品 owner 定義可驗證標準；應用 owner 驗任務適用性 | 結構與版本可工程化；引用是否充分支持主張須固定樣本與評估，非「有 URL 就通過」。不保證下游回答皆正確 |
| 目前身分、委派與政策 | 沿 tSSO 身分，在其控制的 internal／external 讀取及 protected observations 執行目前資格；提供預期內建 GAM-compatible AA，詳細範圍另定；來源上限不能被 app grant 擴大 | 公司 GAM 或受信任相容機制提供有 scope／validity 的可信授權事實；組織決定政策 | 公司要求與內建能力方向已確認，provider／內建實作能力未 qualified；不能用 prototype 取代真服務證據 |
| 用途與模型外送 | 拒絕不支援／不允許的已選交付路徑；交付必要限制，避免任意 caller 自稱 approved route | consumer／模型服務／egress owner 控制實際後續傳送與保留 | 固定一條受控路徑可做；文字離開 KP 後，僅附 label 無法強制禁止複製／training |
| Context injection | 維護來源與處理完整性、受權寫入、已知事件停供；不讓內容修改平台授權 | Agent Owner 控制 context assembly；工具／業務系統控制任務、目標、參數與批准 | 可做分層風險控制，不能保證模型不被騙。read-only client 不必新增付款／刪除等工具治理 |
| 發布、停供與撤回 | 獨立產品生命週期、目前資格、受控快取／引用／附件與晚到成果；不等一般 rebuild 才生效 | consumer 承接其快取／session／保存責任，並提供所宣告範圍的證據 | 需要明確觀察邊界與競態驗證；已交付 context 不能當作已追回 |
| Retention、purge、restore | 對 platform custody 中的來源、採用 artifacts、證據、衍生副本與備份政策歸責；restore 不復活舊資格 | 來源系統及下游各自控制其副本；組織決定適用保留義務 | 可設計／實作，但成本與完成證據依 storage／backup 選型；withdrawal 不等於 purge |
| 審計、回饋與事件 | 最小釋出／拒絕事件及 correlation、受保護的調查存取、帶版本的問題分流 | consumer 提供實際 model request／工具結果；incident owner 協調 | 最小紀錄與 runbook 可做；不承諾完整推理因果、全公司 traces 或全部 logs |
| 業務執行結果 | 提供適用知識與限制 | 應用、Agent Owner、業務系統及有權批准者 | KP 不擁有交易正確性、工具授權或最終業務決策 |

來源支持這種分工，而非替我們完成設計：[NIST ABAC](https://nvlpubs.nist.gov/nistpubs/specialpublications/NIST.SP.800-162.pdf)區分政策判定、執行及屬性來源；[OWASP RAG](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)區分 retrieval 與 tool 授權。[RFC 7009](https://www.rfc-editor.org/rfc/rfc7009.html)的 token revocation 也有傳播與 resource server 協作界線，不能外推成內容副本已撤回。逐項事實及限制見[四項來源反證](knowledge-governance-context-layer-2026-10-17/retro-feasibility-sources.md)。

## Spike 1：現有契約與可重用實作盤點

這是文件／程式檢查，不是 runtime qualification。

- [#53 Q12／Q13](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520)已要求 accountable policy authority、可信 document／authorization-target binding、meaning／scope／validity 相容、caller 不能自選寬鬆 provider、denial 與 unavailable 分開；provider allow 不推翻 platform withdrawal。**沒有 qualified 的具體 GAM protocol／SDK／policy engine。**
- [#56](https://github.com/davidlinnnn/data-ingestion/issues/56)本來就要求 current-state、cache、late completion、rollback／restore、觀察邊界與 enforcement evidence；receipt／applied／enforcement／purge 不混為一談。研究補充不能把它擴張成所有 agent security。
- 本地 checkout 的 [processing](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/src/pdf_processing/processing.py)、[object store](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/src/pdf_processing/object_store.py)、[enrichment](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/src/pdf_processing/enrichment.py)可重用固定 object version／digest、checked artifact reads、producer binding 及必要 evidence barrier。**這些不是 user authorization、Canonical Acceptance 或 Published View publication。** 成功 enrichment 仍明示 `canonical_accepted: False`／`quality_accepted: False`。
- 本地 `src` 未見可直接接入的通用 Serving／GAM adapter／Wiki／Retrieval／撤回／purge／delivery audit；此 branch 落後，不能推論所有 remote 分支都沒有實作。以本地證據只能說：本次尚無可用的端到端整合環境。

## Spike 2：用途、撤回與副本邊界的可執行模型

產物：[可直接用瀏覽器開啟的 HTML](../prototypes/context-governance-boundary.prototype.html)、[執行結果 JSON](knowledge-governance-context-layer-2026-10-17/spike-results.json)、[瀏覽器驗證畫面](knowledge-governance-context-layer-2026-10-17/spike-screenshot.png)。單檔、無 dependency、無持久化；按「執行 self-check」可重跑。不是 production policy engine，也未選定 generation／fencing 為正式機制。

Prototype 與原始 spike 證據保留於本機 throwaway branch `codex/context-governance-spike-20261017`；這是補明公司 tSSO／GAM 要求之前的快照，未實作該整合。未切換目前 checkout、帶入其他工作或推送遠端。相關 implementation／validation 的承接位置是 #56／#76／#57；本報告先保留指向，未在 agreement 前寫入 GitHub 作為採納決策。後續補明的內建 AA 需另有明確產品 owner／規格及交付範圍。

**實際執行：Node v26.5.0，14 個 assert 全通過；開始請求／撤回／晚到成果／還原 payload／釋出回應五事件共 120 種排列。** 正確模型在撤回後新披露為 0；刻意只在開始請求驗權的 negative control 有 20 種排列披露已撤回內容。瀏覽器另操作了正常交付→撤回→快取再次請求，確認新回應不可用、先前接收方副本仍有 1 份；self-check 與 Node 一致。

20 是符合 `begin < withdraw < release` 的模型反例數（`5! / 3!`），不是實測洩漏率。模型只有一位 fixture user、一個 pending request；整張 HTML 是 operator／教學檢視，拒絕不披露的 invariant 僅指 response object，不代表此 debug 畫面可提供給一般 consumer。

| 模型案例 | 觀察結果 | 可以／不可以推論什麼 |
|---|---|---|
| 未核准 route 偽稱 approved purpose；未知 route | 不回內容、版本或 evidence references | 可表達「caller claim 不授權」；trusted route binding 是 fixture，沒有驗證真實 client 身分 |
| 使用者資格撤銷，app 原本仍可用 | 拒絕披露 | 可表達授權不能被 workload grant 擴大；沒有驗證真委派 token |
| 請求開始允許，釋出前撤回／政策不可用 | 拒絕披露 | 只在 admission／request start 查權不足；真實 PDP freshness、失效與 outage 未驗 |
| cache hit、晚到新成果、還原舊 payload | 不恢復治理資格 | 顯示 payload 與目前資格要分開；restore **沒有還原政策 DB**，未證明真 backup restore 安全 |
| 撤回後明確重新核准 | 舊 generation 請求拒絕；新請求可用 | 一個防止舊工作跨資格世代復活的候選；不是正式 regrant 流程或唯一機制 |
| 先前成功交付後撤回 | 接收方仍保有 bytes；僅停止後續新披露 | 原文刪除／API 停供不代表外部 context／memory 清空 |
| response 有 evidence／release record | 記錄固定參照與釋出事件 | 不證明 source truth、client 收到、模型採用、決策因果或 injection 安全 |

**最重要的未驗假設：**模型把目前資格檢查、release 與最小紀錄放在一個原子轉移。真實 check→網路寫入、串流中撤回、多 server cache、policy service 延遲、audit 故障及完整 ledger restore 均未測。120 種排列是這五事件的有限探索，不是任意併發、故障或攻擊的證明；也不涵蓋 mixed-source derivation 與所有 protected observation。

## 可行性結論與成本來源

| 能力 | 現在的判斷 | 主要投入／未解依賴 |
|---|---|---|
| 版本／證據／來源與生成內容歸責、owner 與限制表達 | 可作明確產品需求，沿既有契約開發 | 真實來源 metadata、必要內容品質、projection 保真；不是增加 badge 就完成 |
| 符合條件自動發布、已知缺證／衝突的發布處置 | 可承接，仍須以既定樣本驗證 | #55 產品 gate，#84 processing 能力與 #83 端到端 qualification；不能從此模型推出語意品質已可行 |
| 一條受控 agent path 的目前資格與使用限制 | 邏輯可表達，provider／consumer 整合可行性未決 | #76 選 client／操作／資料流；#56 查可信 identity、binding、validity、revocation 與 outage 事實 |
| 撤回、cache、晚到成果與 restore | 有可行候選，但尚不能承諾數字或 production 一致性 | #56 的觀察／完成契約，#57 的 durable state／restore，#78 實際部署與網路；這是主要工程風險 |
| 最小釋出紀錄、問題分流、operator runbook | 可小範圍開始，不需完整監控產品 | 欄位與事件真實語意、保護／保留／故障處理；使用者／service principal 必須記真實身分，不虛構 end user |
| 偵測所有注入／自動判定全部業務適用性／追回已消費 bytes | 不作產品保證 | 不因 vendor 有安全功能或列出標準就變成可保證；只能做有範圍控制及實測 |

使用者已確認 tSSO＋GAM／GAM-compatible 方向，平台內建相容 AA 亦屬預期能力；目前未取得可測的服務／協定資料，首個 agent client 尚未選定，故真實整合未測。內建 AA 的資源範圍及相容層級未決，亦未做 throughput／latency／儲存／人力估算，不給缺乏依據的工期或成本數字。所列「可承接」是責任與工程路徑合理，不是交付日期或 runtime 達標。

## 建議收斂成五項候選功能

1. **可歸責的知識資訊**：來源／生成角色、owner、固定版本／引用、已知限制；未知資訊不冒充已知。不另建企業真理排序。
2. **可驗收的發布品質**：所選產品的必要支持與 coverage、有依據的缺證／衝突處置，普通合格更新保持自動。
3. **受控交付與公司授權能力**：沿用 tSSO，接 GAM 或使用平台內建 GAM-compatible AA；內建範圍與分期另定。人／selected client 的操作與資料流明確，在每個適用披露邊界執行目前資格，無可信 basis 不披露。只處理實際適用用途限制，不造通用 purpose 推論引擎。
4. **可操作的停供與恢復**：明確授權操作、影響範圍與 runbook，晚到／cache／restore 不復活資格；consumer 處理自己宣告保留的副本，withdrawal／purge 分開。
5. **最低事件證據與問題回饋**：真實 principal／consumer、版本／參照、政策決定／原因、事件時間及 correlation；帶版本回報並分流。不預設保存原始 prompts 或完整 agent trajectory。

這些是產品能力組合，不代表五套服務。已在 map 內的要求維持；新增產品語意／回饋／審計細節由對應 owner 承接，不能整包變成 #52 或 core MVP gate。

## Final agreement 前尚需哪些決策必要證據

| 下一個 bounded spike | 所需輸入與 owner | 最小輸出／停止條件 |
|---|---|---|
| tSSO＋GAM／GAM-compatible 授權整合 | #56；既定公司要求，受信任 authority、client／actor／target binding 與 sandbox；內建 AA 範圍先界定 | allow／deny／unavailable；scope／validity；delegation 不擴權；撤權後的有效性。分別驗真實 GAM 路徑或內建實作；相容 contract fixture 不等於兩者已 qualified，缺能力就調整支援範圍 |
| 所選 Serving／consumer 的交付路徑 | #76＋Agent／model owner；具名 client、模型位置、工具／cache／memory 盤點 | 一個允許路徑、一個實際禁止路徑；只測已暴露的工具／egress／持久化。無驗證失效能力時，優先選不保留 client 持久快取的受控路徑；不能證明控制就不開放該受限資料流 |
| 撤回競態與真 restore | #56／#57／#78；選定觀察邊界、policy state、storage 與 runtime | pause→撤回→繼續 release；cache hit；晚到 publication；舊 backup restore；服務／audit 故障。證明所宣告邊界停止新披露，分開 receipt／applied／enforced／purged；不能先承諾 instant global revocation |
| 知識品質／證據的實際產品切片 | #55／#84／#83＋主題 owner | 確切來源支持、必要內容與已知差異、失敗不冒充通過、合格更新自動發布；人與所選 agent 查到同一治理範圍的適用成果，各投影仍獨立發布 |

前三項是否需要在詳細設計定案前實做，取決於能否取得足以排除決策風險的真實 provider／consumer 事實；不能把所有 runtime qualification 提前變成設計關票條件，也不能把決策必要未知留成「之後再說」。本輪只完成上面的文件盤點與可執行狀態模型，不聲稱這四項整合已通過。

研究／prototype 階段未變更 production code、tracker 依賴或 MVP 範圍。後續已依使用者要求，把已確認產品方向同步至 [#52](https://github.com/davidlinnnn/data-ingestion/issues/52#issuecomment-6230758177)，公司授權／Resource 澄清同步至 [#56](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6230755901)，相關 tickets 各承接 context；候選治理功能、技術機制與 prototype 未因此獲得正式採納或 runtime qualification。可行性證據的邊界如上。
