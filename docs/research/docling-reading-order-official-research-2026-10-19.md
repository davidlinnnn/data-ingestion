# Docling 多欄跨句混接：官方 issue 與方法調查

As of **2026-10-19 Asia/Taipei**。問題來源為現有 S0 的清晰雙欄純影像 PDF：左右欄句子片段在同一個文字輸出中混接。此文件區分外部問題報告、真人維護者說明、bot 建議及已合併修復；沒有新增模型推論。

**後續進度：**使用者另行授權的[單頁 OCR 邊界追蹤](pdf-core-ocr-boundary-trace-2026-10-19/report.md)已完成一次 S0 conversion，確認 22 個分欄原始框經 20-point dilation 合為一張跨欄 crop，reader 原始回覆已混句；零膨脹的離線幾何對照得到 15 個分欄框，尚未做該對照的 OCR。下方保留追蹤前的官方／本機查核脈絡；精確新增定位以後續報告為準，沒有宣稱修復或晉升配置。

## 搜尋範圍與結論

使用 `multi-column reading order`、`two-column PDF`、`text flows across column boundaries`、`merged paragraphs`、`OCR interleaved columns`、`reading_order_rb`、`RapidOCR columns` 等關鍵字搜尋官方 `docling-project/docling` 與 `docling-project/docling-ibm-models`，並用 GitHub API 核對主要 issue／PR 狀態。

**有高度相似的公開問題，但未找到可直接宣稱修好 S0 這個案例的官方單一設定或已驗證修復。** 已確認的局部 reading-order 修復，其適用範圍有限；須先區分 OCR cell 本身是否已跨欄、layout cluster 是否包入兩欄，以及 reading-order 是否只是把完整區塊排錯。單靠 Markdown 表現不能確定是哪一層。本次已進一步核對本機保存的中間產物，定位如下；上游的精確成因仍未證實。

## 最相關的官方討論

| 官方來源與核對狀態 | 內容與身分 | 對本案的意義／限制 |
| --- | --- | --- |
| [#2067 Multi-column layout extraction fails](https://github.com/docling-project/docling/issues/2067) — **Open**，`bug`／`reading_order`，指派 PeterStaar-IBM | 回報者描述三欄正文越過欄界、句子混在一起；版本 2.43.0、`do_ocr=False`。回報者稱各欄 layout bbox 正確，提出自行按欄排序。真人 MEMBER PeterStaar-IBM [要求 PDF 重現檔](https://github.com/docling-project/docling/issues/2067#issuecomment-3174235905)。 | 症狀最接近，但它是非 OCR 路徑，且沒有真人維護者確認修法／已解決。其 `do_cell_matching=False`／TableFormer ACCURATE 建議出自 **dosubot**，不能當正文欄位的官方修復方案。 |
| [#2204 Unable to get correct reading order for a standard two-column pdf](https://github.com/docling-project/docling/issues/2204) — **Open** | 2.50.0 的雙欄論文在左欄尚未讀完時跳右欄，回報者試過 Heron、Layout v2、所有 Egrets。2026-08-17 的 CONTRIBUTOR 又回報 2.120.1 在 born-digital 文件中文字可讀、段落順序仍錯。無真人維護者提供已合併通用解法。 | 支持「換 layout 不保證修好 reading-order」。它主要是完整區塊換序，不能等同本機句內混接的同一根因。此 issue 的內部算法與無設定論述主要由 dosubot 回覆，需另核對程式碼。 |
| [#2683 Spatial Ordering Option for Markdown Export](https://github.com/docling-project/docling/issues/2683) — **Open feature request** | 作者提出 `spatial_ordering=True`、`OrderingStrategy.SPATIAL` 等新 API 草案。真人 MEMBER dolfim-ibm [澄清](https://github.com/docling-project/docling/issues/2683#issuecomment-3579864884)：這應是選擇 reading-order model/module，而非 export mode；當時只有一種 model，未來希望開放更多。 | 草案程式碼**不是已出貨設定**。官方方向支持在 reading-order 模組層改善，而非把 Markdown export 當修復點；2025 年留言不能自行推定今日 API，需查 pinned／current code。 |
| [#3422 Top-of-page heading emitted last](https://github.com/docling-project/docling/issues/3422) — **Open** | 2.93.0 單欄文件 bbox 正確但順序反轉，作者換多種 layout 仍重現；自行 stable bbox sort 可修其案例。真人 MEMBER PeterStaar-IBM 同意 CONTRIBUTOR 嘗試 native fix。 | **單欄** workaround，作者明確警告簡單 `(page, top)` 排序可能破壞多欄順序。被提及的 contributor commits 不能當作已合併發行的修復，也無法拆開已混在同一項目的兩欄句子。 |

上述 issue 位於官方 repository，但回報者推論、bot 回覆與真人維護者承諾是不同強度的證據。

## 已合併修復與歷史，避免誤讀「Closed」

- [docling-ibm-models PR #163](https://github.com/docling-project/docling-ibm-models/pull/163) **Merged 2026-08-27**：重啟同列 left-to-right link，並保留 right partner 的既有垂直父關係；附同列右側／caption orphan regression。PR 作者明確限定：**不解決一般多欄 reading order，也不解決單欄 heading inversion**。真人維護者 cau-git、PeterStaar-IBM approved。這是實際 upstream 修復，但不是本案的保證。
- [Docling PR #4093](https://github.com/docling-project/docling/pull/4093) **Merged 2026-08-28**：把 rule-based reading-order 實作由 `docling-ibm-models` 搬入 Docling，方便獨立迭代與發布；PR 明載 **logic unchanged**、內部 API。不能把搬檔本身說成新模型／新準度修復。
- [#570 Single-page image-text layouts](https://github.com/docling-project/docling/issues/570) 仍 Open；真人維護者 2025 年提到新版模型及 [PR #811](https://github.com/docling-project/docling/pull/811)。**#811 Closed 但未 merged**，作者稱被 [PR #916](https://github.com/docling-project/docling/pull/916) 取代；#916 **Merged 2025-02-20**。這段歷史不能證明 2026 年的本機失敗已在更新版修好。

## 本機中間產物定位：跨欄發生在最後排序之前

只讀既有 JSON、options 及 pinned 套件原始碼，沒有重新 conversion 或載入推論模型。

| 層次 | 保存證據與判斷 |
| --- | --- |
| OCR cells | S0 result.json (`pdf-core-native-round-2026-10-17/S0/scan/result.json`) 的 `pages[0].parsed_page.textline_cells[3]`（檔案第 171 行附近）已同時包含左欄 `or LLMs ... either` 與右欄 `mally introduced ... language`；bbox x=45.8167–565.4389，橫跨兩欄。這是保存的 post-OCR cells，不冒稱未保存的 engine raw。 |
| Cluster | 同檔 postprocessed cluster 3 把左欄首行、右欄以 `for-` 結尾的行及跨欄 cell 分到一起。 |
| Page assembly | 同檔第 6337 行的 assembled text 已有 `foror`。普通合行／去斷詞把 `for-` 接到後面的 `or LLMs`，由已錯的區域／cell 組合形成壞單字；不能把 dehyphenation 本身認定為唯一根因。Pinned [page assembly](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/page_assemble/page_assemble_model.py#L125) 與 [cluster 合行](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/page_assemble/page_assemble_model.py#L200) 可解釋此行為。 |
| Final Markdown | S0 Markdown (`pdf-core-native-round-2026-10-17/S0/scan/document.md`) 只是輸出已混接的 assembled text；重排 `body.children` 不能可靠拆回原來的句子。 |
| S1 對照 | S1 result.json (`pdf-core-native-round-2026-10-17/S1/scan/result.json`) 對應 cells 分開保留左右欄；其 Markdown (`pdf-core-native-round-2026-10-17/S1/scan/document.md`) 仍有完整段落換序。相同凍結 OCR 資產／options，登錄變項是 Heron→Egret，但未保存 pre-OCR rects、raw layout predictions 或完整 tensors，故不能確定是 Heron 權重、rect dedup 或 OCR engine 的哪一項造成差異。 |

原始 OCR crops／rects 未保存，**無法再由這份產物唯一重建 upstream 成因**。本次確認錯誤最晚已在 post-OCR cells 與 cluster 分組出現，精確上游成因待定位；layout 與 OCR 區域處理的互動仍是假說。沒有證明所有 OCR engine、Heron 或原生 reading-order 都必然失敗。

### 現行官方設定已包含什麼

- **設定名稱更正**：S0 effective-options (`pdf-core-native-round-2026-10-17/S0/effective-options.json`) 的實際值是 `ocr_options.mode="default"`，不是先前敘述的 AUTO。`OcrAutoOptions` 是 OCR engine 選擇，不能和此輸入區域 mode 混為一談；歷史封存 artifacts／分數不回寫。
- 官方 [PR #3710](https://github.com/docling-project/docling/pull/3710) 已於 2026-07-23 merged，Standard 改為 `preprocess → layout → OCR → layout postprocessing → table → assembly`。本機 2.132.0 [pipeline](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L785) 已採此路徑；[BaseOcrModel](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_ocr_model.py#L215) 將 DEFAULT 與 PDF_AWARE_LAYOUT_REGIONS 都交給 `_find_pdf_aware_layout_ocr_rects`。因此「改用 layout-first／layout-region OCR」不能當作尚未試過的解法。
- S0 effective-options (`pdf-core-native-round-2026-10-17/S0/effective-options.json`) 已有 `use_reading_order_separators=true`。官方 [options 定義](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py#L2195) 限定它利用 backend 可提供的 visible PDF shape/rule geometry；它不是從 raster 圖中偵測欄間留白的開關。純影像測試頁也沒有原文向量分隔線。PyPdfium 沒覆寫 `get_shape_lines`，[backend 預設](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/pdf_backend.py#L66) 回傳 None。
- 本機 vendored [reading-order 實作](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/postprocessing/reading_order_rb.py#L766) 已有 same-row right partner 保留垂直關係的邏輯；沒有核對完整 commit 血緣，但不能直接宣稱 #163 的相同行為在 pinned runtime 缺席。該邏輯也不能拆開已跨欄的 OCR cell。

### 新版／未合併 PR 的適用限制

GitHub API 本次回傳的 latest release 是 [v2.140.0](https://github.com/docling-project/docling/releases/tag/v2.140.0)，發布於 **2026-10-16**。它列出的 [#4633](https://github.com/docling-project/docling/pull/4633) 是 separator 候選量與 timeout 修復；[#4748](https://github.com/docling-project/docling/pull/4748) 是避免完整包在另一 OCR 區域內的 crop 被重複辨識。後者保留部分重疊區域。這些修復有實際價值，但沒有聲稱解決本例的雙欄 cell 混接，未在本機重跑。

另找到 **Open、未 merged** 的 [PR #4571](https://github.com/docling-project/docling/pull/4571)：在 cell assignment 前處理重疊 TEXT predictions、保存段落邊界，案例包含雙欄。它值得核對，但其報告的 pipeline 品質檢查關閉 OCR／table inference，不能當成已驗證的 raster OCR 修法，也不能填作已出貨預設。

## 對現有驗證的建議界線

1. 將「句內左右欄混接」維持重大缺陷，不放寬成排版小差異。
2. 已檢查同一份保存產物中的 OCR cells、layout clusters、assembled text 與 final body order，確認 OCR cell 已跨欄。下一個尚缺的證據是 pre-OCR raw layout boxes、deduplicated OCR rects、實際 crops 與 engine raw cells；不要先寫通用 Markdown 修字或重排。
3. 若是完整項目換序，研究 reading-order 模組；若同一 text item 已含兩欄片段，末端排序不能恢復原句，須回到來源 cell／cluster 分界。
4. TableFormer 的 table cell-matching 不是正文多欄修復保證。`spatial_ordering` 等 issue 草案不應寫進正式配置。
5. 上游最新變更是否已包含於 **實測 pinned 2.132.0**，由版本／程式碼核對決定；不得因 issue closed、PR merged 或「可升級」就推定問題消失。重跑或引入新方法須另有有限驗證範圍，本文件不啟動新候選。

本次未修改 production 配置、未呼叫 VLM、未下載模型、未發 GitHub 留言；查到的官方 issue 能確認這類問題存在，不能估計本機發生率或保證任何 workaround 對全部文件安全。
