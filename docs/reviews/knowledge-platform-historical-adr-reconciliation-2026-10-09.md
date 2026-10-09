# Knowledge Platform 歷史 ADR 盤點

[Review 索引](README.md) · [Canonical 設計](../design/knowledge-platform-canonical-design.md)

**盤點／補記日：2026-10-09；範圍截至 Canonical Q25。**
依 [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32#historical-adr-reconciliation-checkpoint)
的強制 checkpoint，盤點已確認 overall logical design、source handoff、跨票修訂與本票決策。
三篇既有 ADR 保留原號；新 ADR 按本次建立順序接續，不按決策發生時間重排。
補記只記已確認取捨；不重開歷史票，也不把研究候選或已撤回提案升格成決策。

## 核對方法與結果

新增 ADR 的確認內容及原時間已向 GitHub 原始 comment 核對。
新增 ADR 引用的 overall Q4–Q6/Q16/Q17/Q20 確認於 **2026-09-26**，
不能以後來整體 baseline 的 2026-09-28 代替。
來源各輪日期依原紀錄保留；每篇補記另列 2026-10-09 為記錄日。
同一 comment 中明列 pending 的後續提案不納入 accepted 決定。

| 已確認決策群組／原始確認 | ADR 處置 | 理由與範圍 |
|---|---|---|
| 完整候選作為接受單位；[Canonical Q2/Q3](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6014492266)，2026-10-06 | 既有 [ADR-0001](../adr/0001-complete-candidate-canonical-acceptance.md) | 主文與必要附件共同決定可用性；組件可檢查、不可獨立接受。必要意思／允許限制沿用接受契約，不按每種欄位另立 ADR。 |
| Canonical 來源關係與 Projection 產品引用；[Q4](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6015964591)、[Q14 範圍修訂](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6038854471)、[Q16](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6039900827)，2026-10-06／07 | 既有 [ADR-0002](../adr/0002-canonical-source-relationships-and-projection-citations.md) | 已記來源／產品責任、概念 consumer 驗證及不強制通用可執行圖的取捨。 |
| 固定 accepted revision、規則式選用與歷史引用；[Q7/Q8](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035081526)、[Q9](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035318528)、[Q11](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035858969)、[Q15](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6039615616)，2026-10-07；[Q24](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6076049015)，2026-10-09 | 既有 [ADR-0003](../adr/0003-immutable-accepted-canonical-revisions.md)，本次補 Q24 | 同一接受重送不新增版本，不同候選不強制比對合併；沿用既有不可變／選用邊界，不另建去重 ADR。 |
| 完整固定 Capture Package 在 durable admission 前就緒；[來源 Q3](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124)、[Q6](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945)，2026-09-30；[Q9](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936)，2026-10-03 | 補記 [ADR-0004](../adr/0004-fixed-capture-custody-before-admission.md) | Admission／retry 邊界反轉成本高；排除 execution 時 fetch latest、無保護臨時輸入與部分 package。固定 inputs 必須跨 queue／suspension／retry 可取用。 |
| 採用依賴先受保護再接受；原始來源與 task/intermediate 不同生命週期；[overall Q20](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844054630)，2026-09-26；[來源 Q10](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014)，2026-10-02 | 併入 ADR-0004 | 不讓 processing 清理破壞 accepted evidence；adoption 不強制 copy，也非永久保留。Storage／TTL／purge 機制未定，不補成已選技術。 |
| Package-scoped attachment identity；[修正版來源 Q14](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5992838620)，2026-10-05；[Canonical Q20](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6074671955)，2026-10-09 | 補記 [ADR-0005](../adr/0005-package-scoped-attachment-identity.md) | 明確挑戰全域共享管理後採簡化；相同 bytes 不合併 authority／lifecycle，但不禁止實體重用。先前 shared-attachment 提案從未確認。 |
| Shared Corpus、explicit membership、固定 Materialization inputs；[overall Q4–Q6](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843489434)，2026-09-26 | 補記 [ADR-0006](../adr/0006-fixed-inputs-independent-projection-publication.md) | 共用 Asset 避免因新增 membership 複製／重 parse；固定當次輸入避免執行中暗換。Snapshot 不等於永久 access grant 或複製所有 bytes。 |
| Projection 擁有 serving／產品，獨立 coherent publication；[overall Q16](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843866759)、[Q17](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844008136)，2026-09-26 | 併入 ADR-0006 | 同一產品 index／pages 要一致；Wiki 不須等待 Retrieval。未定 universal gateway、發布 unit 或切換機制，不捏造效能理由。 |
| 分批獨立結果、預設完整產品輸入、membership removal 與 withdrawal 分離；[batch/completeness](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843539018)、[removal](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843568717) | 不另立；保留 logical checkpoint 與 ADR-0006 邊界 | 是獨立處理／發布的行為契約，不再拆一篇狀態或每種操作 ADR。Corpus deletion、missing-work trigger 等仍未定部分沒有被補記採納。 |
| 三種版本選用、standalone ingestion 與 governed reads／management roles；[selection](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843634273)、[standalone](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843694542)、[read](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843749474)、[roles](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843848093) | 不另立；ADR-0003/0006 加原 logical checkpoint | 保留 source-target／exact／eligible 選用與權限邊界；未選 snapshot resolver、API 或儲存機制，無須為介面清單新增 ADR。 |
| Layer-owned recovery、可恢復 change discovery 與使用者指定 Temporal；[overall Q18/Q19](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5843984257)，2026-09-26 | 不新增 Temporal ADR | 原 comment 已核對。方向仍有效，但未記錄 Temporal 替代方案／採擇比較；不為補 ADR 杜撰技術理由，也不把當時 pending Q17 混為已定。 |
| 獨立版本／相容性、工作類別預算；[overall Q21/Q22](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844054630)，2026-09-26 | 不另立；版本邊界沿用 ADR-0003 與 logical checkpoint | 方法變更和資料版本分開；容量／isolation／數值未選，不補成服務或 cluster 決策。該 comment 後段的 production Q23 當時仍 pending。 |
| Major breaking migration 的 authorized release；[overall Q23](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844072563)；復原與 first adoption；[Q24/Q25](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5844091825) | ADR-0003 已保留 release 邊界；其餘不另立 | 已確認自動準備／例行更新與 major release 的區別；未決 cutover／backup／numeric targets 不能補為既定架構。 |
| Source／Asset／Source Revision／request／digest 身分分離；[來源 Q1–Q3](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5909819124)、[Q4](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912631142)，2026-09-30；[Q11](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5968626647)，2026-10-03 | 不另立；CONTEXT／來源 checkpoint，ADR-0003/0005 保留相關取捨 | 保留身份意義與可靠排序要求。Identifier／dedup／排序技術未選；無已記錄的獨立技術比較可補，不能推導內容定址架構。 |
| Trusted policy、持續 validity、authority／evaluation／enforcement 與 acknowledgement 分離；[來源 Q5](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5912982133)、[Q8](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5953381014)、[Q12/Q13](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5991845520)，2026-09-30 至 2026-10-05 | 不另立；保留 source/logical checkpoint | 必要安全語意不自動構成方案比較。Q12/Q13 原 comment 已核對；沒有 GAM／engine／cache／同步 barrier 的已採納取捨，不杜撰。 |
| Direct upload common entry／按需其他 transport、受控工程團隊 pilot；[來源 Q6/Q7](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5911948945)、[Q9](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936)；[unified status amendment](https://github.com/davidlinnnn/data-ingestion/issues/31#issuecomment-5991846818) | 不另立 | Transport 可按需求擴充、pilot 可調整；status 是跨層既定需求，實體機制／phasing 未定。記 checkpoint／原決策即可。 |
| Canonical 最低契約、允許限制、Evidence 精度與 provider disposition；[Q1](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6013869858)、[Q3](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6014492266)、[Q5](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6016542202)、[Q6](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6018564062)，2026-10-06 | 不另立；ADR-0001 與契約 checkpoint | 是接受條件的具體內容；完整候選不等於無損、全用途或事實真實。無須各為 locator／欄位 disposition 建 ADR。 |
| Enrichment／附件更新／舊捕獲；[Q10](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035463278)、[Q12/Q13](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6036282074)，2026-10-07；changed support／撤回；[Q17](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6061378937)、[Q18](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6061678555)，2026-10-08 | 不另立；ADR-0001/0003 與具體案例 | 完整候選、不可變歷史與目前資格的運用；未採細粒度重算引擎、locator migration framework 或新撤回狀態機。 |
| 單一 schema／最少表示／案例／條件式能力；[Q19 撤回](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6062064816)，2026-10-08；[Q21](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075416972)、[Q22](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075543252)、[Q23](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075950574)，2026-10-09 | 不另立 | 具體契約、驗證與按需處置；多 exchange-format 提案已撤回，模型／套件／拓撲未採納。不得為它們建立 accepted ADR。 |

[Canonical Q25](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6076312345) 於 2026-10-09 確認版本內引用、三格式 locator 索引約定及必要未知結果區別。
這是 ADR-0002/0003 與 Q5 證據規則的具體化，未引入新身分、儲存或解析框架；無需新增獨立 ADR。

## 保留未決與歷史界線

- 本次新增 ADR-0004、0005、0006，並將已確認 Q24 補入既有 ADR-0003；沒有重新編號。
- 原 overall／source tickets 已解決；本次不改它們的決策、不新增原生依賴。
- 研究、spike 與設計案例不等於 runtime 資格證據；沒有因本次 ADR 補記新增功能或實作授權。
- 盤點與必要補記已完成到 Q25。最終 review 應連同本表呈現；若後續確認新決策或發現原紀錄衝突，先補核對再關閉本票。
- Canonical 正式契約／案例整體 review 及各結案條件仍獨立存在；本表不代表本票已解決或 map 可以先更新。
