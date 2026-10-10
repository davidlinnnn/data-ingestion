# Canonical 契約與三格式案例

[設計索引](README.md) · [已確認決策](knowledge-platform-canonical-design.md) · [領域術語](../../CONTEXT.md)

**2026-10-10 最終共同確認完成。** [Resolution](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6096650145) 採納本文件的邏輯契約、完整案例、驗證計畫及 owner 交接。
檔名保留原 draft 路徑，以維持既有連結；正式 wire encoding 與實作規格依後續設計輸入落實。
本文件服務 [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32)。
沿用 Q1–Q18、Q19 撤回紀錄與 Q20–Q25 確認。重複附件表示、六組資訊與確切候選的驗證／接受紀錄，
以及最少重複原則已確認。Q22 確認三格式具體問答的必要意思與證據基準。
Q23 確認能力界線、條件式需求及研究處置；實際方法／profile 仍待 Processing 選定。
Q24 確認重送不新增版本、不同候選不強制去重，以及無明確取代依據時保留仍合格的目前版本。
Q25 確認版本內引用、三格式來源定位的索引約定及必要 unknown／無內容區別。
完整具體契約、案例與交接已通過使用者整體確認；本文件不是 parser 執行結果或能力驗證。
2026-10-09 的[候選 spike](../reviews/knowledge-platform-canonical-spike-2026-10-09.md)提供既有原則澄清與簡化建議；
其後的 [Q21 決策](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075416972)採納上述邏輯範圍，未採納正式 schema。

## 1. 本輪如何閱讀

| 標示 | 意義 |
|---|---|
| 已確認 | checkpoint 中的必要語意與責任邊界；選欄位名稱時不重新開啟原則。 |
| 已確認 Q23 | 能力需求／方法處置分開；公式、程式碼與 PDF 章節層級依實際用途成為必要要求。方法／profile 尚未選定。 |
| 已確認 Q22 | 三格式具體問答的預期意思與來源證據，作為設計驗證基準。 |
| 已確認 Q21 | 六組必要資訊、綁定確切候選的驗證／接受紀錄與最少重複原則。 |
| 已確認的邏輯表示 | 用同一第一版 schema 承載已確認語意與必要／條件必要結構；正式名稱與 ID 是示意，尚非 wire syntax 或資料表欄位。 |
| 已確認 Q20 | 同一附件的每個出現位置保留自己的引用、來源位置與上下文，指向同一固定 package artifact。[決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6074671955)。 |
| 證據缺口 | 現有輸出不足以證明必要語意或品質；交代受影響的映射／processing 驗證，不假設已實作。 |

目前只定義一種 Canonical schema，保留 schema 版本識別。Q19 的多格式提案仍已撤回。
一份完整候選是接受單位。以下資料群組不代表不同服務、檔案或資料表，
也不建立可獨立接受／選用的 Enrichment 產品。

## 2. 第一版候選的邏輯契約與示意欄位

Q21 確認以下六組資訊承載 Q1 的最低契約。Capture Package 與 processing manifest
已持有的資訊可用固定版本參照連接，不要求重複複製所有 manifest 或原始檔。

| 群組／示意欄位 | 必須表達的意義 |
|---|---|
| 身分：`schema_version`、`candidate_ref`、`asset_ref`、`source_revision_ref`、`capture_package_ref` | 明確識別固定候選與完整捕獲觀測。接受後的 Canonical Revision 必須綁定確切受評估候選。request／execution ID、digest 與來源先後仍是不同概念；此處不選 ID 編碼或分配方式。 |
| 處理歸屬：`request_ref`、`profile_ref`、`method_refs`、`completion_ref` | 指向固定 parser、映射與採納的 Enrichment 方法及輸入，保留必要工作完成證據。Temporal 執行結束不自動代表 processing 完成或 Canonical Acceptance。 |
| 內容：`components`、`sequences`、`associations`、`source_references` | 有類型的內容、包含關係、有依據的順序、必要關係，以及來源原始引用與解析目標。 |
| Enrichment：`result_ref`、`target_refs`、`input_refs`、`method_ref`、`content`、`evidence_refs`、`limitations` | 區分 OCR 重建、生成解讀與來源原文。輸入可涵蓋多個組件、artifact 或先前結果。採納結果屬於整份候選，可被引用不等於獨立接受或選用。 |
| Source Evidence：`evidence_ref`、`source_artifact_ref`、`locator`、`support_limits` | 固定來源、實際定位精度與支持範圍。若需要採用的 rendering／crop，連同其固定參照與原來源對應。定位可開啟或模型信心分數，都不等於內容獲得支持。 |
| 涵蓋與限制：`mapping_report_ref`、`covered_scope`、`limitations`、`dispositions` | 交代必要來源內容與實際有值的 provider 輸出如何處置。允許省略須有範圍、規則與理由；保留 raw output 不代表理解必要意思。 |

同一事實只需一個權威表示，分組不要求獨立清單。圖片出現組件可直接承載 Source Reference；
包含／順序已表達的關係，不必再複製到 associations。
Q21 採用內容／結果指向證據的最少表示，不要求證據端另存反向清單；支持範圍與限制仍須明確。
限制在所屬結果／映射保留一次，整份涵蓋報告引用即可；Enrichment 文字不必另複製成組件文字。
上述為已確認的邏輯表示原則；正式欄位拼法與編碼於 buildable spec 一致落實。處理輸入、結果目標與支持證據的角色不同，不能為去重而混同。

每個組件至少需要版本內參照、類型、內容、適用的上下文／包含關係、來源／方法歸屬及證據參照。
依來源需要表示標題／文字、步驟、程式碼／公式、表格、圖片、投影片及備註；組件不獨立接受。

包含關係與順序分開：示意 `parent_ref` 表示隸屬位置；
sequence 表示範圍、項目及順序的意義，例如 Markdown 步驟順序或投影片順序。
不能把 provider 集合的遍歷順序直接當成閱讀順序。
caption、註解等關係保留實際目標與依據；目標不確定就明示。

Source Reference 保留原始引用字串及已建立的目標對應。
未解析的外部 URL 仍是來源內容，不自動成為已捕獲依賴。
必要附件指向固定 Capture Package 內的 artifact；Q20 已確認每個重複出現位置各自保留引用與上下文。

### 格式內容與來源定位

| 案例 | 已確認的內容表示 | 來源定位 |
|---|---|---|
| PDF 表格 | 列欄、儲存格文字與位置／跨列跨欄、表頭對應、單位及註解的作用範圍 | 固定原始 PDF 與實體頁面；有依據才提供 region／cell 精度。bbox 須說明座標原點與單位。crop recipe 不等於已保存 crop。 |
| SOP Markdown | 標題、完整文字、有順序及巢狀的步驟、條件／禁止事項、原始連結與附件綁定 | 固定 Markdown 與行／區塊位置；圖片另有固定 artifact 與定位，不強迫套用 PDF 頁碼。 |
| PPTX | 投影片順序、可取得的 native 文字／shape／表格／備註；可靠關係或足以保存必要圖意的文字 Enrichment | 固定 PPTX 與投影片；有支持才提供 shape／notes 位置。若解讀依賴 rendering，指明採用的固定 rendering 與原投影片對應。 |

上述是邏輯要求，不表示每種 locator／worker 已實作。

### 第一版參照與定位表示（Q25 已確認）

2026-10-09 於 [Q25 決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6076312345)確認以下引用／定位語意及索引約定。
此確認不等於完整 wire schema 已完成，也不新增 parser 能力或更細定位保證。
第 2 節六組資訊及第 3 節判定紀錄仍是同一契約。

| 表示位置 | 第一版已確認規則 | 具體例子／限制 |
|---|---|---|
| 固定物件參照 | Asset、Source Revision、Capture Package、candidate、method、artifact 各用其不透明參照；固定來源／artifact 參照須解析到確切版本，不能解析到 live latest。 | I1 是 M1/I1 package 已綁定的固定 artifact；它不是 path、digest 或跨文件共享附件身分。實際 ID 字串分配由規格決定。 |
| 文件內位置 | `component_ref`／`result_ref` 在候選內識別；consumer 引用時帶確切 `canonical_revision_ref` 與版本內參照。兩者共同決定目標。 | C1 的 step-3 不會因 C2 也有 step-3 而改指 C2；不要求跨版本 matching。候選內部關係可直接用 local ref，不必每條邊重複 revision。 |
| Source Evidence | `source_artifact_ref` 加 `locator`，另列實際支持範圍／限制；一個內容或結果可引用多份 evidence。 | 表格值和註解可各有定位，同一結論保留兩者支持；圖片 OCR 的實際輸入、解讀目標與支持證據仍分開。 |
| PDF locator | 實體頁碼從 1 起算；區域可選。若有 bbox，明示座標原點、單位及其所屬原頁或採用 rendering，並保留必要原來源對應。 | 第 3 個實體頁面，不靠印刷頁碼「iii」／「1」猜測。只有頁級支持就不填精確 cell bbox；無須強制存 crop。 |
| Markdown locator | 固定原始 artifact 的行號從 1 起算，行範圍含起訖行；取得可靠 block 位置時可另用版本內 block 參照。 | M1 的發布圖片為第 6 行，警告文字另由 I1 支持。不得對改寫後文字計行卻冒稱原始位置。 |
| PPTX locator | 投影片從 1 起算；shape／notes 位置只有可靠取得時才加入，且只在該固定 PPTX 中解讀。 | T1 的第 2 張投影片；source shape ID 不宣稱跨改版穩定。採用 rendering 時保留固定 rendering 與原投影片對應。 |
| 無更細位置／未知結果 | 可保留整個固定 artifact 的定位，但是否足夠仍依用途。缺少欄位只表示沒有該值；必要的未嘗試、失敗、未知、允許省略或確認無內容，須在所屬結果／mapping disposition 說明。 | 空 OCR 文字不能同時冒充「沒有文字」或「辨識失敗」；不因未知而虛構 bbox／hierarchy，也不為每個可選欄位新增狀態機。 |

這些規則固定引用與位置的意思；正式欄位命名、可讀標籤或 ID 產生方式不是新增領域決策。
版本內 reference closure、locator 所屬來源、實際精度及 unknown／omission 的接受效果，
由 V01–V11 相應案例核對。資料庫、API endpoint 或跨版本轉換框架仍未選定。

## 3. 驗證、接受與目前使用狀態

以下意義在組合成讀取／狀態回應時仍須區分；本文件不指定 API 或實體存放方式。

| 事實 | Q21 確認的必要資訊 | 已確認限制 |
|---|---|---|
| 驗證 | 確切候選、規則版本、必要檢查、結果、允許限制與佐證 | schema 有效、processing 完成、artifact 可讀，不能單獨證明必要意思完整。 |
| 接受 | 確切受評估候選／Canonical Revision 綁定、驗證參照、可歸責的自動規則或授權人員判定、適用範圍與判定依據 | 整份候選接受。必要輸入、工作、證據或治理不足不能豁免；完成接受前，必要來源與採用證據的 custody 保護已成立。重新評估保留歷史判定。 |
| 目前選用 | 選用範圍／目標、確切 revision、適用性／相容性依據、衝突或未就緒資訊 | 已接受不等於目前選用；完成時間不代表來源先後；不預設所有 consumer 共用一個全域 current。 |
| 目前資格 | 適用生命週期／治理事實、範圍及其觀測／判定參照 | 歷史接受不授予目前存取權；固定內容中不嵌入永久授權或可變 current 旗標。 |

Canonical owner 提供自身權威事實給 admission/status，後者負責公開查詢與關聯。
request-record 到期與 Temporal history 不決定已接受內容及必要證據的保留期限。
接受前撤回依 Q18：晚到的處理／驗證成功不形成接受；恢復授權後重新評估。

### Q24：重送、重新處理與選用

2026-10-09 於[Q24 決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6076049015)確認。

| 情況 | 必須保留的行為 |
|---|---|
| 同一候選的同一次接受結果重送 | 回到同一 Canonical Revision，不因重送新增版本。重新評估另留判定紀錄；判定變更本身依 Q9，不必建立新內容版本。 |
| 新請求形成另一個候選 | 可以各自通過接受並形成不同 Canonical Revision；即使內容相同，也不強制跨執行比對／合併。request、candidate、revision 與 digest 仍是不同概念。 |
| 同一來源／方法有多份合格結果 | 依 Q8 的選用規則；無明確取代依據時，保留目前仍合格版本。仍無法決定時明示衝突，不依完成時間決勝，也不恢復已失去資格的舊版本。 |

K1 已對應 C1，原接受結果重送仍回到 C1；S1/M1 的新請求形成 K2，
通過接受後可成為 C2。C2 存在不自動取代 C1。
重送回覆仍受目前治理限制；本契約不指定去重資料表、鎖、ID 編碼、全文比較或自動品質排名。
原子寫入／重送辨識由 Canonical 與 persistence 整合，Admission 保留 request／result 關聯。

## 4. 共用的虛構 Corpus 案例

**以下原文、ID 與位置均為虛構設計 fixture。**
它們不是實際 parser 輸出、已選 pilot 或量測成果。
共同主題為「文件處理與復原」。

### PDF P1：方法限制表

假設原 PDF 第 3 頁有下表：

| 方法 | 重試上限（次） |
|---|---|
| A | 2* |
| B | 0 |

註解為「*僅適用暫時性處理錯誤，且作業必須具備冪等性」。
它限制 A 的重試值，不代表所有失敗都可重試。

候選內容：

- `pdf-table`：兩欄表格、表頭／單位、列欄配對，以及 A 數值上的註記。
- `pdf-note`：完整限制文字，對應到 A 的重試值。
- `pdf-evidence`：固定 P1 原始 artifact、第 3 頁與實際可提供的定位精度；
  其映射須支持表格內容與註解關係。
- 保存來源與抽取／映射方法歸屬。要支援精確值與條件查詢，就須驗證上述對應。

依已確認規則，保存這些意思的候選才能進入其餘必要接受檢查；此處不宣稱已接受。
A/B 數值互換、單位遺失或註解漏掉／掛錯，都無法滿足本案例。
附一個「表格品質可能不佳」警告，不能讓必要資訊的遺失通過接受。

### SOP S1：步驟與重複引用的必要圖片

假設固定 Markdown M1 有以下六行：

```markdown
# 重試與發布
1. 僅暫時性處理錯誤且作業冪等時，可重試。
   ![品質警告](assets/check.png)
2. 完成處理後執行品質檢查。
3. 品質通過才發布；未通過則停止並通知負責人。
   ![發布警告](assets/check.png)
```

完整 Capture Package 把 `assets/check.png` 綁到固定圖片 I1。
圖中文字為「不得略過品質檢查」，本案例將它視為必要內容。
M1/I1 的固定身分、完整性與 custody 沿用來源交接契約；路徑或臨時 URL 不是其身分。

**候選組件；Q20 已確認重複引用各自保留位置與上下文，示意欄位／ID 尚非正式編碼：**

| 版本內參照 | 類型／內容 | 上下文與來源 |
|---|---|---|
| `heading` | 標題「重試與發布」 | M1 第 1 行 |
| `step-1` | 完整的條件式重試指示 | M1 第 2 行 |
| `step-2` | 執行品質檢查 | M1 第 4 行 |
| `step-3` | 通過／未通過的發布指示 | M1 第 5 行 |
| `image-use-1` | 圖片引用；alt 為「品質警告」；原目標 `assets/check.png` | 隸屬步驟 1；M1 第 3 行；解析到 package artifact I1 |
| `image-use-2` | 圖片引用；alt 為「發布警告」；相同原目標 | 隸屬步驟 3；M1 第 6 行；解析到同一 I1 |

步驟順序為 `[step-1, step-2, step-3]`。
兩個圖片出現位置保留不同上下文與 alt，指向同一 I1。
這不要求複製圖片 bytes、跨文件共用附件身分、跨版本配對，或特定 OCR 執行／重用策略。

若候選採納 OCR 警告文字，須記錄確切 I1 輸入、方法、結果與來源支持，
並與 Markdown 原文區分。若生成解讀也讀取前後步驟，輸入參照須包含那些步驟；
圖片 bytes 相同，不足以證明上下文解讀相同。這是既有輸入／歸屬規則的運用。

檢查重點是步驟順序、完整條件／否定、兩個原始引用位置與必要圖片警告。
已知必要 I1 缺失就不符合來源就緒；較晚才發現仍須明確失敗，不能視為可選省略。
I1 換 I2 依 Q12 形成新的來源觀測／候選；可以整份重做，
重用則須符合已確認的相容條件。

### PPTX T1：成功／失敗分支與備註

假設第 2 張投影片是「處理 → 品質檢查」，接著分成
「通過 → 發布」與「未通過 → 停止並通知」。
講者備註說明「此圖表示發布判定，不表示處理階段的重試政策」。

組件保留投影片上下文、圖的固定 artifact／證據與可區別的來源備註。
若可靠取得 native connector，就保留方向與標籤。
若只有圖像，候選可以採納以下文字 Enrichment：

> 處理完成後執行品質檢查。通過才發布；未通過則停止並通知負責人。

解讀須指向實際採用的投影片／rendering 輸入、方法與充分證據；
文字是解讀結果，不冒充 native 原文。備註仍可供 consumer 使用，
避免 Wiki 把「停止」錯套到每一種處理重試。

必要方向、條件、分支動作及備註上下文都須正確。
「品質、發布、停止」三個詞不足以代表流程。
必要箭頭未解出或備註遺失，就無法滿足本案例；只保留投影片圖像不等於理解分支。
不要求通用流程圖模型或可執行流程。

### Q22 已確認的具體問答基準

2026-10-09 於 [Q22 決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075543252)確認。
下列預期結果用於驗證候選保留的必要意思與來源證據；允許不同回答措辭。

| 固定設計來源 | 具體問題 | 預期意思與必要來源支持 |
|---|---|---|
| PDF P1 | 方法 A 最多可重試幾次？ | 最多 2 次，且僅適用暫時性錯誤、作業具備冪等性的情況。數值須連到正確表頭、單位及限制註解。 |
| SOP M1／I1 | 發布前品質檢查失敗，應怎麼做？警告在哪？ | 停止並通知負責人。保留 I1 的「不得略過品質檢查」及 M1 第 6 行、發布步驟中的圖片引用位置。 |
| PPTX T1 | 圖中的「停止」是否表示所有處理錯誤都禁止重試？ | 不是；它是品質檢查未通過時的發布分支。保留方向、條件與區分發布判定／重試政策的講者備註。 |

漏掉必要條件、掛錯註解或混淆分支，不能通過對應檢查。通過這些案例仍須滿足其他接受條件。
Wiki 與 Retrieval 使用同一組固定 Canonical 輸入，依下節需求取得上述意思及證據。
這是設計基準，尚非方法能力或 consumer 執行驗收。

### Wiki 與 Retrieval 概念檢查

假設三份候選已通過適用接受檢查，兩種 consumer 都使用固定輸入
`{P1-C1, S1-C1, T1-C1}`，並遵守目前使用資格。
這些 ID 不宣稱實際存在已接受資料。

| 需求 | 共用 Canonical 輸入的檢查 |
|---|---|
| Wiki 知識整理 | 組織並連結處理方法、重試條件、品質檢查與發布等主題；一個主題可使用多來源，一份來源可支持多頁面。 |
| 跨來源綜合 | 區分暫時性處理錯誤與品質／發布檢查失敗，不能把 A 的「2 次」整理成無條件重試。每項綜合說法保留它實際使用的固定輸入與證據。 |
| 差異／矛盾 | 保留來源範圍與不同說法；若日後來源互相衝突，交由 projection 處理，不偷偷改寫來源內容使其一致。 |
| Retrieval | 從同一組輸入回答重試／發布問題，帶出必要條件及證據；理解 Canonical 內容不依賴 Wiki 頁面。 |
| 更新 | 附件／來源或採納 Enrichment 改變，依規則形成新候選／revision。Projection 依自身發布規則重新評估受影響產品，不假設跨版本組件配對。 |

這是概念契約檢查。生成、連結品質、Retrieval 效果與實際更新／發布測試由 projection 負責。

### 同一第一版表示的三份完整候選（2026-10-10 已確認）

以下是**手工建立的設計預期**，不是 parser 輸出或實際接受紀錄。
`canonical-v1` 是供 review 的單一 schema 識別；欄位拼法可在規格中一致整理，
不能改掉已確認意思。為使 fixture 範圍完整，P1 明定共三頁，前兩頁空白，
第 3 頁為上文表格／註解；T1 共兩張，第 1 張僅標題「文件處理與復原」，
第 2 張為上文流程及備註；S1 使用上文完整六行 M1 與必要 I1。
這些補充只界定虛構 fixture，不推論實際文件中的未知頁面是空白。

#### 最小結構與必要性

| 結構 | 必要資訊／條件必要資訊 | 不得混同 |
|---|---|---|
| Candidate | 必有 `schema_version`、`candidate_ref`、固定 `capture_package_ref`、`processing_ref`、`mapping_ref` 及有類型內容；Asset／Source Revision 可由固定 package 唯一解析。 | 不以 request、digest 或完成時間代替候選／來源身分。 |
| Component | 必有版本內 `ref`、`kind`、來源／方法歸屬及足夠 evidence；依 kind 提供文字、表格位置／spans／header refs、圖片／引用、slide／notes 等必要內容。適用時提供 `parent_ref`。 | 只有結構的 table／slide 不必虛構文字。程式碼／公式可保留足夠原文或重建文字，沒有 AST／求解要求。 |
| Sequence／Association | 順序以 `item_refs` 與順序意思表示；適用時用 `scope_ref` 指定組件範圍，未填表示整份候選。必要關係有 `kind`、起點、終點及依據。表格列欄／span 在本候選從 1 起算；定位仍依 Q25。 | 不把 array 儲存／遍歷順序當來源閱讀順序。已由 parent／sequence 表達的關係不重複。 |
| Source Reference | 保留 `raw_target`；已解出固定目標時才附 artifact／component 目標。未解出須保留其狀況。 | Source Reference 是來源中的引用；它不等於支持內容的 Source Evidence。 |
| Enrichment | 採納結果必有 `ref`、`origin`、實際 `input_refs`、`target_refs`、`method_ref`、內容、evidence 及必要限制；各 ref 標出 artifact／component／前結果角色。 | 一個結果可針對多個位置；輸入、目標與支持證據不合併。不複製其文字到 components。 |
| Evidence | 必有版本內 `ref`、固定 `source_artifact_ref`、Q25 locator 及支持限制；依賴採用 rendering／crop 時附固定參照及來源對應。 | 可定位不等於支持內容；沒有 pixel/cell 精度不能補造。 |
| Mapping report | 必有固定映射方法、候選輸入、所需／已涵蓋範圍與有值 provider 欄位的 disposition；限制與必要未解讀／缺失須可核對。 | 以下已知空陣列表示案例中沒有該類關係／結果，不替代未嘗試或失敗紀錄。 |
| Validation／Acceptance | 驗證綁候選、規則、必要檢查與佐證；接受另綁確切候選／revision、驗證與可歸責規則或授權判定及適用範圍。 | 判定重送依 Q24；目前選用／資格不嵌入固定候選。 |

所有 local refs 必須在同一候選內唯一且可解析；固定外部 refs 須由以下聲明或相應固定紀錄解析。
component 的 `origin: source` 表示來源內容，抽取／映射方法由其固定 processing／mapping 紀錄提供；
OCR 重建與生成解讀各在採納結果中記錄。這裡的來源內容不等於來源事實已被平台證明為真。

#### 固定外部紀錄聲明（同樣是設計預期）

| 候選 | 固定 package | Processing／Mapping | 應受保護的必要資料 |
|---|---|---|---|
| K-P1 | PK-P1 → Asset A-P、Source Revision S-P1、完整 P1 | PC-P1 → request R-P1、profile P-P1、PDF parser P-1、必要工作完成證據；MP-P1 → mapper MAP-1、K-P1/P1、三頁涵蓋及前兩頁確認空白。 | P1、採用的固定處理／映射輸出與判定證據。 |
| K-S1 | PK-S1 → Asset A-S、Source Revision S-S1、完整 M1/I1，兩次相同 path 都綁 I1 | PC-S1 → request R-S1、profile P-S1、Markdown parser MD-1、OCR-1 的 I1 警告結果與必要工作完成證據；MP-S1 → MAP-1、K-S1/M1/I1、六行與圖片必要意思涵蓋。 | M1/I1、採用 OCR 輸出與判定證據。 |
| K-T1 | PK-T1 → Asset A-T、Source Revision S-T1、完整 T1 | PC-T1 → request R-T1、profile P-T1、PPTX parser PPT-1、renderer RENDER-1、FLOW-1 及必要工作完成證據；T1-render2 固定對應 T1 第 2 張；MP-T1 → MAP-1、K-T1/T1、兩張與備註／必要圖意涵蓋。 | T1、採用 T1-render2、FLOW-1 輸出與判定證據。 |

P-1／MD-1／PPT-1／OCR-1／FLOW-1 等是固定方法紀錄的**示例標籤**，不是已採納套件或已驗證模型。
PC-* 不包含 Canonical 接受授權；各方法的實際 code/model/configuration 身分由執行前固定紀錄提供。
本例假設正常接受所需授權與 custody 證據可成立；實際執行缺任何必要證據仍不能接受。

#### PDF 候選 K-P1

```json
{
  "schema_version": "canonical-v1",
  "candidate_ref": "K-P1",
  "capture_package_ref": "PK-P1",
  "processing_ref": "PC-P1",
  "mapping_ref": "MP-P1",
  "components": [
    {"ref":"p-table","kind":"table","rows":3,"columns":2,"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-method","kind":"table_cell","parent_ref":"p-table","text":"方法","cell":{"row":1,"column":1,"row_span":1,"column_span":1,"header_refs":[]},"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-limit","kind":"table_cell","parent_ref":"p-table","text":"重試上限（次）","cell":{"row":1,"column":2,"row_span":1,"column_span":1,"header_refs":[]},"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-a","kind":"table_cell","parent_ref":"p-table","text":"A","cell":{"row":2,"column":1,"row_span":1,"column_span":1,"header_refs":["p-method"]},"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-a-limit","kind":"table_cell","parent_ref":"p-table","text":"2*","cell":{"row":2,"column":2,"row_span":1,"column_span":1,"header_refs":["p-limit","p-a"]},"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-b","kind":"table_cell","parent_ref":"p-table","text":"B","cell":{"row":3,"column":1,"row_span":1,"column_span":1,"header_refs":["p-method"]},"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-b-limit","kind":"table_cell","parent_ref":"p-table","text":"0","cell":{"row":3,"column":2,"row_span":1,"column_span":1,"header_refs":["p-limit","p-b"]},"origin":"source","evidence_refs":["ep3"]},
    {"ref":"p-note","kind":"text","text":"*僅適用暫時性處理錯誤，且作業必須具備冪等性","origin":"source","evidence_refs":["ep3"]}
  ],
  "sequences": [
    {"kind":"source_order","item_refs":["p-table","p-note"]}
  ],
  "associations": [
    {"kind":"qualifies","from_ref":"p-note","to_ref":"p-a-limit","basis":"來源的 * 註記"}
  ],
  "enrichments": [],
  "evidence": [
    {"ref":"ep3","source_artifact_ref":"P1","locator":{"kind":"pdf","page":3},"support_limits":"頁級定位；本設計例以來源核對確認值、單位與註解關係。"}
  ]
}
```

#### SOP 候選 K-S1

```json
{
  "schema_version": "canonical-v1",
  "candidate_ref": "K-S1",
  "capture_package_ref": "PK-S1",
  "processing_ref": "PC-S1",
  "mapping_ref": "MP-S1",
  "components": [
    {"ref":"s-heading","kind":"heading","text":"重試與發布","origin":"source","evidence_refs":["em1"]},
    {"ref":"s-step1","kind":"list_item","text":"僅暫時性處理錯誤且作業冪等時，可重試。","origin":"source","evidence_refs":["em2"]},
    {"ref":"s-image1","kind":"picture","parent_ref":"s-step1","alt":"品質警告","source_reference":{"raw_target":"assets/check.png","artifact_ref":"I1"},"origin":"source","evidence_refs":["em3"]},
    {"ref":"s-step2","kind":"list_item","text":"完成處理後執行品質檢查。","origin":"source","evidence_refs":["em4"]},
    {"ref":"s-step3","kind":"list_item","text":"品質通過才發布；未通過則停止並通知負責人。","origin":"source","evidence_refs":["em5"]},
    {"ref":"s-image2","kind":"picture","parent_ref":"s-step3","alt":"發布警告","source_reference":{"raw_target":"assets/check.png","artifact_ref":"I1"},"origin":"source","evidence_refs":["em6"]}
  ],
  "sequences": [
    {"kind":"source_order","item_refs":["s-heading","s-step1","s-step2","s-step3"]}
  ],
  "associations": [],
  "enrichments": [
    {"ref":"ocr-i1","origin":"reconstruction","input_refs":[{"artifact_ref":"I1"}],"target_refs":["s-image1","s-image2"],"method_ref":"OCR-1","text":"不得略過品質檢查","evidence_refs":["ei1"],"limitations":[]}
  ],
  "evidence": [
    {"ref":"em1","source_artifact_ref":"M1","locator":{"kind":"markdown","line_start":1,"line_end":1},"support_limits":"原始檔行級定位。"},
    {"ref":"em2","source_artifact_ref":"M1","locator":{"kind":"markdown","line_start":2,"line_end":2},"support_limits":"原始檔行級定位。"},
    {"ref":"em3","source_artifact_ref":"M1","locator":{"kind":"markdown","line_start":3,"line_end":3},"support_limits":"原始檔行級定位。"},
    {"ref":"em4","source_artifact_ref":"M1","locator":{"kind":"markdown","line_start":4,"line_end":4},"support_limits":"原始檔行級定位。"},
    {"ref":"em5","source_artifact_ref":"M1","locator":{"kind":"markdown","line_start":5,"line_end":5},"support_limits":"原始檔行級定位。"},
    {"ref":"em6","source_artifact_ref":"M1","locator":{"kind":"markdown","line_start":6,"line_end":6},"support_limits":"原始檔行級定位。"},
    {"ref":"ei1","source_artifact_ref":"I1","locator":{"kind":"artifact"},"support_limits":"整張固定圖片；只支持圖片警告文字，不代表其在 Markdown 中的出現位置。"}
  ]
}
```

OCR-1 只讀 I1；它不把某次出現的步驟上下文冒充另一次出現的輸入。
若方法實際讀取上下文，`input_refs` 必須加入對應組件並依真實依賴評估重用。

#### PPTX 候選 K-T1

```json
{
  "schema_version": "canonical-v1",
  "candidate_ref": "K-T1",
  "capture_package_ref": "PK-T1",
  "processing_ref": "PC-T1",
  "mapping_ref": "MP-T1",
  "components": [
    {"ref":"t-slide1","kind":"slide","origin":"source","evidence_refs":["et1"]},
    {"ref":"t-title","kind":"heading","parent_ref":"t-slide1","text":"文件處理與復原","origin":"source","evidence_refs":["et1"]},
    {"ref":"t-slide2","kind":"slide","origin":"source","evidence_refs":["et2"]},
    {"ref":"t-diagram","kind":"picture","parent_ref":"t-slide2","artifact_ref":"T1-render2","origin":"source","evidence_refs":["et2"]},
    {"ref":"t-notes","kind":"notes","parent_ref":"t-slide2","text":"此圖表示發布判定，不表示處理階段的重試政策。","origin":"source","evidence_refs":["et2"]}
  ],
  "sequences": [
    {"kind":"slide_order","item_refs":["t-slide1","t-slide2"]}
  ],
  "associations": [],
  "enrichments": [
    {"ref":"flow-text1","origin":"interpretation","input_refs":[{"artifact_ref":"T1-render2"}],"target_refs":["t-diagram"],"method_ref":"FLOW-1","text":"處理完成後執行品質檢查。通過才發布；未通過則停止並通知負責人。","evidence_refs":["et2"],"limitations":["本例沒有宣稱已取得可靠 native connector；以來源支持的文字保存必要圖意。"]}
  ],
  "evidence": [
    {"ref":"et1","source_artifact_ref":"T1","locator":{"kind":"pptx","slide":1},"support_limits":"投影片級定位。"},
    {"ref":"et2","source_artifact_ref":"T1","locator":{"kind":"pptx","slide":2},"adopted_artifact_ref":"T1-render2","support_limits":"投影片級定位；採用 rendering 由固定處理紀錄對應到 T1 第 2 張。"}
  ]
}
```

#### 綁定確切候選的預期驗證與接受紀錄

| 預期紀錄 | 候選與規則／佐證 | 允許產生的接受紀錄 |
|---|---|---|
| VAL-P1 | K-P1、RULES-1；V01/V05 及共同身分、參照、涵蓋、來源支持、必要工作、目前資格與 custody 檢查全部通過；來源預期為本節 P1。 | ACC-P1 → K-P1、Canonical C-P1、VAL-P1、RULES-1 的可歸責自動判定；適用於已確認的表格／共用 consumer 用途。 |
| VAL-S1 | K-S1、RULES-1；V02/V05 及相同共同檢查全部通過；M1 的兩次引用與 I1 警告都可追溯。 | ACC-S1 → K-S1、Canonical C-S1、VAL-S1、同一可歸責規則及 SOP 用途；來源或 Enrichment 不能被獨立接受。 |
| VAL-T1 | K-T1、RULES-1；V03/V05 及相同共同檢查全部通過；方向／分支／備註與採用 rendering 支持均成立。 | ACC-T1 → K-T1、Canonical C-T1、VAL-T1、同一可歸責規則及流程解讀用途。 |

RULES-1 指本票確認的共同接受條件及各案例預期；正式紀錄必須綁固定規則版本，
個別檢查結果與可追溯佐證，不以這張摘要表代替實際驗證。
上表都是「條件滿足時應產生什麼」的設計預期，沒有宣稱已實際接受。
任何必要檢查失敗或未評估，都不能生成通過結果；可允許限制須有已確認規則依據。
同一 ACC-* 結果重送不新增 revision；重新評估保留新判定，依 Q9/Q24 處理。

### 有值 provider 欄位的完整處置例（V04）

固定 provider 為 **docling-core 2.96.0**；它輸出的 DoclingDocument schema 版本是 **1.10.0**。
[固定 BaseMeta 定義](https://github.com/docling-project/docling-core/blob/0b55aca55b22f7109502d44db36f8246e238121c/docling_core/types/doc/common/meta.py)
允許符合 `namespace__field_name` 的自訂欄位；
[NodeItem.meta](https://github.com/docling-project/docling-core/blob/0b55aca55b22f7109502d44db36f8246e238121c/docling_core/types/doc/items/node.py)
可承載它。以下是 **synthetic adapter metadata**，不是 parser 實測結果，也不是 Core 內建的 condition 語意：

```json
{
  "schema_name": "DoclingDocument",
  "version": "1.10.0",
  "name": "V04 synthetic",
  "furniture": {"self_ref":"#/furniture","children":[],"content_layer":"furniture","name":"_root_","label":"unspecified"},
  "body": {"self_ref":"#/body","children":[{"$ref":"#/texts/0"}],"content_layer":"body","name":"_root_","label":"unspecified"},
  "groups": [],
  "texts": [{"self_ref":"#/texts/0","parent":{"$ref":"#/body"},"children":[],"content_layer":"body","meta":{"fixture__condition":"僅適用暫時性處理錯誤，且作業必須具備冪等性"},"label":"text","prov":[],"orig":"方法 A 最多重試 2 次。","text":"方法 A 最多重試 2 次。"}],
  "pictures": [],
  "tables": [],
  "key_value_items": [],
  "form_items": [],
  "pages": {}
}
```

待處置欄位為 `/texts/0/meta/fixture__condition`，值非空。
此 fixture 只檢查這一欄的處置；K-P1 其餘內容及接受條件仍須獨立滿足。
本例假設 adapter 的欄位語意已知，該值源自 P1 的必要限制註解；
實際來源支持由固定 P1 案例核對，不能由這個沒有 `prov` 的 JSON 自行證明。

| 明確 disposition | 候選／映射報告的具體結果 | 接受效果 |
|---|---|---|
| 納入 | MP-P1 將該 pointer 對應 `p-note`，將完整條件連到 `p-a-limit`，保留 adapter／MAP-1 歸屬及 ep3 的來源支持。 | 這項檢查在條件、目標與來源支持皆正確時通過；其餘共同檢查仍須通過。 |
| 保留未解讀 | 保留固定 provider artifact 與 pointer；MP-P1 記 `retained_uninterpreted`。若候選只有「方法 A 最多重試 2 次」而缺必要條件，則必要意思未映射。 | raw 可讀也不通過；不產生接受。 |
| 依規則省略重複欄位 | 僅當相同必要條件已在 `p-note` 完整保留並驗證，MP-P1 可依固定重複欄位規則記 `omitted`、理由及對應 `p-note`。 | 省略的是重複 provider 欄位；不省略必要意思。若這欄是唯一條件載體，就不能用此規則通過。 |

**本次已做：** 在既有環境確認 core 2.96.0，建立文件、`export_to_dict()`、
`DoclingDocument.model_validate()` roundtrip，確認自訂欄位與值保留。
以下為可重現的最小 schema 檢查；未安裝新套件、未執行 OCR／VLM：

```python
from importlib.metadata import version
from docling_core.types.doc.document import BaseMeta, DoclingDocument, DocItemLabel

assert version("docling-core") == "2.96.0"
doc = DoclingDocument(name="V04 synthetic")
item = doc.add_text(label=DocItemLabel.TEXT, text="方法 A 最多重試 2 次。")
item.meta = BaseMeta.model_validate({
    "fixture__condition": "僅適用暫時性處理錯誤，且作業必須具備冪等性"
})
restored = DoclingDocument.model_validate(doc.export_to_dict())
assert restored.texts[0].meta.get_custom_part() == item.meta.get_custom_part()
```

**尚未做：** 三種 provider-to-Canonical 映射、來源支持及接受結果的執行驗證。
`prov: []` 只足以做 schema／欄位處置例，不能證明 evidence 充分。
這不是要求保存所有 provider JSON 或採納 namespaced provider attachment 作為 Canonical schema。

### 同一 schema 的附件更新與方法更新（V06–V08）

另設固定 SOP U1：文字「依附件限值設定」，接著引用 `limit.png`；
圖片 IU1 為「10」，IU2 為「100」。這是**獨立的虛構更新案例**，
不把前節 M1/I1 的「不得略過品質檢查」改寫成另一份固定來源。
沿用同一 candidate／component／Enrichment／evidence／判定結構，
最小內容為 `u-instruction` 及 `u-image`；後者保留原始 path 與固定 package artifact 綁定。

| 欄位／固定事實 | 原候選 | 附件更新候選 | 僅更新方法的候選 |
|---|---|---|---|
| Asset／Source Revision／Package | A-U／S-U1／PK-U1 = U1 + IU1 | A-U／S-U2／PK-U2 = U1 + IU2 | A-U／S-U2／PK-U2 不變 |
| request／profile／完成證據 | R-U1／P-U1／PC-U1 | R-U2／P-U2／PC-U2 | R-U3／P-U3／PC-U3 |
| candidate／schema | K-U1／canonical-v1 | K-U2／canonical-v1 | K-U3／canonical-v1 |
| 原文與引用 | `u-instruction` 保留指示；`u-image` 的 `limit.png` → IU1 | 指示仍 U1；`limit.png` → IU2 | 同 K-U2 的固定來源／引用 |
| 採納 OCR 結果 | EU1：input IU1、target u-image、method OCR-1、text 10 | EU2：input IU2、target u-image、method OCR-1、text 100 | EU3：input IU2、target u-image、method OCR-2；必要意思仍由 IU2 支持 |
| Evidence／mapping | eU1 → IU1；MP-U1 保留必要限值／歸屬 | eU2 → IU2；MP-U2 驗證新限值與新 package 綁定 | eU2 可在支持仍充分時沿用；MP-U3 記錄新方法及實際輸入，不能冒稱新來源 |
| 驗證／預期接受 | VAL-U1 → K-U1；全部適用檢查通過才有 ACC-U1 → C-U1 | VAL-U2 → K-U2；通過才有 ACC-U2 → C-U2 | VAL-U3 → K-U3；通過才有 ACC-U3 → C-U3 |
| 歷史／選用 | C-U1 的內容與引用固定 | C-U1 不改指 IU2；C-U2 是否選用另依目標／目前資格 | C-U3 不令 S-U2 變成更新來源；依已採納方法與既有選用規則判斷 |

必要負例：把 EU1 的「10」帶到 K-U2，只將 evidence 改指 IU2，仍不通過；
把同一接受結果 ACC-U2 重送，不新增 C-U4。整份重做可行，任何重用都保留真實 producing inputs／methods。
來源可靠先後已知為 S-U1→S-U2 時，S-U1 搭配較新 platform-state 前置條件仍不滿足明確 S-U2 目標；
歷史接受與目標就緒分開。固定引用 C-U1/u-image 只解析 IU1，受到目前治理與保留限制，
不能為了可用性暗換 IU2 或恢復已撤回資料。

## 5. 帶入後續驗證的跨案例檢查

| 案例 | 已確認規則要求的處理 |
|---|---|
| Provider 有值欄位未被映射清單涵蓋 | 盤點實際欄位與範圍，選擇納入、保留未解讀或依明確規則省略。未知影響不是丟棄許可，raw 留存不是必要語意已理解；依 Q6。 |
| 新 OCR 修正有來源支持的值 | 新候選、重新接受、驗證來源支持；可以仍是同一固定來源與區域，不設額外定位遷移機制；依 Q7/Q17。 |
| 更新後查歷史引用 | 讀取 C1 自身固定內容／證據，受目前治理與 custody 限制；不可用時交代限制，不以 C2 代替；依 Q7/Q15。 |
| 目標已是 S2，舊 S1 搭配新前置條件送入 | 並行檢查成功不代表 S1 滿足 S2；歷史接受與目標就緒分開；依 Q13。 |
| 接受前有效撤回 | 允許時保留處理／驗證事實，停止接受，晚到成果不能恢復資格；依 Q18。 |
| 接受後發現原條件未滿足 | 保留歷史接受，記錄失效理由／證據／範圍與可歸責判定；停止合格選用並交接 Projection／治理，不等新 revision 完成。後來規則變嚴不等於原接受錯誤；依 Q9。 |
| OCR complete，但必要警告缺失 | completion 不證明必要意思已保存；缺少必要內容仍不得接受。PDF core 的具體允許狀態見[spike](../reviews/knowledge-platform-canonical-spike-2026-10-09.md#保留兩個-pdf-映射負例)。 |
| 映射只帶 OCR 文字／完成 manifest，漏接必要證據 | 檢查實際採用的輸入、方法、結果與必要支撐 artifact 的固定對應；core 已保存不等於候選已正確綁定。缺少必要支持不得接受。 |
| Task／checkpoint 清理 | request record 或未採用中間產物刪除，不等於已接受資料撤回／刪除。採用的依賴遵守 custody／抹除規則，實體機制與期限由既有 owner 決定。 |

後續可執行映射驗證計畫須把採納規則對應到來源核對的預期內容與反例：
參照完整性、順序／包含關係、表格／表頭／註解對應、附件範圍、
來源／方法歸屬與證據支持、必要涵蓋，以及確切候選／接受判定綁定。
既有證據足夠就重用；只有影響本票決策且既有證據無法回答的未知，
才做必要的 executable probe（Q14）。本文件未執行 mapping 或 consumer runtime；V04 只完成 provider schema roundtrip。

### 生命週期效果與權威事實交接

以下整理已確認的整體設計、來源交接及 Q1–Q25，並非新增功能或狀態機。
Canonical 提供自己的候選、接受、失效與選用事實；公開查詢由 Admission 關聯，
目前授權及跨介面執行由 Governance 承接，資料保護／刪除由 Custody 承接。

| 操作／情況 | Canonical 效果與必須保留的事實 | 承接邊界 |
|---|---|---|
| 建立／接受 | 固定完整來源、候選、方法及採用依賴；接受前完成適用檢查與 custody 保護。綁定確切判定與規則，不以 processing complete 代填。 | Processing 提供必要成果；Canonical 判定；Admission 公開結果；Custody 證明保護成立。 |
| 讀取固定 revision | 只解析該 revision 自身內容、來源與證據；目前政策／保留限制仍適用。不能以新版本偷換舊引用。 | Canonical 提供固定參照；Governance 決定可見範圍；Custody 提供可用性；Projection 擁有產品引用。 |
| 來源／方法／採納 Enrichment 改變 | 新完整候選與接受；原已接受內容不變。相容重用可選，整份重做可行。新來源或新方法不自動證明原接受失效。 | Processing 選方法、相容範圍與重處理；Canonical 依 Q7–Q13/Q17 選用；Projection 決定產品更新。 |
| 重送／重複處理 | 同一判定重送不新增 revision；不同候選不強制內容去重。選用依 Q24/Q8。 | Canonical／Custody 保持身分與原子結果；Admission 關聯 request；不新增全域去重服務。 |
| 原接受條件後來發現未滿足 | 保留歷史接受，加上有理由／證據／範圍及可歸責判定的失效事實；停止合格選用，不等修正版。較晚的新規則不證明舊接受錯誤。 | Canonical 提供影響；Projection／Governance 承接產品與披露限制；誤判後的重新評估不改寫歷史。 |
| 已確認且適用的來源刪除／撤回 | 依權威範圍停止相關資格；接受前已涵蓋的撤回阻止新接受，晚到成果不恢復資格。歷史接受不改寫。 | 來源交接提供可信意圖與適用性；Governance 執行停止披露。讀取失敗不擅自推論已刪除。 |
| Task／checkpoint 清理 | 不代表 Canonical 刪除，也不移除仍受保護的必要來源／證據。不同候選共享 artifact 時仍須尊重其保護義務。 | Admission／Processing 清理執行紀錄；Custody 判斷採用／釋放及保留；期限交 operating envelope。 |
| 明確 custody purge | 不再承諾被抹除範圍可重建／可讀；保留的引用不能恢復已失去的內容或權限。哪些決策紀錄可合法保留亦須遵守 purge 範圍。 | Governance／Custody 定範圍、相依副本與完成證據。收到請求、停止披露、完成實體 purge 是不同事實。 |
| Corpus 普通移除成員 | 不改寫／刪除共享 Canonical Revision，不默認撤回其他 Corpus 的使用；依既有目前資格限制。 | Corpus／Projection 處理成員及產品更新。Corpus 刪除與 membership-only 補處理的命令／排程由 Admission 明定，產品輸入與發布效果由 Projection 明定；Governance／Custody 承接治理與清理。若新選擇影響本票必要語意，回本決策 review。 |

上述交接均引用第 6 節的既有決策票。無須每層複製一份全域狀態，
也不能用同一個 `done` 同時表示接受、選用、發布或治理完成。

### 映射驗證程序與案例清單

這是可交付後續實作的驗證程序，**尚未執行，也沒有宣稱 fixture 或 mapper 已完成**。
使用第 4 節原文與預期意思準備固定來源；實際 PDF／PPTX bytes、provider 輸出、
parser／mapper／規則版本及 digest 須在執行前固定。範例 P1/S1/T1 不是已量測的資格證據。
Processing 提供必要 producer 輸出；Canonical integration 負責 mapping／acceptance 檢查，
受影響的 request／custody／policy 行為由表內既有 owner 接測。

每次執行依以下順序，重用已有且範圍相符的測試工具，不先建立通用驗證框架：

1. 固定完整 Capture Package、方法／profile、候選及規則；列出案例需要的來源意思與支持證據。
2. 保存實際 parser／Enrichment 輸出及其身分、完成 manifest、採用依賴；對 provider 有值欄位列明處置。
3. 執行映射；核對參照、順序／包含、內容與關係、方法歸屬、證據及限制，不能只比較 JSON 結構。
4. 對正例與最小負例套用同一版本規則，保存逐項結果、固定候選綁定及來源核對依據。
5. 執行受影響的接受／重送／目前資格與 custody 情境；核對實際可觀察結果，而非只核對呼叫次數。
6. 輸出可追溯的案例清單、固定輸入／方法、實際結果、判定及限制。測試計畫、模擬結果和真實 producer 證據分開標示。

| 案例 | 固定輸入與最小變化 | 預期檢查／結果 | 對應交接 |
|---|---|---|---|
| V01 PDF 表格 | P1：A=2*、B=0、單位次；另產生註解掛 B／條件遺失的負例。 | 正例保留「暫時性錯誤且冪等」及 A 的範圍；負例不得通過對應接受檢查。只宣稱實際 page／region 精度。 | P02/P03/P04，Canonical／Processing。 |
| V02 SOP／附件 | M1/I1；兩個圖片出現位置指向同一 I1；負例漏掉第二個引用或 OCR 警告。 | 保留不同位置／上下文及必要警告；字節相同不合併出現位置。必要內容遺失即失敗。 | P02/P05/P06，Canonical／Processing。 |
| V03 PPTX／獨立 Enrichment | T1 投影片與備註；以固定輸入、方法另產生流程解讀，再納入完整候選；負例交換通過／失敗動作或漏備註。 | 保留方向、條件、動作及來源／生成區分；缺必要意思不得接受。獨立產生結果不等於獨立接受或提前交付。 | P02/P04/P05/P07，Canonical／Processing。 |
| V04 Provider 未映射欄位 | 使用第 4 節已完成 schema roundtrip 的 core 2.96.0 synthetic metadata fixture；比較三種明確 disposition 與 p-note／p-a-limit 的預期映射。 | 有明確納入／未解讀保留／允許省略；未知必要意思不得以 raw 留存冒充合格。歷史 absent/empty 證據不能冒稱非空案例通過。 | P06，Canonical／Processing；必要 raw 保護交 Custody。 |
| V05 必要工作／證據不足 | 有 complete manifest，但缺必要警告或 mapper 漏接已保存 crop／方法／支持關係。 | completion 不代替接受；分辨 producer 缺內容與 mapper 漏交接。錯誤候選不得接受。 | P05/P07/P09，Canonical／Processing／Custody。 |
| V06 附件單獨更新 | 第 4 節獨立 U1/IU1→U1/IU2 案例；IU1 說 10、IU2 說 100；負例保留 EU1 解讀只換 evidence ref。 | 新完整候選保存 IU2 意思；負例失敗。整份重做可行；可選重用須固定相容依據與真實 producing inputs。 | Q12/Q17，P01/P04/P08。 |
| V07 方法更新／歷史引用 | 第 4 節 S-U2 同來源、OCR-1→OCR-2 的 K-U3；另測 OCR 修正但舊 locator 不再支持的負例；C-U1 引用保留。 | 新候選／接受、C-U1 固定；舊 locator 仍支持新內容才可沿用。舊引用只解 C-U1；不支持時失敗，不可用時說明限制。 | Q7/Q10/Q11/Q15/Q17，P04/P08/P09。 |
| V08 舊捕獲／新前置條件 | 第 4 節 S-U1 與可靠較新 S-U2；S-U1 搭配較新 platform-state 前置條件。 | 前置條件成功不令 S-U1 滿足 S-U2 目標；歷史接受可獨立判斷，未知先後保留衝突。 | Q13，P01/P08/P10，Canonical／Admission。 |
| V09 撤回／失效／清理 | 接受前適用撤回；接受後發現原必要條件不符；Task 清理與採用 artifact 保護。 | 分別阻止新接受、保留歷史並停止合格選用、保護必要依賴。晚到成功不復權，收到通知不冒稱全平台 enforcement／purge 完成。 | Q9/Q18/Q21，P09/P10；各層保留自己的權威事實。 |
| V10 重送／競爭候選 | K1→C1 的接受結果重送；同 S1/M1 的新 K2→C2；C1 合格／不合格兩種情況。 | 重送仍 C1；不同候選不要求合併；無明確取代依據保留合格 C1，不能用完成時間或已失格 C1 解決衝突。 | Q24，P01/P07/P10，Canonical／Admission／Custody。 |
| V11 條件式能力 | 當實際用途觸發 C03–C05，固定 x²、fail 內 stop、A 子章節的正例與改義負例；C06–C08 僅在採納具體用途後加入對應案例。 | 保存必要意思；反例不得通過。未選用途／未執行標為未評估，不能列為已支援，也不要求現在啟用全部功能。 | Q23，Canonical 定預期，Processing 選方法／證據。 |

V01–V03 另做一次共用 Wiki／Retrieval 的概念檢查：同一固定輸入能支持第 4 節問答、
跨來源主題／連結及證據追溯。Wiki/RAG 執行、生成品質與發布測試交 Projection，
本票不新增 consumer prototype。若真實來源／方法暴露影響本票決策的未知，先依 Q14
補最小必要證據；其餘方法比較與實作驗收由既有依賴票承接。

## 6. PDF core reconciliation 與整合處置

**2026-10-09 Q23 已確認能力界線與處置，見[決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075950574)。**
本表對照已確認需求、固定 PDF 證據、最小整合差距及受影響驗證。
P01–P10 與第 5 節驗證計畫已於 2026-10-10 通過最終完整性確認，作為後續整合交接。
本票 reconciliation 結案條件已完成；不宣稱 Canonical mapper 已通過。
PDF core 固定為 `fe1b283c49c83ad5aeee6808e77b4f25549eba03`；
Docling research 固定為 `47b363781448cc72d6cb12df2b76927c101c2e23`。
Q22 的 P1 表格是虛構來源的預期內容；「2 次」不是 worker retry 設定。

### 能力需求與方法處置（Q23 已確認）

以下分開記錄需求狀態與方法狀態。C01/C02 重述既有要求；
C03–C05 是已確認的條件式需求；C06–C08 是已確認的用途／方法處置，並未選定新功能。
「條件式」表示只有選定來源／用途需要該意思時才成為必要要求，並非現在啟用所有功能。
方法延後不能豁免 Q1–Q3 已確認的必要內容、結構或來源支持。
目前沒有證據可宣稱下列新方法已滿足接受條件。

| 能力 | 需求狀態與最小接受界線 | 既有輸出／證據及差距 | 方法狀態與最小承接 |
|---|---|---|---|
| C01 原文、表格、caption、順序與來源證據 | **已確認**：保存用途所需的意思、結構、關係及實際支持範圍；沿用 Q1–Q6/Q16/Q22。 | 見 P02–P06；既有 PDF 證據有明確 fixture/profile 範圍，未證明三格式全面合格。 | 沿用合格輸出，補映射或必要方法的選擇交 Processing；Canonical 提供 Q22 與 P02–P06 的預期結果。 |
| C02 圖／流程的必要意思 | **已確認**：Q16/Q22 允許有來源支持的文字 Enrichment 保存方向、條件、分支及動作；可靠 native 結構仍保留。 | 既有 PictureItem OCR 不等於流程理解；描述是[可用選項][docling-capabilities]，未因研究而採用或證明品質。 | **未選通用圖片描述功能**。Processing 按必要圖意選方法；先沿用 PPTX 通過／失敗分支案例，不要求描述每張圖片。 |
| C03 公式 | **已確認的條件式需求**：來源／用途依賴公式時，保留必要符號、上下標、運算關係及定義。最小反例：把 x² 留成 x2 會改變意思，不能宣稱該用途合格。 | [研究][docling-capabilities]列公式重建候選；現有 core 未啟用該重建方法，也未證明本反例可通過。 | **方法未選**。有對應來源／用途時，Canonical 固定一個來源核對案例，Processing 選最小抽取／重建方法。無須公式求解或符號運算。 |
| C04 程式碼／偽碼 | **已確認的條件式需求**：用途依賴程式片段時，保留影響解讀的符號、縮排／區塊、順序與上下文。最小反例：把原本只在 fail 分支執行的 stop 移出該分支。 | [研究][docling-capabilities]列 code reconstruction 候選；現有 core 未啟用或驗證其效果。 | **方法未選**。有對應來源／用途時固定一個區塊案例，Processing 選抽取方式；語言資訊須有依據。無須執行、編譯、AST 或正確性證明。 |
| C05 PDF 章節層級 | **已確認的條件式需求**：用途依賴章節深度／作用範圍時，保留可靠的標題與父章節對應。最小反例：把「僅適用 A」的子節掛到 B。不確定時不得冒稱正確層級。 | 已有 heading item 不證明 depth 正確；[研究][docling-capabilities]中的新版階層恢復尚未採納，涉及套件與 checkpoint 變更。 | **方法未選**。以來源 outline 和一個錯掛反例確認需要，再由 Processing 評估；不要求每份 PDF 都有完美章節樹，也不由此直接採納升版。 |
| C06 掃描頁文字／page OCR | **掃描 workload 尚未選定**。已確認用途所需的文字／警告保存要求仍適用。 | P05 的 picture OCR 不等於 page OCR；目前沒有 scan-first 資格證據。[研究][docling-capabilities]。 | **延後方法選擇**。pilot 選到掃描來源且原生文字不足時，Processing 評估必要 OCR、涵蓋及失敗紀錄；來源有必要警告卻遺失的候選仍不得接受。 |
| C07 圖表數值抽取 | **已確認延後通用抽取功能**。必要圖意仍受 Q1–Q3 約束；尚未增加通用機器可查數值的用途。 | [研究][docling-capabilities]列 chart extraction 候選，未證明值、單位、軸及 series 可靠；已取得的 provider 有值欄位仍依 Q6 處置。 | 若具體用途需要精確數值查詢，先由 Canonical 確認值／單位／軸／series 的接受案例，Processing 再選方法。趨勢描述不能代替已要求的精確數值。 |
| C08 依指定 schema 抽取事實 | **已確認延後新增 reusable fact schema／功能**。不以有效 JSON、模型信心取代來源內容或事實支持。 | [研究][docling-capabilities]列 schema-driven extraction 候選，尚無本平台已確認的 fact schema、用途或資格證據。 | 具體通用用途成立時回 Canonical 決定接受契約，再交 Processing；consumer 專用抽取交 Projection。無須現在建立通用 fact extraction 框架。 |

上述反例是概念上的預期結果，並非已執行 fixture。只在決策所需事實無法由既有證據回答時，
依 Q14 做最小 executable probe；不因表格列出能力就要求所有 optional models 全面驗證。

**已確認的工作分工與順序：** 本票先整理必要意思、可接受限制、上述處置與 P01–P10 差距；
[Set the first-adoption workload and operating envelope](https://github.com/davidlinnnn/data-ingestion/issues/54)
可獨立決定實際 pilot 與資源／時效條件。
[Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72)
結合兩票的已確認輸入，選擇最小能力組合、方法／版本／模型／profile 及所需證據，
再交規格與實作整合。
[Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55)
承接產品選擇與 consumer 設計；其原生 prerequisite 是本票，不要求先等所有 Processing 決策。
Docling 升版、WeKnora 產品採用或服務拓撲均未在此採納。
原生依賴與各票目標維持不變；只有具體可行性衝突才回到需求 owner。

### PDF core reconciliation matrix

| 已確認需求 | 固定輸出與證據限制 | 缺口／建議處置與承接 | 最小受影響驗證；尚未執行 |
|---|---|---|---|
| P01 固定來源與候選身分；Q1/Q2/Q21 | request 有 source revision、artifact version/digest、profile；Workflow ID 是執行身分。[Handoff][pdf-handoff]。 | Canonical 綁定 Asset、完整 Capture Package、候選及接受 revision；Admission 保留 request／前置條件關聯；Processing 整合既有 request binding。 | 相同 PDF bytes、不同來源觀測／package 不因 digest 相同而合併；接受紀錄綁對候選。 |
| P02 Typed content、包含／順序／引用；Q4/Q15/Q16/Q20 | Docling graph 有 typed collections、parent/children/captions；Q04 核對引用完整性。遍歷不是閱讀順序；額外關係方法限指定區域的 local-function-block，保留 unknown。[Graph][pdf-graph]、[限制][pdf-limits]、[關係方法][pdf-relations]。 | Canonical 映射版本內參照、有依據的順序與關係，保留 unresolved／coverage；必要關係未能可靠取得時交 Processing。 | 映射後包含／caption 仍指向原目標；必要順序不能由 collection 遍歷假造。 |
| P03 表格值、表頭、單位、註解；Q14/Q16/Q22 | 有 cell offset/span 與來源核對；188／60 cells 是限定 fixture 證據。note associations 限 parser links，未證明 P1 語意。[Cells][pdf-cells]、[限制][pdf-limits]、[研究][research-retained]。 | Canonical 保留並驗證 P1 的值與作用範圍；現有輸出不足時，Processing 評估最小補足方法。 | P1 的 A＝最多 2 次，且暫時性錯誤／冪等條件都在；註解改掛 B 或遺失任一條件即不通過。 |
| P04 實際定位精度與支持範圍；Q5/Q15/Q17 | 有固定 source/page、原頁對應、TOPLEFT points、renderer、region/crop recipe；部分符號僅保留整頁 context。recipe 不表示已保存獨立 crop。[Locators][pdf-locators]。 | Canonical 映射實際精度、支持範圍、採用 rendering/crop 與原來源對應；Processing 補必要定位／語意證據，Custody 保護採用依賴。 | P1 表格／註解回到固定原 PDF 第 3 頁；僅有頁級支持時，不宣稱已驗證 cell 精度。 |
| P05 OCR 與原文／生成解讀的歸屬；Q1/Q5/Q10/Q21 | 選取已輸出的 PictureItems，排除 page render；有 source/method/outcome 與保存的 crop。complete 可包含 no_text_detected；無 PictureItem 可 not_applicable。[Selection/finalize][pdf-enrichment]、[OCR 核對][pdf-ocr]。 | Canonical 綁實際輸入、目標、方法、結果及證據；Processing 驗證必要偵測／OCR 能力；Custody 保護採用 crop。 | 來源有必要警告而候選缺失時，即使 OCR complete、bytes／method 正確，仍不得接受。 |
| P06 Provider 有值欄位的明確處置；Q6/Q21 | 既有枚舉未覆蓋 field_regions/field_items 與所有 metadata。研究發現 comparator 盲點；所查歷史輸出 absent/empty，未證明實際 populated 欄位已遺失。[研究][research-retained]。 | Canonical 盤點實際欄位並納入、保留未解讀或依規則省略；Processing 保全被採納欄位的 adapter 輸出；必要 raw 依賴交 Custody。 | 對採納的未覆蓋欄位加一份有效且非空的 provider fixture，驗證明確 disposition；raw equality 不代替必要語意檢查。 |
| P07 Processing Completion 與接受；Q1–Q3/Q21 | finalization 核對必要工作及歸屬；manifest 明列 canonical_accepted=false、quality_accepted=false。Temporal 正常結束仍可能 processing failed。[Handoff][pdf-handoff]、[finalize][pdf-enrichment]。 | Canonical 提供 exact-candidate／規則／檢查／判定事實；Processing 維持 required-work barrier；Admission 分開呈現結果。 | complete manifest 進入候選驗證，但 P1 註解缺失時不得產生接受；不能以執行完成代填。 |
| P08 方法更新與相容重用；Q7/Q8/Q10–Q13/Q17 | core 分 stage 相容依賴，可重用相容 page-group／assembly；新 request 仍有固定 plan 及 request-bound 結果。不保證跨 request Enrichment payload 重用。[相容依賴][pdf-compat]、[重用範圍][pdf-reuse]。 | Canonical 新結果形成完整新候選並重新接受；Processing 定方法/profile及重用範圍；Admission 保留新 request；Governance 提供目前適用權限。整份重做可行。 | 同一 source 更新 OCR 方法產生新候選／方法歸屬，C1 不變；舊 request 不被暗換 profile。相容 parse 重用是可選路徑。 |
| P09 採用依賴與 custody；Q1/Q21 | export 逐檔經 checked Store 讀取，提供 version/hash/operation inventory；不是平台採用或 retention policy。[Export][pdf-export]、[保留交接][pdf-retention]。 | Canonical 指明接受所需依賴，接受前確認保護成立；Custody 定採用／釋放／保留／purge；Admission 的 request TTL 不支配資料 TTL。 | Task/checkpoint 清理後，C1 必要來源及採用證據仍有適用保護；保護未成立時不能完成接受。 |
| P10 目前資格、失效與 status；Q8/Q9/Q13/Q18/Q21 | core 有 progress/error/time/reuse/final ref；未提供平台接受、選用、資格與各 Projection 發布的統一查詢。[狀態][pdf-status]。 | Canonical 供驗證／接受／失效／selection 權威事實；Admission 公開查詢與關聯；Governance 處理適用政策／enforcement；Custody 處理保留／purge。 | 接受前有效撤回後才完成 processing，可記錄真實完成／驗證；不得產生新接受或恢復資格。另保留 Q9 原條件失效及 Q13 舊來源案例。 |

### 最小交接與完成條件

以下是已確認的既有責任具體交接，未建立新服務或反向依賴。
每個 owner 後續在自己的規格與實作票引用上表列號，保留對應的受影響驗證。
若實測無法滿足必要意思，須回本票討論用途／限制，不能自行降低已確認要求。

| 責任 | 本表交接／完成條件 | 既有決策票 |
|---|---|---|
| Canonical | P01–P10 的映射、接受與權威事實；連同三格式／跨案例的來源核對預期結果。 | [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32) |
| Processing | P02–P08 的實際輸出差距、方法／profile、完成及重用整合；為所選方法保留固定輸入與品質證據。 | [Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72) |
| Admission | P01/P07/P08/P10 的 request 關聯、前置條件與可區別的公開狀態；不複製接受判定權。 | [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31) |
| Governance／Custody | P04/P05/P09/P10 的目前資格、採用依賴、清理／purge 與完成證據；數值期限留給 operating envelope。 | [Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56)；[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57) |
| Projection | 使用同一固定輸入做 Q22 問答與跨來源組織；自行驗證產品、引用與發布行為。 | [Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55) |

這裡列的是待實作的受影響驗證；具體映射驗證計畫見第 5 節 V01–V11，兩者都不是已執行結果。
該計畫仍須固定 fixture／method、測試步驟、輸出證據與通過／失敗條件。
未變的 PDF 資格證據只在原 fixture/profile/runtime 範圍內沿用。

### Docling／WeKnora 研究處置

WeKnora research 固定為 `d7dd71374f63e9d55a3f7ee297696fa2c0765dde`。
「已涵蓋」指現有決策已有對應要求；研究中的 adopt candidate 不自動變成已採納功能。
以下依既有原則及 Q23 確認整理研究對照。延後方法／產品選擇，不延後必要內容要求。
最終 completeness review 與各 owner 的規格／驗證交接仍須完成。

| 研究組別與來源 | 對照／建議處置 | 理由與最小承接 |
|---|---|---|
| 正常化內容與未映射欄位；[Docling deliverables][docling-contract] | 已涵蓋：Q1/Q4/Q6/Q16/Q21，落到 P02/P03/P06。 | 不因研究推薦就採用 namespaced provider attachment 或永久保留所有 raw JSON；正式表示另行 review。 |
| 跨格式 locator、來源／生成歸屬、修改後支持；[WeKnora candidates][weknora-candidates] | 已涵蓋：Q5/Q7/Q15/Q17/Q20；P04/P05。 | 借用反例；不照搬可變 chunk 或一律清 locator。新內容以實際來源支持判定，歷史引用保持原義。 |
| Completion、quality、acceptance；[Docling retained-output][research-retained]、[WeKnora matrix][weknora-matrix] | 已涵蓋；不採用錯誤等同：Q1–Q3/Q9/Q21，P05/P07。 | 有效 JSON、raw equality、模型信心、terminal counter 或引用存在，不代替必要意思／來源支持。 |
| 不可變 revision、重處理、撤回與 custody；[Docling lifecycle][docling-lifecycle]、[WeKnora matrix][weknora-matrix] | 已涵蓋：Q7–Q13/Q15/Q18/Q21，P08–P10。 | 機制與期限交既有 owner；不把來源指令當政策授權，也不將此表當全部 CRUD 已完成。 |
| Wiki／Retrieval 共用輸入與 exports/chunks；[Docling consumer cases][docling-consumers]、[WeKnora shared chunks][weknora-chunks] | 已涵蓋：Q4/Q14/Q16/Q19/Q22；不採用 chunk/export＝Canonical 的等同。 | Projection 擁有組織、chunking、引用與產品品質；較早研究的 adapter demo 建議不恢復為本票結案前提。 |
| 描述、公式、程式碼、heading、page OCR、chart、schema extraction；[Docling capabilities][docling-capabilities] | Q23 已確認分項需求與處置，見本節 C02–C08；具體方法／profile 尚未選定。 | 本票先決定必要意思／限制，Processing 結合已確認需求與 pilot 選最小方法。方法未選不豁免必要語意，也不表示所有 optional features 必做。 |
| Remote API、Activity pools、KServe、serve／升版／recovery；[Docling topology][docling-topology]、[WeKnora candidates][weknora-candidates] | 延後方案選擇，交 Processing／Admission／Governance／Custody 與 operating envelope。 | 不採納服務拓撲、queue、cache／conversion framework 或數字預設；所選方案仍需 owner 決策及 scoped evidence。 |
| WeKnora 產品、editor/diff、元件重用、QA metrics；[採用路徑及處置][weknora-adoption] | 延後產品採用；不採用其 schema／status 作契約等價物。 | Projection 與 operating envelope 比較價值／成本；metrics 不證明表格保真或 Wiki 真實性。延後不是永久拒絕產品。 |

## 7. 最終整體 review 與結案工作

Q20–Q25 均已於 2026-10-09 確認。Q24 已於 2026-10-09 確認重送／不同候選／目前選用規則；
Q25 已確認版本內引用、三格式定位及必要未知結果區別。
各輪確認只涵蓋其明列範圍；第 4 節完整候選與以下整合交接，已於 2026-10-10 獲使用者最終確認。
詳見 [resolution](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6096650145)。

| 已完成的設計結案要求 | 已確認材料 | 後續承接 |
|---|---|---|
| 第一版共同表示與接受契約 | 第 2–3 節六組資訊、必要／條件必要欄位、固定外部參照、確切候選判定；第 4 節三份同 schema 候選。 | 完整邏輯表示已確認可作規格基礎。正式型別／欄位編碼及 API 隨所依賴設計收斂後形成 buildable spec；不改已確認語意。 |
| 三格式／困難／更新案例 | 第 4 節 PDF、SOP、PPTX 與共用 Wiki／Retrieval 問答；非空 provider 欄位處置；附件／方法更新及歷史引用。 | 正反例已確認落實本票用途。真實 source bytes、mapper 與處理方法的執行資格另由具體整合驗證。 |
| 版本與生命週期效果 | 第 3、5 節區分接受、選用、目前資格、撤回、失效、清理與 purge。 | 將權威事實交接既有 Admission／Governance／Custody owner；機制與數字期限仍由其決策。 |
| Processing／Projection／status 交接 | 第 5–6 節權責及必要輸入／輸出／判定證據。 | Processing 選方法，Projection 擁有產品與發布，Admission 關聯公開狀態；不把 completion 當接受／發布。 |
| PDF core reconciliation | 第 6 節 P01–P10：固定 core 證據、涵蓋限制、具體差距、owner 與受影響驗證。 | 差距交接已確認完整；既有相依 Processing 決策承接方法／profile 及整合，Canonical 保留表示與接受責任。 |
| Docling／WeKnora 處置 | 第 6 節 C01–C08 及研究處置表。 | 必要意思不因方法延後而豁免；條件式需求等實際用途觸發，不全面啟用 optional features。 |
| 可執行映射驗證計畫 | 第 5 節 V01–V11：固定輸入、最小變化、步驟、預期結果與 owner。 | 後續實作固定真實 fixtures／方法／規則，執行並保存結果。本次不是 V01–V11 已通過的宣告。 |
| 領域文件與歷史 ADR | [CONTEXT.md](../../CONTEXT.md)、[決策 checkpoint](knowledge-platform-canonical-design.md)、[截至 Q25 的 ADR 盤點](../reviews/knowledge-platform-historical-adr-reconciliation-2026-10-09.md)。 | ADR-0001–0003 保留，0004–0006 補記歷史取捨；其餘有不另立理由。盤點已完成，最終 review 已呈現並確認。 |

**本次實際檢查：** 文件連結／表格與三份 JSON 候選的參照唯一性、參照解析、
表格位置、locator 範圍及已確認案例值。另以既有 docling-core 2.96.0 執行 V04 自訂 metadata schema roundtrip。
獨立只讀 review 未發現中等或重大不一致。這些檢查不證明真實 parser、mapper、來源語意品質或 consumer 效果。

**最終確認範圍：** 使用者採納共同表示、接受／生命週期規則、完整案例、驗證計畫及 owner 交接，
作為本票設計結論。此確認不選套件／模型、儲存方案，也不核准未執行的 runtime 結果。
正式編碼與 buildable spec 隨所依賴設計輸入收斂；必要整合與執行驗證須進入具體 implementation tickets。

2026-10-10 的 [resolution](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6096650145)記錄最終共同理解、結案證據及後續責任。
本票結案不代表整個 map 已完成，也不越過 Processing、Projection、Governance 或 Custody 的未決工作。

[pdf-handoff]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/HANDOFF.md#L8
[pdf-attribution]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L236
[pdf-graph]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L42
[pdf-cells]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L84
[pdf-locators]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/evidence.py#L134
[pdf-limits]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/evidence.py#L215
[pdf-ocr]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L273
[research-retained]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L250
[pdf-relations]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/relationships.py#L128
[pdf-enrichment]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/enrichment.py#L14
[pdf-compat]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/compatibility.py#L54
[pdf-reuse]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/README.md#L164
[pdf-export]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/manage.py#L34
[pdf-retention]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/RUNBOOK.md#L149
[pdf-status]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/RUNBOOK.md#L111
[docling-contract]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L137
[docling-lifecycle]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L220
[docling-consumers]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L155
[docling-capabilities]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L82
[docling-topology]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L186
[weknora-candidates]: https://github.com/davidlinnnn/data-ingestion/blob/d7dd71374f63e9d55a3f7ee297696fa2c0765dde/docs/research/weknora-knowledge-platform-fit-2026-10-05.md#L157
[weknora-matrix]: https://github.com/davidlinnnn/data-ingestion/blob/d7dd71374f63e9d55a3f7ee297696fa2c0765dde/docs/research/weknora-knowledge-platform-fit-2026-10-05.md#L93
[weknora-chunks]: https://github.com/davidlinnnn/data-ingestion/blob/d7dd71374f63e9d55a3f7ee297696fa2c0765dde/docs/research/weknora-knowledge-platform-fit-2026-10-05.md#L73
[weknora-adoption]: https://github.com/davidlinnnn/data-ingestion/blob/d7dd71374f63e9d55a3f7ee297696fa2c0765dde/docs/research/weknora-knowledge-platform-fit-2026-10-05.md#L128
