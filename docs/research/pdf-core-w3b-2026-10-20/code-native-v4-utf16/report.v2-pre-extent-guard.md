# Stage4：原生 code／E0／E1 三源評估

所有運算均為既存輸出及 PDF text layer 的零推論分析。LaTeX listing／algorithm 是共同 gold；三種輸出是 native、E0、E1。E0 和 E1 的 RAW／MAPPED 分別列示。

## 分母與可比範圍

凍結 inventory 99 單位全數保留：78 code（70 IN_SCOPE／8 UNKNOWN），21 algorithm（2 IN_SCOPE／19 UNKNOWN）。67 個固定區域已擷取原 PDF 字元，65 個可估空白單位，2 個 algorithm 僅有 x 階層。

主要 literal code 字元比較 native／E0 各 13 單位，E1 為 8；三源共同可比為相同的 8 個人工 code。17 個來源身分可核不等於17個獨立字元邊界可比；共同ref／shared superset／E1鄰框混入退出主CER與逐行錯誤分母，整item值另存whole_item_diagnostic_metrics。原人工 21 個均保留，4 個已知跨頁／錯區塊 alignment error 為 UNKNOWN，不算模型漏失。其餘未 E1 enrichment 單位標 NOT_PROCESSED。固定對齊的非人工個案仍是 alignment candidate，不能把 CER 當成獨立人工語意金標。

16 個已定位 code 含未展開 LaTeX style macro、2 個已定位 algorithm 含未展開數學表示，主要 CER 不可比較；所有原文、逐行與 token 診斷仍留存。算法沒有泛刪 State／If／For 控制指令。

## 相同 8 個獨立邊界共同單位的字元診斷

| 輸出 | raw CER p50 | raw CER max | 去空白 CER p50（僅診斷） | operator sequence 相同 | number sequence 相同 |
|---|---:|---:|---:|---:|---:|
| native | 0.0367 | 0.0574 | 0.0000 | 8/8 | 8/8 |
| E0_RAW | 0.0823 | 0.1382 | 0.0000 | 8/8 | 6/8 |
| E0_MAPPED | 0.0823 | 0.1382 | 0.0000 | 8/8 | 6/8 |
| E1_RAW | 0.1654 | 0.2975 | 0.0048 | 6/8 | 4/8 |
| E1_MAPPED | 0.1654 | 0.2975 | 0.0048 | 6/8 | 4/8 |

CER 使用真正 Levenshtein，沒有通過閾值，也不是語意錯率。>1 可由大量鄰框／跨單位內容及行排列差異造成，不能把 source identity／extent 未證的字元多生直接稱為模型幻覺。每單位均保存配對行、未配對行、literal indentation、operator／number 序列；行 edit alignment 亦不能自動判定漏行。

## Native 縮排重建與限制

擷取來自原 PDF glyph bbox，而非 E0.orig；glyph raw index、緊 bbox、loose font bbox 均保存。以 loose font bbox 分行，避免 g、底線、標點因字形高度不同被拆列。單格空白優先使用定位 space bbox；本批可估的 65 區域均由近等寬字型的相鄰 x advance 推導，非 LaTeX 補空白。輸出保存空白單位、x_left、縮排量化殘差、可讀 .txt。估計不是精確原空格證明；無可證單位的 2 algorithm 用 x-level rank 的四格縮排供展示，明確不是原始空格數。

初版 tight-bbox 幾何草稿因 ascender／descender 拆列而不適用，已另存 *.v1-geometric-draft.json；最終結果重新評算，不改任何 source、E0 或 E1。這項分析器修正不涉及 conversion。

## 算法與語意界線

P04 p22 Algorithm 1 的手工已知區域另列 algorithm-operator-supplement.json：38/38 原始編號行內容可見。固定映射保留 \in→∈、\geq→≥、State／If／For 關鍵字；其他未支援宏仍列 UNKNOWN。原來源及 E0 第14行為 membership ∈，E1 改成 =；第29、33行 e≥2 改成 e>2；else 分支也被改寫。這是已有來源頁圖證實的 static Q33 邏輯變動，RAW／MAPPED 都交付了變動內容，runtime 未執行。沒有因此把另外19個未知 algorithm 算成漏失。

原 21 人工 code 的語意判定沿用既有證據：9 preserved、6 Q4 blocking、4 alignment error、2 UNKNOWN。SICA 兩個 printed log 的身分／數值改動是 Q4 忠實交付問題，不能當可執行 Q33 證據；prompt literal 與檔名／條件詞變動也與 runtime 正確性分開。沒有以 CER 自動重判語意。

全99個source均套相同extent guard：source↔ref反向索引辨認many-to-one；未有人工作獨立邊界確認的candidate不入主CER，不依source字串切target或補模型。P16 code00003整diff、P08兩code共用ref、P04 code00012共享prompt均標MANY_TO_ONE_BOUNDARY_UNRESOLVED；human原labels維持不動。

主要產物：inventory.json、per-unit.json／csv、summary.json、native-evidence/*.json／txt、selfchecks.json。300 組隨機小字串以獨立 DP 驗證 Myers bit-vector Levenshtein，全部一致。
