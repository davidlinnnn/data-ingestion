# 已確認阻擋索引

全部有來源頁圖或原生格位的人工證據。RAW／MAPPED在下列阻擋的裁決相同。公式／code／algorithm屬E1，表格／圖片屬E0，不能相加成同一設定的整體失敗率。P13p8的表／圖共用一個根因。全表清單另見 table-status.md。

## E1 公式 Q31：15 個最終抽查 block

|來源 ID|頁|family|改義片段／原因|
|---|---|---|---|
|F-nips_attention:formula:00005|7|NeurIPS/ICLR|來源 d_model 的 model 下標截成 mode，必要模型維度變數變成未定義的 d_mode；step_num/warmup_steps 中下劃線也被排成下標減號。兩個冪 -0.5/-1.5 及 min 的兩支仍在，但必要對象不完整。|
|F-acm_ngcf:formula:00001|2|ACM sigconf|原圖第一underbrace只標users embeddings，第二只標item embeddings。E1把users與item兩標籤同放第一underbrace下，第二卻標i_1；改變user/item兩組embedding的對象歸屬，不是字型或空白差異。|
|P-05-2602.08234v2:formula:00005|4|NeurIPS/ICLR|頁圖式(4)先定義 retrieved skills S_ret，式(5)條件亦為 S_ret；E1 將必要條件集合的下標 ret 改成 rev，失去對前述檢索集合的正確引用。其餘 a_t、pi_theta、o_<=t、d、S_g 保留；不是空白字型差異。|
|F-icml_imagetransformer:formula:00002|4|ICML|已逐列核對來源 row1 的 layernorm/q/dropout 及 row2 的 softmax：必要 numerator W_q q (M W_k)^T 被辨為 W_q (M W_k)^T，query q 乘數遺失。此錯誤位於正確 ref86，足以判阻擋；ref87 是來源外鄰式，未把其內容當成式(1)新增錯誤。另有 matrix/Insip/upsilon 等非來源污染。|
|P-05-2602.08234v2:formula:00007|5|NeurIPS/ICLR|來源結果為 S_new，且下一段確實以 SkillBank <- SkillBank union S_new 使用此結果；E1 把下標 new 改成數學字母 n c w，變成 S_ncw，與後續必要集合對象不一致。這是公式變數索引錯誤；T_val 負號與 teacher M_T、SkillBank 輸入則保留。|
|F-acm_lightgcn:formula:00012|5|ACM sigconf|E^(K) 被換成 sampling[K]，多處 E^(0) 遺失或變為 beta^(0)/A^(0)，另插入非來源數學及文字。必要矩陣與各階展開項已改變。|
|F-acm_lightgcn:formula:00014|5|ACM sigconf|來源分母是 sqrt(&#124;N_u&#124;)*sqrt(&#124;N_v&#124;)，E1 變成 sqrt(&#124;N_u&#124;*sqrt(&#124;N_v&#124;))。N_v 指數由1/2改成1/4，係數數值改變；不是字型差異。|
|F-acm_lightgcn:formula:00013|5|ACM sigconf|原等式主要一行正確，但 E1 在同一公式新增含 W_u exp(-t) t if 與多個 exp 的第二數學列；頁圖無此項或條件。新增運算與條件造成公式內容污染。|
|F-acm_lightgcn:formula:00011|5|ACM sigconf|來源第二項 (1-beta) A_tilde E^(k) 的 E 遺失，k 變成 A 的冪。矩陣乘 embedding 被改成 adjacency 的冪，必要對象及運算改變。|
|F-icml_efficientnet:formula:00002|3|ICML|來源用 bigodot（圈點，本文定義為逐stage組合），E1 變成 bigotimes（圈叉，張量積符號），必要組合算子改變。i=1...s、F_i^(L_i) 及 X 的 H_i/W_i/C_i 索引保留；大量尾端空白不另算阻擋。|
|P-07-2504.15228v2:formula:00001|3|NeurIPS/ICLR|score 變成 sore，且成本正規化分母的美元 $ 被改成 LaTeX S 命令（節號 §）。必要變數與貨幣單位改變；300 s 與其餘 min 結構保留不足以通過。|
|F-acm_lightgcn:formula:00001|2|ACM sigconf|兩列均遺失 sigma 最外層右括號；另在同一公式新增錯誤說明 e_i^(k) and e_i^(k)，頁圖原文是 e_u^(k) and e_i^(k)，將user/item對象混同。以必要對象錯誤判阻擋，非僅因雜字或格式。|
|F-cvpr_yolo:formula:00001|2|CVPR/AAAI|E1兩次將定義的IOU變成text{IO}加cup運算子，U不再是該標識的字母，而是二元集合聯集符號；這不是bold/roman的字型切換，改變公式中的變數/運算子。機率乘法與pred/truth雖保留，也不能補救此改義。|
|F-icml_efficientnet:formula:00003|3|ICML|p3右欄式2為max Accuracy及網路定義、Memory/FLOPS兩限制共四列；固定ref117原圖同一塊。E1改為Gamma/Lambda大量重複，完全遺失最佳化目標與資源不等式，確證必要內容變更。|
|F-icml_imagetransformer:formula:00003|4|ICML|p4左欄式2 layernorm/dropout/W1 ReLu(W2 q_a)。E1把ReLu寫成text{Re}\L u，LaTeX命令L是帶刪節線L字母而非ReLU的L，必要activation識別錯；尾multiplicative是無來源片段另記污染。|

## E1 literal code／prompt／log Q4：6 個來源單位

|來源 ID|頁|family|改義片段／原因|
|---|---|---|---|
|P-07-2504.15228v2:code:00010|15|NeurIPS/ICLR|這是列印執行紀錄而非可執行程式。E1 將 main agent_b8845adf 改 agent_b845adf、reasoning 子代理 5673 tokens 改 5763、總成本 $0.712 改 $0.7212，並把 t+70.4s 改 t+20.4s；改變對象、數值與時間序列。不是等價空白。|
|P-07-2504.15228v2:code:00011|16|NeurIPS/ICLR|E1 把工具 literal compare_agent_iterations 改 compare_agent_i_iterations、main token 數 106497 改 10649、archive 子代理 ID 改寫，並將 1.1.2 reasoning_agent 變成 1.1.2.1.1.1 0.0s &#124; Agent...。改工具名稱、對象與樹層級，不是字型或縮排寬度差異。|
|P-03-2603.25158v5:code:00007|23|Pilot-other/unknown|必要前提 Row falls within the explicit deletion range 被改成 Row fails within the explicit deletion range，落於範圍內的正向條件被破壞；MUST/兩條 BOTH/Do NOT 其餘仍在。+++ 與 heading 改寫另列格式/patch風險，不用它單獨證邏輯失敗。|
|P-03-2603.25158v5:code:00008|24|Pilot-other/unknown|第二個 insert_after 的 target_section 原字串 ## Important Requirements 變 # Important Requirements；改變程式化 patch 的目標文字。第一個 content ## Important Automation Guidelines 變 # Import Automation Guidelines，標題字詞也改變。不以 JSON 在論文中的換行或標點裝飾宣稱可執行性。|
|P-03-2603.25158v5:code:00009|24,25|Pilot-other/unknown|source diff 的 a/SKILL.md 與 b/SKILL.md 均在 E1 改成 a/SKIL.md 與 b/SKIL.md，patch 對象檔名改變。必要 recalc.py/ANY/MUST/Do not until success、避免 pandas 與保留 openpyxl 的主要規則仍在。E1 還產生 normparently 後又保留下一 ref 的 permanently，屬鄰段重複/拼寫風險；不靠這點證明邏輯改變。|
|P-04-2605.23904v2:code:00006|23|general arXiv (article; template uncertain)|來源 You may produce fewer if warranted 被改為 You may produce fewer if unwanted，變更何時允許減少 edits 的條件，非換行。其餘 NOT already covered、MULTIPLE、edit budget、PROTECTED/Do NOT 及 JSON operation literals 尚在。前一 prompt 尾部的 no patch warranted→unwanted 不重算本案獨立來源…|

## E1 algorithm 靜態 Q33：1 個來源單位

|來源 ID|頁|family|改義片段／原因|
|---|---|---|---|
|P-04-2605.23904v2:algorithm:00004|22|general arXiv (article; template uncertain)|Cache-membership test is replaced with equality to cache; predicates differ.; Excludes epoch e=2 that source includes; inequality boundary changed.; Else branch marker lost, rejection action duplicated and unknown if d inserted; control flow no longer equivalent.|

## E0 表格 Q13：5 張

逐點錯誤下界與分母見主報告／table/E0-results-v2.json。

|來源 ID|頁|family|類型|裁決|
|---|---|---|---|---|
|P-06-2606.14239v2:table-015|27|NeurIPS/ICLR|complex|FAIL／FAIL|
|P-11-2508.19828v5:table-001|8|ACL/EMNLP|ordinary|FAIL／FAIL|
|P-13-2601.01885v3:table-001|8|ACL/EMNLP|complex|FAIL／FAIL|
|P-13-2601.01885v3:table-003|9|ACL/EMNLP|ordinary|FAIL／FAIL|
|P-13-2601.01885v3:table-005|26|ACL/EMNLP|ordinary|FAIL／FAIL|

## E0 圖片 Q4：2 件

|來源 ID|頁|family|stage／原因|
|---|---|---|---|
|F-icml_imagetransformer:image:figure-0003|5|ICML|LAYOUT_TEXT_LABEL_PLUS_PARAGRAPH_MERGE: Figure2有1D/2D兩panel對應pictures/2及/3；全文caption在text108而無picture parent/link，並插入原body simpler depen- ... dence。mapper不改merge，兩模式仍錯。|
|P-13-2601.01885v3:image:figure-0003|8|ACL/EMNLP|LAYOUT_POSTPROCESS_OVERLAP_TABLE_PREFERENCE_THEN_TABLE_RECONSTRUCTION: p8 Figure4三個bars/綠色增益箭頭沒有nativepicture。raw picture8/10/12/13→同類overlap保13→cross-type由table11勝出；native tables/1末rows15/16含chart字。例HotpotQA Base=38.36被放row15 col5(上方Table2的BabyAI欄)，對象錯誤。|

公式完整source／active／refs／PNG SHA：formula-code/blocking-cases.json。程式runtime未執行；TeX渲染合法性未驗。未裁決或oracle錯配不列為模型blocking；6個inline-math樣本僅列F13攤平，不加入本索引的Q31改義件數。
