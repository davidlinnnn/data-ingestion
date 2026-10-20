# 官方 HTML 表格接點：A gate 執行結果

2026-10-17。已執行[確認計畫](pdf-core-table-html-plan-2026-10-17.md)的A階段。**固定HTML backend→TableData→stock Markdown配置未通過：row group被提升為全表column header，且正確HTML escaping的literal在主要Markdown渲染時仍可被當tag吃掉。依預定停止條件，B階段四頁API比較沒有啟動。**

這是官方表示／parser／serializer組合的限制證據，不是VLM準度失敗。模型推論0次、API requests0次；未讀論文／圖片／G1答案、未開holdout／Paddle、未新增S0頁面或修改production。沒有為這次結果換模型、調prompt、補內容或改SDK。

## 固定環境與實際接線

| 項目 | 實際執行 |
|---|---|
| SDK | 既有research runtime：Docling-slim2.132／Core2.99；原80個installed distributions及所讀SDK來源hash未變 |
| 最小依賴 | 只安裝到`/private/tmp/pdf-core-table-html-20261017/deps`，以PYTHONPATH引入；beautifulsoup4 4.15.0、soupsieve3.0.3、typing-extensions4.16.0（與原環境同版），不修改原venv |
| 公開入口 | `DocumentConverter(allowed_formats=[InputFormat.HTML]).convert_string(..., InputFormat.HTML)`；HTML匯入，不跑Standard或VlmPipeline推論 |
| 來源重綁 | 公開TableItem／insert／append／delete操作，將匯入TableData放進合成PDF文件的原table位置，保留原caption及table-envelope provenance |
| 交付 | 原生JSON保存／reload及stock `export_to_markdown()`；另外以既有markdown-it-py的CommonMark＋table支援檢查實際渲染，不自訂renderer |
| 控制 | 一次依賴安裝後smoke conversion；固定8個正向合成案例、2個無效輸入探針，一次執行，無內容修正／迭代搜尋 |

[probe](pdf-core-table-html-2026-10-17/probe.py)、[固定登錄／來源hash](pdf-core-table-html-2026-10-17/registration.json)、[完整機械檢查](pdf-core-table-html-2026-10-17/verification.json)、[語義／渲染評讀](pdf-core-table-html-2026-10-17/decision.json)、[依賴lock](pdf-core-table-html-2026-10-17/overlay-lock.txt)均保存。以HF／Transformers offline設定執行，沒有載入模型或下載權重。

## 哪些已可交付

- 普通表：`Method`左欄header與`002.50`的printed precision保留。
- 雙列維度：Component／Setting保持兩個獨立欄位，對應值不合併。
- 多層表頭：正確rowspan／colspan及兩個父表頭下同名Score／Cost保留於typed cells；Markdown展開為`North - Score`、`South - Score`等，可辨別父層條件。
- Rowspan context：跨兩列的Group A維持真實span及後續列關係。
- 同格成對值：`Planned / Actual`、`7 / 4`及`5 / 2`保持共同physical cell與角色順序。
- 所有8個正向案例均完成公開來源重綁、caption保留一次、正文前後順序與typed／Markdown reload一致。但「roundtrip一致」不能讓已損失的語義變正確。

這是合成表示能力，不是論文accuracy。原探針中6/8案例的機械文字檢查通過；加入真實Markdown渲染評讀後，escaped-literal案例也出現交付缺陷，不將機械計數當最終通過率。

## 停止理由一：row group錯掛到全表表頭

輸入是一張Category／Count表，兩個`tbody`內分別以`<th colspan="2" scope="rowgroup">`標示By Device及By Region。Native backend將兩個group都標為column_header，而非保留row-group語義；stock Markdown又把第一個group吃進全表header：

```text
| Category - By Device | Count - By Device |
| Desktop              | 17                |
| Tablet               | 9                 |
| By Region            | By Region         |
| East                 | 12                |
| West                 | 14                |
```

後面的Region資料仍處於帶有By Device的全域表頭下；數字和group文字都存在，不等於條件歸屬正確。**主要停止理由是實際關係／Markdown語義，不是硬性要求某個Docling label或row_section flag。** 見[原輸入](pdf-core-table-html-2026-10-17/row_groups/input.html)、[typed結果](pdf-core-table-html-2026-10-17/row_groups/imported.json)、[實際Markdown](pdf-core-table-html-2026-10-17/row_groups/document.md)。

固定版HTML source會unwrap thead／tbody，依整行th／td推斷column header，未以scope=rowgroup保留這個例子的語義；Core的header flatten再將領先column-header rows合併。另有Docling特定`row_section` class辨識，但本輪未試其dialect變體，也不由此宣稱所有HTML表達法都無解。[HTML backend2.132](https://github.com/docling-project/docling/blob/v2.132.0/docling/backend/html_backend.py)、[Markdown serializer2.99](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/transforms/serializer/markdown.py)

## 停止理由二：typed literal正確，Markdown仍成為HTML tag

輸入cell使用正確的`&lt;s&gt;`；HTML backend及typed TableData都有literal `<s>`，原始Markdown字串也找得到它，但stock table serializer直接輸出未escaped的`<s>`。CommonMark在HTML enabled下將它解讀為HTML tag，實際cell可見文字為空。

同一張表另一cell的`item[i] < limit & ready`仍可見，不能泛稱所有小於號都消失。HTML disabled的reference renderer則能保留`<s>`，所以問題涉及Markdown HTML語義／consumer policy；**不是觀察到Codex UI或所有consumer都必然吞字。** 見[Markdown](pdf-core-table-html-2026-10-17/escaped_literal/document.md)、[CommonMark渲染](pdf-core-table-html-2026-10-17/escaped_literal/rendered-commonmark.html)、[HTML disabled對照](pdf-core-table-html-2026-10-17/escaped_literal/rendered-html-disabled.html)。

固定Core的plain TableCell匯出只處理newline／pipe，未套用一般文字的HTML escaping；並非HTML producer忘記escape，也不能只用raw string包含測試認定交付通過。沒有修改cell文字來修結果，沒有替換serializer。

## 其他差異與負控制

- **缺值字形：**HTML cleanup把em dash `—`改成`-`，導致原字串exact檢查失敗；但真正空白、缺值標記、零值仍有區別，`000.00`精度保留。這是需保留的字形正規化差異，不將它誇大為「缺值內容消失」，也不是獨立material停止理由。
- **無效輸入：**未escape的`<s>`及rowspan=0均得到native success；前者literal消失，後者被normalization。它們只證明conversion成功不能當保真判準，不算正向成功，也沒有藉此改成auto repair。
- **尚未完成：**A在官方匯入／stock交付層已失敗，未再實作完整HTML target-envelope adapter／其漏target與unknown-key測試，也未準備兩個新S0頁面、四頁API請求或470點source scoring。不冒稱全部計畫工作均已執行。

## 去留與維護取捨

**停止這個固定stock HTML接合配置，不進B、不將它採用。** 前輪flat JSON API的90個frozen數值／11比較正面證據維持有效，但其原始左欄header／多維度限制也仍存在，沒有因本次停止而升級成完整候選。

若要繼續同方向，新增維護範圍至少涉及兩個共享接點：HTML row-group語義與plain-table Markdown escaping，均須有跨表格回歸；缺值字形容忍另列。這不是換更大VLM能修的問題。本輪未實作patch，未承諾只改幾行就能安全解決，也未評估所有公開dialect／serializer配置；相關變更需另行形成具體有限方案，不能默默擴張本次驗證。

未驗四頁實際論文、公司Qwen3／CUDA／vLLM、高頻負載或完整Canonical Acceptance；跨頁T03、holdout與Paddle持續未啟動。此結果只否決已測配置，沒有宣稱Docling全部table方法或HTML輸出都不適用。
