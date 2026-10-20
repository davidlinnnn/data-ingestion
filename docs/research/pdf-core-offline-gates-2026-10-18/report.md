# A／C 來源方法與 B 離線接點：本輪結果

2026-10-18，Asia/Taipei。**兩條離線工作已結束：B 新評讀介面與 T03 公開接點的 19 項控制通過；A／C 的「整頁 read-only context＋原 owner 分別回填」仍不能登錄為完整方法。**本目錄執行零模型／API、零下載／安裝，未讀 holdout、未改歷史輸出。使用者在此檢查點另明確選擇繼續 B 獨立比較；後續推論獨立保存在 [B challenger](../pdf-core-b-model-challenger-2026-10-18/)，不回寫本輪離線成績。

## A／C：輸入擴大並不自動建立輸出責任

[診斷資料](AC-diagnosis.json)對全部八頁的實際 PNG 核對 SHA、尺寸與非均勻像素，重算全部 40 個舊 hybrid routes，與封存結果逐欄相等。44 source groups、27 ordinary negatives、41 legacy units 分母保留；兩個 unresolved routes 仍是混合圖／圖題及跨 parent 的 algorithm／正文。這不是新的轉錄或準度分數。

本輪新增的診斷假說是：**每個原 owner 各自負責輸出，完整來源頁只提供 read-only context**。不使用人工 bbox／文件 ID 選路，不再依 detector 精準小框。保守盤點除 B 表格責任外共 85 個 owner 單位；重複計算的完整頁輸入為 175,227,744 pixels，八頁原始影像為 15,777,840 pixels，約 11.1 倍。85 不是已排定 API calls，也不把 pixels 倍率換成 tokens、延遲或帳單。

| 實際檢查 | 結論 |
|---|---|
| 完整頁面影像與既有來源範圍 | 實際 bytes 可用；整頁存在仍不證明正確 target discovery、公式重建或讀序 |
| 原生跨 parent algorithm 的實際 refs 進既有 A scope | 重現 `ordered scope requires one native parent`；把大組拆小不等於完整 code 順序／交付已成立 |
| SEAL 圖／圖題及 17 處 math 的分工 | 原 owner 分別回填沒有建立混合圖中公式 occurrence 與正文圖題的共同來源／輸出契約；只保存圖或正文 title 不計重建成功 |
| C 55 頁 FULL_PAGE 產物 | 逐份讀回 19 ranges、55 個來源頁、29 個 native pictures；title 文字在正文，但其 bbox 仍在原 picture 外 |
| 改把完整 SEAL 頁塞入舊 C request | 原 crop request 可 materialize；只替換輸入頁圖時因 `actual image bytes changed` 拒絕。新 context 不可冒用舊 image-key/request 身分 |

**A 與 C：`NO_REGISTERABLE_METHOD`，限定於這個 input-only／沿用原輸出接點的假說。**仍需一個具名且可檢查的跨 owner 來源／順序／補充資料契約，才可排定固定推論。這不證明 Docling／VLM 無法達成，也不表示所有可行方法已窮盡。本輪不擴大 graph repair、不編造圖內公式位置、不把 C 額外 context 當圖內 OCR。

完整來源正確性及陰性內容保護未由這個失敗輸出方法證明；不因全頁提供了所有背景，便宣稱 44/44 quality 或 27/27 negative preservation。已確認的必要輸出阻擋足以停止該完整方法。

## B：評讀器與 T03 的正面證據範圍

[新 scorer](scoring.py)只根據**顯式的來源匹配／判斷**計數，並把決定綁到實際 text、header、dimensions、group、conditions 等觀測 snapshot。它沒有 T01／T04 的特殊命名分支，也不把 delivery 存在當來源審查完成；source decisions 缺少、pending 或 false 都不通過。數學等義仍由明示來源評讀決定，不靠 literal assertion 假裝作任意代數驗證。

控制包括：來源答案生成的 **MOCK T04** 300 點／5 比較，經公開 Core reload 與實際 Markdown render 後可計分；等義維度名稱可通過；允許範圍內的一個數值小錯或 missing cell 可通過；錯誤／過期 header、group、condition、pair 綁定、完整缺列的來源負判斷、額外數值、critical relation 反轉、重複消耗與未審查狀態均拒絕。Dash 的等義字形可保留 missing-run 意思，`0` 不可冒充缺值。這些是機械與顯式來源判斷控制，不是自動語意 detector 的準度證明。

[T03 seam](table_seam.py)從實際 S0 的全部 tables／caption／header 發現 `Table 13` 與兩個明確 continued，形成 `#/tables/2`、`#/tables/3`、`#/tables/4` 的同版 logical relation。它保留三個原項目，只在 isolated copy 更新公開 `TableData`；使用 **MOCK 六欄內容**檢查 JSON reload、主要 Markdown、原 caption 條件參照、三頁 provenance、body graph 及另外兩張表的資料與 rendered Markdown 原樣。不存在 cell-level geometry 就明示 fragment-envelope 精度。缺片、stale revision、重複 initial caption、missing caption、頁序缺口與 header 衝突會拒絕／abstain。

[MOCK bundle](T03-MOCK/document.md)不是實際表格重建；264 numeric／7 comparisons／3 missing marks **均未作新推論準度驗證**。此接點不是 Docling 原生自動跨頁合併，也未把三張表改成一個 SDK item。

## 舊輸出的離線重播

[結果](result.json)採舊 explicit point-to-anchor matching 讀取實際 Core／rendered 數字；數值診斷保持 T01 6/6、T02 84/84、T05 80/80，關鍵比較分別 3/3、8/8、7/7。T04 整頁 withheld，300 required values 未交付，不能寫成 300 個 raw 都辨識錯。Table 7 沿原來源人工判斷重播仍為 3/4，第一式真改義保留。

先前的 structure flags 有機械填 true 問題，新 scorer 的這些 decisions 明列 pending，故不把上述重播自動晉升為新的 source-QA pass。舊版人工成績與 raw 均未改寫。新模型須留下自己的顯式匹配與來源評讀。

## 檢查與版本

- 首次完整執行：16 controls 通過，見 [tests.json](tests.json)與[執行 snapshot](result.json)。
- 複核補上 missing-run dash 等義控制及兩個真實 A／C 邊界反例：19 controls、0 failures、0 errors，見 [tests-v2.json](tests-v2.json)。v1 scorer／tests 保留在 `evaluator-precheck-v1/`；新 scorer 重算舊數值診斷完全相同。沒有因此重跑模型或重封歷史期望值。
- [input-verification.json](input-verification.json)保存已讀來源與歷史輸出 SHA 的前後核對；原始 execution seal 保留，現在入口使用獨立 `artifact-seal-v2.json`。
- 唯讀入口：`/private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-offline-gates-2026-10-18/check.py`。檢查 artifacts／歷史 input identities，再跑上述 controls；不建立新結果、不讀 credential、不載入推論模型。

## 決策

B 的離線檢查具備進入**單獨表格候選比較**的機械證據；A／C 仍阻擋完整 Profile。檢查點後，使用者明確選擇完成 B 獨立比較。只執行已登錄的單一 challenger：最多七次單頁，全部品質符合才做 T03 三次；失敗不自動換模型或調 prompt。完整配置、外部回歸、公司模型／GPU／vLLM 與 pilot SLO 均不能由這份離線報告認定通過。
