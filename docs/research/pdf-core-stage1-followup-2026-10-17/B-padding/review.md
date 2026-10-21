# B-padding 唯讀複核

2026-10-17。**可接受；未發現阻擋問題。證據足以停止目前 B 的追加推論，轉回 next-step.md 的 A／C 離線責任與接合工作。** 這不放行完整 B、跨頁表或第三段配置。

核對範圍為 `method.py`、`verify.py`、`test_method.py`、`results.json` 與兩份 contract audit。方法／verifier hashes 與結果登錄相符（`9344f095…11cd`、`f1f9128e…73d3`）；10 項方法測試通過。未執行會寫封存的 main。

- **規則有界，沒有修值或猜 layout。** method.py:33 (`docs/research/pdf-core-stage1-followup-2026-10-17/B-padding/method.py:33`)只將已宣告 span 的非 anchor exact-empty 槽轉成 null，再經原 strict 檢查；非 covered 空白、字元、數值、spans、roles、group endpoints 均保留。空白字元、零、dash、unknown、covered role、重疊／越界與 ragged 仍拒絕。原 transport 另存於 bindings，輸入不變；這是新表示規則，不是原答案的來源修復。
- **原有效例與交付吻合。** 獨立重讀六筆 raw：四個原合法 targets 完全不變，T05 僅 `(1,0)` 一槽改變，T04 仍拒絕。記憶體重 map 三頁，與保存的 document／bindings／Markdown 完全一致；重新 typed／真正 rendered 評分亦與 results 相同：T01 6/6、T02 84/84、T05 80/80，T05 比較 7/7、pair structure 20/20。非目標、來源、reload 控制成立，未新增數值零錯門檻。
- **Caption 更正沒有遮蔽限制。** verify.py:121 (`docs/research/pdf-core-stage1-followup-2026-10-17/B-padding/verify.py:121`)核對 native caption 原文前後出現次數，gold literal 另列診斷。T02 差異確為既有 `B_m → B m` 與 `B` 標點空白；native captions 均 1→1，gold literal=0、`manual_source_review_required=true` 仍公開，失敗 precheck 亦保留。這證明新接合未惡化 caption，不證明 baseline 已完整保留來源排版／語意。

T04 audit 的 33 列中一列 14 格、其餘 13 格，及四個未被 span 解釋的 null，均獨立重現。Category／metric 宣告衝突不能由 exact-empty padding 消除；299/300 位置診斷不足以補足表頭歸屬。因此 5/6 targets、3/4 pages 只支持有界 saved-response 接合，維持 `full_B_qualified=false` 與停止本輪推論合理。

原 producer／協定 hashes、T04/T05 raw hashes 與 frozen verify 不變。未改原檔或封存，未呼叫模型／API、安裝或讀取 holdout；未重新逐字視覺標註來源。
