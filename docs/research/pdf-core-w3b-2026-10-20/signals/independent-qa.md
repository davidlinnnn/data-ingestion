# Stage5 獨立 QA

只讀原 W3 formula50／code21 cohort、原人工標籤與統計 helper；沒有重評或改 cohort。

自動檢查 138 項：全數通過。

| Cohort | 原單位 | 可用人工標籤 | prediction groups | a known | a pass |
|---|---:|---:|---:|---:|---:|
| W3_FORMULA50 | 50 | 43 | 50 | 44 | 2 |
| W3_CODE21 | 21 | 15 | 20 | 8 | 0 |

50／21 source IDs 與原標籤逐一一致，沒有把外層公式 block 展開成人造逐行標籤。metadata、4 alignment error、2 UNKNOWN 均未當 correct；a primary 必須原 PDF glyph＋相容 scope。code 的 P08 共用 item 仍保留兩行、同一 prediction group，不能算兩個獨立模型。

a-only、formula c／a&c 與 primary confusion 已另寫不呼叫 helper 的計數器交叉核對。ROC 以 error 為正類，風險為1−agreement；主門檻 .95 未改。n=0 時 verified_error／精確信賴區間／AUROC 為 null（NA），不是0%。

全50公式 a availability 包含 metadata，但實際兩個 a pass 都是 eligible：SBERT formula00001 原標 preserved，SICA P07 formula00001 原標 blocking。a-only 可用人工標籤37個，TP10／FP25／FN1／TN1，verified wrong=1/2=50%，精確95%CI約[1.26%,98.74%]；不是metadata被當correct。code a-only TP2／FP6／FN0／TN0，沒有verified，故錯率NA。完整primary因缺獨立b是NO_DECISION。

SICA false pass 的原人工根因是 score 識別字變成 sore、美元 $ 被改成節號 §；必要變數與貨幣單位改變，卻被長字串的高相似度掩蓋。此案證明高字面一致不足以確保識別字／單位保義；二維從屬無法驗證是方法另外一項限制，不把本案誤歸成二維 grouping 故障。

已對 trace 正式 combined／metrics 的 W3 兩 cohort、全部8組規則逐項手算 confusion；各 ROC 另用正負類逐對比較的 AUROC 算法交叉核對，全部一致。未讀取或追隨任何 R1 外部證據。

Combined 保留207個原記錄（50＋21＋136），不是207個獨立同分布來源。R1_OLD44另有formula30／code14子view；把所有metric view相加的251不能當獨立分母。R1 additional math28全correct-only，其AUROC為NA，不能由0wrong推論錯誤辨識力佳；另外6個image-math原blocked且無可評target，仍單獨保留不可判定。

b=0有資料原因：跨兩種重建模型的相同PDF共82個候選配對，但原始頁碼交集為0；沒有可證同一原頁／區域的獨立重建。不是把matcher放寬即可取得有效b，不因無配對宣稱一致或不一致。

UTF-16更正後，R1 old44 a的TP3／FP6／FN1／TN1及a&c的TP1／FP5／FN1／TN1也已獨立核算；不是沿用修正前的0錯估計。固定規則binary ROC僅為.95 operating point加兩端點，另與continuous character ROC分開，沒有挑新門檻或宣稱機率校準。所有R1核對只用W3b內的combined記錄與metrics，未追隨外部檔案。

分母另核：17篇E1實際處理85個原native refs（formula57＋code28），不是85個source formulas。Stage3逐條可評40個source rows為9 exact／28 near／3 error；Stage5原人工formula50是整個source block，code21也是另一個人工cohort。四種分母不可混用。

限制：code native 字串採原PDF glyph＋x縮排重建，formula 使用原raw-index序列，collector口徑不同，已明列。沒有 b 不代表不一致；是 NO_DECISION。字元、運算子、數值相同仍不能證明二維數學結構或語意正確。
