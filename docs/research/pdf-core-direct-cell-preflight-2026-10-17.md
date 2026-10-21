# Direct TableData live preflight

2026-10-17。核對既有 metadata、固定計畫、安裝套件與官方文件；沒有 API 呼叫、推論、安裝、PDF 開啟、圖片視覺檢查或 holdout 存取，沒有修改歷史證據。

稽核補註：初期一次過廣的 `rg` 搜尋碰到既有 native document JSON 內嵌 PNG 的 data-URI 字串並產生截斷輸出；未解碼或觀看圖片。另一次 metadata 程式列出 T04／T05 子項的 ID／欄位名稱，未列出數值或 header 答案。之後改為精確 metadata projection。這些內容沒有進入 producer／prompt，不能聲稱「從未開啟任何 document JSON」。

## 來源與 baseline

僅由 G1 `cases.json` 擷取 case／source／physical page／SHA 欄位，未將 oracle 數值、比較答案或 header 答案用作 producer 輸入。

| 案例 | 原始 PDF | Physical page | SHA256 |
|---|---|---:|---|
| T04／SRC09 | `docs/fixtures/agent-self-evolution-pilot-2026-10-11/09-2502.12110v11.pdf` | 17 | `fec32b521c4a1f793442bf1aeb26139c583078350d1cd4ab8f4eccc54a0694f0` |
| T05／SRC01 | `docs/fixtures/agent-self-evolution-pilot-2026-10-11/01-2608.27454v1.pdf` | 13 | `65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69` |

兩者為既有 DEV 來源，不是未曝光資料。Metadata 與 pilot manifest 一致；此次未重新讀 PDF bytes 核 hash，應由正式執行前檢查完成。

依[四頁計畫](pdf-core-table-html-plan-2026-10-17.md)，T04／T05 尚缺同版 S0，須新增 Standard2.132／Core2.99、Heron、RapidOCR、TableFormer V1 accurate 的各一頁轉換，不可把較舊全文結果當同配置 cached baseline。T01／T02 可重用 live-registration.json (`pdf-core-table-delivery-2026-10-17/live-registration.json`) 已登錄來源：

| 頁面 | baseline | baseline SHA256 | 144dpi input SHA256 |
|---|---|---|---|
| Memory-R1 p8 | `pdf-core-table-delivery-2026-10-17/memory-r1-p8/baseline.json` | `5f77f58972c4ec463b194604e81558b5cad8dde3b455798f585b370833a4834b` | `f2bc340447fea09bd90fcec63ae9aed4ce06e2ad9908d819d4a73f13bdffba03` |
| SkillOpt p8 | `pdf-core-native-round-2026-10-17/S0/skillopt/document.json` | `30f1b5d3450351a42262b71196f85b48fac20156f428b4a4f919157cec928d18` | `b21496108e623d7399e1c6f3d8d653ca3e04446a6e9d8fbde78b393bd9a0870f` |

## 輸出預算

以 source-independent 30 個 data rows × 13 columns，另加 3 層 headers，建立完整 33×13 occupancy 的合成表。前三個 stub header 各跨3列；頂層 metric header 跨10欄，下一層兩組各跨5欄；首 stub 欄的三個 group 各跨10列。共379個實體 cell objects。合成文字為 `Synthetic stub dimension`、`Synthetic grouped metrics`、`Synthetic metric family`、`Synthetic condition group`、`Synthetic printed row label`、`Synthetic metric`、`0.125 / 0.250`；沒有來源答案。

Cell 必填 `text` 與四個 start／end offset；minimal 僅對非預設值寫 spans／三種角色 flags。Full 則額外填滿 `row_span`／`col_span` 和全部 false flags。Envelope 含一個 target、caption／conditions、一個 panel 及完整 TableData。

| 合成輸出 | Compact UTF8 bytes | Pretty UTF8 bytes |
|---|---:|---:|
| Minimal、省略預設值 | 49,497 | 96,762 |
| Full、含所有預設值 | 80,804 | 160,595 |

**這些是 byte 數，不是實測 token 數。** Native runtime 與 bundled runtime 未安裝 tiktoken；UV cache 中雖有 tiktoken0.13.0／0.12.0 的 Python3.14 package，但沒有查得 o200k vocab cache，且其 model mapping 沒有 `gpt-6-luna`。因此未 import 後自動下載詞表，亦未用其他模型 tokenizer 冒充 Luna token count。`chars/4` 只能作粗略估算，不能據此聲稱32768必定足夠。

合成產生器已保存於 live.py 的 `budget_fixture()` (`pdf-core-direct-cell-2026-10-17/live.py`)；`--self-check` 檢查全部 grid occupancy／spans 與上述四種 byte 數，並保存 `budget-preflight.json` 的可重現 payload SHA256。此模式不開啟來源、不載入 adapter／模型、不呼叫 API。

[官方 GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna) 已實際開啟核對：128,000 max output tokens、1,050,000 context，支持 Chat Completions 與 image input。文件支持的模型上限不代表本帳號權限或每次請求可完成；未呼叫 provider 探測帳號。

**建議所有頁面統一凍結 `max_completion_tokens=65536`、compact JSON、省略預設 flags／spans。** 這給上述49,497-byte minimal fixture 留有餘量，且低於官方128,000上限。此建議是保守的預算選擇，不是回應長度保證：實際表格數量、文字長度、空白與 reasoning 仍可能超出合成樣本。若 root 另外取得可驗證的離線 tokenizer estimate，可據其 source-independent 結果選更小的固定 cap，必須在所有 live calls 前登錄。

維持最多4 calls、retry0、concurrency1、每 request180秒／B階段45分鐘；`finish_reason=length`、超時、JSON／結構不合法皆記為失敗，不增加 cap 重跑、不拆表、不隱藏困難 cells。最終 registration 須另核全部 native target 的數量與 request body／protocol hashes；本筆記不是已完成的 live registration。

本次未驗證真實四頁表示、Qwen3、GPU 或高頻效能；沒有讀取或保留 credential。
