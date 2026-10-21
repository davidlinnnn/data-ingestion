# G2 第二輪：圖片 OCR 的有界 CPU 比較

2026-10-14。**直接對圖片區域做 OCR 可以找回第一輪漏掉的中央指示句，但本次三種設定都沒有滿足 G1-O01。** 錯誤包含繁簡字混用；單純放大圖片也不能保證改善。這是同一來源、同一選定區域的診斷，尚未選定正式方法。

## 固定輸入與方法

來源仍是 G1-O01 (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`) 的 NCCU PDF physical p3，SHA-256 `3a8d8a946a5962cc1b666ec6a33dc5482556da7013a70ca096fc8d86439a5f6e`。逐位置核對中央五項 b1–b5，不以側欄或右側重複文字替代。原始中央 panel 為 embedded Image35 的固定 685×230 crop，SHA-256 `67daf56dc4b467605c202096cb16413818dd22063a85dc13a40d2401ce109f68`。

runner (`run.py`) 共執行三次圖片 OCR；不下載模型、不裝套件、不用 API、GPU、MPS、MLX 或 CoreML。採既有 RapidOCR 3.9.2／ONNX Runtime 1.24.3，三個 session 都實際保存並斷言 `get_providers() == ["CPUExecutionProvider"]`，intra-op 4 threads／inter-op 1 thread，classification／recognition batch 1。模型與其餘 resolved config 保存於各 run 的 `producer.json`，不是僅引用配置預期。

| 模型 | SHA-256 |
|---|---|
| `PP-OCRv6_det_small.onnx` | `090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f` |
| `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` |
| `PP-OCRv6_rec_small.onnx` | `6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884` |

| Run | 輸入 | OCR 含 engine load 秒 | 含 child 啟停秒 | sampled tree peak GiB |
|---|---|---:|---:|---:|
| fixed-panel-1x (`runs/fixed-panel-1x/ocr.json`) | G1 固定原始 panel，685×230 | 0.345 | 0.792 | 1.192 |
| picture-scale3 (`runs/picture-scale3/ocr.json`) | 第一輪 `nccu-p3-native` 的 `#/pictures/0`，原頁 scale 3 重繪、1340×980 | 0.510 | 1.061 | 1.048 |
| fixed-panel-2x (`runs/fixed-panel-2x/ocr.json`) | 原始 panel 以 PIL LANCZOS 放大 2×，1370×460 | 0.313 | 0.794 | 1.194 |

資源資料見 `summary.json`。每個 child 180 秒、0.25 秒採樣、process-tree RSS 超過 6 GiB 軟停止；單一 worker 依序執行。數字是本機一次觀察，包含冷暖 cache 差異，不是穩定 latency、容量或 SLO。最初一次在保存含 `Path` 的 resolved config 時失敗，發生於推論前；失敗 summary (`startup-failure-summary.json`) 與 child log 原樣保留，修正序列化後的三次推論均正常完成。

完整 PictureItem crop 重用既有 [圖片 OCR seam](https://github.com/davidlinnnn/data-ingestion/blob/archive/pdf-core-v1/src/pdf_processing/ocr.py)：核對 PDF／parsed result SHA、單頁 provenance、座標原點、原頁 cached pixels 及 PictureItem cached crop 完整性後才重繪。三次的 `source-mapping.json` 保存原頁 bbox、原始 embedded pixel mapping、crop 尺度／rounding 與來源雜湊。`picture-scale3` 的原頁 bbox 為 `[62.582893,242.548553,509.465088,569.274719]`，top-left PDF points，涵蓋中央五項，並未把 b4 裁掉。

## 逐位置結論

`selection-review.json` 保留每項的預期 PDF envelope、raw detector box、raw index、識別文字與 confidence；`review.py` 可離線重驗 hash、session providers、batch、來源位置及文字比較。空白與雙引號字形可正規化；不做繁簡轉換。位置對應使用固定近似 envelope，並已目視核對實際 crop；沒有新增 IoU 或文字錯誤率門檻。

| 中央項目 | 原始 panel 1× | 完整 PictureItem scale 3 | 原始 panel 2× |
|---|---|---|---|
| b1 `現在位置：首頁 > 我的專區 > 應用系統` | `統→统` | 同位置 raw index 13 僅辨成 ` <：系` | `統→统` |
| b2 `我的專區` | 正確 | 正確，中央 raw index 15 | 正確 |
| b3 `應用系統` | 正確 | 正確，中央 raw index 17 | 正確 |
| b4 完整「請由右方點選…」指示句 | 有完整句，但 `結→结`、最後 `統→统` | 有完整句，中央 raw index 21，同樣兩處繁簡誤字 | 有 detector box，但 recognizer 回空字串／score 0，最終輸出移除 |
| b5 `B5A:個人簡要自述` | 正確，保留冒號 | 中央 raw index 24，`簡→简` | 正確，保留冒號 |

三次 raw detector output 都能對應中央五項的位置。原始 panel 的 b4 有非空但錯字的辨識結果，顯示在此輸入上需要改善的是識別保真；2× panel 的 b4 則在已偵測框內得到空辨識，library 的 blank-filter 才將它移除。原始 detector／recognizer／classifier 結果與 preprocessing mapping 均保存在各 run 的 `raw-stages.json`，最終 texts／scores／boxes 保存於 `ocr.json`，兩者沒有互相覆蓋。

第一輪 full-page OCR 的 b4 在最終 Docling JSON 中缺失，而本次兩條直接圖片路徑能取得句子，故**對圖片另做 OCR 值得保留為後續候選**。但第一輪沒有保存 pre-layout raw OCR，且輸入範圍、影像來源／縮放與執行路徑不同，無法據此精確宣稱當時是 detector、recognizer、layout 合併或輸出過濾的哪一步造成缺失。本次也沒有把結果接入完整 Canonical image OCR artifact／required-work contract。

## 決策與邊界

- 保留具來源完整性驗證的圖片 OCR 路徑，下一輪需要較能保留繁中字形的具名 OCR 候選或 VLM crop 比較；禁止僅靠全域繁簡轉換宣稱通過。
- 不把 2× upscaling 列為預設修復：此案例 b4 反而變成空辨識。
- 不淘汰全頁 OCR 的其他用途；本輪只說明圖片區域的額外 OCR 有診斷與補強價值。

未測全頁／全文品質、旋轉案例、其他 OCR 模型、API、GPU、Canonical 交付與高頻負載。三次皆未通過 G1-O01，不能將高 confidence、偵測到框或成功退出視為品質達標。
