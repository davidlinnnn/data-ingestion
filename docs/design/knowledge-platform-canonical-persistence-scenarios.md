# Canonical persistence：情境對照表

**Status:** design result of [#57](https://github.com/davidlinnnn/data-ingestion/issues/57)（2026-11-23）。這份文件不隨之後的決定修改，除非文中有加上日期的註記；決定以 [wayfinder map](https://github.com/davidlinnnn/data-ingestion/issues/52) 與它的票為準。

[Canonical persistence 設計結果](knowledge-platform-canonical-persistence.md)的附件，兩個部分：

1. 跨界檢查（#57 範圍 9）：地圖要求的八個情境，各自對到哪些決策、由誰負責、在哪裡驗證。
2. 情境目錄：2026-11-22 獨立審查列出的 153 個情境，逐列對照決策。

## 1. 跨界檢查

「處理完成」「Canonical Acceptance」「可以發布」「產物的 custody 交接」是四件不同的事，下表每一列都照這個區分檢查過：

- 處理完成：workflow 結束，request 是 `succeeded` 或 `failed`。
- Canonical Acceptance：平台資料庫一筆交易的 commit（B1）。成功的結果不一定形成接受（已刪除的文件、作廢的版本、沒有 candidate、candidate 的位置不對）。
- 可以發布：projection 依文件現況與自己的 Build 決定，回報 serving 事實（consumption 設計紀錄 §5）。平台不替它決定。
- custody 交接：和接受是同一個 commit；產物留在原地，那一刻沒有儲存操作（C 組）。

| 情境 | 前置狀態與固定的輸入 | 要有的結果，在哪裡看得到 | 決策與負責的票 | 目錄的列 | 驗證 |
|---|---|---|---|---|---|
| 初次交文件 | Source 已登錄 Resource；有採用中的版本 | request `succeeded`、Source Revision `accepted`、一筆 revision 紀錄、目前版本、一筆 `current_revision_changed`。文件狀態查詢與 `state` 讀取 | B1–B5、B7、B9。#251（已完成）、#81 | NS1–NS10 | `tests/admission/test_acceptance.py`；模擬；#83 的端到端 |
| 來源更新 | 已有被接受的 revision；Source 交新內容或重交 | 新的 Source Revision 與新的 revision；較舊的結果晚到不會蓋掉新的；同樣內容回 `unchanged` | B5、#258。#251、#96（已完成） | R1–R12、C1、C4–C6 | 同上；模擬的亂序案例 |
| 只換方法的重處理 | 宣告採用新版本並指定重刷範圍 | 範圍內的文件由平台重做，得到新的 revision；`current_revision_changed` 是 `background`；Source 的 Source Revision 不變 | B8、修正後的掃描規則。#261、#98 | U1–U13、C2、C3、P1–P5 | 模擬（採用、範圍、掃描的隨機交錯）；#137 在公司環境 |
| projection 獨立失敗與重建 | 某個 projection 的 Build 壞了或要重建 | Canonical 這一側沒有任何變化：接受不等 projection。重建時 projection 讀文件現況，再用確切的 revision 讀內容 | consumption 設計紀錄 §4、§5；C 組。#268（讀取）、#127、#260 | E1–E7 | #127 的端到端；#83 |
| 撤回後晚到的結果與清理 | pilot 沒有撤回（使用者 2026-11-18，[#56 的紀錄](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6982506436)），拿掉一份文件的做法是 Source 刪除它。所以這一列用兩種實際存在的情況檢查：文件被刪除、方法版本被作廢 | 晚到的成功結果不形成接受，也不讓文件復活；request 照實結束。物件留到文件的清除。之後加入撤回時用同一條規則 | B4、B6.3、D 組。#251、#98、#267 | D1–D10、W2、W3、W5、W6 | `test_acceptance.py`；模擬；#267 的驗收 |
| 破壞相容的升級演練 | 新的 Processing Profile 版本改了內容的 schema 版本 | 平台這一側是一次帶重刷範圍的採用；projection 開新的 Build（#55 的 D2、D3）。出問題時再採用舊版本並作廢新版本 | B6、B8。#261、#98、#81（schema 版本） | U10、W1–W18 | 演練是 first-adoption 的 V04，還沒執行 |
| 撤權後的還原 | 資料庫或物件儲存從備份還原 | 遺失區間的刪除重新套用之前，停下會把文件送出去的路徑（修復、讀取、bootstrap、會發事件的工作）；已清除的物件不會留在儲存裡；授權由目前的 authz 判定，不取自備份 | F 組；#78 的 C12、C26 | V1–V3 | #99 的還原演練；PROD 的排程化在 #269 |
| 狀態查詢的識別一路對得上 | 一個 request 從受理到被讀取 | `request_id` 就是 Temporal 的 workflow ID；`crv_` 加上 request id 的 32 個十六進位字元是 revision 的識別；revision 紀錄帶 `document_uid`、`source_revision_id`、`request_id` 與做出它的版本；內容物件的 key 帶 `document_uid` 與 revision 的識別 | B3、C 組。#251、#97（已完成） | NS2–NS4、X1 | `tests/admission/test_status.py`、`test_acceptance.py` |

## 2. 情境目錄

- 「決策」欄的編號見[設計結果](knowledge-platform-canonical-persistence.md)：N 是需求，A、B 是範圍 1、2 的裁決。
- 「狀態」是 2026-11-22 審查當時的判定。「缺口」與「矛盾」共 37 列，都由同一天的修正寫進各票（[紀錄](https://github.com/davidlinnnn/data-ingestion/issues/57#issuecomment-7080481738)的「修正，依票」）；「發現」欄是審查的發現編號。當時有十列的狀態帶著「待 C–G」（其中六列整列未定），已在 2026-11-23 補上處置。
- 「結果」欄寫的是審查當時依決策推得的行為，每一列都是；之後的修正（「缺口」「矛盾」的列，以及標成「交接」的列）以各票為準。

#### 1. 正常交件

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| NS1 | 第一次交件，每個項目都有結果，最後一筆回報到達 | B1 B2 B3 B5 | Source：request `succeeded`、Source Revision `accepted`。讀取端讀到新的目前版本。feed 一筆 `current_revision_changed`（`normal`） | 涵蓋 | |
| NS2 | 最後一筆回報遺失（平台 API 停超過回報的 60 秒預算） | B1 | workflow 結束後，reconciler（每 5 分鐘）讀 workflow 結果，跑同一個函式。接受最多晚約 5 分鐘；Source 期間看到 `processing` | 涵蓋 | |
| NS3 | 最後一筆回報與 reconciler 同時處理同一個 request | B1 N2 | 第二個發現 request 已結束，什麼都不做。一筆 revision、一筆事件 | 涵蓋 | |
| NS4 | 同一筆最後回報重送 | B1 N2 | 回 `200`，什麼都不變 | 涵蓋 | |
| NS5 | 回報不帶 candidate（#81 完成前每個真實的 workflow 都是這樣） | B2 | request `succeeded`、Source Revision `pending`，沒有 revision、沒有事件，計數。掃描把它當「沒有 Canonical Revision」重跑，沒有次數或間隔的限制 | 缺口 | M1 |
| NS6 | 輸了的 candidate（較舊的 Source Revision，或較低的採用序號） | B5 N10 | 記下 revision 與 `accepted`；目前版本不變；沒有事件。用確切識別讀得到，但讀取的端點還沒有票 | 涵蓋；讀取由 #268 | |
| NS7 | 沒有採用中的版本時交件（第一次確認點通過前，或取消採用後） | B8 #261 | 該項被拒 `UNSUPPORTED_FORMAT`，不建 Source Revision。Source 之後要再交 | 交接 | |
| NS8 | 滾動部署時，帶 candidate 欄位的回報送到還不認得它的 API，或反過來 | B2 | 回報模型不允許多餘欄位：回 `400`，回報不被收下；reconciler 以沒有 candidate 結案，形成不了接受 | 缺口 | L12 |
| NS9 | worker 寫了內容物件，受理的交易沒有 commit | B1 A2 | 沒有紀錄指向這個物件。它不是 Canonical 資料，隨文件的清除一起清掉 | 已定（D 組） | |
| NS10 | 讀取端取內容時，物件不見了或 digest 和紀錄不符 | N1 A2 | 紀錄是唯一的依據，帶著 digest。讀取端點不重算 digest，回應帶紀錄裡的 sha256 與大小；紀錄說有而物件讀不到時回 `503` 與專用的錯誤碼，並計數 | 已定（G 組，#268） | |

#### 2. 重送與新的 Source Revision

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| R1 | 同樣內容再交一次，最新的 Source Revision 已接受 | 規格 §6.4 | `unchanged` | 涵蓋 | |
| R2 | 同樣內容，較高的 `source_version` | #258 | 版本號寫到最新的 Source Revision 上；不重新處理，B5 的序號不動 | 涵蓋 | |
| R3 | 同樣內容，最新的因平台原因失敗、可重試 | 規格 §6.4、B7 | 新 request，`retry_of` 指向失敗的那次，計入額度。掃描可能先開；唯一索引保證只有一筆 | 涵蓋 | |
| R4 | 同樣內容，最新的失敗且不可重試（已登錄的內容失敗） | B7 | 現在：開新 request、立刻重用失敗、扣額度。紀錄寫回 `unchanged`；#98 列為「本票要決定的」 | 矛盾 | L1f |
| R5 | 同樣內容，最新的 Source Revision `pending` 且沒有進行中的 request（成功但沒有形成接受） | B4 B6.3 | `unchanged`：Source 開不了重跑，只有掃描能 | 交接 | |
| R6 | 舊的 Source Revision 還在處理時，新內容到了 | B5 | 兩個都跑。不論到達順序，新的 Source Revision 成為目前版本。一或兩筆事件 | 涵蓋 | |
| R7 | 新內容失敗（可重試），已有舊的 revision | B7 B9 | 舊 revision 繼續提供。Source 看到 `processing_failed`，屬平台。掃描照逐次拉長的間隔重跑，超過次數警示 | 交接 | |
| R8 | 新內容因 Source 的原因被拒（密碼、損壞） | 規格 §3 | Source Revision `rejected`，attention `source_revision_rejected`，舊 revision 繼續提供。掃描不重跑 | 涵蓋 | M13 |
| R9 | 內容退版：A、B、再 A | B6.1 | 第三個 Source Revision（`ordering: source_version` 時要更高的版本號）。登錄過的結果全部重用；新的 `crv_`；它最新，成為目前版本 | 涵蓋 | |
| R10 | 較低的版本，或版本相同但內容不同 | 規格 §6.3 | `STALE_SOURCE_VERSION`／`VERSION_CONFLICT`，什麼都不建 | 涵蓋 | |
| R11 | 前一個 Source Revision 的平台重刷進行中，Source 交了更新 | B5 | 重刷的結果記下但輸了，沒有事件 | 涵蓋 | |
| R12 | 因 profile 的上限被拒（例如超過 64 頁）；之後的版本放寬了上限 | #98 掃描、規格 §6.4 | 掃描：被拒的不重跑。Source 交同一個檔案：`unchanged`。除了刪除再交，沒有辦法；Source 不會被告知 | 缺口 | M13 |

#### 3. 並行與亂序的結果

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| C1 | 舊 Source Revision 的結果比新的晚到 | B5 | 記下，不成為目前版本，沒有事件 | 涵蓋 | |
| C2 | 同一個 Source Revision、不同採用序號的兩個結果 | B5 | 序號高的成為目前版本。兩者不會同時跑：每個 Source Revision 只有一筆進行中的 request | 涵蓋 | |
| C3 | 平手（同一個 Source Revision、同一個採用序號） | B5 ADR-0003 | 維持現有的，沒有事件 | 涵蓋 | |
| C4 | 重新派送後，舊 attempt 的回報 | #97 | `409`，不會觸發接受 | 涵蓋 | |
| C5 | 同一份文件的兩筆受理交易同時進行 | B5 N11 | PostgreSQL：先鎖 Document。MongoDB：兩筆都寫 Document 的版本欄位，一筆重試 | 交接 | |
| C6 | 受理交易和新增 Source Revision 的 finalize 同時進行 | B5 | 兩者都取 Document；序號在它之內給 | 交接 | |

#### 4. 刪除的競態

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| D1 | 成功結果到達前文件已刪除 | B4 | request `succeeded`、Source Revision `pending`，沒有 revision、沒有事件，計數與 log。讀現況：`deleted` | 涵蓋 | |
| D2 | 接受之後才刪除 | ADR-0014 | `document_deleted`（`narrowing`）；projection 在時限內清掉。revision 紀錄與物件留到清除 | 涵蓋；清除由 #267 | |
| D3 | 刪除和受理同時 commit | B4 N3 | PostgreSQL：在 Document 上序列化。MongoDB：受理一定寫 Document，所以會衝突。兩種順序都是 `deleted`，之後沒有接受 | 交接 | |
| D4 | 文件刪除時，它的 request 還在排隊（沒派送） | B4 #98 | #98 寫「不 dispatch」，但沒有結束狀態：request 永遠 `queued`，計入暫停的門檻 | 缺口 | H3 |
| D5 | 誤交的一整批被大量刪除 | B4 | 排隊中的：同 D4。跑到一半的：做完後丟棄，算力白花 | 交接 | H3 |
| D6 | 掃描正在為某文件開 request 時，文件被刪除 | B4 B8 | 可能為剛刪除的文件建了 request；它不會被派送（D4）或結果被丟棄。#98 沒寫掃描要先取 Document | 交接 | L7 |
| D7 | 刪除後用同一個 `document_id` 再交 | 規格 §8 | 新的 `document_uid`，什麼都不重用；舊 uid 晚到的結果被丟棄 | 涵蓋 | |
| D8 | 已刪除文件晚到的失敗結果 | B4 | request `failed`，其他不變 | 涵蓋 | |
| D9 | `applied` 30 天後：清除紀錄、revision、內容物件與 `requests/` 前綴 | N7 A2 | 以文件為單位清除：`documents/{document_uid}/` 與它每個 request 的 `requests/{request_id}/` 之下的物件全部刪除；文件、request、revision 的列留著，標成已清除 | 已定（D 組，#267） | |
| D10 | 跨 Source 的複本（#120）：目前版本屬於另一份文件 | N7 B3 B5 | pilot 不做。為它預留三條規則：物件的位置從 revision 紀錄解析；任何一份文件的目前版本都不會被保留期限清掉；「到期可以清除」的判斷只寫在一處 | 已定（G 組）；功能在 #120 | |

#### 5. 升版與重刷範圍

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| U1 | 升版，`refresh: none` | B8 | 新 request 用新版本。舊文件保留原本的 revision；`details` 顯示方法版本落後。失敗與沒形成接受的文件仍會重跑 | 涵蓋 | |
| U2 | 升版，`refresh: all` | B8 B5 N9 | 每份別的版本做的文件開一筆平台 request。成功就是新的目前版本，`background` 事件。照 N9 的規模，1000 萬份、每分鐘 50 份要約 139 天 | 交接 | |
| U3 | 升版，`refresh: {made_by: [...]}` | B8 | 同 U2，只限列出的版本。列了採用中的版本等於沒列，也沒有訊息 | 涵蓋 | |
| U4 | 第一次重刷還沒做完，第二次採用就來了 | B8 | 只看最新一次的範圍；之後的 `none` 會停掉之前 `all` 剩下的部分 | 涵蓋 | |
| U5 | 重刷失敗 | B8 B6.4 | 舊 revision 繼續提供；Source 看不到（`initiator: platform`）。#98 的表只對「沒有 Canonical Revision」的列寫了重試上限：照字面，失敗的重刷每次掃描都重開 | 缺口 | M12 |
| U6 | 舊版本之下建立的 request 在採用之後才結束 | B5 B8 | 照舊版本做的接受；範圍涵蓋時之後再重刷 | 涵蓋 | |
| U7 | 只改範圍：版本相同，`declaration` 加一 | B8 #261 | 新的採用紀錄，序號加一。副作用：每個不可重試的失敗都再重跑一次 | 涵蓋 | M3 |
| U8 | worker 還沒 current 就宣告採用 | B8 | 不套用；每次執行再試；等太久發警示 | 交接 | |
| U9 | 還有 request 指向的舊版本 build 被拿掉 | #178 規格 §3 | workflow 在沒有 worker 的 queue 上一直等，沒有錯誤；request 一直進行中，掃描無法取代它 | 缺口 | H2 M6 |
| U10 | 採用了 projection 還不支援的內容 schema | B8 #55 D3 | 採用時沒有檢查。第一次改 schema 時才開始有約束力 | 缺口 | L11 |
| U11 | 第二種 media type 以 `refresh: all` 採用 | B8 | 表寫「最新一次採用的範圍」，沒寫「這份文件的 media type 的」。照字面所有 PDF 都在範圍內。pilot 只有一種，碰不到 | 缺口 | L15 |
| U12 | 沒有採用中的版本時掃描執行（宣告取消之後） | B8 | 沒有版本可用來開 request；表沒寫這時什麼都不開 | 缺口 | L15 |
| U13 | 每次掃描掃過 1000 萬份文件 | B8 N9 | 讀 #251 放在 `document` 上的三個值：兩種資料庫都是一張表、一個索引的查詢 | 交接 | |

#### 6. 方法退版與作廢

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| W1 | 退版：再採用 N，`withdrawn: [N+1]` | B6.2 | 確認點通過後，一筆交易寫入採用紀錄與作廢項目。新 request 用 N。目前版本是 N+1 做的文件被重做；每次成功一筆 `normal` 事件 | 涵蓋 | |
| W2 | N+1 的結果在作廢之後才到 | B6.3 | 丟棄：request `succeeded`，沒有 revision、沒有事件，計數。掃描用 N 重跑 | 涵蓋 | |
| W3 | N+1 的結果和作廢在同一刻 commit | B6.3 | 可能被接受（兩筆交易沒有共同寫入的資料）。之後掃描的作廢規則會重做它。B6.3 在那一刻只是省工，不是保證 | 涵蓋 | L7 |
| W4 | 在 N+1 之下第一次交、作廢前已接受 | B6.2 | 由 N+1 的內容提供，直到重做成功 | 涵蓋（已知代價） | |
| W5 | 在 N+1 之下第一次交、作廢時還在跑 | B6.3 | 丟棄，然後重跑。期間 Source 看到 request `succeeded`、沒有內容、沒有 attention；B6 的紀錄寫的是「處理中」 | 缺口 | L6 |
| W6 | 作廢時 N+1 的 request 還在排隊或在跑 | B6.3 | 沒有規則：照樣派送、用有問題的版本跑完、被丟棄、再重跑。文件要等全部做完；N+1 的 worker 要留到它們跑完 | 缺口 | H2 |
| W7 | 退版的 PR 把 N+1 的 build 拿掉 | B6.2 #178 | W6 的 workflow 永遠等下去（U9）。promoter 發警示；解法是把設定放回去 | 缺口 | H2 |
| W8 | 重做失敗 | B6.4 | N+1 的 revision 繼續提供，計數、警示。可重試：照間隔上限一直重試。不可重試：每次採用一次 | 涵蓋；B6.4 已重新確認 | PQ1 |
| W9 | 目前版本是 N+1 做的、屬於較舊的 Source Revision；最新的 Source Revision 被拒或已放棄重跑 | B6.2、掃描的修正 | 紀錄與模擬：重做那個目前版本。#98 的表沒有這一列，寫的是目前版本「繼續提供」 | 矛盾 | H1 |
| W10 | 重做還沒做完，下一次採用宣告 `refresh: none` | B6.2 | 作廢規則不受範圍影響，繼續做 | 涵蓋 | |
| W11 | 宣告採用一個作廢的版本 | B6.2 #261 | 拒絕：exit 非 0、計數、什麼都不寫 | 涵蓋 | |
| W12 | 降版卻沒處理較高的版本 | B6.2 #261 | 同樣拒絕 | 涵蓋 | |
| W13 | 把錯的版本放進 `withdrawn` | #261 | 不能撤銷；它做的每份文件都被重做（事件 `normal`）；那個版本永遠不能再採用 | 缺口 | L10 |
| W14 | 退回一個 worker 已退役的版本 | B8 | 在確認點等，直到 build 回來且 current | 涵蓋 | |
| W15 | 模型服務中斷時退版 | B8 #261 | B7、B9 之下確認點的測試 workflow 過不了。能不能重用之前通過的結果，#261 還沒定。作廢跟著一起等 | 交接 | M10 |
| W16 | 作廢一個較舊的版本，但不降版 | B6.2 | 允許；它做的文件用採用中的版本重做 | 涵蓋 | |
| W17 | 不重新處理、指標退回前一個 revision（#55 D3） | B6.2 N5 | pilot 不做，PROD 上線前要做。N5 要求的查找沒有寫進 #251 | 涵蓋 | L16 |
| W18 | 營運怎麼知道退版做完了 | B6.2 | 沒有 metric 數「目前版本還是作廢版本做的」文件；PROD 不能查資料庫 | 缺口 | M7 |

#### 7. 同一版本內的 build 修補

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| P1 | 修補的 build 成為 current | #178 | 新 workflow 用它；跑到一半的留在舊 build。採用不變，不走確認點 | 涵蓋 | |
| P2 | 修補的 build 做出錯的已接受內容 | B8 | 範圍只能寫 profile 版本；revision 紀錄沒有 build。唯一的辦法是作廢整個版本、發新版本 | 缺口 | M2 |
| P3 | mapper 或 B7、B9 的規則在同一個 profile 版本內被改 | B2 | B2 規定改 mapper 就是新版本，但沒有東西強制：mapper 在 `finalize` 裡，CI 只約束 `methods/` | 缺口 | M2 |
| P4 | workflow 卡在壞掉的 build 上 | #178 | 固定在那個 build；要人用 `temporal` 終止。request 一直進行中，掃描無法取代 | 交接 | H2 |
| P5 | workflow 被終止 | B7 | reconciler 記 `WORKFLOW_ENDED_WITHOUT_RESULT`，可重試；掃描在那個版本的 current build 上重跑 | 涵蓋 | |

#### 8. 服務中斷

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| O1 | VLM 在 Activity 內的重試期間恢復 | — | 看不出任何事 | 涵蓋 | |
| O2 | VLM 中斷數分鐘到數小時 | B7 B9 | request 失敗、可重試。Source 看到 `failed` 與 `processing_failed`。掃描照逐次拉長的間隔重跑，不限次數，超過次數警示。恢復後只重問缺的項目 | 交接 | |
| O3 | 長時間中斷期間第一次交的文件 | B9 | 服務恢復前沒有內容；不會卡到下一次採用 | 交接 | |
| O4 | 摘要超過 900 秒 | B7 | 失敗、可重試。分段結果已登錄，每次重跑都往前推進 | 交接 | |
| O5 | d3 中斷，短或長 | B9 | 有公式、表格或圖片 OCR 的文件同 O2 | 涵蓋 | |
| O6 | d3 中斷好幾天 | B9 | 出口：不含 `d3-check` 的 profile 版本（PR、image、values、確認點、採用） | 涵蓋；出口有陷阱 | M9 |
| O7 | O6 之後 d3 恢復 | B8 | 採用含檢查的版本，`refresh: {made_by: [不含檢查的那版]}`。在那之前那些 revision 沒有 d3 的訊號 | 交接 | |
| O8 | 中斷期間的重跑撞上交件的暫停門檻 | B7 #96 | 沒有裁決：用 `normal` 會暫停所有 Source 的宣告；用 `low` 會排在所有新工作後面 | 交接 | L8 |
| O9 | 平台 API 停 | B1 | 回報放棄；reconciler 補上。交件回 `503` | 涵蓋 | |
| O10 | Temporal 停 | 規格 §9 | outbox 等著；reconciler 失敗；掃描仍會建 request | 涵蓋 | |
| O11 | 物件儲存停 | — | Activity 重試用完：`PLATFORM_ERROR`，可重試；掃描重跑 | 涵蓋 | |
| O12 | VLM 或 d3 的憑證錯誤或過期（401、403） | B7 | `INFERENCE_REQUEST_REJECTED`，不可重試。修好 secret 之後，掃描要到下一次採用才重跑 | 缺口 | M3 |

#### 9. 內容造成的失敗

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| CF1 | 模型拒答、回空、或兩次都不合格式 | B7 | 結果被登錄並重用；request `failed`，不可重試；每次採用重跑一次；出口是方法的新版本。舊 revision 繼續提供 | 涵蓋（已知代價） | |
| CF2 | `no_text`、`disputed`、`unverified` | B7 | 接受 | 涵蓋 | |
| CF3 | Source 的原因（密碼、損壞、頁數上限） | 規格 §3 | `rejected`；由 Source 修 | 涵蓋 | M13 |
| CF4 | mapping 驗證沒過 | B2 | `failed`，平台原因，不可重試；什麼都不寫 | 交接 | |
| CF5 | 一次不幸的回答在方法版本的整個生命期擋住文件 | B7 | 已說明的代價。要不要繼續登錄由 #81 決定，但 #81 的交接已把它歸成「已登錄所以不可重試」 | 交接 | L1e |
| CF6 | 某份文件觸發確定性的 bug（例外、逾時） | B9 | `PLATFORM_ERROR`，可重試：照間隔上限永遠重跑 | 缺口 | M4 |
| CF7 | pilot 失敗文件與原因的清單放在哪裡 | B7 | request 的 `error` 與回報的 log 都有，但沒有交接說哪個是正式紀錄、不進 pod 怎麼讀 | 缺口 | L13 |

#### 10. d3 沒有產出判斷

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| J1 | 回覆裡沒有分數（`SCHEMA_INVALID`） | B9 | 登錄；request `failed`，不可重試；出口是新的 `d3-check` 版本 | 涵蓋 | |
| J2 | 拒答或空回覆 | B9 | `not_run` 帶那個原因；在 #81 的分類裡同 J1 | 交接 | |
| J3 | 被檢查的項目本身是 `failed` 或 `no_text` | B7 B9 | 不檢查；`failed` 的項目照 B7 本來就讓 request 失敗 | 涵蓋 | |
| J4 | d3 給圖片 OCR 低分 | ADR-0011 | 只是弱訊號：項目仍是 `unverified`。但 #76、#127 被告知三類的 `unverified` 都代表「檢查過，沒發現問題」 | 矛盾 | L3 |

#### 11. 時間預算

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| T1 | enrichment 預算（240 秒）用完，還有項目沒送 | B7 | 那些項目 `SERVICE_UNAVAILABLE`；request 失敗、可重試；做完的已登錄，重跑會往前推進 | 交接 | |
| T2 | 需要好幾個預算才做得完的大文件 | B7 B9 | 掃描看起來像中斷：間隔每次拉長，警示也算它 | 缺口 | M4 |
| T3 | Activity 超時或心跳中斷，重試用完 | — | `PLATFORM_ERROR`，可重試；同 CF6 | 缺口 | M4 |
| T4 | request 再也不回報 | 規格 §7.2 | 文件上有 `progress_stalled`；沒有東西結束這個 request | 缺口 | H2 |
| T5 | PROD 尖峰時模型服務變慢（項目晚到，不是失敗） | B7 N9 #93 | 整份文件失敗、重新處理。容量模型是在「文件不等晚到的項目就完成」之下算的；交接說了，但沒有人被要求重算 | 交接 | |

#### 12. 重新派送與重複的回報

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| X1 | Temporal 裡找不到 workflow | 規格 §9 N1 B3 | 用同一個 request id 再啟動；登錄過的項目重用；`result.json` 與內容物件只寫一次，第一份留下 | 涵蓋 | |
| X2 | 第二次的 mapper 輸出差一個 byte | B3 | 已存的物件勝出；回報的 digest 必須是已存物件的 | 交接 | |
| X3 | 失敗的 request 不能留下 `complete` 的結果 | B7 | 規則在 `finalize` 寫任何東西之前執行 | 交接 | |
| X4 | workflow 用舊 build 的結果格式結束（沒有 candidate） | B2 | 沒形成接受；同 NS5 | 缺口 | M1 |
| X5 | reconciler 的 pod 卡住（sidecar）且 `Forbid` | #78 C28 | 遺失的回報永遠補不上；文件停在 `processing` | 交接 | M7 |

#### 13. mapping 步驟被 Temporal 重試

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| Y1 | `finalize` 寫完內容物件之後被重試 | B2 B3 | key 由 request id 決定；物件已存在就沿用 | 交接 | |
| Y2 | `finalize` 五次嘗試都用完 | B2 | `PLATFORM_ERROR`，可重試。可能留下沒有紀錄的物件 | 涵蓋；遺留的物件隨文件的清除清掉（D 組） | |
| Y3 | `finalize` 被重試時的計數 | B9 | 每次執行都計判斷：重試會算兩次 | 缺口 | L4 |

#### 14. commit 時 failover

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| V1 | PostgreSQL 在 commit 寫穩之前停了 | B1 | 什麼都不存在；回報在預算內重試，之後由 reconciler | 涵蓋 | |
| V2 | MongoDB failover，不知道 commit 有沒有成功 | B1 B3 | 重試；「我自己的 `crv_` 已存在」算成功 | 交接 | |
| V3 | 從備份還原，最後一分鐘的接受遺失 | B1 B3 | request 回到 `processing`；reconciler 用同一個 `crv_` 再接受一次。還原後的 feed 位置與 projection 的 cursor 屬 F 組 | 涵蓋；還原的語意在 F 組，feed 與 cursor 一起回捲是 #78 的 C12 | |

#### 15. CronJob 重疊、晚到的 pod、sidecar

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| K1 | 晚到的 `apply-adoption` pod 帶著舊宣告 | B8 | 跳過：只套用大於已套用最大值的 | 涵蓋 | |
| K2 | 兩個 pod 套用同一個新宣告 | #261 | 需要 (media type, declaration) 的唯一限制；#261 只測了舊宣告 | 缺口 | L9 |
| K3 | `apply-adoption` 或掃描的 pod 不結束（sidecar） | #78 C28 | `Forbid` 擋住之後每一次執行：不能採用、退版、重試、重刷。「等確認點」的警示也不會發，因為根本沒執行 | 交接 | M7 |
| K4 | 兩個掃描的 pod | B8 | 唯一索引擋住同一個 Source Revision 的第二筆 request | 涵蓋 | |
| K5 | 掃描跨過一次採用的 commit | B8 | 部分 request 在前一次採用之下建立；最後會收斂（U6、W2） | 涵蓋 | |
| K6 | 確認點做到一半 pod 被殺 | #261 | 下次執行要重用還是重做測試 workflow，由 #261 定 | 交接 | |

#### 16. 宣告寫錯

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| Z1 | 宣告一個不存在的版本 | B8 | 在確認點一直等；等太久發警示 | 交接 | |
| Z2 | 漏了某個 media type | #261 | 當成錯誤拒絕，不當成取消 | 涵蓋 | |
| Z3 | 內容改了但 `declaration` 沒加（或 revert 讓它變小） | #261 | 「什麼都不做，exit 0」：沒套用、沒錯誤、沒計數。設定與資料庫悄悄不一致 | 缺口 | M5 |
| Z4 | 採用中版本的 `profiles` 設定被拿掉 | #178 | 沒有東西拒絕；同 U9 | 缺口 | M6 |
| Z5 | 拿掉 `withdrawn` 裡的項目 | #261 | 拒絕 | 涵蓋 | |
| Z6 | `refresh` 缺少或格式錯 | B8 | 「沒有預設值」意味著拒絕，但 #261 的拒絕清單沒列 | 缺口 | L9 |
| Z7 | 不含 `d3-check` 的 profile 部署時沒有 d3 worker | B9 | promoter 與確認點都要五條 queue 有人 poll：build 永遠不會 current | 缺口 | M9 |

#### 17. 第一次部署

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| I1 | 空的資料庫 | #78 C19 | 沒有指令或 Job 套用 schema；#251、#98、#261 都會加 | 交接 | |
| I2 | 還沒有採用紀錄 | B8 | 確認點通過前，所有 PDF 都 `UNSUPPORTED_FORMAT` | 交接 | |
| I3 | 確認點的第一個測試 workflow | #261 | 需要 custody bucket 裡的測試 PDF、一個 `document_uid`、可用的 VLM 與 d3、它的狀態回報要有去處（現在會 `404`）。都由 #261 定 | 交接 | M10 |
| I4 | 每個 Source 的 Knowledge Profile | #78 | `set-profile` 沒有 CronJob 的形式 | 交接 | |
| I5 | 掃描部署之前就宣告了 `withdrawn`（#261 先於 #98 完成） | B6.3 | 結果被丟棄，沒有東西重跑；Source 重送回 `unchanged` | 缺口 | M11 |
| I6 | 採用紀錄的 tenant | N8 | 一套部署一個 tenant；tenant 來自部署設定，不寫在採用的宣告裡 | 已定（E 組）；#261 已收到 | L9 |

#### 18. MongoDB 的 write skew

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| G1 | 受理對上刪除 | A3 B4 | 受理的每條路都寫 Document 的版本欄位 | 交接 | |
| G2 | 掃描開 request 對上刪除 | B8 | #239 的交接有寫，#98 的 body 沒有 | 交接 | L7 |
| G3 | 受理對上寫入作廢清單 | B6.3 | 沒有共同寫入的資料；同 W3 | 涵蓋 | |
| G4 | finalize 對上取消或新的採用（現在用 `FOR SHARE`） | B8 | 移植時放寬承諾。request 可能建在剛取消的版本上；worker 已不在時就是 U9 | 交接 | H2 |
| G5 | 每個 Source Revision 只有一筆進行中的 request | A3 規格 §3 | 兩種資料庫都用 partial unique index；#236 的 prototype 做過 | 涵蓋 | |
| G6 | MongoDB 上的 feed | N4 B5 | tailer 看 Document 指標的改變；priority 存在被看的紀錄上 | 交接 | |

#### 19. 對 feed 與 projection 的影響

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| E1 | 只有目前版本換了才發事件 | B5 | 輸的 revision、沒形成接受、失敗，都不發 | 涵蓋 | |
| E2 | 事件的 priority | #251 | 換掉作廢版本做的目前版本：`normal`；否則平台 request：`background`；其餘：`normal` | 涵蓋 | |
| E3 | 作廢之後大量重做 | B6.2 | 每份一筆 `normal` 事件，和每天的更新搶（DR A3：批次工作不能擋住每天的更新） | 交接 | L10 |
| E4 | projection 寫入一個已不是目前版本的 revision | #55 DR B5 | 在 commit 時的檢查被丟掉（#252） | 涵蓋 | |
| E5 | 沒有目前版本的文件 | B7 | 沒有事件；projection 不知道它 | 涵蓋 | |
| E6 | 讀目前版本或確切 revision 的內容 | A2 N6 | 內容物件在 `documents/{document_uid}/revisions/{canonical_revision_id}.json`；內容與它列出的產物的位元組由平台的讀取 API 提供 | 已定（C 組，#268） | |
| E7 | 「接受之後失效」（DR §6：pilot 照樣有） | B5 | #251 假設目前版本不會被拿掉；DR 2026-11-18 的註記說文件可以沒有目前版本。沒有裁決說誰會這樣做 | 矛盾 | M8 |

#### 20. metrics 與告警

| 編號 | 情境 | 決策 | 結果 | 狀態 | 發現 |
|---|---|---|---|---|---|
| MA1 | d3 檢查沒有判斷的比例 | B9 | `item_outcomes{method="d3-check@1", status="not_run"}` ÷ 全部；要在規則判定失敗的地方也計數 | 交接 | |
| MA2 | 文件失敗的比例，依原因 | B9 | `document_outcomes{outcome="failed", reason}`；`reason` 是新的 label | 交接 | |
| MA3 | 這些比例數的是什麼 | B9 | 數的是嘗試次數，不是文件數：中斷期間每次重跑、每次重用都加一 | 缺口 | L4 |
| MA4 | 沒形成接受的成功結果，依原因 | B4 B6.3 | 三個計數（已刪除、沒有 candidate、版本已作廢） | 涵蓋 | |
| MA5 | 掃描：可重試超過警示次數；不可重試已放棄 | B9 | 計數，式子交給 infra | 交接 | |
| MA6 | 採用：被拒絕、等確認點 | B8 | 計數 | 交接 | |
| MA7 | CronJob 停止執行 | — | 不在 #78 的清單裡 | 缺口 | M7 |
| MA8 | 存活但超過時限沒有目前版本的文件；進行中超過時限的 request | — | 不在任何清單裡；它是能看出上面每一種「卡住」的那個數字 | 缺口 | M7 |
