# B／C 收斂與外部 benchmark 的分工

2026-10-17。**本輪完成 B／C 的有界收斂；兩者完整能力仍 partial，不放行完整 Processing Profile。** 新增模型／API／下載／安裝／holdout／production／SDK／GitHub 寫入均為 0。A 的 mapper 擴張與頁級 fallback 新支線維持暫停。

## 這輪已經做完什麼

| 分支 | 新證據／決定 | 仍然阻擋什麼 |
|---|---|---|
| B | 一個新候選：明示 header paths＋named row dimensions，沿既有公開 Core／serializer 交付 normalized 表格。10 個新控制與 45 個既有 B 控制通過；保護原 T01／T02／T05，T04 舊 raw 仍拒絕。已核對七張 exact input crops | 沒有新模型準度。T04 的來源表頭、Table 7 四組 math，以及 T03 真實跨頁 grouping／joint reconstruction 未解。單一 logical multi-page item 的合成替換不等於三張真實 fragments 已合併 |
| C | 對原計畫 13 個檔案／55 頁完成 source-only 圖片存在性與 caption 位置 review。發現 18 個資訊圖＋1 品牌圖，8 個 raster wrappers 另列；核對既有真圖、chart、OCR、classifier 與 MOCK 的各自身分／範圍 | 完整語意 oracle、同版 producer inventory／crop／image-key 核對、真實 OCR／description／chart 品質、方向／heading 與完整恢復仍未通過。人工清單是 evaluator-only，不能拿來直接排 VLM jobs |

詳細內容：[B 報告](B/report.md)、[C 報告](C/report.md)。Root 另核對 B 的 22 個 artifact、15 個來源引用；C read-only check 通過 135 個自身檔案、54 個來源引用。Root 對 Memory-R1 p8、WikiSkill p12、controls p7 影像作獨立 spot-check，未重新評分模型或將圖中文字當模型 OCR。

不以新的 mandatory label 或零錯要求提高門檻。表格仍允許每張複雜 logical table 最多 5% 數值錯誤，但必要表頭／條件與關鍵比較必須正確。C 的來源 caption 與生成補充資料分開；OCR failed 保留診斷但不代表成功，unknown 分類也不豁免必要工作。

## 目前少頁實驗可以支持哪些結論

使用者的判斷正確：**近幾輪深入模型比較仍集中在少量固定頁面及 crop。** A 為四來源八頁；B 為四頁六 targets，現在只準備新增一張 Table 7；C 既有真圖 API 只有兩個 exact crops，另有四張 controlled charts。早期曾執行 75 頁 Standard baseline，但完整語意評讀範圍有限，不能宣稱 75 頁全部功能合格。

本輪 C 的 55 頁是圖片存在性／來源責任盤點，不是 55 頁的新模型 run、全文 OCR 語意評分或 55 個獨立樣本。原 470 個表格數值、44 source groups、41 selected units、19 image groups 也不是相同的統計樣本單位。合成／source-derived 重複內容與同文件頁面有關聯，不能靠相加放大泛化證據。

因此現有 DEV 有助於發現失敗機制與排除不可行接點，尚不足以估計目標文件分布的泛化準度。更多資料與獨立確認需要進入計畫，但不能用擴大平均分母掩蓋已知必要內容錯誤。

## OmniDocBench：現在採方法，候選固定後做外部回歸

[專門研究](../pdf-core-omnidocbench-assessment-2026-10-17.md)已核對官方 repo、dataset card、論文及評分程式。當前 card 為 **1,651 個 PDF 頁面**，含多文件類型、版型與語言；提供 OCR／table／formula／reading-order 等評估。這是頁面 benchmark，不是 1,651 份完整文件。[官方資料集](https://huggingface.co/datasets/opendatalab/OmniDocBench)、[官方評估](https://github.com/opendatalab/OmniDocBench#evaluation)

| 時點 | 用法 | 本輪狀態 |
|---|---|---|
| **現在，與 B／C 收斂並行** | 採納分層、版本鎖、matching／metric 與 evaluator custody 設計；分清 isolated recognition 與全頁 discovery→delivery。保留原語意判準，不重新啟動模型大盤點 | 文件／原始碼調查完成；未安裝／下載／執行 evaluator，尚未建立資料版本 lock |
| **對應分支候選可執行並凍結後** | 對 baseline 與唯一候選跑同一個事前登錄的分層外部子集，按語言、版型、table math／merged cells／scan 等分列，保留失敗與成本。分支比較可先做；不宣稱完整 Profile 通過 | 待 B／C 的 source／request／budget gate；研究報告的最多 60 頁僅資源提案，尚未選樣或核定 |
| **完整配置確認階段** | 原完整文件套件驗跨頁、image keys、生成與來源分離、同版 Canonical 交付；公開 benchmark 較大／全量回歸作補充。公司模型／GPU／高頻與六份未曝光 holdout 獨立驗證 | 均未由本輪完成，不開封 holdout |

外部子集一旦被用來逐案調 prompt 或規則，就歸 DEV，不能繼續稱 confirmatory。Public benchmark 也可能被模型訓練／調參使用，未知污染情況；它能提供不同分布的回歸，不能保證無污染，也不替代公司獨立文件。

### 適用性邊界

- TEDS／TEDS-S 衡量 table tree／內容相似度，不等同每表數值錯誤率；TEDS 95 不代表本案的 5% 容忍已通過。CDM／edit-distance 亦不自動證明 code identifier 或數學意思正確。
- 主要 page evaluator 不能替代 T03 的跨頁 logical identity／header inheritance／source continuity；C 的圖內 OCR、生成 description、chart 數據／單位／關鍵比較仍需自己的來源評讀。[官方評估入口](https://github.com/opendatalab/OmniDocBench#end-to-end-evaluation)
- Input track 須分開。官方目前提供 page images，也有歷史 original PDF slices 宣告；尚未核實現行全量都可取得同版原生 PDF。官方 image→PDF helper 只嵌圖。Raster／image 分數不能外推 Standard native-text＋selective OCR 的 born-digital PDF 準度／latency；若無原生 PDF，就保留自己的原生文件套件。[官方 card](https://huggingface.co/datasets/opendatalab/OmniDocBench)、[轉換工具](https://github.com/opendatalab/OmniDocBench/blob/main/tools/image_to_pdf.py)
- Ingest／模型／provider 的耗時與離線 matching／TEDS／CDM 評分成本分列，不能把 benchmark evaluator 的成本算成 production ingest SLO。
- Code 的 Apache-2.0 與 dataset copyright 是不同邊界；官方資料明示研究用途、非商用。公司使用是否符合範圍尚未確證，本輪僅借鑑文件／方法，沒有下載或導入資料。[官方 copyright](https://huggingface.co/datasets/opendatalab/OmniDocBench#copyright-statement)

## 下一步的有限工作

1. **B 單頁候選：** 沿七筆已核對輸入固定新 producer／prompt／完整 response schema、input／output／time／memory／transport budget，控制通過後才執行一次最多七次的來源比較。原六 targets＋Table 7 四 math groups 保護／分母分列；不宣稱 T03 也已解。
2. **B 跨頁：** 先對真 T03 定義 fragment inventory、共同 logical grouping、重複 header 與各段來源責任；缺少可靠接點時保留停止點，不靠猜欄或大量新 merge code。
3. **C：** 固定少數尚缺的真實 chart／OCR／圖意來源契約，再用同版 producer 規則核對是否覆蓋 19 個 source groups、綁定實際 crop／image-key，才凍結真模型工作。19／18／9 是 image／description／registered-chart 的責任數，不是 API calls，N₃ 仍為 null。
4. **外部驗證：** 對應候選可執行、配置凍結及資料使用範圍釐清後，先跑固定分層子集；全量 OmniDocBench 不作目前 B／C 接點缺口的替代方案。

本輪不開始新推論或全量 benchmark，也沒有縮減必含要求。收斂的是方法／證據／下一個門檻，尚未交付通過所有必要功能的配置。
