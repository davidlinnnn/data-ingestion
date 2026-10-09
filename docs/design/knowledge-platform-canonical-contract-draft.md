# Canonical 契約與三格式案例草稿

[設計索引](README.md) · [已確認決策](knowledge-platform-canonical-design.md) · [領域術語](../../CONTEXT.md)

**2026-10-08 建立；2026-10-09 納入 Q20–Q22 確認。邏輯骨架已確認；正式 schema 與實作規格仍待完成。**
本文件服務 [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32)。
沿用 Q1–Q18、Q19 撤回紀錄與 Q20–Q22 確認。重複附件表示、六組資訊與確切候選的驗證／接受紀錄，
以及最少重複原則已確認。Q22 確認三格式具體問答的必要意思與證據基準。
正式欄位名稱、編碼與完整困難／更新案例整合仍待 review；本文件不是 parser 執行結果或能力驗證。
2026-10-09 的[候選 spike](../reviews/knowledge-platform-canonical-spike-2026-10-09.md)提供既有原則澄清與簡化建議；
其後的 [Q21 決策](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075416972)採納上述邏輯範圍，未採納正式 schema。

## 1. 本輪如何閱讀

| 標示 | 意義 |
|---|---|
| 已確認 | checkpoint 中的必要語意與責任邊界；選欄位名稱時不重新開啟原則。 |
| 已確認 Q22 | 三格式具體問答的預期意思與來源證據，作為設計驗證基準。 |
| 已確認 Q21 | 六組必要資訊、綁定確切候選的驗證／接受紀錄與最少重複原則。 |
| 草稿表示 | 用第一版 schema 承載已確認語意的具體方式；正式名稱與 ID 是示意，尚非 wire syntax 或資料表欄位。 |
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
上述為已確認的邏輯表示原則；正式欄位與編碼仍待 review。處理輸入、結果目標與支持證據的角色不同，不能為去重而混同。

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

| 案例 | 內容表示草稿 | 來源定位 |
|---|---|---|
| PDF 表格 | 列欄、儲存格文字與位置／跨列跨欄、表頭對應、單位及註解的作用範圍 | 固定原始 PDF 與實體頁面；有依據才提供 region／cell 精度。bbox 須說明座標原點與單位。crop recipe 不等於已保存 crop。 |
| SOP Markdown | 標題、完整文字、有順序及巢狀的步驟、條件／禁止事項、原始連結與附件綁定 | 固定 Markdown 與行／區塊位置；圖片另有固定 artifact 與定位，不強迫套用 PDF 頁碼。 |
| PPTX | 投影片順序、可取得的 native 文字／shape／表格／備註；可靠關係或足以保存必要圖意的文字 Enrichment | 固定 PPTX 與投影片；有支持才提供 shape／notes 位置。若解讀依賴 rendering，指明採用的固定 rendering 與原投影片對應。 |

上述是邏輯要求，不表示每種 locator／worker 已實作。
案例採人可讀、從 1 起算的位置；正式索引／座標編碼須在 schema review 時明定。

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

候選內容草稿：

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

**候選組件草稿；Q20 已確認重複引用各自保留位置與上下文，示意欄位／ID 尚非正式編碼：**

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
才做必要的 executable probe（Q14）。本草稿未執行 mapping 或 consumer runtime。

## 6. PDF core reconciliation 與整合處置草稿

**2026-10-09 整理；待 Q23 review。** 本表對照已確認需求、固定 PDF 證據、
最小整合差距及受影響驗證。草稿不宣稱 Canonical mapper 已通過，也不完成結案 gate。
PDF core 固定為 `fe1b283c49c83ad5aeee6808e77b4f25549eba03`；
Docling research 固定為 `47b363781448cc72d6cb12df2b76927c101c2e23`。
Q22 的 P1 表格是虛構來源的預期內容；「2 次」不是 worker retry 設定。

### 能力需求與方法處置（Q23 提案）

**本輪尚未確認。** 以下分開記錄需求狀態與方法狀態。C01/C02 重述既有要求；
C03–C05 是建議的條件式需求；C06–C08 說明尚未選定的用途或功能。
「條件式」表示只有選定來源／用途需要該意思時才成為必要要求，並非現在啟用所有功能。
方法延後不能豁免 Q1–Q3 已確認的必要內容、結構或來源支持。
目前沒有證據可宣稱下列新方法已滿足接受條件。

| 能力 | 需求狀態與最小接受界線 | 既有輸出／證據及差距 | 方法狀態與最小承接 |
|---|---|---|---|
| C01 原文、表格、caption、順序與來源證據 | **已確認**：保存用途所需的意思、結構、關係及實際支持範圍；沿用 Q1–Q6/Q16/Q22。 | 見 P02–P06；既有 PDF 證據有明確 fixture/profile 範圍，未證明三格式全面合格。 | 沿用合格輸出，補映射或必要方法的選擇交 Processing；Canonical 提供 Q22 與 P02–P06 的預期結果。 |
| C02 圖／流程的必要意思 | **已確認**：Q16/Q22 允許有來源支持的文字 Enrichment 保存方向、條件、分支及動作；可靠 native 結構仍保留。 | 既有 PictureItem OCR 不等於流程理解；描述是[可用選項][docling-capabilities]，未因研究而採用或證明品質。 | **未選通用圖片描述功能**。Processing 按必要圖意選方法；先沿用 PPTX 通過／失敗分支案例，不要求描述每張圖片。 |
| C03 公式 | **條件式需求提案**：來源／用途依賴公式時，保留必要符號、上下標、運算關係及定義。最小反例：把 x² 留成 x2 會改變意思，不能宣稱該用途合格。 | [研究][docling-capabilities]列公式重建候選；現有 core 未啟用該重建方法，也未證明本反例可通過。 | **方法未選**。有對應來源／用途時，Canonical 固定一個來源核對案例，Processing 選最小抽取／重建方法。無須公式求解或符號運算。 |
| C04 程式碼／偽碼 | **條件式需求提案**：用途依賴程式片段時，保留影響解讀的符號、縮排／區塊、順序與上下文。最小反例：把原本只在 fail 分支執行的 stop 移出該分支。 | [研究][docling-capabilities]列 code reconstruction 候選；現有 core 未啟用或驗證其效果。 | **方法未選**。有對應來源／用途時固定一個區塊案例，Processing 選抽取方式；語言資訊須有依據。無須執行、編譯、AST 或正確性證明。 |
| C05 PDF 章節層級 | **條件式需求提案**：用途依賴章節深度／作用範圍時，保留可靠的標題與父章節對應。最小反例：把「僅適用 A」的子節掛到 B。不確定時不得冒稱正確層級。 | 已有 heading item 不證明 depth 正確；[研究][docling-capabilities]中的新版階層恢復尚未採納，涉及套件與 checkpoint 變更。 | **方法未選**。以來源 outline 和一個錯掛反例確認需要，再由 Processing 評估；不要求每份 PDF 都有完美章節樹，也不由此直接採納升版。 |
| C06 掃描頁文字／page OCR | **掃描 workload 尚未選定**。已確認用途所需的文字／警告保存要求仍適用。 | P05 的 picture OCR 不等於 page OCR；目前沒有 scan-first 資格證據。[研究][docling-capabilities]。 | **延後方法選擇**。pilot 選到掃描來源且原生文字不足時，Processing 評估必要 OCR、涵蓋及失敗紀錄；來源有必要警告卻遺失的候選仍不得接受。 |
| C07 圖表數值抽取 | **建議延後通用抽取功能**。必要圖意仍受 Q1–Q3 約束；尚未增加通用機器可查數值的用途。 | [研究][docling-capabilities]列 chart extraction 候選，未證明值、單位、軸及 series 可靠；已取得的 provider 有值欄位仍依 Q6 處置。 | 若具體用途需要精確數值查詢，先由 Canonical 確認值／單位／軸／series 的接受案例，Processing 再選方法。趨勢描述不能代替已要求的精確數值。 |
| C08 依指定 schema 抽取事實 | **建議延後新增 reusable fact schema／功能**。不以有效 JSON、模型信心取代來源內容或事實支持。 | [研究][docling-capabilities]列 schema-driven extraction 候選，尚無本平台已確認的 fact schema、用途或資格證據。 | 具體通用用途成立時回 Canonical 決定接受契約，再交 Processing；consumer 專用抽取交 Projection。無須現在建立通用 fact extraction 框架。 |

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

以下是既有責任的具體交接草稿，未建立新服務或反向依賴。
每個 owner 後續在自己的規格與實作票引用上表列號，保留對應的受影響驗證。
若實測無法滿足必要意思，須回本票討論用途／限制，不能自行降低已確認要求。

| 責任 | 本表交接／完成條件 | 既有決策票 |
|---|---|---|
| Canonical | P01–P10 的映射、接受與權威事實；連同三格式／跨案例的來源核對預期結果。 | [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32) |
| Processing | P02–P08 的實際輸出差距、方法／profile、完成及重用整合；為所選方法保留固定輸入與品質證據。 | [Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72) |
| Admission | P01/P07/P08/P10 的 request 關聯、前置條件與可區別的公開狀態；不複製接受判定權。 | [Design ingestion admission, task status, and infrastructure integration](https://github.com/davidlinnnn/data-ingestion/issues/31) |
| Governance／Custody | P04/P05/P09/P10 的目前資格、採用依賴、清理／purge 與完成證據；數值期限留給 operating envelope。 | [Define governance enforcement across canonical data and published views](https://github.com/davidlinnnn/data-ingestion/issues/56)；[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57) |
| Projection | 使用同一固定輸入做 Q22 問答與跨來源組織；自行驗證產品、引用與發布行為。 | [Define canonical consumption and publication for Wiki and Retrieval](https://github.com/davidlinnnn/data-ingestion/issues/55) |

這裡列的是待實作的受影響驗證，不是已執行結果或已完成的 runnable mapping-validation plan。
該計畫仍須固定 fixture／method、測試步驟、輸出證據與通過／失敗條件。
未變的 PDF 資格證據只在原 fixture/profile/runtime 範圍內沿用。

### Docling／WeKnora 研究處置草稿

WeKnora research 固定為 `d7dd71374f63e9d55a3f7ee297696fa2c0765dde`。
「已涵蓋」指現有決策已有對應要求；研究中的 adopt candidate 不自動變成已採納功能。
下列對照待同輪 review。延後方法／產品選擇，不延後必要內容要求。

| 研究組別與來源 | 對照／建議處置 | 理由與最小承接 |
|---|---|---|
| 正常化內容與未映射欄位；[Docling deliverables][docling-contract] | 已涵蓋：Q1/Q4/Q6/Q16/Q21，落到 P02/P03/P06。 | 不因研究推薦就採用 namespaced provider attachment 或永久保留所有 raw JSON；正式表示另行 review。 |
| 跨格式 locator、來源／生成歸屬、修改後支持；[WeKnora candidates][weknora-candidates] | 已涵蓋：Q5/Q7/Q15/Q17/Q20；P04/P05。 | 借用反例；不照搬可變 chunk 或一律清 locator。新內容以實際來源支持判定，歷史引用保持原義。 |
| Completion、quality、acceptance；[Docling retained-output][research-retained]、[WeKnora matrix][weknora-matrix] | 已涵蓋；不採用錯誤等同：Q1–Q3/Q9/Q21，P05/P07。 | 有效 JSON、raw equality、模型信心、terminal counter 或引用存在，不代替必要意思／來源支持。 |
| 不可變 revision、重處理、撤回與 custody；[Docling lifecycle][docling-lifecycle]、[WeKnora matrix][weknora-matrix] | 已涵蓋：Q7–Q13/Q15/Q18/Q21，P08–P10。 | 機制與期限交既有 owner；不把來源指令當政策授權，也不將此表當全部 CRUD 已完成。 |
| Wiki／Retrieval 共用輸入與 exports/chunks；[Docling consumer cases][docling-consumers]、[WeKnora shared chunks][weknora-chunks] | 已涵蓋：Q4/Q14/Q16/Q19/Q22；不採用 chunk/export＝Canonical 的等同。 | Projection 擁有組織、chunking、引用與產品品質；較早研究的 adapter demo 建議不恢復為本票結案前提。 |
| 描述、公式、程式碼、heading、page OCR、chart、schema extraction；[Docling capabilities][docling-capabilities] | 分項需求及方法狀態見本節 C02–C08；條件式需求及延後處置仍待 Q23 確認。 | 本票先決定必要意思／限制，Processing 結合已確認需求與 pilot 選最小方法。方法未選不豁免必要語意，也不表示所有 optional features 必做。 |
| Remote API、Activity pools、KServe、serve／升版／recovery；[Docling topology][docling-topology]、[WeKnora candidates][weknora-candidates] | 延後方案選擇，交 Processing／Admission／Governance／Custody 與 operating envelope。 | 不採納服務拓撲、queue、cache／conversion framework 或數字預設；所選方案仍需 owner 決策及 scoped evidence。 |
| WeKnora 產品、editor/diff、元件重用、QA metrics；[採用路徑及處置][weknora-adoption] | 延後產品採用；不採用其 schema／status 作契約等價物。 | Projection 與 operating envelope 比較價值／成本；metrics 不證明表格保真或 Wiki 真實性。延後不是永久拒絕產品。 |

## 7. 下一輪待決與結案工作

**Q20 已於 2026-10-09 確認：** 同一必要附件的各出現位置保留自己的引用與上下文，
共同指向 Capture Package 中的固定 artifact；不要求複製圖片或分別接受。
[決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6074671955) 補足[來源交接](knowledge-platform-source-handoff.md)留給本票的文件內表示。

**Q21 已於 2026-10-09 確認：** 六組資訊、綁定確切候選的驗證／接受紀錄與最少重複原則，
見 [Q21 決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075416972)。
**Q22 已於 2026-10-09 確認：** 三格式具體問答的必要意思與來源證據基準，
見 [Q22 決策紀錄](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6075543252)。
正式欄位／編碼與完整困難／更新案例整合仍待 review；上述確認不代表實際 parser／mapper 或 consumer 通過驗收。
結案前仍需完整三格式／困難案例整合 review、接受與驗證計畫、
權威事實交接與生命週期效果、完整 PDF reconciliation、
研究 disposition，以及強制的歷史 ADR 盤點／補記。
Q23 待 review：第 6 節 C01–C08 的能力需求／方法處置、P01–P10 的 PDF 整合差距、owner 交接與研究處置。
本輪只確認補強此表與交接的工作計畫；尚未確認 C03–C05 條件式需求或 C06–C08 處置。
本草稿不構成結案或 map 已解決索引更新。

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
