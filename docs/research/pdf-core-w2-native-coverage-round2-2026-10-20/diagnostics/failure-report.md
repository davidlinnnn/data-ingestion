# W2 全量：失敗類型與零推論定位

36 篇中 30 篇成功輸出 499 頁，6 篇 216 頁因 RSS guard 停止。本檔集中 machine candidates、指定代表頁的 stage 證據與資源失敗；**candidate 數量不是語意失敗總數**，同一個問題可能出現在多個指標。完整結構化資料見 `summary.json`。主線頁圖抽查與 F01/F02 Q4 裁定另行合併。

候選統計來自 `analysis/candidate-catalog.json`（本次快照 SHA256 在 summary 保存），依數量排序：

| 類型 | machine candidates | 代表頁／定位結論 |
|---|---:|---|
| furniture_in_body | 335 | 字流中普通 bibliography arXiv citation 亦會被寬鬆 stamp rule 命中；本類不能直接宣稱家具污染。交主線 oracle audit 核對，尚未完成此類 stage 定位。 |
| prose_role_or_layer_mismatch | 94 | P07 p12：prompt box 變 picture，其子節點文字仍在 native、預設 Markdown 不輸出。不能將所有非正文 label 視為文字真的消失。 |
| missing_anchor | 67 | Adam p1、P07 p4/p12、P17 p4，4 頁；有實際錯序／圖文插入，亦有 picture-child 覆蓋與 list marker 契約問題。 |
| caption_role_not_separate | 34 | 細看 caption 與圖內 subcaption；不是每個 text label 都混入獨立正文。 |
| caption_in_body | 33（主線統計 6 篇） | YOLO p8、ImageTransformer p5、P01 p8、P14 p15，4 頁；前者是圖子節點，後三者分別有實際正文錯混與獨立 caption 標籤錯誤。 |
| md_lis_outside | 19 | ResNet p1、YOLO p1 的正常分欄框被官方 predictor 排成右欄先於 Abstract／左欄。 |
| native_lis_outside | 18 | 同型，另 Adam 作者被排在 Introduction 之後。兩個 LIS 指標是不同輸出視角，不能相加。 |
| mixed_paragraph | 4 | Tacotron2 p2 是合法 `Each post-net layer...` 跨欄延續，誤報。 |
| duplicate_anchor | 4 | P05 p22：一個 colspan2 table cell 在 Markdown 兩欄展開重複。 |

## 可定位的實際問題與片段

| 代表頁 | 原因與輸出片段 | stage |
|---|---|---|
| ResNet p1 | `greatly benefited from very deep models.` 所在右欄段落先於 Abstract；assembled 左右框分開正確 | reading-order predictor |
| YOLO p1 | 右欄 `methods to first generate potential bounding boxes...` 先於左欄起句 `More recent approaches like R-CNN use region proposal` | reading-order predictor |
| ImageTransformer p5 | `...simpler depen- Local 1D Attention Figure 2. The two different...`，正文後半 `dence across channels...` 在後 | caption 原始 layout 標 text（0.83268），再 paragraph merge：cid67→69,71 |
| P01 p8 | `...matches or exceeds the strongest competing Table 1 | Method comparison...`，caption接進前頁正文 | caption 原始 layout 標 text（0.92826），paragraph merge：cid79→83 |
| P07 p4 | `...sub-task to be naturally LLM Context Window`；下一段才接 `discarded when...` | layout postprocessing 新增 orphan text／圖文角色，predictor 插入，再 merge cid60→65 |
| P17 p4 | `...in which self-edits Algorithm 1 Self-Adapting LLMs...`；下一段才接 `are sampled from...` | algorithm caption 原始 layout 標 text（0.78808），paragraph merge：cid49→39 |
| Adam p1 | `Jimmy Lei Ba ∗ University of Toronto jimmy@psi.utoronto.ca` 仍在 MD offset4015，但排在 Introduction 後，並接進 p2 Algorithm1 caption | reading-order predictor＋paragraph merge cid5→15 |
| P05 p22 | task example `I want a pair of men's black slip-resistant work shoes...`：native 單 cell，Markdown 重複兩欄 | table grid／Markdown serialization，與 reading order 無關 |
| P14 p15 | Table3／Table5 caption 分別獨立 text paragraph；沒有跟正文合段 | layout label（0.68501／0.71737）；有分離標籤問題，語意污染未證實 |
| P07 p12 | prompt boxes 的 native 子節點有全文與 2.1 等 marker，但無巢狀 list graph；3.3／4.2 標普通 text，預設 MD 不輸出圖子文字 | picture/list label＋child materialization＋Markdown serialization；清單從屬 Q4 需主線裁定 |

反例：Tacotron2 p2 `Each` 正確接到右欄 `post-net layer...`，是可接受延續。YOLO p8 `Quantitative results...` 是 `#/pictures/4` 下的 subcaption text，不是獨立正文污染；主 Figure6 caption 則正確獨立。

上述內容類別各最多 5 張代表頁：caption 4、missing 4、order 2、mixed 1、duplicate 1；其他重疊 finding 是同頁的 stage 證據，不另增加樣本。更完整解釋與節點 refs 見 [content-stages.md](content-stages.md)。

## 零推論重播資格

10 份完整文件重播，涵蓋 12 個文件／頁組案例，均確認 texts/groups/body/furniture/tables 與 picture 結構（除官方後附 image）完全相等，Markdown bytes 完全相等，模型推論 0。每個 trace 路徑、逐欄 equality、stage 與 source fragment 保存於 summary。PyPdfium private shape bboxes 依保存值 typed restore；ContainerElement 按原 label 恢復，避免 untagged union 誤還原。早期 `*-mismatch.json` 是 harness 還原／newline 比較問題的留存，不用於結論；最終 exact/restored traces 已重新核對。

重播相等只證明診斷觀測與原保存結果一致，不代表 oracle 完整，也不是全 499 頁逐句人工驗收。

## RSS-stop（6 篇；stage UNKNOWN）

P03／P06／P10／P16／P18／P20 共 216 頁。原 PDF metadata 檢查顯示皆標準 A4／Letter；後四篇有較大嵌圖，但未證實是哪一頁或哪個 stage 導致 RSS。0.1 秒 sampled process-tree RSS 最高 **8.230 GiB**，為 8 GiB guard 的真實取樣 overshoot；不能寫成「始終 ≤8 GiB」。各篇首筆／峰值是 worker 累積生命週期狀態，沒有 isolated fresh-process 比較，不能歸因模型 leak。

本類僅選 5 張輸入規模代表頁：P20 p2、P16 p61、P18 p2、P18 p7、P10 p10；沒有 render 大圖。逐頁 metadata、RSS與官方候選見 [resource-failures.md](resource-failures.md)、`resource-pdfs.json`。

## 建議：只列官方選項，均未執行

- upstream picture／caption／orphan role：官方 Heron101／Egret `layout_options.model_spec` 候選；本輪不改模型，也不保證能修復分欄正確但 predictor 排錯的首面。
- 幾何 reading order：官方 `use_reading_order_separators=False` 可作消融，因本輪 shape bboxes 非空；目前不宣稱有效。
- 標題：官方 `heading_hierarchy_options.enabled=True`，由主線用原輸出重評。
- 資源：較小 `queue_max_size`，以及視保存契約調整 `images_scale`／保存影像與 parsed-pages flags。三個 batch 已是 1。這些未驗證能避免六次 RSS stop。
- 本固定版本未發現停用 paragraph merge 的官方 public pipeline option；亦未找到可直接修復 colspan Markdown 重複或預設 Markdown picture-child omission 的 pipeline 開關，不能把此類說成只需調參。

選項依據是本機固定官方原始碼；精確檔案引用見 [method.md](method.md)、[resource-failures.md](resource-failures.md)。尚未修任何問題、未重跑 conversion；家具 stage 與全篇清單語意驗收仍未完成。
