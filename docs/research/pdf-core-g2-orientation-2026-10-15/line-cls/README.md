# Line classifier two-call diagnostic

2026-10-15。**相同原始 OCR input、相同 detector／recognizer／dictionary／config，僅 per-call `use_cls=False`，使兩個原本為空白的長指示恢復為完整句子。** 其他 raw line texts 沒變；C13 混排仍是 `OpenAl-compatible`。這支持定位此兩個特定輸入的 line-classifier 180° 誤轉問題，不是一般關閉 orientation 的設定建議，也不是完整 C12／C13 通過。

直接讀取已凍結 baseline 的 `controls-p7-selective/raw-ocr-calls/000.png` 與 `controls-p8-full/raw-ocr-calls/000.png`，沒有重 render、crop、resize 或採用 oracle 文字／角度／bbox。PNG 解碼後以相同 `numpy.ndarray uint8` 輸入型別、相同 channel 數值交給 RapidOCR；每個 producer 保存原 PNG path／SHA、array bytes SHA、shape 及 source physical page mapping。Constructor params 從 baseline 已保存值重建，ONNX engine enum 還原為原型別，序列化後 resolved config 完全相同；cached CH-v6 detector／recognizer、字典、batch1、threads4／1與CPU provider不變。[凍結方法](method.json)／[所有輸入雜湊](frozen-inputs.json)

| exact input | baseline cls／raw recognition | `use_cls=False` raw recognition | child wall／sampled peak |
|---|---|---|---|
| p7 selective screenshot crop | raw index3：180／0.911744，text空白 | 長指示完整出現，score0.94768，含`“連結”` | 0.790s／0.746GiB |
| p8 full page | raw index5：180／0.969466，text空白 | 長指示完整出現，score0.9618，含`“連结”` | 1.054s／2.085GiB |

保留 library 原始順序、所有 raw detector boxes／scores、recognizer texts／scores、classification null及前處理紀錄在各 `raw.json`，final filtered boxes／texts／scores 在 `output.json`。Detector 原始／映回輸入的 boxes、scores、前處理紀錄與 input shape 均逐值等於 baseline；全部15個 raw lines只有 index3／5文字變更，詳見 [逐行比較](comparison.json)。p7 final輸出從4項變5項；p8從9項變10項。原字形「系统」與 p8「连结」、混排 OpenAl 等剩餘保真問題沒有被本診斷消除；獨立 reviewer 仍須按 frozen oracle 判斷。

實際只新增兩次 OCR calls。`cls_and_rotate` 在此診斷 subclass 中若被呼叫會直接 assert；兩次 `classifier_results=null`、classification stage=null，line classifier inference次數為0。三個舊模型都因 RapidOCR constructor 初始化 session，但未執行新的方向模型或下載權重；六個 actual ONNX sessions 皆 `CPUExecutionProvider`。Config／session／model／dictionary／input identity 及 call count 存於各 `producer.json`。

[runner](run.py) 重用已凍結 baseline 的 guard／hash helpers，沒有複製新資源框架或變動完成的 orientation artifacts。Final script SHA 在 inference前凍結；shared qualification lock、available≥8GiB、180s、每0.25s sampled process-tree RSS≤6GiB及kill/reap均沿用，兩次無停止／錯誤。[summary](summary.json) 中的 `force_full_page_ocr`／`requested_docling_lang` 是配對 baseline input 的來源屬性；本 lane 只直接跑 OCR，沒有再執行 Docling。這些短測量不是SLO或 cold-cache benchmark。

首次 config comparison preflight 在**第一次 OCR call前**因 memory中的Path與已序列化字串比較失敗。已保留 [preflight](config-comparison-preflight/summary.json)，僅使比較採用與 baseline相同的JSON Path序列化後重新凍結，才執行兩次 final OCR。沒有把 preflight算入兩次 timings，也沒有額外 OCR calls。

[compare.py](compare.py) 不載模型，核對 runner／全部baseline artifacts與模型雜湊、exactconfig／input、detector逐值相同、raw順序及CPU／resource紀錄；核對通過。未跑 pipeline整合、圖片補充內容交付、mapper／Canonical patch、一般文件方向policy或更多樣本。
