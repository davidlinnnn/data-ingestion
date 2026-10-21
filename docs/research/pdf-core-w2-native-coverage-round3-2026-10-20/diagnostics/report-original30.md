# W2 原生圖框文字／serializer 零推論診斷（先完成原 30 篇）

目前可評估的是 30 篇成功輸出的 499 頁；另 6 篇 216 頁缺 conversion output，明確標 `MISSING_RESULT_NOT_ZERO`，尚不能當成全 715 頁結果。

在 167 個 picture 中，117 個框含至少 30 個 PDFium 原生非空白字元（70.1%），涉及 99 頁／29 篇。117／117 已有至少 30 字元的 native descendant text；僅 8／117 能在預設 Markdown 找到至少一個 ≥30 字元的完整 child text。這是字層存在與交付映射的頻率，**不是抽取正確率或全字語意覆蓋率**。圖內 233 個 ≥30 字元 text nodes，只有 18 個 normalized 全文能在 MD 找到；相同文字在文件別處出現仍可能命中，因此這是 MD presence，不證明正確圖文位置。

| family | 篇／頁 | picture | 框內原生字 ≥30 | 涉及篇／頁 | 已有 ≥30 native child | 有 ≥30 child 出現在 MD |
|---|---:|---:|---:|---:|---:|---:|
| ACL/EMNLP | 5／86 | 31 | 20 | 5／13 | 20 | 2 |
| ACM sigconf | 2／20 | 12 | 8 | 2／7 | 8 | 0 |
| CVPR/AAAI | 2／22 | 12 | 12 | 2／11 | 12 | 0 |
| ICML | 2／21 | 15 | 12 | 2／9 | 12 | 0 |
| IEEE conference | 2／10 | 6 | 4 | 2／3 | 4 | 0 |
| NeurIPS/ICLR | 7／145 | 32 | 27 | 6／23 | 27 | 4 |
| Pilot-other/unknown | 4／112 | 37 | 21 | 4／20 | 21 | 2 |
| Springer LNCS | 2／20 | 8 | 5 | 2／5 | 5 | 0 |
| general arXiv | 2／24 | 7 | 2 | 2／2 | 2 | 0 |
| general arXiv（article，template uncertain） | 2／39 | 7 | 6 | 2／6 | 6 | 0 |
| 合計（已成功部分） | 30／499 | 167 | 117 | 29／99 | 117 | 8 |

## 透明幾何方法

以原 PDF 的 PDFium textpage char index 與 `get_charbox` 逐字比對保存的 picture provenance bbox，統一為 BOTTOMLEFT PDF points。非空白 Unicode 字元的 ink bbox 至少 50% 面積落在 picture 內即計入；另保存全 bbox containment（≥1−10⁻⁶）字數供敏感度檢查。≥30 門檻只定義本次觀察頻率，不是通過門檻。UTF-16 surrogate pair 合併後仍保留 raw PDFium index，每頁 normalized 字流與整頁 text range 相等才接受。

native children 以 picture graph 遞迴收集 text node，排除 caption／footnote，不使用 Docling 輸出決定 PDFium 字元是否在框內。保存 `text`、`orig`、list marker、各種字數；MD presence 以 NFKD/casefold/alnum 的整個 child text exact substring 判斷。bbox 可能與正文疊合；「已有字」不證明字序、數值、標籤、全字語意都正確，頻率不可直接升格 Q4 結論。將判定改成嚴格全字框 containment 後，≥30 圖框仍為 117，未改變本次總頻率。[程式](picture_text_inventory.py)、[逐圖完整資料](picture-text-original30-with-orig.json)、[統計](original30-summary.json)。

## Prompt 附錄的責任分流

SICA P07 p12 的 `#/pictures/4`：PDFium 原生字 1,238，native child text／orig 皆 1,238；`#/pictures/5`：PDFium 1,488，native text 1,439，但 native orig 1,488，差額是被存入 marker／orig 的清單編號。兩者 substantial child 都未出現在預設 MD。這兩個 prompt boxes 主要歸 **#81 交付映射**，不能說抽取漏了整段提示或 49 字元。清單層級與 label 錯誤則是獨立問題。

本次 ≥30 圖框中沒有「native children 少於 30 字元」案例；這不排除部分字元抽取損失。後續如補跑資料發現無 children／稀疏 children，才列為抽取遺失候選並對原頁核對。

官方預設 `MarkdownPictureSerializer` 序列化 caption、annotation、image 及 chart table，但沒有遍歷普通 picture text children，因此 native graph 保留字、MD 不交付可同時成立。[固定版本官方 source](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:872>)。

## Colspan 重複：固定版本 serializer 行為

以官方 `DoclingDocument`／`TableData` 建立 2×2 synthetic table：第二列只有一個 colspan=2 的 cell，文字 `Only buy black work shoes below $50.00, size 10.`。沒有模型或 conversion；斷言結果如下：native table_cells 一次、grid 兩次、Markdown 兩次、HTML 一次且保留 `colspan="2"`。native 抽取輸入本來正確，這是 **#81 delivery／serialization**，不歸抽取。[native JSON](synthetic-colspan-native.json)、[Markdown](synthetic-colspan.md)、[HTML](synthetic-colspan.html)、[斷言結果](synthetic-colspan-result.json)、[重現程式](serializer_colspan_check.py)。

原因是官方 grid 將同一 spanning cell 放入每個覆蓋格；Markdown renderer 對每格讀 `.text`，GFM pipe table 無 colspan；HTML renderer 只在 span 的起始座標輸出一次，並加 colspan 屬性。[官方 grid](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/types/doc/items/table/table_data.py:111>)、[官方 Markdown](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:819>)、[官方 HTML](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/html.py:398>)。此證據亦支持 SkillRL P05 p22 的同型 colspan task 重複定位，不能靠移除一份「看起來重複」的文字改 PDF 抽取。

## Caption／algorithm stage 證據

沿用同一 S0 保存輸出的 exact zero-inference traces，SHA 與各欄結構／Markdown equality 已逐一核對，未重跑 conversion。[證據索引](caption-algorithm-stage-evidence.json)。ImageTransformer p5、WikiSkill P01 p8、SEAL P17 p4 的 caption／algorithm 原始 layout 就標 text，之後官方 paragraph merges 將它們接進正文；不是預設 MD 單獨造成的問題。P14 p15 caption 獨立成 text，則屬 label 分離問題，不能誇成正文混段。新增六篇的案例待輸出後再評。

## Egret medium 本機完整性

官方 preset `DOCLING_LAYOUT_EGRET_MEDIUM` 指向 `docling-project/docling-layout-egret-medium`，預設 revision main；本機固定 snapshot 是 `77ede7cc7bed96d853c58f319734803d6ea2ea5c`，artifact 位於 `/private/tmp/pdf-core-native-20261017/artifacts/docling-project--docling-layout-egret-medium`。config、preprocessor、model.safetensors 均存在，模型檔 78,311,396 bytes，SHA256 `e7fc5b9a353826c123c5d03efc230909ac02b93e26293ec7cb4db8978fe9e3af`。只讀 safetensors JSON header 確認 1,009 tensors 的 data_end 符合檔案大小；未載 tensor、未做 runtime 相容性或推論測試。[完整 resolved paths／SHA](egret-medium-local.json)、[官方 preset](</private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/datamodel/layout_model_specs.py:94>)。

零下載、零 API／VLM、零 rendering、零 conversion；六篇缺輸出尚未當成零，待主線通知再補統計。
