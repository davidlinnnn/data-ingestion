# 第一段 B：精簡表格表示離線結果

結論：**partial**。單頁表示／交付 gate 通過；跨頁接合 fail；下一段的 6 個來源工作已準備，但遠端執行登錄仍未就緒，不能立即呼叫模型。

- started_at：2026-10-17T06:10:35.659996+00:00；deadline：2026-10-17T07:40:35.659996+00:00。首次分支 SDK／來源盤點前登錄，硬上限 90 分鐘未重置；完成於 2026-10-17T06:15:10.372587+00:00，實際 274.71 秒（含準備、實作、控制及登錄；未碰時間停止線）。
- 實際載入的套件 metadata：Docling-slim 2.132.0、Core 2.99.0、Parse 7.22.3、Pydantic 2.14.1、markdown-it-py 4.2.0；未載入任何推論模型。
- 程式與證據只新增於本 B 目錄；production、SDK、原計畫／README、歷史回應／helpers、原來源／oracle 均未修改；未 commit／push。

## 實作與真正控制

`protocol.py` 是唯一新協定：位置由二維 grid 決定；spans 只宣告合併格；roles 指定 column／row／corner／section；row_groups 明列 start／end 與 section anchor；保留 panels 及多個 row dimensions。每格不再重複宣告四個座標。機械展開後，直接走既有 caption ownership policy、公開 TableData／TableCell、公開 graph 接點及既有 LiteralTableSerializer extension。沒有新 renderer、數值修補、oracle 值比較、欄位移動或表頭猜測。

空字串只代表已知 blank；dash 保留實際字形；null 僅代表被 span 覆蓋；`{"unknown":true}` 是不同的顯式未知狀態，schema 可保留、完整交付明確拒絕。必要內容與 target-level diagnostics 分開；所有層級 extra=forbid，錯層欄位拒絕，不在看完輸出後搬動。

`controls.py` 實際執行 **25 項控制全部通過、30 個負例全部拒絕**（詳見 `results.json`、`negative-results.json`）。這些是機械控制數，並非模型準度。

| 項目 | 實際結果與證據 |
|---|---|
| 普通表、雙列維度、多層同名 metric | 公開 TableData 完全等於合成原始 physical cells；真正 Markdown 解析保留 A/B 的 Score/Spread ancestry |
| rowspan／colspan、兩個 rowgroups | Core spans／row_section 正確；group alpha [2,5)、beta [5,7) 的明確 scope 在同版 bindings 內原樣保留 |
| paired values、blank／dash／zero／precision | `1.2 ± 0.3`、`10 / 20` 保持同格；空字串、`—`、`0`、`-0.0`、`001.20`、`1e-3` 真正渲染保留 |
| Literal | `<s>`、entity 字串、pipe、反斜線、backticks、Markdown emphasis／link／image 字形與 CR/LF 允許的 reflow，通過實際 CommonMark+table token 與 HTML 產物檢查，未活化為來源不含的 HTML／image |
| Caption／來源／鄰文 | Caption 一次且順序保留；非目標正文及 rich table、pages／origin／furniture、source refs／whole-table provenance 不變；沒有生成 cell bbox；baseline 不變 |
| Panel | 另一個公開接點控制驗兩 panels 的 ref／title identity 與單一 caption ownership |
| 保存 | JSON reload canonical 與 Markdown 一致；第二個 Python process 再讀完整 document／bindings 並重匯出，5 組產物一致 |
| 負例 | 非矩形、重疊／越界／zero span、covered／anchor 矛盾、unowned null、重複／covered／越界 role、非法 header／rowgroup scope、錯層與未知欄位、numeric／bool coercion、漏／重複／未知 target、缺內容、caption 猜測、未知內容、空／截斷 JSON 均拒絕 |
| 不靠 oracle 驗合法性 | 合法但內容為 999 的新增 row 可經 parser；測試不以來源預期列數／數值來調整結構 |

`document.json`、`bindings.json`、`document.md`、`rendered.html` 是同一組合成輸出。Core 的 row_section 只有標記；**精確 rowgroup end scope 在 bindings 的 compact_provider.panels[].data.row_groups**，不是憑 Core boolean 冒稱完整。主要 Markdown 仍可讀，細節由同版 bindings 保留；in-crop conditions 同樣原樣保存在 bindings。這項補充表示是自訂協定，不稱作官方自動推斷。

`mock_sources.py` 另對原四頁 **全部六個 native targets** 統一注入同一個通用合法 mock，每頁一次 complete target mapping。四頁全部通過：非目標內容／順序／來源、原 caption ownership、whole-table provenance、無 cell bbox、literal／precision 實際 render、JSON reload 均保留。原稿相關輸出位於 `source-mocks/`；`MOCK` 值刻意與來源無關，只證明接點，不能當新模型或數值成績。

## 跨頁最小反例：公開型別可存，既有 mapper 仍拒絕

`multipage-public-core.json` 是一個 logical TableItem，含兩頁有序 provenance，以及兩個重複 header rows。公開 Core JSON reload 可保留單一 logical identity、fragment 順序 [1,2]、重複表頭 flags／cells 及無 cell bbox；stock Markdown 實際保留續表 header row 與資料。

同一物件傳入現有 `adapter.inventory(doc, 1)`，實際得到：

> this bounded page protocol does not support multi-page table targets

見 `multipage-result.json`、`multipage-public-core.md`。這證明是**現有頁級 inventory／mapper 接合限制**，不能推成 Core 沒有多頁 provenance 能力。本次到這個有證據的停止點便停止跨頁路徑，沒有加入 merge／graph repair／新 renderer。沒有執行 T03，也沒有把三頁分離表格算續表完成。第三段完整候選仍被阻擋。

## 下一段登錄與成本

`prepare.py` 重新核對原四頁 baseline、頁圖、options、PDF 及全部六張 crop 的實際 SHA256；透過公開 inventory 重數 1+2+2+1 個 targets；144dpi 原生 whole-body bbox 的 floor／ceil crop 邊界與既有資產一致。`asset-verification.json` 保存 exact paths／hashes，並核對歷史 `standard-runtime-v2.json` 的 pinned 版本紀錄。這是 **historical cached S0 身分／相容性證據**，不是本次 fresh Standard，也未用 E1 enrichment 產物冒充 S0。

`next-stage-jobs.json` 固定六個具名 jobs 的來源／physical page／target／image hashes 與 crop 規則，6 calls、concurrency1、retry0、180秒/request、30分鐘/live、12GiB RSS、啟動10GiB／運行8GiB available 界線；不刪兩張 collateral，不加 detector。`prompt-and-schema.json` 保存本協定的唯一離線 draft prompt／schema。

**ready_for_remote=false**，原因逐項保留，未編造預算：

1. 零 API 範圍沒有驗證目前 provider model ID／能力；歷史 `gpt-6-luna` label 不是本次不可變權重證據。
2. 來源 text／conditions／diagnostics 保留 unrestricted string，尚未定義可證明的有限最大合法 payload；因此沒有冒稱「合成最大結構」已容納，也沒有照抄舊 65536 completion cap。
3. 未驗 provider tokenizer／影像 input 計數估法，所以每 job input reserve、總 input／completion 上限、transport byte cap 都是 null，附原因。必須完成可執行預算檢查與 usage overrun／budget_stop 後才能送第一筆。
4. 本次不改寫 live runner；既有 runner 不會自動理解新協定或累計 input budget，不能直接啟動它。

保留固定分母：單頁 primary **470 values／23 comparisons**、兩張 collateral 分開；T03 **264／7** 完全獨立且未執行。本輪沒有來源數值評分、模型準度／成本比較或 fresh pipeline 延遲主張。`source-mock-results.json` 的 mapping／serialize control 時間只是本機 mock 接合，不是文件完整時延。

| 方法部分 | 歸屬 |
|---|---|
| DoclingDocument／TableData／TableCell、公開 graph 修改、JSON 與 Markdown serializer extension 接點 | 官方公開 SDK，實際固定版執行，源碼 hashes 存於 registration |
| compact grid／spans／role scope validation、機械展開、同版 scope／provider bindings | 自訂研究程式 |
| Caption ownership policy、LiteralTableSerializer escaping | 既有自訂 helper 原樣重用；公開接點，不修改 SDK |
| Synthetic fixture／CommonMark renderer、來源 hash／crop核對 | 自訂驗證控制與既有解析依賴；不是新模型 |

下一步最小可執行結論：保留單頁協定為有界候選，但先補有限輸出／input 預算與 provider 能力登錄，才由主線決定是否放行六次比較。完整 profile 仍須處理多頁 mapper；不得以單頁 pass 抵銷跨頁缺口。

未做任何模型／detector／classifier 推論、remote/API、安裝／下載、憑證搜尋、Paddle、holdout、第二／三段實驗。風險是 mock 只證明表示／交付能力，不保證 VLM 能生成正確 grid，亦不保證成本下降。
