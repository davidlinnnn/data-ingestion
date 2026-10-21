# B 有界收斂：表頭 paths 可作新候選，真實品質與跨頁仍未通過

2026-10-17。登錄硬限 60 分鐘，API／模型載入／下載／安裝／holdout／GitHub／production／SDK 修改均為 0。工作只寫入本目錄；既有回應、producer、schema、grader、oracle、圖像及報告不變。

**去留：停止重試舊 grid-spans producer；保留一個可進下一輪固定比較的「明示 header paths／named row dimensions」候選。完整 B 為 partial，沒有任何新來源準度通過的主張。** 不再以 T04 的失敗回應猜補正確 paths；不要求複製原印刷格線或 colspan，也不新增數值零錯門檻。

## 必要性審查與最小實作

T04 原回應同時給出 ragged grid 與互相矛盾的 category／metric／parent spans；其數值位置診斷不能證明必要欄位歸屬。既有 [停止證據](../../pdf-core-stage1-followup-2026-10-17/contract-audit-t04.md)保持有效。本次重跑 unchanged padding parse，六筆仍為五合法、一拒絕，T04 沒有被改判或產生修正版。

新表示把每個 metric 欄直接綁定一條 header path，把 family／variant／method 以具名 row dimensions 明示，不再要求模型協調一份重複的 header grid／span 宣告。Header node 用 scope ID 與 parent identity 區分同名不同條件；同一 ID 的文字／parent 矛盾會拒絕。Section 用明示 row membership 保存，normalized Markdown 為每列帶出 Section；未猜印刷全寬合併格。

`method.py`只把這個新表示轉成既有公開 `TableData`，再使用凍結的 public Core mapper 及已驗 literal Markdown serializer。沒有新 renderer、SDK patch、逐表規則或模型呼叫。這是我們的研究整合契約，並非 Docling 官方新 pipeline。

每個資料 cell 保留 raw string、source-cell ID、row／column key 與 normalized anchor。`001.20 / 0` 保持一個 cell，沒有拆成兩個模型輸出；同一 source-cell ID 若在 normalized 位置重複，所有位置與同一 raw text 都明示保存在 supplement，不能以改文字的方式拆格。Header paths／dimensions／group scope 原文亦保存在同版 supplement。Normalized Core 的 unit spans 只描述展示，不宣稱是原印刷格；原影像／native envelope 才是物理證據。模型自行聲稱的 IDs 與 scope 是否忠於來源，仍需獨立來源核對，機械檢查不會替它證明。

因此，**沒有原印刷 colspan 不是產品失敗理由**；缺表頭／條件或實際錯綁則仍是重大錯誤。Pair 共同來源格與角色順序、列維度、precision／blank／literal、caption 與來源關係均保留必要性。新候選不是任意複雜表的通用格式承諾。

## 實際結果與邊界

| Gate | 結果 | 證據與不能推出的主張 |
|---|---|---|
| 新 normalized 表示 | **pass，synthetic transport** | Named dimensions、同名異 scope headers、明示 section、raw pairs／blank／precision／LaTeX literals，經真實 Markdown parse 及 JSON reload 保持；不證新模型能產生正確內容 |
| T01／T02／T05 舊成果與兩 collateral | **歷史保護 pass** | 原六筆 raw 與 35 個 live artifacts 不變；既有 35 + padding 10 控制通過。沒有把來源答案轉入新表示，再稱新方法通過 |
| T04 真實來源 | **fail 保留** | 原回應仍因不矩形／表頭歸屬矛盾拒絕。新 path producer 尚未執行 |
| Table 7 四組 math | **partial／未重建** | 原生 crop 已準備，E017–E020 的分數範圍及 row/cell 錯置仍未修。Synthetic 合法 LaTeX transfer 只證字串接合，不能代替來源重建，也未驗表內數學排版品質 |
| 已為單一 logical item 的多頁表 | **pass，synthetic transport** | 新 helper 只公開替換該 item 的 data，保留兩頁 envelope、重複 header row、caption、其他 table 欄位與非目標資料；JSON reload 通過 |
| T03 真實跨頁表 | **partial／未解** | 舊 inventory 是研究層主動拒絕 `len(prov) != 1`，不是 Core 無法保存。原生多段如何分組、共同重建及綁定各段來源仍缺證據，本次不猜 matching 或寫通用 merge |

原 T01／T02／T04／T05 的 470 個數值／23 個比較保持；collateral 另列。Table 7 的四組 math 不加入此分母。T03 的 264／7 與單頁分母分開，沒有因未納入本輪而取消必要要求。沿用複雜表最多 5% 數值誤差、所有必要表頭／條件與關鍵比較正確的界線。

## 已完成的有界控制

- 新 10 個 unittest (`test_method.py`)通過；包含 immutable inputs、真實 Markdown／reload、scope 矛盾、missing／foreign／duplicate bindings、group order、unknown vs blank、pair identity，以及 multipage stale source／invalid grid 拒絕。
- 既有 B 的 35 個及 padding 的 10 個測試通過。這些 regression 會讀已曝光 DEV 評分資料；本輪明示為 producer 方法設計者兼曝光 DEV reviewer，不能稱 blind review，也沒有回寫任何答案。
- 保存回放 (`replay.py`)確認 142 個 Stage1、35 個 live 與 166 個 ABC artifact hashes 不變。資料生成／檢查只寫本目錄。
- 首次新控制有一個 harness assert 用 `out.tables[-1]` 找 non-target，public deletion 改變 storage order 而失敗；已依既有 resolved-source signature 方法改為尋找 RichTableCell table。precheck (`precheck.json`)保留，沒有修改候選內容。

合成物見 input (`synthetic-semantic-input.json`)、Core (`synthetic-document.json`)、bindings (`synthetic-bindings.json`)、[Markdown](synthetic-document.md)、實際 render (`synthetic-rendered.html`)。多頁控制另存 Core (`synthetic-multipage-document.json`)與 binding (`synthetic-multipage-binding.json`)。

## 下一步的精確有限工作

七筆輸入 inventory (`proposed-input-inventory.json`)已備妥：前六筆逐一重用原 crop 的 SHA／size，另加 WikiSkill p22 `#/tables/2` 的 Table 7 原 native crop。後者由 pinned public `TableItem.get_image` 從 cached S0 頁圖取得，沒有 padding 或人工 bbox；與獨立 page-image crop pixel-exact，目視四個 framework 的公式／complexity 都在圖內。E017–E020 只標示 evaluator 來源範圍，沒有輸入公式答案。

值得提出下一輪**最多七次、單一新表示／模型配置、零重試**的比較：原六 target 保護普通表、複雜表、pairs 及兩 collateral，再以一個完整 Table 7 target 驗四組 math 與 row association。保留同頁 all-or-nothing delivery；不得只發佈成功主表、丟掉 collateral 或挑成功 panels。新結果應與原 raw 保存比較，不能回頭改判舊輪。

**目前 `live_ready=false`。** 本次未準備新 prompt／provider requests，未凍結新 response producer、完整 input／output tokens、request／total timeout、transport／memory 及截斷處理界線。下一個付費比較須先把這些資源 gate 及測試固定；本輪不擴寫網路 runner。不能把舊六次的 token／latency 直接套到新表示，或據 normalized payload 較短就宣稱更快。

T03 可另外先作離線 gate：明示完整 fragment inventory／logical grouping／重複 header 的角色及各段來源責任，再評最小 public 接合；若仍要猜 matching 或大量 merge 規則，就停止該方法並提出具體取捨。單頁七次有研究價值，不代表跨頁或完整 B 可放行。

沒有新來源轉錄準度、跨頁 source success、GPU／vLLM、吞吐或泛化結論；公司模型及獨立 holdout 未驗。
