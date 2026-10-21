# W3 公式、程式與行內數學：時間預算內部分評估

主線因預估剩餘推論時間超過回合上限，停止新增 conversion。E1 最終範圍17篇、85實際處理refs；封存211gate refs中84已處理、127未處理，另pilot有1額外code ref。未執行清單見 final-processing-coverage.json，不算模型失敗。封存 gold／抽樣 gate／E0 matched refs 不變；分析採 v2 格式正規化與 body tree 順序。

**口徑限制：387 是外層公式區塊，不是已逐條拆開的獨立公式。** 封存rows合計431；lexical TeX行段910，118區塊有多段。多列環境保留 rows，derived row inventory 不能區分單條跨行與多條等式；50 人工抽樣也是公式區塊，未完全達成使用者逐條公式的分母要求。

現行人工規則是 `audit-protocol-amendment.json` 的 **50 FORMULA near/error**，不是早期文件的 20/15/15 混合抽樣。按固定 SHA 排序，近／錯各25，不足轉移；最終pool55（38近／17錯），選33近／17錯，不以 exact/code 補足。

E0：公式 known 194，自動 eligible-role 對齊候選 187；這是候選覆蓋，不是已證偵測準確率。程式 known 70；演算法 known 2。封存未對齊的7單位另全看圖：6其實有formula角色，1 P12來源長式與PDF簡式不一致；不把它們稱7真漏。原生366個formula角色text全空、orig全在，這是materialization現象，並不證366全是真公式。另已看頁圖確證 P16 p25 有35個非公式 task ID 被標 formula，僅為觀測誤偵測下界。

E1：已完成 17 篇；凍結自動對齊樣本中已實際處理的 known source 公式／程式／演算法單位分別 57／21／0；另由頁圖人工身分核對確認P04有1個算法實際處理，見下方例外證據，不改封存map。沒有被選或未實際推論的單位不記作模型失敗。

目前公式抽樣選 50 區塊，已審 50，待審 0；其中確證 blocking 15。已依固定規則封存最終50；額外已審 6 案另列。人工先核對來源與固定 native ref 是否同式，再核模型 active text；非空錯字不以 orig 救回。

RAW 官方 Markdown 與 MAPPED 實際 renderer 輸出，逐 family 數字在 assessment-summary.json。MAPPED 使用凍結 R4 三規則；空 text 才回 orig，保留 picture child 不確定性。數學核心保義、整體重建忠實度與 TeX 可渲染性分開；未執行 TeX rendering，因此 syntax/render 一律未證。

行內來源共4571處，正文候選3751處，其餘按 caption/table/figure/footnote 等脈絡分開；不能將來源 `$` 或上下標數量當成已觀測攤平頻率。固定 hash 的6個正文例已看圖確認 E0 RAW/MAPPED 上下標攤平（F13），未另證 F01/F02 改義。

程式／演算法全99 source 單位已有逐行自動診斷；literal Unicode 不正規化，運算子與字串保留，縮排另列。自動逐行差異受換行與未展開巨集影響，均非自動 Q33 判定。人工程式21單位已全審：9保義、6個Q4忠實度阻擋、4個source→native對齊錯誤、2個語義UNKNOWN。SICA列印log的工具字串/agent ID/數值變更屬Q4忠實度阻擋，不等同已證可執行邏輯改變；P01兩個跨頁partial ref對齊錯誤不計模型漏行。兩個known algorithm另見audit/algorithm-role-review.json：E0共43/43行文字存在，P04在code角色（原對齊漏），SICA在list角色；E0完整邏輯因變數/縮排仍UNKNOWN。P04實際經錯配code5選中refs424/425，E1將集合測試∈改=、epoch e≥2改>2、else分支破壞，確證1個靜態Q33算法邏輯阻擋，RAW/MAPPED都交付；不能被frozen算法gate0掩蓋，也不與code5對齊錯重算。SICA ref90未實際處理、文字與E0相同，不算模型錯。19個來源頁UNKNOWN算法不變。

來源頁 UNKNOWN、巨集與條件式、未編譯 TeX、原生公式誤對齊及未可定位演算法仍保留限制。Adam 僅 includepdf wrapper，沒有可用正文 LaTeX。完整證據見 audit/、row-inventory.json、code-line-assessment.json、blocking-cases.json。
