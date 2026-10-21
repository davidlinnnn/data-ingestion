# W2 原生論文版型覆蓋：第 1 回合檢查點

日期：2026-10-20（Asia/Taipei）。**已完成 oracle 預檢、語料／metric 凍結及兩篇各一頁 smoke，停止於本檢查點；未進入全量。** 全部產物僅在此新 W2 目錄。未讀取 R1 或封存 holdout；未修改既有程式／文件，無 commit、push、GitHub 留言或索引操作。

這一輪證明 harness 能對乾淨原生正文產生可核對的句序與結構結果；**不是 PDF Processing Profile 合格證據**。兩頁都沒有 caption／footnote，且單頁切片沒有測跨頁接合。數學結構與章節層級已有需要保留的風險。

## 1. Set F／Set P 凍結

Set F：**16 篇、164 頁，八個版型 family 各兩篇**，每篇取前 min(12, 原 PDF 頁數)頁。固定版本 PDF／source URL、兩者 SHA256、source 模板行號、PDF 字元幾何與替換理由見 最終 manifest (`corpus/manifest.json`) 與 完整版本表 (`corpus/README.md`)。所有 164 選頁都有 text layer；與來源模板、LaTeX／PDF 及欄位幾何共同確認為 born-digital，未對這些頁做 OCR 實驗。

| Family | 兩篇／選頁數 |
|---|---|
| ACL/EMNLP 雙欄 | BERT v2（12）；Sentence-BERT v1（11） |
| IEEE conference 雙欄 | Tacotron 2 v2（5）；Convolutional recurrent neural networks for music classification v3（5） |
| ACM sigconf 雙欄 | LightGCN v4（10）；Neural Graph Collaborative Filtering v2（10） |
| CVPR/AAAI 雙欄 | ResNet v1（12）；YOLO v5（10） |
| ICML 雙欄 | Image Transformer v3（10）；EfficientNet v5（11） |
| NeurIPS/ICLR 單欄 | Attention Is All You Need v7（12）；Adam v9（12） |
| Springer LNCS 單欄 | U-Net v1（8）；DeepLabv3+ v3（12） |
| 一般 arXiv 單欄 | Matrix Calculus v3（12）；Gradient Descent Optimization Algorithms v2（12） |

按**版型家族**無缺類。須明列兩項資格限制：BERT 是 **NAACL-HLT 2019 的 ACL 模板家族**，不是 ACL 2019 會議論文；若主線要求 ACL／EMNLP 的會議名稱完全吻合，ACL/EMNLP 目前只有 Sentence-BERT 一篇精確吻合，須由下一輪決定是否另建語料版本。Adam 的同版本 source archive 是嵌入 PDF 的 article wrapper，沒有可編輯正文 LaTeX；它的單欄由 PDF 幾何與 ICLR running head 核對，未用作 LaTeX oracle。

沒有只按論文會議名稱分類：LAS 的 arXiv 版本實為單欄、NCF 使用較舊 sig-alternate、SPP 已查版本不符合 LNCS 單欄，均在 conversion 前替換；Scaling Laws 的 nips 衍生樣式也換為一般 article。下載但未選定的候選保留作選擇紀錄，**不屬於 Set F**。

Set P：登錄清單 (`set-p.json`) 為原 pilot **20 篇、551 頁**，全部 PDF SHA256 與既有 manifest 核對一致；本回合 Set P conversion = **0**。全量範圍合計 **715 頁**。

最終 F／P 清單、metrics、初版 scorer／runner、兩頁獨立 reference、oracle 預檢及 F 原始 PDF／source 共 43 個檔案，在首個 Docling conversion 前記入 `freeze.json`。原先選樣 manifest-v1 是 conversion 前被替換的候選版本，沒有混入執行分母。

## 2. Oracle 預檢結果與使用規則

Set P 正式抽查：SICA 2504.15228v2（單欄）、Alita 2505.20286v1（單欄）、Memory-R1 2508.19828v5（ACL 雙欄）。同版本 source 均下載成功；**18 個選定正文 anchor 的相對次序與 LaTeX 一致**。證據、source SHA256、定位 offset 與重現程式見 [Set P oracle](oracle/set-p-oracle.md)／逐 anchor 結果 (`oracle/set-p-checks.json`)。這不是整篇逐句核對。

Set F 抽查：BERT p2 的 **10 個正文段落／item、3 個標題**，及 Attention p2 的 **9 個正文段落、3 個標題**，PDFium 正文順序與 LaTeX 一致。Reference 獨立於 Docling 輸出建立；兩頁全部 PDFium 字流組分別有 69／47 組，被正文、標題與頁碼完整分配。詳見 Set F oracle (`corpus/oracle-precheck.md`)。

已確認的反例／限制：

- Memory-R1 p1 的正文 `later adds “I`，到 p2 才接 `adopted another dog named Scout”`；中間 raw 字流插入頁碼、arXiv 戳記、下一頁 Figure 1 caption。**未清理字流不能直接切句。**
- SICA、Alita 的 figure 內文字／caption 進入字流；Alita 的 footnote 夾在跨頁 contribution list 之間。原始字流鄰接不等於正文或清單從屬。
- BERT `related.tex` 的 `figure*` 宣告在正文段落之間，但該圖實際不在 PDF p2。**LaTeX 檔案宣告順序也不能直接展平為包含 float 的視覺順序。**
- U+FFFE discretionary break、行末斷字、上下標與公式，會造成文字／切句差異。不能刪掉所有 hyphen、負號或標點來追求匹配。

凍結規則：PDFium 僅用於**經 source／版面確認的連續正文區域內**的自動順序參考。獨立標記 figure text、caption、footnote、頁首頁尾、頁碼、stamp、reference、公式及演算法，保留頁碼／bbox／排除理由；它們不進正文句序分母，但仍須驗證必要內容與分離，不能視為可遺失。跨欄／跨頁依 source paragraph／sentence ID 接續，不在頁界重算句數；合法延續不判混段。

當字流／source 衝突、巨集／conditional 不明、來源版本不合、ToUnicode 不完整、欄／區域不明或數學 scope 不可靠，改用可核對的同版本 LaTeX 正文結構與實際 PDF；無法裁定則 **ORACLE_UNRESOLVED／UNKNOWN**，不可填零。五篇的局部核對不授權把其餘 715 頁自動視為可靠。

## 3. Metric 凍結摘要

[metrics.md](metrics.md) 在首個 conversion 前凍結；SHA 在 freeze.json。定義包含：

- 可靠正文完整句的漏句／重複候選及各自 occurrence、item／來源 evidence；跨頁片段單列。
- 原序列相鄰且唯一對齊句的逆序數與可判斷 pair 分母；右欄段落插入尚未讀完左欄的三元組。
- 同一輸出段落含同頁 L／R 句子的候選；以來源段落 ID 分辨合法 continuation 與錯接。
- 頁首頁尾／頁碼混入正文、footnote／caption 的獨立性，及 source 章節文字／層級。
- 每頁 wall、實際 process user+system CPU 秒、0.1 秒抽樣 process-tree peak RSS；initialization 與保存成本另列。
- 每頁／每篇 Q4 四項 YES／NO／UNKNOWN，有原文與 item evidence；**零自動候選不等於語義通過**，沒有整體通過率。

`score.py` 是凍結初版。試跑發現 Core 預設 iterator 排除 furniture layer，初版因此未見 Attention 頁碼。保留初版程式與 `metrics-v1.json`，另以 `score_v2.py` 明確讀取各 layer 及未遍歷文字，僅重評已保存輸出。指標定義與原始 conversion 未改、沒有重跑推論；原因與 hashes 見 `scorer-revision.json`。新版控制涵蓋漏否定、改數值、重複、插欄、混段、註腳混入、標題及真實頁碼回歸。

此 runner **只支援凍結 smoke，沒有全量執行入口**。全量前還須將獨立正文 reference／oracle-uncertain 區域擴到所評頁面，並處理跨頁 occurrence 與逐頁時間歸屬；本次手工建立的兩頁 reference 不能冒充全量自動來源評讀器。

## 4. 兩篇試跑輸出樣本

沿用指定 venv：Docling-slim 2.132.0／Core 2.99.0，StandardPdfPipeline＋PyPdfiumDocumentBackend，Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`、既有 RapidOCR v6 small、TableFormer accurate、CPU4／interop1／batch1。全部 enrichment 關閉，effective options 與 S0 相同（停用 chart 的 supported-engines 集合僅 JSON 列表順序不同）。有效設定 (`smoke/effective-options.json`)、版本 (`smoke/identity.json`)、模型檔 hashes (`model-artifacts.json`)。

保持 S0 的 `do_ocr=True` 與原生頁預設 mode，未開 full-page OCR、未做 OCR 消融。兩個來源頁無 bitmap；保存的 151／71 個 textline cells **from_ocr 全為 false**。此觀察不冒稱有 reader-call tracing。只執行 **2 次 conversion／2 頁、0 retry、0 API／VLM**，持有共用 conversion lock，未併發 Docling。

| 指標 | BERT 原 p2（雙欄） | Attention 原 p2（單欄） |
|---|---:|---:|
| 完整句單位／唯一對齊 | 27／27 | 24／24 |
| 另存跨頁片段 | 2 | 0 |
| 漏句／重複候選 | 0／0 | 0／0 |
| 相鄰逆序／可判斷 pair | 0／26 | 0／23 |
| 右欄插左欄／跨欄混段候選 | 0／0 | 不適用（單欄） |
| 標題文字正確／層級錯誤 | 3／2 | 3／0 |
| furniture | 此頁無來源家具 | 頁碼 2 為 page_footer／furniture；Markdown 正文無混入 |
| footnote／caption | 無此來源區域，NOT_EXERCISED | 無此來源區域，NOT_EXERCISED |
| conversion wall 秒／CPU 秒 | 0.5123／0.5001 | 0.2680／0.3941 |
| conversion 期間 sampled peak tree RSS | 1.434 GiB | 1.437 GiB |

原始輸出：BERT metrics (`smoke/acl_bert/metrics.json`)／Markdown (`smoke/acl_bert/document.md`)，Attention metrics (`smoke/nips_attention/metrics.json`)／Markdown (`smoke/nips_attention/document.md`)。機讀彙整：`smoke-summary.json`。

人工整頁評讀：[Q4 review](oracle/smoke-q4-review.md)。BERT p2 可見正文未見改義漏／重／錯序／清單污染，但 `2.1`、`2.2` 來源應 level 2，native document JSON 全輸出 level 1、Markdown 都是 `##`。編號仍在，故「結構錯誤」確定，是否構成此用途的改義須主線裁定，不能報全面通過。

Attention p2 的普通正文無漏段／重段／串錯；但原圖 `h_{t-1}` 在 Markdown 與 native document JSON 都變成 `ht − 1`，`x_n`／`z_n`／`y_m` 與粗體向量的結構也攤平。索引字元存在不保證數學 scope 等義；**必要數學語義完整性 UNKNOWN**，不能因字面對齊就豁免。這裡的 native document JSON 指 `document.json`；完整 `result.json` 另存 parsed cell 幾何與頁圖，可供回看來源，並非已交付明確 inline math 的表示。

| 人工 Q4 | BERT p2 | Attention p2 |
|---|---|---|
| 改變意思的漏 | NO（本頁可見片段） | UNKNOWN（inline math scope） |
| 改變意思的重 | NO | NO |
| 改變意思的錯序／混段 | NO | NO |
| 清單 scope／家具污染 | NO | NO（消費者須尊重 content_layer） |
| 整頁／整篇 | UNKNOWN／UNKNOWN | UNKNOWN／UNKNOWN |

Attention 頁碼雖由 `body.children` 可達，`content_layer=furniture`；只串 body children 而忽略 layer 的下游會重新混入頁碼。本輪檢查原始輸出與 Markdown，未測下游消費者。兩篇其餘頁及跨頁接合皆 UNKNOWN。

## 5. 全量 CPU／記憶體估算

一次 initialization：wall **1.652 秒**、CPU **1.374 秒**。兩頁 conversion 平均 CPU **0.4471 秒／頁**、wall **0.3901 秒／頁**；全程 sampled peak tree RSS **1.446 GiB**。CPU 為實際 user+system，不是 wall×4。兩頁保存另耗 0.0160／0.0056 秒；監督含 interpreter／import／initialize／conversion／保存共 4.354 秒。

**條件式純文字頁線性估算**（假設全部頁都像這兩張乾淨、無圖表／註腳的原生頁）：

| 範圍 | 頁數 | CPU 分鐘 | conversion wall 分鐘 |
|---|---:|---:|---:|
| Set P | 551 | 4.11 | 3.58 |
| Set F | 164 | 1.22 | 1.07 |
| 合計 | 715 | **5.33** | **4.65** |

若分別用兩個已觀察頁的 min/max 線性外推，715 頁約 CPU **4.70–5.96 分鐘**、wall **3.19–6.10 分鐘**；**這不是全量的不確定區間或上限**。兩頁沒有 TableFormer 實際表格推論，亦未涵蓋圖片區、長篇頁圖保留、複雜 inline math、跨頁 assembly。這些全量成本目前無可靠抽樣，人工／來源標註與評讀成本也不包含在 conversion 時間內。不能將 5.33 CPU 分鐘當成 Claude 已選定的總預算。

單 worker 已觀察約 1.45 GiB；可供主線容量規劃的工程預留值為 **4 GiB／worker**，但未經長篇實測，不能當資格上限。715 頁不應同時持有所有頁圖／result；逐篇保存釋放才能讓單 worker 記憶體近似沿用。現 smoke guard 是 RSS 12 GiB 停止、host available 低於 8 GiB 停止；這是資源停止界線，不是預估消耗。詳細數值與推算公式欄位在 smoke-summary.json。

## 6. 交回主線的決策點

1. **oracle 適用範圍與全量評讀方法**：清理非正文後的局部正文順序有正面證據，但 raw PDFium 全頁序列不是通用 oracle。全量前須決定如何建立獨立區域／source paragraph 身分，以及未可靠區域的人工／LaTeX fallback 成本；不能將 UNKNOWN 當零錯誤。
2. **baseline 的結構／數學風險如何納入 Q4**：兩個 subsection 層級錯誤已實際出現；下標 scope 攤平不能默認等義。保留來源圖／parsed cells 不等於最終 Markdown／native document JSON 已完整表達必要意思。本回合沒有自行修 baseline 或啟用 enrichment。
3. **嚴格會議資格與 source 條件**：ACL family 目前包含 NAACL BERT；Adam 無 editable body LaTeX。若要求確切 ACL/EMNLP 會議各樣本或全部可用 LaTeX，須另定語料版本；不能默默改本次凍結集合。
4. **全量資源預算**：上述時間是乾淨正文條件估算；圖表／長篇與評讀成本未測，是否給全量及其資源停止界線由 Claude 決定。本回合不追加測頁，也不自行花剩餘 90 分鐘預算進入全量。

重現僅評讀：`rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python docs/research/pdf-core-w2-native-coverage-2026-10-20/score_v2.py --selfcheck`；`--job acl_bert`／`--job nips_attention` 只重評保存輸出、不推論。`run.py --smoke` 會拒絕覆寫既有 run，沒有隱性重試或全量入口。

未檢查：全量 715 頁、跨頁接合、真實 caption／footnote 分離與下游消費。已知風險是把零字面差異誤當 Q4 通過，以及乾淨單頁成本誤當完整原生論文上限；工作在本檢查點停止。
