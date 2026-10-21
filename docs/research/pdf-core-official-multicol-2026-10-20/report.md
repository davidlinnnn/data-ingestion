# 官方配置雙欄驗證結果 — 2026-10-20

**決策：兩組 Egret Large 都未通過；結束這輪有限的 Standard 原生配置比較。**

Egret Large 的預設路徑改善了原案例的跨欄句子混接與 Background 辨識，但最終正文閱讀順序仍錯誤，而且右欄五段被整組提前。FULL_PAGE 保留較完整的 OCR，仍將右欄首段提前。第二份雙欄論文也有段落插隊的反例。依已同意的「重大讀序／內容錯誤不可接受」界線，沒有候選可進入泛化驗證。

本輪完成 14/14 新轉換，零 API 呼叫、零推論重試。既有 14 份 Heron 結果作快取對照。六頁額外來源已在候選推論前凍結，因沒有通過開發階段的候選，**六頁推論執行零次**。這是預先約定的停止條件，並非宣稱 #84 或整個 PDF Profile 已達標。

## 配置與實測

共同設定：Docling 2.132.0、Core 2.99.0、docling-parse 7.22.3、RapidOCR 3.9.2；`StandardPdfPipeline`、`PyPdfiumDocumentBackend`、原生 layout postprocessing／assembly／ReadingOrderModel。CPU 4 threads、PyTorch inter-op 1、float32、compile=False；layout／OCR／table batch=1。RapidOCR 使用 ONNX `PP-OCRv6_det_small`、`PP-OCRv6_rec_small`、mobile-v2 方向分類器；det／cls／rec 皆啟用，OCR scale=3、page image scale=2。TableFormer 保留既有 ACCURATE 設定；code/formula/picture enrichment 未啟用，本輪未重新驗收這些能力。

Egret Large 使用官方 `layout_egret_large` preset；revision `fff417c78abd6bab338c87706c95a8d79dc68f1e`，weights 125,100,636 bytes，所有模型檔案雜湊已鎖定。Heron 使用原凍結 revision。完整參數與檔案雜湊見 `registration.json`。配置斷言證明，對照各自 OCR 模式時，差異限於 layout model spec，其餘 pipeline／engine 設定相同。沒有自訂 OCR 裁圖、padding、去重、排序或修字。

| 配置 | 原案例句子跨欄混接 | 原案例最終正文讀序 | 7 頁轉換合計 | 初始化 | sampled tree RSS 峰值 |
|---|---|---|---:|---:|---:|
| Heron DEFAULT（既有） | 有 | 混接干擾讀序判讀；未合格 | 18.54 s | 1.59 s | 5.19 GiB |
| Heron FULL_PAGE（既有） | 無 | 右欄 P06 提前，5 組配對反轉 | 16.58 s | 1.47 s | 3.26 GiB |
| Egret Large DEFAULT（新） | 無 | 右欄 P06–P10 提前，25 組配對反轉 | 19.81 s | 1.78 s | 4.49 GiB |
| Egret Large FULL_PAGE（新） | 無 | 右欄 P06 提前，5 組配對反轉 | 16.94 s | 1.60 s | 4.15 GiB |

轉換時間包含既有 debug/artifact 儲存，排除初始化；Heron 為不同時間的快取測量，不能據此宣稱可靠速度排名、吞吐量或正式 SLO。RSS 是受監督程序樹的取樣峰值，並非模型單獨占用量。兩組新測試都沒有觸及時間／記憶體停止界線。

## 逐頁人工判讀

| 頁面 | Egret DEFAULT | Egret FULL_PAGE | 判讀依據 |
|---|---|---|---|
| 原案例 known | 重大讀序錯誤；正文基本完整，Overview／Background 恢復 | 重大讀序錯誤；OCR 文字與 Heron FULL_PAGE 相同 | 原始頁左右欄、凍結 12 個正文單位、native body refs／list groups、原生視覺化互相核對 |
| ACL p1 | 摘要五個 BLEU 增量數字毀損；列為重大內容缺陷 | 這串數字保留；續段中插入作者註腳，另記結構瑕疵 | 原圖有 0.87、1.24、0.47、0.87、0.86；DEFAULT 輸出為毀損字串。左底接右頂是合法續段，沒有算成跨欄句子混接 |
| ACL p2 | 右欄方法提前到第三項貢獻前；`2 Our Method` 標題缺失，段首另有亂字 | 同樣將右欄方法提前到第三項貢獻前；標題保留，行內符號另有錯誤 | native body 遍歷證實插隊。DEFAULT 的 3 組／FULL_PAGE 的 4 組反轉不可當成 DEFAULT 較好，因 DEFAULT 另遺失一個標題 |
| WikiSkill p2 | 未見本輪新增的重大正文覆蓋／讀序缺陷 | 與 Heron FULL_PAGE 的 Markdown 完全相同 | 單欄正文與來源參考核對；這個局部結果不代表整份論文或其他能力合格 |
| NDHU p7 | 主文網址、登入操作、5 次／15 分鐘條件保留；序號有排版差異 | 與 Heron FULL_PAGE 的 Markdown 完全相同 | 圖片內文不納入這輪正文 OCR 驗收；來源圖說與操作文字有核對 |
| NDHU p9 | 遺失 `※`，功能與登入限定註解的連結仍有缺口 | 同左；與 Heron FULL_PAGE 的 Markdown 完全相同 | 原圖在特定功能與註解使用同一符號。不能因句子通順而忽略這個語意關係 |
| NCCU p3 | 登入方法／進入人事服務網與 B5A 保留，枚舉／字形差異分開記錄 | 與 Heron FULL_PAGE 的 Markdown 完全相同 | 沒有把枚舉差異誤報為整個標題消失 |

`diagnostics.json` 的字元覆蓋、混欄、重複與反轉都是查核提示，最後結論取自來源與輸出對照。未將「零 flags」當成語意正確；也沒有套用文字修正去提高分數。`manual-review.json` 保存逐頁結論、原生 item ref 與文件雜湊。

## 最具決定性的證據

原案例正確正文順序：

`P01 → P02 → H01 → P03 → P04 → P05 → P06 → P07 → P08 → P09 → P10 → P11`

Egret DEFAULT：

`P01 → P06 → P07 → P08 → P09 → P10 → P02 → H01 → P03 → P04 → P05 → P11`

原生 `#/groups/0` 收納提前的五段 list items，位於 P02 之前。Egret FULL_PAGE 則是 `P01 → P06 → P02 → H01 → P03 → P04 → P05 → P07 … P11`。這些順序直接存在 DoclingDocument 的 body／group refs 與序列化 Markdown，不是把 texts array 的儲存順序誤認為閱讀順序。

七頁 **Egret FULL_PAGE 的 OCR cells 與 Heron FULL_PAGE 逐欄位完全相同（7/7）**；原案例的讀序也相同。這支持「這組 layout 替換沒有解決該 FULL_PAGE 最終錯序」，並不證明 ReadingOrderModel 內部是哪個判斷造成，也不證明所有 layout 模型皆無效。DEFAULT 的裁圖／OCR 內容確實改善，但最後排序依然失敗；不能把現在的缺陷繼續全部歸咎於原本的 OCR 混行。

## 實驗流程 review

- 推論前固定七頁舊參考、額外六頁來源、模型 revision／檔案雜湊、完整 options、runtime 與評讀器程式；worker 離線載入模型、remote services=False、external plugins=False。
- Runner 與已驗過的監督程式之差異保存在 `runner-diff.patch`，僅候選 options、profile 清單與 CLI 說明；沿用既有 ZombieProcess race 修正與資源鎖。
- 正控制 C10 的 12 單位順序得到零反轉；負控制 Heron FULL_PAGE 得到五組反轉；部分文字重複的正／負控制通過。C10 只作評讀器控制，並未重新列為採用候選。
- 來源建置前置檢查曾因圖像化 header 沒有 native text 而停止；registration 曾將「零推論」數值當成布林失敗而停止。兩者都在凍結與第一個模型初始化前修正。沒有因此重跑或調整候選推論，沒有隱藏模型失敗或放寬門檻。
- 28 份最終文件均經原生 HTML serializer／visualizer 呈現；檢查顯示用副本的文字、幾何與 Markdown 未被改動。SDK／模型／舊控制的完整性由最終查核再確認。
- 人工判讀者為本次執行 agent，未做盲測或第二位獨立標註者複核。明確的 body refs 與可視反例支撐否決，仍不將這套小樣本判讀當成一般準確率。

## 收斂與下一個方法決策

**不採用 Egret Large DEFAULT 或 FULL_PAGE 作為此次需求的合格雙欄掃描配置。** 本輪沒有證據支持為這項能力更換 Heron 為 Egret Large。也不自動擴增 XL／101／threshold／custom padding 候選。

若維持「重大讀序偏差不可接受」及「不做自訂排序／裁圖」兩個限制，後續選擇是：驗證官方結構化 VLM 對問題頁的替代流程，或等待／採用可證實的上游修正。對高頻 ingest，任何 VLM 方案都須另有有限候選與成本預算，並驗證實際路由條件；本次小樣本不能提供能自動辨識語意錯序的 quality gate。既有 VLM 結果與公司正式模型也不能因此自動視為通過。

這次已凍結的額外六頁來自 BERT p1–2、ResNet p1–2、Attention Is All You Need p2–3；它們未經候選推論。皆為乾淨 raster、英文，未涵蓋自然掃描噪聲。若後續另案使用，應保留原參考與曝光紀錄；本輪不以這六頁宣告 generalization。

## 查閱與重現

- [互動原生結果比較](http://127.0.0.1:62729/official-multicol/index.html#known)：四組配置、七頁、最終文字／讀序／原生圖文對照。
- 機器診斷 (`diagnostics.json`)、評讀器控制 (`evaluator-selfcheck.json`)、推論前註冊 (`registration.json`)、額外來源凍結 (`validation/freeze.json`)。
- 查核命令（零推論）：`rtk proxy <tmp>/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-official-multicol-2026-10-20/verify.py`

限制：未測 GPU、vLLM、真實噪聲掃描、新版本或整體 #84 的 code／table／formula／provenance；沒有由此宣告生產配置合格。
