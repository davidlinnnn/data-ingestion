# 完整 native table crops：品質與成本比較

2026-10-17。已完成原四頁、全部6個 native table targets、一次配置各一次 API 呼叫。**不採用目前的 crop＋完整 cell JSON 配置。** 大表的數值讀取大幅改善，但輸出列欄座標重疊，普通表也退化；本輪總請求時間與輸出 tokens 均增加。保留 source caption ownership 政策及公開 Core 接點，停止這個 producer 配置的追加重試／逐題修補。

這是 [平衡配置研究](pdf-core-balanced-config-2026-10-17.md)的一個 component 比較；主流程仍是 StandardPdfPipeline，沒有讓整份 PDF 改跑 VlmPipeline。四頁皆已曝光 DEV，並非 holdout 或正式高頻負載測試。

## 同一組來源的結果

| 案例 | 數值／必要關係 | 表示與實際交付 | 判斷 |
|---|---|---|---|
| T01 Memory-R1 普通表 | 6個數字字串全部出現；依回應座標僅2/6可唯一綁定，1/3比較可安全成立 | 實際4欄卻宣告3欄，B1與J共用欄位，headers及兩列數值重疊 | 普通表回歸，整頁未接受；不是6個數字皆讀錯 |
| T02 SkillOpt 六 panels | 82/84 exact bindings，2.38%數值錯誤；8/8關鍵大小／相等關係保留，panel／metric headers 保留 | 主表 schema 通過；同頁 Table3 將 uncertainties 放在 root，違反凍結 schema，整頁未交付 | 主表數值容差與比較方向符合；完整頁面未接受 |
| T04 paper09 Table6 | 295/300 raw數值正確，0missing／0extras，錯誤率1.67%；按 raw 標籤／列範圍可核5/5算術比較 | 30行 model variant 和 method 位於同一欄，30個重疊、2 gaps、12 out-of-bounds；Table7 也有 header／schema缺陷 | 讀值改善但不能形成合法完整 table；無 accepted typed／Markdown |
| T05 WikiSkill Table4 | Typed及實際渲染各80/80、7/7比較、20/20成對 physical cells | headers／spans／rowgroups、caption／外部條件、非目標正文與來源保留，caption一次 | 本頁通過 |

固定分母仍是470數值／23比較，按每張 logical table 判斷，不以成功頁平均掉失敗。T04 的295/300是 raw內容診斷，不是295個已成功交付的 canonical bindings。原始 Model／variant／method labels 可辨識不代表它們在有效 grid 中有各自欄位。

T02 兩個數值錯誤是 LiveMath 的61.3分別讀成63.1及63.3，仍計入2/84，沒有替換來源。舊 helper 額外要求 critical endpoints 完全忠於來源，因此報7/8；但使用者確認的是≤5%數值錯誤、必要歸屬正確及關鍵比較成立。本次8/8大小／相等關係均成立，不能稱「一個比較反轉」，也不把額外 exact-endpoint 檢查當產品門檻。若未來用途要求精確差值／比率，應事先將該主張登錄為 critical。本次保留舊 helper 輸出並另列產品判準解讀，沒有重寫歷史分數。

T05 的 stock Markdown 將 row-section label 平鋪重複到7欄，但群組scope及 typed span清楚，評為可接受顯示差異，沒有追加 formatter repair。Caption 修復來自先通過的 [ownership 政策](pdf-core-caption-ownership-2026-10-17/report.md)，其舊回應離線重播已能修復，不能歸因於裁圖。

T04 同頁 Table7 附帶工作經來源高解析圖複核，raw90/90數值可讀；仍有 header缺 end_col_offset_idx、過長row span與錯層 uncertainties。這90點不加進470分母，也不讓其數字正確抵銷結構失敗。T02附帶 Table3 的 schema失敗是欄位位置問題，不宣稱它有數值遺漏或判定模型不會讀該表。

逐項資料：T01/T02 (`pdf-core-table-crops-2026-10-17/quality-small.json`)、T04 (`pdf-core-table-crops-2026-10-17/evaluation-t04.json`)、T05 (`pdf-core-table-crops-2026-10-17/t05-evaluation.json`)、六項協定診斷 (`pdf-core-table-crops-2026-10-17/validation-diagnostics.json`)、[獨立交付審查](pdf-core-table-crops-2026-10-17/delivery-review.md)。

## 成本沒有隨輸入圖面下降

| 同四頁／六目標 | 前輪整頁圖輸入 | 本輪完整表體 crops |
|---|---:|---:|
| API requests | 4 | 6 |
| 送入圖面 pixels | 7,955,748 | 1,499,164（18.84%） |
| Provider prompt tokens | 13,707 | 7,934（減42.1%） |
| Completion tokens，含reasoning | 18,930 | 28,800（增52.1%） |
| 串行 client RTT合計 | 117.13秒 | 210.78秒（本次約1.80倍） |

新請求依序耗時14.93／40.41／15.12／84.26／31.67／24.39秒。全部HTTP200、finish_reason=stop，沒有timeout、token cap截斷或重試。整個live含mapping約210.84秒，peak sampled RSS0.138GiB、最低available13.835GiB，未觸及預設界線。成本重算 (`pdf-core-table-crops-2026-10-17/cost-comparison.json`)、原始 observations (`pdf-core-table-crops-2026-10-17/live-observations.json`)。

這是歷史單輪方法對照，沒有控制provider queue，也同時改變了請求粒度及caption處置，不能將時間比值單獨歸因於crop或稱為p95。新T04產生更多內容，其生成成本不能和舊版大量漏值的失敗輸出視作等品質比較。可以確立的是：**減少輸入pixels不保證減少總tokens或總延遲；當模型輸出每格座標／spans，生成工作本身也需要列入設計。** 暫用OpenAI的client時間不是公司Qwen3/vLLM純推論或GPU算力數據。

## 凍結方法與執行界線

- 重用同版S0四頁baseline及144dpi頁圖，所有原source／options／image hashes先驗證。每個native body bbox以floor/ceil取完整像素；不resize、手切panel、手補表格或取oracle座標。1＋2＋2＋1＝6 targets。
- 同 `gpt-6-luna`、high image detail、low reasoning、JSON object、max_completion_tokens65536、store false。其模型名稱是provider回報的API identity，不推定不可變權重checkpoint。
- 與前輪相同完整plain-cell schema，單一新body-only prompt；caption固定空字串，框外caption／條件仍由baseline保留。Provider不得從看不到的內容猜文字。原5個caption links及Wiki standalone caption維持原位置與來源。
- 6calls上限、concurrency1、retry0、request180秒、live30分鐘、RSS12GiB／available8GiB。一次attempt防止重送；沒有新模型／套件安裝或CPUbaseline推論。
- 全部六次呼叫完成後才讀oracle／評分，再按每頁原target集合一次mapping，避免ref重編號錯置。單一target不合格則該頁沒有accepted document；raw仍保留。其他三頁無accepted artifacts已獨立確認。
- Live前審查發現通用credential regex會污染`task-specific`，已改為僅遮罩實際已知credential，補literal反例；保留preflight-v1並記明amendment。六個requests／prompt未變，修正時尚未呼叫API。憑證僅透過隱藏TTY／程序記憶體使用。

Frozen registration (`pdf-core-table-crops-2026-10-17/registration.json`)、preparation checks (`pdf-core-table-crops-2026-10-17/preparation-verification.json`)、runner (`pdf-core-table-crops-2026-10-17/run.py`)。映射成功的T05另經20項機械交付檢查、真正HTML表格渲染與80點來源比較；沒有把schema通過或assert數量當成模型準確率。

評分程序的兩個修正另留紀錄：T01首次generic grid view遇到重疊即停止、沒有產生分數；之後改成明示ambiguous binding的診斷，不從cell-list順序補欄位。T04 collateral Table7首次低解析人工抄值不可靠，改以288dpi原來源逐點確認，保留原草稿；未修改來源oracle、candidate回應、producer或請求。評分修正沒有帶來新推論。

## 採用判斷

保留 Standard＋專用模型主幹，以及已具局部證據的圖片／chart component VLM方向。本輪兩張複雜主表的純數值誤差都在5%內，無須為每個minor錯字追加後處理；真正的阻擋是無法可靠表示／交付欄位，以及普通表回歸。

**停止目前「每格完整座標JSON」配置的追加推論，亦不將它plugin化。** 表格下一個有價值的假設是先以零模型控制比較較精簡、避免重複座標的通用表格協定（例如二維cell內容＋明示spans／角色），再確定是否值得一輪固定推論。這屬輸出表示／mapper設計，不是替T04挪欄或自動修正數字；應涵蓋原有雙列維度、層級header、paired cells、rowgroups及literal controls。此假設尚未驗證，也不在本輪偷偷新增第七個請求或另一組prompt。

整體選型仍須優先補全文inline公式／code的discovery與保真方法、圖像supplement、完整同版交付及實際公司serving。不能為了少叫VLM漏掉必含工作，也不能拿低延遲的未完整配置通過驗收。

未做公司GPU/vLLM、高頻SLO、holdout或完整ProcessingProfile驗收；沒有修改production／SDK、提交Git或發佈新的GitHub內容。
