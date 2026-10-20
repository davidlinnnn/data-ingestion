# 固定範圍：讀序接點追查與單一 Tesseract best 比較

使用者授權：2026-10-20「OK, 執行你的建議」。

1. 只讀保存產物，對 known／ACL p2 的 Heron FULL_PAGE、Egret DEFAULT／FULL_PAGE、C10、Tesseract fast PSM3、EasyOCR 做原生後處理重播。觀察 assembled text、predict_reading_order、predict_merges、最終 body/group。必須重現保存的文字／結構與 Markdown，才採信定位；沒有載入推論模型、修正輸出或更改 SDK。
2. 唯一新推論候選：Docling 2.132.0 StandardPdfPipeline、PyPdfium、固定 Heron、TesseractCLI 5.5.3、PSM3、eng+chi_tra、OCR scale3、CPU4。將原 fast 的英／繁中權重一起換成官方 tessdata_best 的固定 revision；OSD、TSV 與其餘 pipeline options 保持不變。
3. 固定使用同一組七頁已曝光回歸。每頁一次，共最多七次新轉換；不追加 PSM／語言順序／OCR mode／新引擎，不做錯字修正。候選前鎖定模型 bytes、source/reference、options、runtime、runner／評讀器程式。沿用每頁／初始化180秒、profile900秒、RSS12GiB、可用記憶體啟動10GiB／底線8GiB與程序鎖。
4. 沿用既定重大錯序、句子混接、完整段落／標題遺失、識別字／運算／條件歸屬錯誤不可接受；一般字形與排版小錯可接受。人工核對來源，flags 只供查核，不當語意分數。
5. 以保存的 fast 結果作準度對照；時間包含 debug/artifact 輸出、排除初始化，快取測量不能作成正式速度排名或 SLO。若 best 仍有任一重大缺陷，判定此固定候選未合格並結束，不自動開另一輪。若七頁未見重大缺陷，只能保留為局部候選；本輪不自動啟動額外頁或宣告生產合格。

範圍不含：GPU／VLM、新 Docling 版本、custom crop/padding、排序修補、自然噪聲掃描、整體 code／table／formula Profile 驗收。既有封存結果不改寫。
