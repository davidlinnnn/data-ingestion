# Table target scorer independent QA

固定 v2 候選：4 個 provisional native PASS 全收，5 個 FAIL→PASS 翻轉全收；hash排序未依結果或family重選。9表跨ACL/EMNLP、NeurIPS/ICLR與Pilot三個既有family標籤（Pilot的具體版型仍沿來源標記），8張來源PDF頁圖逐一看過，共201 numeric components。

9個新/既有native grid均與原PDF全部數值、行列表頭一致；實際交付檢查為 RAW 8 PASS/1 UNKNOWN、MAPPED 9 PASS。這不將nativepending誤稱交付通過。

| Table | Variant | Native | RAW | MAPPED |
|---|---|---|---|---|
| F-acl_sbert:html-semantic-table:S5.T5 | E0 | PASS | PASS | PASS |
| F-nips_attention:html-semantic-table:S6.T4 | E0 | PASS | PASS | PASS |
| F-acl_sbert:html-semantic-table:S4.T4 | E0 | PASS | PASS | PASS |
| F-acl_sbert:html-semantic-table:S3.T1 | E0 | PASS | PASS | PASS |
| P-11-2508.19828v5:html-semantic-table:S4.T2 | cellFalse | PASS | PASS | PASS |
| P-13-2601.01885v3:html-semantic-table:S4.T5 | cellFalse | PASS | PASS | PASS |
| P-19-2511.10395v1:html-semantic-table:S7.T6 | cellFalse | PASS | UNKNOWN_HEADER_ASSOCIATION | PASS |
| P-13-2601.01885v3:html-semantic-table:A4.T6 | cellFalse | PASS | PASS | PASS |
| P-13-2601.01885v3:html-semantic-table:S4.T4 | cellFalse | PASS | PASS | PASS |

P13 FILTER表 S4T5 的v2 baseline 15 extra是分析器誤判：packed 6×1表的必要數值仍完整存在，並非新增數字。heading已同意保留v2並修v4 header全局碰撞規則，該翻轉應為UNKNOWN→PASS，不算已確認FAIL修復。其他packed-cell missing也需標明tuple關係失敗與lexical數值存在的不同。

P19 Table6新RAW Markdown含兩行表頭，首行Model/AppWorld/BFCL沒有緊接separator而被Markdown parser視為表外paragraph；thead僅空白/Steps@.9/Steps@.9。數值與相鄰文字仍可由人推斷，故此處獨立判RAW header association UNKNOWN，不直接宣告Q4阻擋。MAPPED HTML同一header cell保留benchmark與Steps，通過。實際render HTML與三份grid證據在target-audit-evidence/。

Gold未改、無新conversion、未讀R1。來源/輸出SHA及選樣SHA保存在JSON；後續分析器修版不回溯替換這9個QA樣本。

V4追蹤：固定9樣本不變。原5個v2翻轉中，P13 FILTER S4T5及P19 S7T6 baseline已改為UNKNOWN，因此僅3個confirmed FAIL→PASS（P11及P13兩張reward表），另2個UNKNOWN→PASS。V4恢復ResNet E0 PASS在原抽樣外，不替換或擴充這9個主樣本。
