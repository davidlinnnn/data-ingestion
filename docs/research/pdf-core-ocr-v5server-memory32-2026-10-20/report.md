# PP-OCRv5 server：放寬記憶體後的七頁結果 — 2026-10-20

**七頁全部成功完成，但此固定配置不採用。** 原案例不再出現原R0那種跨欄文字行旗標，ACL p2讀序與BLEU數值保留亦有改善；然而原案例最終正文仍錯序，單欄WikiSkill出現嚴重內容缺損，中文SOP的登入限定標記仍遺失。這些超過既定minor界線。按停止條件，本輪結束，額外六頁不跑，不再追加模型／裁圖修補。

這是七頁已曝光、乾淨raster的固定配置結果，不是一般準確率或所有PP-OCRv5／Paddle路徑的結論。

## 配置與資源修訂

沿用Docling2.132.0／Core2.99.0／Parse7.22.3、RapidOCR3.9.2／ONNXRuntime1.24.3。StandardPdfPipeline＋PyPdfium＋Heron，官方DEFAULT OCR選區、原生layout postprocessing／assembly／ReadingOrder。CPU4、PyTorch inter-op1，layout float32／compile=False。TableFormer ACCURATE／cell matching保留；code／formula／picture enrichment關閉。

- 偵測：`ch_PP-OCRv5_det_server.onnx`，SHA256 `0f8846b1d4bba223a2a2f9d9b44022fbc22cc019051a602b41a7fda9667e4cad`。
- 辨識：`ch_PP-OCRv5_rec_server.onnx`，SHA256 `e09385400eaaaef34ceff54aeb7c4f0f1fe014c27fa8b9905d4709b65746562a`。
- 原mobile-v2方向分類器保持開啟；det／cls／rec皆只有CPUExecutionProvider，實際載入路徑／hash／版本／大小及ONNX內嵌辨識字典已驗。
- OCR scale3、page image scale2、text_score0.5；RapidOCR det short-side736／min、mean/std0.5、thresh0.3、box_thresh0.5、unclip1.6、dilation=True均保留。Docling各stage batch1；RapidOCR內部cls／rec batch6。

模型配置逐欄等於最初凍結配置 (`docs/research/pdf-core-ocr-v5server-2026-10-20/registration.json`)，**這次只調資源護欄**。沒有custom選區、去重、修字、重排或SDK修改。[官方Docling模型路徑接點](https://docling-project.github.io/docling/_generated/examples/rapidocr_with_custom_models/)、[RapidAI版本／大小參數](https://rapidai.github.io/RapidOCRDocs/v3.9.2/install_usage/rapidocr/how_to_use_ppocrv5/)。這是RapidOCR整合，不是Paddle完整pipeline或內建具名Docling preset。

使用者明確允許提高memory fence後，保留每次中止：

| 嘗試 | 程序樹RSS上限 | 主機available下限 | 結果 |
|---|---:|---:|---|
| 最初封存 | 12GiB | 8GiB | 第一頁available7.982GiB，監督程式停止，零完整頁 |
| 本次先調整 | 16GiB | 4GiB | 第一頁RSS16.18GiB，當時available12.47GiB；停止，零完整頁 |
| 最後資源重跑 | **32GiB** | **4GiB** | **七頁完成，RSS峰值21.14GiB、最低available8.28GiB** |

時間限制仍為180秒/init或頁面、900秒/profile，啟動available門檻10GiB。兩次資源重跑均依使用者授權，非程式自動重試。累計九次頁面嘗試＝兩次中止的原案例＋七次成功；不把中止的工作當作完成樣本，亦不把它們當品質失敗。最後固定32GiB版本內，每頁恰一次嘗試。

## 七頁來源評讀

| 來源 | 觀察與判定 |
|---|---|
| 原雙欄案例 | 原始OCR／最終無自動混欄旗標；但右欄`In-context learning`仍插到左欄第一段後，提前於remainder／Overview／Background／Emergent Abilities。12個參考單位皆定位，四組配對反轉。Background及推理正文另有片段亂字／遺失。**拒絕** |
| ACL p1 | 主標題、Abstract／Introduction、+0.64／+0.87／+1.24／+0.47／+0.86保留。左底接右頂為合法續段，不把混欄旗標當失敗；部分詞與email仍有差異，未宣告全頁逐字正確 |
| ACL p2 | 三項貢獻先於Our Method，讀序零反轉；未出現C10相同重複句首。但方法正文、Y與decoder識別字仍毀損，非等義格式。**拒絕** |
| WikiSkill p2 | 單欄順序旗標正常，卻在多行發生明顯內容損失，例如`Prior work ... EvoSkill`和`Inspired by Karpathy ...`部分消失／亂字。原R0保留這些內容，構成回歸。**拒絕** |
| 中文SOP p7 | 主網域與5次／15分鐘條件保留；`Login`後多底線，部分枚舉數字重複。記錄改善與殘留差異，不宣告完整圖片OCR或網址零缺陷 |
| 中文SOP p9 | 恢復隱私條款尾句「提供的資訊」；但登入限定功能與註解的`※`皆失去，破壞對應關係。**拒絕** |
| 中文SOP NCCU p3 | 登入方法／進入人事服務網／B5A保留；標題枚舉、空格、列點有差異，非整個標題遺失。未觀察到同等重大正文缺陷；未驗圖片內所有文字 |

具體text ref、完整observed文字、來源圖hash與原始OCR cell座標見人工評讀 (`manual-review.json`)。WikiSkill的raw cells21／22已包含`evolul`、`a cumulativehoryof pior...`；這份內容損失並非只在Markdown renderer出現。本輪沒有再追det／rec哪個子階段造成，也未啟動修復支線。

自動旗標仍只是REVIEW_REQUIRED，無整段遺漏／無錯序旗標不等於語意正確。原凍結scorer、分母、門檻未改。人工判讀由執行agent完成，無獨立第二位盲評者。公式enrichment關閉；即使將公式問題另留後續，原雙欄讀序與單欄正文反例已足以拒絕此固定配置。

## 實測成本

| 固定配置 | 七頁轉換合計 | sampled程序樹RSS峰值 |
|---|---:|---:|
| 原R0／v6 small，既有 | 18.54s | 5.19GiB |
| FULL_PAGE／v6 small，既有 | 16.58s | 3.27GiB |
| C10／v6 small，自訂分區，既有 | 29.18s | 6.63GiB |
| **v5 server det＋rec，本輪** | **129.91s** | **21.14GiB** |

本輪初始化1.54s；七頁各20.10／26.24／12.69／13.68／11.31／8.82／37.07秒。含debug／寫檔，轉換合計不含初始化；既有對照來自不同輪快取。不是配對效能實驗、p95、吞吐量或服務SLO，不由此推算正式GPU資源／成本。這次CPU觀測的資源負擔高，且未消除必要能力的重大缺口，沒有支持採用此配置的平衡點。

## 視覺化、查核與收斂

[原生R0／v5 server／C10比較](http://127.0.0.1:62729/ocr-v5server-memory32/index.html#wiki-p2)：七頁三組，最終文字／框與讀序／Docling圖文對照，共21份原生展示。僅顯示用副本替換144dpi來源背景，文字、geometry與Markdown不變，input/output hash有manifest。瀏覽器實際核對WikiSkill的兩份iframe文字並保存畫面 (`preview.jpg`)。

推論前通過C10讀序正控制、FULL_PAGE反控制及部分行重複的正負控制。輸入／模型／runtime／設定／scorer凍結前後一致；六份較早實驗封存由完成查核核對，另外兩份資源中止封存由lineage查核 (`resource-lineage-verification.json`)核對，均未改動。原最初初始化的序列化前置檢查修復仍留在前輪封存，這次沒有新增harness修補或模型變體。

**決策：不採用此固定CPU v5 server組合；額外六頁維持未推論，本輪結束。** C10仍可作讀序對照，但其已知重複內容與自訂選區缺陷未變。資源已允許得到品質結論，剩下是方法取捨，不再以繼續提高memory fence或追加模型搜尋延長本輪。

未測GPU／VLM、自然噪聲、正式負載、完整image／formula／code／table能力；沒有production改動。

零推論複核：`rtk proxy <tmp>/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-ocr-v5server-memory32-2026-10-20/verify.py`
