# 第一版 PDF core：Docling 能力對照與驗證計畫

[Research index](README.md) · [需求決策 #84](https://github.com/davidlinnnn/data-ingestion/issues/84) · [負載與資源 #54](https://github.com/davidlinnnn/data-ingestion/issues/54)

日期：2026-10-14（Asia/Taipei）。**需求基線已由使用者於 Q53 確認；本文件是官方能力／既有證據對照及擬議驗證計畫。候選模型、方法與配置尚待實測選定。** Q54 保留原 pilot，另定高頻 ingest 目標。這次工作未執行模型推論、部署或負載測試。

**G1後續交付**：[首批來源案例與預期結果](docling-pdf-core-g1-source-cases-2026-10-14.md) 已固定57個具體紀錄及五張完整表格分母，並建立明標受控／衍生fixture。下方V01–V19仍是案例群定義；哪些已綁定、哪些仍缺例，以後續case索引及其範圍為準，不把首批來源資料交付當作模型或整個G1全面通過。

## 1. 評估結論與版本邊界

建議以既有 standard PDF 流程及 checkpoint 為比較起點，逐階段補齊 OCR、圖像理解、公式與程式碼等已選功能。章節層級恢復、行內內容對齊、表格比較關係、Canonical Markdown／補充結構的同版交付，是必須獨立驗證的接點。**官方功能存在、選定 pipeline 能產生、adapter 能完整保留、來源核對品質通過，是不同層次的證據。**

- **既有比較基線**：已發佈 profile 的 Docling `2.102.0`／Core `2.96.0`；保留其原始 native、序列化、checkpoint、資源及回歸證據的適用範圍。[Published profile][baseline-profile]、[既有能力 source audit](docling-capabilities-vs-pdf-core-2026-10-02.md)。
- **已知升版候選**：`2.132.0` 是前次調查已核對的 tagged source，可比較 heading 等差異；這裡不稱它為目前最新版本，也未選定升版。所需 Core、模型與依賴須由相容 lock／image 固定，不能把新 SDK 與舊 Core 任意拼接。[Tagged options][new-options]、[tagged packaging][new-packaging]。
- **滾動文件**：本日核對官方 Usage／模型卡；能力若只有 moving docs 證據，須在選定版本查證 stage、engine、prompt 及輸出，不視為 pinned release 已有。既有完整閱讀範圍見 [2026-10-13 Usage 調查](docling-usage-pdf-core-delivery-2026-10-13.md)。
- **公司模型條件**：Qwen3 VLM＋OpenAI-compatible API 是候選之一；其他適用地端開源 VLM 一起評估。Docling 原生／專用小模型由 agent 建議。確切 checkpoint、GPU／serving 配置及新高頻量化目標仍未知，依使用者已表示的後補安排取得；不阻止文件與案例規劃。

## 2. 需求 → 官方能力 → 必要整合

`原生／配置` 表示官方有對應組件；`自訂整合` 表示需要本案的映射、檢查或處理；`方法候選` 表示必須比較後選定；`延後` 沿用已確認範圍。分類均不表示品質已通過。V 編號對應第 4 節，G 編號對應第 7 節。

| ID／已選功能 | 官方能力與版本證據 | 本案必要配置／整合與證據缺口 | 驗證 |
|---|---|---|---|
| F01 全文文字：必含 | Pinned PDF backend及Core文字／清單／註腳／reference型別。[Backend][pdf-backend]、[text][core-text] | 全文含附錄／bibliography，保留可取得orig及來源。Exporter的labels／layers不得暗中裁掉內容；reading-order merge的orig不保證逐字無損。 | V01、V08 |
| F02 版面／順序／結構：必含 | Standard PDF reading-order及Core父子／內容層／順序refs。[Order][reading-order]、[nodes][core-node] | 沿用既有continuation adapter作有身分的比較方法，核對正文／furniture、清單及跨欄／跨頁。Graph合法不代表順序正確。 | V01、V17 |
| F03 章節層級：必含 | Core有level欄位；pinned缺hierarchy stage，2.132有官方bookmarks／numbering／style恢復。[Heading][heading-stage]、[options][new-options] | 方法候選：組裝後官方stage；補章節parent映射及parsed pages／outline保存。清楚來源不得掛錯層級；模型不會判不是來源歧義。 | V02、V17 |
| F04 表格內容／結構：必含 | Pinned TableFormer及Core cells／spans／header flags／rich refs／caption與notes。[Producer][table-stage]、[data][table-data] | 保留完整必要結構。跨頁邏輯表辨識／串接、重複表頭、每點來源頁與註記scope仍需方法／mapper；cell沒有直接page_no，不由多頁table bbox猜定。 | V03–V05、V15 |
| F05 表格比較語意：必含 | Core提供結構組件；不自動交付method／metric／unit／condition的完整比較關聯。[TableData][table-data] | 自訂用途映射及候選補強；producer／schema／mapper／serializer缺口分開。保留#82 Stage B失敗，raw-only不足以完成。 | V03–V05 |
| F06 頁／圖／表來源影像：必含 | Page／picture images；由page及provenance取得table／picture crop。[Options][pinned-options]、[get_image][core-node] | 固定pixels或生成依賴及custody，核對dpi／座標原點。跨頁逐fragment交付；預設第一個provenance不能代表整表。新目錄實際讀圖。 | V05/V06/V15 |
| F07 原文caption／表說：必含 | Reading-order association及floating item caption／footnote refs。[Order][reading-order]、[node][core-node] | 同版映射與原文位置；保留standalone／確切未知，不以生成描述替代。 | V06、V15/V16 |
| F08 圖內OCR：必含 | 既有獨立RapidOCR component route；官方OCR可配recognizer／dictionary。[OCR][ocr-stage]、[options][pinned-options] | 圖片inventory／工作／outcome對賬；英文／繁中／混排及位置須驗。與頁面OCR分開；圖內結果連同版圖片，與主Markdown正文分開。 | V06/V07、V16 |
| F09 掃描／混合頁OCR：必含 | Pinned OCR engines及full-page配置；原生remote seam是KServe V2。[OCR][ocr-stage]、[KServe][ocr-kserve] | 語言模型組、旋轉校正與座標逆轉換、native/OCR去重及順序待驗；不是只開`do_ocr`。清晰印刷0/90/180/270方向依需求覆蓋。 | V08、V17 |
| F10 圖片分類：可選、偏好啟用 | Pinned classifier及分類meta；chart extraction自動依賴它。[Classifier][classifier-stage]、[依賴][base-pipeline] | 配置與outcome可見；不確定／誤分類不可省略其他必含工作。沒有新增分類準確率門檻。 | V09/V10、V16 |
| F11 圖片理解：必含 | Pinned description本地／API VLM及meta.description。[Description][picture-stage] | 實際資訊圖覆蓋、area／classification filters、crop／prompt／model來源保存；原文caption、OCR與生成解讀分開。 | V06/V09、V15 |
| F12 bar/line/pie數據：必含 | Pinned chart stage本地模型→CSV／TableData；固定main commit有API-engine候選。[Chart][chart-stage]、[API候選][chart-api-candidate] | 分類漏判、parse失敗及精確／估值處置；補axis／unit／condition與source關聯。有效CSV不證明Q27–29的數值或關鍵比較達標。 | V10、V16 |
| F13 全文公式LaTeX：必含 | Pinned formula/code VLM stage可接API，但只處理FORMULA item；官方逐頁VLM另一路。[Stage][code-stage]、[pipeline][vlm-pipeline] | 獨立／多行／矩陣區域重建；行內段落偵測／解析／對齊回填與逐頁法比較。原始證據與重建分開，保留來源精度與未知片段。 | V11/V12、V15–V17 |
| F14 code／偽碼／inline片段：必含 | Pinned code stage選CodeItem，重建文字／語言；共用API seam。[Stage][code-stage] | 需處理普通段落內片段、被當table的偽碼及縮排／註解／符號；方法不由F13自動選定，不以可編譯代替忠實原稿。 | V13、V15–V17 |
| F15 表單／鍵值：延後 | Core有相關容器；容器不證明PDF能可靠辨識。[Core document][core-document] | 不新增抽取；已emitted非空內容依F20保留並明示未解讀。 | V15的保留檢查 |
| F16 指定schema資訊抽取：延後 | Pinned DocumentExtractor是另一處理路徑。[Extractor][extractor] | 不新增指定研究事實／metadata抽取任務；F05/F12仍依各自交付。 | 不新增此功能gate |
| F17 基礎metadata／明確title：必含 | Core origin／TitleItem及metadata容器；不是完整file metadata輸出保證。[Origin][core-origin]、[text][core-text] | Capture／adapter保留已供值與取得來源；正文明確title辨識待驗，不取首個字串冒充。各來源並存、差異明示，其他廣泛metadata抽取延後。 | V14 |
| F18 證據／lineage：必含 | Core refs／provenance／page／bbox／charspan／origin。[Reference][core-reference]、[origin][core-origin] | 映射Source Revision、producer/model/config及同版元件；沿用完整SHA-256與manifest。Core uint64 binary_hash不能代替完整SHA-256；不偽造細粒度定位。 | V05/V15/V17 |
| F19 狀態／診斷：必含 | ConversionResult的status/errors/timings/confidence在document JSON之外。[Result][conversion-result] | Required-work inventory與明確outcome；攜出group診斷，不只assembly聚合。Confidence與正常返回都不等於必要語意完整。 | V16/V17 |
| F20 完整provider保存／mapping：必含 | Core序列化＋Q39的10組合成probe；document JSON非完整ConversionResult。[Core][core-document]、[Q39][q39] | 固定首次完整emitted provider，mapper不覆寫；完整攜出影像／診斷／enrichment及未映射處置，承接custody。必要語意不能只存raw。 | V15/V17 |
| F21 Canonical Markdown：必含 | Core Markdown exporter；預設layer／圖片placeholder與描述輸出須核對。[Serializer][markdown-serializer] | 自訂必要hooks及同版入口；原文caption保留，圖內OCR／描述分開，正文重建回原位；表格可讀表示＋完整必要補充結構。獨立HTML/txt/DocTags export延後。 | V01/V04/V12–V15 |
| F22 core切塊：延後 | Core有chunkers。[Chunkers][chunkers] | 有需要的projection擁有實作；本次不固定core tokenizer／chunk size／overlap。 | 不新增此功能gate |

表格的spans、rich refs與header flags提供表示組件；不能據此宣稱所有表型、跨頁與註記scope已覆蓋，也不能反向宣稱nested content一律不支援。用V04/V05的真實來源驗必要結構與比較關聯，缺哪一層就補哪一層。[Core table types][table-data]、[table item][table-item]。

Q39已有界證據涵蓋已知schema回讀、未知欄位處置／正規化、dangling refs、外部影像搬移／缺檔及embedded影像限制；尚非真實PDF或完整Canonical mapper通過。另有source audit指出既有export未遞迴攜出page_groups、assembly並非完整group diagnostics聚合；列為G3驗證／補做接點，未宣稱已觀察到live資料遺失。[Q39 evidence][q39]、[export source][export-source]、[assembly source][assembly-source]。

## 3. 有界候選比較與選型順序

先固定每個實驗的來源、任務與必要品質，再比較方法／模型，最後才調硬體與併發。每輪只加入能解決具體缺口的候選；同一案例的失敗保留在結果中。

| 任務／候選方法 | 首輪模型／配置建議 | 決定依據與主要缺口 |
|---|---|---|
| OCR：圖片與頁面分開 | 保留既有RapidOCR模型組作比較；針對繁中／混排另核對明確recognizer、dictionary與runtime，必要時比較PP-OCRv5組合 | 專用OCR先驗證文字／位置及語言。Pinned resolver含`en`會選English model-set，但無artifacts/model paths時可回到library defaults，須查actual model／dictionary，不能由`['en','zh-tw']`宣稱混排滿足。`use_cls`也不取代四方向校正。[本輪實測](pdf-core-g2-orientation-2026-10-15.md)4-way CPU與inverse mapping通過控制例，但reading order／glyph／delivery仍缺；兩次line-cls-off僅定位特定漏句。[Pinned OCR][ocr-stage]、[PP-OCRv5][ppocr]、[orientation][orientation] |
| 圖片分類 | `docling-project/DocumentFigureClassifier-v2.5`先作基準；模型卡為EfficientNet-B0／26類／MIT | F10可選且偏好啟用；若用內建chart stage則是其執行依賴。重點驗證分類／filter不得漏掉必含圖片或chart工作，不先增加VLM分類替代。[Classifier card][classifier-card]、[pipeline依賴][base-pipeline] |
| 公式／code區域重建 | `docling-project/CodeFormulaV2`與`ibm-granite/granite-docling-258M`先作專用候選比較 | 前者CDLA-Permissive-2.0，後者Apache-2.0；兩者的inline偵測與段落回填仍須另驗。Granite-Docling中文仍experimental，不將多語宣告當繁中通過證據。[CodeFormula card][codeformula-card]、[Granite-Docling card][granite-docling] |
| 行內公式路徑 | 同一來源比較段落crop VLM＋解析／對齊／回填，以及官方逐頁VlmPipeline | 延續已確認兩路；比較完整段落與公式覆蓋、來源定位、重複／漏字、延遲與資源。官方逐頁路徑以各頁轉換，不把整份PDF塞進單一上下文；若替換主路徑，所有已選功能與checkpoint證據都要重新核對。[Pinned VlmPipeline][vlm-pipeline] |
| 圖意／chart資料 | `ibm-granite/granite-vision-4.1-4b`與公司既有Qwen3系列VLM作任務候選 | 先核對checkpoint／prompt／輸出parser及圖意／數值。Granite Vision卡明示英文指令訓練及其他語言可能降質；Qwen3完整公司型號待補，不推定大小、Thinking/Instruct、授權或顯存。[Granite Vision card][granite-vision]、[Qwen官方repo][qwen] |
| 章節層級 | 先比較官方heading recovery的組裝後接口，減少自寫層級演算法 | `v2.132.0`的`assign_heading_levels(document, parsed_pages, outline)`可獨立評估。numbering-only不能證明style/bookmark案例達標；正式採用仍須相容SDK/Core lock及所需輸入的fresh/restored保存。[Heading stage][heading-stage] |

Heading stage會修改傳入document，應作用於候選／工作副本；已固定provider bytes及已接受Revision保留。官方流程用過outline後會清理暫存狀態，capture時點與restore輸入需明確。此seam便於有界比較，不代表把新版class放入舊Core環境即可運作；`2.132.0`要求Core `>=2.98.0,<3.0.0`。[Heading stage][heading-stage]、[package][new-packaging]。

每項先以必要的兩個候選或既有基準＋一個缺口候選比較；只有具體失敗未解才擴大。依任務需要選模型，不預選所有任務共用Qwen3，也不要求每個小模型都服務化。Granite-Docling不定位為通用圖解描述模型；Granite Vision的chart2code是重新繪圖程式，不是F14要還原的作者原碼。[模型用途][granite-docling]、[chart模型卡][granite-vision]。

Pinned圖片描述的`granite_vision` preset指向3.3-2B；4.1-4B雖有pinned chart本地路徑，用於F11仍須設定相符model spec及producer。只覆寫API的`params.model`可能留下舊spec的producer名稱，須核對實際checkpoint與交付身份。[Preset][stage-specs]、[producer來源][picture-stage]。

重要版本差異：pinned chart stage為本地模型執行，當日upstream main的固定commit `2104df53e9c49c59db16d2404e54432e4e0ff8dc`才作此輪API-engine候選的source依據；本文件不把main當已發布release。圖片描述、code/formula及逐頁VLM在pinned已有API seam；OCR／classifier的原生remote seam則為KServe V2，不能以OpenAI chat API通用替代。[Pinned chart][chart-stage]、[固定commit chart][chart-api-candidate]、[API factory][vlm-factory]、[OCR KServe][ocr-kserve]。

Pinned圖片描述預設area threshold為0.05，classification filter也可能跳過圖片；chart stage依主分類gate；formula/code依FORMULA／CodeItem gate。G2必須由來源inventory核對這些入口，處理小型資訊圖、漏分類與普通段落內公式／code，不能只驗模型已收到的crop。[Description gate][picture-base]、[chart gate][chart-stage]、[code/formula gate][code-stage]。

傳輸／解析失敗須納入required-work對賬：pinned helper或stage的錯誤分支可能留下空字串、None或更新後空內容，須用mock錯誤／空值／截斷回應檢查外層outcome，不能以無例外或JSON合法宣告完成。保留原始觀察、可取得orig與來源圖，再保存重建結果；多provenance／跨頁不能只取第一個bbox冒稱完整定位。[API request][api-request]、[stage error/update][code-stage]、[crop base][crop-base]。

API 相容性先核對完整 URL、實際 model ID、影像格式／解析度、task prompt、輸出解析、token／timeout 限制及截斷結果。服務可回應不代表各任務可用。vLLM 支援多模態 Chat Completions，但仍需適用模型及 chat template；Transformers 作模型執行基準時，OpenAI-compatible HTTP 服務由部署端提供。[vLLM server][vllm-server]、[multimodal inputs][vllm-multimodal]。

固定實驗身份：來源版本／頁面、Docling／Core／image、模型 revision／授權、engine／serving 版本、prompt／parser、dtype／量化、影像尺度／裁圖、輸入與生成上限、seed／解碼設定（適用時）、batch／concurrency、CPU 配額／threads／RAM 及實際 GPU／顯存。變動任一必要項目，結果標記為不同比較配置；不默默覆寫舊結果。

2026-10-15 使用者確認：本輪一般說明文字中的 `OpenAI`→`OpenAl` 屬輕微字形誤差，不單獨淘汰候選或阻止 G2。保留 literal 比對差異與原始證據，另記實際意思／用途下的嚴重度，不以單字完全一致直接代表 Acceptance。這不是通用 OCR 錯字比例，也未放寬公式、數值、程式碼／精確識別字或其他來源的既定條件；段落錯接、漏句與必要交付缺漏仍需解決。

## 4. 來源案例與預期結果

以下 V 編號是本計畫的案例群，**尚不是已建立或已通過的測試檔案**。既有來源及證據的實際路徑列在第 5 節；執行前綁定具體來源版本、頁碼／區域與預期結果。一份來源可覆蓋多群；同群亦可能需要多個來源，避免把單一例子外推成全面支援。

| 案例群 | 覆蓋需求 | 固定來源／預期結果與通過條件 |
|---|---|---|
| V01 全文、順序與清單 | F01/F02 | 取正文、多欄、註腳、bibliography、附錄及跨頁延續，逐段標記必要文字、從屬及順序；無遺漏、重複、錯接或否定／條件／單位改義。正文與 furniture 分開。 |
| V02 章節層級 | F03 | 分別有 bookmarks、明確編號、主要依 style、附錄及確有來源歧義的來源；核對 depth／parent／順序／未知範圍。fresh／restored 必須保留推斷所需輸入並得到同範圍結果。 |
| V03 一般表格 | F04/F05 | 固定 cell、標頭、單位、註解及 model/method/metric/value/condition 對應；來源應有驗收資料點全部正確。 |
| V04 複雜表格 | F04/F05/F21 | 各覆蓋多層／合併表頭、多組子表或條件、單格多值；依來源預先分類。每張邏輯表錯誤率 ≤5%，關鍵比較必須正確；同時核對 Markdown 與補充結構能表示必要意思。保留 #82 Stage B 的已知失敗。 |
| V05 跨頁表格 | F04/F05/F18 | 固定續表、重複標頭、各筆來源頁及關鍵比較；驗收視為同一邏輯表，不重複生資料點，不遺失頁面來源。 |
| V06 圖片覆蓋與原文圖說 | F06/F07 | 從 PDF 原稿建立來源圖片／表格清單，核對裁切、頁碼、caption 原文與指向。包含小圖、split/merge 邊界及確有 caption 歧義的來源；不能只核對已 emitted 數量。 |
| V07 圖內 OCR | F08 | 英文、繁中、混排及無文字圖片；固定文字、順序／位置與所屬圖片。文字保真依 Q4/Q47；無文字與 OCR 失敗可區分。未建立 CER 通過門檻。 |
| V08 頁面 OCR／旋轉 | F09/F01/F02 | 清晰英文／繁中／混排、native/scan 混合頁，來源方向 0/90/180/270；核對校正、文字與原頁座標轉換。模糊／手寫等另作範圍外限制案例，不能混成已可靠辨識。 |
| V09 圖片理解與路由 | F10/F11 | 架構、流程、圖表、資訊截圖／照片及純裝飾；逐圖先固定必要元件／關係／方向／條件／趨勢。必要意思錯漏或無據內容不通過；裝飾描述可不適用並附理由。分類錯誤不得靜默跳過必含工作。 |
| V10 圖表數據 | F12 | 長條、折線、圓餅，含明列值與讀圖估值、對數軸及不同單位／系列；精確值正確，估值依 Q27–Q29 的每點幾何容差及來源標示判定；不漏／多生資料，關鍵比較正確。 |
| V11 獨立／多行／矩陣公式 | F13 | 固定原圖、符號、上下標、分數、矩陣與原稿自有錯誤；LaTeX 允許等義寫法，不修正作者，不漏必要公式。可解析／可 render 僅為輔助檢查。 |
| V12 行內公式與回填 | F13/F01/F02/F21 | 同段文字與行內公式、相鄰公式、跨行／跨欄及附錄；固定文字順序、數學結構和實際來源定位。段落 VLM＋對齊與官方逐頁 VLM 用同一來源，核對文字重複／遺漏與回填。 |
| V13 Code／偽碼／行內片段 | F14 | 固定換行、縮排、註解、變數／字串／運算子與 block；至少包含 `<=`、迴圈從屬及混排行內片段。忠實原稿，不要求偽碼可執行；語言無據可未知。 |
| V14 Metadata／title | F17 | 上游、檔案、正文標題相同／衝突／缺省；正文主標題清楚者須交付，不可靠者留空。分來源保存，不覆寫，檔名僅顯示替代。 |
| V15 交付、證據與可攜性 | F18/F20/F21 | 同一 Canonical Revision 的 Markdown、結構、圖內 OCR／生成描述、圖片／表格引用、首次 provider artifact 與 conversion/group diagnostics；移至新工作目錄實際解關係、讀圖，核對未映射非空內容的明示處置及 custody。 |
| V16 完成／未知／來源歧義 | F19/F18及適用內容 | 分別建立 no-content、not-attempted、unsupported、failed、uncertain 與來源確有歧義案例。必含工作缺失、截斷、無效結構／引用不能 empty success；來源歧義與模型不會辨識分開。 |
| V17 新接點恢復與重用 | F18–F21及變更stage | 新 OCR／VLM／heading 等工作在 fresh、restored、retry、method-change／reuse 的結果與證據；涵蓋 API timeout／斷線、部分完成、結果已持久化後失聯、Pod 替換。只重驗受影響接點，沿用既有有界恢復機制。 |
| V18 Pilot 端到端時效 | 全部必含及必要projection接點 | 原 pilot 文件組成、一般到件／初批、共享依賴與資源條件；從完整上傳並持久受理到 Canonical Acceptance／可搜尋分別量測。語意品質仍同時核對。 |
| V19 高頻持續／尖峰與擴縮 | 全部必含、cloud-native | 先由 #54 固定到件率、burst 時間、文件組成、服務容量及 latency／資源目標，再驗證 queue／backlog、吞吐、尾端延遲、冷啟動／擴縮及共用 GPU；數字未定時只可探索，不判定 SLO 通過。 |

表格計數以來源應有複合資料點為分母；錯值、誤配、漏點與多生點計錯，同筆不重複計數，每張表分開。少於 20 個有效資料點的複雜表不得有錯。來源確有歧義者另列，不計正確也不計錯誤率分母；關鍵比較若仍無法回答則不通過。圖表容差是長條／折線每點在數值軸繪圖長度的 2%（對數軸依對數位置）、圓餅每扇區 ±2 個百分點；原圖明列數字仍須正確。這些數值沿用 [#84 已確認規則](https://github.com/davidlinnnn/data-ingestion/issues/84)，未新增或放寬門檻。

實例紀錄最少包含：來源版本與頁／區域、V/F 編號、必要意思／來源資料點／關鍵比較、預先分類、允許限制、來源核對者與依據、實際產出／錯誤分類／通過與否，以及模型／方法身份。先以表格或既有 manifest 擴充落實，不另建通用驗證平台。oracle 來源由核對過的原稿建立，不能用候選模型自己的輸出當答案；LLM judge 如用於輔助，也不取代必要來源核對。

## 5. 可重用的來源與歷史證據

以下路徑本輪已盤點存在，並閱讀manifest／歷史報告；未重新目視全部PDF、重算digest或重跑測試。`來源存在`、`歷史證據`與`本次待補`分別列出。

| 既有來源／證據 | 可重用範圍與連到的案例 | 本次待補／不可外推 |
|---|---|---|
| 固定20份manifest (`docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json`)及原PDF | 20份檔案均存在；manifest共551頁，`zero_text_pages`皆空。DGM是第16份64頁，已包含於551頁。V01–V06/V09–V14的來源起點及V18原批次 | 有文字層不代表無頁內掃描或解析正確。DGM guard/recovery重用同一來源，不另計第21份；補缺scan／繁中來源亦不悄悄加入原初批20份。 |
| 原功能報告 (`paper-pdf-functional-results-2026-10-11.md`)、第二輪 (`paper-pdf-functional-round2-results-2026-10-11.md`)、五份source review (`paper-pdf-five-rerun-review-2026-10-11.md`) | S1–S3/M1–M3/E1–E2及R04/R06/R12/R13/R20等既有必要意思／條件、數值、公式與code失敗。V01/V06/V10–V13 | 第一輪15份在4GiB sampled guard完成、5份中止，第二輪5份改8GiB；不是同runtime／同資源20份全部通過，更未驗新enrichment。原來源預期可沿用，候選輸出不是gold。 |
| 表格controls (`paper-pdf-table-reconstruction-controls-2026-10-12.md`)、negative controls (`eligibility-negative-controls-2026-10-12.md`) | WikiSkill p8 Table1、Memory-R1 p8 Table2；SEAL p8欄名混接、AgeMem p8 table＋figure混框。V03/V04/V06 | 四個值正確只支持已核對關係；新5%驗收須先固定完整來源分母與分類／關鍵比較。 |
| Wide source review (`paper-pdf-table-reconstruction-wide-source-review-2026-10-12.md`)、V3.1 holdout evaluation (`paper-pdf-table-grouped-v31-holdout-evaluation-2026-10-12.md`) | SkillOpt p8多子表與其他錯欄／合值反例；A-Mem p17、Memento p13、AgentEvolver p25的V31H1–3。V04 | 舊8案32關係及167自動區域不是全量來源表格oracle。V31H曾僅4/12關係preserved，其餘unsupported，須保留作regression；若需獨立holdout另凍結未曝光案例，不能替換失敗成員。 |
| SelfEvoSkill末頁來源review (`paper-pdf-five-rerun-review-2026-10-11.md`)與原PDF | p29 Table13 continued是V05跨頁候選 | 仍需核對起始頁、完整續表／表頭／note及各點來源；末頁觀察不等於整張跨頁表已建立oracle。 |
| DGM content review (`paper-pdf-dgm-durable-q10-content-review-2026-10-11.md`)、F/R/E/X report (`paper-pdf-dgm-durable-q10-results-2026-10-11.md`) | D1–D6，code/diff來源p24/p51/p64及跨頁脈絡；64頁13groups的既有fresh/reuse／中斷恢復場景。V01/V13/V17/V18 | 歷史耗時排除upload/admission/publication；R仍做fresh圖片OCR，不是所有enrichment已重用。不能當新profile端到端通過。 |
| 英語synthetic scan (`docs/prototypes/pdf-checkpoint-prototype/fixtures/scan-pages-3-5.pdf`)、[fixture inventory](../prototypes/pdf-checkpoint-prototype/evidence/fixtures.json) | 原survey的物理頁3與5，144dpi raster-only兩頁；可作V08/V17的page OCR／checkpoint起點 | 是兩頁而非3–5連續三頁；無真實noise/skew。既有restore equality不等於新文字品質oracle。 |
| S2來源manifest (`docs/fixtures/pdf-s2-candidates-2026-09-13/manifest.json`) | 真實繁中掃描：01新北25頁、02臺南30頁；混合文字／影像：03 NCCU手冊7頁、04 NDHU手冊26頁。NCCU p3有既有截圖文字錨點。V06–V09 | 先選清晰頁與完整所選文字／位置／圖意oracle；T06的「我的專區」「最新公告」兩錨點不足以證明Q21/Q47。1912公報可供review為限制候選，不直接當清晰印刷正例。 |
| Region comparison (`paper-pdf-region-comparison-2026-10-11.md`)、code geometry comparison (`paper-pdf-code-geometry-comparison-2026-10-11.md`) | 已有公式crop、SEAL／Trace2Skill算法及code符號／縮排差異的來源觀察。V11–V13 | 保留公式／code既有改義失敗，補行內／多行／矩陣及附錄範圍；不要求不同等義LaTeX字串相同。 |
| [Q39固定spike][q39] | 十組無模型provider回讀／缺圖／未知欄位／診斷邊界。V15/V16 | 真實mapper與新增欄位fresh/restored、完整group diagnostics及custody仍待驗；固定歷史輸出不覆寫。 |
| [T06 prepare entry](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/tests/pdf_processing/t06/prepare_fixtures.py)、[T04 result contract](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/tests/pdf_processing/t04/test_result_contract.py)、[T03 checked-store entry](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/tests/pdf_processing/t03/verify_store.py) | 來源衍生／必要工作負例／保存驗證的可重用入口。V15–V17 | 部分舊`/tmp`衍生檔不存在，但原PDF與prior oracle仍有；以新owned輸出重建、核對page map與原身分。真runtime scripts可能連服務／推論，執行前核對配置及副作用，不用`--help`推定安全dry run。 |

**優先綁定**：V03先用Memory-R1 p8 Table2一般表；V04先用SkillOpt p8及既有V31H三例；V05核對SelfEvoSkill Table13完整頁段；V07先review NCCU p3圖文，V08先review英語兩頁scan及S2 01/02的清晰繁中頁；V13保留DGM p24/p51/p64。V02層級、V09各類資訊圖／裝飾、V10各圖型與log-axis、V11/V12矩陣／行內等仍需逐頁選例。這些是來源短名單，不是已凍結全部預期結果。

受控旋轉0/90/180/270、native/scan混合衍生fixture、pie／log-axis及metadata衝突控制已於[G1](docling-pdf-core-g1-source-cases-2026-10-14.md)具名生成／凍結，保留來源／衍生關係與預期；不能取代真實holdout。頁面來源review先行，不能看模型做錯後才改複雜分類或排除資料點。

## 6. GPU、latency 與 cloud-native 驗證

Docling 的 CUDA 選項及 OCR backend 支援需核對實際 device／provider；worker accelerator 與遠端 VLM 服務 GPU 分開配置。原生 PDF 讀取、render/crop、assembly／映射／交付時間亦需計入；不將官方示例 batch 或吞吐數字當本案配置。[官方 GPU guide][gpu]、[pinned device fallback][accelerator]、[VLM engine factory][vlm-factory]。

| 比較 | 固定條件 | 觀察／判定 |
|---|---|---|
| CPU worker vs GPU worker | 同來源／已通過任務適配的 VLM／prompt／品質、API服務與解碼設定 | 區分 layout/OCR/table 的收益、CPU/RAM/GPU峰值與總成本；Qwen3 可作其中一個服務候選，沒有綁定。 |
| VLM候選／專用模型 | 同任務及來源預期；記錄各自必要task prompt與輸出parser | 先通過必要語意；比較可取得的單次／每文件成本、API request與token數、延遲、吞吐及整合負擔。不同精度／解析度不得冒稱同配置。 |
| Transformers參考 vs vLLM serving | 適用且實際可用時，同checkpoint／精度、影像、輸出限制與負載 | 服務容量、排隊、失敗、cold/warm與cache狀態；不預設runtime勝者，不為矩陣重建所有服務。 |
| 串行／有界併發／batch | 同品質合格配置，逐次變一項 | 完成吞吐、queue age／backlog變化、端到端延遲、OOM／timeout與資源。必要品質不隨提高併發而失守；文件到件率與API併發分別記錄。 |
| Kubernetes生命週期／共享服務 | 選定Pod資源與實際共享模型容量 | 權重預備／載入、冷啟動、擴縮與Pod替換、有界恢復、限流／背壓對已受理工作的影響；已有權威狀態／durable work依 #31/#33 承接。 |

時間以完整上傳並持久受理為端到端起點，另記 admission queue、render、本機推論、API round trip、組裝／映射、完整候選檢查／接受及 Retrieval 發布。服務端可觀測時再拆其排隊與推論，避免跨機時鐘直接相減；沒有服務端資料就據實報客戶端 round trip。vLLM 的 waiting/running、queue/inference/request latency 與 token 指標可供對照，但確切名稱依部署版本核對。[vLLM metrics][vllm-metrics]。

持續到件用依固定時程發送的負載，避免只在上一份完成後才送下一份而掩蓋排隊。每次報告請求／文件數、頁數及內容組成、到件時程、實際完成與失敗、觀測窗口／warmup、cache狀態、p50／p95／p99與樣本量、queue峰值與消退時間、各資源峰值；小樣本尾端分位僅為觀察。容量可用於估算下一組配置，但實際高頻達標仍需在已確認目標下量測。

原 pilot 的一般到件是任意10分鐘最多5份、24小時最多10份；每份完整上傳並持久受理後10分鐘內可搜尋，初批20份1小時內全數可搜尋，Wiki另依24小時目標。這些是待驗證目標及其負載條件，並非 parser 單段預算或已測能力；保留其他已確認的文件／依賴及共存條件。[#54](https://github.com/davidlinnnn/data-ingestion/issues/54)。新高頻量化目標仍待本票owner確認，不能套用原pilot結果外推。

SDK 接入既有 worker 是建議比較起點。Docling-serve 的 Local/RQ/KFP/Ray 是其他執行選項；其部署頁明載同步自serve v1.21.0，部分示例有node-local task state，故採serve也需選版及核對持久性。現階段不因cloud-native就另加一套queue或serve層；如實測／整合顯示需要，再比較其接管範圍與既有恢復契約。[官方 deployment][deployment]、[#31](https://github.com/davidlinnnn/data-ingestion/issues/31)、[#33](https://github.com/davidlinnnn/data-ingestion/issues/33)。

## 7. 執行順序與驗證 gates

| Gate | 工作與最低退出條件 | 目前狀態 |
|---|---|---|
| G0 需求與source audit | Q53確認；F01–F22對應能力／版本／整合責任；未知與歷史證據清楚分開 | 需求已確認；本文件完成第一輪對照，不代表所有接口已實測 |
| G1 固定來源與oracle | V01–V16各綁具體來源／頁、預期意思、關鍵比較及狀態；補足缺口；先保留全部既有失敗。可平行做無模型mapping／交付契約檢查 | 首批57個source／controlled／negative／load紀錄已交付，見G1後續報告；仍有明列真實來源／獨立holdout缺口，未宣告全面閉合 |
| G2 任務適配與小範圍spike | 對已固定案例驗證OCR、heading、formula/code、圖片理解／chart與table mapper；按任務核對API語法／截斷／錯誤、來源與語意；淘汰不符合必要能力者並保留結果 | 已有[首輪CPU](pdf-core-g2-local-cpu-2026-10-14.md)、[第二輪](pdf-core-g2-round2-2026-10-14.md)、[第三輪](pdf-core-g2-round3-2026-10-14.md)、[四案例API](pdf-core-g2-api-2026-10-14.md)、[圖片／chart](pdf-core-g2-images-2026-10-14.md)、[heading](pdf-core-g2-heading-2026-10-15.md)、[orientation／混合OCR](pdf-core-g2-orientation-2026-10-15.md)、[inline／回填CPU](pdf-core-g2-inline-2026-10-15.md)、[較強VLM inline API](pdf-core-g2-inline-api-2026-10-15.md)與[boundary/context修正](pdf-core-g2-inline-boundary-2026-10-15.md)。API段落E14／E13保住6／11處LaTeX與prose；六組新context使3公式及7行code改善，SEAL模型下標／漏字仍拒絕，另驗native-only邊界修正；17筆shadow回歸錯擋E14／E04，token guard不採通用。結構回填及原生fallback均非完整F13／語義通過。既有order／glyph／heading／delivery缺口保留；[防overfitting評估已固定](pdf-core-g2-eval-freeze-2026-10-15.md)：六份新論文僅custody，保留既有回歸，限制開發配置及一次配對holdout；標註／方法lock待補。[通用context第1組](pdf-core-g2-context-candidate-2026-10-15.md)已盤點1,594個native item並準備36組新輸入；17筆舊輸出重放保住四個正例的結構適用性，但五項scope仍拒絕、無新模型品質證據，未選定holdout challenger。[第1組36筆新API](pdf-core-g2-context-api-2026-10-15.md)完成：25pass／5minor／6material，34筆結構回填，四個原bounded正例保留；typed／語義與五項未執行scope仍有缺口，不選holdout challenger。其他完整來源、正式接點及公司驗證待補，G2未全面通過 |
| G3 完整交付與恢復 | 合格候選接到同版Canonical候選；V15–V17覆蓋Markdown＋補充內容、provider custody／diagnostics、fresh/restored及retry；required-work barrier與runtime checks可實行 | 待G2及具體mapper／handoff設計，不新增每份文件人工批准 |
| G4 品質＋資源＋負載 | 以合格功能配置跑固定corpus／回歸及V18；在#54高頻數字和環境落實後跑V19；品質與相應時效／資源共同通過 | 待服務／GPU／環境及高頻目標；這些未知只阻擋相依實驗 |
| G5 Profile與buildable handoff | 依結果選定版本化方法、模型、設定、必要工作／runtime rules及適用範圍；列出仍有限制及證據，更新#80–#83／相關owner | 尚未選定正式profile；若目標有衝突，帶實測差距回使用者決策 |

這是有依賴關係的驗證順序；G1無模型工作與G2已有來源的任務研究可並行。不得以整批通過平均分掩蓋某個必含功能或關鍵比較失敗；方法改動只重驗受影響內容及接點，但改主轉換路徑／套件依賴時須重新判斷所有證據適用性。

## 8. 每次 ingest 的自動檢查與證據界線

1. 依固定Processing Profile列出適用必要工作及其outcome；no-content、不支援、未執行、失敗、不確定分開。必含未完成不得宣告完整處理成功。
2. 檢查必要輸出、結構與同版關係、Markdown入口到補充內容的可發現性、來源／producer身份、artifact固定參照及既有digest／custody。實際讀取影像／交付依賴，不能只驗JSON能parse。
3. 由規則明示已知限制及確切未知範圍；保留可取得confidence／conversion及group診斷。模型低信心不是來源歧義，也不能由confidence或stage success推定語意正確。
4. 普通Canonical Acceptance依明確可觀測規則自動執行；與Processing Completion、各projection publication分開。已發現必要條件或證據錯誤不得放行；不新增通用LLM judge或每份文件人工修正／核准。
5. 固定來源案例提供方案資格證據；runtime檢查無法保證每份新文件的全部語意均正確。事後發現必要條件原未滿足，依既有失效／停止合格選用及歷史保留契約處理。[#84](https://github.com/davidlinnnn/data-ingestion/issues/84)、[#58普通接受決定](https://github.com/davidlinnnn/data-ingestion/issues/58#issuecomment-5761731359)、[#32事後缺陷處置](https://github.com/davidlinnnn/data-ingestion/issues/32#issuecomment-6035318528)。

## 9. 未定輸入、owner與下一步

| 輸入／工作 | Owner／承接位置 | 影響 |
|---|---|---|
| 公司Qwen3確切model ID／版本／服務能力、GPU型號／張數／VRAM及可用容量 | 使用者依已表示安排後補；agent核對task／授權／接口 | 阻擋該候選的實際品質／GPU／容量結論；不阻擋其他官方能力與來源規劃 |
| 高頻持續／尖峰到件、文件組成、latency與資源目標 | #54；使用者決策、agent整理容量建議 | 阻擋高頻SLO驗收；保留原pilot及探索性比較 |
| V案例綁定與缺少的來源／oracle、適用package/model/engine身份 | 本研究後續執行，#84/#72/#83 | 先補最小真實案例與來源核對，再任務spike；不要求使用者回答可由現有檔案查明的事實 |
| 核心功能、Canonical mapper、表格品質gate、整體驗證 | #80／#81／#82／#83 | 本文提供規劃輸入；方法選定與buildable spec形成後同步有效實作範圍，保留#72歷史及#82 Stage B |
| Canonical欄位／讀取契約及物理保存、API／狀態與容量控制 | #32/#55/#57及#31/#33 | 沿用各owner；本文件不預選DB、public API欄位、component reference語法或新persistence framework |

目前持續進行 **G2 任務與接口適配比較**；逐輪結果見上表，heading、orientation／混合OCR及inline兩路於2026-10-15完成所列有界範圍，保留失敗與未解接點。[分組／回歸／評分已固定](pdf-core-g2-eval-freeze-2026-10-15.md)，六份新論文僅完成custody；第1組一般context候選已完成source planning與舊輸出結構回歸；[36筆新request已完成來源／交付／成本核對](pdf-core-g2-context-api-2026-10-15.md)，第1組不選為完整候選；接續將typed／角色、scope及模型保真分層，登記第2組單一改善假設並沿用原回歸，再固定合格候選／獨立source-only標註，之後才執行一次配對holdout，並補其他完整案例、已觀察的order／glyph／heading／delivery缺口，同時補足G1明列的真實來源缺口。實際模型執行依可用環境落實。功能完成與最終profile不能僅憑本研究宣告。

## 10. 本次交付與未做事項

完成需求與官方能力的第一輪對照、既有來源盤點、案例群、候選比較及gates；保存Q53需求共識。未執行新模型、下載權重、安裝依賴、升版、API推論、負載／故障演練或production變更。現有測試通過紀錄僅沿用其原範圍，未重跑或宣稱新功能已達標。

[baseline-profile]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/profiles/selected-native-v1.json
[new-options]: https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py
[new-packaging]: https://github.com/docling-project/docling/blob/v2.132.0/pyproject.toml
[gpu]: https://docling-project.github.io/docling/usage/gpu/
[accelerator]: https://github.com/docling-project/docling/blob/v2.102.0/docling/utils/accelerator_utils.py
[vlm-factory]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/factory.py
[deployment]: https://docling-project.github.io/docling/usage/api_server/deployment/
[vllm-server]: https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/
[vllm-multimodal]: https://docs.vllm.ai/en/stable/features/multimodal_inputs/
[vllm-metrics]: https://docs.vllm.ai/en/latest/design/metrics/
[ocr-stage]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/ocr/rapid_ocr_model.py
[ocr-kserve]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/ocr/kserve_v2_ocr_model.py
[ppocr]: https://paddlepaddle.github.io/PaddleOCR/v3.0.0/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5.html
[orientation]: https://paddlepaddle.github.io/PaddleOCR/main/version3.x/module_usage/doc_img_orientation_classification.html
[classifier-card]: https://huggingface.co/docling-project/DocumentFigureClassifier-v2.5
[base-pipeline]: https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/base_pipeline.py
[codeformula-card]: https://huggingface.co/docling-project/CodeFormulaV2
[granite-docling]: https://huggingface.co/ibm-granite/granite-docling-258M
[granite-vision]: https://huggingface.co/ibm-granite/granite-vision-4.1-4b
[qwen]: https://github.com/QwenLM/Qwen3-VL
[vlm-pipeline]: https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/vlm_pipeline.py
[heading-stage]: https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/heading_hierarchy/heading_hierarchy_model.py#L553
[chart-stage]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/chart_extraction/granite_vision.py
[chart-api-candidate]: https://github.com/docling-project/docling/blob/2104df53e9c49c59db16d2404e54432e4e0ff8dc/docling/models/stages/chart_extraction/granite_vision.py
[picture-base]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/picture_description_base_model.py
[code-stage]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/code_formula/code_formula_vlm_model.py
[api-request]: https://github.com/docling-project/docling/blob/v2.102.0/docling/utils/api_image_request.py
[crop-base]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/base_model.py
[pdf-backend]: https://github.com/docling-project/docling/blob/v2.102.0/docling/backend/pdf_backend.py
[core-text]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/items/text.py
[reading-order]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/reading_order/readingorder_model.py
[core-node]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/items/node.py
[table-stage]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/table_structure/table_structure_model.py
[table-data]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/items/table/table_data.py
[table-item]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/items/table/table.py
[pinned-options]: https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/pipeline_options.py
[classifier-stage]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/picture_classifier/document_picture_classifier.py
[picture-stage]: https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/picture_description/picture_description_vlm_engine_model.py
[core-document]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/document.py
[extractor]: https://github.com/docling-project/docling/blob/v2.102.0/docling/document_extractor.py
[core-origin]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/common/origin.py
[core-reference]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/types/doc/common/reference.py
[conversion-result]: https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/document.py
[markdown-serializer]: https://github.com/docling-project/docling-core/blob/v2.96.0/docling_core/transforms/serializer/markdown.py
[chunkers]: https://github.com/docling-project/docling-core/tree/v2.96.0/docling_core/transforms/chunker
[q39]: https://github.com/davidlinnnn/data-ingestion/tree/690b42f/docs/prototypes/q39-provider-preservation
[export-source]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/manage.py#L34
[assembly-source]: https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/src/pdf_processing/execution.py#L404
[stage-specs]: https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/stage_model_specs.py#L1402
