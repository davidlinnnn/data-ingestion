# dots.ocr 小型新增 validation：來源契約

日期：2026-10-16（Asia/Taipei）。角色是 **validation**，不是封存 holdout。來源 curator 沒有讀取六份 holdout PDF、沒有看本輪模型輸出、沒有推論或調參。來源清單先於任何本輪 validation 推論固定；模型可讀完整原始頁面，不能把這份答案、人工 source boxes 或 code 裁圖當成模型輸入。

## 固定來源與抽頁

| 原作／固定版本 | 第一手 metadata／PDF | SHA-256 | 全文頁數 | 固定評分頁 |
| --- | --- | --- | --- | --- |
| Learning Neurosymbolic Generative Models via Program Synthesis (v1) | [arXiv metadata](https://arxiv.org/abs/1901.08565)／[版本 PDF](https://arxiv.org/pdf/1901.08565v1) | `ba060436331579fb145b0077be93e9d016e72ed64d5944ef2af058c198018451` | 13 | 1, 11 |
| Calculation of prompt diphoton production cross sections at Tevatron and LHC energies (v1) | [arXiv metadata](https://arxiv.org/abs/0704.0001)／[版本 PDF](https://arxiv.org/pdf/0704.0001v1) | `387726add6d106da7920ef836cef6c6edacd9accc5e517f8f2e1797c784a7c17` | 47 | 1, 12 |

選材先依公開 metadata 排隊：1901.08565、2106.09685、0704.0001。逐個先搜尋原作 ID、官方完整標題與檔名；LoRA 因既有 repo 引用 23 筆而排除。接受的兩份都沒有精確 ID／標題／檔名引用，也不屬於 exposure-audit 或六份 holdout 的原作群組。搜尋包含 ignored／hidden metadata，以路徑清單記錄命中，排除 PDF／圖片等 binary、Git 內部檔與本輪新輸出目錄。這只是本次實驗的引用／原作邊界，不保證模型預訓練未見、作者或版型獨立，也不能排除改名或未披露副本。各次檢查與例外在 [manifest](manifest.json)。

每份頁數從已固定 bytes 取得，先選物理首頁，再從其餘頁按 `SHA256(lowercase_document_sha256 + ":" + decimal_1_based_page_number)` 的 digest 升冪選第一頁。完整排序已保留。選擇與抽頁先於閱讀 PDF 內容；沒有因內容類型不足、來源難度或模型表現換頁。兩份共 4,008,387 bytes，原始 PDF 未修改。第一輪 sandbox DNS 失敗後，以核准的公開唯讀下載完成同一 URL；沒有改換版本。

## 逐頁來源標註與分母

[Source contract](source-contract.json) 有 12 個適用正例來源單位：11 個含行內公式的段落／段落片段，以及 1 個獨立 pseudocode block。60 個行內數學 occurrence 是其段落的必要子項，不能再加入分母；另有 1 個行內 code identifier `draw`。普通文字負例固定 10 個，不與正例分母相加沖淡錯誤。

| 文件與頁面 | 適用正例 | 普通文字負例 | 來源特徵 |
| --- | ---: | ---: | --- |
| validation-01 p1 | 3 | 6 | sketch／component 公式、三行迴圈程式、程式後說明的行內公式與函式名 |
| validation-01 p11 | 5 | 3 | 生成模型參數、集合、上下標、條件機率與架構說明 |
| validation-02 p1 | 0 | 1 | 普通文字 abstract；DØ 是實驗名稱，不當成數學公式 |
| validation-02 p12 | 4 | 0 | CSS／CFG 說明、scattering channel、spin-flip 關係式與微分符號 |

所有四頁已完整目視核對。三張相鄰頁 render（第一份 p2；第二份 p11、p13）只供辨認段落延續，不新增評分頁、來源單位或行內公式分母。contract 明列前後欄、display code 前後與跨頁延續。只計固定頁上看得見的片段；相鄰頁獨立段落不是新增測試。拒絕、技術失敗、未嘗試／缺輸出都保留在固定正例分母；重複使映射單位失敗；無據新增另計。

第一份 p1 的 code block 包含真實的窗戶影像參數；原生文字抽取漏掉整塊。此處只有保留原圖參數與來源映射或明確拒絕，不能把圖擅自替換為虛構文字 literal。第二份原生文字的大部分字碼錯亂，但原稿 render 清楚；這不是來源歧義，不能靠原生文字當 gold。navigation-only 的抽取文字未留作答案；判準是原始 PDF 與保存的頁面影像。

沒有獨立 display equation，因此該子型態是**未驗**，不是 0 錯誤或 100% 成功。普通可執行 text-only code、長行內程式、繁中、SOP、技術手冊、掃描原稿與旋轉文字也未驗。這兩個有目的選取的原作、四個評分頁只支援有界 validation，不支援全文 detector recall、production accuracy 或廣泛版型泛化。

## 核對與隔離

[Verification](verification.json) 核對新 PDF 的 magic／完整 hash／大小、不同原作與 bytes、抽頁排序、所有 unit ID／頁面／source boxes、coverage 計數，以及來源文件與 renders 的 hash。source boxes 只給 evaluator 定位，不能交給模型裁圖。沒有建立大型工具、下載模型或執行 baseline／challenger。

本資料不能加入舊 holdout 或修改其規則。若使用這份 validation 選配置或門檻，後續應保留它的 validation／開發曝光身分；兩份資料不能再聲稱是未用於選方法的 holdout。舊規則與資料維持不動。
