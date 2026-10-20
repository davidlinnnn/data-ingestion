# 原 W3 人工 50 個公式區塊訊號

本檔屬 BEGIN5 後的衍生分析。`cohort-w3-formula.json` 只包含原 W3 最終 50 個人工區塊，保留 15 個阻擋、28 個保義及 7 個 metadata-only 原標籤。新 W3b 的逐條公式 40 件不進入此分母。原人工單位是整個來源環境／區塊，不將其標籤複製成多條公式。

`a` 以原 PDF 的 pypdfium2 字元為主：沿原 provenance bbox，不加 padding，選取中心落在框內的字元，保留 PDF 字流索引順序及原有空白。每個字元、索引和 bbox 均另存 `formula-native/`。未用輸出文字搜尋、調框或改字元順序；Docling assembled `orig` 僅保留為診斷。重建端採原人工審查的 RAW/MAPPED 字串，這 50 件兩通道字串相同，並逐 ref 記錄實際 enrichment 狀態。來源小於完整固定預測範圍的 ImageTransformer 00002 設 `a=UNKNOWN`，沒有把鄰式造成的差異算成字元失敗。

字元投影、Levenshtein、字型正規化、運算子／數字序列及 .95 門檻均直接使用已登錄 helper。`c` 只對支援且可解析的公式進行本機 Chrome MathML 真實渲染；確證 brace 語法錯誤可為 false，未支援語法或 adapter／環境錯誤保留 UNKNOWN。渲染成功與字元相似不代表數學保義。`b` 由整合者在同 PDF、頁面及可證同源區域下另配獨立模型，單一模型與 orig copy 不算第二重建。

最終版本沿統一的 `signals-character-method-bug-amendment-xml.json` 重算。XML 序列化只等價 escape 字元，不移除模型多出的 `&`；合法 alignment 環境之外的裸 `&` 是可確證語法失敗。各列將 raw TeX syntax、MathML serialization、actual Chrome render 分開保存。舊版 features 與渲染實證保存在 `formula-features-v1/`。

為保留關聯，每列有完整 ref 集合的 composite prediction group，也有逐 ref prediction groups；集合相異但共享 ref 的區塊另標 overlap。原 PDF 單一 bbox 字流末端具有 `(整數)` 的式號另存為來源式號證據，不從 E1 推回式號。多區域或沒有可證式號者仍 UNKNOWN。

最終 50 列中，`a` 為 44 KNOWN（2 pass、42 fail）、6 UNKNOWN；`c` 為 29 次真實 Chrome render pass、11 次確證語法 false、10 UNKNOWN。排除 7 個 metadata-only 後的 43 個有真值標籤單位，`a` 為 2 pass／35 fail／6 UNKNOWN，`c` 為 25 pass／10 false／8 UNKNOWN。這些是訊號結果，非語義正確率：SICA 已知改義的 utility 公式同時通過 `a` 與 `c`，正是一個 verified-wrong 反例。

之後依 `signals-character-method-bug-amendment-pdfium-utf16.json` 修正 PDFium UTF-16 collector：原幾何選中的相鄰 high/low surrogate 才合併為 Unicode scalar，兩個 raw 索引都留存；半 pair 不擴框，應為 UNKNOWN。全部 50 區域重抽，只有 P03 formula00006 的 23 對 supplementary 數學字母影響字串；其相似度由 .55357 升至 .83929，`a` 仍 false，整體判定計數不變。沒有半 pair。最終 decoder 保留所有非 surrogate 的原 `get_text_range` 字串，51 個區域的原 bbox、raw 索引集合及所有 BMP 字串皆逐項 assert 不變；未將原空字替換成控制碼。原 collector、50 native 證據、features、renderer 實證及 SHA manifest 保存在 `formula-features-pre-utf16-v2/`，中間的 BMP 控制碼版本另存 `formula-features-utf16-before-bmp-preserve/`，逐項最終差異見 `formula-utf16-old-new.json`。重新實際渲染的 screenshot 與修正前 byte-identical，`c` 判定亦逐案一致；正常化、門檻、人工標籤均未改動。
