# OCR 分區政策固定比較 — 2026-10-20

本輪完成，兩個自訂政策均不採用。保留 Heron 可以改善原案例，不需要先換 layout model；但「取消合併、各裁圖獨立加邊界」仍不足以成為可接受方法。官方 FULL_PAGE 保留為掃描頁候選，尚非全域合格配置。依凍結停止條件，不再追加 padding、kernel、去重或新模型變體。

## 實作與控制

實跑14頁次：C0/C10各同一組7頁，全部成功，零推論重試、API、GPU或模型下載。使用 Docling2.132.0 StandardPdfPipeline、PyPdfium、Heron、RapidOCR3.9.2 ONNX v6small detector/recognizer及mobile-v2方向分類器（開啟）、CPU4、TableFormer accurate/cell matching。其餘 enrichment 關閉。原R0和前輪FULL_PAGE皆重用封存實測，沒有重跑。

本輪是我們自己的區域政策，透過官方OCR plugin擴充接點載入，不是假稱官方公開參數。局部dist-info entry point加到worker的PYTHONPATH；沒有安裝或修改SDK，也沒有改全域dilation常數。六項離線測試涵蓋真實factory發現/disabled初始化、分離裁圖不再連回、原有重疊成組、頁界裁切、空layout與拒絕原生文字PDF。僅allow_external_plugins旗標及OCR自訂政策改變，其餘模型／pipeline選項逐欄比較一致。

- C0：使用原生dedup dilation0，保留實際重疊群組，不加邊界。
- C10：同一批群組各自加官方20 kernel對應的10pt邊界，裁到頁界，不再次合併。

這不是邊界大小搜尋；10取自原設定，並非針對原案例調參。沒有去重、識別字修補、文字規則或自行重排。僅處理沒有原生文字cell的raster PDF，不能宣稱是混合PDF的完整選區器或已可部署產品。

[凍結計畫](plan.md)、配置與雜湊 (`registration.json`)、plugin (`region_policy.py`)、測試 (`test_policy.py`)。

## 結果

| 政策 | 7頁轉換總秒數 | sampled tree峰值GiB | 要求的OCR區域總數 | 判定 |
|---|---:|---:|---:|---|
| C0 | 27.76 | 4.75 | 79 | 標題遺漏，拒絕 |
| C10 | 29.18 | 6.63 | 79 | 重複文字／公式段落破碎，拒絕 |

原R0七頁18.54秒、前輪FULL_PAGE16.58秒；本輪C10約29.18秒。這是單次、不同輪次、含debug及寫檔的轉換總和，不含初始化；不能當p95、服務吞吐量或正式速度提升/降低百分比。

原案例中C0/C10都請求15個區域，原始OCR與最終文件都沒有跨欄混接旗標。C0再次漏掉完整「2 OVERVIEW」；C10找回該標題及Background，沒有把兩欄重新合成一個大OCR框。

然而C10在真實ACL論文回歸頁產生可直接驗證的重複：acl-p2原始OCR cells54/56都讀到「The output of the encoder is fed into the de-」，cells53/55都讀到「tual representations.」。位置重疊，前一行的box可同時位於裁圖8與9。來源影像中各行只有一次，已視覺核對。最終文件保留重複句首，且向量公式段落也出現兩次「For the input sentence」及一次破碎版本。ACL首頁與原案例也有新增重複行。

因此這是裁圖的context覆蓋鄰區後，原始OCR已產生的重複；不是Markdown renderer造成，也不能只用最終跨欄旗標為零就判合格。拒絕的是此固定政策，並非宣稱所有分區OCR都不可行。具文字歸屬的輸出政策可能是技術解法，但尚未實作/驗證，本輪不自動補上。

人工判讀與原文、cell座標、裁圖、文件ref及hash (`manual-review.json`)。ACL來源頁 (`docs/research/pdf-core-ocr-regression-2026-10-19/corpus/source-pages/acl-p2.png`)。

## 評讀邊界

使用原凍結evaluator，未更換分母或調整門檻。自動旗標只供判讀：

- nccu-p3的「登入方法」「進入人事服務網」仍存在；枚舉字形與順序問題不能誤稱整個標題消失。
- acl-p1的U06→U08是合法跨欄續段，不能當無關句子混接。
- 原evaluator的重複旗標針對whole unit，會漏掉這輪的部分文字行重複。人工在raw cells與來源位置驗出，不因零旗標就放行，也不藉此改寫凍結評分器。
- C0只重現先前B的標題遺漏症狀，並非byte-exact重現：舊B切已渲染的大圖，這次使用PyPdfium原生各區域render與resize，cells116 vs115。原生路徑source會先以scale×1.5 render後resize；本輪兩政策與R0/FULL_PAGE皆走同一backend，舊B僅負面控制參照。

每個政策已有來源確認的重大反例，故拒絕全域資格；沒有為其宣告其餘所有細節均正確或逐頁全量語意通過。七頁輸出與所有diagnostics保留。既有※連結、方向、行內公式及reading-order缺口也不因本輪消失。

## 收斂決策

1. 不採用C0或C10，不將plugin接進產品。
2. 這輪支持保留Heron並把問題定位在OCR區域／context處理，未證明換layout model有必要或所有layout模型無效。
3. 相比目前測過的自訂分區政策，官方FULL_PAGE仍是掃描頁較合理的已測候選；其既有內容缺口未合格，不全域套用原生文字PDF。
4. 若未來選擇分區工程，須先決定是否值得投入「讓每段來源文字只有一個輸出歸屬」的設計與回歸成本，不能把本輪失敗直接變成無限padding/去重搜尋。這是新的方法/資源取捨點，不是本輪默認續跑項目。

## 驗證

原資料、權重、配置與scorer雜湊完成前後核對；三份歷史封存均未改變。14個結果皆包含實際reading_order計時與plugin區域紀錄。六項新離線測試通過，既有九項evaluator/runner控制於前輪已通過，本輪未改其實作。零模型重跑；結果整理時歷史artifact seal有files/artifacts兩種schema，讀取器相容後完成核對，不影響任何推論。

未測新layout模型、未曝光holdout、自然劣化掃描、全頁旋轉、GPU、正式服務SLO，也未驗證自訂文字歸屬方案。所有檔案限本輪研究目錄；無production改動。
