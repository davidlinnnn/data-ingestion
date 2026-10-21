# B 表示契約審核：T04 的獨立停止證據

2026-10-17。依 [next-step.md](next-step.md) 的離線審核範圍執行；只讀保存回應、既有契約、已曝光 DEV oracle 與凍結 runtime 的公開 Core／現有 serializer 程式。新模型／API 呼叫 0；未建立修補後候選。

**結論：T04 不能只靠刪除自訂傳輸冗餘，唯一且忠實地映射成可交付的表。應停止本輪 B 的追加推論，保留 T01／T02 與 compact 協定用量的元件證據。** T05 若另有無歧義的格式簡化，也不能據此放行完整 B。這不是「Docling 無法表示這張來源表」，也不是數值容錯不足；是本筆回應對必要表頭歸屬的宣告互相不一致。

## 必要意思與欄位

| 必要內容 | 本協定及既有交付接點 | 是否只是傳輸冗餘 |
|---|---|---|
| 每個數值屬於哪個 QA category／metric | `grid` 的實體欄位置、header `spans` 與 `roles`；映射為 Core `TableCell` 的 offsets、spans、`column_header`；原生 Markdown serializer 按欄串接多層表頭 | 正確歸屬是必要意思；`null` covered slots 與 span 重複表達 occupancy，但不能在兩者矛盾時任選一者 |
| model family／variant／method 的列維度及適用列 | body 格文字、rowspans、`row` roles；來源要求三個不同維度 | 印刷旋轉、完全相同的格線外觀不是必要；維度及適用列不能消失。role 省略也不應一概當成數值遺失 |
| 分組／paired values | 泛用契約另有 `row_groups`、同一實體格文字與順序；T04 本身未宣告 section 分組或 slash pair | 此兩項不構成 T04 的停止理由，不應為了過關新增 T04 專用分組 |
| 條件、caption、來源位置 | 原生 caption ownership、既有 baseline 內容與來源 envelope；target key 及 bindings；`conditions` 作補充 | 本筆 `caption:""` 是契約規定，`conditions:[]` 本身不能證明來源條件缺失。無需模型重抄既有 caption，但仍須同版保存及核對 |

欄位定義及機械展開見 protocol.py:35 (`B/protocol.py`)、protocol.py:88 (`B/protocol.py`)；明示 row-group supplement 的保存見 protocol.py:124 (`B/protocol.py`)。caption ownership 見 policy.py:14 (`docs/research/pdf-core-caption-ownership-2026-10-17/policy.py`)。三個列維度及三級表頭的來源判準已凍結在 cases.json:18212 (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)、cases.json:18253 (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)、cases.json:24563 (`docs/fixtures/pdf-core-g1-2026-10-14/cases.json`)。本審核讀 oracle 只作必要意思的確認，沒有用它生成替代值或座標。

## 無需讀答案即可確認的衝突

證據為原始 paper09-p17-table0/content.txt (`B/live/paper09-p17-table0/content.txt`) 第 1 行；SHA-256 `eb5e332806bb3bd5ec99db608cfc5015ca346af2a790479c58d3110c48e73366`。下列座標一律是 payload 的 0-based `grid[row][col]`，JSON 根路徑為 `/targets/0/panels/0/data`。

1. **shape 沒有一致欄數。** 33 列中 32 列有 13 格，只有 `grid[1]` 有 14 格。資料與 metric 列使用欄 0…12；category 列延伸到 13。矩形檢查的失敗可直接由回應重現，與來源數值無關。
2. **category 與 metric 相差一欄。** `spans` 宣告頂層 Category 在 row 0、col 3、寬 10，範圍 `[3,13)`；其下五個 category 的起點卻是 4、6、8、10、12，寬度皆 2。第一個 metric `ME` 在 col 3 沒有 category 父格；最後 Adversarial 的範圍 `[12,14)` 超出 Category，也超出 13 欄資料。這不是合法空格或 Markdown 無法畫 colspan 的問題。
3. **四個 null 沒有已宣告 span 的解釋。** `(0,1)`、`(1,1)`、`(1,3)`、`(2,1)` 不在任何非 anchor 的 span 覆蓋範圍。Model 宣告 rowspan 3、colspan 1，沒有覆蓋 variant 欄。把 Model 擴成兩欄，或把 null 當作獨立空白格，會得到不同結構；payload 沒有授權選哪一個。
4. **列角色有省略，但不沿用舊輪碰撞結論。** 此輪 family／variant／method 已在三個不同欄 0／1／2，spans 彼此沒有重疊。body 只有六個 `row` role：rows 3／13／23 的 cols 1／2，family 無 role，後續 variant／method 多數無 role。這是角色保存不足的證據，不能誤稱「本輪 variant 和 method 同欄」。category 衝突已足以停止，不必藉角色省略擴大結論。

按**既有宣告**讀取第一個資料列，會得到以下關係；這是讀取證據，不是替代候選：

| 實體欄 | 原值 | metric | 宣告 category span 的父格 |
|---:|---|---|---|
| 3 | 15.81 | ME | 無 |
| 4 | 47.97 | SBERT | Multi Hop |
| 5 | 7.61 | ME | Multi Hop |
| 6 | 52.30 | SBERT | Temporal |
| 11 | 63.28 | ME | Single Hop |
| 12 | 71.93 | SBERT | Adversarial |

將五個 category 起點都左移一欄，會形成 ME／SBERT 成對的另一種解讀；反過來把 metric／資料右移、補一個未宣告欄，或忽略部分 spans，也能產生不同表。這些做法都須改動至少一種宣告，並引入 payload 沒有提供的優先權。不是說每一種解讀都符合來源，而是**不存在同時保留原宣告、又解決矛盾的唯一機械映射**。來源影像可以幫人選答案，但這正是本次禁止的猜移欄／讀答案修表。

## Core 或 serializer 不會替此回應補上意思

本次確認的 runtime 是 Core 2.99.0，以下 installed sources 的 SHA 與 `B/live-registration.json` 凍結值相同：

- TableCell／TableData (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/types/doc/items/table/table_data.py:20>`)，SHA-256 `4fc56f5bb7dc8da0a3162968d7f7d217b90fff0d37554d23fbd46decf8b09310`。`TableData.grid` 在 line 112 起建立矩形，依 cell offsets 填入；越界 end 使用 `min` 截至 num_rows／num_cols。它沒有判定哪一層表頭座標可信，也沒有證明 clipped 結果等於來源。因此能建立 Pydantic 物件，不能作為必要語意的通過證據。
- Markdown 多層表頭處理 (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:601>`)，SHA-256 `901247aa864647bac32864d98f9bf642aca3096c3f98c159511fd8eaccf393d1`。`_count_header_rows` 判定 leading header band；line 650 的 flattening 逐欄串接既有文字；實際 serializer (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling_core/transforms/serializer/markdown.py:819>`) 消費 `item.data.grid`。它可以降階表達**正確的**多層結構，沒有校正錯位 category 的程序。

研究接合層也不是只有 rectangular 這一項限制：protocol.py:43 (`B/protocol.py`) 檢查形狀、span 邊界、covered slots；adapter.py:38 (`docs/research/pdf-core-direct-cell-2026-10-17/adapter.py`) 再檢查 offsets、coverage 與非重疊。移除一個檢查、直接讓公開 Core 截斷或補空，不會修復表頭歸屬，也會讓真實負例靜默通過。

## 是否值得實作新表示

**本次沒有一個已成立、可通吃原六筆的簡單新表示，故不實作 replay adapter。** 四個已合法 target 可維持目前路徑；T05 的表示冗餘可另議；但任何僅刪 covered null、補 default roles 或重算 colspan 的規則，都沒有額外資訊決定 T04 的 category 應落在哪個資料欄。原六筆中保留這一個必要反例，便不能宣稱完整方法無 material 回歸。

若未來改成「每欄明示 header path、每列明示 dimensions」以減少分離 grid／span 的協調負擔，是可提出的新模型輸出假說；本筆回應並沒有那些正確明示的 paths，不能把審核者依順序配對的答案包成 saved replay。若要走此路，須另定必要來源結構、paired 格與 scope 的保存方式，做通用正負控制，再重新登錄固定比較。它不是本輪零推論審核可宣告的成功。

既有 299／300 位置診斷與 5／5 比較仍保留：postrun_review.py:72 (`B/postrun_review.py`) 清楚使用 oracle 順序把 raw 的第 3…12 欄對位；它不能證明原 header 歸屬成立。25.38→28.53 的單一數值錯誤在既有 5% 容忍內，本結論不依賴把數值標準收緊。

本次沒有改原回應、評分器、producer、oracle、serializer 或舊報告；沒有新 renderer、API、模型推論、安裝或 holdout 存取。這是已曝光 DEV 的表示／接合決策，未驗證新方法、正式模型品質或效能。
