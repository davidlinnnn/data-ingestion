# G2 inline Granite-Docling CPU execution and source audit

2026-10-15（Asia/Taipei）。**完成17個 producer-selected paragraph component probes及5個真正的官方 `VlmPipeline` 原始 PDF physical-page conversions。22次皆 CPU FP32、正常 EOS、未撞 token cap、沒有 resource stop；執行成功不等於 inline math／code 合格。** 原始 generated IDs、解碼前後、官方 parser結果及只移除 terminal EOS/PAD IDs的另一 parser candidate分開保存，未修改已安裝套件。核對結果 (`vlm/verification.json`)

所用 `ibm-granite/granite-docling-258M` 固定 revision `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`、Apache-2.0；直接重用上一輪13個已下載檔案及515,093,104-byte weights（SHA256 `1cdad234deb1cde18ee6a586f849057f19851daf1fedce2e40aff791dbe46f61`）。每個 child執行前與兩個phase結束後，逐檔核對原下載紀錄 (`docs/research/pdf-core-g2-round3-2026-10-14/vlm/download.json`)；本輪沒有下載、安裝／升版、改 baseline environment、HF cache或舊payload。[固定模型卡](https://huggingface.co/ibm-granite/granite-docling-258M/blob/982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe/README.md)宣告整頁、region、inline-equation、formula／code任務能力；這是候選依據，不代替本輪來源核對。

實際 runtime為 Docling2.102.0／Core2.96.0／Torch2.14.0／Transformers5.8.1。engine options明確 CPU／float32、compile=False、quantized=False、trust_remote_code=False、batch1；Torch intra4／interop1。全部22次驗證所有 model parameters為CPU／torch.float32，generate的image tensors也是CPU FP32，input IDs／mask為CPU int64。`load_in_8bit=True` 是未啟用 quantized分支的設定預設，沒有發生8-bit載入。沒有AUTO、MPS、MLX、CoreML、GPU或remote API執行。

Producer只從既有 Standard結果選whole text items，保留28個 ordinary paragraphs的完整 inventory；11個 body candidates由明確字元gate觸發，另6個有formula／code標籤的controls做regression，共17候選／19fragments。每個輸入、source PDF／hash、item ref、charspan、selection reason與crop mapping均由輸入manifest (`inputs/input-manifest.json`)凍結；模型只接收其PNG，不讀oracle答案、targetLaTeX或oraclebbox。SEAL `texts/30` 保留p3＋p4兩個fragment與24px stitch gap，`texts/34`保留同頁兩個provenances；不能把這些input冒稱單一來源page的完整頁面。

Paragraph path重用上一輪官方engine/prompt/parser probe (`docs/research/pdf-core-g2-round3-2026-10-14/vlm/probe.py`)的API與同一模型cache，但使用完整producerparagraph，而非 `<formula>`／`<code>` prompt強迫純公式或code輸出。每張原3× crop直接送入 `VlmEngineInput`，固定prompt `Convert this page to docling.`、temperature0、cap1024、skip_special_tokens=False；不再乘preset.scale2。這條路是**component adapter**，不是 `VlmPipeline` 或Standard enrichment已接通；reinsertion／fallback由獨立adapter另驗。

Official-page path使用 `DocumentConverter`＋`PdfFormatOption(pipeline_cls=VlmPipeline)`＋新runtime的 `VlmConvertOptions.from_preset("granite_docling")`。`images_scale=1.0`、stage.scale2、force_backend_text=False、generate_page_images=True、picture images=False；從原PDF選physical page，沒有抽頁重編。未開layout／OCR／table或任何enrichment。完整 converter result、官方 DoclingDocument JSON與Markdown均保留在各`vlm/page/runs/<id>/`；觀察hooks只保存方法、token與engineinput/output，不更動模型決策或pipeline組裝。

| original source physical page | generated tokens／cap | child wall s | sampled tree peak GiB |
|---|---:|---:|---:|
| WikiSkill／SRC01 p21（E14） | 915／4096 | 17.350 | 3.100 |
| DGM／SRC10 p51（E04） | 1151／4096 | 21.107 | 3.423 |
| SEAL／SRC11 p3（E13） | 1168／4096 | 21.364 | 3.427 |
| SEAL／SRC11 p4（E13） | 1959／4096 | 31.442 | 3.426 |
| controls／SRC05 p1（C01／C02 regression） | 552／4096 | 14.652 | 3.146 |

17個paragraph各36–294 tokens、child wall5.044–9.855秒、sampled RSS2.365–3.319GiB。五個page child wall合計105.915秒，17個paragraph合計110.951秒；這是每個fresh child啟動至退出的相加，不含等sharedlock的queue時間，不是完整文件latency、cold-cache或吞吐SLO。page summary (`vlm/page/summary.json`)／paragraph summary (`vlm/paragraph/summary.json`)。不同crop context、3× vs約144dpi整頁輸入及token cap均有差異，這是兩種方法／配置比較，不能只歸因模型本身。

已稽核本機exact source與SHA (`vlm/runtime-source-hashes.json`)，含page stage (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/models/stages/vlm_convert/vlm_convert_model.py:147`)、Transformers engine (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/models/inference_engines/vlm/transformers_engine.py:393`)、VlmPipeline assembly (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling/pipeline/vlm_pipeline.py:435`)及Core parser (`docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/docling_core/types/doc/document.py:4175`)：

- 安裝版 `vlm_convert_model.py` 的page stage**硬編cap4096**，`VlmEngineInput`未帶decoderextra或stop strings；model spec的8192與stop strings不會自動變成該call的限制。五個真正pipeline runs均保存實際收到的4096、`stop_strings=[]`、`extra_generation_config={}`，沒有為了比較暗改官方call。
- `transformers_engine.py` 在CPU選SDPA，FP32由explicit engine option覆蓋。`predict_batch`回`stop_reason=unspecified`、metadata.num_tokens包含input；所以用generate hook另存prefix、完整sequence、generated IDs／count、EOS及actual cap，沒有依pipeline SUCCESS或metadata token數推斷完成。
- 同engine解碼後執行 `text.rstrip(pad_token)`，把pad token當字元集合。本輪22次皆由`decoder-before-rstrip.json`**逐字重現**其後的untouched engine text；`unclean-decode.txt`與原IDs另外保存。最後EOS／PAD同為ID100257，原始模型output有完整ending tag，engine cleanup仍刪掉其尾端`>`。沒有把它說成模型未生成closing tag或長度截斷。
- 分開的`token-aware-decode.txt`只從ID序列尾端移除EOS／PAD ID，再以skip_special_tokens=False解碼；不strip字元、不補tag、不改公式或code。相同image＋官方Core parser另存`token-aware-parser-candidate/`。`official-parser-component/`與真正page的`document.json`仍解析原engine output，沒有被此候選覆寫。22次兩種parser均有export，但parser成功不是語義／binding正確。
- `vlm_pipeline.py`的DocTags assembly把isolatedpage組成parser page1，以pipeline基礎image像素當page size；它沒有自動保留原physical p21／51／3／4的PDF-point provenance。`force_backend_text=False`也確保沒有偷偷用native text覆蓋VLM識別。

原始source page、hash與實際parser page／image size存於每job的`source-input.json`／`source-mapping.json`。例如WikiSkill完整pipeline仍有page.page_no21，但parser key1、page size595×842像素；engine收到1190×1684影像。外部geometry mapper (`vlm/map_output.py`)對wholepage按原PDFpoint尺寸／parserimage尺寸換算；對paragraph先與每個fragment的canvasplacement求交集，再套producer已凍結的3×3 matrix，保留多個原physical pages。44份parsed文件各有`source-mapped-geometry.json`。這只是model-generated geometry的來源映射，**不代表inline token與source字符語義binding已經正確**，也沒有覆寫官方document座標或pageno。

另用**零次新增inference**的官方 multipage assembly replay (`vlm/assembly-replay/replay.py`)：以`VlmPipeline.__new__`建立未載模型instance，force_backend_text=False，把兩張已保存的SEAL p3／p4 pipeline page images與exact engine responses一起交給實際`VlmPipeline._turn_dt_into_doc`；token-aware responses另做同樣replay。兩個變體均產生36個text items、parser pages1／2，以sidecar映回source physical3／4；沒有任何text item同時帶兩頁provenance。跨頁段落的p3末段與p4首段仍是不同text items（原始段末`...questions and`，下一項起始`associated answers...`）。engine assembly document (`vlm/assembly-replay/engine-output/document.json`)／Markdown (`vlm/assembly-replay/engine-output/document.md`)與token-aware document (`vlm/assembly-replay/token-aware/document.json`)／Markdown (`vlm/assembly-replay/token-aware/document.md`)及核對 (`vlm/assembly-replay/verification.json`)全部保留。這直接驗證了官方**組裝方法**的行為，沒有把它冒稱重新跑過multipage端到端推論，亦沒有手動合併段落。

執行觀察已見不能由closing-tag修復解決的內容限制：controls ordinaryparagraph仍輸出`Let y = x 2 + 1`，inline-code crop拆成兩個text items；nested code能輸出code但標為YAML。17個paragraph的token-aware parsed output均無inline group；官方完整page也無inline group（可能把數學放在text裡），因此不能只憑某個公式字串出現就宣稱inline typing／relativeposition／paragraph preservation成立。具體公式、code、ordinaryprose和crosspage保真以獨立review為準，這裡不代填pass。

runner (`vlm/run.py`)與兩phase input/model/runtimehash均在第一次timing前凍結；22個成功job沒有重跑，也沒有inference/writer失敗。本輪每child持有同一qualification lock，available≥8GiB、180秒、每0.25s sampled process-tree RSS≤6GiB軟停止，父程序kill/reap自身PGID；22個ownedgroups無殘留process (`vlm/post-run-process-check.json`)。不是OS硬memorylimit。verify.py (`vlm/verify.py`)無inference核對全部凍結bytes、actualCPU/device/dtype/budget、22次EOS/no cap、paragraphPNG pixels相等與engine清理重現；全部通過 (`vlm/verification.json`)。獨立geometry小測驗及44份sidecar也完成；geometrymapper第一次在尚未完成job的空folder遇缺檔後加skip，未更改inferencecode或重跑模型。

未執行公司GPU／serving、更多model／prompt調參、remote API、整份文件、完整corpus、Canonical mapper或正式Processing Profile採用。本輪能力／品質判斷仍須結合producer selection gate、reinsertion adapter及獨立來源核對；來源含數學卻無gate字元時可能漏選，模型識別成功亦不自動成為可信交付。
