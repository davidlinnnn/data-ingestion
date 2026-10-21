# V1：ReasoningBank P10 全文差異補充裁定

**沒有確認修復；發現兩個新增 F02 讀序回歸群（p23、p24–25）。** Frozen anchors／candidate 0 增減沒有涵蓋這些 prompt／section 序列，不能因此說 V1 與 baseline 語意等價。P10 p9／p26 既有 native clipped-text 污染完全未變。

本輪逐一讀 `V1-full-differences/P-10-2509.25140v2.diff` 全部 hunks，核對原 PDF p10、p23、p24、p25 頁圖及 native graph／Markdown。p10、p24、p25 以 PDFium 記憶體內渲染檢視，沒有額外圖片檔；p23 使用既有頁圖。Baseline 是登錄的 recovery 輸出，V1 只將 reading-order separators 關閉，推論模型與 enrichment 保持固定。

| 頁／變動 | 裁定 | 理由 |
|---|---|---|
| p10 Figure6 附近 `Find reviewer...` 與 `Emergent advanced strategies...` 拆段、後移 | **NEUTRAL／既有來源 artifact 重排**，不計修復 | 這些舊圖字 provenance 超出原頁高度 841.89 pt（如 y849、930），原可見圖實際是現行策略標籤。V1 只是把原有 ghost 片段移到正文下方、拆成數段，仍交付不應出現的片段；不能將拆段稱為已修正文義。 |
| p23 Figure11 prompt 與 A.3 正文換序 | **NEW_BAD，F02** | 原頁左 panel 是 System Instruction → Guidelines／Output Format → Input Prompt → Query／Trajectories，右側兩個 check panels 同屬 Figure11，圖說及 Memory Consolidation／Storage／A.3 在圖下。V1 卻先輸出 Query、圖說、正文、A.3 至 `grounds the memory extraction process`，然後才輸出整個 SystemInstruction／Guidelines／右側 checks，InputPrompt 標題也被留在後方。必要 prompt 被移到不同正文／章節之後。 |
| p24–25 Figure12 prompt 與 B/B.1/Datasets 換序 | **NEW_BAD，F02** | 原頁 SystemInstruction／evaluation criteria 在 Figure12 上方，Query／Trajectories 在同 panel 下方，圖說與 A.3 續文、Best-of-N、B/B.1 在後。V1 先列 Query／圖說與這些正文，再將整個 SystemInstruction 區塊插到 Datasets 句中：p24 `...coding (Gitlab),` → 一整組 prompt → p25 `and forums (Reddit)`。來源跨頁是直接續句，V1 新增了段落串錯。 |

Baseline p23 原本已把右 panel checks 插到左 InputPrompt／Query 之間，並非完美；但仍把 Figure11 instructions 保持在其 caption／A.3 正文之前。V1 把整個 instructions 區塊移到 caption／正文／A.3 後，是額外回歸，不能因 baseline 已有局部問題就稱中性。p24 baseline 則完整先列 Figure12 prompt，再接正文，Datasets 跨頁續句亦沒有 V1 的 prompt 插入。

## 隔離 stage 的證據

Baseline 與 V1 的 assembled unit、全部 parsed pages、全部 layout predictions **逐欄完全相等**。變動不是新的 OCR／layout 框或文字來源。對同一批保存結果以各自實際 reading-order options 重播官方 ReadingOrderModel，texts/groups/body/furniture/tables、pictures（除後附 image）與原結果相等，Markdown bytes 亦相等；兩份都是零模型推論。stage calls／CID／provenance／source SHA 保存於 `V1-supplementary-trace-review.json`。

因此 p23／p24 的回歸定位在 **reading-order predictor 的 separator 條件改變，並影響後續 paragraph merge／跨頁接合**。既有頁外 bbox export clamp warnings 仍出現，沒有在本次 review 改框；不能把 Core-load 警告當作這次上游推論變更。

## 既有 p9／p26 是否修復

沒有。兩頁全部 native text／orig／provenance 與 parsed-page 資料對 baseline **完全相等**；`Experiment Results`／`Synergy of Memory and TTS`、`WebArena44` 等夾入正文的來源仍在。

先前零推論已確認這些污染來自原 PDF 嵌入圖的裁剪字流，再被 PyPdfium 對重疊 text rect 的 `get_text_bounded` 重讀放大，早於 layout／reading order／serializer。V1 關閉 separators 沒有移除該 backend 來源，故不能報成修復。來源與 bounded-cell 證據 (`docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/adjudication/recovery-helper/source-cell-origin.md`)。

本報告只裁定 P10 全文差異；未新增 conversion、未修問題，也不宣告 V1 全語料合格。
