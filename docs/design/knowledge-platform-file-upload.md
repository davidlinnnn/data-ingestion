# Knowledge Platform 文件交付指南：設計、決策與 Source API

**狀態：** Contract companion：說明契約，不另立契約；和規格不一致時以規格為準。2026-11-07 定案方向與契約；最近一次對齊在 2026-11-20（第 7.2 節）。實作票與進度在第 7.3 節。

本文是「Source 如何把文件交給平台」的單一入口。讀完這一份，就知道設計的想法、做過的決定與理由、API 怎麼用、部署要準備什麼，一般不必再開另外兩份文件；每條規則的完整條文仍在規格。三份的用途不同：

| 文件 | 給誰 | 內容 |
|---|---|---|
| 本文 | Source 開發者、DevOps、想了解設計的人 | 設計、決策、架構與流程、API 使用方法、部署需求 |
| [admission 規格](knowledge-platform-admission-spec.md) | 平台實作者 | 完整契約：每條受理規則、狀態、派送與耐久、保留期 |
| [admission 設計筆記](knowledge-platform-admission.md) | 查歷史的人 | 逐輪的問答紀錄（Q4、Q5 等編號），含已被取代的內容 |

Resource 登記的契約在[授權指南](knowledge-platform-authorization-guide.md) §4.7。術語依 `CONTEXT.md`。

| 讀者 | 先讀 | 再讀 |
|---|---|---|
| 想了解設計的人 | 摘要；第 2 節：選項與決定 | 第 3、4 節 |
| Source 開發者 | 摘要；第 5 節：使用指南（第 5.6 節是每個呼叫的欄位表） | 第 4.2 節的失敗表、第 4.3 節的狀態 |
| DevOps | 第 3 節：架構；第 6 節：部署與維運（第 6.8 節是設定的格式，第 6.9 節是部署順序與驗收） | 第 4.2 節的失敗表、第 4.3 節的狀態、第 7.3 節的實作狀態 |
| 平台實作者 | 規格 §5、§6（契約） | 第 2 節的決定、第 4 節 |

## 摘要

Source 是把文件交給平台的系統，例如 KM。它用平台核發的 credential 呼叫 API。交一份文件是三個呼叫；處理在背景進行，結果用查詢取得。

| 步驟 | 呼叫 | 平台做什麼 |
|---|---|---|
| 準備（每個 Resource 一次） | `PUT /v1/resources/{key}` | 記下這個 Resource；Resource 決定誰讀得到文件 |
| 1. 宣告 | `POST /v1/batches` | 還沒收檔就檢查規則，回覆哪些檔案要上傳 |
| 2. 上傳 | 每個檔案一個 `PUT` | 邊收邊驗大小與 SHA-256，通過才存下來 |
| 3. finalize | `POST /v1/batches/{batch_id}/finalize` | 一次受理整批，回 `202` 與每份文件的 `request_id` |
| 之後 | `GET /v1/requests/{request_id}`、`GET /v1/documents/{document_id}` | 回報這一次處理的結果，以及文件是否已經可以被讀到 |

三個主要的決定：

- **檔案經平台 API 上傳。** 不用 presigned URL，也不讓 client 直接寫 storage：公司政策禁止前者，後者要多發一套 storage 憑證（第 2.3、2.4 節）。
- **先宣告、再上傳、最後 finalize。** 沒變的文件在宣告就結束，只改一個附件就只傳那個附件；finalize 把整批在一個 transaction 受理，`202` 之後不會遺失也不會重複（第 2.5 節）。唯一的例外是資料庫的磁碟區毀損後從備份還原：最後大約一分鐘內受理的 request 可能遺失，要請 Source 重送（規格 §9）。
- **Resource 用 Source 自己的 key，先登記再使用。** 打錯的 key 會被擋下，不會默默建出一個新的 Resource（[ADR-0013](../adr/0013-resource-identified-by-source-key.md)）。

最短的用法是第 5 節開頭的 quick start。

## 1. 背景與限制

### 1.1 誰上傳、上傳什麼

- 上傳者是 Data Owner 的系統（`CONTEXT.md` 的 **Source**），用平台核發的 Source credential 呼叫 API；人只是觸發者，平台不以人的身分授權這個操作（設計筆記 2026-10-18 的 client 釐清）。
- 一次提交是一個 **Batch**，最多 50 個 item；每個 item 是一份 Document 的一個版本，含一個 `main` 檔與零到多個附件，每個檔案宣告 `sha256`、`size`、`media_type`。
- 主檔格式要有採用中的 Processing Profile 版本才收（admission 規格 §3、§6.1 第 2 條）；pilot 只有 PDF（`paper-pdf`）。

### 1.2 不變的邊界

這些在政策變更前後都成立，是本文所有選項的共同前提（「上傳直接就位」一列在 2026-11-11 取代了原本的「staging 與 custody 分開」）：

| 邊界 | 內容 | 出處 |
|---|---|---|
| 三步驟提交 | 宣告 → 上傳 → 明確 finalize；finalize 才做耐久受理並回 `202` | 規格 §5、設計筆記 Q4 |
| 固定輸入先於受理 | 檔案內容在受理前固定，SHA-256 由平台驗證；任何後續寫入都不能改變已 finalize 的輸入 | [ADR-0004](../adr/0004-fixed-capture-custody-before-admission.md) |
| 上傳直接就位 | 檔案驗證通過後，直接寫到它在 custody bucket 的 key；finalize 不寫 storage；沒被受理的檔案由 admission 清除 | 規格 §5.2、§6.2、§10；[ADR-0012](../adr/0012-uploads-written-at-custody-key.md) |
| 受理即派送 | finalize 的同一個 transaction 寫入 request 與 outbox，dispatcher 再啟動 Temporal workflow | 規格 §9 |
| 處理端不碰 client | processing 用平台憑證依 `custody_ref` 讀檔，不對 client 發任何 URL | [#129](https://github.com/davidlinnnn/data-ingestion/issues/129) |

### 1.3 公司政策（2026-10-30）

主管確認：公司政策禁止 client 以 presigned URL 上傳檔案。SAS 是同類的、由 storage 簽發的 bearer URL，轉達時一併視為排除。這條政策讓 2026-10-20 定下的上傳 grant 形式（storage 原生 presigned URL 或 SAS，設計筆記 Q5）失效。紀錄：[#95 的轉達](https://github.com/davidlinnnn/data-ingestion/issues/95#issuecomment-6518076869)、[#96 的轉達](https://github.com/davidlinnnn/data-ingestion/issues/96#issuecomment-6658212404)、[資料安全文件](knowledge-platform-data-security.md) §2。

**政策範圍（使用者 2026-11-07 確認）**：政策只排除 presigned URL 這種 bearer URL 機制，不限定傳輸管道；經 admission API 上傳可行。這是本文決定的唯一前提，已成立。

### 1.4 規模

PROD 負載規格（[#88](https://github.com/davidlinnnn/data-ingestion/issues/88#issuecomment-6633160435)，2026-11-04）：

| 項目 | 數值 |
|---|---|
| 尖峰 | 每分鐘 50 份 PDF，持續 10 分鐘；一次 burst 500 份 |
| 檔案大小 | 平均 20 MB，硬上限 50 MB |
| 換算 | 約 1 GB／分鐘，即 17 MB/s；一次 burst 約 10 GB |
| 同時上傳數 | 每條連線 100 Mbps 時，一份 20 MB 約 1.6 秒傳完，平均同時 1 到 2 個上傳 |

換算與同時上傳數是估算，不是量測。

## 2. 選項與決定

### 2.1 最初的五個方案（#53 Q9，2026-10-02 至 10-03）

| # | 方案 | 誰搬檔案 | 當時的結論 | 政策下的狀態 |
|---|---|---|---|---|
| 1 | 平台發上傳授權，client 直接 PUT 到 storage（presigned URL） | client | 選為通用入口 | 被排除 |
| 2 | Source 發 signed GET，平台去抓檔 | 平台 | 保留為選用的匯入路徑 | 也是 presigned URL，只是方向相反；不採用 |
| 3 | 長期委派的 connector（暫時憑證、聯邦身分） | 平台 | 只給需要持續同步的來源 | 不受影響，但建置成本最高 |
| 4 | 預先註冊 Source 的 storage，平台用自己的身分去讀，client 只送檔案位置 | 平台 | 最早的 pilot 提案；每個 Source 都要設定 endpoint 與 token，改為方案 1 | 不受影響 |
| 5 | 檔案內容直接放在 ingestion API 的 request 裡 | client → API | 影像、影片不該經過 API；pilot 不提供 | 不受影響 |

出處：[Q9 最終建議](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966660481)、[Q9 確認](https://github.com/davidlinnnn/data-ingestion/issues/53#issuecomment-5966721936)、[雲端實務研究](../research/attachment-handoff-cloud-practices-2026-10-02.md)。

### 2.2 push 對 pull

push：client 把檔案送進平台。pull：平台去 Source 的 storage 讀檔。

| 面向 | Push | Pull |
|---|---|---|
| client 要做的事 | 實作上傳與失敗重傳 | 只送檔案位置與 sha256 |
| 平台要做的事 | 收檔、驗證 | 多一個抓檔元件，負責重試、限速、逾時 |
| 每個來源的上線成本 | 發一組 credential | 逐一談定 storage 位置、讀取權限、防火牆 |
| 網路方向 | client 連平台，平台不必對外連線 | 平台要能連到每個來源的 storage |
| 憑證風險 | 平台不持有來源的憑證 | 平台持有所有來源的讀取權限，被入侵時影響面大 |
| 檔案固定性 | 檔案一到就算 SHA-256、立即固定 | 宣告到抓檔之間檔案可能被改或刪，要綁版本並處理失敗 |
| 回應時機 | finalize 當下就知道檔案齊不齊 | 多一個非同步的「抓檔中」階段與對應的錯誤狀態 |
| 流量控制 | client 決定何時送，burst 直接打到平台，靠限流擋 | 平台自己排隊抓，可以把 burst 攤平 |
| 適用的來源 | 任何能呼叫 HTTP 的系統 | 只有檔案已放在相容 storage 的系統；其他系統要各寫 connector |
| 越權風險 | 小：只能寫自己被指定的位置 | 要防 A 來源藉平台的身分讀到 B 來源的檔案 |
| 對規格的改動 | 小：三步驟流程與規則不變 | 大：上傳步驟換成抓檔階段，狀態與錯誤碼要重定 |
| 公司政策 | 經平台端點多半合規 | 沒有 client 上傳；但平台讀其他團隊的 storage 需要另外核准 |

兩種方式搬的資料量一樣（burst 時約 1 GB／分鐘），檔案最後都要在 custody 存一份，所以 pull 不省儲存空間。pull 的價值只在「檔案本來就放在公司核准的 storage」的來源，這也是 Q9 當時「已在核准 custody 的檔案不必再傳一次」的結論；pilot 目前沒有這種來源。

### 2.3 經平台 API 對 client 直接寫 storage

presigned URL 本來就是「讓 client 不拿 storage 憑證也能直接寫」的機制。它被禁之後，client 要直接寫 storage 就必須持有 storage 的憑證，等於在 Source credential 之外再多一套身分系統。

| 面向 | 經 API 上傳 | client 直接寫 storage |
|---|---|---|
| 資料路徑 | client → API pod → storage，多一跳 | client → storage |
| client 持有的憑證 | 只有 Source credential | 另外一組 storage 憑證：長期金鑰，或 STS 暫時憑證（MinIO：15 分鐘至 365 天，預設 1 小時） |
| 每個 Source 上線 | 發 credential 即可 | 還要在 storage 建身分、綁定只能寫自己 prefix 的 policy |
| 網路 | storage 留在內部，只有平台連得到 | storage 要開放給所有 client 的網段 |
| 檔案落地前的檢查 | 傳輸中就能擋下大小、型別、未知 batch、超出配額，並同時算 SHA-256 | policy 能限制 prefix，但文件裡沒有可限制上傳大小的條件；只能等 finalize 才發現並清掉 |
| client 的開發 | 一般的 HTTP PUT | S3 SDK 與 endpoint 設定 |
| 與 storage 產品的耦合 | client 看不到 storage；#57 尚未選定產品，之後怎麼選都不影響 client | client 綁定 S3 API 與該產品的憑證機制 |
| 稽核 | 上傳紀錄集中在平台 | 分散在 storage 與平台兩邊 |
| 公司政策 | 多半合規 | 風險最高：發給 client 的暫時憑證比 presigned URL 權限更大，很可能遇到同樣的反對 |

多一跳 API 的代價以目前的規模很小：17 MB/s、平均同時 1 到 2 個上傳，而 admission 的 `api` 本來就是水平擴充的角色。檔案到 GB 等級，或流量高一到兩個數量級時，直接寫 storage 才划算。

### 2.4 決定（2026-11-07）

- **方向：push，經平台上傳端點。** client 以 Source credential 把每個檔案 `PUT` 到 admission 的上傳端點，admission 串流寫入 storage（2026-11-11 起直接寫到 custody 的 key，見第 3 節）。
- **契約採最小形式**（規格 §5.2）：上傳端點直接以 Source credential 驗證，不另發 grant token；每個檔案一個 `PUT`；宣告回應的 `uploads[]` 列出平台端點；原本的 grant 重發端點與一小時效期刪除。理由：少一套 token 的簽發、過期與重發；上傳的授權本來就在 finalize 再檢查一次；Source credential 是每次呼叫都要帶的東西。
- **不做的事**：分段或續傳（50 MB 以下整個重傳即可）、inline 內容、pull 路徑（等有具體來源再開）。
- **對 Valet Key 原則的影響**：client 不再持有任何對 storage 的委派權限，設計筆記裡「以 Valet Key 模式授予 client 有限的 storage 存取」改為歷史。平台先驗證提交者的授權、再接受資料傳輸，這個順序沒有變。

### 2.5 為什麼是這幾個呼叫（2026-11-19 的審查）

2026-11-19 對 Source 這一側的 API 做了一次獨立審查，問題是流程能不能更簡單。結論是呼叫不變，使用者同日確認照審查的建議處理；紀錄在[設計筆記](knowledge-platform-admission.md#api-review-on-2026-11-19)。每一步的理由：

| 步驟 | 換到什麼 | 併掉或拿掉會失去什麼 |
|---|---|---|
| 登記 Resource | 平台只收它認得的 key，打錯的 key 在宣告時被擋。登記要 `manage_relations`、交文件要 `submit`，兩種權限分開 | 併進宣告（沒見過的 key 自動建立）：打錯字會默默建出一個 Resource，只有 `submit` 的 credential 也能建 |
| 宣告 | 檔案還沒傳就逐 item 檢查規則；只傳有變動的檔案；內容沒變的文件在這一步就結束 | 併進上傳：被拒的 item 也已經把檔案傳完，沒變的檔案每次都要重傳 |
| 每檔一個 `PUT` | 可並行；失敗只重傳那一檔；平台收到就驗證 | 併進宣告：50 個 item、每個 20 MB 是一個 1 GB 的 request，任何一檔失敗都整批重來 |
| finalize | 整批在一個 transaction 受理；受理當下重查刪除、Resource 與版本順序；重複呼叫回同一份結果 | 改成「最後一個檔案到就自動受理」：並行上傳時由哪一個 `PUT` 帶回受理結果不固定，那個回應遺失時 client 要另外查詢 |
| 查詢 | 處理是非同步的，結果用查詢取得 | 沒有替代品，除非做 callback；callback 列為之後的事（規格 §1） |

出處：規格 §5、§6.1、§6.2、§9；設計筆記 Q4、Q4a、Q10.1d；[ADR-0012](../adr/0012-uploads-written-at-custody-key.md)、[ADR-0013](../adr/0013-resource-identified-by-source-key.md)。

和公開的 API 比較。數的是「把一個檔案交出去，到對方承認收到」的呼叫數，不含查詢：

| API | 一個檔案 | 完成的方式 |
|---|---|---|
| 本平台 | 3 | 明確的 finalize，一次涵蓋整批 |
| [Slack 外部上傳](https://docs.slack.dev/messaging/working-with-files/) | 3 | 明確的 complete |
| [S3 multipart upload](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html) | 3（只有一段時） | 明確的 complete |
| [OpenAI Uploads](https://developers.openai.com/api/docs/api-reference/uploads) | 3（只有一段時） | 明確的 complete |
| [GCS resumable upload](https://docs.cloud.google.com/storage/docs/resumable-uploads)、[tus](https://tus.io/protocols/resumable-upload)（核心協定） | 2 | 最後一個 byte 到就完成 |
| [OpenAI Files](https://developers.openai.com/api/docs/api-reference/files/create) | 1 | 沒有事前檢查，也沒有「只傳有變動的檔案」 |

有明確 complete 的三個，都是把多個獨立的上傳組成一個單位；本平台的單位是多份文件乘多個檔案，屬於同一類。兩個呼叫的那兩個處理的是一條依序送的 byte stream；本平台允許檔案並行上傳，沒有「最後一個 byte」可看。

審查之後的處置：

- **做**：SDK 把三個呼叫包成一個（[#194](https://github.com/davidlinnnn/data-ingestion/issues/194)）；第 5 節加 quick start 與欄位表；規格 §5.1 寫明哪些欄位必填，以及 client 照 `uploads[]` 給的 `url` 上傳。
- **不做：單一 request 的便利端點。** 它是第二條進件路徑，和「單筆與批次共用一個契約」（設計筆記 2026-10-18）不一致。重新考慮的條件已經定了：pilot 的 client 無法使用 SDK（設計筆記 Q4a）。
- **現在不做：自動 finalize。** 設計筆記 Q4a 把它列為之後的最佳化；有 SDK 之後，省下的那一個呼叫開發者看不到。

對「一份文件、一個檔案」的情境，宣告與 finalize 分開給 client 的好處很少。這個情境的簡化交給 SDK，不改契約。

## 3. 系統架構

```mermaid
flowchart LR
  subgraph source["Source：Data Owner 的系統"]
    C["client 或 SDK"]
  end
  subgraph platform["Knowledge Platform"]
    I["Ingress"]
    A["Admission API（api 角色，固定副本數）"]
    DB[("Admission DB（pilot：PostgreSQL）")]
    CU[("Custody bucket（#57）")]
    D["Dispatcher"]
    T["Temporal"]
    W["Processing worker"]
    J["CronJob：reconciler、過期與清理、保留期"]
  end
  C -- "登記 Resource、宣告、finalize、查詢、刪除（JSON）" --> I
  C -- "PUT 檔案 bytes" --> I
  I --> A
  A -- "PUT：串流寫入，驗證通過物件才出現" --> CU
  A -- "resource、batch、document、source_revision、request、outbox" --> DB
  A -- "finalize：確認檔案已就位" --> CU
  D -- "取 outbox" --> DB
  D -- "start workflow，ID = request_id" --> T
  T --> W
  W -- "依 custody_ref 讀檔" --> CU
  J -- "核對沒有結果的 request" --> T
  J --> DB
  J -- "清除沒被受理的檔案" --> CU
```

Admission DB 在 pilot 是 PostgreSQL。PROD release 之前，admission 要移到公司代管的 MongoDB（[#239](https://github.com/davidlinnnn/data-ingestion/issues/239)，[2026-11-17 的裁決](https://github.com/davidlinnnn/data-ingestion/issues/78#issuecomment-6949497546)）。移植改寫的是資料存取、dispatcher 取件與 Change Feed 的做法；Temporal 自己的資料庫兩個階段都是 PostgreSQL。pilot 累積的資料在切換時搬移，或請 Source 重送，#239 開始時決定。

### 3.1 元件職責

| 元件 | 職責 | 出處 |
|---|---|---|
| client 或 SDK | 算 SHA-256、宣告、上傳、finalize、查詢；失敗時重送 | 規格 §5、設計筆記 Q4 |
| Ingress | TLS 終止、轉送；上傳路徑要放寬 body 上限與 timeout | 第 6 節，#78 |
| Admission API | 平台 API 的 `api` 角色：驗證 Source credential、Resource 登記、套用 §6 規則、串流收檔並驗證、finalize、狀態查詢、刪除 | 規格 §5、§6；[授權指南](knowledge-platform-authorization-guide.md) §4.7 |
| Admission DB | resource、batch、document、source_revision、request、outbox 等紀錄 | 規格 §3；resource 見授權指南 §4.6 |
| Custody bucket | 上傳的檔案；受理後成為固定輸入，processing 依 `custody_ref` 讀取；沒被受理的由 admission 清除 | 規格 §6.2、§10，#57 |
| Dispatcher、Temporal | 受理後的派送與處理，與上傳方式無關 | 規格 §9、§10 |
| CronJob | reconciler 每 5 分鐘核對已派送但沒有結果的 request；每小時把逾期的 batch 標為過期，並清除沒被受理的檔案；每天執行 Change Feed 的保留期（batch 等紀錄的保留期還沒實作，#250） | 規格 §9、§13 |

### 3.2 憑證與信任邊界

| 誰 | 持有什麼 | 能做什麼 |
|---|---|---|
| client | Source credential，權限是 `submit`、`manage_relations` 其中之一或兩者 | 對自己的 Source 登記 Resource、宣告、上傳、finalize、查詢、刪除；寫不到 storage |
| Admission（`api` 與清理的 CronJob） | custody bucket 的憑證（查物件是否存在、寫入、刪除）、DB 連線。兩個角色可以共用一組憑證，也可以照第 6 節各給最小的權限 | `api` 代 client 把檔案寫進 custody bucket；清理的 CronJob 刪除沒被受理的檔案、中止未完成的上傳 |
| Processing worker | 同一個 bucket 的讀寫憑證 | 依 `custody_ref` 讀固定輸入，寫處理結果（規格 §10） |

storage 的憑證只存在平台內；client 的網段只需要連到 Ingress。平台的設定只放 Source credential 的 SHA-256，不放 credential 本身（授權指南 §6.2）。worker 的憑證讀得到已上傳但還沒受理的檔案，到 admission 清除它們為止（[ADR-0012](../adr/0012-uploads-written-at-custody-key.md) 的後果）。

## 4. 流程

### 4.1 正常流程

```mermaid
sequenceDiagram
  autonumber
  participant C as Source client
  participant A as Admission API
  participant DB as Admission DB
  participant CU as Custody
  participant D as Dispatcher
  participant T as Temporal
  C->>A: PUT /v1/resources/{key}（每個 Resource 一次，可重複）
  A->>DB: 記下這個 Source 登記了 key
  A-->>C: 第一次 201，重複 200
  C->>A: POST /v1/batches（items：document_id、source_version、resources 的 key、files 的 sha256 與 size）
  A->>DB: 規則檢查（規格 §6.1，含 key 是否已登記），建立 batch 與 items
  A-->>C: 201：batch_id、每個 item 的 uploads[]（只列有變動的檔案）
  loop 每個 uploads[] 的檔案，可並行
    C->>A: PUT /v1/batches/{batch_id}/items/{index}/files/{path}（Content-Length、bytes）
    A->>CU: 分段串流寫入，每段 8 MiB，同時算 SHA-256 與 bytes
    A->>A: 比對 size、sha256，偵測 media type
    A->>CU: 相符才完成上傳，物件這時才出現；不符則中止
    A-->>C: 204；不符則 400 或 422，不留檔
  end
  C->>A: POST /v1/batches/{batch_id}/finalize
  A->>CU: 確認 uploads[] 的每個檔案都已就位
  A->>DB: 同一 transaction：規則檢查（規格 §6.2）、document、source_revision（每個檔案的 custody_ref）、request、outbox
  A-->>C: 202：每個 item 的 request_id
  D->>DB: 取 outbox
  D->>T: start workflow，workflow ID = request_id，REJECT_DUPLICATE
  C->>A: GET /v1/requests/{request_id} 或 GET /v1/documents/{document_id}
  A-->>C: 狀態
```

### 4.2 失敗與重試

| 情境 | 結果 | client 該做的事 |
|---|---|---|
| 宣告的 `resources` 填了沒登記的 key | 該 item `RESOURCE_NOT_FOUND` 被拒，其他 item 照常 | 先 `PUT /v1/resources/{key}`，該 item 重新宣告 |
| 上傳中斷線 | 該檔沒有 `204`，不留檔 | 重送整個 `PUT` |
| `Content-Length` 或實際 bytes 不等於宣告的 `size` | `400 SIZE_MISMATCH` | 檢查檔案與宣告；檔案真的變了就重新宣告 |
| SHA-256 不等於宣告 | `422 DIGEST_MISMATCH` | 同上 |
| 偵測到的 media type 不等於宣告 | `422 MEDIA_TYPE_MISMATCH` | 修正宣告或檔案，重新宣告 |
| `PUT` 到 `carried_over` 或未宣告的 path | `404` | 該檔不需要上傳 |
| 同一個檔案 `PUT` 兩次 | 沒有變化：已就位的檔案就是宣告的內容 | 無 |
| 檔案沒上傳完就 finalize | 該 item `FILES_MISSING` 被拒，其他 item 照常受理 | 該 item 重新宣告 |
| batch 開啟 24 小時未 finalize | `409 BATCH_EXPIRED`；已上傳的檔案由清理刪除 | 重新宣告 |
| 上傳中 storage 或資料庫無法回應 | `503 UNAVAILABLE`；檔案可能已就位，也可能沒有 | 依 `Retry-After` 重送整個 `PUT`；兩種情況重送都安全 |
| finalize 時 storage 無法回應 | `503 UNAVAILABLE`；batch 維持 open，什麼都不變 | 依 `Retry-After` 重試 finalize |
| finalize 在 commit 之前中斷（pod 被終止、資料庫重啟） | 連線中斷或 `503`；batch 維持 open，檔案都在 | 重試 finalize |
| finalize 已 commit，但 `202` 沒送到 | 已受理 | 重試 finalize，拿到同一份結果 |
| 文件在宣告之後被另一個 batch 建立 | 該 item `STALE_DECLARATION` 被拒，其他 item 照常受理 | 該 item 重新宣告 |
| finalize 之後再 `PUT` | `409 BATCH_FINALIZED` | 新版本要重新宣告 |
| finalize 重複呼叫 | 回同一份結果 | 可安全重試 |
| `429` 或 `503` | 帶 `Retry-After` | 依 `Retry-After` 重試；`ADMISSION_PAUSED` 只擋宣告，不擋上傳與 finalize |
| API pod 在上傳中被終止 | 連線中斷，物件不會出現；未完成的分段由清理中止 | 重送整個 `PUT` |

表中的「重新宣告」是一次新的宣告，要換一個 `Idempotency-Key`，body 相同也一樣：同一個 key 配同一個 body，24 小時內拿回的是原本的結果（設計筆記 Q6）。

### 4.3 一份文件經過的狀態

一次提交在三個地方留下狀態。三者回答不同的問題，不要混用：

| 看哪裡 | 回答什麼 | 值 | 誰讓它改變 |
|---|---|---|---|
| batch 裡 item 的 `status` | 這個 item 有沒有被受理 | 宣告時是 `declared`、`unchanged`、`queued` 或 `rejected`。之後 `declared` 變成 `queued`（受理）、`unchanged`、`rejected` 或 `expired` | 宣告與 finalize 時的規則（規格 §6） |
| request 的 `state` | 這一次處理做完了沒 | `queued` → `processing` → `succeeded` 或 `failed` | 處理端的回報；回報沒送到時由 reconciler 補記 |
| document 的 `readiness` | 這份文件現在讀不讀得到 | `not_ready`、`ready_stale`、`ready`、`deleted` | 各讀取端回報自己提供哪一版（#252） |

受理（`202`）之後，平台在背景依序做這些事：

1. finalize 的 transaction 寫入 request 與一筆 outbox。這時 request 是 `queued`。
2. dispatcher 每秒取一次 outbox，用 `request_id` 當 workflow ID 啟動 Temporal workflow。Temporal 停機時 outbox 留著，dispatcher 不會結束，恢復後繼續。同時在處理中的 request 有上限（全部 1000、每個 Source 500，暫定值）；超過的留在 outbox 等，這時 request 也是 `queued`。
3. processing worker 依序跑四個階段：`prepare`、`parse`、`enrich`、`finalize`，並向 `api` 回報進度。第一筆回報讓 request 變成 `processing`。
4. 最後一個階段回報成功，request 變成 `succeeded`。任何階段回報失敗，request 變成 `failed`，帶一個 error block。
5. 回報沒送到時，reconciler（每 5 分鐘）向 Temporal 查 workflow 的結果，補記 request 的結束。所以 request 可能不經過 `processing`，直接從 `queued` 變成結束。

受理後的 item，在 batch 裡的 `status` 跟著它的 request 走（`queued`、`processing`、`succeeded`、`failed`）。batch 是那一次提交的紀錄；文件的現況看 document。

## 5. 使用指南：給 Source 開發者

本節依契約寫，不是現況。`dev` 上能呼叫的是 Resource 登記、宣告、上傳、finalize、`GET /v1/batches/{batch_id}` 與狀態查詢；刪除還沒實作，進度見第 7.3 節。讀取端的回報接收已經接上（#252），但還沒有讀取端會送回報：要等 Canonical Acceptance 的記錄（#251）寫出 `current_revision_changed`，以及 consumer SDK 與 reference projection（#127）。在那之前每份未刪除的文件的 `readiness` 都是 `not_ready`；這段期間用 request 的 `state` 追蹤一次提交（規格 §5.6）。

### Quick start：一份文件、一個 PDF

```sh
# 準備：算出檔案的 SHA-256 與大小
shasum -a 256 policy.pdf     # 64 個十六進位字元
wc -c < policy.pdf           # bytes

# 準備（每個 Resource 一次）：登記 Resource。credential 要有 manage_relations（第 5.1 節）
curl -X PUT https://kp.example/v1/resources/hr-all -H "Authorization: Bearer $KP_TOKEN"

# 1. 宣告。回應 201，帶 batch_id 與 items[0].uploads[0].url
curl -X POST https://kp.example/v1/batches \
  -H "Authorization: Bearer $KP_TOKEN" -H "Content-Type: application/json" \
  -d '{"items":[{"document_id":"hr:leave-policy","source_version":"1","resources":["hr-all"],
       "files":[{"path":"policy.pdf","role":"main","sha256":"9f2c…","size":18342,"media_type":"application/pdf"}]}]}'

# 2. 上傳到回應給的 url。回應 204
curl -X PUT "https://kp.example/v1/batches/bat_01J…/items/0/files/policy.pdf" \
  -H "Authorization: Bearer $KP_TOKEN" -H "Content-Type: application/pdf" \
  --data-binary @policy.pdf

# 3. finalize。回應 202，帶 request_id
curl -X POST https://kp.example/v1/batches/bat_01J…/finalize -H "Authorization: Bearer $KP_TOKEN"

# 之後：用 finalize 回應的 request_id 查詢，直到 state 是 succeeded 或 failed
curl https://kp.example/v1/requests/req_01J… -H "Authorization: Bearer $KP_TOKEN"
```

一開始可以不管的東西：

| 項目 | 為什麼可以先不管 |
|---|---|
| `Idempotency-Key` | 選填。沒帶而重送宣告，會多一個 batch、多扣一次配額，但同樣的內容不會被受理兩次（規格 §6.2、§6.4） |
| `title`、`source_url`、`metadata`、`uploaded_by` | 選填，不影響處理 |
| `carried_over` | 只有重送多檔文件時才不是空的 |
| `GET /v1/documents/{document_id}` | 讀取端開始回報之前（#251、#127），`readiness` 都是 `not_ready`；這段期間看 request 的 `state` 就夠（第 5.2 節「之後：查詢」） |
| `GET /v1/batches/{batch_id}` | 整批的進度；交單份文件用不到 |

以下各小節是完整的說明。

### 5.1 前置

- 向平台取得 `source_id` 與 Source credential（pilot 是平台核發的 service-account token）。credential 的權限有兩種：`submit`（交文件）與 `manage_relations`（登記與刪除 Resource）。宣告與刪除文件需要 `submit`；登記 Resource 需要 `manage_relations`，只有 `submit` 的 credential 會得到 `403`。
- `source_id` 不用放進任何呼叫，平台從 credential 知道是哪個 Source；回報問題時用得到。
- 有三個值由平台設定，沒有 API 可以查，上線前向平台確認：這個 Source 的排序方式（預設依 `source_version`；設成依到達順序的 Source 可以不填 `source_version`）、有沒有預設 Resource（預設沒有）、單檔上限（預設 50 MB）。
- base URL 由部署提供，下面以 `https://kp.example` 代表。
- 每個呼叫帶 `Authorization: Bearer <credential>`。回應裡不認得的欄位略過；`bat_…`、`req_…` 這類 ID 當成不透明的字串。其他通則與每個呼叫的欄位在第 5.6 節。
- 登記 Document 要放入的 Resource。key 是 Source 自己對這個 Resource 的識別，例如 KM 的 space id；1 到 200 個字元，含 `/` 時在路徑寫成 `%2F`。v1 只能把文件放進自己登記的 Resource（[ADR-0013](../adr/0013-resource-identified-by-source-key.md)）。

```sh
curl -X PUT https://kp.example/v1/resources/hr-all \
  -H "Authorization: Bearer $KP_TOKEN"
```

第一次回 `201`，重複呼叫回 `200`，所以每次交文件前都呼叫一次也可以（交文件用的 credential 要同時有 `manage_relations`）。列出、取得與刪除 Resource 的契約在授權指南 §4.7；key 的義務（同一個 Resource 的文件讀者相同、key 不可換一批讀者重用）在授權指南 §3.2。

### 5.2 三個呼叫

**1. 宣告**

```sh
curl -X POST https://kp.example/v1/batches \
  -H "Authorization: Bearer $KP_TOKEN" \
  -H "Idempotency-Key: 7c9e4b1a-…" \
  -H "Content-Type: application/json" \
  --data @declare.json
```

`declare.json`：

```json
{
  "items": [
    {
      "document_id": "hr:leave-policy",
      "source_version": "3",
      "title": "Leave policy",
      "source_url": "https://km.example/hr/leave-policy",
      "resources": ["hr-all"],
      "uploaded_by": "sso:user-1",
      "metadata": { "km_folder": "HR/Policies" },
      "files": [
        { "path": "policy.pdf", "role": "main", "sha256": "9f2c…", "size": 18342, "media_type": "application/pdf" },
        { "path": "assets/flow.png", "role": "attachment", "sha256": "1ab0…", "size": 220114, "media_type": "image/png" }
      ]
    }
  ]
}
```

這個例子列出全部的欄位。每個 item 的欄位：

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| `document_id` | 字串 | 是 | Source 自己的文件代號；重送、查詢、刪除都用它。字元限制見第 5.4 節 |
| `files` | 陣列 | 是 | 這個版本的全部檔案，見下表 |
| `source_version` | 字串 | Source 依版本排序時要（預設） | 內容是整數（最多 18 位），或帶時區的 RFC 3339 時間，例如 `"3"`；一份文件只能用其中一種。寫成 JSON 數字，整個 request 會得到 `400`。比上一版小的會被拒（`STALE_SOURCE_VERSION`）；和上一版相同但內容不同的也會被拒（`VERSION_CONFLICT`），除非上一版被判定無法處理。比上一版大、檔案卻都相同的不會再處理一次：item 是 `unchanged` 或 `queued`，平台把這個版本記成最新版的 `source_version`，之後的排序以它為準。Source 沒有版本號時，請平台把它設成依到達順序，就不用填 |
| `resources` | 字串的陣列 | 新文件，且 Source 沒有預設 Resource 時要 | 一個已登記的 key，放在陣列裡，只能一個。既有的文件不用填，平台沿用原本的綁定 |
| `title`、`source_url` | 字串 | 否 | 目錄資訊；送了就取代現值 |
| `metadata` | 物件，key 與值都是字串 | 否 | Source 自己的註記；送了就取代整份，`{}` 清空。讀得到這份文件的人都看得到它，所以只放可以給讀者看的內容（[2026-10-31 的裁決](https://github.com/davidlinnnn/data-ingestion/issues/96#issuecomment-6542094987)，規格 §6.5）。大小限制見第 5.4 節 |
| `uploaded_by` | 字串 | 否 | Source 聲明的提交者身分；只做紀錄，不用於授權 |

每個檔案的五個欄位都必填：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `path` | 字串 | 文件內的相對路徑，最長 1024 個字元，不可重複。不能以 `/` 開頭，不能有空的段落或 `..`；可以有空白與非 ASCII 字元。它也是上傳網址的最後一段 |
| `role` | 字串 | 恰好一個 `main`，其餘是 `attachment` |
| `sha256` | 字串 | 64 個十六進位字元。平台用它判斷檔案有沒有變，並驗證收到的內容 |
| `size` | 整數 | bytes。超過上限的在宣告時就被拒；上傳時要和 `Content-Length` 相同 |
| `media_type` | 字串 | 檔案實際的型別，最長 255 個字元。主檔的格式要是平台支援的（pilot 只有 `application/pdf`），否則宣告時就被拒。附件沒有限制型別，但平台會看檔案的 bytes：它認得的六種（PDF、PNG、JPEG、GIF、WebP、TIFF）必須和宣告相同，例如 JPEG 要寫 `image/jpeg`，寫 `image/jpg` 上傳時會被拒；它認不得的型別以宣告為準 |

排序方式與預設 Resource 是每個 Source 的設定，由平台設定（規格 §2）。規則的完整條文在規格 §6.1。

回應 `201`：

```json
{
  "batch_id": "bat_01J…",
  "state": "open",
  "expires_at": "2026-10-22T09:00:00Z",
  "items": [
    { "index": 0, "document_id": "hr:leave-policy", "document_uid": "doc_7f3…", "status": "declared",
      "uploads": [ { "path": "assets/flow.png", "method": "PUT", "url": "https://kp.example/v1/batches/bat_01J…/items/0/files/assets/flow.png" } ],
      "carried_over": ["policy.pdf"] }
  ]
}
```

要用的是 `batch_id`、每個 item 的 `status`，以及 `declared` 的 item 的 `uploads[]`。`uploads[]` 只列與上一版不同的檔案，其餘列在 `carried_over`，不必再傳；上例是重送，只有附件變了。item 的 `status`：

| `status` | 意思 | 接下來 |
|---|---|---|
| `declared` | 等上傳與 finalize | 上傳 `uploads[]` 的檔案，再 finalize。`uploads[]` 可能是空的（只拿掉了附件，留下的檔案都和上一版相同）：不用上傳，但仍然要 finalize |
| `unchanged` | 內容和最新版相同；`title`、`source_url`、`metadata` 已更新，`source_version` 較大時記下新的版本。平台不會再處理一次 | 結束。它不代表那一版處理成功：上一版被判定無法處理時，再送同樣的內容仍然是 `unchanged`。那一版的結果看 document 的 `attention` |
| `queued` | 同樣的內容已經有 request 在處理，或上一次是平台這一側失敗、現在重新排入；帶 `request_id` | 不用上傳也不用 finalize；用 `request_id` 查結果 |
| `rejected` | 被拒，帶 `error`（`reason` 與 `message`） | 修正後重新宣告 |

兩種情況不用上傳，也不用 finalize：

- 沒有任何 item 是 `declared`（例如全部 `unchanged`）：回應的 `state` 直接是 `finalized`。
- 每個 item 都被拒：回 `422 ALL_ITEMS_REJECTED`，不建立 batch；body 的 `items` 列出每個 item 的 `error`。

**2. 上傳**：對 `uploads[]` 的每個檔案發一次 `PUT`，可以並行。網址用 `uploads[]` 給的 `url`，不要自己組；回應裡不認得的欄位略過。

- `url` 已經做過 URL 編碼（`path` 有空白或中文時），原樣使用。
- `url` 的 origin 應該和 base URL 相同。不同的話不要把 credential 送過去，當成錯誤處理（規格 §5.1）。
- 每個 batch 的上傳是分開的。同一個檔案在另一個 batch 傳過不算數，照這個 batch 的 `uploads[]` 再傳一次。

```sh
curl -X PUT "https://kp.example/v1/batches/bat_01J…/items/0/files/assets/flow.png" \
  -H "Authorization: Bearer $KP_TOKEN" \
  -H "Content-Type: image/png" \
  --data-binary @assets/flow.png
```

`curl` 會自動帶 `Content-Length`；自寫 client 時必須帶，且等於宣告的 `size`。`Content-Type` 可以帶宣告的 `media_type`，平台不檢查它的值，而是檢查檔案的 bytes（第 6.5 節）；`curl --data-binary` 沒指定時會帶 `application/x-www-form-urlencoded`，所以範例明確指定。成功回 `204`，沒有 body。

**3. finalize**

```sh
curl -X POST https://kp.example/v1/batches/bat_01J…/finalize \
  -H "Authorization: Bearer $KP_TOKEN"
```

回應 `202`，內容是這個 batch 與它的每個 item，和 `GET /v1/batches/{batch_id}` 同一個形狀；受理的 item 帶 `request_id` 與 `source_revision_id`，被拒的帶 `error`。節錄：

```json
{
  "batch_id": "bat_01J…", "state": "finalized",
  "items": [
    { "index": 0, "document_id": "hr:leave-policy", "document_uid": "doc_7f3…",
      "status": "queued", "request_id": "req_01J…", "source_revision_id": "srv_3" }
  ]
}
```

finalize 之後，每個 item 是三種結果之一：

| 結果 | 怎麼認 | 接下來 |
|---|---|---|
| 受理 | 帶 `request_id` | 記下 `request_id`，用它查結果。它可能是另一個 batch 已經為同樣內容建立的 request |
| 內容已是最新版 | `status` 是 `unchanged`，沒有 `request_id` | 結束。例如另一個 batch 先交了同樣的內容，而且已經處理完 |
| 被拒 | `status` 是 `rejected`，帶 `error` | 依第 5.3 節的原因表處理 |

判斷有沒有受理，看有沒有 `request_id`，不要比對 `status` 是不是 `queued`：重複呼叫 finalize 或之後查 batch 時，受理的 item 的 `status` 會跟著 request 變成 `processing`、`succeeded` 或 `failed`。

每個 item 都被拒時（例如唯一的 item 少了檔案），finalize 回的是 `422 ALL_ITEMS_REJECTED`，body 的 `items` 列出每個 item 的 `error`；這個 batch 已經結束，修正後要重新宣告。

**之後：查詢**

處理在背景進行。finalize 的回應裡，每個受理的 item 帶一個 `request_id`；用它查這一次提交的結果。

```sh
curl https://kp.example/v1/requests/req_01J… -H "Authorization: Bearer $KP_TOKEN"
```

回應（這個例子是內容被拒；每個欄位見第 5.6 節）：

```json
{
  "request_id": "req_01J…", "kind": "process", "state": "failed",
  "document_id": "hr:leave-policy", "document_uid": "doc_7f3…", "source_revision_id": "srv_3",
  "initiator": "source", "retry_of": null, "batch_id": "bat_01J…",
  "created_at": "2026-10-15T09:10:00Z", "updated_at": "2026-10-15T09:12:00Z",
  "terminal_at": "2026-10-15T09:12:00Z",
  "error": { "domain": "kp-canonicalization", "reason": "PASSWORD_REQUIRED",
             "message": "The PDF needs a password.", "retryable": false,
             "metadata": { "cause": "source", "category": "source" },
             "support_ref": "temporal:req_01J…/…", "occurred_at": "2026-10-15T09:12:00Z" },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "details": { "attempt_id": "…", "seq": 1, "stage": "prepare", "progress": null }
}
```

持續查詢，直到 `state` 是 `succeeded` 或 `failed`：

| `state` | 意思 | 接下來 |
|---|---|---|
| `queued` | 已受理，還沒開始處理。`202` 之後立刻查就是這個值 | 繼續查 |
| `processing` | 處理中 | 繼續查 |
| `succeeded` | 處理完成 | 結束。文件讀不讀得到，看 document 的 `readiness` |
| `failed`，且 `error.metadata.cause` 是 `source` | 這一版的內容無法處理，例如 PDF 有密碼 | 看 `error.reason` 與 `error.message`，修正檔案後重新宣告。`source_version` 可以沿用被拒的那一版，也可以用更大的 |
| `failed`，其他情況 | 平台這一側的失敗，平台的負責人會收到告警。`error.message` 是一句固定的英文，不帶原始的錯誤內容 | 檔案不用改。平台修復後，重新宣告相同的內容，那個 item 的 `status` 會是 `queued`，帶一個新的 `request_id`。回報問題時附上 `error.support_ref` |

- 查詢的間隔契約沒有規定。建議從幾秒開始，逐次拉長到 30 秒左右；這是建議，不是量測出來的值。
- 處理要多久沒有承諾值。尖峰時一份文件可能等到大約 25 分鐘才處理完（規格 §7.3 的估計，不是量測），所以輪詢的總時限要留得夠長。進行中的 request 不會過期。
- 查詢不扣進件配額；配額只算宣告的 item（第 5.4 節）。
- request 結束滿 30 天後回 `404`。

文件的現況用 `document_id` 查：

```sh
curl https://kp.example/v1/documents/hr:leave-policy -H "Authorization: Bearer $KP_TOKEN"
```

```json
{
  "document_id": "hr:leave-policy", "document_uid": "doc_7f3…", "resource_id": "hr-all",
  "title": "Leave policy", "source_url": "https://km.example/hr/leave-policy",
  "metadata": { "km_folder": "HR/Policies" },
  "readiness": "not_ready", "since": "2026-10-15T09:10:00Z",
  "latest": { "source_revision_id": "srv_3", "source_version": "3", "request_id": "req_01J…" },
  "serving": [],
  "attention": [
    { "kind": "source_revision_rejected", "action_owner": "source", "source_version": "3",
      "message": "The PDF needs a password.", "since": "2026-10-15T09:12:00Z" }
  ],
  "deleted_at": null
}
```

request 的 `succeeded` 只代表處理完成；文件是否可被讀到，看 `readiness`（規格 §7.1）：

| `readiness` | 意思 |
|---|---|
| `not_ready` | Source 要求的讀取端（projection，例如 Retrieval、LLM-Wiki）裡，還有一個沒有這份文件的任何版本；或平台沒有為這個 Source 設定任何讀取端 |
| `ready_stale` | 每個讀取端都有這份文件，但至少一個還是舊版 |
| `ready` | 每個讀取端都是最新版 |
| `deleted` | 已刪除 |

**現況（2026-11-22）：** 讀取端的回報接收已經完成（#252），但還沒有讀取端會送回報：要等 Canonical Acceptance 的記錄（#251）寫出 `current_revision_changed`，以及 consumer SDK 與 reference projection（#127），所以每份未刪除的文件仍是 `not_ready`，`serving` 是空陣列。在那之前，一次提交成功與否只看 request 的 `state`。之後新加進 Knowledge Profile 的讀取端，要等它回報補建完成才計入 `readiness`，在那之前它在 `serving` 的那一列是 `building`。讀取端寫入新的一版時，從它登記寫入到確認完成之間，文件會短暫是 `not_ready`（規格 §7.4）。規格還有 `withdrawn` 這個值，pilot 不會出現。

`attention` 列出需要有人處理的事，沒有就是空陣列。`action_owner` 是 `source` 時輪到 Source 處理：

| `kind` | `action_owner` | 意思 | Source 要做什麼 |
|---|---|---|---|
| `source_revision_rejected` | `source` | 最新的這一版內容無法處理 | 依 `message` 修正檔案，重新宣告 |
| `processing_failed` | `platform` | 平台這一側處理失敗，而且沒有進行中的 request。帶 `track`，說明是哪一段失敗 | 不用做事；要催的話附上 request 的 `error.support_ref` |
| `progress_stalled` | `platform` | 處理超過期限沒有回報進度 | 不用做事，平台會處理 |

讀取端也會帶來下面兩種，`track` 是讀取端的名稱（規格 §7.2）。`processing_failed` 與 `progress_stalled` 也可能來自讀取端，這時 `track` 是它的名稱，不是 `canonical`。`withdrawn` 在 pilot 不會出現。

| `kind` | `action_owner` | 意思 | Source 要做什麼 |
|---|---|---|---|
| `skipped` | `source` 或 `platform` | 讀取端略過這份文件。`source` 表示原因在內容 | `source`：依 `message` 修正；`platform`：不用做事 |
| `status_unverified` | `platform` | 讀取端一段時間沒有回報，平台無法確認它提供的狀態 | 不用做事，平台會處理 |

**刪除**

```sh
curl -X DELETE https://kp.example/v1/documents/hr:leave-policy -H "Authorization: Bearer $KP_TOKEN"
```

還沒實作（#98）；`dev` 上現在回 `405`。契約是：回應 `202` 與一個 `delete` 的 `request_id`，重複呼叫回同一個 request。刪除不能復原；內容在各讀取端清理完成（`enforced`）之後才不再被提供，階段與時限見規格 §8。

**每個回應都帶 `X-Trace-Id` header**，錯誤的 body 也帶 `trace_id`（規格 §4）。把它記進自己的 log，回報問題時附上。

### 5.3 錯誤與重試

| 回應 | 意思 | 處理 |
|---|---|---|
| `401 UNAUTHENTICATED`、`403 PERMISSION_DENIED` | credential 無效，或沒有這個操作需要的權限 | 修正 credential；不要重試 |
| `404 NOT_FOUND` | batch、item、path、request 或 document 不存在，或不屬於這個 Source | 上傳時檢查 `uploads[]`；不要重試 |
| `400 TOO_MANY_ITEMS`、`400 INVALID_ARGUMENT` | 宣告超過 50 個 item，或 body、參數不合格式 | 修正後重送 |
| `422 ALL_ITEMS_REJECTED` | 每個 item 都被拒。宣告時不建立 batch；finalize 時 batch 已經結束 | 看 body 的 `items` 裡每個 item 的 `error`，修正後重新宣告 |
| `422 IDEMPOTENCY_KEY_REUSED` | 同一個 `Idempotency-Key` 配了不同的 body | 新的宣告換一個 key |
| `400 SIZE_MISMATCH`、`411 LENGTH_REQUIRED` | 上傳：長度不符或缺 `Content-Length` | 修正後重送 |
| `422 DIGEST_MISMATCH`、`422 MEDIA_TYPE_MISMATCH` | 上傳：內容與宣告不符 | 檢查檔案；需要時重新宣告 |
| `409 BATCH_EXPIRED`（上傳、finalize）、`409 BATCH_FINALIZED`（上傳） | batch 已過期，或已經 finalize 還在上傳。重複呼叫 finalize 不會得到 `409 BATCH_FINALIZED`，它回原本的結果 | 重新宣告 |
| `429 RATE_LIMITED`、`503 ADMISSION_PAUSED`、`503 AUTHZ_UNAVAILABLE`、`503 UNAVAILABLE` | 超過配額、平台暫停受理（只擋宣告）、授權服務或資料庫、storage 暫時不可用 | 依 `Retry-After`（秒）重試。重試宣告時沿用同一個 `Idempotency-Key`。要重試幾次契約沒有規定 |
| 連線錯誤、逾時 | 傳輸中斷 | 重送整個 `PUT`；finalize 可重複呼叫 |

上表是整個 request 的結果。宣告與 finalize 另外對每個 item 給結果：被拒的 item 在回應裡帶 `error`（`reason` 與 `message`），其他 item 不受影響。全部的原因在下表。規則的條文在規格 §6；和 Resource 有關的處理方式在授權指南 §3.2。

item 被拒的原因（`error.reason`）。「階段」是它出現在宣告還是 finalize 的回應：

| `reason` | 階段 | 意思 | 處理 |
|---|---|---|---|
| `INVALID_ARGUMENT` | 兩者 | item 的欄位不合規則：`document_id` 的字元或長度、同一個 request 裡重複的 `document_id`、不是恰好一個 `main` 檔、`path` 重複或含 `..`、`sha256` 不是 64 個十六進位字元、`resources` 不是恰好一個、`source_version` 或 `metadata` 的格式；或 `source_version` 的種類（整數、時間）和上一版不同 | 依 `message` 修正 |
| `FILE_TOO_LARGE` | 宣告 | 有檔案超過單檔上限 | 這個檔案交不了；上限見第 5.4 節 |
| `UNSUPPORTED_FORMAT` | 兩者 | 主檔的 `media_type` 沒有可用的處理方法；pilot 只收 `application/pdf` | 換成支援的格式 |
| `SOURCE_VERSION_REQUIRED` | 宣告 | 這個 Source 依版本排序，item 卻沒有 `source_version` | 補上 `source_version` |
| `RESOURCE_REQUIRED` | 宣告 | 新文件沒有填 `resources`，Source 也沒有預設的 Resource | 補上 `resources` |
| `RESOURCE_NOT_FOUND` | 兩者 | `resources` 的 key 沒有登記，或在宣告之後被刪除 | 先 `PUT /v1/resources/{key}` 再宣告 |
| `BINDING_CONFLICT` | 宣告 | 既有的文件宣告了另一個 Resource | 省略 `resources`，或填原本的 key。把文件移到另一個 Resource 還沒有做（#205） |
| `STALE_SOURCE_VERSION` | 兩者 | `source_version` 比最新版記下的 `source_version` 小 | 這一版已經過時，不用再送 |
| `VERSION_CONFLICT` | 兩者 | `source_version` 和上一版相同，內容卻不同，而且上一版沒有被判定無法處理 | 內容真的變了就用更大的 `source_version` |
| `FILES_MISSING` | finalize | `uploads[]` 裡有檔案沒有上傳成功 | 重新宣告、上傳、finalize |
| `STALE_DECLARATION` | finalize | 宣告之後，另一個 batch 先建立了同一個 `document_id` 的文件 | 重新宣告 |
| `DOCUMENT_DELETED` | finalize | 宣告之後，文件被刪除了 | 還要交的話重新宣告；它會是一份新的文件 |

整個 request 失敗時的 body（規格 §4）；程式判斷用 `details[].reason`，回報問題附上 `trace_id`：

```json
{
  "error": {
    "code": 409,
    "status": "FAILED_PRECONDITION",
    "message": "The batch expired at 2026-10-22T09:00:00Z.",
    "details": [
      { "@type": "type.googleapis.com/google.rpc.ErrorInfo",
        "reason": "BATCH_EXPIRED", "domain": "admission.knowledge-platform",
        "metadata": { "batch_id": "bat_01J…" } }
    ]
  },
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
}
```

- 同一個 HTTP 狀態碼底下，`error.status` 不一定相同；判斷只用 `details[0].reason`。
- `ALL_ITEMS_REJECTED` 的 body 在 `error` 與 `trace_id` 之外多一個 `items`，每筆有 `index`、`document_id`、`status`（`rejected`）與 `error`：

  ```json
  {
    "error": { "code": 422, "status": "FAILED_PRECONDITION", "message": "Every item is rejected.",
               "details": [ { "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                              "reason": "ALL_ITEMS_REJECTED", "domain": "admission.knowledge-platform" } ] },
    "trace_id": "060e919ac53a497e8272beccd846e7c1",
    "items": [ { "index": 0, "document_id": "hr:leave-policy", "status": "rejected",
                 "error": { "reason": "RESOURCE_NOT_FOUND", "message": "The Source registered no Resource with this key." } } ]
  }
  ```

- 三種回應的 body 不是這個格式：網址打錯、沒有這個路由的 `404`，method 不對的 `405`，未預期的 `500`。它們同樣帶 `X-Trace-Id` header。

### 5.4 限制

| 項目 | 值 | 出處 |
|---|---|---|
| 每次宣告的 item 數 | 50（暫定） | 規格 §11 |
| 每個 Source 的進件配額 | token bucket：最多 50 個宣告 item，每分鐘補回 50（暫定） | 規格 §11 |
| 單檔大小上限 | 50 MB，部署可調 | 規格 §11、#88 |
| 上傳方式 | 每檔一個 `PUT`，單一 request；無分段、無續傳 | 規格 §5.2 |
| batch 有效期 | 建立後 24 小時 | 規格 §11 |
| `Idempotency-Key` | 最長 255 字元；24 小時內同一 key 回同一結果，前一次還在處理時等它 commit | 規格 §5.1、§11 |
| `document_id` | 1 到 256 個字元，`[A-Za-z0-9-_.~:]`，區分大小寫；不能含 `/` | 規格 §11 |
| Resource 的 key | 1 到 200 個字元，區分大小寫 | 授權指南 §4.7 |
| `metadata` | 最多 50 個 key；key 是 1 到 64 個字元的 `[A-Za-z0-9_.-]`；值是最長 512 個字元的字串；總共 8 KB | 規格 §11 |

### 5.5 SDK 與實務建議

- 設計筆記 Q4 要求 SDK 把三個呼叫包成一個操作；最小的 Python SDK 是 [`kp_sdk`](../../src/kp_sdk/__init__.py)（#194）：`Client(base_url, credential).submit(items)`。item 照規格 §5.1 寫，只是每個檔案用 `local`（本機路徑）取代 `sha256` 與 `size`，SDK 自己算、宣告、照 `uploads[]` 的 `url` 依序上傳、再 finalize。`429`、`503` 依 `Retry-After` 重試；其他失敗丟出 `PlatformError`，帶 `trace_id`，每個 item 都被拒時另帶各 item 的結果（`items`）。上傳被拒時 batch 維持 open，24 小時後過期，修正後重新呼叫 `submit` 即可。上傳網址的 origin 和呼叫的不同時，它不送 credential，直接丟出例外（規格 §5.1）。
- 宣告前先算好每個檔案的 SHA-256 與大小；宣告後只傳 `uploads[]` 列出的檔案。
- 多個檔案並行上傳；全部收到 `204` 再 finalize。
- 同一次宣告的重送（逾時、連線中斷）用同一個 `Idempotency-Key`；修正之後重新宣告要換一個 key。上傳與 finalize 本身可重複，不需要 key。
- 大量提交時依 50 item／分鐘的配額排程；收到 `429` 就依 `Retry-After` 等待。
- 不要在 log 裡記 credential；診斷資訊用回應的 `X-Trace-Id`。

### 5.6 API 參考：每個呼叫的欄位

第 5.2 節照順序說明怎麼用，這一節用來查表。內容依規格 §4、§5；回應的欄位另外對 `dev` 上的 `api` 實際跑過一次核對（2026-11-20，真的資料庫與物件儲存）。規格是契約，兩者不一致時以規格為準。

**通則**

| 項目 | 規則 |
|---|---|
| 驗證 | 每個呼叫帶 `Authorization: Bearer <Source credential>`。沒帶，或平台不認得，回 `401`；credential 沒有這個操作需要的權限，回 `403` |
| 格式 | request 與回應的 body 是 JSON（上傳除外），欄位用 snake_case |
| 時間 | UTC 的 RFC 3339 字串，例如 `2026-11-20T08:02:00Z`；小數秒的位數不固定 |
| ID | `bat_…`、`req_…`、`doc_…`、`srv_…` 是不透明的字串，不要解析 |
| 沒有值的欄位 | 宣告、finalize 與 batch 的回應裡，沒有值的欄位不出現；request 與 document 的回應裡是 `null` |
| 不認得的欄位 | 略過。之後的版本可能新增欄位 |
| 追蹤 | 每個回應帶 `X-Trace-Id` header。可以自己送 `traceparent` header（W3C Trace Context），平台沿用它的 trace id |
| 分頁 | `page_size`、`page_token`、`next_page_token`（AIP-158）。`next_page_token` 是空字串，表示這是最後一頁 |
| 看不到的東西 | 不屬於這個 Source 的 batch、request、document 一律回 `404`，和不存在一樣 |
| 重試 | `429` 與 `503` 帶 `Retry-After`（秒） |

**登記 Resource：`PUT /v1/resources/{key}`**

需要 `manage_relations`。列出、取得與刪除見授權指南 §4.7。

| 位置 | 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| 路徑 | `key` | 字串 | 是 | 1 到 200 個字元；含 `/` 時寫成 `%2F` |
| body | `name` | 字串 | 否 | 顯示用的名稱，最多 200 個字元。body 可以整個省略 |

回應：第一次 `201`，重複呼叫 `200`。

| 欄位 | 型別 | 說明 |
|---|---|---|
| `key` | 字串 | 登記的 key |
| `name` | 字串 | 有設定才出現 |
| `created_at` | 時間 | 第一次登記的時間 |
| `change_id` | 字串 | 只在第一次（`201`）出現 |

**宣告：`POST /v1/batches`**

需要 `submit`。

| 位置 | 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|---|
| header | `Idempotency-Key` | 字串 | 否 | 最長 255 個字元。24 小時內同一個 key 配同一個 body，回原本的回應；配不同的 body 回 `422 IDEMPOTENCY_KEY_REUSED` |
| header | `Content-Type` | | 是 | `application/json` |
| body | `items` | 陣列 | 是 | 1 到 50 個 item；每個 item 的欄位見第 5.2 節的表 |

回應 `201`：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `batch_id` | 字串 | 上傳、finalize 與查詢這個 batch 都用它 |
| `state` | 字串 | `open`：等上傳與 finalize。`finalized`：沒有任何 item 需要上傳，這個 batch 已經結束，不用再 finalize |
| `expires_at` | 時間 | 在這之前要 finalize；建立後 24 小時 |
| `items` | 陣列 | 和 request 的 `items` 同樣的順序，每個 item 一筆 |

`items` 的每一筆：

| 欄位 | 型別 | 什麼時候出現 | 說明 |
|---|---|---|---|
| `index` | 整數 | 一定有 | 這個 item 在 request 裡的位置，從 0 開始；上傳網址裡的 `{index}` |
| `document_id` | 字串 | 一定有 | 宣告時給的值 |
| `document_uid` | 字串 | 被拒的 item 沒有 | 平台給這份文件的 ID。文件刪除後再提交同一個 `document_id`，會是新的 `document_uid` |
| `status` | 字串 | 一定有 | `declared`、`unchanged`、`queued`、`rejected`（第 5.2 節） |
| `uploads` | 陣列 | `declared` | 要上傳的檔案，每筆有 `path`、`method`（固定是 `PUT`）與 `url`。只列和上一版不同的檔案 |
| `carried_over` | 字串的陣列 | `declared` | 和上一版相同、不用上傳的檔案的 `path` |
| `request_id` | 字串 | `queued` | 已經在處理同樣內容的 request，或平台失敗後重新排入的 request |
| `error` | 物件 | `rejected` | `reason` 與 `message`；原因見第 5.3 節 |

整個 request 的失敗：`400 INVALID_ARGUMENT`、`400 TOO_MANY_ITEMS`、`401`、`403`、`422 ALL_ITEMS_REJECTED`（不建立 batch；body 的 `items` 列出每個 item 的結果）、`422 IDEMPOTENCY_KEY_REUSED`、`429 RATE_LIMITED`、`503`（`ADMISSION_PAUSED`、`AUTHZ_UNAVAILABLE`、`UNAVAILABLE`）。`429` 與 `503` 不會記在 `Idempotency-Key` 底下，用同一個 key 重試即可；`422 ALL_ITEMS_REJECTED` 會，同一個 key 與 body 再送一次拿到同樣的 `422`。

**上傳：`PUT /v1/batches/{batch_id}/items/{index}/files/{path}`**

需要 `submit`。網址直接用 `uploads[]` 的 `url`，不要自己組。

| 位置 | 欄位 | 必填 | 說明 |
|---|---|---|---|
| header | `Content-Length` | 是 | 要等於宣告的 `size`。沒帶回 `411 LENGTH_REQUIRED` |
| header | `Content-Type` | 否 | 可以帶宣告的 `media_type`；平台不檢查它，檢查的是檔案的 bytes |
| body | 檔案的 bytes | 是 | 一個 request 傳完整個檔案。不用 multipart form，不用 chunked encoding，不能續傳 |

| 結果 | 回應 |
|---|---|
| 大小、SHA-256 與偵測到的型別都和宣告相同 | `204`，沒有 body |
| 大小不符 | `400 SIZE_MISMATCH`，不留檔 |
| SHA-256 不符 | `422 DIGEST_MISMATCH`，不留檔 |
| 偵測到的型別不符 | `422 MEDIA_TYPE_MISMATCH`，不留檔 |
| 這個 path 不在 `uploads[]`（包含 `carried_over` 的檔案），或 batch、item 不存在 | `404` |
| batch 已 finalize、已過期 | `409 BATCH_FINALIZED`、`409 BATCH_EXPIRED` |
| storage 或資料庫沒有回應 | `503 UNAVAILABLE`；重送整個 `PUT` |

同一個檔案重複 `PUT` 回 `204`，沒有變化。

**finalize：`POST /v1/batches/{batch_id}/finalize`**

需要 `submit`。沒有 body。回應 `202`，內容和下面的 `GET /v1/batches/{batch_id}` 相同。重複呼叫回同一份結果。

| 結果 | 回應 |
|---|---|
| 至少一個 item 沒有被拒 | `202`；受理的 item 帶 `request_id`，內容已是最新版的是 `unchanged`，被拒的帶 `error` |
| 每個 item 都被拒（例如唯一的 item 少了檔案） | `422 ALL_ITEMS_REJECTED`，body 的 `items` 列出每個 item 的 `error`。batch 已經結束，修正後要重新宣告 |
| batch 已過期 | `409 BATCH_EXPIRED` |
| storage 無法確認檔案是否就位，或授權服務、資料庫沒有回應 | `503`；batch 維持 `open`，稍後重試 |

**查 batch：`GET /v1/batches/{batch_id}`**

需要 `submit`。回應 `200`：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `batch_id` | 字串 | |
| `state` | 字串 | `open`、`finalized`、`expired` |
| `created_at`、`expires_at` | 時間 | |
| `finalized_at` | 時間 | finalize 之後才出現 |
| `counts` | 物件 | 每種 `status` 有幾個 item，例如 `{"succeeded": 1, "rejected": 1}` |
| `items` | 陣列 | 每個 item 一筆，見下表。一個 batch 最多 50 個 item，一次回完 |
| `next_page_token` | 字串 | 空字串 |

`items` 的每一筆：`index`、`document_id`、`document_uid`（被拒的 item 可能沒有）、`status`、`request_id` 與 `source_revision_id`（受理的 item 才有）、`error`（被拒的 item 才有）。

`status` 的值：還沒 finalize 是 `declared`；沒 finalize 就過期是 `expired`；宣告或 finalize 時定案的是 `unchanged`、`rejected`；受理之後跟著 request 走，依序是 `queued`、`processing`、`succeeded` 或 `failed`。

**查 request：`GET /v1/requests/{request_id}`**

需要 `submit`。回應 `200`：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `request_id` | 字串 | |
| `kind` | 字串 | `process`（處理一個版本）。`delete` 是刪除的 request，還沒實作（#98） |
| `state` | 字串 | `process`：`queued`、`processing`、`succeeded`、`failed`。`delete`：`received`、`applied`、`enforced` |
| `document_id`、`document_uid` | 字串 | 這個 request 屬於哪份文件 |
| `source_revision_id` | 字串 | 處理的是哪個版本 |
| `initiator` | 字串 | `source`：Source 的提交。`operator`：平台人員重送。`platform`：平台因為處理方法更新而重跑 |
| `retry_of` | 字串或 `null` | 平台失敗後重新排入時，前一個失敗的 `request_id` |
| `batch_id` | 字串或 `null` | 建立這個 request 的 batch |
| `created_at`、`updated_at` | 時間 | |
| `terminal_at` | 時間或 `null` | 結束的時間；還沒結束是 `null` |
| `error` | 物件或 `null` | 失敗時才有，見下表 |
| `trace_id` | 字串 | 建立這個 request 的那次呼叫的 trace id |
| `details` | 物件或 `null` | 處理端最後回報的位置（`attempt_id`、`seq`、`stage`、`progress`）。給平台除錯用，不要拿來判斷狀態 |

`error` 的欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `domain` | 字串 | 哪個元件回報的，例如 `kp-canonicalization` |
| `reason` | 字串 | 原因代碼，例如 `PASSWORD_REQUIRED`。由處理端定義，之後會增加，本文不列清單；程式決定下一步只看 `metadata.cause` |
| `message` | 字串 | 英文說明。平台原因的失敗是固定的一句話 |
| `retryable` | 布林 | 處理端標示這個失敗重試有沒有可能成功。Source 要不要重送看 `metadata.cause`，不看這個值 |
| `metadata` | 物件 | `cause` 是 `source` 表示要 Source 修正內容。其他值、沒有 `cause` 或沒有 `metadata`，都當成平台這一側的原因。其他的 key 給平台用 |
| `support_ref` | 字串 | 回報問題時附上，平台用它找到那一次執行。不一定有 |
| `occurred_at` | 時間 | 不一定有 |

`404`：request 不存在、屬於別的 Source，或結束已滿 30 天。

**查文件：`GET /v1/documents/{document_id}`**

需要 `submit`。回應 `200`：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `document_id` | 字串 | Source 自己的文件代號 |
| `document_uid` | 字串 | 平台給這份文件的 ID |
| `resource_id` | 字串 | 文件所在的 Resource，值是 Source 登記的 key |
| `title`、`source_url` | 字串或 `null` | 宣告時給的目錄資訊 |
| `metadata` | 物件或 `null` | 宣告時給的 `metadata` |
| `readiness` | 字串 | `not_ready`、`ready_stale`、`ready`、`deleted`（第 5.2 節） |
| `since` | 時間 | `readiness` 從什麼時候開始是現在這個值。刪除的文件是刪除的時間；還沒變過的是文件建立的時間 |
| `latest` | 物件 | 最後受理的版本：`source_revision_id`、`source_version`，以及它最新的 `request_id`（不算平台自己的重跑）。同樣的檔案用較大的 `source_version` 再送，`source_version` 會變成新的版本，`source_revision_id` 不變 |
| `serving` | 陣列 | 每個讀取端在提供哪一版，每筆有 `projection`、`state`（`ready`、`building`、`stale`）、`source_revision_id`、`source_version`。`source_version` 是那一版目前記下的版本，所以 `source_revision_id` 和 `latest` 的相同時，讀取端提供的就是最新的內容。沒有在提供這份文件的讀取端不列出 |
| `attention` | 陣列 | 需要有人處理的事，每筆有 `kind`、`action_owner`、`source_version`（最新版記下的版本）、`message`、`since`；`processing_failed`、`progress_stalled`、`status_unverified`、`skipped` 另外帶 `track`。沒有就是空陣列 |
| `deleted_at` | 時間或 `null` | 刪除的時間 |

文件刪除後又提交同一個 `document_id` 時，回的是現存的那一份；全部都刪除時，回最後刪除的那一份，`readiness` 是 `deleted`。`404`：這個 Source 沒有這份文件。

**列出文件：`GET /v1/documents`**

需要 `submit`。

| query 參數 | 必填 | 說明 |
|---|---|---|
| `resource_id` | 否 | 只列這個 Resource（key）裡的文件 |
| `readiness` | 否 | 只列這個 `readiness` 的文件；值不合法回 `400` |
| `projection` | 否 | 只列這個讀取端正在提供的文件 |
| `page_size` | 否 | 省略、`0` 或超過 1000 時是 1000 |
| `page_token` | 否 | 上一頁的 `next_page_token`；不是這個列表給的值回 `400` |

回應 `200`：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `documents` | 陣列 | 每筆有 `document_id`、`document_uid`、`latest.source_version`、`readiness`、`metadata`。依 `document_id` 排序 |
| `next_page_token` | 字串 | 空字串表示最後一頁 |

- 刪除未滿 30 天的文件也會列出，`readiness` 是 `deleted`；用它和自己的清單對帳。
- `readiness` 與 `projection` 是讀完一頁之後才篩選的，所以一頁可能少於 `page_size` 筆，甚至是空的，後面卻還有。要一直讀到 `next_page_token` 是空字串，只讀第一頁會漏資料。

**刪除文件：`DELETE /v1/documents/{document_id}`**

還沒實作（#98）；`dev` 上現在回 `405`。契約是回 `202` 與 `{ "request_id": "req_…", "kind": "delete", "state": "received" }`，重複呼叫回同一個 request（規格 §5.8、§8）。

## 6. 部署與維運需求

DevOps 要準備的東西。數值與設定名稱多數還是暫定的，由 [#78](https://github.com/davidlinnnn/data-ingestion/issues/78) 定案。admission 用自己的 image，不帶 PDF 解析與推論的套件（[2026-11-11 的裁決](https://github.com/davidlinnnn/data-ingestion/issues/78#issuecomment-6792552979)）；admission 還沒有 Dockerfile，程式邊界與依賴的拆分在 [#207](https://github.com/davidlinnnn/data-ingestion/issues/207)。

| 項目 | 需求 | 細節在哪 |
|---|---|---|
| 角色 | 一個 image，三種角色：`api`（固定 2 個副本，不用 HPA）、`dispatcher`（至少 2 個副本）、CronJob（reconciler 每 5 分鐘；batch 過期與上傳清理每小時；保留期每天） | 規格 §13；第 6.1、6.3 節 |
| 指令 | 已有：`kp-admission api`、`dispatcher`、`reconcile`（跑一次就結束，CronJob 每 5 分鐘）、`expire`（把逾期的 batch 標為過期，再清理結束滿一小時的 batch 的上傳，跑一次就結束，CronJob 每小時；要物件儲存的設定）、`feed-retention`（CronJob 每天，見下一列）、`set-profile`（設定 Source 要求的 projection）、`adopt` 與 `cancel-adoption`（設定某個檔案格式用哪個 Processing Profile 版本）。第一次宣告之前要先採用 PDF 的版本：`kp-admission adopt --tenant <tenant> application/pdf paper-pdf@1`，否則每個宣告都是 `UNSUPPORTED_FORMAT`（規格 §3）。順序是：profile 版本已 release、processing worker 已部署、`adopt`、第一次宣告；`adopt` 不檢查這個版本存不存在。還沒有：redrive 與 refresh（#98）、規格 §11 的紀錄保留期（#250） | [`kp_admission/cli.py`](../../src/kp_admission/cli.py) |
| Admission DB | pilot：一個 PostgreSQL instance，放在網路磁碟的 persistent volume，不用 operator；WAL 連續歸檔，加上排程的 base backup，都放到物件儲存。版本要 17 以上；`api` 的資料庫角色要 `pg_read_all_stats`。`feed-retention` 要每天跑：它刪掉超過 90 天的 Change Feed，也預先建立之後幾個月的分區，長期沒跑的話 admission 的寫入會失敗。目前沒有套用 schema 的指令：資料表定義在 [`schema.sql`](../../src/kp_admission/schema.sql)，整份套用在空的資料庫，由誰套用、用哪個 migration 工具由 #78 決定。PROD release 之前移到公司代管的 MongoDB | 規格 §9、§13；[#137 的交接](https://github.com/davidlinnnn/data-ingestion/issues/137#issuecomment-6983041476)；第 3 節；#239 |
| 物件儲存 | S3 相容，一個 bucket，原始檔與處理結果共用。`api` 現在要 `s3:GetObject`（finalize 用 HeadObject 確認檔案已就位）與 `s3:ListBucket` 的權限：少了 `s3:ListBucket`，storage 對不存在的物件回 `403` 而不是 `404`（[AWS HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html)），finalize 會一直回 `503`。上傳另外要 `s3:PutObject` 與 `s3:AbortMultipartUpload`；`expire` 的 CronJob 要 `s3:DeleteObject`、`s3:AbortMultipartUpload` 與 `s3:ListBucketMultipartUploads`。少了任何一項，上傳會一直回 `503`，清理則每次都把 batch 留給下一次，並以 exit code 1 結束。processing worker 要讀寫。必要的行為用 `storage_probe.py` 驗證 | 規格 §10；第 6.3、6.7 節；產品由 #57 決定 |
| Temporal | `dispatcher` 與 `reconcile` 要連得到：`TEMPORAL_ADDRESS`、`TEMPORAL_NAMESPACE`。`api` 不連 Temporal，所以 Temporal 停機時照常受理，outbox 裡的 request 等它恢復 | 規格 §9 |
| 路由 | 對外只開放 `/v1/`。`/authz/`、`/read/`、`/report/`（處理端回報狀態）、`/healthz`、`/openapi.json` 與 metrics 不對外。上傳路徑要另外放寬 | 授權指南 §6.1；第 6.2 節 |
| Mesh sidecar | CronJob 的 pod 可能因為 sidecar 不會自己退出而無法結束：確認是否啟用 native sidecar，沒有的話關閉注入，或在結束時停止 proxy。應用程式可能比 proxy 先啟動：`api` 會自行重連資料庫；`dispatcher` 啟動時連不上資料庫，或執行中斷了資料庫連線，會結束，由 Kubernetes 重啟。`dispatcher` 連不上 Temporal 不會結束，outbox 的 request 等它恢復。`api` 收到 SIGTERM 會先處理完進行中的 request，結束碼是 143 | [#78 的交接](https://github.com/davidlinnnn/data-ingestion/issues/78#issuecomment-6854292201)；第 6.2 節 |
| 設定 | 環境變數。每個角色都要 `KP_ADMISSION_DATABASE_URL`，缺了就以 exit code 2 結束。`api` 另外必填：`KP_AUTHZ_PROVIDER=allow-all`、`KP_DEPLOYMENT=pilot`、`KP_ADMISSION_PUBLIC_URL`（Source 經 ingress 呼叫的 https origin，例如 `https://kp.example`；`uploads[].url` 用它組成，不依賴 ingress 轉送的 header。只接受 `https`、不帶路徑，DEV 也一樣），以及物件儲存的 `KP_S3_ENDPOINT`、`KP_S3_BUCKET`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`；缺一個就不啟動。`api` 的其他設定：`KP_CREDENTIALS`（每個 Source credential 的 SHA-256 與權限）、`KP_AUTHZ_PEP_CREDENTIALS`（讀取端的憑證）、`KP_PIPELINES`（回報者憑證的 SHA-256 與它登記的 pipeline；沒設時 `api` 照常啟動，但每筆回報都是 `401`，規格 §7.3）、`KP_SOURCES`（每個 Source 的排序方式與預設 Resource）、`KP_MAX_FILE_SIZE`（bytes；預設是規格 §11 的 50 MB 上限，程式用 50 × 2²⁰ bytes）、`KP_PAUSE_BACKLOG`、`KP_ADMISSION_API_PORT`（預設 8080）、`AWS_REGION`（預設 `us-east-1`）。`expire` 也要物件儲存的四個設定。canonical processing 的 orchestration worker 另外要 `KP_ADMISSION_URL`（`api` 的叢集內位址）與 `KP_ADMISSION_TOKEN`（回報用的憑證，從 Secret 掛載）。改了要重啟 pod | 授權指南 §6.2；[`kp_admission/cli.py`](../../src/kp_admission/cli.py) |
| 健康檢查、metrics、log | `api` 的 `GET /healthz` 用 HTTP probe，並用 `--metrics-port` 開 metrics；`dispatcher` 還沒有 HTTP 端點與 metrics（#189）。log 是 JSON、寫到 stderr，`api` 的每一行帶 `trace_id` | 授權指南 §6.3、§6.6；第 6.4 節 |
| 上線前的驗證 | pilot 前跑叢集層驗證：資料庫故障三案、終止 pod、Temporal 停機、容量 | 第 6.6 節；規格 §13；#99 |

### 6.1 Admission API

- 上傳端點串流處理：每收到一段（8 MiB）就以分段上傳寫入 storage，同時累計 SHA-256 與 bytes；超過宣告大小立即中斷。每個上傳佔用的記憶體是一段的大小，與檔案大小無關；同時 20 個上傳約 160 MiB。
- 上傳與控制 API 同一個 `api` 角色、同一個 image。固定 2 個副本，不用 HPA（2026-11-13 起，依公司慣例，見規格 §13）；server 用 async 框架（FastAPI），每個副本一個 uvicorn worker，慢連線不阻塞其他 request。寫入 storage 的 boto3 是同步呼叫，要放到執行緒執行，否則會卡住同一個副本的所有 request。之後若要隔離上傳流量，把上傳路徑拆成獨立 Deployment，契約不變。

### 6.2 Ingress

ingress-nginx 的預設值是為小 request 設的，上傳路徑要另外設定；公司的 ingress 不一定是 nginx，但同類設定都有，由 #78 定值。

| 設定 | ingress-nginx 預設 | 上傳路徑需要 |
|---|---|---|
| `proxy-body-size` | 1m | 不小於單檔上限，或對上傳路徑不設限。上限預設是 50 × 2²⁰ = 52,428,800 bytes；設成 50,000,000 會擋掉平台已經接受宣告的檔案 |
| `proxy-request-buffering` | on | off：直接轉送，不先把整個 body 收在 ingress |
| `proxy-read-timeout`、`proxy-send-timeout` | 60 秒 | 放寬到幾分鐘；50 MB 在 10 Mbps 約需 40 秒 |

pod 帶 mesh sidecar 時，body 上限、不先緩衝與 timeout 在 sidecar 那一層也要成立，同樣由 #78 定值。

另外兩件事在 ingress 與 sidecar 都要成立：

- 上傳的 `Content-Length` 要原樣送到 `api`。中間的 proxy 把 body 改成 chunked 的話，每個上傳都會得到 `411`。
- 不要改寫路徑。Resource 的 key 與檔案的 `path` 會帶 `%2F`、空白與非 ASCII 字元的編碼；平台的路由接受解碼後的 `/`，所以 proxy 解不解碼都可以，但不能合併重複的斜線或刪掉路徑的段落。

### 6.3 未受理的檔案與清理

- 每小時的 CronJob 清除兩種殘留（規格 §6.2、§13）：沒建立 Source Revision 的 item 所上傳的物件（被拒、過期，或 finalize 時內容和最新版相同），以及沒完成的分段上傳。已受理 item 的物件不刪。
- 只處理 finalize 或過期已滿 1 小時的 batch，讓當時還在傳的上傳先結束；目標是 batch 結束後 2 小時內清完（規格 §11，未量測）。
- 清理用資料庫紀錄算出完整的 key，逐一刪除與中止，不靠 storage 的 lifecycle 規則，也不靠列出前綴：AIStor 不支援中止未完成上傳的 lifecycle 動作，列出未完成的上傳時要給完整的物件名稱（[AIStor S3 API compatibility](https://docs.min.io/aistor/developers/s3-api-compatibility/)）。
- 容量估算：未受理的檔案和已受理的在同一個 bucket，最多保存到過期後 2 小時，一次 burst 約 10 GB。這是正常情況的估算，不是上限：上限取決於每個 Source 能同時開啟的 batch 數，這個值還沒定（規格 §11）。

### 6.4 指標與告警

- 上傳 request 數與結果分布（`204`、`400`、`422`、`409`、中斷）、bytes、上傳時長分布、同時上傳數。
- 等待清理的 batch 數與清理數；上傳失敗率與等待清理的 batch 數設告警。
- 這些併入 #78 的可觀測性清單；量測在 #99。dispatcher 與 reconciler 的 metrics 在 [#189](https://github.com/davidlinnnn/data-ingestion/issues/189)。

### 6.5 安全

- 只走 TLS；credential 與上傳 body 不進 log（資料安全文件 D3）。
- 檔案型別不看副檔名，也不看 `Content-Type`，看檔案的 bytes。平台偵測得到的六種型別（`application/pdf`、`image/png`、`image/jpeg`、`image/gif`、`image/webp`、`image/tiff`）必須和宣告相同；偵測不到的型別（例如 `text/markdown`）以宣告為準，除非檔案開頭是偵測得到的型別（規格 §5.2，2026-11-19 使用者裁決）。所以宣告 `image/jpg` 的 JPEG 會被拒，要宣告 `image/jpeg`；開頭是 `%PDF-` 的純文字檔也會被拒。主檔的 media type 決定走哪個 Processing Profile，沒有特徵的格式就照 Source 的宣告走。
- 文件內容的惡意 payload 與有害內容篩檢屬 #107、#108 的範圍，在受理後的 workflow 裡做，不在上傳端點。

### 6.6 驗證

#99 的叢集層驗證加上：PROD burst 經上傳路徑；上傳進行中殺掉 API pod，client 重送後無殘留、無重複；ingress 設定在單檔上限與慢線路下成立。

### 6.7 Storage 行為的依據（#184，2026-11-11）

設計依賴的行為都列在「必要」；公司的 storage 用 [`storage_probe.py`](../validation/184/storage_probe.py) 重跑，缺一項就不能用（#137）。本機實測的三套是 RustFS 1.0.4、MinIO 社群版 RELEASE.2025-09-07、SeaweedFS 4.50。

| | 行為 | 官方文件 | RustFS | MinIO | SeaweedFS |
|---|---|---|---|---|---|
| 必要 | 分段上傳在完成之前，物件查不到也列不出來 | — | 是 | 是 | 是 |
| 必要 | 未完成的上傳用完整的 key 列得出來 | [ListMultipartUploads](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListMultipartUploads.html) | 是 | 是 | 是 |
| 必要 | 中止的上傳不能再完成，也不留物件 | — | 是 | 是 | 是 |
| 必要 | 刪除不存在的 key 回成功 | — | 是 | 是 | 是 |
| 不依賴 | 未完成的上傳用資料夾前綴列得出來 | [AIStor](https://docs.min.io/aistor/developers/s3-api-compatibility/)：要給完整的物件名稱 | 是 | 否 | 是 |
| 不依賴 | 完成分段上傳時帶 `If-None-Match: *`，key 已存在就回 `412` | [AWS conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html) | 是 | 是 | 是 |
| 不依賴 | `CopyObject` 帶 `If-None-Match: *`，目的 key 已存在就回 `412` | [CopyObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html)（AWS 自 [2025-10-29](https://aws.amazon.com/about-aws/whats-new/2025/10/amazon-s3-conditional-write-functionality-copy-operations/) 起）；AIStor 列為支援 | 是 | 否：回 `200` 並覆蓋 | 是 |

- 儲存端複製和「不覆蓋既有物件」能不能同時成立，要看產品和版本；不支援的實作不報錯，直接覆蓋。這是上傳改成直接就位、finalize 不複製的原因之一（[ADR-0012](../adr/0012-uploads-written-at-custody-key.md)）。
- 一般 bucket 沒有原子的搬移，搬移就是先複製再刪除（[AWS：複製、搬移、改名物件](https://docs.aws.amazon.com/AmazonS3/latest/userguide/copy-object.html)）。
- 未完成的分段會一直佔空間，到期規則刪不掉，AWS 建議用 lifecycle 規則中止（[AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpu-abort-incomplete-mpu-lifecycle-config.html)）；AIStor 不支援這個 lifecycle 動作，所以由第 6.3 節的 CronJob 中止。

### 6.8 設定值的格式

第 6 節的表列出有哪些設定；這裡是四個 JSON 設定的格式。名稱都是暫定的，由 #78 定案。四個都只放 credential 的 SHA-256，不放 credential 本身：

```sh
printf '%s' "$TOKEN" | sha256sum    # 64 個小寫的十六進位字元；credential 不含結尾的換行
```

| 設定 | 誰讀 | 內容 |
|---|---|---|
| `KP_CREDENTIALS` | `api` | 每個 Source credential 是誰、有什麼權限 |
| `KP_SOURCES` | `api` | 每個 Source 的排序方式與預設 Resource；選填 |
| `KP_PIPELINES` | `api` | 哪些 credential 可以回報處理狀態 |
| `KP_AUTHZ_PEP_CREDENTIALS` | `api` | 哪些讀取端可以呼叫授權 API 與 `/read/`；格式在授權指南 §6.2 |

`KP_CREDENTIALS`：一個 Source 要交文件，至少要一筆有 `submit` 的；要登記 Resource，要一筆有 `manage_relations` 的。可以是同一筆。

```json
{
  "<km credential 的 SHA-256>": { "credential_id": "km-1", "tenant_id": "t1", "source_id": "km",
                                  "scopes": ["submit", "manage_relations"] }
}
```

- `tenant_id`：這套部署只有一個 tenant，所有 Source credential 都要相同。
- `credential_id`：不能重複；log 與變更紀錄用它識別 credential。
- 同一個 Source 放兩筆就能重疊輪替，拿掉一筆就是撤銷。

`KP_SOURCES`：沒列在裡面的 Source 依 `source_version` 排序，沒有預設 Resource。

```json
{
  "km":      { "ordering": "source_version", "default_resource_id": "inbox" },
  "scanner": { "ordering": "arrival" }
}
```

- `ordering`：`source_version`（Source 自己給版本，預設）或 `arrival`（依到達順序，item 不用填 `source_version`）。
- `default_resource_id`：新文件沒填 `resources` 時用的 key。Source 仍然要先登記這個 key。

`KP_PIPELINES`：canonical processing 的登記如下。兩個期限暫定各 1800 秒，等 #99 的叢集層量測。

```json
{
  "<回報用 credential 的 SHA-256>": {
    "pipeline_id": "kp-canonicalization", "track": "canonical",
    "stages": ["prepare", "parse", "enrich", "finalize"],
    "start_deadline_s": 1800, "update_interval_s": 1800
  }
}
```

- 同一把 credential 的原文放在 orchestration worker 的 `KP_ADMISSION_TOKEN`（從 Secret 掛載）。
- `stages` 要和 workflow 實際回報的階段相同、順序相同：最後一個階段回報成功，request 才算 `succeeded`。
- `start_deadline_s` 是派送後多久內要有第一筆回報，`update_interval_s` 是兩筆回報之間最長多久；超過就在文件的 `attention` 顯示 `progress_stalled`。
- 輪替時放兩筆，內容要完全相同；不同的話 `api` 不啟動。

讀取端（projection）也登記在 `KP_PIPELINES`，`track` 是它的名稱，和 `set-profile` 用的名稱相同，例如 `{"pipeline_id": "kp-retrieval", "track": "retrieval", ...}`（規格 §7.4）。

- 同一把 credential 也要登記在 `KP_AUTHZ_PEP_CREDENTIALS`，名稱相同：讀取端用它讀 Change Feed，也用它回報。
- 兩個 pipeline 不能用同一個 `track`，否則 `api` 不啟動。
- 讀取端的 `update_interval_s` 也是它的 Build 最久多久要回報一次：超過就在 `attention` 顯示 `status_unverified`，`kp_serving_builds_without_liveness` 也會計入。

四個設定共同的行為：

- 預設值是 `{}`。`KP_CREDENTIALS` 是 `{}` 時沒有任何 Source 能呼叫；`KP_PIPELINES` 是 `{}` 時 `api` 照常啟動，但每筆回報都是 `401`。
- 格式不對時，`api` 在 stderr 印出是哪個設定，以 exit code 2 結束。
- 程式不檢查 digest 寫得對不對。寫錯時 `api` 照常啟動，用那把 credential 的每個呼叫都是 `401`。
- 改了要重啟 pod。

其他設定的格式：

| 設定 | 誰讀 | 格式與行為 |
|---|---|---|
| `KP_ADMISSION_DATABASE_URL` | 每個角色與每個指令 | PostgreSQL 的連線字串（libpq 格式），例如 `postgresql://<user>:<password>@<host>:5432/<db>?sslmode=verify-full` |
| `TEMPORAL_ADDRESS`、`TEMPORAL_NAMESPACE` | `dispatcher`、`reconcile` | `host:port`（預設 `localhost:7233`）與 namespace（預設 `default`）。目前只有這兩個設定：連線不加密，也不帶憑證。Temporal 要求 TLS 或驗證的話要先改程式（第 7.1 節） |
| `KP_S3_ENDPOINT`、`KP_S3_BUCKET`、`AWS_ACCESS_KEY_ID`、`AWS_SECRET_ACCESS_KEY`、`AWS_REGION` | `api`、`expire` | endpoint 是含 scheme 的完整 URL，例如 `https://<host>:9000`；用 path-style 定址；region 預設 `us-east-1`。storage 連不上時 `api` 照常啟動，上傳與 finalize 回 `503` |
| `KP_ADMISSION_PUBLIC_URL` | `api` | Source 呼叫的 https origin，不帶路徑，例如 `https://kp.example` |
| `KP_MAX_FILE_SIZE` | `api` | bytes，預設 52,428,800 |
| `KP_PAUSE_BACKLOG` | `api` | 整數；不設就永不暫停。排隊中、一般優先序的處理 request 達到這個數量時，新的宣告回 `503 ADMISSION_PAUSED`；數量降下來就自動恢復。上傳、finalize 與查詢不受影響 |
| `KP_ADMISSION_API_PORT` | `api` | 預設 8080 |
| `--metrics-port`（參數） | `api` | 沒有預設值，給了才開；路徑是 `/metrics` |
| `KP_ADMISSION_URL`、`KP_ADMISSION_TOKEN` | orchestration worker | `api` 的叢集內 base URL，例如 `http://<service>:8080`，worker 在後面接 `/report/v1/…`；token 是環境變數，值來自 Secret |
| `KP_AUTHZ_PEP_CREDENTIALS` | `api` | JSON 物件：讀取端 credential 的 SHA-256 對它的名稱 |

credential 本身可以是任意字串，平台只保存它的 SHA-256；建議用 32 bytes 以上的亂數。

每個 Source 要求哪些讀取端，不是環境變數，而是寫進資料庫的指令：`kp-admission set-profile --tenant <tenant> <source_id> [projection ...]`。沒設定的 Source 不要求任何讀取端，它的文件會一直是 `not_ready`。

### 6.9 第一次部署的順序與驗收

照這個順序準備。每一步的細節在第 6 節的表與規格 §13。

| # | 做什麼 | 完成的樣子 |
|---|---|---|
| 1 | 建立空的 PostgreSQL 資料庫（17 以上），整份套用 [`schema.sql`](../../src/kp_admission/schema.sql)，它也建立 Change Feed 頭三個月的分區。`api` 的資料庫角色要有 `pg_read_all_stats`；跑 `feed-retention` 的角色要是 `change_feed` 資料表的擁有者，因為它建立與刪除分區 | 資料表都在 |
| 2 | 準備 custody bucket 與 storage 的憑證（權限見第 6 節「物件儲存」一列） | [`storage_probe.py`](../validation/184/storage_probe.py) 以 exit code 0 結束。它在 repo 的開發環境執行，讀 `KP_S3_ENDPOINT`、`KP_S3_BUCKET` 與 `AWS_*`，寫在 `probe184/` 這個前綴底下，跑完自己刪掉 |
| 3 | 確認 Temporal 的 namespace 連得到，processing worker 已部署 | orchestration worker 在輪詢 `<profile>-<版本>.orchestration`；採用 `paper-pdf@1` 時是 `paper-pdf-1.orchestration` |
| 4 | 產生 Source credential 與回報用的 credential，把 digest 寫進 `KP_CREDENTIALS` 與 `KP_PIPELINES`（第 6.8 節）；設定第 6 節「設定」一列的必填項目 | Secret 與環境變數就緒 |
| 5 | 啟動 `kp-admission api`（2 個副本）與 `kp-admission dispatcher`（至少 2 個副本） | `api`：叢集內 `GET /healthz` 回 `200`。`dispatcher` 沒有 HTTP 端點：pod 維持 Running、沒有重啟，log 沒有錯誤 |
| 6 | 建立三個 CronJob：`reconcile` 每 5 分鐘、`expire` 每小時、`feed-retention` 每天 | 各跑一次，exit code 0 |
| 7 | 採用 PDF 的處理方法版本：`kp-admission adopt --tenant <tenant> application/pdf paper-pdf@1`。用同一個 image 跑一次（Job 或進入 pod 執行），只需要 `KP_ADMISSION_DATABASE_URL`；`<tenant>` 是 `KP_CREDENTIALS` 裡的 `tenant_id` | 印出 `adopted_version`。指令不檢查這個版本有沒有 worker：採用了沒有 worker 的版本，request 會一直是 `queued` |
| 8 | 設定每個 Source 要求的讀取端：`kp-admission set-profile`（第 6.8 節），執行方式同上一步。名稱是讀取端登記的名稱，例如 `retrieval`。讀取端開始回報之前（#251、#127）這一步不影響任何結果，可以晚點做；Knowledge Profile 第一次設定時就有的讀取端直接計入 `readiness`，之後加入的要等它回報補建完成 | 印出 `profile_seq` |
| 9 | 設定 ingress：對外只開放 `/v1/`，上傳路徑放寬 body 上限、關閉緩衝、放寬 timeout（第 6.2 節） | 從 Source 的網段連得到 `/v1/`，連不到 `/report/`、`/read/`、`/authz/` |
| 10 | 設定 orchestration worker 的 `KP_ADMISSION_URL`（`api` 的叢集內位址）與 `KP_ADMISSION_TOKEN`，然後重啟 worker | worker 的 log 沒有 `KP_ADMISSION_TOKEN is not set` 這行 warning |

維運上要知道的幾件事：

- `GET /healthz` 不讀資料庫，資料庫停機時仍回 `200`。拿它當 liveness 與 startup probe，pod 不會因為資料庫停機被重啟；它不能代表「資料庫連得到」。
- 資料庫連線數：每個 `api` pod 最多 5 條，等不到連線 2 秒後那個呼叫回 `503`；每個 `dispatcher` 1 條；CronJob 每次執行 1 條。
- 進件配額存在資料庫，所有 `api` pod 共用一份。
- `reconcile` 連不到 Temporal 時以非 0 結束；`expire` 有 batch 沒清完時以 exit code 1 結束，下一次接著清。兩者重跑都安全。建議 CronJob 設 `concurrencyPolicy: Forbid`；兩次執行重疊的情況沒有測過。
- batch 過期是呼叫當下依 `expires_at` 判斷的，不等 `expire` 跑；`expire` 沒跑只會讓沒受理的檔案留在 bucket。
- `feed-retention` 每次建立當月與之後兩個月的分區。連續兩個月沒跑，admission 的寫入會開始失敗。

驗收：從 Source 的網段，用一把真的 Source credential 跑第 5 節的 quick start。

| 步驟 | 預期 |
|---|---|
| 登記 Resource | `201`；再呼叫一次 `200` |
| 宣告 | `201`；`uploads[].url` 的開頭是對外網址（`KP_ADMISSION_PUBLIC_URL`） |
| 上傳 | `204` |
| finalize | `202`，item 帶 `request_id` |
| `GET /v1/requests/{request_id}` | 先是 `queued`，worker 開始回報後是 `processing`，最後是 `succeeded` |
| `GET /v1/documents/{document_id}` | `readiness` 是 `not_ready`、`attention` 是空陣列。讀取端開始回報之前（#251、#127）這是正常的結果 |

結果不如預期時：

| 現象 | 可能的原因 |
|---|---|
| `api` 一啟動就結束，exit code 2 | 設定缺少或格式不對；stderr 會印出是哪一個 |
| 每個呼叫都是 `401` | credential 的 digest 沒有寫進 `KP_CREDENTIALS`，或算 digest 時多了換行 |
| 登記 Resource 回 `403` | 這把 credential 沒有 `manage_relations` |
| 每個呼叫都是 `503 UNAVAILABLE` | `api` 連不到資料庫 |
| 每個宣告的 item 都是 `UNSUPPORTED_FORMAT` | 第 7 步的 `adopt` 還沒做 |
| 每個宣告的 item 都是 `RESOURCE_NOT_FOUND` | Resource 還沒登記，或登記在另一個 Source 底下 |
| `uploads[].url` 是錯的主機 | `KP_ADMISSION_PUBLIC_URL` 的值不是 ingress 的對外 origin |
| 上傳回 `413`，或連線被中斷，回應沒有 `X-Trace-Id` | 被 ingress 或 sidecar 擋下：body 上限、緩衝或 timeout（第 6.2 節） |
| 上傳一直回 `503` | storage 連不到，或憑證少了 `s3:PutObject`、`s3:AbortMultipartUpload` |
| finalize 一直回 `503` | storage 連不到，或憑證少了 `s3:ListBucket` |
| request 一直是 `queued` | dispatcher 沒在跑、連不到 Temporal，或沒有 worker 在輪詢那個 task queue |
| request 不經過 `processing`，幾分鐘後直接變成 `succeeded` 或 `failed` | 回報沒送到，結果是 reconciler 補記的。檢查 `KP_PIPELINES`、worker 的 `KP_ADMISSION_URL` 與 `KP_ADMISSION_TOKEN`；`kp_api_calls_total{operation="report_status"}` 的 `401` 會增加 |
| `readiness` 一直是 `not_ready` | 讀取端開始回報之前（#251、#127）的正常結果。之後還是這樣：檢查讀取端在 `KP_PIPELINES` 的 `track` 和 `set-profile` 用的名稱相同；credential 不在 `KP_PIPELINES` 時它的回報都是 `401`（`kp_api_calls_total` 看得到）（第 6.8 節） |

## 7. 未決事項與變更紀錄

### 7.1 未決

| 事項 | 影響 | 負責 |
|---|---|---|
| pull 路徑 | 等有「檔案已在公司核准 storage」的具體來源再開 | #96 之後另開票 |
| Temporal 連線的 TLS 與驗證 | `dispatcher`、`reconcile` 與 worker 目前只讀 `TEMPORAL_ADDRESS` 與 `TEMPORAL_NAMESPACE`，連線不加密也不帶憑證。部署的 Temporal 要求其中之一時，要先加設定與程式 | #78 |
| PostgreSQL 的備份工具、排程與還原程序 | 規格 §9 只定了目標：WAL 連續歸檔，磁碟區毀損時最多遺失約一分鐘內受理的 request。做法與演練還沒定 | #78、#99 |
| 大檔案的續傳 | 5 GB 以上才需要；可以用新增的端點加上，不破壞既有 client（第 7.4 節） | 不在第一版 |
| 公司的 ingress 產品與設定值 | 第 6.2 節的數值 | #78 |
| `KP_ADMISSION_PUBLIC_URL` 的值 | `api` 用它組 `uploads[].url`（規格 §5.1），必填，不依賴 ingress 轉送的 header；值是 ingress 的對外 origin。驗收：經 ingress 宣告，回應的 `url` 是對外網址 | #78 |

### 7.2 變更紀錄

| 日期 | 事件 |
|---|---|
| 2026-10-03 | #53 Q9：通用入口為平台發授權的直接上傳；signed GET 與 connector 為選用 |
| 2026-10-20 | #31 Q5：上傳 grant 為 storage 原生 presigned URL 或 SAS，一小時效期 |
| 2026-10-30 | 主管確認公司政策禁止 client 以 presigned URL 上傳；轉達 #95 |
| 2026-11-05 | 規格與設計筆記加上 superseded 註記；轉達補到 #96 |
| 2026-11-07 | 決定 push、經平台上傳端點；契約寫入規格 §5.2；本文建立 |
| 2026-11-07 | 使用者確認政策只排除 presigned URL，不限定傳輸管道；本決定的前提成立，未決事項移除 |
| 2026-11-11 | #184：上傳直接寫到 custody 的 key，不設 staging，finalize 不寫 storage（[ADR-0012](../adr/0012-uploads-written-at-custody-key.md)）；第 1.2、3、4、6.3、6.4 節改寫，新增第 6.7 節 |
| 2026-11-18 | 對齊之後的決定：Resource 由 Source 自己的 key 識別、先登記再宣告（ADR-0013，#114）；上傳與 SDK 拆到 #194；每個回應帶 `X-Trace-Id`（#204）；pilot 用 PostgreSQL，PROD release 前移到 MongoDB（#239）。新增讀者表、刪除的呼叫、第 6 節的總表與第 7.3 節。`document_id` 的例子改成符合規格 §11 的字元 |
| 2026-11-19 | 本文成為「Source 交付文件」的單一入口，標題改為文件交付指南：新增摘要、第 2.5 節（API 的獨立審查，契約不改）、quick start、欄位表、`readiness` 的說明、第 7.4 節（大檔案的評估）。#96 已合併，第 5、6、7.3 節跟著更新。規格 §5.1 寫明必填欄位與 `uploaded_by`，並要求 client 照 `uploads[]` 的 `url` 上傳。`metadata` 讀者可見（2026-10-31 的裁決）補進規格 §6.5、設計筆記與 `CONTEXT.md` |
| 2026-11-19 | #194：上傳端點、上傳清理與最小 SDK 實作完成。上傳中 storage 無法回應定為 `503 UNAVAILABLE`（規格 §5.2 補上一列）；`uploads[].url` 改用 `KP_ADMISSION_PUBLIC_URL` 組成；media type 的偵測規則補進規格 §5.2 與第 6.5 節。第 7.1 節移除 storage 那一列，對外網址那一列改成 #78 要給的設定值；第 5.5、6 節跟著更新。獨立審查之後：規格 §5.1 寫明 `url` 用平台的對外 origin（部署設定），§5.2 列出偵測的六種型別、`503` 那一列涵蓋資料庫並註明檔案可能已就位，§3 的 `batch` 加上 `cleaned_at`，§13 改為引用 §6.2；本文第 6 節的 S3 權限按角色列出 |
| 2026-11-20 | #97：canonical processing 的回報接收與狀態查詢實作完成（PR #253）。#97 在開工前拆成三張：projection 的回報接收（#252）與 Canonical Acceptance 的記錄（#251）另外實作。第 5 節寫明 `readiness` 在 #252 之前都是 `not_ready`，以及平台原因失敗的訊息是固定句子；第 6 節補上 `/report/`、`KP_PIPELINES` 與 worker 的兩個設定；第 7.3 節更新，保留期的票是 #250 |
| 2026-11-20 | 補上讓 Source 開發者與 DevOps 只讀本文就能串接的內容：第 4.3 節（三種狀態與受理後平台做的事）、第 5.2 節的查詢改寫（用 request 的 `state` 判斷結果，各種結果該怎麼處理）、第 5.3 節 item 被拒的原因表、第 5.6 節（每個呼叫的 request 與回應欄位）、第 6.8 節（四個 JSON 設定的格式）、第 6.9 節（部署順序、驗收與常見現象）。回應的欄位對 `dev` 上的 `api` 實際跑過一次核對。另外請兩個只讀本文的獨立讀者試做：一個照本文寫出 client，對真的 `api`、資料庫與物件儲存跑過 8 個情境；一個照本文寫出部署計畫。兩者回報的缺口已補上。契約不變 |
| 2026-11-20 | #258：版本較大、檔案都相同的重送不再處理一次，和版本相同、內容相同一樣走規格 §6.4（`unchanged`、`queued` 或平台失敗後的重試），並把新的版本記成最新版的 `source_version`。原本回 `declared`、`uploads: []`，finalize 後重新處理整份文件；這是規格 §6.3 漏掉的組合（設計筆記的裁決同日補上）。第 5.2 節的 `source_version`、`declared`、`unchanged`，第 5.3 節的 `STALE_SOURCE_VERSION`，與第 5.6 節的 `latest`、`serving`、`attention` 跟著改；規格 §3、§6.3、§6.4 與 `CONTEXT.md` 的 Source Revision 條目一起更新 |
| 2026-11-22 | #252：讀取端的回報接收實作完成：Build 狀態、寫入前登記與 B5 檢查、serving 事實、heartbeat、attempt 回報、補建完成；`readiness`、`since`、`serving` 與讀取端的 `attention` 改由這些回報算出（規格 §7.4）。修復 view 的接收拆到 #260。第 5 節更新現況：讀取端還沒開始回報（#251、#127），所以仍是 `not_ready`；第 6.8 節補上讀取端的登記 |

### 7.3 實作狀態（2026-11-22）

進度以各票為準；這張表在票結案時更新。

| 步驟 | 端點或元件 | 票 | 狀態 |
|---|---|---|---|
| 受理核心 | 受理紀錄、outbox、dispatcher、reconciler | #95 | 已完成，在 `dev` |
| 共用處理 | `trace_id`、`/healthz`、metrics、log | #204 | 已完成，在 `dev` |
| 登記 Resource | `PUT`、`GET`、`DELETE /v1/resources/{key}`，`GET /v1/resources` | #114 | 已完成，在 `dev` |
| Change Feed | 讀取端取得文件變更的 API（`/read/v1/`，不對外） | #126 | 已完成，在 `dev` |
| 宣告、finalize | `POST /v1/batches`、`POST /v1/batches/{batch_id}/finalize`、`GET /v1/batches/{batch_id}`、batch 過期、採用紀錄 | #96 | 已完成，在 `dev` |
| 上傳 | `PUT /v1/batches/{batch_id}/items/{index}/files/{path}`、上傳清理、最小 SDK | #194 | 已完成，在 `dev` |
| 版本較大、檔案相同不重新處理 | 宣告與 finalize 的排序規則（規格 §6.3、§6.4） | #258 | 已完成，在 `dev` |
| 狀態查詢 | `GET /v1/requests/{request_id}`、`GET /v1/documents/{document_id}`、`GET /v1/documents`；canonical processing 的回報接收（`/report/v1/`，不對外） | #97 | 已完成，在 `dev` |
| projection 的回報接收 | Build 狀態、登記、serving 事實、heartbeat 與修復要求、attempt、補建完成；`readiness` 的 serving 部分 | #252 | 已完成，在 `dev`；讀取端開始回報之前（#251、#127）`readiness` 仍是 `not_ready` |
| 修復 view 的接收 | 讀取端送來整份 view，一次替換 mirror | #260 | 未實作，在 #252 之後 |
| Canonical Acceptance 的記錄 | `accepted`、目前的 Canonical Revision、`current_revision_changed` | #251 | 未實作，等 #57 對受理點的結論 |
| 刪除、重送、重跑 | `DELETE /v1/documents/{document_id}`、redrive、refresh | #98 | 未實作，在 #260 之後 |
| 保留期 | batch 與 `Idempotency-Key` 到期回 `404` 並移除紀錄 | #250 | 未實作 |
| dispatcher 與 reconciler 的 metrics | | #189 | 未實作 |
| 驗證 | CI 層與叢集層 | #99 | 未實作，在 #98 之後；叢集層另外等 #78 |
| admission 的 image、依賴拆分 | | #207 | 未實作 |
| 部署形態、ingress 數值、告警 | | #78 | 設計中 |
| 移到 MongoDB | | #239 | pilot 之後，PROD release 之前 |


### 7.4 大檔案（1 GB 以上）的評估（2026-11-19）

問題：之後要收 1 GB 以上的影片時，現在的契約夠不夠。結論：之後可以用新增的方式支援，現在不用改契約。下表的連線速度是假設，時間是換算，都不是量測。

| 檔案 | 100 Mbps 下傳一次 | 現在的契約 |
|---|---|---|
| 50 MB 以下 | 4 秒以內 | 可用；50 MB 是部署設定的上限（規格 §11） |
| 1 GB | 80 秒 | 調高上限，調整第 6.2 節的 ingress 與 sidecar 設定，並把 pod 的終止寬限與 sidecar 的 drain 時間拉到比上傳時間長，就可用 |
| 5 GB | 6.7 分鐘 | 勉強：斷線要整檔重傳（規格 §5.2） |
| 20 GB | 27 分鐘 | 不可用：斷在 90% 就損失 24 分鐘，而且撐不過一次部署 |

- **最先遇到的限制是「單一 request、不能續傳」**，不是 storage，也不是記憶體。依設計（#194 實作），平台寫入 storage 是分段的，每段 8 MiB，一個上傳佔的記憶體和檔案大小無關（第 6.1 節）；20 GB 是 2,385 段，低於 S3 的 10,000 段上限（[AWS](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)）。
- **部署會切斷長時間的上傳。** pod 的終止寬限預設 30 秒（[Kubernetes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)），Istio sidecar 的 `terminationDrainDuration` 預設 5 秒（[Istio](https://istio.io/latest/docs/reference/config/istio.mesh.v1alpha1/)）。上傳時間超過寬限的，每次部署都會被切斷重來。慢的連線現在就會遇到：50 MB 在 10 Mbps 要 40 秒；client 重送整個 `PUT` 即可（第 4.2 節），寬限的數值由 #78 定。
- **續傳可以新增。** 保留現在的 `PUT`，在宣告與 finalize 之間加分段上傳的端點，形狀和 OpenAI Uploads 的 create、add parts、complete 相同。`uploads[]` 的每一項已經有 `method` 與 `url`，整檔的 `sha256` 照舊；規格 §5.1 因此要求 client 照回應的 `url` 上傳。
- **影片當主檔還需要一個 Processing Profile**（pilot 只有 PDF）；這也是新增。
- **20 GB 級的檔案另有一條路**：平台去公司核准的 storage 讀檔（第 7.1 節的 pull 路徑），檔案不經過 API pod。
- 做續傳時，清理的假設要跟著改：現在假設上傳在一小時內結束（第 6.3 節）。

## 來源

- [admission 規格](knowledge-platform-admission-spec.md)、[admission 設計筆記](knowledge-platform-admission.md)、[授權指南](knowledge-platform-authorization-guide.md)、[Source handoff 設計](knowledge-platform-source-handoff.md)、[資料安全文件](knowledge-platform-data-security.md)
- [雲端實務研究](../research/attachment-handoff-cloud-practices-2026-10-02.md)、[inline 與 reference ingestion 研究](../research/document-inline-reference-ingestion-2026-10-18.md)、[CSP admission 實務研究](../research/admission-authorization-csp-practices-2026-10-20.md) §7、§8
- MinIO 官方文件：[STS](https://docs.min.io/enterprise/aistor-object-store/developers/security-token-service/)、[存取控制](https://docs.min.io/enterprise/aistor-object-store/administration/iam/access/)（頁面描述的是企業版 AIStor，公司使用的版本可能有差異）
- [ingress-nginx ConfigMap](https://kubernetes.github.io/ingress-nginx/user-guide/nginx-configuration/configmap/)、[boto3 S3 transfer](https://docs.aws.amazon.com/boto3/latest/reference/customizations/s3.html)、[OpenAI Uploads API](https://developers.openai.com/api/docs/api-reference/uploads)
