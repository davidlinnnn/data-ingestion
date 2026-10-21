# W2 第 3 回合：全部候選逐案裁定

只在此新目錄寫入。Round 2 的 frozen oracle、分析、conversion artifacts 全部唯讀；沒有重跑 conversion、沒有修改分析分母/語料或 Git 狀態。

候選清單：`catalog-baseline36.json`；原 30 篇完整清單另外保留為 `catalog-v3.json`。原 30 篇非家具由 oracle agent 裁定；六篇補完的非家具由 trace agent 裁定；全部家具候選由 heading agent 裁定。每個候選 ID 各有 record，允許同頁、同一來源根因共享證據，但不能用一個範例替代未檢視的其他頁。

`prepare.py` 將原始 PDF 頁面以本機 PDFium scale=1.5 渲染至 `pages/{job}/pNNN.png`，並建立全頁 contact sheets。`packets.py` 準備來源 anchor、native text/ref/provenance 與相應頁面文字，沒有自動決定 Q4。`decisions.json` 是看過原頁圖及原生/Markdown後明確記錄的共享裁定，`decide.py` 只把這些人工根因展開成逐 ID records，未列入規則的候選會維持待裁定，不能默認 clean。

## 三類與範圍

- `CONFIRMED_BLOCKING`：頁圖/來源與實際交付 text/Markdown 已證明必要內容漏、重、錯序、錯接或家具污染。整篇即使另有未裁定範圍，也以已確認阻擋優先。
- `CLEAN_AFTER_ADJUDICATION`：該篇所有機器候選已裁定，沒有發現阻擋；不是全文逐字逐句的等義驗證，也不是 Profile 通過率。零候選但有可用 oracle 的篇，依本輪定義列此類。
- `UNKNOWN`：無可用 oracle、未裁定候選或證據不足。不可將尚未裁定自動歸 clean。

每篇與 family 摘要都保留稀疏 trusted-anchor 限制。章節層級及數學品質由其各自分支報告，不以本表 clean 宣稱它們正確。

## 關鍵辨別

1. **caption label 不同，不等於內容混入**。若 caption 是僅含圖/表說的獨立 text item，且 Markdown 有明確 Figure/Table 前綴與分段，判 metadata-only；若同一 item 把 `simpler depen-`、`Amazon Mechanical`、`self-edits` 或 `strongest competing` 這類正文片段接上 caption/algorithm，再到後續 item 才續原句，屬實際錯接。
2. **native `orig` 與可用 `text`／Markdown 分開**。Adam p12 Definition10.1 的英文仍在 `orig`，但 `formula.text` 空且 Markdown 缺失，路由至 label/materialization/export，不能稱 backend 抽不到。SICA prompt 可在 picture 子字存在但 Markdown 只給 image placeholder，亦是交付出口損失。每案保留 `native_json_vs_markdown`；原 30 篇另有同頁原始欄位證據 `native_orig_evidence`。
3. **D1 範圍錯誤與 D3 分開**。Adam text-layer fallback 將頁首、頁碼、圖軸、section 小標、caption、display equation、algorithm 混入 prose anchor，可判 `source_oracle_error`／`oracle_scope_error`。純 inline-math/下標攤平依 D3 另列 F13，不自動當 F01/F02。空 display formula/algorithm increment 不是公式等價證據，也不自動稱 F13-only；其實際交付數學損失另留風險。完整必要英文定義或量詞條件漏失，仍是 Q4 阻擋。
4. **家具須辨原頁身分**。References 裏的 arXiv publication 字串不是頁邊 stamp；保留為正文書目正確。幾何 eligibility 只是一個候選限制，不能推翻頁圖確認的實際頁碼/家具身分。

## 合併與計數

`merge.py --old30` 驗證原 608 IDs；`merge.py` 驗證最終 875 IDs。重複、未覆蓋或額外 ID、缺圖、缺來源/輸出理由、未視覺核對，皆 assert 失敗，不能產出完整覆蓋宣稱。輸出 `records*.json`、`papers*.json`、`families*.json`、`root-groups*.json`、`summary*.json`。

同一問題可能同時有 missing、role、caption 或兩種 LIS 告警；**候選數不是獨立缺陷事件數**。`shared_evidence_group` 以來源頁與同一語意根因去重，variant 的 fixed/new-bad 應按來源根因組比較，不可把候選消失直接稱修好。同組有多個 source instances（例如四筆 colspan 重複或兩個 prompt 框）時，另報 instance/partial-fix；只有所有必要 instances 都解決才稱整組修好。
