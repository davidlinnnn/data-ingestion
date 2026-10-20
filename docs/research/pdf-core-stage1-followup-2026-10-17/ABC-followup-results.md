# A／B／C 本輪離線驗證收斂

2026-10-17。**本輪接點驗證已收斂；尚無完整合格配置，不啟動新模型推論或第三段。** 此處的完成是各分支已有結果、剩餘缺口及去留判定，包含 partial／fail，不表示所有必含功能通過。

主幹維持 cached StandardPdfPipeline S0：Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3、Heron／RapidOCR／TableFormer V1；本輪沒有重新跑 Standard、模型、API、GPU 或 holdout。公司 Qwen3／vLLM 的品質及效能仍未由本輪證明。

| 分支 | 本輪新增證據 | 判定與剩餘阻擋 |
|---|---|---|
| A 公式／code | 公開 Core fragment-order 接點通過 `BODY → middle → TITLE` 的舊排序反例；prose＋inline、空 display、code literals／縮排、跨頁單 block、pure-formula picture handoff 均有合法 mock 控制。實際固定 S0 的 66 個 body-direct owners 及 11 個 group children 分別完成 mock mapping／JSON reload | 表示與順序接點有進展，完整 A 仍未通過。圖／正文邊界及未 emit glyph 沒有完整通用來源覆蓋；caption 的原位運輸與 typed inline enrichment 亦分開，後者不冒稱已支援。沒有新轉錄準度成績 |
| B 表格 | [已完成契約審核](contract-audit.md)，只增加明示 span 內 exact-empty padding 規則。同六筆 saved responses 的新方法 replay 保留 T01／T02 並交付 T05：80／80、7／7 比較、20／20 pairs | T04 的 category／metric／父 span 歸屬仍矛盾，停止本輪 B 的追加推論。原 v1 失敗與六次成本保留；跨頁 mapper 亦未解，不放行完整 B |
| C 圖片 | 同一 pinned NCCU native owner、894×653 crop、明示 MOCK response、image key／公開 PictureMeta／supplement，搬移後第二 process 讀回。53 個原 children、正文／caption／順序／來源保持；從 baseline 獨立重建 crop window／scale，24 個合成四方向點正逆映射與 17 個負例通過 | 單一 native 同輸入機械 gate 通過，完整 C 仍 partial。全來源圖片 census、heading／title／semantic parent、真實方向模型及 OCR／圖意／chart 準度、fresh worker 恢復未完成 |

## A 的責任／來源對照

[隔離來源評讀](A-review/summary.md)沿用原先獨立凍結的八頁 census，沒有將答案、人工 bbox 或 target 清單交給 producer。原 44 組來源 spans 中，36 組有 A eligible scopes、7 組由表格負責、1 組為圖／正文邊界 partial；原 41 selected units 均有可綁定的原生 owner，27 個普通陰性亦有 eligible scopes。這些是幾何／責任計數，**不是辨識準確率、API jobs 或已交付正確內容**。

七組 table-owned 中，三組 code 的內容與 row association 已由 native table 保留，不重複送 A；四組 table math 仍有來源內容或 cell 歸屬失真。來源無關的 [A↔B 轉交控制](test_cross_component.py)證明合法 LaTeX／code cell 字串可經既有 parser、Core、真正 Markdown HTML 解析與 reload 保存；typed 字串精確保留，顯示層依既有非必要空白規則核對。它沒有替四組來源生成或修復答案。

新 ordered stream 只讓合法 blocks 在未改動的 sibling anchors 之間插入；anchors 相對順序、fragment identity 與來源 binding 受檢查。它不會自動知道來源閱讀順序，也不會發現原生模型未 emit 的全部公式。66＋11 是分開的機械控制，沒有拼成一份已通過所有內容判準的完整候選。詳見 [A 方法與控制](A/summary.md)。

隔離 evaluator 另將七份未修歷史 payload 通過新接點，涵蓋四個保護正例與四個跨頁 joins；typed literal／math 次序、Markdown 文字、anchors、binding 與 reload 保留，三筆舊斷段也原樣保留。這是運輸回歸。來源已由 parent caption 保留的公式，依必要意思及 minor 判讀，不因缺少 typed-inline label 自動判失敗；caption typed-inline enhancement 是尚未支援的介面範圍。本輪完整 A 的實質來源覆蓋阻擋仍是圖／body 邊界及未 emit 的必要字形。

## 複核、回歸與檢查入口

獨立 [Standards](../../reviews/pdf-core-abc-followup-2026-10-17/standards.md)、[A Spec](../../reviews/pdf-core-abc-followup-2026-10-17/A-spec.md)及 [C Spec](../../reviews/pdf-core-abc-followup-2026-10-17/C-spec.md)分開保存；來源 census 對照也由不同 evaluator 執行。評分器、producer 及來源答案保持分工，舊檔與失敗預檢保留。

本輪 root review 重現 C 的兩種漏洞：同時改 scale＋投影座標，或等尺寸平移 window＋投影座標，原自洽檢查仍會接受。最終版改由不可變 baseline 的原生 provenance、page／picture ImageRef DPI、頁圖及 embedded crop 獨立驗證；兩個反例、改 crop 同時更新全部 hashes 的反例均拒絕。這是驗證修正，原 bundle 沒有改圖或重建模型答案。[預檢紀錄](ABC-mapping-review.json)與 C 的 `precheck-v1/` 均保存。

統一入口只比對保存證據、執行離線 regression 與既有 read-only checks，不刷新 manifests 或呼叫模型：

```sh
rtk /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-stage1-followup-2026-10-17/check.py
```

入口分 process 執行 A、B、B-padding、C、跨元件／checker suites，拒絕空 suite；避免同名 `method`／`controls` 模組及非 package 子目錄造成漏跑。完整結果與檔案 hashes 見 [核對紀錄](ABC-followup-verification.json)。檢查成功只支持保存一致性和列出的程序行為，來源品質依各 branch review 判斷。

## 下一個研究決策

保留已成立的元件與公開接合；停止對現有失敗 producer 的追加 prompt／模型重試。下一輪若投入，應先提出能補上「圖／正文邊界與未 emit 必要內容」的明確發現方法，並保留 T04 表頭及跨頁表的阻擋；不能以 ownership 分類、mock 或 raw-only 代替完整交付。新的選擇性 detector／較大 context 會增加多少 calls／pixels，須先有來源覆蓋與有限預算，再決定是否值得固定推論。沿用原必含要求及 minor 容忍，不在此縮減需求。

本輪已到適合做 [Matt retro](../../reviews/pdf-core-abc-followup-2026-10-17/retro.md) 的界線：三分支都有有界結論，接著回顧環境／檢查／導航如何避免同類錯誤。Retro 不取代模型評估，也不授權新推論。

未新增模型品質、latency／吞吐或公司 GPU 資格證據；完整配置、method lock／獨立 holdout 確認及第三段仍未放行。
