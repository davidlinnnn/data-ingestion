# G2 第三輪：PP-OCRv5 繁中識別候選

2026-10-14。**保留相同圖片、偵測框與方向分類，只換 recognizer，PP-OCRv5 mobile／server 仍未通過 G1-O01。** mobile 中央五項僅二項正確，server 三項；兩者在 b1／b4 都將繁體 `統` 誤辨為簡體 `统`。本輪不採用新 OCR 設定，也沒有修改來源或 oracle。

## 為什麼試這兩個模型

PaddleOCR 官方將 PP-OCRv5 mobile／server recognizer 列為支援繁體中文的統一識別模型；這提供具名候選依據，並非本案例品質保證。[PaddleOCR Text Recognition Module](https://www.paddleocr.ai/main/en/version3.x/module_usage/text_recognition.html)。

RapidAI 官方說明既有 RapidOCR 前後處理能配合 PP-OCRv5 ONNX recognizer，並說明把 character 字典寫入 ONNX metadata 後發布到具版本的 ModelScope 路徑。[RapidAI PP-OCRv5 整合紀錄](https://rapidai.github.io/RapidOCRDocs/main/blog/2025/05/30/rapidocr-%E9%9B%86%E6%88%90-pp-ocrv5_rec-%E6%A8%A1%E5%9E%8Bmobileserver%E8%AE%B0%E5%BD%95/)。實際下載 URL 和預期 SHA 取自本機已安裝 RapidOCR 3.9.2 的 `default_models.yaml`，可與 [RapidAI 模型登錄](https://github.com/RapidAI/RapidOCR/blob/main/python/rapidocr/default_models.yaml) 對照；未依賴第三方轉檔。

| Candidate | versioned registry | 檔案大小 bytes | SHA-256 |
|---|---|---:|---|
| `ch_PP-OCRv5_rec_mobile.onnx` | `RapidAI/RapidOCR v3.9.2` | 16,631,306 | `5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5` |
| `ch_PP-OCRv5_rec_server.onnx` | `RapidAI/RapidOCR v3.9.2` | 84,577,022 | `e09385400eaaaef34ceff54aeb7c4f0f1fe014c27fa8b9905d4709b65746562a` |

[download.json](download.json) 保存版本化 URL、HEAD metadata、實際大小／hash 與下載時間。兩個模型僅放在 `/private/tmp/pdf-core-g2r3-ocr-models-20261014/`；沒有裝套件、改舊模型 cache 或增加 DB 內容。`inference_executed:false` 是下載當下的狀態；後續實際執行以 [summary.json](summary.json) 為準。版本 tag 不當作不可變 revision，下載後的 SHA-256 才固定本次 bytes。

## 相同輸入與執行邊界

沿用 [G1-O01 registry](../../../fixtures/pdf-core-g1-2026-10-14/cases.json) 的 NCCU PDF physical p3；選取原始 embedded Image35 中央 panel，685×230，未放大。來源 PDF SHA `3a8d8a946a5962cc1b666ec6a33dc5482556da7013a70ca096fc8d86439a5f6e`；固定圖片 SHA `67daf56dc4b467605c202096cb16413818dd22063a85dc13a40d2401ce109f68`。逐位置核對中央 b1–b5，禁止以右側或側欄重複字串替代。

[run.py](run.py) 依序執行兩個 CPU child，重用第二輪 runner 的 raw-stage instrumentation 與來源座標映射；保留既有 v6-small detector（SHA `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f`）及 v2 orientation classifier（SHA `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`）。detector 框、detector scores、classifier results 和 preprocessing coordinate record，皆與第二輪同圖片 `fixed-panel-1x` 完全一致，由 [review.py](review.py) 斷言檢查，因此這次有隔離識別模型差異的證據。

RapidOCR 3.9.2／ONNX Runtime 1.24.3；三個 session 的實際 providers 皆保存且斷言為 `CPUExecutionProvider`，intra-op 4／inter-op 1 thread，recognition／classification batch 1。未啟用 CUDA、MPS、MLX、CoreML 或 API。

兩個模型均由內建 metadata 讀取 18,383 個 character，CTC 加 blank／space 後 18,385 類，與實際 output tensor 最後維度相符。字典 SHA `17665d27ed39f0deb82007859992d626d3105d0ee4578c120b7c72138dc04d05`；G1 五項的所有漢字均存在，包含 `統`／`結`，故本輪繁簡混用並不是該模型缺少這些字的證據。各 run 保存字典、producer config、input/output shape、source mapping、raw／final OCR。不得換錯字典或繁簡轉換後宣稱通過。

| Run | OCR 含 engine load 秒 | child 啟停秒 | sampled tree peak GiB |
|---|---:|---:|---:|
| `mobile-fixed-panel-1x` | 0.398 | 0.788 | 1.183 |
| `server-fixed-panel-1x` | 0.471 | 0.793 | 1.230 |

單 child 180 秒／RSS 6 GiB 軟停止，0.25 秒取樣，啟動前 available memory 至少 8 GiB；兩次均 exit 0、未觸發停止。這是本機一次觀察，非穩定 latency、全文件 SLO 或高頻容量。最初錯把 RapidOCR enum 參數傳成字串，於載入模型／推論前失敗；[失敗 runner](startup-failure-run.py)、[summary](startup-failure-summary.json) 與 [log](startup-failure-mobile/child.log) 原樣保存，修正 enum 後才完成上述兩次推論。

## 逐位置結果

[selection-review.json](selection-review.json) 保存每項預期、實際字串、confidence、source envelope、raw box 與位置對應。已目視原始 crop；只允許空白與雙引號字形正規化，不改漢字或冒號／句點。

| 項目 | PP-OCRv5 mobile | PP-OCRv5 server |
|---|---|---|
| b1 首頁 breadcrumb | `應用系统`，繁簡混用 | `應用系统`，繁簡混用 |
| b2 `我的專區` | 正確 | 正確 |
| b3 `應用系統` | 正確 | 正確 |
| b4 完整中央指示句 | `統→统`，`連結` 等字串損壞、`應→愿` | `統→统`，`結→结`，缺結尾引號 |
| b5 `B5A:個人簡要自述` | 冒號誤成句點 | 正確 |

raw detector boxes 能定位五項，raw recognizer 在五框都非空；錯誤已存在於 raw 識別字串，非 final blank-filter 造成。server 的 b4 原文為 `請由右方點選您要設定的常用應用系统或直接點選“連结進入應用系统：`。兩個候選皆未達五項通過，因此未額外跑 actual PictureItem scale3 分支。

本輪只淘汰這兩個具體設定作為本案例的直接替代，不推論 PP-OCRv5 在所有來源都不適用。可另評估繁中專用 recognizer 或 VLM 圖片區域，但需要新一輪固定來源比較；此輪不採全域繁簡轉換，也不以字元 confidence 代替來源保真。

未測全頁、其他圖片、其他 OCR 語系、API／GPU、Canonical image artifact 回填與高頻負載。G1-O01 仍未合格，F08 端到端交付與整體 G2 不得標成通過。
