# 原生 JSON → MD／HTML 最小交付 mapper

36 篇原生 baseline 已套用，只有 R4 衍生輸出；沒有 conversion、Docling pipeline／options 修改、模型、OCR、API 或新套件。這是可檢查的交付原型，沒有回寫 DoclingDocument，也不是通過全文 Q4 的 production profile。

## 輸入與 reference

逐篇只讀 [R3 baseline-inputs.json](../../pdf-core-w2-native-coverage-round3-2026-10-20/baseline-inputs.json) 指向的原始 `document.json`。原檔為 canonical `$ref`；原型以 `self_ref` 索引直接解 reference，也接受 model_dump 的 `cref`，有合成等價 selfcheck。沒有 Core load／重存，因此不帶入 R3 曾記錄的 bbox clamp 或 reference alias 重存問題。每篇輸入 SHA256 與執行後不變檢查均保存。

每篇在 `outputs/<job-id>/` 有 `mapped.json`、`document.html`、`document.md`、`counts.json`，共 144 個逐篇檔案。`mapped.json` 是明示 `w2-raw-native-mapper-v1` 的自訂 schema，不是可交回官方 loader 的 DoclingDocument；其中 `self_ref`／原 `parent` 代表來源 locator，不是新 tree 的 JSON Pointer。Markdown 使用 CommonMark 可容納的 raw HTML，以表達 span、來源與不確定區域；純文字或會剝除 HTML 的下游尚未驗證。`mapped.json` 的 `text`／`orig` 是來源證據，`units` 是稽核索引；消費者只應讀 tree 的 `delivered_text` 或 table cell 一次，不可把全部 metadata 欄位串接當正文。

## 三條規則

1. `text.strip()` 為空且 `orig.strip()` 非空時，在原生節點原位置交付 `orig`，保留原角色並標 `ROLE_UNCERTAIN`。不把 formula 自動改為 prose。366 個回退節點全被 baseline 標成 formula；其中 64 個含非換行／tab 的控制字元。JSON 原字串保留，HTML／MD 將控制字元顯示為 `\uXXXX`，避免默默刪除。原生字串可能已有破碎上下標、重複指標、缺字或條件錯接；回退不等於公式正確。
2. picture 的所有原生 children（含 group／list）交付到獨立 `picture_native_uncertain` 區，不拼入正文段落。保留 `marker`、`enumerated`、原 parent／ancestors，渲染時補出原 marker 一次。C 圖片 supplement 另有 `NOT_EXECUTED` 區；沒有 OCR／VLM 或圖片補述。原型沒有自創密集度門檻，因此也暴露低字量圖標／圖表文字，並非都可當語義段落。
3. 表格讀原生 `table_cells`，不用展開後 grid 重複 cell 文字。有效座標使用 HTML rowspan／colspan 與空位置 placeholder，單一 cell 只交付一次。8 個原生重疊座標表格改用明示 `TABLE_LAYOUT_UNCERTAIN` 的單次 cell 清單，保留原 row／col／span，不推測欄位關係。原生結構本身的真偽未由此修復。

正文保留原 children 順序；家具按 content_layer／page_header／page_footer 分到獨立家具區，仍保留來源證據。所有節點沿用原 parent 資訊，不重建語義樹。child／caption／footnote 重複 reference 只訪問一次，記錄 alias。

## 影響量與驗證口徑

|規則／範圍|Docling item refs 或框|篇數|另計的 cell／leaf 單位|
|---|---:|---:|---:|
|empty text → orig|366 個 text items|30|—|
|picture native 交付|226 個 picture 框|36|10,265 個 text items；picture 內 table cells 為 0|
|全部表格單次 cell 表示|238 個 table items|34|6,723 個 native cells|
|其中含 merged cell|74 個 table items|26|282 個 merged cells|
|前三規則主要 item refs 聯集|830|36|fallback texts + picture containers + table containers|
|再含 picture descendant text refs 的聯集|11,095|36|不能視為同數量的語義段落或修好事件|

226 框中有 16 框的 native 字流只有 10 個以下空白分詞，分布 4 篇，逐框清單在 [impact-counts.json](impact-counts.json)。此分桶僅描述暴露風險，不作密集度篩選、品質通過門檻或噪聲真偽判定；高字量圖表也可能含軸標與數字噪聲。獨立 channel 不代表內容已驗證。

36 篇共 19,342 個來源 text items 與 6,723 個 table cells，全部在 tree／HTML／MD 以其 source ref 單次交付；0 missing refs、0 unlinked roots、0 新增同 ref 重複。逐 unit 檢查可見字串仍存在其對應 HTML 節點。此處只保證 identity 與字詞交付，不保證跨 ref 無語義重複。來源已有 2,290 組「同篇不同 ref 的完整字串相同」值被保留，其中許多是頁碼／圖表數字；沒有用字串相同就去重，也沒有全文語義重複審核。

合成 selfchecks 包含 canonical／modeldump references、empty/orig 控制字元、picture child 與 caption alias、merged span 單次文字；實際 36 篇驗證來源 hash 不變、所有 unit identity／字詞對應、渲染 ref 單次。這些不是全文 Q4 或公式／讀序測試。[selfcheck.json](selfcheck.json)、[counts.json](counts.json)、[impact-counts.json](impact-counts.json) 保存機器結果。

## 四事件逐 item 核對

已重新看過 R3 保存的原頁圖：Adam p12、P16 p25、SICA p12，以及 SkillRL p22–24；[four-case-evidence.json](four-case-evidence.json) 保存每一 item／cell、原 text／orig、parent／marker、交付值、渲染節點文字、來源頁圖與輸入 hash。

|事件|最小交付修復證據|Q4 完整修好範圍|
|---|---|---|
|Adam p12|texts/419、420、423、426、430、432、434：Definition 10.1 量詞行與六個攤平公式從 orig 交付，在原生位置標不確定|字詞可取回；公式、原生順序、完整條件仍未驗證，UNKNOWN|
|P16 p25 task IDs|35 個 text-empty formula items 的 ID 回退；連原本可見項目，60 個來源 ID 均可取得且彼此 distinct|補回 ID 出口漏失；不重標 formula、不證成左右欄／清單從屬，全文 Q4 未宣稱|
|SICA p12 兩 prompt 框|28 個 text items 與全部 21 個清單 marker 保留。第二框去空白字元 text 1,439／orig 1,488；marker 補回後交付為 1,488，21 個 ListItem 的 marker + text 都等於 orig|修復明示 picture-native channel 的出口省略；沒有把圖誤標角色或原生樹重建修好，全文 Q4 未宣稱|
|SkillRL p22–24|tables/10 cell1、11 cell1／cell13、14 cell9 的 Task／skills 字串各只渲染一次，原 colspan 2／2／2／3 保留|這 4 個已知 serializer 重複 instance 修好；不據此宣稱整篇 Q4 通過。cell14/9 的原控制字元仍明示不確定|

可直接檢查：[Adam HTML](outputs/F-iclr_adam/document.html)、[P16 HTML](outputs/P-16-2505.22954v1/document.html)、[SICA HTML](outputs/P-07-2504.15228v2/document.html)、[SkillRL HTML](outputs/P-05-2602.08234v2/document.html)。這些交付範圍不含已知的作者區串錯、SICA p4 句子插圖串錯、SICA p13 原生 payload 順序、其他 furniture 或 native layout 錯誤的修復。

## 重現

原型只用 Python 標準庫：

```sh
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/pdf-core-native-std-20261017/venv/bin/python docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/mapper/map_documents.py
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/pdf-core-native-std-20261017/venv/bin/python docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/mapper/evidence.py
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/pdf-core-native-std-20261017/venv/bin/python docs/research/pdf-core-w2-native-coverage-round4-2026-10-20/mapper/outline_summary.py
```

來源與既有判定：[凍結 baseline 位置](../../pdf-core-w2-native-coverage-round3-2026-10-20/baseline-inputs.json)、[R3 逐案原判](../../pdf-core-w2-native-coverage-round3-2026-10-20/adjudication/records.json)、[R3 SICA／Alita 差異核對](../../pdf-core-w2-native-coverage-round3-2026-10-20/comparison/V2-semantic-p07p08.json)。heading 的有／無 outline 分組另外見 [heading-outline.md](../heading-outline.md)。
