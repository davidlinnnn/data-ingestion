# 兩個 smoke 樣本的獨立 Q4 評讀

評讀範圍：各原論文 **PDF 第 2 頁整頁**的 `corpus/{acl_bert,nips_attention}/page2.png`、`reference-page-2.json`，以及 `smoke/{id}/document.md`、`document.json`、`metrics.json`。已看過兩張完整頁面，由頁首至頁底逐段核對文字、段落、欄序、清單、標題與頁碼；沒有執行 conversion，也未修改任何凍結產物。

`NO` 表示本次人工評讀的可見頁面內容中未發現該類改變意思的錯誤，不代表整篇通過；`UNKNOWN` 表示證據不足以裁定等義，不得填成 NO。自動對齊的零候選數只是輔助定位。

## 逐頁裁定

| 論文／原始頁 | 改變意思的漏 | 改變意思的重 | 改變意思的錯序／混段 | 清單從屬錯誤或家具混入正文 | 額外已確認缺陷 | 該頁整體 Q4 |
|---|---|---|---|---|---|---|
| BERT p2 | NO（僅本頁可見部分） | NO | NO | NO | 2.1、2.2 的章節層級錯誤 YES | UNKNOWN：正文四項未見阻擋，但章節結構已錯；是否阻擋須依預期的結構用途裁定，不能宣稱完整品質通過 |
| Attention Is All You Need p2 | UNKNOWN：必要下標關係在輸出中未顯式保留 | NO | NO | NO（以 Markdown 或遵守 content_layer 的正文消費方式） | inline 數學結構遺失 YES | UNKNOWN：不能把下標攤平一律當作等義字型差異 |

### BERT p2 的證據

- 雙欄讀序正確：左欄 Introduction 尾段 → 三個 contributions → 2 Related Work → 2.1 首段；接續右欄 `These approaches…`、`ELMo…`，再到 2.2 的兩段。沒有右欄段落插入尚未讀完的左欄段落，亦未見兩個不相干段落合併。
- 三個 bullet 在 JSON 為同一 `#/groups/0` 的三個 `list_item`（`#/texts/1` 至 `#/texts/3`），Markdown 也為三個平行項目；各項內容和從屬正確。
- 關鍵意思仍在：`unidirectional`／`bidirectional` 的對比、`not deeply bidirectional` 的否定、`eleven NLP tasks`、相關引用及 task 對象均未見改變。引號、引用旁空白、行末斷字合併的細節不造成可見正文意思變更。
- **已確認層級錯誤**：source reference 的 `2 Related Work` 為 level 1，`2.1…`、`2.2…` 為 level 2；JSON 三者全部 `level: 1`、直接掛在 `#/body`。Markdown 三者全部 `##`。編號 `2.1`、`2.2` 尚保留，人可推回正確關係，因此不能只憑這個斷定自然語言正文意思已改變；但 JSON／Markdown 標題層級確實不忠實，不能給「章節層級正確」或整頁全面通過結論。
- 本頁開頭 `word based only on its context` 為前頁延續，結尾 `Left-to-right language model-` 為次頁延續；此次切片有保留可見片段。**跨頁接合尚未驗證**，不能將不完整頁邊句子算作漏句，也不能宣稱跨頁延續已正確。
- `https://github.com/ google-research/bert .` 在 Markdown/JSON 含空白，與圖上跨行的 URL 對應字元仍在。這是可點擊連結／字串表示缺陷的候選；本次未把它等同正文陳述意思改變，亦未測試連結行為。
- 此頁圖中沒有 caption、footnote、頁首頁尾文字／頁碼；家具污染 NO 僅適用這張沒有相關元素的頁面，不能算分離能力已受測。

### Attention p2 的證據

- Introduction 的 4 段、Background 的 4 段、Model Architecture 的 1 段，與三個標題都按整頁由上而下出現，沒有漏段、重段、段落串錯的可見證據。
- 意義敏感的普通文字仍在：`In all but a few cases`、`without using sequence-aligned RNNs or convolution`、`twelve hours on eight P100 GPUs`、`linearly for ConvS2S and logarithmically for ByteNet` 等限定、否定、數值和對象在輸出中保留。
- **不能直接認定數學下標攤平只是字型差異**：圖中 Introduction 第 2 段為 $h_t$、$h_{t-1}$；Markdown 與 JSON `#/texts/2` 的 `orig`／`text` 都是 `h t`、`ht − 1`。`h_{t-1}` 是前一時間步的狀態，`h_t - 1` 則是狀態減一；這個 scope 有數學意義。上下文 `previous hidden state` 可讓熟悉者猜回原義，卻不足以證明輸出明確等義。
- 同樣地，Architecture 圖中為 $(x_1,\ldots,x_n)$、$\mathbf z=(z_1,\ldots,z_n)$、$(y_1,\ldots,y_m)$；JSON `#/texts/11` 與 Markdown 為 `(x1, ..., x n)`、`z = (z1, ..., z n)`、`(y1, ..., y m)`。索引字元還在，但不是明確的下標表示；粗體向量與純量的區分亦未在文字中保留。不能以查找正規化後相同來消除這個問題。
- **native JSON 沒有補救語義**：這兩個 text item 的 `orig` 與 `text` 一樣已攤平；沒有 inline math、LaTeX、MathML、下標 span 或字符級 baseline 資料。`prov` 只有整段頁碼、bounding box 與 charspan；它能指回 PDF 區域，不能單靠該 JSON 重建每個下標的 scope。`pictures`／`tables` 也未提供這些 inline math 的結構替代物。故 native JSON 不能作為「下標語義其實有保留」的證據。
- 本次確定的是**數學表示結構遺失**；未直接裁成「已發生數值錯誤 YES」，因這一頁文字脈絡下，讀者或應用能否唯一還原尚不明。依 Q4 保守列必要表示的語義完整性 UNKNOWN，交主線裁定是否允許這類 plain-text 記法。不能報 Q4 NO／通過。
- 圖中頁底頁碼 `2` 在 JSON `#/texts/12` 為 `label: page_footer`、`content_layer: furniture`；Markdown 沒有頁碼混入正文，所以已觀察輸出為污染 NO。該 item 仍由 `#/body.children` 可達，**消費者必須遵守 `content_layer`**；若只遍歷 body children 串字串，將重新混入頁碼，此用法未受測。
- 此頁無 list、footnote、caption；只能記未觀察到污染，不能記該類型覆蓋成功。三個一級標題的相對層級在 JSON 均為 level 1，與 reference 一致。

## 每篇／全量狀態

| 論文 | 已人工評讀 | 其餘頁面 | 跨頁延續 | 整篇 Q4 |
|---|---|---|---|---|
| BERT | 原始 p2 | UNKNOWN | UNKNOWN | UNKNOWN |
| Attention Is All You Need | 原始 p2 | UNKNOWN | 未受測／UNKNOWN | UNKNOWN |

此次沒有產生任意整體通過率，也沒有回填自動 metrics 的 UNKNOWN。全量前需由主線決定：章節層級錯誤是否阻擋預期的 NotebookLM 類結構用途，以及數學下標／向量表示遺失如何裁定；應把 `math_structure_uncertain` 與 heading-level defect 顯式保留，避免正文句子完全對齊就被解讀成語義完整。

未檢查其他頁面、跨頁接合或下游檢索／生成行為；這兩頁的文字覆蓋結果不能外推為整篇 Q4 通過。
