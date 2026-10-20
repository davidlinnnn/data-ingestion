# Table HTML 接合：固定版來源筆記

2026-10-17。僅核對已安裝 Docling2.132／Core2.99 原始碼與既有研究文字／G1登錄；沒有推論、安裝、讀 PDF／圖片或開啟 holdout。本筆記支持下一輪規劃，不代表接點已實測通過。

## 可重用的官方路徑

`DocumentConverter.convert_string(content, format=InputFormat.HTML)` 是公開入口，將字串包成 DocumentStream 後走正常 conversion。HTML backend 的 `parse_table_data` 直接建立公開 `TableData`／`TableCell`，承載文字、rowspan／colspan、offsets及header flags。因此可先驗「VLM回傳table HTML → 官方HTML backend → 公開Core表格 → stock Markdown」，不用另造一套完整cell座標協定。[Docling2.132 converter](https://github.com/docling-project/docling/blob/v2.132.0/docling/document_converter.py)、[HTML backend](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/html_backend.py)

本機實際讀取位置為 `/private/tmp/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/` 下上述檔案；公開網址供重查，未以未讀到的網頁內容增加主張。這是PDF主幹輸出後的研究接合，不是官方PDF pipeline內建API table stage。

研究主代理另已檢查此S0 runtime的 `importlib.find_spec('bs4')` 為False；因此目前不能稱HTML backend已可直接import／執行。本輪若獲准執行，需先在research runtime補齊必要 `format-html` 依賴、保存前後lock，再做零模型gate；不以自製parser繞過官方接點。此處只轉記已觀測的缺件，沒有新增import成功證據。

## 必須先驗的限制

- HTML backend會unwrap `thead`／`tbody`，依整行 `th`／`td` 與span推斷header，不能假設完整HTML `scope` 語義會保留。空字串cell仍建立，但文字會strip邊界空白。
- `_get_cell_spans` 將缺少／無效／零span回退為1，過大span會clamp；後續也依table範圍clamp。因此conversion成功不等於來源結構正確，不可默默接受模型輸出的非法結構。
- `<`／`&` 等來源literal需正確HTML entity逃逸；未逃逸字串可能被當作tag。合成控制應含空白／重複header、多層header、rowspan／colspan、雙列維度及`&lt;s&gt;`等literal。
- Core2.99 stock Markdown把多層header合成一列，逐欄以 ` - ` 連接；相鄰相同header文字會去重，即使來自不同header層。GFM沒有spans，必須另外驗證主要Markdown中的條件與關係仍可解讀，不能只驗typed cells。[Core2.99 Markdown serializer](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)

若合成gate必須靠private backend修補、案例專用補字或另寫renderer才能通過，停止該表示路徑，保留具體阻礙；不要將它擴成通用HTML修復器。

## 有界開發覆蓋

依既有[凍結G1登錄](../fixtures/pdf-core-g1-2026-10-14/cases.json)，單頁表格可固定如下四頁；合計470個數值綁定、23項關鍵比較，逐表套原門檻，不以合併分母稀釋失敗。

| 案例 | 來源頁 | 數值綁定 | 關鍵比較 |
|---|---|---:|---:|
| G1-T01 | Memory-R1 p8 | 6 | 3 |
| G1-T02 | SkillOpt p8 | 84 | 8 |
| G1-T04 | paper09 Table6 p17 | 300 | 5 |
| G1-T05 | WikiSkill p13 | 80 | 7 |

T01／T02已登錄同版S0 baseline與144dpi圖，可核對hash後重用；其餘頁面不能未查證就稱為同版cached。各頁仍需處理全部native table targets，附帶表格不擴大以上oracle分母。

完整五個G1邏輯表共七個來源頁；排除的G1-T03位於paper06 p27–29，另有264數值與7比較。現[mapper](pdf-core-table-delivery-2026-10-17/mapper.py)明確拒絕多頁provenance，故跨頁T03需要獨立gate，不能隱含在本輪HTML表示驗證中宣稱完成。
