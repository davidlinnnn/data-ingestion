# Oracle 抽查登錄

本輪選樣在閱覽頁圖之前固定 `audit/selection.json`，附 selection SHA256；目標為十個機器標錯候選與十個機器標正確案例。錯誤樣本優先跨類別與論文，正確樣本跨 family 與論文；採確定性排序，不做隨機人口推估。每案保留 source anchor／LaTeX 位置、原 PDF 頁、輸出 item 或 Markdown 片段、頁圖檔與評讀理由。

標錯候選：原頁與原始檔證實 oracle scope／順序／內容正確，且輸出確實漏、重、錯序、混段或角色污染，為 true positive；輸出正確但 oracle 抽取、locator、source order 或告警定義造成告警，為 false positive。若同一告警混有真正缺陷與 oracle 誤差，分開記載，不以單一成功掩蓋兩者。

標正確案例：檢查 anchor 的完整文字、否定、條件、數字、單位、對象與相鄰 source anchors 的順序及輸出段落。發現 Q4 內容問題而機器未標示為 false negative；未發現則 true negative，僅適用該 anchor 與檢查範圍，不是整頁／整篇無錯證明。純 inline math 上下標攤平按 D3 另記 F13，不列為 F01/F02 漏報，除非還有漏、重、錯序。

無法在頁圖與來源中核對者列 UNKNOWN，不計入可裁定的 FP/FN 分母。十加十是條件抽查樣本，不能外推整體精確率、召回率或通過率。
