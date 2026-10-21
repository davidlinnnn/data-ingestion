# 官方逐頁 API：medium 對 low 的獨立來源核對

候選 3 沿用候選 2 完全相同的 8 頁、41 個來源單位及 來源契約 (`contract.json`)，只改 `reasoning_effort` low → medium。8 次新推論及 4 份官方組裝文件完成後，分別檢查原始 DocTags、官方 parsed document 與 stock Markdown。逐項資料、配對差異及輸出 hashes 見 `results.json`，可用 `assess.py` 重複核對而不覆寫凍結結果。

**候選 3 不採用，也不因整體數字改善而選它作 challenger。** 它找回一些公式與標號，卻新增來源數學錯誤、code 運算符交付錯誤及段落／provenance 退化。這正是先前要求保留回歸案例的用途。

| 項目 | low | medium | 判讀 |
|---|---:|---:|---|
| 固定來源單位，皆已嘗試 | 41 | 41 | 分母不縮小 |
| Raw source pass／minor／material | 33／2／6 | 36／2／3 | 只評原始內容；不等於可交付準確率 |
| F13 完整 expression／presentation | 4／18 | 6／18 | 有恢復也有新退化，不能只看總和 |
| F14 內容／區塊 | 6／7 | 4／7 | Controls 運算符新增失敗 |
| 四個正例的原內容意思 | 4／4 | 3／4 | E13 新增實質數學錯誤 |
| 四個正例依原有界判準交付 | 2／4 | 2／4 | E13、E14 都未交付通過 |
| 含至少一個越界預測框的單位 | 27 | 11 | 不越界也不證明定位正確 |
| 含缺失 item provenance 的單位 | 1 | 13 | 巢狀 markup 被拆平的退化 |

F13／F14 子項會重疊，且不含完整來源幾何驗證，不能相加或當作 Canonical Acceptance。Raw XML entities 可作為 markup 讀取意思，但最終 code／LaTeX 依實際保存的字串判斷，沒有做 HTML unescape 修復。

## 改善與新錯誤

- WikiSkill `ReflACT` 恢復正確；E14 的六處數學在 raw 中完整，low 僅四處。但 medium 把 `<inline>` 包進 `<text>`，官方 parser 將其拆成根層 display formulas，`p &lt; 0.05` 也未解碼。E14 仍不是原本的完整行內段落交付。
- E13 source `LM_{theta}` 被改成 `L_M`，失去 theta 並改變符號結構。SEAL 32 的 source `LM_{theta'}` 被改成 `LM_{theta_t}`。兩者都是新的 raw 模型內容錯誤，不能由 parser 修復。
- DGM diff 646 仍有多處 `test_stats` → `test_state`、遺漏 log，並新增 `attempt_num + 1` → `len(attempts) + 1` 等改寫。不能用較好的其他案例抵銷。
- 四個 SEAL display equations 的 source 標號 `(1)`–`(4)` 都回到 raw；前三個能完整交付。第四個 raw 使用 literal `<s`，官方 parser 在 `\mid y_{` 處截斷，後續條件、`C_i` 與 `(4)` 全部遺失。
- Controls 完整 `y=x²+1` 改善為單一 inline LaTeX。但 piecewise 的 `&amp;`／`&lt;` 仍留在最終 LaTeX；code body 與 inline code 的 `&lt;=` 留在最終 code 字串，原來的 `<=` 未交付。縮排正確仍不能算 code 保真通過。

## 四個原正例

- E04：五個 inline code tokens、node 6／24 綁定及 23.3%／40.5% 仍通過，官方 parser 也保留 inline group。
- WikiSkill 362：原先的「開頭句遺漏」有界判準通過；但本次兩個公式被拆成 display，完整 F13 相對 low 退化。不能把有界正例擴張成整段 F13 通過。
- E14：raw 數學意思完整，最終行內段落／來源交付失敗。
- E13：raw 數學本身已錯，跨頁段落與部分 provenance 也未通過。

五個原本未執行單位全部有輸出。四個 display equations 的 raw 全文與標號恢復；其中三個完成 F13 交付，第四個被 parser 截斷。原 native 誤合併的段落／Algorithm 1 標題正確拆開，但仍有原句 `of this` 遺漏及行內公式交付失敗；不宣稱五項全數解決。

## 證據保存與停止點

SEAL p2 唯一 `[REDACTED]` 是既有保密 regex 誤判普通 `task-specific`；位於 41 項之外，官方 live parsed document 保留實際原詞。這是保存證據邊界問題，沒有列為模型錯誤或回補 raw 檔案。

原始 source contract、候選 2 結果、模型輸出及先前 25／5／6 歷史評分皆不變。本輪第三個配置名額已使用，沒有新增特例、後處理、重試、prompt 調整或 holdout 執行。三個開發候選目前沒有符合全部必要條件的 challenger；完整方法不進入 holdout。

這仍是暫用 OpenAI 模型的有界比較，不能代表 Qwen3 或公司 GPU／高頻環境。公司資訊不是完成本輪比較的前置條件；暫用候選失敗也不能據此推論 Docling 所有模型／方法都已達極限。
