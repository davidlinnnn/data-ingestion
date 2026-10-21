# dots.ocr native parser 預檢獨立核對

日期：2026-10-16（Asia/Taipei）。核對範圍是 `preflight.py`、`preflight/results.json`、三種 Markdown、完整 `document.json`，另外用原 runtime 跑 11 個小型合成文字案例，以及 7 個 resize 尺寸對照。沒有模型呼叫、權重下載、PDF／holdout 讀取、套件安裝或 source patch。

**結論：既有預檢正確證明選定原生接點可保留公式、code 區塊與段落，但不支持「設定兩個 export flags 後一般內容均安全」或「完整 pipeline／F13／F14 已通過」。** 另確認合法 Markdown 的 HTML code literal 會在原生 parser 被改義；截至已發布 v2.139.0，沒有找到涵蓋這個簡單案例的官方修正。可以繼續把 dots 模型 raw output 做可行性研究，但目前不能把這條 mapping 路徑稱為完整合格方案。

## 既有預檢真的證明了什麼

- 原始行內段落保存在一個 `TextItem`，輸出 `escape_underscores=False, escape_html=False` 後完整 LaTeX、prime、code `<=` 與句子保持一致。F13 不要求每個 token 都有獨立 typed JSON；此例的段落內 LaTeX 可交付是有效的局部證據。
- 預設 export 把 `$x_i^2$` 寫成 `$x\_i^2$`，把 backtick 內的 `<=` 寫成 `&lt;=`；只關 underscore 仍未解決 code 字面值。實際 Marko render 也顯示 code 內 `&lt;=` 變成可見 entity 字串，不是單純 HTML source 編碼差異。
- 獨立公式 `p(y_{<s}) = ... \tag{4}` 以 FormulaItem 完整保存，預設 Markdown 保留字串；沒有舊 DocTags 的 `<s` 截斷。這裡沒有實際 KaTeX／MathJax render，不能宣稱所有 LaTeX 語法或特定 renderer 已驗。
- 四行 code 成為 CodeItem，縮排、`<=`、字典／陣列 literal 保持相同；預設和 native flags 皆保留區塊內容。這個 probe 沒驗真實 DGM 或巢狀 backtick fence。
- TableData 的 `A` 保留 row_span=2，值及位置正確；Markdown 把跨列 A 重複呈現，不等於 Markdown 能表示 rowspan。Picture caption 實際指向 `#/texts/4` 的 Figure 1，crop 可由保存的 page image 導出，picture 自身 image 欄位為 null。
- 手動提供 model_image_size=(1120,1680) 及 page=(560,840) 時，範例座標等比例縮半、page_no=3 正確；並未實跑 DocumentConverter 的頁碼組裝或影像 processor。
- `all_boxes_within_page`／`physical_page_preserved` 僅遍歷存在的 provenance；HTML 文字拆分後 `bold` 和句點子項沒有 own provenance，這兩個 true 並非全部 child provenance 完整的證明。
- 截斷 JSON 原生 parser 仍回傳 10 個 item；strict JSON 完整性 gate 拒絕它，負例有實際意義。JSON 完整仍不保證文字無漏或意思正確。

證據：原始預檢結果 (`preflight/results.json`)、原生結構 (`preflight/document.json`)、[原生 Markdown](preflight/native-markdown.md)。所有受檢檔案保持未改。

## 全域 export flags 的實際副作用

獨立 probe 用 Docling-slim 2.132.0、Core 2.99.0、Marko 2.2.4。Marko 只用來檢查一般 Markdown／inline code 的渲染，沒有用它判斷公式排版。程式 (`review/export_probe.py`)、逐例 JSON／Markdown／HTML／visible text (`review/export-results.json`)。

| 輸入文字的意圖／表示 | 預設 export | 兩個 flags 關閉 | 判斷 |
|---|---|---|---|
| LaTeX `$x_i^2$`、inline code `<=` | 改變原始 Markdown，code entity 變可見文字 | 原字串保持 | native Markdown 候選需要這組 options 才通過此例 |
| 字面 `__init__`、`_TEMP_` 未 escaped | 顯示保留底線 | render 成 bold／italic，底線消失 | 當 source 本意是 literal 時不可接受 |
| 同一 literal 使用正確 `\_` escape | 保留 | 保留 | 模型必須輸出符合其 Markdown 契約的 escaping |
| 字面 `<widget>` 未 escaped | literal 可見 | 被當 HTML tag，literal 消失 | 當 source 本意是 literal 時不可接受 |
| `<widget>` 用 `&lt;widget&gt;` 正確文字 escape | 雙重 escape，entity 可見 | literal 正確可見 | native flags 較符合「已是 Markdown」輸入 |
| backtick code span 內 `<widget>`／`a <= b` | code 被額外 escape | code literal 正確 | unknown-tag case 正常 |
| backtick code span 內 `<b>bold</b>` | 變成 `**bold**` | 也變成 `**bold**` | **原生 parser 在 export 前先破壞內容** |

裸 `__init__`／`<widget>` 是 Markdown 語意歧義：若模型本來就把它當格式，flags off 不算新增錯誤；若來源印出 literal，則模型必須用合法 Markdown 表達。不能以此推斷 dots 模型必然失敗，也不能把 flags off 推廣至所有 provider／所有純文字 item。

但 `Use \`<b>bold</b>\` literally; preserve \`x_i\`.` 是**合法的 code span Markdown**，仍被 `_HTML_TAG_PATTERN` 導向 HTML parser，把 b-tag 解為格式，輸出 code `**bold**`。這是確定的 native mapping 缺口，不是評分偏好，也不是 token 沒有 typed JSON 的問題。把 code span 裡的 `<b>` 改成 entity 也不通用，CommonMark code span 會將 entity 原樣顯示；本次沒有加任何這類修補。

建議將兩個 flags off 列成「dots native Markdown 的候選 export 設定」，先固定，再同時驗正確 literal、公式、code；不能當作產品全面通過。也不新增辨別每字串後 escape 的 custom 後處理。

## 已發布版本核對：最早格式支援不等於缺陷已修

官方文件的 Native dots inline formatting 段落來自 [commit 0d604da／PR #4631](https://github.com/docling-project/docling/commit/0d604da3abf47437aa673eca9b5bf4bf6c621e1d)，首次發布為 [v2.135.0](https://github.com/docling-project/docling/releases/tag/v2.135.0)，時間 2026-10-07 10:42:24 UTC。截至本次查核，最新正式發布 [v2.139.0](https://github.com/docling-project/docling/releases/tag/v2.139.0) 是 2026-10-14 12:18:27 UTC，兩版 dots_utils.py SHA-256 相同：`275598760faa3377ccfca453c4bbff49c8912a33875b85601e314ea387b83622`。版本查核 JSON (`review/release-source-check.json`)

v2.135 的 `_add_inline_text` 確實新增 Marko 與 formula／code literal 優先規則，但只在含 `*` 或 `_` 時進入 Markdown 解析，而且只有 rendered HTML 出現 `<strong>`／`<em>` 才採用該輸出。簡單 `Use \`<b>bold</b>\` literally.` 不含這些觸發條件，因此仍讓 raw `<b>` 進 HTML parser；即使有普通 `x_i`，未產生 emphasis 也會回到原字串。故不能因文件總述就宣稱這個 edge case 已修。v2.133／2.134 仍是原 parser；v2.135 至2.139及目前 main 的此段邏輯相同。[v2.135 source](https://github.com/docling-project/docling/blob/v2.135.0/docling/utils/dots_utils.py)、[v2.139 source](https://github.com/docling-project/docling/blob/v2.139.0/docling/utils/dots_utils.py)

這一節是 released source 的分支核對，沒有安裝 v2.135／2.139，也沒有把新 source 注入舊 runtime 冒稱正式版執行。**未找到本案例已修復的最小已發布版本；不建議為了這個缺陷單獨升級到2.135。** 可以另外把新版本列作格式能力候選，但它不是本缺陷的已證修正。

## 正常 2× 頁面 geometry 與小圖邊界

未安裝 Transformers 的預檢 runtime 不能直接匯入 processor。因此本核對從官方 [Transformers v4.57.6 source](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/qwen2_vl/image_processing_qwen2_vl.py) 取出**未修改的純 `smart_resize` 函式**，用固定 dots preprocessor 的 factor=28、min=3136、max=11289600，與實際 installed Docling helper 比較。這不是 processor／model 執行，亦未 patch runtime。函式來源紀錄 (`review/release-source-check.json`)、對照程式 (`review/geometry_probe.py`)、結果 (`review/geometry-results.json`)

| 原始推論圖像 pixels | dots resize | Docling 推定 | 一致 |
|---|---|---|---|
| 1120×1680 | 1120×1680 | 1120×1680 | 是 |
| 1200×1600 | 1204×1596 | 1204×1596 | 是 |
| 1224×1584（US Letter 2×） | 1232×1596 | 1232×1596 | 是 |
| 1191×1684（約 A4 2×） | 1204×1680 | 1204×1680 | 是 |
| 1200×1800 | 1204×1792 | 1204×1792 | 是 |
| 200×300 | 196×308 | 392×560 | **否** |
| 1800×2400 | 1792×2408 | 1344×1820 | **否** |

因此**正常 A4／Letter 2× 並非已知一定座標錯**；兩組參數落在共同 pixel 範圍內時，factor28 round 可一致。CPU tiny smoke 或大頁超過2.5MP才有明確參數分岔。正式執行仍應記錄實際推論 image size／grid，不以 source 函式比較取代 model bbox 準度或完整 pipeline mapping 驗證。

本次只新增 review 文件及 synthetic probe artifacts；原 run／結果／套件保持未改。尚未驗模型內容、實際 PDF 全流程、LaTeX renderer、公司 GPU 或高頻負載。
