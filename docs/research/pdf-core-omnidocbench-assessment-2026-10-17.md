# OmniDocBench 與 PDF core 驗證的分工

2026-10-17。以官方 repository、dataset card、論文及評分實作調查；本次只有文件／程式碼閱讀，沒有下載資料集、安裝 evaluator、模型或 API 推論，沒有開啟既有 holdout。

**建議現在採用它的分層評估與版本管理設計；B／C 方法收斂、配置固定後，再跑預先抽好的外部回歸。** 不應用既有少頁 DEV 的結果宣稱泛化，也不應直接把新 benchmark 變成另一組持續調 prompt 的 DEV。OmniDocBench 能擴大版型與內容多樣性，但不能代替我們的跨頁、圖片 enrichment、來源交付與公司獨立 holdout。

## 已核實的範圍與版本

| 項目 | 官方證據／對本案的意義 |
|---|---|
| 現行資料規模 | Dataset card 指明 **1,651 個 PDF 頁面**，包含 2026-04 新增的 296 頁 hard subset；單位是頁，不是 1,651 份完整文件。涵蓋 10 類文件、5 類 layout、5 類語言，文件包括論文、PPT-to-PDF、書籍／教材、考卷、筆記、雜誌、研究／財報、報紙、歷史文件；語言屬性包含英文、簡中、中英混合、繁中與 other。[官方 dataset card](https://huggingface.co/datasets/opendatalab/OmniDocBench) |
| 標註 | Card 列出 28 個 block 與 4 個 span 類別；區域位置、text、formula LaTeX、table HTML／LaTeX、reading order／部分關聯及屬性。可依合併儲存格、表格公式、邊框、方向、模糊掃描及多欄等分層。[官方標註 schema](https://huggingface.co/datasets/opendatalab/OmniDocBench#dataset-introduction) |
| 版本不能混用 | Repo changelog 宣告工具更新至 v1.7，仍有 v1.6_full 榜單；目前 `pyproject.toml` 寫 1.6.0。須固定 **code commit SHA、dataset revision、annotation hash、樣本 manifest、config**，不能只記「latest」或「v1.7」。本調查尚未建立可執行的版本鎖。[官方更新記錄](https://github.com/opendatalab/OmniDocBench#updates)、[package metadata](https://github.com/opendatalab/OmniDocBench/blob/main/pyproject.toml) |
| 論文是歷史版本 | CVPR 論文 v2（2025-03-25）描述的是 981 頁／9 類；適合了解評估理念，不能拿該規模或舊版分數當現行資料集結果。[原論文 v2](https://arxiv.org/abs/2412.07626v2) |

## 指標如何使用

官方支援整頁 Markdown 的 end-to-end 評估，也支援 layout、OCR、table、formula 的 single-module 評估。建議使用 JSON GT 的 `end2end`，保留 category／attribute／ignore 資訊；`md2md` 是另一個入口。官方四個主要輸出為 text、display formula、table、reading order。[官方評估說明](https://github.com/opendatalab/OmniDocBench#evaluation)

| 對象 | 可加入的外部診斷 | 不可以取代的本案驗收 |
|---|---|---|
| 文字 | Normalized Edit Distance，必要時依語言／版型分層 | 漏掉大段必要內容、識別字與 code 意義改變 |
| 公式 | Edit Distance 與 CDM；CDM 將 GT／prediction LaTeX 渲染後比對字元及位置，減少不同 LaTeX 寫法的影響。[CDM 官方方法](https://github.com/opendatalab/OmniDocBench/blob/main/metrics/cdm/README.md) | 數學等義與必要運算／上下限的人工 source audit；CDM 不是符號代數等價判定 |
| 表格 | TEDS（HTML tree、rowspan／colspan、內容）；TEDS-S 只看結構。[TEDS 實作](https://github.com/opendatalab/OmniDocBench/blob/main/src/metrics/table_metric.py) | 每張複雜表最多 5% 數值錯誤、表頭／條件歸屬、關鍵比較正確。**TEDS 95 不代表數值錯誤率 5%** |
| Reading order | 匹配區塊順序的 Edit Distance | 完整 canonical graph、跨頁續接及各 component 的來源位置／責任不重複 |

目前預設 config 使用 `quick_match`。官方更新將 matching 描述為 prediction-side granularity adaptation；這是**評分時**消除切段差異的工具，不可把 GT matching 結果回饋成 production routing、修表或改模型輸入。版本、matching timeout／fallback 也會影響成績，必須保留匹配記錄與 failures，固定後對 baseline／candidate 同樣執行。[官方 matching 說明](https://github.com/opendatalab/OmniDocBench#end-to-end-evaluation-method---end2end)、[預設 config](https://github.com/opendatalab/OmniDocBench/blob/main/configs/end2end.yaml)、[現行 matching 呼叫與 fallback](https://github.com/opendatalab/OmniDocBench/blob/main/src/dataset/end2end_dataset.py)

不要只報 Overall：官方總分平均 text、table、formula 三項，reading order 另列。對我們應保留每類分母、失敗數、來源必要條件與延遲／calls／tokens，避免平均數掩蓋 T04 這種表頭歸屬錯誤。[官方 end-to-end 定義](https://github.com/opendatalab/OmniDocBench#end-to-end-evaluation)

## 它補不齊哪些 B／C 缺口

- **Image／PDF 輸入要分軌。** 現行 card／檔案入口明列 page images，並提供 `image_to_pdf.py`；該腳本逐圖建立空白頁後只 `insert_image`，本身沒有加入 native text layer。Card 的 2024-12-25 更新也明確宣告發布 original PDF slices with metadata，因此不能斷言官方「只有 raster PDF」。但本次只讀 metadata，現行 root tree 未顯示 `ori_pdfs`／`pdfs`，沒有確證目前 1,651 頁皆有可取得、同版 GT 對應的 original PDF，或其文字層完整性。官方 `docling_img2md.py` 從 `./OmniDocBench/pdfs` 讀 PDF、用預設 converter；腳本本身未證明該資料夾是 original 或 raster 版本。[Dataset card／PDF 歷史更新](https://huggingface.co/datasets/opendatalab/OmniDocBench#updates)、[現行檔案 tree](https://huggingface.co/datasets/opendatalab/OmniDocBench/tree/main)、[官方 image-to-PDF 實作](https://github.com/opendatalab/OmniDocBench/blob/main/tools/image_to_pdf.py)、[Docling inference 範例](https://github.com/opendatalab/OmniDocBench/blob/main/tools/model_infer/docling_img2md.py)
- **比較限制：** 若以 images 或上述 raster-PDF 做 benchmark，它測的是視覺／OCR 路徑；對本案保留 native text、selective OCR 的 Standard 基線，不能外推成 born-digital PDF 全流程準度／latency。外部回歸須先標記 input track；baseline／candidate 用同一來源、DPI、轉換政策。原生 PDF 的比較需另核對檔案、文字層、page crop、GT 對齊及 source hash；取不到就保留我們原生完整 PDF 套件，不把 image 輸入結果混入同一延遲分布。此限制是由輸入路徑推得，並非 OmniDocBench 宣稱原生 PDF 一律不可用。
- **B 單頁表很適合外部回歸**：merged cells、table math、邊框／方向／語言能提供不同來源的挑戰。但「單一元件辨識」若直接用 GT crop，只測辨識；必須另測全頁 detection→routing→canonical delivery，不能把 oracle crop 成績當端到端成功。
- **跨頁表仍要自己的連續文件測試**：論文談到 cross-page paragraph affiliation，但現行入口按 page 讀 GT 與同名 Markdown，頁內 truncated 關聯合併也不能證明跨頁 table identity、header inheritance、cell continuation 成立。結論是「不是我們的 whole-document／跨頁表驗收替代品」，不是宣稱資料裡完全沒有相鄰頁。[論文 annotation／評估設計](https://arxiv.org/html/2412.07626v2#S3)、[page evaluator 實作](https://github.com/opendatalab/OmniDocBench/blob/main/src/dataset/end2end_dataset.py)
- **C 的 figure box／原 caption 可有幫助，但不直接驗證生成式 description、圖中 OCR 完整性、chart 數據與語意**。論文說 figure 本身沒有 recognition annotations；目前 card 的 `figure_caption` 是來源圖題，`chart_mask` 等 mask 類別也不能當 chart understanding GT。沒有核實到本案所需的 image-key enrichment／chart 語意官方評分任務；須維持自己的真實來源 image census 與 source-grounded 判準。[論文附錄標註說明](https://arxiv.org/html/2412.07626v2#A2)、[現行類別 schema](https://huggingface.co/datasets/opendatalab/OmniDocBench#dataset-introduction)
- **A inline／code 要另留必要判準**：論文把 code 合入文字，inline formula 轉換後與段落共同評估；目前預設公式主項仍是 display formula。無法用高總分直接宣稱全文 inline／code 的必要語意都通過。[論文 extraction 設計](https://arxiv.org/html/2412.07626v2#S4.SS1)、[現行 metric config](https://github.com/opendatalab/OmniDocBench/blob/main/configs/end2end.yaml)

## 分階段採用建議（本案設計，尚未執行）

1. **現在：B／C 收斂與評估設計並行。** 保留已曝光 DEV 作診斷；先定義外部樣本 strata、版本鎖與 source grouping，不下載全量、不換一批模型。分清 component 的 oracle-crop 診斷與完整 pipeline 指標。B 的 header／condition／數值比較判準及 C 的 image-key／generated-vs-source separation 都不變。
2. **配置固定後：一輪固定外部回歸。** 建議先 60 頁作資源受限的外部回歸提案，優先 table with spans／table math、繁中／中英、多欄、掃描／方向與負控制；頁面可跨 strata，最終逐層數量由 annotation-only inventory 決定，不能為滿足任意 quota 偷換樣本。選樣只依預先登錄屬性及固定 seed，不看候選輸出。baseline 與唯一 candidate 跑相同輸入；失敗／timeout 留在分母，同記 end-to-end latency、calls／tokens／pixels、模型與硬體。若預算不支援，先降低預登錄樣本數，不能執行後挑成功頁。
3. **Custody：把 producer 與 evaluator 分開。** 獨立 evaluator 保存 GT、manifest、hash、樣本 lineage／同源頁 group、評分設定；producer 只拿來源輸入。若 source ID 不足以阻止同文件分拆，先列出限制。看過 GT、逐案失敗並用來調 prompt 的樣本立即改列 DEV，不再稱 confirmatory。公開 benchmark 可能已在模型訓練或調參資料中；未知是否污染，故只稱外部回歸，不稱公司獨立盲測／無污染 holdout。
4. **完整文件與部署驗證仍獨立。** 用保留的完整論文／SOP／PPTX 等驗跨頁、文件層級 canonical 交付；公司 Qwen3／vLLM／GPU 與高頻 ingest 另測。大型全量 OmniDocBench 可以後續執行，但不應先擴大成本來掩蓋已知 B／C 功能阻擋。

## 成本與資料使用邊界

評分器不是零成本的純字串比較：metadata 要求 Python >=3.10,<3.12；CDM 要 Linux、TeX Live、ImageMagick／Ghostscript，LaTeX table 轉 HTML 可需 `latexmlc`，BLEU／METEOR 會用 HF cache。建議獨立容器／環境且固定 image digest，不把依賴裝入現有 Docling venv。對本機是否可行、每頁 evaluator 耗時及記憶體，本次沒有實測。[官方依賴定義](https://github.com/opendatalab/OmniDocBench/blob/main/pyproject.toml)

量測表需將 **ingest／模型推論時間** 與 **離線 matching／TEDS／CDM 評分時間** 分列。CDM 渲染與計分是研究驗證的開銷，不加入 production ingest SLO；若預先做 image→PDF，也分別記 preprocessing 與實際接收檔案後的 pipeline 時間。

**Code 與資料許可要分開。** Repo code 是 Apache-2.0；repo／dataset card 的 Copyright Statement 明示資料研究用途、非商用。公司內部評估是否符合其許可，本次不能確證；在確認前，現在可以借鑑評分方法與 schema，資料集實際納入公司的流程則保留條件，不把公開可下載等同商用授權，也不把原 PDF 重新發佈到我們的公開 repo。[Code LICENSE](https://github.com/opendatalab/OmniDocBench/blob/main/LICENSE)、[Dataset copyright](https://huggingface.co/datasets/opendatalab/OmniDocBench#copyright-statement)

本次未做新推論、全量資料 inventory、版本 SHA 鎖定或授權認定；沒有改舊實驗、開 holdout 或發佈 GitHub。外部分數也不能保證公司文件分布或正式吞吐。
