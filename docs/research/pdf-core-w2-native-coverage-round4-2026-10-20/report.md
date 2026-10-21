# W2 round4：V4 與 mapper 可修性驗證

最終建議：**不採 V4，維持 PyPdfium + Heron + separators=True + bookmark-only heading。** 全部 36 篇／715 頁成功、零重試。依原 26 件來源事件逐一核對，完整修好 **5**、部分改善 **8**、未完整修好 **21**；新增 **6 組／6 篇／16 job-pages** 的確認阻擋，所以未符合零新增條件。原事件內的對象替換退化另外報，不藏在群組計數裡。

## 方法與凍結

V4 唯一 backend 改為 pinned 2.132.0 的 PdfFormatOption 官方預設 `ThreadedDoclingParseDocumentBackend`（docling-parse 7.22.3），並非已 deprecated 的舊 V4 alias。其餘固定選定 S0 組合、研究影像關閉；26 件均重核對 native/MD/原頁圖。凍結 v3 source-identity 比較 72 removed／63 added，共 135 rows 全部逐頁圖裁定；移除警報不直接算修好，新增警報不直接算新壞。Adam 的數學符號／algorithm scope 假警報保留明確理由。未改 oracle、分析器與舊產物。

來源：註冊與 SHA (`registration.json`)、逐件裁定 (`comparison/V4-adjudicated.json`)、[原30篇詳細報告](comparison/original30-summary.md)、[補跑6篇詳細報告](comparison/recovery-report.md)、[backend notes](diagnostics/backend-notes.md)。F03 的 heading transitions 另列於 `heading/V4-changes.json`，不與正文候選混算。

## 完整修復／新增阻擋（來源群組）

| family | 原26完整修好 | 部分改善 | 新增阻擋 |
| --- | --- | --- | --- |
| ACL/EMNLP | 0 | 0 | 1 |
| ACM sigconf | 0 | 0 | 0 |
| CVPR/AAAI | 0 | 0 | 0 |
| ICML | 0 | 0 | 1 |
| IEEE conference | 0 | 0 | 0 |
| NeurIPS/ICLR | 2 | 2 | 2 |
| Pilot-other/unknown | 1 | 2 | 1 |
| Springer LNCS | 0 | 0 | 0 |
| general arXiv | 0 | 0 | 0 |
| general arXiv (article; template uncertain) | 2 | 4 | 1 |

| 原事件 | 論文 | 確認頁 | V4裁定 |
| --- | --- | --- | --- |
| resnet-p1-right-before-left | F-cvpr_resnet | 1,2 | PERSISTING_BLOCKING |
| yolo-p1-right-before-left | F-cvpr_yolo | 1,2 | PERSISTING_BLOCKING |
| imagetransformer-figure2-breaks-body-sentence | F-icml_imagetransformer | 5 | PERSISTING_BLOCKING |
| imagetransformer-table5-breaks-amazon-mechanical-turk | F-icml_imagetransformer | 7 | PERSISTING_BLOCKING |
| adam-author-merged-into-algorithm1 | F-iclr_adam | 1,2 | PERSISTING_BLOCKING |
| adam-definition101-english-omitted | F-iclr_adam | 12 | PERSISTING_BLOCKING |
| wikiskill-table1-breaks-crosspage-sentence | P-01-2608.27454v1 | 7,8 | PERSISTING_BLOCKING |
| p02-first-author-attribution-order | P-02-2603.02766v1 | 1 | PERSISTING_BLOCKING |
| skillrl-colspan-markdown-duplicates | P-05-2602.08234v2 | 22,23,24 | PARTIAL_IMPROVEMENT |
| sica-figure2-breaks-subagent-sentence | P-07-2504.15228v2 | 4 | PERSISTING_BLOCKING |
| sica-p12-prompt-export-suppression | P-07-2504.15228v2 | 12 | CONFIRMED_FIXED |
| sica-p13-initialrequest-problem-order | P-07-2504.15228v2 | 13 | CONFIRMED_FIXED |
| seal-algorithm1-breaks-onpolicy-sentence | P-17-2506.10943v1 | 4 | PERSISTING_BLOCKING |
| p03-caption-spliced-p14 | P-03-2603.25158v5 | 13,14 | PERSISTING_BLOCKING |
| p03-caption-spliced-p21 | P-03-2603.25158v5 | 20,21 | PERSISTING_BLOCKING |
| incidental-p03-table3-breaks-reporting-clause-p5-p6 | P-03-2603.25158v5 | 5,6 | PERSISTING_BLOCKING |
| p10-chart-label-contamination-p9 | P-10-2509.25140v2 | 9 | PARTIAL_FIX |
| p10-chart-numeric-contamination-p26 | P-10-2509.25140v2 | 26 | PARTIAL_FIX |
| incidental-p10-offpage-old-figure-task-object-p10 | P-10-2509.25140v2 | 10 | CONFIRMED_FIXED |
| p16-task-ids-formula-role-p25 | P-16-2505.22954v1 | 25 | PARTIAL_FIX |
| P-20-2505.03335v1:furniture_in_body:00035 | P-20-2505.03335v1 | 6 | CONFIRMED_FIXED |
| p20-duplicated-corrupt-body-p6 | P-20-2505.03335v1 | 6 | PARTIAL_FIX |
| p20-table2-caption-spliced-p12 | P-20-2505.03335v1 | 11,12 | CONFIRMED_FIXED |
| p20-caption-duplicated-p28 | P-20-2505.03335v1 | 28 | PARTIAL_FIX |
| p20-sudoku-caption-duplicated-p46 | P-20-2505.03335v1 | 46 | PARTIAL_FIX |
| p20-caption-object-contamination-p48 | P-20-2505.03335v1 | 48 | PARTIAL_FIX |

| 新增事件 | 論文 | 頁 | 經原圖核對的缺陷 |
| --- | --- | --- | --- |
| v4-memgen-p25-column-order-prompt-suppression | P-13-2601.01885v3 | 25 | V4RAGtext653/C.4heading654提前到左欄prompt/C.3前；text656評分prompt入picture5，MD變imageplaceholder。MD呈C.4後C.3且Trainingconfiguration接在C.3，baseline/implementation對象錯屬，必要prompt英文亦漏交付。 |
| v4-p10-running-title-body-pollution | P-10-2509.25140v2 | 2,4,6,8,9,10,23 | V4將running-title字串標text/body並輸出MD；p9還接入p8末MaTTS consistently後，改變正文續句。Q4明列頁首混入正文為阻擋。 |
| v4-p18-running-title-interrupts-crosspage-prose | P-18-2511.16043v1 | 2,3,7,8 | V4將p3頁首接在p2正文acts後；p8頁首插入p7complex與p8constraint satisfaction tasks之間。真家具污染與必要條件／對象讀序插斷；eligible_margin門檻不能推翻頁圖清楚可辨頁首。 |
| v4-p20-running-title-breaks-deepseek-continuation | P-20-2505.03335v1 | 10,11 | V4texts233將p11頁首接到p10句尾DeepSeek之後，必要模型對象與跨頁續文被頁首插斷。 |
| v4-seal-p18-json-keys-orphaned | P-17-2506.10943v1 | 18 | V4text437在Exampleoutput後偷接use_basic/use_chain/use_repeat三key，code438的data_generation只剩use_size。三個key離開原JSON物件，必要清單從屬/對象改錯；非無害paragraphmerge。 |
| v4-skillrl-p24-result-skills-omitted | P-05-2602.08234v2 | 24 | V4table14最後一列只餘Step3Result:tion.Key碎片；SpatialPriors/完整Result必要結果及技能說明在所有native text/cells及MD均消失。removedduplicate/role是因漏內容，非修復。 |

指定五處字層污染 **0 件完整修好，5 件皆部分改善**：P10 p9、p26；P20 p6、p28、p48。P10 p9仍圖字插入 WebArena/Shopping 和 between/memory，p26仍數字／圖例混在正文；P20仍重複或混入舊 figure 對象。另 P20 p46 Sudoku 重複也僅部分改善。docling-parse 避免 PyPdfium 合併 bbox 再取字的一部分放大，但來源舊字串仍存在，不能宣稱 clipping 問題已解。五處原生字流與 backend cells 追蹤 (`diagnostics/backend-source-spotchecks.json`)。

caption 插斷：只有 P20 Table2 p11–12 這件完整修好，其餘 8 件仍在；SICA p12 prompt 出口、p13 引言／payload 順序另完整修好，P10 p10 舊圖 reviewer 任務和 P20 p6 footer 污染完整修好。P16 60 IDs 中 4 個恢復、3 個新漏，交付 25→26，但仍 34 個 formula.text 空；這是同一既有群組內的得失，不是整件修復，也不能描述成「沒有新漏」。

## 新發現的既有阻擋與 oracle 盲點

P20 p25、27、30、31、33 各一個 caption 重複事件，baseline 原生與 Markdown 原已重複，V4少一些但仍2份。這5件不列新增回歸，不加進原26修復分母；最終選定設定已知31件／13篇／40頁，交接已納入 [decision-record.md](decision-record.md) 與 `selected-limitations.json`。詳見 逐圖的baseline/V4/source證據 (`comparison/newly-discovered-baseline.json`)。

本輪固定 v3 不檢查 caption 字串重複的所有實例，家具50pt margin gate亦會漏識正文區內錯放的頁首；因此 machine furniture contamination 仍0，不等於沒有家具阻擋。原圖確認的新增頁首仍照 Q4 判阻擋。沒有用匹配失敗的符號、code／formula 角色或獨立腳註單獨當語義缺陷。

## 凍結 v3 描述指標（baseline→V4；非語義結論）

正文 anchor 6024/6097（98.803%）→6036/6097（99.000%），missing73→61、duplicate4→2、MD LIS外19/5982→21/6002、混段4→6。caption528全部找到，角色正確455→460、正文內71→66；footnote37全部找到、角色正確37→36，新增角色候選逐圖裁為獨立交付／metadata問題。欄跳躍0候選不能反證已確認的 CVPR 首頁錯序；Adam mixed/column仍NOT_EVALUABLE，未當0品質通過。

| family | 頁 | anchor找到／分母 | missing | duplicate | MD LIS外 | 混段 |
| --- | --- | --- | --- | --- | --- | --- |
| ACL/EMNLP | 86 | 932/932 → 932/932 | 0→0 | 0→0 | 0→3 | 0→0 |
| ACM sigconf | 20 | 366/366 → 366/366 | 0→0 | 0→0 | 0→0 | 3→3 |
| CVPR/AAAI | 22 | 411/411 → 411/411 | 0→0 | 0→0 | 18→18 | 0→0 |
| ICML | 39 | 257/257 → 257/257 | 0→0 | 0→0 | 0→0 | 0→0 |
| IEEE conference | 10 | 132/132 → 132/132 | 0→0 | 0→0 | 0→0 | 1→1 |
| NeurIPS/ICLR | 238 | 1763/1832 → 1772/1832 | 69→60 | 4→2 | 1→0 | 0→2 |
| Pilot-other/unknown | 167 | 1279/1282 → 1281/1282 | 3→1 | 0→0 | 0→0 | 0→0 |
| Springer LNCS | 20 | 129/129 → 129/129 | 0→0 | 0→0 | 0→0 | 0→0 |
| general arXiv | 24 | 213/213 → 213/213 | 0→0 | 0→0 | 0→0 | 0→0 |
| general arXiv (article; template uncertain) | 89 | 542/543 → 543/543 | 1→0 | 0→0 | 0→0 | 0→0 |

逐篇數值（每列都 conversion success，表內均 baseline→V4）：

| 論文 | family | 頁 | 找到／分母 | missing | duplicate | MD LIS外 | 混段 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F-acl_bert | ACL/EMNLP | 12 | 139→139/139 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-acl_sbert | ACL/EMNLP | 11 | 160→160/160 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-ieee_tacotron2 | IEEE conference | 5 | 100→100/100 | 0→0 | 0→0 | 0→0 | 1→1 |
| F-ieee_crnn | IEEE conference | 5 | 32→32/32 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-acm_lightgcn | ACM sigconf | 10 | 184→184/184 | 0→0 | 0→0 | 0→0 | 1→1 |
| F-acm_ngcf | ACM sigconf | 10 | 182→182/182 | 0→0 | 0→0 | 0→0 | 2→2 |
| F-cvpr_resnet | CVPR/AAAI | 12 | 196→196/196 | 0→0 | 0→0 | 5→5 | 0→0 |
| F-cvpr_yolo | CVPR/AAAI | 10 | 215→215/215 | 0→0 | 0→0 | 13→13 | 0→0 |
| F-icml_imagetransformer | ICML | 10 | 90→90/90 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-icml_efficientnet | ICML | 11 | 65→65/65 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-nips_attention | NeurIPS/ICLR | 12 | 114→114/114 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-iclr_adam | NeurIPS/ICLR | 12 | 187→178/232 | 45→54 | 0→0 | 1→0 | 0→0 |
| F-lncs_unet | Springer LNCS | 8 | 75→75/75 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-lncs_deeplab | Springer LNCS | 12 | 54→54/54 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-arxiv_matrixcalculus | general arXiv | 12 | 65→65/65 | 0→0 | 0→0 | 0→0 | 0→0 |
| F-arxiv_gradientdescent | general arXiv | 12 | 148→148/148 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-01-2608.27454v1 | Pilot-other/unknown | 28 | 138→138/138 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-02-2603.02766v1 | NeurIPS/ICLR | 22 | 119→119/119 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-03-2603.25158v5 | Pilot-other/unknown | 25 | 202→202/202 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-04-2605.23904v2 | general arXiv (article; template uncertain) | 27 | 160→160/160 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-05-2602.08234v2 | NeurIPS/ICLR | 31 | 211→209/211 | 0→2 | 4→2 | 0→0 | 0→0 |
| P-06-2606.14239v2 | NeurIPS/ICLR | 29 | 274→274/274 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-07-2504.15228v2 | NeurIPS/ICLR | 18 | 138→158/159 | 21→1 | 0→0 | 0→0 | 0→1 |
| P-08-2505.20286v1 | general arXiv (article; template uncertain) | 12 | 141→141/141 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-09-2502.12110v11 | NeurIPS/ICLR | 28 | 268→268/268 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-10-2509.25140v2 | Pilot-other/unknown | 30 | 141→143/144 | 3→1 | 0→0 | 0→0 | 0→0 |
| P-11-2508.19828v5 | ACL/EMNLP | 20 | 196→196/196 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-12-2508.16153v2 | Pilot-other/unknown | 28 | 172→172/172 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-13-2601.01885v3 | ACL/EMNLP | 27 | 267→267/267 | 0→0 | 0→0 | 0→3 | 0→0 |
| P-14-2607.03726v1 | ACL/EMNLP | 16 | 170→170/170 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-15-2610.05923v1 | Pilot-other/unknown | 27 | 259→259/259 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-16-2505.22954v1 | NeurIPS/ICLR | 64 | 290→290/292 | 2→2 | 0→0 | 0→0 | 0→0 |
| P-17-2506.10943v1 | NeurIPS/ICLR | 22 | 162→162/163 | 1→1 | 0→0 | 0→0 | 0→1 |
| P-18-2511.16043v1 | ICML | 18 | 102→102/102 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-19-2511.10395v1 | Pilot-other/unknown | 29 | 367→367/367 | 0→0 | 0→0 | 0→0 | 0→0 |
| P-20-2505.03335v1 | general arXiv (article; template uncertain) | 50 | 241→242/242 | 1→0 | 0→0 | 0→0 | 0→0 |

標題467個：選定B-only 352正確／79層級錯／33 strictmissing／1role／2ambiguous；V4 351／79／33／4／0。correct→role兩件：SICA p15 ExampleTraces被頁首、MD不交付（F03內容損失，但未證成語義改義），P10p9 4.4變text（完整獨立文字仍在，未證從屬改義）。其餘ambiguous/missing轉換不當作整體修復。逐項評分 (`heading/V4-assessment.json`)與原30／6篇獨立heading review保留。這不是凍結v3正文指標的一部分。

## mapper 與最終交接

三條最小 JSON-only 匯出規則已套全部36篇。Adam定義、P16 IDs、SICA prompt原生文字皆可交付；SkillRL4個已知colspan重複實例可單次交付。未宣稱任何整篇因此通過Q4。366orig回退／226picture框／10,265picture文字項／282mergedcells；主要item聯集830。所有來源text/cells單次交付，但來源跨ref重複、64控制字元、低字量圖字及8重疊表格仍需qualification。完整原型、單位定義、四案證據和風險見 [mapper/README.md](mapper/README.md)。

正式 Profile 必須重開 page/picture images 供F06，group5處理記憶體。已知限制與#81交接、#83資格驗證、Q4受影響13/36（36.1%）的精確適用範圍全部在 [decision-record.md](decision-record.md)；其餘23篇CLEAN不是全文Canonical Acceptance通過。

## 時間與記憶體

36 conversions，715 pages；逐篇worker總wall **845.98s**（14.10min），其中conversionwall 720.39s。conversionCPU 3013.78s，初始化CPU 49.59s。每頁stage service p50/max **1.164/12.612s**；含佇列的residence p50/max 10.238/94.173s，不可累加當wall。每頁取樣所屬程序treeRSS p50/max **5.29/10.99GiB**，不是每頁獨占記憶體；host取樣可用最低 20.29GiB。完整資源 (`resources.json`)。

沒有失敗或重試。36PDF與44oracle files、v3、backend、runnerhash與有效設定檢查306項PASS：`verification.json`。所有產物限本R4。W2完成，停在此檢查點，交W3；未commit/push/GitHub留言、未開holdout/R1、未下載模型。
