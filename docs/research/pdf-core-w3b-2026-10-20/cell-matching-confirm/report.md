# W3c：cell matching 退化確認

**建議不採用 `do_cell_matching=False` 作為全域F04 Profile，維持官方預設True。** 八張原UNKNOWN→FAIL中，已確認3張baseline語義通過、False新增阻擋；即使另有確認修復，也不能宣稱零退化。沒有重跑conversion、API或模型推論；只讀保存輸出與來源，所有新增產物在本目錄。舊W3b答案、scorer與封存均保留。

## 1. 八張疑似退化逐張裁定

下表兩出口RAW／MAPPED在這8張的判定相同。「率」指False的確證錯率，=為全部數值已裁定，≥僅確證下界，不冒稱完整精確率；未定上界不硬截100%。部分人審只確認足以超標的必要錯誤，因此新下界可能低於原機器估計；這不是輸出改善，也不是把其餘候選判為正確。原機器下界在逐表CSV另外保留。

|論文／原PDF頁／表|Q13|baseline|False|False錯率|是否確認退化／原因|
|---|---|---|---|---|---|
|SBERT p5 Table2|複雜|FAIL|FAIL|≥3/30＝10%|否。baseline已有明確Model→Spearman錯對象，至少2/30＝6.67%；False另有74.92→7492及漏77.03、79.23。|
|YOLO p7 Table3|一般|UNKNOWN|FAIL|≥1/420＝0.2381%|未定。baseline各類數列交錯，無法不重排而唯一對應；False確證漏plant45.3。|
|DeepLab p9 Table3|複雜|UNKNOWN|FAIL|≥13/56＝23.2143%|未定。baseline的Decoder/MS/Flip條件勾選歸屬不明；False遺失或裁掉13個必要mIOU百分比。|
|P04 p7 Table1|複雜|UNKNOWN|FAIL|≥36/688＝5.2326%|未定。baseline多層模型／metric關係及完整分母未定；False有36個必要score/gain小數失真。|
|P04 p8 Table3|一般|UNKNOWN|FAIL|≥1/25＝4%|未定。baseline尾端61.3需回插先前setting，不能猜配；False將72.9混入不應包含它的Slow/meta group。|
|P13 p27 Table7|一般|PASS|FAIL|4/32＝12.5%|**確認退化**。baseline完整32點可按輸出自述header與method邊界直接讀；False重複四個+ST/RL數值。|
|P15 p15 Table5|一般|PASS|FAIL|1/3＝33.3333%|**確認退化**。baseline完整句清楚表達40／56／46 tasks所屬集合；False把56另混入Lite evaluation core。|
|P19 p20 Table2|複雜|PASS|FAIL|5/48＝10.4167%|**確認退化**。baseline每model/setting六值原序完整；False的Zero-shot額外混入16.1、232、255、588、498。|

結論為**3確認退化、1兩版同樣失敗、4無法排除退化**；不是把後4張當零退化。baseline通過的3張合計83個必要資料點已逐一檢查。壓欄本身另記為grid缺陷，不等於數值語義正確；通過只限輸出自己能唯一表達的關係。反之，已有明確typed cell把值指派錯欄時，不許flatten後按來源猜回正解。裁定界線見 [adjudication-method.md](adjudication-method.md)，逐圖、全部原native cells及tuple證據見 [regression-audit/report.md](regression-audit/report.md)、[adjudication.json](regression-audit/adjudication.json)。root另獨立覆核 [P15](root-audit/P15-independent-adjudication.json) 與 [P19](root-audit/P19-independent-adjudication.json)。

P04 Table1另暴露答案分母限制：frozen HTML的344不是完整可見score＋gain component個數。逐頁核對每metric cell最多2個可見數字，以完整分母上界688及36個確證錯誤建立5.2326%下界，已超複雜表5%；不能沿用36/344稱完整精確率。沒有修改原oracle。

## 2. 修復與新增PASS抽查

固定抽樣在看本輪頁圖前登錄：原FAIL→PASS總共只有3張，全部核對，不虛構補足5張；22張MAPPED UNKNOWN→PASS按固定seed/source-ID SHA排序取前5張。沒有換樣。本輪共8表、270個數值、24張實際檢視圖。

|樣本|baseline RAW/MAPPED|False RAW|False MAPPED|結論|
|---|---|---|---|---|
|P11 p8 Table2|FAIL|PASS|PASS|真修復：獨立F1/B1欄的數值錯配消失。|
|P13 p9 Table4|FAIL|PASS|PASS|真修復：TC值3.93不再錯入明確MQ cell。|
|P13 p26 Table6|FAIL|PASS|PASS|真修復：TC值7.21不再錯入明確MQ cell。|
|P15 Table14|PASS|PASS|PASS|baseline已有完整有序O/A/T數值；不是新增語義修復。|
|P19 p21 Table3|PASS|FAIL|PASS|RAW是假PASS／另1張確認退化：BFCL值被掛在pp列；MAPPED同格BFCL身分仍唯一，36值保義。|
|P05 Table3|PASS|PASS|PASS|baseline已有完整有序ALFWorld/WebShop關係；span形狀差異另記。|
|P03 Table9.fig2|UNKNOWN|PASS|PASS|False確實通過；baseline的Runner／metric分組仍無法唯一解讀。|
|P01 Table1|FAIL|PASS|PASS|新增樣本中另1真修復：3個WikiSkill row各有3個metric順序錯，baseline下界9/150＝6%超過5%。|

因此原3張修好均為真；新增5張中，MAPPED的5張通過均屬實，但只有1張確證從失敗修好，3張原本已通過、1張baseline仍未知。RAW有1張評分器假PASS。完整抽樣登錄、每出口逐表判定及所有數值見 [pass-audit/report.md](pass-audit/report.md)、[sample-audit.json](pass-audit/sample-audit.json)。不能把機器UNKNOWN→PASS全部當作修復，也不能把定向樣本推成全量退化率。

## 3. 正文、caption與讀序

只使用保存的34篇、175個原PDF表格頁、84個連續區間；實際調用W2 analyzer v3，另用官方ReadingOrder與bookmark-only做零模型推論重播，以隔離全文／區間上下文差異。

- 保存的PDF parsed-page、raw layout與post-layout各175/175逐值相同，非TableElement的assembled元素亦175/175相同。
- 全文baseline重播34/34精確重現原保存結構，再截成相同84區間保留True table predictions、重播相同官方後處理。
- 同區間控制下，84/84正文raw文字與caption的文字、角色、layer及provenance相同；共同正文／caption讀序175/175相同。W2 v3 anchor覆蓋、重複、LIS與caption指標84/84一致，沒有確認新增正文阻擋。
- 不能稱所有JSON結構逐值相同：83/84區間的全部非table arrays相同，P01 p10–11區間的p11 Table3有7個表內文字item新增、7個picture重新掛入table cell。不是新增獨立正文段落；表格內交付／ownership差異及未評範圍另列。
- 直接拿全文對區間時可見的段落邊界、去連字與45個heading-level差異，由相同頁面區間重播及bookmark-only重播證明為上下文效應，不能歸因cell matching。原差異清單與修正前分類均保留，不隱藏差異。
- 此選項也作用於8個label=document_index、結構型別為TableElement的目錄／附錄目錄。因此「只影響表格」必須指TableElement處理範圍，不能窄稱只影響label=table的資料表。

逐頁差異、反事實重播與來源SHA見 [body-impact/report.md](body-impact/report.md)。沒有重跑conversion，也沒有新增模型推論。

## 4. Q13全量記帳與每張FAIL的錯率

下表範圍是183張IN_SCOPE表。僅16張定向稽核表套用本輪人工裁定，其餘沿用W3b機器判定，**不代表其餘所有FAIL都在本輪重新人審**。另60張來源定位UNKNOWN、3張範圍外照舊；Adam表數不可知。一般表零錯，複雜表每張≤5%，不跨表平均。

|設定／交付|一般 P/F/U|複雜 P/F/U|合計 P/F/U|
|---|---|---|---|
|True RAW|7/5/59|4/7/101|11/12/160|
|True MAPPED|7/5/59|4/7/101|11/12/160|
|False RAW|19/4/48|8/5/99|27/9/147|
|False MAPPED|21/4/46|9/4/99|30/8/145|

全部FAIL表、兩出口及每張錯率／下界在 [q13-summary.md](q13-summary.md)、[fail-tables-final.csv](fail-tables-final.csv)；全183表的原判→人工結果與採用來源在 [per-table-final.csv](per-table-final.csv)。精確率與下界分列；部分FAIL只能確定已超門檻，完整錯率及多生上界未能判定，不拿未評部分填0。

## 5. Profile建議

**不採用False作為全域設定，維持 `do_cell_matching=True`。** MAPPED已確認4張修復，但同時確認3張新增語義阻擋；RAW另外確認P19 Table3退化。這不是修好與弄壞張數相減的問題，也不以多數通過率取代Q13。

固定官方選項False會直接用預測cell bbox向PDF backend擷取文字；框跨鄰列時可重複捕入其他列的數值，框裁窄也會截掉必要小數／百分比。此機制與頁圖觀察一致，定位在table cell content mapping／backend rectangle extraction，而非正文layout或reading-order。pinned官方程式片段及SHA見 [official-cellFalse-branch.json](root-audit/official-cellFalse-branch.json)。

本輪不實作逐表切換、依文件例外或自訂重建。True仍有既知結構與表格資料缺陷，須保留Q13 UNKNOWN與阻擋清單；本輪結論只排除False無條件取代True的資格，不宣稱True已符合全文件Canonical Acceptance。
