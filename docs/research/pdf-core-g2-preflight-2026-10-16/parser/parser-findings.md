# DOTS 原生 parser／Markdown：零推論 preflight

2026-10-16（Asia/Taipei）。依 [PDF-core 審查](../../../reviews/pdf-core-experiment-audit-2026-10-16.md) 的分層要求，固定 Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3，直接執行已安裝的官方 `parse_dots_json`、`DoclingDocument` 與 Markdown serializer。**現有 public options 無法同時修正重複公式定界符及已被 HTML parser 改義的 inline code。** 這是此版本原生 mapping／export 的界線，不能推成模型不會讀公式或 code。

沒有載入 GPU／模型、import MLX／Torch／Transformers、網路呼叫、PDF／holdout 讀取、套件修改、舊 raw 修補或 production 變更。四份原始 raw 與五份 installed source 在執行前後 hash 相符；完整舊 evidence 的核對由上層 compare-only checker 負責。

## 固定方法與可重現輸出

[registration.json](registration.json) 在 parser 測試前登記 [16 個自寫來源控制](inputs.json)、七組全域設定、四份舊 raw 身分、runtime／source hashes。合成 source 是輸入的真值，沒有從舊模型答案反推預期字串。七組為 stock、僅關 underscore escaping、僅關 HTML escaping、兩者皆關、兩者皆關＋compact tables、兩者皆關＋`format_code_blocks=False`、兩者皆關＋embedded images。

每例保存 raw、實際 `DoclingDocument` prediction 與七份 Markdown；部分普通文字／code 負例另保存 Marko 2.2.4 的實際 HTML。[run/results.json](run/results.json) 記錄原始字串／typed 結構檢查；[delivery-assessment.json](delivery-assessment.json) 另分 exact Markdown 與渲染後 literal 保真，避免把 Markdown 字串不同當成內容錯誤、或把 raw 字串相同當成可見內容保留。後者的 visible-text assertions 是首次 run 後補的評分核對，**不冒稱獨立 preregistered validation**，輸入及輸出均未更動。

首次 run 已完成所有 parser／export 控制與 raw replay，但 direct-model 對照的段落 spacing assertion 期待單空白，官方 inline group 輸出雙空白而停止；code literal 本身正確。保留 [原 runner](preflight-attempt01.py)、[原登記](registration-attempt01.json)、[全部首次輸出](run-attempt01/) 與 [failure record](attempt01-failure.json)。第二次只將該 assertion 改成核對完整 code block 與 exact inline code literal；16 inputs hashes 與七設定一致。第二次成功退出，沒有重試模型或挑答案。

```sh
# 已執行；輸出存在時拒絕覆寫，不刷新期待值。
rtk /private/tmp/pdf-core-g2-dots-mlx-20261016/venv/bin/python \
  docs/research/pdf-core-g2-preflight-2026-10-16/parser/preflight.py register
rtk /private/tmp/pdf-core-g2-dots-mlx-20261016/venv/bin/python \
  docs/research/pdf-core-g2-preflight-2026-10-16/parser/preflight.py run
rtk /private/tmp/pdf-core-g2-dots-mlx-20261016/venv/bin/python \
  docs/research/pdf-core-g2-preflight-2026-10-16/parser/assess_delivery.py
```

## 內容、原生結構與 Markdown 分開看

| 固定控制 | 官方 parser／JSON | Markdown 與可用設定 |
|---|---|---|
| Bare `Formula` LaTeX：`p(y_{<s})`、sum、index、tag | exact 字串保留 | stock 正確加一對 `$$`；七設定皆符合控制的交付字串。沒有測數學 renderer。 |
| `Formula.text` 已含 `$...$`／`$$...$$` | exact raw 字串保留；不算數學內容辨識錯 | 七設定皆再加 `$$`，不符合單一外層 display delimiter 契約。沒有既有參數能指定「已包定界符」。[wrapped prediction](run/formula-display-wrapped/prediction.json)／[Markdown](run/formula-display-wrapped/native-markdown.md) |
| 段落內 LaTeX＋`items[i] <= limit` | exact 單一 Text 保留 | 同時 `escape_underscores=False, escape_html=False` 才保留本控制的 raw Markdown。僅關一個仍失敗；這是一般設定可修的序列化差異。[控制](run/inline-math-code/native-markdown.md) |
| `<s` 的兩種邊界 | `p(y_{<s})` 保留；合法 TeX 關係 `a<s>0` 被當 `<s>` HTML，內容已改；inline 控制還有後文缺損 | 七設定不能恢復已遺失的 `s`。**不是所有 `<s` 都截斷**，而是與 recognized HTML tag 形狀衝突。[bare](run/formula-bare/native-markdown.md)／[collision](run/formula-less-s-tag/native-markdown.md)／[inline collision](run/inline-less-s-tag/native-markdown.md) |
| Fenced Python：literal `<b>bold</b>`、`<s>strike</s>`、縮排、`user_id`、`under_score`、`<=` | exact CodeItem 保留 | stock 與正常 flags 全部保留完整 block；關 `format_code_blocks` 則失去 code block 表示。fence 路徑在 HTML 判斷前執行。[完整 block](run/fenced-html-code/stock.md) |
| 合法 Markdown code span：`<b>bold</b>` | parser 先把 b-tag 當格式，變成 bold 的文字內容，literal tag 已遺失 | 七設定都失敗；Marko 可見 code 是 `**bold**`。`escape_html=False` 不能重建原 tag。[raw](run/inline-html-code/raw.txt)／[JSON](run/inline-html-code/prediction.json)／[render](run/inline-html-code/native-markdown.html) |
| Unknown tag 的 code span：`<widget>` | exact Text 保留 | 關 HTML escaping 後可保留；證明 recognized HTML tag 缺口不等於所有 angle brackets 都無法交付。 |
| 合法 HTML code：`<code>&lt;b&gt;bold&lt;/b&gt;</code>` | 產生 exact `<b>bold</b>` CodeItem | stock 也能保留 literal code。這是另行登記的 raw 表示，**沒有把失敗 raw 改成此形式**。[prediction](run/html-code-semantic/prediction.json)／[render](run/html-code-semantic/stock.html) |
| Ordinary HTML：bold、H sub 2 O、x super 2 | `formatting.script=sub/super` 留在 JSON | stock／七設定皆攤成 `H 2 O`、`x 2`；不能把 JSON 存在當成 Markdown LaTeX／subscript 已交付。[JSON](run/ordinary-html/prediction.json)／[Markdown](run/ordinary-html/native-markdown.md) |
| Table：rowspan Method、colspan Score、兩層 header | TableData 保留 span、位置、數值及第一層 header；裸 `<th>` 第二列的 Train／Test 沒有 column_header role。另行登記的 explicit thead／scope 控制則完整保留所有 cell 位置／spans／header roles | stock／compact pipe table 重複 Method／Score 並攤平 header；沒有 colspan／rowspan。JSON 補充結構仍須檢查角色，不以文字存在代替。[初始 JSON](run/merged-table/prediction.json)／[Markdown](run/merged-table/native-markdown.md)／[追加控制](header-controls/results.json) |
| Picture＋caption | crop 200×200 pixels、caption ref、page 3 bbox 存在；picture 的自身 image 欄位為空，crop 由 page image 取得 | stock 為 placeholder；public `image_mode="embedded"` 交付實際 PNG data URI 與 caption，這項可用一般設定完成。[native crop](run/picture-caption/native-crop.png)／[embedded](run/picture-caption/native-embedded.md) |

另用 public `DoclingDocument.add_code()` 建立相同 exact block 與 typed inline code；[JSON](run/typed-code-controls.json)／[Markdown](run/typed-code-controls.md) 通過。這證明 document model／code serializer 能承載內容，缺口在 DOTS Text 的字面表示判讀，不能以此對照宣稱 parser 原案已修好。

初始 table 的 content check 只涵蓋文字、span 與第一層 header，不代表第二層 native 角色通過。檢視後另在執行前固定 [header-control-registration.json](header-control-registration.json)，以兩份不同的合成 source（explicit `<thead>` 或 `scope="col"`）測相同邏輯表；[header_controls.py](header_controls.py) 對全部七 cells 的 row／column／spans／header role 作精確相等檢查並通過。原始裸 `<th>` 控制及舊 raw 均未修改。這證明支援明確 HTML roles，不能宣稱有參數能替既存輸出補角色。

每個已存在 provenance 的 page_no 都為 3；提供 1120×1680 model size、560×840 page size 時縮放正常。但 HTML 拆分產生的後續 inline children 沒有自身 provenance，例如 ordinary HTML 的六個 child、inline code 的兩個 child。不能用 `all(existing_prov)` 代替「所有內容皆有來源位置」。合成 bbox 本來由本測試指定，不是實際來源定位準度測試。

## 普通文字負例：全域 flags 不是自動保真保證

| 自寫 source 的意圖 | stock 的實際可見文字 | 兩個 escaping flags 都關的實際可見文字 |
|---|---|---|
| 普通 `task-specific`／`under_score_name`／ReflACT／`3 < 4` | 保留（即使 Markdown source 被 escape） | 保留 |
| 已正確 Markdown escape 的 literal `__init__`、`_TEMP_`、`<widget>` | entity 被雙重 escape，顯示 `&lt;widget&gt;` | 所有 literal 保留 |
| 未 escape、意圖 literal 的 `__init__`、`_TEMP_`、`<widget>` | literal 保留 | 變成 bold／italic，底線及 tag 不再可見；exact raw Markdown equality 仍是 true，不能算表示保真 |

因此兩個 flags 都關適用於「provider 已交付合法 Markdown」的候選契約，不能直接套在任意純文字 item。這些是合成邊界控制，不是對 dots 模型在文件上出現比例的估計；沒有加逐字串 escape／entity／tag 修補。[全部 rendered assessment](delivery-assessment.json)

## 重放四份原始 saved raw

不讀原 PDF，使用同一份已登記 raw，搭配明示的合成 page image／geometry 以隔離 parser／export。這些 prediction 的 bbox／image **不可當原文件 provenance 證據**，也不重新評分來源內容。

| 原 raw | parser／七設定效果 |
|---|---|
| controls-p1 | strict JSON valid，16 texts；三份 Formula.text 已有外層 `$$`。七設定都留下六處 `$$$$`（每公式兩端各一），fenced code 的原內容保留。 |
| seal-p4 | strict JSON valid，43 texts；四份 wrapped Formula.text。七設定都留下八處 `$$$$`；HTML sub/sup 的原生拆分仍存在，flags 不會變出所需 LaTeX。 |
| wikiskill-p22 | strict JSON valid，9 texts／1 table；wrapped formula 七設定皆有兩處 `$$$$`。 |
| dgm-p51 | strict JSON invalid escape；官方 parser 回傳 0 texts／tables／pictures，七份 Markdown 為空。export flags 不會修復 invalid JSON，更不會恢復識別字。 |

[逐份 replay 紀錄](run/results.json) 保存原路徑及 SHA；[所有新輸出](run/) 保留四份 exact raw 副本。沒有改動舊評分、舊 Markdown、原 parser 或任何舊 manifest。

## 官方接點與下一個候選的必要界線

本次另外由獨立 agent 作唯讀 source review，結論與執行一致：

- [`parse_dots_json` signature:96](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling/utils/dots_utils.py:96) 只有 source geometry／image 等參數；[HTML detector:53](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling/utils/dots_utils.py:53)、[fence／HTML 分支:233](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling/utils/dots_utils.py:233) 決定原文字面是否被轉成 HTML。
- [`MarkdownParams:215`](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:215) 無 formula delimiter 選項；[`FormulaItem` wrapping:420](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:420) 固定再加定界符；[`format_code_blocks`:411](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:411) 只影響已存在的 CodeItem。
- [HTML inline runs:298](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling/utils/chandra_utils.py:298) 解析 HTML 格式並為 sub/sup 設 script；[Markdown 的 inherited script hooks:615](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/common.py:615) 直接回傳文字。[Markdown table limitations:692](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:692) 明示單層 header／無 spans。
- [HTML table role mapping:246](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling/utils/chandra_utils.py:246) 僅把 scope=col 或第一列／thead 中的 th 標成 column header；這解釋本次裸第二列 th 與 explicit thead／scope 的差異。
- Public [serializer injection:1219](/private/tmp/pdf-core-g2-dots-mlx-20261016/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:1219) 允許自訂 `text_serializer`／`table_serializer`。這需要新實作與驗證，並非已存在的參數；而且 serializer 無法恢復 parser 已刪掉的 literal code。本輪沒有實作它、升級 runtime 或測 newer release，故不宣稱新版行為。

下一候選應在推論前明確固定「bare Formula LaTeX 或自帶 delimiter 的輸出契約」，並證明必要公式／literal code 會經過保真的原生 mapping。若候選沿用此 DOTS mapping，不能把全域 escaping flags、改 prompt 要求模型碰巧換表示、或 typed document 的正例當成現有兩個 blocker 已解。必要的 merged table／script／image 亦須有可交付的原生補充結構或正式投影方法；只看到 Markdown 中有字、有數字不足以通過。

略過模型／PDF／數學 renderer／新版 runtime／正式同版 handoff；本結果只界定此 pinned parser／serializer 的能力與缺口，不是新候選品質或整體 G2 通過證據。
