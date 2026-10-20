# Stage4 原生 code 評估預備設計

本設計於 Stage3 完成通知前保存；目前只執行合成字串 selfcheck，未讀取目標 code 評分或計算目標資料。實際資料計算須等 root 明確解除順序 gate。

三種輸出來源是 **native code（PDF 字元與 x 座標重建）、E0、E1**。LaTeX listing／algorithm 是共同 gold，不算第四種輸出。E0 RAW 與 MAPPED 分開列示；原生輸出不得用 E0.orig 冒充。所有來源 inventory 均保留，code 與 algorithm 分開，不將只審 21 個共同個案寫成全量 code。

## 分母與對齊

- 保留凍結 LaTeX inventory 的全部 source ID、kind、scope、頁碼；沒有可證對齊者 UNKNOWN，不大量重新人工定位，也不修改 gold。
- 使用 W3 已固定 ref／頁碼／source identity。已知四個人工 alignment error 保留 UNKNOWN；同頁或字串相似不足以證明同一區塊。
- 每來源分別報 source units、scope known、identity matched、可比較、不可比較原因。另報 native／E0／E1 的三方共同可比分母，以及原 21 人工 code 共同子集；共享 native ref 及 E1 實際呼叫去重另列。
- E1 只對實際 enriched refs 報差異；未 enrichment 是 NOT_PROCESSED，不能算漏。已處理但 source alignment 不足者仍 UNKNOWN。

## Native、E0、E1 擷取

native 從原 PDF 的 pypdfium2 字元讀取 text、raw index、page、char bbox，在既有對齊 ref 的合法區域擷取。僅用 native bbox／字元座標分行，保留每行 x_left、絕對位置、raw indices；明列幾何排序與 native 原索引順序差異。LaTeX 僅協助對齊，絕不補字、補運算子、補縮排、重排 native token。既有 refs 未覆蓋完整 source block、跨頁 extent 不足或相鄰框混入則 UNKNOWN。

PDF 有定位的空白原樣保留；沒有可證 font advance 時，縮排以 x 差與階層關係記錄，不用 source 的縮排量回推字元寬度。分欄／多框可能產生幾何排序歧義，這是 reconstruction 限制，不能變成模型錯誤。不得藉來源補齊 native 不存在的行或括號。

E0 使用既有 native document 節點內容與實際 RAW／MAPPED 交付，各別保存 active text 與 orig 的差異及 provenance；不可把 fallback 的恢復直接算為 RAW 已交付。E1 使用實際 enrichment 後 active text，保留原始輸出，不以 gold 修正。所有資料只讀保存輸出，無新 conversion、模型呼叫或套件。

## 指標

`metrics.py` 用真正的 Levenshtein 插入／刪除／替換距離，CER = distance / source characters，允許 >100%；空 gold 為 UNKNOWN。主要 CER 保留原字元及空白；另附移除空白的診斷 CER，不能替代主要指標。沒有 NFKC，①不等於1。LaTeX markup 與印刷碼本身不同時標 representation mismatch，不把其 CER 當語意錯率。

逐行以內容 edit alignment 配對，保存所有新增／刪除行與 ambiguity，不按 gold 行數直接 zip native。每行保存 source／output 原文、literal indentation、native x_left、indent hierarchy 可比狀態，以及保留字、運算子、字串及數值 token 差異。TAB 寬度及不明字元 advance 不猜。CER 和 lexical diff 是忠實度診斷，沒有自創整體通過閾值。

語意標籤沿用既有人工證據，不靠 CER 自動推導：printed log／prompt 的身分、數字或 literal 變動可影響 Q4，並不證明可執行邏輯 Q33 改變。實際執行均未進行；runtime correctness 不得宣稱。對 algorithm 的階層／運算子判斷也須分清 native 已攤平、alignment 未證與 E1 改寫。

## 產物計畫

Stage4 gate 後新增 inventory.json、per-unit.json、summary.json、report.md、native 字元／逐行 evidence；原 21 人工共同子集另列。每單位保留 source ID、來源 hash、固定 refs、native bbox extent、三源可比原因與實際 E1 processed refs。全部既有來源與舊評分維持唯讀。本準備程式不會 import 或讀目標檔案。
