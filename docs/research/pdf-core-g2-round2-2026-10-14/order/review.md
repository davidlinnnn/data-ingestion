# G2 第二輪：閱讀順序的有界重放

2026-10-14（Asia/Taipei）。**既有 continuation-v3 無法修正 G1-O03 的插段。** stock 與 v3 都將右欄「In-context learning」放進左欄兩段之間；兩個輸出的 document JSON／Markdown 與第一輪完全相同。本輪只重放 assembly，沒有重跑 OCR、layout、table 或其他模型。

## 固定輸入與方法

- 輸入為第一輪 english-scan-p1-ocr 完整 provider result (`docs/research/pdf-core-g2-local-cpu-2026-10-14/runs/english-scan-p1-ocr/conversion-result.json`)，SHA256 `2cbc578c3f957e24b08d72ef1451905d4b1d3e34428f8cadf939cf1990bfd514`；使用其中相同的 pages、15 個 assembled TextElements、OCR／layout 結果及來源座標。
- 原掃描 PDF 的 physical p1（原來源 printed p3），SHA256 `7856cfe6127948d506ca5fad750e915134be362b5e1436c70b378f42a6fda2a0`。評分使用固定 G1-O03 的兩段／16 行 oracle；未改來源或 oracle。
- 第一個 assembly 使用 installed Docling 2.102.0／Core 2.96.0／IBM models 3.15.0 的 stock `ReadingOrderModel`／`ReadingOrderPredictor`；第二個只把 predictor 換成既有 `ContinuationPredictor`。
- 選定的 adapter 是 Git commit `f46f51115cd0444a59c22b4de13666bd1ef93602` 的 `src/pdf_processing/continuation.py`。本輪保存的 原始 bytes (`historical-continuation-v3.py`) SHA256 `ab5f1bb51b86c1cd8966c645e6e96df839c86460ce265be079451530402935ed`，與歷史 native-v1 的 method (`docs/research/paper-pdf-functional-2026-10-11/dgm-group5/16-2505.22954v1/native/method.json`) 完全相符。
- 目前工作樹的 `src/pdf_processing/continuation.py` 是 **v1**、SHA256 `791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772`；未執行或修改它，不能把它稱為歷史 native-v1 的 v3。
- CPU、4 Torch intra-op threads／1 inter-op thread、單 worker、offline；沒有建構 `StandardPdfPipeline` 或 page inference models。assembly 各一次；同時可能有其他 CPU 工作，毫秒級 elapsed 只作診斷紀錄，沒有效能比較意義。

runner (`run.py`) · 完整比較／版本／設定與來源 hash (`summary.json`)

## 重建與保真檢查

原 provider 檔保持不動。`InputDocument` 的 custom constructor 無法直接載入其 serialized fields，因此只對保存的 input metadata 使用 `model_construct`；不開 PDF backend。其餘完整 `ConversionResult` 經 Pydantic validation。四個 confidence `null`（document／page 的 parse_score 與 table_score）在記憶體還原為 NaN；再次序列化仍為原本 null。使用原 `model_dump_json` alias 模式，未改寫 `cref`／`$ref`。

在執行 assembly 前，roundtrip JSON (`conversion-result-roundtrip.json`) 與首次 provider JSON 的整份 parsed object **完全相等**，涵蓋文字、預測、diagnostics、timings 與 confidence。這只確認本案例的重建，不能外推為所有 union 類型的通用 loader；本頁 15 個元素全是 TextElement，沒有 table／picture／container union 歧義。

Reading order 後僅把原 document 的 page image 原樣附回，對應 Standard pipeline 後續的 image attachment，避免把 page image 缺省誤判為內容差異。兩個新 document 的全部欄位與原 document 相同；text/orig/label/provenance 序列也全部相同。每個 reassembled conversion result 有獨立檔名，並非宣稱它是首次 provider bytes。

## 比較結果

| 檢查 | stock | 既有 continuation-v3 |
|---|---|---|
| 左欄兩段文字，允許斷行／斷字／range dash 正規化 | 兩段完整相符 | 兩段完整相符 |
| 兩段相鄰、不被右欄內容插入 | **不符合** | **不符合** |
| `predict_reading_order` 順序 | 相同 | 相同 |
| caption／footnote／merge mappings | 全部空 | 全部空 |
| 全部 15 個 text、orig、label、provenance 序列 | 與原輸出相同 | 與原輸出相同 |
| document JSON SHA256 | `e685fa8ce61185099be657afa9e2d493206706b30b8d54435abee898b7edf35a` | 相同 |
| Markdown SHA256 | `8088fc2e8910300306926d1a475e4e636ee5a7554e4751e100fd0fed3274af37` | 相同 |

順序仍是 `#/texts/1` 左欄第一段 → `#/texts/2` 右欄 bullet → `#/texts/3` 左欄第二段。negative check 明確要求檢出這個插段，兩者皆被檢出，不會因兩段字串各自正確就誤報通過。

stock JSON (`stock/document.json`) · stock Markdown (`stock/document.md`) · stock trace (`stock/predictor-trace.json`) · v3 JSON (`continuation-v3/document.json`) · v3 Markdown (`continuation-v3/document.md`) · v3 trace (`continuation-v3/predictor-trace.json`)

## 缺口的位置與處置

v3 僅覆寫 `predict_merges`，繼承 stock `predict_reading_order`、caption 與 footnote 方法。**它是 continuation merge 修正，不能當作一般多欄重排方法。** 這個案例沒有 merge edge；因此 v3 的其他 continuation 能力並未在此被觸發，不能據此淘汰其原本任務。

只讀幾何診斷 (`geometry-diagnostic.json`) 顯示，同欄兩段的 layout bbox 垂直重疊約 **0.3992 PDF points**，使 upstream `is_strictly_above` 為 false；第一段與右欄 bullet 同時符合 `follows_maintext_order`、strict-left 與 vertical IoU≥0.8 的條件，實際 `_init_l2r_map` 連出 `#/1/3 → #/1/7`。這定位到「保存的 layout 幾何＋stock order 規則」的交互作用，支持後續比較專門的多欄順序／幾何處理，或 VLM 頁面轉換。未修改 bbox、做 ablation 或執行新 order 算法，不能宣稱已唯一隔離整套流程的根因。

本輪處置：**不採用 v3 作這個插段缺口的修補方案**；保留 stock 作對照，將一般多欄 reading-order 列為未解項。後續候選須獨立驗 order 與 merge，且保留原文字與來源位置，不能靠刪掉右欄文字或硬接段落讓案例通過。

未驗：真正跨頁／跨欄 continuation、完整頁面／全文正確性、含圖片／表格／container 的 assembly、Canonical mapper、GPU、VLM、並行負載與 SLO。本輪沒有生產程式變更或新的模型執行；不代表 G2／Canonical Acceptance 通過。
