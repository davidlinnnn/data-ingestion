# PDF-core G2：實際圖片與原生交付 preflight

2026-10-16。延續[獨立實驗審查](../reviews/pdf-core-experiment-audit-2026-10-16.md)，本輪完成實際 model-input 圖片攔截重放、DOTS parser／Markdown 邊界控制，並固定一個下一候選。**輸入檢查已通過；現有 DOTS 交付仍有必要條件缺口；下一候選尚未達到可推論狀態，G2 仍未通過。**

本輪沒有模型推論、GPU model load、付費 API、權重下載、套件安裝、holdout 內容讀取或 production 修改。實際 PDF 僅重放四個事前固定的診斷頁，並非新增的盲測品質樣本。Docling 的 API transport 被固定合成 stub 取代，socket 連線禁止；stub 成功只證明流程與 guard 可執行，不代表模型準度。

## 本輪驗證及結論

| 層次 | 實際執行方法 | 結果與界線 |
|---|---|---|
| 實際圖片 | Docling-slim **2.132.0**／Core **2.99.0**／Parse **7.22.3**；原生 `VlmPipeline`、`dots_ocr` preset；`images_scale=2`、VLM scale=2、batch=1；兩個官方 PDF backend | **4 來源頁 × 2 backend＝8 張輸入**。控制 p1、WikiSkill p4 兩種皆可讀；validation-02 p1／p12 的 `DoclingParseDocumentBackend` 有大面積黑色遮蔽，`PyPdfiumDocumentBackend` 可讀。兩位 reviewer 直接看過全部八張實際 engine-input PNG。 |
| 圖片攔截重放 | 核對 source path／SHA、physical page、backend、兩個 scales、完整 options、實際 RGB size／pixels、完整非 image engine input；同一原生流程重跑 | **6 張核准者 native stub conversion 成功；2 張黑頁在 stub 前被擋，stub calls=0**。初始 17 個 guard controls 與最終實際圖片／request 的 **106 個獨立 controls** 通過，涵蓋缺核准及各欄位變動。這是研究輸入核准，沒有制定正式每次 ingest 的人工審核政策。 |
| 設定可重現性 | 實際 schema、兩個獨立 process hash seeds、set permutations、URL、Path 與有序 stop strings | **66 個 assertions 通過**。首次 gate 因設定 hash 不穩定而全部拒絕；修正 set 序列化後才有上述 6／2 結果。原失敗、原 runner 與核准資料均保留，沒有鬆綁 guard。 |
| DOTS 原生交付 | 16 個事前登記的合成控制 × 7 組 public export settings；4 份 unchanged saved raw replay；另登記 2 個 table header controls | 裸公式與 fenced code 可保留；已有定界符的公式被再包一層，部分合法 inline code／TeX 被 HTML parser 改義。**沒有一組現有全域設定能同時保真所有必要內容。** 這不是新的模型品質分數。 |
| Paddle 官方 Docling importer | 已安裝且未修改的 `parse_paddleocr_vl_result`，與官方 v2.132.0 source／distribution RECORD 核對；perfect-provider 合成測試 | 能接原始單頁 JSON 並保留部分結構；stock Markdown 會破壞 code literal、展開獨立 inline formula、重複公式定界符。不能直接當下一候選的主要內容交付。 |
| Paddle 原生 Markdown | 兩份完整未改的官方 PaddleX 3.7.2 converter modules，正常 namespace import，合成 block／真 PIL image 測試 | 已 fenced code、正文 inline LaTeX、自帶定界符公式、HTML table spans 與 image map 可保留；plain algorithm 不自動 fencing，分離的 inline_formula 不回到正文，bare formula 不補 delimiter。**尚未驗完整 Result／save_to_markdown／磁碟圖片整合。** |

實際結果與審查：[render collection](pdf-core-g2-preflight-2026-10-16/render-inputs-v2/results.json)、[核准資料](pdf-core-g2-preflight-2026-10-16/render-approvals-v2.json)、[gate replay](pdf-core-g2-preflight-2026-10-16/render-gate-v2/results.json)、[獨立 guard review](pdf-core-g2-preflight-2026-10-16/guard-review.md)、[parser 詳細報告](pdf-core-g2-preflight-2026-10-16/parser/parser-findings.md)。

## 已釐清的錯誤來源

第一輪 collection 與 gate 的圖片、engine request 完全相同，但 options hash 不同。根因是 Pydantic 把 `supported_engines` 的 Python set 轉成順序不穩定的 JSON list；只排序 dictionary keys 不足以解決。修正後使用 Python dump，只排序真正的 set，保留 list／tuple 順序，明確處理 URL／Path，拒絕未知型別。獨立 reviewer 重現了原來兩個 hash，並對真正 options schema 驗證。第二次 collection 的八張 PNG file bytes、RGB pixels 與完整 request 均與原先直接目視的圖片一致，因此能沿用原視覺判斷、重新綁定完整設定。[原失敗 gate](pdf-core-g2-preflight-2026-10-16/render-gate/results.json)仍保留，不能算成功。

DOTS 的 parser／serializer 則有另一類限制。Formula.text 若已含 `$`／`$$`，stock serializer 仍再加定界符；合法 backtick code 內的 `<b>...</b>` 會先被 HTML parser 當格式，之後的 export flag 無法恢復 literal。關閉 escaping 可保存 provider 已交付的合法 Markdown，但會把普通文字中的 `__init__`、`_TEMP_` 或 `<widget>` 當標記；不能把它當成普遍修正。`p(y_{<s})` 本控制沒有出錯，形如真正 `<s>` tag 的內容才發生衝突，不能過度泛化。

表格要分清楚 native JSON 與 Markdown：spans 可以留在 JSON，pipe Markdown 仍會攤平；第二列裸 `<th>` 不一定得到 header role，明確 `<thead>`／`scope="col"` 的另兩份控制則可保留。圖片 placeholder 可用 public `image_mode="embedded"` 解決，但來源 crop／caption 關係仍應另外檢查。對既有 raw 的重放沒有修字串、換答案或重新評分來源準度；DGM 的 invalid JSON 在所有 export options 下仍為空。

首次 parser run 也保留失敗：所有輸出產生後，direct typed-code 對照因預期單空白、實際 inline join 雙空白而停。只修正 assertion 為 exact code literal；16 inputs 與七設定未變。後補的 rendered-visible-text assessment 明列為事後核對，不稱盲測或獨立 preregistered validation。

## 固定的下一候選

**PaddleOCR-VL-1.6 完整 pipeline：CPU layout → 依區域類型呼叫 MLX VLM → Paddle 原生 Markdown，原始 JSON／圖片與 DoclingDocument 作補充。** 這是探索候選，沒有採用新的正式架構；既有 baseline 與全部歷史結果保留。不能只把整頁丟給 VLM，就聲稱驗過官方完整 Paddle 流程。

| 部位 | 固定候選設定；尚未執行模型 |
|---|---|
| Client | Python 3.12；PaddleOCR 3.7.0、PaddleX 3.7.2、PaddlePaddle 3.2.1；需獨立環境及 transitive lock |
| Layout | `PaddlePaddle/PP-DocLayoutV3@241f8bdfc77a7c7bee915a5057aaee58c235a8d3`，CPU；threshold=0.3、NMS=True、unclip=[1,1] |
| VLM | `PaddlePaddle/PaddleOCR-VL-1.6@c5630abae1d940eafe0697512a0325494b02ab42`，0.9B；MLX-VLM 0.7.8／MLX 0.32.4，本機 service；之後使用 exact snapshot 路徑 |
| 流程 | layout=True；orientation／unwarp=False；merge_layout_blocks=True；format_block_content=False；chart=True；seal／image OCR=False；queues=False；concurrency／batch=1 |
| 生成 | min_pixels=112896、max_pixels=1003520、max_new_tokens=4096、temperature=0、top_p=1、repetition_penalty=1；使用官方區域 prompts |
| 交付 | 原生 Markdown `pretty=False`、`show_formula_number=True`；先保留原始每頁 JSON 與 live images，再做官方多頁 restructure；Docling importer 僅接原始單頁結果 |

版本、官方來源、行為測試與完整設定見[候選報告](pdf-core-g2-preflight-2026-10-16/candidate-findings.md)及[candidate-plan.json](pdf-core-g2-preflight-2026-10-16/candidate/candidate-plan.json)。已更正先前對接點的假設：**已安裝的 Docling 2.132.0 確實有官方 Paddle importer**，無須拼接 moving-main 原始碼；其存在仍不代表 Markdown 契約通過。

## 下一個執行點與停止條件

1. 隔離 client stack，先做零模型的完整 `PaddleOCRVLResult → save_to_markdown`／圖片落盤測試；包括公式編號、plain code、分離 inline formula，以及 pipeline math normalization 對美元 literal 的影響。純 converter 成功不能代替完整整合。
2. 只把本輪核准的 PNG 傳往 Paddle；保存並檢查它真正的 layout input、VLM crops 與 processor pixels。四個來源頁不是連續頁集合；跨頁驗證須另外核准同來源連續範圍。本輪 Docling 核准不能替代 Paddle preprocessing 核准。
3. 若必要表示在 perfect-provider 下仍不成立，先界定一個通用、依官方結構的最小交付接點及回歸控制，再決定是否值得繼續。不能靠模型恰好輸出可用格式、答案特例修補或無限改 prompt 掩蓋問題。
4. 通過後才登記一次有界模型執行，分別評 source semantics、原始輸出、native mapping、Markdown、provenance 與 latency。延用固定 development／regression 規則，holdout 不參與選法；有界模型 run 不自動獲得 G2 acceptance。

本輪的完成點是「輸入 guard 可重現、交付缺口有實測、唯一候選與未滿足前置條件已固定」。後續仍須驗候選模型準度、M5 真實資源／延遲、公司 CUDA／vLLM 與高頻 ingest；尚無可正式採用的完整 Processing Profile。

## 證據完整性

前次 compare-only checker 成功：舊模型 evidence **326 entries**、前次 audit seal **119 entries** 相符，原 source oracle 未變，先前三份完整論文／75 頁結果保留，owned paper workers=0。[核對紀錄](pdf-core-g2-preflight-2026-10-16/prior-audit-check.json)。本輪用[compare-only checker](pdf-core-g2-preflight-2026-10-16/check_evidence.py)核對原始 freeze／保留 runner、兩次 collection、兩次 gate、parser 身分與官方 source，並比對新封存；不重新產生 manifest 來宣稱一致。[本輪核對結果](pdf-core-g2-preflight-2026-10-16/verification.json)。

略過模型、完整 Paddle client 整合、數學 renderer、公司 GPU／load 及 holdout；本輪只能支持流程與交付邊界結論，不能估計模型泛化準度或宣稱 G2 通過。
