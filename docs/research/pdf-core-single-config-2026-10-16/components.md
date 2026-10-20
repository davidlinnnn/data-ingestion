# 單一 Standard 配置：元件選擇與證據界線

2026-10-16。這是 Step 1 的既有證據整理，**不是一次新實驗、已合格配置或新推論授權**。結論沿用 [retro 收斂](../../reviews/pdf-core-retro-closure-2026-10-16.md)：保留一組具名 Standard 基底，但現有元件不能拼接成已滿足所有必含需求的結果。PaddleOCR-VL 建置、整合及新推論維持暫停。

本文只負責 layout、table、OCR、圖片分類與 heading；公式／code／圖意等完整配置由本資料夾主文件決定。沒有讀取封存 holdout、執行模型、安裝套件、下載模型或修改既有證據。

## 一組基底，而非歷輪最佳輸出的拼接

建議主配置的共同底座是 `StandardPdfPipeline`、Docling 2.132.0／Core 2.99.0，使用同一個明確指定的 PDF backend。根據目前 render preflight，主提案以 `PyPdfiumDocumentBackend` 為全文件 backend；不能逐頁依答案挑 renderer。這是新的組合提案：舊 2.102 CPU 的文字／表格成功，及新版 heading 的 stage replay，都不能直接轉成這組配置的品質通過。

| 工作 | 此一提案保留的元件與固定值 | 為何保留 | 現有證據與必要限制 |
|---|---|---|---|
| Layout | `docling-project/docling-layout-heron@8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；新版 `LayoutObjectDetectionOptions.from_preset("layout_heron_default")`；Transformers engine、FP32、`compile_model=False`、`score_threshold=0.3`；`create_orphan_clusters=True`、`skip_cell_assignment=False`、`keep_empty_clusters=False` | 有多輪實際 Standard evidence、普通表與六個必要圖片定位結果；沒有可靠證據支持現在換 layout 模型能修好已知語意缺口。 | 歷史 2.102 的 Heron finding 不等於新版 engine／backend 的等價性。多欄閱讀順序與 title 角色仍有問題，不能把 layout 找到區域當作完整閱讀結構正確。 |
| Table | `TableStructureOptions(mode=ACCURATE, do_cell_matching=True)`，即 V1；`docling-project/docling-models@fc0f2d45e2218ea24bce5045f58a389aed16dc23` 的 accurate 權重／config；以明確本機 artifacts tree 固定，不能依 moving `main` 自動下載。`do_table_structure=True`；官方 stage scale=2（144 dpi） | 普通表 G1-T01 的六個數值、三個 critical comparisons 與 caption 歷史核對通過。V2 同來源仍錯，沒有既有證據支持以 V2 替換能修好 T02。 | G1-T02 六 panel 表在 producer JSON 已有 headers／rows／setting binding 錯誤；V1、V2 都不合格。未完整分類 84 點，不能聲稱它只是允許的 ≤5% 輕微誤差，也不推論所有複雜表都做不到。 |
| 頁面 OCR | `RapidOcrOptions(backend="onnxruntime", lang=["ch"], force_full_page_ocr=False, bitmap_area_threshold=0.05, text_score=0.5, use_det=True, use_cls=True, use_rec=True)`；三個實際 ONNX 路徑明選：Chinese PP-OCRv6 det-small／rec-small、v2 mobile 0/180 line classifier；embedded dictionary，不另套繁簡轉換 | selective OCR 保留混合頁原生文字；全頁 OCR 會把可靠 native layer 換成 OCR 字串。既有 v5 mobile／server recognizer 沒有通過相同五項來源，不應僅因宣稱支援繁中就替換。 | `use_cls=True` 是原比較基底的實際值，**不代表這個值已合格**：兩個已測長指示被 line classifier 翻轉後回空。只有兩個 same-input 診斷不足以採全域 `use_cls=False`，因此這裡保留明確的已知 blocker，不能宣稱已找出完整 OCR 解法。 |
| 獨立圖片 OCR | 與上列同一具名 OCR producer，直接處理實際 `PictureItem` image；輸出須保留 image ref、來源 bbox、原文 caption 關係與同版 supplement 身分 | 第一輪頁面 OCR 與後續圖片 crop 證明兩者不可混為一個成功條件；獨立圖片 OCR 可找到部分被頁面流程漏掉的內容。 | 是 required-work 的配置責任，**不是 stock `do_ocr=True` 已完整交付**。現有 OCR 有漏指示／繁中字形錯誤，固定 crop 成功亦不能轉成實際 layout crop／全文件已成功。Canonical image key／交付由後續接點處理。 |
| 圖片分類 | `docling-project/DocumentFigureClassifier-v2.5@f859dfbff5c9916cd996942d4b0db7fa25808220`；`TransformersImageClassificationEngineOptions` 對應 Transformers engine，FP32、`compile_model=False`、`top_k=None`；`do_picture_classification=True` | 六個來源 × 兩種 crop 的 broad family 均相符；權重約 16 MB，已有真實 CPU 與 meta.classification 證據。 | 只是分類／路由證據，不是圖意、OCR 或 chart 數值證據。分數未校準；原生 chart gate 只接受 top class bar／line／pie，不看低信心或次佳類別。不得用 gate／other／低分豁免必含工作。 |
| Heading | `HeadingHierarchyOptions(enabled=True, use_bookmarks=True, use_numbering=True, use_style=True, use_font_style=False, style_size_tolerance=0.05, numbering_schemes=None, max_level=6, bookmark_match_threshold=0.8)`；`generate_parsed_pages=True` | 原生規則 stage，無新模型：所測 WikiSkill 正文 9/9、書籤附錄 4/4 層級正確；比保持所有 headers level1 有具體證據支持。 | 舊結果使用 DoclingParse font cells 與 `use_font_style=True`；本提案因 PyPdfium 只有一般 TextCell，明關字型樣式，`use_style=True` 只保留 cell 尺寸訊號。這是不同配置，不直接移轉品質結果。歷史無書籤附錄 0/4、無編號控制頁的六個章節絕對深度 0/6；native parent 仍非語意章節 parent。不能以 native label 不是 TITLE 單獨判失敗，必須看可靠 title 與實際層級／歸屬。 |

共同本機研究設定保留 `device="cpu"`、4 threads、Torch inter-op=1、layout／OCR／table batch=1、同時一個 worker。ONNX intra-op=4／inter-op=1；明關 CUDA／CoreML／DML／CANN 等 providers，並在後續真正執行時核對 live providers。這是避免不可比較的實驗設定，不是公司效能配置或 p95／高頻 ingest SLO。

RapidOCR 其餘選項沿用已保存的 `producer.json`（preprocess、detector threshold／unclip、recognizer shape 等），不是另做 tuning：`Rec.rec_batch_num=1`、`Cls.cls_batch_num=1`；原 baseline 的 `use_cls=None` 實際解析成 True，本提案將其明寫。新版 `lang=["ch"]` 是 canonical 拼法，品質依實際模型 bytes 與 dictionary，不依語言標籤推定。

## 模型身分固定

以下 SHA 是既有實際 bytes 身分，不是本輪新下載／推論結果。

| 資產 | SHA-256 |
|---|---|
| Heron `model.safetensors` | `00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c` |
| TableFormer V1 accurate 權重 | `2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9` |
| TableFormer V1 accurate `tm_config.json` | `984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd` |
| `PP-OCRv6_det_small.onnx` | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` |
| `PP-OCRv6_rec_small.onnx` | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` |
| embedded dictionary，UTF-8 newline joined 18,708 characters | `f7aa897ca828a4c7c9e2739c30f9161a33306d532f020bcdb91dcfb664a5507e` |

Figure classifier 的 revision、weight bytes／hash 以既有 [download.json](../pdf-core-g2-images-2026-10-14/classifier/download.json) 為準；本輪不另建立第二套 model manifest。其餘模型資產含 config／preprocessor 身分見原始 [Standard method](../pdf-core-g2-local-cpu-2026-10-14/runs/skillopt-p8/method.json) 與 [凍結模型／來源清單](../pdf-core-g2-orientation-2026-10-15/baseline/frozen-inputs.json)。

四方向需求另外保留既有 `PP-LCNet_x1_0_doc_ori_onnx@7330ab7039123e46af2dc03154b9969aa412c61d` 的 adapter 證據（weight SHA `af9a0a4f317ff0709ce752067807f819cb15d883f8ecad89f28df1c6ee2d9c92`，不是 PaddleOCR-VL 候選）。它不是 stock Standard 頁面方向 stage。現有實驗僅證明四個受控 raster 變體方向正確與來源逆映射；整合需明確限制掃描頁與 derivative identity，不能為了方向把所有 native／mixed 頁 rasterize。**此頁面路由與全文件組合尚未證明，因此不把四方向標成提案已完整可執行。**

## 直接核對的歷史實驗及限制

| 證據 | 實際版本／執行單位 | 對此提案能支持什麼 |
|---|---|---|
| [第一輪](../pdf-core-g2-local-cpu-2026-10-14.md)／[原始 table review](../pdf-core-g2-local-cpu-2026-10-14/table-review.json) | Docling 2.102.0、Core 2.96.0、IBM models 3.15.0、parse 6.2.0；六個單頁 CPU probes | V1 普通表所選關係成功；T02 錯誤已在 producer；所選英文文字完整但閱讀順序錯。不是 2.132／PyPdfium 完整 pipeline。 |
| [第二輪](../pdf-core-g2-round2-2026-10-14.md)／[V2 review](../pdf-core-g2-round2-2026-10-14/table/review.json) | V2 stage：Docling 2.124.0、Core 2.96.0、IBM models 4.0.3、parse 7.16.0；重用完整 table cluster，非全文件 | V2 的 selected ordinary table 成功，T02 仍錯；是 stack 比較，不是單模型 causal ablation。不支持本次直接換 V2。 |
| [第三輪](../pdf-core-g2-round3-2026-10-14.md)／[OCR review](../pdf-core-g2-round3-2026-10-14/ocr/selection-review.json) | 固定同一 685×230 panel／detector／classifier，只換 v5 mobile／server recognizer；另有 Granite 元件 probes | v5 mobile 五項 2 項、server 3 項相符，沒有證據作繁中直接替換。Granite 的其他任務結果不變成本配置的補綴輸出。 |
| [Heading](../pdf-core-g2-heading-2026-10-15.md)／[actual stage results](../pdf-core-g2-heading-2026-10-15/review/output-review.json) | Docling-slim 2.132.0／Core 2.99.0／parse 7.22.3 的 stage replay，輸入為舊 assembled document＋全 28 頁 font cells／outline | 編號與書籤優先處理有用，title／無書籤附錄／semantic parent 仍未完成。不是完整 fresh conversion，也不是新 backend 的 heading 品質。 |
| [方向／混排](../pdf-core-g2-orientation-2026-10-15.md)／[actual producer](../pdf-core-g2-orientation-2026-10-15/baseline/runs/controls-p7-selective/producer.json) | 舊 Standard 七頁、四方向 direct OCR、四 normalized Standard、兩個 same-input cls-off 診斷 | 支持 selective OCR、實際 v6 CPU providers／dictionary 身分與四方向候選；不支持全域關 classifier 或全文件先 rasterize。 |
| [分類](../pdf-core-g2-images-2026-10-14/classifier/results.md)／[method](../pdf-core-g2-images-2026-10-14/classifier/method.json) | 舊 2.102／Core 2.96，實際 12 crop calls，同六來源兩種 crop，非 12 個獨立樣本 | 支持 broad family 路由候選；不支持圖意／chart 正確或完整 enrichment lifecycle 已驗。 |

## 已查本機官方實作的接點

本輪唯讀檢查 `/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/` 的已安裝 2.132 官方程式碼；沒有更改或執行 stage constructor。以下為可重查的官方 pinned 同版 source 入口，並非本輪做了網路最新版調查：

- [pipeline_options.py](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py)：V1 與 V2 options 分開；新版 layout options；RapidOCR 單語言／明選模型 paths；heading options 與 parsed pages 需求。
- [stage_model_specs.py](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/stage_model_specs.py)：Heron 預設 Transformers engine；ONNX 使用另一 repo，不能為了 CPU 悄悄改成未測 ONNX 版本。
- [standard_pdf_pipeline.py](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py)：OCR→layout／table→assembly，reading-order 後呼叫 heading；需要 backend outline／parsed pages。這是官方 composition 接點，不保證每個功能品質。
- [table_structure_model.py](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/table_structure/table_structure_model.py)：V1 由 `artifacts_path` 找權重，options 沒有獨立 revision 欄位；固定 artifacts tree／hash 才能固定模型。其 table scale 是 2.0。
- [pypdfium2_backend.py](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/pypdfium2_backend.py) 與 [heading_hierarchy_model.py](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/heading_hierarchy/heading_hierarchy_model.py)：PyPdfium 可取 outline／SegmentedPdfPage，但普通 TextCell 沒有 font_name；heading 會保留尺寸訊號，不能復用舊 font-cell stage 的完整樣式論述。

## Step 1 判斷

這組元件足以形成**同一個待驗 Standard 基底**，不足以宣稱一個滿足必含功能、已準備推論的 challenger。已知六 panel 表結構錯誤、多欄順序、圖片 OCR 漏指示、無編號／無書籤 hierarchy，以及未完成的四方向整合，均不能靠「換成新版＋全部 flags 打開」自動消失。公式／inline／code 必含缺口仍須由主配置明示，不可在這份元件表旁加未驗 fallback 然後宣稱完整。

若主配置無法給每個必含工作一條具名、內容保真且可交付的路徑，Step 1 的正確結果就是 **尚不可進入新推論**，而不是自動擴增模型清單或修補已知題目的輸出。

未執行新模型、全配置或公司 GPU／負載；所有選擇仍是提案，歷史局部成功不能替代其品質與延遲資格。
