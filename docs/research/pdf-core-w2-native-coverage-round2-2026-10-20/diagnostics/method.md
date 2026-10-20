# W2 第 2 回合：零推論 stage 定位方法

本檔依本機固定 `docling-slim==2.132.0`、`docling-core==2.99.0` 原始碼，準備保存結果重播；不新增 conversion、不改 upstream 資料或輸出。

`trace_native.py` 從完整 `result.json` 還原 `ConversionResult` 的 input metadata、pages、assembled；以 `InputDocument.model_construct` 避免開啟 PDF backend。依 runner 保存的 `reading-order-options.json` 建立官方 `ReadingOrderModel`，只包裝此 instance 的官方呼叫以觀測 input/output。官方 `ReadingOrderPredictor` 是幾何規則，沒有 learned model inference。[ReadingOrderModel](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/reading_order/readingorder_model.py:714>)、[ReadingOrderPredictor](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/postprocessing/reading_order_rb.py:404>)。

每份重播先驗證完整 texts、groups、body、furniture、tables 結構相等，以及 pictures 除後附 image 之外欄位相等。若提供已保存 Markdown，再驗證逐字相等。任一失敗即停止該 trace，不能宣稱有 stage 定位。第一回合 BERT p2 已通過上述所有等價斷言，結果保存 `selfcheck-bert.json`。

需要保存的 stage 證據：原始 layout 模型 cluster（`layout-raw.json`）、postprocessed layout/page cells（`result.json` pages）、assembled 元素含 cluster cells、reading-order predictor 輸出、caption/footnote 關聯、paragraph merge mappings、final document 含 content_layer 與 provenance。原始 layout 與 final layout 差異要分辨模型框與 cell assignment/postprocessing。assembled array 的先後只是 deterministic tie-break，不是正文序 oracle。

定位標準：

- 同一 cluster/cell text 在 predictor 之前已含跨欄混文：upstream layout box/cell assignment；若 raw layout 已跨欄則優先定位 layout box。
- 正確分開的 assembled 文段，官方 predictor 將順序排錯：reading-order predictor。
- predictor 的各片段順序正確，但 `predict_merges` 的 mapping 將不應相連的片段併入同一 final paragraph：paragraph merge；跨欄、跨頁的正確延續不能算錯。
- 頁碼/stamp/header 原始或 post-layout label 已被當成 text，最終進入 BODY：furniture 標記。官方只對 PAGE_HEADER/PAGE_FOOTER 指派 FURNITURE；caption/footnote 要依 label 與關聯另查。
- source cell 尚有內容，final 缺少時需比較 assembled 與 materialization，不能僅憑未匹配 anchor 判定漏文。

官方 predictor 把 header/body/footer 分開排序，按頁合併；`predict_merges` 略過 header/footer/table/picture/caption/footnote，再依 TEXT、跨頁或左右關係以及字尾/字首規則決定續接。[官方 predictor 與 merge 規則](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/postprocessing/reading_order_rb.py:404>)；[官方 materialization 與家具 layer](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/reading_order/readingorder_model.py:610>)。

`private-shapes.json` 依本輪實際 `_shape_lines`／`_shape_bounding_boxes` 格式以 `BoundingBox.model_validate` 還原。PyPdfium 的 shape bounding boxes 確實非空，不得假定 backend 無幾何訊號。[separator 取得與運用](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/reading_order/readingorder_model.py:718>)。

## 只供主線評估的官方選項（未執行）

- `heading_hierarchy_options.enabled=True`：只針對 heading level。官方以 bookmark/numbering/style 取階層，須沿用相同文件再評，不能從此推論正文漏文或讀序改善。[官方 options](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:2205>)。
- 若代表頁顯示 upstream layout 框／家具標記錯誤，可評估官方 `layout_options.model_spec` 的 Heron 101 或 Egret 系列；這是新的模型 conversion，並非本回合零推論定位。官方提供模型清單但不保證本語料改善。[官方 model specifications](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/layout_model_specs.py:82>)、[官方選項](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:1637>)。
- `use_reading_order_separators` 只對 backend 能提供 visible shape geometry 時有意義；baseline 預設已開，因此不能把「再打開」當候選。空 private shapes 的 PyPdfium 保存結果也無資料可用此開關恢復。[官方選項說明](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/pipeline_options.py:2195>)。
- 不建議為 paragraph merges 編造官方開關：本固定版本 `ReadingOrderOptions` 只有 model_names/use_page_separators，未暴露停用 paragraph merge 的 public pipeline option。[官方 ReadingOrderOptions](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/models/stages/reading_order/readingorder_model.py:55>)。

尚未依本輪總數挑選代表頁；階段判定須等全量候選與頁圖核對，以上方法不是本輪已證實失敗統計。
