# 分析器修正記錄（source gold未改）

- v1-native：第一輪候選，未驗出口；保留原檔。
- v2-native：共同caption多native union、source/native figure/table身份衝突守門、兩來源row壓成一native row不得當唯一row；保留原檔。
- v3-rendered：加入RAW片段實際保存存在性與MAPPED單次cell交付；此版仍未實際解讀多行Markdown header，保留原檔。
- v4：依獨立QA，短header與packed header全局消歧；優先完整header相等避免MR/MRPC誤碰；packed row-label數值不當必然漏；source physical extent未知不判absent為漏；真正Markdown render後父header不在thead則RAW UNKNOWN。來源cells/points/Q13/定位完全不動。

所有source freeze hashes驗證通過。固定9個QA樣本不因修分析器替換；UNKNOWN→PASS與FAIL→UNKNOWN不冒充已確認阻擋修好。

- v4另將同數值但unit suffix／鄰字不明（例如53819.6後換行M、12.5後s)）保留UNKNOWN，不宣稱數值變更；原生數字解析接受.5=0.5及跨行unit空白。來源gold不變。
