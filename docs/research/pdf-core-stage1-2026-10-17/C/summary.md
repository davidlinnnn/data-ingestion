# C：圖片 supplement 離線接合

結論：**機械接合 gate pass；C 整體 partial，不放行第三段完整配置。** 這輪實際寫了最小的 image-key sidecar 與公開 Core 控制，沒有只留下新計畫，也沒有執行任何模型。`results.json` 是機械結果，`registration.json` 是計時／下一段未就緒欄位，`evidence-hashes.json` 登錄讀取並再次核對的歷史證據。重跑入口：既有 Python 加 `-B controls.py`；所有輸出只落本 C 目錄。

## 實際證明與界線

| 控制 | 實際結果／證據 | 能支持的結論 |
|---|---|---|
| 六份已保存 API response | `bundle-original/provider/`、`supplement.json`，2 圖意＋4 chart | 原 raw response、model、usage、uncertainties 與完整 parsed payload 均隨 bundle 保存；不是新準度成績 |
| 一份保存 RapidOCR | 原 `picture-scale3/ocr.json` 的全部 53 texts、scores、polygons、engine/model hashes 原樣保存 | 有文字回應可交付，不宣稱文字全部正確；其舊 crop 與目前 S0 crop 不同，沒有假裝同一輸入 |
| 無文字／OCR failure | 2 個白色 synthetic image 與明示 mock state | `no_text`、`failed`、`unattempted` 分開；failure 必須有 diagnostic，不能帶「已交付」文字。不是實際 OCR 跑出空值或失敗 |
| Caption／description | 合成 source caption 恰好一次；生成 description 存 PictureMeta 與 supplement，主 Markdown 排除 meta／annotations | Caption 不被模型描述覆寫；鄰文不變。主 Markdown 保留圖片資源 URI，key 即檔名 |
| Chart | 4 chart 的 13 點、series、x、value_status、axes、unit、relations 均原樣 round-trip | 不轉換、不修值。Pie 的 `about 25%`／`about 75%` 及 null unit 原樣保存；沒有憑類型補 `%` 或改成精確數值 |
| Unknown classification | 所有控制設 unknown；required_work 固定保守列 OCR／description／chart_assessment | 未知分類不豁免必要工作。沒有完成的 task 保留 unattempted，不藉 classification 當已接受 |
| 錯誤控制 | revision、method、foreign／duplicate／missing owner、work exemption、failure＋texts、provenance、key、實際缺圖，共 10 項拒絕 | 機械資料邊界能拒絕這些輸入；不代表自動語意判分 |
| 搬移／第二 process | `bundle-relocated/` 從新 cwd 載入 document JSON、Markdown、全部 image keys、provider 與 supplement，驗 SHA／內容 | bundle reload 成立，不是 fresh／Pod／checkpoint 恢復 |
| 真正固定版 cached S0 | `native-bundle-original/`、`native-bundle-relocated/` | 目前 S0 NCCU 的一張 native picture、53 個 children 及全文 graph／text／caption／provenance 完全保留，只將 picture 的 embedded image 換成 bundle 相對 URI；第二 process 讀回通過 |

歷史六份 API／OCR 以 **synthetic legal public owners** 驗內容接口，並未聲稱其歷史 S0 為本輪固定版。真實固定版 S0 native graph replay 是另一組控制；不能把兩組拼成一次新端到端轉換或全圖 coverage。原 API crops 來自歷史人工 DEV envelopes，本次只用於保存回應接合，不提出它們為通用 producer discovery 規則。

## 官方與自訂

| 部分 | 身分／固定接點 |
|---|---|
| Runtime | Docling-slim 2.132.0、Core 2.99.0、Parse 7.22.3、PyPdfium2 5.14.0，程式硬性核對 |
| 公開 Core | `DoclingDocument.add_picture/add_text`、`PictureMeta.description`／`DescriptionMetaField`、`ProvenanceItem`、`ImageRef`、`RefItem.resolve`、`PictureItem.get_image`、`export_to_dict/load_from_json/export_to_markdown` |
| 官方 Markdown policy | `ImageRefMode.REFERENCED`、`allowed_meta_names=set()`、`include_annotations=False`；保留原 caption ownership，生成描述不冒充原文 |
| 自訂內容 | image key＝hash(document revision、owner ref、crop hash)；sidecar、Work／Chart payload validation、artifact hash manifest、保守 required-work policy、mock 與負控制。這不是官方內建 image-supplement schema，也不宣稱 native chart extraction 已完成 |
| 歷史 provider | 六份 raw response 的 model 為 `gpt-6-luna`，raw id／usage／其他欄位逐份保存。RapidOCR 3.9.2／ONNX Runtime 1.24.3 及三模型 SHA 在原 payload；沒有載入它們 |
| 目前 cached S0 | `pdf-core-native-round-2026-10-17/S0/nccu/document.json`，runtime 由 `standard-runtime-v2.json` 支持，`S0/effective-options.json` 有實際 OCR paths。已記 SHA。該 S0 的 classifier／description／chart extraction／heading 均關閉 |

`Chart`／`Point` 的已知欄位嚴格驗證，未知 provider 欄位以 extra allow 原樣保存；raw response 永遠另存。不把未知欄位移層，也不把字串估值隱式轉成數字。這個 supplement 可以保留 pie 的觀測值與不確定性，尚未證明消費端能直接作數值運算。

## 全需求的第三段來源與責任

下表是**仍需驗證的責任**，沒有將「已有局部證據」升格為完成。55 頁來源範圍沿原計畫；本 C 沒有重作全來源 census。

| ID | 第三段來源／工作責任 | 未解與處置 |
|---|---|---|
| F01 | 全 WikiSkill；SEAL p2–4；NCCU p3／臺南 p1；英文 scan p1–2；controls 全8頁。Standard／selective OCR | 漏文／混合 native-OCR／全文內容需原稿清單，尚未有完整 gate |
| F02 | 同上，特別多欄 scan、SEAL 與跨頁 WikiSkill。Heron／assembly | 多欄錯序與 title/body 歸屬仍未解，不由 supplement 修復 |
| F03 | WikiSkill 全28頁／附錄；controls。官方 heading recovery＋明示 semantic parent adapter | 舊版 stage replay 不能當固定版整合；無 bookmark 附錄、title role、parent/depth 仍缺；目前 S0 heading disabled |
| F04 | Memory-R1 p8、SkillOpt p8、paper09 p17、WikiSkill 表；SelfEvoSkill p27–29。B 分支 | 單頁及跨頁 logical table 身分／表示須 B gate；不能以分離三張表通過續表 |
| F05 | 同 F04，原470數值／23比較與 T03 264／7分開 | 每表數值與全部關鍵比較／表頭條件依原判準，C 不改評分 |
| F06 | 全 WikiSkill 與各補充頁。Standard render／inventory＋image-key bundle | 本輪一 native picture 和合成 owners 有界成功；未emit image／table／multi-fragment 的來源完整清單仍缺 |
| F07 | 同 F06，所有原文 caption。Baseline graph ownership | 本輪 synthetic caption 分離通過；原生漏 caption 與未知歸屬不能用生成 description 填充 |
| F08 | NCCU／混合 controls／圖內文字。RapidOCR＋supplement | 53 saved texts 交付可行，但完整 picture census、漏長指示與字形／順序仍需查核 |
| F09 | controls 四方向與混合頁；臺南／英文 scans。四方向 adapter＋selective OCR | 舊方向實驗為 Docling2.102／Core2.96／Parse6.2；固定版前置接合、derivative lineage／inverse mapping 仍未完成。Line 0/180 classifier 不能替代頁面四方向 |
| F10 | 所有圖，含 Trace2Skill p2、ReasoningBank p9。FigureClassifier-v2.5 | 可選且偏好開；本輪未跑／未接固定版 classifier。未知／錯類不得豁免 F08/F11/F12 |
| F11 | 全 WikiSkill、Trace2Skill p2、NCCU 與 controls。固定 component description 方法 | 兩保存回應只證接合；全圖目標清單與同版新圖意準度未驗 |
| F12 | 真實 ReasoningBank p9；controls bar/line/log/pie。component chart＋typed supplement | 13 saved points round-trip 成立，真實 chart 準度／完整 coverage 未驗；pie null unit 不被修值 |
| F13 | WikiSkill、SEAL p2–4、controls，display／inline。A 分支 | 完整 source census 與通用發現／交付 gate 由 A 判定；C 成功不能抵銷 A 缺口 |
| F14 | WikiSkill p20–22、DGM p24/p51/p63–64、controls。A 分支 | literal／識別字／鄰文及跨頁來源仍需完整 gate；DGM p63–64新契約與原41 units分開 |
| F15 | 原有 emitted 內容依 F20 保留 | 延後表單新增抽取 |
| F16 | 不新增指定 schema 抽取 | 延後 |
| F17 | WikiSkill 明確 title／metadata；controls。native metadata／title role | 不新增 LLM metadata 抽取；title、缺省與衝突需查核 |
| F18 | 全55頁與實際 continuation。各 owner source/hash/provenance；方向 adapter | 本輪 keys／refs／SHA 有界控制通過；完整 revisions／多fragment／方向座標映射仍缺 |
| F19 | 每頁 source-only required-work census；各 provider／mapping group | failed／unattempted 明示，本 bundle 整體 partial；HTTP200／stop 不能當語意成功 |
| F20 | 同版 raw responses、conversion／group diagnostics、saved artifact bundle | 本輪 provider raw 完整隨 bundle 保存；fresh-restored worker／group失敗與未知欄位全流程仍待驗 |
| F21 | 全 WikiSkill＋全部補充頁主要 Markdown、Core、同版 supplements | 本輪 public metadata/key/graph/reload 有界成功；仍非完整同配置文件交付 |
| F22 | 不新增 core chunking | 延後，由 projection 需求決定 |

## 下一段去留與成本

本輪新增 remote calls＝0、model loads＝0、detector/classifier inference＝0、下載／安裝＝0。`results.json` 的 control wall time 只計最後一次程式控制，不含來源調查／實作；完整 C elapsed 依 registration 計算。沒有重用歷史 API RTT 作本輪延遲，也沒有計新模型準度。

目前可以保留 **public Core＋自訂 sidecar 的有界元件接合**。完整配置仍不能進第三段付費推論：需要全頁 source-only image/work census、同版 heading/title/semantic parent 方法、四方向前置與逆映射，以及 A/B 各自必要 gate。這些不是靠再送一次 description API 能解決的問題。

C 的已準備離線 jobs 為6 saved API＋1 saved OCR＋2 mock owners，另1 pinned cached S0 native replay；**不是 N_3**。下一段精確 image jobs／N_3／每job input保留量／總input與completion cap 都為 unknown：必須先按計畫完成 fresh S0（第三段才允許）與全量 inventory，再凍結預算；未凍結不得送 request。沒有編造可用的 call/token 上限。

保留歷史來源、helpers、production、SDK、原計畫與所有 holdout；只新增本 C 目錄。未測新準度、全量 coverage 或真正 worker 恢復，不能據此宣告完整 profile 可交付。
