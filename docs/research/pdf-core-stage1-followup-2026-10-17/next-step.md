# B 六次比較後的下一步

2026-10-17。主線維持 Standard＋必要元件 VLM 的配置目標、原品質容忍與延遲／算力取捨。原六次推論與評分封存，最新結果見 [B-results.md](B-results.md)。

[Matt 雙軸腳本 review](../../reviews/pdf-core-b-script-review-2026-10-17/review.md) 的三項評分缺陷已修正：全部 panel 的計數、明示 row-group scope，以及 pair 結構／數值容忍分離。35 個離線測試通過，T01／T02 Markdown 報表已與實際 render 一致；同六筆 saved responses 的[新版評分](B/rescore-v2/evaluation.json)仍是兩頁交付、兩頁未交付。原推論與報告均保留，完整性核對及[修正後複核](../../reviews/pdf-core-b-script-review-2026-10-17/fix-review.md)已另存。可繼續下方的離線方法取捨；本次評分修正沒有啟動新模型比較。

## 立即下一步：表示契約與必要意思的離線審核

**已執行。** [審核與 replay 結果](contract-audit.md)：新方法只增加一條明示 span 內的 exact-empty padding 規則，同六筆回應可接合五個 targets／三頁；T05 typed／Markdown 80／80、7／7 比較、20／20 pairs，T01／T02 無 material 回歸。T04 的 header／category 歸屬仍矛盾，完整 B 未通過，停止本輪 B 的追加模型推論。45 個測試及三頁第二 process 讀回通過，原 B 失敗／成本與所有輸出保留；沒有新 API。下段保留原審核範圍，接續工作改為 A 的 ownership／coverage gate，再到 C。

目標：確認 B 的結構限制是否都是交付必要條件，或部分只是自訂傳輸協定的冗餘。時間上限 60 分鐘，新模型／API 呼叫預算 0。這是一次方法決策，不再排一輪沒有新假說的 prompt／模型重試。

T05 的數值、明示 row_groups 與 header spans 可讀，但 covered 空字串／null、row role、section colspan 未符合本輪表示；這些不能一律等同來源意思遺失。另一方面，仍須實際交付合法 Core、可讀 Markdown 與同版 supplements，不能只憑 raw 80／80 改判通過。T04 的 ragged／錯位表頭及衝突 spans 仍是實質阻擋，299／300 位置診斷不能抵銷。

審核產出只需三項：

1. 必要意思與表示欄位的對照：表頭／列維度／條件／分組／paired values／來源各由何處保存；哪些欄位是必要語意，哪些是重複編碼。
2. 唯一無歧義的機械映射是否存在。只依 payload 已宣告的資訊，使用公開 Core／現有 serializer；不得讀來源答案補格、猜／移欄、猜 spans、修數字或新增 renderer。
3. 去留判定。若有明顯更簡單的方法，另存新方法，先用原六筆 saved responses 及通用合成正負控制驗合法交付、render、reload、來源及非目標回歸；saved replay 僅算離線接合。原輪結果保留失敗。若仍需猜測或案例專用處理，停止 B 的追加推論，保留已成立的元件證據。

新方法只有在必要結構能完整交付、原正例無 material 回歸、負例能拒絕後，才值得另訂一次固定模型比較。若 T04 仍 unresolved，不能把 T05 的格式簡化當成完整 B 放行。

## 接續：回到完整配置的其他阻擋

| 分支 | 最小下一個問題 | 可交付成果 |
|---|---|---|
| A 公式／code | 必要內容由正文／表格／圖片誰負責？跨 owner 的來源片段能否經一個通用公開接點保留順序？ | 自動產生的責任／可達清單與合法回應的交付控制；表格已保存內容不重複送 VLM，混合 owner 未解不能宣稱全含 |
| C 圖片與其他元件 | 實際同版原生 owner 的 image key／supplement 是否成立？圖片 mapping、heading 與四方向責任是否可測？ | 原生同輸入接合、明確座標 mapping、搬移／讀回及剩餘來源覆蓋清單；不把 synthetic 與另一份 native replay 拼成完整驗收 |

先收斂方法與控制，再凍結各分支的實際模型工作／預算。模型選擇維持按元件評估，不限定 Qwen3；公司模型與 GPU／vLLM 的正式品質／效能仍需具名環境驗證。

當每項必含能力都有可交付方法後，才進原第三段：同一配置、fresh Standard 配對基線、完整 WikiSkill 28 頁及具名補充範圍，量測全部成本與實際保存／恢復。仍有 material 缺口就交付具體配置取捨點，不執行已知不完整的付費全量 run。未曝光 holdout 持續封存，固定方法後才用於確認。

表示契約審核及獨立 padding 方法的離線 replay 已完成；A／C 接續工作尚未執行，沒有啟動新推論。
