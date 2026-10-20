# W4b：Decision3.0官方runtime的本機品質閘門評測

**結果：nano與mini皆可用官方runtime在本機MPS執行；目前沒有足夠證據把任何類別直接接為正式自動verified閘門。** Mini公式排序優於nano，但test verified仍有1/25改義（4%）；mini code僅verified1項，不足以證明低風險；描述仍錯認操作。Chart/caption的dev沒有改義負例，按事先規則不校準、不自動verified。這是項目狀態判斷，不阻擋文件Canonical Acceptance，原圖、原生文字與模型重建輸出皆未修改。

本輪完成後停止：沒有第三種大小追加、改門檻重跑test、重切資料、讀holdout、commit、push或GitHub留言。專案產物僅在W4b。

## 1. 官方核實與安全

- nano固定`vllm-sr/d3-nano@462efc366229ea268cf4eed3738b3fc4415e4817`：2,213,241,664參數，Qwen3.5-2B底座，Apache-2.0；weight/readout4,428,644,200bytes。
- mini固定`vllm-sr/d3-mini@bd0090dd758d32ba59ef5c749910a8e87fc4391f`：4,539,265,536參數，Qwen3.5-4B底座，Apache-2.0；weight/readout9,081,227,360bytes。
- 兩款含其他root檔案總payload **13,556,210,856bytes**，沒有另下載base。權重SHA-256對過HF公布的LFS值，完整hash在`weights-d3-nano.json`／`weights-d3-mini.json`。
- flash（8.39B）完整weight/readout16,789,656,976bytes；三款光權重就30,299,528,536bytes，超出本輪十進位30GB上限，**未下載／未評**。26B未評。不是因為mini表現不好再擅自開新候選。
- mini官方文字／Vision Index52.6／63.2、nano38.9／54.7均核實，但沒有拿公開分數替代本輪內容保真評測。全系列與量化版revision在`official/family-lock.json`。完整d3目前card宣告Qwen3.8-27B，而config為qwen3_5架構；不能把「架構」當成全部系列皆同一Qwen3.5底座。這不影響所選nano/mini。

[官方recipe](https://recipes.vllm.ai/vllm-sr/d3-nano)、[nano固定模型卡](https://huggingface.co/vllm-sr/d3-nano/blob/462efc366229ea268cf4eed3738b3fc4415e4817/README.md)、[mini固定模型卡](https://huggingface.co/vllm-sr/d3-mini/blob/bd0090dd758d32ba59ef5c749910a8e87fc4391f/README.md)。vLLM nightly的SystemOne端點與CUDA/ROCm路徑已核實，但本機沒有開server；全程直接`AutoModel.from_pretrained(...,trust_remote_code=True,device="mps",local_files_only=True)`及`model.system_one(...)`。

8個remote Python檔（4396行）已於執行前審閱，且nano/mini/flash相同。未發現隱藏外傳或無關系統操作。程式**確實存在**使用者選URL時的下載函式、video tempfile寫檔及Hub模型下載分支，沒有謊稱原始碼完全無網路/寫檔。這輪只用固定本機目錄＋PIL、無videos；這些分支不走。推論child設HF離線、Python socket.connect/urllib guard，記錄0網路嘗試；標準HF動態模組快取放W4b。細節及行號見`remote-code-audit.md`。

另有重要文件差異：recipe稱confidence是被選機率，但固定版`d3_runtime.py316–322、341–343`實際是**1−normalized Shannon entropy**。本輪不讀confidence作決策；Q1讀`probabilities["faithful"]`，Q2讀`noul`。沒有重寫prompt renderer、attention mode、checkpoint temperature或head；維持官方BF16 backbone、FP32 readout、SDPA與非因果full-attention設定，batch_size=1。

## 2. 事前登錄與資料隔離

凍結`freeze.json` SHA-256：

`336461e7b277447e9a49e9a8fd379c84c405db9214f2d22219f1175454f527b9`

在任何d3輸出前固定兩組問題、選擇/校準/門檻規則、所有輸入及gold。沿用W4的81dev＋185test，**兩個帶提示的項目仍保留在相同test位置，只移除提示**。state嚴格只有`category`和原始`reconstruction`；移除全部人工source_locator／expected／reason／per-item tolerance提示。沒有因為看test而修正任何來源答案或單一案例prompt。

來源裁圖與W4相同；124個唯一圖像內容中10個超過1,600,000pixels，按固定等比例LANCZOS縮小，尺寸／比例／前後SHA在`image-transforms.json`。官方processor另有65,536至1,638,400pixels的smart-resize限制，保留其原生行為，沒有沿用VJev的512px長邊上限。沒有改裁圖邊界或補字。新state沒有舊W4兩筆k=5來源定位提示。

Q1為四選項choice，criteria是「選項→一句定義」；faithful與minor邊界在`questions.json`寫明。Q2為是否忠實保義的noul。公式/程式/描述/chart各有固定類別判準，每個模型使用相同問題；不對個案改問法。Chart printed值要求原數字，估計值的通用視覺容忍在類別問題固定；state不提供正確數值。

每模型每類只用dev進行：

1. 比較Q1的P(faithful)與Q2的P(yes)之AUROC（correct對meaning_changed；minor不進AUROC）。較高者勝；平手或兩者不可算選Q2。
2. 在選定分數上做**一次固定單調regularized Platt**：logit(raw score)→sigmoid(a*x+b)，a≥0，L2 λ=1，無超參數搜尋；目標Y=1為correct/minor，Y=0為改義。
3. 在dev唯一校準分數門檻中，取「經驗verified改義率≤2%」下覆蓋最多者；無非空可行集合則不verified。**dev只有單一類別時不擬合、不用identity假裝校準，門檻null，維持不verified。**
4. 在test第一筆之前將各模型的問題、calibrator、門檻與producer hash寫入`selection/<model>/selection.json`及`test-launch.json`，然後每模型只跑185筆選定問題一次。Test未用於重選Q、再校準或移動門檻。

ECE採10個固定等寬bin，針對保義Y=correct/minor；Q1 raw P(faithful)與該保義事件不完全相同，Platt輸出才是估計保義機率。AUROC主表統一以**raw safe score**為正向（越高越correct），不以entropy confidence代替。單調Platt不修正內容，也不改善排序；本批校準後AUROC與raw相同。

## 3. Test結果

|模型|類別|test n|dev選定Q|AUROC|ECE前→後|verified內改義|verified覆蓋率|
|---|---|---:|---|---:|---:|---|---:|
|d3-nano|formula|55|Q1|0.778|0.155 → 0.096|2/24（8.3%）|43.6%|
|d3-nano|code|28|Q2|0.613|0.182 → 0.118|1/10（10.0%）|35.7%|
|d3-nano|caption|13|Q2|—|0.010 → —|N/A（0/0）|0.0%|
|d3-nano|description|17|Q1|0.100|0.286 → 0.145|2/8（25.0%）|47.1%|
|d3-nano|chart|72|Q2|0.710|0.237 → —|N/A（0/0）|0.0%|
|d3-mini|formula|55|Q2|0.859|0.204 → 0.086|1/25（4.0%）|45.5%|
|d3-mini|code|28|Q2|0.800|0.393 → 0.173|0/1（0.0%）|3.6%|
|d3-mini|caption|13|Q2|—|0.005 → —|N/A（0/0）|0.0%|
|d3-mini|description|17|Q1|0.333|0.422 → 0.132|1/7（14.3%）|41.2%|
|d3-mini|chart|72|Q2|0.657|0.234 → —|N/A（0/0）|0.0%|

`—`表示不能估計；caption無test負例，AUROC不可算。Chart/caption的dev均只有correct，校準後ECE未定義，沒有假造fit或測試門檻；0/0風險不是0%。兩模型均185/185有效回應、0執行失敗、0test重試。每模型81個dev呼叫各問2題，185個test呼叫各問1題：**各347個question forward，合計694**；零遠端推論API。

### Dev選擇收據（沒有用test重選）

|模型|類別|dev AUROC Q1/Q2|選定|校準門檻|dev verified/n|dev改義率|
|---|---|---:|---|---:|---:|---:|
|d3-nano|formula|0.9167 / 0.9028|Q1|0.9009|12/23|0.0|
|d3-nano|code|0.5185 / 0.7037|Q2|0.8201|5/12|0.0|
|d3-nano|description|0.9000 / 0.8000|Q1|0.8957|9/11|0.0|
|d3-nano|caption|— / —|Q2|—|0/6|N/A|
|d3-nano|chart|— / —|Q2|—|0/29|N/A|
|d3-mini|formula|0.8750 / 0.9306|Q2|0.8963|15/23|0.0|
|d3-mini|code|0.6667 / 0.6667|Q2|0.8293|6/12|0.0|
|d3-mini|description|0.8000 / 0.7000|Q1|0.8978|8/11|0.0|
|d3-mini|caption|— / —|Q2|—|0/6|N/A|
|d3-mini|chart|— / —|Q2|—|0/29|N/A|

上述可擬合三類在dev的verified都是0錯誤，但dev負例僅公式4、code3、描述1；樣本量小於能提供2%風險保證的程度。**≤2%只是dev的經驗選擇目標，並非test或生產分布的承諾。** 描述dev只有1個負例、10個正例，一對排序就會使AUROC改變0.1，所選問法的優勢很脆弱。描述的dev錯誤是不同圖中箭頭關係，test兩個錯誤是Greek字母與中文操作，錯誤家族並未充分覆蓋。這是內容泛化與抽樣限制，不是HTTP或JSON格式失敗。

代表false verified（原圖已再次人工檢視，原人工label未改）：

- 兩模型都放過`S_ret`被寫成`S_rev`的條件集合下標；mini raw yes0.8405→校準0.9038，超過dev門檻0.8963。圖中ret可見，並非來源UNKNOWN或source crop錯位。
- nano另放過LightGCN分母由兩個平方根乘積變成巢狀平方根（改變指數）；mini在本批未將此項verified。
- nano放過程式化文字條件`if warranted`→`if unwanted`，不是換行或格式差異。
- 兩模型都放過中文「由右方點選」被寫成right-clicking；mini rawfaithful0.7995→校準0.9073，仍錯把操作保義。
- nano另放過希臘τ被描述成拉丁T；mini在本批未將此項verified。

完整原重建輸出、裁圖路徑、人工理由與分數在`false-verified-evidence.json`。**沒有因為這些錯誤再寫個案prompt、改標籤、修字或挑新門檻。**

### 與W4 VJev並列

W4發布的AUROC用P(meaning_changed)當風險分數；本輪Q1/Q2要共同對應safe event，因此事前指定以P(faithful)/P(yes)排序。四分類中P(faithful)不是1−P(meaning_changed)，兩種AUROC可能不同。為公平比較，從W4保存輸出另算同口徑AUROC，保留其原發布數字；**未修改W4、沒有重跑或重校準VJev**。

|類別|W4原發布AUROC（risk）|W4同口徑AUROC（faithful）|W4未校準ECE|W4覆蓋率／風險|
|---|---:|---:|---:|---|
|formula|0.761|0.653|0.296|0%／N/A|
|code|0.320|0.053|0.548|0%／N/A|
|caption|—|—|0.408|0%／N/A|
|description|0.900|0.467|0.379|0%／N/A|
|chart|0.496|0.803|0.447|0%／N/A|

這是候選**整體配置**比較，包含問題、解析度、state清理、校準與門檻方法變更，不能把差異單獨歸因於權重大小或D3架構。W4原兩筆帶數值定位提示仍是其舊baseline限制，本輪已全部移除。

所有資料仍為已有人工判定的DEV來源之內部分割，不是外部holdout。Code test的25個correct都是R5 inline occurrence，3個改義都是W3 block，存在來源/長度confounding；chart72點只來自2頁4張圖，5個錯點同一曲線圖；描述test只有2個改義；caption沒有負例。104筆原先被W4排除的混合群組、字型證據、缺輸出與UNKNOWN仍未補成獨立真值。因此不能把本輪稱為完整A/C品質資格證明。相同test ID給W3b合併的`w3b-test-join.csv`每模型38個W3 block；不要混入dev輸出。

## 4. 成本與公司GPU推估

實機Apple M5 Pro48GiB，PyTorch2.14.0／Transformers5.20.0／torchvision0.29.0，兩模型均MPS **BF16 backbone／FP32 readout**，CPUthreads=2，無CPU模型回退。每次`system_one`前後明確MPS同步；官方runtime自己的synchronize只同步CUDA。以下每筆system_one延遲包含tokenization、vision processor及forward；外層開圖/PIL準備與檔案hash在單筆計時前，另由整批wall計時涵蓋。單筆不含model載入，載入後也使用暖檔案快取，非冷啟動benchmark。

|模型|test p50/p95秒|test含載入wall秒|峰值RSS GiB|最大記錄MPS driver GiB|最低host可用GiB|
|---|---:|---:|---:|---:|---:|
|nano|0.351 /1.681|111.60|5.14|5.21|18.65|
|mini|0.838 /3.706|252.22|9.49|9.67|16.77|

RSS/hostavailable由parent每0.25秒取樣；MPS driver為每forward後的最大觀察值，並非精密瞬時峰值。Unified memory兩者重疊，不相加。PyTorch current_allocated_memory僅回報很小數值，未反映完整權重足跡，因此沒有用它宣稱模型只占幾MB。8GiB可用記憶體與180秒load/request硬守門均未觸發。依賴環境與逐筆成本在`runtime-summary.json`、`runs/*/*/supervisor.json`。

官方在**AMD Instinct MI325X**、AutoModel單張1.6MP圖／單題warm請求公布nano p50/p90=90.2/90.7ms、mini112/113ms；AutoModel峰值9.1/14.8GiB。以p50取倒數得到粗略串行參考約 **11.1／8.9次判斷/秒/GPU**；不是嚴格吞吐上限或穩態平均值。若每份文件N個項目，理想吞吐為該數字除N份/秒；不是公司GPU的實測或SLO，亦未包含共享GPU上的原始重建、排隊與IO。官方318req/s是text batching，不能挪用為圖片吞吐。實際公司GPU型號未知，並行batch/fast kernels還可能造成near-tie機率差異；不能把MPS的門檻資格直接帶到另一runtime。來源是上述固定nano/mini官方卡的Serving performance段，推估另存`official-GPU-estimate.json`。

初次nano load在任何forward前發現既有環境缺官方所需accelerate，已停止並保留錯誤；在W4b/runtime-deps隔離安裝accelerate1.15.0後重載，沒有改shared SDK或官方code/權重，不是模型推論失敗。沒有其他重試或改dtype。

## 5. 建議與交接

- **正式自動verified：目前各類都不建議直接採用。** nano公式/code/描述的test觀察風險8.3%/10%/25%；mini公式/描述仍4%/14.3%；mini code僅1個verified，0/1的Wilson95上限約79.3%，不表示可靠。Chart/caption缺必要dev負例。
- **若只保留一個離線候選訊號：nano較省記憶體與延遲；若專注公式排序，mini較好（AUROC0.859），可保留作DEV審查優先序。** 這不是將任何項目晉升正式verified。高頻ingest暫不為尚未證明的閘門普遍增加這筆成本。
- **搭配便宜訊號的建議**：公式用原生字層的運算子／下標／識別字一致性與LaTeX結構；code用適用語言parse/AST、literal／路徑／縮排差異；描述用caption/OCR的實體與動作支持、關係／條件有無新增；chart用printed label、panel/series/x對應與tick-scale幾何檢查。語法可解析或兩重建器一致均不是語意正確保證。
- 主線可用同一test ID比較W3b，**本輪沒有實測聯合AND閘門，不能宣稱組合後就達標**。不為`ret/rev`或right-clicking寫單案規則，不用test重選門檻來補資格。依既定第一版政策，內容保留為模型重建並帶unverified/disputed/failed等狀態；enrichment錯誤不阻擋文件Canonical Acceptance。

本回合以決策與證據交接停止，不自動再下載flash、開新提示或追加測試。

最終完整性核對74項與統計控制12項通過，見`final-check-results.json`／`control-results.json`；只證明輸入隔離、官方機率抽取、dev選擇規則、test單次執行與記憶體/檔案完整性，不能當品質通過證明。
