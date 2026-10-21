# 完整 TableData＋公開 serializer：實際驗證結果

2026-10-17。依[已接受計畫](pdf-core-official-table-integration-plan-2026-10-17.md)完成 A 與 B；**公開接合機制成立，但此 producer／mapper 配置未通過完整交付，不進入 C plugin 化。** 這不是否決 TableData 的表示能力，也不是正式選定 VLM。

結果摘要經使用者明確同意後，已發佈至公開 [GitHub #84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6230056274)。本機完整 artifacts 尚未提交至 Git。

## 四頁結果

| 固定案例 | 完整數值／關係評分 | 主要 Markdown／交付 | 判定 |
|---|---|---|---|
| T01 Memory-R1 p8，普通表 | 6/6 exact numeric bindings；3/3 critical comparisons；Method 與箭頭表頭完整 | Typed、真正渲染、caption、來源與 roundtrip 通過 | 本頁通過 |
| T02 SkillOpt p8，六 panels | 84/84；8/8；6個 panel、Setting 與三個 metric headers 完整 | 六個表格及同頁 Table3 分開保留；caption／條件完整 | 本頁通過 |
| T04 paper09 p17，Table6 | Raw 依來源位置保留50/300個 exact numeric strings；250個遺漏，遺漏率83.33%。5個比較僅1個有足夠位置數值，4個缺資料 | 原契約整頁拒絕，沒有 accepted typed／Markdown；兩個 native targets 被錯併為一個 target 的兩個 panels | 失敗 |
| T05 WikiSkill p13，Table4 | Typed 與實際渲染各80/80；7/7；20/20成對 physical cells，共同 cell 身分與 Proposed／Accepted 角色保留 | 表頭、row groups、數值通過；完整 caption 重複兩次 | 交付失敗 |

分母維持470個數值、23個 comparisons，沒有把漏掉的數值移出分母。普通表要求零錯，各複雜表最多5%且所有必要比較／表頭／條件／交付成立，不能用其他頁面的成功抵銷 T04。T04 的「沒有 accepted artifact」與「raw仍有50個正確位置數值」是不同衡量，不能將前者說成所有 raw 數字都辨識錯誤。

SkillOpt 附帶 Table3 另經實際144dpi圖片核對：24/24數值、8組 Component／Setting 雙列維度及3個 metric headers，皆保留到 raw、typed、實際 Markdown。這24點不加入470分母。T04 同頁另有 Table7；其錯誤 target 歸屬單獨記錄，沒有增設數值分母。

## 本輪實際配置

| 階段／component | 固定選擇 |
|---|---|
| Runtime | Docling-slim2.132.0／Core2.99.0／Parse7.22.3，沿用已安裝隔離環境，無新安裝 |
| PDF pipeline／backend | `StandardPdfPipeline`＋`PdfPipelineOptions`／PyPdfium；不是整頁 `VlmPipeline` |
| Layout | Heron，revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`，Transformers FP32、compile off |
| OCR | RapidOCR：PP-OCRv6 det_small／rec_small＋mobile_v2 cls；CPU，4 threads／interop1 |
| Native table baseline | TableFormer V1 accurate；OCR/layout/table batch1，enrichments off |
| 圖片 | 144dpi full page（scale2）；原生 whole-table bbox 僅提供 target inventory，不裁新 crops |
| 額外 table producer | OpenAI Chat Completions `gpt-6-luna`；image detail high、reasoning low、JSON object、store false |
| Producer 輸出 | 一個完整 plain-cell contract：原生 target key、panel、TableData dimensions、文字、offsets、spans、三種角色 flags；不提供 cell bbox／rich refs |
| 公開接合 | 公開 TableCell／TableData、插入／刪除／重編號 API；all-or-nothing copy，禁止補值／自動填空格 |
| 主要 Markdown | 官方 `MarkdownDocSerializer(table_serializer=...)` extension；只對目標 plain cells 的 render 副本做通用 HTML／Markdown escaping，委派 stock table serialization |

完整有效 options 與輸入／request／protocol hashes 見 live registration (`pdf-core-direct-cell-2026-10-17/live-registration.json`)。Memory-R1／SkillOpt 核 hash 重用同版 S0；另外兩頁各做一次新 S0，完整 options 比對一致。未把 OpenAI 結果當成公司 Qwen3 的具名模型驗證。

## A：表示與 serialization gate 通過

A 結果 (`pdf-core-direct-cell-2026-10-17/verification.json`)：17項正向控制、40項拒絕控制，0模型／API／來源論文／oracle。涵蓋雙列維度、多層及重名 metric headers、rowspan／colspan、row sections、同一 physical cell 的成對值、空白／缺值／零／精度、HTML／Markdown literals 的實際 CommonMark＋table 渲染、合法 corner 雙 header flags。

同時驗完整 grid coverage、bounds、overlap、span／offset一致、嚴格型別、漏／重複／未知 target、source caption／provenance／全部 source spans、正文與非目標 rich table、JSON reload及canonical不可變。Rich targets、非caption children、無法完整保留的非預設 target metadata 明確拒絕。只沿用 native whole-table envelope，不生成 panel／cell 位置。

通用 extension 不修改 canonical cell strings、數值或角色。CR／LF與其他換行只在顯示副本展平成空格；stock表格本來也會折疊顯示空白。spans／精細結構保留在 typed artifact；pipe Markdown 不承諾 PDF 視覺版面無損。

保留了三次合成 gate 的紀錄：前兩次停在測試 helper 將合法的 rich-cell reference 重編號當成內容變更（第二次尚未處理 `cref` alias），第三次改用 reference 指向的來源內容比對後通過。實作預檢也補正 serializer 初始化、非預設 metadata 拒絕及通用換行處理。這些都在 B freeze 前；**四次 API 期間與評分後 producer／adapter／prompt 均未更動。** 不是用來源答案修正候選。

## B：固定四次請求，失敗原因分開記錄

觀測 (`pdf-core-direct-cell-2026-10-17/live-observations.json`)為4次 HTTP200、全部 `finish_reason=stop`；一次配置、concurrency1、retry0。依非來源合成33×13／379實體cells的[預檢](pdf-core-direct-cell-preflight-2026-10-17.md)統一凍結 max completion65536、compact JSON、省略預設 flags／unit spans。這是保守 byte 預估，不是精確 tokenizer 保證。

| 頁面 | API client 秒數 | Completion tokens（含 reasoning） |
|---|---:|---:|
| Memory-R1 | 7.80 | 678 |
| SkillOpt | 41.22 | 7,117 |
| paper09 | 46.93 | 7,780 |
| WikiSkill | 21.17 | 3,355 |

合計117.13秒、prompt13,707／completion18,930 tokens。T04 回應正常結束、遠低於輸出上限，`uncertainties=[]`；**不是 token 截斷或 timeout**，增加 cap 不能由本次證據證成。既有 strict gate 攔下其不完整 grid／錯誤 target，沒有接受部分成功。

T04 宣告33×13，但只有83個實體 cells，覆蓋154/429 positions；缺275格＝250數值＋25 method labels。前5個method rows之後的大量數值沒有輸出。10個 metric header paths 正確，但 Model 的跨欄關係錯誤、旋轉模型 variant 文字另有辨識缺陷。將 `4o-mini`讀作`40-min`的嚴格 context 分數另列，不靠這類可能需寬容裁決的 OCR 錯字誇大主要失敗；250數值遺漏本身已足以否決。

T05 的 source caption 已在 baseline 正文 TextItem，native table 的 `captions=[]`。目前 mapper 在沒有 native caption link 時採用 provider caption fallback，新增了同一段 caption，導致 canonical／Markdown皆重複。這是**caption ownership／接合缺陷**，不是數字辨識錯誤，也不是 escaping 錯誤。A 的合成 caption 都有 native link，沒有覆蓋此真實情境；不能以 A 通過推論所有 caption assembly 都正確。沒有新增文字 dedup／猜測 attachment 規則來隱藏問題。

三個 mapped 頁面的 graph、typed cells→實際渲染、source spans、來源 envelope、非目標正文／位置、canonical serialization不變、JSON reload皆經獨立交付審查 (`pdf-core-direct-cell-2026-10-17/delivery-verification.json`)；Wiki caption 失敗另外明列，不被機械項目通過所抵銷。

CPU 兩頁峰值取樣 tree RSS 約2.46／2.02GiB；API程序峰值約0.145GiB、最低 available14.81GiB。B執行到最後 API 約170.6秒，未觸及180秒／request、45分鐘、RSS12GiB／available8GiB界線。這是本機有界執行資料，非 production高頻／併發／GPU SLO。

## 結論與下一步界線

**可以保留「TableData＋公開 serializer」作為接合技術；不能晉升目前完整配置。** 舊 flat protocol 的左欄 literal header與雙維度／paired cell 限制已有正面證據，rich／任意文件與所有來源仍未成立。

依原計畫不啟動 C：將這個 producer 搬進 Standard table engine plugin，不會自行補回 T04 遺漏，也沒有證據會解決 native caption 未綁定的情況。先保留失敗輸出與評估，將後續工作分成 producer完整性與caption ownership兩個問題；不以更多逐case後處理或同題重試視為新候選。若要另開下一輪，應先固定解決哪一個問題、比較哪個模型／方法，再重新登錄；本輪不擴張成完整 renderer／graph repair。

公司具名 Qwen3／CUDA／vLLM、高頻 ingest、跨頁T03、Paddle與6份holdout均未執行。這四頁都是已曝光 DEV；本輪既沒有泛化證據，也未完成code／inline公式／圖片等其他必含功能資格。

可重現評分：T01／T02 (`pdf-core-direct-cell-2026-10-17/quality-small.json`)、T04 (`pdf-core-direct-cell-2026-10-17/evaluation-t04.json`)、T05 (`pdf-core-direct-cell-2026-10-17/t05-evaluation.json`)。所有答案讀取都在四次固定推論完成後，沒有回流至 producer。沒有 SDK／production修改、安裝、模型下載或新的 API 重試；憑證只經隱藏TTY／程序記憶體使用，未寫入研究檔案。
