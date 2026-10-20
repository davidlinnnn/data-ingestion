# PaddleOCR-VL → Docling：零推論接合結論

2026-10-20。**檔案與資產接合可行；原封不動使用 Paddle 官方輸出＋Docling importer，尚不能滿足 #84 的完整必要交付。** 主要未通過項目是跨頁表格的資料／來源保真，以及部分 Markdown 內容與衍生資料分離。這是輸出與後處理契約的結論，不是 Paddle 模型準度不合格的結論。

## 實際執行範圍

這輪使用手寫的正確 provider protocol controls，建構真正、未修改的 `PaddleOCRVLResult`，執行 JSON／Markdown 存檔、官方純後處理及 Docling 匯入，再實際搬移資產目錄與讀回。**沒有呼叫完整推論 pipeline constructor、模型 factory、predict 或 API，也沒有權重下載。** 因此不把這輪稱為「已跑通 Paddle 完整模型流程」。

| 元件／操作 | 固定身分與設定 |
|---|---|
| Paddle 結果／輸出／純後處理 | PaddleX 3.7.2；官方 `PaddleOCRVLBlock`／`PaddleOCRVLResult`、`save_to_json`／`save_to_markdown` |
| 官方跨頁後處理 | 真正 `_PaddleOCRVLPipeline.restructure_pages`／`concatenate_markdown_pages` 的 unbound method，`self=None`；未抽取 AST 或替換 SDK |
| Docling 接合 | docling-slim 2.132.0、Core 2.99.0；官方 `parse_paddleocr_vl_result`；importer 與官方 2.140.0 逐 byte 相同 |
| 出版設定 | `pretty=False`、`show_formula_number=True`；image OCR=False、chart recognition=True；`format_block_content=False`；不忽略任何 label |
| 測試資料 | 合成四頁 PDF 的實體第 3／4 頁，實際 PyPdfium 144dpi 渲染；兩頁尺寸不同、相同 bbox 但不同圖片；orientation=False、unwarp=False |
| 環境變更 | 獨立 `/private/tmp` venv 安裝鎖定的 PaddleX client／export dependencies；保留 pip receipt 與完整 lock；未變更既有 Docling runtime，未安裝 Paddle 推論 engine |
| 網路與推論 | 行為 worker 禁止 socket 連線；兩個 probe 都沒有網路嘗試；task cache 沒有模型權重。套件安裝本身使用 PyPI 網路，不在此零網路宣稱內 |

實驗事前凍結 [plan](plan.md)、[fixture](fixture.json)、腳本及來源 hash：[registration](registration.json)。本輪不是統計準度樣本，也不是實際模型的 response；合成圖只驗證幾何／資產輸出。

## 四項判定

| 交付項目 | 實測結果 | 判定與界線 |
|---|---|---|
| 座標 | importer 保留 processed-image pixels、頁面尺寸及原實體頁 3／4。明確的 144dpi 無旋轉映射將 `[100,100,220,220]` 轉為原 PDF top-left points `[50,50,110,110]`；負座標、超出頁面範圍被拒絕 | **可接合，須來源 ledger。** 不可把 processed pixels 當 PDF points。實際 Paddle renderer、旋轉／unwarp 反變換、字元／cell 精細 bbox 未驗 |
| 圖片 | 原生 JSON 不含圖片 bytes；兩頁同 bbox 原生檔名相同，在共享輸出目錄確實覆寫。只調整 export view 的逐頁資產路徑後，保留兩張不同圖片，整包實際搬移、hash 讀回通過；缺圖與錯 revision 被拒絕 | **一般封裝工程可解。** 原始 serialization 不變；`document:revision:page:block` 是 identity，hash 僅作完整性。native JPEG 是已編碼交付資產，未宣稱與來源 PNG crop 逐像素相同；完整 caption／OCR／chart supplement ownership 尚未建成 |
| 多頁 | 逐頁匯入可行；public `DoclingDocument.concatenate` 把頁 3／4 改為 1／2，需來源對應。Paddle 拼接 payload `page_index=None` 被 importer 明確拒絕；官方表格 merge 有有效正控制與兩個失敗負控制 | **物理頁組裝可行；完整跨頁語意未通過。** 不能把串接頁面等同正確續表／續段或完整 provenance |
| 主 Markdown | native 保留來源 caption、已帶 fence 的 code literals、正文內 inline math 的原字串、帶式號 display formula，以及 HTML 表格 rowspan／colspan。plain algorithm 在 CommonMark render 遺失 `<tag>` literal／必要縮排；stock Docling 的 fenced code 被 escape 改變。chart 衍生資料進 native 正文；stock 主文含 image OCR 與 chart 衍生文字 | **部分通過，完整契約未通過。** 需保留 native MD 與 stock MD 的不同身分；code serialization、來源家具／supplement 分離是待處理 exporter policy，不能把來源 raw 中有內容當作主 MD 已忠實交付 |

圖片測試刻意在 image block 放入非空衍生內容，即使 image OCR=False，也用來測 importer 如何處理既有內容；**不表示模型在該開關下會產生 image OCR**。

## 跨頁表格：反例與根因

三個案例都呼叫未修改的官方 `restructure_pages(merge_tables=True,relevel_titles=False,concatenate_pages=False)`；不是本專案新增 merge 規則。

| 控制 | 輸入 | 實際輸出 |
|---|---|---|
| 正控制 | 兩頁相同 A/B 表頭，資料 `(a,1)`、`(b,2)` | 合成一表，重複表頭移除，兩筆資料保留 |
| 合法重複資料負控制 | 兩頁相同 A/B 表頭，**各有一筆合法 `(a,1)` 觀察** | 只剩一筆 `(a,1)`；資料 multiplicity 被改變 |
| 不相關表格負控制 | fixture 指定獨立的 A/B 與 C/D 表，寬度／欄數相同 | 仍合成一表，C/D 被併入前表 |

官方續表候選以頁尾／頁首 table、寬度差、欄數／span 等條件判定；沒有內容主題或來源表身分的保證。重複表頭偵測比較前幾列文字與 colspan，沒有區分 `<td>` 的資料角色，造成第二個反例。第三例證明**本例不相關表未被阻止**，不推論所有換表頭的表都必然不該續接。[官方固定版本實作與使用契約](official-contract.md)

merge 把 HTML 放到第一頁 block，第二頁 block content 留空；兩頁 bbox／group link 留著，沒有 row/cell 對雙頁的來源分配。後續官方 Docling importer 拒絕空 table；第一頁成功匯入的 merged table 也只有第一頁 provenance。單純略過空 block 不能恢復資料列來源或被刪資料。

關閉 `merge_tables` 可以避開這段 merge，代價是仍交付逐頁 fragments，不能宣稱達到既有「同一邏輯跨頁表＋正確來源」要求。這輪不建立自訂續表／去重／內容修復演算法。[完整正負控制](paddle/table-controls.json)、[匯入結果](docling/results.json)

## Markdown 與來源關係的實際界線

原生 algorithm handler 原樣交付字串。下列正確 code 若沒有 fence，Markdown source 雖保留所有字元，真正 CommonMark renderer 仍將 `#` 當標題、`<tag>` 當 HTML，且不保留 code 所需的縮排：

```python
# source comment
if x_i < y_j:
    return "$5 & <tag>"
```

同一段已帶 fence 的 native control 可正確交付；stock Docling serializer 會修改 fence 內 literals。因此失敗依據是實際內容／語意變化，**不是強制某種 backtick 或 CodeItem 型別**。若後續加入按既有 algorithm label 正確序列化 code，屬 exporter 工程；本輪沒有默默加入。

已在正文內的 inline formula 與 literal `$5` 原字串可保留；分成 text／inline_formula／text 的 control 則沒有恢復正文插入關係，官方 postprocess 還分別賦予 global_group_id。原 local group 仍在 raw，可追溯，但不等同已交付連續正文。未測上游模型輸出 normalization 對 `\(...\)`、`\[...\]` 與 literal `$` 的處理，也未執行數學 typesetter。

跨頁段落的兩個 fragment 都保留。沒有產生某個精確 joined string **不構成語意失敗證據**；官方 concatenate 僅串接頁 Markdown，沒有建立 logical continuation relation。完整續段能力仍未證實，不把這例列為模型漏段。

image OCR、chart 解讀可原樣保留在 supplementary artifact，並透過同 revision 的 image key 查找。當前測試只證明 raw／asset identity 的基礎，不代表 supplement schema 已實作完成。分離已標記的衍生欄位、家具和資產路徑屬一般 export policy；推測 inline ownership、跨頁表語意與細粒度來源則是另一層方法工程。

## 評讀更正與證據完整性

原始 probe／結果全部保留；新增 [adjudication](adjudication.json) 與 [獨立覆核](independent-review.md)。兩個診斷誤判已修正：

1. stock Markdown 轉義 underscores，原始字串搜尋沒找到 marker；實際 rendered visible text **同時包含衍生 image OCR 與 chart data**。
2. 公式精確搜尋期待無式號的 `$$E = mc^2$$`，實際為正確的 `$$E = mc^2 \tag*{(7)}$$`。本例 delimiter／式號保留成功；本 fixture 沒有另測「無式號 bare formula」。

Paddle live 與 saved-dict postprocess 也不等價：saved-dict 分支移除 code 開頭 `# ` 並沒有圖片 bytes；live control 保留原 code comment。因此需在任何 mutable restructuring **之前**封存原始逐頁 JSON／資產，不能以 saved-dict 重建當作無損 live replay。原始頁序列化在 export view 封裝後保持不變。

## 收斂決策

**在「不新增語意續接演算法、維持全部必含要求」的條件下，這條 stock 完整交付路徑為 NO-GO。** 座標／圖片／來源包裝已證明可行，不需要再為它們開一輪模型候選。code 與 supplement export 可用有限通用工程改善；真正不能靠路徑／JSON mapping 解掉的是跨頁表的資料保真、語意歸屬與來源。

這不排除 PaddleOCR-VL 完整流程作為 layout／區塊辨識／讀序的候選。若下一步只要回答「能否改善目前雙欄 OCR」，可以另做固定頁集合的有限推論比較，並把本輪交付缺口明列為未解；不能因此宣告 #84 全方法合格。本輪依停止條件完成，不自動下載模型、增加新候選或開始推論。

未驗：真實 Paddle 模型／實際 renderer 輸入、雙欄辨識準度、真實跨頁資料集、GPU、延遲、tokens／成本及高頻 ingest；合成 controls 不提供這些結論。沒有 production code 變更、commit、push 或 GitHub 發佈。

## 重現與檔案

- 初始完整 Result probe：[paddle_probe.py](paddle_probe.py) → [paddle/results.json](paddle/results.json)
- 官方匯入／render probe：[docling_probe.py](docling_probe.py) → [docling/results.json](docling/results.json)
- 判讀 assertions：[adjudicate.py](adjudicate.py)；以既有 Docling venv `python -B` 執行，不重跑模型或改原結果。
- 可攜資產包：[document.md](paddle/relocated-bundle/document.md)、[assets.json](paddle/relocated-bundle/assets.json)、[integrity.json](paddle/relocated-bundle/integrity.json)
- 座標來源：[source-geometry.json](source-geometry.json)、[source-ledger.json](docling/source-ledger.json)
- [resolver receipt](install-report.json)、[client lock](paddlex-client-lock.txt)、[runtime check](runtime-check.json)
- 全目錄交付 hash：[artifact-seal.json](artifact-seal.json)；不含 manifest 本身，包含本報告及原始診斷。

官方來源：[PaddleX 3.7.2 Result](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/result.py)、[官方 pipeline／postprocess](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py)、[Docling importer](https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/utils/paddleocr_vl_utils.py)。更完整的逐項來源見 [official-contract.md](official-contract.md)。
