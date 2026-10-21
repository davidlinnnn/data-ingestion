# Adam p12：必要定義被 formula role 隱去，native orig 仍保留

英文定義並未在 PDF backend 抽取時完全遺失。原始 layout 將 `Definition 10.1. A function f : R d → R is convex if for all x , y ∈ R d , for all λ ∈ [0 , 1] ,` 標成 formula（cluster19，confidence 0.585979）；assembled formula 元素保留整句。final `#/texts/419` 的 `orig` 與該 assembled text 逐字相同，但 `text=''`。緊接的 `#/texts/420` 也保留原不等式於 orig、text 空。這是必要條件／對象的英文敘述在可讀交付面漏掉，不能只歸行內數學 F13 排版。

根因鏈：

1. **layout role**：原生字層抽到定義後，被 layout 判成 formula，而非普通正文。這一階段已可見公式角色選擇。
2. **reading-order materialization**：官方 `_handle_text_element` 的 FORMULA 分支明確 `add_text(label=FORMULA,text="",orig=cap_text,...)`。所以 text 清空／orig 保留是此固定官方 stage 的實作行為，不是 backend 字流漏掉或 Markdown 才刪字。[官方 source](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/reading_order/readingorder_model.py:633>)。
3. **enrichment 關閉**：S0 的 formula/code enrichment 均 false，官方 pipeline 的 CodeFormulaVlmModel 為 disabled，沒有後續公式 decoding 將 text 回填。這符合固定 baseline 的實際預期，但不能代表符合 Q4 必要內容交付要求。[官方 pipeline](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/pipeline/standard_pdf_pipeline.py:662>)。
4. **Markdown delivery**：官方 FormulaItem serializer 在 text 空且 orig 有字時只輸出 `<!-- formula-not-decoded -->`，不回退輸出 orig。故 default MD 找不到 Definition10.1；這是 pipeline 角色表示與交付 mapping 共同造成的可讀缺口。[官方 serializer](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:420>)。

分流應分兩層：必要英文被判 formula 是 **pipeline formula-role** 的品質問題；交付是否應處理 `orig`／空 text 狀態則是 **#81 mapping／serialization** 契約。orig 保留的是 backend 原文，不保證合法 LaTeX，不能盲目當成已解碼數學內容，也不能宣稱整句原生抽取完全遺失。此輪只定位，不改 label、text 或匯出策略。

## force_backend_text 為何不能直接列為有效 S0 修復

PdfPipelineOptions 雖有 `force_backend_text` 欄位與原生字層說明，但本機固定 Docling2.132.0 的完整套件搜尋顯示，實際讀取該選項的地方在 `VlmPipeline`；`StandardPdfPipeline`、reading-order FORMULA 分支與 default Markdown FormulaItem 分支沒有依此開關改變行為。這個案例本來就已有 backend 文字，問題是後續 role／active text／orig 表示。因此沒有源碼依據支持「把 S0 force_backend_text=True 即會恢復此定義」，本輪沒有執行該變更。[宣告](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:2100>)、[VLM 實際讀取](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/pipeline/vlm_pipeline.py:148>)。

以本機官方 ReadingOrderModel 重播 Adam 完整文件，selected trace 保存 p12：texts/groups/body/furniture/tables、pictures（除官方後附 image）全相等，Markdown bytes 亦完全相等；模型推論 0。[exact trace](trace-adam-p12-formula.json)、[raw layout／assembled／final 與 source SHA 證據](adam-p12-formula-evidence.json)。

未開 formula enrichment、未跑 conversion；沒有將 orig 的保留當作可讀輸出合格，也未把這個必要正文缺口降級為可接受字型差異。
