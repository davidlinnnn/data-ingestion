# 建議組合下仍存在的已確認阻擋

採 Heron＋原 reading-order separators＋bookmark-only heading；heading 不改正文，以下 26 個來源事件仍保留，分布於 13 篇、35 個確認頁。沒有證實可全域安全解決它們的本輪官方選項組合；不代表官方永無解法。

其中 4 件曾在未採用的官方變體個別修好；其餘 22 件／11 篇／30 頁在本輪未觀察到完整修復。SkillRL 的一個 colspan instance 有局部改善，但同群其他頁仍重複。

| 來源根因事件 | 論文 | 頁 | 本輪官方選項觀察 | 可核對的缺陷 |
| --- | --- | --- | --- | --- |
| P-20-2505.03335v1:furniture_in_body:00035 | P-20-2505.03335v1 | 6 | 本輪未觀察到完整官方選項修復 | The clipped raw8615 glyph survives backend extraction as nativecell183, then orphantext37 and #/texts/232(text='6',orig='6',layer=body,parent=#/body); Markdown exports line405. The distinct raw10983/nativecell237 follows layout page_footer18 into #/texts/233 furniture. This is source-clipped-text/backend extraction plus orphan role contamination, not serializer duplication of one glyph. It is isolated; no additional sentence-order corruption is demonstrated by this candidate. |
| adam-author-merged-into-algorithm1 | F-iclr_adam | 1,2 | 本輪未觀察到完整官方選項修復 | texts/12把p1第二作者及機構直接與p2 Algorithm1 caption串同一text item，且在Introduction與作者註腳後才出現；native/Markdown亦如此，改變作者區與演算法的歸屬。不是作者文字消失，但屬必要對象錯接；fallback複合句同時包含abstract造成oracle邊界不準。 |
| adam-definition101-english-omitted | F-iclr_adam | 12 | 本輪未觀察到完整官方選項修復 | texts/419.text與420.text為空formula，但419.orig仍完整保留Definition10.1及A function...is convex if for all...；Markdown省略這些必要英文與量詞條件，只從texts/421的Also, notice...繼續。屬orig→可用text/materialization/label/export映射損失，非PDF backend抽取不到。這超過inline符號攤平，F01阻擋。 |
| imagetransformer-figure2-breaks-body-sentence | F-icml_imagetransformer | 5 | V2 完整修好，但全域新增 13 件阻擋 | texts/108與Markdown在simpler depen-之後插入Local1DAttention及整段Figure2圖說，正文後續才恢復。此5個caption anchors皆被串進同一正文item，實際切斷語意，不是單純caption label差異。 |
| imagetransformer-table5-breaks-amazon-mechanical-turk | F-icml_imagetransformer | 7 | 本輪未觀察到完整官方選項修復 | texts/142在Amazon Mechanical後直接串Table5 caption及兩個評估句，table後texts/143才續Turk...。native與Markdown均把完整正文句子切斷；兩個caption anchors及其角色告警屬同一實際錯接。 |
| p03-caption-spliced-p14 | P-03-2603.25158v5 | 13,14 | 本輪未觀察到完整官方選項修復 | texts/313把前頁正文from which we直接接Table8 caption，texts/317才續remove every evolving-set problem，caption插斷必要條件。 |
| p03-caption-spliced-p21 | P-03-2603.25158v5 | 20,21 | 本輪未觀察到完整官方選項修復 | texts/454把正文Table14 reports SpreadsheetBench-直接接Table14 caption；texts/457才續Verified Vrf scores，caption插斷正文。 |
| p10-chart-label-contamination-p9 | P-10-2509.25140v2 | 9 | 本輪未觀察到完整官方選項修復 | texts/307反覆插入Experiment Results、Synergy of Memory and TTS圖字，切斷between memory quality，並在後半重複前文數段碎片；orig本身亦污染，非只MD轉義或單一metadata錯誤。 |
| p10-chart-numeric-contamination-p26 | P-10-2509.25140v2 | 26 | 本輪未觀察到完整官方選項修復 | texts/721把圖例、座標數字及其他圖字混入正文，出現number of 47、WebArena44、in44.4等；插入數值改變句子對象／讀序，orig也已污染，並重複多個圖字。 |
| p16-task-ids-formula-role-p25 | P-16-2505.22954v1 | 25 | V2 完整修好，但全域新增 13 件阻擋 | 多個task IDs被標formula、text空，MD只formula-not-decoded placeholder；orig仍保留ID。Initial10至少12754、15930、10880等ID缺可讀交付，Additional50亦大量同型。這是F01必要對象漏交付，pipeline formula role＋#81 orig/active-text映射，不是backend完全沒抽或F13排版。 |
| p20-caption-duplicated-p28 | P-20-2505.03335v1 | 28 | 本輪未觀察到完整官方選項修復 | texts/777與MD把Figure21 caption重複多次，混入截斷句與pppppg等碎片；orig已相同污染。不是只caption標text，也不是合法跨頁延續。 |
| p20-caption-object-contamination-p48 | P-20-2505.03335v1 | 48 | 本輪未觀察到完整官方選項修復 | texts/1720與orig重複混入舊Figure41 SolveAbductionTaskExample／main Figure7文字與頁碼48，切斷實際Sum-Product條件並重複caption；最後anchor句雖找到，所在段落對象與條件已污染。 |
| p20-duplicated-corrupt-body-p6 | P-20-2505.03335v1 | 6 | 本輪未觀察到完整官方選項修復 | texts/203及orig含多份AZR uses code executor...和This setup...，中間混入重複章節標題、缺字碎片及變形符號；必要句被切斷並重複，MD同樣輸出，不是anchor規則單獨誤報。 |
| p20-sudoku-caption-duplicated-p46 | P-20-2505.03335v1 | 46 | 本輪未觀察到完整官方選項修復 | texts/1642與orig先重複Figure40 VibeCheck1:Sudoku標題和截斷ast Sudoku...，再接完整caption；MD重複交付此內容，與原頁單份不同，非純metadata。 |
| p20-table2-caption-spliced-p12 | P-20-2505.03335v1 | 11,12 | 本輪未觀察到完整官方選項修復 | texts/441把p12整個Table2 caption接在p11正文helps之後；caption後才出improve performance。所有caption anchors共用這個真實句子插斷，非純label差異；rows1&2的oracle反斜線亦非此阻擋根因。 |
| resnet-p1-right-before-left | F-cvpr_resnet | 1,2 | 本輪未觀察到完整官方選項修復 | native與Markdown先輸出Figure1及右欄degradation各句，之後才Abstract/Introduction；原左欄have also跨頁接p2 are comparably good，未接p1右欄greatly benefited。各LIS-outside anchor屬同一必要正文錯序/錯接原因。 |
| seal-algorithm1-breaks-onpolicy-sentence | P-17-2506.10943v1 | 4 | 本輪未觀察到完整官方選項修復 | texts/96在self-edits後直接插入Algorithm1 title，並在9行演算法後texts/106才續are sampled from...；Markdown亦把同句切斷。句中文字仍在，但正文被演算法內容串錯，F01/F02阻擋。 |
| sica-figure2-breaks-subagent-sentence | P-07-2504.15228v2 | 4 | 本輪未觀察到完整官方選項修復 | native texts/67中途插入圖字LLM Context Window，之後圖內清單與caption，texts/85才續正文；Markdown同樣打斷必要句子。原詞大多仍在，不是整句完全抽取消失，而是圖文字/float串入正文讀序。 |
| sica-p12-prompt-export-suppression | P-07-2504.15228v2 | 12 | 本輪未觀察到完整官方選項修復 | native pictures/4、pictures/5的texts/255、258–282及其orig仍保留prompt/清單；但Markdown只給image placeholders，必要全文與否定/清單內容不可用。lower-list anchors尾端下一項編號有oracle切句誤差，但去掉該誤差後仍有完整必要文字出口漏失。 |
| sica-p13-initialrequest-problem-order | P-07-2504.15228v2 | 13 | 本輪未觀察到完整官方選項修復 | native texts/299先初始請求引言，texts/300卻提前輸出問題引言，texts/301才把初始請求payload與問題payload放同一code item；Markdown同樣如此。必要文字未全消失，但context與當前problem的引言/對象錯接，兩個source anchors都因真實重排而失配。 |
| skillrl-colspan-markdown-duplicates | P-05-2602.08234v2 | 22,23,24 | 本輪未觀察到完整官方選項修復 | native各為一個table cell（tables/10 cell1、11 cell1/cell13、14 cell9），但Markdown展開colspan時在同一列的兩欄各重複一次完整必要Task/技能說明。非來源真重複，屬文字出口重複，F01阻擋；本案未另外證成正文讀序錯。 |
| wikiskill-table1-breaks-crosspage-sentence | P-01-2608.27454v1 | 7,8 | 本輪未觀察到完整官方選項修復 | texts/139先保留前頁正文至strongest competing，再把Table1 caption全部接入同一text item，表格後才由另一item續method across all models...。native與Markdown均以caption打斷必要正文，不能只作captionlabelmetadata。 |
| yolo-p1-right-before-left | F-cvpr_yolo | 1,2 | 本輪未觀察到完整官方選項修復 | native與Markdown先右欄methods to first generate...與After classification等句，之後才左欄Abstract/Introduction；左欄底region proposal被接到p2 making predictions。各LIS-outside anchor屬必要正文錯序並造成跨頁錯接。 |
| p02-first-author-attribution-order | P-02-2603.02766v1 | 1 | V1 完整修好，但全域新增 3 件阻擋 | baseline texts/2 Noah先於texts/3 Salaheddin，Markdown亦如此，改變首作者歸屬；V1相同refs內容互換恢復原順序。不是名字漏失，但屬必要對象/署名順序錯置，F02阻擋。 |
| incidental-p03-table3-breaks-reporting-clause-p5-p6 | P-03-2603.25158v5 | 5,6 | V2 完整修好，但全域新增 13 件阻擋 | baseline texts162 inserted Table3 caption after We report the; V2 texts164 correctly continues official ANLS, caption174 separate. This is a genuine local fix but not in previously adjudicated23 groups; do not inflate original group repair numerator. |
| incidental-p10-offpage-old-figure-task-object-p10 | P-10-2509.25140v2 | 10 | 本輪未觀察到完整官方選項修復 | texts347/body與MD在Figure6前輸出一個409字元舊圖段，首句另指定找抱怨客服reviewer任務，再接舊標題／策略說明，新增具體任務對象並把舊圖指令當論文正文，改變讀者對案例任務及內容的理解。這是已存在於PDF原字流／backend的頁外內容污染，不是serializer憑空造句；不是空白、字型或合法跨頁延續。 |
