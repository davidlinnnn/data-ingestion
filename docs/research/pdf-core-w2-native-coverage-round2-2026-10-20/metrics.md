# W2 round 2：D1–D4 評讀登錄

凍結來源是上一回 Set F 16 篇／164 頁與 Set P 20 篇／551 頁，合計715頁；jobs.json保留原PDF SHA。正文讀序的主oracle是同版本LaTeX展開input/include後的整篇唯一prose anchors（至少8詞），包含附錄；figure/table/algorithm/equation環境不當正文，caption/footnote分別建anchor。Adam用PDFium字流備援，獨立標示。來源無法取得／解析／對齊不等於Docling漏句，列oracle_uncertain。

F取前12頁或全篇較短者：LaTeX順序不改，以PDFium全文匹配定位頁面，只將所選範圍anchor納評；其餘OUT_OF_SCOPE。沒有獨立來源頁範圍定位者UNKNOWN，不能把第13頁後算Docling漏失。P全文適用相同交叉核對。

匹配正規化可處理空白、字型連字、discretionary line breaks、已標記的citation／LaTeX格式，不可為求匹配刪除否定、數字、單位或對象。機器匹配只定位，不代替Q4語義評讀。

## 本輪指標

- 覆蓋：每個可信、範圍內anchor分別在native正文段落、整個native可見文字、Markdown查找，保存occurrence與item refs。body缺但其他角色有屬misclassification候選；完全缺為missing候選，超過來源occurrence為duplicate候選。模糊匹配只能提候選，不能直接判等義。
- 順序：只對唯一對齊正文anchor計算其Docling順序的LIS；報`aligned - LIS`數量與除以唯一對齊數的比例，保存LIS外IDs。多個等長LIS採穩定的最早位置演算法；LIS外不是獨立錯誤事件數，不與相鄰逆序混稱。
- 插欄跳躍：同來源頁，來源正文預期左欄段落後接右欄；輸出出現L→R→L，且後一L是尚未讀的來源左欄anchor，列三元組候選。缺獨立欄位位置時UNKNOWN，不硬由Docling bbox反推oracle。
- 混段：同一輸出正文item包含來自不同來源段落、在可信source-anchor序列中相距至少5位的anchors；這個距離是定位告警定義，非品質門檻。合法跨欄／跨頁continuation以來源paragraph ID排除；保留完整span供人工判斷。
- 家具污染：獨立PDF頁邊running text／頁碼／arXiv stamp字串或幾何區域對到正文段落。頁碼須同頁bbox交叉核對，不能用全篇數字substring判污染。沒有獨立來源身分者只列candidate。
- caption／footnote：各自可信anchor是否存在、是否在獨立且正確角色item、是否嵌在正文item；角色缺失、內容缺失、正文污染分開報。
- headings：用LaTeXsection/subsection等、或獨立明確編號，對baseline與官方後處理同一輸出逐項對齊，報missing／角色錯／level錯。官方stage不保證重建語義parent；其其他變更完整保存。
- inline-math：source inline math與PDF位置／候選scope保留為F13類，另報已確認flattening與候選；D3下不因純數學攤平改F01/F02裁定，除非同時有漏、重、錯序。

## Q4與抽查

每篇F01/F02的YES表示已人工確認必要內容的改義漏／重／錯序或家具／清單污染；NO須有該宣稱範圍完整核對，只有anchor零告警不自動給整篇NO；其餘UNKNOWN。另列anchor範圍的機器結果，不混稱完整profile合格。沒有整體通過率。

Oracle audit採確定性分層：從標錯候選取10、標正確取10，跨文件與類別分散，固定sample IDs後看來源整頁圖／LaTeX和輸出，報誤報／漏報及無法裁定。這是20案例條件抽查，不能外推整體FP/FN率；無圖像或來源不完整列UNKNOWN，不默認correct。

## 執行與資源

單一並發conversion worker、CPU4／interop1／batch1，S0選項與enrichment關閉保持不變。每篇timeout為baseline的180秒×選頁數，失敗篇保留後跳下一篇；零retry。RSS超8GiB或host available低4GiB停該worker；host memory仍不足則停止本輪。整輪絕不超過主線2.5h上限。

每篇保存完整ConversionResult、DoclingDocument、Markdown、stage timings、raw-layout、private shape/separator inputs與實際reading-order options。僅觀測stage wrapper，每次呼叫原方法一次，無SDK檔案修改或內容修補。每頁latency為preprocess開始至assemble結束的pipeline residence wall（包含queue、可與別頁重疊，不含最終全篇reading-order）；另報stage service wall總和及整篇conversion wall，不能把頁latency相加當全量wall。RSS是每0.1秒process-tree抽樣、該頁存活期間的程序峰值，不是該頁獨占配置量。CPU秒直接讀process user+system，不以wall×4推算。
