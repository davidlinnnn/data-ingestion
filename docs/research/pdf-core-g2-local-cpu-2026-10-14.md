# PDF core G2：首批本機 CPU 執行與模型比較邊界

[Research index](README.md) · [G2 模型／設定提案](docling-pdf-core-g2-pipeline-start-2026-10-14.md) · [G1 固定來源](docling-pdf-core-g1-source-cases-2026-10-14.md) · [需求 #84](https://github.com/davidlinnnn/data-ingestion/issues/84)

2026-10-14（Asia/Taipei）。**六次離線 CPU 診斷執行均正常結束；一般表所選內容保留正確，複雜表、繁中圖片文字與閱讀順序已有明確缺口。** 這不是整個 G2、完整文件、Canonical Acceptance 或效能資格通過。未下載模型、安裝／升版、呼叫 API、使用 GPU 或改部署。

## 使用者本輪執行決定

- 本機先跑可負擔的 CPU 模型與流程；模型過大、時間／記憶體或硬體不合適時，再由公司環境補驗。Mac 即使有其他 accelerator 能力，本輪仍明確選 CPU，不用 AUTO 改走 MPS／MLX／CoreML。
- 本機需要 remote 大模型時，可暫用 **OpenAI 官方 VLM 作比較候選**；公司實際環境是 self-hosted VLM／vLLM，已有 Qwen3。確切 API model／endpoint 尚未提供，本輪沒有 API 請求。
- 暫用 API 的接口、任務品質與 latency 各自留證；不能推定 Qwen3 效果相近，也不取代公司地端開源候選的品質、GPU／serving、資源及高頻驗證。Qwen3 仍不排除其他適用地端候選。

## 方法、資源與保存

本機 MacBook Pro／Apple M5 Pro／18 cores／48 GiB RAM、macOS arm64；開跑前 available memory 約15–17 GiB，為動態觀察。使用既有 prototype Python 3.12.13，Docling 2.102.0／Core 2.96.0、Torch 2.14.0、Transformers 5.8.1、RapidOCR 3.9.2、ONNX Runtime 1.24.3；與保存的本機套件版本相符。這些不是公司 Linux runtime 或 GPU 的測量。

- **stock `StandardPdfPipeline`**，不經既有 continuation、table reconstruction 或 Canonical mapper。TableFormer V1 `accurate`、cell matching=True；page／picture images=True、scale=1；CPU4 threads、Torch inter-op1、layout／table／OCR batch1、一次一個 fresh child。
- native四次關 OCR；兩次 OCR 明確 RapidOCR／ONNX Runtime、force_full_page_ocr=True。formula／code／classifier／description／chart enrichment 全關，是診斷對照設定，不是需求完成配置。`RapidOcrModel` wrapper 的輸入計數在 OCR 關閉時仍可能為1，不能當作發生 OCR 推論。
- HF／Transformers offline。使用既有 Heron snapshot `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`、TableFormer snapshot `fc0f2d45e2218ea24bce5045f58a389aed16dc23` 及三個既有 RapidOCR ONNX；17個資產欄位與固定值／現存bytes相符。
- child timeout180秒、每0.25秒 sampled process-tree RSS，6 GiB軟停止；每次開跑前available須至少8 GiB。這是本機保護預算，沒有macOS硬memory limit保證。
- 首次資源監測遭 sandbox 拒絕 process inventory，owned child已停止並保留[startup failure](pdf-core-g2-local-cpu-2026-10-14/startup-failure.json)；取得該本機監測存取後重跑，六次無timeout或memory stop。這是監測setup失敗，不算模型品質結果。

[runner](pdf-core-g2-local-cpu-2026-10-14/run.py) 重用既有[experiment.py](../prototypes/pdf-checkpoint-prototype/experiment.py)，只在本輪process覆寫batch並增加首次完整序列化。每次先保存 `conversion-result.json`（包括pages／predictions、confidence、timings、errors、assembled、document及input），再保存export的`document.json`／Markdown、method、events、metrics及log。首次provider bytes未改；兩種document表示只在`cref`／`$ref` alias與null省略正規化後相等，沒有把export檔冒稱全部provider輸出。

來源直接選原PDF physical page，沒有重新編號的抽頁副本。G1 registry與來源bytes未變；G1的`candidate_execution_status=not_run`是當次oracle freeze狀態，本輪執行索引另存，不覆寫固定oracle。

## 六次執行觀察

| 原來源／物理頁 | 配置 | child啟動至退出秒 | convert秒 | sampled tree peak GiB |
|---|---|---:|---:|---:|
| Memory-R1 p8，G1-T01 | native＋Heron＋TableFormer | 6.303 | 0.667 | 1.662 |
| SkillOpt p8，G1-T02 | 同上 | 5.777 | 2.199 | 1.633 |
| SEAL p4，G1-E05–E09來源 | 同上，無公式／code enrichment | 3.657 | 0.338 | 1.588 |
| NCCU p3，G1-O01/O05/S07來源 | native對照 | 3.942 | 0.383 | 1.386 |
| NCCU p3，同來源 | full-page RapidOCR | 5.227 | 1.409 | 2.998 |
| 英文scan physical p1，G1-O03 | full-page RapidOCR | 7.608 | 3.761 | 3.099 |

六次child wall合計32.514秒；不是五份完整文件處理時間。每配置一次、既有模型／OS cache未清空；fresh process不等於清空cache的cold-start benchmark。convert排除部分啟動／模型初始化／輸出，stage時間不能直接加成elapsed，也沒有API、queue、Acceptance或Retrieval publication。沒有p95、持續吞吐或高頻SLO結論。[原始觀察](pdf-core-g2-local-cpu-2026-10-14/summary.json)

## 來源核對結果與範圍

| 範圍 | 本輪結果 | 能支持與不能外推的結論 |
|---|---|---|
| **G1-T01一般表** | 六個method×metric值逐格正確；三個critical比較成立；caption文字與連結正確 | 該表所選內容／歸屬通過本輪核對；不表示整頁閱讀順序、所有普通表或Canonical交付通過。 |
| **G1-T02複雜表** | 未通過：metric headers混成合併文字；mini-batch2包含設定4的數值；設定4/8合列，關鍵比較無唯一row binding；另一panel setting40的75.4落在孤立下一列 | 錯誤在stock producer JSON已存在，Markdown延續；不能歸罪尚未執行的舊mapper。尚未逐點完整分類84點錯誤，不給全表error%。 |
| **G1-O01繁中截圖中央5組** | 2組文字相符；breadcrumb「統」變「统」；中央B5A漏冒號；完整操作指示整句缺失 | 尚未滿足該選定區域文字保真。不能拿右側相似標籤代替中央位置；需區分偵測／識別／crop／交付缺口。 |
| **G1-O03英文所選兩段16行** | 允許斷行／斷字正規化後文字完整相符；但右欄In-context learning段落插入兩段之間 | 支持該選定範圍的文字轉錄；閱讀順序仍有問題，不宣稱整頁OCR／順序通過。 |
| **SEAL公式／code來源** | 已形成layout／原生文字對照，未開重建模型 | 不能由本輪判定公式／code重建能力；後續需按各任務開啟候選並用相同oracle比較。 |

核對由本次Codex代理以固定來源／圖像及provider輸出交叉檢查；未新增人類逐字認證。[table review](pdf-core-g2-local-cpu-2026-10-14/table-review.json)、[OCR／identity review](pdf-core-g2-local-cpu-2026-10-14/ocr-review.json)

NCCU的完整JSON內已有52個圖片子文字，Markdown僅原生說明與image placeholder。**不能說OCR沒有執行，也不能把它當作已符合F08的同版圖片補充內容交付。** 要繼續驗獨立圖片OCR入口、來源位置／歸屬、same-revision讀取與Markdown reference。

CPU accelerator／thread／batch選項已保存；OCR log確認ONNX Runtime backend，但未保存live `session.get_providers()`，所以實際ONNX provider欄位明示未capture，不宣稱已取得GPU／provider placement證據。

## 後續比較與未執行項目

1. 先依新G1來源與失敗位置評估表格替代方法：TableFormer設定／V2、Granite Vision專用table stage、Granite-Docling頁面或具名區域adapter。沿用逐表門檻與critical比較，不用數字出現率替代歸屬正確。
2. 圖片OCR從固定crop與pipeline實際crop分開診斷，補實際provider記錄，測完整指示、混排、旋轉／回轉與來源綁定。頁面OCR不能自動代替獨立圖片補充內容。
3. CodeFormulaV2、Granite-Docling、classifier與大型vision模型目前未在所查cache中。先按取得大小、CPU smoke時間／RSS判斷可負擔性；缺少cache不是CPU不可行的證據，也不因此先宣告移公司或改模型。
4. 使用者暫用API待確切model／endpoint可用後才做任務與錯誤／截斷／parser比較；公司Qwen3／vLLM另用相同來源補驗。正式交付／恢復在G3，完整corpus與GPU／高頻資格在G4。

本輪執行資料的檔案與hash見[artifact manifest](pdf-core-g2-local-cpu-2026-10-14/artifacts.json)。沒有重跑舊Granite／MLX失敗、下載新權重、呼叫API、執行GPU、完整mapper／custody／recovery或高頻負載；六次成功只是執行狀態，不能標成G2全面通過。
