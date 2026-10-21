# 表格 API 接合：兩頁 live 結果

2026-10-17。依[確認計畫](pdf-core-table-delivery-plan-2026-10-17.md)，在[離線gate](pdf-core-table-delivery-results-2026-10-17.md)通過後完成 **一組通用協定、兩頁、三個native table targets、兩次API呼叫，各一次、無重試**。

**數值與關係交付通過：普通表6/6與3/3比較、六panel表84/84與8/8比較，都保留到typed table及主要Markdown。** 同頁Table3也完整處理，24個數值逐一對來源核對相符。不過固定schema未承載左欄印出的`Method`／`Setting`，Table3的`Component`與`Setting`亦合在row setting文字；因此不是完整來源保真通過，更不是正式Processing Profile或G2全面通過。沒有在結果後補字或調prompt重跑。

## 實際方法

| 項目 | 本輪執行 |
|---|---|
| Docling主幹 | StandardPdfPipeline／Docling2.132／Core2.99；PyPdfium、Heron、selective RapidOCR v6det／rec-small＋v2cls、TableFormer V1 accurate、native assembly |
| Memory-R1 p8 | 新做一次CPU S0 conversion；全部有效參數與歷史S0一致（只正規化` supported_engines `無序清單的序列化順序作比對）；1個native table target |
| SkillOpt p8 | 使用既有同版S0結果與144dpi頁圖；2個native table targets，包含Table2及Table3 |
| VLM | 暫用gpt-6-luna，回應model亦為同名；Chat Completions，非Qwen3或Granite；無immutable weights snapshot |
| 請求 | 各頁完整144dpi圖＋全部native bbox／opaque target keys；同一通用prompt與schema，未指定Table2、未手裁panel、未傳oracle值 |
| 有效參數 | detail high、reasoning low、JSON object、max_completion_tokens8192（包含reasoning）、store false、concurrency1、retry0、timeout180秒；固定官方endpoint、TLS驗證、不跟redirect／proxy env |
| 寫回 | 離線已凍結的同一公開Core mapper；typed panel tables、來源caption、整張表的provenance envelope與manifest；stock Markdown，非內建API table stage |
| 安全／資源 | 本次使用者直接提供的credential經hidden TTY進程序記憶體；未存檔。API worker每250ms觀測RSS／available；12GiB／8GiB／30min界線均未觸發 |

固定實際登錄 (`pdf-core-table-delivery-2026-10-17/live-registration.json`)、runner (`pdf-core-table-delivery-2026-10-17/live.py`)、請求結果 (`pdf-core-table-delivery-2026-10-17/live-observations.json`)、評讀 (`pdf-core-table-delivery-2026-10-17/live-evaluation.json`)均保存；payload可由登錄prompt／schema／image重建並核對body hash，沒有Authorization header或credential。新的API請求不使用舊raw內容。

## 逐來源結果與交付限制

| 任務 | 數值／關係 | 完整表示評讀 |
|---|---|---|
| Memory-R1 Table2 | 6個printed values及method／metric綁定全對，3個比較成立；F1↑／B1↑／J↑保留 | 左欄`Method`未由schema承載；typed首欄有row_header語義及兩個完整PPO method文字，但Markdown左上header為空。caption保留原source文字。不能將數值通過等同全部來源文字均保留 |
| SkillOpt Table2 | 六panel、28列、84個printed values／綁定全對，0extras、0numeric errors；8比較全部成立，低於原≤5%門檻 | panel title及三個metric headers保留；左欄`Setting`仍為schema缺項。provider將完整caption分成短caption及conditions，主要Markdown沿用原native完整caption，三組來源條件可解讀，並非從oracle補內容 |
| SkillOpt Table3（附帶工作） | 8列／24個數值對實際頁圖全部相符；修復原S0格網錯配 | 原Component與Setting兩個dimension合在帶分隔符的row setting中，值與group關係可解讀，但未重現兩個獨立欄位；bold／light-blue的cell級表示未承載。只報來源核對，不擴大T02分母或冒稱新frozen oracle |

實際輸出：[普通表Markdown](pdf-core-table-delivery-2026-10-17/memory-r1-p8/document.md)、[兩張複雜表Markdown](pdf-core-table-delivery-2026-10-17/skillopt-p8/document.md)。評分器從**已保存／reload的typed cells**重建數值，並逐cell驗Markdown格網與typed grid相同；不是只評provider raw。原G1評分規則未改。

兩頁全部non-table正文／圖片／來源位置／順序不變，caption各保留一次，public tree／references有效，無orphan。target集合各次精確相等、無漏項／未知key；新兩頁request沒有人工選特定panel或漏掉同頁Table3。這只證明這兩頁的native inventory可驅動接合，不證明能偵測任何文件中漏掉的表。

每個panel仍只綁native整張表範圍，cells沒有bbox；來源粒度沒有被提升成精確panel／cell定位。原生caption位置及舊字型／數學抽取限制也沒有藉此修復。原首欄header缺項在離線階段已有明列，live結果再度顯示協定保真範圍有限；它是表示協定缺口，不是模型把數值讀錯，也不應靠事後補固定字串解決。

## 執行成本與程序紀錄

| 工作 | 實測 |
|---|---:|
| Memory-R1 S0 worker，含import／load／export | 約6.4秒；sampled process-tree RSS peak3.28GiB；最低available14.75GiB |
| Memory-R1 API client RTT | 3.592秒；prompt3442／completion197tokens，reasoning0 |
| SkillOpt API client RTT | 17.764秒；prompt3496／completion2301tokens，含reasoning299 |
| API兩呼叫合計RTT | 21.356秒 |
| API worker sampled RSS peak | 0.140GiB；最低available16.17GiB；無guard stop |

兩次HTTP200、finish_reason=stop、無refusal，schema與mapping均通過。這不是Qwen3／GPU latency、p95或高頻benchmark；SkillOpt upstream為cached，不能稱兩頁全fresh。

模型前保留兩次setup stop：第一次sandbox拒絕psutil程序清點，worker尚無log／模型輸出，已終止reap；第二次把完整options誤比欄位不完整的舊registered JSON，assert在初始化前停止。改比實際effective options後確認active設定一致，才做上述**唯一一次實際S0 conversion**。未更改模型、dtype、crop、時間／RAM上限，未重試推論。兩次目錄分別為`memory-r1-p8-prep-sandbox-stop`及`memory-r1-p8-prep-options-stop`。

另記程序偏差：尋找Memory-R1來源路徑時，agent在API推論前讀到了已曝光DEV的T01 oracle文字，未遵守計畫中「oracle只於推論後讀取」的嚴格分離。producer程式不載oracle；通用prompt／schema／mapper hashes在本輪前已固定且未變，實際請求僅含schema、native bbox／keys及source image，沒有把正確值帶入。仍保留此偏差，不把本輪說成盲測或獨立泛化認證。

## 去留

**保留這條table API＋公開Core映射，作為有數值／關係交付證據的研究候選；不採用為完整保真配置。** 此輪已完成，停在原兩次API預算，不為`Method`或`Setting`追加prompt調參或補字。下一個合理工程問題是讓通用表格協定明確承載row-dimension headers及多欄row context，先用非來源專用的合成控制驗證，而不是替這兩張表寫特例；若繼續模型比較，公司具名Qwen3-VL需以相同完整協定另驗。

未改production、舊raw／oracle；Paddle、holdout維持暫停。未驗完整G1表格集合、unseen泛化、公司CUDA／vLLM、高頻併發及完整Canonical Acceptance；code／inline公式與圖片supplement的必要缺口仍獨立存在。
