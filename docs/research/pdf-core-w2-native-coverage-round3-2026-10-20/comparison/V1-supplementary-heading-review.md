# V1 完整輸出差異補充核對

實際將三張原 PDF 頁以 PDFium scale 1.5 在記憶體 render 並看圖，交叉核對完整 Markdown diff／原生 items。Q4 收緊後結果是 **1 FIX、1 NEUTRAL、1 REGRESSION**，不是「v3 anchor 候選零增減就代表無旁側影響」。未改凍結 oracle 或原 875 候選。

| 文號／physical page | 裁定 | 原頁與前後差異 |
|---|---|---|
| P02 p1 | FIX | Salaheddin Alzubi 是獨立上排作者，Noah Provenzano 在下一排左側。Baseline 將 Noah 先列，V1 恢復 Salaheddin → Noah；名字未漏，但 first-author attribution 次序被修正。 |
| P13 p19 | NEUTRAL；只改善版面讀取貼近度 | 原頁上半 Alg1 左／Alg2 右，下面共享 Figure8 caption，再往下才是 B case study。V1 將完整 Alg2 float 移回 caption／B 之前。Baseline 雖較遠，但 Alg2 仍有獨立 Training(Part2) 標題、完整 code，caption 仍描述兩部；未證條件／對象被改變或文字混入對話，因此不宣稱 Q4 修好。 |
| P18 p18 | REGRESSION；F02 確認阻擋 | 原頁 Table17 城市／球面題含題幹、公式、for i=1,2,3、Given A/B coordinates，之後才是 Tables18–20。V1 將 Table17 尾段先放到頁首，再列18–20，才回到17 caption／題幹／公式，切斷條件與對象的歸屬。未證新漏／重；既有公式未解碼另列。 |

凍結 anchors 未捕捉的原因不同：P02 作者不屬正文 prose；P13 算法環境被排除，B prose 整塊移動仍保有正文 anchors 相對順序；P18 表格／公式環境被排除，因此框內問題的條件接合沒有 oracle pair 可評。

P02 baseline 明確改變 first-author 署名順位，標 q4_blocking_baseline=true／F02=true，另立 incidental outside-oracle finding，供主線更新 paper 分類；不混入原 875 候選數。P13 只有允許的完整 float 位置差，不新增 baseline 阻擋；P18 的新增 F02 阻擋另報，不能用凍結候選零增減抹除。

唯一官方變更是 use_reading_order_separators=False，且保存的原生 traversal 確有改序。上述版面原因是根據原頁的幾何／語意群組推論，未另外重播 predictor／merge 子程序，因此不將精確內部 subroutine 宣告為已證實。逐案證據 (`V1-supplementary-heading-review.json`)
