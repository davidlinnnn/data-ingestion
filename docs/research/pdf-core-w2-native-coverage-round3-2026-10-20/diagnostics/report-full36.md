# W2 全 36 篇：picture 原生字層與交付映射

完整 36 篇／715 頁已有保存輸出，本診斷對照 `baseline-inputs.json` 全 36 路徑逐一相符；30 篇沿用原 S0 結果，6 篇使用本輪 recovery 結果。本工具僅讀 PDF／保存 JSON／Markdown，零 conversion、零 OCR／VLM／模型推論，保留原 30 篇報告。

235 個 picture 中，**172 個框含至少 30 個 PDFium 原生非空白字元（73.2%）**，涉及 146 頁、35 篇。172／172 已有至少 30 字元的 native picture descendant text；僅 14／172 在預設 Markdown 找到至少一個 ≥30 字元的完整 child text。327 個 substantial child text nodes 中，28 個可在 MD 找到。

這些是 **原生字層存在／交付映射頻率**，不是抽取正確率、全文覆蓋率或 Q4 通過率。「MD 找到」可能在文件別處命中，未證明位置正確；「child ≥30」未證明整個框內所有字都正確。

| family | 篇／頁 | picture | 框內原生字 ≥30 | 涉及篇／頁 | 已有 ≥30 native child | 有 ≥30 child 在 MD |
|---|---:|---:|---:|---:|---:|---:|
| ACL/EMNLP | 5／86 | 31 | 20 | 5／13 | 20 | 2 |
| ACM sigconf | 2／20 | 12 | 8 | 2／7 | 8 | 0 |
| CVPR/AAAI | 2／22 | 12 | 12 | 2／11 | 12 | 0 |
| ICML | 3／39 | 20 | 15 | 3／12 | 15 | 0 |
| IEEE conference | 2／10 | 6 | 4 | 2／3 | 4 | 0 |
| NeurIPS/ICLR | 9／238 | 50 | 43 | 8／35 | 43 | 5 |
| Pilot-other/unknown | 6／167 | 60 | 41 | 6／37 | 41 | 5 |
| Springer LNCS | 2／20 | 8 | 5 | 2／5 | 5 | 0 |
| general arXiv | 2／24 | 7 | 2 | 2／2 | 2 | 0 |
| general arXiv（article，template uncertain） | 3／89 | 29 | 22 | 3／21 | 22 | 2 |
| **合計** | **36／715** | **235** | **172** | **35／146** | **172** | **14** |

全量逐框 PDF text／bbox／raw char indices、native children text／orig／marker、MD presence：`picture-text-full36.json`。統計、輸入清單與 inventory SHA：`full36-summary.json`。

## 補齊六篇的觀察

| recovery 論文 | picture | 原生字 ≥30 | 其中有 substantial child 出現在 MD |
|---|---:|---:|---:|
| P03 Trace2Skill | 8 | 6 | 0 |
| P06 SelfEvoSkill | 10 | 8 | 1 |
| P10 ReasoningBank | 15 | 14 | 3 |
| P16 Darwin Gödel Machine | 8 | 8 | 0 |
| P18 Agent0 | 5 | 3 | 0 |
| P20 Absolute Zero | 22 | 16 | 2 |

新增 55 個 ≥30 圖框全部已有 ≥30 native child text；此全量觀察沒有「框內 ≥30 但 children 不足 30」案例，不能將這種缺口數報成未完成或把圖文字整段消失歸抽取。仍須對具體字句裁定部分遺失／錯序，不能由總字數推論無錯。

## 方法與分流

原 PDF 字層使用 PDFium `get_text_range`／`get_charbox`；統一 BOTTOMLEFT PDF points，以每字 ink bbox 和 picture provenance bbox 的 intersection／char bbox area ≥0.5 判定入框，非空白 Unicode 字元逐字計數。另存 full bbox containment ≥1−10⁻⁶；改用此嚴格定義，≥30 圖框仍是 172。每頁處理 UTF-16 surrogate pair 並 assert normalized 逐字字流與整頁字流相等。沒有 render／bitmap decode。

picture graph 遞迴收集非 caption／footnote 的 descendant text，保存 text 與 orig，避免清單 marker 從 text 拆走造成誤判。MD 使用 NFKD/casefold/alnum 的完整 child text exact substring，≥30 非空白字元才計 substantial。框內 overlap 可以包含圖外正文或圖中文字，這是保守幾何候選；未作全圖逐字語意人工驗收。

P07 p12 的兩個 prompt boxes，PDFium／native orig 字量分別同為 1,238 與 1,488；第二框 text 少 49 字元是 marker 拆分，orig 仍全保留，不能說抽取漏掉。兩框文字未出現在預設 MD，歸 **#81 匯出映射**。官方 Markdown picture serializer 未遍歷普通 picture text children；full native graph 有字與 MD 未交付可以同時成立。官方 source (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:872>`)。

Colspan 重複亦歸 **#81 serialization**：官方 synthetic 2×2 native table 的 colspan2 句子，native table_cells 一次、grid／MD 兩次、HTML 一次且帶 colspan2，所有斷言已通過。原 native input 正確，無模型推論。native (`synthetic-colspan-native.json`)、[MD](synthetic-colspan.md)、HTML (`synthetic-colspan.html`)、結果 (`synthetic-colspan-result.json`)。官方 grid 在各覆蓋格放同一 cell，MD 每格輸出 text，HTML 只輸出 span 起點。grid (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/types/doc/items/table/table_data.py:111>`)、MD (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:819>`)、HTML (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/html.py:398>`)。

Caption／algorithm 插入正文仍是另一類：既有 exact 零推論 traces 支持 ImageTransformer p5、P01 p8、P17 p4 由原始 layout text label 及 paragraph merges 造成；不將它們混算成 MD picture-child omission。固定輸出 evidence／SHA (`caption-algorithm-stage-evidence.json`)。本次只刷新 baseline 頻率；V1 變更成效尚未分析。

Egret medium 的本機 preset／config／preprocessor／78,311,396 bytes 模型 SHA 與 1,009-tensor 靜態 header 已核對；沒有載入 tensor或新增推論。完整本機證據 (`egret-medium-local.json`)。

未修改任何舊 artifact 或套件、未跑 conversion；本報告不取代逐頁語意裁定或 V1 變動根因檢查。
