# Canonical 契約與三格式案例草稿

[設計索引](README.md) · [已確認決策](knowledge-platform-canonical-design.md) · [領域術語](../../CONTEXT.md)

**2026-10-08 review 草稿。尚未採納為 schema 或實作規格。**
本文件服務 [Design canonical representation, acceptance and lifecycle across PDF, Markdown, and PPTX](https://github.com/davidlinnnn/data-ingestion/issues/32)。
沿用 Q1–Q18 與 Q19 撤回紀錄。下列欄位名稱、具體表示方式與案例仍待 review；
它們不是 parser 執行結果、已接受資料或能力驗證。

## 1. 本輪如何閱讀

| 標示 | 意義 |
|---|---|
| 已確認 | checkpoint 中的必要語意與責任邊界；選欄位名稱時不重新開啟原則。 |
| 草稿表示 | 用第一版 schema 承載已確認語意的具體方式；名稱與 ID 是示意，尚非 wire syntax 或資料表欄位。 |
| 待決 Q20 | 同一附件在文件中出現兩次，各位置如何保留自己的引用與上下文。 |
| 證據缺口 | 現有輸出不足以證明必要語意或品質；交代受影響的映射／processing 驗證，不假設已實作。 |

目前只定義一種 Canonical schema，保留 schema 版本識別。Q19 的多格式提案仍已撤回。
一份完整候選是接受單位。以下資料群組不代表不同服務、檔案或資料表，
也不建立可獨立接受／選用的 Enrichment 產品。

## 2. 第一版候選的邏輯欄位草稿

Q1 的六項最低契約可以落到以下群組。Capture Package 與 processing manifest
已持有的資訊可用固定版本參照連接，不要求重複複製所有 manifest 或原始檔。

| 群組／示意欄位 | 必須表達的意義 |
|---|---|
| 身分：`schema_version`、`candidate_ref`、`asset_ref`、`source_revision_ref`、`capture_package_ref` | 明確識別固定候選與完整捕獲觀測。接受後的 Canonical Revision 必須綁定確切受評估候選。request／execution ID、digest 與來源先後仍是不同概念；此處不選 ID 編碼或分配方式。 |
| 處理歸屬：`request_ref`、`profile_ref`、`method_refs`、`completion_ref` | 指向固定 parser、映射與採納的 Enrichment 方法及輸入，保留必要工作完成證據。Temporal 執行結束不自動代表 processing 完成或 Canonical Acceptance。 |
| 內容：`components`、`sequences`、`associations`、`source_references` | 有類型的內容、包含關係、有依據的順序、必要關係，以及來源原始引用與解析目標。 |
| Enrichment：`result_ref`、`target_refs`、`input_refs`、`method_ref`、`content`、`evidence_refs`、`limitations` | 區分 OCR 重建、生成解讀與來源原文。輸入可涵蓋多個組件、artifact 或先前結果。採納結果屬於整份候選，可被引用不等於獨立接受或選用。 |
| Source Evidence：`evidence_ref`、`source_artifact_ref`、`locator`、`supported_refs`、`support_limits` | 固定來源、實際定位精度與支持範圍。若需要採用的 rendering／crop，連同其固定參照與原來源對應。定位可開啟或模型信心分數，都不等於內容獲得支持。 |
| 涵蓋與限制：`mapping_report_ref`、`covered_scope`、`limitations`、`dispositions` | 交代必要來源內容與實際有值的 provider 輸出如何處置。允許省略須有範圍、規則與理由；保留 raw output 不代表理解必要意思。 |

每個組件至少需要版本內參照、類型、內容、適用的上下文／包含關係、來源／方法歸屬及證據參照。
依來源需要表示標題／文字、步驟、程式碼／公式、表格、圖片、投影片及備註；組件不獨立接受。

包含關係與順序分開：示意 `parent_ref` 表示隸屬位置；
sequence 表示範圍、項目及順序的意義，例如 Markdown 步驟順序或投影片順序。
不能把 provider 集合的遍歷順序直接當成閱讀順序。
caption、註解等關係保留實際目標與依據；目標不確定就明示。

Source Reference 保留原始引用字串及已建立的目標對應。
未解析的外部 URL 仍是來源內容，不自動成為已捕獲依賴。
必要附件指向固定 Capture Package 內的 artifact；重複出現位置由 Q20 確認。

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

| 事實 | 欄位內容草稿 | 已確認限制 |
|---|---|---|
| 驗證 | 確切候選、規則版本、必要檢查、結果、允許限制與佐證 | schema 有效、processing 完成、artifact 可讀，不能單獨證明必要意思完整。 |
| 接受 | 確切受評估候選／Canonical Revision 綁定、驗證參照、可歸責的自動規則或授權人員判定、適用範圍與判定依據 | 整份候選接受。必要輸入、工作、證據或治理不足不能豁免；重新評估保留歷史判定。 |
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

**候選組件草稿；其中 Q20 的重複引用表示仍待確認：**

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
| Task／checkpoint 清理 | request record 或未採用中間產物刪除，不等於已接受資料撤回／刪除。採用的依賴遵守 custody／抹除規則，實體機制與期限由既有 owner 決定。 |

後續可執行映射驗證計畫須把採納規則對應到來源核對的預期內容與反例：
參照完整性、順序／包含關係、表格／表頭／註解對應、附件範圍、
來源／方法歸屬與證據支持、必要涵蓋，以及確切候選／接受判定綁定。
既有證據足夠就重用；只有影響本票決策且既有證據無法回答的未知，
才做必要的 executable probe（Q14）。本草稿未執行 mapping 或 consumer runtime。

## 6. 初步 PDF 證據對照

**這是初步證據清單，不是已完成 review 的結案 reconciliation matrix。**
PDF core 固定為 `fe1b283c49c83ad5aeee6808e77b4f25549eba03`，
Docling research 固定為 `47b363781448cc72d6cb12df2b76927c101c2e23`。
草稿欄位名稱不因列在這裡就變成採納要求。

| 已確認需求 | 現有證據與限制 | 映射／整合缺口與受影響檢查 |
|---|---|---|
| 固定輸入與方法歸屬 | request 有 `request_id`、`source_revision`、`profile`、artifact version／digest；Q04 核對 profile／producer。[Handoff][pdf-handoff]、[歸屬核對][pdf-attribution]。 | 綁定平台 Asset、完整 Capture Package、候選與接受身分；不能把 Workflow ID 當 Canonical Revision。 |
| Typed content 與關係 | Docling collections、`self_ref`／parent／children／captions；Q04 檢查重複／懸空參照與包含關係。[Graph checks][pdf-graph]。 | 定義正常化語意及映射涵蓋；遍歷順序不證明閱讀順序；清單外有值欄位須明確處置。 |
| 表格保真 | 有 cell 位置／span 與限定來源文字檢查。Wiki 188 cells、YOLO 60 cells 是 fixture 證據，非一般能力保證。[Cell checks][pdf-cells]、[retained-output research][research-retained]。 | 驗證案例需要的表頭／單位／註解對應。既有 note associations 限 parser links，其餘未確認。[限制][pdf-limits]。 |
| 定位與 OCR 歸屬 | 有原頁／region／crop 對應及 OCR input／method／outcome。crop 核對不證明文字正確；recipe 不承諾 crop 已保存。[Locators][pdf-locators]、[OCR checks][pdf-ocr]。 | 映射 locator／採用 artifact 參照；對必要內容補來源語意核對，辨識 custody 依賴。 |
| Processing 完成與接受 | Handoff 明列 `canonical_accepted=false`、`quality_accepted=false`。[Handoff][pdf-handoff]。 | Canonical 另建候選／規則／驗證／接受事實；必要工作、品質、來源支持及目前治理各自有相應檢查。 |

[Design canonical processing profiles and PDF-core integration](https://github.com/davidlinnnn/data-ingestion/issues/72)
負責受影響方法／profile／執行整合及能力驗證；本票負責 Canonical 映射／接受語意。
[Select canonical persistence and artifact ownership](https://github.com/davidlinnnn/data-ingestion/issues/57)
負責實體 custody、artifact 採用及保留機制。
完整矩陣、其他 owner 交接與 Docling／WeKnora disposition 仍待完成。

## 7. 下一輪待決與結案工作

**Q20 建議：** 同一必要附件在文件內每個出現位置，都有可在該 revision 內定位的引用及上下文；
這些位置仍指向同一 Capture Package 內的固定 artifact。
下一輪確認 SOP 的兩個 `image-use` 是否採這個表示。
[來源交接](knowledge-platform-source-handoff.md) 已將文件內出現位置的表示留給本票。
這不要求分別保存兩份圖片或分別接受。

確認後再納入採納的表示，並根據案例差異完成第一版欄位契約。
結案前仍需完整三格式／困難案例 review、接受與驗證計畫、
權威事實交接與生命週期效果、完整 PDF reconciliation、
研究 disposition，以及強制的歷史 ADR 盤點／補記。
本草稿不構成結案或 map 已解決索引更新。

[pdf-handoff]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/HANDOFF.md#L8
[pdf-attribution]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L236
[pdf-graph]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L42
[pdf-cells]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L84
[pdf-locators]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/evidence.py#L134
[pdf-limits]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/evidence.py#L215
[pdf-ocr]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/tests/pdf_processing/q04/consumer.py#L273
[research-retained]: https://github.com/davidlinnnn/data-ingestion/blob/47b363781448cc72d6cb12df2b76927c101c2e23/docs/research/docling-capabilities-vs-pdf-core-2026-10-02.md#L250
