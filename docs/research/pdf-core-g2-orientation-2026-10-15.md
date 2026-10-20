# PDF-core G2：四方向、native／scan 混合 OCR 的 CPU 驗證

日期：2026-10-15（Asia/Taipei）；需求依據 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)，沿用 [G1 frozen cases](docling-pdf-core-g1-source-cases-2026-10-14.md)。**官方小型方向模型在 CPU 的四個受控方向都正確，座標逆轉換亦通過；接回 Standard 後仍有多欄閱讀順序缺口，混合頁還有字形與交付表示問題。F08／F09 與 G2 均未因此全面通過，沒有採用正式 Processing Profile。**

## 固定來源與比較方法

| 來源範圍 | 判準 |
|---|---|
| G1-C08–C11，SRC05 physical p3–6 | 同一清晰英語掃描的 0／90／180／270° 內容變體；全部 PDF Rotate=0、無文字層。選定 16 行／兩段沿用 G1-O03，來源頁與 bbox 必須映回各自物理頁。不是四份獨立文件。 |
| G1-C12，p7 | 五個 native blocks，包含繁中／英文同句；另有來源衍生 screenshot、原圖說。native 前後段各一次，圖內 OCR 屬同版圖片，不能冒充 native 原文。 |
| G1-C13，p8 | p7 的全頁 raster 版本，無文字層；核對完整可見的十個 ordered blocks，不能借用 p7 native layer 宣稱 OCR 成功。 |

來源 PDF、六張 frozen render 與 oracle SHA 都保留。獨立視覺／文字層檢查見 [source review](pdf-core-g2-orientation-2026-10-15/review/source-review.md) 及 [source checks](pdf-core-g2-orientation-2026-10-15/review/source-check.json)。沒有新增 CER／IoU 品質門檻，也沒有把模型錯誤改列來源模糊。

本輪分開保留四個比較接點：

1. **七次 Standard baseline**：四方向各一次 full-page OCR，p7 selective／full 各一次，p8 full 一次。沿用 Docling 2.102.0／Core 2.96.0、CPU4／batch1，明確固定既有 Chinese PP-OCRv6 detector／recognizer、二方向 line classifier 與 ONNX embedded dictionary。完整 `ConversionResult` 在 export 前保存；原始 det／cls／rec、native-before／OCR-before／merged-after、圖片 children／caption references 均保留。[Baseline 方法與結果](pdf-core-g2-orientation-2026-10-15/baseline/README.md)
2. **四次 learned orientation + OCR**：用完整頁 raster 判斷方向，依模型 label 回轉後跑相同 OCR 模型；不餵 oracle 角度、文字、區域或行號。四個模型 label 是 corrective CCW `0,270,180,90`，不是來源內容的旋轉標記。前處理、原分數／tensor、model revision／SHA、實際 CPU providers 均保存。[Primary sources 與方法](pdf-core-g2-orientation-2026-10-15/orientation-primary.md)
3. **四次 normalized Standard**：把分類器轉正的影像製成具名 derivative raster PDF，再接回同一 Standard／OCR 設定，確認 layout／order 的實際交付。原始 provider result 的 origin 保持 derivative SHA；另用 review wrapper 保存原 SRC05 page、inverse matrix、quadrilateral／envelope，不竄改 raw result 假裝直接處理原檔。[衍生來源與映射](pdf-core-g2-orientation-2026-10-15/normalized/README.md)
4. **兩次行級分類診斷**：以 p7 selective screenshot crop 與 p8 full-page 的相同已保存 input bytes，另測 per-call `use_cls=False`；模型／config／detector boxes 與 scores 全部相同，只隔離行級分類的影響，不直接改正式 profile。[Same-input 對照](pdf-core-g2-orientation-2026-10-15/line-cls/README.md)

`PP-LCNet_x1_0_doc_ori_onnx` 來自 [PaddlePaddle 官方 repository](https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori_onnx/tree/7330ab7039123e46af2dc03154b9969aa412c61d)，revision `7330ab7039123e46af2dc03154b9969aa412c61d`，Apache-2.0；weight 6,788,069 bytes，SHA 與 config 另存，並與[官方 LFS metadata](pdf-core-g2-orientation-2026-10-15/orientation-model-integrity.json)一致。使用既有 ONNX Runtime，沒有安裝 Paddle 或修改 baseline 環境／模型快取。Docling 的 OCR `use_cls` 是行級 0／180 分類，不能當成此四方向頁面模型；這次四方向路徑是明確的 adapter 候選，沒有宣稱 Docling 原生已接好此 stage。[官方模型 config](https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori_onnx/blob/7330ab7039123e46af2dc03154b9969aa412c61d/inference.yml)

## 方向、文字與閱讀順序的結果

| 工作 | 選定文字 | 順序／整體判斷 |
|---|---|---|
| 原始 Standard，p3／p4／p5／p6 | raw OCR 分別 16／14／12／16 行完全吻合 | p3 兩段各自正確，但右欄段落插在兩者之間；其他方向的最終段落亦未通過。不能因某頁有 16 行就宣稱方向／閱讀順序合格。 |
| 方向模型 + direct full-page OCR | 四頁 corrective angle 全對；每頁 16/16 行完全吻合，normalized PNG 與 117 項 OCR text list 四頁完全一致 | 原始 OCR stream 仍左右欄交錯；只按 oracle 過濾後的子序列正確，不算已完成閱讀順序恢復。 |
| 方向模型 + normalized Standard | 四頁 raw 各 16/16；最終兩段各自的內容與相對順序正確 | 每頁仍在兩段之間插入右欄「In-context learning」段落，因此沒有通過選定兩段的完整閱讀順序。 |

方向判斷由模型原始四分數 argmax 產生，沒有額外 softmax、confidence 門檻或 oracle fallback。四張轉正 PNG 的 SHA 完全相同，證明這組受控回轉的一致性；不把 winning score 約 0.92 當作語意品質保證，也不外推模糊、彎曲、斜拍、手寫或不同真實文件。

Standard baseline 與方向候選都輸出 216 dpi 尺寸，但 **像素 bytes 並非相同**：Docling backend 先以 4.5 倍 render 再 resize 至 3 倍，方向候選直接 PDFium scale3；normalized Standard 又經 derivative raster PDF 的 render。這是明確的 model／method／input transformation 比較，不能將文字變化全部歸因於單一方向 flag。[Render rounding 說明](pdf-core-g2-orientation-2026-10-15/baseline/coordinate-note.md)、[獨立 pixel／tensor 檢查](pdf-core-g2-orientation-2026-10-15/review/pixel-check.json)

## native／scan 混合與圖片交付

C12 selective OCR 保留原生五個 blocks，包括 `請確認 GPU worker 在 ready 狀態後，呼叫 OpenAI-compatible API。`；前／後 native 段落各一次。Full-page 模式把原生 cells 換成 OCR 結果，最終把 `OpenAI` 改成 `OpenAl`（大寫 I 變小寫 l）。因此 full-page OCR 不能一律當成混合頁的升級設定。原生與 OCR 合併前後的 cells、原位置及重複候選均保存，沒有只憑合併後字串猜來源。[官方 cell 合併行為](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/base_ocr_model.py)

兩個 C12 baseline 的 screenshot 都只有 3/5 literal 文字 blocks 完全吻合：breadcrumb 有繁簡字差異，長操作指示在 raw recognizer 成空字串；二方向 classifier 對該行輸出 180。C13 raster 控制在 raw provider／document 條目只有 7/10 literal blocks 吻合，混排 native line 的 raster 版本也出現 `OpenAl`；document traversal 的 caption 又排在圖內文字 children 前。Main Markdown 只呈現 4/10 完全吻合的可見 blocks，圖片 placeholder 沒有呈現圖中文字。不放寬繁簡／引號／關鍵條件要求來計為整體通過。

相同 pixels 的 `use_cls=False` 對照讓兩個長操作指示都重新出現；十五個 raw recognition slots 中只有這兩項由空字串改成句子，detector 輸出完全一致。P7 圖片 filtered texts 從 4→5，p8 全頁從 9→10；p7 的繁體指示文字恢復，但引號改成 curly quotes，literal 比較仍 3/5。P8 指示把 `連結` 寫成 `連结`，`OpenAl-compatible` 也沒有修好，literal blocks 仍 7/10。引號／中性空白允許變化的文字診斷另列於獨立 review，沒有改寫原輸出或 oracle，breadcrumb 字形缺口始終保留。這定位了特定漏句的 line-classifier 影響，沒有把「找回句子」當成文字完全正確，也不支持所有文件一律關閉 classifier。[診斷結果與完整性](pdf-core-g2-orientation-2026-10-15/line-cls/comparison.json)

Stock Docling 結構已有圖片 children 與原 caption reference；image OCR、caption／picture 的歸屬可從保存的結構核對。原 caption 在 Markdown 保留一次，沒有把 screenshot OCR 塞進 native prose。但 stock Markdown 仍只有 `<!-- image -->`，不是能讓 projection 取同版圖片補充內容的穩定 image key。這一部分需要 Canonical mapper／Markdown delivery 的接點；不能說「Markdown 沒顯示 OCR」就等同辨識沒跑，也不能說「raw OCR 有文字」就等同已完整交付。

## 來源位置與可恢復輸入

方向候選保存完整頁尺寸、原 physical page／source SHA、predicted corrective angle、原圖至 normalized raster 的 3×3 matrix 及 inverse；OCR 每個 polygon 都映回原始物理頁 PDF points。採 continuous raster edges，pixel sample center 另明示，不混用 `W−x` 與 pixel-index 的 `W−1−x`。獨立檢查通過 936 個 raw／filtered polygons、四角變換、像素精確回轉與 tensor／原分數一致性。[每頁映射範例](pdf-core-g2-orientation-2026-10-15/orientation/runs/p4/source-mapping.json)、[saved evidence checks](pdf-core-g2-orientation-2026-10-15/orientation/verification.json)

Normalized Standard 的 raw result 保持 derivative identity、normalized page images／尺寸與內部 provenance 一致。另存 wrapper 把 normalized PDF top-left points 映至原始 source top-left points，保留原 page 尺寸與 item refs／內容／順序；不是已完成的 Canonical document adapter。對原 stock OCR crop 的 mapping 則保留 backend rounding／resampling 限制，沒有杜撰像素精度。持久化 raw stage 輸入／輸出支持重建證據，但本輪沒有執行 Pod 替換、完整 retry／recovery 或 Acceptance。

## 資源、完整性與採用判斷

| 工作 | child wall 秒 | sampled process-tree peak | 限制 |
|---|---:|---:|---|
| 七次原始 Standard | 4.537–8.142 | 2.231–3.275 GiB | 含模型載入、觀測與程序啟停，一頁一次 |
| 四次 orientation + direct OCR | 2.361–2.380 | 2.257–2.273 GiB | 方向 inference 本體約 1.986–2.352 ms；不把整個 child 時間當成此小模型耗時 |
| 四次 normalized Standard | 6.05–6.57 | ≤3.364 GiB | derivative rasterization 邊界另記；非單一變因效能比較 |
| 兩次 same-input line-cls-off OCR | 0.790／1.054 | 0.746／2.085 GiB | p7 image crop／p8 full page，各一次；與既有 cls-on input bytes 配對 |

CPU4／batch1、actual ONNX providers、Torch CPU options、模型／dictionary／runner SHA 均保存。全部 scored worker 在 shared lock 下串行，啟動前 available ≥8 GiB，180 秒／6 GiB sampled RSS 軟停止、0.25 秒取樣，成功退出且回收；沒有 AUTO／MPS／MLX／CoreML／GPU 或 remote model inference。方向首次 attempt 在推論後因 `PosixPath` JSON serialization 失敗，完整保留後只修 writer、重新凍結再跑 final 四頁，未混進品質／latency 表；line-cls 的 config-equality preflight 也在 OCR 前因 Path／serialized string 比較停止，保留後修正比較並重新凍結，final 仍只有兩次 OCR。

本輪亦實證了設定解讀的界線：Docling 2.102 的 `lang` resolver 雖選 language model-set，但 `artifacts_path=None` 且未指定 model paths 時，不會把該 model-set paths 傳給 RapidOCR；實際可回到 library defaults。故不能單看 `lang=['en']` 或 `['en','zh-tw']` 就聲稱跑過 English／混排 recognizer。本輪明選的實際模型皆是固定 Chinese v6，constructor params、resolved config、live providers 及 embedded dictionary 都有證據。這補充先前 source-level 語言選擇論述，沒有更動前輪 raw 結果。[Language/path source audit](pdf-core-g2-orientation-2026-10-15/baseline/language-path-note.md)、[官方 pinned constructor](https://github.com/docling-project/docling/blob/v2.102.0/docling/models/stages/ocr/rapid_ocr_model.py)

**保留官方四方向小模型作候選；保留 selective OCR 作混合頁比較起點。** 尚未解決多欄閱讀順序、必要 image OCR 文字保真、raster 混排字形與同版 image reference 交付；沒有以平均行數或高 score 掩蓋缺口。這也不代表所有文件都應關閉 line classifier，仍需看有無可靠頁面正向化與實際旋轉文字。

獨立逐案例與反例檢查見 [output review](pdf-core-g2-orientation-2026-10-15/review/output-review.md)／[JSON](pdf-core-g2-orientation-2026-10-15/review/output-review.json)。G1 與前六輪 606 個 payload 不變，原環境／模型快取與 production code 保留；本輪只新增研究與有界 runner，未 commit／push。完整性與資料清單見 [validation](pdf-core-g2-orientation-2026-10-15/validation.json)／[artifacts](pdf-core-g2-orientation-2026-10-15/artifacts.json)。

接續 G2 仍有 inline formula／code 偵測及回填、其他完整表格／來源與方法組合，也保留上一輪 title／無書籤附錄／章節 parent 缺口。完整文件 holdout、公司 GPU／vLLM、高頻 ingest、Canonical Acceptance／delivery 與完整 pilot 未於本輪通過。
