# W3b 順序、來源凍結與比較口徑

本回合11:00:36 UTC開始，14:00:36 UTC截止。工作依1→2→3→4→5執行，stage-log.json記錄轉換點；新conversion最晚13:35:36 UTC停止。只寫W3b，沿用36篇715頁，不開holdout，不新增enrichment、API或模型下載。

## 1：HTML source-only

舊論文先ar5iv、新論文先arXiv官方HTML，僅請求原凍結idvN；不靜默換latest。原HTML bytes、URL、HTTP、SHA與生成註解全部保存，HTTP成功不等於答案可信。36份HTML皆可下載，Adam只有PDF-wrapper提示而無結構答案；P04的head title是Introduction，但正文完整論文標題、作者與內容皆在，未誤當section-only。

轉換器自述為LaTeXML oxide：16篇0.7.5、20篇0.7.6；這不是Perl LaTeXML版本號。部分canonical不帶vN，不能從requested URL或SHA自行證成論文內文版本。source-trust.md記錄官方來源、版本與排除規則。

表格依共同caption/float分組為semantic table，多leaf子表合為complex，不能拿各子表分別套ordinary零錯門檻。數值分母按每個numeric component及行／列／表頭關係；±與向量另帶同格component index/role，完整cell value也保留。不把row/header label裡的型號數字當資料點。來源歧義保留UNKNOWN。

source-only v1定位過度依賴完整caption。讀來源時發現BERT Table1因HTMLfootnote導致無法定位，遂在任何評分前保留v1並補v2：原PDF字層caption前20→12→10詞，必須在整PDF唯一頁命中；不看Docling、不降低門檻逐文件塞頁碼。只更動locator與衍生source numeric crosscheck，cells/points/Q13逐值相同。semantic table 246張，183IN_SCOPE／3OUT／60定位UNKNOWN。

固定10表完整headers/value/span及20公式行均先對PDF頁圖核對。公式有1條內容忠實但屬續行，排單條比較，未替換以湊20個完整等式。所有抽查局部沒有已確認必要語義誤轉，不能推論全36篇HTML無錯。全域oracle-freeze.json於11:20:54 UTC封存108檔，之後才讀E0與執行消融。

## 2：表格比較

E0重用W2最終PyPdfium／Heron／separators=True／bookmark-only保存輸出。新變體僅table_structure_options.do_cell_matching=False；研究影像關閉、所有enrichment關閉，其他S0固定。從來源表可定位頁與保存E0 native-table頁取聯集，限原語料頁範圍：34篇175頁84個連續interval。使用原PDF的page_range，沒有另寫切頁PDF或改backend。沒有表頁的Adam／GradientDescent不重跑。

單一worker CPU4，每篇新process、同篇interval逐段執行，零自動重試；共用qualification lock、RSS12GiB與host available4GiB守門。supervisor在正常或中斷的finally都保存資源sample，避免重演W3末篇RSS遺失。原生JSON、Markdown、raw layout、effective options、timings與逐篇supervision均存cell-runs。

表格一般表零錯、complex逐表≤5%，不跨表平均。必要數值+標籤錯配／漏／多生計錯；collapsed cell不能按gold重排後當正確，也不將所有未知點當錯。每表保留確證錯誤下界、未決點與率區間；有未決點不能冒稱PASS，complex下界已>5%可FAIL。關鍵比較未評。RAW/MAPPED分開：沿W2三條JSON-only規則；不修原生tuple關係。

## 3–5：凍結原則

公式只用新逐條HTML答案評已保存E1與E0 orig。先以來源頁與E0固定來源對齊，之後比較E1，不依E1最好相似度重新找答案。continuation／不可拆多式與無法單獨分離的many-to-one保留UNKNOWN。

code重建以原生PDF字元／x座標恢復縮排，與LaTeX來源及已保存E0/E1比較；不執行來源程式。字元／運算子／數值與縮排從屬分開，來源定位錯配不算模型漏行。

不確定訊號門檻在任何W3b訊號計算／R1讀取前寫入signals-preregistration.json：a與b字符一致度至少0.95且operator/number序列完全相同；primary formula verified要求a/b/c皆可用且通過，code要求a/b；缺訊號不verified。另報固定單訊號規則、ROC，禁止依結果挑門檻。render成功只證所用renderer語法／呈現，不能證明保義；描述文字沒有可比原生字層時標NA。

W3的50個人工判定原單位是block，不能把block中一列錯誤擴散成每列／每ref都錯。訊號評估保留原人工單位；若切為逐條，只有能明確歸屬的證據才給line label。R1僅在stage5讀使用者新授權的live-preflight/round5-strict子目錄，不讀其他R1產物。
