# B 收斂計畫與 A/B/C 長期返工的因果審查

**執行已結束：**[19 個離線控制與 A／C 診斷](../pdf-core-offline-gates-2026-10-18/report.md)完成後，使用者選擇 B 獨立比較；[Sol 七次推論](../pdf-core-b-model-challenger-2026-10-18/report.md)已執行，T04 必要模型家族歸屬仍錯，候選 `METHOD_STOP`。後三次 T03 與外部回歸依 gate 未執行。本文件保留為歷史規劃／根因證據，不再是待啟動 run。

本文件只約束 B 的唯一已登錄模型比較；與 A／C 共同來源檢查並行的離線順序、付費前的整體成本檢查，以及 #84 結案條件見[最終決策界線](../pdf-core-issue84-final-decision-2026-10-18.md)。

2026-10-18，Asia/Taipei。使用者要求先釐清「換模型」及驗證久拖原因。本輪僅查證、離線重播與制定計畫，沒有修改凍結評讀結果、啟動模型／API、開 holdout 或推進 C。

**目前順序：B 的 evaluator 與 T03 離線接點檢查，和 A／C 共用來源方法診斷並行；兩線各有結論後，按最終決策文件判斷付費 B 是否值得執行。**A 尚未有完整合格方法；C 的模型推論與完整整合仍未放行。

## 需要更正的上一輪建議

「換模型」原意是：保留 Standard 主幹、同一裁圖與表格交付協定，只換負責表格轉錄的外部 VLM。它不表示更換 TableFormer、改成整頁 VlmPipeline，或掃描所有模型家族。

但是，直接將它列為下一步太早。新證據顯示，上一輪 `evaluate.py` 是記錄當輪人工 source matching 的 materializer，不是已能獨立評另一模型的 grader。上一輪報告已明示這個程式的人工性質，但下一步建議沒有先驗它能否處理「另一種合法答案／修好的答案」。主線應先攔住這項 readiness 缺口。

## 本次新重播：已確認的缺口

可執行診斷 (`evaluator-replay-audit.py`)及機器結果 (`evaluator-replay-audit.json`)只改記憶體／temporary copy；原 producer、raw、Core、Markdown 與來源 hashes 前後相同。

| 探針 | 真實程式結果 | 應如何解讀 |
|---|---|---|
| T01 只將 dimension `Method` 改成等義 `method` | Parser→公開 Core→Markdown 均通過；`observation()` 因匹配寫死而 assertion fail | 評讀工具綁定當輪命名，不能直接拿來跨模型比較 |
| 用 T04 真實 oracle 的 `Multi Hop/ME` 進 `observation()` | 落入 collateral 分支，KeyError | 上輪 T04 既已拒絕，沒走到成功分支；未實作的成功評讀路徑因此未被發現 |
| Table 7 第一式由 `c_{-1}` 改成來源正確的 `c-1` | 現有 literal assertion 反而不成立；原程式又將第一組 false、其餘 true 及 3/4 寫死 | 程式記錄了當輪人工判斷，不能視為獨立數學評分器 |
| `manual_structure_review` | 程式以 delivery 存在自動設 true，overall 只讀數值／比較 | 這些 flags 不能作下一輪的自動來源品質證明；人工審查項目必須有明確 decision／evidence |
| 真實 T04 saved response | 5 rows／50 metric cells；groups=[] 卻引用 gpt，parser 合理拒絕 | 這次模型輸出確有問題，不能以修 scorer 將它改判通過 |

對應程式：硬編碼 matching (`docs/research/pdf-core-fixed-seven-source-2026-10-18/evaluate.py`)、結構旗標／overall (`docs/research/pdf-core-fixed-seven-source-2026-10-18/evaluate.py`)、math 當輪結果 (`docs/research/pdf-core-fixed-seven-source-2026-10-18/evaluate.py`)。本輪不修改這份歷史 materializer，也不讓修正後 evaluator 回寫原版報告。

T04 實際 wire image 是 796×563，bytes 與前輪相同。前輪同模型 alias 曾讀到 295/300 數值且無漏值，本輪改 semantic 協定後只回 50 個。這次 completion=1,856、finish=stop，遠低於 32,768 cap，沒有 token 截斷證據。**因此不能宣布已碰到 Luna 能力上限；協定負擔、模型隨機性、供應商 alias／視覺處理差異尚未完全分離。**

同時，T04 缺 25 列、E017 在 provider 階段就改變分母意思是可獨立確認的真失敗，不靠這些 scorer 缺口也足以不晉升。本次沒有推翻實際呼叫數、成本或來源錯誤證據。

## 為何久拖：確認事實與因果判斷

| 原因 | 已有證據 | 對返工的影響／判斷 |
|---|---|---|
| **評讀器追著當輪輸出寫，測試也沿同一假設** | 本次成功 T04 路徑未實作、等義命名被拒、正確 math 會撞斷言；歷史另有漏計 extra panel、忽略 group scope、pair 暗加零錯 | **已確認的設計缺口。** 正常／傳輸 controls 通過，仍不足以證明評讀器能公平評新候選。新模型一改輸出形狀就再修評分程式；這是 evaluator 對當輪輸出的過度貼合 |
| **較晚才把來源意思、模型轉錄與表示／交付拆開** | 完整 cells→compact grid→padding→header paths；T05 原內容完整，padding saved replay 即能交付；T04 又確實有錯誤來源綁定 | **已確認過程，因果判斷。** 太早讓模型生成尚未穩定的表示，之後才辨別哪些限制是產品必要、哪些是接點限制，產生多輪契約與接合返工；不是使用者一直加需求 |
| **低估來源 ownership／discovery 是 A/B/C 的共同前置問題** | A 的來源跨 table/caption/mixed owners；C 全圖 census 才揭露局部 screenshot／timeline 範圍與圖外 title；T03 仍是三個 independent items | **已確認來源缺口，架構判斷。** 以 SDK emitted item 當實驗單位，容易先測成功的小區域，再發現完整必要內容根本不在該輸入中；換模型不能補回未送入的內容 |
| **交接與前置檢查的完成定義不一致** | 歷史逐頁 MLX run 卻談跨頁 assembly；兩張實際 model PNG 變黑；Stage1 B 曾缺 runner／token budget，摘要卻概括阻擋後段 | **已確認。** 主線需補測、修正可支持的結論與重接工作；不能把部分完成、mechanical pass、品質通過互換。現在 ZombieProcess／permission 已處理，不應繼續當未解原因 |
| **有每輪停止線，欠跨輪的有限候選與最終決策點** | 原三段計畫已有硬限與 stop，但停止一個 producer 後又可另立表示／context 假說；導航也曾指向舊狀態 | **治理推論。** 每輪都能合法結束，整體卻持續「下一步」。缺的是 B 整體在有限候選後要交付何種去留／取捨，而不是再加一個每輪 timeout |

歷史 primary evidence：三項 grader findings 與重播 (`docs/reviews/pdf-core-b-script-review-2026-10-17/review.md`)、修正複核 (`docs/reviews/pdf-core-b-script-review-2026-10-17/fix-review.md`)、A/B/C retro (`docs/reviews/pdf-core-abc-followup-2026-10-17/retro.md`)、早期方法／輸入問題 (`docs/reviews/pdf-core-experiment-audit-2026-10-16/retro.md`)、Stage1 主線複核 (`docs/reviews/pdf-core-stage1-main-review-2026-10-17.md`)、[表示契約審核](../pdf-core-stage1-followup-2026-10-17/contract-audit.md)。

這不是「所有實驗作廢」：修評讀器通常可重播同一批 raw，不須重付模型成本。也沒有證據可精確把總耗時按百分比分給模型／腳本／溝通，或斷言每次都因 script 出錯。使用者對低延遲、minor 容忍、避免後處理的目標相當一致；主線在實驗分層、readiness 與跨輪收斂上的把關不足，是應由主線負責的部分。

## B 模型比較的有限計畫

本計畫不保證候選必然通過；保證把它收斂成可審查的通過／不通過結果，失敗後不自動再增模型、prompt 或表示。

### 1. 先凍結 B 的完成矩陣

- 單頁：原四主表 470 數值／23 比較、兩 collateral、Table 7 四組 math。
- 跨頁 T03：264 數值／7 比較／3 missing marks、完整三頁來源、條件繼承及非目標保護。
- 交付：原義、必要 headers／conditions／aggregation、paired roles、實際 Markdown、同版結構／來源。
- 品質沿原判準：每張複雜表最多5%數值錯誤、必要歸屬／關鍵比較／數學意思正確；不加 printed-grid 或零錯要求。
- 分清「B 開發候選通過」「外部回歸通過」「正式公司模型／SLO資格」，避免再以七筆結果宣稱整個 B 完成。

### 2. 兩項 B 離線 gate 先完成

**Evaluator：**沿用原來源答案與 rubric，分開 source matching decisions、實際 Core／rendered extraction 與算分。新模型的 row/header IDs、大小寫或等義 labels 不當 GT；output-specific matching 放在顯式審查記錄，不寫成只適用前一模型的分支。數學由逐項來源 review 記錄輸入，程式只核對已保存的觀測與決策完整性，不假裝靠字串比對證明任意代數等價。

必要 controls：完整合法 T04 可評、修正／錯誤 math 可區分、等義 labels/IDs 可過、錯 header/condition/group、extras、missing rows、pair 顛倒皆不可過；一個5%內且不改關鍵關係的 minor 可過。人工結構 review 未完成／無 evidence 時不可變 true，overall 必須讀取這些必要 decisions。先重播舊 raw；不得修改舊 raw 或改判掉真實漏列／改義。

**T03：**只登錄一條小型接合假說：以通用的明確 `Table N`／`Table N (continued)`、頁序及相容 headers 建立同版 logical-table relation；保留三個 native fragments，僅在 isolated document copy 更新其公開 `TableItem.data`。不 delete/insert/reindex，不強制壓成單一 TableItem，不猜欄、不補數字、不造 cell bbox。重複編號、多個可能前段、caption 缺失／衝突時 abstain。初始 caption 的 dash／rounding 條件透過原 caption ref 適用三段。

這是新的研究 integration sidecar 假說，不是宣稱 Docling 已原生合併。需驗證三段順序、repeated headers、共同條件、三頁 provenance、JSON reload、主要 Markdown 可理解性；同頁另兩表完整 public graph、caption、provenance、位置與 rendered Markdown 必須原樣。所有三段成功才可能接受 T03。

離線實作合計硬限 **120分鐘**，未完成即記 partial／blocked 並提出具體決策，不自動換另一套協定。**任一 gate 不成立，就停止完整 B 的這個候選，不先付費跑七次。**

### 3. 單一模型 challenger，最多七次

只登錄 `gpt-6.1-sol` 對照既有 `gpt-6-luna` 結果；建議及來源見 [model-options.md](model-options.md)。官方確認影像輸入、Chat Completions 與 low reasoning 支援，帳戶 access 尚未驗證。[官方模型頁](https://developers.openai.com/api/docs/models/gpt-6.1-sol)

七張圖片 bytes、prompt/schema、mapper、high detail、low reasoning、JSON object、store=false 與接受條件保持。只改 model ID 及必然變化的 request hash；不加解析度、改 group 規則或調 prompt。這是相同應用輸入／契約的候選比較，不是相同內部視覺 tensors 或因果隔離的純權重實驗。

最多7 calls，concurrency=1、retry=0，180秒/request、1,800秒/整輪、32,768 completion/call；延續已凍結的記憶體與 cumulative usage guards。先核對 model access／有效參數，參數不支援時停止，不暗換 settings。按來源獨立評讀，保留已成功項目的回歸；停止／拒絕／usage不明照原規則處理。

它回答「另一模型是否更適合此交付協定」，不宣稱已證明 Luna 的能力上限，也不承諾公司 Qwen3 同樣有效。

### 4. 單頁全部符合後，T03 最多三次

只有步驟2的 T03 source/接合 gate 已通過，且七次品質符合，才由通用 producer 對三個原 native table crops 各呼叫同一 challenger 一次。每次180秒／32,768 completion cap、三次合計540秒；三個確切 request、input reservation、來源與方法 hashes 在首個請求前固定成整數／明確 bytes。

同頁兩張 collateral 不另送模型：新接合只做 data 替換，須以完整原樣比較保護它們；不能直接沿用舊刪除／插入、要求全頁全部 targets 重建的 mapper。任何一段內容或必要條件失敗，整個 T03 失敗，264／7／3 分母均保留。

**本輪最多一個新模型、10次開發推論（7＋3），零逐題重試。** 七次失敗不再做後三次；不自動升 Astra、不再加新 representation。

### 5. 開發門檻全過才做固定外部表格回歸

沿既已凍結的 OmniDocBench 60頁 manifest，只取其中28頁 table strata（table-math10、merged10、其他table8），不依結果換頁。先完成所需 evaluator runtime 與 page-input hashes，並用離線 fixture 確認表格指標可執行；不等模型已跑完才發現評分環境未就緒。

Standard baseline 與固定增強配置在同一批來源配對比較。所需 live jobs 由原生 producer inventory 決定，不是直接假設28頁等於28 calls；首個遠端請求前必須凍結實際 calls／tokens／時間預算，超出登錄就停止，不隱藏未送項目。這是下一個獨立有界執行段，**不含在前述10次開發比較中**。

TEDS／TEDS-S 是補充結構指標，不能當作「數值誤差≤5%」的替代。原先 T04／E017／T03 不因外部平均較高而免除；公開資料亦不等於私有盲測。六份 sealed holdout 保持封存，完整 Profile 固定後才另作資格驗證。

### 6. 交付 B 結論，納入 A／B／C 整體決策

交付單一矩陣：每項品質、尚未支援內容、原 native／增強後交付、calls／tokens／pixels、CPU／API latency 與測試分布限制。沒有正式高頻SLO時先報增量成本，不宣稱已達吞吐或最佳 Pareto 點。

若符合，保留具名 B 候選，連同 A／C 的方法可登錄性及共通必含缺口作一次整體決策；若仍不符，帶具體來源缺口與代價讓使用者決定支援範圍／方法／投入，不自動開下一輪。A／C 的方法與固定推論未因 B 通過而取得資格。「這一候選的驗證完成」不等於「B 功能已符合需求」。OpenAI 是暫用方法比較；正式公司 Qwen3 exact ID、GPU／vLLM與高頻部署資格仍後續獨立。

## 本輪執行範圍

三個分工做了歷史因果、B saved-input／scorer、官方模型文件的獨立核對；主線另重播實際 parser→Core→Markdown→評讀反例。沒有新增推論、修 evaluator、實作 T03、改驗收門檻或更動 credential。以上是下一步計畫；不得將它標成已執行或已解決。
