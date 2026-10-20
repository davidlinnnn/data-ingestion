# PDF-core 原生模型比較：2026-10-17 執行結果

本輪已完成使用者授權的 [固定計畫](pdf-core-native-round-plan-2026-10-17.md)：**三組各11頁、21個range conversion呼叫、最多33個頁面請求**，沒有推論重跑、換prompt、調threshold或加入修字／parser／continuation。Paddle與六份holdout維持暫停。**G2仍未通過；本輪不推薦直接替換成C1或Egret。**

最有價值的正面結論是：**Docling2.132原生reading-order／assembly已能把四個指定跨頁段落正確續接，並保留兩頁provenance**：WikiSkill357、368，SEAL21、30。這些來源不需要重用失敗的自訂continuation。這不代表所有跨頁段落或全部必要功能已合格。

## 配置與執行

共同Docling-slim2.132.0／Core2.99.0／Parse7.22.3／pypdfium2 5.14.0，顯式PyPdfiumDocumentBackend。來源與順序為controls1→Wiki20–22→SEAL2–4→DGM51→SkillOpt8→NCCU3→scan fixture1；兩個三頁範圍各自連續一次conversion。

| 項目 | C1 | S0 | S1 |
|---|---|---|---|
| Pipeline | VlmPipeline | StandardPdfPipeline | StandardPdfPipeline |
| 主要候選 | Nemotron-Parse2.0 MLX8bit | Heron default | Egret medium |
| revision | e7e89479657fb3631028ac12b6bc0d5a59ceafe4 | 8f39ad3c0b4c58e9c2d2c84a38465abf757272d8 | 77ede7cc7bed96d853c58f319734803d6ea2ea5c |
| 裝置／型別 | Mac Metal；decoder8bit/group64、visionBF16 | CPU FP32、4threads、interop1 | 同S0 |
| 設定 | 官方nemotron_parse_v2 prompt/parser；greedy0、cap9000、batch1；no_text_in_pic | Transformers layout閾值0.3、compile=False；native reading order、separators=True | 只替換layout preset及其官方processor/config |
| OCR | 不另接OCR | selective RapidOCR v6det/rec-small＋v2cls；det/cls/rec=True；bitmap0.05、textscore0.5；ONNX4/1threads | 同S0 |
| 表格 | 原生VLM輸出 | TableFormerV1 accurate、cellmatching=True | 同S0 |
| enrichment | 無額外enrichment | formula/code/picture classification/description/chart/heading hierarchy均off | 同S0 |
| 保留證據 | 公開engine輸入圖/request、公開page VLM raw、typed JSON、stock Markdown | parsed cells、postprocessed layout/table predictions、assembled items、typed JSON、stock Markdown | 同S0 |

輸出images_scale=2；C1輸入也是scale2。Standard layout實際scale1，OCR options scale3；**不能把144dpi輸出當成每個模型的輸入大小**。三組11頁的公開scale2圖像尺寸與像素hash全部一致，見[渲染配對](pdf-core-native-round-2026-10-17/public-render-pairing.json)。完整processor tensor、OCR實際crop與每個forward未捕捉，不補造數據。layout公開predictions已經過postprocessor，沒有私有raw-box hook。

| 執行觀察 | C1 | S0 | S1 |
|---|---:|---:|---:|
| worker總時間，含import/export等 | 230.62秒 | 32.03秒 | 22.61秒 |
| pipeline初始化 | 1.75秒 | 11.29秒 | 1.44秒 |
| control首個conversion | 9.24秒 | 1.32秒 | 1.19秒 |
| 其他6個conversion合計 | 217.39秒 | 17.35秒 | 17.97秒 |
| sampled process-tree RSS peak | 2.43GiB | 4.92GiB | 4.94GiB |
| Metal allocator peak | 3.18GiB | 不適用 | 不適用 |
| native conversion success | 5/7 | 7/7 | 7/7 |

未觸及資源停止線。Metal和RSS不相加，取樣不是整機峰值；S0較長的初始化受到同次環境與cache狀態影響，不能因此宣稱Egret吞吐較快。這是一輪開發集觀察，**不是冷啟動分布、p95、高頻SLO或公司vLLM效能**。[逐range metrics](pdf-core-native-round-2026-10-17/range-metrics.json)保留每次耗時與狀態。Standard公開table predictions共S0=5、S1=6；不冒充forward/crop次數。C1儲存11個公開頁面請求，但批次失敗後不能證明每頁內部generation均完成。

## 原41項契約

[逐項評讀](pdf-core-native-round-2026-10-17/unit-review.json)固定列出三組各41項、對應typed item、原來源區域、實際文字與provenance。這是**交付狀態分布，不是模型accuracy**；尤其S0/S1刻意不開重建enrichment，未實作與辨識錯誤分開。

| 41項交付狀態 | C1 | S0 | S1 |
|---|---:|---:|---:|
| 原必要內容／表示通過 | 13 | 17 | 17 |
| material交付缺陷 | 19 | 7 | 8 |
| 重建enrichment未啟用 | 0 | 17 | 16 |
| runtime failure | 7 | 0 | 0 |
| raw有內容、parser依賴缺失而未交付 | 2 | 0 | 0 |

不可用17/41當Standard模型辨識率，也不可把C1七項runtime失敗當七項OCR錯誤。來源四個保護正例完整交付均僅1/4：DGM E04通過；Wiki362保留opening但未完整交付math，E14缺六個inlineLaTeX，E13缺完整math／或單段交付。四個正例都未被刪除或降標。

| 指定觀察 | C1 | S0→S1配對結果 |
|---|---|---|
| Wiki357/368、SEAL21/30跨頁 | Wiki range執行錯誤；SEAL21缺p2；SEAL30仍分段且有page furniture插入 | 四個段落均完整續接，native同版assembly完成；S1無額外恢復 |
| Wiki inline math | `⊂`使整個三頁range失敗，公開結果沒有保留下來 | prose與可讀native glyph保留；formula重建off，沒有必需LaTeX |
| SEAL heading歸屬 | Unlike正文與Algorithm1標題分開，是局部結構改善 | 兩者仍把Algorithm1標題併進正文；S1另把algorithm body當table並重排 |
| SEAL公式1/2/3 | raw恢復主要數學結構及原式號；stock export把原有parenthesized math delimiter再包進display delimiter | 未重建；S1又把公式4判為table，不能當恢復 |
| SEAL公式4 | raw把history `y_<s`的`<`漏掉；另有相同delimiter交付問題 | S0為空formula；S1變table，必需LaTeX都未交付 |
| 控制matrix/fraction/cases | matrix攤成數字列表；fraction/cases raw可讀但stock formula wrapper有缺陷 | S1增加matrix/fraction的formula分類，但仍未重建；不是公式準度通過 |
| 真實DGM diff | raw變成LaTeX table，literal／換行escape／條件出錯；typed又受缺依賴影響 | 相同扁平code與literal空白缺陷；未開code enrichment，無恢復 |
| 控制code block | raw已失縮排，parser再攤平並移除comment的`#` | 兩臂都成一行code；不能保留必要nesting |
| 控制inline code | 保留原句及`<=`；HTML escape不是錯誤 | S0切成獨立code block；S1改判formula後主Markdown完全漏式，新增退化 |

C1的`stop_reason=unspecified`不是EOS證明。SEALp2有9001 reported tokens（設定cap9000）、重複未閉合table、沒有原Knowledge Updating正文，這是有具體證據的cap／內容缺失，不能因native success略過。

## 表格與OCR：分開分母

[三項G1評讀](pdf-core-native-round-2026-10-17/g1-review.json)保持完整Table2六panel／84點／8critical comparisons、NCCU五項、scan16行三個獨立任務，沒有混進41項。

| 任務 | C1 | S0 | S1 |
|---|---|---|---|
| G1-T02完整複雜表 | raw多個panel數值可讀，但重複矛盾header／多出numeric column；typed table受缺依賴影響 | 六panel併為混亂grid，metric合cell、mini-batch4的64.5混入mini-batch2；綁定不合格 | 同樣綁定失敗；colspan cell又在stock Markdown重複，屬新增export退化 |
| G1-O01 screenshot五項 | `壹`執行錯誤，無公開raw，不推論模型圖片OCR能力 | 公開parsed OCR cells有五項，部分系統/連結字形minor；主要Markdown只留picture | breadcrumb變錯文，其餘四項有OCR；仍沒有image-key supplement |
| G1-O03 scan16行 | 兩段各自文字完整，卻把右欄段落插在兩段之間 | 左右欄字串混入兩個target paragraph | 兩段各自文字恢復，仍插入右欄段落，順序未過 |

**三項完整交付都尚未通過。** Table2已全六panel檢視，84個必要綁定與8比較全列為未證實，沒有用數字命中報準確率；**未完成可安全配對的numeric reading error%裁定，因此不報百分比，也不聲稱84個數字都辨識錯**。即使部分原數字齊全，header/condition/metric綁定與critical比較不能由交付表安全確立，就不滿足原契約；使用者容許≤5%複雜表誤差的規則未被取消或收緊。[S0](pdf-core-native-round-2026-10-17/S0-table-evidence.json)／[S1](pdf-core-native-round-2026-10-17/S1-table-evidence.json)保留完整native grid供查核；C1保留未改raw。

NCCU選定OCR可在public parsed cells出現，但三組都沒有完成與image key關聯、和source Markdown分離的F08交付。C1的no_text_in_pic routing與runtime錯誤也限制外推。scan的16/16可讀文字不等於完整順序通過，右欄插入不能略過。

## 方法限制與本輪未修補之處

1. **C1相容性缺陷確實存在。** 無模型的[tokenizer重現](pdf-core-native-round-2026-10-17/C1-tokenizer-diagnostic.json)對token64488 `⊂`、57841 `壹`重現MLX BPEStreamingDetokenizer KeyError。不是來源不可讀，也不是Qwen/NVIDIA BF16能力結論；不修改detokenizer、不追加推論。
2. **C1 LaTeX table parser依賴不完整。** 未在model前做完整pure-parser smoke，實測才發現缺`pylatexenc`。這是本次前置檢查不足，不能包裝為乾淨的table模型accuracy比較。原raw仍保存，DGM650/652清楚分列dependency-missing；不為修capture重跑模型，也不在本輪另建parser。
3. **Standard最小安裝的機械問題已在模型前修復。** 第一次完整converter import缺scipy，接著缺rtree；保留[失敗執行](pdf-core-native-round-2026-10-17/preparation-S0-import-error/execution.json)，補齊後全import／依賴check再登錄，兩臂共用80-package runtime。沒有Standard模型推論重跑。原MLX環境未改。
4. **三頁OCR中間cells不同，不能作純layout因果歸因。** 11頁公開scale2render全相同，八頁retained parsed textline cells完全相同，但SEAL2、NCCU3、scan1不同，包含OCR文字／分行，不只是confidence。它們發生於公開中間表示；未捕捉stage當時input tensor，故不能把scan恢復或NCCU退化單獨歸因到Egret權重。見[逐頁cells配對](pdf-core-native-round-2026-10-17/paired-public-cells.json)。其他八頁也不能聲稱所有內部tensor一致。
5. **定位不是只看bbox合法。** 保存123項原來源區域與可得輸出provenance；指定跨頁association可確認，SEAL標題錯歸屬已明記。未完成全部region的獨立精確定位認證，沒有宣稱全頁coverage或source bbox100%正確。
6. **時間分解與呼叫數有限。** 保存公開range／VLM generation時間、pipeline timings與resource samples；沒有每stage獨立wall-time、所有OCR crop／forward數或完整processor tensor hash。無來源證據的部分不填估值。保存輸出後的評讀腳本曾修正自身JSON escape assertion，未產生舊分數、未改模型輸出或oracle。

[初始登錄](pdf-core-native-round-2026-10-17/registration.json)、[Standard模型前修訂](pdf-core-native-round-2026-10-17/standard-registration-amendment.json)、[C1固定runner](pdf-core-native-round-2026-10-17/run-C1.py)、[Standard runner](pdf-core-native-round-2026-10-17/run.py)、[權重hash](pdf-core-native-round-2026-10-17/weights.json)、[共享OCR/table資產](pdf-core-native-round-2026-10-17/shared-assets.json)、[MLX runtime](pdf-core-native-round-2026-10-17/C1-runtime.json)、[Standard runtime](pdf-core-native-round-2026-10-17/standard-runtime-v2.json)均保存。沒有修改production、既有oracle或舊實驗結果。

## 去留與下一個決策

- **C1：淘汰本機目前這個配置作為整合候選。** raw部分數學與heading有價值，但Unicode runtime、重複cap、code/matrix及官方parser/export交付缺口並存。這不淘汰Nemotron全家族，也不外推公司vLLM；本輪不投入自訂修補。
- **S1：不替換S0，暫留局部觀察。** 沒有讓必要的41項／三個G1任務整體過關，且有inline code、formula/table分類、Markdown重複等退化。scan內容改善又有upstream cells差異，尚不足推薦整合。
- **S0：保留同版原生baseline。** 可重用原生跨頁assembly這個已證實能力；enrichment off的此配置不能冒充正式profile，更不是G2通過。

本輪**不推薦新的整合候選，也不自動開另一輪模型或恢復Paddle**。若要再投入，建議先決定是否接受「完整官方VLM路徑仍有source定位與Markdown表示缺口，需要公司地端API上的最小profile整合及補驗」這項成本；公司Qwen3/vLLM仍是候選，不是指定唯一模型。公司環境尚不可用時，可先以已保存raw做官方parser依賴／export的零推論診斷，但它無法修復本輪raw已遺失的matrix、code indentation、history符號，也不應演變成大量後處理。

未開holdout、未測公司GPU/vLLM與高頻SLO，未報精確table numeric error%及完整定位認證；上述限制保留為未驗證項。
