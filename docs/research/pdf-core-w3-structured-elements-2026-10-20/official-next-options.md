# 官方選項的後續候選（只建議，未執行）

1. **表格 `table_structure_options.do_cell_matching=False` 單變量消融。** P06／P11／P13 的部分失敗已出現在 native grid：PDF 文字跨欄合成一格、數字與標籤錯配。這個官方布林選項直接改變 cell matching，值得以同一批凍結表重新檢驗；不保證修復。必須逐表沿一般表零錯、複雜表 ≤5% 的門檻，並回歸 W2 的正文／讀序。不能以數值 multiset 相同當修好。pinned `docling/datamodel/pipeline_options.py` 的 `TableStructureOptions`（151–174 行）確認此選項存在，預設 True、模式為 ACCURATE；本輪沒有改它。

2. **把 `do_formula_enrichment`、`do_code_enrichment` 分開評估。** 兩者是官方開關。本輪聯合 E1 用來驗證重建，不能因語法更像 LaTeX／程式碼就全域啟用；只要頁圖確證改變數學意義或程式邏輯，即分別受 Q31／Q33 阻擋。拆開成本與品質，維持已選定 PyPdfium／Heron／separators=True／bookmark-only，不加入逐文件例外。沒有提出新的模型下載或 VLM API。

3. **圖片正式交付維持 W2 的影像開啟與 group5 記憶體管理。** 這不是本輪新增的準度解法。W3 重用的研究 JSON 沒有 image payload；PDF raster bbox 包含率只能證幾何候選，不能驗證正式交付的 crop bytes，也不能涵蓋向量圖。待正式 core 具備影像交付後，重用這次來源／頁碼核驗實際 crop 與 caption 關聯。圖片描述和 chart 數值仍交 A／C live run。

本輪沒有證成官方選項可修復 caption 插入正文或 table／picture overlap 抑制造成的圖表混合；這兩類保留已知限制。三條 mapper 規則只改善已抽取內容的交付，不重建數學、code 邏輯、表格行列或 caption parent/link。

以上依 pinned 本機套件原始碼與本輪證據提出，沒有執行任何新消融。未將 `scale`、生成長度、閾值或逐文件修補列為既定解法。
