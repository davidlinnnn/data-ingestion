# 官方逐頁 API 方法：獨立來源核對

8 次新推論與 4 份官方組裝文件完成後，逐項核對凍結的 41 個 selected logical units。來源真值來自新推論前的 `contract.json`，結果與逐項證據見 `results.json`。沒有重跑、修改 prompt、猜補答案、讀取 holdout 或改寫上一輪評分。

**此候選不整體採用。** 41 項都找到輸出，但必要行內 LaTeX、跨頁段落、code 保真與來源位置仍有缺口。官方 parser 能接受輸出，不代表符合產品交付要求。

| 來源 | 固定單位 | 原始內容 pass | minor | material |
|---|---:|---:|---:|---:|
| WikiSkill | 7 | 6 | 0 | 1 |
| DGM | 6 | 5 | 0 | 1 |
| SEAL | 19 | 13 | 2 | 4 |
| Controls | 9 | 9 | 0 | 0 |
| 合計 | 41 | 33 | 2 | 6 |

這是本次全來源內容與標號評分，不是先前自訂 typed JSON 契約的 25／5／6，也不是 Canonical Acceptance 或模型準確率。六項 material 包含兩項實質內容錯誤，以及四項完整公式缺少來源方程編號；不得把分母／rubric 不同的數字直接相減當改善幅度。

## 內容與交付的區別

- WikiSkill 368 的 `ReflACT` 變成 `RefACT`。DGM 646 多處 `test_stats` 變成 `test_state`、tie-break 條件改寫、log 字串改變，並漏掉 `Test Success` 一行；這些是內容保真問題。
- 新增處理的 SEAL 四個 display formulas 保留主要數學結構，但全部遺失 `(1)` 至 `(4)` 來源標號。公式 2、4 的 XML `&amp;`／`&lt;` 在官方 parsed LaTeX 中仍是字面字串，未成為可用的 alignment／小於符號。
- SEAL 多處原始回應使用 HTML sub／sup；官方 parser 將其攤平成普通文字，例如 `ReSTEM`、`θold`、`ys(i,j)`。原始符號可讀與最終可用 LaTeX，分別判斷。
- E13 原始 p3 把 `<inline>` 包在 `<text>` 內；官方 parser 產生多個根層文字與 display formula blocks，其中 14 個 child items 沒有 provenance。跨頁最終文件沒有成為一個完整普通段落。
- Controls 的 matrix、fraction、piecewise 與完整七行 code、inline code 成功。Comment 與 body 合成同一 code block 是合理的官方全頁結果，不沿用先前 target-only 請求的 context leakage 判準。
- SEAL 原 native 合併的段落與 Algorithm 1 標題正確拆開；左欄段落與後續 `are sampled from...` 正確相接。仍有 `of this` 兩字遺漏及未交付行內 LaTeX，分開記錄。

F13 完整 expression／presentation 子項為 4／18：這是逐來源單位的完整交付檢查，包含公式標號與正式變數，不是公式辨識率。F14 內容／區塊子項為 6／7；此子項不包含另行失敗的來源幾何。兩種 task slices 會重疊，不能相加成總準確率。

## 四個原正例

| 原判準 | 內容意思 | 原完整交付 |
|---|---|---|
| WikiSkill 362 開頭遺漏回歸 | 通過 | 通過 |
| E04 五個 code tokens／node 綁定／數值 | 通過 | 通過；不另要求 typed JSON |
| E14 六處行內數學／全文 | 通過 | 失敗：只有 4 處 formula，兩個 `p≥0.05` 是普通文字 |
| E13 十一處數學／單一跨頁段落／雙頁來源 | 通過 | 失敗：公式被拆成 display、段落未組回，部分 items 無 provenance |

## 來源位置與保存證據

41 項可透過已登記的 input-order sidecar 追到各原始實體頁；這不等於精確來源框正確。27 項含至少一個超出 page bounds 的模型預測框，E13 另有 item provenance 缺失。即使框沒有越界，也不代表已驗證定位精度；不得將模型推測框當作來源測量真值。

唯一 `[REDACTED]` 出現在 SEAL p2、41 項以外的 Synthetic Data Generation 段落。既有保密 regex 誤把普通 `task-specific` 的 `sk-specific` 部分視為金鑰格式；官方 parsed document 仍保留實際原字串。這是保存證據邊界的 false positive，沒有列為模型錯誤，也沒有從 parsed 文件回補 raw 檔案。

驗證方式：執行 `assess.py` 核對凍結契約、41 個映射、逐項頁面、所有輸出 SHA256、四個正例與關鍵內容觀察。原始 contracts、模型輸出與上一輪 25／5／6 評分不變。

此結果僅覆蓋已曝光固定 8 頁的 41 個 selected units，不代表全部頁面內容或所有文件型態。公司 Qwen3／GPU、高頻負載與 holdout 尚未驗證；不以等待公司資訊作為這一輪暫用模型比較的停止理由。
