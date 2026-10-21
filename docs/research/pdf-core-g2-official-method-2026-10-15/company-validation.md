# 公司部署驗證後續清單：當前 G2 使用 OpenAI 暫代

2026-10-15。使用者補充「把openai當作qwen3vl」：**當前 G2 方法比較繼續以 OpenAI 作為暫用 Qwen3-VL proxy，不等待公司 model ID、endpoint 或 GPU 資訊。** 實際推論身分仍記錄為 `gpt-6-luna`，不能改名為 Qwen3，也不能據此宣稱公司模型的品質／latency／GPU 容量已驗證。本文件降為日後實際公司部署的資訊清單，不是當前執行前置條件。

官方 remote DocTags 候選已完成8次 HTTP200，但有原稿保真及超出0–500規格的模型座標缺陷；傳輸接通不代表可採用。主流程正繼續最後一組有界方法比較，僅檢驗 `reasoning_effort=low→medium` 假設，其餘依登記固定，不加入個案內容修補。公司 Qwen3-VL 或其他適用地端開源模型留待實際部署另驗。

## 日後實際公司部署驗證時再提供

- **服務實際接受的完整 model ID**；若知道，附 underlying checkpoint／revision。不要只填 Qwen3 family，也不預設大小、Instruct／Thinking 或量化。
- **完整 Chat Completions endpoint**，以及這台筆電能否存取；若只能公司機器存取，可在公司環境執行。
- 認證方式與**已設定秘密的環境變數名稱**。不要傳金鑰值、含秘密的 URL 或授權標頭。

以上資訊目前不需補充即可繼續 G2 proxy 比較。日後 GPU 型號／張數／每卡顯存、dtype／量化、vLLM 版本及共享容量可一起補；實際公司容量／GPU 加速結論才需要完整硬體資訊。新高頻業務目標留待 #54／G4，不新增為當前品質測試的前置阻擋。屆時可填 資訊模板 (`company-request.template.json`) 的 null 欄位；它是資訊表，**不是可直接執行的設定檔**。

## 日後實際公司模型的最小驗證流程

1. **先按精確模型核對官方輸入／prompt／輸出 parser。** OpenAI-compatible 只表示傳輸介面相近，不表示 DocTags／Markdown 相容或品質達標。Docling2.102 的 `qwen` preset 實際對應 Qwen2.5-VL-3B-Instruct＋Markdown，不能當 Qwen3 已驗支援；也不直接複製本輪 GPT 的 DocTags grammar prompt。先以 mock transport 捕捉真正 request，核對參數及固定回應的 inline LaTeX、code 字面值／縮排、來源頁／bbox／圖片表示與空值／截斷／錯誤處置。若官方 parser 已丟失必要表示，先記 no-go，不加大型後處理橋接。[既有離線預檢](preflight/results.md)
2. **固定下一組方法後，只作8頁一次比較。** 模板列本輪實際 API 收到的8張 `input.png`、SHA及原 PDF／物理頁；沿用 41個來源工作契約 (`review/contract.json`)、四個既有正例，以及 既有對照索引 (`review/prior-review-reference.json`)。這些PNG與契約中的review raster可能尺度不同，應驗真正送出的bytes；不把答案、評分框或契約正文放進模型請求。若從原PDF重render，先驗輸入hash或登記輸入轉換，不能默認相同。
3. **不重跑挑成功、不修 prime／識別字／code 字面值。** 以8頁中第一頁作已登記的一次實際介面檢查；不可用就停止並保留失敗／缺失，能用才完成其餘7頁。依原41來源分母報 raw內容保真、官方document／Markdown交付、正例退化、未嘗試／失敗及旁支缺陷；固定來源外的整頁內容不另膨脹成功分母。
4. **依結果保留或停止。** 有品質可行證據才鎖單一 challenger，獨立來源標註後進一次 paired holdout；本交接不開啟holdout。Client RTT／tokens可觀察，但不代替端到端高頻SLO或GPU capacity。當前候選配置上限仍是既定三組，最後一組由主流程依 OpenAI proxy 的單一假設登記；此公司交接不另占名額，也不自行增加第四組或重設預算。

## 若只能在公司機器執行

可以沿用這個 repo 的來源契約、原稿／8張PNG和研究runner中的傳輸捕捉／保存做法，但**目前 `run.py` 不能直接拿去測公司模型**：它硬編 GPT endpoint、model、DocTags prompt 與 GPT 參數，且禁止覆寫原輸出。取得公司資訊後，需要最小適配認證環境變數、模型專屬設定／官方 parser、精確 package lock及新的執行目錄，重新凍結身份後才跑；此交接沒有提供假裝可用的 CLI。

公司 checkout 還須帶到模板列出的開發證據與必要原稿：單純 `git clone` 不保證取得尚未commit或被ignore的 PDF／PNG。依模板hash核對，勿一起帶秘密或六份未啟用holdout。CPU worker的render／parser與遠端VLM GPU分別記錄，不能把遠端HTTP成功算作已驗GPU加速。

本次僅更新此交接與模板的執行定位，沒有另作API、模型推論、權重下載或正式程式修改。當前G2依授權以OpenAI proxy繼續；實際公司模型品質與完整Canonical交付仍未知，proxy結果不移轉為Qwen3部署證明。
