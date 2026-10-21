# 固定外部回歸：分層抽樣、版本與評分契約

2026-10-18（台北）。**已完成 metadata／annotation／code 鎖與真實 60 頁選樣；尚未取得 page inputs、安裝或執行官方 evaluator，也沒有任何模型推論。** 這是 B／C 收斂後使用的 targeted external regression，不是全量榜單、隨機代表樣本或公司獨立 holdout。這次不改原實驗或 production。

## 固定版本與可核實 bytes

- Official code commit：`f133a71e9e91c3621c7ce8994200a7b394a06eb3`。[官方 commit](https://github.com/opendatalab/OmniDocBench/commit/f133a71e9e91c3621c7ce8994200a7b394a06eb3)
- Dataset revision：`aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec`。[固定 dataset tree](https://huggingface.co/datasets/opendatalab/OmniDocBench/tree/aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec)
- `OmniDocBench.json`：42,208,096 bytes／1,651 頁；實際下載 bytes 的 SHA256 為 `a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496`，與官方 LFS metadata 一致。只取得這一個 annotation JSON，存於 `<tmp>/pdf-core-omnidocbench-eval-20261018/OmniDocBench.json`，權限 0600，沒有放進 repo；未取 images／PDF。[官方 annotation metadata](https://huggingface.co/datasets/opendatalab/OmniDocBench/blob/aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec/OmniDocBench.json)
- `upstream.lock.json`含官方 code／config／dataset card schema 說明及 API metadata 共 15 個小型 snapshot 的來源 URL、bytes、SHA256。Code commit 固定整體來源；沒有宣稱已下載整份 evaluator 或建立 runtime image lock。Dataset card 是官方描述式 schema，不是假稱官方另有正式 JSON Schema。`artifacts.json`鎖本次方法、規則、manifest 與本地 snapshot。

README 的版本名稱與 package metadata 不完全一致，故以以上 commit／revision／bytes 為準。[固定 README](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/README.md)、[固定 package metadata](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/pyproject.toml)

## 已固定的 60 頁

`sampling.json`是本案 preregistration；`sample.py`只取 category／attributes／IDs／provenance metadata，不匯出 text、LaTeX、HTML、polygons 或答案。Seed 是 `pdf-core-external-regression-2026-10-18-v1`。同一頁依下表優先歸入唯一 stratum，無 output-driven reselection；quota 不足會列 deficit，不挪用。Stratum 內先 language round-robin，再 document type round-robin，各 cell 以 `SHA256(seed + NUL + page_id)` 排序。

| Primary stratum | Metadata 判斷 | 可選頁 | 固定頁數 |
|---|---|---:|---:|
| Table math | 非 ignore table＋page `table_with_formula` | 51 | 10 |
| Merged table | 其餘 table＋page `table_span` | 85 | 10 |
| Other table | 其餘非 ignore table | 322 | 8 |
| Figure＋來源 caption | 其餘頁有非 ignore figure／figure_caption | 278 | 8 |
| Display formula | 其餘頁有 equation_isolated | 258 | 8 |
| Degraded scan | 其餘頁有 fuzzy_scan／fuzzy_content／geometric_deformation／transparent_pages | 25 | 8 |
| Multicolumn／other layout | 其餘非 single_column 頁 | 270 | 4 |
| Ordinary-text control | 其餘 text_block，無 table／figure／display formula／code block，無顯著 page issue | 156 | 4 |

Page tags 是頁級 metadata，不保證該頁每張表都有 span／math；沒有解析 GT table 答案來選樣。現行 annotation 的 block `attribute` 全為空（已盤點），所以直接使用已存在 page tags，沒有用內容補標。Ordinary-text control **可能有 inline formula**，不是 formula-negative。部分其他頁不屬於本輪 primary strata。

`sample-manifest.json`固定完整 60 個 page IDs、attributes、category counts、seed rank 與分母，沒有 GT 答案。各 primary quota 均滿足；marginals 如下：

- 語言：英文 22、簡中 20、中英混合 12、繁中 5、other 1。
- 文件：PPT2PDF 14、book 14、academic literature 9、colorful textbook 8、exam paper 10、magazine 3、historical document 2。**沒有 newspaper／note／research_report**。
- Layout：single column 35、mixed 4、other 16、double column 5。**沒有 three column**。
- Subset：v1.5 40、table hard 5、layout hard 14、equation hard 1。

以上是有意偏向 B／C 的小型外部回歸，不能包裝成覆蓋全部 10 類文件的代表性 Overall。`metadata-inventory.json`與 manifest 明列缺少的 strata／marginals。沒有為補漂亮分布而根據候選輸出換頁。

## Source family 與 custody

實際 `page_info` 只有 height／image_path／page_attribute／page_no／sample_id／width，沒有可驗證 document／source family ID。**60 頁的獨立 source families 驗證數為 0**；全部歸入同一 `unresolved-provenance` pool，不把 UUID、page_no 或 filename prefix 猜成 paper identity。若未來有明確 source document ID／PDF SHA，sampler 對該 verified family 全局最多選 2 頁；unknown pool 不錯套此 cap。這是保守相關性記錄，不是證明 60 頁來自同一文件，也不是 60 個獨立文件。

因此本輪不切 DEV／confirmatory、不報 page-IID 信賴區間或「60 個獨立來源」；只報 paired、逐頁／逐 stratum 的描述性差異。若後續要 source-disjoint split，先取得獨立 provenance map、確認與既有 DEV 不重疊，再建立新 registration，不能補造 family。公開 benchmark 的模型訓練污染未知，也不稱公司盲測。

Evaluator custodian 讀 GT；producer 只取得鎖定的來源輸入及固定接口，不取 GT、oracle bbox、答案或 matching 結果。這是角色／流程隔離，並非聲稱同帳號 workspace 有強制存取隔離。GT 有效期限／保存另依研究流程管理；本次 private tmp 不代表長期保管。看過逐案 GT 並用來調模型的樣本須改列 DEV，若需確認性驗證則重新登錄未曝光樣本。

## 固定評分與必要條件

`scoring.json`鎖定 JSON GT 的 `end2end_dataset`：text Edit Distance、display formula Edit Distance／CDM、table TEDS／Edit Distance 與 TEDS 自帶 `TEDS_structure_only`（TEDS-S）、reading order Edit Distance。保持官方 category／ignore／normalization；不改 GT 幫候選加分。[官方 config](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/configs/end2end.yaml)、[TEDS／TEDS-S 輸出實作](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/src/metrics/cal_metric.py)

Matching 固定 `quick_match`、單 worker、300s truncated／420s page timeout、開啟官方 timeout fallback（max span 10、order penalty 0.10）；CDM／TEDS 各單 worker。保存 unmatched、ignored、timeout、fallback 原因及數量，matching 只屬 evaluator，不能回饋 producer routing。[官方 page matching 實作](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/src/dataset/end2end_dataset.py)

所有 60 頁保留在 delivery 分母，conversion／routing／inference／truncation／export／metric failures 不刪頁，不只報成功平均。官方得分照實保存，另外列有效 scored units／pages、空類別 N/A、failures；官方 evaluator crash 不自創「0 分」偽裝成可比官方成績。若官方自行給特定例外 0 分，保留原結果與例外記錄。沒有 official aggregate 就報 unavailable。

仍須通過本案補充 gate：B 每張 logical complex table 數值錯誤 ≤5%，必要 header／condition binding 與關鍵比較正確，table math 的 scope／運算保留；跨頁表需完整文件另驗。C image census、原 caption、image-key supplement／provenance 與 source/generated separation，以及真實 image OCR／description／chart grounded accuracy 另驗。A inline／code 意義、識別字、運算與順序仍獨立核對。**TEDS 95 ≠ 5% 數值錯誤；CDM ≠ 代數等義；Overall 不會抵銷必含功能失敗。**

## 後續可執行條件與成本分列

1. B／C 的單一 candidate method 與 Standard baseline 都固定，另登錄模型／prompt／參數、runtime image digest、硬體／並行與 paid calls／tokens 的總上限。當前授權執行範圍的模型呼叫數是 0；這份 60 頁 manifest 本身不啟動推論。
2. 取得 manifest 指定的 images，逐檔 hash，記錄 DPI；baseline／candidate 使用相同 bytes。若轉 raster-PDF，固定轉換器／政策並兩臂一致。當前只有 annotation 和 metadata hashes，**page assets／hashes 尚缺**。
3. 評分環境單獨建立並驗證固定版本；本次未安裝或跑 official evaluator。該套件要求 Python >=3.10,<3.12，CDM 另需 Linux／TeX Live／ImageMagick／Ghostscript 等，runtime 必須另外鎖定。[官方依賴](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/pyproject.toml)
4. Ingest latency（含所需 component 推論）與 matching／TEDS／CDM 的**離線評分耗時、記憶體分列**；image→PDF preprocessing 另列。記錄 calls／tokens／pixels、失敗、cold／warm／硬體。不可用像素估算替代實際 latency，也不是正式 SLO。
5. Image／raster track 只代表視覺／OCR 路徑；不能當作保留 native text＋selective OCR 的 born-digital PDF 準度／latency。Original PDF 的供應、文字層、GT 對齊未核實，另保留原生完整 PDF 套件。官方 image→PDF 只嵌圖；Docling 範例讀 `pdfs` 並不能證明該 folder 是 original。[官方轉檔](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/tools/image_to_pdf.py)、[Docling 範例](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/tools/model_infer/docling_img2md.py)

Code license 與 dataset card 的研究用途／非商用聲明均已保存；這次是方法及研究評估 custody，沒有作商用許可結論或併入 production。[固定 dataset card](https://huggingface.co/datasets/opendatalab/OmniDocBench/blob/aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec/README.md)

## 重現與 freeze 保護

只檢查本地鎖與方法測試，不讀 GT、不連網、不執行 official evaluator：

```sh
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-eval-interfaces-2026-10-18/evaluation/check.py
```

Evaluator custodian 才能以 `sample.py --annotation <tmp>/pdf-core-omnidocbench-eval-20261018/OmniDocBench.json` 重播選樣。它先比對實際 annotation hash，既有產物若 bytes 不同會拒絕，沒有 refresh／force 開關。`check.py`只比較期望 hash，不刷新。未重用既有六份公司 holdout 的特定 validator：其 custody／分母綁定不同，本次也沒有開啟那些 holdout。

目前 readiness：**metadata/version lock 完成；60 頁 selection 完成；評分契約完成；live evaluation 尚未就緒；production 未合格。**
