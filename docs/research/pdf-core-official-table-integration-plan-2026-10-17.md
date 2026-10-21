# HTML gate後：Docling官方接點與下一輪建議

2026-10-17。已查官方文件／範例、固定Docling2.132／Core2.99 source，並完成一個小型公開API控制；沒有新模型推論、API費用、安裝、論文／圖片／holdout存取或production修改。

後續執行：[完整結果](pdf-core-direct-cell-results-2026-10-17.md)。A通過；B四次固定API完成但整體未通過，故C不啟動。下文保留原計畫，開頭的零推論描述是本計畫撰寫當時的狀態。

**建議走「結構化table JSON → 公開TableData／TableCell → 官方公開table serializer擴充 → 主要Markdown」；表示與live證據成立後，再考慮移入Standard官方table engine plugin。** 這是擴充既有JSON路徑的表達能力，不是新模型，也不是SDK現成的一個remote table旗標。

上輪只否決了已測的「一般HTML row-group匯入＋stock pipe Markdown」配置，並未證明所有HTML方法都不可行。更關鍵的是：row-group推斷錯誤在HTML匯入層，literal問題在共用Markdown輸出層；只換成JSON／OTSL不會自行修好後者。

## 官方實際提供什麼

| 官方接點 | 對本案的用途 | 必須保留的界線 |
|---|---|---|
| `TableData／TableCell`與`add_table／add_table_cell` | 直接承載文字、列欄offset、spans、column_header／row_header／row_section。Standard的TableFormer本來也映射到這些型別 | 要由producer提供正確關係，並驗bounds／overlap；Pydantic合法不等於內容正確 |
| `MarkdownDocSerializer(table_serializer=...)` | 官方明確示範替換表格serialization。可只擴充table輸出，不更換正文serializer、不fork SDK | 擴充仍由專案維護，不能稱完全stock；來源metadata與consumer渲染也要回歸 |
| Table structure engine plugin | 官方factory允許自訂`BaseTableStructureModel`／options，真正替換Standard內的table stage並沿用native assembly | API client、validation、table IDs、來源綁定與失敗傳遞仍要寫，不是現成Qwen3接口 |
| 既有DoclingDocument再enrichment | 官方有post-conversion範例，支持先重用既有文件做有限接合驗證 | 範例沒有代寫完整table reconstruction；成功後再plugin化可避免過早包裝 |

官方依據：[文件模型／公開API](https://docling-project.github.io/docling/reference/docling_document/)、[serialization說明](https://docling-project.github.io/docling/concepts/serialization/)、[實際替換table serializer範例](https://docling-project.github.io/docling/_generated/examples/serialization/)、[table plugin](https://docling-project.github.io/docling/concepts/plugins/)、[既有文件enrichment](https://docling-project.github.io/docling/_generated/examples/enrich_doclingdocument/)。

固定版Source與歷史實驗比較另存三份筆記：[直接typed接合](pdf-core-official-tabledata-integration-notes-2026-10-17.md)、[serializer選項](pdf-core-official-table-serialization-notes-2026-10-17.md)、[OTSL／DocTags／DocLang及plugin](pdf-core-official-table-format-alternatives-2026-10-17.md)。目前線上文件／main可能比固定版新，不將main的rich-cell修正視為Core2.99已具備。

## 此次額外做的小型控制

為確認官方extension不是紙面選項，使用合成TableData明確宣告兩個row sections，並測literal `<s>`、來源本來就是`&lt;s&gt;`的文字、`&`／小於號／pipe、前置零／精度、caption與正文順序。不是修正前輪HTML輸出，也沒有讀來源答案。

公開API探針 (`pdf-core-official-table-integration-2026-10-17/public_serializer_probe.py`)的專案自訂部分只有一個`MarkdownTableSerializer`子類：在render用副本進行通用HTML escaping，再委派stock表格輸出，將SerializationResult的source item保留為原始item。不改canonical cell text／numeric value／flag，沒有來源名稱或case專用分支。實作過程補上source metadata檢查，避免span攜帶render副本而誤認成原始內容；不是模型／prompt調參。

控制結果 (`pdf-core-official-table-integration-2026-10-17/verification.json`)通過：

- 直接typed row-group沒有被併入global column header。
- CommonMark＋table、HTML enabled下，兩種literal／entity文字均正確可見；pipe與`001.20`保留。
- caption一次、正文次序相同；canonical JSON前後byte-identical。
- serializer回傳的source items與原文件items一致；SDK零修改，模型／API呼叫零次。

這只證明**小型public extension可行**。未驗完整spans、多層表頭、rich-cell、全部Markdown syntax、實際論文或完整producer；不是新gate全通過。RichTableCell未作為逃避plain-cell escaping的替代方法。

## 為何不優先換其他格式

- **OTSL／DocTags：** Docling2.132的獨立table OTSL parser保留三種角色，但Core2.99 legacy DocTags parser未設定它們。兩者最後仍受同一stock Markdown escaping限制。Granite OTSL及generic API＋DocTags已有失敗實測，不換名稱再跑。
- **DocLang：** plain cells有較完整角色，但rich-cell分支仍有限制。這輪沒有證據顯示應為它另開模型比較。
- **Markdown內嵌HTML table：** 可以使用官方HTML serializer保留spans／escaping，與HTML backend「匯入」是不同方向；但projection／renderer須能完整消化HTML。它是consumer契約選項，不能默默等同原本純Markdown表格消費。
- **HTML `row_section` dialect：** 官方有此標記，但它不會自動取消全列th被推斷的column_header，亦不修共用escaping。可保留研究，不需要繼續堆HTML修復規則。

官方本來就將內容模型與輸出策略分開，並建議需要合併格資訊的consumer使用JSON／HTML，或替換table serializer。精細spans留在同版typed artifact，主要Markdown仍須保留可讀的值／條件與table key；不承諾GFM pipe table能無損重現PDF視覺版面。

## 下一輪有界計畫

### A：完整表示／serialization gate，最多90分鐘、0模型

固定**一個完整cell contract＋一個通用table serializer extension**，重用前輪合成來源語義：左欄header、雙列維度、多層與同名metric、rowspan／colspan、兩個row groups、成對值共同cell身分、空白／缺值／零與精度、literal的真正render結果。另驗invalid bounds、overlap、span／offset不一致及漏／重複／未知target明確拒絕，不補值、不改輸入。

加入caption／source spans／provenance、正文及非目標table前後回歸、JSON reload、CommonMark消費內容。plain cell是此候選範圍；既有rich-cell必須保留既有行為或明列不支援，不以逐case換type追通過。精細位置只取可證實的native envelope，不生成假的cell bbox。

**停止界線：**一旦需要私有SDK patch、通用graph repair、依案例補header／值、或擴成另一套完整renderer，就停止並列實際成本。這次推薦允許的是官方公開table serializer擴充；相較上一輪禁止自訂renderer的邊界，這是一項明示的新維護取捨，不悄悄沿用成「仍完全stock」。

### B：通過後，回到四頁一次live比較

維持原四頁T01／T02／T04／T05、470個數值綁定、23個critical comparisons，以及普通表零錯、各複雜表≤5%且全部critical comparisons成立；所有同頁native targets包含附帶表格，不擴大分母。最多4次API requests、一組配置、retry0、concurrency1。保留S0／144dpi full-page／同模型及reasoning，僅修改完整table表示／公開serializer。

**輸出預算須重新預檢，不能盲沿用8192。** 完整cell JSON比舊flat rows冗長；先以非來源專用的最大結構合成資料估計回應大小，核對provider限制並凍結一個適用全部頁面的token上限／總預算。若在可接受cap內不具可行性，於送出前停止；不能先截斷再加碼、默默拆表或略過困難cells。此研究報告不是已完成的live registration。

Memory／SkillOpt兩個S0結果可核hash重用；另兩頁須同設定新S0。新頁每次conversion180秒、API每request180秒，整個B階段45分鐘；RSS12GiB、available至少8GiB，失敗不調參重跑。producer只看source／native inventory／contract，全部推論完成後evaluator才讀oracle。既有DEV不能當盲測／泛化證據。

### C：品質成立才移入Standard table plugin

先用mock／既有raw驗plugin的native table IDs、assembly、caption與失敗傳遞，再決定是否把API producer放進Standard table stage，替換原table engine，減少TableFormer後再重建的重複推論。官方提供plugin接點，但本次未實作plugin，不能先聲稱latency改善或cloud-native資格已通過。

跨頁T03、holdout、Paddle、公司具名Qwen3／CUDA／vLLM及高頻測試仍不啟動。表格候選即使通過，也不能抵銷code／inline公式／圖片supplement的獨立必要缺口。
