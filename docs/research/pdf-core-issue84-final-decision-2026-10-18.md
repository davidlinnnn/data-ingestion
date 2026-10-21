# #84 最終決策界線與 A／B／C 退出規則

更新至 2026-10-20，Asia/Taipei。**本文件是 #84 能力狀態、已停止候選與下一動作的唯一最新入口。**[配置盤點](pdf-core-balanced-config-2026-10-17.md)保留當時的取捨；[三段計畫](pdf-core-three-stage-plan-2026-10-17.md)是已凍結的事前規劃，後續導航與狀態只更新本頁，不再寫入凍結計畫。各實驗報告與封存產物仍是結果依據。本次整理不改 F01–F22、品質容忍、歷史評分或原始結果，也不宣稱已有合格 Processing Profile。

## R1 live 前置檢查交接（2026-10-20）

依主線 Claude 指示，#84 以決策／交接票收斂，品質資格由 #80–#83 gates 負責；公司模型／GPU 留在 #82/#83。固定 DEV 模型 `gpt-6.1-sol`，唯一 metadata GET 200，零推論。[本輪報告](pdf-core-r1-method-2026-10-20/live-preflight/report.md)：43/43 mock 接點、24 個 runner 控制與既有 109 個測試通過；**live_ready=false**。第 2 項仍缺官方模型 tokenizer／image token 規則，189,438 只屬文字 proxy，completion cap 合計 475,136；第 3 項規約、11 份來源檢查表與全部 43 job 非目標 QA 已凍結，但完整 occurrence／OCR golden 尚未完成。已停下等待主線裁定，不啟動 43 次真實推論，不改 W2 或原 thread 狀態。以下先前盤點中的 A/C 下一動作由本段與下列表格新列更新。

## R1 本輪已結束（2026-10-20）

使用者已批准並執行一次 8 小時上限、零新推論的方法工程。結果為 **METHOD_REGISTERABLE：僅固定 DEV 範圍的離線接合候選，live_ready=false**；下方舊提案中的未選擇／未開始狀態由此更新取代。[完整結果與停止線](pdf-core-r1-method-2026-10-20/report.md)。19 個新控制與既有 109 個測試通過；兩個實際反例以 MOCK 證明公開 Core／serializer 可交付，不能代表模型準度。原生 caption 修復責任使候選完整工作量由 32 增至 43 次遠端請求，另有 29 個本機 OCR 工作，均未啟動。正式推論前仍缺模型/token 預檢、擴充來源評讀規約與 bounded runner 接點；不自動延長 R1 或開始付費批次。A/C 內容、B 與雙欄缺口仍保留。

## 目前 component 狀態（2026-10-20）

每列分開核對必要目標是否被發現／送入、模型內容、實際交付與來源、成本／回歸。`局部成功` 僅涵蓋引述來源；完整方法、來源覆蓋與同版整合各有自己的 gate，不能互相代替。

研究主幹仍是 Docling-slim 2.132.0／Core 2.99.0、`StandardPdfPipeline`／PyPdfium／Heron／RapidOCR v6 small／TableFormer V1 accurate，CPU4／interop1／batch1。這是比較基線；code、formula、picture 等 enrichment 沒有因被列為候選就全域開啟。

| 能力／實測路徑 | 目標發現／實際輸入範圍 | 模型內容 | 寫回、Markdown／supplement 與來源 | 成本／回歸證據 | 終局／下一動作 |
|---|---|---|---|---|---|
| A/C：R1 live 前置（最新） | 固定 15 次 source reconstruction＋14 次 description/context OCR＋14 次 chart；29 圖 | 固定 `gpt-6.1-sol` DEV；本輪零推論，GET 200 不代表品質 | 43/43 mock、11 份來源組裝、14 份 supplement；原子交付、超額／逾時／失敗即停 | 24 控制、既有 109 測試通過；逐 job 正式 input／費用仍未確認；source-only partial golden 已凍結 | **live_ready=false**；主線決定補齊第 2/3 項或交接；未核准不執行。見[報告](pdf-core-r1-method-2026-10-20/live-preflight/report.md) |
| 雙欄／OCR／讀序 | 原 Heron 22 框分欄；Docling 膨脹合為跨欄 OCR 輸入。另有原生 ReadingOrder 錯序、paragraph merge 跨欄，須分開定位。[接點追查](pdf-core-order-tessbest-2026-10-20/report.md) | C10、Tesseract fast／best 在 known 與 ACL p2 兩頁讀序正確；其他頁仍有重複、數值、識別字或 URL 缺陷。v5 server 亦未消除必要內容缺口 | 原 raw OCR 混句、原生排序與段落 merge 都有具體反例；只修某一層不等於最終內容合格 | C10 已跑七頁且有重複；best 七頁 28.01s；v5 server 七頁 129.91s／21.14GiB peak RSS，皆非正式 SLO。[C10](pdf-core-ocr-region-policy-2026-10-20/report.md)、[v5 server](pdf-core-ocr-v5server-memory32-2026-10-20/report.md) | **未收斂，不是無解。**這些固定配置不採用；保留診斷與正負控制，不再自動搜尋 padding／模型變體。新方法或官方版本對照須另有有限範圍與停止線 |
| A：code／偽碼／inline code | CodeFormulaV2 實跑 8 頁、10 regions；普通正文、picture-child 與跨 parent 必要目標仍無完整通用輸入／輸出責任 | 真實指令、巢狀結構與部分 literals 恢復；diff 的 `===`、`:.2f` 改字，鄰文寫入 code。[E1](pdf-core-standard-enrichment-results-2026-10-17.md) | 公開寫回與 MD 可執行；原 bbox／orig 保留不等於鄰文歸屬正確，原位 inline／完整順序仍缺 | E1 worker 55.72s／6.21GiB，與下列 formula 共用同 run，不重複加成本；41 單位完整評讀保存 material／未涵蓋 | 局部成功保留；E1 不全域啟用。R1 離線接合候選已登錄；模型完整品質未合格，live 前置第 2/3 項待補。依上列交主線裁定，不跑 code API |
| A：獨立／行內 formula | 原生 root formula 可送入；普通段落 inline、圖內 math 及圖題跨 owner 範圍不完整 | 真實 SEAL Eq2 的 cases／條件／式號通過；Eq1 改義、Eq3／4 漏式號。後來 B Table 7 math 4/4 是另一任務，不代替全文 F13 | 部分 LaTeX／主要 MD 成功；語法可解析不證明數學等義。完整發現、原位插入、圖內 occurrence 與來源關聯未成立 | 同 E1 成本；[A／C 離線診斷](pdf-core-offline-gates-2026-10-18/report.md)保留 44 groups、27 ordinary negatives 與兩個跨 owner／parent 缺口 | 局部成功保留；R1 typed math 接合已有離線候選，完整發現／內容品質仍未合格。live 前置同上列；不以文件 ID 或 oracle 選路 |
| B：普通／複雜／跨頁 table | Sol 固定七次涵蓋 T01／T02／T04／T05、兩張同頁表與 Table 7 math；T03 live、外部 28 頁未啟動 | T01／T02／T05、同頁兩表、math 4/4 通過；T04 按位置 298/300，但家族綁定後 198/300、比較 4/5。[Sol 終局](pdf-core-b-model-challenger-2026-10-18/report.md) | 公開 Core／serializer 有實際交付證據；T03 僅 MOCK 三片段／多頁來源接點，不是跨頁模型品質 | Sol 七次 214.50s、11,809 input／15,081 completion；與 Luna 工作輸出量不同，非等品質加速比 | **METHOD_STOP；登錄候選已用盡。**T03 live 與外部回歸 NOT_RUN；保留接合與局部成功，不自動再開模型、prompt 或表示法 |
| C：圖片 inventory／caption／OCR | 早期有真實 crop OCR；後來 55 頁／29 圖來源盤點及 FULL_PAGE 比較完成。SEAL 圖題已在正文，仍在 picture crop 之外 | OCR 有局部內容成功與漏字；FULL_PAGE 恢復 ReasoningBank caption，未修完整 picture 輸入範圍。[C 來源結果](pdf-core-c-source-closure-2026-10-18/report.md) | image-key／supplement 接點局部成立；完整 inventory、跨 owner 輸入與同版來源／輸出責任仍不足。caption 在正文不能算模型已在 crop 看見 | FULL_PAGE 55 頁 conversion 146.717s；該輪新 component remote calls 0。舊 29 圖／58 requests 因 gate 未啟動，不是已花費推論 | R1 來源/context 接合候選已登錄，完整 C 品質未合格；第 2/3 項缺口交主線裁定，不以逐圖 padding 補成通過 |
| C：圖片分類／圖意／chart | FigureClassifier-v2.5 實跑 6 來源／12 crops；早期 API 實跑兩張真實圖意、四張受控 chart。這與後來停跑的 29 圖／58 requests 是不同輪次 | broad family 相符；兩圖必要流程／UI 關係、四 chart 的 13 點與關鍵關係有正面證據；SmolVLM 預設漏必要圖意。[早期實測](pdf-core-g2-images-2026-10-14.md) | 生成 OCR／圖意／chart 必須透過同 revision image key 進 supplement；typed unit、完整圖片覆蓋與來源關聯未整體驗收 | classifier 約 0.1s/crop；早期六次 API 共 5,284 input／3,574 completion。真實 chart 分布、整體回歸／成本及公司服務未驗 | 保留 classifier 可選、偏好開與 task-specific VLM 方向；不是 C 全部沒測，也不是完整 C 合格。分類不得免除必要 enrichment |
| PaddleOCR-VL Result → Docling | 本輪以正確 synthetic protocol controls 測真正 Result/export/import，**零模型推論**；不是已跑完整 Paddle 模型流程 | 沒有新模型品質結果；不能據此判 layout／雙欄成敗 | 座標 ledger、逐頁圖片資產與搬移讀回可行；stock 跨頁表 merge 刪合法重複資料／誤併、來源不足，MD code／衍生資料分離有缺口。[接合結論](pdf-core-paddle-join-preflight-2026-10-20/findings.md) | 安裝隔離 client/export 套件；無推論 engine／權重下載、模型/API calls 0。GPU／延遲未驗 | **維持全部必含且不新增語意續接方法時，stock 完整交付 NO-GO。**保留辨識候選身分，沒有授權接著推論 |
| 同版完整 Profile／其他共通必含 | A／B／C 外仍有正文、章節／title、方向、metadata、狀態、lineage 與恢復等責任；[F01–F22 歷史盤點](pdf-core-balanced-config-2026-10-17.md#全部需求盤點)供查核 | 局部元件成功不能填補漏送目標或其他必含失敗 | 尚無同一配置完整 A＋B＋C／共通功能的 accepted 產物；raw-only、bundle reload 不代替必要語意或 worker recovery | 無正式 p95／高頻吞吐／公司 GPU 成績；pilot 目標仍保留，不能相加歷史單輪秒數估完整延遲 | **完整方法未合格；整合 run NOT_RUN。**先決定具名方法／資源／範圍，再由相依議題執行 qualification |

上述 A 亦包含較早[component context API](pdf-core-g2-context-api-2026-10-15.md)的實際推論證據：36 次中有真實正文／inline math 的局部成功；原分類 25 pass／5 minor／6 material、34 筆可結構回填，不能互換為完整成功率。RTT 合計 193.37s、25,720 input／13,643 completion；仍有 `{}`→`[]`、數學 prime／identifier 改義及角色接點問題。此輪不選為完整 challenger，與 E1、後來零模型方法診斷分開記錄。

### Enrichment 與交付責任

維持「Standard 主流程＋依 category 選擇適合的 enrichment」方向。每個必要目標要同時有來源清單、實際送入範圍、內容與寫回責任；上游沒發現或 crop 不含的內容，不能假設後續 enrichment 會補回。Category 可重疊：圖內 math、表內 code／公式仍有必要工作，image／table 分類不構成豁免。

主要 Markdown 保留來源正文、code／公式重建、表格、原圖與原文 caption。生成圖意、圖片 OCR、chart 解讀以同 revision image key 關聯 supplement，保留 source／reconstruction／generated 身分；完整 provider 證據另行保存。路徑 namespacing、來源 ledger、已標記欄位分離屬一般封裝；推測跨 owner 歸屬、語意續表或修正模型內容是方法工程，須另作取捨。

### 本次完成點與下一決策

評讀與證據的統一入口見無推論守門說明 (`tests/pdf_research/README.md`)。CI 執行可攜純控制；本機完整模式另比對封存、保存的實際輸出並沿用既有 A／B／C gates。檢查成功只證明其明列的回歸／完整性，不將本表的 `METHOD_STOP` 或 `NOT_RUN` 改成品質通過。

本次只校正狀態入口與既有評讀的無推論守門；未啟動新模型、A／C 方法設計或整合 run。**R1／R2／R3 尚未選；本次環境修正不是 R1 的 8 小時工程授權。**具體三選一仍見下節，保留原必含及停止條件。後續摘要與交接先讀本矩陣，再依該列連結查原始報告；每有新結果只更新本入口的現況，不重寫封存或複製另一份當前矩陣。

## 既有決策與診斷紀錄（2026-10-18–19）

以下保留當時的結果與提案，若涉及「最新」「尚未啟動」等時間性敘述，以當時輪次解讀；2026-10-20 的跨輪現況以上表為準。原有資源取捨、授權與退出規則繼續適用。

**最新執行結論：**[兩條離線工作已完成](pdf-core-offline-gates-2026-10-18/report.md)，19 個 controls 通過；A／C 的完整頁 context／原 owner 回填假說仍無完整可登錄方法。使用者在檢查點明確選擇完成 B 獨立比較，隨後[Sol 七次比較](pdf-core-b-model-challenger-2026-10-18/report.md)已完成：T01／T02／T05、兩張同頁表及四組 math 通過；T04 雖有 298/300 位置讀值，必要 Qwen 家族歸屬錯誤，故 `METHOD_STOP`。T03 live 與外部回歸依 gate 未啟動。**本輪 B 候選已用盡，沒有已登錄的下一個模型比較；完整整合仍未放行。**

**2026-10-19 閱讀順序定位補充：**[官方 issue／pinned code 調查](docling-reading-order-official-research-2026-10-19.md)確認 S0 保存的 OCR cell 已跨欄，`foror` 在 page assembly 合行時形成，早於最後 reading-order／Markdown。實際 OCR mode 是 `DEFAULT`／PDF-aware layout regions，不是先前口語稱呼的 AUTO；layout-first 與 separators 已在基線，不能當成未試的新修法。未找到能直接宣稱修好本例的已驗證官方設定。本次零新推論；使用者正逐項檢視能力與容忍度，R1／R2／R3 尚未選定，8 小時提案未啟動。

**後續單頁追蹤已完成：**使用者另行授權的[OCR 邊界 trace](pdf-core-ocr-boundary-trace-2026-10-19/report.md)只重跑一次原 S0、零 API／重試。Heron 22 個原始框均分欄；20-point dilation／連通區合併形成單一跨欄 reader 輸入，raw OCR 已混句。離線 0 對照只證明框分開，不代表 OCR 修復。原 cells／layout／assembly／provider document 與 Markdown 均和歷史 S0 相同。此診斷完成，偏差仍不合格；未啟動 R1、未新增下一模型名額、未修改必含或正式配置。

**後續裁圖消融已完成：**另經使用者授權的[同模型 1＋15 次 OCR 比較](pdf-core-ocr-crop-ablation-2026-10-19/report.md)證明分離裁圖可使本頁 raw 混行 3→0，但會丟失 `2 OVERVIEW`，既有 Background 首行被 classifier 誤轉 180° 的缺陷仍在；原生 ReadingOrder 另建立 P01→P06→P02 關係，最終仍有四對正文錯序。零膨脹配置不採用，這輪到此停止。A 控制完全重現，評讀器 `cref`／`$ref` 接點缺口以具名修正重評保存結果，沒有重跑推論。0 API／重試／新 Heron，僅一張已曝光 raster 頁，沒有合格正式配置或新增 A／B／C 候選；R1／R2／R3 仍待取捨。

## 方法與資源取捨提案（2026-10-18，待使用者選擇）

公開同步：[完整取捨提案](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6247306136)。以下仍待選擇，尚未改動既有必含或授權新推論。

**建議：保留已確認的完整需求，另外決定是否投入一次有上限的工程方法工作。現有模型研究在此結束，不把下一個模型當成預設續跑。**這是產品／資源提案，尚未獲選，不是新的執行授權，也不是已選定的完整 Processing Profile。

### 現在可以決定的方法去留

| 項目 | 建議取捨 | 證據與限制 |
|---|---|---|
| PDF 主幹 | 保留 `StandardPdfPipeline`／PyPdfium／Heron／RapidOCR／TableFormer V1 accurate，沿既有 pinned runtime 及 CPU4、interop1、batch1 比較基線 | 可本機執行且有局部正面證據；不是完整功能或正式容量已合格。F01/F02/F03/F09 的掃描順序、章節與語言覆蓋仍需資格驗證。 |
| 整頁 VLM | 不選作預設轉換，也不採每個 owner 重送整頁的預設方式 | 已測逐頁配置有內容／來源交付缺陷。A/C 的 85 owners、11.1 倍重複 pixels 是診斷，不能當已執行 calls 或帳單。 |
| 全域 CodeFormulaV2 | 不全域啟用 | 既有輸出有 operator／identifier／literal 改義，亦不能保證全文 inline discovery。 |
| 表格 VLM | 保留公開 Core／serializer 接合證據；Luna 與 Sol 本輪配置都不晉升為完整 B | Sol 七次 214.50 秒、11,809 input／15,081 completion；比 Luna 同輸入 88.11 秒慢，輸出完整度不同。T04 數字 298/300，卻有一個家族名稱錯誤影響十列歸屬，不能當已符合必要表格條件。 |
| 圖片／chart VLM | 保留按任務增強的方向與局部正面證據；尚不承諾完整 C | 欠完整來源群組與同版輸出責任；分類器不能豁免必含內容，也沒有已驗證的「困難圖片／表格」自動路由。 |
| GPU／vLLM／公司 Qwen3 | 作正式地端部署及效能 qualification 的候選；不因目前缺口立即追加 GPU 或換模型 | 精確 model ID／版本、serving 及 GPU 資訊仍待使用者提供。API 相容與 GPU 加速都不證明來源歸屬／全文覆蓋正確；OpenAI 只代表獲准的 DEV 暫用比較。 |

這不是 Pareto 最佳配置或正式成本估算。既有 Standard 11 頁 worker 32.03 秒與 Sol 七次 component 呼叫涵蓋不同工作，不相加推估新文件延遲；沒有 p95、GPU seconds 或正式帳單證據。維持原 pilot 目標，新高頻負載及資源預算另定，不拿研究 timeout 當 SLO。

### 三個互斥的產品／資源選項

| 選項 | 具體決定 | 所付代價與終點 |
|---|---|---|
| **R1：保留完整需求，批准一次有界工程方法工作（建議）** | 不改 F01–F22、minor 誤差及無逐文件人工修正／核准原則。最多 **8 個 active engineering hours，合計一次**，只做下面的來源／輸出契約與離線可行性；零新推論／模型下載。 | 8 小時是提案的投入上限，不是交付估計或成功保證。結束即作可登錄／方法停止／預算停止及 #84 交接結論；不自動接模型比較。仍缺完整方法時停止／改期原完整第一版，無第二輪自動延長。 |
| **R2：修改第一版範圍** | 第一版採 Standard 與來源／provider／Markdown 交付；明確延後 F13/F14 全文公式／code、F11/F12 圖意／chart 解讀，以及 F04/F05 中未合格的複雜／跨頁表格義務。保留一般表、圖片／OCR、來源及其他未被修改的要求。 | 這是改掉先前的「第一版必含」，不是原需求通過。剩下的文字／順序／章節／掃描與交付仍須驗證，不能宣稱縮範圍就可立即上線；需改寫 #84 與 #80–#83 後再執行。 |
| **R3：現在停止／改期原第一版** | 不追加方法工程或模型預算；保存既有主幹、接點與實驗，記錄完整第一版目前 no-go。 | 不推出聲稱滿足原需求的 Profile；後續若重啟，須另作明確的新範圍／資源決定。 |

推薦 R1 的理由是使用者已多次確認完整公式、code、圖片及表格用途必含；不應由 agent 自行刪除。**但不建議以無上限工程換取這些要求。**若不接受這一次有限的自訂整合投入，建議明確選 R3；若近期交付優先於完整功能，才選 R2。人工逐文件修補不是已同意的第四條捷徑。

### R1 的可審閱工程邊界

- **負責人與投入**：本主線 agent；只有使用者選 R1 才開始計時。所有設計、最小 prototype、正反例及報告合計最多 8 個 active hours；不把每個分支各分配 8 小時，不含等待使用者提供公司資訊的時間。
- **唯一新設計目標**：一個跨 owner 的來源群組／輸出責任契約。完整來源頁可作唯讀 context；可寫 target、必要原文／公式／code occurrence、讀序與同版 supplement 關聯必須分清。對混合圖／圖題與跨 parent algorithm，說清誰產生何種內容、如何進主要 Markdown、如何保留原文 caption 與 image-key 增強分離。這是自訂 adapter 設計，不能稱為 Docling 已提供的 inline enrichment 開關。
- **完整驗證範圍**：重用既有 A 的八頁／44 source groups／27 ordinary negatives 與 C 的 55 頁／19 source groups inventory；保留兩個已知跨 owner／parent 反例。使用實際 source bytes 與公開 Core／serializer 的最小 mock 正反例，禁止文件 ID、oracle bbox 或逐題修值。Mock 只證明交付接點，不能計為公式／code／圖片品質。
- **B 不重啟**：已有公開接合與來源評讀證據；本項工作只把 T04 歸屬失敗、T03 live 未跑及未選正式表格模型寫入 #82 的待決／資格工作，不重命名輸出、不再設另一個 B prompt／schema／model 比較。R1 不保證 A/C 工程成功就能解除 B 的阻擋。
- **交付／停止**：交付一份通用方法與設定／輸入／輸出／來源責任、機械正反例、實際 inventory 及可計算 jobs／資源，或具體不可登錄的原因。不能只交一張 schema 或聲稱整頁都有內容便算方法成立。沒有完整可執行方法即停止；不把新 prompt、裁圖、模型或額外 8 小時稱作既定下一步。
- **推論及 qualification**：本提案的 remote／GPU 推論預算為 **0**。新方法若可登錄，實際模型、逐 job 數量及 token／時間／資源上限必須在 #80–#83 的具體交接中另行固定；未選身份不得用「Qwen3」填作 formal identity。本提案不預先授權那批推論。

### #84 及相依議題的交接界線

本次取捨提案本身**不能關閉 #84**；既有 A/C 方法、B 配置品質與正式模型身分缺口仍如實保留。#84 不要求先證明 pilot 全部通過，但需要可執行的具名方法／身分與實際更新的交接。使用者選定後，按所選範圍作一次規格同步，不建立重複 implementation tickets：

| 議題 | 最小必要同步 |
|---|---|
| #80，core | 取代 Q11 的舊排除項及「不新增 inference stage」；寫入真正選定的方法、required-work／恢復與資源邊界。仍未選定者明列阻擋，不稱 ready。 |
| #81，mapping | 正式 Markdown、同版 table/image references、source／reconstruction／generated 分離、完整 provider／diagnostics／custody；必含內容不能 raw-only 當完成。 |
| #82，table gate | F05 已是本版必要工作；每邏輯表 ≤5% 資料點錯誤，必要歸屬及關鍵比較正確。保存 Sol `METHOD_STOP` 與 T03／外部回歸 `NOT_RUN`，不重開模型搜尋。 |
| #83，qualification | 所選完整或縮減 Profile 的全部必含、來源回歸、同版整合、fresh／reuse／recovery 及 pilot 時效；未驗公司 GPU／高頻另列，不借舊 CPU 結果宣稱通過。 |
| #72／#54／#55 | 保留歷史 #72，明示被取代的 scope 與未改的恢復／來源原則；同步 pilot／新高頻、Markdown 消費與 table-dependent 用途邊界。 |

目前等待的是 **R1／R2／R3 的具名產品／資源選擇**；不是要求使用者替技術診斷。正式公司 VLM 身分與 GPU／高頻數值後補，分別只阻擋其相依的 selection／qualification／capacity gate，不構成自動追加本機模型研究的理由。

## 兩個不同的終點

[#84](https://github.com/davidlinnnn/data-ingestion/issues/84) 是**決定第一版 PDF Processing Profile、Canonical 交付／失敗／驗收契約，並交給實作與資格驗證票執行**的議題。其 D 節允許把尚未證明的可行性列為具體驗證工作；關閉 #84 本身不代表 A／B／C 實測通過或 pilot 達標。

**A／B／C 是元件分支**：A 為全文公式／code，B 為普通與複雜／跨頁表格，C 為圖片及相關增強。原[三階段計畫](pdf-core-three-stage-plan-2026-10-17.md)則是離線可行性、固定元件推論、同版整合。分支結果與階段結果均要分開記；單一元件成功不能代替完整配置。共通的正文、順序、掃描 OCR、章節、原文 caption、metadata、lineage、狀態、provider 與 Markdown 仍須在同版整合與 #84 交付矩陣中覆蓋。

## 每個實驗分支怎樣結束

每個已登錄方法只有五種結果：`PASS`（固定來源範圍內的必要內容、實際交付、來源與回歸符合原判準，成本已量測）、`METHOD_STOP`（方法碰到已確認的必要缺口）、`BUDGET_STOP`（預先固定的時間／呼叫／資源上限先到）、`NOT_RUN`（前置 gate 或具名外部條件尚未成立）、`INVALID_EVIDENCE`（已執行，但後來證實 runner／評讀器缺陷使品質結果無效）。後四者都是**該次方法／執行的終局紀錄**，不是能力不可能做到的證明。每份紀錄必有方法與輸入版本、完整分母、缺口及對應票；有執行時保存可取得的 raw／Core／Markdown、來源評讀、非目標回歸與實際成本，未產出者明列原因與零或部分成本。`INVALID_EVIDENCE` 保留已消耗的呼叫及原始資料，不判模型品質、也不暗中重試；再跑須另作預算決定。未執行的必要目標保留在分母，不用部分成功改寫整體狀態。

| 分支 | 截至本日的方法結論 | 此計畫還有多少已登錄候選 | 下一個允許的動作 |
|---|---|---:|---|
| A，F13／F14 | 公開 Core fragment-order／mock 運輸接點通過狹義控制；picture／body 邊界及未 emit 的必要字形仍缺通用來源方法。**現有完整 A 方法未取得資格；`N_CF` 未固定。**[來源評讀](pdf-core-stage1-followup-2026-10-17/A-review/summary.md) | **0** | 保存完整 A 方法的 `METHOD_STOP`／partial 證據，於 #84 交接時提出一個可實作方法或明確產品取捨；不能直接開始 A 付費推論。 |
| B，F04／F05 | [Sol 七次比較已完成](pdf-core-b-model-challenger-2026-10-18/report.md)：T04 30 列已交付、298/300 位置讀值，但 Qwen 家族錯誤影響 100 點歸屬；math 4/4。候選 `METHOD_STOP`，T03 只有離線接點證據、live 未執行。 | **0** | 提交 #84 的方法／資源／範圍決策；不自動再換模型、prompt 或表示。 |
| C，F06／F08／F11／F12 及圖片交付；F10 可選 | Image-key 同版接合局部成立；官方 FULL_PAGE OCR 修復一處 caption，但 SEAL 必要圖題仍在原 picture crop 之外，圖片增強未啟動。[C 實測](pdf-core-c-source-closure-2026-10-18/report.md) | **0** | 保存現有方法的 `METHOD_STOP`／partial；跨 owner、帶來源的輸入仍是待設計問題，不能用舊 29 圖／58 requests 當新方法的凍結預算。 |
| 同版完整配置 | 尚無 A＋B＋C 及共通必含工作的單次整合合格產物 | **0 個可啟動的整合 run** | 所有必含分支有具名可執行方法、離線 gate 與固定預算後，才進原計畫的一次整合 run。 |

## 本輪已執行順序與停止條件（歷史）

以下保留本輪的事前規劃；執行結果以上方現況與兩份報告為準，不再構成下一輪模型授權。

A／C 的「0 個已登錄下一候選」表示**下一方法尚待設計與登錄**，不是功能完成或功能 no-go。A 現在缺完整來源／重建方法；B 只是唯一已有具體下一輪模型比較的分支。下一次執行依下表進行，不採 B 跑完後才首次處理 A 的順序。

| 次序 | 工作 | 完成後的決定 |
|---|---|---|
| 1A，與 1B 並行 | A／C 共同來源與輸出責任診斷，一次最多 120 分鐘、零模型 | 各自能否登錄一個可執行方法；完整 A 仍須有獨立公式／code 品質驗證，C 仍須有獨立圖片品質驗證。 |
| 1B，與 1A 並行 | B 評讀器反例及 T03 三片段接合，合計最多 120 分鐘 | B 是否可安全進入已登錄的固定推論。 |
| 2 | 合併兩線的來源、接點與成本結果 | A／C 可登錄且 B 兩關過，才按既定上限跑 B；若必含仍無方法，先交 #84 的具體取捨，另明列 B 對 #82 的獨立價值。 |
| 3 | B 單一 challenger 最多 7＋3 次 DEV；DEV 全過才做事前凍結預算的 28 頁外部回歸 | 交付一次 B 去留結論；A／C 新方法的固定推論須各有具名方法與新預算，由 #80–#83 接手。 |
| 4 | #84 決策與交接檢查 | 必要方法／身分與交接完整則結束決策票；仍有必含無方法則作資源／範圍／停止取捨，不自動新增下一方法。 |

**A／C 共同來源檢查先開始，尚不登錄新的模型候選。**A 的「方法未合格」指完整來源發現、視覺輸入與輸出責任；公開 Core 的 fragment-order／mock 運輸接點已通過狹義控制。SEAL 第 2 頁的圖題在 `#/texts/0`、圖在 `#/pictures/0`，舊 picture crop 沒有圖題；後來的 FULL_PAGE OCR 已把完整 `RL Outer Loop Iteration t` 放進 Canonical 正文，**仍沒有把圖題放進 picture crop，也沒有重建這個圖題／圖像來源群組的 17 處 math**。這同時影響 A 的公式輸入和 C 的圖片理解輸入，但兩者的輸出與品質判準不能混算。A 來源邊界 (`pdf-core-stage1-followup-2026-10-17/A-review/figure-boundary-evidence.json`)與[C 實測](pdf-core-c-source-closure-2026-10-18/report.md)保留兩版不同的實際證據。

只用既有 Standard／FULL_PAGE 產物、頁圖與公開 provenance，做**一次有界、零模型的通用輸入方法診斷**：對 A 已凍結的八頁／44 groups／27 陰性、原 41 selected units、五個原未準備目標及所有適用的 inline／prose／code scope，連同 C 已盤點的圖片來源核對；明示 picture、相鄰文字及必要頁面視覺如何組成輸入。至少覆蓋 SEAL 圖題／圖內公式、跨 parent 的 algorithm／正文，以及普通非目標。確認來源字形真的在將送出的影像或文字中，路由不使用文件 ID／人工 oracle bbox，圖題仍在正文原位，圖片 OCR／描述仍以 image key 關聯，A 的重建須有自身可交付的 source binding。若輸入跨多個 owner，context-only 節點不可被當成可改寫 target。核對實際圖片 bytes、完整來源分母、非目標不重複，以及最壞 jobs／pixels；不能以頁圖存在、文字現在可讀或 mock 可存，推定重建成功。

這項診斷建議單次上限 **120 分鐘**，與 B 兩項離線 gate 的 120 分鐘是**分開的並行預算**；不下載模型、呼叫 API、修改私有 SDK 或開 holdout。結束時只產出兩者各自的 `METHOD_REGISTERABLE`（有通用輸入／輸出責任、來源與陰性反例、可計算的 jobs／預算）或 `NO_REGISTERABLE_METHOD`（具體缺口及成本）的決定；這是**方法登錄判斷，與上文五種執行結果不同，也不是 A／C 模型品質通過**。只有前者才能各自登錄**一個**具名方法與新預算，再由 #80–#83 接手固定推論；若仍無可實作方法，直接進 #84 產品／資源取捨，不自動開第二種 A／C 方法。

**B 同時只做既定離線兩關。**修復跨模型評讀器的合法／錯誤答案控制，並驗 T03 三個片段的公開接合；兩項合計仍受下述 120 分鐘上限約束。這些工作不依賴 A／C，可保留表格路徑的獨立價值。**付費 B 七次比較在兩條離線工作都有結論後再決定**：若 A／C 有可登錄方法且 B 兩關通過，按既定 7＋3 上限執行；若 A／C 仍無方法，先交付 #84 的整體阻擋及 B 對 #82 的獨立價值／成本，不把付費表格優化默認為完整配置的下一步。這不抹除 B 已登錄候選，也不把 A／C 的不確定當作表格模型失敗。

**唯一已登錄的下一個模型比較仍是 B。**B 的兩項離線 gate 合計上限 120 分鐘。若評讀器未就緒，模型部分記 `NOT_RUN`；T03 方法有實質缺口記 `METHOD_STOP`；時間先到記 `BUDGET_STOP`。兩關通過並經上段整體成本檢查後，保留 Standard／Heron／RapidOCR／TableFormer 與同一裁圖、prompt、schema、回填及原判準，只比較一個外部表格 VLM：`gpt-6.1-sol`。單頁最多七次；全部符合才做 T03 三次，合計最多十次 DEV 推論、零逐題重試。若 DEV 全過，再對已固定的 OmniDocBench 表格分層 28 頁作獨立有界回歸；其實際 jobs／token／時間上限須依 producer inventory 在首個請求前固定，不能假設一頁一 call。完整細節只在[B 收斂計畫](pdf-core-b-closure-plan-2026-10-18/plan-and-causal-review.md)維護；這裡不另定第二套模型或評分規則。

**B 結束就是一次整體決策檢查點。**報告 A／B／C、共通功能、同版整合的上述狀態，列所有必含 material gaps 和已量測成本。這是研究收斂點，**不是 #84 必須等 B 實測成功才可結案的條件**；若 #84 的決策與交接清單先完成，可以先結束該決策票。A、C 目前沒有已登錄的下一方法，故 B 成功也不能自動放行第三階段。新表示、模型、裁圖或跨 owner 方法若要繼續，先作**新的顯式決定**：具名通用方法、來源範圍、評分反例、最壞呼叫／時間／算力、替換哪個既有候選與終止線。不能把它稱為本輪既定計畫的續跑。若無可實作方法或合理預算，就停在具體取捨；保留已成立元件，不宣稱整體合格。

第三階段只沿原[三階段計畫](pdf-core-three-stage-plan-2026-10-17.md)執行**一次**同版整合：最多 64 頁、3 小時、精確 `N_3` 事前登錄、每 job 一次。若 A 或其他必含來源 gate 未通過，第三階段付費 run 為 `NOT_RUN`，不能用不完整資料拼成成功。六份未曝光 holdout 在方法固定前繼續封存。DEV 成功仍需另驗公司地端模型／GPU／vLLM、cloud-native 恢復及 pilot／高頻延遲，不能以 OpenAI 暫用模型替代資格認定。

## #84 只在這個條件下結案

一次 #84 決策檢查的輸出只能是以下三者之一：

| 決策 | 充分條件與處置 |
|---|---|
| **交接就緒，關閉 #84 作為決策票** | 全部 F01–F22 的必含／可選／延後、適用範圍、Canonical Markdown／同版結構／來源／provider、required-work 失敗與 Canonical Acceptance 規則固定；每個必含 stage 的可實作候選方法及所需 package／model／engine／configuration 身分已具名選定。未驗品質、成本、公司模型表現與 SLO 均列為有 owner、固定案例、通過／停止條件的 #80–#83 工作。明列取代 #72 的舊 scope 與保留部分，同步 #54／#55；實際更新 #80–#83 的過時規格，使執行者可以動手。結案文字只說**方案與交接已完成**。 |
| **產品／資源決策待定，停止自動研究** | 必含能力仍無可實作的具名方法，或需放寬必含、接受高頁級成本、追加模型／GPU／工期才能繼續。只提交一份含來源反例與成本的取捨：保留要求並批准一個新的有界方法、明確修改第一版要求、或停止／改期第一版。決定前不把 #84 當作已交付；只對**具名使用者或外部資訊**使用 `needs-info`，技術不確定本身不是反覆追加推論的理由。 |
| **明確 no-go／被取代** | 使用者決定停止或改寫第一版目標後，以具體未滿足的必含項及新 scope／後續票記錄該結果；不以「pilot 已通過」結案。 |

目前第一項的功能取捨及 delivery matrix 已記錄，但 #84 D 節的**方法／身分選定、#72 範圍對照、#54／#55 同步、#80–#83 規格更新與可執行交接**仍未全部完成。尤其現有 #80／#83 尚帶較窄的 #72 假設；#84 內「不採商業託管模型比較」也須與後來獲准的 OpenAI **僅作 DEV 暫用比較**一致，同時保留正式部署的地端開源要求。不能因本決策文件寫成，就勾掉這些未做的事項。若實際公司模型 ID 或高頻數值仍未知，要寫清 owner、取得時點及對哪個 qualification gate 形成阻擋；不能填作已驗證的 profile identity。

## Retro 後的最小環境修正

1. **最高：單一決策入口。** 研究首頁及舊三階段計畫只指向本頁；歷史結果保留原狀。每輪結束更新上表的狀態、證據與剩餘已登錄候選，防止把 `partial` 自動翻成新實驗。這是主線決策責任，不再往簡短的 `AGENTS.md` 堆規則。
2. **次高：模型費用前的評讀器反例。** B 的下一輪需有獨立合法 T04、等義 label、正確／錯誤 math、錯 header／group／pair 及 missing／extra 的控制；人工來源決定 pending 時不得通過。既有舊研究檢查入口 (`pdf-core-stage1-followup-2026-10-17/check.py`)不涵蓋新七次評讀器，應在 B 研究目錄就地加入最小 preflight，避免另造通用評測平台。
3. **後續：CI 守門。** 目前研究已有本機 compare-only 檢查，但 repo 無通用 root check／CI／pre-commit；固定路徑 runtime 尚不可攜。先完成本機可重播 gate，環境可重建後再接現有檢查入口，不把這次決策改成基礎建設專案。

此頁的 #84 條件取自[議題原文](https://github.com/davidlinnnn/data-ingestion/issues/84) D 節；A／B／C 現況取自實際輸出與三階段回顧 (`docs/reviews/pdf-core-abc-followup-2026-10-17/retro.md`)。實驗方法失敗與產品目標失敗分開記錄；本頁不是新增推論授權。
