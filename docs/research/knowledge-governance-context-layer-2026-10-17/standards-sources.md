# Knowledge／Agent Context 治理：官方指引與標準來源

**查閱日期：2026-10-17（Asia/Taipei）。狀態：來源研究，非已採納需求或合規認證。**

目的：釐清企業知識平台除了「誰可以讀」之外，還要治理什麼；尤其當內容成為 agent 的 context、工具輸入或可重用的衍生知識時。以下區分官方已發布指引、標準語彙、進行中工作，以及本研究提出的產品控制。來源日期與查閱日期分開，不把網站近期更新當成標準新版本。

## 1. 來源與效力

| 來源 | 日期／狀態 | 適合回答什麼 |
|---|---|---|
| [NIST AI RMF 1.0 官方入口](https://www.nist.gov/itl/ai-risk-management-framework) | 2023 年 framework；查閱時官方註明修訂中 | 自願性的 AI 風險管理架構，不是認證或法律義務清單 |
| [AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) | AI RMF 1.0 官方摘錄 | Govern／Map／Measure／Manage 的組織、用途、驗證、監測與處置責任 |
| [AI RMF Appendix C：Human-AI Interaction](https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/) | 2023 年 framework 官方摘錄 | 人類責任、監督與自動化如何隨情境安排 |
| [NIST AI 600-1：GenAI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) | 2024-07-26；已發布的跨產業 companion profile | GenAI 額外風險與 suggested actions，不是 mandatory implementation checklist |
| [NIST AI Agent Standards Initiative](https://www.nist.gov/artificial-intelligence/ai-agent-standards-initiative) | 建立 2026-02-17，頁面更新 2026-08-14 | 研究、協作與標準化方向，不能當作已完成的 agent 標準 |
| [NCCoE agent identity resource hub](https://pages.nist.gov/nccoe-ai-identity/) | 查閱時為進行中 project | 實作指引與示範的開發方向；未標示內容發布日 |
| [Agent Identity／Authorization Concept Paper](https://www.nccoe.nist.gov/publications/other/accelerating-adoption-software-and-ai-agent-identity-and-authorization-concept) | 2026-02-05；Draft Concept Paper | 徵求用例、identity／authorization／audit 問題，不是最終 reference architecture |
| [NIST agent identity 官方文章](https://www.nist.gov/blogs/cybersecurity-insights/back-future-why-agentic-ai-needs-strong-identity-foundation) | 2026-08-27；Bill Fisher、Ryan Galluzzo 官方 blog | 避免共用 credential、過廣授權與把 HITL 當成所有問題的解答；是說明文章而非規範 |
| [W3C PROV-O](https://www.w3.org/TR/2013/REC-prov-o-20130430/) | 2013-04-30；Recommendation | 可交換的 entity／activity／agent 與 derivation／attribution／delegation 語彙 |
| [W3C PROV Overview](https://www.w3.org/TR/2013/NOTE-prov-overview-20130430/) | 2013-04-30；Working Group Note | PROV family 導讀；Overview 本身不是 Recommendation |
| [W3C ODRL Information Model 2.2](https://www.w3.org/TR/2018/REC-odrl-model-20180215/)／[Vocabulary 2.2](https://www.w3.org/TR/2018/REC-odrl-vocab-20180215/) | 2018-02-15；Recommendations | 使用許可、禁止、義務及用途／時間等限制的政策表示 |
| [W3C Data Quality Vocabulary（DQV）](https://www.w3.org/TR/2016/NOTE-vocab-dqv-20161215/) | 2016-12-15；Working Group Note | 品質量測、政策、註解及其來源；不是通用真實性認證標準 |

## 2. 官方指引對「治理超過 ACL」的直接支持

### NIST AI RMF：管理用途、責任與整個生命週期

**來源事實：**Govern 是跨其他 functions 的持續責任。Core 明列政策與 accountable roles、系統 inventory、第三方資料／元件風險、用途與知識限制、部署前與運行中量測、使用者回饋、incident response、停用與 change management。它明說 functions 不是固定順序的 checklist，可依風險與資源使用。[Core，Govern 1／2／6、Map 1／2、Measure 2／3、Manage 2／4](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)

**本研究解讀：**「已授權讀取」只解決一部分問題。同樣獲准的文件，仍可能不是目前有效版本、不適合某個任務、存在互相矛盾的解釋，或不能被帶到另一個模型供應商。平台需要讓這些差異可被判斷與處置；不必因此建立新的中央治理服務。

### GenAI Profile：可核對的具體 suggested actions

以下僅選與知識 context 直接相關的條目，非完整 Profile 或整套控制的採用承諾：

| 條目 | 官方建議的重點 |
|---|---|
| GV-1.2-001 | 記錄 training／generated data 的來源與歷史，支持 content transparency |
| GV-1.3-002 | 建立可衡量的 performance／assurance thresholds，供部署 go／no-go 使用 |
| GV-1.5-001 | 為 provenance 定期檢視及 incident monitoring 指定組織責任 |
| GV-1.5-003 | 為 TEVV 與 content transparency 的歷史建立 document retention policy |
| MS-2.5-001 | 不由狹窄、非系統性的評估外推能力 |
| MS-2.5-003 | 在部署前量測與持續監測時核對生成結果的 sources／citations |

來源：[NIST AI 600-1，第 3 節，各 action ID](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)。Profile 涵蓋 privacy、IP、information integrity、confabulation、human-AI configuration 等風險；引用它不代表本產品已符合特定法律，亦不支持無限保留所有 prompt／文件。

### 人類負責，不等於每份文件都要人工簽核

**來源事實：**Appendix C 描述 human-AI configuration 從 fully autonomous 到 fully manual；有的系統不需要 human oversight，有的需要，應明確區分人員角色及責任。[Appendix C](https://airc.nist.gov/airmf-resources/airmf/appendices/app-c-ai-risk-management-and-human-ai-interaction/)

**本研究建議：**保留既有「明確規則合格即自動接受／發布，需判斷的例外才交有權責人」方向。人類責任落在規則與適用範圍、驗證結果、例外處置、停用與重大變更；不能從 governance 一詞推導出所有 ingestion 都改成人工核准。

## 3. Agent context 需要的 authority 與 attribution

**來源事實：**NIST 官方 2026-08-27 文章指出，把個人或企業 credentials 直接交給 agent 會破壞 accountability；agent 宜有自身 identity 與 entitlement，並連到其代表的人／系統。文章也討論 short-lived、scoped、audience-restricted credentials，並提醒過度依賴 HITL approval。這些是 IAM 方向，並非已頒布一套專屬 agent standard。[官方文章正文](https://www.nist.gov/blogs/cybersecurity-insights/back-future-why-agentic-ai-needs-strong-identity-foundation)

**狀態界線：**NCCoE hub 明說最終交付「將是」SP-1800 practice guide，含 implementations、architectures 與 build details。查閱時不能把未來交付寫成現成架構或產品認證。[Project hub](https://pages.nist.gov/nccoe-ai-identity/)、[Draft Concept Paper](https://www.nccoe.nist.gov/publications/other/accelerating-adoption-software-and-ai-agent-identity-and-authorization-concept)

**本研究建議：**一次 context delivery 應能歸責到「哪個 agent／workload、代表誰、哪個任務、允許什麼用途與接收者、採用哪些固定知識版本」。不應把通過 login、持有 MCP token、或有讀文件權限，當成可以轉交外部模型、改寫知識或呼叫其他工具的完整授權。確切 identity／delegation protocol 交既有 Serving／Governance 設計決定。

## 4. PROV、ODRL、DQV 能借用什麼，不能代替什麼

### PROV：把生成與責任鏈說清楚

**來源事實：**PROV-O 提供 Entity、Activity、Agent，以及 `used`、`wasGeneratedBy`、`wasDerivedFrom`、`wasAttributedTo`、`actedOnBehalfOf` 等關係。它有助交換某份資料由誰、經哪個活動與輸入產生的記錄。[PROV-O starting-point terms](https://www.w3.org/TR/2013/REC-prov-o-20130430/#description-starting-point-terms)

**本研究建議：**用來檢視 source→processing→Canonical→projection→consumer 的證據鏈是否缺欄位；讓生成解讀與原文、實際方法與宣稱方法可區分。這不要求全面改用 RDF／graph DB，也不表示記錄 provenance 就能證明內容為真、發出者有授權或 log 未被篡改；這些仍需其他驗證與控制。

### ODRL：使用權比 read ACL 多一層

**來源事實：**ODRL policy 可表示 asset 上的 Permission、Prohibition、Duty，以及 constraints；其標準 vocabulary 包含 purpose、recipient、dateTime、derive、distribute、attribute、delete。這是在表達誰能以哪些條件使用與再利用內容。[Information Model](https://www.w3.org/TR/2018/REC-odrl-model-20180215/)、[Vocabulary](https://www.w3.org/TR/2018/REC-odrl-vocab-20180215/)

**本研究建議：**在具體來源需要時區分內部閱讀、生成摘要、提供 agent context、傳給指定外部模型、用於訓練及再散布；保留 policy authority／版本及承接 owner。這些是本產品可能要定義的 action／purpose 語意，尤其「模型訓練」不可假定已有完全符合需求的 ODRL core action。ODRL 是政策表示，不會自行執行刪除、不會阻止模型使用內容，也不判定合約有效性；未知與不支援的限制不可默默放寬。

### DQV：品質要附測量範圍與方法

**來源事實：**DQV 不試圖制定唯一 quality 定義；它提供可交換的 measurement、metric、policy、feedback 與 provenance，讓 consumer 判斷 fitness for purpose。它是 Working Group Note，不能稱為 W3C Recommendation 或通用認證。[DQV Introduction／Vocabulary Overview](https://www.w3.org/TR/2016/NOTE-vocab-dqv-20161215/)

**本研究建議：**分開記錄來源權威性、抽取保真、引用支持、時效、適用任務與已知缺漏。任何「合格」都要能看出測了哪個版本、用哪個規則、分母與必要條件；不要將 metadata completeness 或模型 confidence 轉成無條件的 trust score。

## 5. 可轉成交付工作的控制問題

以下是本研究提出的產品問題，不是上述標準逐字要求，也不自行改寫既有設計決策：

| 治理面向 | 除了 access 還要能回答 | 可觀察的結果／驗證例 |
|---|---|---|
| Authority／ownership | 哪份來源有權建立這個定義？誰負責矛盾與例外？ | 兩份政策衝突時保留各自來源與適用域，交指定 owner，不由 popularity 決勝 |
| Provenance／evidence | 原文、OCR、生成解讀及人工修正如何區分？ | 查一段 context 能回到固定來源／方法／判定，而非只連向會改動的 URL |
| Quality／fitness | 這份知識通過什麼驗收、可支持什麼任務？ | 閱讀摘要合格不被自動解讀為數字比較、法規判斷或自動執行也合格 |
| Lifecycle／currentness | 新版本、失效、撤回如何影響已發布與衍生內容？ | 固定歷史引用仍可追溯；當前使用資格另判，撤回不等普通 rebuild |
| Purpose／use／retention | 可以讀，是否也能外送、訓練、轉售或無限留存？ | 不符合用途／接收者條件的交付被拒絕或標記 unsupported；依責任保存必要證據並執行適用清理 |
| Agent authority | agent 的操作是代表誰、為哪項任務？ | 取消委派後不能憑舊 token 或舊 context 持續取得新披露／執行權 |
| Evaluation／audit | 能否發現錯誤並歸因到來源、處理、投影或 consumer？ | 固定失敗案例可重測；處置有 accountable owner；log 本身亦受資料與保留政策限制 |
| Controlled change／incident | 誰能修改規則、停用錯誤版本及恢復？ | 自動發布失誤有可查判定／影響範圍與撤回；重大變更依既有 owner 與 release gate |

平台能提供版本、證據、政策、驗證與交付邊界；External Consumer／agent application 仍負責其最終 context assembly、工具執行與業務決策。提出治理問題不代表平台要包辦通用 agent runtime 或自行判斷所有企業法務規則。

本次未做法域法律分析、認證對照、工具實測或新契約採納；也沒有把進行中的 agent 標準化計畫當成已定技術規範。適用限制需由有權責的內部角色或來源契約提供，不能由模型從網頁推測。
