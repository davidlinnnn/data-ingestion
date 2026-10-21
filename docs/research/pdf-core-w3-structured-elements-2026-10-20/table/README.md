# W3 table：source-only 凍結 oracle

PHASE1 只讀 W2R4 的 36 篇凍結 jobs、R2 的 LaTeX archive／source oracle／PDF text layer。沒有讀取 Docling、conversion、mapper 或其他輸出；沒有 conversion、API、模型、TeX 執行或新套件。

最終來源封存為 v2 [oracle.json](oracle.json) 與 [freeze.json](freeze.json)，程式為 [build_source_oracle.py](build_source_oracle.py)。全域 seal 前仍 source-only 的根檔解析修正保留 [oracle.v1.json](oracle.v1.json)、[freeze.v1.json](freeze.v1.json) 與原 parser；[root-resolution.json](root-resolution.json) 保存原因與雜湊。所有 36 個來源 archive SHA256 都與 R2 凍結下載記錄相符；來源檔案逐檔 SHA、PDF SHA 與 parser SHA 另存 freeze／oracle，不寫舊目錄。

## 分母與定位

252 個來源 table／獨立 grid 候選，175 個可定位 IN_SCOPE、3 個 OUT_OF_SCOPE、74 個定位 UNKNOWN。IN_SCOPE 內預先分 ordinary 60、complex 115；全來源 ordinary 92、complex 160。table float 的多個 tabular 合併為同一 table、保留各 grid；內嵌 tabular 不另冒充第二個可評表。

來源 numeric-bearing cell 候選為 9,832 個，只有 2,214 個已確定值與 row／col labels；其中 IN_SCOPE trusted 為 2,212 個。候選 cell 並非全部已可評的 numeric datapoint：沒有明確 header、標籤／macro 未解、多值組件語義不明、結構不明或定位不明者保留 UNKNOWN。不能以 trusted 子集當作完整表格分母後宣稱整表通過。15 個來源候選沒有 numeric-bearing cell，另報文字結構，不能給 0/0 PASS。

定位使用來源 caption 的 PDF text-layer 全句唯一匹配；失敗時僅用同檔案、附近來源行號的凍結 caption anchor，且結果必須唯一頁。沒有依 native 偵測框、output 字串或已知 conversion 頁碼補 gold。找不到為 UNKNOWN；只有來源已定位至選定頁外才 OUT_OF_SCOPE。跨頁環境另標 extent 未核對，避免把 caption 首頁等同所有資料頁已知。

兩篇的來源 table universe 不能宣稱完整：SICA 的 pgfplotstable generator／參數化 input 未展開；Adam 的 source oracle 是 text-layer fallback／PDF wrapper。這些 paper 不得以抽到 0 表宣稱沒有表格。Image Transformer 的兩個 root 展開內容 SHA 完全相同，屬 archive 重複副本；P13 只有選定 root 的來源 title 與 PDF 首頁唯一匹配，另一個 root 是無實際 sections 的 ACL LuaLaTeX template。因此 v2 以來源證據解除這兩篇的 root UNKNOWN，未猜測內容。其他未知 macro、column dialect、nested grid、conditional 仍逐表保留。

## Parser 方法與限制

- 以凍結 source audit root 展開實際 input／include，保留原檔與行號；只分析 document body，避免把 preamble 巨集定義誤當實際表。
- 解析 tabular、tabular*、tabularx、longtable 等 environment；balanced braces 下切 `&`／`\\`，保留 escaped ampersand、multicolumn／multirow span、caption、column spec、raw cell。
- 只將明確 booktabs midrule 前的來源 rows 視為 header，避免從 output 或數值猜表頭。沒有這項證據的 header 保留 UNKNOWN；不會把 first row 自動當 gold header。p／m／b、重複 column spec 可解析；未定義的 Y 等自訂型別不猜。
- numeric token 的原文字串、來源 cell、row label chain／column header chain 同時保留。值或標籤的 unknown macro 不抹掉後視為等價。單格多值保留整體候選與數字列表，未解析成有角色的多個 datapoint時 UNKNOWN。
- complex 事前理由：merged、明確多層表頭、多子表、單格多值、跨頁型 environment。未能看懂的結構不以 ordinary 的零錯宣稱通過。
- 合成 selfchecks 覆蓋 escape／brace alignment、multicolumn、可解 row／column labels、重複 column spec 與未知 macro 不猜測。沒有 compile LaTeX，也沒有宣稱涵蓋所有 TeX 語法。

## PHASE2 預定裁決（尚未讀輸出）

等 root 宣布全類 freeze 後，才讀 E0 的 36 篇 RAW／MAPPED。先對每一來源表確認唯一 native table、頁與 caption／內容證據，再比較偵測、row／col／header、每個值與 row／col label。漏值、錯值、錯配標籤、多生皆進分子；錯率 = 錯誤數／來源應有資料點數，可大於 100%。ordinary 必須零錯；complex 每表 <=5%。分母、對齊或關鍵結構有 UNKNOWN 就不能 PASS。沒有 numeric points 的表不給 0/0 PASS，不跨表平均。

partial oracle 仍可提供確證阻擋：ordinary 若任一 trusted point 經原圖證明出錯，標 `FAIL_WITH_PARTIAL_ORACLE`（零錯要求）；complex 只有完整可信分母或來源點數上界，且可證錯誤下界已 >5% 才能 FAIL，否則 UNKNOWN。絕不把 trusted 子集錯率冒充整表錯率。

RAW 的官方 Markdown／grid 出口與 MAPPED 的 source-cell 單次交付分開評；mapper 不改 native label、框或偵測。原生已錯的 row／col／數值不能算 mapper 修好。後續只能新增 assessment，不能看到輸出後改此凍結 oracle。

評分口徑來源：[root metrics-preregistration.md](../metrics-preregistration.md)。原始 source oracle 入口：[R2 job-index.json](../../pdf-core-w2-native-coverage-round2-2026-10-20/oracle/job-index.json)；語料：[W2R4 jobs.json](../../pdf-core-w2-native-coverage-round4-2026-10-20/jobs.json)。
