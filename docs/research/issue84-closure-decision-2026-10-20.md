# #84 結案決策表（v2 定稿候選，2026-10-20 21:45；U1–U5 已確認，W3c 已納入）

> 用途：#84 以「決策與交接票」結案的依據。結案代表**方案與交接已完成**，不代表 pilot 已通過或正式模型已取得資格。
> 狀態圖例：✅ 已定案　🟡 候選已定，細節待補　⏳ 待證據　❓ 待使用者決策

## 0. 摘要

- **正文、讀序、標題（F01–F03）**：已定案。原生論文 36 篇／715 頁全量驗證；13/36 篇有已知的位置類缺陷，交 #83。
- **表格（F04/F05）**：TableFormer，維持 `do_cell_matching=True`；複雜表用 HTML 交付；依 U2 帶表格狀態、不阻擋文件。部分表格有多欄被壓成單格的結構缺陷（數值仍在），交 #82。
- **公式、code、圖片 enrichment（F08、F11–F14）**：依使用者確認的 B 方案，交付「模型重建內容＋狀態標記」，不阻擋 Canonical Acceptance。第一版一律 `unverified`，並附佐證訊號；`verified` 的開放條件交 #83。
- **code**：原生 PDF 優先使用「原生字層＋座標縮排」，模型重建只作補充。
- **正式模型**：公司地端 VLM 的身分待取得，列為 #82/#83 的 gate。DEV 的參考身分是 `gpt-6-luna`。

## 1. 需正式記錄的使用者決策（2026-10-20）

| # | 決策 | 取代或修改 |
|---|---|---|
| D1 | 選 R1 並執行：方法可登錄（`METHOD_REGISTERABLE`），但 A/C 的完整方法不晉升 | 10-18 的 R1/R2/R3 提案 |
| D2 | 原生論文（含原生多欄）版型覆蓋是第一優先；**掃描 PDF（F09）優先序往後** | F09 的第一版範圍 |
| D3 | DEV 推論改用 `gpt-6-luna`；Sol 只作一次天花板參考；正式版維持地端開源模型（Q51） | Q51 的 DEV 暫用範圍 |
| D4 | **第一版 enrichment 走 B 方案**：交付為模型重建內容，帶 `verified`／`unverified`／`disputed`／`failed` 標記；原圖、原生文字與位置一律保留 | F11–F14「必含即阻擋」的語意 |
| D5 | **Q31/Q33 拆開評估**：enrichment 出錯不阻擋文件的 Canonical Acceptance；品質改由方法資格驗證管，指標是「verified 中的改義率」與 verified 覆蓋率 | Q31、Q33（以及 Q45 的阻擋語意） |
| D6 | 評測 JEV 式決策模型作為品質閘門（已完成 W4／W4b） | — |
| D7 | DEV API 常備預算 US$5（只限 Luna）；Sol 單獨核准 US$3 | — |

## 2. 主幹身分（交接給 #80）

| 元件 | 身分 |
|---|---|
| Docling | docling-slim 2.132.0、docling-core 2.99.0 |
| Pipeline | `StandardPdfPipeline`、`PyPdfiumDocumentBackend` |
| Layout | `layout_heron_default`，revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；reading-order separators=True |
| 表格 | TableFormer V1 accurate，**`do_cell_matching=True`（預設，維持）**；False 因 3 張確認語意退化而不採用 |
| OCR | RapidOCR PP-OCRv6 small det/rec＋ch_ppocr_mobile_v2 cls（點陣區域與圖片裁切） |
| 標題 | `HeadingHierarchyModel.assign_heading_levels`，bookmark-only 規則 |
| 影像 | 正式版開啟 `generate_page_images`／`generate_picture_images`（F06）；記憶體由 core 的 group5 處理 |
| Enrichment VLM | 正式版：公司地端 VLM（身分待定，#82/#83 gate），**須接近 Sol 等級**（公式與 code 重建強烈受模型等級影響）；DEV 參考：`gpt-6-luna`（下限）、`gpt-6.1-sol` low（上限） |
| 不採用 | CodeFormulaV2 在 CPU 上執行（每項約 140 CPU 秒，公式改義 25%）；整頁 VLM 轉換；VJev-Vision 作閘門；官方選項 V1（separators 關閉）、V2（Egret）、V4（docling-parse backend） |

## 3. 逐功能決策

| 功能 | 第一版定位 | 方法與身分 | 證據 | 阻擋或標記規則 | 已知限制 → 去處 |
|---|---|---|---|---|---|
| F01 原生文字 | 必含 | 主幹＋mapper 三條匯出規則 | W2：正文 anchor 找到 98.6% | Q4，依 U1 調整：遺漏與重複阻擋，位置類缺陷加標記 | 字層重複與雜訊 2 篇 → #83；匯出問題 4 件 → #81 |
| F02 版面與讀序 | 必含 | 主幹 | W2：ACL、IEEE、ACM、LNCS、arXiv 讀序全對 | 位置類缺陷依 U1 加文件標記 | CVPR 首頁等讀序 5 篇、caption 插斷 6 篇 → #83 |
| F03 章節層級 | 必含 | bookmark-only 後處理 | 修好 175、0 退化 | Q7 | 10 篇沒有 outline → #83 |
| F04 表格結構 | 必含 | TableFormer，cell_matching=True；**複雜表用 HTML 交付** | W3b＋W3c 人工裁定（mapper 後）：一般表 7 通過、5 失敗、59 無法判定；複雜表 4 通過、7 失敗、101 無法判定 | 依 U2：交付＋表格狀態，不阻擋 | UNKNOWN 145 張、定位不到 60 張 → #82 擴充答案 |
| F05 表格可解讀性 | 必含 | 同 F04；VLM 表格為備選（Sol METHOD_STOP） | 同上 | 依 U2 | 關鍵比較尚未評 → #82 |
| F06 原圖可檢視 | 必含 | Docling 影像開啟＋custody | 980 個 raster 中 865 個完整在框內 | 阻擋（交付缺圖） | 向量圖無法判定 → #83 |
| F07 原文 caption | 必含 | 原生 layout＋mapper | 195 張主圖中 144 張有對應 | 阻擋（caption 遺失） | 插斷正文的併入 F02 限制 |
| F08 圖內 OCR | 必含 | **本機 RapidOCR**（不用 VLM） | 513 項中 467 項正確 | 依 U3 納入狀態標記 | 小圖示、密集文字 → #83 |
| F09 掃描頁 OCR | **優先序往後（D2）** | RapidOCR 預設 | 多欄掃描頁沒有合格配置 | 掃描頁標示品質限制 | → #83 列為已知限制；後續另案 |
| F10 圖片分類 | 可選 | FigureClassifier v2.5 | 12 張裁切大類相符 | 不阻擋 | — |
| F11 圖意描述 | 必交付、帶標記（D4） | 自訂 adapter：整頁 context＋裁切、嚴格 schema、一圖一請求 | Luna：29 張中 25 張通過 | `unverified`（決策模型對描述無效） | 正式模型 → #82/#83 |
| F12 Chart 數值 | 必交付、帶標記 | 同一 adapter 的 chart 請求 | 類型 29/29，數值多數全對 | `unverified` | 幾何驗證訊號尚未建立 → #83 |
| F13 公式 | 必交付、帶標記 | VLM 來源群組 adapter；原生 orig 作後備 | Luna 28/34、**Sol 34/34**；困難群組 Luna 12/30 → Sol 22/30（雙方都有效的組）；Luna 的模型改義 3/44 | `unverified`＋佐證訊號（d3-mini 分數、字層一致、語法） | verified 開放條件 → #83 |
| F14 code | 必交付、帶標記 | **原生字層＋座標縮排優先**；VLM 重建補充無字層的情況 | 字元錯誤中位數：原生 3.7%、E0 8.2%、CodeFormulaV2 16.5% | 原生優先；模型重建 `unverified` | 樣本僅 8 個單位 → #83 擴大 |
| F15/F16 | 延後 | — | — | — | — |
| F17 metadata 與標題 | 必含（照原規劃） | 原規劃 | **今天未驗證** | 原規則 | → #83 |
| F18 來源追溯 | 必含 | 頁碼、bbox、版本；重建內容為頁面範圍精度 | 搬移與讀回通過 | 阻擋（缺來源） | — |
| F19 狀態與不確定性 | 必含 | 四種狀態標記＋佐證訊號（見第 4 節） | — | — | 規格 → #81 |
| F20 provider 保存與映射 | 必含 | 三條匯出規則 | mapper 原型 | — | → #81 |
| F21 Canonical Markdown | 必含 | 複雜表用 HTML；生成內容只進 supplement | W3b 發現官方 Markdown 會讓父表頭掉出表外 | — | → #81 |
| F22 | 延後 | — | — | — | — |

## 4. 狀態標記規格（交 #81，開放條件交 #83）

- `verified`：佐證訊號一致，**而且**該類別已在 #83 證明 verified 改義率 ≤2%（暫定）。**第一版沒有任何類別達到 → 不使用。**
- `unverified`：有重建結果，未達 verified 條件。**第一版的預設。**
- `disputed`：佐證訊號互相矛盾，例如字層顯示 `S_ret`、重建卻是 `S_rev`。
- `failed`：沒有產出。
- **每個項目都附**：原圖裁切參照、原生文字（若有）、佐證訊號（原生字層一致度、運算子與數字比對、語法檢查、d3 分數），以及缺資料的理由。
- **開放 verified 的條件（#83）**：每類建立 ≥300 項的已判定校準集；在保留的測試集上 verified 改義率 ≤2%，並報覆蓋率；用公司正式模型重測。

## 5. 取代 #72 的範圍

- **取代**：Q11 的「不承諾表格比較、圖意、公式與 code 重建、不新增 inference stage」→ 改為第 3 節的交付定位。
- **保留**：恢復與 required-work 原則、來源追溯、64 頁執行目標與資源邊界（Q12）、自動版本化改進（Q13），以及「production 不做逐文件人工修正」。

## 6. #54／#55 同步

- **#54**：高頻負載目標依 U4 移到新的正式版 gate 小票；#54 加註指向新票。
- **#55**：Markdown 是主要消費表示；enrichment 一律帶狀態標記，下游必須處理 `unverified`；複雜表用 HTML；附上第 3 節的已知限制清單；表格解讀的用途界線依 U2 決定。

## 7. #80–#83 改寫要點

- **#80 core**：第 2 節的主幹身分；影像開啟、group5；enrichment 階段（本機 RapidOCR、VLM adapter、閘門訊號）；required-work 與失敗語意；CodeFormulaV2 只能在 GPU 上評估，CPU 不採用。
- **#81 mapping**：三條匯出規則；複雜表 HTML；四種狀態標記與佐證訊號欄位；生成內容不進正文；code 原生優先。
- **#82 表格 gate**：arXiv HTML 答案集；cell_matching 的結論（True 維持；False 結構較好但有 3 張語意退化）；**候選驗證訊號：兩種設定各跑一次，不一致就標 `disputed`**；逐表門檻與 U2 的處置；擴充 UNKNOWN 的答案；關鍵比較。
- **#83 qualification**：已知限制清單；公司 VLM 與 GPU 的 gate；verified 開放條件；高頻負載（依 U4）；F17 驗證。

## 8. 使用者決策（2026-10-20 確認，照主線建議）

| # | 決策 |
|---|---|
| U1 | **調整 Q4**：原生 PDF 只有「位置類」缺陷時（caption 插斷、讀序錯、作者順序錯，但文字完整），文件可以通過 Canonical Acceptance，並加上文件層級的已知限制標記；**內容遺漏或重複仍然阻擋**。caption 插斷的自訂修復另立可選的改善票 |
| U2 | **表格比照 B 方案**：表格一律交付（原生格子＋HTML＋原圖），帶表格層級狀態；未達 Q10–Q16 門檻不阻擋文件，但下游做表格比較前必須檢查狀態。#82 以「可判定表的通過率」作資格指標，並擴充答案集 |
| U3 | **F08 圖內 OCR 納入狀態標記機制** |
| U4 | **高頻負載目標另開小票**，列為正式版 gate（類似 #86），不擋 pilot 與 map |
| U5 | **模型權重移出 repo**；新開 `research/issue84-pdf-core` 分支，只 commit 報告、計畫、程式、manifest、雜湊與小型摘要；大型輸出保留在本機或物件儲存，以雜湊引用 |

## 9. 未決的外部輸入

- 公司 VLM 的精確身分與 GPU 配置：使用者後補 → #82/#83 gate。
- 高頻負載數值：依 U4。
- Sol 天花板測試已完成（US$1.08）：公式 34/34、困難群組 22/30、code 6/7；描述與 Luna 相當；chart 數值經診斷 99/101 在容差內。2/73 個請求被拒判，應記為 `failed`。結論：公式與 code 受模型等級影響很大，#83 以 Luna／Sol 作為公司模型的下限與上限參考。

## 10. 證據索引（本機，尚未 commit）

- W2：`docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/decision-record.md`（另有 round2、round3）
- W3：`docs/research/pdf-core-w3-structured-elements-2026-10-20/report.md`
- W3b：`docs/research/pdf-core-w3b-2026-10-20/report.md`；W3c：`docs/research/pdf-core-w3b-2026-10-20/cell-matching-confirm/report.md`
- A/C：`docs/research/pdf-core-r1-method-2026-10-20/`（R1 `report.md`、`live-preflight/round3-luna`、`round4-local-ocr`、`round5-strict`、`round6-sol`）
- W4：`docs/research/pdf-core-w4-decision-gate-2026-10-20/report.md`
- W4b：`docs/research/pdf-core-w4b-d3-2026-10-20/report.md`
