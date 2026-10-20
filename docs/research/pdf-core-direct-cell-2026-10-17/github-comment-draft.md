### G2：完整 TableData＋公開 serializer 實測完成；配置未晉升

依已接受的「完整 plain-cell JSON → Docling 公開 TableData／TableCell → 公開 table serializer extension」計畫完成 A 與 B。公開接合技術可行，但此次完整 producer／mapper 配置未通過，因此不進入 C 的 native table-plugin 化。

| 固定案例 | 數值／比較 | 完整交付 |
|---|---|---|
| T01 Memory-R1 p8 | 6/6 bindings、3/3 critical comparisons | 通過，Method／箭頭表頭及caption完整 |
| T02 SkillOpt p8 | 84/84、8/8 | 六panels通過，Setting與metric headers完整 |
| T04 paper09 p17 Table6 | Raw按來源位置保留50/300，250數值遺漏，漏失83.33%；5個比較僅1個有足夠位置數值 | 整頁嚴格拒絕，沒有accepted typed／Markdown；原生兩個targets被合併成一target的兩panels，Table7歸屬錯誤 |
| T05 WikiSkill p13 Table4 | typed與實際渲染各80/80、7/7；20/20共同physical cells的成對值與角色完整 | 失敗：完整caption重複兩次 |

470數值／23比較分母不變，各複雜表≤5%且全部必要比較／表頭／條件／交付成立的門檻不變。SkillOpt附帶Table3另外目視核對24/24數值、8組Component／Setting關係、3個metric headers；不加入470。T04的「沒有accepted artifact」不等於所有raw數字都辨識錯誤；其Model span及旋轉variant文字另有缺陷，但250數值遺漏本身已足以否決。

固定配置：Docling-slim2.132／Core2.99／Parse7.22.3；StandardPdfPipeline＋PyPdfium、Heron、RapidOCRv6det/rec_small＋v2cls、TableFormerV1 accurate，CPU4threads，enrichments off。Memory／SkillOpt核hash重用同版S0；另外兩頁各一次新S0，完整options一致。額外producer為gpt-6-luna OpenAI API、144dpi full-page、native table inventory、detail high／reasoning low／JSONobject／storefalse，完整cells＋offsets／spans／roles；不是整頁VlmPipeline，也不是公司Qwen3具名模型實測。

A合成gate通過17項正向／40項拒絕控制，涵蓋multilevel headers、row/col spans、rowgroups、paired cells、空白/缺值/零/精度、literal HTML/Markdown的真正渲染、source spans、graph、non-target rich table及JSON reload。保留前兩次測試helper將合法rich reference重編號誤判為內容變更的失敗紀錄；第三次改以解析後來源內容比較通過。所有實作修正都在B freeze前。

B固定4次API／6個native targets，retry0、concurrency1；全部HTTP200、finish_reason=stop。先以source-independent33×13／379cells估計輸出大小，凍結65536cap；T04實際只有7780completion tokens且uncertainties=[]，不是截斷或timeout，不增加cap重跑。四頁client時間7.80／41.22／46.93／21.17秒，合計117.13秒；prompt13,707／completion18,930tokens。CPU兩頁取樣treeRSS峰值2.46／2.02GiB，全部在既定180秒/request、45分鐘、12GiB RSS/8GiB available界線內；未作production吞吐推論。

T05缺陷是caption ownership：原native table.captions空，但同段caption已存在baseline正文；mapper fallback新增provider caption，導致canonical與Markdown皆重複。A合成資料只有已綁定caption，沒有涵蓋這個真實情境。沒有加入文字dedup／猜測attachment或來源專用修補；三個mapped頁面的其他graph、raw→typed→真正Markdown、source/provenance、non-target內容與roundtrip審查皆另存。

結論：保留公開TableData／serializer作為可用接點，不採用目前完整配置。Plugin化不會自行補回T04遺漏，也未證實能解決caption未綁定。後續須分別處理producer完整性與caption ownership，先固定新假設再登錄下一輪，不靠逐case後處理或同題重試追通過。

所有oracle答案讀取在四次推論完成後，producer／adapter／prompt於freeze後未變。無SDK／production修改、新安裝或API重試；公司Qwen3／CUDA／vLLM、高頻、跨頁T03、Paddle與6份holdout未啟動。四頁都是已曝光DEV，沒有泛化證據。

本機完整報告：`docs/research/pdf-core-direct-cell-results-2026-10-17.md`；可重現gate、raw、registrations與分層評分：`docs/research/pdf-core-direct-cell-2026-10-17/`（尚未提交至Git）。
