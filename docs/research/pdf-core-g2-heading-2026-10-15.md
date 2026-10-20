# PDF-core G2：官方 heading recovery CPU 驗證

日期：2026-10-15（Asia/Taipei）；需求依據 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)，沿用 [G1 frozen cases](docling-pdf-core-g1-source-cases-2026-10-14.md)。**官方 stage 能恢復本次論文的編號正文與有書籤附錄，但無編號案例的文件標題／章節區分仍失敗，沒有選定正式 Processing Profile，G2 未全面通過。**

## 比較方法與版本邊界

本輪只回答組裝後的章節層級能否修復。WikiSkill 重用完整 28 頁、Docling 2.102.0／Core 2.96.0 的 continuation-v3 checkpoint restore 結果；沒有重跑論文模型，也沒有冒稱全新 stock 2.132 pipeline。控制文件另用既有離線 Standard CPU4／batch1 runner 跑原始 PDF 的 physical page 1，完整 provider result 在 export 前保存。來源、原結果與 checkpoint hashes 見 [input manifest](pdf-core-g2-heading-2026-10-15/inputs/input-manifest.json) 與 [input validation](pdf-core-g2-heading-2026-10-15/inputs/validation.json)。

候選放在隔離環境：`docling-slim==2.132.0`、`docling-core==2.99.0`、`docling-parse==7.22.3`，不修改原 baseline venv／模型快取。官方 Docling 的 Core 下限為 2.98，但這次 parse 的相容依賴要求至少 2.99；依 resolver 固定實際相容組合。此 runtime 沒有 Torch／Transformers／IBM models，不載入推論模型；native parser 明設一個 thread，禁止 remote/local fetch、render 與 bitmap 輸出。[官方 packaging](https://github.com/docling-project/docling/blob/v2.132.0/pyproject.toml)、[版本與官方原始碼核對](pdf-core-g2-heading-2026-10-15/primary-research.md)。

直接呼叫原套件的 `assign_heading_levels(document, parsed_pages, outline)`，`enabled=True`，其餘 heading options 採官方預設：bookmarks → numbering → style 優先。這個功能在 Standard options 預設關閉；此 stage 是規則處理，並非新的 VLM 模型。[官方 stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/heading_hierarchy/heading_hierarchy_model.py#L553)、[官方 options](https://github.com/docling-project/docling/blob/v2.132.0/docling/datamodel/pipeline_options.py)。

對同一份 assembled document，用新版 native backend 取得 WikiSkill 全 28 頁的 `SegmentedPdfPage`／font cells 與 32 筆 outline，控制文件只取相同 page 1（沒有 outline）。所有 stage inputs 在使用前持久化。Core load 的 reference alias／null 預設值變化與 stage 的實際修改分別保留；再以獨立子程序重新載入 document、parsed pages、outline，核對 fresh-input／reloaded-input 輸出。這是 **stage input replay 等價**，並非完整 fresh conversion、Pod 替換或 Canonical recovery 資格。

## 來源核對結果

| 固定案例 | 原基準 | 官方 stage | 判斷 |
|---|---|---|---|
| G1-S02：正文九個選定節點 | 9 個標題與頁碼存在；只有 2/9 深度正確 | 9/9 深度、依順序與 level 推得的父節點正確；三級章節恢復 | 本次選定範圍通過 |
| G1-S03：附錄四個選定節點 | 標題存在；只有 2/4 深度正確 | A／B 為 level 1，A.1／A.2 為 level 2；4/4 深度與推得父節點正確 | 有原始書籤時通過 |
| G1-S02：錯目的頁書籤 | outline 的 Experiments 指向 physical page 6；可見標題在 page 7 | 標題仍在 page 7；錯頁書籤不匹配，numbering fallback 給 level 1 | locator 保留；不是修正 PDF 書籤 |
| 同一論文移除 outline 的消融比較 | 同一 assembled document／parsed pages | 正文仍 9/9；四個附錄節點都成 level 4，0/4 正確 | 附錄不能只靠此設定的 numbering／style |
| G1-C07：無編號樣式，title + 2 主節 + 4 子節 | 七個節點全是 level 1 的 section header | title 仍是 section header level 1；主節變 level 2、子節變 level 3；六個章節絕對深度 0/6 正確 | 不通過；沒有將 oracle 的 title 角色餵回候選修正 |

C07 的四個子節仍掛在 Mathematical structures 下，表示相對樣式有辨別效果；但兩個主節多出文件標題父節點，不能因此把整份結果判為通過。Markdown 實際也輸出 `# Synthetic PDF controls`、`## Mathematical structures`、`### Inline expression`，與已固定的 title／章節契約有差距。原來的 code 排版與公式辨識問題沒有在此輪修復，也沒有因 stage 保留字串就宣稱它們合格。

獨立核對保存於 [source review](pdf-core-g2-heading-2026-10-15/review/source-review.md)、[output review](pdf-core-g2-heading-2026-10-15/review/output-review.md) 與 [逐案例結果／反例檢查](pdf-core-g2-heading-2026-10-15/review/output-review.json)。這只評分已固定的選定節點與控制案例，不是全 28 頁每個章節的完整人工 oracle。

## 修改範圍與交付接點

官方 stage 在 WikiSkill 改了 39 個既有 header 的 `level`，控制頁改了 6 個。獨立深度比較確認 stage 沒改其他欄位：文字、`orig`、來源頁／bbox／charspan、項目與 traversal 順序、code／formula／footnote／caption 標籤、內容及 graph references 保留；沒有新增誤升的非 heading。原本將 title 分類成 section header 的問題仍存在。Core-load 的 alias／null 變化另作語意等價核對，沒有混算為 stage 修正。

**原生 `parent` 仍是既有 Docling 容器關係，沒有被重建為語意章節樹。** 本輪 `headings-*.json` 的 `inferred_parent` 是依閱讀順序與 level 產生的檢視結果，與原生 `actual_parent` 明確分開；不能讓 Canonical adapter 直接把原生 parent 當成章節父節點。[官方 stage 實作](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/heading_hierarchy/heading_hierarchy_model.py#L553)。

可直接檢視 [論文章節樹（前）](pdf-core-g2-heading-2026-10-15/runtime/wikiskill-final/headings-before.json)／[章節樹（後）](pdf-core-g2-heading-2026-10-15/runtime/wikiskill-final/headings-fresh.json)、[論文 Markdown](pdf-core-g2-heading-2026-10-15/runtime/wikiskill-final/document-fresh.md)、[無書籤消融 Markdown](pdf-core-g2-heading-2026-10-15/runtime/wikiskill-final/document-no-outline.md)、[控制頁 Markdown](pdf-core-g2-heading-2026-10-15/runtime/controls-p1-final/document-fresh.md)。兩份文件的 stage inputs 重新載入後，document JSON、Markdown 與 font-cell 型別／數量均一致，完整 native 原始結果仍保留。

## 本機資源與可推論範圍

| 工作 | wall 秒 | sampled process-tree peak | 範圍 |
|---|---|---|---|
| 控制頁原 Standard CPU baseline | 5.770 | 1.579 GiB | 一頁、含模型載入／程序啟停；0.25 秒取樣 |
| 論文 native parse + stage + 消融 + 獨立程序 reload | 1.886 | 0.405 GiB | 28 頁已有 assembled document；不含論文模型推論；0.05 秒取樣 |
| 控制頁 native parse + stage + 獨立程序 reload | 0.815 | 0.125 GiB | 一頁已有 assembled document；0.05 秒取樣 |

論文 fresh-input stage 本體約 0.017 秒，控制頁約 0.00074 秒；都包含 document deepcopy，與整文件 ingest latency 不同。監測採 180 秒／6 GiB sampled RSS 軟停止、啟動前 available ≥8 GiB，所有正式子程序 exit 0 且已回收。最終 runner／guard SHA 在啟動前寫入 [論文 execution method](pdf-core-g2-heading-2026-10-15/runtime/wikiskill-final/execution-method.json) 與 [bounded record](pdf-core-g2-heading-2026-10-15/runtime/wikiskill-final/bounded-execution.json)；startup import／sandbox 監測失敗與檢查期間的早期執行另留 attempt trace，不計為額外品質案例。

CPU 可以承擔這個小型後處理候選；本輪一次觀察不提供 p95、公司 GPU、Kubernetes 或高頻 ingest SLO 結論，也沒有新增 remote API 呼叫。

## 採用判斷與後續缺口

保留官方 heading stage 作候選，不立刻採用為 F03 的完整交付方法。接續須明確解決：文件 title 與最高章節的角色區分、缺書籤附錄、Canonical 的語意 parent 映射；並對真正的 fresh／checkpoint 邊界保存必要 font／outline inputs。不同版面與真實無編號來源還需 holdout，不能用單張 synthetic 成功或失敗概括所有文件。

本輪完成已授權的 heading 比較，具體失敗保留，不放寬 G1。後續 G2 還有 orientation／混排 OCR、inline formula／code 偵測及回填、其他完整表格／案例與候選組合；公司 GPU／高頻、Canonical Acceptance 與完整 551 頁 pilot 尚未通過。既有 baseline 環境、G1 與前五輪 payload 保留，未修改 production code、commit 或 push。完整性資料見 [validation](pdf-core-g2-heading-2026-10-15/validation.json) 與 [artifact manifest](pdf-core-g2-heading-2026-10-15/artifacts.json)。
