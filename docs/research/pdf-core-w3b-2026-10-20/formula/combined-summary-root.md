# 逐條公式v1＋v2最終分母對帳

只合併已封存標籤，沒有新增評分。全域compound guard的13個來源候選同時退出E0與E1；286原候選不變，273仍符合自動條件、150可唯一定位、123身分不明。未flag者未全人工認證。

|輸出|可獨立評分|完全一致|接近|錯誤|
|---|---:|---:|---:|---:|
|E0 orig|126|0 (0%)|49 (38.89%)|77 (61.11%)|
|E1 RAW/MAPPED|40|9 (22.5%)|28 (70%)|3 (7.5%)|

E0另24個locator行界不明。E0是攤平字層對TeX文字桶，以上不是數學保義率，也不是RAW Markdown已交付。E1人工40條為10核心改義、22核心保義、8metadata；metadata不冒稱完全忠實，也不是Q31核心阻擋。57實際formula refs中39個有獨立source row分數（共40source行）、7parent行界不明、3compound、8身分不明。未處理E1不算漏句。

## E0 orig按family

|Family|exact|near|error|
|---|---:|---:|---:|
|ACL/EMNLP|0|16|7|
|ACM sigconf|0|0|14|
|CVPR/AAAI|0|1|3|
|ICML|0|8|2|
|NeurIPS/ICLR|0|9|14|
|Pilot-other/unknown|0|8|17|
|Springer LNCS|0|0|1|
|general arXiv|0|5|17|
|general arXiv (article; template uncertain)|0|2|2|

E1 family、10個阻擋的逐案原頁理由見assessment-v2；原W3 50block人工抽查與這40條不同單位、可能重疊，不相加。

同40條E1可評source行的E0 orig文字桶：{"ERROR": 33, "NEAR": 7}。這消除兩版不同子集的分母差異，仍不能消除glyph字流與TeX結構的表示差異。
