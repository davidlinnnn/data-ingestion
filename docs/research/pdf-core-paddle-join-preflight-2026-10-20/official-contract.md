# PaddleOCR-VL → Docling：零推論交付契約查核

2026-10-20；僅查官方固定版本原碼及既有來源快取，沒有安裝、權重下載、模型載入或推論。這份筆記不是模型準度或完整 runtime 已通的證據。

**結論：官方 importer 是「既有單頁結果的結構轉換」，不是完整 Paddle pipeline，也不是無損 canonical converter。** 若採 Paddle 原生 Markdown＋原始逐頁 JSON／圖像＋Docling 補充結構，可以繼續作有界接合測試；若要求 stock Docling 同時無損還原 inline、code、圖片與跨頁結構，目前契約不足。

## 固定身分

| 元件 | 固定版本／commit | 本次核對 |
|---|---|---|
| Docling importer | 2.132.0／`5c349dd696d81c67fe29c378a4fdff08e28090bd`；2.140.0／`0e54294231b69bc2cf7a39873235495788f76b57` | 兩版同一檔案均 11,945 bytes，SHA256 `53597708ea8cde2f3477c49bdbd461c0a7868f8401c4153f9f536f5694eb1839`，逐 byte 相同 |
| PaddleX | 3.7.2／`ffb64904d23708863ff5b8da312a5cbd52a7f462` | result SHA256 `1a7f4070a7a978cdbd26eda900b61745bed3eb3ca3eca56d66eb553e8babe77b`；pipeline `32966d14aad6ac1bc043737c96352a4f0b4efcbead96f9354254dd4b9d1c6675` |
| PaddleOCR usage/wrapper | 3.7.0／`b03f46425e8ff4442b268ce449e3eef758146cd4` | 官方完整流程包括 layout／讀序／裁圖，再逐區 VLM；單呼叫 VLM 不等於完整 pipeline |

來源：[Docling 2.132 importer](https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/utils/paddleocr_vl_utils.py)、[2.140 importer](https://github.com/docling-project/docling/blob/0e54294231b69bc2cf7a39873235495788f76b57/docling/utils/paddleocr_vl_utils.py)、[Paddle 完整流程說明](https://github.com/PaddlePaddle/PaddleOCR/blob/b03f46425e8ff4442b268ce449e3eef758146cd4/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md)。既有下載與 hash：retrieval.json (`docs/research/pdf-core-g2-preflight-2026-10-16/candidate/retrieval.json`)。

## 逐項契約與必要界線

| 項目 | 官方實際行為 | 接合要求／限制 |
|---|---|---|
| 座標 | pipeline 在 `doc_preprocessor_res.output_img` 跑 layout／crop；`width/height` 也取這張 processed image。Docling 使用 `block_bbox`、TOPLEFT、processed raster pixels，`charspan=(0,0)`。polygon 原始值未進 Docling provenance。 | 原 PDF points／旋轉前座標不可直接沿用。先固定 orientation=False、unwarp=False；保存實際輸入 PNG、尺寸、來源頁／render 矩陣／hash。多邊形及 block IDs 原樣留 sidecar。 |
| 旋轉／去扭曲 | preprocessor 先 rotation 再 unwarp。其 JSON 只存設定與 angle，沒有輸出可逆的 dense warp 對應；實際 input／rotated／output images 是 live arrays。 | 開啟 unwarp 後，不可只靠 angle 宣稱能回投原 PDF；本輪不實作反變換。 |
| 圖片 | live block `.image={path,img:PIL.Image}`；`imgs_in_doc` 另收 crop。一般 `.json`／`save_to_json` 不含 image bytes；私有 `_to_json(keep_img=True)` 不是可攜圖像檔封裝。`save_to_img` 輸出 preprocessor/layout/spotting 視覺化，並非圖片資產匯出替代品。 | 必須保存 native Markdown image map／實際 crop bytes；Docling `PictureItem` 沒有 importer 自動附 bytes。只存 JSON 不能恢復 live 圖片。 |
| 圖片 key | `construct_img_path(label,bbox)` 只有 label 與整數 bbox，沒有 page/document identity；converter 用此字串當 dict key。 | 不同頁同 label＋bbox 會 key 碰撞／磁碟覆寫。逐頁隔離目錄後保留相對資產，或建立含 source/page identity 的映射；禁止悄悄覆寫。 |
| 頁號 | Paddle PDF `page_index` 是 0-based；Docling 轉為 1-based。PNG 常為 None，只能透過明確來源 manifest／`page_no` 指定真實原頁。 | 分開的 PNG 不可因 list 順序就冒稱原 PDF 連續頁。維持 source hash＋source page＋provider page index 的明確對應。 |
| 讀序 | importer 按 `parsing_res_list` 現有順序新增；不以 `block_order` 重排、不重跑 Heron／ReadingOrderModel。 | 讀序責任在 Paddle 完整流程；原始 order/group IDs 另保留，不能用自訂欄位排序掩蓋模型錯序。 |

座標來源：[Paddle pipeline](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py#L879)、[preprocessor](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/doc_preprocessor/pipeline.py#L167)、[preprocessor JSON](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/doc_preprocessor/result.py#L82)。新讀 source SHA256 分別是 `9d75e4d0c628c8e01bd23c5637b8bce218cab19fc4c1bac5ec898a04b66b23f2`（preprocessor）與 `ae21fff10a3510f0b0669c315e1b432b77d11b49b11fe751e028a6c9b6e69832`（result）。

圖片來源：[live Result 與 JSON](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/result.py)、[圖片路徑與 crop](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/layout_parsing/utils.py#L333)、[Markdown map collection](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/converter/markdown_converter.py#L74)。`layout_parsing/utils.py` 新讀 SHA256 `c689481cd1d93d614a51732e146be15ce44123acb1fb72fe3dd08475255afe42`。

## 多頁：保留原始頁，再執行官方 restructure

`restructure_pages(merge_tables=True,relevel_titles=True,concatenate_pages=False)` 會設定 global IDs、以官方規則合併跨頁表／重訂標題；它會修改 live blocks 與輸入 page dict。**必須先封存原始逐頁 JSON／資產，再對另一份物件跑 restructure。** 它不是一般的跨頁 paragraph join 保證。

saved-dict 分支要求 `{"res":payload}`，清空 `imgs_in_doc`，對所有 block content 去除 `^#+\s`，並把可推導圖片設成 `img=None`；這會影響 code comment 與圖片交付，不等同 live 結果。`concatenate_pages=True` 將 `page_index=None`、`page_count=len(pages)`，同時沿用第一頁 canvas；block 的動態 page_index 亦未由一般逐 block JSON serializer 輸出。**Docling importer 明確拒絕這種多頁拼接 payload，`page_no` override 不能解除拒絕。** 使用官方單頁 import＋來源對應側錄；不能將拼接後 bbox 冒稱單頁座標。

來源：[restructure_pages 固定實作](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/pipeline.py#L1251)、[官方跨頁使用範例](https://github.com/PaddlePaddle/PaddleOCR/blob/b03f46425e8ff4442b268ce449e3eef758146cd4/docs/version3.x/pipeline_usage/PaddleOCR-VL.en.md#python-api)、[單頁 importer 限制](https://github.com/docling-project/docling/blob/5c349dd696d81c67fe29c378a4fdff08e28090bd/docling/utils/paddleocr_vl_utils.py#L187)。

## Markdown／結構表示：兩者不是等價輸出

| 能力 | Paddle native | stock Docling importer／Markdown |
|---|---|---|
| table | `block_content` 保存 HTML，native Markdown 也可交付 HTML table；跨頁表合併是額外官方步驟 | `_add_html_table` 轉結構，不保證每種表頭語意／原始 HTML 無損；Markdown 可展平 span。保留 raw HTML 才能追溯 |
| formula | formula handler 原樣傳 content；不自行替 bare LaTeX 加 delimiter。`show_formula_number=True` 可在相鄰 display formula＋number 加編號 | 各 formula label 都變 FormulaItem；分離 inline formula 沒有正文插入位置/group 還原。原 provider delimiter 可與 stock serializer 再包裝衝突 |
| code | algorithm handler 只去首尾換行，不建立 code fence／language／typed CodeItem；已存在 fence 可保留 | algorithm→TEXT；完整字串可存在 JSON，但 Markdown escape／換行不保證 code 語意忠實 |
| image enrichment | image OCR 開啟時，native formatter 可把 OCR content 直接放在圖片下方；chart recognition 可轉 HTML 表 | picture-like content 另變一般 TEXT，沒有 typed OCR/caption attribution。不能直接當作來源正文承諾 |

來源：[native format handlers](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/converter/markdown_format_funcs.py#L300)、[converter](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/converter/markdown_converter.py)、[native Result formatting](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/pipelines/paddleocr_vl/result.py#L300)。既有純 converter／perfect-provider 行為測試見 [2026-10-16 findings](../pdf-core-g2-preflight-2026-10-16/candidate-findings.md)；本次沒有把那些純元件測試改稱完整 Result runtime 測試。

`save_to_markdown(pretty=False,show_formula_number=True)` 會呼叫 native converter，將 `markdown_texts` 寫檔並逐一保存非空 `markdown_images`。須實際驗證相對 image path、bytes、頁隔離與重新讀取，而非只檢查 `.md` 有產生。source：[MarkdownMixin](https://github.com/PaddlePaddle/PaddleX/blob/ffb64904d23708863ff5b8da312a5cbd52a7f462/paddlex/inference/common/result/mixin.py#L757)。

## 允許的最小 packaging 與停止條件

必要且不改辨識語意：原始頁 JSON／PNG／crop bytes 封存、source/page key、相對路徑命名空間、hash／尺寸／座標系 manifest、JSON reload 邊界驗證、同來源頁序的明確組裝。保留兩種輸出及其版本關聯，不將原生 Markdown 重新說成 stock Docling 完整序列化結果。

不在本輪默默加入：推測跨頁 paragraph／inline slot、補 code fence／縮排、數值修字、自訂讀序、圖像描述併入來源正文、去除重複 OCR、反推 dense warp。若必要功能只能靠這些語意補救達成，記為接合缺口並停止該必要能力的合格判定；不得以「模型可能剛好輸出好格式」視為已解決。

**待證：**完整未改 Result／save runtime、真正 Paddle 輸入與 crop、模型品質、速度、資源、公司 CUDA／高頻負載。零推論能判定表示與封裝能力，不能判定模型能否解決雙欄讀序。
