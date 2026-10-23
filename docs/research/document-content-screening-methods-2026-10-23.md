# 文件夾帶 payload 與有害內容：偵測方法研究

日期與所有外部來源查閱日：**2026-10-23（Asia/Taipei）**。本檔服務文件內容偵測研究（#105）、量測（#106）、政策（#107）與 workflow placement（#108）；候選排序是研究建議，不是採用決定。版本、授權與官方效能數字均為查閱當日所見，非本機驗證結果。`UNKNOWN` 表示一手來源未給出足夠證據，絕不是通過。

## 摘要與研究範圍

| 類別 | 優先量測建議（研究推論；理由見各節） |
|---|---|
| 1. PDF 檔案本身的主動內容／parser 攻擊面 | PDFiD + pdf-parser 的結構訊號，與 ClamAV 的 malware signatures 互補；兩者都不能替代解析隔離。 |
| 2. 人看不到、agent 讀得到的文字 | Docling geometry／rendering-mode 檢查，加額外樣式擷取、render/OCR 差異與 Unicode properties；不能假設 Docling 有真實字色與字級。 |
| 3. 可見惡意指令或程式碼 | Prompt Guard 2 86M／22M 與自建 YARA 規則 baseline，加上 d3-mini 自訂判準（2026-10-23 補充）；Azure Prompt Shields 僅列 DEV 比較。中文 document injection 的有效性仍 UNKNOWN。 |
| 4. 色情、暴力內容 | 文字量 Qwen3Guard-Gen 0.6B／4B，圖片量 ShieldGemma 2 4B；Azure Content Safety 作 DEV taxonomy／結果比較。三者類別與分數不能互換。 |

**工作筆記／問題拆解：**第 1 類保護自己的 parser／worker；第 2 類辨識視覺與機器讀值落差；第 3 類判斷可見文字是否企圖改寫 agent 行為，並區分文件中的程式碼與實際執行；第 4 類依內容 taxonomy 辨識文字和圖片。每個候選均檢查 on-prem、繁／簡中與英文、長文件、圖片、授權、延遲／硬體、分數／門檻。這四類可重疊，不能用一個「safe」布林值抹平。

本研究沿用 [CONTEXT.md](../../CONTEXT.md) 的 Processing Profile、Enrichment Method、Canonical Acceptance 與 Processing Result。[PDF workflow v2](../design/knowledge-platform-processing-workflow-v2.md) §3 為 prepare → parse groups（Docling native parse）→ assemble → inventory → local／VLM／summary enrichment → finalize；§6 區分 extraction integrity、enrichment item failure 與 platform failure；§8 定義 Processing Result。既有「Enrichment 失敗仍可完成」規則不能自行解讀為 screening 失敗可放行，#107／#108 須決定其契約。

Pilot 為中英文研究論文 PDF，最多 64 頁；正式推論使用公司 on-prem shared GPU VLM service，雲端僅 DEV（本次任務給定條件）。[資料安全框架](knowledge-platform-data-security-aspects-2026-10-20.md) 面向 8 約束 processing egress，面向 13 涵蓋解析不可信檔案的隔離。Knowledge Platform 管接受與釋出的內容；Agent Platform 管 runtime agent defence。本次只讀文件／原始碼／論文，沒有執行 scanner 或模型，也沒有下載測試 payload。

## 1. PDF 主動內容與 parser 攻擊面

### 候選比較

此類 `zh/en` 是**不依賴自然語言的檔案結構／bytes 檢查**，不是中文語意能力；`images` 指圖片檔案／PDF image streams 的 malware 檢查，與第 4 類的圖片色情／暴力分類不同。

| candidate | what it detects | on-prem | zh/en | long docs | images | licence | latency/hardware | score/threshold | sources |
|---|---|---|---|---|---|---|---|---|---|
| A1：PDFiD 0.2.10 + pdf-parser 0.7.14 | PDFiD 計數 `/JS`、`/JavaScript`、`/AA`、`/OpenAction`、`/Launch`、`/EmbeddedFile`、`/ObjStm` 等，處理 name hex obfuscation；pdf-parser 追查 objects／references、解碼 streams／object streams。是 feature triage，不是任意 exploit detector。 | 是，Python CLI，離線讀檔。 | 結構掃描不依語言；不判斷文字意圖。 | 整個檔案／objects；不受 LLM context 限制。64 頁耗時與資源上限 UNKNOWN。 | 不做視覺語意；pdf-parser 不 render。 | 兩支原始碼均 public domain。 | CPU／Python；RAM、64 頁 p50／p95 UNKNOWN。不把「簡單」換算成毫秒。 | counts、object IDs、可自訂規則／plugin；不是校準機率。門檻由平台量測後設定。 | [作者說明][S01]、[PDFiD source][S02]、[pdf-parser source][S03] |
| A2：ClamAV（ScanPDF 開啟的本地 engine／clamd） | malware signatures／heuristics；可 decode PDF 後掃描，另有 image／image fuzzy hash 掃描。不能據此保證列出所有 active actions 或未知 parser exploit。 | 是；clamd + 本地 signature DB。DB 更新與內容掃描分開配置。 | bytes／signatures 不依語言；不分類 injection 或色情語意。 | 依 bytes、recursion、scan-time 等限制；超限可能未完整掃描，必須單獨記錄。 | 可掃 image bytes／fuzzy signatures；非視覺 moderation。 | GPLv2（官方總覽）。 | 官方 Docker 文件仍列 minimum 3 GiB、preferred 4 GiB（原文基準日期 2020-09-20）；DB reload 會增加 RAM。64 頁延遲 UNKNOWN。 | signature 名稱與 FOUND／OK／ERROR，非惡意機率；可配置 heuristics／限制；`AlertExceedsMax` 可標出部分超限。 | [功能／授權][S04]、[配置原始碼][S05]、[RAM][S06]、[掃描運作][S07] |

### 解讀與推薦

**推薦 #106 同時量 A1 與 A2。**A1 提供可定位的主動內容 feature，A2 提供 malware signature 覆蓋，兩者問題不同（研究推論，依 [A1][S01] 與 [A2][S04]）。`/OpenAction`、JavaScript 或附件存在，不等於惡意；PDFiD 作者明說 benign PDF 也能有 JavaScript，字串計數有 false positives，incremental updates 也會影響計數。[作者限制][S01] 因此應保留 action／object 的關係與掃描覆蓋，不直接用關鍵字出現次數作採用政策。

掃描器本身也會讀取不可信結構；**靜態掃描與 sandbox 的關係是偵測與限制損害的分工**（研究推論）。PDFiD 作者刻意避免完整 parsing，以降低自己的攻擊面；ClamAV 的 PDF decoding 仍是 parser 工作。[PDFiD 設計][S01] [ScanPDF][S05] gVisor 的官方說明則是隔離 application 與 host OS、縮小 container escape 風險，並不聲稱判斷 PDF 是否含惡意內容。[gVisor][S08]

給面向 13／#108 的研究建議：scanner、parser、renderer、OCR/image decoder 都納入隔離邊界，限制 CPU／RAM／時間／解壓量，使用最小檔案存取與無不必要網路權限；sandbox 型態及額外延遲須由該票驗證。這不是本研究新增的正式 gate，也不表示 A1/A2 clean 就能免隔離。找不到一手證據可證明本表任一候選能完備偵測任意刻意構造的 parser exploit；此能力為 **UNKNOWN**。

ClamAV 的超限與錯誤不可算 clean：原始配置有 `MaxFileSize`／`MaxScanSize`／`MaxRecursion`，`AlertExceedsMax` 預設關閉；官方也提醒 malware alert 可能是 false positive。[配置][S05] [alerts FAQ][S09]

## 2. 視覺隱藏文字與不可見 Unicode

### Docling 實際提供什麼

以下核對 **2026-10-23 的 upstream `main` source**，不是本 worktree runtime 的版本保證；採用前須 pin Docling、docling-core、docling-parse 及 backend，再做契約探測。

| 層級 | 實際欄位／限制 | 能做什麼、還缺什麼 | 一手來源 |
|---|---|---|---|
| `DoclingDocument` 的 `TextItem` | `orig`（untreated）、`text`（sanitized）、optional `formatting`；Formatting 只有 bold、italic、underline、strikethrough、script。 | 沒有可直接使用的 foreground/background color、font-size 或 opacity 欄位。`orig` 是該 item 的未處理文字，不是整份 PDF 全部 content streams。 | [TextItem][S10]、[Formatting][S11] |
| Source Evidence 定位 | `ProvenanceItem.page_no/bbox/charspan`；`PageItem.size/image/page_no`。 | 可回指頁面／區域、取 render crop；不能保證每個字元都有 bbox，也不能靠最後 assembly 推定所有被 parser 丟掉的文字。 | [reference models][S12] |
| 底層 `TextCell`／`PdfTextCell` | oriented `rect`、text／orig、font_key／font_name、rendering_mode；mode 3 是 INVISIBLE，mode 7 是 ONLY_CLIPPING。沒有 explicit font_size。 | rect 高度只能當幾何 proxy，不能冒稱 PDF 原始字級。底層結果需額外保存，不能假設會完整進入上層輸出。 | [page models][S13] |
| `rgba` 的陷阱 | schema 有 `ColorRGBA`，但 `_to_cells_from_decoder` 把每格填成預設 rgba；預設為黑色、不透明。 | **不能以欄位存在證明抽到了真實字色／alpha。**目前查到這條路徑不足以直接做白底白字偵測；其他 backend／版本是否提供，UNKNOWN。 | [page models][S13]、[parser mapping][S14] |
| 頁界 | parser mapping 讀 CropBox／MediaBox，建立 page geometry。 | 原始 page boxes 可支援頁外訊號；要檢查抽取前是否已裁掉或正規化座標。不能只掃最後 Markdown。 | [parser mapping][S14] |

以上是程式碼層級的觀察／推論，**沒有執行任何 Docling 轉換**；尤其「沒抽到」不能推導為「沒有隱藏文字」。

### 候選比較

| candidate | what it detects | on-prem | zh/en | long docs | images | licence | latency/hardware | score/threshold | sources |
|---|---|---|---|---|---|---|---|---|---|
| B1：Docling geometry／rendering-mode 規則 + PyMuPDF `get_texttrace()` 樣式補足（組合方法） | 頁外 bbox、極小幾何、invisible render；PyMuPDF 另回 color、size、opacity、type、seqno，可提示透明或被後畫物件遮蓋。低對比需另對照區域背景，不能只看白字。 | 是；規則需自行實作。 | 幾何／樣式不依語言；文字是否正確 decode，zh/en 都需測。 | 逐頁／span，無模型 context 限制；跨頁一致性需自建。 | 檢查 PDF 文字繪製與物件，不辨認圖片內文字；需 B2/OCR。 | docling-core／parse MIT；PyMuPDF AGPL 或 commercial。整組相依授權須核對。 | 本地 CPU 路徑可行；64 頁延遲、RAM UNKNOWN。 | 原始幾何／樣式值與 rule hits；size、opacity、contrast、off-page 比例可調，不是機率。 | [Docling][S13] [mapping][S14]、[PyMuPDF API][S15]、[授權][S16] [S17] [S18] |
| B2：PhantomLint／render-vs-native OCR Consistency Test | 抽取 text block、render 對應區域、OCR 後比較缺少的文字，再與 suspicious phrase spans 相交；可找同色、遮蓋、tiny、off-page、clipping 等。 | 是；Python、Tesseract、Poppler、PyMuPDF 等；需預置模型，研究不是部署驗證。 | 英文有論文評估；原始 OCR 呼叫未傳 `lang`，預設語句表英文。中文 turnkey 能力 UNKNOWN；Tesseract 有 eng／chi_tra／chi_sim，可改接但需驗證。 | 依頁／block 處理；論文有多頁 PDF，64 頁上限與效能 UNKNOWN。 | render 圖供 OCR；不是一般圖片 injection／色情分類器。 | PhantomLint BSD-3-Clause；PyMuPDF 仍 AGPL／commercial；Tesseract 及 tessdata_fast Apache-2.0。相依套件不是一律 BSD。 | 論文 M1 Pro、16 GB RAM：ICML PDF 平均 68.25 秒／篇；非 p95、非公司硬體。 | CLI `--threshold`（預設 0.75）調語句相似度；輸出 suspicious／hidden spans，非校準 document probability。 | [論文 §3–5][S19]、[README][S20]、[CLI][S21]、[OCR code][S22]、[licence][S23]、[Tesseract][S24] [S25] [S26] |
| B3：Unicode UCD properties 規則（自建） | `Default_Ignorable_Code_Point`、`Bidi_Control`，另記錄 tags／variation selectors／zero-width runs，保存 code point 與原文 offset。 | 是；表格／regex／字元迭代即可；不是現成惡意意圖分類器。 | property 比對不依語言；中英文均可，但正當 variation／joining 用法須分辨。 | 線性掃字元是建議實作；可串流，跨 chunk run 要接續。 | 只處理抽取／OCR 文字，不能從 pixels 找不可見字元。 | Unicode data／software：Unicode License V3；自建程式授權另定。 | CPU 可行（研究推論）；特定 runtime 吞吐／RAM UNKNOWN。 | code-point hit／run length／density 可自訂；無官方 maliciousness score。 | [UAX #44][S27]、[UTS #39][S28]、[Unicode licence][S29] |

### 解讀與推薦

**推薦 B1 + B3 做可定位 baseline，B2 作獨立差異訊號一起量測。**這是依介面與覆蓋範圍的研究排序，沒有證明其中一個可單獨當 gate。B1 的低對比、字級、遮蓋門檻應輸出可解釋數值；文字與背景相同只是 visibility 訊號，不是 malicious intent。PyMuPDF 文件明示 opacity／ignored text／後畫物件的 seqno 可協助找 invisibility，但 bbox overlap 仍只是遮蓋推測。[API][S15]

B2 的一手先例是 PhantomLint 的 OCR Consistency Test。其研究在 3,257 篇 ICML PDF 中有 3 個 false positives（約 0.092%），原因包括 OCR 失敗與小字；這個數字只屬於該 corpus／配置，不能當繁中論文的 FPR 或保證。論文的 text-only prompt detection 也明確指出，討論 injection 的論文本身可被誤判。[PhantomLint][S19] **原生文字與 OCR 不一致須記為 discrepancy**：OCR 認錯、合法 searchable text layer、公式、雙欄對齊均應列入 #106 負例與誤差分析，不能直接判成攻擊（研究建議）。

PhantomLint 是研究 prototype，不能直接當 production-ready：查閱當日 CLI 宣告 `--bad-list`，但對應分支讀取 `args.injection_list`；這是原始碼可見的名稱不一致，未在本次執行重現。中文詞表／OCR adapter 的試驗需先確認這條路徑，不能只傳參數就算完成中文支援。[CLI source][S21]

B3 以 Unicode 18.0.0 UCD／UTS #39（查閱當日版本）為規格依據，**不把 identifier security profile 原樣當文件拒絕規則**。UTS #39 明說某些 Default_Ignorable 的 joining controls 是正當文字顯示所需。[UTS #39][S28] 建議保留原文，只額外產生 escaped view／code-point spans；是否正規化、刪除或拒絕由 #107 決定。

## 3. 可見惡意指令或程式碼

### 候選比較

| candidate | what it detects | on-prem | zh/en | long docs | images | licence | latency/hardware | score/threshold | sources |
|---|---|---|---|---|---|---|---|---|---|
| C1：Llama Prompt Guard 2 86M／22M（open-weight classifier） | explicit instruction override／已知 injection、jailbreak patterns；binary benign／malicious，不預測攻擊是否成功，也不是 malware／色情分類器。 | 是，可載入本地權重；公司服務能否承載此 classifier 尚需確認。 | 官方評估 en、fr、de、hi、it、pt、es、th，**未列 zh**；86M 有 multilingual pretraining，22M 沒有。繁／簡中效能 UNKNOWN。 | 512 tokens；需切段，禁止只截前段。跨段 intent UNKNOWN。 | 否；只能另以 OCR 接文字，pixel-only 攻擊未覆蓋。 | Llama 4 Community License + AUP；非 Apache／MIT，下載與使用有條件。 | 官方 A100 GPU、512 tokens：86M 92.4 ms／次、22M 19.3 ms／次。CPU 延遲、最低 RAM／VRAM、64 頁吞吐 UNKNOWN。 | 可取 logits；平台可由分類分數訂 threshold，須自己校準；不是已校準的文件攻擊成功率。 | [model card][S30]、[licence][S31] |
| C2：Azure AI Content Safety Prompt Shields，standalone `2024-09-01` API | `documents` 的 indirect document attack patterns；另有 `userPrompt` 分析，兩者不可混用。不是內容有害性或 provenance 驗證。 | 所查候選為 Azure managed API；沒有找到可下載的地端版本。PROD 不符合本案前提。 | 官方主要以英文訓練／評估；有 multilingual 能力描述，zh 品質 UNKNOWN。 | prompt ≤10K characters；最多 5 documents，documents **合計** ≤10K characters，需切段。 | 否，Prompt Shields 為 text-only。 | 雲端服務契約／用量計費，非開源權重授權；本案合約細節 UNKNOWN。 | 遠端服務；client 無本地推論 GPU 需求。官方未提供本工作負載的 p50／p95 或硬體規格，UNKNOWN。 | 每個 document 回 `attackDetected` Boolean；此 API 未見公開連續 score／可調 numerical threshold，UNKNOWN；應用可自行決定後續處置。 | [概念][S32]、[限制／語言][S33]、[API example][S34]、[FAQ][S53] |
| C3：YARA 4.x + 自建 document-text 規則 | 字串、hex、regex、條件組合；可標記指令覆寫措辭、疑似外洩要求、下載後執行的 code pattern。**規則是待建 baseline，非 YARA 已提供的 injection detector。** | 是，CLI／library；只讀文字，不執行 code。 | 英文 patterns 可直接寫；中文要指定 UTF-8 bytes／escapes 及詞形。YARA `wide` 不是通用 Unicode 語意能力。 | 沒有 token context 上限；全檔／分塊由整合決定，要設定 timeout 與資源限制。 | 不理解 pixels；需 OCR，亦不解壓整份 PDF 的語意文字。 | engine BSD-3-Clause；自建／外部 rules 的授權分開。 | CPU 路徑；吞吐取決於 rules／regex，64 頁 p95／RAM UNKNOWN。 | rule IDs、matched strings／位置、條件；自訂 counts／組合門檻，非校準 probability。 | [rules／Unicode 限制][S35]、[CLI][S36]、[licence][S37] |

### 解讀與推薦

**推薦先量 C1 的兩種大小，並保留 C3 作解釋性 baseline；C2 僅是經面向 8 允許時的 DEV 對照。**86M 的 multilingual base 是優先比較理由，不能當作繁中通過證據；22M 的官方延遲較低，應以同一測試集測其漏判交換。C1 model card 自述會受 adaptive attacks、application-specific distribution 影響。[Prompt Guard 2 限制][S30] C3 應記錄規則版本／span，不把一般 SOP 的下載執行範例或資安教學直接判成惡意（研究建議）。

**可見的危險程式碼與 injection intent 要分開標註。**文件可能只是引用程式碼；一個 guard 說「沒有 instruction override」不能證明 shell 片段無害。反過來，命中下載後執行的 pattern，也不能證明文件要求本平台執行它。C1 的定義只涵蓋 explicit override，C3 只是 pattern matching。[C1 scope][S30] [C3 mechanics][S35] 本次未找到一手證據，證明任何本表候選可完備判定任意中英文 SOP／code 的惡意性，故這項能力為 **UNKNOWN**。

文件篩檢仍會遇到「談論攻擊」與「發動攻擊」同文同句的歧義：PhantomLint 明確以包含可見攻擊語句的研究論文說明 false alarms；NotInject 則專門評估 benign trigger-word inputs。[PhantomLint §3][S19] [NotInject][S39] 因此 #106 須加入引用、否定、安全教育、論文範例，並分開報告 **intent label、visibility label、code-risk feature**，不要把「提到 ignore／system」當 ground truth（研究建議）。

### 公開 indirect injection benchmark 與已知限制

下表只讀論文與 benchmark 說明，**沒有下載 corpus**。公開、可讀不表示可把其 payload 或素材放入本 repo。

| benchmark／一手報告 | 與文件篩檢的關聯／可借用設計 | 作者報告的結果與界線 |
|---|---|---|
| BIPIA，論文 v4（2025-01-27） | 外部內容中的 indirect attacks；email QA、web QA、table QA、summarization、code QA，並變更 attack 在開頭／中間／結尾的位置。 | 25 個受測 LLM 都有不同程度脆弱性；作者的 defense 結果是在特定任務與模型下的 ASR。**不是 PDF 檔案解析／visibility benchmark，也不是 detector recall。**本案 zh／64 頁／圖片覆蓋 UNKNOWN。 [paper §4–7][S38] |
| NotInject／InjecGuard，論文 v3（2025-03-30） | 339 個 benign samples，刻意包含 attack trigger words，測 over-defense；適合 hard negatives 的設計。 | 當時受測的 Deepset、Fmops、PromptGuard、ProtectAIv2 有明顯 over-defense；例如 ProtectAIv2 over-defense accuracy 56.64%。這是**當時版本與資料集**，不能移植為 Prompt Guard 2 的 FPR；NotInject 亦不是長 PDF benchmark。 [paper §3、5][S39] |
| LLMail-Inject，論文 v1（2025-06-11） | adaptive email-borne injection，含 retrieval、外洩／工具呼叫目標；可取設計作文件片段壓力測試。 | Table 3 在「已觸發指定 tool call 的攻擊子集」上，Prompt Shield v2 recall 為 phase 1 **0.678**、phase 2 **0.487**；不是所有提交或今日 API 的 recall。作者指出目標有限、部分標籤依賴 LLM，不建議直接以該資料訓練。 [paper §4.5、6][S40] |
| CrackedPDFs，**v2**（2026-08-02） | 29,322 個 generated PDF、paired benign-confounder controls、按來源切分；專門保留文件結構，連結第 2／3 類。 | 2,919 份 held-out test 的 hybrid F1 **0.960**；v2 把 973+973 balanced subset 的 **95.9% classification accuracy** 與 **100% paired score ordering** 分清楚，不能引用舊摘要混稱。作者明說未證明 broad real-world robustness／cross-family generalization；本案繁中覆蓋 UNKNOWN。 [v2 abstract][S41] |

### 補充：d3 決策模型（自訂判準型 judge）

d3 是 vLLM Semantic Router 的 Decision 3.0 系列（0.6B 至 27B，Apache-2.0，可地端部署）。它不是專用安全分類器：由平台自己寫問題與選項定義，模型對每個選項回傳機率、不生成文字。#84 已用它產生 enrichment 的佐證分數，見 [W4b 報告](pdf-core-w4b-d3-2026-10-20/report.md)。

| 面向 | 狀況 |
|---|---|
| 長文件 | d3-nano 上下文 262,144 tokens，不需要像 C1 切成 512 tokens |
| 圖片 | 支援，同一模型可問文字與圖片題 |
| 自訂判準 | 可直接把政策寫成判準，例如區分「指示 AI 讀者行事」與「討論攻擊」 |
| 公開安全評估 | 模型卡只有 Hateful Memes moderation（d3 43.9、d3-lite 11.8、d3-edge 6.8）；沒有 prompt injection 評估 |
| 自身可被影響 | 它讀取整段不可信內容；小規模試跑中，一段繁中「對分類器下指令」的句子讓 nano 的判斷從 0.952 掉到 0.479 並改選 `neither`，mini 不受影響 |
| `confidence` 欄位 | HF 套件路徑是 1 − normalized entropy，vLLM 端點是 max(p) × label_mass；判斷一律讀 `probabilities`／`noul` |

試跑（24 段合成短文，nano 與 mini，本機 MPS）：mini 全部判對，nano 錯一段；這不是 FP/FN 量測。細節見 [d3 probe 報告](document-content-screening-methods-2026-10-23/d3-probe/report.md) 與 [Part A](document-content-screening-methods-2026-10-23/d3-probe/part-a.md)。

**推薦：d3-mini 列入 #106 第三類候選，與 C1 在同一份資料上比較；測試集加入針對分類器本身的指令（含中文與改寫變體）。**d3 也可在同一次呼叫中加問品質題，作為不擋件的 tag；是否合併由 #108 決定。第四類的公開證據偏弱，只作對照。

AgentDojo 是 runtime agents 在 untrusted tool data 上的任務／攻擊環境，可提醒量測要區分 utility、detector error 與 attack success；完整 runtime 防禦評估由 Agent Platform 負責，非本票範圍。[作者論文 v3][S42]

同理，Spotlighting／TaskTracker 需改動下游 prompt 或讀取模型內部狀態，屬 runtime defence；本票只記其與 document-side screening 的界線，不推薦把它們做成文件靜態分類器。[Microsoft 說明][S32] [LLMail-Inject §2.2][S40]

## 4. 文字／圖片色情與暴力

### 候選比較

| candidate | what it detects | on-prem | zh/en | long docs | images | licence | latency/hardware | score/threshold | sources |
|---|---|---|---|---|---|---|---|---|---|
| D1：Qwen3Guard-Gen-0.6B／4B | 文字 safety classification：Safe／Controversial／Unsafe + harm categories；官方介面是 user prompt／model response moderation，不是已驗證的文件 admission classifier。 | 是，Transformers／vLLM 等本地部署；shared service 支援性 UNKNOWN。 | 作者報告中英文及 multilingual 評估、支援 119 languages／dialects；繁中論文專屬評估 UNKNOWN。 | 兩個 config 的 max_position_embeddings 為 32,768；不是 64 頁安全有效長度保證，仍應切段並保留上下文。 | 否，所查 Gen 為 text model；圖片需 OCR + D2。 | Apache-2.0（模型發布／技術報告）。 | 0.6B／4B；config 為 bfloat16。最低 RAM／VRAM、Gen 的本案延遲 UNKNOWN；不能把 Stream latency 當 Gen latency。 | 預設輸出類別文字，未見標準 calibrated probability。strict 把 Controversial 當 unsafe，loose 當 safe；這是 label mapping，非連續 threshold。 | [README][S43]、[model card][S44]、[configs][S45] [S46]、[report][S47] |
| D2：ShieldGemma 2 4B，`google/shieldgemma-2-4b-it` | 單張圖片的 Sexually Explicit、Dangerous、Violence/Gore policies。 | 是，公開權重與本地 inference example；須接受 Gemma terms。 | policy／訓練設定為 English only；無文字的圖片不需 zh tokenizer，但**圖中文字、中英文混合語意能力 UNKNOWN／有明確限制**。 | 逐 picture／page image，不是整份 PDF 輸入；需切出圖片並量測小區域漏判。 | 是，natural／synthetic 單圖；不是 interleaved text+image document reasoner。 | Gemma Terms of Use；非 Apache 模型授權。 | 4B，本地 single／multi-GPU example；最低 inference VRAM、CPU 延遲、每圖 p95 UNKNOWN。TPUv5e 是訓練硬體，非 inference requirement。 | 每個 policy 的 Yes／No token probability；可自行調 threshold，須在目標圖片上校準。 | [model card][S48]、[官方權重／範例][S49]、[paper][S50]、[terms][S51] |
| D3：Azure AI Content Safety Analyze Text／Analyze Image（standalone API） | Hate／Sexual／Violence／Self-harm，文字與圖片有各自 severity。 | 所查為 Azure managed API；未找到本候選的地端權重發佈。DEV-only 對照。 | text classifiers 官方 trained／tested 含 Chinese、English；繁／簡中與論文領域各自品質 UNKNOWN。圖片中文字的綜合語意不應由此推定。 | Text 預設最大 10K characters，需切段；非 PDF input。Image ≤4 MB，50×50 至 7200×7200，需拆圖／render。 | 是；純 Analyze Image 與 image+text multimodal preview 是不同 API／能力，不可混稱。 | 雲端服務契約／用量計費；本案合約細節 UNKNOWN，非開源模型。 | 遠端 managed inference；本地不用推論 GPU。64 頁與每圖 p50／p95、服務 hardware UNKNOWN。 | Text 可回 0–7 或 trimmed 0／2／4／6；Image 回 0／2／4／6；平台可設 severity cutoff，**不是 probability**。 | [taxonomy][S52]、[limits／language][S33]、[FAQ][S53] |

### Taxonomy 不可互換

| candidate | 原生 taxonomy 與本題關聯 | 需要政策票決定的差異 |
|---|---|---|
| D1 Qwen3Guard | Violent、Non-violent Illegal Acts、Sexual Content or Sexual Acts、Personally Identifiable Information（輸出範例用 PII）、Suicide & Self-Harm、Unethical Acts、Politically Sensitive Topics、Copyright Violation；prompt moderation 另有 Jailbreak label。Violent 包含 depiction 與暴力指引。 [policy／範例][S44] | 保留各 category 的原始輸出；與本題無關的類別不能默默成為拒絕政策。Jailbreak label 不等於已通過 indirect document injection 量測。 |
| D2 ShieldGemma 2 | Sexually Explicit、Dangerous、Violence/Gore；Violence/Gore 的定義偏向 shocking／gratuitous violence，Dangerous 包含鼓勵／協助造成現實傷害。 [policy][S48] | 一般暴力敘述、醫學圖片、論文中的安全研究，不一定等於這組 policy 的違規。更換自訂 policy 後效果也要重測。 |
| D3 Azure | Hate／Sexual／Violence／Self-harm；各自有 severity 定義，文圖刻度不同。 [categories][S52] | Sexual 詞彙範圍較廣，提及敏感主題不等於高 severity；不能把所有非零值直接當色情／暴力拒絕。 |

### 解讀與推薦

**推薦 #106 量 D1（文字，0.6B／4B 對照）與 D2（圖片）組合；D3 是 DEV 對照，不是正式採用建議。**D1 有中英文 moderation 的一手評估，D2 有明確的圖片 policies 與連續分數，兩者互補。[Qwen report][S47] [ShieldGemma 2][S48] 但 submitted document 是 source content，和聊天中的有害請求／模型回覆分布不同；D1 的 document-mode adapter、policy prompt 與 aggregation 都是待驗證實驗，不能直接沿用其 chat benchmark 數字（研究推論）。

ShieldGemma 2 作者明列三項限制：圖上文字與視覺互動形成的 harmfulness 不在本工作範圍、只做 single-image classification、不曾對其他 policy 專門 fine-tune。[paper §7][S50] 因此需另跑中英文 OCR text screening，並保留「只有組合語意才有害」的漏判測試；不以一張 benign score 代表該頁或整份文件通過。Azure 的文字／圖片 classifier 亦會有 FP／FN，safe 不代表其他風險不存在。[官方限制][S52]

對醫學、歷史、新聞、安全研究與文學內容，**content presence、context、severity、platform policy disposition 分開標註**（研究建議）。D1 的 Safe／Controversial、D2 的 probability、D3 的 severity 既不同量綱也不同政策，不應取平均得到單一安全分數。

## 共通條件的整體結論

| 條件 | 結論與必須保留的限制 |
|---|---|
| 正式 on-prem | A1／A2、B1–B3、C1／C3、D1／D2 有本地工具／權重路徑；這是可行性，並未證明公司 shared VLM service 能服務 classifier／scoring。C2／D3 只留 DEV 對照，送出文字、crop、page image 都受面向 8 約束。依據為各候選 sources 與 [repo 安全框架](knowledge-platform-data-security-aspects-2026-10-20.md)。 |
| 中英文 | structural／Unicode 規則不依語言，仍受抽取品質影響；B2 原樣不是已證明的中文方案。C1／C2 中文 injection 品質 UNKNOWN；D1 有中文 benchmark、D3 text 有 Chinese trained/tested，但兩者繁中論文品質仍 UNKNOWN。D2 不能作中英文圖文聯合理解的保證。 [B2][S22] [C1][S30] [Azure][S33] [D1][S47] [D2][S50] |
| 長文件 | A／B 以檔案、頁、span 為單位；C1 512 tokens、C2 documents 合計 10K characters、D1 config 32,768 positions、D3 text 10K characters。page count 不是 token count；64 頁不能直接整份塞入模型。 [C1][S30] [Azure][S33] [D1 config][S45] [S46] |
| 切段與聚合 | **研究建議：**按 Source Evidence 保留頁碼／bbox／原文 offset，再以實際 tokenizer 的窗口切段（預留 template 與 special tokens），測 overlap、跨段／跨頁指令、頭中尾和尾端 append。每段都要有 outcome；max／any-hit 等 document aggregation 要另測，不能把 chunk FPR 當 document FPR。不要只掃摘要，否則未進摘要的片段沒有 coverage。 |
| 圖片 | 第 1 類 image byte scanning ≠ moderation；C1／C2／C3 不直接看 pixels。D2／D3 圖片分類，B2／OCR 可補圖片內文字；整頁縮圖與 picture crop 應分開量測。圖文組合語意仍有缺口。 [ClamAV][S05] [Prompt Shields media][S53] [ShieldGemma 限制][S50] |
| 授權 | public domain／MIT／BSD／Apache、AGPL／commercial、Llama 4、Gemma、Azure service contract 是不同條件；授權如各表，查閱日 2026-10-23。模型、engine、OCR data、相依套件、rule set、測試集應分開記錄；本報告未作法律合規判定。 |
| 延遲／硬體 | 只有表中明列的作者測量能引用：C1 A100 per-512-token latency、B2 M1 Pro per-document mean、A2 舊基準 RAM guidance。其餘本 workload p50／p95、最低 memory／VRAM 都為 UNKNOWN。不能以 parameter count、訓練 TPU 或 provider 宣稱低延遲填補。 [C1][S30] [B2][S19] [A2][S06] |
| 分數／門檻 | A／B／C3 多是 feature／hit；C1 logits／分類分數；C2 Boolean；D1 文字 labels；D2 probability；D3 ordinal severity。皆不能視為跨工具可比較的機率。可調條件不等於已有可用 production threshold。 [C1][S30] [C2][S34] [C3][S35] [D1][S44] [D2][S48] [D3][S52] |
| error／缺覆蓋 | **研究建議：**encrypted／malformed／超限／timeout／OCR failure／missing modality／schema failure 都保留獨立狀態與原因，不寫成 negative。UNKNOWN 永不自動變 pass；是否 retry、review、拒絕或停止 Canonical Acceptance 由 #107／#108 定義。 |

## 給 #106 的量測建議

以下是**建議的量測設計**，不是已執行的測試，也不是 #107 的正式門檻。

### 候選與實驗順序

1. 先確認 Docling／backend 的 visibility 欄位契約、OCR coverage 與 scanner 超限回報；不完整時，先報 coverage gap，不進行「全文件安全」評分。A1 明確開啟 pdf-parser object-stream inspection（`--objstm` 預設關閉）。 [option source][S03]
2. 同一批檔案比較 A1、A2；同一批 paired pages 比較 B1、B2、B3；對各單項與聯集分別計數。B2 中文需接上 `chi_tra+chi_sim+eng`／對應語言 OCR，並驗證文字切分／diff，不沿用英文 word diff 就稱支援中文。Tesseract 官方列出這些 language data，亦支援多語參數與 TSV bbox／confidence。[languages][S24] [CLI][S54]
3. C1 86M／22M 用相同 document chunks 與 tokenizer budget 比較，C3 先固定一版規則；依 #107 給的候選 FPR 預算做 operating-point curve，不在 test set 選 threshold。C2 如後續允許雲端 DEV，再補比較；本次不呼叫。
4. D1 0.6B／4B 先比較中文／英文 chunk moderation 及 strict／loose mapping；D2 比較 picture crop、page render、OCR text 的互補與漏判；D3 如後續符合面向 8 再補 DEV 對照。
5. 單項 baseline 完成後才測整組連用的 document FPR、缺覆蓋率與額外 latency；不能從單項數字相乘或把所有 signal 直接 OR 後假設可接受。

### 測試集組成

| stratum | 建議內容／配對方式 | 必須回答的問題 |
|---|---|---|
| 真實 benign pilot | 建議先備至少 **300 份獨立 benign Documents**：英文 100、繁中 100、簡中 50、中英混合 50；pilot 不足則補合法公開／自有 benign 論文，明列選樣差異。依 1–4、5–16、17–32、33–64 頁分層；另列 scanned／born-digital、雙欄、公式、圖片密集、OCR text-layer。此數量是起始設計，不是證明低 FPR 的充分條件。 | 每語言／頁數的 document false alarms、處理失敗與 p95；不要只測簡短英文 attack strings。 |
| 第 1 類 feature fixtures | 安全合成的 action／attachment 結構、hex-obfuscated names、object streams、incremental updates、加密／損壞／資源限制；每種搭配功能相近的 benign control。只用 inert／不觸發實際系統操作的 fixtures。 | feature detection、object 定位、active-content false alarms、限制是否確實回報；**此集不能證明真實 exploit recall**。若日後另有受控 malware corpus，測試環境與素材管理交由資安程序，結果明確另列。 |
| 第 2 類 matched visibility | 每個 base document 產生 visible／hidden／benign hidden OCR-layer 三聯；涵蓋白底白字、彩色背景低對比、tiny text、頁外 CropBox／MediaBox、mode 3／7、透明／遮蓋／OCG、clipping、font mapping；繁中、簡中、英文同樣設計。Unicode 包含 tags、zero-width、bidi、variation-selector runs，並放合法 joining／variation／emoji controls。 | 能否指出原始 span／頁位置；原生抽不到時有沒有被誤當 clean；benign 隱藏文字能否與 malicious intent 分開。設計借鏡 [PhantomLint][S19] 與 [CrackedPDFs][S41]，不是下載它們的 payload。 |
| 第 3 類 indirect attacks | 採 BIPIA 的任務／位置分層與 LLMail 的 adaptive／外洩目標設計；在研究論文、SOP、引用段落、註腳、表格、code block、圖片 OCR 中測試指令覆寫、角色冒充、外洩要求、編碼／Unicode／多語改寫。長文加單一尾端片段、跨 chunk 與跨頁拆分，保留完整上下文。 | detector recall 與 localization；attack span 單獨評分 vs 藏在長文的評分差距；不可把 downstream ASR 當文件 detector recall。 [BIPIA][S38] [LLMail][S40] |
| 第 3 類 hard negatives | NotInject 的 trigger-word benign 類型；另加資安論文討論 prompt injection、安全教育的警告／否定句、quoted examples、正常 SOP 的命令範例、文學角色對話、合法資料傳輸。visible 與 hidden 版本分開標註。 | 尤其繁中與英文的 false positives；「提及攻擊」不能預先標成 attack。 [NotInject][S39] [PhantomLint][S19] |
| 第 4 類 text／image | 分 Sexual 與 Violence，涵蓋 presence／instruction／depiction、程度、單一類別與重疊；自然照片／插圖／合成圖分層。合法醫學、歷史、新聞、藝術、研究討論作 context controls；圖片內中英文、圖文單看 benign 但合起來有害的案例另列。只以日後獲准的合法受控材料量測，本次不取得或產生素材。 | taxonomy agreement、per-class precision／recall、FP 的 context 原因；text-only、image-only、OCR+image 各自 coverage。ShieldGemma 的圖文限制必須單列。 [D1 policy][S44] [D2 limits][S50] [D3 taxonomy][S52] |
| 掃描失敗／不完整 | timeout、service unavailable、malformed／encrypted、圖片尺寸／token 超限、OCR 空輸出、模型拒答／無效 schema、某頁／某圖漏排。 | missing outcome 與 legitimate negative 可否區分；error 不得納入 true negatives。 |

數量配置建議：synthetic visibility／injection 每個方法 × 語言至少以數個**不同 base Documents**起步，先找失效模式，再擴到足以給信賴區間的 held-out set；不假定同一 PDF 的 100 個變體就是 100 份獨立樣本。以 base Document／來源／attack family 切 train/calibration/test，翻譯與排版變體不可跨 split；另外留未見 attack family 測 generalization。這項設計參考 CrackedPDFs 的 provenance splits／paired controls，但不採用其分數作本案目標。[CrackedPDFs][S41]

### 指標、記錄與交付給政策票的資訊

- 先保留 ground truth 多軸標籤：active feature、visibility、instruction intent、code-risk pattern、harm category／severity／context；兩位評註者獨立判讀爭議樣本，再記錄裁決。`uncertain` 不硬塞 benign。
- 以 **document、page、chunk／span、picture** 分別報告 TP／FP／FN／TN、precision／recall、FPR、coverage／未完成率、分母與信賴區間；每語言、頁長、attack family、harm category 分層。分數模型畫 precision–recall／threshold curve，另報固定 benign document FPR 下的 recall；Boolean API 只報其 operating point。
- benign 按實際分布取樣與 balanced challenge set 分開報告；測整份文件 any-hit 聚合後的誤報，不以 chunk 層好看就結案。可定位訊號報原始 span／bbox 命中情況與 reviewer 工作量。
- runtime attack success 不是此票的 pass 指標。若量測 VLM／summary 是否被影響，只能在**無真實副作用**的受控下游任務記錄為額外實驗；需要 runtime defence 的部份交 Agent Platform。
- 效能記 cold／warm p50／p95、每頁／圖／chunk 與整份 64 頁耗時、CPU、peak RSS、GPU／VRAM、batch、dtype／quantization、token count、DPI／pixels、排隊時間、併發與 error／timeout；公司 shared GPU 的 queue 與模型 compute 分開。不要把 paper mean 當服務 SLO。
- 每次 run 固定 scanner／DB digest、model revision、tokenizer、rule set、OCR language data、renderer／font、threshold／label mapping、chunk／overlap／aggregation、Processing Profile 版本及實際 inputs digest。Azure 官方說模型持續更新，不能僅靠 API version 假設模型不變，故另記日期／region／response metadata。[Azure FAQ][S53]

**公開 repo 的材料邊界：真實惡意檔案與有害內容永遠不得提交，包含 payload 原文、raw model output、rendered pages／crops／screenshots 與可還原它們的 encoded copy。**此處是本次任務要求及 [workflow v2 §11](../design/knowledge-platform-processing-workflow-v2.md)「reports／case lists／hash manifests 留 git、raw outputs 在外」的量測延伸。repo 只留無害案例描述、版本／digest manifest、聚合指標與經檢視的非有害 evidence；受控素材與原始輸出使用獨立受限儲存，不以 dataset 公開為豁免。採樣、授權與素材取得由 #106 另行落實，本研究未執行。

## 給 #107／#108 的交接，不是 placement 決定

研究推論：第 1 類與 scanner／parser／renderer 的面向 13 隔離有關；第 2 類需要保留原生幾何和 page pixels；第 3 類會影響平台自己的 VLM／Document Summary；第 4 類則需文圖雙路。若只在 finalize 才掃描，先前 enrichment 可能已接觸來源內容；若在 parse 前只掃 bytes，又無法完成語意／render 差異檢查。這些是 #108 應比較的資料依賴，**本檔不指定 gate stage**。依據為 [workflow graph／inputs](../design/knowledge-platform-processing-workflow-v2.md) 與本報告各候選介面。

建議將篩檢結果保留 method／model／rule 版本、actual inputs、範圍、coverage、signals／score、頁碼／bbox／span、原始 taxonomy、失敗原因及證據 reference；是否列為 Enrichment Method、Processing Result 新欄位或獨立治理證據，由 #108 決定。Processing Profile 的方法與規則變更須可追溯，不能把既有 accepted Canonical Revision 靜默改寫；完整候選與固定 revision 的既定原則見 [ADR-0001](../adr/0001-complete-candidate-canonical-acceptance.md)、[ADR-0003](../adr/0003-immutable-accepted-canonical-revisions.md)。

由 #107 決定的問題包括：哪些 feature／類別屬禁止、哪些允許帶 limitation、研究／醫學／教育例外、閾值／review 區間、缺覆蓋／error disposition、保留原文或另產衍生視圖、既有接受內容的重評規則。偵測訊號與 Canonical Acceptance／釋出處置分開；本研究不作採用決定。

## 開放問題與 UNKNOWN

- Docling 最終採用版本／backend 能否完整保留隱藏 cells、原始頁界與真實字色／字級，尚未執行驗證。
- 公司硬體上的 64 頁 p50／p95、CPU／RAM／VRAM、shared GPU 排隊成本、classifier／scoring serving 能力，全部 UNKNOWN；本研究沒有跑模型，無法由 parameter count 補值。
- C1／C2 對繁中／簡中 document-borne injection 的 recall／FPR、D1 的繁中長論文與 domain shift、B2 中文 diff／OCR 品質，均 UNKNOWN。找不到本案四類與 modalities 的共同校準資料集；不能以某一公開 benchmark 代替。
- 圖中文字和視覺互動、cross-page／cross-chunk intent、僅 pixels 可見的 injection、未知 parser exploits：本次候選都沒有完備覆蓋證據。
- B1／B2 的 AGPL／commercial 相依、C1 的 Llama 4 條件、D2 的 Gemma terms、各測試集再散布權與 Azure 合約，採用前仍須確認；engine／模型主授權不代表全部相依或素材授權。
- 偵測 error、timeout、超限及缺 modality 的政策與 Processing Result 表示方式，由 #107／#108 決定；本報告不把現有 enrichment failure semantics 自動沿用為 screening semantics。
- 本次未取得 policy ticket 的正式可接受 FPR／漏判預算、harm taxonomy 與例外準則，也未建立 ground truth 或正式 threshold。這些是量測輸入／政策決定，不是研究缺資料時可自行填的通過條件。
- 研究內容已寫入本檔；merge 到 `dev` 與貼回 ticket 依本次指示留給主線，**未執行 commit／push／GitHub 寫入**。

## Sources

以下均為一手作者、規格、原始碼或官方文件；查閱日一律 2026-10-23。`main`／`latest` 連結可變；量測需另記 commit／模型 revision／DB digest。研究沒有引用搜尋摘要作效能結論。

- [S01 — Didier Stevens：PDF Tools][S01]
- [S02 — PDFiD source，0.2.10][S02]
- [S03 — pdf-parser source，0.7.14][S03]
- [S04 — ClamAV introduction／features／GPLv2][S04]
- [S05 — ClamAV clamd.conf.sample][S05]
- [S06 — ClamAV Docker RAM guidance][S06]
- [S07 — ClamAV scanning][S07]
- [S08 — gVisor isolation model overview][S08]
- [S09 — ClamAV interpreting alerts][S09]
- [S10 — Docling TextItem source][S10]
- [S11 — Docling Formatting source][S11]
- [S12 — Docling ProvenanceItem／PageItem source][S12]
- [S13 — Docling TextCell／PdfTextCell source][S13]
- [S14 — docling-parse decoder mapping][S14]
- [S15 — PyMuPDF get_texttrace API][S15]
- [S16 — PyMuPDF licence][S16]
- [S17 — docling-core licence][S17]
- [S18 — docling-parse licence][S18]
- [S19 — PhantomLint paper v1][S19]
- [S20 — PhantomLint README][S20]
- [S21 — PhantomLint CLI source][S21]
- [S22 — PhantomLint OCR source][S22]
- [S23 — PhantomLint BSD-3-Clause][S23]
- [S24 — Tesseract languages][S24]
- [S25 — Tesseract README／licence][S25]
- [S26 — tessdata_fast licence][S26]
- [S27 — UAX #44 UCD][S27]
- [S28 — UTS #39 Unicode Security Mechanisms][S28]
- [S29 — Unicode License V3][S29]
- [S30 — Llama Prompt Guard 2 model card][S30]
- [S31 — Prompt Guard 2／Llama 4 licence][S31]
- [S32 — Azure Prompt Shields concepts][S32]
- [S33 — Azure region／input limits／language evidence][S33]
- [S34 — Prompt Shields standalone API quickstart][S34]
- [S35 — YARA rule syntax／Unicode behavior][S35]
- [S36 — YARA CLI／timeouts／matches][S36]
- [S37 — YARA BSD-3-Clause][S37]
- [S38 — BIPIA paper v4][S38]
- [S39 — NotInject／InjecGuard paper v3][S39]
- [S40 — LLMail-Inject paper v1][S40]
- [S41 — CrackedPDFs corrected abstract v2][S41]
- [S42 — AgentDojo paper v3][S42]
- [S43 — Qwen3Guard official README][S43]
- [S44 — Qwen3Guard-Gen-0.6B model card／policy][S44]
- [S45 — Qwen3Guard-Gen-0.6B config][S45]
- [S46 — Qwen3Guard-Gen-4B config][S46]
- [S47 — Qwen3Guard technical report v1][S47]
- [S48 — ShieldGemma 2 official model card][S48]
- [S49 — Google ShieldGemma 2 weights／inference example][S49]
- [S50 — ShieldGemma 2 paper v1][S50]
- [S51 — Gemma Terms of Use][S51]
- [S52 — Azure harm taxonomy／severity][S52]
- [S53 — Azure Content Safety FAQ／model updates／media／billing][S53]
- [S54 — Tesseract CLI／languages／TSV][S54]

[S01]: https://blog.didierstevens.com/programs/pdf-tools/
[S02]: https://raw.githubusercontent.com/DidierStevens/DidierStevensSuite/master/pdfid.py
[S03]: https://raw.githubusercontent.com/DidierStevens/DidierStevensSuite/master/pdf-parser.py
[S04]: https://docs.clamav.net/
[S05]: https://raw.githubusercontent.com/Cisco-Talos/clamav/main/etc/clamd.conf.sample
[S06]: https://docs.clamav.net/manual/Installing/Docker.html
[S07]: https://docs.clamav.net/manual/Usage/Scanning.html
[S08]: https://gvisor.dev/docs/
[S09]: https://docs.clamav.net/faq/faq-scan-alerts.html
[S10]: https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/types/doc/items/text.py
[S11]: https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/types/doc/common/formatting.py
[S12]: https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/types/doc/common/reference.py
[S13]: https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/types/doc/page.py
[S14]: https://raw.githubusercontent.com/docling-project/docling-parse/main/docling_parse/pdf_parser.py
[S15]: https://pymupdf.readthedocs.io/en/latest/functions.html#Page.get_texttrace
[S16]: https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright
[S17]: https://raw.githubusercontent.com/docling-project/docling-core/main/LICENSE
[S18]: https://raw.githubusercontent.com/docling-project/docling-parse/main/LICENSE
[S19]: https://arxiv.org/html/2508.17884v1
[S20]: https://github.com/tobycmurray/phantom-lint
[S21]: https://raw.githubusercontent.com/tobycmurray/phantom-lint/main/phantomlint/cli.py
[S22]: https://raw.githubusercontent.com/tobycmurray/phantom-lint/main/phantomlint/ocr.py
[S23]: https://raw.githubusercontent.com/tobycmurray/phantom-lint/main/LICENSE
[S24]: https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html
[S25]: https://github.com/tesseract-ocr/tesseract
[S26]: https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/LICENSE
[S27]: https://unicode.org/reports/tr44/
[S28]: https://www.unicode.org/reports/tr39/
[S29]: https://www.unicode.org/license.txt
[S30]: https://raw.githubusercontent.com/meta-llama/PurpleLlama/main/Llama-Prompt-Guard-2/86M/MODEL_CARD.md
[S31]: https://raw.githubusercontent.com/meta-llama/PurpleLlama/main/Llama-Prompt-Guard-2/86M/LICENSE
[S32]: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/jailbreak-detection
[S33]: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/region-availability
[S34]: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/quickstart-jailbreak
[S35]: https://yara.readthedocs.io/en/stable/writingrules.html
[S36]: https://yara.readthedocs.io/en/stable/commandline.html
[S37]: https://raw.githubusercontent.com/VirusTotal/yara/master/COPYING
[S38]: https://arxiv.org/html/2312.14197v4
[S39]: https://arxiv.org/html/2410.22770v3
[S40]: https://arxiv.org/html/2506.09956v1
[S41]: https://arxiv.org/abs/2607.19396v2
[S42]: https://arxiv.org/abs/2406.13352v3
[S43]: https://raw.githubusercontent.com/QwenLM/Qwen3Guard/main/README.md
[S44]: https://huggingface.co/Qwen/Qwen3Guard-Gen-0.6B
[S45]: https://huggingface.co/Qwen/Qwen3Guard-Gen-0.6B/blob/main/config.json
[S46]: https://huggingface.co/Qwen/Qwen3Guard-Gen-4B/blob/main/config.json
[S47]: https://arxiv.org/html/2510.14276v1
[S48]: https://ai.google.dev/gemma/docs/shieldgemma/model_card_2
[S49]: https://huggingface.co/google/shieldgemma-2-4b-it
[S50]: https://arxiv.org/html/2504.01081v1
[S51]: https://ai.google.dev/gemma/terms
[S52]: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/concepts/harm-categories
[S53]: https://learn.microsoft.com/en-us/azure/ai-services/content-safety/faq
[S54]: https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html
