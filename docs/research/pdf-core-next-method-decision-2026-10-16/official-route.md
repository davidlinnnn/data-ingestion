# Paddle 官方路徑對下一個方法決策的意義

2026-10-16；只查核既有封存 primary sources 與既有 synthetic 結果。Paddle 建置、整合與新推論維持暫停。本筆記不更新舊候選狀態，也不新增執行授權。

**判定：完整 PaddleOCR-VL-1.6 與已測 Standard／DocTags 是不同方法，但其原生交付已有必要條件缺口，現在不建議恢復模型試驗。** 本輪起初考慮過條件式小試驗；綜合 literal 轉換與原 Q4 跨頁要求後，改為只提出零模型交付接點原型，見[主決策](../pdf-core-next-method-decision-2026-10-16.md)。不能由 `inline_formula`／`algorithm` label 推定全文公式／code 成功，也不能縮成 raw-only 成功來迴避主要交付缺口。

| 實際官方機制 | 可支持的推論 | 不支持的推論／已知反例 |
|---|---|---|
| 完整頁面先 layout／閱讀順序，再逐區域裁圖，分流 OCR／formula／table／chart，最後輸出原生 Markdown。 | 不是把另一個 VLM 換進同一 DocTags parser；能測試不同 discovery、裁圖與交付路徑。 | 官方 benchmark／模型介紹不能轉為我們必含功能或 latency 通過。官方也明確區分完整 pipeline 與單獨 VLM。 |
| PP-DocLayoutV3 的 label 有 `inline_formula`、`display_formula`、`algorithm`。 | 具備不同於 Standard CodeItem gate 的版面辨識入口。 | label 集合不是 recall 證據；`algorithm` 不是所有 code／inline code 的保證。 |
| `filter_overlap_boxes` 在 inline_formula 與另一 box 重疊比例 >0.5 時丟棄 inline_formula。 | 重疊正文中的公式可能交由含公式的整段文字 OCR 處理；這可形成待驗假設。 | 不能把 inline_formula detector 當成完整公式 inventory，更不能宣稱每一行內式都會送入 formula specialist。 |
| `merge_layout_blocks=True` 由 `merge_blocks` 合併特定同 label 的 `text` 圖片；長寬比過高則不合併；同組後續 blocks 的 image 可為 None。 | 在一些跨欄／上下錯落的文字區域增加單次辨識上下文。 | 不是通用 inline_formula→正文插回，也不是語意段落／跨頁重組器；`group_id` 不證明文字關係保留。 |
| `algorithm`／普通文字走 `OCR:`；formula 走 `Formula Recognition:`；table／chart 各自分流。 | 不必靠通用大 VLM 自行完成所有任務；元件角色可稽核。 | 沒有專用 code prompt／code model／inline code type。正確縮排、literal、code fence 必須實測，不能由 algorithm routing 推定。 |
| 原生 Paddle Markdown 直接保留 formula content；algorithm formatter 只 strip 換行。 | 正確含 delimiter／fence 的 provider 輸出可保留；可避開已觀察到的 Docling exporter 部分改寫。 | 不自動替裸 formula 加 delimiter，也不替裸 algorithm 加 code fence。既有 synthetic 已直接證實。 |
| 共用 MarkdownConverter 有 paragraph continuity，但 PaddleOCRVLResult 未開 `use_seg_flag`，一般 blocks 以雙換行串接，且不讀 group_id。 | 只有已在單一 provider block 內的 prose＋inline 才能直接保留上下文。 | 分開的 inline_formula 即使同 group 仍不會組回句子；既有 synthetic 已證實。不能挪用 PP-StructureV3／ResultV2 的 continuation 功能來宣稱 Paddle 路徑具備它。 |
| `format_block_content` 只選擇 JSON 的 block_content 是否套用 Markdown formatter。 | False 可避開這個末端 formatter，利於歸因。 | False 仍無法關掉上游 math normalization；不是未改動的原始 VLM 輸出。True 不提升辨識／discovery，也不補段落或 code 型別。 |
| `restructure_pages` 可跨頁合表、重定 heading level、串接頁面。 | 可作原生跨頁表格／章節功能的候選接點。 | 未見通用跨頁公式／code／段落語意合併；saved-dict 路徑另會去掉 `^#+\s`，不能用它無損重建所有 code。 |

## 若未來恢復，仍須滿足的條件（本輪不授權）

只接受一個固定完整官方配置，先在已曝光開發資料上驗證「正文含行內式／code 能留在同一正確 block，且 raw 與原生 Markdown 一致保留」；同時納入普通 prose／literal 負例，避免只修公式。須先固定來源與 oracle、模型與設定、實際 layout／VLM 圖片、內容與交付分開評分及資源上限。這不是新的模型搜尋，也不碰 holdout。

完整 Result／save 接點及原生 math normalization 要先有零模型控制：pipeline 中只要輸出同時含 `\\(...\\)` 或 `\\[...\\]`，會先刪除所有 `$` 再轉 delimiter，可能破壞混合 code／貨幣 literal。這是需要驗證的通用風險，不用調答案修補。實際 layout 與 crop 也必須另外 preflight，不能挪用先前 Docling 圖片批准。

若實際仍需自製全文 code detector、從分離 formula boxes 猜句子位置、逐題補 delimiter／code fence、修 identifier／prime／表格關係，就停止，記為該路徑未達成 B1；不自動擴大後處理或換下一模型。Paddle 原生路徑能否同時改善 B2／B4 只能在同一次固定配置中觀察，不能由接口存在先行宣告。

因此，**目前連立即恢復小型模型試驗也不建議：先決定是否接受有限的交付接點維護。** 原生 normalization 會改動 literal，原生跨頁組裝也沒有通用段落續接，這些不是載模型就能解除的未知。若不接受這筆整合維護，維持暫停並報告目前無完整解法；不能把大量客製修復藏進 integration。

固定 `pipeline.py` L535–579 的 `_paddleocr_vl_assemble_parsing_results(...)` 接收尚未轉換的 `vlm_results`、blocks 及批次內 `(page_idx, block_idx)` 對應，故可設計 instance subclass 在呼叫原方法前保存必要欄位。這是私有介面的靜態證據，**不是實際 capture 已驗證**；來源頁號、跨批次唯一性與座標系仍須另外精確綁定。當前建議只用既有 runtime、明確合成 contract 測試交付映射與未修改的既有 continuation，最多 2 小時；不安裝 Paddle、不新增偵測／修字／段落規則。完整邊界及停止條件以主決策為準。

## 精確來源與證據界線

以下均為先前保留的官方 source，不是本輪重新抓取的 moving latest；本輪核對八個來源的 SHA-256 與既有 `retrieval.json` 相符。

- 完整 pipeline 定義：[PaddleOCR v3.7.0 官方教學](https://github.com/PaddlePaddle/PaddleOCR/blob/v3.7.0/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md#L16-L24)；`merge_layout_blocks` 文字定義 L1415，JSON formatting L1610。
- 分流／合併／輸出前轉換：[PaddleX v3.7.2 pipeline.py](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.2/paddlex/inference/pipelines/paddleocr_vl/pipeline.py#L281-L400)，math normalization L578–595、group_id L609、restructure_pages L1245–1335。
- inline overlap 丟棄、文字裁圖合併：[v3.7.2 uilts.py](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.2/paddlex/inference/pipelines/paddleocr_vl/uilts.py#L111-L172)，`merge_blocks` L284–443。
- 原生結果／JSON／Markdown：[v3.7.2 result.py](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.2/paddlex/inference/pipelines/paddleocr_vl/result.py#L344-L484)；[共用 converter](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.2/paddlex/inference/common/result/converter/markdown_converter.py#L38-L128)；[algorithm handler](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.2/paddlex/inference/common/result/converter/markdown_format_funcs.py#L353-L363)。
- layout labels／v1.6 官方設定：[固定 layout revision](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3/blob/241f8bdfc77a7c7bee915a5057aaee58c235a8d3/inference.yml)，[v3.7.2 pipeline YAML](https://github.com/PaddlePaddle/PaddleX/blob/v3.7.2/paddlex/configs/pipelines/PaddleOCR-VL-1.6.yaml)。
- 既有真實 component 控制：native-synthetic-results.json (`docs/research/pdf-core-g2-preflight-2026-10-16/candidate/native-synthetic-results.json`)。它只跑完整未改官方 pure converter，不是完整 PaddleOCRVLResult／save，不是模型準度證據。

本輪未做 import、建環境、抓模型、推論、PDF／holdout 內容讀取或新評分；純 source 可證明路徑與邊界，不能證明完整候選的品質／效能。

## 同一配置是否可附帶圖片 OCR（靜態補查）

若有界實驗保留 NCCU 圖片文字的 collateral check，**唯一新提案應顯式設 `use_ocr_for_image_block=True`**；舊封存配置仍是 False，不覆寫。`pipeline.py` L668–674 在 True 時將 `image`／`header_image`／`footer_image` 移出辨識跳過清單；L303–313 因而以 `OCR:` 送入 VLM，L619–628 仍掛上原始 crop 的 PIL image。`result.py` L295–325 與 `markdown_format_funcs.py` L148–168 也會保留圖片 reference，接著附上 OCR 文字。這是可執行路徑的靜態證據，不是 NCCU 準度或完整 save 已通過。

原生 Markdown 直接把 OCR 附在圖片下方，沒有 Canonical 所需的來源／enrichment 區分；因此 raw 原生 Markdown 只能作研究 artifact，圖片 OCR 必須在 raw block 獨立評分，未來正式交付仍須一般化地分離 supplement。True 亦會增加 header/footer 圖片辨識工作；資源上限必須計入實際 crop／呼叫，不能只限頁數。若不想擴張這個實驗，就保留 False 並移除圖片 OCR claim，不能把未執行當辨識失敗。

將 provider 的 `algorithm` label 映成 `CodeItem`／code block 是通用 typed mapping，不是新增 detector，但**官方 Docling importer 目前把它映成 TEXT（`docling-v2132-paddleocr_vl_utils.py` L109）**；它只能涵蓋已標記 algorithm 的區塊，不能證明 code discovery，也不得據此猜測普通正文 inline code 或重組分離公式。pseudocode／誤分類應保留並評分，language 未知時不猜語言。
