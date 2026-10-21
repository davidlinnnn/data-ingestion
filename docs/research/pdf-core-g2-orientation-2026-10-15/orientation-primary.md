# G2 document orientation CPU primary candidate

2026-10-15（Asia/Taipei）。**官方 PP-LCNet 四方向模型在既有 Mac arm64 CPU runtime 可執行；四個旋轉控制頁均產生正確回轉、同一張正規化影像及同一份原始 OCR 文字輸出。** 這是完整頁面方向偵測與回轉的 bounded probe；所選 16 行的文字、順序與來源位置由獨立 reviewer 另驗，這裡不代填 semantic pass。

範圍僅 frozen `G1-C08–C11`／`SRC05` 的原 PDF physical p3–6。四頁是同一英語掃描的受控 0／90／180／270° 內容變體，並非四份獨立文件。原 PDF 的 Rotate=0、native text count=0、source SHA256 與 registry 原封核對。未輸入 oracle 角度、區域、文字、行號或預期答案；producer 只讀完整 RGB raster。使用 scale3／216 dpi，與本輪 Standard OCR baseline 的解析度一致。[input manifest](orientation/input-manifest.json)

選用 [PaddlePaddle 官方 ONNX repository](https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori_onnx/tree/7330ab7039123e46af2dc03154b9969aa412c61d)，pin revision `7330ab7039123e46af2dc03154b9969aa412c61d`、Apache-2.0。`inference.onnx` 實際下載 6,788,069 bytes，SHA256 `af9a0a4f317ff0709ce752067807f819cb15d883f8ecad89f28df1c6ee2d9c92`；config 與 README 的 bytes／hash 一併保存在 [download manifest](orientation/model-download.json)。模型只放 isolated `.scratch/pdf-core-g2-orientation-2026-10-15/models/`，未改既有 HF cache、套件或 OCR 模型。既有 ONNX Runtime 1.24.3 本來就有官方 [macOS arm64 wheel](https://pypi.org/project/onnxruntime/1.24.3/#files)，所以不需安裝 Paddle 或新增 runtime。

前處理依 [官方模型 config](https://huggingface.co/PaddlePaddle/PP-LCNet_x1_0_doc_ori_onnx/blob/7330ab7039123e46af2dc03154b9969aa412c61d/inference.yml) 及 tagged PaddleX v3.3.0 [predictor](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.3.0/paddlex/inference/models/image_classification/predictor.py)、[resize／normalize](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.3.0/paddlex/inference/models/common/vision/processors.py)、[crop／Topk](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.3.0/paddlex/inference/models/image_classification/processors.py)：RGB，短邊 256 且兩維 `round`、OpenCV LINEAR，中心 crop224、float32 ImageNet RGB normalization、CHW／batch1。實作保留官方逐 channel 的 `pixel *= ((1/255)/std); pixel += (-mean/std)` 運算次序。保存實際 224px crop、輸入 `.npy`、tensor hash、原始四分數 `.npy`／JSON；沒有額外 softmax、confidence threshold 或失敗時 oracle fallback。[凍結方法](orientation/method.json)

class index `[0,1,2,3]` 對應 label `[0,90,180,270]`。這個 label 是**修正用 CCW 角度**：官方 [preprocessor pipeline](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.3.0/paddlex/inference/pipelines/doc_preprocessor/pipeline.py) 把 label 直接交給 [rotate_image](https://raw.githubusercontent.com/PaddlePaddle/PaddleX/v3.3.0/paddlex/inference/pipelines/components/common/warp_image.py) 的正角度 OpenCV rotation。本輪用 `numpy.rot90` 做精確 90° 像素置換，避免另加插值；因此來源內容 CCW90 的修正 label 是270。這是輕量 adapter，沒有宣稱跑過整個 PaddleX pipeline。

| physical page／case | model corrective CCW label | raw winning score | orientation inference ms | child wall s | sampled tree peak GiB |
|---|---:|---:|---:|---:|---:|
| p3／C08 | 0 | 0.926849 | 1.986 | 2.361 | 2.257 |
| p4／C09 | 270 | 0.922970 | 2.279 | 2.380 | 2.268 |
| p5／C10 | 180 | 0.925339 | 2.083 | 2.375 | 2.269 |
| p6／C11 | 90 | 0.923956 | 2.352 | 2.375 | 2.273 |

各次 fresh child 先載入 orientation 模型（約 8.1–8.6 ms），再執行單張分類、回轉及完整頁 OCR。各 stage 的秒數、actual provider、OCR session options 保存在每頁 `orientation.json`／`runtime.json`，child 啟動至退出另存 [summary](orientation/summary.json)。四個 orientation session 及十二個 OCR sessions 全部實際為 `CPUExecutionProvider`；thread 設定 intra4／inter1（OCR另保存 live options），CUDA／CoreML／DML／CANN 關閉，沒有 AUTO／MPS／MLX／GPU。CPU／RAM 動態狀態與 model／OS cache 未清空；此表不代表 cold cache、p95、吞吐或公司 serving 能力。

OCR 沿用既有 RapidOCR3.9.2 的 `PP-OCRv6_det_small.onnx`、`PP-OCRv6_rec_small.onnx` 及既有二方向 line classifier，明確固定 CH、rec／cls batch1；沒有因這四頁為英語而換模型、字典或語言。OCR model hashes 在 method 與 run 前後核對。Recognizer 的 ONNX embedded dictionary 18,708 entries，decoder 加 blank／space 後 18,710；每頁保存完整 dictionary bytes／JSON 及 hash。四張 normalized PNG 同為 SHA256 `20c316502a57edecd57951404ce314266ad57098f387c511c72658a02a3c6329`，各頁 final OCR 有117項且文字列表相同；這只證明此四個回轉輸入一致，並不自行證明所選段落文字或閱讀順序正確。

原始 full-page detector boxes／scores、recognizer texts／scores、line classifier outputs 與前處理座標記錄，均在 RapidOCR score filtering 前存成 `raw-ocr-stages.json`；`ocr.json` 保留 library 原順序，不按 oracle 篩選或重新排序。每頁 `source-mapping.json` 保存來源 physical page／source SHA、model label、正向與逆向 3×3 matrix；每個 quadrilateral 都附映回**原始物理頁**的 polygon 及 bbox envelope。座標採 continuous raster edges `[0,W]×[0,H]`、top-left origin／x右y下，像素 sample center 是 `(column+.5,row+.5)`；90° CCW 為 `(x,y)→(y,W−x)`，180° 為 `(W−x,H−y)`，270° 為 `(H−y,x)`。這與 pixel-index 的 `W−1−x` 明確區分；最後除 scale3 才是原始 PDF points。

[self-check](orientation/run.py) 以不對稱小圖驗四個 pixel-center 置換及 matrix inverse；[saved-evidence verification](orientation/verify.py) 不載模型，核對凍結 script／method／source hash、16個 live CPU session 記錄、原始 tensor／四分數、完全相等的 image permutation，以及每頁234個 final＋raw polygon 的逆轉換。[全部核對通過](orientation/verification.json)。每次遵守 shared `/private/tmp/data-ingestion-pdf-qualification.lock`、開始前 available≥8 GiB、0.25s sampled process-tree RSS≤6 GiB、180s timeout；每個 owned PGID 由父程序 wait/reap，[無剩餘 owned model process](orientation/post-run-process-check.json)。這是 sampled 軟停止，並非 OS 硬 memory limit。

第一個 p3 attempt 在分類及 OCR 後，因 resolved config 的 `PosixPath` JSON serialization 失敗。原 script／method、log、raw outputs 與 resource summary 完整存於 [serialization-failure](orientation/serialization-failure/summary.json)。只修正 writer 的 `default=str` 後重新凍結，再跑上述四個完整 final children；第一次失敗不是模型品質或資源失敗，也未混入 final latency。未執行模型的 scale2 render preflight 在 final run 前改為 scale3，舊 preflight inputs／manifest／method另留 isolated scratch，沒有混用。

本輪未跑 normalized-image StandardPdfPipeline、PDF mapper、圖片補充內容交付、Canonical Acceptance、完整文件、多來源 holdout 或負載資格。下一步是否把方向模型接到 Standard pipeline，須先由獨立 reviewer 對 frozen selected16lines 的文字、順序與來源位置給結論；方向正確不會自動修正閱讀順序與交付缺口。
