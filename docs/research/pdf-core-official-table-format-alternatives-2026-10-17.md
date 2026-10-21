# 官方表格格式與 Standard 接點調查

2026-10-17。僅閱讀官方文件、固定版已安裝來源及既有研究報告；沒有模型推論、安裝、下載權重或讀取 PDF／圖片／holdout。結論：**換成 OTSL／DocTags 不能自動解決主要 Markdown 交付；優先驗公開 TableData 與官方 serializer 接點，不再重跑既有失敗模型。**

## 格式與 parser 必須分開辨認

| 接點 | 固定來源可確認的能力 | 目前限制／建議 |
|---|---|---|
| Docling 2.132 `docling.utils.otsl.parse_otsl_output` | 解析 fcel/ecel、lcel/ucel/xcel、ched/rhed/srow；建立含 span、column_header、row_header、row_section 的 TableCell | 與 Granite Vision native table stage 使用同一接點；不是完整文件來源／caption mapper，亦非完整 malformed-grid validator。可作有界零模型控制，不把它包裝為新模型能力 |
| Core 2.99 legacy DocTags table parser | 接受相同語義 tokens，建立格網與 spans | `otsl_parse_texts` 建立 TableCell 時未賦值三種 header/section flags，故不能假定 round-trip 保留角色；同一內容仍進入 stock Markdown |
| Core 2.99 DocLang deserializer | plain cells 明確保留 ched/rhed/srow，corn 同時標記 column/row header；支援來源、caption 與結構化表格 | 不是 legacy DocTags parser 的別名。但 rich-cell 分支另建 RichTableCell，該分支未設定上述 flags；不能以 plain-cell source 能力推廣所有 rich-cell 組合。未執行本案零模型 gate，不推薦直接啟動 VLM 生成新格式 |
| 公開 `TableData`／`TableCell` | 直接設定完整格網、span 與角色，避開 HTML heuristic／舊 DocTags role loss | 是有限自訂 producer contract 與 validation，非 Docling 現成 remote-table toggle；仍須驗 Markdown 最終表示 |

上述判讀來自固定 runtime 的檔案閱讀，可核對上游同版：[Docling OTSL parser](https://github.com/docling-project/docling/blob/v2.132.0/docling/utils/otsl.py)、[Core legacy OTSL parser](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/utils.py)、[DocLang deserializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/deserializer/doclang.py)。Web 對前兩個固定版 URL 回覆 cache miss，沒有把缺失的 web 擷取當新來源證據；實際 source 是已安裝且先前固定的 2.132／2.99 runtime。

## 換輸入格式不會修正共用 Markdown 限制

官方明列 JSON、DocLang、DocTags 與 HTML 可以保留 spans，Markdown 需作扁平化；若需要準確合併格，建議 HTML／dict，或使用公開 `BaseTableSerializer` 客製接點。[官方 serialization 說明](https://docling-project.github.io/docling/concepts/serialization/)

固定 Core 2.99 的 `MarkdownTableSerializer` 對 plain TableCell 讀取 `.text`，僅處理 newline／pipe；`<s>` 會保持未 escaped。這與 HTML／JSON／OTSL producer 無關。RichTableCell 則走一般 item serializer，一般 TextItem 可套 HTML escaping，但這只是值得零模型驗的公開路徑，不能用 source inspection 宣告已解決。尤其不能透過把 typed cell 改成 `&lt;s&gt;` 來污染 canonical 原文。[固定版 Markdown serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)

因此，若必須維持主要 Markdown，先判定使用官方可替換 serializer 或 rich-cell 表示能否同時保留條件與 literal；如果 consumer 只接受純 GFM pipe table，rowspan／colspan 本來就不能無損表示，這是輸出契約取捨，非換更大模型可處理。HTML fragment 嵌入 Markdown 是可研究的輸出策略，尚須驗 consumer 是否接受、是否保留與正確顯示；不是 HTML backend import 已失敗就等於 HTML export 亦失敗。[官方 serializers 與 span 取捨](https://docling-project.github.io/docling/concepts/serialization/)

## 真正的 Standard table-stage 接點存在

官方提供 `table_structure_engines()` plugin factory；實作 `BaseTableStructureModel` 與 `BaseTableStructureOptions`，透過 `PdfPipelineOptions.table_structure_options` 選擇，外部 package 需 `allow_external_plugins=True`。這是在 Standard 的 table stage 內替換 engine，不必先執行 TableFormer 再回填。[官方 plugin 文件](https://docling-project.github.io/docling/concepts/plugins/)

固定 2.132 `StandardPdfPipeline` 在 layout／OCR／postprocess 後建立 table-model stage，再交給 assembly；base interface 為 `predict_tables(conv_res, pages)` → `Sequence[TableStructurePrediction]`。因此 native plugin 可重用 detected table clusters、保留 native assembly；但 API request、輸出 validation、table id／來源綁定與錯誤傳遞仍是本案要負責的有限整合。它不會自動補全漏偵測表格、不解決跨頁 logical-table grouping，也不會修 serializer。[Standard 源碼](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py)、[base table-model interface](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_table_model.py)

Granite Vision 4.1-4B 是官方提供的 OTSL table engine，但其現成 stage 固定 Transformers CPU／CUDA，不能以通用 `ApiVlmEngineOptions` 換成公司 Qwen3 endpoint；MLX 研究接合也不是此 stock stage 的 native MLX 選項。[官方 model catalog](https://docling-project.github.io/docling/usage/model_catalog/)、[固定 Granite stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/table_structure/table_structure_model_granite_vision.py)

## 不重複已完成的比較

- Granite-Docling-258M full-page／OTSL region、TableFormer V2 已驗，必要數值／綁定有錯；不能重新命名為下一輪新方法。[既有 coverage](pdf-core-g2-official-method-2026-10-15/coverage.md)
- Granite Vision 4.1-4B CPU 曾逾時，MLX BF16 GPU 在另外兩表已完整完成，但仍有必要數值與增量關係錯誤；不是只有 CPU 不夠快，也不是尚未驗 MLX。[Granite CPU／上游比較](paper-pdf-table-upstream-results-2026-10-11.md)、[MLX 完整結果](paper-pdf-granite-mlx-results-2026-10-11.md)
- 通用 API＋官方 `VlmPipeline`＋DocTags 的 low／medium 各八頁已驗，內容、位置與 parser 交付仍有缺陷；只換格式或 reasoning flag 不構成全新 producer 假說。[官方方法決策](pdf-core-g2-method-selection-decision-2026-10-15.md)

## 下一個值得投入的 gate

**第一順位：零模型驗「公開 TableData＋公開 serializer 接點」，而非新增 OTSL 推論。** 重用上輪八種合成表示，先隔離已知 row-group 與 literal，驗 stock 可用表示或官方 HTML table serializer 嵌入 Markdown；保留 typed 原文字串、caption／來源與正文，不修內容、不改私有 SDK。若仍需要自訂完整 parser／renderer，先以具體 diff 評估維護成本並停止擴張。

這個 gate 通過才值得把同一固定 producer contract 放入官方 table-engine plugin，先 mock／replay 驗 native assembly 與錯誤案例，再考慮原四頁有限 live 評估。Plugin 僅改接線，不能從這一點宣告模型品質更好；格式未通前不應再花四次 API 嘗試證明同一 serializer 限制。

未實作上述 gate／plugin，沒有宣告 stock Markdown 或 DocLang 已通過；公司 Qwen3、真實論文四頁、跨頁與泛化仍未驗。
