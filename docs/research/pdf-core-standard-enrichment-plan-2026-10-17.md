# 下一輪：Standard 原生 code／formula enrichment 的有界驗證

2026-10-17。承接使用者「繼續規劃下一輪的目標及作法」與[前輪結果](pdf-core-native-round-results-2026-10-17.md)。**本文件是計畫，尚未安裝、載入模型或執行新推論。** 本次只查固定版 source、保存的 JSON 結構與既有模型 metadata；未開 PDF、圖片或 holdout。

## 要回答的決策

**S0 加上官方 CodeFormulaV2，能否在真實 Standard 流程保留 code 的 literal／縮排、重建原生可達的獨立公式，並維持已正確的正文與跨頁續接？**

這一輪決定的是「是否保留這個原生 enrichment 元件進入後續組合」。不把它當作能直接通過 G2 的完整 Processing Profile：普通段落的 inline formula、複雜表格、圖片 OCR supplement 等既有必要功能仍未解。

值得補驗的原因：先前 CodeFormulaV2 只跑過兩張固定 oracle crop、512-token 上限；受控 code 成功，SEAL Eq2 仍漏分支。**尚未驗的是偵測結果 → 原生裁圖 → 模型 → typed item 寫回 → 主要 Markdown 的整條路徑，以及真實 DGM diff。** 本輪採官方一次性裁圖與設定，不依錯誤重裁、放大、修字或挑最佳輸出。[既有結果](pdf-core-g2-round2-2026-10-14.md)、[官方接點核對](pdf-core-next-round-official-path-notes-2026-10-17.md)

## 一組配置，沿用八頁

候選 **E1**：`StandardPdfPipeline` 保留 S0 的 Heron、selective RapidOCR、TableFormer V1 accurate、原生 reading order／assembly，只加入官方 code／formula enrichment。

| 項目 | 固定方式 |
|---|---|
| Runtime | Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3／pypdfium2 5.14.0；以已完成的 Standard 隔離環境為起點，執行前重新封存完整依賴 |
| PDF 與上游 | 顯式 PyPdfiumDocumentBackend；S0 Heron revision、OCR 三模型及 TableFormer 資產 hash 不變；layout／OCR／table batch 1；CPU 4 threads、interop 1 |
| 新增元件 | `CodeFormulaVlmOptions.from_preset("codeformulav2")`；`do_code_enrichment=True`、`do_formula_enrichment=True` |
| 模型 | `docling-project/CodeFormulaV2`，revision `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`；既有約 631 MB 權重，執行前重核完整 hash，不取 `main` |
| Engine | 明確 Transformers、CPU FP32、compile=False、quantized=False、load_in_8bit=False、trust_remote_code=False；不用 AUTO_INLINE 自動換 engine |
| 有效原生設定 | 約 120 dpi、bbox 擴張 18%、只取 `prov[0]`；`<code>`／`<formula>`；temperature 0、cap 2048；enrichment element batch 最多 5，不冒稱 batch 1 |
| 保存／匯出 | parsed pages、page／picture images；預設 Markdown export；保留 raw、stock cleanup 後 typed text、原 `orig`、provenance 與完整輸出 |
| 其他功能 | classifier、picture description、chart extraction、heading hierarchy 等保持 S0 的 off；不新增 API fallback |

`CodeFormulaVlmOptions.scale` 並非此 stage 實際裁圖尺度；以原生 stage 的有效呼叫為準。CPU 型別、參數與實際批次長度須觀測確認，不能只看 options JSON。[官方 stage](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/stages/code_formula/code_formula_vlm_model.py)、[裁圖接點](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_model.py#L184)

| 執行順序 | Physical page，1-based | 作用 |
|---|---|---|
| Controls | 1 | 受控 code、inline code、公式與普通正文對照；首次 smoke 算在本次內 |
| WikiSkill | 20–22，連續一次 conversion | 原四個正例中的 Wiki 內容、兩個跨頁段落與 inline coverage 缺口 |
| SEAL | 2–4，連續一次 conversion | 四個獨立公式、跨頁段落及錯誤 heading 歸屬的回歸 |
| DGM | 51 | 真實 diff、identifier／literal／必要縮排；也檢查被標為 code 的自然語言指令 |

**最多一組配置、8 頁、4 次 conversion；不另跑 S0。** 保存的 S0 是歷史配對基線，同一次 E1 的 pre-enrichment snapshot 才是辨認 enrichment 改了什麼的直接依據。所有原 41 項及四個保護正例保留，不把未進 enrichment 的工作移出分母。

從保存的 S0 結構可預期：Controls 2 個 code、Wiki 1 個 formula、SEAL 4 個 formula、DGM 3 個 code，共 **10 個原生可達候選元素**。Wiki 的該獨立公式位於原 41 項之外，是整頁流程的已計數附帶工作，不加到成功分母。執行前以預設 traversal 核對並登錄；本輪最多 **10 個 region model inputs**。若實際清單超出，記錄路由差異並停止送出超額工作，不臨時擴預算或挑掉難例。這不是 10 次 HTTP：本輪沒有 remote API，`predict_batch` 與 model forward 次數分開記錄。

## 先做能阻止浪費推論的檢查

共同準備與零模型檢查最多 30 分鐘，不再建立通用 preflight framework。

1. **完整 import／依賴與官方資料流。** 核對本配置所需的 converter、model class、processor、stock cleanup／export 與權重身分。真正的 `initialize_pipeline()` 會 eager 載模型，不算零模型檢查；模型載入只准在登錄後執行一次。
2. **用保存的 S0 結構檢查原生路由。** 核對 root／group code、root formula、picture child formula、普通 inline paragraph。人工合成合法 code／LaTeX 回應只進 mock engine，走原生 cleanup、寫回及 stock export；不將 oracle 答案送進 live model，也不用合成通過冒充辨識成績。
3. **證明公開 observer 不改行為。** 只在公開 enrichment `__call__`／engine `predict_batch` 接點透傳並保存 pre-enrichment document、item refs、實際 crop、prompt／參數和原始回應；mock 驗證輸入、回傳及項目次序未變。不改私有 crop／parser，不為抓證據新增 producer 演算法。公開接點無法保存必要證據就記未就緒，不先跑再補。
4. **按能力分開停。** root code／formula 的合法 mock 仍無法經原生路徑交付，則不花對應推論。可在模型前依此固定為 code-only 或 formula-only 的同一個 E1 分支，保留另一能力未實作狀態；兩者皆不成立便結束。分支只能由這個機械性檢查決定，不能看模型成績後切換或再跑第二組。

已知的路由限制必須先寫清：S0 的 matrix／fraction／cases 三個 formula 是 picture 的 children；官方 enrichment 用預設 `iterate_items()`，不 traverse pictures，因此不會送這三個 child。普通正文 inline formula 同樣不符合 gate。**這些是已知 coverage 缺口，不宣稱開旗標即可修好；也不因此全面否決 root SEAL formula 或 code 的獨立實測。** 不另寫 traversal、把節點升到 root 或手動塞 oracle crop 來造通過。[Pipeline traversal](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/base_pipeline.py#L156)、[Core 預設](https://github.com/docling-project/docling-core/blob/v2.99.0/docling_core/types/doc/document.py#L3297)

## 固定評分、證據與停止條件

評讀沿用原[41 項來源契約](pdf-core-g2-official-method-2026-10-15/review/contract.json)，全部仍是已曝光的開發／回歸資料，沒有新泛化主張。

| 問題 | 驗證方式 |
|---|---|
| Code 是否值得保留？ | 受控 comment＋六行 body、DGM 完整 diff 與兩組指令全文；逐一核對 identifier、quoted literal、運算子、增刪號、必要縮排與行序。自然語言指令不能被當成可任意修寫的程式。AST 不作唯一判準。 |
| Root formula 是否有價值？ | SEAL 原四式的數學關係、式號、cases 兩分支、theta prime／subscript、history `<s`、footnote 角色；分 raw 認識、stock cleanup 與可用 LaTeX／原位交付。不以字串全等拒絕等義 LaTeX。 |
| 偵測與交付有沒有漏？ | 列每個 source unit 是否進原生 gate、是否有有效 crop、是否真的呼叫、raw／typed／Markdown 各留下什麼。例外被吞後寫空字串不能算完成。沒有送模型的內容不評成模型辨識失敗。 |
| 是否破壞已有能力？ | 所有正文、四個原保護正例、四個已成功的跨頁 join、page provenance 與 pre/post node 關係配對；對既有失敗列維持／恢復，不把本來缺 math 的單位當完整正例通過。 |
| 來源位置與成本 | 保存實際 native bbox、第一個 provenance 對應 crop、圖像尺寸／像素 hash、逐 batch request／output、模型載入、range／enrichment 耗時及 sampled RSS。不能把 bbox 合法當精確定位，也不以單輪估 p95。 |

同一次 E1 的前後差異優先；與歷史 S0 若上游 item／cells 已不同，就標為完整路徑觀察，不作純 enrichment 因果歸因。必要內容錯誤仍完成剩餘固定工作，避免依分數挑停止點；環境、輸入、timeout 或資源錯誤則保留 partial／missing／unattempted，不刪分母。

| 投入上限 | 規則 |
|---|---|
| 準備／零模型 gate | 最多 30 分鐘；只做本配置必要工作 |
| 模型階段 | 最多 30 分鐘，初始化最多 3 分鐘；合計準備＋模型最多 60 分鐘，不含保存後人工評讀 |
| 每個 range | 單頁 180 秒、連續三頁 540 秒；包含該範圍的 enrichment，不重置為每個 region 180 秒 |
| 記憶體 | 一個 worker；sampled tree RSS 12 GiB、system available 低於 8 GiB 停止；預啟動至少 10 GiB 可用，不關使用者程式或提高限額 |
| 新增推論 | 至多上述 8 頁／4 conversion／10 region inputs；無自動 retry、第二模型、prompt／crop／threshold 調整或 best-of-N |

推論前的可證明機械問題可在時間內修復、保留失敗後重新封存。模型執行過的輸入不重跑；若 capture 缺失，就記證據缺失。沒有新修字、全域繁簡轉換、括號／operator 猜補、custom parser 或 continuation。

Region 預算須在公開 enrichment 呼叫外層、送出整批前檢查；不足就由 supervisor 停止並記 `budget_stop`，不部分送批或默默跳項。不能只在 engine observer 拋一般 Exception：官方 stage 會捕捉它、把整批寫空並繼續，容易把預算中止誤記成模型失敗。

## 結果會導向哪個決策

- **保留有界元件：** 真實／受控 code 或 root display formula 有事前指定的 material 恢復，未新增原正例與已正確內容的 material regression，且經官方接點交付。只保留已證實任務；code 成功不代替 formula，反之亦然。
- **停止這條組合：** 沒有實質恢復、重要 literal／數學仍錯、或需要額外 crop／parser／修字才能交付。保留原結果，不自動加下一模型或更大 token cap。
- **不是 G2 通過：** 即使有元件可留，inline discovery／LaTeX、複雜表關係與 image-key supplement 仍須另一個具體方法。下一個需使用者取捨的是「是否接受最小、可驗證的通用 API adapter／表示層整合成本，或等待公司任務模型服務」，而不是再跑一輪相同 flags。

本輪不重跑 SkillOpt T02、NCCU screenshot、scan，也不重新修復 C1 parser。這些工作不會因本次 code／formula 元件選型而被宣稱已通過；C1 既有 raw 缺陷已足以維持不採用，補依賴不會改變去留，故不再花一輪做無關的 parser replay。通用 OpenAI full-page DocTags low／medium 已測過，不當作新方法重跑；公司 Qwen3 仍是候選，不把 API 相容誤認為 `<code>/<formula>` 任務協定或品質等價。[既有 API 比較](pdf-core-g2-method-selection-decision-2026-10-15.md)

另補前輪解讀：固定 source 的真正 queue wiring 是 **preprocess → layout → OCR**，`OcrMode.DEFAULT` 依 layout clusters 產生 PDF-aware OCR 區域。因此 Heron／Egret 下三頁 cells 差異可以是完整 preset 的下游效果，不能稱成與 layout 無關的 upstream 失控因素；仍無實際 crop 證據把每處差異唯一歸因給權重、OCR 或 postprocessor。此前來源解讀補充不改原輸出、分數或不採用 S1 的結論，也不追加重跑。[Queue 接線](https://github.com/docling-project/docling/blob/v2.132.0/docling/pipeline/standard_pdf_pipeline.py#L790)、[OCR routing](https://github.com/docling-project/docling/blob/v2.132.0/docling/models/base_ocr_model.py#L215)

交付沿用既有 research 格式：一份預登錄／有效參數與資產身分、一份 41 項配對表、必要原文與 crop／定位證據、一份時間／資源表，及明確元件去留。沒有新增 benchmark framework 或 production 修改。

未啟動本計畫；Paddle 與六份 holdout 維持暫停。公司 GPU／vLLM 與高頻 SLO 不在本輪，CPU 小模型可執行不代表正式環境 latency 已合格。
