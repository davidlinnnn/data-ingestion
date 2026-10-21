# T05：完整表身 crop 的獨立來源／交付評讀

2026-10-17。六次固定 API 呼叫全部完成、`all-calls-complete.json` 存在後，才讀取本輪回應與 frozen oracle。獨立檢視原始 216dpi Table4 證據圖及實際送模型的 144dpi 原生表身 crop；沒有改 producer、prompt、mapper、回應或 oracle。

**本頁在原定表格範圍通過。** Typed 與實際 CommonMark＋table 渲染後的 HTML，各自保留 80/80 數值綁定、7/7 關鍵比較、20/20 同一 physical cell 的 Proposed／Accepted 成對值；無額外或重複數值。此次沒有依結果放寬數值、表頭或條件判準。

| 項目 | 結果 |
|---|---|
| 表頭與 spans | Category 的 rowspan2；Skills／Wiki Patterns 各 colspan3；Create／Edit／Avg. Length 的父子與 Proposed／Accepted 順序皆保留 |
| Row groups | By Model (All-Dataset Average)、By Benchmark (All-Model Average)，原順序、各自 colspan7／row_section 角色保留；十個 category 是 row headers |
| Source caption／外部條件 | Baseline 原 standalone caption 在主 Markdown 與 canonical 各保留一次，包含 average length 的 markdown-lines 單位及 all wiki creations/edits retained 條件；沒有猜測 attachment |
| 表身模型輸出 | Caption 為空，conditions 為空；表內平均範圍留在 row groups；沒有憑 crop 重建看不到的原文 caption |
| 來源與非目標 | 原生 table envelope 保留；所有非空原正文的內容、orig、label、順序及 provenance 不變 |
| 交付 | 評分取實際渲染 HTML 的 cell text，含 entity 解碼；canonical 未受評讀或渲染修改 |

主 Markdown 的 pipe table 將每個 row-section 字串重複顯示在七欄；typed 中仍是一個 colspan7 的來源 cell，顯示範圍清楚，沒有把它當成七個新數值或錯誤的 global header。這屬可接受的表示差異，不能據此額外要求 pipe Markdown 無損重現 PDF 排版。

相較前一輪 full-page producer，數值／比較同樣通過；此次 caption 不再重複的原因是先完成的 ownership 政策，不能歸功於 crop 讓模型學會 caption association。此頁結果也不能抵銷同輪其他表格的失敗。

[逐點評分](t05-evaluation.json) 保留全部 observations、比較、paired cells、來源／程式 hashes；[實際 HTML](wikiskill-p13/evaluated-rendered.html) 可檢視渲染結果。[evaluator](evaluate-t05.py) 重用先前 frozen T05 評分函式，另以實際 HTML parser 核對 rendered cells，並有改一個數值、換錯 header binding、HTML entities／nested inline text 三個自我檢查。Frozen method 與六份 response hashes 評讀前後一致。

未取得 unseen 泛化、整份文件或公司 Qwen3／高頻資格；來源定位仍是 whole-table envelope，沒有生成 cell bbox。本評讀未呼叫新模型／API。
