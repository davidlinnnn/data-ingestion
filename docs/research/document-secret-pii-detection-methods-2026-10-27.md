# 文件內 secret 與 PII：地端偵測方法研究

日期與所有外部來源查閱日：**2026-10-27（Asia/Taipei）**。本檔回答 #121，補上 [#105 篩檢方法研究](document-content-screening-methods-2026-10-23.md) 未涵蓋的第 5 類「敏感資料」；服務量測（#106）、政策（#107）與 workflow placement（#108），但不替它們做決定。候選排序是研究建議，不是採用決定。版本、授權與作者公布的數字均為查閱當日所見；`UNKNOWN` 表示一手來源沒有足夠證據，絕不等於通過；`未驗證` 表示本次沒有在中文文本上跑過。

## 摘要與研究範圍

| 類別 | 優先量測建議（研究推論；理由見各節） |
|---|---|
| 1. Secret（密碼、API key、連線字串、私鑰） | gitleaks 8.30.1 預設規則加自訂中文關鍵字規則作 baseline，CredSweeper `--doc` 的 ML 過濾作對照；TruffleHog 只能在 `--no-verification`、`--no-update` 並封鎖 egress 時當比較組。三者都沒有內建中文關鍵字。 |
| 2. 結構化 PII（身分證字號、居留證統號、電話、email、工號） | Presidio 當框架，自寫台灣 recognizer（含檢查碼、CJK 安全邊界、全形正規化視圖）。查閱當日 Presidio 正式版沒有台灣 recognizer。 |
| 3. 人名 PII | CKIP Transformers（繁中訓練）、spaCy `zh_core_web_trf`、OpenAI Privacy Filter、GLiNER multi PII 四者同一資料比較。對台灣論文文本的準確度全部 `未驗證`；HanLP 模型為 CC BY-NC-SA 4.0，商業使用受限。 |
| 4. 篩檢訊號 | 訊號只放類別、位置、偵測器版本、原生分數與遮罩後的證據；不放 secret 或 PII 原值，也不放未加 key 的 hash。 |

**問題拆解：**secret 偵測問「這段文字是不是可用的憑證」；PII 偵測問「這段文字能不能識別一個自然人」。前者的誤判多來自看起來隨機的字串（hash、UUID、範例 key），後者在研究論文中多來自**合法揭露**的個資（作者、致謝、引用）。兩類都必須回指 Source Evidence 的位置，且結果本身不能變成新的外洩點。

本研究沿用 [CONTEXT.md](../../CONTEXT.md) 的 Processing Profile、Source Evidence 與 Processing Result；[PDF workflow v2](../design/knowledge-platform-processing-workflow-v2.md) §8 的 enrichment 項目已有 `signals{}`、`evidence_refs`、`method_ref`。輸入限制：所有內容只能送 on-prem 服務，雲端服務只能拿公開資料當對照（#121 給定）。台灣《個人資料保護法》第 2 條把自然人的姓名、國民身分證統一編號、聯絡方式等列為個人資料。[個資法][S53] 因此論文作者姓名屬 PII，但多半是合法揭露。[#87 設計紀錄](../design/knowledge-platform-data-security.md) 已定：B5 平台不遮蔽原文，第 5 類初始模式為「記錄＋警示」；B6 篩檢訊號從第一天就寫進 Processing Result，收緊模式時用已存的訊號重新判斷，不重新處理文件。所以訊號本身要帶足重新判斷所需的資訊（類別、位置、角色、分數），但不能帶原值。本研究只談偵測與標註，**收緊、gate 與例外由 #107 決定**。

**本次實際執行的範圍：**以 gitleaks 8.30.1 掃過 12 段合成字串（全部是隨機產生、不可用的假值），也用 spaCy `zh_core_web_sm` 3.8.0 跑過 7 句合成中文句子的冒煙測試；兩者都在開發筆電（Apple M5 Pro）上執行，不是公司 K8s 硬體。TruffleHog、detect-secrets、CredSweeper、CKIP、GLiNER、OpenAI Privacy Filter 都**沒有執行**，只讀文件與原始碼。

## 1. Secret 偵測

### 文件抽取文字和 git repo 的差異

這些 scanner 原本是為 source code 與 git history 設計的。用在 PDF／Markdown／PPTX 抽出的文字時，有四個會直接影響結果的差異：

| 差異 | 證據 | 影響（研究推論） |
|---|---|---|
| 預設會跳過文件檔 | gitleaks 預設 config 的全域 allowlist 以副檔名排除 `docx?`、`xlsx?`、`pdf` 等；本機探測中，同一段文字存成 `.pdf` 時沒有 finding，存成 `.pptx` 時有。 [config][S02] | 不能把原始 PDF 直接丟給 gitleaks。要掃抽出的文字，而且要知道「沒有 finding」可能是因為被 allowlist 排除。 |
| Markdown 序列化會改寫字元 | Docling `MarkdownParams` 預設 `escape_underscores=True`、`escape_html=True`，只有 code 與 formula item 例外。 [Docling serializer][S21] | 正文裡的 `api_key` 會變成 `api\_key`，offset 偏移，regex 也可能失配。建議逐 item 掃 `text`／`orig`，並保留 item 的 provenance，不掃最終 Markdown。 |
| 版面斷行 | PDF 的行與欄由排版決定；PEM 區塊、長 token、連線字串可能被斷在兩行、兩欄或兩頁。gitleaks 的 private-key 規則要求 BEGIN 與 END 標頭之間至少 64 個字元。 [config][S02] | 單行規則在斷行處會漏掉，跨行規則又可能把不相干的段落接起來。#106 需要斷行與跨頁的測試案例。 |
| 位置單位 | 本機探測：gitleaks JSON 的 `StartColumn`／`EndColumn` 是 1-based 的 **UTF-8 byte** 位置（中文前綴 5 個字＝15 bytes，結果的起點是 16）。 | 要寫成 Source Evidence 的字元位置，需另外把 byte 換算成 code point；直接沿用會在中文文本中指錯位置。 |

### 候選比較

| candidate | what it detects | on-prem／網路 | zh/en | 抽取文字適配 | 典型誤判 | licence | latency/hardware | output／score | sources |
|---|---|---|---|---|---|---|---|---|---|
| S1：gitleaks 8.30.1（2026-03-21 發布） | 預設 config 222 條規則：供應商 token 格式、private key、`generic-api-key`（英文關鍵字＋值＋entropy ≥ 3.5）。可解 percent／hex／base64（`--max-decode-depth`，預設關）。 | 單一 Go binary，`dir`／`stdin` 離線掃描；沒有驗證功能。 | 關鍵字全是英文；本機探測中 `密碼：`／`密碼=`／`API 金鑰為` 三種寫法都沒有命中。自訂 `[[rules]]` 可用中文關鍵字，探測中三種都抓到。 | `dir` 與 `stdin` 都可用；要處理 byte column 與上述 allowlist。 | 探測中，`key:` 後接 SHA-256、`secret_id:` 後接 UUID 都被判為 `generic-api-key`。AWS 規則已 allowlist 結尾是 `EXAMPLE` 的範例 key。 | MIT。 | 本機：1.6 MB 中英混合 Markdown 約 0.36 秒（含程序啟動），0 finding；K8s CPU 數字 UNKNOWN。 | RuleID、Entropy、行／欄、Fingerprint；`--redact` 把 Secret 與 Match 裡的值換成 `REDACTED`（Match 保留關鍵字前綴）。沒有機率分數。 | [README][S01]、[config][S02]、[licence][S03]、[release][S04] |
| S1′：Betterleaks（gitleaks 原作者的後繼專案） | 規則型；README 列 BPE tokenization 過濾自然語言誤判、Expr 規則、keyed fingerprint（`--hmac-key`）。 | v2 README：預設不驗證，加 `--validate`／`--analyze` 才會發 HTTP 請求；驗證邏輯寫在規則裡。 | 中文 UNKNOWN。 | `stdin`、檔案系統皆可。 | UNKNOWN。 | MIT。 | UNKNOWN。 | v2 尚未正式發布（`main` 為 v2 開發中，最新 tag 為 v1.9.0）；config 格式與 gitleaks 不同，需看 migration guide。 | [README][S05] |
| S2：TruffleHog v3.99.7（2026-10-24 發布） | 800 多種 secret 類型的 detector；有 `uri`、`jdbc`、`postgres`、`mongodb`、`privatekey` 等 detector；decoder 有 base64、utf16、escaped unicode、html。 | **驗證預設開啟**：用候選憑證呼叫供應商 API。必須加 `--no-verification`（"Don't verify the results"）與 `--no-update`（"Don't check for updates"）；custom detector 的 `verify` 會 POST 到 webhook，不可設定。 | 中文關鍵字 UNKNOWN（未讀遍 detector）；`--filter-entropy` 只作用於 unverified 結果。 | 有 `filesystem` 與 `stdin`。 | UNKNOWN；關掉驗證後只剩 unverified，主要的過濾手段跟著消失（研究推論）。 | AGPL-3.0；貢獻需 CLA。 | Go binary；本案延遲 UNKNOWN。 | JSON 的 `Raw` 是**偵測到的原值**；README 範例中 `Raw` 與 `Redacted` 是同一個 access key ID，`Redacted` 放什麼由各 detector 決定，不能假設已遮罩。README 沒有遮罩選項。 | [README][S06]、[detectors][S07]、[decoders][S08] |
| S3：detect-secrets 1.5.0（2024-05-06） | 約 28 個 plugin：Base64／Hex high-entropy（預設 4.5／3.0）、KeywordDetector、PrivateKeyDetector、各供應商格式。 | `scan --all-files` 可掃非 git 檔；`-n/--no-verify` 停用網路驗證。 | KeywordDetector 的 denylist 只有英文與西班牙文（`contraseña`）。 | 可以，但工具以 repo baseline 為中心。 | 內建 filter 排除 UUID、連續字串、模板 placeholder（`${key}`、`{{key}}`）等。 | Apache-2.0。 | Python；本案延遲 UNKNOWN。 | baseline 以**未加鹽 SHA-1** 存 `hashed_secret`。 | [README][S09]、[filters][S10]、[keyword][S11]、[hash][S12]、[PyPI][S13] |
| S4：CredSweeper v1.19.5（2026-10-26 發布） | 151 條規則，其中標示 `doc` target 的規則只在 `--doc` 模式套用；21 個 filter；內附 ONNX ML 模型過濾誤判（`--ml_threshold`，0 為關閉）。`--depth` 可直接拆 pdf／docx／pptx（experimental）。 | Python＋onnxruntime；文件中沒有網路驗證功能。 | 規則檔與關鍵字表中沒有任何 CJK 字元。 | `--doc` 是為文件設計的模式；仍建議餵抽出的 item 文字，以便定位。 | 預設 exclude pattern 含 AWS `EXAMPLE` 範例；官方列出 `password = "template_password"` 類典型誤判。 | MIT。 | 本案延遲 UNKNOWN；有 `--jobs`、`--ml_batch_size`。 | `rule`、`severity`、`confidence`、`ml_probability`、`value_start／value_end`、`entropy`；JSON 預設含 `value` 與整行 `line`。`--hashed` 會 hash line／variable／value（演算法與加鹽方式未讀到，UNKNOWN）。 | [README][S14]、[guide][S15]、[architecture][S16] |

其他看過但不列入短名單：Kingfisher（Apache-2.0，Rust，**驗證預設開啟**，需 `--no-validate`）[S18]；Titus（Apache-2.0，Go，487 條規則，驗證預設關閉，`--extract` 可拆 PDF／Office）[S19]，它是 Nosey Parker 的後繼，Nosey Parker 已於 2026-04-24 封存 [S20]。兩者都是可用的對照組，但本研究沒有讀到它們的中文處理或文件誤判證據。

### 本機探測（gitleaks 8.30.1，合成假值）

每段一個檔案，值都是隨機產生、不可用的字串；目的只是確認介面行為，不是量測 precision/recall。

| 案例 | 預設 config | 加 1 條中文關鍵字規則 |
|---|---|---|
| 英文 `password = <20 字元>` | 命中 `generic-api-key` | 命中 |
| 英文 `api_key: <32 字元>` | 命中 | 命中 |
| 中文 `密碼：<20 字元>`、`密碼=<20 字元>`、`API 金鑰為 <32 字元>` | **3 段都沒命中** | 3 段都命中 |
| PostgreSQL 連線字串（含假密碼） | **沒命中** | 沒命中（規則沒有涵蓋） |
| 假的 GitHub PAT 格式 | 命中 `github-pat` | 命中 |
| 論文句中的 SHA-256（無關鍵字） | 沒命中 | 沒命中 |
| `key:` 後接 SHA-256、`secret_id:` 後接 UUID | **2 段都誤判** | 2 段都誤判 |
| Markdown 內嵌 base64 PNG、DOI | 沒命中 | 沒命中 |

### 解讀與推薦

**推薦 #106 以 S1 為 baseline，S4 作 ML 過濾對照；S2 只當比較組。**理由是授權與網路行為：S1、S4 為 MIT 且沒有驗證功能；S2 是 AGPL-3.0，而且驗證預設開啟，正是本案禁止的對外呼叫。S1 的上游已宣告 feature complete、之後只出安全修補，這個維護狀態要記為採用條件；Betterleaks 的 v2 正式發布後，可以用同一份測試集評估是否改用。[S1 README][S01] [Betterleaks][S05]

**網路隔離要做兩層。**TruffleHog 與 Kingfisher 要靠旗標關驗證，Betterleaks 則是在規則內定義 HTTP 驗證；只要漏設一個旗標，或日後換了 config，就會把候選憑證送出去。研究建議：scanner pod 以 Kubernetes NetworkPolicy 預設拒絕 egress（前提是叢集的 CNI 有實作 NetworkPolicy），旗標只是第二層。[NetworkPolicy][S62] 這也延伸了 #105 對 scanner 隔離的建議。

**中文是規則問題，不是工具問題。**gitleaks、detect-secrets、CredSweeper 的關鍵字都沒有中文；在文件情境中，中文的「密碼」「口令」「金鑰」「密鑰」「帳號／密碼」等寫法需要自訂規則，而且要配合 entropy 或長度條件，否則「密碼長度至少 8 碼」這類說明文字也會命中（研究推論）。供應商 token（有固定前綴的格式）不受語言影響。

**連線字串需要另外處理。**gitleaks 預設規則沒有通用的「URL 內嵌帳密」規則（探測中 PostgreSQL URI 沒命中）；TruffleHog 有 `uri`／`jdbc`／`postgres` detector，但它們原本是靠驗證減少誤判。建議把 `scheme://user:password@host` 寫成自訂規則，並排除 `example`、`localhost`、placeholder 密碼（研究推論）。

## 2. PII 偵測（以繁體中文／台灣為重點）

### 台灣識別碼：規則與檢查碼

| 類型 | 格式依據 | 規則要點（研究建議） | sources |
|---|---|---|---|
| 國民身分證統一編號 | 1 碼英文＋9 碼數字；第 2 碼 1／2 表示性別；最後一碼為檢查碼。 | 英文字母先轉兩位數（A=10…，但 I、O、W、Z 不按字母序，需要查表），兩位數與後 9 碼共 11 位，依序乘權重 1、9、8、7、6、5、4、3、2、1、1，總和可被 10 整除即為有效。**沒有找到內政部公開的編碼規格**；算法來源是大學課程講義，屬非官方來源，實作時需用合成案例驗證。 | [講義][S56] |
| 新式外來人口統一證號 | 2021-01-02 起核發 1 碼英文＋9 碼數字；第 2 碼 8（男）／9（女），並「比照身分證字號的編碼原則」；舊式（2 碼英文＋8 碼數字）用到 2030-12-31。 | 第 2 碼接受 1、2、8、9；舊式統號另寫一條規則。新式統號沿用同一套檢查碼，是依「比照編碼原則」的推論，官方原文沒有寫明，需以案例驗證。 | [移民署][S54]、[中央社][S55] |
| 行動電話 | 數位發展部〈公眾電信網路號碼計畫〉：090～098 等字頭為行動通信，總碼長 10 碼（含字頭碼）。 | `09` 加 8 碼，允許 `-`、空白、`+886 9…` 寫法；市話依區域碼長度不同，需另寫規則。Presidio 的 PhoneRecognizer 用 python-phonenumbers，但**預設 regions 只有 US、GB、DE、FR、IL、IN、CA、BR**，要另外加 `TW`。 | [號碼計畫][S57]、[Presidio phone][S30]、[libphonenumber][S58] |
| email | Presidio `EMAIL_ADDRESS`：pattern＋context＋RFC-822 驗證。 | 與語言無關；研究論文的通訊作者 email 是最常見的合法 PII。 | [Presidio entities][S24] |
| 工號 | 各公司格式不同。 | 用設定檔定義 regex 與中英文 context 詞（例如「工號」「員工編號」）；格式本身不放進公開 repo。Presidio 的 context 增強預設看實體**前方 5 個** token、後方 0 個，預設用 substring 比對。 | [context enhancer][S31] |

**兩個與中文直接相關的陷阱：**

1. **`\b` 在 CJK 旁邊不成立。**Python 的 `\w` 包含中日韓字元，所以 `身分證字號` 直接接英數字時，字與字之間沒有 word boundary。本機以 Python `re` 確認：`\b[A-Z][1289][0-9]{8}\b` 在「冒號＋號碼」時會命中，但在「中文字直接接號碼」或「號碼後直接接中文字」時都不命中；改用 `(?<![A-Za-z0-9])…(?![0-9])` 就能命中。Presidio 待審的台灣身分證 PR（#2072，查閱日仍 open）用的正是 `\b` 版本。[PR #2072][S33]
2. **全形數字與零寬字元。**Presidio issue #2396（2026-10-24 開立）回報：全形數字或夾雜零寬字元的識別碼會讓 pattern recognizer 漏掉，NFKC 正規化並移除 `Cf` 類字元之後就能抓到。[issue #2396][S35] 這和 #105 B3 的 Unicode 檢查是同一件事：建議產生一份正規化視圖去比對，並保留回到原文 offset 的對照表，不直接改寫原文。

### 候選比較

| candidate | what it detects | on-prem | zh／繁中證據 | licence | latency/hardware | output／score | sources |
|---|---|---|---|---|---|---|---|
| P1：Presidio Analyzer 2.2.366（2026-10-27 發布；repo 已由 `microsoft/presidio` 轉到 `data-privacy-stack/presidio`） | 框架：pattern／checksum／context recognizer＋NLP engine（spaCy、Stanza、transformers）＋可插 GLiNER。內建全域實體有 PERSON、EMAIL、PHONE、CREDIT_CARD、IBAN 等，另有多國的國別實體。 | 是，Python library／Docker。 | **預設只支援英文**；每個 recognizer 只對應一種語言，非英文要自己設定 NLP engine 與 context 詞。國別清單**沒有 TW 或 CN**。slim engine 把 `zh` 對應到 `zh_core_web_sm`。台灣 recognizer 有 issue #2065 與 PR #2072，尚未合併。 | MIT。 | 官方沒有延遲數字；取決於所用 NLP engine。 | `RecognizerResult`：entity_type、start、end（字元 offset）、score，可附 analysis explanation。分數是 recognizer 自訂的 0–1，不是校準過的機率。 | [repo][S23]、[entities][S24]、[languages][S25]、[custom][S26]、[slim engine][S32]、[#2065][S34] |
| P2：spaCy `zh_core_web_sm`／`lg`／`trf` 3.8.0 | OntoNotes 18 類 NER，含 PERSON、ORG、GPE。 | 是。 | 訓練來源為 OntoNotes 5（簡體為主，見 P3 說明）。作者公布的全實體 ENTS_F：sm 68.42、lg 71.39、trf 74.26；**沒有 PERSON 單類與繁中數字**。本機冒煙測試結果見下。 | 模型 MIT；OntoNotes 原始語料受 LDC 授權。 | sm 46 MB、lg 575 MB、trf 396 MB。本機 sm：84,400 字約 1.74 秒（約 4.8 萬字／秒，單程序，含 tagger／parser）。 | span＋label，沒有每個 span 的分數。 | [sm][S36]、[lg][S37]、[trf][S38] |
| P3：CKIP Transformers 0.3.4（2023-04） | 繁體中文 WS／POS／NER；NER 為 OntoNotes 18 類。 | 是，`device=-1` 跑 CPU。 | **唯一以繁體訓練的候選**：NER 訓練資料是 OntoNotes 5.0 中文部分用 OpenCC 轉成繁體（由此可知原語料為簡體）。作者公布 NER F1：bert-base 81.18%、albert-base 79.47%、bert-tiny 74.21%、albert-tiny 71.17%（全類別、轉繁後的 OntoNotes，不是台灣論文）。 | 程式與模型均為 **GPL-3.0**。 | bert-base 102M、albert-tiny 4M 參數；CPU 延遲 UNKNOWN。 | span＋label。 | [README][S39]、[model][S40] |
| P4：HanLP 2.1 | 多任務模型，NER 有 PKU／MSRA／OntoNotes 版本。 | 有本地 `pip install hanlp`，也有需要 auth key 的 RESTful 雲端 API；後者不可用。 | 繁體支援在 README 中沒有提到，UNKNOWN。 | 程式 Apache-2.0，但**模型預設 CC BY-NC-SA 4.0（禁止商業使用）**。 | UNKNOWN。 | — | [README][S41] |
| P5：GLiNER multi PII（`urchade/gliner_multi_pii-v1`；Presidio 內建 `GLiNERRecognizer`） | zero-shot NER，由呼叫端給標籤字串（person、email、phone number…）。 | 是；Presidio 範例用 `map_location="cpu"`，可選 ONNX。 | GLiNER 論文：GLiNER-Multi 在 MultiCoNER 中文 zero-shot F1 為 **24.3**（有監督 XLM-R 為 53.1）；fine-tune 資料只有英文。PII 版以合成資料微調，模型卡沒有中文數字。Presidio 預設把文字切成 250 字元、重疊 50 字元的 chunk。 | Apache-2.0。另有 knowledgator gliner-pii（Apache-2.0，只有英文與合成多語資料的 F1）與 NVIDIA gliner-PII（NVIDIA Open Model License，只標英文）。 | multi v2.1 約 0.2–0.3B 參數；CPU 延遲 UNKNOWN。 | span、label、score；threshold 由呼叫端設定（knowledgator 建議從 0.3 開始）。 | [paper][S43]、[repo][S44]、[PII model][S45]、[multi v2.1][S46]、[Presidio GLiNER][S27]、[knowledgator][S47]、[NVIDIA][S48] |
| P6：OpenAI Privacy Filter（2026-04-22 發布） | 雙向 token classifier，8 類：`private_person`、`private_email`、`private_phone`、`private_address`、`private_url`、`private_date`、`account_number`、`secret`。 | 是，`opf --device cpu`；1.5B 總參數、每次啟用 50M（MoE）；context 128K tokens，不需切段。 | 作者的合成多語評估中，「Mandarin Chinese」971 例 F1 **0.917**；有類別提示詞時（1,191 例）precision 0.926、recall 0.786。**沒有說明繁簡**，資料由 GPT 生成，也不是論文文本。模型卡自述非英文、非拉丁字母時表現可能下降。 | Apache-2.0。 | CPU 延遲與記憶體 UNKNOWN。 | `detected_spans` 有 label、start、end，**也有 `text`（原值）**與遮罩後全文；precision／recall 用 6 個 Viterbi transition bias 調整，標籤政策要改只能 fine-tune。 | [HF card][S49]、[repo][S50]、[model card PDF][S51]、[schema][S52] |

Stanza 的中文 NER（OntoNotes，F1 79.2）只有 `zh` 一個模型，頁面沒有繁體版；可以當 Presidio NLP engine 的備選，未列入短名單。[Stanza][S42]

### 本機冒煙測試（spaCy `zh_core_web_sm` 3.8.0，7 句合成句子）

句子中的人名都是編造的常見姓名組合；本報告不列出名字。這是**冒煙測試，不是準確度量測**。

| 案例 | 結果 |
|---|---|
| 作者行，繁體，3 個人名 | 命中 2 個，漏 1 個 |
| 同一作者行改成簡體 | 3 個全中，另把機構名標成 ORG |
| 繁體致謝句，2 個人名 | 2 個都抓到，但第二個把前面的「與」也併進 span（邊界錯誤） |
| 繁體引用句「某某等人（2019）」 | 人名漏掉，只標到 DATE |
| 繁體聯絡資訊 | 人名命中；「聯絡人」被誤標為 LANGUAGE |
| 中文句中夾 3 個英文人名 | 0 個 |
| 沒有人名的句子 | 正確地沒有 PERSON |

同一份作者行繁體漏、簡體全中，與 P3 提到「OntoNotes 原為簡體」一致，但 7 句不足以下結論。中文句中的英文人名全數漏掉，對中英混合的論文是要量測的風險。

### 解讀與推薦

**推薦 P1 當框架，結構化 PII 全部用自寫規則。**台灣身分證、新式統號、手機、工號都是格式明確的識別碼，用 regex＋檢查碼＋context 就能做，而且可以解釋；不需要模型。Presidio 的價值在於統一的 recognizer 介面、context 增強與 offset 輸出，以及可以在同一流程中接入人名模型。[custom recognizers][S26] 待審的 PR #2072 能提供參考，但它的 `\b` 邊界在中文旁邊會失效，不能直接沿用。

**人名要在同一份資料上比較 P3、P2 trf、P6、P5，四者目前都是 `未驗證`。**P3 是唯一以繁體訓練的模型，但 GPL-3.0、最後發布在 2023 年；P6 有最新的中文證據，但那是合成、繁簡不明的資料；P5 的論文中文數字偏低；P2 的冒煙測試已顯示繁簡差異。HanLP 的模型授權不適合公司使用，除非另外取得授權。

**OpenAI Privacy Filter 也偵測 `secret`，可當 secret 的第二意見。**作者在 CredData 上的 token-level F1 為 0.842，但 span-level 只有 0.617；模型卡也承認會把 hash、placeholder、範例憑證誤判為 secret，新格式的憑證則會漏掉。[model card §4.3、§7.4][S51] 它不能取代規則型 scanner。

## 3. 實務：K8s CPU 執行、吞吐與篩檢訊號

### 執行條件

| 項目 | 研究建議與依據 |
|---|---|
| 網路 | scanner／模型 pod 預設拒絕 egress（NetworkPolicy）[S62]；secret scanner 一律加上關驗證的旗標（S2 `--no-verification --no-update`、Kingfisher `--no-validate`、detect-secrets `-n`、Betterleaks 不加 `--validate`）。模型權重預先放進 image 或 volume，並設 `HF_HUB_OFFLINE=1`，避免執行時連線到 Hugging Face。[HF env][S63] |
| CPU | S1／S2 是 Go 單一 binary，S3／S4 與 P1–P6 是 Python。規則型掃描在本機是亞秒級：1.6 MB 文字約 0.36 秒。spaCy sm 約 4.8 萬字／秒。CKIP、GLiNER、Privacy Filter 在 CPU 上的吞吐、峰值 RSS、冷啟動載入時間全部 UNKNOWN，必須在 pod 的 CPU／memory limit 下實測。 |
| 每頁吞吐 | 一頁的字數依語言與版面差異很大，本研究不換算「每頁毫秒」。#106 應以 pilot 論文實際抽出的字數，分別記錄每頁與 64 頁整份的 p50／p95。 |
| 暫存檔 | gitleaks 不加 `--redact`、TruffleHog、CredSweeper 預設、Privacy Filter 的輸出都含原值。研究建議：scanner 的 stdout 與報告檔不進 worker log；報告寫到 pod 內的暫存空間，轉成訊號後立即刪除；轉換步驟只取下表允許的欄位。 |

### 篩檢訊號應該包含什麼（研究建議，欄位名稱與位置由 #108 決定）

| 必要內容 | 理由 |
|---|---|
| 類別：`secret` 或 `pii`，加上子類（rule ID 或 entity type） | #107 依類別訂處置，需要可篩選。 |
| 偵測器身分：工具名稱與版本、rule set／config digest、模型 revision | 規則或模型變更後要能重評，也能沿用 #105 的版本可追溯原則。 |
| 位置：Source Evidence ref（page、bbox 來自 item provenance）、item ref、item 文字內的 code-point `start`／`end` | 讓 reviewer 回到原文；byte column 必須先換算。 |
| 原生分數與分數種類：CredSweeper `ml_probability`、Presidio／GLiNER score、gitleaks 只有 entropy | 不同工具的分數量綱不同，不能平均成一個分數（和 #105 結論相同）。 |
| 遮罩後的證據：保留關鍵字上下文，把值換成類別與長度，例如 `密碼：[REDACTED secret len=20]` | reviewer 不看原值也能判斷；原值仍可從受控的原始文件回查。 |
| 覆蓋狀態：已掃、部分（超過大小上限、逾時）、錯誤 | 沒掃到不能記成沒有 finding（#105 的 UNKNOWN 原則）。 |

**不要用未加 key 的 hash 當指紋。**台灣身分證去掉檢查碼只有 26 × 2 × 10⁷ ≈ 5.2 億種組合，手機號碼 `09` 後也只有 10⁸ 種；這種空間用普通 hash 很快就能窮舉回原值（研究推論）。detect-secrets 的 baseline 用的正是未加鹽 SHA-1。[S12] 如果需要跨 revision 去重，建議用平台持有 key 的 HMAC：Betterleaks 的 `--hmac-key` 是同一思路；Presidio 從 2.2.361 起 hash operator 預設隨機加鹽，需要一致性時要自行給至少 16 bytes 的 salt，官方也建議不要把 salt 寫進輸出。[Betterleaks][S05] [Presidio anonymizer][S28]

### 研究論文的典型誤判

| 來源 | 會觸發的偵測 | 研究建議 |
|---|---|---|
| 作者、機構、通訊作者 email、ORCID | PERSON、EMAIL | 屬 PII 但通常是合法揭露。訊號要帶「出現位置的角色」（作者區、致謝、參考文獻、正文），讓 #107 能訂例外。Docling 的 `DocItemLabel` 有 `title`、`section_header`、`footnote`，`reference` 只用於 markup 格式，**沒有作者標籤**，所以角色需要用版面規則推斷（第一頁、title 與 abstract 之間）。[labels][S22] |
| 引用（某某 et al.、某某等人） | PERSON | 冒煙測試中繁體引用句的人名被漏掉；英文引用則可能大量命中。兩種方向都要量測。 |
| 範例憑證、placeholder（`<YOUR_API_KEY>`、`xxxx`、`EXAMPLE` 結尾） | secret 規則、Privacy Filter `secret` | gitleaks 的 AWS 規則與 CredSweeper 預設 exclude 已排除 `EXAMPLE`；detect-secrets 排除模板 placeholder。教學類論文仍需要負例。 |
| hash、commit ID、UUID、checkpoint digest 出現在 `key`／`token`／`secret` 這類字附近 | `generic-api-key` | 本機探測已重現。可加 allowlist（例如 `sha256`、`checksum` 這類上下文詞）並在 #106 量測代價。 |
| 內嵌 base64 圖片、LaTeX、長數字表格 | entropy 規則、PHONE、DATE_TIME | Docling Markdown 的 `image_mode` 預設是 placeholder，不輸出 base64；改成 embedded 時要排除。Presidio 的 DATE_TIME 與寬鬆的電話比對在數字表格中可能大量命中，建議只開需要的 entity。[serializer][S21] |
| 圖片裡的文字（終端機截圖、投影片截圖） | 文字層掃描看不到 | 需要 OCR 文字一起掃；覆蓋狀態要標出哪些圖片沒掃。 |

## 4. 候選短名單與條件

以下是研究排序，不是採用決定。

| # | 候選 | 用途 | 採用前必須成立的條件 |
|---|---|---|---|
| 1 | gitleaks 8.30.1＋自訂中文與連線字串規則，`--redact` | secret baseline | 逐 item 掃描並換算 byte offset；egress 封鎖；接受上游只出安全修補，並以同一測試集評估 Betterleaks v2。 |
| 2 | CredSweeper `--doc`，開 ML | secret 誤判過濾對照 | 在論文負例上確實降低誤判，且不增加漏判；輸出只取允許欄位；確認 `--hashed` 的 hash 方式。 |
| 3 | Presidio＋自寫台灣 recognizer（身分證／新式統號檢查碼、手機、email、可設定的工號） | 結構化 PII | 使用 CJK 安全邊界與 NFKC 正規化視圖並保留 offset 對照；用合成案例驗證檢查碼（含 8／9 開頭）。 |
| 4 | 人名：CKIP bert-base、spaCy `zh_core_web_trf`、OpenAI Privacy Filter、GLiNER multi PII 四選一或組合 | PERSON | 在繁中、簡中、中英混合論文上量到可用的 recall 與 precision；CKIP 的 GPL-3.0 與 Privacy Filter 的 CPU 成本都要先確認。 |
| 5 | TruffleHog（`--no-verification --no-update`） | 僅作 #106 比較組 | AGPL-3.0 經確認可用；`Raw` 欄在轉換時丟棄。 |

不建議：HanLP 預設模型（非商業授權）、任何雲端 PII／secret API 用於非公開文件（#121 限制）、detect-secrets 當主力（2024 年後沒有新版、只有英西關鍵字、未加鹽 SHA-1 baseline）。

## 5. 給 #106 的量測建議

以下是建議的量測設計，不是已執行的測試，也不是 #107 的門檻。

### 測試集

| stratum | 內容 | 要回答的問題 |
|---|---|---|
| 真實 pilot 論文（benign） | 沿用 #105 建議的分層（英文、繁中、簡中、中英混合；頁數分層）。人工標註作者區、致謝、參考文獻、正文中的 PERSON／EMAIL／PHONE，並標角色。 | 合法 PII 的命中量，以及每份文件有多少 secret 誤報；這是 reviewer 負擔的主要來源。 |
| 注入的合成 secret | 測試時產生的不可用假值：各供應商格式、中英文密碼賦值、連線字串、PEM 區塊（斷行、斷頁、放在表格或 code block）、OCR 截圖。**不提交到 repo**。 | 各寫法與位置的 recall；能否定位到 item 與頁面。 |
| secret 困難負例 | hash、UUID、DOI、arXiv ID、`EXAMPLE` 範例 key、placeholder、base64 圖、LaTeX、說明密碼規則的中文句子。 | 誤判率與 allowlist 的代價。 |
| 注入的合成台灣識別碼 | 檢查碼正確與錯誤各半；第 2 碼 1／2／8／9；舊式統號；全形數字、零寬字元、中文字緊鄰、跨行；手機多種寫法；email 只用 `example.com`；工號依設定格式。 | 規則的 recall 與檢查碼帶來的 precision；邊界與正規化是否有效。 |
| 外部參考集 | CredData（Apache-2.0；19,459,282 行中 4,583 行標為真憑證，其中 Markdown 253 行），以程式碼為主，只當補充；ai4privacy pii-masking-300k 沒有中文，不適用。 | 讓結果能與作者公布的數字對照。CredData 的工具比較表是 2022 年、由 CredSweeper 作者自行執行，不能當今日的工具排名。 [CredData][S17] [300k][S61] |

合成資料可以用 Faker 的 `zh_TW` locale（有 person、phone_number、ssn、address provider）與 presidio-research 的產生器。[Faker][S59] [presidio-research][S60] 需注意：檢查碼正確的合成身分證號可能剛好等於某個真實號碼，這類案例和結果原文只能放在受控儲存，repo 只留生成腳本的參數與 digest（沿用 workflow v2 §11「報告與 hash manifest 進 git、原始輸出放外面」）。

### 指標與記錄

- 依 entity type、角色、語言分層報告 span-level 與 document-level 的 precision、recall；Presidio 文件建議 recall 較重要時用 F2。[Presidio evaluation][S29]
- **洩漏測試：**每個注入的假值都當作 canary，跑完後在 worker log、Processing Result、訊號、暫存目錄搜尋這些值，出現次數必須為 0。這比 precision／recall 更直接驗證「不把原值寫進結果」。
- 效能：在 pod 的 CPU／memory limit 下記錄冷啟動（含模型載入）與暖機後每頁、每份 64 頁論文的 p50／p95、峰值 RSS；規則型與模型型分開記錄。
- 每次 run 固定工具版本、rule set digest、模型 revision、Presidio recognizer 設定、正規化設定與 threshold；Privacy Filter 另記 transition-bias preset。

## 給 #107／#108 的交接，不是 placement 決定

- **#107：**作者、致謝、引用中的 PII 是否屬於例外；secret 與 PII 是否分開處置；檢查碼錯誤的「像身分證」字串怎麼處理；偵測錯誤或未覆蓋時的處置。
- **#108：**secret 與結構化 PII 掃描只需要抽出的 item 文字與 provenance，人名模型則需要較多 CPU 或記憶體；掃描要排在任何會把內容送給其他服務（VLM、summary）的步驟之前或之後，屬於 #108 要比較的資料依賴。訊號放進 enrichment `signals{}`、獨立 enrichment，或另立治理證據，也由 #108 決定。#87 的出口表把 #121 的候選列為「由 #108 採用時登錄」；本報告的候選都能在平台 worker 內執行，若改由平台外的服務執行，就要依 B4 登錄出口。
- 本研究的主張只有兩個：**訊號不得含原值或可窮舉的 hash**，以及**未掃描不等於沒有 finding**。

## 開放問題與 UNKNOWN

- 所有人名模型在繁中台灣論文上的 precision／recall：`未驗證`。spaCy 只有 7 句冒煙測試；CKIP、GLiNER、Privacy Filter 本次沒有執行。
- 所有模型在公司 K8s CPU 上的吞吐、記憶體、冷啟動：UNKNOWN。
- 台灣身分證檢查碼沒有找到政府公開的一手規格；新式統號是否沿用同一檢查碼，只有「比照編碼原則」的官方說法。
- CredSweeper `--hashed` 的 hash 演算法與加鹽、TruffleHog 是否有中文關鍵字的 detector：未讀到。
- CKIP（GPL-3.0）、TruffleHog（AGPL-3.0）、NVIDIA Open Model License、OntoNotes（LDC）在內部服務中的授權條件：本報告不做法律判斷。
- gitleaks 上游只出安全修補；Betterleaks v2 尚未正式發布。採用時要再查一次維護狀態。
- 研究內容只寫入本檔與 README 索引；未貼回 ticket、未 push。

## Sources

以下均為一手文件、原始碼、模型卡、論文或官方公告；S56 是例外，為大學課程講義（非官方），因為沒有找到政府公開的檢查碼規格。查閱日一律 2026-10-27。`main`／`latest` 連結內容可能變動；量測時需另記 commit、模型 revision 與 rule set digest。

- [S01 — gitleaks README][S01]
- [S02 — gitleaks default config][S02]
- [S03 — gitleaks licence][S03]
- [S04 — gitleaks v8.30.1 release][S04]
- [S05 — Betterleaks README][S05]
- [S06 — TruffleHog README][S06]
- [S07 — TruffleHog detectors][S07]
- [S08 — TruffleHog decoders][S08]
- [S09 — detect-secrets README][S09]
- [S10 — detect-secrets filters][S10]
- [S11 — detect-secrets KeywordDetector source][S11]
- [S12 — detect-secrets PotentialSecret（SHA-1）][S12]
- [S13 — detect-secrets PyPI][S13]
- [S14 — CredSweeper README][S14]
- [S15 — CredSweeper guide][S15]
- [S16 — CredSweeper architecture][S16]
- [S17 — CredData README][S17]
- [S18 — Kingfisher][S18]
- [S19 — Titus][S19]
- [S20 — Nosey Parker（已封存）][S20]
- [S21 — Docling Markdown serializer][S21]
- [S22 — Docling DocItemLabel][S22]
- [S23 — Presidio repository][S23]
- [S24 — Presidio supported entities][S24]
- [S25 — Presidio languages][S25]
- [S26 — Presidio adding recognizers][S26]
- [S27 — Presidio GLiNER sample][S27]
- [S28 — Presidio anonymizer operators][S28]
- [S29 — Presidio evaluation][S29]
- [S30 — Presidio PhoneRecognizer source][S30]
- [S31 — Presidio context enhancer source][S31]
- [S32 — Presidio slim spaCy engine source][S32]
- [S33 — Presidio PR #2072（TW national ID）][S33]
- [S34 — Presidio issue #2065（TW recognizers）][S34]
- [S35 — Presidio issue #2396（CJK full-width／zero-width）][S35]
- [S36 — spaCy zh_core_web_sm 3.8.0][S36]
- [S37 — spaCy zh_core_web_lg 3.8.0][S37]
- [S38 — spaCy zh_core_web_trf 3.8.0][S38]
- [S39 — CKIP Transformers README][S39]
- [S40 — CKIP bert-base-chinese-ner model][S40]
- [S41 — HanLP README][S41]
- [S42 — Stanza NER models][S42]
- [S43 — GLiNER paper v1][S43]
- [S44 — GLiNER repository][S44]
- [S45 — gliner_multi_pii-v1 model card][S45]
- [S46 — gliner_multi-v2.1 model card][S46]
- [S47 — knowledgator gliner-pii-base-v1.0][S47]
- [S48 — NVIDIA gliner-PII][S48]
- [S49 — OpenAI Privacy Filter model page][S49]
- [S50 — OpenAI Privacy Filter repository][S50]
- [S51 — OpenAI Privacy Filter model card PDF][S51]
- [S52 — OpenAI Privacy Filter output schemas][S52]
- [S53 — 個人資料保護法][S53]
- [S54 — 移民署：新式統一證號][S54]
- [S55 — 中央社 2020-12-16：新式統號第 2 碼][S55]
- [S56 — 身分證檢查碼課程講義（非官方）][S56]
- [S57 — 數位發展部：公眾電信網路號碼計畫][S57]
- [S58 — libphonenumber][S58]
- [S59 — Faker zh_TW locale][S59]
- [S60 — presidio-research][S60]
- [S61 — ai4privacy pii-masking-300k][S61]
- [S62 — Kubernetes NetworkPolicy][S62]
- [S63 — Hugging Face Hub environment variables][S63]

[S01]: https://github.com/gitleaks/gitleaks
[S02]: https://raw.githubusercontent.com/gitleaks/gitleaks/master/config/gitleaks.toml
[S03]: https://raw.githubusercontent.com/gitleaks/gitleaks/master/LICENSE
[S04]: https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1
[S05]: https://github.com/betterleaks/betterleaks
[S06]: https://github.com/trufflesecurity/trufflehog
[S07]: https://github.com/trufflesecurity/trufflehog/tree/main/pkg/detectors
[S08]: https://github.com/trufflesecurity/trufflehog/tree/main/pkg/decoders
[S09]: https://github.com/Yelp/detect-secrets
[S10]: https://raw.githubusercontent.com/Yelp/detect-secrets/master/docs/filters.md
[S11]: https://raw.githubusercontent.com/Yelp/detect-secrets/master/detect_secrets/plugins/keyword.py
[S12]: https://raw.githubusercontent.com/Yelp/detect-secrets/master/detect_secrets/core/potential_secret.py
[S13]: https://pypi.org/project/detect-secrets/
[S14]: https://github.com/Samsung/CredSweeper
[S15]: https://credsweeper.readthedocs.io/en/latest/guide.html
[S16]: https://raw.githubusercontent.com/Samsung/CredSweeper/main/docs/source/overall_architecture.rst
[S17]: https://github.com/Samsung/CredData
[S18]: https://github.com/mongodb/kingfisher
[S19]: https://github.com/praetorian-inc/titus
[S20]: https://github.com/praetorian-inc/noseyparker
[S21]: https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/transforms/serializer/markdown.py
[S22]: https://raw.githubusercontent.com/docling-project/docling-core/main/docling_core/types/doc/labels.py
[S23]: https://github.com/data-privacy-stack/presidio
[S24]: https://presidio.dataprivacystack.org/supported_entities/
[S25]: https://presidio.dataprivacystack.org/analyzer/languages/
[S26]: https://presidio.dataprivacystack.org/analyzer/adding_recognizers/
[S27]: https://presidio.dataprivacystack.org/samples/python/gliner/
[S28]: https://presidio.dataprivacystack.org/anonymizer/
[S29]: https://presidio.dataprivacystack.org/evaluation/
[S30]: https://github.com/data-privacy-stack/presidio/blob/main/presidio-analyzer/presidio_analyzer/predefined_recognizers/generic/phone_recognizer.py
[S31]: https://github.com/data-privacy-stack/presidio/blob/main/presidio-analyzer/presidio_analyzer/context_aware_enhancers/lemma_context_aware_enhancer.py
[S32]: https://github.com/data-privacy-stack/presidio/blob/main/presidio-analyzer/presidio_analyzer/nlp_engine/slim_spacy_nlp_engine.py
[S33]: https://github.com/data-privacy-stack/presidio/pull/2072
[S34]: https://github.com/data-privacy-stack/presidio/issues/2065
[S35]: https://github.com/data-privacy-stack/presidio/issues/2396
[S36]: https://github.com/explosion/spacy-models/releases/tag/zh_core_web_sm-3.8.0
[S37]: https://github.com/explosion/spacy-models/releases/tag/zh_core_web_lg-3.8.0
[S38]: https://github.com/explosion/spacy-models/releases/tag/zh_core_web_trf-3.8.0
[S39]: https://github.com/ckiplab/ckip-transformers
[S40]: https://huggingface.co/ckiplab/bert-base-chinese-ner
[S41]: https://github.com/hankcs/HanLP
[S42]: https://stanfordnlp.github.io/stanza/ner_models.html
[S43]: https://arxiv.org/html/2311.08526v1
[S44]: https://github.com/urchade/GLiNER
[S45]: https://huggingface.co/urchade/gliner_multi_pii-v1
[S46]: https://huggingface.co/urchade/gliner_multi-v2.1
[S47]: https://huggingface.co/knowledgator/gliner-pii-base-v1.0
[S48]: https://huggingface.co/nvidia/gliner-PII
[S49]: https://huggingface.co/openai/privacy-filter
[S50]: https://github.com/openai/privacy-filter
[S51]: https://cdn.openai.com/pdf/c66281ed-b638-456a-8ce1-97e9f5264a90/OpenAI-Privacy-Filter-Model-Card.pdf
[S52]: https://github.com/openai/privacy-filter/blob/main/OUTPUT_SCHEMAS.md
[S53]: https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=I0050021
[S54]: https://www.immigration.gov.tw/5385/7445/238440/238446/247454/cp
[S55]: https://www.cna.com.tw/news/asoc/202012160106.aspx
[S56]: https://people.cs.nycu.edu.tw/~tsaiwn/introcs/02_handouts/idcheck/
[S57]: https://www-api.moda.gov.tw/File/Get/moda/zh-tw/GvvKwygqxJeenqO
[S58]: https://github.com/google/libphonenumber
[S59]: https://faker.readthedocs.io/en/master/locales/zh_TW.html
[S60]: https://github.com/data-privacy-stack/presidio-research
[S61]: https://huggingface.co/datasets/ai4privacy/pii-masking-300k
[S62]: https://kubernetes.io/docs/concepts/services-networking/network-policies/
[S63]: https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables
