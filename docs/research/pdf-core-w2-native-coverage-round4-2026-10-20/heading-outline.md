# R3 B-only：有／無 PDF outline 的範圍與殘留標題錯誤

只讀 R3 已保存的官方 PDFium outline／評分，未跑 conversion、後處理或模型。`outline_pdfium_count > 0` 定義「有 outline」；這是 PDF 文件本身可由 S0 backend 取得的 bookmark，不是有 LaTeX 原始檔。

|組別|篇數（可評／無可評標題）|baseline 正確／層級錯|B-only 正確／層級錯|strict missing／role／ambiguous|修好／新壞|
|---|---:|---:|---:|---:|---:|
|有 outline|26（25／1）|136／183|311／8|33／1／2|175／0|
|無 outline|10（9／1）|41／71|41／71|0／0／0|0／0|

|B-only 殘留狀態的篇數（可重疊）|有 outline|無 outline|
|---|---:|---:|
|level_error|5|9|
|missing|9|0|
|role_error|1|0|
|ambiguous|2|0|

有任一上述狀態的篇數：有 outline 10 篇，無 outline 9 篇。篇數不能把各狀態列直接相加。

結案口徑：467 個可評結構標題，baseline 正確177／level error254／strict missing33／role1／ambiguous2；B-only 正確352／level error79／strict missing33／role1／ambiguous2。175 個轉正確、0 個由正確轉錯，全來自有 outline 組。無 outline 組沒有規則輸入，因此保留 baseline。Adam 與 Matrix Calculus 沒有本 oracle 可評結構標題，各分屬無／有 outline；不能當標題全對。

`level_error` 是和凍結 LaTeX 層級不符，含可能的全篇一致層級偏移；未逐案證明對象／條件／從屬改義，不自動等同 Q4 阻擋。`strict missing` 是正規化標題＋唯一匹配＋頁交叉沒有嚴格對上，也不自動等同內容真漏；role／ambiguous 同樣須另外核對。此表不能當 F01/F02 的新增阻擋事件或整篇通過率。

來源：R3 PDFium integration summary (`docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/heading/pdfium-integration/summary.json`)、R3 各篇 baseline / B-only 原始評分 (`docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/heading/jobs`)、凍結評分器 (`docs/research/pdf-core-w2-native-coverage-round2-2026-10-20/heading/assess_headings.py`)。逐篇數值與完整有／無 outline 清單見 `heading-outline.json`。
