# PDF core G2：起始 pipeline 與逐任務驗證提案

[Research index](README.md) · [能力與驗證計畫](docling-pdf-core-capability-validation-plan-2026-10-14.md) · [G1 來源案例](docling-pdf-core-g1-source-cases-2026-10-14.md) · [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)

日期：2026-10-14（Asia/Taipei）。**G2 已分批進行本機 CPU 與暫用 API 的任務比較，候選覆蓋仍不完整，未選定正式 profile。** 使用者授權CPU優先，公司補GPU／超出本機資源的驗證，暫用OpenAI官方VLM作比較候選；GPU與負載尚未於這次G2驗證。沿用已確認的必要功能與品質要求，以下逐輪記錄實際完成範圍。

**第二輪執行**：[CPU缺口比較](pdf-core-g2-round2-2026-10-14.md) 已完成3次圖片OCR、2次TableFormerV2、2次CodeFormulaV2及2次無模型order重放。code所選七行正確；現有圖片OCR、V2六panel表、v3 order及所選分段公式仍有明確失敗。CodeFormulaV2已放入獨立快取並驗CPU FP32，並非所有公式／code候選已合格；G2未全面通過。

**第三輪執行**：[繁中recognizer與Granite CPU比較](pdf-core-g2-round3-2026-10-14.md) 完成6次有界推論。PP-OCRv5 mobile／server仍有繁簡錯字；Granite-Docling-258M CPU可跑，改善所選兩段順序與公式第二分支，但公式／註腳、全頁文字保真、全頁及專門OTSL表格仍未合格。另由保存tokens定位官方engine尾端清理缺陷，與模型品質錯誤分開記錄；未改套件或採用新profile。

**暫用 API 執行**：[GPT-6 Luna 四案例比較](pdf-core-g2-api-2026-10-14.md) 已用使用者指定 endpoint／`gpt-6-luna` 完成4次直接HTTP任務。Table2的84個數值綁定及8項關鍵比較正確、caption body／條件保留但漏字面標號；英文所選16行通過；公式分支／註腳標記保留，renderer未驗；OCR漢字／位置正確但改引號。這是暫用候選內容證據，未驗Docling API engine接點、同版回填或公司Qwen3／GPU，G2仍未全面通過。

**圖片與chart執行**：[分類／圖意／chart比較](pdf-core-g2-images-2026-10-14.md) 新跑2個Standard來源頁，分類6來源×2crop共12次CPU、SmolVLM描述2次CPU、API圖意2次與chart4次。DocumentFigureClassifier-v2.5 broad family核對通過；SmolVLM預設描述漏必要意思；API兩張圖意與13個受控chart數值／關係通過，pie百分比字串／unit需adapter。原生chart top-class gate與description的area／filter／空輸出風險另有離線controls。仍待heading、orientation／混排、inline、其他完整表／案例及公司候選；G2未全面通過。

**2026-10-15 heading CPU 執行**：[官方 recovery 比較](pdf-core-g2-heading-2026-10-15.md) 以隔離 slim2.132／Core2.99／parse7.22 stack，對既有完整28頁論文與新跑的控制頁作組裝後 stage replay。論文13/13選定深度與推得父節點正確、錯頁書籤沒有改 locator；移除outline後附錄0/4，無編號控制頁因title仍是section header而六節皆多一層。所有其他stage欄位保留，原生parent仍未重建為章節樹。保留候選，title角色／無書籤附錄／Canonical parent映射仍待解；stage-input fresh／reload等價不等於完整pipeline／recovery資格。G2仍未全面通過，接續尚有orientation／混排、inline、其他完整案例與公司候選。

**2026-10-15 orientation／混合 OCR 執行**：[四方向與混排比較](pdf-core-g2-orientation-2026-10-15.md) 已完成7次原始Standard、4次learned orientation＋OCR、4次normalized Standard及2次same-input line-cls-off OCR。四個corrective angles及來源座標逆轉換正確，normalized頁面各16/16選定行吻合，但Standard仍在兩段之間插入右欄段落；C12 selective保住native，full把OpenAI寫成OpenAl；C12／C13圖內文字仍有繁簡／漏句。關閉行級分類可找回兩個漏句，字形與image-key交付仍缺，不作全面關閉建議。Actual模型／providers明確固定，`lang`標籤不等於實際recognizer；相同dpi也不等於相同render pixels。G2未全面通過，接續inline、其他完整案例及已知缺口／公司候選。

**同日使用者嚴重度澄清**：這個一般說明文字案例的 `OpenAI`→`OpenAl` 為輕微字形誤差，不單獨淘汰方法或阻止 G2。既有 literal mismatch、oracle 與 raw outputs 原樣保留；literal 比對與交付嚴重度分開。此確認不擴大為所有 OCR 字誤、程式碼／識別字、公式符號或數值的通用容許門檻；段落插入、漏句及必要圖片參照交付等缺口仍獨立判斷。下一項依既有計畫進行普通正文／附錄的行內公式與 code 偵測、重建及回填比較。

**行內公式／code CPU 執行**：[完整段落與官方逐頁比較](pdf-core-g2-inline-2026-10-15.md)已完成。28個普通 items 由 producer gate 選11個，另6個 controls；固定 Granite-Docling258M 執行17次 paragraph component probes、5次真正官方 VlmPipeline，全部CPU FP32／EOS／未撞cap。原engine結尾清理缺陷與模型內容錯誤分開；token-aware回填僅9筆結構套用、8筆保留原文，仍有套用段首漏句、inline LaTeX缺漏及模型重複。整頁controls code與獨立公式局部較好，但inline平方攤平；保存兩頁回應重放官方assembly亦未合併SEAL段落。此default配置不採為最終inline方案，G2仍未全面通過；下一個比較沿用相同完整來源及輸出契約評估較強VLM，公司候選與高頻／GPU驗證另行落實。

**較強 VLM 行內比較**：[暫用 gpt-6-luna API](pdf-core-g2-inline-api-2026-10-15.md)完成17段落＋5整頁的same-PNG direct component比較，兩路均非本輪官方API VlmPipeline。段落E14／E13保住6／11處LaTeX與完整prose，362段首亦恢復；整頁E14仍有2處math未重建LaTeX、SEAL有下標誤讀，其他選中段落也有數學錯誤。11筆結構回填不代表語義通過；matrix裁圖不完整、SEAL34混入caption及provider role接點需另解。保留完整段落VLM候選，優先補source crop／item邊界及保真；G2、公司候選、正式整合與高頻效能仍未通過。

**裁圖／item 邊界修正**：[六組新 context 驗證](pdf-core-g2-inline-boundary-2026-10-15.md)已完成來源導出的 parent＋child union、相鄰 code grouping、SEAL空間片段隔離／續句接回與段落＋公式 context 比較。三個公式及七行code保真改善；SEAL32仍錯下標／prime，SEAL34仍漏字，模型正文替換須拒絕。保留原 provider，另驗 working Markdown／補充結構、inline role reuse及 native-only boundary fallback；邊界修正不等於F13／Canonical Acceptance完成。17筆舊輸出shadow回歸顯示token guard錯擋E14／E04，因此不採為通用規則，不調參迎合已知案例。G2仍未全面通過，接續先固定跨來源holdout與回歸範圍，再驗公式候選的來源對齊。

**防止 overfitting 的評估已固定**：[資料分組、回歸與評分 protocol](pdf-core-g2-eval-freeze-2026-10-15.md)保留57個G1 case、17筆paragraph outputs及四個正例錨點；六份新論文只完成custody，未開內容或跑模型。下輪最多三組開發配置，固定一個challenger後才作一次配對holdout；來源標註與方法lock仍待完成，不能將已曝光案例重切成未見資料。下一步先在開發集整理一般候選與回歸，再獨立標註固定頁面。

**第1組通用context候選已執行**：[Source planning與回填回歸](pdf-core-g2-context-candidate-2026-10-15.md)盤點四份既有provider的1,594個item／60個group，產生36組新輸入；17筆舊輸出在原條件下重放，四個已知正例保持結構性適用。SEAL四個公式及一個混合段落仍abstain，段落context未觸發，不因保守拒絕就視為必要能力已完成。無新模型推論、holdout讀取或配置調參；尚未選定challenger，下一步須對新request作開發集推論與來源品質核對。

**第1組36筆新API推論完成**：[來源品質與交付核對](pdf-core-g2-context-api-2026-10-15.md)以固定輸入／prompt／規則單次執行，來源初評25pass／5minor／6material；四項內容／數學錯誤及兩項typed code缺陷保留。34筆可結構性回填仍不是Canonical Acceptance，五個selected來源單位維持未執行。四個舊bounded正例依原判準保留，新舊SE型別註記差異另存；未改gold、調參或重跑。ClientRTT合計193.37秒／median5.03秒；公司效能不可外推。第1組不選holdout challenger，下一步先按來源角色／typed契約、scope與模型保真分層，登記第2組單一改善假設再比較。

## 起點與 default 的用途

建議以 **明確配置的 `StandardPdfPipeline`** 作主比較起點。先取得無新增 enrichment 的 native 對照，再分任務啟用必要 stage；不以裸 `DocumentConverter()` 作需求完成基準，也不先把所有 flag 打開跑整批。官方標準 PDF 預設類別確為 `StandardPdfPipeline`／`DoclingParseDocumentBackend`；明寫類別與序列化設定是為固定實驗身份。[Pinned converter](https://github.com/docling-project/docling/blob/v2.102.0/docling/document_converter.py#L177)

`2.102.0` 的 `PdfPipelineOptions()` 預設 `do_ocr=True`、`do_table_structure=True`，table mode 為 `accurate`、cell matching 為 True；code、formula、picture classification、picture description、chart extraction 均為 False。page／picture images 預設 False，scale 為 1；OCR 預設是 `OcrAutoOptions`，實際選到的 backend 不可省略紀錄。因此可以小樣本跑一次原樣 default，回答「開箱行為是什麼」，但它既沒有包含全部必含功能，也沒有固定本案 OCR 模型組與來源影像交付。[Pinned options](https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/pipeline_options.py#L1493)、[common enrichment defaults](https://github.com/docling-project/docling/blob/v2.102.0/docling/datamodel/pipeline_options.py#L1170)

官方滾動文件亦說明 enrichment 通常增加模型執行與時間，多數預設停用。公式 enrichment 的入口是 label 為 FORMULA 的 TextItem；code 是 CodeItem。**開啟 formula／code flag 不等於已發現及重建普通段落內的行內片段。** [官方 enrichment 說明](https://docling-project.github.io/docling/usage/enrichments/)、[pinned gate](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/code_formula/code_formula_vlm_model.py#L116)

歷史控制組可用固定 commit `fe1b283c49c83ad5aeee6808e77b4f25549eba03` 的 `selected-native-v1.json`：Docling `2.102.0`／Core `2.96.0`、CPU 4 threads、page groups 5、table accurate／cell matching、page／picture images scale 1；native OCR 與全部 enrichment 皆關閉，另有 continuation adapter。這是舊方法身份及回歸證據，不是新版功能的完成配置。該 `selected-native-v1.json` 路徑目前工作目錄不存在，不能當作現況已部署。既有相同方法、相同來源的保存結果可先重用，不為建立報表重跑推論。[歷史 profile](https://github.com/davidlinnnn/data-ingestion/blob/fe1b283c49c83ad5aeee6808e77b4f25549eba03/deploy/pdf-processing/profiles/selected-native-v1.json)、[既有 source audit](docling-capabilities-vs-pdf-core-2026-10-02.md)

## 首輪比較配置

下列是實驗變因設計，不是正式 runtime 配置檔。先固定來源、Docling／Core／依賴 lock、模型 revision、prompt／parser、影像尺度、dtype、device、batch／concurrency 與資源；每次只改要回答的變因。`2.102.0` 是歷史比較點；已核對的 `2.132.0` 是含 heading recovery 的升版候選，不稱為目前最新版本，也不把新版 stage 任意移入舊 Core。[既有版本邊界](docling-pdf-core-capability-validation-plan-2026-10-14.md)

| 順序 | 配置／輸入 | 本輪要回答的問題與保留證據 |
|---|---|---|
| 0：環境與控制組 | 讀取可用 lock／runtime／模型 cache／endpoint 身份；明確 Standard pipeline，native OCR／enrichment 關閉，table accurate／cell matching，page／picture images 開啟並固定尺度；stock reading order 與既有 continuation adapter 分開命名 | 能否重現既有來源輸出？讀取／render／layout／table／assembly 花多少時間？首次完整 provider JSON、可取得的 conversion diagnostics、Markdown、頁圖／crop 與實際 options 都保存。先在小樣本診斷，不宣稱完整內容通過。 |
| 1：OCR 與來源定位 | Standard + 明確 RapidOCR 模型組；圖片 OCR 與頁面 OCR 分開比較。依 G1 的 native／scan／mixed、繁中／英文／混排與四方向案例；有具體缺口再加入 PP-OCRv5／orientation 候選 | 文字、順序、native/OCR 去重、旋轉及原頁座標回轉正確嗎？無文字、失敗、timeout 必須可區分。`do_ocr=True` 或有文字輸出本身不算通過。 |
| 2：公式／code 區域 | Standard + `do_formula_enrichment=True`、`do_code_enrichment=True`；先比較 `CodeFormulaV2` 與 `granite-docling-258M` 的固定區域輸出；formula 與 code 分開評分 | 對已知 crop 的模型能力是否合格？pipeline 能否實際找出及送入全部必要區域？同時保存 oracle crop 與 pipeline crop，區分 detector／gate 漏件和重建錯誤。驗負號、上下標、矩陣／分段、縮排、註解、原始符號與語言。 |
| 3：行內公式／code | 同一來源並列「Standard + 段落 crop VLM + 解析／對齊／回填」與「官方逐頁 `VlmPipeline`」；先用 Granite-Docling，再依可用模型加入公司 Qwen3 VLM 候選 | 比較整段文字與行內片段有無遺漏、重複、改義、位置錯置及耗時。逐頁 VLM 是替代主轉換方法，需另驗表格、圖片、順序、provenance 與輸出結構，不能把公式變好當作整體勝出。[Pinned VLM pipeline](https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/vlm_pipeline.py)、[官方 VLM 說明](https://docling-project.github.io/docling/usage/vision_models/) |
| 4：圖片／chart | classifier `DocumentFigureClassifier-v2.5`；圖意與數值候選 `granite-vision-4.1-4b`、公司 Qwen3 VLM；description／chart 分任務、prompt 與輸出 parser 固定 | 比較來源元件／關係／方向與數值、單位、series／axis／condition。分類或 size filter 不得靜默漏掉必要圖片；chart 開啟會自動依賴 classifier。圖片 OCR、原文 caption、生成描述維持可辨識的同版結果。[Pinned common stages](https://github.com/docling-project/docling/blob/v2.102.0/docling/pipeline/base_pipeline.py#L153) |
| 5：heading／table 接點 | heading 用相容的 `2.132.0` stack 評估官方 recovery；table 重用五張 G1 完整 oracle，先檢查 Standard producer + 既有 mapper，缺口明確後才加 table reconstruction 候選 | heading depth／parent／style／bookmark 是否正確？table 的缺口在哪一層：producer、schema、mapper 或 Markdown？一般表全部正確；複雜表逐張 ≤5% 且關鍵比較正確，跨頁仍算同一邏輯表。 |
| 6：候選組合可行性 | 把個別合格任務合成一個研究候選，用有交互作用的代表文件重跑必要範圍 | 單項改善有無破壞全文、順序、來源、table 或其他 enrichment？必要輸出能否進入同版 Canonical 候選／Markdown + 補充資訊？這是接點可行性，完整 handoff／checkpoint／retry qualification 在 G3。 |

## 每任務模型與設定的比較單位

每個候選固定自己的 package／model revision、engine、prompt、輸出格式／parser、圖像尺度、dtype、batch／concurrency、device 與資源。以下是短名單，不做全部模型乘全部案例；有具體缺口才增加比較。

| 任務 | CPU 起點／可用時先做的比較 | 其他候選與必留設定 |
|---|---|---|
| 版面／閱讀順序 | 已快取 Heron＋stock Standard，保留 raw clusters／bbox；舊 continuation 另命名 | 其他 layout model 或整頁 VLM；不能同時更換 layout／reading-order adapter 後把改善全歸給模型 |
| 表格 | 已快取 TableFormer V1 `accurate`＋cell matching=True；五張 G1 邏輯表逐張驗 | 相容 stack 的 TableFormer V2、Granite Vision table stage、Granite-Docling 頁面或有明確 adapter 的區域路徑；固定 cell／span／header／條件／note／來源與 parser |
| 頁面／圖片 OCR | 已快取 RapidOCR detector／recognizer／classifier、明確 CPU backend；兩種入口分開 | PP-OCR／方向校正候選按缺口加入；模型檔與 dictionary、文字位置、旋轉與去重分開驗，full-page OCR 不等於已交付圖片 OCR 補充內容 |
| 公式／code | CodeFormulaV2、Granite-Docling 在模型可取得時先量 CPU 小樣本 | 太慢或超出本機可用資源才移公司；區域 crop 與整段／整頁任務分開，記錄解碼長度、格式、符號與縮排 |
| 圖片分類 | DocumentFigureClassifier-v2.5 可取得時先做 CPU smoke | 分類未知／no-text 不得省略必含圖意工作；保存 filter 與未送模型的必要圖片 |
| 圖意／chart／行內內容 | 暫用 OpenAI `gpt-6-luna`／官方 Chat endpoint 已確認；OCR／公式／order／table、圖意／chart及inline已有有界API比較；inline段落局部成功，整頁／其他items及交付仍有缺口 | 公司 self-hosted Qwen3／vLLM 與其他適用地端候選仍各自比較；task prompt、輸出 parser、token／timeout、解析／回填與來源關係必須固定 |

**三種 table 路徑不可混稱**：TableFormer 是專用 table stage；官方 `GraniteVisionTableStructureModel` 是 Granite Vision 的 table crop→OTSL→cells 路徑；Granite-Docling 的整頁 `VlmPipeline` 是另一個主 producer。若以 Granite-Docling 只轉 table crop，要另固定實際 DocTags／HTML／OTSL 輸出與對應 adapter，不能把三種語法任意互換，也不是只改 TableFormer flag。逐層核對「原模型輸出→Docling TableData→Canonical mapper→Markdown」；原始數字存在不等於關係保留。[官方 table remedies source audit](paper-pdf-docling-official-table-remedies-2026-10-11.md)

已有 CPU TableFormer V2、Granite／MLX 的局部歷史失敗，先核對來源 hash／版本再重用其範圍，不因新 G2 命名重跑無效實驗，也不冒充 G1 新版來源已驗證。[既有 V2 結果](paper-pdf-table-v2-results-2026-10-11.md)

## API、GPU 與時間的驗證位置

API 先做最小任務 smoke：正確完整 endpoint／model ID、image payload、chat template、prompt、輸出 parser、token／timeout／截斷；再注入空值、錯誤格式與失敗結果，對賬 required-work。OpenAI-compatible transport 可以成功，不代表該模型能完成公式、圖意或數值任務。Pinned description／formula-code／VLM 有 API seam；pinned chart 主路徑是 local，OCR／classifier 原生 remote seam 是 KServe V2，不能將一個 OpenAI-compatible endpoint 當所有 stage 的通用實作。[既有逐 stage source audit](docling-capabilities-vs-pdf-core-2026-10-02.md)、[pinned API engine](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/inference_engines/vlm/api_openai_compatible_engine.py)

**執行位置依使用者本輪指示固定**：本機 MacBook Pro 強制 CPU，不用 AUTO 默默改用 MPS／MLX／CoreML。先跑現有小模型與可負擔的 CPU smoke，記錄 stage 耗時、RSS、冷／暖狀態；有具體時間／記憶體或硬體限制再交公司補驗。公司環境到位後才驗 GPU device／provider／placement，分開 worker GPU 與 remote serving GPU。正式相同條件 CPU/GPU 比較、持續併發及高頻容量／端到端 SLO 放 G4；Mac CPU 結果不當 Linux／GPU／production 效能。[官方 GPU guide](https://docling-project.github.io/docling/usage/gpu/)、[既有資源與負載計畫](docling-pdf-core-capability-validation-plan-2026-10-14.md)

**暫時 API 與公司交付分開**：使用者已確認本機需要 remote 大模型時可暫用 OpenAI 官方 VLM；公司實際環境為 self-hosted VLM／vLLM，已有 Qwen3。前者可驗任務接口、schema／parser、來源對齊、回填與錯誤處理；但 task quality 仍依該模型自己的來源結果判定，不能宣稱與 Qwen3 效果相近。公司候選必須用相同來源重驗品質、latency、資源與 serving；地端開源的正式交付條件保留，Qwen3 也不排除其他適用地端候選。服務端不可觀測時只記 client round trip，不臆測拆出排隊／純推論／網路耗時。

## 執行範圍與產出

G1 的 57 個紀錄不是 57 份 PDF。G2 使用 31 個既有來源 + 13 個受控正向案例所對應的頁面／區域；跨頁／reading order 需要上下文時保留相鄰頁或完整必要範圍。11 個契約負例中可在任務接口核對的部分先做 task mock／adapter smoke；真正持久性、完整 handoff 與恢復留待 G3，不能以 mock 充當通過。兩個負載情境留給 G4。先做代表小樣本排除不適用候選，再擴至其任務相關案例；不做所有模型 × 所有案例的笛卡兒積。[G1 registry](../fixtures/pdf-core-g1-2026-10-14/cases.json)

每個實驗交付固定配置、原始 provider／回應／圖像、來源對照結果、失敗所屬層、stage latency／資源及「保留／淘汰／需補強」理由。通過門檻沿用需求；G1 真實來源／holdout 缺口保持可見。G2 結束應能提出 **一個可送 G3 整合的候選配置，及各任務的證據與未解缺口**，而不是宣告正式 production profile 或全部需求達標。

若任何必含任務仍無可行路徑，就記錄 G2 尚未通過與具體缺口；不為進入 G3 而刪除功能或放寬已確認門檻。

本機 CPU 與暫用 OpenAI `gpt-6-luna`／`https://api.openai.com/v1/chat/completions` 的任務結果已單獨保存，未改部署。公司 Qwen3 model ID、服務參數、GPU 與可用容量仍待確認；credential不記錄在程式、研究文件或ticket。本機／暫用API結果不能證明公司Linux／CUDA runtime或高頻吞吐合格。
