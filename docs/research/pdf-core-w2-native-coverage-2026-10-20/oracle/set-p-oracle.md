# Set P oracle 預檢（2026-10-20）

正式抽樣 3 篇：07 SICA（2504.15228v2，單欄）、08 Alita（2505.20286v1，單欄）、11 Memory-R1（2508.19828v5，ACL 雙欄）。均使用 Set P 原始固定版本 PDF，僅以 pypdfium2 5.14.0 讀取前 4 頁字流，沒有 Docling、OCR 或 raster conversion。原先候選 20 Absolute Zero 的 source 也成功下載，但不納入正式 3 篇結論。

## 來源與重現

三篇固定版本 `https://arxiv.org/src/{id}` 均 HTTP 200、gzip tar，response headers 與原始下載位元組保存在本目錄。安全解開僅 `.tex/.sty/.cls/.bbl`；沒有執行 LaTeX 或來源程式碼。PDF SHA256、source archive SHA256 與逐 anchor 的 PDF 頁碼、正規化 offset 見 `set-p-checks.json`。下載成功不等於自動認證所有來源巨集及條件編譯與 PDF 一致；本次以可見正文 anchor 核對固定版一致性。

執行：

```sh
rtk /private/tmp/pdf-core-native-std-20261017/venv/bin/python docs/research/pdf-core-w2-native-coverage-2026-10-20/oracle/check_p_oracle.py
```

`check_p_oracle.py` 對人工選取、在 source 與 PDF 前 4 頁各唯一的正文 anchor 做定位，保留兩者獨立的序列，內含唯一性與正規化 self-check。查找時移除標點與空白，**這只用來找位置，不能以此判定數值、否定、單位等 Q4 語義正確**。`.txt` 是未經正文清理的 PDFium 字流，保留反例以供主線複核。

## 實際段落證據

| PDF | LaTeX 正文段落順序（anchor 摘要） | PDFium 字流定位 | 結果 |
|---|---|---|---|
| 07 SICA | `have recently made impressive…` → `These agent systems often…` → `Recent improvements in coding agents…` → `Our contributions are` → `We make our code available` | 前三段 p1；後兩段 p2 | 5 個 anchor 次序與 `sections/01_introduction.tex` 相同 |
| 08 Alita | `Large language models…rapidly evolved…` → `However, most of the current…` → `In contrast to the prevailing…` → `We conduct comprehensive experiments…` → `We propose a new agent architecture…` → `We present Alita…` | 前五個 p2，最後 p3 | 6 個 anchor 次序與 `templateArxiv.tex` 相同；包含跨頁清單延續 |
| 11 Memory-R1 | `Large Language Models…shown remarkable…` → `One early effort…` → `deciding what to remember…` → `These challenges…` → `In this paper…Memory-R1` → `Our contributions…` → `LLMs have emerged…` | 前三個 p1；接著三個 p2；最後 p3 | 7 個 anchor 次序與 `latex/acl_latex.tex` 相同；涵蓋雙欄與跨頁延續 |

18 個選定 anchor 均存在且次序一致；這是正文段落相對順序的局部證據，不能外推為整篇、每句或所有雙欄原生論文的 oracle 準確率。本次未對這 3 篇做完整逐句比對。

## 已觀察到的失準

1. **跨頁正文被 float、頁碼、arXiv 戳記切斷。** Memory-R1 p1 末尾的正文為 `later adds “I`，接著字流含頁碼 `1`、arXiv 戳記；p2 先出現 Figure 1 caption，之後才出現 `adopted another dog named Scout”`。LaTeX line 154 是同一段、同一句。未清理的字流不能直接切句，也不能因 caption 夾在中間而說正文錯序。
2. **figure 內部的文字會進入字流。** SICA p2 在 `Our contributions are` 前含 `Agent 0 / Base Code / Benchmarks…`、Figure 1 caption。Alita p2 在 `In contrast…` 與 `We conduct…` 之間含 Youtube、MCP Box、Manager Agent 等圖內文字及 Figure 2 caption。這些不能計為正文句子或正文遺漏。
3. **footnote 與清單跨頁相鄰。** Alita p2 最後第一個 contribution 後有 footnote `1 https://www.anthropic.com/news/model-context-protocol` 與頁碼 `2`，p3 才是第二個 contribution。Raw 字流會把 footnote 夾在相鄰 list item 之間；不能以鄰接關係推斷清單從屬。
4. **重複頁首。** 補充樣本 Absolute Zero p2 的第一行是重複論文標題，接著圖中文字、caption，再接 Introduction。這表明只有段落序列一致還不足以當正文 oracle。
5. **斷字與編碼。** Memory-R1 字流出現 `re\ufffe\nmarkable`、`mem\ufffe\nory` 等；SICA 有 `implemen\ufffe\ntations`。不能視為內容真正缺字，也不能無條件消除所有連字號（負號、數值範圍與專有名詞可能有意義）。

## 凍結前建議的適用／排除規則

- PDFium 字流僅作**經來源／版面確認的正文區域內**的預設相對順序 oracle。每個採用區域記錄 PDF 頁碼、字流 offset、欄、LaTeX anchor／段落 ID；不得把「可抽文字」當成正文序正確的證據。
- 非正文單獨保留並驗證分離：圖內文字、figure/table caption、footnote、running header/footer、頁碼、arXiv 戳記、作者／affiliation、bibliography、公式與 algorithm/table 內部。不計入正文句子覆蓋／順序的分母，也**不可默認它們可遺失**；其分離與必要內容完整性另列 Q4 人工待判。
- Caption/footnote 的字串位置不由 source 檔案出現位置決定，因 TeX float 可移動；以實際 PDF 幾何位置、LaTeX 環境與引用關聯認定其類型。單憑底部百分比或字級不可刪除正文。
- 跨頁／跨欄句子在移除已確認非正文後，依 LaTeX 同一 paragraph/sentence ID 合併，仍保留原頁 attribution；不在頁界硬切句或重算句數。Alita 的 itemize 依來源 item ID 保留從屬與原次序。
- 遇正文 anchor 次序衝突、非唯一對齊、缺失／不完整 ToUnicode、混雜 figure 文字、公式插入、source 條件編譯不明、source 與 PDF 版本不符：標記 `oracle_uncertain`；有可核對的 LaTeX 時改用已展開 `input/include`、排除註解／非正文環境後的來源段落順序；無可靠來源則人工看 PDF。不得把排除或 unknown 填成零錯誤。
- 對多欄頁，先確認欄界與 full-width block；來源正文段落序優先處理跨欄／跨頁 continuation。**同一正確段落合法跨欄延續不算混段**；只有無關段落被串在一起才是 Q4 候選錯誤。
- 文字對齊與語義裁定分開：查找正規化可合併空白、Unicode ligature 與經查證的換行斷字；裁定必須檢查原始否定、條件、數值、單位、對象及 list hierarchy，結果 `blocking / nonblocking / uncertain`。本預檢不提供自創通過率。

尚未檢查：完整 3 篇所有頁、每一句的語義一致性、全部 20 篇的 oracle 適用範圍。主要風險是把局部順序一致誤當成全域可自動裁定；每頁應保留 uncertain 與非正文遮罩證據。
