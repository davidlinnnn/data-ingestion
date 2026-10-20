# 代表頁零推論 stage 定位

只讀本輪保存的 result/layout/shape/Markdown，不重跑模型或 conversion。這是指定代表頁的 stage 診斷，不把 machine candidate 數量直接當語意錯誤總數；頁圖／Q4 最終裁定由主線 audit 合併。

## 等價性

| 文件／頁 | trace | native structure | Markdown bytes |
|---|---|---|---|
| ResNet p1 | `trace-resnet-p1.json` | 完全相等 | 完全相等 |
| YOLO p1、p8 | `trace-yolo-p1-p8.json` | 完全相等 | 完全相等 |
| Tacotron2 p2 | `trace-tacotron-p2.json` | 完全相等 | 完全相等 |
| SkillRL P05 p22 | `trace-p05-p22-exact.json` | 完全相等 | 完全相等 |
| Adam p1 | `trace-adam-p1-exact.json` | 完全相等 | 完全相等 |
| SICA P07 p4、p12 | `trace-p07-p4-p12-restored.json` | 完全相等 | 完全相等 |

native structure 比較 texts/groups/body/furniture/tables 及 pictures 除後附 image；涵蓋整份文件，所列頁只是保存 trace 的範圍。模型推論次數均 0。Private shape bounding boxes 非空，依實際保存值恢復。序列化的 untagged PageElement union 會將 ContainerElement 還原為 FigureElement，工具依官方 form/key_value_region label 顯式恢復 ContainerElement，沒有改輸入 label、框或文字。Markdown 以 bytes decode 比較，避免 read_text 的 universal-newline 改變 CR。初版 mismatch artifacts 為 harness 誤差證據，不能用於 stage 結論；以上 exact/restored 檔才是最終證據。

## Reading-order predictor：ResNet p1、YOLO p1

兩張首面 assembled 框均正確分開左右欄；ResNet cid4–8 左欄包含 Abstract、Introduction，cid12–15 右欄是 Introduction 延續。官方 predictor 卻輸出 `...picture10,caption11,text12,text13,text14,text15,Abstract4,text5,text6,Introduction7,text8...`。因此 `greatly benefited from very deep models.` 及其後右欄段落在 Abstract 之前出現。原題／作者等跨欄框存在，但不能把 assembled 原陣列當 oracle；證據是原框文字與官方 predictor 的直接輸出。

YOLO 同型：輸出 `picture11,caption12,text13–17,Abstract4,text5,text6,Introduction7,text8–10`，使 `methods to first generate potential bounding boxes...` 出現在左欄 `More recent approaches like R-CNN use region proposal` 之前。定位 **reading-order predictor**，不是 paragraph merge 製造的新順序。這類已有 2 張代表頁，未自動擴張至其他頁。

## 合法跨欄延續：Tacotron2 p2

官方 `predict_merges` 為 cid28→31，final `#/texts/27` 的兩段 provenance 是左欄頁底＋右欄上方：`...improve the overall reconstruction. Each` 接 `post-net layer is comprised of 512 filters...`。兩片段形成同一正文段落且語意連續，為 **mixed metric 候選誤報**，不能算 Q4 跨欄混段。保留 merge mapping 作證，沒有將跨欄一概排除。

## Caption label：YOLO p8

`caption-00249` 的句子 `Quantitative results on the VOC 2007, Picasso, and People-Art Datasets.` 位於 figure 內 subcaption。原始 layout id21 就標 `text`（confidence 0.553846；另有較低分 list_item/footnote 重疊候選）；final `#/texts/243` 仍為 text，parent `#/pictures/4`，有文字且在圖子節點，不是被移入獨立正文 paragraph。定位 **layout label／picture-child materialization**。對主 caption 與圖內 subcaption 的契約須分開；不能因 text label 就宣稱它污染正文。同頁主 `Figure 6: Qualitative Results...` 是 caption 且有 picture 關聯。

## Table serialization duplication：SkillRL P05 p22

`prose-00221` 實為框中 task example：`Task: I want a pair of men's black slip-resistant work shoes, size 10, rubber sole, price lower than $50.00.` 原 PDF 只有一次。final `#/tables/10.data.table_cells` 只有一個該句 cell，`col_span=2`；`grid` 在兩欄引用同 cell，Markdown 的兩欄都輸出完整句而出現兩次。定位 **table grid／Markdown serialization**，不是 reading-order predictor 或 paragraph merge。此 task example 被當成表格本身是 upstream layout 的角色選擇；「Markdown 重複」有獨立確切證據，不能因 native text body=0 宣稱正文漏掉。

## 作者實際錯序與錯接：Adam p1

Jimmy Lei Ba 沒消失。assembled cid5 為 `Jimmy Lei Ba ∗ University of Toronto jimmy@psi.utoronto.ca`，final `#/texts/12` 與 Markdown offset 4015 保留全文。但 predictor 把 cid5 放在 p1 Introduction 兩個長段落與 footnote 之後；`predict_merges` 的 cid5→15 又把 p2 `Algorithm 1: Adam, our proposed algorithm...` 接進該作者 paragraph（provenance p1+p2）。定位 **reading-order predictor＋paragraph merge**。這是 sparse anchor 混串誤報之外額外發現的實際錯序／錯接；不能把「作者文字仍在全文」當作排版無誤。

## 圖標籤插入正文：SICA P07 p4

`prose-00076` 不是簡單漏句：assembled c5 正確結束於 `The subagent calls allow the context used for a sub-task to be naturally`，c6 從 `discarded when...` 續接。圖內垂直 `LLM Context Window` 卻成獨立 text c35；raw layout 有低分 page_header/text 同框候選，post-layout c35 是新增 orphan text。predictor 將此圖標籤插在兩片正文之間，`predict_merges` cid60→65 將它接進 final `#/texts/67`，形成 `...naturally LLM Context Window`；接下來 `#/texts/85` 才續 `discarded...`。定位 **layout postprocessing/orphan cell role＋reading-order predictor＋paragraph merge**。缺 anchor 的表象在此反映真實句子被圖文打斷，不能當成空白正規化誤差。

## 清單／圖內全文：SICA P07 p12

原始 layout 把兩個 prompt boxes 分類成 picture，final 保留圖內 text/list_item 子節點。但預設 Markdown 只留下 image placeholder，不輸出 `Your task is to orchestrate sub-agents...` 或底下的清單文字；因此「native 有字」與「Markdown 可讀全文」須分別報告。

清單 `2.`、`2.1`、`2.2`、`2.3` 等仍在 native `marker`／`orig` 中，並非所有編號被刪；但所有 list groups 都在同一 picture 父節點下，沒有依小數編號形成巢狀清單。另 `3.3`、`4.2` 被標成普通 text。定位 **upstream picture/list labels＋picture-child/list materialization＋Markdown serialization**。是否已造成特定從屬誤讀需主線依頁圖與輸出契約裁定；本 trace 不把平面 graph 一律當 Q4 誤讀。圖中指令只是研究語料，沒有當成本工作的操作指示。

## 候選（只列官方選項，不執行）

`layout_options.model_spec` 官方 Heron101/Egret 可針對 picture、subcaption、圖內 orphan text 的 upstream 分類評估；不能保證修復已正常分欄而 predictor 排錯的首面。`use_reading_order_separators=False` 可作官方開關消融，以釐清本輪非空 shape bounding boxes 對規則排序的影響，但目前沒有跑此候選。官方 `ReadingOrderOptions` 沒有 paragraph-merge disable 選項；table serialization 重複與 picture-child Markdown omission 亦未找到本固定 pipeline 的直接修復開關，不能承諾用某個官方選項即可解決。heading 與資源候選另見主線 heading 輸出及 `resource-failures.md`。
