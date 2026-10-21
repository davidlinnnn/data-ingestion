# W4：本機開源多模態決策模型作為 enrichment 訊號

完成日期：2026-10-20。本回合零遠端推論 API；只有下載公開文件、權重及繪圖套件的網路存取。只寫 W4，沒有改原始產物、thread、票、Canonical schema 或狀態。

**決策：運算上可行，這個固定設定尚不能作自動 `verified` 閘門；本輪另有資料覆蓋、輸入提示與選項事件的評測限制，不是完成的盲測資格證明。** 固定 P(faithful)≥0.8 下，185個 test 項目全部 `unverified`，沒有 `verified`／`disputed`／`failed`。verified 中實際改義比例是未定義的0/0，不是0%錯誤，也不是通過品質驗收。建議暫不為這個訊號增加線上 ingest 延遲；公式與描述的排序能力可保留作離線研究證據。此判斷只針對項目狀態，**不阻擋文件 Canonical Acceptance**；原圖、原生文字與模型重建內容的保留政策不變。

## 1. 候選核實與選擇

|候選|核實結果與決定|
|---|---|
|`yah01/vjev-vision`|**選用**。4,539,265,536參數，Apache-2.0（模型卡與Qwen3.5-4B base metadata），圖片＋typed choice probabilities。官方 helper明示支援MPS。revision `2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2`。merged權重約9.079 GB，加processor/tokenizer/head等實際下載檔案共9,098,703,205 bytes。|
|`akhilaaa3/Jev-Omni`|存在，11,959,730,224參數，Gemma4-12B底座，Apache-2.0聲明，具多模態決策頭。revision `fee89b076e2263bfa8bce8d34142caa4ca733a48`。約23.920 GB，但官方loader拒絕非CUDA裝置，predict硬寫CUDA autocast。這輪不移植、不下載、不跑，因此沒有它的test數字。|
|CLEF／JEV-27B-VL／pplx-decider-v1-27b|官方完整權重約52–56 GB，已超過40 GB下載上限，也無法在48 GiB主機保留8 GiB餘裕；第一候選可執行，沒有改用未驗證量化版或丟棄決策頭。|

[固定revision的VJev模型卡](https://huggingface.co/yah01/vjev-vision/blob/2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2/README.md)、[MPS reference code](https://huggingface.co/yah01/vjev-vision/blob/2fa8b58e40e5bc351a7d6dd39b953469a8f3ded2/vjev_infer.py)、[Jev-Omni官方loader](https://huggingface.co/akhilaaa3/Jev-Omni/blob/fee89b076e2263bfa8bce8d34142caa4ca733a48/jev_omni.py)。詳細授權、base metadata、其他候選與每個權重SHA-256見 `candidate-research.md`／`candidate-verification.json`。兩個優先候選在模型卡聲明Apache-2.0，revision未附獨立LICENSE檔，已如實記錄。三個safetensors與head下載後皆對過發布者SHA-256，見 `weights-integrity.json`。

VJev是shared linear decision head讀取選項slot，單一forward得softmax，沒有生成文字或解析自報信心。使用的是 **P(faithful)**，不是helper另外算的 normalized confidence。保留官方512px長邊縮圖、固定選項順序、merged backbone及head；沒有MLX轉換或量化、權重微調、temperature fitting。

## 2. 資料、凍結與範圍

可可靠對應的內容項目共266：公式78、code40、caption19、描述28、chart點101。dev81（30.45%）、test185（69.55%）。依原始來源頁做connected components；多頁項目連接各來源頁。以固定seed的SHA-256排序、按類別配額接近30%做label-blind分配，**沒有相同原始頁hash跨dev/test**。跨W3/R5不同解析度頁面另做96×128灰階MAE<3的重複screen，沒有命中；這是完整性檢查，不是另做split。不同頁仍可能來自同一論文，本集不是文獻或生產分布的獨立holdout。

在任何決策模型輸出前凍結資料、標籤、問題、選項與規則，`freeze.json` SHA-256：

`a51ca0bb1f17897b4ff61f81e9b3eaa554800a5edfba9c36a3bb2d58f3971e6d`

`test-gate.json`在test前再次固定runner/metric程式；dev只檢查格式及runtime，沒有計算或使用dev accuracy調prompt。模型只讀 `model-inputs.json`，不含人工label、判定理由或expected欄位；但最後稽核發現下述兩個定位文字含數值提示，不能把欄位隔離當成完全無答案提示。71條W3人工收據的既有packet hash／active output比對均無不一致。

104筆另外列清冊：6條W3 UNKNOWN/來源對應錯誤、44個R5原有混合群組（缺唯一孤立輸出對應且與新增registry重疊）、43筆字型證據（不是獨立語意項目）、10筆缺失／歧義typed occurrence、1筆網路中斷無回應。沒有把F1/F3冒充「改義」，也沒有事後猜答案。**因此沒有完整涵蓋原44混合群組內所有已知重大錯誤**；這限制本輪對整套A/C的代表性。清冊在 `items-with-gold.json`。本輪未評OCR literal項目，不能對OCR閘門下結論。

W3整個formula/code block維持原判定單位，不拆成獨立TeX行。原METADATA_ONLY映為minor；原CONFIRMED_BLOCKING映為改義。R5 caption僅沿用字面caption片段判定，不把它說成caption ownership或caption math整體正確。chart沿用既有逐點數值／關聯與容忍值；只把容忍規則供模型，沒有把人工正確數值或marker座標供模型。

來源有唯一native provenance時以union bbox加固定8來源像素pad；沒有唯一位置就保留原頁。只做幾何定位，不修字、不按錯誤裁圖。12個dev幾何樣例的contact sheet已檢視，見 `dev-image-integrity-contact.png`。官方長邊512限制保留；整頁fallback上的微字、code以及多圖組本來就比單一公式裁圖困難。

## 3. Test結果（不報dev accuracy）

AUROC主指標以P(meaning_changed)區分correct與meaning_changed，minor不進AUROC。ECE是**事先固定的二元閘門校準量**：P(faithful)對「人工correct或minor仍保義」事件，10個等寬bin；不是全四類multiclass ECE。固定verified規則為P(faithful)≥0.8；未verified且P(meaning_changed)≥0.5為disputed，其餘unverified。

|類別|test n|改義 n|AUROC|ECE|verified／覆蓋率|verified改義比例|延遲p50／p95秒|
|---|---:|---:|---:|---:|---|---|---:|
|formula|55|11|0.761|0.296|0 / 55（0%）|N/A（0/0）|0.779 / 1.132|
|code|28|3|0.320|0.548|0 / 28（0%）|N/A（0/0）|0.972 / 1.837|
|caption|13|0|N/A（無負例）|0.408|0 / 13（0%）|N/A（0/0）|0.806 / 1.101|
|description|17|2|0.900|0.379|0 / 17（0%）|N/A（0/0）|1.436 / 3.253|
|chart|72|5|0.496|0.447|0 / 72（0%）|N/A（0/0）|0.845 / 0.973|

185/185有效機率、0執行失敗。各類P(faithful)最大值僅0.7392／0.5424／0.6935／0.7598／0.6105（依表中順序）；P(meaning_changed)全低於0.5。沒有把「空verified集合」寫成零風險。每類完整21個門檻點（0、0.05…1）在 `threshold-curves.csv`、`test-metrics.json`，圖為 `threshold-curves.svg/png`。0.8維持不變，不看test挑門檻或改用P(faithful)+P(minor)。

可靠度圖 `reliability.svg/png` 揭示：這批保義項目的比例高於P(faithful)；但改義項目也常被分到faithful/minor，而非強烈wrong。四選項中的faithful與minor會分走保義機率；本輪固定規則衡量的是faithful而不是兩者合計。這是**固定問題／選項／機率事件的限制**，不能由本次ECE推論所有應用、或模型在其原訓練domain都同樣不校準。任何不同事件定義、互斥選項重寫或重新校準都需要下一個預先固定方案，不能事後替換本輪結果。

重要抽樣與輸入限制：

- **最後稽核發現來源提示：** R5:A2-022／A2-026（皆test）的人工source_context被當作定位文字，分別含`Specifically, at k=5`與`55.1 vs.54.5 at k=5`。這兩筆有oracle-assisted locator，不能算純圖片盲評。保留原凍結資料、輸出與主表，不在看test後修prompt重跑或偷偷換分母；混合formula AUROC0.761僅描述本設定，不作乾淨盲測資格結論。`input-hint-audit.json`記錄此缺陷。W3 formula子集沒有這類定位文字，另列其AUROC；這也不能補成完整R5的驗證。

- formula的35個W3 test block含18 correct／6 minor／11改義；同一公式類內W3子集AUROC=0.884。其餘20個R5公式都是correct，不能由它們評拒錯能力。
- code test的25個correct全是R5 inline occurrence，3個改義全是W3 block；來源與長度／版型confounding嚴重，沒有W3 block內的兩類對照。0.320不能當成一般code judge的可靠能力估計，更不能翻轉分數後宣稱變好。
- description只有2個改義，AUROC0.900仍很脆弱；不能解讀成已可作保證。
- chart72點實際只來自2來源頁上的4張圖，5個錯點全在同一曲線圖；不是72個獨立chart。
- caption13個全是正例，AUROC不可計算，沒有證明拒絕錯caption的能力。

上述子集仍使用同一固定metric，沒有拿子集選門檻。`test-source-subgroups.json`提供數字；原始test收據及完整對照在 `test-item-results.json`。主線與W3b合併時可用 `w3b-test-join.csv` 的38個匹配test block（35formula＋3code），**不可把本輪dev預測混回test比較**。

代表內容錯誤與機率（都仍為unverified，不是false verified）：

- LightGCN分母把sqrt(Nu)×sqrt(Nv)改成sqrt(Nu×sqrt(Nv))，改變指數；P(faithful)=0.6716，P(changed)=0.0872。
- Code把patch target `## Important Requirements`改成`# Important Requirements`；P(faithful)=0.5424，P(changed)=0.1373。
- 中文SOP「由右方點選」被描述為right-clicking；P(faithful)=0.6054，P(changed)=0.1957。
- 另一描述把希臘τ說成拉丁T；P(faithful)=0.6028，P(changed)=0.1545。

逐項原輸出、原始來源圖路徑與人工理由見 `representative-errors.json`，沒有改標籤。

## 4. 本機成本與公司GPU推估

M5 Pro、48 GiB，PyTorch2.14.0／Transformers5.20.0、MPS float16。trunk與head全部參數裝置都assert為MPS，CPU fallback關閉；CPU只有2 threads的tokenization/前處理與控制。PyTorch提示缺少CUDA optimized causal-conv/gated-delta kernels，使用的是MPS tensor上的reference PyTorch實作，不是CPU模型推論。

- test載入3.317秒，185筆含載入與寫檔總191.853秒。
- 每筆同步計時涵蓋開圖、resize、tokenization、processor及forward：p50 **0.858秒**、p95 **約2.165秒**、最大4.339秒；合計186.556秒。
- test峰值RSS **15.869 GiB**；MPS allocated峰值 **8.459 GiB**、driver峰值 **9.822 GiB**。unified memory會重疊，不能把RSS與MPS加總。
- test主機可用記憶體最低 **16.425 GiB**；含dev格式pilot的整輪最低約15.669 GiB，均高於8 GiB。parent以0.25秒監測，獨立180秒phase硬停止與總時間停止線；沒有觸發停止。
- 只下載一個模型約9.10 GB payload，繪圖依賴另約數十MB量級，遠低40 GB；無第二模型／base重複下載。未量測網路重傳封包流量。完整環境、各筆延遲／記憶體與host樣本在 `runtime-summary.json`、`supervisor-test.json`、`predictions-test/`。

容量推估：公司GPU需約9.1 GB半精度模型payload加activation與工作空間；單卡24 GB級是合理的容量候選，**尚未實測CUDA速度、batch吞吐或公司GPU**，不把Mac延遲換算成H200數字。官方有CUDA路徑，但標準generative chat API不能代替決策頭輸出；若後續部署需保留scoring head及固定輸入render，不把生成的信心文字當等價實作。目前品質閘門沒有可用覆蓋率，因此沒有購置或部署建議。

dev找到並修正一個reference helper格式bug：它對長文字呼叫Path(text).is_file()，macOS拋檔名過長。以LiteralText wrapper讓原helper走str(x)分支，token文字完全相同，權重、head、render、問題未改；5個成功dev forward未重跑，1個錯誤發生在forward之前。原碼、錯誤收據與log保留，見 `dev-format-fix.md`。這輪實際決策forward為81dev＋185test=266，無test重試。沒有SDK修改。

最終機械完整性核對見 `final-check-results.json`；其中「沒有label/expected欄位」只檢查欄位隔離，不是無人工提示的保證。上述人工提示稽核缺陷單獨保留，不能用機械檢查全通過掩蓋。

## 5. 建議交接

**當前不作任何類別的自動verified決策者。** 0%覆蓋率下多加約1秒判斷成本，對高頻ingest沒有已證明的自動交付效益。保留公式與圖片描述的排序訊號，若主線要再研究，可限於離線審查優先序；不要把AUROC當校準證明。code、chart目前沒有支持接線的證據；caption缺負例；OCR本輪未測。

與W3b合併時，建議比較相同test ID的便宜訊號：

- 公式：原生字層的運算子／索引／符號對應、LaTeX語法及結構、雙重建器分歧。字串一致不等於保義；原生字層可能同樣錯。
- code：parse/AST或語言適用的結構檢查、字串literal／路徑／縮排差異、雙重建器一致度。parse成功不是語意正確。
- 描述：與原生caption/OCR的實體支持、是否新增動作／條件／箭頭關係，再用多模態分數作研究排序。文字支持不能證明圖上關係正確。
- chart：printed label直接核對、panel/series/x對應、tick-scale幾何與範圍檢查；目前不推薦用此judge替代數值驗證。

這些是待主線比較的訊號，不是本輪已驗證的聯合AND閘門；不能假設兩模型／兩訊號獨立或把一致視為真。維持unverified/disputed等項目狀態及原圖／原生文字，不因enrichment錯誤拒絕整份Canonical。若要改機率事件、門檻或資料覆蓋，另行預註冊，**本輪不自動追加**。
