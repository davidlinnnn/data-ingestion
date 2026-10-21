# WikiSkill Figure 1：來源評讀契約

2026-10-18。僅供 evaluator；不是模型輸入、圖號 routing 或新準度成績。完整固定參照見 [JSON](evaluator-wikiskill-figure1-contract.json)。先看原頁，再看已生成的 native crop；沒有借用論文 Table 1 的值。

這是四條 series、四個類別的 line chart，共 16 個未印值 marker。所有數值都是幾何估值，不能標為 printed 或 exact。以可見 75%／30% 刻度間的 253 px 校準，保留人工 marker 中心 ±2 px 的標註不確定範圍，沿用 2% 正規化幾何誤差；不猜未標示的完整 axis domain 或零點。缺少／不可讀／錯綁點保留在 16 點分母。

WikiSkill 在四個類別皆最高、No skill 皆最低，各 series 向右上升。最後一組 EvoSkill／SkillOpt 接近重疊，不強制低於來源可辨解析度的排序。WikiSkill 相對 No skill 的差距並非四組嚴格遞增；不能把 source caption 的概括說法擴張成圖上不成立的數值主張。X 軸是模型類別，不從間距或名稱推測參數量。

OCR 須核對完整 legend、四個模型類別、Accuracy (%) 與四個 tick 字串；PDF text 與本清單都只是參照，不是 OCR 產物。原 Figure 1 caption 保留為來源內容，生成解釋仍透過同版 image key 提供。最後的類別 label 接近 native crop 右緣，實際省略須另記，不為本圖添加 padding／修補規則。

尚未評分任何新模型輸出。所有 references 與判定須查實際保存／reload 的 supplement、image key 及 primary Markdown，不能只看 provider 宣告。
