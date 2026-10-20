# Knowledge Platform 資料安全治理面向

**日期：2026-10-20，更新 2026-10-21（Asia/Taipei）。狀態：討論用框架，不是已確認的決策、新增 MVP gate 或技術選型。** 後續討論與決議由 [#87](https://github.com/davidlinnnn/data-ingestion/issues/87) 承接；持續更新的面向表格在 #87 的 Overview，本文是 2026-10-21 的快照。

Knowledge Platform 管「哪些資料、以誰的身分、在什麼條件下被釋出」；Agent Platform 管「agent 拿到資料後做了什麼」。15 個資料安全面向中，4 項已有 ticket 推進，7 項只部分涵蓋，4 項目前沒有負責的 ticket。

本文補充 [Knowledge Platform 作為 Agent Context Layer 的治理研究](knowledge-governance-context-layer-2026-10-17.md)與其 [retro](knowledge-governance-retro-spike-2026-10-17.md)。那份研究涵蓋來源權威、品質、用途限制與 agent context 責任；本文只看資料安全，並依 2026-10-19／10-20 的授權決策（#56、#85、#86、#31 第一至三輪）與 #84 結案紀錄更新各 ticket 的現況。第 7、8 項、灰色地帶第 1 點和第 14 項與該研究重疊；第 4、9、12、13、15 項是新增。沿用 retro 的界線：這些面向要依已選 pilot 和資料流判斷是否適用，不是整包新增的 gate。

## 邊界

資料一旦釋出，後續怎麼使用就歸 Agent Platform（由另一個 infra team 負責）。兩邊各管什麼，取決於中間那欄的契約怎麼定。[#76 在 2026-10-17](https://github.com/davidlinnnn/data-ingestion/issues/76#issuecomment-6230760445) 已確認：consumer／Agent Owner 負責 context 組裝、egress、memory 和工具副作用。

| 面向 | Knowledge Platform | 兩邊之間的契約 | Agent Platform |
|---|---|---|---|
| 身分 | 驗證呼叫者，判斷是代表哪個使用者 | on-behalf-of 委派的格式：agent 代表誰、帶什麼 token | 發 agent 身分；決定 agent 可以代表哪些使用者 |
| 授權 | 每次讀取都判定；看不到的不回傳，也不透露存在 | — | 決定 agent 能用哪些 tool |
| 釋出之後 | 每筆結果附上版本、有效期、原文或生成標示 | agent 遵守有效期，撤權後不再使用 | memory、快取、要送給哪個模型、往外送資料（egress） |
| 內容安全 | 標示 provenance；控制誰能寫入 | — | 防禦 prompt injection；控制工具副作用 |
| 稽核 | 記錄「釋出給誰」 | correlation ID | 記錄「agent 拿這份資料做了什麼」 |
| 寫入 | agent 提交文件時視同一般 submitter，走 #31 的授權 | — | 決定 agent 能不能呼叫寫入 API |

## 交界灰色地帶

下面四個情境，兩邊單獨都管不完，要在契約裡講好。

1. **撤權到不了 agent 的 memory。** 資料釋出後平台收不回來，所以平台能保證的只有「撤權之後不再釋出」。要讓撤權也影響已拿走的內容，契約就要要求 Agent Platform 遵守有效期、不能無限期保存。
2. **大量抽取。** agent 用使用者的權限，可以合法讀完該使用者看得到的全部內容。只有 Knowledge Platform 看得到讀取量，讀取配額和異常偵測適合放在我們這邊；目前 #31 只有寫入配額。
3. **透過文件夾帶 prompt injection。** 惡意指令來自被收進平台的文件。平台無法保證內容沒有 injection，但能控制誰可以把內容放進 Resource，並標示來源；真正的防禦在 Agent Platform。
4. **agent 用自己的身分讀取。** 這是背景工作，不是代表某個使用者。這種 agent 必須被明確授予 reader relation，不能因為是平台服務就看得到全部（[#56 在 2026-10-20 列為待決](https://github.com/davidlinnnn/data-ingestion/issues/56#issuecomment-6285578350)）。

## 15 個資料安全面向

分類：1–4 存取、5–6 生命週期、7–9 資料本身、10–11 完整性、12–13 基礎防護、14–15 問責。

| # | 面向 | 要回答的核心問題 | 現況 | 負責 ticket 與備註 |
|---|---|---|---|---|
| 1 | 身分與委派 | 每次存取能歸屬到具體的人或服務嗎？委派會擴大權限嗎？ | 有 ticket 推進 | #85、#56、#76；#31 第三輪把 service account 憑證的簽發交給 #85 |
| 2 | 存取控制與職責分離 | 讀取、提交、管理權限分開嗎？授權服務無法判定時 fail-closed 嗎？ | 有 ticket 推進 | #85、#56、#31 |
| 3 | **衍生資料洩漏**（知識平台特有） | 摘要、Wiki、embedding、KG、搜尋片段、結果數量、引用，會不會洩漏無權看的內容或其存在？ | 部分涵蓋 | ADR-0007（#55、#56）只涵蓋事先生成的產品，前提是同一 Resource 內的輸入讀者相同；embedding 與索引未討論。#31 第三輪定了狀態查詢的揭露限制：只有 Source 憑證能查，自由文字不得帶出其他文件 |
| 4 | 特權存取 | 維運人員和 DBA 能直接讀內容嗎？有 break-glass 流程與稽核嗎？ | 無 owner | — |
| 5 | 撤權、撤回、刪除的傳播 | 會傳到索引、快取、衍生產品、備份嗎？多久生效？ | 有 ticket 推進 | #56、#57、#32；#31 第三輪：rebind 縮小讀者時走撤權路徑，撤下時效待 #56 決定 |
| 6 | 保留、合法刪除、legal hold | 什麼資料保留多久？刪除時要提出什麼證據？ | 部分涵蓋 | #57、#54 |
| 7 | **資料分級與處理規則** | 誰標敏感等級？各等級能做什麼，例如能不能送外部模型、能不能進 Wiki 綜合？ | 無 owner | 目前最大的缺口 |
| 8 | 處理過程的資料流出 | 內容送到哪些 OCR、VLM、LLM、embedding 服務？在哪裡執行、會不會留存？ | 部分涵蓋 | #84 已結案：DEV 推論用外部 API，正式版維持地端開源模型；哪些資料可以送外部 API 尚未寫成準則 |
| 9 | 文件夾帶的敏感資訊 | 文件裡有密碼或 PII 時，要偵測、遮蔽，還是由 Source 自己負責？ | 無 owner | — |
| 10 | 來源完整性與 provenance | 能偵測竄改、追溯來源版本、分辨原文與生成內容嗎？ | 有 ticket 推進 | #31（digest）、#76、#32 |
| 11 | 知識投毒 | 誰能影響別人或 agent 讀到的內容？ | 部分涵蓋 | #85 的 contributor 模型，尚未以此角度審視 |
| 12 | 加密、金鑰、secret | 靜態與傳輸加密？各 tenant 分開金鑰嗎？signed URL 當 secret 處理嗎？ | 部分涵蓋 | #57、#78、#53 |
| 13 | 隔離 | tenant 隔離；開發環境能不能用真實資料；解析惡意 PDF 時有沒有 sandbox？ | 部分涵蓋 | #56（tenant）；後兩項無 owner |
| 14 | 稽核紀錄 | 讀取、關係變更、判定來源都要記錄嗎？稽核紀錄誰能看、保留多久？ | 部分涵蓋 | #85（欄位）、#56（operator 揭露） |
| 15 | 濫用與大量抽取 | 讀取有配額和異常偵測嗎？ | 無 owner | 見灰色地帶第 2 點 |

## 觀察與優先順序

- **知識平台最容易出事的是第 3 和第 7 項，不是基礎防護。** 平台會把文件加工成摘要、Wiki、向量和答案，敏感資訊可能經由這些衍生資料外洩；判斷資料能不能被加工，也需要分級。
- **embedding 要當成跟原文一樣敏感。** [Vec2Text](https://arxiv.org/abs/2310.06816) 從 embedding 精確還原了 92% 的 32-token 輸入，並從臨床筆記的 embedding 還原出全名。[OWASP LLM09:2026](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM09_VectorAndEmbeddingWeaknesses.md) 把 embedding 還原、用結果數量推斷他人文件存在、檢索投毒列為主要風險，並要求向量庫備份與原文同等敏感。
- **第 12、13 項多半可以引用公司既有的資安標準**，只要在 #57、#78 確認有遵守。
- **準則以正式版會收的資料為準。** pilot 是研究論文，敏感度低；只照 pilot 設計，以後會像 tenant 一樣要回頭補。

## 待確認問題

- [ ] 公司有沒有既有的資料分級標準（例如公開／內部／機密／限閱）？有的話，第 7 項只要對應處理規則。
- [ ] 正式版預期會收哪些資料？只有技術文件，還是也有人事、客戶、財務資料？這決定第 3、7、9 項要做到多嚴。
- [ ] Agent Platform 的 infra team 有沒有已定義的委派 token 和 agent 身分格式？尤其是釋出的資料可以保存多久。

## 來源

- [OWASP LLM09:2026 Vector and Embedding Weaknesses](https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM09_VectorAndEmbeddingWeaknesses.md)（查閱 2026-10-20）
- [Morris et al., Text Embeddings Reveal (Almost) As Much As Text, EMNLP 2023](https://arxiv.org/abs/2310.06816)
- 各面向的現況取自 [#52](https://github.com/davidlinnnn/data-ingestion/issues/52) 及 #31、#53、#55、#56、#57、#58、#76、#78、#85、#86 的內文與留言（2026-10-21 讀取）
