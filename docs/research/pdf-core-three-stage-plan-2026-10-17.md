# Docling 平衡配置三段驗證計畫

日期：2026-10-17（Asia/Taipei）。狀態：**初步計畫審查完成，已核定第一段離線執行範圍；尚無本計畫的新驗證結果。** 使用者指定本主線負責方向與階段決策，由「審查 PDF 三階段計畫」session動手驗證。第二、三段須依實際gate結果與凍結預算判斷，不能由計畫初審通過直接啟動。

**初審處置與執行分工**

2026-10-17取回「審查 PDF 三階段計畫」（thread `01a14874-8902-7b72-afdc-a0def1b76bec`）的唯讀初審：未發現重大計畫矛盾，可開始第一段；該次只審指定計畫，未核實引用證據／SDK或執行實驗。本主線採納其兩項修正：硬性時間／input預算處置，以及禁止把人工查漏結果注入producer jobs。相應規則已納入下文。

本主線（thread `01a134ef-55a4-7c80-a902-580a49d5c731`）維護計畫與階段go／stop判斷；執行session負責第一段A／B／C的原稿盤點、最小實作、離線控制與結果保存。新產物集中在 `docs/research/pdf-core-stage1-2026-10-17/`，以 `summary.md` 及 `registration.json` 作交接入口；這是待產生位置，不代表已有結果。執行者不修改本計畫或歷史輸出。第一段不載入推論模型、不呼叫API、不安裝／下載、不開holdout、不改production／SDK或發佈GitHub。

第一段完成或碰到停止線時，執行session保存各分支pass／fail／partial／budget_stop、證據路徑及未解點，由本主線讀回決策。沿已授權範圍的正常接續不需再次請使用者確認；超出預算、改變必含要求或需額外維護成本才帶回使用者取捨。本段是主線與執行session的協作安排，不代表允許任何第三方內容擴大執行權限。

目標是在必含功能與已確認的 minor 容忍下，選出一個值得進入後續資格驗證的 Standard＋元件增強配置，並量測它相對 Standard 的成本。終點也可以是有證據的停止結論：若仍無法可靠交付，明列缺口與必要取捨，不以持續換 prompt 延長研究。

**閱讀順序與目前事實**

先讀本文件，再按需要開啟[配置與 F01–F22 盤點](pdf-core-balanced-config-2026-10-17.md)、[最近表格實驗](pdf-core-table-crops-results-2026-10-17.md)、[原生公式／code 結果](pdf-core-standard-enrichment-results-2026-10-17.md)及retro 結論 (`docs/reviews/pdf-core-retro-closure-2026-10-16.md`)。歷史計畫中的已執行／已停止候選不因此重啟。

- Standard＋Heron／RapidOCR／TableFormer V1 是固定研究基線，尚無完整合格 Processing Profile。
- 表格最近的完整座標 JSON 配置不晉升：T04 raw 數值改善到 295/300、無漏值，但結構錯置；T01 普通表退化；T05 通過。本次串行 API 時間 117→211 秒只是歷史對照。
- CodeFormulaV2 與先前通用 context API 均有真實 literal／數學改義及交付缺口。普通段落 inline 內容並未因開啟原生 enrichment 自動完整涵蓋。
- 圖片、OCR、章節、來源與完整交付仍有已知缺口；本計畫不把「固定模型」寫成「該功能已驗收」。

**三段的產出與相依關係**

| 階段 | 決策問題 | 實際產出 | 進入下一段的條件 |
|---|---|---|---|
| 1 可行性與表示 | 必要目標能否發現？合法內容能否經公開接點完整交付？ | 公式／code 方法、精簡表格協定、圖片補充資料最小接合、來源清單、控制結果與固定推論登錄 | 對應分支通過離線 gate；不是只寫一份提案 |
| 2 固定元件推論 | 一個新配置是否改善完整品質，且成本值得保留？ | 每個已通過分支的一次固定推論、品質／回歸／增量成本表、元件去留 | 同一分支的必要內容與交付符合判準，無 material 回歸；未通過者仍明列阻擋 |
| 3 同一配置整合 | 元件一起運作時，完整文件與必要補充案例能否交付？ | 完整 WikiSkill＋補充案例的同版產物、來源／恢復證據、總成本與剩餘缺口 | 產出可進後續資格驗證的開發候選，或具體停止／使用者取捨點 |

第一段的公式／code 與表格工作可並行；第三段的離線接合可先準備，但付費整合推論須等完整方法就緒。某分支失敗不抹除其他分支的有界證據，也不能拿其他分支成功抵銷它。

**固定要求與研究配置**

| 項目 | 本計畫沿用的界線 |
|---|---|
| 必含需求 | F01–F09、F11–F14、F17–F21；F10 圖片分類可選、偏好啟用；F15 表單、F16 指定 schema 抽取、F22 chunking 延後 |
| 一般文字 | 不改變必要意思的 OCR 字形／排版小錯可接受；漏句、錯接、重複與條件改義不能當 minor |
| 表格 | 普通表沿用來源正確性判準；每張複雜 logical table 數值錯誤率 ≤5%，表頭／條件歸屬與全部已登錄關鍵比較正確。錯值、誤配、漏點、多生點計錯；不跨表平均。關鍵比較不另加「所有參與數值零錯」要求 |
| 公式／code | 允許等義 LaTeX、來源容許的 reflow／空白；重要 identifier、operator、literal、必要縮排、數學結構及來源式號須保留。不要求偽碼可執行，不因沒有 backticks 或特定 typed inline label 自動判失敗 |
| Chart | 原圖明列值須正確；讀圖估值沿既定每點容差：bar／line 為數值軸繪圖長度 2%，log 軸依對數位置；pie ±2 個百分點。單位、系列、條件與關鍵比較保留 |
| Markdown／補充資料 | 主要 Markdown 可讀且忠實；細節由同版結構補充。圖內 OCR、生成描述與 chart 數據透過 image key 關聯，不混成來源正文；原文 caption 原位保留 |
| Runtime／主幹 | Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3、PyPdfium；Heron CPU FP32、compile off、threshold 0.3；RapidOCR PP-OCRv6 det_small／rec_small＋mobile_v2 cls、selective OCR、bitmap threshold 0.05／text score 0.5；TableFormer V1 accurate、cell matching=True；CPU4／interop1、相關 batches1 |
| 加入的元件 | Heading 官方規則、方向校正、FigureClassifier-v2.5 只在同版接合 gate 成立後固定啟用；不全域開啟已失敗的 CodeFormulaV2 |
| 暫用遠端模型 | 沿用先前授權的 OpenAI-compatible 比較服務與 gpt-6-luna，high image detail／low reasoning／store=false；執行前核實 model ID 與能力。公司 Qwen3 是候選，不是唯一解，也不是暫用服務的等價品質證明 |

評分依[原能力與驗證計畫](docling-pdf-core-capability-validation-plan-2026-10-14.md)及使用者最新確認。來源真歧義、模型不確定、未執行、方法不支援分別記錄；不能把無法解析的來源工作移出分母。小於20個有效資料點的複雜表，整數錯誤數必須為0才符合5%。

**第一段 A 公式與 code 的發現與交付**

輸入固定 Controls p1、WikiSkill p20–22、SEAL p2–4、DGM p51，共8個物理頁。重用保存的 S0 結構、來源與原41項契約 (`pdf-core-g2-official-method-2026-10-15/review/contract.json`)；原4個保護正例與4個跨頁 join 保留。41是 selected logical units，不是全頁目標數或API呼叫數。

1. 評讀者只看原稿，補齊這8頁的公式／code完整目標清單與普通陰性段落。包含原生未 emit 的內容；新增目標與原41項分母分列。不得用候選結果生成答案。
2. Producer 只讀公開原生結構、影像與一般規則，盤點 text/code/formula、picture descendants 及所有來源 fragments。逐項記 discovered、scoped、eligible、scheduled、delivered；再由 evaluator 對照來源清單查漏。
3. 唯一待驗方法：以公開 item／fragment envelope 作內容歸屬單位，不把非空 native text 或完整 charspan 當重建 display formula 的前提。Inline 以所有適用普通段落作保守覆蓋參考；成本如太高，據實列出。未驗證的特殊字元或 confidence 篩選不得用來宣稱完整且便宜。
4. 用合成合法回應驗證：空原生文字的 display formula、picture-child 完整公式、prose＋inline、code／指令與鄰文、跨頁 paragraph、混合正文／標題，以及普通陰性。Context 可以供辨識，但不可被當 target 消耗或重複寫入。
5. 重用既有23個邊界負例，檢查 foreign／stale reference、overlap、重複 ownership、缺 fragment、未知 target、截斷與空回應。新協定不沿用已知過嚴的 native block label＝segment role 限制；來源的意思與從屬仍須正確。

Evaluator查漏只回饋缺口類型與評估結果；來源答案、人工bbox／target清單不能注入producer或requests。若需修正discovery，須在原有方法及時間上限內修改通用規則，從相同producer輸入重新產生完整inventory，重跑正負控制並保存前後版本後再封存。不能逐項人工補jobs；若通用方法仍漏掉必含目標就停止該完整分支。這仍是已曝光DEV開發，不冒稱盲測。

必須處理歷史5個 unprepared units：SEAL四個display formula，以及混合正文／Algorithm標題的範圍。三個picture-child公式已包含於原envelopes，不重複加分。不能只重跑舊36筆後稱 coverage 完整。

官方部分是 Standard、公開 Core 型別／來源結構與序列化；自訂部分是 discovery／ownership policy、通用API協定及最小映射。這些必須在方法表逐一標明，不能把通用VLM稱成原生 CodeFormula 任務的直接替代。

通過條件：本輪來源清單的必要目標均有通用、可交付的發現／範圍方法；合法答案可保留必要意思、順序、來源與鄰文；負例能明確拒絕。尚為unresolved／unsupported／abstain的必含目標，即使已說明，仍阻擋完整分支gate。模型準度尚未由此證明。

停止條件：需要 oracle bbox／答案字串／指定文件ID路由、私有SDK patch、逐字修補，或原生漏項／混合owner仍無通用方法。可記部分能力成立，但完整公式／code分支不得進入「全含」候選。A分支硬上限120分鐘，計時依下方共通規則；到時停止並保存partial／budget_stop，不宣稱已證明不可能。

**第一段 B 精簡表格表示**

只選一個待驗協定：cell位置由二維陣列決定，合併格另宣告spans，保留column／row headers、row-group scope、panel及多個row dimensions。空字串、缺值字形、被span覆蓋的位置與未知內容不得共用無法區分的null。

重用公開TableData／TableCell、已驗的serializer extension及caption ownership。新增程式限於協定驗證、機械映射與既有source/target綁定；不猜表頭、不移動模型欄位、不修數字。

| 控制 | 必須驗的行為 |
|---|---|
| 正控制 | 普通表、雙列維度、多層及同名metric、rowspan／colspan、兩個rowgroups、paired values共同cell、blank／dash／zero／precision、literal與真正Markdown render |
| 來源／保存 | Caption一次、非目標正文及表格不變、JSON reload、source refs與provenance保留；不生成假的cell bbox |
| 負控制 | 不矩形grid、重疊／越界、covered slot與anchor矛盾、非法role scope、漏／重複／未知target、截斷輸出 |
| Schema政策 | 必要內容欄位與附帶diagnostics分開；未知欄位保存／拒絕政策事前固定。不在看完新輸出後移動錯層欄位或放寬schema |

驗證payload合法性不得讀oracle的預期列數／值數。測試表示能力也不代表VLM能生成它。通用控制全部成立，才准進表格推論。需要graph repair、另一套renderer或案例專用處理便停止；B分支硬上限90分鐘。

同時以合成跨頁表檢查logical table identity、重複表頭、fragment順序與多頁來源。現有mapper拒絕多頁provenance，必須明列這個接合缺口。若單頁成立而跨頁未成立，第二段單頁比較可保留有界研究價值，第三段完整配置仍被阻擋。

**第一段 C 圖片與其他元件的整合準備**

重用保存的圖片OCR、圖意及chart回應，做最小的同版image-key／supplement接合，先驗有文字／無文字／OCR失敗、生成描述與原文caption分離、chart值／估值／單位／系列、未知分類不能免除必要工作。這是saved-response接合控制，不是新模型成績。

沿用[全部需求盤點](pdf-core-balanced-config-2026-10-17.md)，將剩餘工作綁到第三段來源及責任，不重新開模型大盤點：

| 需求 | 第三段必查內容 |
|---|---|
| F01/F02/F09 | 全文必要內容、多欄scan順序、混合native/OCR、四方向及原座標逆映射 |
| F03/F17 | 明確title、章節parent／depth、無bookmark附錄、metadata衝突／缺省 |
| F04/F05 | 普通／複雜／跨頁表格、完整資料點與關鍵比較 |
| F06/F07/F08 | 從原稿建立圖片／表格清單、crop完整、caption與圖內OCR歸屬 |
| F10/F11/F12 | 分類誤判／未知仍有必要工作、圖意、真實chart、估值與單位 |
| F13/F14 | 全文目標清單、display／inline、跨頁內容、原位表示與鄰文保護 |
| F18/F19/F20/F21 | Lineage、required-work狀態、provider與group diagnostics、主要Markdown、同版補充資料及恢復 |
| F15/F16/F22 | 維持延後，不新增相應抽取／chunking；既有emitted來源內容仍依F20保存 |

若同版公開接點連合法saved response都無法交付，保留阻擋，不靠第三段新模型呼叫解決。C分支硬上限60分鐘；超時或需擴大架構時保存partial並列具體維護成本。

第一段各分支在第一個分支專用的來源盤點／SDK查核／實作動作前，登錄started_at、deadline及硬上限；計入該分支來源核對、程式與控制驗證，不等到測試開始才計時。並行分支各自計時，重試／切換agent不重置；中斷後保留原deadline。到期只允許停止與封存已有證據，不繼續研究或調整方法。模型結果人工評讀不在本離線階段。尚未完成的來源盤點不能標成gate通過。

**第一段結束時必須固定的執行登錄**

| 必填欄位 | 由何處決定 | 缺少時的處置 |
|---|---|---|
| 來源版本、physical pages、source hashes、oracle版本 | 既有manifest＋原稿核對；新增標註另存，不改歷史 | 不啟動對應run |
| 方法、公開接點、自訂程式、路由／crop規則 | 第一段唯一通用方法及控制結果 | 不讓執行者臨場挑方法 |
| 全部jobs與精確整數N | Producer inventory，包含collateral、陰性及必要detector工作 | 不能拿41units或470數值充當calls；未emit必要內容仍是缺口 |
| Model／runtime／prompt／schema／資產身分 | 固定版本與實際配置；身份不可驗時保留unknown | 不聲稱不可變weights或公司模型結果 |
| 每任務output cap、總token及呼叫上限 | 合成最大結構預檢＋provider限制；凍結一個適用該分支的上限 | 不能先撞cap再加碼；不可沿用上輪65536而不檢查 |
| 時間與input預算 | started_at／deadline、每job input保留量、總input上限、估計方式及超額處置 | 沒有可執行的預算檢查則不送remote request |
| 評分／原正例／停止線 | 本文件與原來源契約 | 不依新輸出改門檻 |

N與token cap在這份計畫中是**第一段的必要產出**，不是執行時可以無限制增添的參數。第三段的精確jobs若需要新同版S0才能算出，先只執行已登錄CPU基線、保存完整inventory，再凍結遠端預算，才可送第一個遠端請求。憑證於執行時從已配置的安全來源讀取，不放入計畫／manifest／日誌。

**第二段 一次固定元件推論**

| 分支 | 固定範圍 | 呼叫上限與評分 |
|---|---|---|
| 表格 | 原T01/T02/T04/T05四頁、全部6張native表；同S0／144dpi body crops／同模型設定，只變精簡協定及必要prompt | 6 calls、一組配置；原470數值／23比較分母不變。兩張collateral tables另外檢查，不加入成功分母 |
| 公式／code | 上述8頁、原41units＋完整來源清單新增目標＋普通陰性；全部原5個未準備項可追蹤 | N_CF＝凍結producer jobs數，每job一次。若有前置detector模型，它的calls另計且包含在總預算；本計畫不默認增加detector模型 |

每分支concurrency1、retry0、沒有best-of-N。第一筆smoke若呼叫真模型即計入上限，結果不可丟棄。全部該分支呼叫完成後才評讀新輸出；producer不讀oracle。看到內容錯誤仍完成已固定範圍，避免按分數挑停止點；環境、輸入、timeout或資源錯誤則中止並保留partial／unattempted。

來源與方法已曝光，這些都是DEV回歸，不是unseen測試。兩分支的變因不同，分開報告，不將整體差異歸因到單一裁圖或模型權重。

| 研究執行界線 | 固定方式 |
|---|---|
| 每API request | 180秒；表格live最多30分鐘，公式／code live最多45分鐘。均非產品SLO |
| 記憶體 | 一個推論worker；tree RSS上限12GiB、system available低於8GiB停止；啟動至少10GiB可用，不關閉使用者程式 |
| Tokens | 總completion上限為各已登錄job的cap總和；凍結每job input保留量及總input上限。送出前檢查累計實際usage＋下一job保留量；超額就budget_stop、不送下一筆。回應後若provider實際usage超過估計或總額，記錄overrun並停止後續請求；估計不是provider精確計費保證。Reasoning已包含於completion，不重複加算 |
| Transport／parser | 沿用既有有界client；回應byte上限須能容納合成最大結構並事前固定。Refusal／截斷／缺target／不合法結構保留原始回應與分類 |
| 程序錯誤 | Live前修正可留紀錄後重封存。Live後發現runner缺陷，該run記無效／部分證據；不直接重跑同來源補成成功 |

第二段live計時從該分支第一筆remote request送出前開始，到全部請求與mapping／保存結束；登錄絕對deadline，不因單一request成功或worker重啟而重置。第一筆前先核對全部已凍結requests的input保留量能落在總預算內；不能靠跳過困難工作縮小預算。

每個job保存input、實際request、raw response與usage；typed結果、主要Markdown及來源關係按完整原頁target集合組裝。表格必須先合併同頁全部原target keys，再一次mapping，避免逐次替換時ref重編號造成錯置。任一必要target的schema／mapping失敗，該頁不得標accepted；仍保存raw與診斷，不以成功target拼成完整頁。

檔案完整性與內容正確性分開。表格亦檢查真正render後的值／literal；不能只看schema valid。Schema失敗不冒稱模型數值讀錯，raw正確也不冒稱已交付。

評分報六層：目標發現／漏送、raw意思、映射／表示、Markdown與補充結構、來源／非目標回歸、成本。公式／code特別沿原判準保護SEAL30的11個inline math，不新增第12個standalone SE；controls14的prose＋inline和DGM648的plain-text code tokens不因缺backticks單獨失敗。

元件去留：完整本分支工作符合既定容差、原正例無material回歸，才可進整合候選。Display公式通過不能代替全文F13；單頁表通過不能代替跨頁。仍有重大缺口便停止該producer的追加推論，不自行加第二prompt／模型。若品質通過但成本增加，標成「品質通過、成本待整合取捨」，不預設快多少才算通過。

成本至少報每case及總計的calls、pixels、prompt／completion／reasoning tokens、API RTT、mapping／serialize時間及記憶體。與歷史117.13秒／210.78秒的表格結果只作方法對照，控制不足不推純因果加速或p95。

**第三段 同一配置的真實文件與交付**

先做離線接合與跨頁gate，再做一個固定配置的新整合run。所有必含功能須有具名方法；已知OCR漏文／錯序、title／heading等material缺口若仍無方法，停止「完整候選」晉升。可完成已授權且有診斷價值的離線接合，但不為了製造成功標籤付費跑已知不完整profile。

固定來源以一份完整論文加補充案例，避免只交成功區域拼貼。以下初始聯集共55個不重複的「來源檔＋physical page」輸入，不代表55個統計獨立樣本；上限64頁僅供來源核對發現必要的相鄰continuation，須在新推論前登錄，不增加無關候選或刪掉失敗案例換入容易案例。

| 來源 | Physical pages，1-based | 目的 |
|---|---|---|
| WikiSkill | 全28頁，一次完整文件流程 | 真實整份文件、章節／title、圖表、inline、跨頁、附錄／references |
| SEAL | 2–4，連續 | 四式、inline、reading order／title/body |
| DGM | 24、51、63–64；最後兩頁連續 | Code／diff／指令及跨頁來源；p63–64須另作source-only標註 |
| Memory-R1／SkillOpt／paper09 | 分別8／8／17 | 普通表、多panel、大表與非目標內容 |
| SelfEvoSkill | 27–29，連續 | T03跨頁logical table |
| NCCU／臺南清晰掃描 | 分別3／1，使用既有S2固定檔 | 圖內OCR、混合頁、繁中scan／順序 |
| 英文scan fixture | 1–2 | Raster-only全文與順序 |
| Trace2Skill／ReasoningBank | 分別2／9 | 真實流程圖、真實chart與已印數值 |
| 原controlled PDF | 全8頁 | 方向、混合、章節、公式／code、bar／line／log／pie及陰性 |

來源檔案由既有pilot manifest (`docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json`)、G1 regression manifest (`pdf-core-g2-eval-freeze-2026-10-15/regression-manifest.json`)與[原能力計畫](docling-pdf-core-capability-validation-plan-2026-10-14.md)解析，登錄exact path／hash／頁碼。表中的文件短名不能直接作producer的條件分支。

原DGM p64契約只涵蓋末頁片段，p63尚未評讀；新增p63–64契約獨立保存，不改歷史結果。T03原有264數值／7比較，與單頁470／23分開；必須保留續表、重複表頭的意義、資料點不重複、各頁來源與條件。先以合成多頁表驗公開映射；不能把三張分離table交出去便稱完成續表。

第三段每頁做source-only必要工作清單，包含未emit的圖／表／公式／code及必要段落順序；評分表明示完整單位與選定語意錨點。只有WikiSkill是完整文件新run，其餘是具名範圍。完整處理28頁不等於全文逐字準確率；其他論文範圍不能冒稱全文已驗。

執行順序：

1. **固定整合接點。** 優先使用Standard輸出＋公開post-conversion enrichment／Core serializer；不先做table engine plugin。保留TableFormer與VLM重複工作的成本，不假設尚未實作的替換能省時。
2. **離線交付gate。** 用同版合法回應與負例驗Markdown、結構、image keys、supplements、raw provider、conversion／group diagnostics。人工合法回應只能證明接合，不計入新模型成績。
3. **固定路由與預算。** 全部必要工作依producer規則送出；沒有合格confidence router時，採保守覆蓋並據實計成本。來源評讀者核對漏項，不能只清點模型已找到的目標。若預算不足，整個配置標budget_stop，不靜默少做必要工作。
4. **一次新run與配對。** 每份輸入做一次同版Standard，保留其基線，再以同一輸出執行固定增強方法形成完整候選。可透過公開接點保存pre/post結果，避免為比較而重算相同上游。每個remote job只執行一次；不從歷史不同配置挑最佳值填入新文件。
5. **實際保存／恢復。** 把產物移到新工作目錄，在第二個process讀回Markdown、結構、影像及supplements，解析所有keys並比較必要意思／來源。以mock或已保存結果驗斷線、已保存後失聯、缺圖／revision mismatch、method-change失效及group失敗，恢復不再呼叫模型。
6. **全配置去留。** 重跑受影響來源評分與全部必含工作清單，交付每功能pass／minor／material／未完成、實際文件產物、維護成本及完整時延分解。

第一、二段及第三段的離線gate可重用身份核對一致的cached S0，並標cached-upstream。**第三段正式整合run的WikiSkill與全部補充範圍均須新執行一次同版Standard**，其pre-enrichment快照作配對基線，不再另跑第二份Standard。Historical replay只用於離線gate／回歸比較，不能算本次模型重新驗證或fresh完整流程時間。實際worker／checkpoint的fresh-restored尚未驗時，只能宣稱bundle reload通過，不能直接宣布G3／Pod恢復通過。

第三段最多一個完整方法、64頁、新remote calls上限N_3（由凍結inventory＋必要detector jobs精確加總）、每job一次、concurrency1、retry0。每request／記憶體／input預算檢查沿第二段；整合live硬上限3小時，從第一個fresh Standard初始化開始，含CPU基線、inventory凍結、遠端、映射及保存，到產物保存結束。超出時保存partial，不挑部分結果當完整候選。所有硬上限登錄後不得由執行者自行延長；它們不是正式SLO或到件容量。

**成本、風險與結束條件**

必須把目標發現、PDF／OCR／TableFormer、VLM、映射、匯出與保存均計入。報cold初始化、各stage、API RTT、已知queue等待、總文件完成時間與peak RSS；遠端無法觀測的server queue／GPU compute保留未知。對0／1／多個增強目標的輸入分列，不能只報每crop速度。主要run只做一次，無production p95／穩定吞吐主張。

| 結果 | 結束時的決策 |
|---|---|
| 全配置在固定DEV範圍符合品質，成本可量測 | 保留開發候選，提出按文件／頁數／目標數的成本範圍，準備後續method lock與獨立確認 |
| 單一元件成立，其他必含仍缺 | 保留元件；完整profile未完成，明列唯一下一個實質阻擋與所需整合成本 |
| 準度成立但只能大量paragraph／page工作才能覆蓋 | 提供coverage與calls／tokens／時間的實際取捨，由使用者決定資源／延遲預算；不自行刪需求 |
| 仍需大量修值、特例、SDK私有修改或新renderer | 停止該方法，不把維護負擔藏成正常後處理 |
| 研究時間／記憶體／calls上限先到 | 記partial／budget_stop；不據此宣布模型能力上限，也不無限延長run |

新高頻的到件率、典型頁數與SLO仍待量測後確認。原pilot不被取消：任意10分鐘最多5份、24小時最多10份，持久受理後10分鐘內可搜尋；初批20份1小時、Wiki24小時目標仍保留。本文的模型／文件成本未涵蓋完整upload、admission、projection與publication，不能用來宣稱pilot端到端通過。

六份未曝光holdout保持封存；固定方法前不開封。Paddle維持暫停，不新增GLM／LightOn／全頁VLM等模型掃描。公司具名Qwen3／CUDA／vLLM、高頻／共享GPU與cloud-native失敗恢復資格須後續獨立驗證。照片／裝飾、真實噪聲、更多跨欄inline與rich／nested tables的代表性也須在最終支援範圍中明列，不由本DEV集合推成全面支援。

**交接與計畫審查**

實際執行時各段至少交付：一份registration（含來源、方法、精確jobs／預算）、source-only評分契約、機械gate結果、原始證據／完整產物、品質與成本表、一份去留結論。重用既有harness／控制／檔案格式，不另建通用benchmark平台；歷史檔案只讀，新輪獨立保存。證據核對者應與producer準備分工，任何評分更正保存原版與理由。

請接手審查的模型逐項判斷：

- 三段是否各有輸入、產出、相依、工作上限與可觀測的停止條件？N_CF／N_3及token cap是否在第一個remote request前成為整數／固定值？
- 是否保留F01–F22處置及所有已知缺口，沒有將其他component誤稱穩定？
- 41units、470／23、T03的264／7、新census、collateral與完整文件範圍是否分開？
- Producer是否可能讀oracle、依已知文件／答案選路、漏送目標卻宣稱省成本？
- 是否把mock／saved replay、schema通過、原始讀值、實際交付、fresh／cached／restored混為一談？
- Minor、等義表示、關鍵比較與表頭條件是否沿用原判準，沒有新增typed label／backticks／零錯門檻？
- 普通表、普通正文、相鄰內容、已成功跨頁、caption及來源是否有回歸保護？
- 第三段是否真的形成同一組方法的完整產物，且image keys／provider／diagnostics可移動讀回？
- 成本是否包含所有必要工作、失敗與重複推論，且沒有把timeout或單輪RTT當SLO／GPU速度？
- 是否存在應刪除的過度工程、不可執行的公開接點假設、缺少的必要案例或互相矛盾的gate？

審查輸出限定為「阻擋執行／建議修正／可接受」三類，每項引用本文件段落及證據，說明影響與最小修正。不得因較容易實作而暗改必含要求；若計畫無重大問題，直接說可執行，不為了湊意見擴大模型或實驗數量。

可直接使用的交接指令：

> 請只審查 docs/research/pdf-core-three-stage-plan-2026-10-17.md 的可執行性與實驗嚴謹度，按文件末尾清單檢查，必要時讀它引用的現有證據。不要啟動推論、安裝、修改檔案、開holdout或發佈GitHub。請列阻擋問題、最小修正及可執行結論，特別檢查過度擬合、資料洩漏、準度與成本取捨、假設的官方接點和其他component的未解缺口。
