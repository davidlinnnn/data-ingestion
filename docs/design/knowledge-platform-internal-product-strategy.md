# Knowledge Platform 內部產品策略與功能規劃

**更新日期：2026-10-17**

**狀態：Q1–Q5 產品方向已由使用者確認。以下將其轉為初版功能與開發交接方案；未取代各 owner 的詳細規格，也未變更 tracker 範圍或開發優先序。**

Knowledge Platform 長期定位為公司內部共用產品，讓部門與主題負責人把分散來源整理為有證據、可驗證、能持續更新，並可供人與 agents 共用的知識。人類主要透過瀏覽、搜尋、閱讀與來源查證使用產品；既有 agents 使用相同知識，平台不預設內建對話問答。第一個研究團隊 pilot 用來驗證完整工作流程與收益；不把論文研究當成唯一長期使用情境。

產品策略驅動功能與開發優先序；資料庫、模型、協定與部署選擇依選定功能及驗收需求比較。現行設計依據是 [GitHub wayfinder map #52](https://github.com/davidlinnnn/data-ingestion/issues/52) 與 owner 的最新決策，local HLD 不作為目前設計 authority。

## 已確認的產品方向

| 決策 | 共識 | 對產品的影響 |
|---|---|---|
| Q1 長期定位 | 公司內部長期共用產品 | 成功看內部採用、重用、任務收益與維護成本；不以外部成交或訂閱收入設計初期功能 |
| Q2 核心工作 | 整理、驗證、發布知識，供人及 agents 共用 | 使用者要能持續維護可用知識；搜尋與接入是這條工作流程的消費入口 |
| Q3 維護分工 | 部門／主題知識負責人主導，應用與平台團隊協作；角色可兼任 | 有內容與問題的負責人；應用團隊驗收任務使用，平台團隊負責運行 |
| Q4 信任承諾 | 整理結果有充分來源支持，缺證／衝突透明，合格更新自動發布 | 不要求每份文件人工批准；一般更新自動進行，問題需要被看懂與處理 |
| Q5 人類主要體驗 | 瀏覽／搜尋／閱讀與來源查證為主；既有 agents 使用同一知識 | 優先交付可閱讀、可回來源的知識成果；不默認平台要擁有 hosted answering 與 agent runtime |

Q4 不取消既有來源保真、必要內容、權限、版本、撤回與接受條件。已知缺證不能只加警告就當成合格結果；哪些內容可保留並標示 unsupported、哪些失敗應阻止接受／發布，依相關產品與 Processing Profile 的既定條件執行。來源可追溯不等於來源主張已被全面驗真。

## 公司身分與授權要求

**2026-10-17 使用者確認：**user authentication 沿用公司 tSSO；GAM 是公司中央 resource authorization service，管理 resource 與 user（tSSO token 身分）的授權關係，並可在 request 時透過其服務判權。公司要求使用 GAM，或採用與 GAM 相容的同類授權機制。

Knowledge Platform 預計提供內建 GAM-compatible AA，讓未直接接 GAM 的小型應用使用，仍沿用 tSSO 身分。因此授權是平台預期提供的產品能力，包含兩種合規路徑：接公司 GAM，以及使用平台內建的 GAM-compatible 機制。這不是另建帳號／登入系統，也不表示管理員或 caller 可任意選寬鬆授權來源。

兩條路徑須遵循同一組已支援的資源／使用者／操作與決定有效性契約；GAM-compatible 的 meaning／scope／validity 要求沿用 [#53 Q12／Q13](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520)，具體相容層級由 #56 設計。受信任設定決定適用 authority／resource binding；內建 AA 並非 GAM 故障時自動放行或切換的 fallback。Source Authorization Ceiling、企業限制與平台 withdrawal 仍有效。GAM 的 allow 不能自動代表產品目前合格或已解除撤回。

**使用者補充的管理方式：**data owner 透過平台提供的 Resource Service，在平台內維護 resource 關係。這明確了維護入口與參與者；data owner 可管理的具體資源、關係及授權操作，仍受其權限與來源政策上限約束。

### Data owner 定義 Resource 與授權情境

**使用者明確的需求：**data owner 定義自己管理的 Resource，建立 `document → resource` 與 `user → resource` 存取關係，由兩者決定 user 對 document 的存取。Workspace 只是例子，不是固定的新領域實體；Resource 可以直接等於 Corpus，不強制額外包一層容器或另造一份身分。授權 scope 的意義與可信 binding 必須明確，不能由未受信任 caller 任意重解釋。

例如 Resource R 就是 Corpus C；文件 D1／D2／D3 屬於 C，data owner 授予 User 1／2／3 對 C 的適用存取權，這些使用者即應能存取該範圍內的文件。此權限來自明示的 user→resource policy 與文件關係共同成立；單純把文件加入一個未有相應授權的集合，不會憑空授權給任何人。

本稿依目前閱讀／搜尋／查證的產品方向，先將此處的 access 解讀為讀取；寫入、修改授權、管理成員及發布／撤回不自動隨讀權取得。

| 關係／操作 | 產品語意 |
|---|---|
| 文件綁定 Resource R，或屬於作為 R 的 Corpus C | 宣告文件納入該授權 scope；有相應 user grant 時可影響存取資格，因此相關新增／移除／重綁操作須治理 |
| User 1／2／3 取得 R 的存取權 | 在適用來源上限、企業限制及目前資格下，可讀 scope 涵蓋的文件；不需逐文件重複配置相同 grant |
| 未取得 R 的存取權的使用者 | 不能藉該 scope 的搜尋、片段、引用或附件繞過授權；其他合法授權路徑仍依各自契約判定 |
| 移除 resource grant／文件關係 | 該路徑的授權效果依已宣告的關係政策與生效契約變更；快取／在途請求及其他授權路徑由 #56／#76 處理，不把一般 Corpus reconciliation 與全域瞬時撤權混為一談 |

Corpus 描述知識組織，Resource 描述授權用途，兩個角色可由同一對象承擔。這不要求重定義既有 Corpus 的知識生命週期，也不要求 Resource 永遠與 Corpus 分離。多重歸屬、grant 合併及 Published Views 如何綁定該 scope，由 #53／#55／#56／#76 承接；不由一個命名例子推定。

為維持「取得 resource 存取權即可讀 scope 內文件」的體驗，**建議**在文件關係、成員／授權變更時驗證相容性：若來源授權不允許目前受眾，拒絕該不相容變更或先取得有權責的來源授權；resource grant 不覆蓋來源上限。來源政策後續變更仍須被追蹤，request enforcement 不能只靠加入時的檢查。這項衝突處置是建議，尚未由使用者選定；#53／#56 保有信任、上限及目前資格的詳細契約。

最小驗收情境：以一個真實 data owner 的 Resource 定義（可以直接是 Corpus）驗證 User 1／2／3 可讀 scope 內合格文件；無資格者不取得受保護內容／存在性；新文件關係沿用既有授權政策；grant／關係變更按生效契約處理；無管理權者不能修改 binding／grant。來源不相容的處置與目前資格生效點須明確。本段是功能驗收輸入，尚未執行，也不新增 core MVP gate。

建議的責任邊界如下，供 agreement 討論，不代表已選定新的實體服務或同步機制：

| 責任 | 建議歸屬與限制 |
|---|---|
| 知識資源的組織與管理 | 平台提供受控的資源／關係管理及 authorization-target binding；既有 Source／Asset／Canonical／Published View owners 保有各自 domain facts，不另造第二套內容／生命週期真相 |
| 資源關係與授權關係 | 分清分組／隸屬／衍生等關係，以及 user／resource／operation 的授權政策；Corpus 可直接作 resource，明示 grant 與 membership 共同決定資格，但 membership 本身不憑空產生 user grant |
| 關係變更的授權效果 | 若 hierarchy／membership 參與權限繼承，移動 parent／加入 group 就是授權敏感操作；驗證管理權並留下變更證據，分開「關係已保存」與「授權端已生效」。若需同步到 GAM，固定 authoritative side、失敗／延遲語意及生效觀察，不允許副本各自直接寫入 |
| Data owner 的維護權 | 只在被委派的 resource／operation 範圍管理；owner 身分不自動取得來源修改、跨域管理或任意擴權能力 |
| GAM 與內建 AA 的政策權威 | 每項授權關係只有一個權威寫入來源；GAM 管理的政策依其權威讀寫，平台可在已支援介面下提供管理入口；內建 AA 管理的政策依其宣告 scope 判定。最終資格仍套用全部適用的來源上限、企業限制與 withdrawal，不建立兩份可獨立修改且互相矛盾的政策 |
| 身分與 request enforcement | tSSO 提供 user authentication；GAM／受信內建 AA 提供其支援範圍的決定；平台與應用在實際可控邊界執行 |

**建議第一階段範圍：**從具名 data owner 實際管理的知識資源驗證共同授權契約；若 Corpus 已符合所需 scope，就直接用作 resource，不預建通用 resource graph／hierarchy engine。小型應用若還要代管其他業務資源，另界定其產品 owner、操作模型與責任。此處是分期建議，並未限制 Resource 必須叫 Workspace 或只能對應一種知識組織。

**尚待界定：**具體 data owner 的 resource scope 與關係語意、來源不相容的處置、多重歸屬／grant 合併／操作範圍，以及 API／SDK 相容程度與模式分期。Resource 可直接等於 Corpus 已是可接受的需求方向；詳細契約與分期仍未定案，也不因本段新增 core MVP gate。

## 與 Atlan 的策略比較

Atlan 的 Marketplace 面向資料與知識的發現、理解、責任與使用；CES 把 context 組合、測試、改善與交付形成工作流程。這兩點值得借鏡。[Data Marketplace](https://atlan.com/data-marketplace/)、[CES 概念](https://docs.atlan.com/product/capabilities/governance/context-engineering-studio/concepts/what-is-context-engineering-studio)

| 維度 | Atlan 公開產品方向 | 本產品的選擇 |
|---|---|---|
| 產品對象 | 多家企業的商業 context／governance 平台 | 同一公司內部可持續採用、可跨團隊重用的產品 |
| 主要維護工作 | 發現資產、補充語意與責任、建立及交付 context | 部門／主題 owner 維護來源範圍、知識成果、品質問題與更新 |
| 起步內容 | Data estate metadata、glossary／semantics，並延伸文件知識 | 沿用已選研究文件 pilot，驗證文件理解、Wiki／Retrieval 與證據鏈；其他來源由具名採用情境帶動 |
| 可信的使用方式 | 提供來源、認證、lineage、品質訊號與 context 測試；各路徑成熟度不同 | 明確承諾來源支持、限制透明與目前授權；以實際案例證明能力，避免先宣稱全面更可靠 |
| 成長方式 | 廣泛企業整合、不同 context 工作入口與下游工具 | 第一個完整知識流程可用，再讓第二個 consumer／team 重用，依實際維護需求擴張 |
| 產品證據 | 商業採用與各模組操作文件 | 已確認設計契約、限定 PDF core 證據；端到端產品能力與內部收益仍須驗證 |

詳細競品來源與交付狀態見 [Atlan 調查](../research/atlan-official-source-survey-2026-10-17.md)；現行 map 的比較見[策略調查](../research/atlan-knowledge-platform-product-strategy-2026-10-17.md)。不因 Atlan 有某個模組，就把它放入本產品 backlog。

## 建議的產品工作範圍

以一個**主題或業務用途的知識範圍**組織產品：有用途、負責人、允許的來源、使用限制，以及發布給人與應用的成果。使用者能從這個範圍找到相關文件與知識，也知道發生問題時找誰。

這是產品的組織方式，沒有選定新 Canonical entity、schema 或一個範圍與 Corpus／Published Views 的一對一關係。詳細 mapping 沿用 #55／#76 的契約工作，保留來源與產品各自權責。

### 完整工作流程

1. 主題負責人指定用途、來源範圍與預期使用者；取得適用的來源與提交授權。
2. 加入固定來源後，看到哪些已受理、處理、接受及發布，哪些失敗或仍有缺口。
3. 人類與應用團隊用實際問題檢查知識，回到正確版本來源核對；看懂已發現的缺證、衝突與限制。
4. 通過條件的成果自動發布，供授權的人與 selected agent client 使用；不同投影保留自己的產品語意與發布生命週期。
5. 來源或方法變更後，自動更新適用成果；普通更新與撤權／撤回分開處理。
6. 發現錯誤、缺漏或過時內容時，可帶著結果版本與證據回報；主題 owner 分流，修正後重新驗證與發布。

主題負責人不因維護這個範圍就取得 Source Owner 的修改／授權權力。來源錯誤回到有權限的 Source Owner；轉換、投影與應用行為問題分別交給對應 owner。回報不直接改寫 Canonical Knowledge，也不自動成為每份文件的人工發布關卡。

### 一個具體的知識成果案例

沿用已選 AI-agent self-evolution 研究任務：主題負責人加入獲准論文後，Wiki 提供一份主題整理，說明各方法在什麼條件下修改 skill／memory、使用哪些回饋、有哪些有依據的成效與限制。主張附來源引用；文獻沒有交代或結果互相矛盾時明示。研究者能從整理回到原文核對，selected agent client 也能透過相同知識範圍的已發布成果查找證據。

這個候選案例交付的是可重複閱讀與使用的主題整理，研究者直接瀏覽／搜尋、閱讀並查證，不必先發問才取得內容。具體組織／比較方式由 Wiki／Retrieval 產品 owner 定義，沒有新增 Canonical 指定欄位抽取 schema，也不減少 #84 已確認的必要內容要求。

## 建議的初版功能

PF 編號僅用於產品需求追蹤，與 #84 的 PDF F01–F22 分開。

| 功能 | 使用者完成的事 | 最小驗收成果 | 既有承接與新增產品責任 |
|---|---|---|---|
| PF01 用途與責任 | 指定知識的用途、範圍、責任人與適用限制 | 使用者知道這批知識用於什麼、包含什麼、問題由誰處理；不因加入範圍擴大權限 | 來源／Corpus／投影契約沿 #53、#55；用途與維護者的產品表達需新增產品需求 |
| PF02 來源加入與狀態 | 提交獲准來源，理解從受理到可用的進度與失敗 | 一份文件能分清受理、處理完成、Canonical Acceptance、各投影發布；失敗有可行的下一步 | #31、#32、#84、#55；不另造狀態權威；完整管理 UI 依 #79 |
| PF03 知識發現與閱讀 | 瀏覽／搜尋、閱讀主題成果與原文，理解內容脈絡 | 可直接找到並讀取主題整理；從 Wiki／Retrieval 結果到正確來源，保留產品區別與目前授權 | #54、#55、#76；完整人類 UI 依 #79 |
| PF04 證據與品質透明 | 看懂來源／生成內容、固定版本、缺口、已知衝突與限制 | 關鍵主張有正確且充分的支持；無法支持時不冒充可下結論；未授權證據不披露 | #32、#55、#56、#76、#84；新增已知衝突／問題的產品呈現，不承諾自動找出所有矛盾 |
| PF05 自動發布與維護 | 合格知識自動更新，辨認仍可用版本、更新中與失敗成果 | 新版本資格與發布有依據；失敗 replacement 不等於舊版都不可用；撤回不等背景重建 | #55、#56、#57；保留既有 automatic compatible-update policy |
| PF06 Agent 使用 | 既有 agent 在目前授權下使用相同知識與證據 | 一個 selected client 完成具體任務，保留結果／版本／引用與不可用狀態；user delegation 不被背景 grant 擴大 | #76、#56；不先指定 MCP／plugin，也不默認平台代管 agent |
| PF07 問題回報與修正追蹤 | 回報錯誤、缺漏、過時或不適用，知道誰處理與何時可用 | 回報附當時結果與版本；找到責任人；可追到修正／無須修改的處置與適用新版 | 新增產品回饋責任，連回 #53、#55、#76／#79 的授權寫入及生命週期；先不建立通用 source editor |
| PF08 採用與運行證據 | 判斷產品是否幫到團隊，以及維護是否可承擔 | 能完成實際任務、觀察更新／撤回／失敗，並記錄重用、返工、人工與運行成本 | #54、#78、#83 供既有營運與驗證輸入；產品任務收益需由產品與應用 owner 承接 |
| PF09 公司身分與資源授權 | 沿用 tSSO；接 GAM，或讓未直接接 GAM 的小型應用使用內建 GAM-compatible AA；data owner 定義 Resource（可直接為 Corpus），維護 document→resource 與 user→resource 存取關係 | 使用者透過明示 resource grant 與文件關係取得存取，符合來源上限與目前資格；binding／grant 管理需授權；request enforcement、相容性及模式分期須固定驗收 | 使用者確認的公司要求、預期能力及 resource 情境；#53 信任契約、#56 enforcement、#76 consumer 承接；內建 AA 需明確產品 owner／規格及開發交接，不由 #56 自動接管完整服務實作 |

PF01–PF09 描述能力與驗收，不代表九個獨立模組、九套服務或九張 UI。可先用既有受控 client、現成介面及簡單流程完成必要行為，再依實際使用摩擦決定完整 UI 的細節。

### 一組共同驗收案例

| 場景 | 應看見的結果 |
|---|---|
| 首次加入與使用 | 同一批已授權文件供人類理解／查證與一個 agent 任務使用；雙方可回到確切來源 |
| 已知品質問題 | 必要內容失敗不假裝可用；允許的 unsupported／缺口保留正確限制；對已知矛盾不默默合併成唯一結論 |
| 普通來源／方法更新 | 來源、處理方法與發布版本可區分；合格替代品自動發布；舊版是否可用依目前資格與政策 |
| 授權變更或撤回 | 受影響內容、存在性與引用等按選定治理契約停止披露；晚到成果與 restore 不恢復舊資格 |
| 使用者回報問題 | 可重現當時成果、分流到正確 owner，追到處置與重新發布結果；不能以回報權取得管理或來源修改權 |
| 另一個任務或採用者重用 | 另一個具名任務、獨立採用的應用或團隊不重複擷取與理解相同來源；新增整理、投影、接入與維護投入及收益可說明，不能只把原有 Wiki＋Retrieval 兩個入口算成跨團隊採用 |

既有 research pilot 任務、文件與數值目標依 [#54](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106396809)；擴大 PDF 需求依 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。不把 PDF／SOP／PPTX 設計案例直接轉成三種格式都已可交付的承諾。

## 功能排序與發布順序

策略排序以完整工作流程為單位。第一個完整內部產品需要下述功能切片中的 PF01–PF06 與最小 PF07／PF08。這些 PF 是需求分類，不各自成為一個大型模組；新增的產品表達／回饋／收益功能也不自動變成 #52 或 core MVP 的關票條件。

PF09 的公司身分與授權要求適用於上述流程；內建 AA 的 resource 範圍及分期另外界定，不預設首版必須同時交付兩種模式，也不能以分期為由省略適用授權要求。

### 第一個完整功能切片

**成果：研究者能使用一個持續維護的主題整理，查回正確原文；主題 owner 能處理更新與問題，既有 agent 也能使用相同知識範圍的適用已發布成果。**

範圍沿用 #54 的研究團隊、獲准 paper corpus 與 self-evolution 任務，不另創一個替代 pilot。可從固定 corpus 內選出支援同一研究問題的文件，先完成串接 checkpoint；這不減少完整 pilot、#84 必含內容或既有驗收範圍。

| 使用者動作 | 必須交付的成果 | 必要能力與驗收責任 |
|---|---|---|
| 主題 owner 選來源並提交 | 用途、來源範圍、owner 可辨識；看懂每份文件是否受理、處理、接受與發布 | PF01／PF02；主題 owner 接受範圍，平台／來源 owner 接受授權與狀態行為 |
| 研究者瀏覽／搜尋主題 | 讀到跨文件整理的 trigger、skill／memory 變更、回饋、成效條件與限制，主張有依據 | PF03／PF04；Wiki／Retrieval owner 定義成果，研究使用者／應用 owner 驗收真實問題 |
| 從主張開啟引用 | 到固定版本的正確來源位置；必要缺證／不支持內容不偽裝可用，已知衝突可辨識 | PF04；依 #32／#55／#84 的證據、必要意義與產品條件驗收 |
| 經歷一次合格更新及一次失敗更新 | 合格替代成果自動發布；更新失敗時，仍能分清失敗候選與可用的授權成果 | PF02／PF05；publication／governance owners 接受版本、資格與可見狀態 |
| 經歷撤回及晚到成果 | 搜尋、閱讀、引用等按宣告的治理邊界停止披露；晚到成果不恢復資格 | PF05；#56 給出明確 enforcement 邊界，與 publication／custody／serving owners 一同驗收 |
| 回報一個錯誤或缺漏 | 以當時結果、版本、證據與問題說明找到責任人，追到處置與適用新版 | 最小 PF07；主題 owner 分流，對應 Source／processing／projection／application owner 修正 |
| 既有 agent 查找同一主題證據 | selected client 完成指定任務並保留版本／引用／不可用狀態，不擴大委派權限 | PF06；應用 owner 驗收任務，#76／#56／#55 驗收存取與產品語意 |

同一知識範圍不要求 Wiki／Retrieval 同時發布或共用一個 Published View Version。首輪可用受控 client、既有閱讀入口、簡單 owner 記錄與既有問題追蹤完成可觀察流程；完整 UI 仍依 #79。PF08 同步記錄任務、查證／返工、主題維護、平台支援與運行投入，先不建立全公司 analytics 系統。

| 階段 | 交付成果 | 開始下一階段前需要的證據 |
|---|---|---|
| 核心整合與 pilot | 依現有 map 完成所需契約與實作，讓固定來源到 Wiki／Retrieval、證據與治理行為可驗收 | #54 任務、#84 必含需求及相依整合／qualification；核心 MVP 的實際接受證據 |
| 第一個完整內部產品 | 依已選人類體驗交付日常工作入口、最小管理與問題處理，並驗證 selected agent client | 目標使用者可完成真實工作；責任人能處理品質與更新；維護成本可承擔 |
| 另一個具名任務或採用者 | 另一個任務、獨立應用或 team 重用相同知識或工作方式；補該情境需要的來源／接入 | 新增整理、導入、投影與維護投入可解釋，重用收益存在、權限與責任完整；不只看文件數或入口數 |
| 擴大產品能力 | 按已驗證缺口增加連接器、協作、語意管理或新的知識產品 | 有具名需求與可驗收成果；新能力不稀釋原有來源、品質與治理責任 |

現行 [#79](https://github.com/davidlinnnn/data-ingestion/issues/79) 已確認完整 human UI 的設計在實際 core MVP 實作並接受之後。這份產品策略現在定義角色、能力及驗收，不開始完整畫面／編輯 UX 或前端實作。若採用者需要變更先後順序，應明確修改那項優先序；產品策略不默默增加 reverse blocker。

### 後續功能的進入條件

| 後續功能 | 何時值得做 |
|---|---|
| 新來源自動整合 | 已有具名來源與穩定到件，手動提交的投入成為實際採用障礙；能維持來源政策與變更交接 |
| 訂閱、通知與更完整變更比較 | 使用者確實需要主動追蹤更新／影響，既有狀態與簡單查看不足以完成工作 |
| 更完整協作、編輯與業務語意管理 | 有可重複的跨人整理、定義衝突或修正需求，且 Source／projection／publication 的寫入與歸責清楚 |
| 新投影或 Graph | 具名任務需要現有 Wiki／Retrieval 無法提供的關係操作與成果，且能定義品質與維護責任 |
| 內建問答或更廣 AI context 交付 | 新任務證明現有閱讀入口／外部 agents 不足，並另外確認回答、測試、狀態與修正責任 |

這些是擴張條件，不是預先排定的功能清單。真正的第一版是前述完整工作流程與已選必要功能，而非 Atlan 所有模組的縮小版。

## 如何驅動開發

產品功能進入開發前，必須連起：**使用角色 → 真實任務 → 可觀察成果 → 必要功能 → 驗收證據 → owner 與開發議題**。

1. 對已由 map 承接的能力，將被選中的產品任務與驗收交回原 owner；不複製來源、接受、發布或治理契約。
2. 將新的用途／維護者表達、問題回饋與產品收益驗證記成明確產品需求，指出依賴的既有契約與負責人。
3. 調整 #84 與 #80–#83 的承接範圍時，保留已確認的新需求與歷史證據；不能用舊 restricted-use 範圍限制新目標，也不能用需求當成驗證成績。
4. 先補沒有它就無法完成共同案例的缺口；其餘功能需指出改善哪個任務、如何量測，才進入下一次開發排序。
5. 技術選型比較選定需求的品質、端到端時效、恢復、權限、維護與資源成本；不以 Atlan 的技術組件表倒推本產品功能。

功能需求條目至少記錄：角色與觸發、預期成果、固定驗收案例、失敗／授權行為、既有 owner 或新產品 owner、相依契約、交付範圍與驗證證據。功能範圍／分期與開發交接在共同確認後承接；目前已依使用者要求同步已確認的 context，不改 issue 狀態、指派或 dependencies。

### 既有開發工作的具體輸入

| 承接位置 | 這份產品策略帶入的開發問題 | 應得到的交付物 |
|---|---|---|
| [Publication #55](https://github.com/davidlinnnn/data-ingestion/issues/55) | Wiki 的可閱讀主題成果與 Retrieval 結果如何支援同一真實任務，並保留輸入、引用、限制與自動更新語意 | 固定 multi-document 案例、具體成果／必要操作、產品品質與發布驗收；避免只交出檔案清單 |
| [Serving #76](https://github.com/davidlinnnn/data-ingestion/issues/76) | 人類如何 browse／search／read／follow evidence，selected agent client 如何使用適用成果 | 共同 consumer obligations、所選入口／client、結果／版本／證據／不可用範例及 bounded validation；協定仍由該 owner 比較 |
| [Admission #31](https://github.com/davidlinnnn/data-ingestion/issues/31) | 主題 owner 如何分清提交、處理、接受及發布結果，發生失敗後能做什麼 | 與原有 guarantees 一致的 command／status／correlation 契約與驗收，不另造一套產品狀態真相 |
| [PDF delivery #84](https://github.com/davidlinnnn/data-ingestion/issues/84) 與 [#80–#83 交接](https://github.com/davidlinnnn/data-ingestion/issues/72#issuecomment-6124692207) | 必要來源意義能否在處理、mapping、閱讀與引用中保留 | 新需求與舊規格 reconciliation、正式 profile／方法及 source-based qualification；不以範例任務降低必含功能 |
| [Governance #56](https://github.com/davidlinnnn/data-ingestion/issues/56)、[Persistence #57](https://github.com/davidlinnnn/data-ingestion/issues/57)、[Topology #78](https://github.com/davidlinnnn/data-ingestion/issues/78) | 日常使用、背景更新、撤回、晚到成果、失敗及 restore 如何共同成立 | 依目前授權、custody、固定 evidence 與 operating envelope 可驗收的詳細機制與營運交接 |
| 新增產品需求 | 用途／主題 maintainer 的產品表達、問題回報與處置、任務收益及維護成本尚需明確承接 | 一份最小產品需求與負責角色，重用既有 metadata／狀態／問題追蹤能力；不先建立通用工作流系統 |
| [Human UI #79](https://github.com/davidlinnnn/data-ingestion/issues/79) | 實際 MVP 驗收後，將已選 browse／search／read／evidence 與最小維護行為做成日常體驗 | 有界 first UI release 與端到端使用驗收；沒有提前選前端或改原先後順序 |

上述是產品輸入的優先重點，工程順序仍遵守 native prerequisites。#31 與 #55 可依 map 的既有 frontier 推進；#76 等待其必要產品契約，之後由治理、持久化與部署 owners 完成相依設計。正式實作依各規格與 dependencies 承接，不能把這份功能規劃當成所有前置設計都已完成。

## 產品成功的判斷

- **使用成果：** 實際人類與 agent 任務是否完成，重要結論是否有正確證據，返工是否減少。
- **重用：** 另一個具名任務、獨立採用的應用或團隊是否使用相同知識；計入新增整理、接入、投影與維護後，是否仍降低重複來源準備工作。
- **持續維護：** 新文件、來源更新、已知衝突與回報問題能否由 owner 處理，不依賴平台工程師長期代整理。
- **可承擔的成本：** 包含處理／重處理、查詢、儲存、來源核對、主題 owner 與平台支援投入。
- **持續採用：** 使用團隊是否願意把真實工作移入產品並承接維護責任。

任務與時間基線從目前做法取得；新增產品數值門檻由實際基線與 owner 設定。既有品質、權限及 #54 operating targets 按原適用範圍保留，不能用採用率或平均分取代必要條件。

## 進入詳細規格前的交接

**已同步 GitHub — 2026-10-17：**[map #52 的產品方向紀錄](https://github.com/davidlinnnn/data-ingestion/issues/52#issuecomment-6230758177)保存 Q1–Q5 與 owner 交接；[#56 授權／Resource 主紀錄](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6230755901)保存 tSSO、GAM／相容內建 AA、data owner 管理關係及 Resource 可直接等於 Corpus 的澄清。各自交接已加入 [#55](https://github.com/davidlinnnn/data-ingestion/issues/55#issuecomment-6230759824)、[#76](https://github.com/davidlinnnn/data-ingestion/issues/76#issuecomment-6230760445)、[#79](https://github.com/davidlinnnn/data-ingestion/issues/79#issuecomment-6230760883)，已結案 [#53](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-6230761362)只補後續指標。開放票本文有摘要及連結，均已讀回核對；這不是所有候選 PF 功能／分期的採納，也不新增 core MVP gate。

治理需求的後續研究見[Knowledge Platform 作為 Agent Context Layer 的治理研究](../research/knowledge-governance-context-layer-2026-10-17.md)。它提出 access control 之外的來源權威、適用性、用途限制、context 安全邊界、交付審計與事件處理，供 PF01／PF04–PF08 及既有 owners 評估；這些研究建議尚未自動加入 MVP 範圍。

正式 agreement 前的[責任 retro 與 bounded spike](../research/knowledge-governance-retro-spike-2026-10-17.md)進一步收斂為知識歸責、發布品質、受控交付、停供／恢復、最低事件證據與問題回饋。KP 不承接完整 agent 行為保證；使用者已補明 tSSO＋GAM／GAM-compatible 方向及平台內建 AA 的預期能力，首個 client、具體相容範圍與整合可行性仍未決。可執行模型不代替真實 provider／consumer qualification，也不增加 core MVP gate。

Q1–Q5 的產品方向已收斂。接下來不再重新詢問內用定位、核心工作或人類入口，而是由既有 owners 把上面的共同案例落成具體成果與驗收：固定論文／版本與問題、selected client、具名接受人、實際資源／成本與必要交接。這些依 #54／#55／#76 等原有 gates 補齊。

功能與分期的正式採納、產品 owner 的指派與 tracker 範圍／優先序變更仍需對這份具體方案取得共同理解；不能把已確認的策略選擇或已同步的 context 當成所有新增功能都已獲准開發。本稿已提供可供該決定檢視的功能範圍、共同案例與既有 owner 對照。
