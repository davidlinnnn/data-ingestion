# W3b：結構答案、逐條準度與不確定訊號

本回合只使用已凍結的36篇、715頁。E0沿用 PyPdfium、Heron、separators=True、bookmark-only heading；重用保存輸出。唯一新推論是表格的官方 `do_cell_matching=False` 消融，沒有新增 E1 enrichment。RAW 與套用 W2 三條 mapper 規則的 MAPPED 分開報告。

## 1. HTML 答案與可信度

36/36 可下載 HTTP 產物；35/36 有可用的結構 HTML。Adam 僅是 PDF wrapper，答案為 UNAVAILABLE，不能視為零表格或零錯誤。每篇 requested/final URL、SHA256、版本宣告在 [html-manifest.json](html-manifest.json) 與 [source-version-summary.json](source-version-summary.json)。轉換器自述為 LaTeXML oxide：16篇0.7.5、20篇0.7.6；不是 Perl LaTeXML 的版本號。

來源先抽固定10張完整表、20條公式行對照原PDF頁圖，再於11:20:54 UTC以 [oracle-freeze.json](oracle-freeze.json) 封存108檔，之後才開始本輪目標評分。10表的數值、標籤與合併格均局部忠實；20公式行中19條可獨立比較，1條忠實但只是續行而排出獨立公式分母。沒有局部確認的 LaTeXML 改義，不能據此推論所有未抽查單位正確。

公式保留外層環境與逐條身分；矩陣、cases 等內部列不拆成獨立等式。表格以共同 caption 的 semantic table 為判定單位，多子表合為複雜表。246張 semantic tables 中183張確定在範圍內、3張範圍外、60張來源定位仍未知。來源宏、版本、續行、無法定位、跨頁實體範圍與多值角色不明均保留 UNKNOWN，不猜答案。完整規則見 [source-trust.md](source-trust.md)、[method.md](method.md)。

## 2. 表格全量與官方消融

IN_SCOPE 的183張表使用同一份答案；數值與行、列、表頭的對應一起計分。一般表須零錯，複雜表逐表錯率≤5%；未知不充當通過，也不一律當漏值。關鍵比較未評。

| 版本／交付 | PASS | FAIL | UNKNOWN |
|---|---:|---:|---:|
| E0 RAW | 5 | 10 | 168 |
| E0 MAPPED | 5 | 10 | 168 |
| cell matching=False RAW | 28 | 8 | 147 |
| cell matching=False MAPPED | 30 | 8 | 145 |

以上183張已定位表之外，另60張來源定位 UNKNOWN、3張範圍外；Adam 的表數不可知。全246張已知HTML表的記帳為 E0 5PASS／10FAIL／228UNKNOWN／3範圍外、cellFalse MAPPED 30PASS／8FAIL／205UNKNOWN／3範圍外，不能把60張省略後冒稱全量均已判定。按family／複雜度的範圍覆蓋見 [table/inventory-coverage-root.md](table/inventory-coverage-root.md)。

| 複雜度 | E0 MAPPED P/F/U | cell matching=False MAPPED P/F/U |
|---|---|---|
| 一般 | 4/5/62 | 21/4/46 |
| 複雜 | 1/5/106 | 9/4/99 |

| Family | 複雜度 | E0 MAPPED P/F/U | cellFalse MAPPED P/F/U |
|---|---|---|---|
| ACL/EMNLP | 複雜 | 0/1/14 | 0/1/14 |
| ACL/EMNLP | 一般 | 3/3/9 | 7/1/7 |
| ACM sigconf | 複雜 | 0/0/7 | 0/0/7 |
| CVPR/AAAI | 複雜 | 1/0/9 | 1/0/9 |
| CVPR/AAAI | 一般 | 0/0/5 | 0/1/4 |
| ICML | 複雜 | 0/0/9 | 0/0/9 |
| ICML | 一般 | 0/0/8 | 2/0/6 |
| IEEE conference | 複雜 | 0/1/3 | 0/0/4 |
| NeurIPS/ICLR | 複雜 | 0/2/15 | 1/0/16 |
| NeurIPS/ICLR | 一般 | 1/0/16 | 3/0/14 |
| Springer LNCS | 複雜 | 0/0/4 | 0/1/3 |
| Springer LNCS | 一般 | 0/0/3 | 0/0/3 |
| 一般arXiv／article，模板不確定 | 複雜 | 0/0/8 | 0/1/7 |
| 一般arXiv／article，模板不確定 | 一般 | 0/1/7 | 3/1/4 |
| Pilot-other／unknown | 複雜 | 0/1/37 | 7/1/30 |
| Pilot-other／unknown | 一般 | 0/1/14 | 6/1/8 |

Set F的一般arXiv單欄兩篇沒有此處可評的IN_SCOPE semantic table，不把零表說成通過。RAW差異與全部來源定位未知／範圍外記帳見下面的完整表。

確認修好3張：P11 p8 Table2、P13 p9 Table4、P13 p26 Table6。0張 PASS→FAIL；但另有8張 UNKNOWN→FAIL，不能宣稱已證零退化。7張 FAIL→UNKNOWN 也不算修好。MAPPED另保留了RAW Markdown丟到表外的父表頭，增加2張通過。

逐表錯誤率及上下界、錯配／漏／多生與未知原因見 [table/per-table.csv](table/per-table.csv)；完整 RAW/MAPPED 證據見 [table/report.md](table/report.md)、[table/summary.json](table/summary.json)。按實際 family 與複雜度的表見 [table/family-summary-supplement.md](table/family-summary-supplement.md)：沿用 W3 的版型標籤，保留 Pilot-other／模板不明，不把來源 oracle 的 Pilot placeholder 冒充版型。這只補充分析標籤，沒有改 source 或評分。精確錯誤率的分布只納入分母、全部資料點及多生都能判定的表；不把未知填為0%。來源多值角色不明與目標壓欄是主要剩餘未知，HTML 解決來源可取得問題，尚未解決所有行列關係。

已FAIL表的確證錯率下界範圍：E0為5.93%–50%，cellFalse為4.76%–33.33%；其未決上界另列，不能當精確錯率，也不能用兩組不同表的分布宣稱改善。4.76%的YOLO一般表仍FAIL，因一般表門檻為零錯；不是套複雜表5%。完整下界記帳見 [table/fail-rate-bounds-root.json](table/fail-rate-bounds-root.json)。

新conversion只跑34篇中有表格的175個原PDF頁、84個連續區間；單worker CPU4。175頁的raw layout與原E0逐值相同，表格變化定位於table structure／cell matching與組裝；RAW父表頭丟失定位於serializer／Markdown語法。conversion wall405.89秒、CPU1401.69秒，含啟動監控wall528.68秒；peak tree RSS6.18GiB，最低host available15.71GiB。所有守門通過，沒有重試或enrichment。完整記錄見 [cell-resources.json](cell-resources.json)、[page-scope-control.json](page-scope-control.json)。這是表頁對照，不是完整文件讀序重新驗收；全文與interval的跨頁組裝等價未另行證明，實體範圍不足的表保留UNKNOWN。

## 3. 逐條公式

逐條 E1 的40條可評來源為 **9完全一致（22.5%）／28接近（70%）／3文字錯誤（7.5%）**；RAW/MAPPED文字桶相同。逐頁核對為10核心數學改義、22核心保義、8式號／鄰文等metadata雜訊。這是可唯一對齊子集，不是全模型準確率，也不與W3原50個block抽查相加。

來源初凍結的286個單條候選不改。評分時發現複合定義粒度問題，另封全域source-only guard及排除註記：3個確認複合、10個可能複合而保留UNKNOWN；E0/E1同步退出，尚符合自動條件273條、150可唯一定位、123身分未知。未flag者未全量人工認證。v1與補充v2均保留；補充只用來源式號、原PDF頁及式號字元bbox固定native ref，不依E1相似度挑答案。

17篇保存E1實際85 refs＝57 formula＋28 code；57 formula refs中39有獨立source行分數（共40行）、7個parent可定位但行界不明、3個複合、8個身分不明。未處理或無法對齊不算模型漏句。E0 orig可獨立取界126條：0完全一致／49接近（38.89%）／77文字錯誤（61.11%），另24 locator行界不明。E0是攤平PDF字流對TeX結構，文字錯誤桶**不等於改義**，亦不表示RAW Markdown已交付；orig由mapper規則1回填並保留角色不確定。共同40條及family的對帳見 [formula/combined-summary-root.md](formula/combined-summary-root.md)。

代表阻擋包括LightGCN p5式11漏必要的 E^(k)、式14把兩個根號相乘改成巢狀根號，EfficientNet的逐元素運算改成張量積、Attention的 d_model 改名、SICA的金額符號改字。反例是YOLO的leaky-ReLU核心分支正確卻帶鄰圖碎片，因此文字ERROR不直接當Q31核心改義。完整逐條、family與頁圖理由見 [formula/assessment-v2/report.md](formula/assessment-v2/report.md)、[formula/assessment-v2/combined-per-formula-scored.json](formula/assessment-v2/combined-per-formula-scored.json)。

## 4. 原生 code 與兩版輸出

99個來源單位全保留（78 code／21 algorithm）；72個確定在評測範圍、27個來源位置未知。67個固定原PDF區域已擷取glyph及座標，65個以實際近等寬字元advance重建可讀縮排，2個algorithm僅展示x階層，不冒稱原始空格。

全99個來源套用同一範圍守門：共用ref、鄰區混入或未能獨立確認邊界者退出主CER，不能把整item重複當成多段source並計假多生。native／E0各13個可比；E1與三源共同可比皆8個、來自4篇。這8個包含3段Python（同一篇GradientDescent）、2個prompt、2個printed log及1個TOOL_CALL XML，不能當成8個可執行程序或8篇獨立證據。

| 同8個單位 | raw CER p50 | 去空白CER p50（診斷） | 運算子序列相同 | 數字序列相同 |
|---|---:|---:|---:|---:|
| native | 3.67% | 0% | 8/8 | 8/8 |
| E0 RAW/MAPPED | 8.23% | 0% | 8/8 | 6/8 |
| E1 RAW/MAPPED | 16.54% | 0.48% | 6/8 | 4/8 |

逐行字元距離、原文、配對／未配對與縮排診斷見 [code-native/line-diagnostics-root.csv](code-native/line-diagnostics-root.csv)。已配對行的字面縮排差異為native 0/184、E0 7/23、E1 154/180；E0有169個未配對來源行，native有8、E1有12。這些是物理換行／空白差異，含整體縮排offset；**不是已確認邏輯錯誤或漏行數**。文字CER亦不設任意通過閾值。

原21個人工標籤維持9保義／6 Q4阻擋／4對齊錯誤／2未知。6個阻擋包含log、prompt、檔名與條件文字，不能全稱可執行Q33邏輯錯誤。額外P04 p22 Algorithm1已有頁圖證據：原生與E0保留的∈、≥被E1改成=、>，else也遭改寫，屬static Q33阻擋，未執行來源程式。其餘無法展開算法表示的CER維持UNKNOWN。

在這個小共同子集，原生字面與縮排較忠實；3段Python既有人審並未確認E1邏輯退化，不把字面差異當成邏輯敗例，也不推廣為所有code可靠。完整分母、各單位與原生座標見 [code-native-v4-utf16/report.md](code-native-v4-utf16/report.md)、[code-native-v4-utf16/summary.json](code-native-v4-utf16/summary.json)。UTF-16修正後全99個source重評，僅P03 code00009一個原生字元恢復；主13個的CER與共同8個的全部指標不變。原v3封存不動；逐行補充表的共同8分母亦逐值確認相同。

## 5. 不確定標記的佐證訊號

門檻在任何訊號計算前固定：a與b均要求字元一致度≥0.95、運算子及數字序列完全一致；公式primary verified須a、b、c全部可用且通過，code須a、b。缺訊號不verified。另報固定單訊號及組合、ROC，沒有依結果挑門檻。語法render成功不等於數學保義，描述文字的字層相似度不等於描述內容正確。方法見 [signals-preregistration.json](signals-preregistration.json)、[signals-operationalization.json](signals-operationalization.json)。

W3原50個公式block保留15阻擋／28核心保義／7metadata；原21個code保留9保義／6 Q4阻擋／4對齊錯誤／2未知。沒有把block標籤複製到逐條，也沒有把本輪40條加到這個主分母。primary a只接受原PDF區域glyph，組裝後orig僅作診斷；多人共用大item與human小單位範圍不一致時UNKNOWN。code21來自20個prediction groups，相關性另記。

| W3訊號（錯誤為正類） | 可評且人審已定 | 錯誤警示precision | recall | 規則標成verified後的已知錯誤 |
|---|---:|---:|---:|---|
| formula a | 37 | 28.57% | 90.91% | 1/2（50%） |
| formula c | 35 | 30% | 30% | 7/25（28%）；另4 metadata不充當正確 |
| code a | 8 | 25% | 100% | 無verified，錯誤率NA |

precision／recall只在訊號可用、人審標籤可判的單位計算；UNKNOWN不當成錯誤或正確。code的100% recall只是此8個可評中的2個阻擋，不是原21個中的全部6個。formula a的verified覆蓋2/50、已知錯誤1/2；其描述性精確95%CI為1.26%–98.74%，不能當部署錯率。a與c都通過仍包含同一SICA阻擋：少數必要識別字／金額符號改字被長字串高一致掩蓋。語法成功也未排除7個已確認改義。

c明確分raw TeX可支援語法、MathML序列化與實際Chrome渲染；沒有TeX compiler，不冒稱已通過TeX編譯。過程發現converter未escape裸&的XML表示問題，保留舊helper／首次features，統一修正所有cohort並重新render；原LaTeX在合法alignment環境外的裸&仍判語法false，不因escape成可畫字元而升為語法成功。所有版本與理由均另封，門檻及人工標籤未變。另修正PDFium UTF-16代理對的字元收集：只合併原框內已選的成對indices，BMP字串保持原樣；半對保留未知，不擴框。W3公式50與code21的通過數不變，code全部99來源重評；R1兩筆分數改變，其中E023的a由false轉true。舊collector、features、metrics及圖均保留。

R1保留136筆原評分記錄，與W3的71筆合為207筆來源記錄；各層可能重疊／共用prediction，不合併成整體準度。R1原44群另分formula30／code14，這是同一44筆的子view，不是新增44個獨立樣本。額外34個math義務分為28個文字math及6個image-math；另有28個inline code、1個程序／diff與29個description。43個code-font證據不是43個新的語義標籤，未灌分母。

| R1層／訊號 | 全記錄 | 可評人審單位 | 錯誤警示precision／recall | verified已知錯誤 | verified覆蓋 |
|---|---:|---:|---|---|---|
| 原44群 a | 44 | 11 | 33.33%／75% | 1/2（50%） | 2/44 |
| 其中formula a | 30 | 8 | 16.67%／50% | 1/2（50%） | 2/30 |
| 其中code a | 14 | 3 | 66.67%／100% | 無verified，NA | 0/14 |
| 原44群 formula c | 30 | 9 | NA／0% | 2/9（22.22%） | 9/30 |
| 額外文字math a | 28 | 7 | 0%／NA | 0/4 | 4/28 |
| 額外文字math c | 28 | 28 | NA／NA | 0/28 | 28/28 |

R1新增的a誤驗例E023保留原嚴格F2人審標籤，理由為一般C與書寫體C的符號／字型角色不忠實；這與W3b公式忽略字型指令的文字正規化準則不同，不能把它新增算作已確認Q31核心數學改義。逐筆原理由與限定修正見 [signals/report.md](signals/report.md)。

上述額外28個文字math**全是原人審正例**，沒有錯例，故0/28不能證明能分辨對錯，AUROC與錯誤recall均NA。另6個image-math、28個inline code及1個程序項目缺相容原生區域／可取重建，不可評，均未偽裝成低錯率；掃描來源未開原PDF補做OCR。29個description沒有能當語義真值的literal原生字層，a不適用；c也不適用。不能把描述像不像圖中文字當成描述正確性。

跨重建器b沒有任何可證相同來源區域的配對：相同論文仍在不同原頁／區域，不用末式號或輸出相似度硬配。**b的precision／recall／誤驗率為NA**。完整primary（formula a&b&c、code a&b）因此verified=0、覆蓋率0、誤驗率NA，不是0%錯。a&c省略b的規則仍把W3公式SICA阻擋標為verified（2個中1錯）。本輪沒有證據支持把這三個訊號的組合當可靠認證。

各層完整混淆矩陣、pass-as-correct precision／recall、缺訊號及未知label數、固定門檻敏感度在 [signals/metrics.json](signals/metrics.json)；原始cohort與已知限制見 [signals/report.md](signals/report.md)，138項獨立檢查全部通過，見 [signals/independent-qa.json](signals/independent-qa.json)。[ROC圖（PDF）](signals/figures/roc-by-cohort.pdf) 與 [固定門檻敏感度圖](signals/figures/a-threshold-sensitivity.png) 使用所有觀測門檻，未據此選新門檻。purposive抽樣、同paper／同prediction相關性限制，均不做部署機率校準。 字元一致度的error-positive AUROC：W3 formula 0.717（n=37）、W3 code 0.833（n=8），R1原formula子view 0.125（n=8）、code 0.500（n=3）；語法訊號W3 formula為0.510（n=35）。小分母、不同人審準則與可評覆蓋不同，不能以單一較好的AUC推薦verified或反轉方向挑門檻。

## 6. #84 建議與界線

| 類別 | 建議方法與交付 | 限制／下一步 |
|---|---|---|
| Table | 沿用TableFormer，交付能保留span的JSON／HTML與每格標籤關係；套用#81三規則mapper | cell matching=False列官方候選，不直接改Profile：已證3表修好，但8個原UNKNOWN成為確認FAIL。逐張按Q13，未知不能稱通過；先裁清新確認阻擋與行列邊界。 |
| Formula | 模型重建與原生orig、原頁／crop、來源ref分別保存；模型內容標unverified | 不再擴CPU CodeFormulaV2；raw orig可回退文字但不能當忠實LaTeX或2D數學。非空模型錯字不以orig聯集掩蓋。需其他已qualification的enrichment路徑才啟用，不能以本輪文字高相似放行。 |
| Code／algorithm | 原生字層＋x縮排是born-digital的優先候選，與模型結果分列；已知算子改寫不可覆寫原生佐證 | 這是本輪研究原型，不是已驗所有family的官方功能；正式mapper是否採用交使用者裁定。官方do_code_enrichment=False可作保守候選，但E0本身仍有換行／縮排攤平，不能聲稱已解Q33。 |
| Image description／chart | 維持A/C live run的模型重建與獨立視覺評分範圍，附來源圖片與unverified標記 | 原生字層或語法訊號不是圖意真值；本輪未做新VLM／chart數值重建，不以本輪NA宣稱描述可靠。 |

不確定標記宜交付**可稽核訊號及其適用範圍**，而非未校準的百分比：來源PDF SHA、原頁、bbox／raw char indices、native/模型兩份內容、重建器與版本、字元／運算子／數字一致度、語法與實際render結果、缺資料或scope不合的理由。`syntax_rendered`、`native_agreement`、`independent_agreement`與`human_adjudicated`必須分開；缺訊號維持unverified，不能當一致。

對currency／必要識別字做更嚴格檢查可列**未驗證的後續候選**，因SICA反例顯示少量必要字元改變仍可高相似；本回合沒有把它們加進詞表後重報較好成績。若要驗b，下一輪須先登錄相同區域的雙重建器配對及完整來源身分，再用既定規則評，不以不同頁或局部末式號充數。這些建議未執行。

W2最終正文設定不變：PyPdfium、Heron、separators=True、bookmark-only。正式Profile的影像需求與group5記憶體處理沿用W2決策；研究時影像關閉不構成正式交付設定。Q13失敗、Q31改義、已確認Q33變動仍是阻擋，不因帶不確定標記而自動通過Canonical Acceptance；無完整答案／範圍的項目維持UNKNOWN。

執行與交接索引見 [results-index.json](results-index.json)；最終SHA與交叉檢查見 [completion-manifest.json](completion-manifest.json)、[completion-checks.json](completion-checks.json)。本輪只新增表格cell matching消融推論，未新增E1、API或模型下載；完成後停止。
