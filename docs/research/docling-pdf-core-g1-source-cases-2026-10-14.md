# PDF core G1：首批來源頁面、預期結果與負例

[Research index](README.md) · [能力對照／驗證計畫](docling-pdf-core-capability-validation-plan-2026-10-14.md) · [需求 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

2026-10-14（Asia/Taipei）。**已完成首批 G1 來源資料的固定與目視核對，可供有界 G2 方法比較使用；尚未執行候選模型、Canonical mapper／Acceptance、恢復或負載驗證。** 這不是完整 pilot 或整個 G1 覆蓋均已通過的聲明。來源與條件依 #84 Q53／Q54，沒有縮減必含功能。

## 1. 本輪交付與證據界線

- cases.json (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)：**57 個具體案例**，包含31個既有來源目視案例、13個原創／來源衍生受控案例、11個宣告式契約負例、2個負載情境。每例有F/V對應、輸入／來源、預期意思或資料點、位置／證據及未執行狀態。
- 集中來源表含13份PDF及1份原pilot manifest；使用SHA-256識別固定bytes，影像也附實際hash。20份原pilot PDF的bytes全部與原manifest再次相符，共551頁，DGM64頁仍是其中第16份。
- 受控來源PDF (`docs/fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf`)、生成參數／truth (`docs/fixtures/pdf-core-g1-controls-2026-10-14/truth.json`)、最小生成程式 (`docs/fixtures/pdf-core-g1-controls-2026-10-14/generate.py`)：8頁，補矩陣／無印值圖表、四方向掃描及混合內容。它是明標測試來源，不是論文或公司文件的實測成果。
- 頁面／區域證據 (`evidence/pdf-core-g1-2026-10-14`)：所選完整頁、crop、來源與生成驗證紀錄。個別bbox明示PDF point／影像pixel、原點、物理頁及精度；人工區域框是近似範圍，未新設IoU／CER門檻。
- 資料完整性檢查 (`docs/fixtures/pdf-core-g1-2026-10-14/validation.json`)：57例身分／F-V引用、73個檔案hash（含59個PNG）、五張表分母與30個關鍵比較均一致；受控PDF重新生成後hash一致。這些只驗fixture與oracle內部一致性。

核對者是本次Codex各代理的來源目視與交叉檢查，**未宣稱另有人類完成逐字認證**。文字工具用於定位／轉錄，圖像、表頭、符號、從屬與作用範圍由渲染頁核對。標示source-reviewed/frozen指測試oracle已固定，並非候選結果PASS；57例也不代表57份獨立來源或統計樣本。部分案例故意重用同頁檢查不同接點。

## 2. 可直接使用的來源案例

頁碼一律是PDF物理頁（1-based），印刷頁碼不同時另記於JSON。

| 案例 | 固定來源／頁面 | 預期與核對範圍 |
|---|---|---|
| G1-S01 | WikiSkill `2608.27454v1` p1 | 雙行主標題合成同一title；正文明確title與原檔metadata title分來源保留；日期／作者列／arXiv邊標不混入。 |
| G1-S02 | 同文p4/p5/p7 | 9個選定正文heading的depth／parent／順序。包含3→3.2→3.2.1及4→4.2→4.2.1；Experiments書籤目的頁為6，但可見第4章在物理p7，不可照目的頁錯掛locator。 |
| G1-S03 | 同文p19 | A與B同層，A.1／A.2屬A；Algorithm1不是正文第一章。只對選定heading與內容存在作oracle，不冒稱完整演算法轉錄。 |
| G1-S04 | 同文p15 | AI Disclosure與References及前三個來源引用的順序／作者題名歸屬；頁眉不是新主標題。不新增指定schema參考文獻抽取。 |
| G1-S05 | 同文p4 Figure2 | 三層知識、四步流程、方向及conditional skill update；raw immutable、wiki never reset。原文caption、圖內OCR與生成解讀分開。 |
| G1-S06 | 同文p25所選prompt | 六項規則、第五項續行、literal markup與容器關係；不把來源prompt內`## Rules`提升為論文章節。來源指令是待保留文字。 |
| G1-S07 | NCCU手冊物理p3所選panel | 首頁→我的專區→應用系統、選取／連結指示及B5A標籤的圖意；不編造未顯示的操作結果。 |
| G1-O01 | NCCU p3原嵌入截圖 | 中央選定區域完整5組文字及相對位置，包含繁中指示、重複標題與Latin標籤，不只沿用舊兩詞錨點。 |
| G1-O02 | 臺南掃描來源02 p1 | 清晰抬頭、時間地點等所選區域9組文字、順序與位置。 |
| G1-O03/O04 | 原英語scan fixture物理p1/p2（原文p3/p5） | p1左上兩段16行，p2完整所選Figure1圖說及指向；允許中性斷行正規化，引用範圍與章節對應不可改義。不是整份掃描全文oracle。 |
| G1-O05 | NCCU p3照片crop | 此crop無文字；不能因此推定整張資訊圖無需描述或已確定純裝飾。 |
| G1-E01–E04 | DGM `2505.22954v1` p24/p51/p64 | 偽碼、彩色diff、末頁延續及inline command；保留可見縮排、成員／集合符號、Boolean優先序、diff markers及來源自身限制。不修作者原碼。 |
| G1-E05–E09 | SEAL `2506.10943v1` p4 | inline更新、Eq1巢狀期望、Eq2分段reward與footnote2、Eq3→4多行展開、Algorithm1的inner／outer模型狀態。等義LaTeX可不同字串。 |
| G1-E10 | Trace2Skill `2603.25158v5` p2 Figure2 | 分支trace→analyst→patch→merge；方向、來源分組與必要關係。 |
| G1-E11/E12 | ReasoningBank `2509.25140v2` p9 Figures4/5 | 完整列出30＋12筆印值observations及系列／panel／條件；Figure4的部分相同起點共用印值標籤，不稱有30個獨立標籤。 |
| G1-E13 | SEAL p3→p4 | 一個完整跨頁段落：兩頁各4行、11個inline數學片段，從模型參數定義到更新式；p3/p4各有locator，不能只留primary page3。 |
| G1-E14 | WikiSkill附錄p21 | 完整7行正文、6個inline數學片段；最佳集合、`p<0.05`／`p≥0.05`及sole-top／statistical-tie條件。 |

每個所選區域保留全部已宣告預期內容；未選區域仍屬產品全文處理要求，但不因本輪局部source review就宣稱已逐字核對。完整文字、關係、數值、限制與原圖參照以JSON各case為準。

## 3. 五張完整表格的固定分母

| 案例／來源 | 來源分類先行 | 全表數值分母／額外標記 | 已列定必要關係與例子 |
|---|---|---:|---|
| G1-T01 Memory-R1 p8 Table2 | 一般表：兩方法、三metric | 6 | J-based的J較高；EM-based的F1/B1較高。保留reward設定，不從相鄰圖推定單位或backbone。 |
| G1-T02 SkillOpt p8 Table2 | 複雜：六個子panel及不同超參數條件 | 84 | 同名Setting不跨panel合併；caption中的split／subset及batch含義保留；不能拿下方Table3替換本表數值。 |
| G1-T03 SelfEvoSkill pp27–29 Table13 | 複雜：跨三頁、重複表頭 | 264＋3個明確missing-run符號 | 25＋60＋4＝89列屬同一表，逐點保留頁面來源；「缺run在平均時計0」是原文規則，不把dash改寫成已觀測0。 |
| G1-T04 A-Mem p17 Table6 | 複雜：model／variant／method與多層category→metric | 300 | 30列×10值；不混入Table7的F1/BLEU百分比單位，不因灰底A-MEM就聲稱每項最佳。已曝光舊holdout作regression。 |
| G1-T05 WikiSkill p13 Table4 | 複雜：單格Proposed／Accepted雙值、model與benchmark兩區 | 80 | 20個成對來源cell拆成40個具角色數值，其餘40值另有欄義；不可把`3.1 / 1.6`當分數計算或平均，不跨兩區錯配條件。 |

共734個數值與3個非數值missing標記，**總數僅為inventory，錯誤率逐張邏輯表計算**。一般表六點須全對；複雜表沿用≤5%，依上述分母最多4／13／15／4筆數值錯誤，所有事先關鍵比較仍須正確。每張表另須保留header、condition、note、missing markers及必要結構；數字在場不代表完成。

資料點以來源應有數值及完整歸屬為準，同點多種錯誤只計一次，漏／多生／誤配都計錯；新增輸出不能擴大分母。明確missing-run符號是已知來源狀態，另行必須保留，不拿來增加數值分母，也不誤標成來源不可辨識。這五張表未發現需排除的來源歧義；後續若有例外仍須來源證據，不從低confidence產生。

所選案例已覆蓋Q13的多層／合併表頭、多組子表條件、單cell多值及跨頁續表四類。這不宣稱所有nested／rich cell或所有註記scope均已覆蓋，也不代表任何候選已達上述錯誤率。

## 4. 受控PDF的頁面與oracle

第一、二頁是原創toy內容；其餘是明示來源衍生與混合頁。生成程式／truth不是模型輸出。PDF共8頁，所有頁面已渲染目視；第一次CJK fallback缺字已改為嵌入字型並重新核對，凍結資料只指最終版本。

| 案例 | PDF物理頁 | 輸入與預期 |
|---|---:|---|
| G1-C01 | 1 | `[[1,-2],[3,4]]`矩陣、上下分數、兩分支piecewise及句內superscript；原始結構與LaTeX等義規則明列。 |
| G1-C02 | 1 | `<=`、`+=`、巢狀if／outer else、註解及inline code；保留相等邊界與block，不要求執行。 |
| G1-C03 | 2 A | 長條明列10／20，單位%與類別固定，數字必須精確。 |
| G1-C04 | 2 B | 無印值linear雙系列，6個點及相對方向；標estimated，逐點偏差≤數值軸繪圖長度2%。 |
| G1-C05 | 2 C | log10軸1/10/100，三點在對數空間等距；同2%幾何容差，不能按線性軸解讀。 |
| G1-C06 | 2 D | 無印值pie的25／75兩扇區，估值逐扇區±2個百分點及A/B歸屬。 |
| G1-C07 | 1 | 無numbering／bookmarks的style-only heading控制；正文兩主節、數學子節、註腳。不是實際掃描font恢復已證明。 |
| G1-C08–C11 | 3–6 | 原英語scan整頁影像內容0／90／180／270度；PDF `/Rotate=0`、四頁無文字層，不能只靠rotation metadata假稱校正。預期選定兩段與O03一致，來源位置按各頁轉換。 |
| G1-C12 | 7 | native前後文、NCCU來源截圖／caption及原創繁中英文同句；圖片OCR屬同版圖片補充，native文字不重複。 |
| G1-C13 | 8 | 第7頁的raster-only副本，完整可見選定頁按固定10個block及中英同句核對；沒有native文字層可冒充OCR結果。 |

實際業務文件中的矩陣、pie、log／無印值圖表，以及更廣的混排仍需實例驗證；受控來源只能隔離已知結構／數值／轉換，不取代真實分布品質。四方向也只凍結目前清晰受控來源，不外推模糊、紙張彎曲或手寫。

生成程式只用已安裝的ReportLab／pypdf／PDFium；不下載模型或新增套件。重建需所列來源PNG及本機Arial Unicode字型；字型只以subset嵌入PDF，未把字型檔複製進repo。此為fixture製作條件，不是production worker依賴。生成內建assert檢查頁數、文字層、旋轉metadata、字型glyph覆蓋及固定內容；亦已做重建雜湊與渲染一致性核對。

## 5. 可執行實作前先固定的契約負例

以下N案例已給具體input／expected，但**沒有跑到真正的mapper／Acceptance／服務**。Outcome名稱只是fixture記號，wire enum仍屬既有owner。

| 案例 | 固定差異與應有判定 |
|---|---|
| N01/N02 | 三來源title衝突各自保留；沒有可靠主標題就不猜。 |
| N03/N04 | OCR timeout不是no-text；區分未執行、失敗、完成但無文字，另保留可見文字卻回傳no-text的漏失反例。 |
| N05 | 同名local ref指到不同Canonical Revision時，不能混接補充內容。 |
| N06 | JSON能parse但影像引用失效，交付不完整；搬移後仍須實讀。 |
| N07 | 已知某group失敗，不能只export assembly成功而遺失該診斷。 |
| N08 | mapper不能改首次provider bytes；必要語意不能以raw-only disposition充當已完成。 |
| N09/N10 | lost ACK後保留已持久結果歸屬；method change建立新candidate，不改已接受revision的引用。 |
| N11 | O05 crop無文字、分類unknown，仍不能省略必要圖意或猜成純裝飾；不得編造人物身分／活動。 |

F15/F16/F22延後範圍不新增抽取／切塊必要工作；已有非空provider資料的保存仍依F20與N08/Q39邊界核對。

## 6. V案例群與下一階段的承接

| V群 | 首批具體case | 本次已固定／尚待實作 |
|---|---|---|
| V01/V02 | S01–S04/S06、E07/E13/E14、C07/C13 | 文字／層級／footnote／附錄來源與預期；source-reviewed範圍以各例為準，完整551頁轉錄未做。 |
| V03–V05 | T01–T05 | 五張完整邏輯表及分母／條件／關鍵比較；producer→mapper→Markdown／補充結構仍待測。 |
| V06/V07 | S05/S07、O01/O04/O05、C03/C12/C13 | 圖與caption、OCR、所選資訊圖的來源／位置；不是整20份的完整來源圖片清單。 |
| V08 | O02–O04、C08–C13 | 英語／繁中、四方向、mixed與raster來源；bbox逆轉換及實際OCR待測。 |
| V09/V10 | S05/S07、E10–E12、C03–C06、N11 | 圖意、42筆真實印值observations及13筆受控圖表值；photograph／純裝飾的更廣真實案例仍有缺口。 |
| V11–V13 | E01–E09/E13/E14、C01/C02 | 公式／code及跨頁／附錄inline；尚無真實cross-column inline完整段落oracle。 |
| V14–V17 | S01、C12、N01–N11及各來源定位 | 固定交付／狀態／來源與負例；真正same-revision handoff、custody、fresh/restored與required-work barrier待實作驗證。 |
| V18 | L01＋原20份固定manifest | 原pilot的input及時效起訖；未執行E2E。 |
| V19 | L02 | 保留pilot、另定高頻；arrival／burst／文件組成／資源與latency數字未定，不能判高頻SLO。 |

原pilot一般到件仍為任意10分鐘最多5份、24小時最多10份；每份完整上傳並持久受理到接受且可搜尋≤10分鐘，初批20份≤1小時，Wiki另24小時。這是既定目標及條件，不是本次量測；queue、processing、acceptance與publication分別記錄。L02缺輸入只阻擋高頻資格，不阻擋其餘source／方法研究。

## 7. 尚未閉合的覆蓋與選型工作

1. 真實cross-column inline、來源本身不可辨識／有歧義、更多informational photo／純裝飾、nested/rich cell等仍需具名補充，保持缺口可見；不能把模型失敗改列來源歧義。
2. 既有圖片coverage反例、其他source-reviewed正文回歸及其餘pilot內容仍保留；本首批不替換整20份或#82 Stage B失敗。需要獨立holdout時在調整方法前另凍結，已曝光A-Mem不再稱unseen。
3. #80/#81/#82/#83將案例接到選定方法、Canonical mapping／Markdown、table gate、完整交付及有界恢復。宣告式負例不能代替實際服務的持久性或語意驗收。
4. 下一個有界實驗先用對應case做接口／任務適配，再擴到固定集合；凍結package／model／prompt／engine／設定及輸入。公司Qwen3仍只是VLM候選之一，小模型依任務品質、latency、吞吐與資源評估，未在本輪選定。

本輪實際檢查只有來源／影像bytes、page／bbox／引用、表格分母／比較、JSON結構與受控fixture生成／渲染。未跑Docling新方法、OCR／VLM模型、GPU、API、load／recovery或Canonical Acceptance；沒有新的Processing Profile或品質通過宣告。
