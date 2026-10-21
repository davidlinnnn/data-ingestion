# CPU supervisor 退出競態修正

2026-10-18。後續 CPU supervisor 使用 cpu_baseline_v2.py (`C/cpu_baseline_v2.py`)。封存的 `cpu_baseline.py`、44 頁轉換結果及 `parent_harness_error` 紀錄不回寫；新版沿用其模型處理函式、設定、資源界線與既有 attempt 防重跑機制。

根因是 `poll()`／程序列舉並不能保證程序在下一個 RSS 讀取時仍存在。新版只略過已消失／zombie 的程序，仍計入存活程序的 RSS；AccessDenied 等監控錯誤繼續回報失敗。最後狀態依 worker 的實際 exit code 判定，非零退出不改判成功。Budget stop 後若程序恰於 `killpg()` 前退出，僅容忍 ProcessLookupError，仍 wait/reap 並保存停止紀錄。

回歸測試 (`C/test_cpu_supervisor_v2.py`)直接執行 supervisor parent：舊程式可穩定重現四項失敗；新版八項測試通過，含兩個真實短命 worker（exit 0／7），沒有模型載入。也驗證失敗權限不被忽略、記憶體預算仍停止，以及既有 attempt 不重啟。為避免改寫封存來源，原 parent 沒有可注入的監控接點，故新版保留一份小型 supervisor loop；模型處理本體不複製。

```sh
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B -m unittest discover -s docs/research/pdf-core-eval-interfaces-2026-10-18/C -p test_cpu_supervisor_v2.py -v
```

原 C 的 159 個來源階段檔案與 61 個引用 hash 檢查仍通過。未重跑 PDF／VLM／API，沒有更新既有來源品質判定；完整 PDF 工作負載的監督器重跑不在本次驗證範圍。
