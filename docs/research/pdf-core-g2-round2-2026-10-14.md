# PDF core G2 第二輪：CPU 缺口比較與處置

[Research index](README.md) · [G2 計畫](docling-pdf-core-g2-pipeline-start-2026-10-14.md) · [第一輪 CPU](pdf-core-g2-local-cpu-2026-10-14.md) · [需求 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

2026-10-14（Asia/Taipei）。**已完成7次有界CPU推論與2次無模型assembly重放。獨立圖片OCR值得保留，但現有設定仍有錯字；V2表格與既有continuation均未修好各自缺口；CodeFormulaV2在CPU可跑，所選code區塊正確、分段公式仍失真。** G2尚未全面通過，沒有選定正式Processing Profile。

## 本輪範圍與比較結果

沿用固定G1來源、oracle、原physical page與SHA；不修改原稿／預期，不把第一輪失敗換成容易案例。本輪不改`src`、既有prototype或baseline環境。模型推論依序執行，reading-order重放可能與其他CPU工作重疊，毫秒級assembly時間不作效能比較。

| 任務 | 本輪比較 | 結果與處置 |
|---|---|---|
| **圖片OCR：G1-O01** | 固定中央panel 1×、實際PictureItem原頁scale3、固定panel放大2×；既有RapidOCR三模型 | 直接圖片OCR可找回第一輪缺失的完整指示句，但前兩種仍有繁簡錯字，2×輸入的指示句有detector框卻回空辨識。三次皆未滿足來源保真；保留獨立圖片OCR路徑，不能把upscale或全域繁簡轉換當修復。 |
| **閱讀順序：G1-O03** | 第一輪相同OCR／layout／assembled結果，重放stock與固定歷史continuation-v3 | JSON／Markdown完全相同，右欄bullet仍插在左欄兩段間。v3只改merge，不能修此一般多欄order缺口；不否定其原continuation任務。 |
| **表格：G1-T01/T02** | 重用原完整TABLE cluster，官方TableFormerV2 CPU stage，matching=True；普通表control＋六panel表 | T01六個值與三個critical comparison保留；T02仍有panel／header合併、設定合列及漏值，必要比較未通過。不採用這套V2配置修T02；未完整分類84點錯誤，不提供全表error%。 |
| **公式：G1-E07 Eq2** | 新固定CodeFormulaV2，oracle equation crop、官方engine／`<formula>` prompt／postprocess，CPU FP32 | 原始與postprocessed輸出都缺`0／Otherwise`分支，並把註腳2寫成指數。89個生成tokens、正常EOS、未撞512上限；這個crop／配置未通過，不能歸因於截斷。 |
| **Code：G1-C02區塊** | 同模型，受控PDF七行code crop、`<code>` prompt | 七行文字／註解、`<=`、nested if及outer else完全相符，Python AST相等；59個生成tokens、正常EOS。只支持所選區塊，未驗inline code、偽碼、detector、回填或完整文件。 |

## 圖片OCR：已定位與仍未知

三次都直接保存detector／classifier／recognizer的raw output與最終library output、位置與crop mapping。三個ONNX session均實際驗證為`CPUExecutionProvider`，intra-op4／inter-op1、batch1；不是只看accelerator設定。

- 固定panel 1×可辨識完整指示句，但「結／統」被轉錄成「结／统」；中央breadcrumb也有字形錯誤。
- 實際PictureItem scale3涵蓋全部五項，未把指示句裁掉；可取得該句但仍有錯字，其他中央文字也有退化。
- 2×panel有該句detector框，recognizer卻回空字串／score0，之後被blank-filter移除；放大沒有提供通用改善。

第一輪沒有保存pre-layout raw OCR，且兩輪影像來源／尺度與路徑不同，因此仍不能宣稱第一輪的漏句唯一發生在detector、recognizer或輸出合併。本輪沒有接到完整same-revision Canonical圖片補充內容／required-work contract。

[OCR review](pdf-core-g2-round2-2026-10-14/ocr/review.md) · 逐位置結果 (`pdf-core-g2-round2-2026-10-14/ocr/selection-review.json`) · 離線檢查 (`pdf-core-g2-round2-2026-10-14/ocr/review.py`)

## 閱讀順序：與continuation責任分開

使用歷史Git commit `f46f51115cd0444a59c22b4de13666bd1ef93602` 的v3，SHA `ab5f1bb51b86c1cd8966c645e6e96df839c86460ce265be079451530402935ed`，與原native-v1 method相符；目前工作樹v1並未拿來冒稱v3，也沒有修改它。

完整provider result重建後parsed object roundtrip相等，15個text的文字／orig／label／provenance未變。兩種assembly的document JSON／Markdown與第一輪byte相同。幾何診斷發現同欄兩段bbox約0.3992 PDF point重疊，與stock左→右規則交互作用；這是後續候選的具體輸入，不是已完成的根因ablation或修復。未刪除右欄文字、修改bbox或硬接段落造通過。

[Order review](pdf-core-g2-round2-2026-10-14/order/review.md) · 重放／trace索引 (`pdf-core-g2-round2-2026-10-14/order/summary.json`)

## 表格：新來源的V2結果

T02本輪是SkillOpt p8 Table2六panel，並非舊p7 Table1；全部84個source數值bbox都在完整TABLE cluster內。候選使用既有snapshot `51559fad3946873e26a6f9b8e912f948e8745bef`，權重209,735,468B，沒有重下載。官方stage的144dpi crop會resize至448×448；未另外試新resize或人工切panel。

候選runtime是Docling2.124.0／IBM-models4.0.3／parse7.16.0／Core2.96.0；第一輪是2.102.0／3.15.0／6.2.0。因此這是候選stack比較，不能把差異歸因為單一模型。CPU FP32、1 thread、batch1；T02生成157tokens、正常EOS、未撞512上限，必要關係仍錯。T01所選stage內容保留正確，但本輪未重做caption／Markdown／Canonical交付。

下一個表格方向應比較能處理多panel的producer／分區方法或table VLM；即使分區，仍須保留整個Table2的panel、caption、條件及84點分母，不只挑容易panel宣稱通過。現有結果不足以選定新方法。

[Table review](pdf-core-g2-round2-2026-10-14/table/review.md) · 逐critical結果 (`pdf-core-g2-round2-2026-10-14/table/review.json`)

## 小型公式／code模型與成本

匿名讀取官方HF metadata後，取得CodeFormulaV2固定revision `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`。權重630,993,616B（約631MB），下載19.514秒，時間與推論分開；下載bytes的SHA與該revision官方LFS hash相符。存入獨立scratch cache，未改原baseline模型快取或安裝套件；trust_remote_code=False。Granite-Docling-258M metadata所列權重515,093,104B，revision `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`；本輪未下載／執行它，不能由大小宣稱CPU品質或時效合格。模型成本 (`pdf-core-g2-round2-2026-10-14/models/model-costs.json`) · 下載／檔案hash (`pdf-core-g2-round2-2026-10-14/models/codeformula-download.json`) · 官方LFS核對 (`pdf-core-g2-round2-2026-10-14/models/model-integrity.json`)

CodeFormulaV2官方模型卡說明120dpi區域輸入、公式LaTeX及保留縮排的code；本輪使用相同任務prompt與pinned Docling engine／postprocess，但**固定oracle crop、CPU FP32與512-token探索上限**。所選公式crop從G1的216dpi圖以LANCZOS重採樣至約120dpi；code從受控PDF按固定bbox render。不是正式pipeline的偵測、18%擴張crop、完整enrichment或來源回填。[官方模型卡](https://huggingface.co/docling-project/CodeFormulaV2)、[pinned stage](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/code_formula/code_formula_vlm_model.py)

實際所有model parameters均為`cpu`／`torch.float32`，4 intra-op／1 inter-op，batch1、compile=False、quantized=False。保存raw文字、實際generated token IDs、EOS、cleaned文字與來源；不能拿engine metadata的input＋output token總數當生成tokens。code檢查另以`<=→<`、內層emit退縮排、移除註解三個負例確認會拒絕。公式輸入的兩個分支均已目視，模型raw output已漏分支，並非只有postprocess丟字。

Model runner (`pdf-core-g2-round2-2026-10-14/models/probe.py`) · 模型結果／來源核對 (`pdf-core-g2-round2-2026-10-14/models/review.json`)

## 本機資源觀察與限制

| 子任務 | 次數 | 每次child wall秒 | sampled peak GiB |
|---|---:|---|---|
| 圖片OCR | 3 | 0.792／1.061／0.794 | 1.192／1.048／1.194 |
| TableFormerV2 | 2 | 4.187／3.147 | 1.201／0.867 |
| CodeFormulaV2 | 2 | 4.975／4.724 | 2.111／2.121 |
| Stock／v3 assembly | 2 | 各約1.4ms的assembly區段；未作速度比較 | 未另作可比memory measurement；不列為0 |

推論各一次、單一worker順序執行、既有OS cache未清空；每child 180秒、0.25秒sampled tree RSS、6GiB軟停止，不能當macOS硬limit或production budget。七次均正常退出且無guard／timeout；不能外推完整文件、穩定latency、CPU/GPU加速倍數或高頻SLO。

CodeFormula的`result.json.initialization_seconds`量到的是eager stage constructor後的重複`initialize()`呼叫，**沒有涵蓋載入**，不可當作模型初始化時間。child wall包含import／load／推論／輸出；`inference_seconds`涵蓋predict_batch前處理／生成／decode，公式約2.011秒、code約1.698秒，不等同純generation。

OCR最初一次保存Path設定失敗、table supervisor最初缺psutil，都發生在推論前，已保留startup failure；之後改用正確序列化／既有venv。這些不算模型品質錯誤或額外成功推論。兩個主runtime均未升級或修改安裝。

## 下一階段與保留缺口

1. 圖片OCR需比較較能保留繁中字形的具名recognizer／OCR組合或VLM crop；保持位置與完整句子驗收。
2. 一般多欄order須比較專門的順序／幾何處理或頁面VLM；continuation merge與order各自驗證。
3. 表格保留V1對照，V2此配置不作T02修復；下一候選仍須用同一完整邏輯表與critical比較。
4. CodeFormulaV2保留為code候選，但要補真實code／偽碼、inline、偵測與回填；公式需其他模型／裁圖配置比較。Granite-Docling仍是可考慮的本機小模型候選，不因尚未下載就宣稱必須公司GPU。
5. Remote大模型需要時，依已允許的暫用OpenAI API進行；公司self-hosted Qwen3／vLLM仍以相同來源另驗，不能把模型效果或效能當成等效。

本輪尚未執行整頁VLM、remote API、GPU、其他OCR模型、另外三張完整G1表、Canonical mapper／Acceptance／custody／recovery或高頻負載。來源圖像與模型輸出由本次Codex交叉核對，沒有另行人類逐字認證。執行資料與hash另見manifest (`pdf-core-g2-round2-2026-10-14/artifacts.json`)；本機檔案尚未commit／push。
