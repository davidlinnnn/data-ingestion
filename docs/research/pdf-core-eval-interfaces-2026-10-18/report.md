# 分層評估、版本鎖與 B／C 實測接點

2026-10-18（台北）。本輪完成評估方法與來源輸入的具體化；不將離線控制、來源盤點或 CPU conversion 成功當作新 VLM 準度。詳細入口：[外部評估契約](evaluation/protocol.md)、[B 接口與評分](B/report.md)、[C 接點與來源核對](C/report.md)。

## 外部評估已固定

- 固定真實 **60 頁**，以內容類型分層，再按語言／文件類型輪流取樣及固定 seed 排序：table math 10、merged table 10、其他表格 8、figure＋caption 8、display formula 8、degraded scan 8、multicolumn 4、ordinary text control 4。五種語言皆有；這不是無公式負樣本或全量榜單。
- Official code commit 為 `f133a71e9e91c3621c7ce8994200a7b394a06eb3`，dataset revision 為 `aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec`。單一 annotation 檔 42,208,096 bytes 的實測 SHA256 與官方 LFS metadata 一致；GT 留在 private evaluator custody，未進 repo，未下載 page images／PDF。
- Manifest (`evaluation/sample-manifest.json`)在候選預測前固定，不看結果換頁。60 頁未能驗證 source-family 獨立性；它是 targeted external regression，不能稱公司獨立盲測。缺少的三種文件類型與 three-column layout 已明列，不能外推全部文件分布。
- 評分契約 (`evaluation/scoring.json`)固定 text Edit Distance、table TEDS／TEDS-S、formula CDM／Edit Distance、reading order、matching／fallback、failure 分母，以及 B／C 補充語意 gate。TEDS 95 不等於數值錯誤 5%，Overall 不抵銷必含失敗。
- Ingest／推論成本與 matching／TEDS／CDM 評分成本分列。Image／raster 與原生文字 PDF 分軌。官方 evaluator runtime／page input hashes 仍須在真正執行前補齊；本輪未安裝或執行官方 evaluator。

## B 已具備固定比較入口

七份請求 (`B/requests`)的 exact bytes、prompt、strict schema、來源 SHA、model 設定與資源上限已固定。重用既有公開 Core mapper、caption ownership 與 Markdown serializer，沒有新 renderer、SDK 修改或來源答案修補。整頁所有必要 targets 收齊才映射；baseline 在 assembly 前再核 SHA。

上限為 **7 次、並行 1、零重試**，每次 180 秒／32,768 completion tokens，總 1,800 秒／229,376 completion tokens；input reservation 106,634。這些是實驗資源上限，不是花費預測或正式 SLO。`--dry-run` 不讀 credential、不連網，root 獨立重跑通過；13 個新控制也通過。

固定手動評分 (`B/scoring-manifest.json`)承接新 normalized representation，保留原 **470 數值／23 比較**，兩張 collateral、Table 7 四組 math 與 T03 的 **264／7＋3 missing marks** 分開。全部新輸出須核對 actual Core／rendered Markdown 與來源，不能把 provider IDs 當 GT；舊 grid-specific grader 不會被錯套或修改。

真 T03 已用本輪 C 的同版 Standard 輸出確認：三頁仍為三個獨立 table items，沒有共同 logical owner。分組、條件繼承與跨頁來源接合仍未解，沒有用七次單頁比較掩蓋這項必要功能。

## C 的來源與實際 native 輸入

原定 **55 頁／13 檔案**均有同版 Standard 輸出：重用 11 頁已核對 cache，缺少的 44 頁以同一 CPU S0 設定各轉換一次。Pipeline 為 `StandardPdfPipeline`，Heron layout、RapidOCR／ONNX、TableFormer accurate＋cell matching，CPU／4 threads／batch 1／images scale 2；C 的分類與 VLM enrichment 尚未啟用。

12 個新範圍的 conversion 都成功，合計約 80.82 秒；這是範圍 conversion 耗時，非完整 ingest SLO。Supervisor 約 84.61 秒、sampled process-tree RSS 約 6.62 GB，但結束時有監控 race，保留 `parent_harness_error`，不冒稱乾淨 watchdog pass。沒有為此重跑已完成的 44 頁。

Producer 先從公開 native 結構生成 inventory、crop 與同版 image key，之後 evaluator 才查 source census；人工圖號與 source locators 不產生 jobs。實際有 **29 個 native crops**，準備 29 個 local OCR tasks、58 個 description／chart-assessment tasks。這是此 component 候選的工作量，並非 19 個 logical source groups、完整 `N₃` 或建議 production 成本。

19 組來源皆有 owner 對應，但 owner 存在不足以通過：SEAL Figure 1 的 crop 缺整行內容；ReasoningBank Figure 5 的原 caption 破碎、重複且混入鄰文。這些缺口須保留為來源交付失敗，不能用生成描述冒充原 caption，亦沒有添加逐圖裁切／補字規則。

本輪補齊 WikiSkill Figure 1 的 16 個來源估值與必要意義，以及 Memory-R1 bar boundaries／continuous curves 的有限來源契約。估值、printed 與 unreadable 分清；不從旁邊表格借數字、不要求恢復圖上不可見的 raw data，scatter 不新增全點數值門檻。這些只供 evaluator，不證模型已正確重建。

有限參照不強迫模型使用同一種資料表示：可接受足夠細的有名 series／polyline，或明確標示基線與增量、可無歧義還原彩色上邊界的等義表示。不能把增量誤稱獨立總分，也不能把多個累積邊界再相加。表示轉換只供 evaluator 對照，不修改 producer 結果或虛構原始實驗值。

## C 的執行預算已由 client 強制檢查

來源子階段的 [C 報告](C/report.md)及 `requests.json` 保留當時「只有 envelope 檢查、transport 待驗」的封存狀態；後續獨立的 runner (`C/runner.py`)與 驗證 (`C/runner-verification.json`)補齊 HTTP streaming client，沒有回寫該來源快照。

Client 會在解碼前限制 response bytes，強制每次／總 wall-clock、own-process RSS、逐次與累計 token reservation／actual usage、request hash／crop hash，並保存 raw provider 與同版 image-key receipt。Usage 不明、超額或 timeout 停止後續呼叫；合法 transport 產物仍明示 `semantic_acceptance=false`，不改原始 Markdown。所有 source gates 先於 credential 與 client 建立。

Root 獨立重跑 dry-run，核對 58 個實際請求；9 個 MockTransport 測試通過，涵蓋預算、截斷、錯誤 envelope、實際 wall timer、來源變動、secret redaction 與 source Markdown 保護。這證明 client 控制可運作，沒有證明遠端存取或新模型準度。

**C 的完整執行仍未放行。** 已知來源缺口和部分 screenshot／timeline 全圖 OCR 評讀契約尚未完成；`--live` 在讀金鑰、建立 client 或建立 run 目錄前即拒絕。這是已可運作的停止機制，不是用 synthetic payload 將品質 gate 改為通過。

## 執行界線

Runtime lock (`runtime-lock.json`)保存 Python 3.12.13、80 個 package versions 與 8 個 pipeline／Core／serializer source hashes；C 另保存實際 active model assets 與設定。這不是完整 wheel／container lock；remote service alias 也不是 immutable weights。

本輪沒有新遠端模型／VLM 呼叫、沒有讀 credential、沒有開封既有六份 holdout、沒有 GitHub 或 production 修改。A 的 mapper／頁級 fallback 擴張維持暫停。B 的 transport-ready、固定 scoring method、C 的 native input／接收端檢查，以及完整 Processing Profile 的品質合格是不同門檻；已知必要缺口仍阻擋完整驗收。
