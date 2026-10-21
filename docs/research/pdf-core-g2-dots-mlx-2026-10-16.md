# G2 dots.ocr＋MLX GPU：實際推論與固定來源核對

日期：2026-10-16（Asia/Taipei）。執行授權：「OK, 先執行 dots.ocr＋MLX GPU」。

**本機 GPU 路徑可用；這組 dots.ocr 尚不採用為完整方案。** 已完成12頁單次推論，再以官方替代PDF backend完成2頁來源渲染診斷。有效輸入頁的主實驗轉換時間約16.4–31.0秒，中位數21.5秒；同一controls頁約16.4秒完成，先前CPU在180秒界線停止。公式／程式碼仍有來源內容與原生交付缺陷，G2未通過。

## 實際配置與可重現界線

- MacBook Pro M5 Pro，20 GPU cores、48 GiB unified memory；隔離runtime `<tmp>/pdf-core-g2-dots-mlx-20261016/venv`。
- **相同固定權重** `dots-studio/dots.ocr@c0111ce6bc07803dbc267932ffef0ae3a51dc951`，直接載入既有兩份shard。再次核對官方SHA；沒有下載另一個社群checkpoint，也沒有量化。
- Docling-slim2.132.0／Core2.99.0／Parse7.22.3，MLX0.32.4／MLX-VLM0.7.8／Transformers5.20.0；官方PDF converter extras補齊後依賴檢查通過。Transformers在此提供processor，模型forward使用MLX，不把前次Torch dots模型的Transformers5座標問題直接當作此路徑已知結果。
- 官方`VlmPipeline`、`dots_ocr` preset、`MlxVlmEngine`、DOTS_JSON parser。保留官方prompt、scale2、max_tokens24000、有效temperature0、BF16與單請求；每頁180秒、12 GiB sampled RSS停止線，MLX allocator預算12 GiB、cache256 MiB、系統available低於4 GiB停止。未把使用者應用關閉或提高系統memory limit。
- 643個原始tensor、3,039,179,264 parameters，通過原生strict loading；上游sanitizer後的名稱／shape／BF16覆蓋全部一致。卷積權重依上游轉換到MLX排列，未手寫模型。**不是每個載入後tensor的bitwise checksum**；完整原始shard SHA與strict mapping是本輪身分證據。

第一次啟動在import時缺`rtree`，未建立模型、未推論；紀錄保留於`run-attempt01`。補齊官方`convert-core,format-pdf` extras，保留原freeze並另存v2 runtime lock，沒有重跑模型答案挑成功。

Docling2.132宣告`trust_remote_code`但未轉交`mlx_vlm.load`，原生載入會要求互動同意而失敗。本輪只在上游公開loader API補傳`trust_remote_code=True,use_fast=False`，保留原source processor與CPU的slow處理。這是明確的小型執行接點補參數，**不能宣稱完全零接線的preset開箱成功**；未patch已安裝套件、模型、prompt或輸出parser。

CPU與MLX的controls實際1191×1684圖片像素相同；formatted prompt、token IDs、attention mask、pixel_values、grid各自hash一致，實際grid為`[1,120,86]`。新processor另有`mm_token_type_ids`，本模型不使用；不把整份dict誤稱byte-identical。MLX原生`temp=0`介面參數與新上游的`temperature=0`預設相符，有效greedy值固定。

主實驗登記 (`pdf-core-g2-dots-mlx-2026-10-16/registration.json`)／補參數與輸入等價 (`pdf-core-g2-dots-mlx-2026-10-16/compatibility-registration.json`)／實際processor (`pdf-core-g2-dots-mlx-2026-10-16/run/controls-p1/actual-processor.json`)／權重映射 (`pdf-core-g2-dots-mlx-2026-10-16/run/weight-mapping.json`)／最終runtime lock (`pdf-core-g2-dots-mlx-2026-10-16/requirements-runtime-lock-v2.txt`)

## GPU時間與記憶體

主實驗12頁均完成，全部upstream finish reason為`stop`，沒有token上限停止、timeout、模型重試或memory停止。以下不以兩張輸入已損壞的頁面拉低平均延遲。

| 指標 | 實測 |
|---|---|
| 正常渲染的10頁 | 最小16.393秒／中位數21.484秒／最大31.046秒，合計221.157秒 |
| controls p1 | 16.393秒；767 generated tokens；原生完整轉換完成 |
| 主實驗總時間 | 243.830秒，含初始化／核對／12頁工作；不是每份PDF的SLO |
| MLX peak allocated | 7,135,904,158 bytes，約6.65 GiB |
| 外部取樣process-tree RSS | 約3.96 GiB；與MLX allocated量測範圍不同，**不能相加或把任一值稱作完整系統峰值** |
| 當時系統available最低值 | 約8.82 GiB；包含使用者其他工作負載影響 |

MLX確認`Device(gpu,0)`、Metal可用並實際完成生成。這些是單模型、單併發、固定頁面觀察，包含首次kernel／prefill成本，後續頁重用駐留模型；未測多次重複、冷啟動分布、高頻排隊或公司CUDA。CPU數據是timeout截斷值，GPU頁面計時不含相同初始化範圍，因此不報一個虛假的精確加速倍數。

逐頁結果 (`pdf-core-g2-dots-mlx-2026-10-16/run/completed-pages.json`)／外部監控 (`pdf-core-g2-dots-mlx-2026-10-16/run/execution.json`)

## 八頁／41來源單位回歸

沿用原source oracle、欄位與等價規則，沒有從模型輸出重新挑單位或放寬identifier門檻。這是曝光開發回歸；有些新native PDF render與前次API PNG不同，不當作只有engine一變因的完整配對benchmark。

| 核對層次 | 結果 |
|---|---|
| Raw來源內容 | 36符合原準則、5不符；其中包含原約定必須精確的名稱／大小寫，不能解讀成5個公式語義錯誤 |
| Raw JSON | 回歸7/8合法；DGM有invalid escape，官方parser交付0個text/table/picture，但native conversion仍回報success |
| F13完整表示／交付 | 可確認6/18；其餘包括模型誤讀、HTML取代必要LaTeX、跨頁段落及Markdown定界符問題，不是全部都數學意思錯 |
| F14完整內容／區塊交付 | 可確認3/7；三個controls單位通過，DGM四個必要單位未完整交付 |

主要來源錯誤：DGM的`test_success`／`run_tests`／`best_attempt`被改字或空格，段落內`edit_actions`變成`editActions`；SEAL更新式把原本的`θ`讀成`θ_0`。原嚴格oracle另標出`ReflACT→RefLACT`、`ICL→ICI`，未把單獨接受的OpenAI/OpenAl例外擴大到其他identifier。

改善也保留：WikiSkill的E14整段、六個行內公式與判定條件都正確留在Markdown；原bootstrap完整開頭正例保留。Controls矩陣、分數、分段函數的原始數學內容均正確，程式碼縮排、`<=`與inline code也保留。這些局部成功不足以抵銷E13／DGM的失敗。

原生交付仍有缺口：Formula.text已含`$$`時，stock Markdown又加一對，出現`$$$$`，完整交付因此未確認通過；HTML sub/sup在正文中被攤平成`ReST EM`等文字。SEAL Algorithm1 collateral被壓成一行，屬額外觀察，不新增到41分母。跨頁段落尚未成為單一logical paragraph。主實驗已有30個原生item無自身provenance（含表格／inline children）；可用bbox全在頁框內，只證明邊界沒有越界，不證明辨識位置正確。前次HTML-in-inline-code parser控制案例的缺口也未被本輪修復。

全部逐單位review (`pdf-core-g2-dots-mlx-2026-10-16/review.json`)／controls Markdown (`pdf-core-g2-dots-mlx-2026-10-16/run/controls-p1/document.md`)／SEAL Markdown (`pdf-core-g2-dots-mlx-2026-10-16/run/seal-p4/document.md`)

## 獨立validation與來源渲染診斷

原先固定兩份原作、四頁、12正例來源單位與10普通文字負例，來源及標註hash保持不變。60個inline math occurrence仍只是子項，不增加分母。

主實驗中，validation-01的兩頁正常：8個正例來源單位中6個內容符合、2個失敗。失敗是把程式的窗戶影像參數替換為黑方塊literal，以及把`q_{\tilde{\phi}}`讀成`q_\phi`；另外`9×9`與`16×16`雖內容正確，沒有交付必要LaTeX。9個普通文字負例中7個符合，兩個Iizuka引用有大小寫誤讀；沒有觀察到false math/code enrichment，但不將字面名稱錯誤算作完全保真。

validation-02的兩頁在主實驗**送模型前已被預設renderer畫黑**，約81%像素為深色；模型只看到邊角字樣。四個公式段落與一個普通文字abstract記為input-render failure，不能記作模型準確率失敗、也不能從分母刪除。

另登記兩次**渲染診斷**，唯一處理變更為官方`PdfFormatOption(backend=PyPdfiumDocumentBackend)`；同PDF、同scale2、同模型／BF16／prompt／token cap。先在零模型呼叫的render-only預檢中目視核對原稿，兩張1224×1584圖片恢復，深色像素約0.8%／1.4%。這是不同backend的處理配置，未覆寫原12頁或以診斷較好的輸出替換原validation分數。

兩次診斷都正常stop，頁面耗時約16.16／14.06秒。首頁abstract及DØ名稱保留；第12頁4個公式段落3個符合、1個失敗：兩處來源`gg+gq_S`都被讀成`gg+gq\bar{s}`，改變數學下標／channel。這排除了將黑頁問題全部歸咎於模型的誤判，也獨立證實有效輸入下仍有公式缺陷。

渲染前後量測 (`pdf-core-g2-dots-mlx-2026-10-16/renderer-preflight/results.json`)／診斷登記 (`pdf-core-g2-dots-mlx-renderer-diagnostic-2026-10-16/registration.json`)／診斷逐頁 (`pdf-core-g2-dots-mlx-renderer-diagnostic-2026-10-16/run/completed-pages.json`)

## 選型結論

本機Apple GPU已能執行實際文件模型，現階段**公司endpoint不再是繼續模型比較的必要前提**。本輪不採dots.ocr為完整PDF處理方案；即使處理公式外層定界符，也仍有來源公式、code identifier、inline LaTeX、跨頁結構與來源追溯缺口。維持已有Standard／小模型作比較基底，不因速度改善便改正式profile，也不追加逐題後處理。

下一輪應比較其他官方文件模型／元件組合；PyPdfium已成為具體的官方backend候選，仍需完整範圍回歸才可採用。這輪沒有建立vLLM服務、訓練模型或開六份holdout。原freeze、來源答案、舊評分與production程式保留。證據核對見verification (`pdf-core-g2-dots-mlx-2026-10-16/verification.json`)及manifest (`pdf-core-g2-dots-mlx-2026-10-16/artifacts.json`)。

本輪結果已於2026-10-16成功[寫回#84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6216361258)，讀回內容與[保存文字](pdf-core-g2-dots-mlx-2026-10-16/issue-comment-pending.md)完全一致；發布狀態 (`pdf-core-g2-dots-mlx-2026-10-16/issue-update.json`)已更新，保留先前連線逾時紀錄。Issue狀態與標籤維持不變，未重跑推論。
