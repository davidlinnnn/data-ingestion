# 表格表示契約審核與離線驗證

2026-10-17。依 [下一步計畫](next-step.md) 的 60 分鐘、零新推論界線執行。**保留一條小型 padding 表示候選；停止本輪 B 的追加模型推論。** T05 已能以同一原始回應完整接合，T04 的表頭歸屬仍矛盾，故完整 B／第三段尚未通過。

## 必要意思與表示

| 項目 | 必須保留 | 本次審核判斷 |
|---|---|---|
| 數值與欄位 | 數值文字、欄位順序、父子表頭及條件歸屬 | 必要；T04 的錯位不能以 minor 或格式簡化抵銷 |
| 列維度 | Category／model／variant／method 的文字及適用列 | 必要；已有命名欄與明示範圍時，不再要求猜補 body `row_header` flags |
| 分組 | label、聚合條件、明示 row-group 起迄 | 必要；scope 保存在同版 supplement，實際 Markdown label 另核對，不能只從前一 section 延伸 |
| Paired values | 共同 cell identity、Proposed／Accepted 順序及數值 | 必要；沿用 ≤5% 與全部關鍵比較標準，不新增數值零錯門檻 |
| 合併格 | 已宣告的 anchors／spans 與對應欄位 | 必要；不能猜未宣告的 section 全寬 span。精確複製來源 header 的換行數不作新增門檻 |
| Covered padding | 已宣告 span 內沒有獨立內容的 slots | 原 v1 只接受 null；可另立規則接受精確空字串 padding。span 外真空白格仍保留，非空內容不可吞掉 |
| Caption／來源 | 原 caption ownership、來源 envelope、非目標內容及可讀回關係 | 必要；沿用 native baseline，保留 raw provider 與表示方法版本。沒有新增假的 per-cell bbox |

獨立來源／SDK 審核見 [T04](contract-audit-t04.md)與 [T05](contract-audit-t05.md)。本次使用已凍結的本機 Core 2.99.0 原始碼；沒有以未核實的新版本功能作假設。

## 唯一新增的通用規則

[grid-spans-v2-padding 方法](B-padding/method.py)只在**明示 span 的非 anchor 覆蓋位置**，把精確 `""` 視為無內容 padding，轉成既有 strict 格式的 null。模型宣告的 span 是這份新傳輸契約的結構權威；這不是證明 span 符合來源真相，也不是修復原 v1 回應的宣稱。

其餘內容、座標、spans、roles、group endpoints、數字及欄位順序均不改。Covered slot 的 `" "`、`"0"`、dash、unknown 或 role 仍拒絕；不矩形、越界、重疊、無主 null、未知欄位及 target inventory 不完整仍拒絕。Section 旁有非空值時會原樣保存，不推成全寬合併格。原 raw 另存 `transport_provider`，canonical supplement 保存 normalized compact 及 `covered_padding` 座標清單。

接合沿用原公開 Core／來源 mapper／已驗 literal serializer，沒有新 renderer、SDK patch、逐表 route 或答案回填。此方法是在曝光 DEV 後形成，不能當成盲測或一般化證據。

## 同六筆保存回應的 replay

| 主案例 | 新方法的離線交付 | 原六次模型比較的狀態 |
|---|---|---|
| T01 | Typed／實際 Markdown 6／6，關鍵比較 3／3；native caption 與非目標來源保持 | 原通過保留 |
| T02 | Typed／實際 Markdown 84／84，關鍵比較 8／8；六 panels 與同頁 collateral 保存 | 原通過保留 |
| T04 | 仍拒絕：header row 14 格而資料 13 格；category spans 與 metric／父 span 錯位且末端越界 | 原失敗保留；同頁合法 collateral 不部分採用 |
| T05 | Typed／實際 Markdown 80／80，比較 7／7、pair 結構 20／20；label 與 scope 核對通過，來源 caption 一次 | 原 v1 失敗保留；新方法只增加離線交付證據 |

六個 target 中五個可接合，四頁中三頁完整保存。主分母仍為 470 數值／23 比較；可交付的主案例涵蓋 170 個正確數值與 18 個比較，但**這不是 170／470 的模型準確率**，也不把 collateral 加入主分母。T05 沒有補 section colspan 或 body row flags，沒有改任何數值。表格展示及更細結構分工維持原需求。

[完整 replay 報告](B-padding/results.json)、[實際 T05 Markdown](B-padding/replay/wikiskill-p13/document.md)、[Core](B-padding/replay/wikiskill-p13/document.json)及 [bindings／supplements](B-padding/replay/wikiskill-p13/bindings.json)均保存。三頁均通過 JSON reload、非目標內容／來源 signature 保持；[第二個 Python process 讀回](B-padding/fresh-process-reload.json)亦一致。這不代表 worker checkpoint 或搬移 bundle／GPU 恢復已驗收。

[45 個測試全部通過](B-padding/test-results.json)：新 padding 控制 10 個、既有 evaluator 13 個、runner 22 個。涵蓋 null／empty 等價、raw／baseline 不變、冪等、真空白／literal／precision、多維表頭、分組旁非空值、完整頁面及負例拒絕。測試 log 與 [獨立複核](B-padding/review.md)另存。

首次離線 verifier 因 T02 的 oracle-caption 全字串等值 assert 停止：native baseline 已把 `B_m` 渲染為 `B m`。該次產物與程式保留在 `B-padding/precheck-caption-literal-assert/`。正式檢查改為核對 native caption 原樣、原次數保存，並另外保留 source-caption literal mismatch 診斷；沒有對 `B_m` 寫特例修補，也沒有因此宣稱完整公式／code 能力已成立。T05 原 caption 全字串一致，且視覺核對既有 crop 的欄位、兩組 aggregation labels、pairs 與單位未見 material 差異。

## 去留與接續

T04 不只是 padding 表示問題：五組 category 的起點比 ME／SBERT 資料欄晚一欄，最後一組跨出父 Category 與資料欄界；另有未由 spans 解釋的 null。照原宣告消費會錯綁，左移 category、右移資料或擴 Model span 都須引入未宣告的選擇。公開 Core 的裁切或填空不能證明哪個版本忠實。故不再追加同一 B producer 的 prompt／模型重試，也不為了過 DEV 強補表格。

保留 Standard＋Heron／RapidOCR／TableFormer 基線及 T01／T02／T05 的有界元件證據。新的 padding 方法可供後續接合研究使用，但不足以選為正式複雜表配置。若之後另選「明示每欄 header path／每列 dimensions」或更換具名 table 模型，須以新假說、來源結構保存控制與固定比較重新登錄；本次不啟動。

依原三段計畫，下一個可獨立推進的工作是 **A 的公式／code ownership 與必要漏項的離線 gate**，接續 C 的同版 image keys／座標與來源接合。其他 component 不因 B 的局部改善被視為穩定。完整方法仍有 material 缺口，不進付費整份整合 run；跨頁表格接點亦未解除阻擋。

新 API／模型載入／holdout 讀取均為 0；沒有新模型品質、成本、latency、吞吐、Qwen3 或 vLLM 的主張。原 B 輸出、grader v2、frozen producer、歷史結果及 oracle 均保持不變；完整性與時間界線見 [核對紀錄](contract-audit-verification.json)。
