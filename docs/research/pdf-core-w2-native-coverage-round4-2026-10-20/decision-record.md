# W2 最終決策紀錄：#84 的 F01–F03 研究交付

日期：2026-10-20。範圍為凍結 Set F 16 篇／164 頁與 Set P 20 篇／551 頁，共 36 篇／715 頁 born-digital 論文。W2 於本回合收斂，交 W3；沒有更動正式 Profile、Docling、pipeline、Git index 或 GitHub。

## 選定設定

保留 **StandardPdfPipeline + PyPdfiumDocumentBackend、Heron、use_reading_order_separators=True、官方 bookmark-only heading**。Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；heading `enabled=True/use_bookmarks=True/use_numbering=False/use_style=False`，其餘數值沿用官方預設。未改動的 `use_font_style=True` 在 `use_style=False` 的關閉規則下不啟用 style heuristic。CPU4、batch1、TableFormer accurate/cell matching 與 RapidOCR v6 small 均沿用 S0；`do_ocr=True` 亦原樣保留，未另做掃描或 OCR 消融。公式、code、picture description/classification、chart 等 enrichment 及遠端服務全部關閉。套件固定 docling-slim 2.132.0／docling-core 2.99.0，沒有下載模型或安裝套件。

V1（separators=False）、V2（Egret）維持不採用。V4 官方預設 ThreadedDoclingParseDocumentBackend 雖完整修好原 26 件中的 **5 件**，但新增 **6 組**經頁圖確認的阻擋，故依「零新增阻擋且至少修好一件」規則 **不採用**。不以機器 anchor 找到率上升取代語義裁定。詳見 [V4 報告](report.md)、[逐事件／135 變動候選裁定](comparison/V4-adjudicated.json)。這是已測官方選項中全域採用的取捨，並非宣稱其他官方版本永遠無解。

**研究時 generate_page_images=False、generate_picture_images=False 只為記憶體安全。正式 Profile 必須開啟這兩項影像輸出，供 F06 使用；記憶體由正式 core 的 group5 分組處理。** 本研究不實作 group5。R3 兩篇影像開關等價控制僅證明該控制樣本的文字、label、結構、閱讀順序、Markdown 與評分未變，不證明圖片功能等價、全語料峰值記憶體相同，亦不是 V4 backend 等價控制。[繼承控制的來源與範圍](controls-equivalence.json)。[effective options](selected-effective-options.json) 是 V4 研究執行的設定；選定 Profile 使用相同 S0/options 組合但 backend 保留 PyPdfium，正式兩項影像開關恢復 True。

## F03：bookmark-only 的覆蓋範圍

26 篇有 PDF outline，10 篇沒有。467 個可評 section/subsection/subsubsection，baseline：177 正確／254 層級錯／33 strict missing／1 role error／2 ambiguous；bookmark-only：**352／79／33／1／2**，175 個轉正確、0 個由正確轉錯。所有改善都來自有 outline 組；對缺 outline 文件無效。

|組別|篇數（有可評標題）|bookmark-only 正確|層級錯|strict missing|role／ambiguous|仍有任一上述候選的篇數|
|---|---:|---:|---:|---:|---:|---:|
|有 outline|26（25）|311|8|33|1／2|10|
|無 outline|10（9）|41|71|0|0／0|9|

無 outline 清單：F-acl_bert, F-acl_sbert, F-cvpr_resnet, F-cvpr_yolo, F-icml_imagetransformer, F-icml_efficientnet, F-iclr_adam, F-lncs_deeplab, P-18-2511.16043v1, P-19-2511.10395v1。Adam 沒有可評結構標題，不能當全對；有 outline 的 Matrix Calculus 亦無可評結構標題。層級錯分布於 14 篇；strict missing 分布 9 篇，role error 1 篇，ambiguous 2 篇，這些篇數可重疊。缺 outline 的 9 篇可評文件全部仍有層級不符。

79 個 level error 包含可能的全篇一致層級偏移，33 個 strict missing 只是凍結唯一匹配規則未對上，不能直接改稱必要文字真漏或 Q4 改義。此處如實列 F03 結構缺口；**沒有把 19 篇有標題候選當成 19 篇 Q4 阻擋，也沒有宣稱其他文件 F03 全文驗收通過**。另有 197 個 paragraph/subparagraph 命令不在此結構分母，與正文是否漏失不同。完整逐篇與定義見 [heading-outline.md](heading-outline.md)、[heading-outline.json](heading-outline.json)。#83 qualification 應保留這項限制；自訂 numbering/style 後處理只能列為可選方案，沒有實作或授權為 Profile。

## 已知阻擋與根因去向

選定組合保留原 26 件確認事件；本回合另人工發現 P20 p25、27、30、31、33 的 5 個既有重複 caption 事件。這些原已存在於 baseline，沒有列為 V4 新壞，也沒有改動原 26 件的修復分母。最終已知 **31 件／13 篇／40 個 job-pages**。分母是本文涵蓋的 36 篇，不把未選 Set F 後續頁納入。相同頁上的多個事件只計一次；各類篇數／頁數不可直接相加。

| 根因類別 | 事件 | 篇 | 頁 | family 分布（篇／頁） | 交接 |
| --- | --- | --- | --- | --- | --- |
| 正文／署名／prompt 對象錯序 | 5 | 5 | 8 | CVPR/AAAI 2篇/4頁；NeurIPS/ICLR 3篇/4頁 | #83 |
| caption／圖／algorithm 插斷正文 | 9 | 6 | 14 | ICML 1篇/2頁；NeurIPS/ICLR 2篇/2頁；Pilot-other/unknown 2篇/8頁；general arXiv (article; template uncertain) 1篇/2頁 | #83 |
| 原生字流重複、圖字／頁外字與家具污染 | 13 | 2 | 12 | Pilot-other/unknown 1篇/3頁；general arXiv (article; template uncertain) 1篇/9頁 | #83 |
| formula 空 text，orig 有必要內容 | 2 | 2 | 2 | NeurIPS/ICLR 2篇/2頁 | #81 |
| picture children 已有原生文字但出口省略 | 1 | 1 | 1 | NeurIPS/ICLR 1篇/1頁 | #81 |
| Markdown colspan 展開重複 | 1 | 1 | 3 | NeurIPS/ICLR 1篇/3頁 | #81 |

其中 #81 為 4 件／4 篇／6 頁的出口映射可修證據；#83 為 27 件／11 篇／34 頁，尚無已證實可全域安全採用的官方方案。後者部分事件在拒採的 V1/V2/V4 個別改善或修好，但不能將有新增阻擋的變體當正式解法。native duplication/noise 這一類不全是同一 clipping 機制：部分來源 PDF 有舊／隱藏字流，PyPdfium 合併 bbox 再取字會放大重複；p48 等未完整證明 clipping 根因。重複已在原生 orig／cells，不能全歸給 Markdown serializer。stage 與逐頁證據沿用 R3，加上 [backend 原始碼／五處核對](diagnostics/backend-notes.md)、[新增既有 caption 證據](comparison/newly-discovered-baseline.json)。

可選自訂方案僅供使用者裁定：float/caption 邊界後處理、跨頁句子保留可追溯續接、頁外／clipping 文字過濾與兩欄順序校正。這些都涉及刪字／重排風險，W2 沒有實作，也不把它們當作已解限制。標題 heuristic 的無退化組合只有本次選定 bookmark-only；不加單篇例外或數值調參。

| family | 篇 | 頁 | CONFIRMED_BLOCKING | CLEAN_AFTER_ADJUDICATION | UNKNOWN | 確認受影響頁 |
| --- | --- | --- | --- | --- | --- | --- |
| ACL/EMNLP | 5 | 86 | 0 | 5 | 0 | 0 |
| ACM sigconf | 2 | 20 | 0 | 2 | 0 | 0 |
| CVPR/AAAI | 2 | 22 | 2 | 0 | 0 | 4 |
| ICML | 3 | 39 | 1 | 2 | 0 | 2 |
| IEEE conference | 2 | 10 | 0 | 2 | 0 | 0 |
| NeurIPS/ICLR | 9 | 238 | 6 | 3 | 0 | 12 |
| Pilot-other/unknown | 6 | 167 | 3 | 3 | 0 | 11 |
| Springer LNCS | 2 | 20 | 0 | 2 | 0 | 0 |
| general arXiv | 2 | 24 | 0 | 2 | 0 | 0 |
| general arXiv (article; template uncertain) | 3 | 89 | 1 | 2 | 0 | 11 |

Pilot 的 family 使用 R3 已保存的來源／模板判定；Pilot-other/unknown 與 general arXiv（article; template uncertain）明保留不確定性，不硬歸到八個受控 family。[逐篇清單、每類事件與頁](selected-limitations.json) 保存全部 36 篇。

## #81 交接：最小匯出原型的證據與邊界

只讀原始 DoclingDocument JSON、零推論，全部 36 篇已套用：[原型與結果](mapper/README.md)、[四案逐 item 證據](mapper/four-case-evidence.json)。產生自訂 mapped.json 及可表達 span／uncertainty 的 MD(raw HTML)/HTML，沒有修改正式 mapper 或原 DoclingDocument。

|規則|代表事件與可回收資訊|已驗證的修復範圍|
|---|---|---|
|空 text 回退 orig，原位置交付並標角色不確定|Adam p12 texts/419 定義量詞及公式；P16 p25 task IDs|必要字詞可回收；P16 60 IDs 可取，35 個為回退。沒有證明公式、上下標、左右欄／清單關係完整正確|
|picture children 文字另成 picture-native channel，與 C supplement 分開|SICA p12 pictures/4、5，28 text items、21 list markers|第二框 text 1439／orig 1488，補 marker 後交付 1488；原出口省略可修。圖內文字不混正文，C supplement 未執行；不重建原生語義順序|
|native table_cells 單次交付、保留 row/col span|SkillRL p22–24 的 4 個 colspan 重複 instance|4 個已知 serializer 重複實例各交付一次；不是所有原生表格布局已正確|

影響量：366 個 orig 回退 text items（30 篇）；226 個 picture 框含 10,265 個原生 text items（36 篇）；238 個 table items、6,723 native cells，其中 74 表／26 篇含 282 個 merged cells。主要 item refs 聯集 830；加 picture descendants 為 11,095，不能當作語義段落或修好事件數。

所有來源 text/cell refs 及渲染 refs 各交付一次、來源 SHA 不變。**0 新增同 ref 重複不等於跨 ref 無語義重複**：來源 2,290 組同篇不同 ref 相同完整字串被保留。64 個 fallback items 含控制字元，明示不確定。所有 picture children 交付也暴露 16 個低字量框／4 篇；高字量圖仍可能只是軸標／數字，未逐字驗收噪聲。8 個原生重疊表格用 TABLE_LAYOUT_UNCERTAIN 單次 cell 清單，避免偽造欄位關係。純文字／會剝除 HTML 的下游未驗證。這些風險是 #81 正式 mapper 必須接手的界線，**不據原型將任何整篇改判通過**。

## 與 Q4 / Canonical Acceptance 的關係

13／36 篇（36.1%）已有至少一個經頁圖確認、會改變意思或符合 Q4 明列家具／重複／必要資訊漏失的缺陷，故選定組合的原始 native/Markdown 交付無法讓這些文件通過 Canonical Acceptance。這是此凍結開發／pilot 語料中已知受影響的比例，**不是產品整體失敗率或自創通過門檻**。這 40 頁為已確認範圍，不是全語料缺陷頁的完整普查。

其餘 23 篇為 CLEAN_AFTER_ADJUDICATION，表示所有自動 F01/F02 候選已裁定且未見阻擋，並附已知 incidental 檢查；不是逐字完整驗收，也不能由此宣稱 Canonical Acceptance 23 篇通過。F03 尚有上述結構候選；數學、圖像內容與未被 anchor 覆蓋的文字仍有資格驗證限制。純行內數學／下標攤平另歸 F13，不以此單獨否決 F01/F02；若同時漏必要定義、條件或對象（如 Adam/P16），仍是 Q4 阻擋。

oracle 為凍結整篇 LaTeX prose anchors（含附錄），caption/footnote 分開，Adam 是 PDFium text-layer fallback；稀疏／唯一性／正規化、float/algorithm scope、符號編碼與 clipping 都有盲點。尤其 caption 重複和家具 margin gate 會漏報，本回合 5 個新增既有事件正是反例。v3 保留不變；新判定另存，不回寫 oracle 或舊分析器。沒有據「anchor 全找到」斷言全文完整。

## 稽核與完成範圍

V4 36/715 全成功、單一逐篇 CPU4 worker、零重試、12 GiB RSS／主機可用 4 GiB 守門；pipeline wall 845.98 秒，conversion CPU 3013.78 秒（另初始化 CPU 49.59 秒），峰值 10.99 GiB，取樣最低主機可用 20.29 GiB。[resources.json](resources.json)。36 份 PDF、44 個 frozen oracle 檔案、v3 分析器與註冊 runner/backend source hash 檢查 PASS；[verification.json](verification.json)。只把 dormant supported_engines 集合序列化順序正規化，未忽略有效設定值。

所有產物只在本 round4 新目錄；沒有開 holdout、碰 R1、下載模型、API/VLM、commit、push 或 GitHub 留言。W2 在此停止，W3 與 #81/#83 依上述證據接手；正式交付與任何自訂後處理由使用者裁定。
