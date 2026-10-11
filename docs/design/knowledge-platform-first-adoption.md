# Knowledge Platform first-adoption workload and operating envelope

**狀態：已確認，2026-10-11。** 使用者已確認 Q1–Q22，以及下列 V01–V08 驗證矩陣、缺證輸入的 owner／交付門檻與 Map revisit 處置。詳細決策權威在 [Set the first-adoption workload and operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54) 的各輪紀錄及結案紀錄。本文件是已確認的設計輸入與驗證交接；實際論文、具名窗口、配置成本及 runtime qualification 仍須依交付門檻補齊。

## 已確認的採用範圍

| 項目 | 已確認內容 | 決策紀錄 |
|---|---|---|
| 首批使用者與工作 | Research team 使用 LLM／AI agent 論文，進行主題式文獻整理與方法比較。Wiki 支援跨論文理解；Retrieval 支援來源查找、核對與比較，供閱讀、討論及選題使用。 | [使用者／文件方向更正](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6097475921)、[Q1](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6098053959) |
| 初期整合與分期 | 預期由使用者手動上傳文件，透過受控 client 呼叫 ingestion API 提交與更新已捕獲論文。第一階段驗證 Canonical 到 Wiki／Retrieval，包含權限、更新、撤回及 breaking-upgrade rebuild／publication 演練；不接管既有正式資料／流量。真實上游 application 接入另設交付階段，沿用同一份目標契約。手動操作不預選 GUI／CLI 或特定 client。 | [Q2](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6103968793)、[Q20](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106234277) |
| 研究主題 | AI agent 自我演進能力（self-evolution），包含 skill／memory 等面向。這是論文研究主題，不是平台須實作的 agent 能力。 | [Q3](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6103968793) |
| 代表性問題 | 不同 AI agent 方法如何透過 skill／memory 的改變，改善後續任務表現？它們的觸發條件、改變內容與成效驗證有何差異？Wiki 做跨論文比較；Retrieval 核對原文與實驗依據。論文未交代的部分標示未知。 | [Q4](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104011374) |
| 初批集合 | 收集目標 20 篇代表性論文，以有文字層的 PDF 為主。必要圖表、公式依研究用途判斷；需檢查實際文件後確認方法與支援範圍。20 篇不代表容量上限、正式工作量或資格驗證已完成。 | [Q5](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104011374) |

Q4 是驗收案例的輸入，不新增 Canonical reusable fact schema，也不要求重現論文實驗。各 projection 的品質、產品語意與發布驗證由其 decision owner 承接。

## 目標、待查輸入與能力證據

| 項目 | 已選定目標／已知限制 | 仍缺的輸入或證據 | 決策／查證責任 |
|---|---|---|---|
| 文件集合與特性 | 20 篇起點、兩週採用期間，最多 50 篇有效論文，文字層 PDF 為主；50 是本階段容量範圍，不是必須補滿的目標或平台永久上限。[Q12](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104972386) | 實際清單、來源／使用授權、頁數／檔案大小、必要圖表／公式與處理特性均尚未盤點 | 本票確定採用範圍；agent 查證可取得的清單／檔案；資料與政策責任人待指定 |
| 到件與更新 | 按需提交；日常每週 1–2 批、每批最多 5 篇新增／更新。[Q6](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104219412)。尖峰以任意 10 分鐘最多 5 篇、任意 24 小時最多 10 篇一般新增／更新評估；初批 20 篇與全量重建另計。[Q14](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6105003701)。這些不是 admission 硬性限額或已觀測速率 | 實際文件 bytes、request／重試與既有 backlog；50 篇容量範圍不自動提高到件速率。不可用每週平均量推定 outage／排隊容量 | 本票選目標；admission／processing／projection 分別承接 |
| 更新與初批時效 | 依賴服務正常可用、文件與負載位於約定範圍內時，日常最多 5 篇新增／更新，每篇自完整上傳並由 API 持久受理起，10 分鐘內完成 Canonical Acceptance 及 Retrieval 更新發布而可搜尋，包含排隊時間。初批 20 篇於整批完整上傳並受理後 1 小時內全部可搜尋，已就緒文件儘早可用。Wiki 保留獨立背景更新的 24 小時目標；撤回／撤權仍走緊急治理路徑。[Q8](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104655502)、[Q10](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104877792) 細化並取代 Q7 對一般 Retrieval 更新僅設 24 小時期限的要求 | 實際文件與資源適用邊界；須在 Q14 尖峰到件條件下驗證。故障恢復另依 Q22，不與正常更新期限混用。API 受理回應延遲另計 | 本票選目標；processing／projection／admission 定義相應語意與機制 |
| 全量重建 | 依賴正常、文件及負載在約定範圍內時，最多 50 篇全量重建自工作受理起，Retrieval 8 小時、Wiki 24 小時內各自完成更新發布；日常檢索與更新仍優先。[Q15](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6105003701) | 實際方法／資料、資源及與日常負載共存的端到端證據；不是可容忍停機時間或故障復原期限 | 本票選目標；processing／projection owners 定重建與發布驗證 |
| 多人服務與擴充 | Serving 須支援多人併發、stateless 實例替換與水平擴充；正確性不能依賴某實例唯一持有的記憶體／本機磁碟狀態，必要權威資料與進度須持久保存。身分／授權須依 request 隔離；ingestion／parser 併發與 query 併發分開評估。[Q9](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104655502) | 代表性請求及可用性／資源預算；須驗證單實例多請求、多實例、授權隔離及實例替換。未選定 replicas、HPA 或服務拆分 | 本票選 operating 目標；projection／serving／governance／infra owners 承接契約、機制與驗證 |
| 檢索負載與回應 | 整體部署以 10 個同時進行的檢索請求為驗證負載，95% 請求於 3 秒內回傳結果（p95 ≤ 3 秒），包含權限檢查與檢索處理；LLM 長答案生成另計。不是帳號／使用者上限或每個實例的容量承諾。[Q11](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104877792) | 涵蓋最多 50 篇的代表性 query／回傳範圍、持續時間／樣本與錯誤觀測，以及文件處理共存下的資源影響；無端到端能力證據 | 本票選 workload／latency 目標；projection／serving owners 定測試語意與實作驗證 |
| 容量與資源 | 20 篇起點，兩週最多 50 篇有效論文；日常檢索與新增／更新優先於背景全量重建。[Q12／Q13](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104972386)。後續設計先提出達標的最小配置與成本，由平台營運／資源窗口確認可承擔範圍；成本不合適時明確修訂資源、工作量或時效目標。[Q21](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106176641) | 實際文件／歷史版本／衍生資料用量、可用資源、配置／成本／預算、具名窗口、排隊／接收上限與共存驗證均未完成；既有 PDF 配置不是平台預算，未授權無上限支出 | 本票選 operating 目標；processing／projection／custody／admission owners 提出方案，平台營運／資源窗口確認可承擔範圍 |
| Admission 恢復與查詢 | 既有要求：保護已受理工作度過有界 24 小時 Temporal outage 與單一 admission storage node failure；request record 保留至 terminal 後 30 天。Pilot 可暫停新受理；必要依賴恢復並持續可用起，1 小時內恢復正常受理與啟動處理，一般增量積欠於同一時點起 Retrieval 2 小時／Wiki 24 小時內完成；初批／全量重建分開驗證。正式版須有有界、耐久的工作緩衝，於來源 custody、授權、admission persistence 可用且容量足夠時，可先受理等待處理。[Q22](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106292316) | 總排隊／儲存仍須計入既有 backlog、初批／重建、request／重試與實際 bytes，不能把 Q14 的 24 小時一般到件最多 10 篇當作總容量；實際接收上限、啟動速率與端到端恢復證據未定。正式採用前另定實際負載與故障範圍，不把 pilot 目標推為 production 保證 | 本票定 workload／operating 條件；admission owner 定接收／排程／重試／status，custody owner 配合持久保護；processing／projection owners 提供吞吐證據 |
| 故障資料保護 | 必驗證程序／Pod 重啟與單一節點故障：已持久受理的工作、已接受的權威資料與必要治理紀錄不得遺失。衍生資料僅在合格 inputs／methods／configuration 可取得時才視為可重建；不可重建的唯一資料另須保護。[Q16](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6105897968) | Q22 接收／恢復方案、營運安排、具體故障拓樸及 restore 證據；不宣稱整個機房／區域毀損亦零損失 | 本票選故障／損失目標；admission／governance／custody／projection owners 定機制與驗證 |
| 線上讀取復原 | Q16 的程序／Pod 重啟及單一節點故障範圍內，自故障導致線上讀取不可用起，3 小時內恢復對既有合格資料的授權讀取；須符合目前授權／撤回，不能只以服務啟動成功計為完成。[Q18](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106106166) | 具體復原方案與端到端故障驗證；不以 Q15 的 8／24 小時背景全量重建目標替代，也未新增整個機房／區域災難承諾 | 本票選復原需求；projection／serving／governance／custody owners 與平台營運窗口承接 |
| 資料保留 | 在來源授權允許且不抵觸適用撤回／刪除要求下，來源／證據、Canonical 與必要版本／發布紀錄至少保留至試用結束後 90 天；到期前由資料責任人決定續留、轉正式服務或清理。Request record 仍為 terminal 後 30 天；可重建衍生資料不一律套同一期限。[Q17](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6105897968) | 實際來源條件、具名資料責任人、各類衍生資料及引用相依性的保留／清理安排；不能因 request TTL 或 Temporal history 到期而刪除 accepted dependencies | 本票選保留目標；governance／custody owners 定具體執行 |
| 正式服務共存 | 第一階段手動上傳、獨立 pilot 資料範圍；無接管既有正式資料／流量、資料遷移／切換或舊 client 相容性義務。正式 application 接入留在後續階段，完整權限／生命週期要求持續適用。[Q20](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106234277) | 是否共用基礎設施及其資源／資料／權限隔離的配置證據；後續正式 application 的接入條件與時程另定，不是本階段驗收前提 | 本票已回答 pilot coexistence 範圍；source／admission／projection／serving owners 承接契約與後續交付 |
| 責任窗口與授權 | 已確認採用／資料、平台營運／資源、Wiki／Retrieval 三類窗口，允許兼任。[Q19](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6105931730)。Source Owner、授權提交者、來源政策權威等契約角色仍保持分離，窗口不自動取得來源權限 | 具名窗口或其指定人、實際授權綁定仍未提供；不能把 issue 認領者當作已指定全部責任人 | 使用者指定人選；各窗口依下列分工承接；agent 查證已提供的設定／證據 |

初批 20 篇整批可搜尋目標為 1 小時；最多 50 篇全量重建則自受理起，Retrieval 8 小時、Wiki 24 小時內各自發布，兩個期限不串接相加。背景重建目標不代表可容忍停機時間、RTO 或 RPO；正常依賴下的日常 10 分鐘目標也不代表 Temporal outage 期間可照常完成 ingestion。已就緒文件應儘早可用。具體 publication unit、觸發方式及 coverage 表示由 projection 決策承接，不能以尚未完整接受的 Canonical candidate 縮短時效，也不能暗示未就緒／失敗文件已完整覆蓋。先前 48 小時整批完成、5 位使用者／2 個同時操作的建議未採納。

兩週是採用規劃期間，不是資料自動到期刪除時間；Q17 的 90 天從試用結束計起，也不構成永久保存授權。50 篇有效論文不涵蓋歷史版本、來源／證據與衍生產物的總儲存量。先前 13 週／150 篇建議未採納。

Q16 的資料保護與 Q17 的保留要求不自行選定備份／複寫／儲存機制；仍需 restore 驗證。還原舊備份時，必須核對可信的目前授權與撤回狀態後才恢復披露，不能以舊備份中的 allow 狀態代替現行政策。

數值或方案被選定只代表設計目標。實際文件特性、量測與完成驗證須另記，不能由既有測試 fixtures 推定本次 pilot 已取得資格。本 session 不進行 live load tests 或基礎設施變更。

[Q18](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106106166) 已確認線上讀取復原目標為 3 小時，從不可用起計，不從人工開始處理時計；先前 4 小時提案未採納。後續方案須證明可在期限內恢復讀取，不能只以一條允許耗時 8／24 小時的全量重建路徑作為足夠復原證據。Admission 接收／恢復與積欠補完另依 Q22，不能取代此處的線上讀取復原期限。先前週一至週五 09:00–18:00 人工支援提案維持撤回，不預設詳細值班排程。

[Q20](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106234277) 已確認手動上傳的獨立 pilot；手動提交仍須經 ingestion 契約，不直接寫入／覆寫 Canonical。獨立採用範圍不等於身份驗證或授權豁免，也不表示須另建完整基礎設施。提交授權與 reader policy 分開，檢索／讀取及受保護的結果、引用、附件等披露仍依目前有效權限；Canonical Acceptance 不給永久讀取權。若採 agent 代使用者操作，仍須保留可信委派，不能借背景 workload 權限越權；本輪不新增 agent consumer 必交付能力。Q9、Q11、Q18 的授權驗證要求保持不變，詳細 serving／governance 機制仍留在其決策票。[Q20 澄清](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106176641)

### 背景 ingestion 與線上讀取

[Q13](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104972386) 確認兩條路徑解耦：一般文件受理後的 ingestion、處理、Canonical Acceptance 及 projection materialization／publication 在背景非同步執行；online retrieval／fetch 讀取符合目前授權與相應就緒／發布契約的資料，不在讀取請求內同步等待 ingestion 或全量重建。Offline 不表示只在夜間或人工觸發；日常更新時效仍適用，query-time retrieval 計算仍可在線上執行。撤回／撤權不等背景重建完成才生效。

資源競爭時優先維持日常檢索與新增／更新目標；背景全量重建依 Q15 的 Retrieval 8 小時／Wiki 24 小時目標評估。重建期間可沿用的既有內容仍須符合目前授權與可用性契約，不能繼續披露已撤回或不合格資料。須驗證兩條路徑共存的時效與授權隔離；邏輯解耦不證明共享 CPU／儲存／DB／模型的資源或故障隔離，也不預選兩個微服務、獨立 DB 或新 queue。

Fetch 是線上讀取的工作類型；Canonical 對 agent／application 直接開放 by-ID 讀取的候選契約仍由 Serving 決策處置。Q11 檢索目標不自動套用至任意大小檔案下載。

### Pilot 與正式版的依賴故障處理

[Q22](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6106292316) 允許 pilot 在背景必要依賴故障時暫停新受理並明確告知稍後重試。已持久受理工作仍須保護，依賴恢復後合格工作自動續跑，不能要求使用者因背景故障重新上傳，也不能恢復已撤回／不合格工作的資格。恢復受理／啟動處理 1 小時、一般增量 Retrieval 2 小時及 Wiki 24 小時，皆從必要依賴恢復並持續可用的同一時點計算，不相加；文件／負載須在約定範圍內，初批與全量重建另行驗證。

正式版須讓上傳工作的耐久受理與 Temporal／worker／模型等處理端可用性解耦：來源可安全留存、授權與 admission persistence 可用且容量足夠時，處理端中斷不應迫使一律拒收。必要接收基礎失效或容量達限時，仍須保護既有工作並明確拒收新工作。Queue 表示有界、耐久、可追蹤／排程／恢復的行為，不預選 broker 或新微服務；既有耐久 request records 加 dispatch／reconciliation 若能滿足要求即可。單純 upload complete 或 process 記憶體中的 task 不構成 durable acceptance。正式版的實際來源、負載／bytes、容量及故障保護範圍須另估算與驗證。

### 適用階段與後續修訂

本票數值為 first-adoption 的設計／驗收基準，可於 production 階段依實際來源、規模、流量、服務需要與資源預算修訂。修訂須註明適用階段、取代哪些假設／目標及受影響的設計與驗證，保留決策歷史並補上相應量測；本輪數值不是永久產品上限或 production SLO。[Q10／Q11 與適用範圍澄清](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6104877792)

容量／延遲調整不自動取消已確認的 Canonical 完整接受／不可變性、來源追溯、授權隔離或撤回要求。共同契約如需改變，仍須由其決策 owner 明確處理相容性與遷移；正式版耐久工作緩衝已由 Q22 明確要求納入設計；其餘未知 production 規模不構成預建額外機制的理由。

### 可重用的既有量測及其限制

[PDF qualification 的 supported configuration](../../tests/pdf_processing/t09b/SUPPORTED-CONFIGURATION.md) 只涵蓋四個固定 fixtures 與其受控序列；採單一 parser slot、serialized business work，worker 配置為 4 CPU／5 GiB hard limit。這不是整個平台的資源選擇，也未資格化 two-child throughput；拒收上限不代表其範圍內任意 PDF 均通過資格。

現有處理時間不提供 production-capacity／SLA 主張。[PDF-core handoff](../../deploy/pdf-processing/HANDOFF.md) 明確區分 processing completion 與 Canonical acceptance；該份資格證據不包含本次 20 篇論文的 Canonical／Wiki／Retrieval 端到端完成時間。Q8–Q11 的日常 5 篇每篇 10 分鐘／初批 20 篇整批 1 小時可搜尋、Wiki 24 小時、多人服務與 10 個同時檢索請求之 p95 ≤ 3 秒目標，仍需依實際文件、方法與 projection／serving 方案評估驗證。Q14 的尖峰負載與 Q15 的全量重建／日常工作共存亦未量測。單一 parser slot 的已量測範圍不能推論為 query 單用戶限制或 query capacity 證明。

## 邊界與交付責任

[Q19](https://github.com/davidlinnnn/data-ingestion/issues/54#issuecomment-6105931730) 確認以下最少必要窗口，可由同一人兼任，具名人員仍待指定。

| 採用責任窗口 | 職責 |
|---|---|
| 採用／資料 | 論文清單、來源使用條件、研究驗收及保留到期處置 |
| 平台營運／資源 | 基礎設施、資源預算、故障與復原 |
| Wiki／Retrieval | 各 projection 的交付、品質及服務驗證 |

這些窗口不新增組織或人力要求，也不替代 Source Owner／來源政策權威等契約角色。設計決策的責任仍如下：

- [Source handoff](knowledge-platform-source-handoff.md)、[Canonical contract](knowledge-platform-canonical-contract-draft.md) 與 [logical design](knowledge-platform-logical-design.md) 的已確認語意繼續適用。API client 提出授權的生命週期操作，不可直接覆寫已接受 Canonical；移出 Corpus、停止披露與實體清除保持不同意義。
- [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31) 承接 Q22 的 pilot 恢復與正式版耐久工作緩衝需求，定義接收邊界、容量、排程／重試、status 與恢復啟動率；此處不選定 queue／DB 或解決該設計票。
- [Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72) 接收本票的必要內容／workload／operating 目標，負責方法取捨及相應品質／資源／延遲證據。研究候選不是必做功能。
- [Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55) 接收代表問題與同一批 Canonical 輸入，負責產品品質、更新、重建及獨立發布。
- [Define the Knowledge Serving contract and agent access](https://github.com/davidlinnnn/data-ingestion/issues/76) 承接共同 consumer 契約與 access/adaptation 決策。不同團隊實作的 projections 仍需共同治理保證；MCP／plugin 是討論候選。Agent／application 直接依 ID 讀 Canonical 仍待該票處置，未列為本階段必交付能力；見[需求澄清](https://github.com/davidlinnnn/data-ingestion/issues/76#issuecomment-6100536754)。
- [Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56) 負責授權／委派、撤回與跨介面 enforcement；[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57) 承接 custody／retention／restore 機制與最終跨界檢查。

Q1–Q22、下列有界驗證矩陣及缺證交接已經使用者最終確認。Pilot coexistence 由 Q20 處置；operational revisit 由下列既有設計 owners 繼續承接。只完成本票的 workload／operating 決策，其他設計與 Map 最終跨界整合檢查依既有責任繼續。

## 最小驗證矩陣

以下驗證方法已由使用者確認；「通過條件」指日後應如何評估，全部尚未執行。各 owner 的設計票見上節。每個場景須保留實際固定文件／版本、方法／profile／模型／程式版本、部署與資源設定、工作量、事件時間及 outcome；避免拿不同配置的局部結果拼成端到端通過。

| 場景 | 觀察 | 通過條件／待補條件 | Owner／handoff |
|---|---|---|---|
| **V01 初批 20 篇手動匯入與研究使用**：獨立、明確授權的論文集合；同批 Canonical 供 Wiki／Retrieval 使用 | 完整 capture、durable admission、processing、Canonical Acceptance、各 projection 發布時間與 IDs；Q4 的觸發條件／skill-memory 改變／成效證據比較及原文引用 | 初批在整批完整上傳並持久受理後 **1 小時內全部可搜尋**，已就緒文件儘早可用；Wiki 依獨立 **24 小時**目標。只能使用完整接受且目前合格的 Canonical；研究比較有實際來源支持，未交代者標未知。具體研究 oracle／品質標準由採用窗口與 projection owner 補定，不虛構分數門檻；不要求重現論文實驗 | 採用／資料窗口提供集合與來源核對；admission/status owner 負責受理；processing owner 負責處理；projection owner 負責品質／發布 |
| **V02 日常新增／更新、重送與必要失敗路徑**：任意 10 分鐘最多 5 篇、24 小時最多 10 篇；含來源更新與 method-only 重處理的適用案例 | 每篇排隊至 accepted／Retrieval published 的完整時程；Source Revision／Canonical Revision／method 關聯；重送、缺必要輸入、單篇失敗及受影響 coverage | 依賴正常且在約定文件／負載範圍內，一般新增／更新每篇自持久受理起 **10 分鐘內可搜尋**（含排隊），Wiki **24 小時**；失敗不冒報完成、不破壞其他獨立成功 outcome；固定舊引用不改指新版，method-only 不冒稱來源變新。預設完整輸入／partial coverage／publication unit 依 projection owner 選定契約驗證；不得將尚未接受的 partial candidate 提早發布。全量 method rebuild 依 V04，不把 10 分鐘套至任意重跑 | admission/status owner request／重送／status；processing owner 負責處理；projection owner update／coverage；依已確認 Canonical 契約 |
| **V03 多人檢索、stateless 與替換**：最多 50 篇範圍，整體部署 10 個同時檢索；涵蓋單實例多請求、多實例及實例替換 | 端到端 latency、errors、授權結果、版本／可用性資訊；request 是否依賴特定實例記憶體／本機狀態；觀察與 V04 共存時影響 | 檢索 **p95 ≤ 3 秒**，包含授權檢查及檢索，LLM 長答案／任意大小下載另計；request 間不串用身分／授權；實例替換不遺失必要權威狀態／進度，正常讀取不等待 ingestion。query set、結果大小、樣本／持續時間及錯誤觀察由 projection／serving owners 補定；若未設定／未量測，不宣稱達標或用快速失敗當成功 | projection owner retrieval；serving owner serving；governance owner request 授權；平台營運／資源窗口承接部署與觀測 |
| **V04 全量重建與 breaking-upgrade rehearsal**：最多 50 篇，與 Q14 日常新增／更新及 V03 檢索共存 | 實際輸入快照、方法／產品版本、各自發布時程、日常 latency、資源／成本；新舊版本切換／失敗／晚到結果及 release 記錄 | 自重建受理起 **Retrieval 8 小時、Wiki 24 小時**各自完成，不串接相加／不設跨 projection barrier；日常檢索／更新目標仍適用。相容且授權的舊發布可服務；新候選須經品質／治理驗證。演練重大 breaking migration 的可歸責 release 判定與受控切換；不執行真實 PROD 接管，不假設任意 rollback 可行 | projection owner publication／migration；processing owner 方法／重用；serving owner reader 相容性；governance／custody owners 治理／custody；營運窗口資源共存 |
| **V05 Pilot 背景依賴故障、Temporal outage 與積欠恢復**：保留既有有界 24 小時 Temporal outage 設計要求；pilot 在故障時可暫停新受理，已受理 backlog、Q14 到件嘗試、初批／重建分別記錄 | 已持久受理 requests 的耐久性、可查 status、dispatch/reconciliation、重送與重啟結果；新提交明確未受理／稍後再試的回應；必要依賴恢復並持續可用時點，以及正常受理、處理啟動、Canonical Acceptance、各 projection 發布時間；backlog／bytes 與目前資格 | 已持久受理工作不遺失、不偽報完成，不要求使用者因背景依賴故障重新上傳；仍合格者自動續跑，撤回／不合格者不得恢復資格，不重複產生衝突效果。自必要依賴恢復並持續可用的**同一時點**起，**1 小時內恢復正常受理與啟動處理；一般增量積欠 2 小時內可搜尋、Wiki 24 小時內完成更新**，1／2／24 小時不相加。一般增量限約定文件／負載，初批與全量重建分開驗證，不推及任意 backlog；正常 10 分鐘目標不套用 outage。這不代替 V06 從讀取不可用起算的 3 小時復原。正式版耐久緩衝及其未來驗證依下方分期要求，不能以 pilot 暫停受理省略 | admission/status owner admission／dispatch 與有界驗證主責；custody owner 來源／工作紀錄 custody；processing／projection owners 提供實際吞吐／恢復證據；governance owner 資格；平台營運窗口提供依賴／故障界定及環境 |
| **V06 指定故障與線上讀取復原**：程序／Pod restart、單一節點故障；涵蓋 retained data 與授權／撤回狀態復原 | 故障前後 accepted work、權威／唯一資料、治理記錄與必要依賴的完整性；從線上不可用至真實授權讀取恢復的時間；目前政策比對 | 指定範圍內已持久受理工作、已接受權威資料與必要治理記錄**不得遺失**；唯一不可重建資料亦受保護。從故障造成讀取不可用起 **3 小時內**恢復既有合格資料的授權讀取；health check 成功不足。舊 backup allow 不替代目前授權；無可信資格則 fail-closed。衍生資料可重建前提是合格 inputs／methods／configuration 可得；8／24 小時背景重建不是 3 小時復原證據 | custody owner restore／custody；governance owner 目前治理；admission/status owner accepted work；projection／serving owners publication／serving；平台營運窗口 |
| **V07 存取隔離、撤權／撤回與晚到成果**：手動上傳與閱讀權限分開；使用受控允許／拒絕／授權不可驗證案例；撤回與處理／發布競爭 | Admission/read／evidence/status 的授權結果；policy／withdrawal receipt、applied、enforced 三類事實；late result、cache／replica 或 restore 是否重新披露 | 未授權者不能取得受保護 content、existence、citation／artifact 或 status；背景權限不擴大使用者權限；Canonical Acceptance 不給永久 grant。撤回不等普通重建，晚到成功不恢復資格；收到請求不冒稱全邊界 enforced。具體 enforcement 邊界、時效及證據由 governance owner 確定，未定／未測保持明示；如 serving owner 未採外部 agent，本場景不新增 agent consumer 必交付能力 | governance owner 主責；admission/status owner exposure；projection／serving owners serving；custody owner dependent copies；資料／政策窗口供權威依據 |
| **V08 保留、到期處置與相依清理**：request／captured source／adopted evidence／Canonical／publication 各類資料分開；含 checkpoint cleanup、到期與適用 purge | 保留規則與起算事件、相依引用、清理前後可讀性、到期處置授權及 purge 完成證據；日後可以受控時間案例驗證，不要求本 session 等 90 天 | 來源許可且無優先撤回／刪除義務時，來源／證據、Canonical、必要版本／發布記錄至少到**試用結束後 90 天**；到期前資料責任人決定續留／轉正式／清理；request 仍 terminal＋30 天。Task／checkpoint cleanup 不破壞仍需保護依賴；可重建衍生資料不強制同一期限但須滿足復原目標；withdrawal ≠ physical purge，purge 後不能承諾重建／披露 | governance／custody owners 保留／purge；admission/status owner request TTL；processing owner 中間產物；projection owner publication；採用／資料窗口做期限處置 |

**V05 的正式版分期要求：**admission/status owner 現在就須將有界、耐久的 upload／ingestion task 緩衝與管理能力納入設計；custody owner 配合來源／工作紀錄 custody。來源可安全留存、授權／admission persistence 可用且容量足夠時，Temporal／worker／模型等處理端故障不應使正式版一律拒絕新工作；可先耐久受理，再排程、追蹤及續跑。這不承諾 storage／授權失效或容量耗盡時無條件接單，也不預選獨立 broker／queue 產品。既有 durable request records 與 dispatch/reconciliation 若能滿足需求，可由方案與驗證證明；記憶體暫存或 upload complete 不等於 accepted。**正式採用前**須依實際來源、流量／bytes、容量與故障保護範圍，按 Q21 估算／驗證並明確修訂正式數值目標；processing／projection owners 提供吞吐／恢復證據。此為已確認的正式版需求及後續驗證 gate，不是本 session 或 pilot 已量測通過的能力。

## 尚缺輸入、owner 與交付門檻

下表是缺證／輸入 handoff，不表示已補齊。Q19 只確認角色，可兼任；具名窗口或有權指定的責任人仍待落實。若估算／實測無法達標，回到本票的優先與目標修訂，不得由下游自行降規。

| 尚缺輸入 | Owner／取得方式 | 最晚何時補齊 | 阻擋的後續工作 |
|---|---|---|---|
| 實際 20 篇論文清單、可用的固定檔案／版本、未來至 50 篇的代表性取樣 | 採用／資料窗口決定代表性；agent 查證／盤點已授權資料 | processing owner 選方法與 projection owner 固定驗收案例前；需要實際下載／提交前先確認授權 | 真實品質／圖表公式需求、方法可行性、文件級 latency 與完整端到端 qualification；不能用舊 fixtures 代替 |
| 來源使用條件、reader policy／authority、上傳與生命週期委派、受控 allow/deny 身分與範圍 | 採用／資料窗口協調 Source Owner／policy authority；已確認 source handoff 的語意，governance owner 執行契約；agent 查已有授權證據 | 正常 ingestion admission／真實讀取之前；governance owner 具體設計前提供代表性政策 | 合法持有／保留、真實提交與分享、V07/V08；公開可下載不自動等於無限制使用 |
| 每份 bytes／頁數、文字層、必要圖表／公式、依賴、更新特性；歷史版本與衍生資料用量估算 | agent 在可取得文件上量測盤點；processing owner 分析 processing 特性；admission／custody owners 估 queue／storage | processing owner 能力與資源方案、admission/status owner admission 上限、custody owner retention/restore sizing 定案前 | 文件支援範圍、排隊容量、資源／成本估算；50 篇不是全部歷史／artifacts 的 storage cap |
| 既有基礎設施可用資源、storage／Temporal 限制、模型與依賴可用性、權限；達標最小配置與成本 | 平台營運／資源窗口提供已知環境；agent 做經授權唯讀查證；admission／processing／projection／serving／custody owners 組合方案估算 | 物理方案／profile 最終選定及任何支出／部署前；pilot 啟動前確認實際可用配置 | 方案可行性、資源與成本接受、可靠性／延遲完整主張；Q21 不是無上限預算授權；K8s／shared Temporal 設計方向不證明資源已可用 |
| 具名採用／資料、平台營運／資源、Wiki／Retrieval 窗口（或具權威的指定人） | 使用者／組織指定，可兼任 | Pilot 啟動前完成；若相關資料／成本／驗收決策更早發生，須在該決策前指定相應窗口及授權 | 選文件／政策、接受配置成本、研究驗收、故障責任、90 天到期處置；issue 認領不能代替全部職責 |
| 代表性 query、來源核對 oracle、回傳大小、latency 觀察期間／樣本、error 記錄；獨立 pilot 實作／驗收排程 | 採用／資料窗口與 projection／serving owners；平台營運窗口配合 | V01/V03/V04 的 qualification 開始前固定 | 「研究有用」與 p95≤3 秒的可解釋結果；不得用未知品質門檻或只計快速成功子集合宣告通過 |
| Pilot 實際既有 backlog／bytes、Q14 到件嘗試、初批／重建併存假設、request／retry 數量，以及恢復啟動率／容量證據；正式版另有實際來源／流量與故障保護範圍 | admission/status owner 整合有界 workload／排程容量；custody owner custody／storage sizing；processing／projection owners 提供處理與恢復吞吐；平台營運／資源窗口確認環境與成本，採用／資料窗口提供到件資料 | Pilot admission/status owner 容量／恢復方案定案及 V05 qualification 前固定；正式版資料與數值目標在正式採用前另行估算、驗證並明確修訂 | V05 可重現的容量與 1／2／24 小時驗證、既有 24 小時 Temporal outage 的有界設計；正式版耐久緩衝容量及保證。Q22 的 business 目標已確認，但未量測、未固定的 backlog 不可標為已支援 |

## Map mandatory revisit 的已確認處置

- Pilot coexistence：依 Q20 記錄為獨立資料範圍、無既有 PROD 接管／遷移／切換義務；正式 application 接入另階段處理。
- Operational/integration：容量、恢復與 task/status 交由 [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31)；Q22 正式版緩衝已留下[需求交接](https://github.com/davidlinnnn/data-ingestion/issues/31#issuecomment-6106329050)。
- 處理方法／吞吐與資源證據交由 [Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72)；更新／重建／升級發布與產品品質交由 [Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55)。
- 線上消費契約及授權讀取交由 [Define the Knowledge Serving contract and agent access](https://github.com/davidlinnnn/data-ingestion/issues/76)，授權／撤回 enforcement 交由 [Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56)。
- 保留／還原／相依資料 custody 及 Map 最終跨界整合檢查留在 [Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57)。
- 各 owner 依 V01–V08 保留各階段／發布／授權／故障／資源的必要觀測；本票不選 monitoring 產品，也不因本票完成而宣稱其他決策或 Map 完成。Map 僅保存處置摘要與本票結論連結。
