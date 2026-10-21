# T05 表示契約離線審核

2026-10-17。範圍只有已曝光 DEV 的 T05 saved payload、現有來源契約、凍結 mapper 與 pinned Docling Core 2.99.0。沒有模型／API／安裝、holdout、來源答案回填或新 renderer；沒有修改任何候選輸出。這是方法審核，沒有執行修訂契約的交付實驗。

結論：**原 B / grid-spans-v1 的失敗應保留。T05 的主要障礙含有傳輸表示衝突，不能全部解讀為必要意思遺失。** 一個明示 span 優先、covered slot 只允許無內容 padding 的新傳輸契約值得做最小離線控制；這是另立方法，不能回頭改判原輪通過。不能補猜 section 全寬 span 或 Category body row-header flags，也不能憑 T05 的可簡化性放行仍未解的 T04。

## 原 payload 明示了甚麼

輸入為 content.txt (`B/live/wikiskill-p13-table0/content.txt`)，SHA-256 `49c6f2ebfd6349e770bacd2a682ef0c586fc91e57b71f9fa56b9f73e187afeff`。它是 14×7 的矩形 grid；不是 T04 類型的 ragged header。

| 必要意思 | payload 的現有證據 | 判斷 |
|---|---|---|
| 欄位歸屬 | Skills / Wiki Patterns 各自明示三欄 colspan；下一行依序保留 Create、Edit、Avg. Length | 已有層級與位置，無須移欄或猜 spans |
| 行維度 | Category 欄下保留五個 model、五個 benchmark 的原始名稱與位置 | 缺 `row` flag 不等於文字或欄位關聯消失；不得猜出來源未明示的 role |
| 分組／聚合條件 | row 2 與 row 8 的 section label，`row_groups=[2,8),[8,14)`，各含 label 與五個 data rows | 明示了區間，不必靠前一 label 無限延伸；仍須實際驗 scope 與 Markdown label 一致 |
| Paired values | `Create (Proposed / Accepted)`、`Edit (Proposed / Accepted)` 與每個 `a / b` 原始單格文字 | 角色順序與共同 physical-cell identity 明示，無須拆格或修數值 |
| 空白與覆蓋 | Category rowspan 覆蓋 `(1,0)`，但該位置是 `""`；其他 covered header slots 是 null | 在原契約中衝突；不能靜默視為合法 |
| Section 的外觀 | section label 在 c0，其餘六格為 `""`；沒有 section colspan | 不足以唯一證明原圖是單一全寬合併格；也不必為保留分組意思發明全寬合併格 |
| Caption、單位與來源 | target key 指向原生表；`caption=""`、`conditions=[]` | payload 本身不能證明完整 caption／單位／外部條件或 provenance。必須依既有 native ownership 與同版 baseline 保存、另做來源驗證 |

來源判準以 G1-T05 契約 (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)為準：兩組各五行、Proposed / Accepted 的次序及 slash 不是除法，見 conditions (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)；允許語意組件表示，但共同 source-cell identity 與 roles 須保留，見 cell_component_semantics (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)。來源 Category 跨三個原始 header rows，見 header span (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)。本 payload 把 Create 與 Proposed / Accepted 寫在同一第二層 header，不能只因變成兩層就判改義；必須看欄位路徑與角色是否仍完整。原計畫接受忠實可讀 Markdown 與同版補充資料，並未要求複製原圖排版，見[品質界線](../pdf-core-three-stage-plan-2026-10-17.md)（第 40 行）。

## 哪些是必要語意，哪些是多重編碼

1. **Covered slot 的 `""` / null 區別是原協定明訂的合法性要求。** protocol.py:56 (`B/protocol.py`) 要求 span 內其他位置必須是 null，protocol.py:60 (`B/protocol.py`) 規定 null 只代表 covered。因此原 payload 沒有合法的原協定映射。唯讀呼叫現有 `Grid.model_validate` 已重現 `covered positions must be null, never duplicate content`；沒有呼叫 map／main 或產生修補版本。被審 protocol SHA-256 為 `73ebe98cee394c4bfe03c21789bb82d515b0be42673c24458b2473983f2311f3`。
2. **Section span 與分組範圍是不同資訊。** `row_section` 標記 label，row_groups (`B/protocol.py`) 宣告哪些 row 受 label 管轄；section 的 col_span 則描述 label 本身橫佔哪些 slots。原 payload 的 group scope 已完整，不需要從六個空格推導 colspan。以單格 section label 加六個顯式空白格保留，比補成全寬合併格更忠於已宣告資訊。
3. **Body row-header flag 不應成為內容完整性的額外零容錯門檻。** 公開 TableCell (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/types/doc/items/table/table_data.py:20>`) 的 `row_header` 預設 False。每行文字仍在名為 Category 的明示欄；保留既有欄／列座標即可讀出行標籤的對應。可以保留已宣告 flag，但不應自動補 flag，也不能據此聲稱已還原原圖的全部版面語意。
4. **Markdown 不保存精確 spans，也不會自動編碼 row-group scope。** 現有 MarkdownTableSerializer (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:692>`) 將多層 header flatten，body 依 grid 輸出；section 的 `row_section`／body `row_header` 不會使它額外發明分組結構。精確 scope 仍要保存在 compact_provider supplement (`B/protocol.py`)，並與顯示 label 核對。原已驗 LiteralTableSerializer (`docs/research/pdf-core-direct-cell-2026-10-17/adapter.py`)只處理 literal escaping，沒有必要再加 renderer。

## 唯一映射的界線與可反駁的新契約

在 **原契約下沒有合法映射**。若忽略契約，輸入還存在兩種意圖解釋：rowspan 是真、`""` 是 padding；或 `""` 是獨立空白 cell、rowspan 是誤報。單憑 payload 不能證明哪個是來源真相，故不能稱為「原資料唯一正確修復」。

可以另訂一個通用、事前固定的 **span 為結構權威的契約**：

- 先驗矩形、span 邊界／互斥、anchor、roles 及明示 scope。declared spans 決定 cell ownership；covered slots 只允許 null 或精確空字串 padding，均不生成第二個 cell。非 covered 的 `""` 仍生成獨立已知空白 cell，非 covered null 拒絕。
- 非空字串、空白字元、unknown sentinel 或 role 出現在 covered slot，均拒絕；不能當「空」吞掉。保留原 raw payload 與新方法版本，讓 padding 政策可追溯。
- 只依已宣告 anchors／spans／roles 生成公開 TableCells；不補 section colspan，不推斷 body row flags，不延伸 group endpoint。原始 cell text、pairs、數值、column order 一律不變。
- 沿用現有來源／caption mapper、公開 Core 與 serializer，將原 `row_groups` 以同版 supplement 保存。公開 TableData.grid (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/types/doc/items/table/table_data.py:111>`) 本身會以後來 cell 覆寫重疊位置，因此不能用「Pydantic 可建構」代替前述不重疊驗證。

給定這個新契約，可定義一個確定的機械映射；它不等於證明模型宣告 spans 為真，也未在本審核實際產生／render／reload。新增的維護面應只是一條 covered-padding 邊界規則；若需要猜 header、搬欄或補來源 layout，就停止。

下一步離線控制至少要可反駁這些主張：

| 控制 | 預期 |
|---|---|
| 同一 legal span 的 covered null／`""` 兩種輸入 | 同樣的 Core／Markdown／scope；raw 觀察仍各自保存 |
| Span 外的真空白格，及不含 span 的表 | 空白格仍存在，不能被刪除或變成合併格 |
| Covered slot 中為 `"0"`、`" "`、`"—"`、unknown 或另一 role | 明確拒絕，不能吞內容 |
| 重疊／越界 span、孤立 null、錯置或重疊 group | 明確拒絕，不能交給 Core overwrite 容忍 |
| Section row 另有非空條件／數值 | 保留獨立格；不能自動全寬合併、移除 row 或吞值 |
| Group endpoint 少含一行、label 被改、header/pair 次序交換 | 來源／scope／實際 render 評估必須失敗，即使數字全對 |
| 原正例、多 row dimensions、同名 metrics、literal 及非目標項目 | 不得 material 回歸，保存及 reload 前後一致 |

原六筆 saved responses 的新方法 replay 若成立，只是離線接合證據。原 T05 仍失敗；也不能把沒有推論過的新契約當成新模型品質、成本改善或完整 B 通過。

## 未證明

沒有執行新映射、實際 Markdown render／reload／來源保存測試；沒有證明被模型漏報或誤報的 spans 能自動恢復，也未補齊 native caption 的來源完整性。本審核不能放行 T04、跨頁表格或整份配置。
