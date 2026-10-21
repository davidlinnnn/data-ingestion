# PDF-core Step 1：單一配置草案與可執行性判定

2026-10-16。承接 retro 收斂 (`docs/reviews/pdf-core-retro-closure-2026-10-16.md`)及使用者「先進行第一步」的指示，只整理既有證據、模型／版本／設定與必要缺口。**Step 1 已完成；可提出一組具名 Standard 主幹，但現有證據不足以封成完整、可執行的新候選。暫不進入 Step 2 實作或新推論。**

這不是把各輪最好輸出拼成成功文件。下列元件是在一份未來配置中的選擇意圖；舊 2.102／DoclingParse 的結果與新版 stage replay 只支持原範圍，沒有轉成這個新組合的品質紀錄。Paddle 建置、後續整合與新推論維持暫停。

## 一組明確主幹

提案 ID：`standard-2132-pdfium-selective-enrichment-draft1`。以同版 released Docling SDK 加必要 enrichment 為方向，沒有引入另一個整頁 VLM 主流程。模型與精度皆顯式指定，避免 AUTO 隨本機可用套件改路線。

| 部位 | 單一提案的選擇與設定 | 證據界線／未解處 |
|---|---|---|
| SDK／Core | Python 3.12.13、`docling-slim==2.132.0`、Core 2.99.0、Parse 7.22.3、pypdfium2 5.14.0 | 使用同版 heading／enrichment／chart 接口，不把新版 class 拼進舊 Core。尚無這份完整配置的依賴 lock 或執行證據。 |
| Pipeline／backend | `StandardPdfPipeline`＋明確指定 `PyPdfiumDocumentBackend`，整份文件同一路徑 | 避開已觀察到的兩張 DoclingParse 黑色遮蔽輸入；不是證明新 backend 的文字／表格品質。2.132 的預設 backend 實為 threaded DoclingParse，本提案不是 default setup。 |
| Layout | Heron `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；`layout_heron_default`、Transformers CPU FP32、compile=False、score threshold=0.3 | 保留已具實測的模型身分；新版 engine／backend 組合未驗。閱讀順序不能由 layout 成功推定。 |
| Table | TableFormer **V1 accurate**、cell matching=True；`docling-models@fc0f2d45e2218ea24bce5045f58a389aed16dc23`，固定實際 artifacts tree／hash | V2 沒修好相同六 panel 表，故不替換。V1 普通表有局部成功，但 T02 的 headers／rows／setting binding 已在 producer 層錯誤。 |
| 頁面 OCR | RapidOCR／ONNX Runtime，明選既有 Chinese PP-OCRv6 det-small／rec-small＋v2 line classifier；selective OCR、bitmap threshold=0.05、text score=0.5、det／cls／rec=True | 保留 native layer，不全頁一律 OCR。兩次 cls-off 診斷不足以決定全域關閉；保留的 cls-on 比較基底仍有已知漏句。 |
| 圖片 OCR | 同一 OCR producer，獨立處理實際圖片；位置與 image key 留在 supplement | 不是打開 `do_ocr` 就完成。圖片工作清單、實際 crop、文字保真與同版交付未完成。 |
| 四方向 | 保留既有 PP-LCNet 頁面方向 adapter 的證據；不把它當 stock Standard flag | 不是 PaddleOCR-VL。四個受控方向與逆映射成功，但掃描／混合／native 頁的全文件路由仍未證明，因此尚未綁成可執行步驟。 |
| 章節 | 官方 heading hierarchy；bookmarks／numbering／style=True、font_style=False；tolerance=0.05、max_level=6、bookmark threshold=0.8；parsed pages=True，outline 須另行攜出保存 | PyPdfium 只有 cell height，缺完整字型資訊。舊字型 stage 成功不能直接移轉；title／無書籤附錄／語意 parent 仍有缺口。 |
| 圖片分類 | `DocumentFigureClassifier-v2.5@f859dfbff5c9916cd996942d4b0db7fa25808220`；CPU FP32、compile=False、top_k=None，偏好啟用 | 只用於分類／路由；低分或 other 不免除必含圖片工作。 |
| 已偵測 code 區塊 | `CodeFormulaV2@ecedbe111d15c2dc60bfd4a823cbe80127b58af4`、Transformers CPU FP32、compile=False、quantized=False；code=True | 歷史七行 code 是 512-token component probe；2.132 native stage 固定 2048 cap／temperature=0，並非同配置已驗。只處理已標記 CodeItem。 |
| 全文公式／inline code | **必含，producer／完整方法尚未選定；阻擋完整候選** | CodeFormulaV2 的公式案例失敗；native gate 不發現普通正文 inline。舊 context／official DocTags 配置亦有真實內容錯誤，不能換名稱復跑。 |
| 圖意／chart | **必含，完整 producer／接點尚未選定；阻擋完整候選** | 暫用 `gpt-6-luna` 的圖意、受控 chart 有局部內容證據；不是完整 Docling 整合或 Qwen3 證據。Smol 預設描述不復跑；不憑原生 chart API 存在就宣稱模型品質通過。 |
| Metadata／證據／交付 | 上游 metadata 與可靠正文 title 分來源；完整 provider／診斷先保存；Markdown 主內容＋同版結構／圖片／enrichment supplement | 正式 mapper、image key 與可攜交付仍未完成；F13／F14 的缺失不能只存 raw 即算完成。 |

共同研究設定：CPU4 threads、Torch inter-op=1、ONNX intra-op=4／inter-op=1、layout／table／OCR batch=1、一次一份文件；page／picture images=True、page image scale=2、parsed pages=True。這是可比較的本機起點，不是要求正式環境只用 CPU；公司 GPU 與高頻資格仍在後續階段。

TableFormer 實際 stage crop scale=2；code stage 宣告 option scale=2，**實際取圖卻由 class scale=1.67、bbox expansion=0.18 控制**。後者還只取 `prov[0]`，不能當跨頁／多 fragment crop。這些值來自靜態 source，尚未對本組配置捕捉實際 engine input。完整模型 SHA／OCR 設定來源見[元件筆記](pdf-core-single-config-2026-10-16/components.md)，版本與接點見[runtime 筆記](pdf-core-single-config-2026-10-16/runtime.md)，公式／圖像取捨見[enrichment 筆記](pdf-core-single-config-2026-10-16/enrichment.md)。

## 為什麼不能直接進下一步

| ID | 問題類型 | 對必含需求的影響 | Step 1 處置 |
|---|---|---|---|
| B1 | 必要方法未能成立 | F13＋F14 inline 缺全文 discovery、具名且保真的重建、原位／跨頁交付；已有 clear-source prime／identifier／code literal 錯誤 | 不用字元 gate、confidence fallback 或局部成功假裝覆蓋。完整候選未成立；需要新的方法假設，不是再調 serializer 就可解。 |
| B2 | 既有內容／結構錯誤 | F02／F04／F05／F08／F09 的多欄順序、六 panel table 關係及長指示漏句仍未解 | 不復跑已證實不能修該缺口的 V2／v5 配置，不用全域繁簡轉換或關 classifier 追單題。新 backend 也不能被當成已證實修復。 |
| B3 | 部分內容可行，完整接點未驗 | F11／F12 direct API 局部成功，但完整圖片 inventory、原生 producer／schema、typed chart、來源綁定與所需補充資料未就緒 | 保留自己的模型身分與局部證據；不填入 Qwen3、不把圖意當 literal OCR、不把 chart2code 當原始碼。 |
| B4 | 結構／映射與訊號不足 | F03／F17 的 title、章節歸屬、無書籤附錄仍有問題；選擇 PyPdfium 又少字型訊號 | 不以 native TITLE label 作新門檻，也不假定把第一個 heading 升成 title 即可修復。 |
| B5 | 執行環境不完整 | 目前 2.132 是 slim；缺 IBM models `>=4.0.2,<5`、Accelerate、RapidOCR、ONNX Runtime 等；Hub2.2.0 不符該 extra `<2` | 沒有建環境或安裝。舊 IBM3.15 不搬進新 SDK。後續須先解析真正所需依賴並固定 lock；補套件不會解決 B1–B4。 |
| B6 | 完整交付未驗 | F18–F21 同版 mapping、完整診斷／provider、Markdown 到圖片及補充結構、fresh/restored 尚待 G3 | 設計可規劃，不能以原生 JSON 存在或 compare-only 通過取代完整交付。 |

上述有「已觀察失敗」也有「尚未驗證」；兩者沒有混算模型錯誤率。F15／F16／F22 繼續延後，F10 是可選且偏好開啟；其他 18 項必含均在配置草案 (`pdf-core-single-config-2026-10-16/proposal.json`)逐項對應，沒有刪掉尚無方法的欄位。

## 有界驗證登錄：草稿，不是可執行排程

本步投入上限為 **0 模型載入、0 新推論、0 安裝／環境建置、0 holdout 內容讀取**。本步只完成 source／metadata／既有結果查核。原三組配置已結束；此草案沒有新增推論名額。

若未來有可說明的完整方法，建議至多登錄 **1 組完整配置**。可重用的開發來源為既有 WikiSkill28頁、SkillOpt27頁、Memory-R1 20頁，以及 G1 的 OCR／繁中／掃描／公式／code／表格正負例；它們都是已曝光資料，並非 unseen confirmation。實際抽取範圍、全部必要來源單位、oracle、對照 baseline、依賴／模型／prompt 身分、資源與成本上限須在新推論前固定，不能把此清單冒充已完成的新 registration。

開始條件至少包含：B1 有具名完整方法、其他必要工作有清楚路徑、所需最小交付接點能保留正確輸出、環境／模型身分固定，且新的比較有明確增益假設。若只能靠猜內容、逐題修補或大量新 detector／parser／graph repair 才滿足，應帶具體成本回來決策。停在這裡比重新跑 75 頁後再次確認相同缺口更有用。

## Step 1 的決策輸出

**保留一組 Standard 主幹的設計，但不選定完整 challenger、不啟動實作或模型。** 現在最關鍵的決策問題是：是否存在一條以少量通用整合，真正涵蓋全文公式／inline 內容與已知必要關係的新增方法；現有資料沒有足以直接指定這條方法的證據。

因此本次沒有把「下一步補格式接點」當作默認可行，也沒有自動恢復 Paddle。若要繼續，應先針對 B1 與 B2 提出具體、有限的新方法命題及預期改善，再決定是否投入下一輪；不要求使用者現在放寬必含需求或自行挑模型。

本提案的核對紀錄 (`pdf-core-single-config-2026-10-16/verification.json`)保存本次文件／來源身分、需求覆蓋、靜態限制與舊 evidence 比對。沒有修改舊評分、manifest、production、套件或模型。這是可行性規劃的完成，不是 G2 或 Canonical Acceptance 通過。

未做實際 import／kernel／模型執行、完整新配置、數學 renderer、公司 serving 或高頻負載；現有元件成功不能轉成這份提案的品質／latency 結論。
