# 圖片 classifier CPU method

本次變更只增加 research runner／記錄與獨立模型 cache。使用既有 `.venv`；不變更套件、production code、G1 PDF／圖片／registry／oracle 或 GitHub。適用來源為固定 G1-C03～C06、G1-S05、G1-S07；範圍及每個 crop 的 SHA／原始 physical page／PDF bbox 見 input manifest (`docs/research/pdf-core-g2-images-2026-10-14/inputs/input-manifest.json`)。這六個 input 是來源定位 crop。另加 native inventory (`docs/research/pdf-core-g2-images-2026-10-14/layout/native-inventory.json`) 的六個實際 `PictureItem`：採用原生 layout 未修改 bbox，在 PDF 重新 scale3 render，不能聲稱與 baseline cached crop pixels 相同或已涵蓋全部必要內容。兩組合成只含路徑／provenance 的 `inputs.json`，模型仍只收到圖片。

模型／API 合約見 [primary research](primary-research.md)。下載使用三個明列檔案，固定 `f859dfbff5c9916cd996942d4b0db7fa25808220`；匿名下載，實際 bytes 與 SHA 驗證另見 `download.json`。模型放在既有 prototype 的 `PROTOTYPE-wipe-me/g2-picture-classifier-hf`，不共用 baseline cache。下載與推論分開計時。

`probe.py` 使用 Docling 2.102.0 原生 `DocumentPictureClassifier`，Transformers engine、`float32`、`compile_model=False`、`enable_remote_services=False`、CPU4／interop1／batch1。固定 model revision，`HF_HUB_OFFLINE=1`／`TRANSFORMERS_OFFLINE=1`，初始化後驗全部 parameters 的 CPU／FP32。沒有 OCR、VLM、prompt、oracle 或 expected family 作模型輸入；模型只收到 RGB crop。

十二張 crop 在一個 child 中依序執行，只有一次 eager model load，每次 stage call 的 batch 為1。Child 包括 import／load／十二次 stage call／輸出；整個 child 180 秒、每 0.25 秒取樣 process-tree RSS、6 GiB 軟停止，啟動前 available memory 至少 8 GiB。此 guard 不是硬記憶體隔離；採樣可能漏掉瞬時峰值。沿用前輪 G2 supervisor 方法。stage construction timer 含 eager load；stage call timer 含前處理／softmax／分類 metadata 寫回，不當作純矩陣運算時間。OS cache 未清空，每例一次，不稱 cold benchmark／p95。

保存 engine 的 26 類 scores／IDs 與原生 `PictureItem` serialization，檢查 scores 和為 1、順序與 config numeric ID mapping 一致。固定 source crop 使用新的 PictureItem；native crop 則由原始 provider `document.json` 載入原本 PictureItem 並原地 enrichment，保留 before／after。執行原生 chart `is_processable()` 記錄路由結果，但以 `object.__new__` 建立 gate object，沒有載入 chart VLM，也沒有生成 chart data。

`check.py` 另以無推論的人工 metadata 驗 gate：低 confidence chart 會通過，flow／scatter／box／other／unknown 不通過，次佳 bar 不會 fallback。這只驗實際程式行為，不把 confidence 當正確性或無文字、`other` 當資訊豁免。品質須回到 frozen source 分開判斷圖類別與圖意／數值；分類成功不代表 F11 圖意或 F12 chart extraction 已交付。

第一次啟動在 sandbox 內無法使用 psutil 讀 process tree，0.0036秒即停止 child，尚無推論輸出。`startup-failure-*` 保存相同 runner、summary、空 log／runs；之後以已授權的同一 offline CPU runner 允許 process inspection，完成十二次分類。這不是額外一輪品質試驗。
