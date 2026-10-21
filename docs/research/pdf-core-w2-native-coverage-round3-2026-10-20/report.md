# W2 第 3 回合：補完、裁定與官方選項全量消融

完成 Set F 16 篇／164 頁及 Set P 20 篇／551 頁。建議 Profile 保留 Heron 與 `use_reading_order_separators=True`，關閉頁面／圖片產圖，啟用官方 **bookmark-only heading**。V1 與 V2 都有已確認的新阻擋，不建議全域納入。這是研究結論與候選設定，沒有修改正式 Profile 或既有檔案。

## 1. 等價控制及 6 篇補跑

Sentence-BERT（11 頁）與 P01（28 頁）控制均通過：只遞迴排除 `image` 欄位，DoclingDocument 其他每個值完全相同；Markdown 位元組完全相同；v3 的 metrics、anchors、candidates、pages 四份結果亦逐值相同。證據：[controls-equivalence.json](controls-equivalence.json)。通過後才執行補跑。

| 論文 | 頁 | 結果 | 程序 wall 秒 | 峰值 RSS GiB | 重試 |
| --- | --- | --- | --- | --- | --- |
| P-03-2603.25158v5 | 25 | success | 31.52 | 7.751 | 0 |
| P-06-2606.14239v2 | 29 | success | 46.35 | 8.418 | 0 |
| P-10-2509.25140v2 | 30 | success | 53.04 | 9.071 | 0 |
| P-16-2505.22954v1 | 64 | success | 102.60 | 6.857 | 0 |
| P-18-2511.16043v1 | 18 | success | 30.69 | 8.927 | 0 |
| P-20-2505.03335v1 | 50 | success | 80.81 | 8.728 | 0 |

全部實際 conversion 均逐篇啟動新的 CPU4 worker，batch 1，單工共享鎖，12 GiB RSS／主機可用 4 GiB 守門；沒有 conversion 重試。30 篇沿用第二回合輸出，補齊的 6 篇採影像關閉結果。不能把記憶體下降完全歸因於產圖開關：第二回合曾長駐 worker，本回合每篇新程序也是差異。

## 2. 全部候選裁定與 36 篇判定

875／875 個自動候選已對照頁圖裁定（包含 Adam 的 45 個 fallback 漏句候選）；747 個非阻擋、128 個阻擋告警，合併相同來源事件後為 23 件。額外全文差異檢查發現的已確認缺陷也獨立納入，最終合計 **26 個來源事件、13 篇 CONFIRMED_BLOCKING、23 篇 CLEAN_AFTER_ADJUDICATION、0 篇 UNKNOWN**。若只計自動候選則是 12／24／0，不能用來蓋過已確認的額外缺陷（例如 P02 首位作者錯序）。

三個額外事件為 P02 p1 首位作者錯序、P03 p5–6 Table3 切斷 `We report the ... official ANLS`、P10 p10 頁外舊圖字串新增不可見的 reviewer 任務對象。最後一項在 V1 只是拆段移位、V2 仍完整保留，均不算修好；已加入 baseline 的事件／受影響頁，沒有改凍結 oracle 或自動候選數。

| family（保留凍結分類） | 篇 | 頁 | BLOCKING | CLEAN | UNKNOWN | 確認受影響頁（篇內去重） |
| --- | --- | --- | --- | --- | --- | --- |
| ACL/EMNLP | 5 | 86 | 0 | 5 | 0 | 0 |
| ACM sigconf | 2 | 20 | 0 | 2 | 0 | 0 |
| CVPR/AAAI | 2 | 22 | 2 | 0 | 0 | 4 |
| ICML | 3 | 39 | 1 | 2 | 0 | 2 |
| IEEE conference | 2 | 10 | 0 | 2 | 0 | 0 |
| NeurIPS/ICLR | 9 | 238 | 6 | 3 | 0 | 12 |
| Pilot-other/unknown | 6 | 167 | 3 | 3 | 0 | 11 |
| Springer LNCS | 2 | 20 | 0 | 2 | 0 | 0 |
| general arXiv | 2 | 24 | 0 | 2 | 0 | 0 |
| general arXiv (article; template uncertain) | 3 | 89 | 1 | 2 | 0 | 6 |

全部 36 篇表：[papers.md](papers.md)。逐候選頁圖、來源理由、輸出理由與共用根因：[adjudication/records.json](adjudication/records.json)、[adjudication/root-groups.json](adjudication/root-groups.json)；額外缺陷亦保留獨立來源。

`CLEAN_AFTER_ADJUDICATION` 僅表示所有自動候選都已裁定，且沒有已知阻擋；不是全文逐字驗收。Oracle 是稀疏 anchor：可信正文共 6097 個；長度、唯一性、LaTeX 清理與可對齊範圍仍有限，作者、表格／algorithm、部分 prompt、數學與短句會漏檢。Adam 的 text-layer fallback 還會把跨欄作者、標題與數學組成不實複合句。公式符號的純呈現攤平另列 F13；必要英文條件或對象遺失仍是 F01。

Adam 的部分 display／algorithm 數學確有空 formula 輸出；這些 fallback 複合 prose 告警依 D1 記為 oracle 範圍錯誤，**沒有宣稱數學內容完整，也沒有一概當成 D3 的 inline-math 呈現差異**。已保留 actual_formula_loss 與數學未驗風險；該篇本身仍因必要英文條件等缺陷列為 BLOCKING。可信 footnote 37 個全數找到且角色分離；528 個可信 caption 全數找到，仍可能切斷正文，所以「找到」與「正確分離」分別報告。

## 3. 四類失敗的零推論根因

**CVPR 首頁右欄先讀。** ResNet 與 YOLO 的來源 layout 框已分欄，錯在 reading-order predictor 先取右欄，之後段落合併擴大成跨頁錯接（兩篇各 p1–2）。關閉 separators、改 Egret 都未修好既有首頁錯序。

**caption／algorithm 與正文錯接。** Image Transformer p5 的 `depen- ... dence`、p7 的 `Amazon Mechanical ... Turk`，WikiSkill p7–8 的跨頁句與 SEAL p4 的 `self-edits ... are sampled`，在原 layout 已把獨立圖說／演算法標題標為 text；reading-order 將它放在未完正文之間，再被 paragraph merge 串起。單純 label 不正確但仍是獨立完整段落的案例，裁為 metadata 差異，沒有算 Q4 阻擋。

**prompt 框被判 picture。** SICA P07 p12 的兩個 picture 均有原生 children，`orig` 分別保留 1238／1488 個字元（第二框 `text` 1439，另有 49 個清單標記在 orig）；Markdown 省掉整框。這是匯出／映射問題，應交 #81，不能宣稱 backend 沒抽到。全 715 頁共 235 個 picture，其中 **172 個框（73.2%）含 ≥30 個非空白 PDF 原生字元，分布 146 頁／35 篇**；172 個框都有大量 native children，但僅 14 個框至少一個 substantial child 在 Markdown 可找。這是「文字密集 picture」代理統計，包含圖表文字，**不是 172 個已確認 prompt 框或漏文事件**。見 [diagnostics/report-full36.md](diagnostics/report-full36.md)。

**colspan Markdown 重複。** SkillRL P05 p22–24 的 merged cell 在 native table 唯一；官方 serializer 按展開 grid 重複輸出。最小零推論樣本：native 唯一 1、grid 2、Markdown 2、HTML 1 並保留 colspan=2，確認是固定 Markdown 交付行為，歸 #81，沒有修改抽取器或 serializer。

另外兩個實質根因不能被上面四類掩蓋。Adam p12 的英文 Definition 10.1、P16 p25 必要 task IDs 被 layout 標為 formula，官方 reading-order 將文字放入 orig 並清空 text，公式 enrichment 關閉時 Markdown 只剩 placeholder；原字仍可回收，但交付漏必要條件／對象。P10 p9／26、P20 p6／28／48 的部分舊圖中文字則已存在於 PDF 的不可見或裁切 text layer；`get_text_bounded` 的重疊框再次放大重複。P20 p6 的舊頁碼是獨立且位於 clipping rectangle 外的 glyph，漏進 orphan body，不是同一頁碼的 serializer 重複。p48 部分覆蓋機制仍未確定，不能把所有案例都稱為 clip 問題。見 [diagnostics/adam-p12-formula-role.md](diagnostics/adam-p12-formula-role.md)、[adjudication/recovery-helper/source-cell-origin.md](adjudication/recovery-helper/source-cell-origin.md)。

## 4. 官方選項消融

V1、V2 各 36 篇／715 頁，均使用影像關閉、完全相同凍結 oracle 與原版 v3 分析器。Egret 權重已在本機，使用官方 `LayoutObjectDetectionOptions.from_preset("layout_egret_medium")`，沒有下載模型；其餘 layout 設定與 baseline 逐值核對。模型檔與 preset 證據：[diagnostics/egret-medium-local.json](diagnostics/egret-medium-local.json)。

### 自動候選與語意事件分開計數

| 變體 | 頁 | prose 找到／可信 | 覆蓋率 | 自動漏 | 自動重 | MD LIS 外 | 混段候選 | caption 入正文候選 | footnote 入正文候選 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 715 | 6024/6097 | 98.803% | 73 | 4 | 19 | 4 | 71 | 0 |
| V1 | 715 | 6024/6097 | 98.803% | 73 | 4 | 19 | 4 | 71 | 0 |
| V2-official | 715 | 5956/6097 | 97.687% | 141 | 3 | 19 | 4 | 108 | 0 |
| V3_B | 715 | 6024/6097 | 98.803% | 73 | 4 | 19 | 4 | 71 | 0 |

覆蓋率不是通過率。混段候選的 4 件來自可評估的 35 篇；Adam 的跨欄混段為 NOT_EVALUABLE，沒有當成零錯誤。V1 自動候選刪除／新增為 0／0，但 full native 與完整 Markdown 差異檢查仍發現真退化。32／36 篇逐值相同；其餘 P02、P10、P13、P18 逐段核對。**V1 修好 1 個來源事件（P02 p1 首位作者），新增 3 個阻擋事件（P18 p18、P10 p23、P10 p24–25）**；P13 p19 完整 algorithm float 移位而內容／歸屬仍清楚，裁為允許的移位，沒有算修好。P10 的保存上游 layout、parsed pages、assembled 逐值相同；兩套 reading-order 零推論重播都與各自 native／Markdown 完全一致，確認變動發生在 separator 控制的讀序與後續 merge。

V2 的自動候選刪除／新增為 **88／242**（69 個篇內頁），不是 88 個修好或 242 個新壞。其逐案語意比較與按 family／失敗類型彙總另附 [comparison/semantic-summary.md](comparison/semantic-summary.md)。

自動指標另按 family／候選類型完整列在 [comparison/automatic-family-type.md](comparison/automatic-family-type.md)，保留原先對 Pilot 模板不確定的分類，不強行併入八個已知 family。逐篇原始 v3 JSON 中保留的 F01/F02 UNKNOWN 是未改動分析器的自動輸出；最終三類判定以獨立 adjudication 為準。

### V3：全部 36 篇 × 8 組規則

下表單位是參考標題，不是論文或 Q4 事件；b=bookmark、n=numbering、s=style。全部 288 份結果只變 heading level，文字、orig、順序、實際 parent 關係不變。

| 規則 | 修好 | 新壞 | 正確標題 | 層級錯誤 |
| --- | --- | --- | --- | --- |
| b0-n0-s0 | 0 | 0 | 177 | 254 |
| b0-n0-s1 | 5 | 176 | 6 | 425 |
| b0-n1-s0 | 181 | 40 | 318 | 113 |
| b0-n1-s1 | 181 | 81 | 277 | 154 |
| b1-n0-s0 | 175 | 0 | 352 | 79 |
| b1-n0-s1 | 177 | 61 | 293 | 138 |
| b1-n1-s0 | 232 | 17 | 392 | 39 |
| b1-n1-s1 | 232 | 33 | 376 | 55 |

**bookmark-only 修好 175、新壞 0**，剩下 79 個層級錯誤、33 個 structural heading 缺項、1 個 role error、2 個 ambiguous；另有 197 個 paragraph command 未被當 heading，已分開揭露，沒有當作正文遺失。按 family 的完整八組表：[heading/family-comparison.md](heading/family-comparison.md)。

使用實際 S0 PyPdfium backend 的官方 PDFium outline extractor、`parsed_pages=None` 重評 36 篇，完整 JSON、level 與 Markdown 都與 B-only 原結果相同，確認可直接用官方 pipeline options 整合。載入 Core 會裁正 P10／P20 共 222 個 bbox 欄位；已在 heading 的 source→Core normalization 單獨記錄，stage 的「只改 level」比較起點是同一份 Core baseline。早期 240 份 stage artifact 未先清除不使用的 image metadata，後來只在本回合目錄移除 image，逐值證實其他欄位及 Markdown 不變；其餘 48 份從一開始就關閉 image。詳見 [heading/verification.json](heading/verification.json)、[heading/pdfium-integration/summary.json](heading/pdfium-integration/summary.json)。

另對 Egret 的 36 份保存輸出評估 raw 與 B-only：raw 相對 Heron 是標題修好 0／新壞 1；Egret+B 相對 Egret raw 是 178／0，相對 Heron raw 是 178／1。其中多出的 3 件包含 missing／ambiguous 的匹配轉變，沒有當成額外的語意修復。B-only 不能彌補 Egret 引入的圖說／prompt 正文阻擋；其 1029 個 v3 候選與 Egret raw 逐值相同。見 [heading/V2-bookmarks/summary.json](heading/V2-bookmarks/summary.json)、[comparison/V2-Bonly-candidate-equivalence.json](comparison/V2-Bonly-candidate-equivalence.json)。

## 5. 建議 Profile 與剩餘阻擋

建議候選設定：[recommended-profile.json](recommended-profile.json)：Heron、separators=True、產圖 False／False，heading enabled=True、bookmarks=True、numbering=False、style=False，其他 baseline 值及所有 enrichment 關閉不變。這個組合的 B-only 後處理已在同一批保存輸出全量驗證，不需要重跑 conversion；凍結 v3 的正文候選亦完全不變。

V1 的作者收益伴隨 3 個新阻擋；V2 的 task ID／caption 收益也伴隨新正文錯接與 Markdown 遺失。這些結果不足以支持全域替換。沒有對個別文件設例外，沒有調數值參數。

採建議組合後，原有 **26 件／13 篇／35 頁** 的已確認 F01/F02 阻擋仍在；完整範圍與來源片段：[remaining-blockers.md](remaining-blockers.md)。包括兩篇 CVPR、Adam、Image Transformer、WikiSkill、P02、P03、SkillRL、SICA、P10、P16、SEAL、P20。#81 可承接 picture-child、formula-orig 與 colspan 的可用文字／Markdown 交付問題；讀序、layout label、backend clipping 污染仍需要後續解法。本輪沒有證實一套無退化的官方選項可一起解決，不能寫成「官方永遠無解」。

其中 **4 件**曾由未採用的官方變體個別修好（P02 作者、Image Transformer p5、P03 p5–6、P16 p25）；**其餘 22 件，影響 11 篇／30 頁，在本輪尚未觀察到完整的官方選項修復**。SkillRL 一個重複 cell 有局部改善但整群仍未解。這個區分避免把「沒有安全的全域替換」誤寫成「每個個案都沒有官方選項效果」。

## 6. 時間、RSS 與重現紀錄

| 實際 run | 成功／嘗試 | 頁次 | wall 秒（含 init） | conversion CPU 秒 | 每頁 service p50／max 秒 | 峰值 RSS GiB | 主機最低可用 GiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| controls-v1 | 2/2 | 39 | 39.1 | 142.7 | 1.005/5.127 | 7.798 | 19.870 |
| recovery | 6/6 | 216 | 345.0 | 1308.2 | 2.221/8.298 | 9.071 | 20.738 |
| V1 | 36/36 | 715 | 986.6 | 3547.5 | 1.491/11.857 | 8.784 | 20.943 |
| V2-official | 36/36 | 715 | 990.2 | 3552.2 | 1.497/13.165 | 8.543 | 20.515 |

實際 80 次 conversion、1685 頁次；程序 wall 合計 2360.9 秒，已量測 conversion＋init CPU 8663.9 秒。每頁 service 為 stage service 時間；pipeline residence 含排隊／重疊，不能逐頁相加當全程 wall。RSS 是採樣的 process tree 峰值，不是單頁專用記憶體；完整每頁 residence、RSS、CPU 在 [resources.json](resources.json)。

保留兩個 harness 預檢錯誤：先有 2 筆 options 比較因 set 序列化順序而失敗；另有 36 筆 Egret factory init 因誤用 legacy model constant 而失敗。兩者都在 conversion／模型推論前發生，原日誌完整保留；修正型別／比較方式後才進行上表實際 conversion，沒有重試已開始 conversion 的論文。見 [preflight-correction.json](preflight-correction.json)、[v2-initialization-correction.json](v2-initialization-correction.json)。

凍結 v3 SHA256：`915f598207a20e2ede942abedd12dd707e3d3620ff9748edb95e178c801176fa`；oracle seal SHA256：`17c02e47c9e11fabdeb996b2d7327d3326b45feff80baa3125218693cd518c4e`。原始分析器未改；所有新 runner、評分、裁定、設定、圖與報告均在本回合目錄。沒有 API／VLM、沒有新模型下載、沒有開 holdout、沒有碰 R1、沒有 commit／push／GitHub 留言。完成後停止，等待主線下一步。
