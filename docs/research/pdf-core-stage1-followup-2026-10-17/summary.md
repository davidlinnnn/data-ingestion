# PDF core 主線接手：表格離線補齊

日期：2026-10-17。主線直接執行本輪修正、驗收與階段判定。依據 [第一段複核](../../reviews/pdf-core-stage1-main-review-2026-10-17.md) 補齊 B；A 的完整方法及第三段完整配置仍未放行。

**B 單頁表格的離線 gate 已補齊，後續六次真實 API 比較亦已完成。最新結論見 [B 固定六次比較結果](B-results.md)：精簡協定降低本輪用量，但 T04／T05 結構／交付仍未通過。** 以下保留離線準備紀錄，不能當作最新模型成績。

後續評分器 review 的三項缺陷已修正，35 個測試與同六筆保存回應的離線重評通過；原候選與報告未變。最新評分／完整性紀錄在 `B/rescore-v2/`，T01／T02 通過、T04／T05 未交付的結論不變。

再依 [表示契約審核](contract-audit.md)完成一個獨立 padding 方法的離線 replay：T05 也可交付，T01／T02 保持，T04 仍有表頭矛盾。45 個控制測試通過；原 v1 結果與成本不改。停止本輪 B 追加推論，下一步回到 A 的 ownership／coverage gate 及 C 的同版接合；完整配置仍未放行。

| 項目 | 結果 |
|---|---|
| Section 範圍修正 | 要求 section cell 的 rowspan 不超出 row_group；反例拒絕，合法跨列情況仍可映射、保存及讀回 |
| 表示與保存控制 | 26 項通過，31 個負例拒絕；literal、表頭、spans、caption、非目標內容及來源的原有控制保留 |
| 原生 target 接合 | 原四頁全部六個 target 使用同一個明示 MOCK 完成接合與讀回，不讀來源答案，不代表模型準度 |
| 執行器 | 22 個 mock HTTP 測試通過；獨立審查者另重跑並核對主要修正 |
| 預算與停止 | Input reservation、completion、transport、deadline、tree RSS／available 均已登錄；usage 不明或超額停止後續請求 |
| 原輪證據 | 142 個封存產物重新 hash 比對，無變動；沒有改 production、SDK 或歷史 helper |

## 固定六次比較

沿用原 StandardPdfPipeline 的 cached S0、原四頁六張 native table body crop、144 DPI、不補邊／縮放。同模型 `gpt-6-luna`、`reasoning_effort=low`、image detail high、store false；只變 compact 協定及必要 prompt。Cached upstream 不能計作本輪新 Standard 推論。

| 研究界線 | 凍結值 |
|---|---|
| 呼叫／並行／重試 | 6／1／0；失敗與 smoke 均佔次數，不補跑 |
| 每筆 completion | 32,768 tokens，已包含 reasoning；總額 196,608 |
| Input reservation | Prompt／schema UTF8 bytes + 8,192 圖像估計 + 1,024 framing；六筆合計 81,560 |
| Parser／transport | Content 65,536 bytes；HTTP envelope 524,288 bytes |
| 時間 | 每 request 180 秒，整輪 30 分鐘；週期 guard 涵蓋 HTTP 等待與頁面 assembly |
| 記憶體 | Tree RSS 12 GiB、available 低於 8 GiB 停止；啟動至少 10 GiB available |

8192 是研究用圖像 reservation。官方影像指南未明列 Luna 的 multiplier，因此不宣稱精確計費。每次發送前檢查累計實際 usage 加下一筆保留量；收到回應後若超出估計或總額，記錄 overrun 並停止後續。缺失／非法 usage 不填零，分類為未知並停止。

合成預檢為來源無關的 64×16 單 panel、32×16 雙 panel：compact 分別 10,199／10,957 bytes，pretty 31,685／34,536 bytes。Parser／transport 可容納這些樣本與 JSON escape；此預檢不代表任意合法表格都保證放得進 token cap。截斷、超界、未知來源值及結構失敗均保留診斷，不截短資料來換成功。

六筆固定完成後才評讀品質。Schema／內容失敗繼續剩餘已登錄 jobs；transport、provider envelope、usage、環境或資源失敗停止整輪。所有同頁必要 target 收齊後，從 immutable baseline 一次映射；缺一張便不產生該頁的合格文件。保留原 470 數值／23 比較分母，兩張 collateral 另報，T03 跨頁不納入本次單頁比較。

## 可觀測結果與限制

Runner 分開保存 `http_response_seconds`、包含 parse／驗證的每 job `seconds`，以及每頁 mapping、serialize／reload／save、assembly 時間；server queue／GPU compute 仍未知。週期 guard 保留 resource samples；回應中途停止則保存有界 prefix。沒有把研究 timeout 當產品 SLO。

Model／Chat Completions 能力核對來自 [OpenAI 模型文件](https://developers.openai.com/api/docs/models/gpt-6-luna)、[completion cap 定義](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) 與 [影像指南](https://developers.openai.com/api/docs/guides/images-vision)。帳號存取權與實際 provider 行為尚待真實請求驗證。

主要入口：`B/live-registration.json`、`B/runner.py`、`B/runner-test-results.json`、`B/runner-test-log.txt`。`B/live-registration-before-timing.json` 保留 live 前補計時欄位之前的登錄；新增計時欄位後已重跑控制並重新封存，兩版均未送出 API。

主線允許進入這六次獨立單頁研究比較；這不放行 A 完整分支或第三段。執行憑證只從已配置環境讀取，不放在命令參數、產物或日誌。執行時使用既有 pinned Python：

```sh
rtk /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-stage1-followup-2026-10-17/B/runner.py --verify
rtk /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-stage1-followup-2026-10-17/B/runner.py --live
```

本輪 API／模型載入／holdout 讀取均為零。A 的必要內容責任與順序接合、C 的座標 mapping 與其他完整功能仍待收斂；未宣稱新模型準度、成本、GPU 效能、高頻吞吐或完整配置通過。
