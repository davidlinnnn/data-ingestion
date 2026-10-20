# 離線交付的來源／表示評讀

2026-10-17。只重放先前已目視評讀的 Table2 API raw 與 Standard S0 JSON；本輪沒有重新開 PDF／圖片，沒有新模型品質證據。

- [完整 stock Markdown](document.md)逐段檢查：六個 panel title 依(a)→(f)出現；各 panel 的三個 metric headers、setting、printed values 均在對應 Markdown table。驗證器亦逐 cell 比對 Markdown 與 public TableData，84點未改；型別reload後再次匯出完全相同。
- 原 source caption 在(a) title之後、第一張子表之前完整出現一次。由第一張子表引用，source-key manifest把六張子表綁在同一 group。這是主要 Markdown 的邏輯展開，沒有承諾保留PDF左右排版或建立 heading hierarchy。
- 可見條件由既有 native caption 交付：每個 panel只改一個factor、(a)固定4:1:5及各train subsets／100%重用split run、(b)reflection mini-batchsize、(c)rollout batchsize。它們與舊provider三項conditions語義一致；`B m`／`B`是原Standard抽取，不在本輪改成新數學表示。完整provider conditions另保留於[bindings](bindings.json)，沒有當成額外來源段落再重複插入Markdown。
- provider原caption漏字面`Table 2`仍完整保留在manifest。Markdown使用原Standard caption（它本來已有表號），不是從oracle補字，也不重新把舊raw判成無缺陷。
- 空白左上header保留provider未提供獨立setting header的狀況；setting仍以首欄的row_header型別與printed row strings保留。沒有編造`Setting`這個來源文字。
- Table3、兩段後續正文及它們原有caption／provenance／順序未改。Table3原本的cell錯配／flattening也仍存在；「未退步」不等於Table3內容已合格。live階段若執行，兩個native targets都必須處理與評讀。
- 六個panel沒有個別bbox；各title／table沿用整張native table envelope，cells bbox=None，manifest明記粒度。這不證明panel或cell精確定位，也不能把它當完整F18認證。

離線gate通過：公開Core型別與文件樹API可承載這份正確raw；無數值修補、私有helper或自訂renderer。已知replay target綁定不是自動路由，兩頁live仍未執行。
