# W3b HTML table source oracle（全域 freeze 前）

僅使用 root 保存的 exact-request-version HTML bytes／manifest、原 PDF、W3 凍結 LaTeX table oracle 的來源 caption／頁定位。沒有讀 E0/E1、mapper 或評分。HTML URL／metadata 是版本證據，不等於實際全文版本認證；10 張抽表與 PDF 的局部內容一致，不能推出整篇所有段落一致。Adam 只有 PDF wrapper，ANSWER_UNAVAILABLE，不能說來源沒有表。P04 依 body identity 完整，不能只因 head title 為 Introduction 判成部分來源。

以既有 lxml 解析 HTML，不執行 JavaScript、不安裝套件。保留 bytes SHA、DOM id/line、caption、原 td/th 與 scope/class、rowspan/colspan、MathML presentation 及獨立 alttext。MathML annotation 不再次拼入 presentation，避免同式重複。表格 grid 以原實體 cell id 參照，不因 span 複製資料值；非法／相撞／越界 span、ragged grid、LaTeXML error marker 均記 UNKNOWN。未展開語意不猜測。

排除 equation/math layout，以及含 nested table 的外層排版容器；保留 leaf data tabular，含 inline tabular 與 figure 內真正資料表。無數值的圖示 grid／文字表仍保守列為 source candidate UNKNOWN，不給 0/0 PASS。原先 float-only draft 的 232 leaf inventory 保留在 oracle.draft-v1.json；擴充 inclusion 後為 267 leaf，沒有依輸出挑表。

主評單位是 `semantic_tables`：同一共同 caption 的 float 多個 leaf 合成一表，points 相加、各自 subgrid 保留，強制 Q13 complex；無共同 caption 的獨立表不硬合併。`tables` 是 leaf inventory，不能把多子表拆成 ordinary 各自過關。

表頭推定由 HTML span/grid 與首次具 row label 的數值資料列分界決定，原 HTML guessed header 標記獨立保留。純數值第一欄如 train OS／layer count 是資料，不因在第一欄就漏掉；沒有獨立實驗列標籤時保留 physical-source-row configuration 與完整 source row signature，不捏造模型名。空白／引用換行列、非唯一 row/column label、跨 label domain 的 data span 保留 point UNKNOWN。HTML 結構可信與 row-label 語意可信分開。

主資料點是「單一 numeric component + row/column hierarchical label + cell-local component_index/role」。完整 cell value 另留，可輔助同格一致核對。± 左／右分別記 central value／reported uncertainty，沒有定義不自稱 standard deviation；Search Space 的 bracket list 記 candidate option；其他多值無法確定子角色便 UNKNOWN。所有多值 cell 事先 Q13 complex。GPT-4、模型大小或數字在 row/header label 裡，不拆成數值資料點。數值 unit suffix 與完整 cell 單位上下文保留，不任意換算。來源數值分母不把未知 component 當正確；也不把 cell 多值全算一點。

Q13 complex 在來源端固定：多層 header、任一 merged span、多子表、單 data cell 多 numeric components、來源跨頁。其餘 ordinary；不依 target 表現改標籤。

固定種子 `W3b-html-table-audit-20261020`，以 SHA256(seed + `|` + leaf id) 排序來源 IN_SCOPE、含數值的 leaf candidates，取前10。原 float-only draft 與初抽清單留存；source-only inclusion 修正後，同種子抽樣新增 P03、移除 P10，10 表已全部逐格核原圖 header/value/span，沒有因抽到錯表換樣。五表由獨立 trace reviewer 核對，五表由本 reviewer 核對；結果見 audit.json、原頁 PNG/SHA。10 表全部 PDF_FAITHFUL，沒有確認的 LaTeXML value/span 錯轉；抽查發現的 numeric suffix 截斷是本 parser bug，已在 freeze 前修正並 selfcheck。

對所有已 source-caption 定位的表，用 pypdfium2 原 PDF text layer 檢查 numeric+unit 的頁面 multiset。這不是 E0。頁內多表共用文字流，presence 只能支持來源數值存在，不能證明 row/column 關係；absence 可能是 PDF text layer 的抽字缺陷，不宣稱 LaTeXML 錯。真正 source/PDF 衝突須原圖證據，標 SOURCE_PDF_MISMATCH/UNKNOWN 後不當模型錯；本輪沒有確認的衝突。未定位表 UNKNOWN，不推定缺表為來源0。

下階段既定判準：每張 semantic table 報確證錯誤／可信 N、未裁定點與錯率區間。ordinary 有一個已證錯誤即 FAIL；complex 錯率下界 >5% 才能由下界確證 FAIL，未知上界仍可能 >5% 則 UNKNOWN。native collapsed cell／header 不按 gold 把數列 zip 回多欄當正確，也不全算錯；完整 numeric value+row/column association 才算正確。SOURCE UNKNOWN 與 TARGET ALIGNMENT UNKNOWN 分開。沒有 numerical point 的表不給 0/0 PASS，不跨表平均掩蓋失敗。

Source locator v2（仍未讀E0/E1）：保留 oracle.v1.json／freeze.v1.json／來源程式v1 後，對原 UNKNOWN caption 使用來源原 PDF 全頁 native text 查找前20→12→10詞的 normalized prefix，必須整份PDF只有唯一頁命中才定位；歧義仍UNKNOWN。此步只改locator與衍生source-numeric crosscheck，cells/points/Q13逐值不變，10表抽查不重抽。BERT Table1由來源prefix唯一定位p6。
