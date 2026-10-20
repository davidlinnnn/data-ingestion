# W3 評分預登錄（source-only 階段）

2026-10-20 08:15 UTC 開始，最晚 11:15 UTC 停止；conversion 最晚 11:00 UTC 停止以保留彙整時間。沿用 W2 凍結 36 篇／715 頁；所有研究產物只在本 W3 目錄。

## 順序與 E0 / E1

三類 oracle builder（formula+code、table、image）只讀 LaTeX archive、W2 的 source/prose oracle 及 PDF 原生文字／頁圖。不得以 Docling 的偵測或重建結果決定 gold 的存在、內容、複雜度或定位。各類封存後建立全域 `oracle-freeze.json`，才讀取 E0 或啟動 E1。解析或定位不到的項目保留 UNKNOWN；來源可證在選定頁外才標 OUT_OF_SCOPE；無 LaTeX 的 Adam 不假造結構 gold。舊 W2 已看過的失敗不當作本回合盲測。

E0 是 PyPdfium、Heron、separators=True、bookmark-only heading、影像關閉、enrichment 關閉，優先重用 W2 R3/V3_B 已保存輸出。原生頁框、layout stage 必要時用對應原 conversion 的已保存 result/layout-raw；零推論，不以新模型或 backend 改寫 E0。後處理 loader 曾 clamp 的 bbox 另註明，不能把序列化 clamp 當成模型改善。

E1 只增加 do_formula_enrichment / do_code_enrichment。本機已有 CodeFormulaV2 `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`，不下載／升版／更換模型，不呼叫 API 或圖片描述／chart model。每篇 fresh CPU4 worker、單工、RSS 12 GiB、主機可用至少 4 GiB、零自動重試。生成 token 上限、temperature、batch 等官方預設不調參。新增 batch 計時僅觀測，不修改輸入或推論結果。

## Oracle 與數值口徑

所有類別同時列：來源元素總數、IN_SCOPE 可定位數、UNKNOWN（解析／定位／匹配各原因）、OUT_OF_SCOPE。偵測率分母為可評 IN_SCOPE 的來源元素，不能把 UNKNOWN 當未偵測或正確。另列全來源可評覆蓋範圍。gold→native item 必須保存來源頁、文字／幾何證據、item ref；只有同頁或不唯一候選不能直接算偵測成功。

Formula：保留 raw LaTeX。正規化只忽略使用者允許的空白、left/right、間距／字型命令差異；不得抹去否定、不等號、指數、下標、分母、範圍或數字。完全一致／接近／錯誤是重建對齊類別；近／錯只有對頁圖裁定改義才能列 Q31 語義阻擋。事先以固定 hash 規則從近／錯抽 50，數量不足全部；保留未抽／無法裁定數。行內 $…$ 源位置及攤平型態另評，不混入獨立公式分母。

Code／algorithm：source 原文及 macro 正規化行序，保留換行與縮排證據。逐行報漏／多行、縮排、運算子／字串變動；無法確定邏輯改變的文字差異保留 UNKNOWN，Q33 改變邏輯即阻擋。algorithm 不是 runnable code 時明列其比較方式；原文已被誤偵測成 table/picture 不能算 enrichment 重建已評。

Table：來源 numeric data point 是「值＋來源 row/column labels」；重建缺少、錯值、錯標籤對應、多生資料點均算錯。每表的錯誤率 = 錯誤數／來源應有的資料點數；若多生很多，錯誤率可 >100%，不截斷。複雜表依來源多層表頭／merged、多子表、單格多值、跨頁預先標記；複雜表 <=5%，一般表 0 錯。資料點分母或標籤不可解析時 UNKNOWN，不將 UNKNOWN 表宣稱通過，不跨表平均裁決。「關鍵比較」未評。無 numeric data point 的純文字表另報文字結構，不能給 0/0 通過。

Image：figure 與子 figure 分別保留識別和多對一／一對多關係，includegraphics 呼叫數不是 PDF 可見圖數的保證。caption 接圖與 raster object bbox containment 分開評；頁圖 vector、未知物件或來源不可定位為 UNKNOWN。PDF raster objects 幾何可直接從原 PDF 讀，不需為此重跑 conversion。native picture children 不是 C 分支的圖片 supplement。

## 雙交付模式

RAW = 官方保存 native text/Markdown/table-grid 出口；MAPPED = 沿用 W2 三條 JSON-only 規則：empty text 回退 orig 並標角色不確定，picture children 原生字獨立交付、與 C supplement 分開，native table cells 單次輸出並保留 span。兩模式的偵測 label/bbox 並不因 mapper 改變；交付、覆蓋或重複可改變。回收 orig 不等於公式／code 正確，圖片內文字不能自動當正文，跨 ref 真重複不去重。

RAW 與 MAPPED 都保存分子／分母與 UNKNOWN；只有輸出模式相同者比較改善。不新增整體通過率、人工接受分數或自訂 Canonical Acceptance 門檻。資料點準確度與使用者逐表規則分開。樣本裁定不外推成全部公式或 code 無誤。

## 成本決策

先登錄完整選定頁的 CRNN（5頁）與 SICA（18頁）作 E1 成本測量，覆蓋短公式及長 code/prompt。完成後同時報 wall、CPU、每 formula/code crop 耗時／長度與 RSS。以全量 CPU4 執行的牆鐘預估是否 <=7200秒決定：符合則全36；超過則從每 family 最多40條獨立公式的事先 hash 分層名單＋code/algorithm 全收。抽樣頁／item 名單必須在相應 inference 前再封存。若 code 全收本身也預計超出剩餘時間，停止並回報可達範圍，不暗中截短 code、降低生成上限或只挑簡單公式。

樣本若有偵測不到、定位 UNKNOWN 或 model 不處理，保留其狀態，不以替換其他元素湊成功數。pilot 只有其事先選定的範圍，不能混充 family 分層評分分母。
