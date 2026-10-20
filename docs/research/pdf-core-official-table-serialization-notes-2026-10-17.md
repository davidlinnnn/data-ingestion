# 官方 table serialization：HTML gate 後的接點研究

2026-10-17。僅讀官方文件、GitHub source／issue及本機固定 Docling-slim 2.132／Core 2.99 source，未執行程式、模型、API、安裝或讀取 PDF／圖片／holdout。這是可行性研究，不能當作新配置已通過。

## 結論

前輪否決的是「一般 HTML rowgroup 匯入＋stock pipe Markdown」的固定組合，**沒有證明 HTML、TableData 或所有官方 serializer extension 都無法接合**。Docling 官方把表格內容模型和最終 serialization 分開，提供 `BaseTableSerializer` 擴充入口；維持 `StandardPdfPipeline` 主幹時，可以在已組裝文件之後用公開模型／serializer 處理表格，不必 fork SDK。[官方 serialization 概念](https://docling-project.github.io/docling/concepts/serialization/)

值得先做零模型探針的方向有兩個：**明確 typed cells＋小型 Markdown serializer extension**，或 **typed cells＋官方 HTML table fragment 放進 Markdown**。兩者都要獨立證明 typed table 語義正確，不能把 serializer 當成修錯條件歸屬的工具。第二個方向還需要明確的 consumer HTML policy；只放 artifact pointer 無法滿足目前「主要 Markdown 可被 projection 直接消化表格內容」的要求。

## 官方接點和實際限制

| 接點 | 固定版 source／官方提案 | 可以處理什麼；不能保證什麼 |
|---|---|---|
| `MarkdownDocSerializer(table_serializer=...)`／`BaseTableSerializer.serialize(...)` | Core 2.99 有 public class 和注入欄位；官方範例實際更換 table serializer | 改表格輸出策略；不必替換整個文件 renderer。它是應用程式維護的官方擴充，不是 stock `export_to_markdown()` option |
| `TableData`／`TableCell` | 有 row/column offsets、row/col span、`column_header`、`row_header`、`row_section` | 明確承載儲存格與 section 語義；producer 仍須提供正確關係及通過維度／重疊／coverage檢查。Schema不會自行辨識原稿 |
| `HTMLDocSerializer.serialize(item=table)`／`TableItem.export_to_html(doc)` | 使用官方 table serializer，plain text 經 HTML escaping，span 轉成原生 rowspan／colspan | 可以保留 literal `<s>` 和 span 的 HTML 表示；不會修復上游錯誤的 column_header／row_section |
| `RichTableCell` | cell 透過 `RefItem` 指向文件內的 text／group，Markdown 會委派 text serializer | 確有 rich cell 接點，但不宜只為 escape plain literal 就引入 children／refs／visited 的維護；固定版還有跨欄文字重複解析風險 |

來源：[Core 2.99 public base](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/base.py)、[Markdown serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)、[typed cells](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/items/table/table_data.py)、[HTML serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/html.py)、[table exports](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/items/table/table.py)、[官方可更換 serialization strategy 範例](https://docling-project.github.io/docling/_generated/examples/advanced_chunking_and_serialization/)。

## Plain Markdown：不用把內容改掉，但要承認 extension 成本

固定版 `MarkdownParams.escape_html=True` 確實存在；一般 text 會使用它。然而 plain table cell 分支直接讀 `cell.text`，只處理 newline／pipe，沒有經過該 HTML escaping。因此改同一個 flag 不能合理視為新修正；`compact_tables` 也只改排版。公開 `serialize()` override 可以在輸出邊界進行通用 escaping，但必須保留數值字串、空白／缺值區別、caption、來源 metadata，以及 stock header flatten 行為的預期限制。這是 transport escaping，不是看答案修數值。[固定 Markdown source](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)

需要另外處理 row sections。`row_section` 不是給 stock Markdown 展開成獨立 group column 的選項；前輪錯誤來自 HTML backend 把 section 同時標成 column_header，接著 leading header rows 被 flatten。官方 HTML backend 有 `row_section` class dialect，但它只是另外設定 row_section flag：若 producer 繼續用全列 `<th>`，不能假設 column_header 會因此取消。應以固定合成案例驗證其完整輸入／typed／Markdown結果，不能事後改 flag 來冒稱 stock匯入通過。[Docling 2.132 HTML backend](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/html_backend.py)

## Markdown 內 HTML：可研究，不是現成一行即可交付的承諾

官方將 spans 在 JSON／HTML 的保留能力和 Markdown pipe table 的 flatten trade-off 區分，建議有結構依賴的 downstream 使用 HTML／dict，或替換 table serializer。可以維持正文 Markdown，讓小型 table extension 委派官方 `HTMLDocSerializer` 產生 table fragment；不自行寫 HTML renderer。這是由官方 extension 組合得到的候選設計，官方文件並未承諾這個混合配置已適用所有 Markdown consumers。[官方 serialization 提案](https://docling-project.github.io/docling/concepts/serialization/)

不要直接把 `HTMLTableSerializer()` 注入 Markdown 父 serializer 就宣布完成：HTML table serializer會呼叫父層 `serialize_captions(tag="caption")`；Markdown父層的共用實作不產生 caption tag，而 rich-cell 文字也會經過父層的格式策略。以完整 HTML serializer 處理單一 table，再以公開 `SerializationResult` 接回原文件，比跨格式委派父層更清楚；仍須驗 caption恰好一次、來源 metadata、排除規則、children／visited與順序。[共用 serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/common.py)、[HTML serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/html.py)

Consumer gate 必須同時驗證人類渲染與 projection 真正抽到的 cell 內容。HTML disabled時畫面可能呈現標籤原文；有些 Markdown parser把整個 HTML table視為單一 raw block；即使 HTML enabled，消費端也需要自己的安全處理策略。這個方案不能悄悄把「Markdown主要消費」改成「consumer 必須另外讀 artifact」；如果要改，需列為需求決策。

## Current 與 pinned 的差異

截至本次官方查核，跨欄 `RichTableCell` 文字只在第一欄保留的 issue #4717 已由 PR #857於2026-10-12合併修正；current main 以起始 row／col快取 rich cell輸出。固定 Core2.99 source仍逐 grid position呼叫 serializer，不能把最新文件／main行為當成本次runtime行為。PR #855只是另一個已關閉提案，不是實際合併的修正。這也不代表為解本次 plain-cell escaping 應立即升版或改用 RichTableCell。[官方 issue](https://github.com/docling-project/docling/issues/4717)、[合併 PR #857](https://github.com/docling-project/docling-core/pull/857)、[current Markdown source](https://github.com/docling-project/docling-core/blob/main/docling_core/transforms/serializer/markdown.py)

## 建議下一個 gate

先固定四個合成檢查：普通 header、連續兩個 row sections、span＋重複 header、literal `<s>`／`&`／pipe。候選上限兩個，逐一比較 typed與最終消費內容：官方 HTML dialect＋stock Markdown；若語義正確但 plain-cell escaping仍失敗，再評估一個 public table serializer extension。原始字串與source model不得為了輸出改值；不依 testcase分支，不修改 SDK，也不換 VLM。若 extension不能維持 caption／provenance／既有輸出，停止並估維護成本。混合 HTML route另列 consumer contract gate，不以「放一條連結」當完整表格交付。

未驗證上述候選執行結果、四頁論文、模型準度或高頻效能；研究提出的組合仍有 serializer 回歸與 consumer 相容性風險。
