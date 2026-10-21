# PDF-core G2：裁圖完整性、item 邊界與回填保真

日期：2026-10-15（Asia/Taipei）。承接[較強 VLM 比較](pdf-core-g2-inline-api-2026-10-15.md)與 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。**本輪完成六組新來源 context 比較：完整公式框及 code context 可保住來源內容，但兩筆 SEAL 模型重寫仍有語義／漏字錯誤。新增回歸亦發現 token guard 誤擋既有正確案例，因此不採為通用規則。邊界修正、模型辨識與 Canonical Acceptance 分開記錄；G2 尚未全面通過。**

修正只作用於獨立 working Markdown／補充結構。原 provider JSON、來源 PDF、圖片、圖譜、前輪輸出與 oracle 均保留；沒有修改 production pipeline 或採用正式 Processing Profile。

## 來源規則與六組新輸入

本輪使用 producer 的 parent／child、provenance、stage clusters、native cells、字元範圍及座標關係產生新輸入，沒有將 evaluator 的正確公式、答案或 oracle bbox 放進規則或 prompt。[Source audit](pdf-core-g2-inline-boundary-2026-10-15/boundary-primary.md)與 [20 個固定 source hashes](pdf-core-g2-inline-boundary-2026-10-15/source-audit.json)保留實際證據。

| 問題 | 本輪有界修正 |
| --- | --- |
| Formula child 文字框裁掉結構線 | 驗證 immediate PictureItem parent／same page，取 parent 與所有相關 child bbox 的 union，再沿用 2pt padding、3× rerender／outward rounding。不能只取 parent：分數 child 較 parent 向下多 2.82pt，分段式 child 較 parent 向右多 0.81pt。三個新 requests 分別處理矩陣、分數、分段式。 |
| 註解與 code 主體被拆成兩個 CodeItems | 依相鄰同 parent／page、左緣與 native 行距／連續 cells 合成一個 context，保留原註解與縮排，共一個新 request。獨立 inline line 保持另一個來源單位。 |
| SEAL34 混入右側 title，正文續句落在45 | 原 item 的兩個 provenance 分別匹配左正文與右 title cluster；隔離左 fragment，再以同左緣、小行距、未完句／小寫起頭及唯一候選找到45。將兩片分開裁切後拼接，避免矩形 union 吃進右側 algorithm。右 title 另保留，共一個新 body request。 |
| SEAL32 的 model-name／下標錯誤 | 納入緊接該段的 display formula33作 context，共一個新 request。33不因此被消耗或覆寫；只評估／回填目標段落32。 |

SEAL34 的 title cluster 原生 label 仍是 `text`；空間隔離不等於原生自動 caption 分類。Caption／title 角色的模型判斷另記來源。歷史 continuation-v3 保留上游 inline joins 的分支允許左右框只要垂直重疊，造成高正文框吸入右 title；本輪未改動該歷史檔案，也未宣稱已修正通用 reading order。

[輸入 manifest](pdf-core-g2-inline-boundary-2026-10-15/inputs/input-manifest.json) SHA256 `9cbaf2d1e31dc8fca9820c75f5c7b14d3a08f4bf8909698e39f3f6466856e22b` 固定 **6 張 PNG、7 個來源 fragments**。Reviewer 逐圖確認括號／分數線／brace、七行 code、正文與續句完整。SEAL body 兩片的 padding 有 **5px 垂直來源重疊**：第一片只露出下一行的微小 glyph fringe，第二片有完整續句，沒有整詞／整行重複；不能稱其 pixel-disjoint。所有 transforms 與拼圖位置保留。

沿用暫用 `gpt-6-luna`、low reasoning、Strict JSON segments、high image detail、`store=false`、4096 completion-token cap、單次 attempt／順序執行。System prompt／schema 與前輪相同，user prompt 改為完整 context／多來源 blocks。這同時改動來源 pixels 與 context prompt，是方法比較，不是只改裁圖的單一變因實驗。仍為 direct API component，沒有跑官方 API `VlmPipeline`。[Runner](pdf-core-g2-inline-boundary-2026-10-15/api/run.py)

## 模型輸出與獨立品質判斷

| 新輸入 | 實際結果 | 處置 |
| --- | --- | --- |
| 完整矩陣 envelope | 正確 2×2 square-bracket matrix，四值／負號／排列保留 | 保留 working formula replacement 候選 |
| 完整分數 envelope | `g(x)=1/(x+1)` 的結構與分母完整 | 保留 working formula replacement 候選 |
| 完整分段式 envelope | 兩 branch、平方、`x≥0`／`x<0` 邊界正確 | 保留 working formula replacement 候選 |
| 註解＋code context | 七行完整、Python、`<=`、縮排／巢狀／註解均忠實 | 以宣告的兩個來源 refs 合成單一 working code block |
| SEAL34 body＋45 | 續句只出現一次，未混入 title／algorithm；但漏掉第一個 `parameters`，另有 `re-sult`／`mis-aligned` 差異 | 拒絕模型正文替換；保留模型失敗，邊界候選另使用原生文字 |
| SEAL32＋formula33 context | 目標仍將 LM 下標讀成 `L_{M_θ}`，並遺失 prime；旁邊 formula 的 LM 不可拿來抵銷目標錯誤 | 拒絕模型段落替換；context33原封不動留在其原位 |

沒有為使案例通過而修正模型字串、追加正確答案或重跑成功輸出。所有 response／parsed blocks／uncertainties 分開保存。空 uncertainties、合法 LaTeX 或 strict schema 成功均不證明內容忠實。

## Working Markdown 與來源保留

Hidden formula children 必須透過宣告的外層 picture rendering boundary 才能進入主 Markdown；僅修改 child 不會改變 stock serializer 輸出。本輪保留 parent picture／image／child 原物件與來源關係，另產生 formula 的 working rendering。Code12／13則以兩個 refs 的 source accounting 合成七行 block，避免註解或主體重複。

Inline code14重用前輪已忠實的原始 API paragraph／inline-code 結果，**沒有新增推論**。Role 調整只在本輪 working projection 內發生；需保住原來源 prose、identifier、運算子及 source／parent／scope 關係，不能只因模型偏好 paragraph 就普遍放寬 CodeItem role。

Working outputs 共八個 proposals：**四個新模型結果套用、兩個 SEAL 模型結果拒絕、一個 native-only 邊界修正及一個前輪 inline role reuse**。本輪 overlay 以原始 provider 為基準，沒有累加前輪所有候選；scope 外的既有缺陷保持可見，例如 controls 的 native inline 平方仍攤成 `x 2`。這不是一份已完成所有能力的 profile 輸出。

SEAL34 的模型正文被拒絕後，另建立 **native-only 邊界候選**：原34的左正文 charspan＋原45全文成為完整正文，原34右 title charspan保持分開並保留角色 lineage。這項工作不使用模型改寫的 prose，也不補原生文字沒有的 LaTeX。原34／45與所有算法項目仍保存在原 provider；working rendering 只有在全部 charspans／來源片段完整計帳時，才能於34呈現正文與 title、於45取消重複序列化。數學重建仍為未完成的必要工作，不能將 native-only fallback 說成 F13 成功。

回填使用明確 repair units 與 consumed／retained／context refs，保留完整 source/document/item hashes、父子／鄰居、字元範圍及輸出位置。旁支 algorithm、formula33等未消耗內容須保持不變。語義失敗保留為未套用 proposal，不因 boundary 已修正而取得 Canonical Acceptance。

本輪實驗另檢查原生 identifier／prose token 的保留；此檢查限於目標範圍，不能由 context 中同名 identifier 代替。它能抓到本輪 LM 拆字及漏字，但不是通用數學等價判定器，也不能證明公式、括號、上下標與資料綁定全部正確。下列回歸已否定它作為通用拒絕規則的適用性；保留實驗程式與結果供追溯，未將它升為已選 runtime gate。

## 防止 overfitting 的回歸與採用決策

使用者明確要求不能為修某個錯誤而降低其他 testcase 的表現。本輪將固定的新 token guard 以 shadow 方式套到前輪全部17個 paragraph outputs，並核對四個已有 source-positive 證據的 anchors；**不調 regex／threshold 去配合結果，也不重跑模型挑成功輸出**。

已知四個 positive anchors 中僅兩個保留：E13與362通過；E14因原生 `topranked` 與來源忠實的 `top-ranked` 不同而被錯擋，E04則因 `benchmark`／`bench-mark` 而被錯擋。這是 **2／4 anchors 的 eligibility／coverage 退化**，不是整體辨識 accuracy 的統計估計。抓到一個既有 SEAL 錯誤不能抵銷錯擋已通過案例。

**決策：不採用此 token guard 作通用回填門檻。** 它也有 false-negative 邊界：若保住 `LM` 卻刪去 prime，Latin word counts 仍可能通過，但來源 review 必須拒絕。原生抽取是可有斷字、flatten或錯序的 source observation，不能視作 gold。六組 boundary／context修正仍僅是局部候選，通用 parent crop、續句門檻、role調整及新context prompt均未取得跨來源可泛化的證據。

這17筆是回歸資料，已知正例／失敗也參與本輪分析，**不是未見 holdout**。下一次方法選擇前應先固定跨來源 holdout 與必要能力回歸集，同時報告來源品質、成功交付覆蓋與拒絕率；不能只以已接受輸出的精度掩蓋大量 abstention，也不能把舊檔 hash 不變當成新規則不會退化的證據。

[Shadow 回歸說明](pdf-core-g2-inline-boundary-2026-10-15/regression/README.md)／[完整結果](pdf-core-g2-inline-boundary-2026-10-15/regression/results.json)亦保留分母：17筆 first-block 診斷為13 pass／4 abstain；其中16筆 single-root eligible為13／3，1筆多root本來即不適用。前輪11筆結構套用若加上此guard，只會保留8筆；其中2筆拒絕為已知正例，不能把coverage下降報成品質提升。六個小測驗也記錄Greek、單字母、operator等未受此guard保護的邊界。

## 執行範圍與後續

六次皆 HTTP200、`finish_reason=stop`、無 refusal、單次 attempt；request body／source PNG／runner→template→client chain 與 20 個 source hashes核對通過。[API verification](pdf-core-g2-inline-boundary-2026-10-15/api/verification.json)。合計 client RTT **30.60 秒**，每次 **2.91–8.20 秒**；prompt 4,387＋completion 2,418＝**6,805 tokens**（reasoning 1,439 包含在 completion）。沒有 raw EOS/token IDs，沒有量到 remote GPU／RAM；HTTP timeout／shared lock 也不是高頻 ingest 或 server cancellation 的證據。

本輪提供完整 source context 與有來源計帳的 working boundary adapter 的局部證據；剩餘數學／漏字錯誤及回歸退化均保留。接續先固定跨來源 holdout 與回歸範圍，再評估原生文字／位置作為有不確定性的錨點，以及公式候選的來源對齊，之後才進行完整 Docling／Canonical 整合與公司候選驗證。

未驗證通用 boundary detector、完整 corpus、正式 mapper／恢復、公司 GPU／vLLM 或高頻負載；目前 working 結果不能自動視為已接受的 Canonical Knowledge。

[獨立品質核對](pdf-core-g2-inline-boundary-2026-10-15/review/output-review.md)／[21 個負例與計帳結果](pdf-core-g2-inline-boundary-2026-10-15/review/output-review.json)保留六組輸入／輸出、原生812字元的邊界計帳及未改動的旁支。後續[整體驗證](pdf-core-g2-inline-boundary-2026-10-15/validation.json)與[artifact manifest](pdf-core-g2-inline-boundary-2026-10-15/artifacts.json)亦核對前九輪1,717個payload、local links及credential pattern。所有模型失敗與回歸退化保留，本輪沒有正式profile採用。

[結論摘要已寫回 #84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6192739352)，本文只加入摘要連結，44 個 feature rows 均保持原樣，issue 維持 OPEN；[寫回核對紀錄](pdf-core-g2-inline-boundary-2026-10-15/ticket-update.json)保存摘要與本文的 exact readback／hash。完整來源、runtime 及 artifact 證據留在本機報告。
