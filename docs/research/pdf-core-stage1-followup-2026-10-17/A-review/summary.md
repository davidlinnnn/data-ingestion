# A 獨立來源與交付核對

結論：**新的公開 Core 接點與有界 transport 控制成立；完整 A 來源 gate 仍未放行，分支為 partial。** 舊的混合 owner 單點替換限制已有可實際交付的通用 fragment-order 接點；但圖／body 交界與原生未 emit 的必要字形，仍沒有完整影像輸入與責任交接證據。責任分類、幾何可達、合法回應運輸、來源意思與模型品質分開判斷。

這是已曝光 DEV 的獨立核對。沿用原先在讀 producer 前封存的 44 個來源 groups、27 個普通陰性，以及另列的舊 41 units；沒有重建分母或把這些數字當 API jobs。Evaluator 沒有向 producer 傳來源答案、人工 bbox 或 target 列表。

| 核對 | 新結果 | 可以支持的結論 |
|---|---|---|
| 44 來源 groups | 36 個有 A eligible envelope；7 個屬表格；1 個圖內／圖題 group 部分可達 | 只代表來源幾何及責任，不等於 36 個內容已正確 |
| 原 41 units | 41/41 有可達 A owner，原來是 40/41 | 原混合 owner 的表示限制有進展；不是模型改善分數 |
| 原 5 個 unprepared units | 四個空文字 display formula 可走公開 formula 路徑；混合 owner 可分 fragment 插入 | 必要工作不再因 native text 空白或單點替換被排除；轉錄與實際來源讀序仍未驗 |
| 普通陰性 | 27/27 有 eligible scope，原來是 24/27 | 三個 caption 由 parent serializer 原位一次交付；不能因沒有獨立 slot 判遺失 |
| 公開接點控制 | 獨立重跑 17/17 unittest 通過 | 包含 BODY→middle→TITLE、跨頁單 block、literal/code、caption、pure-formula picture、邊界拒絕與 saved artifact reload |
| 實際 native/MOCK 運輸 | 66 個 direct-body owners，加上另存的 11 個 group children | 原生範圍與 mock 可映射及 reload；不同控制的文件沒有被拼成完整候選 |
| 保護正例／跨頁回歸 | 7 個未改歷史內容 payload，涵蓋 4/4 正例、4/4 joins，全部通過新接點 | Typed literal/math 次序、Markdown math 文字、非目標 anchors、來源 binding、JSON reload 保留；舊 3 個內部斷段也原樣保留 |

幾何比較使用原稿非空白 glyph 中心與 native envelope 的 2pt tolerance；舊 41 locator 使用 0.45 bbox overlap。原先 44 項的 glyph／discovery／eligibility 計數全部精確重現後，才評新 inventory。表格 cell 沿用整張表 provenance，沒有虛構 cell bbox，也不把每個 cell 重疊整張表當額外 discovery 分數。圖上未 emit 的字形只能由來源視覺評讀確認，不能由這個幾何分數證明完整。

七個 table groups 必須分成兩類。Table 6 的三個 code groups 已在 cached S0 的 typed strings 與主要 Markdown 保留工具識別字及正確 row association；少了 backticks 與不標準 grid 排版本身不算漏 code。Table 7 的四個 math groups 則仍有必要意思失真：分數缺少明確除法範圍，部分公式跨 row／cell 錯置；這不是 minor typography。它們可以交由 B 承責，但通用合法 math-cell transfer 只證明表示接點，不能把這四個來源答案改判已修好。具體 source-only 對照在 `native-delivery-evidence.json`。

Table 7 的 formula caption 已由 table parent 序列化一次；變數定義與 full-batch 條件保留，flat subscript 及少量字形屬 minor。新 caption 接點只接受 plain-text payload、明確拒絕 typed inline children；F13 不要求特定 typed inline label，因此這個限制本身不構成該已保留 caption 的必要意思失敗。

混合 algorithm／prose 的 source owner 現在可以用合法 fragment/order response 運輸；generic 排序反例確實通過。實際來源 mock 沿 native literal 與原始次序運輸，沒有執行新的模型分段、轉錄或來源讀序評分；不能將原生 eligibility 與排序控制，寫成該論文 algorithm／正文已修正。Pure-formula picture 的 3 個 owners 另有公開接點控制，沒有因分類到 picture 就掉出 A，也沒有把 owner/member 雙算為 jobs。

圖內公式 group 仍阻擋完整來源 gate。來源共有 17 個 math occurrences，其中圖題的必要字形沒有被原生文字層 emit，原生 picture envelope 又不包含該 title box。單看 picture.children、保留原圖或建一個可存 OCR 的 supplement，都不能證明完整輸入／重建；尚需通用的 picture/body 邊界與來源影像 coverage 規則。細節只留 evaluator 的 `figure-boundary-evidence.json`，沒有傳給 producer 作特例。這不是模型或 SDK 無法解決的證明。

凍結 inventory SHA-256：`d6172d5aeb10813eea2a228dc36af3c0444979defe1f4e4eee15c8f374fb0382`；方法：`9831bdae81c19b08546fe49b3bda8d3a3332712e09d89fa925bbeae60ae223e9`。機器對照在 `producer-coverage-comparison.json`；原 census freeze、舊輸入及新產物 hashes 在 registration／verification／artifact-sha256。第一輪 evaluator replay wrapper 因仍帶歷史 bbox/code_language 被新 schema 拒絕，已保留 `replay-wrapper-precheck.json`；更正只換 native scope 包裝，原內容與 segment 次序未改，沒有重呼叫模型。

本輪未做新模型／API、下載安裝、holdout 或 production／SDK 修改。`N_CF` 仍是 null；完整來源／影像責任及正式 jobs／input／output 預算未固定前，不啟動完整 A 推論。歷史 payload transport 成功也沒有修正其舊內容／斷段，更不代表完整配置或來源語義驗收通過。
