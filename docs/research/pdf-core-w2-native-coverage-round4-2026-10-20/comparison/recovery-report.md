# V4 recovery 六篇語義裁定

凍結v3全量比較44個變動candidate identities已逐一裁定；13個原baseline sourcegroups全部查核。見recovery-exact-coverage.json。

| 原baseline群 | V4結果 | 受影響來源頁 |
|---|---|---|
|p03-caption-spliced-p14|PERSISTING_BLOCKING|13,14|
|p03-caption-spliced-p21|PERSISTING_BLOCKING|20,21|
|incidental-p03-table3-breaks-reporting-clause-p5-p6|PERSISTING_BLOCKING|5,6|
|p10-chart-label-contamination-p9|PARTIAL_FIX|9|
|p10-chart-numeric-contamination-p26|PARTIAL_FIX|26|
|incidental-p10-offpage-old-figure-task-object-p10|CONFIRMED_FIXED|10|
|p16-task-ids-formula-role-p25|PARTIAL_FIX|25|
|P-20-2505.03335v1:furniture_in_body:00035|CONFIRMED_FIXED|6|
|p20-duplicated-corrupt-body-p6|PARTIAL_FIX|6|
|p20-table2-caption-spliced-p12|CONFIRMED_FIXED|11,12|
|p20-caption-duplicated-p28|PARTIAL_FIX|28|
|p20-sudoku-caption-duplicated-p46|PARTIAL_FIX|46|
|p20-caption-object-contamination-p48|PARTIAL_FIX|48|

原13群：3完整修復、7部分改善且仍阻擋、3持續阻擋。完整修復為P10 p10舊reviewer任務、P20 p6頁碼進正文、P20 p11–12 Table2 caption錯接。不得把partial當整群修復。

P16 p25必要task IDs：原60個中可讀MD交付25→26；恢復4個，同時新漏3個。這是既有群內的實質退化，新增sourcegroup數0並非零新壞內容。恢復：django__django-15930, sphinx-doc__sphinx-7454, sphinx-doc__sphinx-7748, sphinx-doc__sphinx-11510；新漏：django__django-12209, django__django-12308, sphinx-doc__sphinx-9320。

新增V4阻擋3群，均為running title進正文：P10影響2/4/6/8/9/10/23頁，P18影響2/3/7/8頁，P20影響10/11頁。跨頁原native prov已保存。

另外發現5個原baseline漏登的caption重複群，來源頁P20 25/27/30/31/33（Figure18/20/23/24/25）。已另存newly-discovered-baseline.json，不更動原26群修復分母；決策的remaining/affected範圍必須納入。各圖原PDF字流已有2份，舊backend cells放大至3–4份，V4仍2份；全為既有阻擋部分改善，不是新回歸或完整fix。

來源定位：diagnostics/backend-source-spotchecks.json。五個指定spotchecks的原PDF→舊backend cells→V4cells為P20p6 2→4→2、p28 2→4→2、p48 2→4→2，P10p9 2→5→2、p26 1→2→1；p10舊reviewer任務1→1→0。新backend減少重查放大，沒有保證清除全部原隱藏／clip文字。

標題另核：P10p9 4.4與P20p6 3.2的完整標題仍在獨立text段；F03 role降級無新增Q4從屬誤讀。P20 Buffer Initialization仍code內兩份，機器missing屬matching邊界，不是新全文漏抽。

全程零conversion、零模型推論、零API、未下載；舊研究資料唯讀。
