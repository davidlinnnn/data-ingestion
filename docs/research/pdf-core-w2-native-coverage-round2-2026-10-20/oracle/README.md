# W2 Round 2：LaTeX-first oracle（獨立於 conversion）

D1 整篇順序以 LaTeX 展開後的 source_offset/order 為主，未讀取任何 Docling 輸出。所有處理只在此 oracle 目錄寫入。

## 重現

依序以 baseline venv Python 執行 `build_oracle.py`、`supplement_oracle.py`、`source_geometry.py`；設 `PYTHONDONTWRITEBYTECODE=1`。不執行 TeX、不做 OCR、不呼叫 API/VLM、不下載套件。HTTP 只用於公開 arXiv source；20 篇 P 已全取得（16 篇 HTTP 200、4 篇沿用前回合 bytes 並記錄前次 HTTP 200）。F 16 篇 source SHA256 均符合已凍結 manifest。原始 URL、回應 SHA256 與 bytes 見 `source-manifest.json`。

## 凍結規則

- Archive 僅讀取安全相對路徑、一般檔案且 ≤10 MB 的 `.tex/.ltx` members；不 extract、不執行，拒絕 symlink/path traversal。一般 gzip TeX 亦可讀。
- 展開 `input/include`，保留 root/included-files/unresolved/cycle audit；多個 document root 的選擇屬保守 heuristic，root_candidates 全數保留。附錄不截斷；references 環境排除。
- 排除 figure/table/algorithm/equation 及常見相關環境正文，caption/footnote 另類取出。正文以句尾 `.?!` 分句，≥8 個英文字詞；來源段落行號、原文、normalized、章節與順序保留。
- citation/reference 命令及 inline math 移除後，只作 alphanumeric normalization。對其他 macros/conditionals 不嘗試完整 TeX 語意；unknown_commands 與 conditional_uncertain 留存。這些候選能否可靠使用由 PDF 層交叉核對。
- 同篇所有候選（含 caption/footnote）substring 唯一，且完整 PDF text layer normalized 只有一次 exact match，且不在未知 conditional，才標 TRUSTED。PDF 定位僅決定可信度與頁碼，絕不重排 LaTeX 順序。
- F 使用完整 PDF 定位，但只納選定前 12 頁或實際頁數內的 anchors。越界為 OUT_OF_SCOPE；PDF 無法唯一定位者 ORACLE_UNCERTAIN，不能算成 Docling 漏句。
- Adam source 僅 PDF wrapper，明標 textlayer_fallback；可檢測輸出遺漏，但不能獨立驗證 PDF 原生字流讀序。
- heading 的 pdf_pages 若非唯一，scope=UNKNOWN；不能因找不到相同字樣就斷言輸出層級錯。
- inline_math_source_candidates 只記來源公式及附近文字可定位頁碼；不是實際 flattening 次數，含 caption/float/附錄等候選。不可把 5180 個候選當 F13 實際錯誤數。

## 覆蓋與限制

整體候選依類別及狀態：`{"prose:ORACLE_UNCERTAIN": 3478, "prose:TRUSTED": 6097, "caption:TRUSTED": 528, "footnote:ORACLE_UNCERTAIN": 22, "footnote:TRUSTED": 37, "caption:ORACLE_UNCERTAIN": 255, "caption:OUT_OF_SCOPE": 17, "prose:OUT_OF_SCOPE": 167, "footnote:OUT_OF_SCOPE": 3}`。可信正文 **6097**、caption **528**、footnote **37**。

這是稀疏 anchor oracle，不是整篇所有句子的完整語意覆蓋。排除 citation/math/macros 失配、PDF 內 float/註腳穿插與未解析條件分支，可降低假漏；代價是 oracle blind spots。即使可信 anchors 零漏/零錯序，也不能自行宣告全文 Q4=NO（無語意錯誤）。仍需錯誤/正確抽查，並保留未覆蓋區域 UNKNOWN。來源段落位置可能包含多個候選句，source_line 表示段落起點；caption/footnote 表示命令起點。

## 每篇分母

| ID | 選定頁數 | trusted prose | uncertain prose | out-of-scope prose | trusted caption | trusted footnote | root |
|---|---:|---:|---:|---:|---:|---:|---|
| acl_bert | 12 | 139 | 103 | 56 | 15 | 2 | main.tex |
| acl_sbert | 11 | 160 | 52 | 0 | 14 | 1 | sentence-bert.tex |
| ieee_tacotron2 | 5 | 100 | 37 | 0 | 5 | 0 | main.tex |
| ieee_crnn | 5 | 32 | 16 | 0 | 1 | 0 | icassp2017_proposing_convrnn.tex |
| acm_lightgcn | 10 | 184 | 109 | 0 | 9 | 2 | 0_main.tex |
| acm_ngcf | 10 | 182 | 140 | 0 | 7 | 5 | ms.tex |
| cvpr_resnet | 12 | 196 | 132 | 0 | 25 | 5 | residual_v1_arxiv_release.tex |
| cvpr_yolo | 10 | 215 | 40 | 0 | 15 | 0 | yolo.tex |
| icml_imagetransformer | 10 | 90 | 88 | 0 | 18 | 0 | Image Transformer/main.tex |
| icml_efficientnet | 11 | 65 | 74 | 0 | 10 | 3 | arxiv-stripped.tex |
| nips_attention | 12 | 114 | 60 | 0 | 7 | 1 | ms.tex |
| iclr_adam | 12 | 232 | 15 | 15 | 0 | 0 | arxiv.tex |
| lncs_unet | 8 | 75 | 27 | 0 | 14 | 2 | paper459.tex |
| lncs_deeplab | 12 | 54 | 91 | 8 | 10 | 0 | main.tex |
| arxiv_matrixcalculus | 12 | 65 | 204 | 88 | 0 | 0 | matrix-calculus.tex |
| arxiv_gradientdescent | 12 | 148 | 70 | 0 | 0 | 5 | overview_sgd.tex |
| p01 | 28 | 138 | 129 | 0 | 19 | 0 | main.tex |
| p02 | 22 | 119 | 50 | 0 | 3 | 3 | main.tex |
| p03 | 25 | 202 | 124 | 0 | 23 | 1 | main_v2.tex |
| p04 | 27 | 160 | 113 | 0 | 26 | 0 | main.tex |
| p05 | 31 | 211 | 146 | 0 | 11 | 0 | neurips_2026.tex |
| p06 | 29 | 274 | 124 | 0 | 29 | 0 | main.tex |
| p07 | 18 | 159 | 39 | 0 | 5 | 3 | neurips_2025.tex |
| p08 | 12 | 141 | 40 | 0 | 15 | 0 | templateArxiv.tex |
| p09 | 28 | 268 | 116 | 0 | 18 | 0 | neurips_2025.tex |
| p10 | 30 | 144 | 160 | 0 | 18 | 2 | main.tex |
| p11 | 20 | 196 | 77 | 0 | 31 | 0 | latex/acl_latex.tex |
| p12 | 28 | 172 | 135 | 0 | 12 | 0 | main.tex |
| p13 | 27 | 267 | 158 | 0 | 19 | 0 | acl_latex.tex |
| p14 | 16 | 170 | 81 | 0 | 18 | 0 | main.tex |
| p15 | 27 | 259 | 101 | 0 | 28 | 0 | paper.tex |
| p16 | 64 | 292 | 65 | 0 | 26 | 0 | main.tex |
| p17 | 22 | 163 | 99 | 0 | 9 | 1 | neurips_2025.tex |
| p18 | 18 | 102 | 127 | 0 | 9 | 0 | main.tex |
| p19 | 29 | 367 | 167 | 0 | 26 | 1 | colm2025_conference.tex |
| p20 | 50 | 242 | 169 | 0 | 33 | 0 | main.tex |

模板及 p2–p4 PDFium 原生換行行段 bbox的初步幾何依據見 `family-geometry.json`。幾何只用來描述樣本版型，含圖表/多欄同列時可能 mixed，並非已人工確認的每頁分類。

原始資料來源：[arXiv source retrieval](https://info.arxiv.org/help/faq/source.html)；每篇確切 source URL 已記在 source-manifest.json。


V2修正：`input/include` 只匹配完整命令（排除 includegraphics 前綴）；v1 每篇保留在 `oracle.v1.json`。空白分詞不足 8 詞、abstract/首 section marker 前的 frontmatter 全部降為 uncertain；abstract 本身仍保留 prose。每 anchor 的 uncertainty_reasons 與每篇 oracle_uncertainty_reasons 統計可解釋分母。來源 paragraph 的 `(source_file,source_offset)` 可作 paragraph ID。
