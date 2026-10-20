# W3 結構元素準度驗證

狀態：**依預估超時提前停止，交付已完成部分。** E0 全36篇／715頁已評；E1 成功17篇，預登錄抽樣尚有10篇未啟動。這不是全量 E1 或完整 Canonical Acceptance 驗收。

目前證據不支持無條件啟用 CodeFormulaV2 的公式／code enrichment：人工已確證數學改義與演算法邏輯退化。mapper改善已抽取內容的交付，沒有修復這些非空錯字或原生表格關聯。也沒有任何 family 在本輪被證成所有結構元素可靠；下面將已知正向證據、阻擋與未知分開。

## 範圍與讀法

E0 使用 W2 採納的 PyPdfium／Heron／separators=True／bookmark-only，重用36篇715頁保存輸出，沒有新 E0 conversion。E1 加本機 CodeFormulaV2 formula／code enrichment；成本外推約250分鐘，依授權改為讀輸出前已登錄的分層來源清單：232個 formula 環境區塊、78個 literal code 與21個 algorithm。已知來源頁且對應到 eligible native refs 的推論 gate 共211 refs，不能把沒有可定位來源／未被正確偵測的單位當成 E1 已完成。

全域 source-only oracle 在08:26:05 UTC封存，所有 SHA、原始及修正版分析器保留。Adam 沒有真正 LaTeX；無法建立結構 gold。多列公式的區塊口徑不是逐條數學式口徑。表格巨集／複雜表頭及部分來源頁定位不足，使許多表保持 UNKNOWN；不能因沒有確證錯誤就算 PASS。協議、成本、harness 修正及盲化限制見 [method.md](method.md)。

初始兩篇試跑推估全量約250分鐘，故改用預登錄分層樣本。10:00:08 UTC 用22個實際batch重新外推，當時剩餘enrichment需77–89分鐘，超過整個任務剩餘74.95分鐘，且尚未加conversion／報告成本；按指示停止新增conversion，讓活動P08成功保存後停止parent。[budget-stop.json](budget-stop.json) 保存兩種外推與原始batch SHA。已完成211個gate refs中的84個，127未處理；pilot另有1個非樣本code ref，總實際85 refs。未完成來源不補選、不計模型失敗。

RAW 與 MAPPED 分開評。MAPPED 只套 W2 的空 text→orig（標角色不確定）、picture children 原生文字獨立交付、合併儲存格單次交付三條規則。非空但錯誤的 E1 model text 不以 orig 救回。

已確認的公式／code／algorithm／逐表／圖片案例，統一索引在 [blocking-list.md](blocking-list.md)，包含來源ID、頁碼、片段與定位stage的原始證據連結。

按 family 的四類完整條件式計數見 [family-summary.md](family-summary.md)／[family-summary.json](family-summary.json)；此處的偵測分數會附來源可定位分母，不能當未知單位不存在。pilot原清單中仍有模板不確定的類別，未硬塞進8個Set F family。

## 公式：可找到角色，重建忠實性未達可全域採用

387個封存公式block中194個有已知來源頁，187有自動eligible-role對齊候選。另7個候選未匹配經頁圖補核：6其實已有formula角色，1是LaTeX與PDF公式不一致；沒有將7例當真漏。全E0 native共有366個formula item，text全空而orig全非空；RAW出口的遺漏與mapper orig回退的可取回性分開。P16 p25有35個task ID被標formula，為已確認誤偵測下界，不能把其他未匹配item全算FP。

實際E1已處理的57個已知來源公式block，兩出口同為2 canonical exact、38 near、17 error/missing。這是格式正規化分類，不是Q31裁決。字型／空白wrapper移除，必要運算子、索引、數字、貨幣單位保留；分析器v1及v2更正均保留，固定E0 refs不重配。

從55個near/error block按固定hash／分層協議最終抽50，全部對照頁圖及全部可見列：**15確認改義、28核心意義保留、7額外metadata／鄰文污染**。近類不足／錯類不足時依封存規則轉補，最終33 near＋17 error。這是有意從near/error抽出的樣本，不能用15/50估整體模型錯率。全部未編譯輸出TeX，render/syntax仍UNKNOWN；核心保義不等於完整可顯示或完全忠實。

代表阻擋有 LightGCN p5 根號分母改變次方、YOLO p2 `IOU`變`IO`加聯集符號、Attention p7必要維度下標被截字、ImageTransformer p4 query乘數遺失、EfficientNet p3組合算子變張量積，以及SICA p3美元單位變節號。這些定位在E1重建出口；mapper不以orig覆蓋非空錯式。

逐案清單、頁圖、refs與前後片段見 [formula-code/blocking-cases.json](formula-code/blocking-cases.json)、[formula-code/report.md](formula-code/report.md)、[formula-code/audit50-final-selection.json](formula-code/audit50-final-selection.json)。人工50仍是block口徑；431封存rows與910詞法行段不能當910條獨立公式，未完全達成使用者逐條公式分母。

行內數學來源4571 spans中3751是正文候選，其餘含表格／caption／footnote／macro。固定hash的6個正文上下標樣本都已頁圖確認在E0兩出口攤平；樣本類型包含上下標從屬與索引連成平字。**全語料攤平頻率仍UNKNOWN**，不能用來源span數或6/6外推。沿W2 D3歸inline-math／F13，不自動改判F01/F02。

## Code／algorithm：部分程式保義，literal與條件有確證退化

來源literal code78個、algorithm21個；已知來源頁分別70／2，自動eligible-role對齊候選54／0。這是enrichment角色匹配，不能視為其餘內容全漏。實際已處理、可對齊的21個code來源單位自動分類為4 exact、9 near、8 error/missing，RAW與MAPPED同數。

21案人工核對：9保義、6確認Q4忠實交付阻擋、4原source→fixed-ref對齊錯誤、2UNKNOWN。六件阻擋包括印刷log的工具／agent／數值被改寫、必要條件`falls within`變`fails within`、patch目標字串／檔名改變。沒有把log當可執行演算法；runtime effect未執行。3段Python的來源與輸出AST相同且頁圖縮排一致，是本樣本的正向證據，不外推所有程式。

兩個已知algorithm另補核：E0的P04 p22有38/38編號行、SICA p5有5/5動作文字，完整scope仍UNKNOWN。P04本來就有code424/425，是凍結aligner漏配；其425因另一prompt候選而實際進E1，輸出把`Hash(s) ∈ C`改成`= C`、`e ≥ 2`改成`e > 2`並破壞else分支。這是**1件頁圖確認的靜態Q33邏輯退化**，兩出口皆交付錯active文字，與執行測試區分；不因frozen algorithm gate顯示0就隱藏。SICA的list90未被enrichment處理，不能算E1模型失敗。

逐行漏／extra／縮排／literal／operator候選見 [formula-code/code-line-assessment.json](formula-code/code-line-assessment.json)；裁定見 [formula-code/audit/code-review.md](formula-code/audit/code-review.md)、[formula-code/audit/algorithm-role-review.md](formula-code/audit/algorithm-role-review.md)。未定位／未執行項目保留UNKNOWN或時間停止狀態。

## 表格：已完成

來源252表候選：175在評測頁內、3範圍外、74來源定位未知；在175表中，138有唯一來源／native偵測證據，37對齊仍UNKNOWN。只有14表具完整可信的數值資料點分母，不能把所有候選點當作已解析 gold。

逐表套一般表零錯、複雜表≤5%門檻，RAW與MAPPED皆為5 FAIL、244 UNKNOWN、3範圍外；本輪未證成整表PASS。五個 FAIL 分布3篇、5頁，29個確證錯誤 tuple 為下界，不是全量完整錯誤總數。關鍵比較未評。

|文件／來源表／頁|類別|確證錯誤下界／分母|錯率下界|RAW／MAPPED|
|---|---|---|---|---|
|P06 table-015 p27|複雜|17／50|34.0%|FAIL／FAIL|
|P11 table-001 p8|一般|2／6|33.3%|FAIL／FAIL|
|P13 table-001 p8|複雜|6／來源點數上界87|6.9%|FAIL／FAIL|
|P13 table-003 p9|一般|2／8|25.0%|FAIL／FAIL|
|P13 table-005 p26|一般|2／8|25.0%|FAIL／FAIL|

P13 p8 的 Table2 吸收 Figure4 條圖是 layout overlap 抑制造成，與圖片類的一件阻擋相同，不能再加成兩個獨立全域事件。另四表的錯配已存在 native grid，定位在 table structure／cell matching 出口，非 Markdown serializer 首因。

正向補查10張完整來源表：223個 numeric 值與符號／單位及 multiplicity 都保留，8表 numeric 序列保留、2表移位；但行列標籤關係仍不完整，仍為UNKNOWN。沒有按 gold 把單格數列重排成正確多欄。

RAW expanded-grid 有73表、677次同格額外曝光（包括表頭）；MAPPED 同一 cell ref 單次交付。這些曝光不等於677個錯誤來源資料點，mapper 也未修復上述五表的原生關聯錯誤。逐表清單見 [table-status.md](table-status.md)，完整逐點／row／col／header 證據見 [table/E0-results-v2.json](table/E0-results-v2.json)、[table/report.md](table/report.md)、[table/report-v2.md](table/report-v2.md)。

## 圖片：已完成

220個 main figure 來源環境中195在範圍內；144有明確 caption→picture link 候選，29來源頁沒有 picture label（不能等同必要圖片遺失），39各類UNKNOWN，8範圍外。58個 subfigure 中13有對應候選；其餘不能以主圖存在就算每個子圖偵測成功。

222個在範圍內的 caption identity，RAW交付片段204、MAPPED220。這是文字身分片段，不是完整 caption 語義或接圖正確率。mapper不修改 caption parent/link。已確證兩類阻擋：ImageTransformer p5 Figure2 caption 插進正文，P13 p8 Figure4 被 Table2 吞入；兩模式皆未修。

980個在頁面內的 raster object bbox：865完全落在picture框、103部分相交、12不相交；另3個物件在頁外。人工看過的6個部分相交物件全是白邊，未確認必要 raster 像素被裁失；其餘115個疑慮物件未逐一看圖，向量圖也UNKNOWN。不可把bbox包含率當完整crop準度。研究保存JSON的235個picture均無image payload，不能驗收正式F06交付。

引用 W2 R3：235個picture框中172個含至少30個PDF原生非空白字元，分布35篇146頁；這172框也都有至少30個native descendant字元。RAW Markdown只有14框的 substantial child 可找到。mapper另交 picture-native-uncertain 文字，不冒充 C 圖片 supplement。這是文字密集框頻率，非圖意理解準度。

詳見 [image/report.md](image/report.md)、[image/family-summary.csv](image/family-summary.csv)、[image/blocking-cases.json](image/blocking-cases.json)、[image/layout-zero-inference-replay.json](image/layout-zero-inference-replay.json)。

## 耗時、RSS與範圍交叉檢查

|設定|已完成範圍|wall／CPU|RSS|
|---|---|---|---|
|E0重用|36篇715頁；新conversion 0|歷史成功conversion合計904.49秒／3655.24 CPU秒|歷史最大已觀測9.07 GiB|
|E1已保存|17篇成功、85實際refs；另5次前推論harness失敗＋1次中斷|有完整supervision的attempt wall合計3453.14秒；另P08 conversion 50.18秒未含其初始化；已知conversion CPU合計13311.95秒|最大已保存觀測8.47 GiB；P08完整peak未保存，UNKNOWN|
|E1 enrichment本體|完成batch保存結果|3088.00秒 wall／11906.55 CPU秒|與conversion共程序，不虛構每元素獨占RSS|

E0歷史含30篇影像開、6篇關，不是新跑的全36影像關閉benchmark。E1成本含harness失敗，兩個未完整supervised attempt（早期中斷與最後成功P08）有censored欄，完整總成本為下界；wall合計不是任務端到端時間。P08在parent暫停後已完成，手動monitor開始時無活動child，0sample不等於0RSS；最後區間連續守門覆蓋亦UNKNOWN。這個資源證據缺口不隱藏。

參見 [resources.json](resources.json)、[harness-repair.json](harness-repair.json)、[verification.json](verification.json)。所有封存source與樣本SHA、36份E0保存JSON／Markdown身分，以及成功E1的effective options／gate均已交叉檢查；`supported_engines`原型是Set，僅此JSON序列順序不影響設定比較。無API／新模型、未開holdout、未改正式pipeline、未commit／push／GitHub留言。

## 官方選項後續建議

只列建議，未執行：[official-next-options.md](official-next-options.md)。優先是官方 cell matching 單變量，以及把 formula／code enrichment 分開評；維持 W2 選定 backbone，不以自訂逐文件修補掩蓋阻擋。沒有證成某個 family 的全部結構元素符合 Canonical Acceptance。
