# 讀序接點定位與 Tesseract best 結果 — 2026-10-20

**兩項工作均完成：原生後處理的失敗接點已定位；唯一新增的 Tesseract best 候選未合格。**

本輪零 VLM／API 呼叫、七次新頁面轉換全部成功、零推論重試。原始七頁、權重、options、runtime／程式雜湊在候選推論前凍結；沒有修正文字、修改 SDK 或加入 custom crop／排序。既有封存保持不變。

## 接點追查：已能區分三個問題

| 問題 | 現有證據 | 定位與界線 |
|---|---|---|
| 原 RapidOCR 基線的跨欄文字行 | 前輪已重播原 Heron22框→Docling膨脹合為1個OCR輸入，再產生跨欄文字行 | OCR區域合併與偵測交互作用；本輪不重跑此實驗 |
| Heron／Egret FULL_PAGE 的段落錯序 | assembled 的每個正文元素仍分欄、文字未混接；`predict_reading_order()` 已將 P06 提前。`predict_merges()` mapping 為空，最後 body 保留此錯序 | **錯序已存在於 Docling 原生 rule-based ReadingOrderPredictor 輸出**，不是之後 list grouping 才把正確序列弄錯 |
| EasyOCR 最終混段 | assembled／predictor 元素仍各自分欄；原生 `predict_merges()` 回傳 `10 → [3,4,8,9,11]`，把左欄 P05 與右欄 P07–P11 合到同一段 | **下游 paragraph merge 的跨欄合併**；不是證據顯示 EasyOCR detector 直接輸出一條跨欄長行 |

這些都是特定 cells／layout geometry／label 輸入下的實際行為。它們不能證明 layout 訊號完全正確，也不能推論每種 OCR 都會被相同規則排錯；Tesseract 與 C10 提供的輸入就得到不同結果。ReadingOrderPredictor 在此版本是規則演算法，不是另一個需下載的神經模型。

對六組既有方法各重播 known／ACL p2，共12份；新 best 再重播兩份，共14份**零模型推論的後處理重播**。全部重現原生 text/group/body/furniture/table 結構、picture 非image欄位及 Markdown。圖片 image 附件由 Standard 後續掛入，刻意不冒稱它由 ReadingOrder 產生。

| 方法 | known：predictor／最終配對反轉 | ACL p2：predictor／最終配對反轉 | 補充 |
|---|---:|---:|---|
| Heron FULL_PAGE | 5／5 | 4／4 | 兩頁 paragraph merge mapping 都空 |
| Egret DEFAULT | 25／25 | 3／3 | ACL另缺一個標題；反轉較少不代表較好 |
| Egret FULL_PAGE | 5／5 | 4／4 | mapping空 |
| C10 | 0／0 | 0／0 | 仍有已知內容亂字／重複，且為使用者拒絕的 custom 裁圖方向 |
| Tesseract fast PSM3 | 0／0 | 0／0 | 仍有既知內容缺陷 |
| EasyOCR | 5／5 | 6／6 | known另發生跨欄 paragraph merge |
| Tesseract best PSM3（新） | 0／0 | 0／0 | 仍有下述內容缺陷 |

assembled陣列是 predictor 的輸入／tie-break來源，**本來不保證是最終讀序**；不把其輸入排列的反轉數當成前一階段失敗。重播保存的前／後文字、bbox、label、CID、source anchors與merge mapping，見 [order-traces/summary.json](order-traces/summary.json) 及 [best-order-traces/summary.json](best-order-traces/summary.json)。

## 唯一新候選：官方 tessdata_best

固定 Docling2.132.0 StandardPdfPipeline、PyPdfium、Heron、CPU4／interop1、float32、compile=False。TesseractCLI5.5.3、DEFAULT OCR mode、PSM3、eng+chi_tra、OCRscale3／pageimagescale2；table／enrichment維持原fast對照設定。

官方best revision：`e12c65a915945e4c28e237a9b52bc4a8f39a0cec`。eng 15,400,601 bytes，chi_tra 12,985,735 bytes；下載內容的Git blob及SHA256皆核對。OSD與TSV原檔完全相同。斷言證明 fast／best options 僅 tessdata 路徑不同，並非此次才啟用繁中。[模型紀錄](model-receipt.json)、[推論前註冊](registration.json)、[固定計畫](plan.md)。

| 對照 | 七頁轉換合計 | 初始化 | sampled程序樹RSS峰值 |
|---|---:|---:|---:|
| Tesseract fast PSM3（既有） | 17.33s | 1.14s | 1.81GiB |
| Tesseract best PSM3（新） | 28.01s | 1.45s | 1.84GiB |
| RapidOCR FULL_PAGE（既有） | 16.58s | 1.47s | 3.26GiB |

包含debug／artifact儲存、排除初始化；舊對照來自快取，不是配對的吞吐量／p95／SLO實驗。沒有資源超限，不能由這些單次結果宣稱一般速度排名。

## 人工逐頁判讀

| 頁面 | best 相對 fast 的觀察 | 判定 |
|---|---|---|
| known | 維持正確左欄→右欄讀序，沒有句子混接；部分bullet／註腳marker字形不同 | 本頁正文順序通過；字形差異依minor處理 |
| ACL p1 | 左底接右頂是合法續段；但來源`+0.47`／`+0.87`變成`40.47`／`40.87` | 重大數值語意缺陷；沒有把合法續段當混欄 |
| ACL p2 | 第三項貢獻先於方法段落，順序正確；但`x_1,x_2,…,x_n`仍辨識成`zy,29,…,2,`，decoder識別字亦毀損 | 重大識別字／公式內文缺陷，不是等義格式 |
| WikiSkill p2 | 大部分相同；`AI→Al` | 按既定界線視為minor；未據此否決 |
| NDHU p7 | 一般中文與5次／15分鐘條件保留；兩個網址仍辨識錯 | `yuntech`變成`yunteech`／`vuntech`，影響可用網址，非排版小錯 |
| NDHU p9 | 明顯恢復`※`與登入限定註解；有改善。隱私條款尾句仍缺「提供的資訊」 | 記錄改善與遺漏，沒有宣稱中文全部變好 |
| NCCU p3 | 恢復「壹」；登入方法／人事服務網／B5A保留 | 改善；原fast枚舉錯字不等於整個標題遺失 |

來源圖、凍結native文字參考、原生DoclingDocument／Markdown互相核對。具體ref與文件雜湊見 [manual-review.json](manual-review.json)。字元覆蓋／混欄／缺段flags不代替語意驗收，未新增字詞修補或事後調整門檻。人工判讀者為執行agent，沒有獨立第二位盲評者。

fast與best在相同八個短OCR區域都出現原生OSD「字數不足」警告；顯式語言模式下，Docling捕捉後保留0°並繼續OCR。這不是模型重試，也沒有當成方向辨識成功；本輪是已知直立頁，沒有驗收旋轉泛化。[OSD對照](OSD-control.json)。

## 流程查核與停止

推論前的接點測試曾發現兩項重播／檢查邊界：InputDocument不可直接從JSON走其開檔constructor，因此只重建已雜湊的metadata並驗證Page／AssembledUnit；picture image由RO之後附掛，因此結構比對排除image但保留其餘欄位。最初停止的部分產物保留在`order-traces-preflight-incomplete`。舊selfcheck還綁定前輪六頁目錄，改為在本輪明確執行C10正控制與FULL_PAGE負控制。這些均在候選凍結／初始化前完成；沒有重跑推論或放寬準度界線。

**決策：不採用這組best配置作為完整需求的合格方案。** 讀序與局部繁中確有優點，但公式識別字、數值、網址仍超出已接受的minor界線。依計畫結束本輪，不追加PSM／語言順序／OCRmode／新引擎，沒有使用額外六頁或sealed holdout。

方法收斂：目前已找到具體Docling接點，應把原生讀序與跨欄paragraph merge當成官方修正／版本對照的驗證目標。RapidOCR與Tesseract各保留成本／準度對照；沒有證據可將其中一組升為整體合格。若改走選擇性VLM，仍須另定有限候選、觸發條件與成本預算，本次沒有啟動。

## 查閱

- [fast／best／RapidOCR原生對照](http://127.0.0.1:62729/order-tessbest/index.html#acl-p2)：七頁、三組、文字／原生框與讀序／圖文對照，共21份展示。
- [診斷結果](diagnostics.json)、[runner差異](runner-diff.patch)、[最終查核](final-verification.json)。
- 零推論查核：`rtk proxy /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-order-tessbest-2026-10-20/verify.py`

限制：沒有修復生產pipeline，未驗GPU／VLM、自然噪聲、正式負載或整體code／table／formula能力；正確讀序的小樣本不代表一般化合格。
