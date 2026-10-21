# 下一個固定候選：PaddleOCR-VL-1.6 完整流程

2026-10-16。依 research skill 查核官方固定來源；本輪只預檢交付接點、保存小型原始碼／config／metadata，**0 模型載入、0 推論、0 API inference、0 安裝、0 權重下載**。沒有讀 holdout，也沒有另找候選。這是[原 next-cycle-options](../pdf-core-g2-official-method-2026-10-15/next-cycle-options.md)中第二條的具體化，並延續新 audit (`docs/reviews/pdf-core-experiment-audit-2026-10-16.md`)的實際影像、連續頁、表示與 raw fidelity 分層。

**固定一個方向：Paddle CPU layout＋本機 MLX VLM，Paddle 原生 Markdown 作主交付，原始單頁 JSON／圖像與 Docling 結構作補充。狀態是 `awaiting_native_result_export_and_input_preflight`，尚未成為可推論或合格 challenger。** 純 converter 元件已實測，但完整 `PaddleOCRVLResult`／`save_to_markdown` 整合和實際 Paddle 輸入尚未驗；也已有不依賴模型準度的 code／inline 接點缺口。

## 固定版本與方法

| 部位 | 唯一選擇與證據 |
|---|---|
| 官方整體流程 | `PaddleOCRVL(pipeline_version="v1.6")`，PaddleOCR **3.7.0**／commit `b03f46425e8ff4442b268ce449e3eef758146cd4`；PaddleX **3.7.2**／commit `ffb64904d23708863ff5b8da312a5cbd52a7f462`。官方明確區分 layout＋各區域 VLM 與僅呼叫 VLM；不把整頁直接送 MLX 服務冒充完整流程。[固定 wrapper](https://github.com/PaddlePaddle/PaddleOCR/blob/b03f46425e8ff4442b268ce449e3eef758146cd4/paddleocr/_pipelines/paddleocr_vl.py)、[固定完整流程說明](https://github.com/PaddlePaddle/PaddleOCR/blob/b03f46425e8ff4442b268ce449e3eef758146cd4/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md) |
| Layout | **PP-DocLayoutV3**；`PaddlePaddle/PP-DocLayoutV3@241f8bdfc77a7c7bee915a5057aaee58c235a8d3`，Paddle CPU。不是基礎 `PaddleOCR-VL.yaml` 裡的 V2；必須用 **PaddleOCR-VL-1.6.yaml**。該 config 預設 threshold0.3、NMS=True、unclip `[1,1]`，有 inline/display formula、algorithm、table 等類別。[固定 config](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/configs/pipelines/PaddleOCR-VL-1.6.yaml)、[固定模型 config](https://huggingface.co/PaddlePaddle/PP-DocLayoutV3/blob/241f8bdfc77a7c7bee915a5057aaee58c235a8d3/inference.yml) |
| VLM | **PaddlePaddle/PaddleOCR-VL-1.6@c5630abae1d940eafe0697512a0325494b02ab42**，官方原始 checkpoint，不換社群量化版本。PaddleX 模組名稱是 `PaddleOCR-VL-1.6-0.9B`；HF repo 名稱則如左，兩者不能混成猜出的新 model ID。[固定模型卡](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6/blob/c5630abae1d940eafe0697512a0325494b02ab42/README.md) |
| Apple 執行方法 | Python3.12、PaddlePaddle **3.2.1** client runtime，`vl_rec_backend="mlx-vlm-server"`，服務在 `http://127.0.0.1:8111/`；model name 必須指向上述 revision 的**本地 snapshot 絕對路徑**，不能讓 HF `main` 漂移。MLX-VLM **0.7.8**（tag commit `9790231827a890eade1a626643a6bc94a1317c72`）、MLX／MLX-Metal **0.32.4**；現存 MLX 只有程式碼，未載入 Paddle checkpoint。[官方 Apple 指南](https://github.com/PaddlePaddle/PaddleOCR/blob/b03f46425e8ff4442b268ce449e3eef758146cd4/docs/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.en.md)、[固定 MLX Paddle module](https://github.com/Blaizzy/mlx-vlm/blob/9790231827a890eade1a626643a6bc94a1317c72/mlx_vlm/models/paddleocr_vl/paddleocr_vl.py) |
| Docling 補充結構 | **Docling-slim2.132.0／Core2.99.0**，官方 `parse_paddleocr_vl_result`。這是已確認存在的 released stack，不再只引用 moving main；不聲稱最早 release。v2.132.0 commit=`5c349dd696d81c67fe29c378a4fdff08e28090bd`。[固定 importer](https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/utils/paddleocr_vl_utils.py)、[固定測試](https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/tests/test_paddleocr_vl_utils.py) |

Apple 指南列 CPU Paddle＋MLX service 路徑，官方實測硬體為 M4；本機是 M5 Pro，因此「有官方路徑」不等於本機已通。PyPI metadata 確有 Paddle3.2.1 cp312 macOS arm64 wheel，PaddleOCR3.7.0 的 PaddleX 範圍包含3.7.2；這只證明套件候選相容範圍，沒有安裝成功證據。Paddle client 必須隔離安裝，先產生完整 transitive lock，不能把依賴塞入既有 Docling／MLX runtime。[官方套件 metadata](https://pypi.org/pypi/paddleocr/3.7.0/json)、[Paddle3.2.1 metadata](https://pypi.org/pypi/paddlepaddle/3.2.1/json)

固定 options：layout=True；orientation/unwarp=False（維持固定 PNG 像素座標）；merge_layout_blocks=True；format_block_content=False 保存 raw content；markdown_ignore_labels=[]；queues=False、單張／單區域 batch、concurrency1；chart recognition=True；seal/image OCR=False；min_pixels112896、max_pixels1003520、max_new_tokens4096、temperature0、top_p1、repetition_penalty1。原生save選`pretty=False`、`show_formula_number=True`以保留公式編號；本次純converter cases以False執行且沒有formula_number輸入，True的相鄰公式編號整合仍列待測。這是待實作的唯一配置，不是已執行設定。真正 service request／processor 參數仍須在零模型 setup 與正式登記中核對。[固定 pipeline](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py)

不另寫特殊 code prompt：完整流程自行將公式區域送 `Formula Recognition:`、表格送 `Table Recognition:`、chart送 `Chart Recognition:`，algorithm 走 `OCR:`。`prompt_label` 只在關閉 layout 時生效，不能拿它替完整流程改善 code。沒有官方 code-fence／縮排保證。pipeline 對含 `\\(...\\)`／`\\[...\\]` 的整個區塊會移除所有 `$` 再換 math delimiter；這是 raw provider JSON 之前的已知轉換，需把混合 code／math／美元 literal 納入下一個無模型 helper test，而不能在後端猜補。[固定 routing／normalization source](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py)

## 已完成的真實 parser／Markdown 預檢

現存 `<tmp>/pdf-core-g2-dots-mlx-20261016/venv` 的 importer SHA256=`53597708ea8cde2f3477c49bdbd461c0a7868f8401c4153f9f536f5694eb1839`，與官方 v2.132.0 原檔**逐 byte 相同**，也符合 distribution RECORD。相關 chandra／vlm utility RECORD 符合；不是只看套件 metadata，更沒有替換 runtime source。見runtime identity (`candidate/runtime-identity.json`)。

先登記的合成 scope (`candidate/synthetic-scope.json`)將 perfect single-page provider JSON 送未改的官方 importer、Docling JSON round-trip、stock Markdown；結果 (`candidate/synthetic-results.json`)及[實際 Markdown](candidate/synthetic-document.md)已保存。可接受 bare mapping／`{"res": ...}`／JSON字串／bytes；JSON與Markdown round-trip穩定。負座標、超界 bbox、缺 page_index 的多頁拼接 payload 均拒絕。

| Perfect provider content | Docling2.132／Core2.99 的實測交付 |
|---|---|
| code literal／縮排 | JSON逐字保留，但 algorithm→TEXT；stock Markdown escape `< > & _`，連 fenced block 內都轉 entity且加 hard breaks，不能作忠實 code 主交付。 |
| 正文 inline LaTeX | JSON保留；stock Markdown escape underscore／`<`。獨立 inline_formula一律變獨立FormulaItem／`$$...$$`，provider group_id不還原正文。 |
| display formula | bare LaTeX得到單層`$$`；provider已有`$$`則變`$$$$`。是表示缺陷，不能算模型公式辨識失敗。 |
| table | rowspan／colspan與第一列表頭保留；第二列無thead／scope的`<th>A/B</th>`未標column_header，完整表頭角色未保真。帶scope=row的列頭保留；Markdown展平表格。 |
| title／caption | format flag=True時清理title／heading／caption wrapper；這不會自動建立picture-caption關聯。 |
| image／provenance | picture item沒有bytes、沒有typed caption；chart內容另存普通text。page_index2→page3，保留processed pixel bbox／TOPLEFT；polygon、provider block/group IDs與order欄位不進Docling JSON。origin hash=0／mimetype=application/json，不能冒稱原PDF hash／原頁point座標。 |

因此固定候選改以 **Paddle 原生 Markdown 為主**，Docling只是補充結構，不讓stock Markdown的損失拖累主內容。這沒有改模型或對題目答案做字串修補。

原生路徑也做了真正的**純元件 behavioral preflight**：先登記scope (`candidate/native-synthetic-scope.json`)，以完整未改的兩份官方v3.7.2 converter modules作正常namespace import，沒有AST抽函式、依賴stub、安裝或拼接完整Paddle runtime。使用官方DocumentBlock協定的合成輸入、`pretty=False`對應handler wiring。結果 (`candidate/native-synthetic-results.json`)、[原生Markdown](candidate/native-synthetic-document.md)。[固定 converter](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/converter/markdown_converter.py)、[固定 formatters](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/converter/markdown_format_funcs.py)

- **實測保留**：fenced code literal／縮排、正文內inline LaTeX、已有delimiter的公式、HTML表頭與span、header/footer；有真PIL image物件時建立正確reference與image map。
- **仍有缺口**：plain algorithm不補code fence（因此`#`／`<tag>`在Markdown可能被當標記）；分開的inline_formula即使同group仍插空行；bare公式不補math delimiter；缺image物件時省略image reference。這些不可以假設模型一定輸出恰好可用格式來消除。
- **尚未實測**：完整PaddleOCRVLResult→`save_to_markdown`與圖片磁碟交付。固定source顯示官方Mixin會存markdown_images，但這不能代替實際整合test。[固定 result](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/result.py)、[固定 save mixin](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/mixin.py)

## 進模型前真正剩下的工作

1. 在隔離的固定client stack作**零模型**完整Result／save_to_markdown合成test，確認code、公式、HTML表、圖片bytes能在原生Markdown＋同版supplement交付；若plain code或分離inline仍缺必要表示，先決定是否實作一個通用的結構保留接點。本輪沒有暗改官方parser，也沒有將這些缺口當作已解決。
2. 本輪renderer預檢v2 (`render-inputs-v2/results.json`)是**4個來源頁×2個backend＝8份rendered input**，不是8個不同頁面；視覺核准v2 (`render-approvals-v2.json`)核准6份可用輸入、拒絕2份變黑的DoclingParse validation影像。修正collection／gate沒有改原始像素。**僅可將已核准影像傳往後續階段**；這些仍是Docling實際PNG，尚不是Paddle actual input。Paddle須直接吃已核准PNG、關閉orientation/unwarp，保存Paddle實際layout輸入與VLM各crop／processor像素及hash後再目視核准；不能讓另一個PDF renderer悄悄重畫。這4個來源頁本身不是連續頁集合；跨頁context須另行固定並核准同來源的連續頁範圍，不能由目前collection推定已具備。
3. 多頁先保留原始每頁JSON與live result物件，再按同來源連續頁走官方restructure_pages。Docling importer只吃原始每頁結果，**不接受concatenated多頁payload**；官方restructure只合表／調heading／串頁，不承諾跨頁paragraph join。若用saved dict重建，官方程式還會對所有block content套`^#+\s`清理，可能傷到code comment，且無法從JSON回復image bytes；因此不得用該路徑假裝live結果。必要logical paragraph／image mapping用同版supplement明列，仍須實測，不靠手填oracle。[固定restructure source](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py)

上述通過後才有條件登記一次有界模型執行；本輪不啟動。模型品質、M5資源／時間、公司CUDA、高頻load及holdout均未驗。所有下載來源／hash見retrieval.json (`candidate/retrieval.json`)；只有小型source、config、metadata，沒有模型weights。
