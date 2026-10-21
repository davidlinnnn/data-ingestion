# C：55 頁來源盤點與既有圖片證據收斂

2026-10-17。**來源圖片存在性與 caption 責任盤點已覆蓋原計畫全部 55 頁；C 完整配置仍 partial。** 本輪新增模型／API／下載／安裝／holdout／production／SDK／GitHub 操作均為 0。沒有重做已成立的 MOCK 接合，也沒有把歷史答案接到新 crop。

`source-census.json` 是本輪 evaluator-only 來源資料；`source-pages.json`、`pages/`、`sheets/` 保留逐頁來源 hash、實際影像、14 張 contact sheets 與逐頁 review 狀態。來源由原三段計畫第三段的固定範圍解析，13 份檔案的原 registry SHA 全部符合；55 個 `(source hash, physical page)` 不重複。這是具名 DEV 跨頁範圍，只有 WikiSkill 是全 28 頁文件，並非 55 個統計獨立樣本或通用準度估計。

## 來源實際看見什麼

先看來源頁影像，不用 Docling native picture 清單或 PDF embedded-image 物件當真值。全部 55 頁已做圖片存在性／圖說位置視覺 review；有圖頁另看完整 1.5× render。小字、密集曲線與完整 OCR 未固定的部分明列未完成，PDF text 只存為來源定位輔助，**不當作圖片 OCR 的模型結果**。

| 來源 | 已檢視 physical pages | 視覺來源組／責任 |
|---|---|---|
| WikiSkill | 1–28 | Figure 1 真實 line chart；Figure 2 流程圖；Figure 3 wiki/skill 交互圖；另有 Google Research 品牌圖。Table 1–7 歸 B；算法與 prompt/code 框歸 A |
| SEAL | 2–4 | p2 Figure 1 流程圖，包含原 picture 外的標題 `t`；圖內數學保真仍歸 A，不用 C 圖意抵銷 F13 |
| DGM | 24、51、63–64 | 可見 code/diff、prompt、算法／正文，歸 A；這四頁未見另立資訊圖片 |
| Memory-R1 | 8 | Figure 6 雙 panel bars、Figure 7 雙 panel training curves、Figure 8 三 panel scatter；Table 2 歸 B |
| SkillOpt／paper09 | 8／17 | 可見的多 panel 與大表歸 B，沒有因為版面看似圖而重算為 C 圖片 |
| SelfEvoSkill | 27–29 | Table 12 與 Table 13 三頁續表歸 B；沒有將整頁表格算為圖片理解成功 |
| NCCU | 3 | 一張完整 screenshot；既有 S07 只是其中 panel，不能代表完整 screenshot OCR／圖意 |
| 臺南 scan | 1 | raster page 是文字＋表格，分給 F01/F09 與 B；不因 embedded raster 就新增整頁 F11 描述工作 |
| 英文 scan | 1–2 | p1 全文；p2 頂部一張 LLM timeline。Raster wrapper 與真正 timeline 分開 |
| Trace2Skill／ReasoningBank | 2／9 | 一張流程圖；兩張真實混合 bar/line 圖，原 G1 已有 42 個 printed observations 與比較契約 |
| Controls | 1–8 | p2 四張 toy charts；p7/p8 各一張 source-derived screenshot；p3–6 是方向控制文字頁，不能算四個新圖片語意來源 |

合計 **18 個資訊 figure/image groups＋1 個品牌圖＝19 組**，分布在 12 頁；另 43 頁是本 C 圖片存在性陰性。這是 logical source groups；圖內小 logo／人物照／panel 並非自動新增獨立 canonical owners。8 個 raster page wrappers 另列，避免漏掉 vector figure，也避免把整頁 scan 重複當語意圖片。以上不是 producer jobs 或 N₃。

10 個 chart groups 中，**9 組屬既定 F12 bar／line／pie 範圍**；Memory-R1 Figure 8 是 scatter，先保留 F11 圖意、方法／percentile／latency 關係及影像／OCR責任，**不新增所有 scatter 點的數值抽取硬門檻**。Figure 6 bar convention、Figure 7 dense continuous curve 的 finite observation 方式、Figure 8 小字／marker 歸屬，以及 WikiSkill Figure 1 的 16 個估值 oracle 尚未凍結，不能猜值或用 caption 替代。

## 舊證據能重用到哪裡

`saved-evidence-audit.json` 實際核對每份 input、request description、API raw response、usage 與固定 hash；31 個歷史引用檔案 hash 仍符合原登錄。沒有重新評分後偷偷改原結果。

| 證據 | 可保留 | 不能聲稱 |
|---|---|---|
| 2 張真圖 API：WikiSkill Figure 2、NCCU selected panel | `gpt-6-luna`、high detail、low reasoning、6144 cap 的具名 task 配置，在原 exact crop 的圖意通過；raw／uncertainties／tokens／RTT 身分可追溯 | NCCU 完整 screenshot、其他 12 個資訊 groups、公司 Qwen3 或新 native crop 已通過 |
| 4 張 controls chart API／13 點 | 原 2＋6＋3＋2 observations、printed／estimated、series／unit 與關鍵比較；包含 pie 字串百分比/null unit 的原樣保存 | 真實 chart 42 點或更多圖表準度；也不是 4 個獨立真實文件 |
| 1 份 RapidOCR／53 texts | 原 1340×980 crop，RapidOCR 3.9.2／ORT 1.24.3／三個模型 SHA、polygons/scores/文字完整保存 | 全 screenshot 文字皆正確；也不能把它掛到 follow-up 的 894×653 native crop |
| classifier 6 來源／12 crops | DocumentFigureClassifier-v2.5 固定 revision，CPU FP32 的 broad-family 比較與 routing negatives | 同版 2.132.0 完整 profile；分類錯／unknown 可豁免必含工作；12 個獨立來源 |
| 第一段 saved-response bundles | synthetic legal public owners 上的 raw／typed／Markdown 分離及搬移保存可行 | 舊 API 來源已經在新 S0 native owner 真實推論 |
| follow-up 一個 native owner、同 crop MOCK | Core 2.99.0 的 image-key、原 children/caption/graph 保護、獨立 crop pixel／mapping 驗證成立 | 圖片 OCR／description／chart 真實準度、55 頁 coverage 或 worker/Pod 恢復 |

六次歷史 API 的實際 totals 在 audit JSON 中列出，只是歷史 component cost；不能乘上 19 就宣稱本配置成本，也不能作新 run 的時間。兩個 screenshot controls 是 NCCU 衍生內容，英文/controls raster 也有共源，均不增加獨立泛化樣本。

## 同版工作與成本登錄

來源需求下限為：19 組 source-image／OCR outcomes（可明示 no_text／failed）、18 組資訊圖 description、9 組既定 F12 chart-data 來源；品牌圖描述可依來源判斷 N/A，但尚未驗證可安全作該豁免的 production 規則。**failed 只保留失敗狀態／診斷，不等於必含 OCR 成功，也不自動放行 Canonical Acceptance；no_text 須有方法證據，不能用 unknown 分類代替。** 分類可選且偏好啟用。這些是 **任務責任，不是 19／18／9 次 API**；同一圖可以有多個必要 task，同一 native figure 也可能 split／merge，cost 必須由 producer 真實 inventory 決定。

沿用既有 image-key 接點即可：同版 document revision＋owner ref＋實際 crop hash；原 caption 留在來源正文，OCR／生成描述／chart supplement 連至同版 key，provider raw／model／method／mapping／diagnostics 一起保存。未知分類不能讓必要工作變成完成或豁免。

**census 裡的人工作業 locator／圖號／要求只供 evaluator 查漏，不產生 producer 裁圖或 jobs。** Producer 只能從公開 native 結構、頁影像及事前固定的一般規則產生完整 inventory；再由 evaluator 比對來源。若漏掉品牌、timeline、小圖、未emit figure 或跨 owner 內容，仍是 coverage 缺口，不許把本清單當 oracle routing。Census→producer owner/crop→same-revision key 的責任與身分核對尚未執行。

因此 `N_3`、crop pixels、精確 calls、每 job input reserve、completion/total cap、CPU/RSS/latency 增量仍為 null。新同版 Standard 產生完整 inventory 後才可凍結，不能拿已知 19 source groups 當呼叫數。第三段 fresh Standard、heading/title/semantic parent、真實四方向 detector／derivative lineage、分類／OCR／圖意／chart 同版產物與 fresh-restored worker 都仍未驗。

## 去留

**保留 Standard＋RapidOCR＋可選 FigureClassifier＋task-specific VLM supplement 的 C 候選與既有公開 Core 接點；不再新增 MOCK replay。** 本輪已把「圖片有哪些、誰負責、哪些舊分數可沿用」收斂成可查核清單；不是 C profile 準度通過。

下一個 C 實質門檻是：完成少數未定的來源 chart／OCR契約，再對同版 producer inventory 查漏並凍結一次必要真模型工作的預算。若通用 inventory 無法覆蓋，先停止完整候選；不能靠人工圖號路由付費跑出成功。B／A／heading／方向的必要 gate 尚未通過時，不啟動第三段完整付費整合。

本輪未新增 inference、未打開 holdout；55 頁存在性 review 不是全文逐字準度或生產吞吐驗收。
