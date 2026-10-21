# PDF-core G2：較強 VLM 的行內內容與回填比較

日期：2026-10-15（Asia/Taipei）。承接[前輪 Granite CPU 比較](pdf-core-g2-inline-2026-10-15.md)及 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。**完成 17 個 whole-item 段落及 5 個整頁的暫用 `gpt-6-luna` API 比較。段落路徑在兩個主要行內公式案例有明確改善，可保留為候選；整頁路徑仍漏 LaTeX／誤讀下標，不能升為通用替代方案。G2 尚未全面通過。**

這是使用者允許的暫用 hosted candidate。公司 self-hosted Qwen3／vLLM 仍須獨立驗證，沒有改成只能選 Qwen3，也沒有以 hosted 模型的品質或 latency 代證公司部署。原始來源、provider、前輪模型輸出、oracle 與失敗不變；沒有寫入正式 Canonical Knowledge。

## 固定輸入與實際方法

輸入 manifest (`pdf-core-g2-inline-api-2026-10-15/inputs/input-manifest.json`) SHA256 `c87899f88b96553f9dc856d020adafdea7281938b00fb121a5f358b6a1a75f0d` 引用前輪 **17 張完整 item PNG／19 個 fragments**，以及前輪官方 CPU engine 收到的 **5 張整頁 PNG**。全部 bytes 與尺寸相同，沒有重新裁圖、放大或使用 oracle bbox。所有來源為固定版本公開論文及原創 synthetic controls。完整保留前輪 28 個普通 items 的 gate inventory；這輪沒有新增 inline detector，也未提高其 coverage 證據範圍。[準備與來源限制](pdf-core-g2-inline-api-2026-10-15/inputs/README.md)

模型只讀 image 與共用任務 prompt／schema，不讀 producer 原文、正確公式、案例答案或 evaluator。SEAL E13 跨頁段落沿用已由 historical continuation-v3 合成的一個 provider item，模型輸入是兩頁來源 fragments 的拼圖；本輪成功不能冒稱新解決自動跨頁發現。

| 設定 | 本輪固定值與邊界 |
| --- | --- |
| Endpoint／model | 使用者指定 Chat Completions endpoint／`gpt-6-luna`；22 個 responses 的 returned model 均保留，alias 未提供固定 dated build |
| 推論設定 | `reasoning_effort=low`，省略 temperature，`store=false`，image detail high；單次 attempt、順序執行、不自動 retry |
| 輸出 | Strict JSON schema：ordered blocks、image-pixel bbox、text／math／code／unknown segments、nullable code language、uncertainties；math segment 為不帶外層 delimiter 的 LaTeX |
| Token cap | 段落 4096、整頁 8192 completion tokens，包含 reasoning；不能等同前輪本機 generated-token cap |
| 執行路徑 | 兩種輸入都重用既有安全 HTTP client，屬 direct API component；**沒有執行官方 API `VlmPipeline`**，也沒有把 JSON 冒充 DocTags／DoclingDocument |

選擇 JSON segments 是為了直接保留 prose 與重建片段的順序，便於檢查和產生候選 Markdown。與前輪 default DocTags prompt 的差異也包含 schema、prompt、reasoning 及 provider image 處理；same PNG 只能固定送出的視覺輸入，**不是單一 model 因果排名**。Schema 正確不保證內容正確。[本輪 source audit](pdf-core-g2-inline-api-2026-10-15/api-primary.md)／runner (`pdf-core-g2-inline-api-2026-10-15/api/run.py`)

官方 API engine 的 source audit 發現安裝版會注入 temperature，而本輪 low reasoning 應省略它；該 helper 另會重編影像、strip content、縮減 response 與映射錯誤。這些留給具名 transport／parser 整合驗證，沒有悄悄修改官方套件或另增不同 reasoning 設定來混算。模型的 image input 與 Structured Outputs 支援已核對[官方模型頁](https://developers.openai.com/api/docs/models/gpt-6-luna)及[官方 API guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=chat)，本輪真正可用性則由保存的 responses 證明。

## 獨立來源核對

| 來源／必要內容 | API 段落路徑 | API 整頁路徑 |
| --- | --- | --- |
| E14：WikiSkill p21 七行完整正文、六處 inline math | 六處正確 LaTeX、門檻／否定／量詞及文字順序保留，`top-ranked` 亦保留 | 六處意思保留，但僅四處 math segments；兩個 `p≥0.05` 留在普通文字，F13 重建仍不完整 |
| E13：SEAL p3→4 八行、十一處 inline math | 一段完整 prose、十一處正確 LaTeX、LM 下標／prime／arrow／參數順序保留，p4 不重複 | p3 將 LM 的 theta 下標讀成 `L_M`，並漏掉 `(C,tau)` 的右括號；p4 update 正確不能抵銷。兩頁分別轉錄，沒有實作跨頁合併 |
| E04：DGM p51 五個 inline code occurrences、node／action／23.3%／40.5% | 五個 tokens、bindings 及 prose 保留；三個標 code、兩個 `edit` 留 text。`bench-mark` 為視覺換行差異 | 五個 tokens／bindings／數值保留，四個標 code；source 換行保留成 `bench-`＋次行 `mark`，差異另記 |
| WikiSkill 362 段首遺漏回歸 | 保住統計檢定段首與 1,000 iterations，前輪 omission 沒有重現 | 另保留完整頁面輸出，不能由這一段宣告全頁忠實 |
| C01 controls：inline 平方／矩陣／分數／分段式 | Inline 平方改善；矩陣 crop 的右括號及上下邊界本來已裁掉，輸出仍未忠實重建原方括號 | 四種數學結構可作局部成功證據；不由 synthetic controls 推及真實全文件 |
| C02 controls：七行 code 與 inline `items[i] <= limit` | 註解、六行主體及 inline fragment 忠實，主體標 Python；註解／inline 的 role 與原 provider 不同，故保留原文 | 七行 Python、註解、巢狀及 inline boundary 保留；普通 label 的空格差異獨立記錄 |

F13 明定所有必要行內公式須交付 LaTeX，不能只以普通文字保留數學意思算完成。F14 依內容與區塊忠實判斷；未標 typed code 本身不是新增淘汰條件。DGM 沒有 frozen 全文逐字分母，以來源視覺核對與具體差異報告，不捏造百分比。

其他選中 items 也保留失敗：SEAL32 把 `LM_{theta'}` 讀成 `L_{M_{theta'}}`，並產生額外 prose `}`；不能因 E14／E13 成功就批准全部候選。模型回傳的 uncertainty 為空也不證明沒有錯誤。完整原始 responses、解析結果與獨立來源判斷分別保存，沒有用 evaluator 答案修補輸出。

[獨立 review 說明](pdf-core-g2-inline-api-2026-10-15/review/output-review.md)及機器結果 (`pdf-core-g2-inline-api-2026-10-15/review/output-review.json`)記錄這些來源差異、22 個 in-memory 負例及完整 parsed／reinsertion 核對。E14／E13 的 pass 僅限其固定案例與方法，沒有批准其他 items。

## Provider 邊界、解析與回填

本輪揭露兩項不能只靠換大模型解決的輸入問題：

- **矩陣裁圖不完整。** Producer 的窄 formula bbox 加固定 padding 後，仍裁去原矩陣的右方括號與部分上下界。模型只能看到左側直線與數字。這是 region acquisition／crop 完整性缺口；輸出無 uncertainty、仍給出不符原稿的 delimiter 也需保留，不能將全部失敗歸因模型。
- **SEAL34 的 provider item 已混入 caption。** 拼圖含一段截至 `self-edits` 的 prose，以及 Algorithm 1 caption。API 分成 paragraph＋caption 是來源可見內容，並非捏造 caption；whole-item 單一 root 的安全回填仍須拒絕，不能靜默重寫 graph 或刪 caption。

本地 postprocessor 驗證 JSON／segments／bbox，產生獨立 Markdown 與補充片段資料，並沿用 exact provider item／document／neighbor hashes、完整 charspan、one compatible block、重複 prose 及 scope 外不變等 guard。原 provider 不變；hidden picture children 的公式亦不能只換 child 便宣稱已交付到主 Markdown。模型輸出、postprocess、候選替換與語義核對是分開的證據。

22 筆皆完成本地 contract validation／render。17 個段落候選中 **11 筆結構套用、6 筆保留原文**：SEAL34 的多 blocks、3 個 hidden formula children，以及 controls 註解／inline code 與原 provider 的 block role 不一致。Role disagreement 需回到來源與 mapper 判斷，不能一律當成模型內容辨識失敗。保留全部原 blocks／uncertainties，不挑第一塊、不補答案、不靜默改 source graph。解析摘要 (`pdf-core-g2-inline-api-2026-10-15/parsed/summary.json`)／回填摘要 (`pdf-core-g2-inline-api-2026-10-15/reinsertion/summary.json`)

來源定位保留 physical p21／51／3／4／1 與既有 fragment transforms。API bbox 是推論出的 image-pixel 區域，幾何投影與輸出 segment offsets 不代表 glyph 測量或正確的語義對齊；拼圖跨頁的單一 block 必須保留多個原來源 fragments。沒有用 page-1／crop-local box 冒充原 PDF 座標。

這些 checks 是有界驗證；固定來源的 oracle 不能變成每次 ingest 都知道內容正確的 runtime 判定器。結構上可替換的候選仍可能包含 SEAL32 等內容錯誤，沒有自動獲得 Canonical Acceptance。

## 時間、可觀測性與後續

22 次均 HTTP 200、`finish_reason=stop`，沒有自動重跑。每個原始 body、request body hash、image hash、request ID、returned model、usage、refusal／finish 及 client round-trip 保留；Chat API 沒有提供本機 generate hook 的 raw token IDs／EOS，沒有偽造相同可觀測性。送出的 API credential 不在檔案、command line 或報告內。

| 輸入 | 次數 | 單次 client round-trip 秒 | 合計秒 | Prompt tokens | Completion tokens（含 reasoning） |
| --- | ---: | ---: | ---: | ---: | ---: |
| 完整 item／段落 | 17 | 2.52–7.06 | 85.25 | 12,346 | 7,614 |
| 整頁 | 5 | 8.23–15.93 | 57.36 | 14,227 | 8,387 |

總 client round-trip **142.61 秒**，usage 合計 **42,574 tokens**（其中 reasoning 5,409）。這是小樣本、順序單次 hosted API 測量，不是公司 GPU、warm serving、batch／併發、高頻吞吐或完整文件 SLO；也不能與前輪包含每次 CPU model load／process exit 的時間直接當硬體速度排名。實際限制為既有 HTTP timeout／single attempt／shared lock，沒有量到 remote GPU／RAM 或證明遠端取消。

建議保留「Standard 主流程＋完整段落 VLM 候選」方向，將本輪 E14／E13 的改善作為可行性證據。下一個應優先處理的是 producer 的 crop／item 邊界與輸出語義保真，再評估相同規格的公司候選及真正 Docling／Canonical 整合；不以每頁全部改走 VLM 解決這些問題。G2 原有 heading、order、OCR、delivery 及其他來源缺口仍保留，沒有採用最終 Processing Profile。

未驗證公司 GPU／vLLM、高頻負載、完整 corpus、官方 API pipeline、正式 Canonical mapper 或恢復。暫用 hosted 成功不能替代地端開源部署條件，結構回填亦不能代替語義 Acceptance。

整體驗證 (`pdf-core-g2-inline-api-2026-10-15/validation.json`)／artifact manifest (`pdf-core-g2-inline-api-2026-10-15/artifacts.json`)核對本輪證據、前八輪 1,517 個 payload、source hashes、local links 及 credential pattern；API 檢查 (`pdf-core-g2-inline-api-2026-10-15/api/verification.json`)與回填檢查 (`pdf-core-g2-inline-api-2026-10-15/reinsertion/verification.json`)分別保留其實際範圍。完整證據留在本機，GitHub 僅回寫[結論摘要](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6192058531)與正文指標；逐字 readback (`pdf-core-g2-inline-api-2026-10-15/ticket-update.json`)確認 44 個 feature rows 不變、issue 保持 OPEN。
