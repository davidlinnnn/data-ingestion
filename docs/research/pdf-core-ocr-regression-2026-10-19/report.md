# OCR 固定回歸比較：本輪不採用全域替換

2026-10-19。**完成方向配對與 R0／R1／T1 七頁比較；沒有一套滿足本輪完整的無重大缺陷／無重大回歸要求，依停止條件結束。**沒有因故障頁改善就採用候選，也沒有追加模型、門檻、PSM、padding 或修字規則。正式配置未修改；S0 仍只是已知不合格的研究基線。

## 固定方法

三套都實際執行 `StandardPdfPipeline`＋PyPdfium；Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3。Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`、CPU FP32、threshold 0.3、compile off；CPU4、OCR scale3、layout/OCR/table batch1。保留 DEFAULT／PDF-aware layout OCR regions 與原生 20-unit dilation，沒有改 SDK 或客戶端合併政策。TableFormer V1 accurate 維持啟用；formula/code/picture enrichment 沿用 S0 停用設定，本輪不驗收這些能力。

| 配置 | OCR 元件與唯一差異 |
|---|---|
| R0 | RapidOCR 3.9.2／ONNXRuntime CPU；PP-OCRv6 det_small＋rec_small；mobile_v2 0/180 cls 開啟，threshold0.9；text score0.5 |
| R1 | 與 R0 相同，只設 `use_cls=False` |
| T1 | 只替換 OCR options：Docling 原生 Tesseract CLI 5.5.3、`psm=3`、固定 `eng+chi_tra`，權重與原廠設定雜湊鎖定。此 adapter 每個 OCR region 會先嘗試 OSD；明確指定語言時 OSD 失敗仍接續 OCR |

T1 是整個 OCR 引擎比較，不是 detector-only 消融，也不共用 RapidOCR classifier。R0 已逐值重現原 S0 的 cells／texts／body／furniture 與 Markdown，才允許其他配置。`registration.json` 鎖定 94 個來源／模型／程式檔，`environment-amendment.json` 補記下述原廠輸出設定。

## 防止只修好故障頁

- 故障頁之外，先凍結 **6 頁、4 份獨立文件**：ACL2024 雙欄論文2頁、WikiSkill單欄密集英文1頁、教育部手冊繁中與英文網址2頁、政大手冊標題及識別字1頁。
- 來源單位61個、來源文字行263條；來源原生文字均已分配。圖片內文字、原生 Unicode 不完整的圖內標籤及獨立公式依事前紀錄排除。兩段行內數學識別字已在推論前校對並納入，沒有在結果變差後移除。
- 來源、標註、12張方向裁圖與評讀器在候選推論前封存。資料來自已曝光的 regression 文件，**不是新盲測 holdout**；既有封存 holdout 未開啟。輸入是144dpi清晰raster，非自然劣化掃描。
- 九項零推論測試含原 S0 混句、舊拆圖方案漏標題、合法跨欄標題、word/line粒度差異、空輸出及實際 SDK 序列化控制。所有自動分數只產生 `REVIEW_REQUIRED`，逐頁人工核對後才作判決。

## 方向分類結果

12條來源行取自上述4份文件，另製作其180°對照；它們是配對衍生資料，不是24份獨立樣本。固定裁圖，執行一次 native classifier 及兩次 recognizer，各辨識24條。90/270°與整頁旋轉不在本次行級 probe 範圍。

| 輸入 | cls 開 | cls 關 |
|---|---:|---:|
| 12條正向行，忽略標點空白後全文相同 | 12 | 12 |
| 12條180°行，全文恢復 | 9 | 0 |

三條倒置行雖被判為180°，分數未超過0.9，因此沒有實際翻轉。沒有下調門檻。既有114行配對已證明關閉分類器可恢復 Background；新資料也證明全域關閉會失去倒置處理能力。**R1只能視為有上游正向保證時的條件候選，且仍未修復混欄。**T1 的整頁倒置能力未經此 probe 驗證，不能從其正向頁輸出推論。

## 跨文件人工評讀

| 案例 | R0 | R1 | T1 |
|---|---|---|---|
| 已知雙欄故障頁 | 3個原始混行、2個最終混段，Background破損 | Background恢復；混行／混段保留 | 11個正文段落與標題分離完整，無混句；註腳／bullet小錯 |
| ACL p1 | 五個BLEU數值與一行具名引用破損 | 數值與引用恢復；無新增重大缺陷 | 正文可接受；`+`→`十`等符號小錯已記錄 |
| ACL p2 | 首行破損，`2 Our Method`無法正確保存 | 標題字串恢復，卻插進左欄 `stu- … dent model` 句中，仍重大混句 | 左欄完整、右欄標題獨立；但行內 `x_1/x_2/x_n` 與 `H_dec` 識別字／括號嚴重退步 |
| WikiSkill p2 | 正文可接受 | 文本與R0完全相同 | 正文可接受；頁碼小錯 |
| NDHU p7 | 正文、網址保留；圖註與caption小錯 | 與R0完全相同 | 兩個網址的 `yuntech` 變成 `yunteeh`／`vuntech`，有新增識別字缺陷 |
| NDHU p9 | `※`從功能及解釋註記消失，登入限制與目標功能的關聯破損 | 與R0完全相同，既有語意缺口保留 | 目標符號保留，但整句登入限制註記變成拉丁亂碼，新增重大退步 |
| NCCU p3 | 正文、登入方法、B5A識別字保留 | 與R0完全相同 | 登入方法仍存在；`壹`→`Be`是編號破損，不是整個標題遺失 |

人工解除的旗標也保留：ACL p1 左欄末段接右欄首段是合法的同一句續接；NDHU分散的3/4/5不是連續字串；NCCU標題不能因短字串未完全匹配就宣告消失。相反，NDHU的`※`雖被文字正規化忽略，仍在人工作業判為具有語意的缺失。**沒有用平均分數掩蓋個別重大回歸。**

完整來源區塊／DocItem證據見 `known-review.json`、`manual-english-review.json`、`manual-chinese-review.json`。自動原始混行數不直接用來排名 T1，因其輸出詞框，RapidOCR則輸出行框。

## 本機成本

| 配置 | 七頁完成耗時合計 | 七頁逐頁耗時中位數 | OCR階段合計 | Sampled process-tree RSS峰值 |
|---|---:|---:|---:|---:|
| R0 | 18.54s | 2.82s | 15.53s | 5.19GiB |
| R1 | 18.16s | 2.71s | 15.07s | 5.57GiB |
| T1 | 17.33s | 2.47s | 13.79s | 1.81GiB |

Pipeline預先初始化分別1.59／1.43／1.14s，另列而未混入逐頁耗時。每頁只有一次觀測，含原生 debug 圖及證據序列化；不同內容頁的中位數不是服務p50。RSS以0.25s抽樣，短命子程序可能漏峰。不能由此宣稱穩定的效能排名、p95、吞吐SLO或GPU表現。這次 T1 沒有顯示整體成本增加，但準度退步已足以否決全域替換。

## 執行偏差與證據有效性

首次 T1 的自訂 tessdata 只有模型，缺少原廠 `configs/tsv`；CLI沒有產生Docling期待的TSV欄位，七頁均出現 `KeyError: text`。這是**我的環境封裝及 preflight 覆蓋缺口**，不是 Tesseract 準度失敗。原始七頁完整保留於 `T1-environment-invalid/`。

補入與原廠位元相同的1行TSV設定後，以具名 `environment-amendment.json` 記錄一次額外T1七頁執行。R0/R1沒有重跑；原runner、權重、語言、PSM、來源、判準及評讀器不變。這是明確偏離原「每頁一次」預算的環境修正，**不能報成零重跑**。有效比較21頁次，加上7個無效環境嘗試；另有一次重複啟動被既有輸出保護在worker建立前拒絕。沒有API／VLM或準度調參重試，修正後未再追加候選。

## 本輪判決與下一個決策

**不採用 R1 或 T1 作全域正式替換。**R1有跨文件的方向修復證據，但混欄仍不可接受且倒置處理退步；T1證明同一個大OCR輸入可以正確分欄，卻在中文註記／識別字及行內數學內容產生重大回歸。因此不能只把責任歸給「框合得大」，也不能把一頁修好當成完整方法合格。

若要繼續，我建議下一個具名工程決策聚焦**保留欄界的 pre-OCR 區域策略**，並保留現有方向與中文回歸。它是新方法工程，不是已存在的 Docling 開關；本輪沒有實作或自動啟動。後續閱讀順序、表格、公式/code enrichment、公司GPU與高頻ingest仍待各自驗收；本報告不改變 #84 既有必要能力或終局。
