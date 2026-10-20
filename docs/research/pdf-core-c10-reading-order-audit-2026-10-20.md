# C10 / FULL_PAGE reading-order audit — 2026-10-20

C10原案例的主文閱讀順序完全符合既有參考，FULL_PAGE仍有5組來源順序反轉。此結論修正「FULL_PAGE較值得保留」可能造成的讀序優劣暗示，不改寫封存實驗或門檻。

實際核對native `body.children`，使用既有source anchor對應，並非只看JSON texts陣列。參考與C10：P01→P02→H01→P03→P04→P05→P06→P07…P11。FULL_PAGE：P01→P06→P02→H01→P03→P04→P05→P07…P11。右欄頂端P06被提前到左欄5個單元之前。參考原已排除furniture/footnotes，此次未更改分母。[機器可核對證據](pdf-core-c10-reading-order-audit-2026-10-20.json)。

C10的邊界算法是我們的工程，官方只提供plugin擴充接點，沒有建議獨立10pt、不重合併的這個配方。10pt取自原20kernel的半寬，不是官方認證調參值。[實作](pdf-core-ocr-region-policy-2026-10-20/region_policy.py)、[官方plugin文件](https://docling-project.github.io/docling/concepts/plugins/)。

保留FULL_PAGE是保留官方對照與較簡單的成本選項，不代表它讀序較好、已合格或一定要當主線。現有不同輪次單次七頁轉換總和：C10 29.18s、FULL_PAGE16.58s，含debug/寫檔、不含初始化，不是SLO或正式效能排名。C10雖有讀序優勢，仍有重複、亂碼及語句缺損，不能整包降為minor。

原案例不需再修C10排序。若選擇繼續C10，下一個獨立工程範圍是讓context只幫助辨識、同一來源文字只有一個輸出歸屬；不先改原生ReadingOrder、不做全域xy排序。歸屬處理可能改變原生排序輸入，須把本頁正確順序作positive control，並同時驗七頁正文次序、標題、合法跨欄續段、重複與內容。只有真實仍錯序的頁面才繼續診斷ReadingOrderModel，不能假設去重後必然保留讀序。

本次只讀取封存結果；無模型推論、無新增ownership候選、無驗收變更，也未證明改善讀序的內部因果或七頁全量合格。
