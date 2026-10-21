# 官方 TableData 直接接合：研究筆記

2026-10-17。只讀官方文件、固定版 source 與既有實驗紀錄；沒有推論、安裝、PDF／圖片／holdout 存取。本筆記調查 HTML gate 失敗後，還有哪些官方接點值得有限驗證。

## 結論

**優先驗「完整 cell JSON → 公開 TableData／TableCell → stock Markdown」，避開 HTML backend 的 header 推斷。** 這是擴充既有直接 Core mapper 的輸入表達能力，不是新模型，也不是宣稱先前沒試過 JSON 接合。上一輪 flat JSON 省掉了 row-dimension header 與多欄 row context；問題首先在協定，不是 Core 只能有一個 row header。

官方 DoclingDocument 定位本來就是可建構及操作的 Pydantic 文件模型，公開 `add_table(data, caption, prov, parent)` 與 `add_table_cell(table_item, cell)`。它們不要求先經 HTML converter。[官方模型說明](https://docling-project.github.io/docling/concepts/docling_document/)、[官方 API reference](https://docling-project.github.io/docling/reference/docling_document/)

## 官方接法與本案差異

| 接法 | 官方證據 | 對本案的意義 |
|---|---|---|
| 直接建 TableData／TableCell | Core 2.99 public 型別含 text、起迄 row／column offsets、row_span／col_span、column_header／row_header／row_section、optional bbox；TableData 另存方向及格網大小 | 左欄標題、兩個 row dimensions、row-group 可直接表達，不必將它們壓進一個 setting 字串 |
| Standard 的 TableFormer → typed cells | Stage 對 TableFormer `tf_responses` 呼叫 `TableCell.model_validate()`，並保存 row／column 數；reading-order 直接包成 TableData | 直接 typed 接合與原生內部資料流一致，HTML 不是必要中介 |
| 自訂 table engine plugin | 官方 table factory 接受 BaseTableStructureModel 與 BaseTableStructureOptions，可由 PdfPipelineOptions 選取 | 未來可把外部 VLM 放在 Standard table stage；這是公開擴充機制，但 engine／API client／錯誤處理仍由我們維護 |
| 已完成文件後 enrichment | 官方提供對既有 DoclingDocument 再 enrichment 的例子 | 先驗 source-preserving 的 Core replacement 亦合乎官方操作方向；官方例子不是現成 remote table reconstruction implementation |

來源：[Core 2.99 TableData](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/items/table/table_data.py)、[Standard 2.132 table stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/table_structure/table_structure_model.py)、[reading-order mapping](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/reading_order/readingorder_model.py)、[官方 plugin 文件](https://docling-project.github.io/docling/concepts/plugins/)、[既有文件 enrichment 範例](https://docling-project.github.io/docling/_generated/examples/enrich_doclingdocument/)。固定版同檔已在本機 venv 核對。

`row_section` 能儲存角色，不代表 Markdown 會自動輸出完整可解讀的 group hierarchy；仍要評真正交付的條件歸屬。`bbox=None` 不能變成精確 cell provenance；應維持上游 table envelope 的真實粒度。

## HTML 以外仍有的 serializer 問題

Core 2.99 stock Markdown 對 plain TableCell 直接使用 text，只處理換行及 pipe。因而 literal `<s>` 的 HTML 解讀問題，**改成 JSON 輸入也不會自行消失**。同一 serializer 對 RichTableCell 則 resolve 它指向的 document item，經一般 text serializer；一般 TextItem 路徑有 HTML escaping。這是一條可先驗的公開、免 SDK patch 表示方法，不宜先說已可解決所有 literal 與 span。[固定 Markdown source](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)

RichTableCell 需要有效 ref 與以 table 為 parent 的 child item；`add_table_cell` 會核對 parent。它比 plain cell 多 document nodes，mapper 因此有實際複雜度。[Core public construction source](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/document.py)

目前官方 repository 亦有 spanning RichTableCell 在 Markdown／chunker 因 visited 去重而缺字的 bug report 與修補提案；這是限制線索，不能當成固定版已修復或新版本已通過。本輪若驗 RichTableCell，必須包含 colspan／rowspan 重複可見值及重複表頭控制。[官方 repo issue #4717](https://github.com/docling-project/docling/issues/4717)

## 與既有結果的關係

- [既有 flat JSON live](pdf-core-table-live-results-2026-10-17.md) 已有普通／六 panel 的數值及比較通過，不能重稱新的 model accuracy breakthrough。新假說只是完整 cell protocol 能否補協定表達缺口。
- [HTML gate](pdf-core-table-html-results-2026-10-17.md) 否決的是已測的 HTML inference／stock renderer 組合。它沒有否決所有 TableData，也沒有測 RichTableCell 路徑；不需要先擴大 VLM 推論來辨識哪層壞了。

## 最小下一步

1. **零模型、90 分鐘 gate。** 沿用既有 8 類合成來源語義，直接提供完整 typed cell JSON，不讀論文答案；比較 reload 後 typed data 與真正 Markdown 渲染。新增 invalid bounds、overlapping cells、span／offset mismatch 的拒絕控制，不自動修復 provider 內容。
2. Plain cells 正確承載 row-group、左欄標題、多維度與 spans；另外獨立驗 RichTableCell／TextItem 的 literal escaping 與 span controls。不要為特定 `<s>` 改文字；cell text 一律保持原值。這是預先界定的通用表示比較，不作逐 testcase 選 renderer。
3. 通過才凍結一份通用 cell protocol，回到原定四頁一次 live 比較；保留全部 native targets、來源 caption、正文順序與粗粒度 provenance。原 470 bindings／23 comparisons rubric不變。
4. 若必須 patch SDK、改表格值、補缺 header 或另寫 renderer，停止。可另提一個共享 serializer 修補／上游回報的維護成本決策，不默默升級本輪。

最小維護範圍仍是 provider payload validation、typed mapping、來源 target／caption／order 綁定；plugin 化不會取消這些工作。建議先不用 table plugin 包裝，等表示及 live 證據成立再決定是否移入 Standard table stage。

未實測上述新 gate、當前新版 Core、Qwen3／vLLM 或高頻負載；官方可擴充並不保證模型辨識品質或 stock Markdown 完整保真。
