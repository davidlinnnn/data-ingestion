# 企業知識作為 Agent Context：安全治理官方來源筆記

**查閱日期：2026-10-17（Asia/Taipei）。** 僅使用 OWASP 與 MCP 官方來源；這是研究與產品需求輸入，未採納新架構、人工審批流程或技術選型，也不是現有系統通過安全驗收的證據。

## 1. 版本與適用範圍

OWASP 官方 repo 將 **LLM Top 10 2026** 標示為 Published、release date 2026-08-04，`2026/final/` 為正式 Markdown 來源。本文採 2026 編號：Prompt Injection 為 LLM01、Excessive Agency 為 LLM03、Data and Model Poisoning 為 LLM05、Vector and Embedding Weaknesses 為 LLM09；避免混用 2025 的 LLM04／LLM06／LLM08。[官方版本說明](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/README.md)

Agentic Top 10 2026 的官方發布頁日期為 2025-12-09。MCP `latest` Authorization 查閱時導向 **2026-07-28**；本文區分其 normative specification 與標明 `draft` 的 Security Best Practices 教學，不把教學的每項建議當成已採納規格。[Agentic 官方發布頁](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)、[MCP Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)

## 2. 關鍵發現與產品含意

### Context 是資料，不能授予指令或工具權力

LLM01:2026 涵蓋 retrieved documents、tool outputs、多模態內容與 persistent memory；模型本身無可靠的架構邊界區分資料與指令。OWASP 建議假設模型的指令防線可能被繞過，限制其能做的事與輸出可到達的系統。Delimiters、提示詞、掃描與分類器只能分層降低風險；結構合法的輸出仍可能含惡意語意。[LLM01:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM01_PromptInjection.md)

**本研究推論：** 來源中的 SOP、操作範例或「請呼叫某工具」可作待理解的領域資料；被收錄、接受或發布，不會使它取得 system／developer instruction 的權位。即使文件屬公司內部或 owner 認可，也不能單憑該內容擴張 agent 的任務、權限或外傳目的地。

### 來源投毒與檢索投毒是不同攻擊面

LLM05:2026 明示 poisoning 不限訓練資料，也能發生於 ingest、transform、embedding、RAG 與 reuse；惡意來源、受污染的正常流程及 agent 間傳播都在範圍內。它建議來源與轉換 lineage、驗證、隔離與對抗測試。[LLM05:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM05_DataModelPoisoning.md)

LLM09:2026 另區分 embedding geometry／similarity-search 的攻擊：不含惡意指令的內容也能操縱召回、推測他方資料或污染 semantic cache。控制應在伺服器與實際檢索邊界落實，保留 embedding provenance，並管理索引、備份與衍生資料生命週期；事後隱藏文字結果不能涵蓋所有側通道。[LLM09:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM09_VectorAndEmbeddingWeaknesses.md)

**本研究推論：** 來源驗證、擷取品質與 retrieval integrity 需要分別驗收。中毒內容被摘要／重組後仍可能繼續傳播，不能讓生成整理洗掉原始來源、信任邊界與警示。安全掃描的觀察／隔離也不應無痕改寫固定原始證據，或刪掉本來應保留的研究內容。

### Provenance、簽章、認證與 trust label 都不是安全保證

OWASP RAG Cheat Sheet 明示：digest 與受控 baseline 相符，只證明內容一致，不證明沒有 prompt injection。它也要求檢索當下的授權、衍生內容的存取邊界及可追溯來源。[RAG Security，§1、§4–5](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)

MCP Tools 規格要求：非可信 server 提供的 tool annotations 必須視為不可信；server 仍須驗證輸入與存取，client 應驗證結果。Annotation 不能取代實際執行控制。[MCP Tools，Tool／Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/server/tools)

**本研究推論：** 「有來源」「內容受支持」「可發布」「目前可讀」「允許 agent 執行」必須分開。Trust／certified／read-only 顯示、來源簽章與 sanitizer 均不授予權限，也不能宣稱徹底安全。這些建議不構成全面簽章系統或逐文件人工批准的採納決策；合格更新可維持既有自動發布方向。

### 可讀知識不等於可執行動作；委派不能放大權限

LLM03:2026 把過多工具功能、過大權限與過高自主性分開，建議以任務所需最小工具與權限、使用者身分、完整 mediation 及高影響動作批准控制。多 agent 呼叫仍應保留原始使用者與授權 scope，不可只依 calling agent／service 的權限。[LLM03:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM03_ExcessiveAgency.md)

OWASP Agent Security 將執行授權放在 agent context 外：批准須綁當前 actor 與確切 action／參數，不能相信模型產生的 `user_confirmed`。它亦要求最少化敏感 context、分隔 memory、限制保存與跨 agent 權限。[AI Agent Security，§1、§3–4、§7–8](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html)

MCP Authorization 的 normative 規格要求 token audience 驗證、client `resource` binding，明文禁止將 client token 原樣轉交 upstream；proxy 的特定 confused-deputy 情境要求 per-client consent。成功登入或協定相容不等於所有下游操作已授權。[MCP Authorization Security Considerations](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations)

### Context 範圍與外洩路徑要同時管

官方 Prompt Injection Cheat Sheet 包含文件／issue／email 等間接注入、跨回合持續攻擊，以及 HTML／Markdown image 或連結夾帶資料的外洩路徑。安全測試應觀察實際工具呼叫及外傳目的地；乾淨的最終回答不證明沒有外洩。[Prompt Injection Prevention，Attack Types／Testing](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

MCP draft Security Best Practices 建議漸進的最小 scope，而非預先給全域權限；另處理 metadata discovery／redirect／URL fetch 的 SSRF。這些是實作安全指引，不代表本產品已選 MCP。[MCP draft Security Best Practices，Scope Minimization／SSRF](https://modelcontextprotocol.io/docs/draft/tutorials/security/security_best_practices)

**本研究推論：** Context 應依目前 actor、應用及已授權任務範圍最小化；caller 自填 purpose／topic 不能自行變成安全權威。保留完整來源與提交證據，和只向 consumer 交付必要且可讀內容是兩種責任。威脅模型需包含外部模型 provider、tool arguments、URL／rendering、agent 回覆、logs、cache 與 backups；read-only 知識服務仍有外洩風險。

### Memory 污染會跨 session 保存，來源撤回不會自動清除下游記憶

Agentic Top 10 的 ASI06 將 memory／retrievable context 的持續污染與一次性 prompt injection 區分。摘要、共用 memory、回饋與跨 agent 傳播都可能延續攻擊；建議隔離、保存界線、來源歸責、到期、quarantine／rollback，並避免 agent 自己產生的內容自動重新攝入 trusted memory。[Agentic Top 10 2026，ASI06，PDF pp.24–26](https://genai.owasp.org/download/52117/?tmstv=1765059207)

**本研究推論：** 未來若回收 traces、summaries、memory 或 feedback，需獨立的寫入資格與接受流程，不能因來自已授權 agent 就提升為可信企業知識。平台停止後續披露，與處理已交付 consumer 的 session、memory、cache、logs 是不同控制；後者需要 consumer 合約／配合，不能宣稱一鍵撤回能遠端清除所有副本。

## 3. Knowledge Platform 與 consumer 的責任界面

下表是以上來源的**設計推論**，不是新的 repo owner 決策。

| 責任 | Knowledge Platform 應能承接的證據／控制 | Agent harness／工具／應用必須另承接 |
|---|---|---|
| 來源與投毒 | 來源身分、固定版本、轉換／發布歸責、可疑內容處置與受影響範圍 | 對引用資料保留資料／指令邊界；不依標籤免除防護 |
| 存取與範圍 | 在每次服務依目前資格限制可披露內容、來源與引用；可追溯已交付版本 | 保留 user delegation／purpose；不得把 service grant 當 end-user grant |
| 資料最少化 | 提供有界檢索與適用資訊，不預設全庫注入 | context assembly、模型 provider 選擇、外傳／rendering 與秘密處理 |
| 有副作用的動作 | 知識服務不憑內容授權寫入、寄信、刪除、執行程式 | 工具／resource 級授權、獨立 policy enforcement、必要批准與 replay 防護 |
| 記憶與回饋 | 若要重新入庫，另驗身分、來源、品質、用途及生命週期 | session／memory 隔離、保存／到期、工具回饋與跨 agent 傳播 |
| 事件處理 | 暫停受污染發布、找出衍生內容／曾交付範圍、阻止後續披露 | 停止 agent／工具、處理 consumer 副本與 credential／action 風險 |

交付紀錄可證明平台交出了哪些 context；若沒有 consumer instrumentation，不能據此證明 agent 實際用了哪些內容、如何推論或哪個來源造成某次工具動作。

## 4. 事件處理與最低驗證輸入

OWASP RAG 指引要求能追索文件 IDs、授權決策、model／tool outcomes，並演練隔離中毒來源、失效 cache、識別受影響使用者。它同時警告不要預設記錄原始 prompts、retrieved content 或 tool arguments；必要事件證據另做權限、刪節與保存控制。[RAG Security，§11–12](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)

研究建議的驗證輸入：受信來源中的惡意文字／隱藏內容、來源正確但檢索被操縱、越權與撤權後讀取、含敏感資訊的引用／外部 URL、模型要求未授權工具、跨 session memory 再攝入，以及事件隔離後的 consumer 行為。觀察真實披露／工具效果與良性任務完成；未觀察到、缺 telemetry 或測試失敗不能算防護成功。[Prompt Injection Prevention，Testing／Report results with their limits](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

撤回、暫停披露、physical purge、備份與稽核保存須依各自政策處理，不把指引中泛稱的 deletion 直接當成本 repo 的 purge 協定。

**限制：** 未做本平台／Atlan／agent 的紅隊實測，未驗證任何控制已實作；官方指引也不能支持零 prompt injection、零投毒或完美回答的保證。僅提供安全責任、失效模式與後續驗證輸入，沒有加入通用簽章系統、全面人工審核或新 agent runtime。
