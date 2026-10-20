# W3b HTML 來源可信度與轉換排除規則

研究角色：背景 primary-source legwork。只讀官方文件、下載的來源 HTML 與本機工具 metadata；全域 oracle freeze 前未讀 E0/E1/mapper/評分。來源公式20與表格10的抽樣清單由 oracle/table agents 獨立固定後，才分派互斥樣本人工核對。

## 來源能證明什麼

arXiv 官方 HTML 是由論文 TeX 轉換而來的可存取格式；官方明示仍可能有轉換、套件支援及呈現問題。因此「官方網域、HTTP 200、成功下載」只證明來源可取得，不能直接證明公式與表格忠於同版本 PDF。[arXiv accessible HTML](https://info.arxiv.org/about/accessible_HTML.html)、[官方錯誤說明](https://info.arxiv.org/about/accessibility_html_error_messages.html)。

ar5iv 的維護者說明它提供從 arXiv 經 LaTeXML 轉成的 HTML5，是衍生轉換來源，不是第二份獨立作者原稿。[ar5iv 維護者 repo](https://github.com/dginev/ar5iv)。LaTeXML 的宏展開、DOM rewrite、math parse 與序列化均可能改變衍生表示；因此 HTML alttext 與同頁 MathML 不能當作彼此獨立的兩票真值。[LaTeXML architecture](https://math.nist.gov/~BMiller/LaTeXML/manual/architecture/latexml/)。

## 三個版本必須拆開

1. **論文版本**：完整 arXiv `idvN`，與原 PDF SHA256、來源 archive SHA256 綁定。無 `vN` 的識別碼指向最新版本；各版內容、附錄、標題甚至作者可能不同，不能悄悄以 latest 取代凍結 PDF。[arXiv identifier](https://info.arxiv.org/help/arxiv_identifier.html)、[version availability](https://info.arxiv.org/help/versions.html)。
2. **轉換器版本與種類**：保存原 HTML 的 `meta generator`、生成註解、footer 原字串；分記 `LaTeXML` 或 `LaTeXML oxide` 及其自述版本。找不到時記 `UNKNOWN_GENERATOR_VERSION`，不可從下載時間、CSS 版本或網域猜。oxide 維護者自述是 Rust 重實作，不能把其版本號視同 Perl LaTeXML 相同版本。[oxide 維護者 repo](https://github.com/dginev/latexml-oxide)。
3. **轉換產物快照**：requested URL、HTTP/final URL、retrieval UTC、redirect 鏈、原 HTML SHA256、canonical/og:url/citation metadata 與任何生成日期原文。SHA 只能重現這份產物；不證明其內容與同版 PDF 一致。

本輪下載中 BERT 實際來源 `html/F-acl_bert.html`（SHA `979577cb850282e11206957a52022b0c4c667a8df08a2427743590c9bb678530`）註解明列 `LaTeXML oxide (version 0.7.5)`；requested/final URL 為 `1810.04805v2`，但 canonical/og URL 省略 vN。這是**精確版本端點已成功回應**的證據，與**產物內文未自行宣告論文版本**兩件不同事情；後者需用原 PDF/同版 TeX 的局部內容核對，不能僅因 canonical 無版即宣告內容一定錯版，也不能僅因 requested URL 有版即宣告全部內容忠實。此例只用於 metadata 說明，未依模型錯誤挑樣。

## 轉錯偵測與可用性判定

官方 LaTeXML 錯誤依 Info/Warn/Error/Fatal 分級，Error 通常仍繼續產生輸出，Fatal 才通常無法繼續；所以可 parse 的 HTML 或非空公式不等於成功轉換。警告（例如 math parse 未識別）也不是語義一定錯，需看局部證據。[LaTeXML error codes](https://math.nist.gov/~BMiller/LaTeXML/manual/errorcodes/)。

本輪先記錄所有 `ltx_ERROR`、`ltx_missing`、error/warning 顯示節點、unsupported package 提示、殘留未知控制序列、缺圖/缺表/缺 MathML 及可用的 logs；保留 CSS class、node id/XPath、上下文、數量與原字串。不把一般正文中的 error 字樣算轉換錯，也不把一個頁首警告擴大成全文不可用。這是保守偵測規則，**沒有錯誤標記不證明沒有靜默誤轉**。

每個抽樣單位需 source-only 對同版原 PDF 頁圖逐項查：公式全部可見列、符號、上下標、分母、根號/括號範圍、運算子、數值、單位與條件；表格完整 header/value、rowspan/colspan、分組、單位/註腳與必要對象。HTML `alttext` 與 MathML 的關係也要核對，不能只拿 alttext 字串替 MathML 結構背書。巢狀 split/aligned 的整個 source block 不等於一條獨立式；每筆另記外層 unit、實際可見列及核對範圍。

| 狀態 | 採用規則 |
|---|---|
| `SOURCE_VERIFIED_LOCAL_UNIT` | PDF 同一單位身分與必要語義已人工確認；只對該單位生效，不推論整篇忠實。 |
| `EXCLUDE_VERSION_MISMATCH` | 有明確不同版 id 或內容差異證據；不當成 PDF 抽取錯誤。 |
| `EXCLUDE_HTML_CONVERSION_ERROR` | 同版 PDF/TeX 存在必要內容，HTML/MathML 已漏、改或錯組；留 source evidence，退出相應 oracle 分母。 |
| `UNKNOWN_VERSION` | 端點/metadata 無法證實，且局部內容不能核對；不自動當錯版或正確。 |
| `UNKNOWN_ALIGNMENT` | 公式或表格無法獨立定位到原 PDF；不猜頁、不用 Docling 定位。 |
| `UNKNOWN_CONVERSION_FIDELITY` | 未完成必要列/符號/表頭/跨欄組合核對，或證據互相衝突。 |
| `UNAVAILABLE` | 下載失敗、landing/error page、無實際論文 HTML；不算零錯誤。 |

判定證據固定後才讀 E0/E1。若稍後發現 oracle 錯誤，須 amendment 記錄舊/新 SHA、理由、受影響單位；不能依模型結果靜默換 gold。整體 HTML 可用篇數、可定位篇數、局部人工驗證單位數、排除/UNKNOWN 數各自報分母，不創造任意通過率。

## 本機 renderer 盤點（未執行 render）

完整環境快照見 `renderer-inventory.json`。指定 venv 可用 `latex2mathml 3.81.1`、`lxml 6.1.3`、`sympy 1.14.0`、`pypdfium2 5.14.0` 與 Pillow；TeX (`latex/pdflatex/xelatex/lualatex/tectonic`)、LaTeXML/oxide、pandoc 不在 PATH，已檢查的 MacTeX 位置也無 pdflatex。沒有安裝任何套件。latex2mathml 是 TeX→MathML 轉換器，**不能因此聲稱已排版或驗證任意論文宏**。

`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` 存在，bundle 版本 `155.0.8059.85`；Safari 也存在。Chrome 官方記錄從109提供 MathML Core，並有現成 headless screenshot/DOM 模式，因此是後續 step5 本機 MathML renderer 的候選；目前僅讀 metadata，未啟動 screenshot 或跑評分。[Chrome MathML Core](https://developer.chrome.com/blog/chrome-109-beta)、[Chrome headless 官方文件](https://developer.chrome.com/docs/automation-and-testing/headless)、[W3C MathML Core](https://www.w3.org/TR/mathml-core/)。

若 step5 獲授權，可使用凍結本機 HTML/MathML 與固定 viewport/font 環境 render，不依賴 CDN/下載新 renderer。需另記 browser/build、字型、頁面 SHA、render 完成與錯誤；瀏覽器畫得出來只證語法與呈現，仍不能證明公式數學保義。TeX render 不可用時，應報 `TEX_RENDERER_UNAVAILABLE`；不可用 latex2mathml 成功代替真 TeX 編譯成功。既有 PDF 頁圖可由 PDFium 零推論 render；它是原 PDF 參考，不是新 TeX renderer。
