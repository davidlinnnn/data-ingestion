# PDF core G2：圖片分類、圖意與 chart 比較

[Research index](README.md) · [G2 計畫](docling-pdf-core-g2-pipeline-start-2026-10-14.md) · [前次 API 比較](pdf-core-g2-api-2026-10-14.md) · [需求 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

2026-10-14（Asia/Taipei）。**圖片 classifier 已完成 CPU 比較；SmolVLM 預設描述未保留兩張圖的必要意思；暫用 GPT-6 Luna 保留所選流程圖／操作畫面的必要關係，以及四張受控 chart 的13個數值／歸屬與估值標記。Pie 的欄位表示仍需 adapter。** 這輪補上先前未執行的模型／任務，未選定正式 profile，G2 尚未全面通過。

## 本輪執行與結果

使用 G1 固定來源、SHA、physical page、bbox、oracle 與品質門檻。新跑兩個 Standard CPU 頁面，重用一個既有 NCCU 頁面；圖片分類為六個來源各兩種 crop、共12次 batch1，並非12個獨立來源／holdout。另跑兩次 SmolVLM CPU 描述、六次暫用 API。模型 worker 依序執行；研究／離線檢查可能重疊，沒有改套件、production code、來源或 oracle。

| 任務／candidate | 實際執行 | 所選來源結果與處置 |
|---|---|---|
| Standard／Heron 實際圖片發現 | WikiSkill p4、controls p2 新跑；NCCU p3 重用第一輪 | 找到6個實際 PictureItem；與固定區域逐圖核對，必要文字、流程連線、座標軸／legend／mark 均完整。未擴成整文件圖片 inventory 已合格。 |
| DocumentFigureClassifier-v2.5 | CPU FP32，固定6 crop＋實際 layout bbox6 crop | 流程圖、電腦截圖、bar、linear／log line、pie 的 broad family 均相符；8張 chart crop 皆進原生 chart gate。保留為分類候選，不以 score 保證圖意／數值品質。 |
| SmolVLM-256M-Instruct | CPU FP32，官方 description preset／prompt／200-token stage，S05／S07 固定 crop | 只描述「table/text/icons」或「page/blue boxes」，漏三層／四步流程與必要 UI 操作關係。15／40 tokens 正常 EOS；此預設配置未滿足兩個 F11 案例，非200上限截斷。 |
| 暫用 GPT-6 Luna：圖意 | S05 WikiSkill Figure2、S07 NCCU panel，具名 JSON task | 保留三層角色、不變性、四步／回圈、條件更新；UI breadcrumb、畫面角色與兩種進入途徑保留，沒有編造後續操作已完成。僅所選圖意範圍通過。 |
| 暫用 GPT-6 Luna：chart 資料 | C03 printed bar、C04 linear雙系列、C05 log10、C06 pie，逐圖固定輸入 | 13個數值／series或category歸屬符合固定門檻；印值 exact、未印值 estimated、linear／log 正確。Pie 使用 `"about 25%"`／`"about 75%"` 且 `unit=null`；數值語義通過，typed欄位／unit解析仍未交付。 |

[Classifier 結果](pdf-core-g2-images-2026-10-14/classifier/results.md) · SmolVLM runner (`pdf-core-g2-images-2026-10-14/description/probe.py`) · API runner (`pdf-core-g2-images-2026-10-14/api/run.py`)

## 固定輸入與實際 pipeline crop

S05 來自 WikiSkill `2608.27454v1` p4，圖像與 caption 分開；S07 使用先前 byte 相同的685×230 NCCU中央 panel。C03–C06 來自原創受控 PDF p2，各依 frozen envelope render scale3。既有 control box 頂緣略切標題字形，沒有改 bbox／補字；軸、單位、legend、數字及 mark 完整，API亦明列標題裁切的不確定性。輸入／mapping (`pdf-core-g2-images-2026-10-14/inputs/input-manifest.json`) · 獨立 oracle 參照 (`pdf-core-g2-images-2026-10-14/inputs/oracle-references.json`)

實際 PictureItem 來自同一 baseline 的完整 provider／document。以其未修改 bbox重新render scale3，不冒充 baseline cached crop pixels。S05流程圖與四個chart的bbox比固定envelope小，但逐圖目視必要內容仍完整；Wiki回圈筆畫貼下邊界，完整方向及 Next Iteration 可辨。NCCU原生項目是較完整的截圖，包含固定panel。Envelope面積重疊率僅作幾何描述，不作來源意思完整率。原生 inventory (`pdf-core-g2-images-2026-10-14/layout/native-inventory.json`) · [逐圖 coverage review](pdf-core-g2-images-2026-10-14/inputs/native-coverage-review.md)

兩個真實 PDF 本次匿名公開 GET200，原始 bytes SHA 與 G1 相同；四張控制圖是原創 toy charts，沒有上傳 controls PDF 其他來源衍生頁。API只收到六張固定 crop，沒有收到整份 PDF、oracle 或正確答案；credential沿用隱藏TTY／memory-only方式，不寫入檔案／ticket。公開來源核對 (`pdf-core-g2-images-2026-10-14/inputs/source-safety.json`) · [來源說明](pdf-core-g2-images-2026-10-14/inputs/provenance.md)

## Classifier 與原生 gate 的界線

固定 `docling-project/DocumentFigureClassifier-v2.5` revision `f859dfbff5c9916cd996942d4b0db7fa25808220`，權重16,378,200B，官方 LFS SHA相符；匿名下載3.439秒、獨立cache。實際所有parameters CPU／float32、4threads／interop1／batch1。保存完整26類softmax、native `meta.classification`與deprecated annotations；原生PictureItem的source provenance、caption refs等非分類欄位維持原樣。下載 (`pdf-core-g2-images-2026-10-14/classifier/download.json`) · 設定 (`pdf-core-g2-images-2026-10-14/classifier/method.json`) · [primary source audit](pdf-core-g2-images-2026-10-14/classifier/primary-research.md)

原生 chart gate只看top class是否為bar／line／pie，不設confidence threshold、不回退第二名，亦無literal unknown／no-text分類。9個離線controls確認低分bar也可進入、top other／second bar不進入；流程圖與操作截圖不進chart extractor，但仍有必含F11圖意工作。這個classifier不能讓圖意或chart數值工作自動獲得豁免。Gate 檢查 (`pdf-core-g2-images-2026-10-14/classifier/check.py`)

圖片描述另有預設5% page-area與可選class allow／deny filter。以本次實際6個PictureItem metadata作無模型dispatch重放，預設均會送出；再用明確synthetic小面積／deny／provider exception／短輸出對照，觀察到小圖與deny不呼叫engine，exception會被stage轉成空字串並寫入description，短輸出則沒有對應yield。這些是installed component的mock契約證據，不宣稱完整pipeline刪掉文件內容。Required-work必須分辨skipped／failed／empty／missing，不能以「無例外」算完成。Description gate／錯誤重放 (`pdf-core-g2-images-2026-10-14/gates.py`) · 結果 (`pdf-core-g2-images-2026-10-14/description-gates.json`)

## 小型描述模型與 API 的內容比較

SmolVLM固定 `HuggingFaceTB/SmolVLM-256M-Instruct` revision `7e3e67edbbed1bf9888184d9df282b700a323964`，權重513,028,808B，官方LFS hash相符，獨立cache下載24.149秒。使用官方small-model preset／`Describe this image in a few sentences.`，明確CPU FP32、compile=False、quantized=False、trust_remote_code=False；兩張固定crop直接呼叫官方 `_annotate_images`，沒有把detector、size filter或完整enrichment接點冒稱已驗。這是預設配置的有界比較，不推論整個SmolVLM family都不適用。模型檔案 (`pdf-core-g2-images-2026-10-14/description/download.json`) · 實際方法 (`pdf-core-g2-images-2026-10-14/description/run/method.json`)

兩次都短於200-token預算且EOS。Model decode前的文字已漏必要意思；已知engine尾端 `rstrip(pad_token)` 另外把完整終止字串清成 `<end_of_utteranc`，不把清理缺陷誤報為模型截斷。Raw generated IDs、EOS、未清理decode、engine與stage輸出皆保存。

API沿用使用者指定 `gpt-6-luna`／官方Chat endpoint；`low` reasoning、`high` image detail、JSON object、6144 completion token budget、concurrency1，每例一次且無retry。圖意用明確components／relations／steps，chart用axes／scale／units／data／printed-or-estimated；與Smol的預設自然語言prompt不同，是模型＋task設定的比較，不作單一模型的因果排名。[官方模型身份](https://developers.openai.com/api/docs/models/gpt-6-luna) · 六次回應與usage (`pdf-core-g2-images-2026-10-14/api/observations.json`)

獨立來源review確認S05所有必要方向、條件與不變性，S07的畫面意義／操作邊界，以及四張chart的13點歸屬與numeric／scale／status條件。數值checker以原先印值exact、linear／log軸長2%、pie各sector±2pp為門檻；7個反例拒絕印值錯誤、系列錯置、log當linear、估值標成印值、pie類別互換、tolerance內但破壞step2 tie，以及編造log單位，另驗3個含邊界／3個超界。數值容差不取代critical關係；本次tie與factor10意思另作source review。Pie的`about ...%`只在評分中作有明確格式的百分比解析，raw provider輸出未修改，也不宣稱typed adapter已完成。[內容 review](pdf-core-g2-images-2026-10-14/review/output-review.md) · 逐任務 verdict (`pdf-core-g2-images-2026-10-14/review/output-review.json`) · 13點與反例 (`pdf-core-g2-images-2026-10-14/review/chart-checks.json`) · 數值 checker (`pdf-core-g2-images-2026-10-14/review/check_chart_outputs.py`)

本輪API沒有跑Docling原生Granite chart model，亦沒有把OpenAI模型改名冒充Granite。Pinned原生chart是本地producer／CSV或summary/code parser；這次是direct HTTP的具名JSON候選，接回Docling／Canonical仍需明確adapter。原文caption、圖內literal text、生成圖意與數值估計保持不同來源身分；chart2code不等同還原作者原碼。

## 資源與 latency

| 工作 | 本機 child wall／client round trip 秒 | 資源與限制 |
|---|---|---|
| Standard：WikiSkill p4／controls p2 | 5.244／3.680 | CPU4／batch1；sampled peak約1.604／1.581GiB；NCCU重用既有結果 |
| Classifier：12crop共用一個eager model | 3.982 | CPU FP32；sampled peak0.566GiB；stage各0.094～0.107秒，含模型load的constructor0.068秒 |
| SmolVLM：兩次描述共用一個model | 7.992 | CPU FP32；sampled peak2.191GiB；`_annotate_images`約2.421／2.609秒 |
| API：S05／S07 | 12.060／10.127 | client round trip，遠端GPU／queue／純inference不可觀測 |
| API：bar／linear／log／pie | 4.636／5.310／7.330／4.969 | 各一次；非p95、整文件或高頻SLO |

本機採180秒／6GiB sampled tree RSS軟停止、0.25秒sample、啟動前available≥8GiB，沒有改PROD預算；全部正式worker exit0／reaped。Classifier首次sandbox監測失敗在推論前停止，保存startup artifacts後用同一offline worker在可讀process資訊的權限下完成，非模型錯誤或額外成功推論。六次API均HTTP200／finish_reason=stop／無refusal；總5284 prompt／3574 completion tokens，其中680 reasoning。時間不與本機predict或公司vLLM GPU直接換算加速倍數。

## 採用判斷與下一個缺口

保留小型classifier作分類／路由候選，並保留API圖意／chart路徑的內容證據。SmolVLM這個預設配置不作S05／S07必要圖意的交付方法；GraniteVision4B先前CPU600秒逾時的表格結果保留，沒有在本輪盲重跑或改用本機GPU，亦未拿歷史表格結果冒充圖意／chart已驗。公司Qwen3／vLLM與GraniteVision GPU候選仍須另外評估。

四張chart只證明受控case；真實分布的chart、更多流程圖／照片／裝飾圖、不同印值／軸／模糊程度仍需來源與holdout。Pie的raw百分比字串與unit-null，明確列為typed adapter缺口；不修改raw response或評分oracle。原生chart gate與description的空值／filter風險也須接到required-work對賬，不能靠confidence當作全內容自動品質保證。

接續G2仍要補heading recovery、四方向／混排OCR、行內公式／code的偵測與回填、其餘完整G1表及適用案例，再組合可送G3的候選。公司GPU／高頻負載、完整Canonical交付／Acceptance／恢復、551頁pilot均未於本輪完成。未commit／push，需求44個feature表格列與G1／前幾輪原始證據保留。

完整性核對 (`pdf-core-g2-images-2026-10-14/verify.py`) 驗來源與前輪payload SHA、兩個小模型下載／官方LFS、六個API request body重建hash、回應與parsed JSON、credential pattern及本機連結；資料見 artifact manifest (`pdf-core-g2-images-2026-10-14/artifacts.json`) 與 validation (`pdf-core-g2-images-2026-10-14/validation.json`)。
