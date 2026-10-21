# C：真實 native 輸入、同版 image-key 接點與來源評估

2026-10-18（Asia/Taipei）。**已實作 55 頁的通用 native producer，實際交付 29 個 crop／image keys、58 個遠端候選 request 與 29 個本地 OCR 工作。輸入接點成立，完整 C 仍被來源裁切與原文 caption 缺陷阻擋。** 沒有把人工圖片清單變成 producer jobs，也沒有執行 VLM／API／下載／安裝／holdout。

## 實際上游與成本

固定範圍沿原三段計畫的 13 來源／55 頁。保留 11 頁同版 cached S0，只對缺少的 44 頁跑一次 CPU Standard，共 12 ranges，全部 conversion status=success、pages 與來源 SHA 符合登錄。

| 項目 | 固定／觀測 |
|---|---|
| Runtime | Python 3.12.13；Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3；80 套件版本符合 root runtime lock，8 個執行來源檔 SHA 與 9 個模型／設定資產 SHA 核對 |
| Pipeline／backend | StandardPdfPipeline／PyPdfium；image scale=2，page/picture images 開啟 |
| Layout | Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`，CPU FP32、compile=False、threshold=0.3 |
| OCR | RapidOCR PP-OCRv6 det_small／rec_small＋mobile_v2 cls，ORT，selective OCR、text_score=0.5、CPU4／interop1 |
| Table | TableFormer V1 accurate、cell matching=True；OCR/layout/table batch 均 1 |
| 未啟用元件 | code/formula、heading recovery、classification、description、chart enrichment；沒有把 baseline 當完整 profile |
| 新 CPU conversion | 44 頁合計 80.8200 秒；監督程序總 84.6112 秒；觀測 peak tree RSS 6,624,772,096 bytes |
| 新 VLM／API | 0；公司 Qwen3／GPU／vLLM 未驗 |

`native-preregistration.json` 保存完整 options、17 個 active-asset/source SHA、來源範圍及 25 分鐘／12 GiB／minimum available 8 GiB 的 CPU 界線。每個 conversion 前都核對 PDF SHA 與固定資產；結束後再次核對。

**監督程序並非乾淨通過：** child 以 exit 0 完成全部 44 頁後，父程序最後一次 RSS 取樣撞到 `psutil.ZombieProcess`，記錄仍為 `parent_harness_error`。保留完整輸出與錯誤，沒有重跑 CPU；`cpu-output-validation.json` 獨立驗每份 status／實際頁碼／runtime／資產，再採用這批不可變產物。這支持輸入盤點，不能稱 watchdog 可靠性或 fresh-restored worker 通過。

更早兩個 launch 在 pipeline 初始化前停止：sandbox process visibility denied，以及停用 chart 的 `supported_engines` 集合順序造成 equality 拒絕。兩份 preflight 原件均保留；只將該未啟用集合排序後比較，實際 options 保存。這些不是模型／prompt 重試。CPU 程序已加 existing-attempt guard，避免誤重跑。

## Producer 已具體做什麼

`scope.json` 只有固定來源／頁段。`producer.py` 先讀公開 native 結構，對**全部 native PictureItems** 用保留的 public `get_image`／native mapping seam 建立實際裁圖，不依面積、分類、文件 ID 或已知答案篩選。

`producer-inventory.json` 是 19 ranges／55 頁／29 個 native pictures 的固定結果。每個 crop 都驗與 page image 的整數 crop window 逐像素相等；所有 29 個同版 key 都是 `hash(document_revision, owner_ref, crop_sha256)`，含來源、完整 provenance、caption refs、children、mapping 與 unknown classification。沒有 multi-provenance picture；若出現，既有 seam 會明列 unresolved，不猜合併。

`producer-custody-v1.json` 在 evaluator 讀本輪來源清單前固定 inventory／crop 責任；之後只修已審出的 schema／wire materialization 邊界，未按來源清單加減任何 jobs。初版 requests／程式保留在 `interface-precheck-v1/`。

一個 WikiSkill p9 text provenance 超出頁寬，公開 Core load 時有 clamp warning。原 baseline bytes 未改；本輪 revision 依公開 load 後的 graph 計算，不能冒稱 raw JSON graph 未經標準化。所有圖片 mapping／pixels 另核對，沒有用這項 warning 去修 crop 或內容。

`bundles/` 實際保存 19 組 document JSON／主要 Markdown／supplement，使用上述 image keys 和真 crop URI。supplement 所有工作仍是 unattempted、provider_results=[]。JSON reload 後，除 picture resource URI 外原 graph、正文、children、caption、順序皆相同；主要 Markdown 逐 byte 一致，不插入生成內容。首個驗證因 `read_text` 換行正規化誤報，原件保留；改為 UTF-8 bytes 比較，未修來源字詞。這是實際 native 輸入交付，沒有新增 MOCK 圖意／OCR 來湊成績。

## 固定候選 request 與真正可執行程度

| 項目 | 值／狀態 |
|---|---|
| 遠端候選上限 | 58＝29 個 description＋29 個 chart assessment；每個一次、concurrency=1、retry=0 |
| 本地 OCR 工作 | 29；沿既有 RapidOCR 資產／options，30 秒／job、content cap 500,000 bytes；本輪未另跑 |
| 遠端身分 | 暫用 `https://api.openai.com/v1/chat/completions`、`gpt-6-luna`、high detail、low reasoning、store=false；alias 不等於 immutable weights 或公司模型 |
| 每 job tokens | input 為事前 heuristic reserve；completion cap 6144（含 reasoning） |
| 總 tokens | input reserve 605,230；completion cap 356,352 |
| 實際輸入量 | 58 個帶真 PNG data URL 的 UTF-8 JSON body 共 4,947,137 bytes；重複任務合計 9,076,626 pixels |
| Transport／時間／記憶體 | request ≤8 MiB；response envelope ≤2,000,000 bytes／job，content ≤500,000；總 response 上限 116,000,000；每 job 180 秒，遠端總 cap 10,440 秒；RSS 12 GiB／available 8 GiB |

**58 是目前保守 producer 的候選成本上限，並非推薦 production 工作量，更不是 N₃。** Source census 的 19／18／9 是來源責任，不能換算成相同 calls。現階段 58 也包含公式圖、表格內小圖示和非 chart assessment 的額外成本。

`requests.json` 包含每筆實際 crop、binding、prompt/body、schema hash、template hash、**實際 Base64 materialized HTTP body SHA**、tokens／bytes／time caps。`materialize()` 會重算 crop SHA 和 template，`validate_response()` 核對 request、input、model、整數 usage/caps、finish/refusal，再驗已知 payload 型別。Unknown provider fields 原樣保留；unreadable value 明示 null，不把它計成正確觀測；not_chart／unsupported_chart／unknown 分開。

15 個負控制拒絕錯 crop／revision／request、截斷、空描述、錯 list element、錯 model、bool usage、token overrun、失敗 OCR 冒充文字、未知 chart kind、空 supported chart 及 null estimated value。6 份歷史真實 payload 通過已知內容 schema 相容檢查，**沒有重綁到新 owner**，也不算新準度。

輸入 materialization 與宣告的 envelope validation 已可檢查；**本來源／接口階段不實作 HTTP client**。目前大小檢查針對重建的 envelope，並未證明 predecode streaming 限流、累計 usage＋下一 job reserve、hard deadline／RSS 在 live client 中被強制執行。input reserve 也非 provider 精確 token 保證。因此本階段封存的 `remote_execution_ready=False`、`live_run_budget_enforcement_ready=False`；不送出任何 request。另由主線整合獨立 transport 子輪（`runner.py`／`runner-verification.json`）；它使用獨立驗證／seal，不能回寫本階段成為已驗 live client，也不能抵銷 source gate。

## 來源對照與新評分契約

`compare_source.py` 是獨立 evaluator，使用來源頁＋已固定 crop 視覺對照後，才建立人工評估關聯。這些 source locators 不會被 producer 讀取。

| 來源對照 | 結果 |
|---|---|
| 55 頁／19 個 logical source groups | 19／19 都找到一個 native owner；不是語意準度 100% |
| SEAL Figure 1 | **material partial input**：完整 `RL Outer Loop Iteration t` 標題不在 crop，主圖分支可見；A 的數學責任未被 C 免除 |
| ReasoningBank Figure 5 | **material original-caption failure**：native `#/texts/68` 混入鄰文、破碎並重複；描述 API 不可替代 source caption |
| WikiSkill Figure 1 | caption 留在 standalone `#/texts/28`，picture 未連 caption；未知關聯本身不判失敗。末一個 x label 貼邊，未做特例修正 |
| 額外 10 個 native candidates | Controls 三個公式圖、WikiSkill Table 3 七個 check/cross 圖示；分別是 A／B 來源責任，但保留在本 C 候選成本，未人工刪掉 |

同輪 evaluator 補上：WikiSkill Figure 1 的 16 個幾何估值；WikiSkill Figure 3 的 68 行完整圖內 literal inventory 與 8 組圖意要求；Memory-R1 Figure 6 的 18 個彩色上邊界估值、Figure 7 的 12 個 finite plotted-ink intervals，以及 Figure 8 的 F11 關係。F8 scatter 不新增 all-point numeric 門檻。Dense curves 的通用 protocol 在每 panel／series 的 x-range 1/8、1/2、7/8 取樣，保存 ink uncertainty 與整體趨勢；這些不冒稱連續 raw data。既有 G1 42 個 printed 真實圖值、13 個受控圖值及 S05/S07/E10 關係契約繼續保留，分母分開。

完整 screenshot／timeline 的全部圖內文字與逐項語意契約仍有未完成處；圖像 presence、少數關鍵詞、caption 或 PDF text 輔助都不能代替完整 OCR 驗證。Source-contract index 明列已凍結與 pending。failed OCR 只保存診斷，不等於必含工作成功；no_text 須有方法證據，unknown classification 不豁免工作。

## 收斂結論

可以保留這個 **public native input → image key → unattempted supplement／source Markdown** 接點及嚴格回應邊界。已具體量出保守工作量，無需再做 MOCK-only replay。

完整 C 尚不能進付費整合：SEAL source-image 邊界、ReasoningBank 原文 caption 先保留為必含阻擋；全圖 OCR／語意契約和 live 預算強制執行仍待補。不得用人工來源圖號補 crop jobs，也不以全部 29 個 crop 可保存就聲稱 source coverage 合格。`N_C_candidate=58`，**完整 profile 的 N₃=null**。

本輪未測新 VLM 品質、公司 GPU、heading／四方向完整配置或 worker／Pod 恢復。
