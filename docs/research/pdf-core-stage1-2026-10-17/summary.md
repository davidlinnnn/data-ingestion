# PDF core 第一段離線執行結果

日期：2026-10-17（Asia/Taipei）。**本次第一段A／B／C已完成有界離線執行；完整方法未通過，不放行第二／三段推論。** 保留單頁表格及圖片補充資料的機械接合成果；沒有用其他元件成功抵銷必要 coverage缺口。

依據計畫 SHA256：`518c410a3c8349cfb8f2300b19a7c097ab0a49a53a705518aa8474ecf670af65`。較新人類授權已由主線 `確認 #84 第一版 PDF core 功能` 的原始 userMessage 核實，ID為 `01a14878-42af-7e31-81ac-c76a75127dea`。本聊天承接實際驗證，主線保留後續階段決策。

## 分支去留

| 分支 | 狀態 | 已實證 | 阻擋／最小後續決策 |
|---|---|---|---|
| A 公式／code | **fail：完整來源 gate** | 8頁原稿獨立 census、固定版 cached S0 producer inventory；7合成正例、25新負例、完整23歷史負例；79個可達原生 owner 的 mock交付；4個歷史未準備display formula可交付 | 來源44個分組 spans中33完整 eligible、7表格內未發現、1 caption未支援、3圖內／混合owner部分 eligible；混合正文／Algorithm標題仍缺通用 ownership與順序方法。先解這個涵蓋／交付問題，再談新推論 |
| B 精簡表格 | **partial**；單頁 pass、跨頁 fail | 25項機械控制、30負例；原4頁全部6個native targets同頁一次mapping；5組第二process讀回；同版 rowgroup／panel scopes補充保存 | 公開Core能存一張表的多頁來源，現有mapper實際拒絕；不能由此聲稱Core不支援。六個單頁工作可保留，但output／input／transport caps、provider能力及live runner未就緒，不可直接呼叫 |
| C 圖片及其他接合 | **partial**；機械接合 pass | 6 saved API＋1 saved OCR＋2 mock、13 chart點原樣保存、10負例；合成owners及真實同版NCCU 1圖／53children分開控制，均搬移後第二process讀回 | 完整圖片／必要工作census、heading／title／parent及四方向接合／逆映射未完成；圖片回應接合成功不能代替其他必含功能 |

A的44是來源分組 spans，79是原生可達 owner 候選，兩者均不是已凍結calls。原41 units與新census、單頁470數值／23比較與兩張collateral、T03 264／7均保持分開。來源無法對應的必要內容沒有移出分母。

保護正例／cross-page joins由隔離evaluator另作7個歷史payload的有界運輸控制，涵蓋4正例／4joins；三個join payload原有內部斷段原樣保留，因此沒有宣布完整來源／段落回歸通過。普通陰性27個中24個eligible，3個caption邊界仍不支援。

## 實際範圍、方法與成本

固定SDK實測：Docling-slim2.132.0／Core2.99.0／Parse7.22.3；只使用公開Core型別、JSON reload及serializer extension。Discovery／ownership、精簡table協定、image keys／supplements與控制程式是自訂部分，沒有當成官方內建能力。舊helper原樣重用，不修改SDK、不加另一套renderer或graph repair。

Producer先固定inventory再交隔離來源evaluator核對。Evaluator原稿答案、人工bbox／target清單未餵入producer；root只接收缺口類型／數量，未據此修改producer或補jobs。完整答案與對照留在 `A-evaluator/`，producer及交接驗證程式不讀它們。

| 分支 | started_at（UTC） | 硬deadline（UTC） | 實際分支耗時 |
|---|---|---|---|
| A | 06:10:12.428499 | 08:10:12.428499 | 423.41秒 |
| B | 06:10:35.659996 | 07:40:35.659996 | 274.71秒 |
| C | 06:10:46.740681 | 07:10:46.740681 | 233.07秒 |

全部於硬期限前停止；分支並行，耗時不能相加當整體牆鐘時間。包含來源／SDK調查、實作、離線修正及驗控制，不是推論延遲或產品SLO。完成後僅整理交接與完整性核對，沒有追加方法探索。

新增遠端calls＝0、本地模型載入／推論＝0、API＝0、安裝／下載＝0、holdout讀取＝0。未找憑證，Paddle保持暫停；沒有準度、tokens或API成本新數據。Saved API usage／回應與mock分開保存，沒有將其冒充新模型成績。

## 可執行結論

1. **不放行A的完整公式／code推論，也不放行第三段完整配置。** 目前失敗在通用發現／ownership／順序及跨頁mapper，更多相同模型呼叫無法先補齊這些接合缺口。
2. **保留B單頁協定與C圖片sidecar成果。** B六個具名工作已準備；主線可另判斷是否值得完成有限payload、token保留量／總額、transport上限、provider能力及runner登錄後，進行原定六次有界比較。本輪沒有替主線放行。
3. **不編造N_CF／N_3及token caps。** `registration.json`逐欄保存null與原因。固定完整方法與必要工作清單未成立前，不以79候選、41units或六個table工作代替全配置預算。

## 交接入口

- `registration.json`：三分支時鐘、狀態、範圍、下一段未就緒預算。
- `A/summary.md`、`A/results.json`、`A/inventory.json`：producer、離線controls與停止證據；`A/ordering-counterexample.json`是最小排序反例。
- `A-evaluator/summary.md`、`source-registration.json`、`source-census.freeze.json`、`producer-coverage-comparison.json`、`saved-payload-replay.json`：隔離來源證據，不作producer輸入。
- `B/summary.md`、`B/results.json`、`B/next-stage-jobs.json`、`B/multipage-result.json`：單頁、來源mock、六工作及跨頁限制。
- `C/summary.md`、`C/results.json`：保存回應、image-key、chart／OCR狀態及F01–F22責任／第三段來源／剩餘缺口。
- `verify_handoff.py`、`handoff-verification.json`、`artifact-hashes.json`：交接內部一致性與原SDK／歷史引用hash核對；verification pass不等於完整方法pass。

本次只在指定新研究目錄新增檔案；原計畫／README、歷史oracle／產物／helper、production及SDK保持只讀，未commit／push／發佈GitHub。

未測新模型準度、實際成本、全量文件、fresh／restored worker或production負載；本輪證據只支持有界機械接合與明確停止結論。
