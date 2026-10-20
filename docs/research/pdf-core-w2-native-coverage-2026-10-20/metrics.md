# W2 native coverage metrics — v1（全量前凍結）

範圍：born-digital 論文；Set P 全頁只登錄，Set F 每篇前 min(12, PDF頁數)頁。此回合只跑 frozen smoke jobs 的兩篇各一頁；跨頁指標在 smoke 中為 NOT_EXERCISED。沒有整體通過率或任意可接受比例。

## 獨立來源與 oracle

1. PDF SHA256、固定版本 URL、頁範圍及版型依據在任何 Docling conversion 前凍結。保留 pypdfium2 字流、字元位置、行 bbox（PDF bottom-left 座標），**不把幾何排序冒充原始字流**。
2. 正文段落、必要清單、章節、caption、footnote、furniture 的來源區域獨立於 Docling 輸出標註。字流 oracle 僅用於經 LaTeX anchor 核對的正文連續區域。樣本核對不能證明整篇／整個 family 可靠。
3. 浮動圖表、公式、演算法、reference、註腳、頁首頁尾、頁碼、欄／頁邊界殘句、來源與 PDF 版本不一致區域分別登錄，不能默默丟出分母。正文品質之外的圖表數學重建不在本研究範圍；與正文邊界、漏必要文字仍在範圍。
4. source 可取得時以相同 PDF 版本的 LaTeX `\\input`／`\\include` 展開後正文先後、`\\section`／`\\subsection` 為替代順序及層級依據，移除 float/footnote 的插入順序影響；無法展開或 macro/conditional 不確定標 UNKNOWN，人工看 PDF，不能推定來源順序。
5. 全量時每一段可靠性需有區域記錄。未確認區域報 ORACLE_UNRESOLVED／分母數量，不用它判 extraction 錯序或宣稱無缺陷。

## 字句對齊

正文以來源段落為單位切句，記錄 sentence ID、原文、page、column(L/R/S/full)、paragraph ID、char index／bbox及可靠性。保留否定、大小寫、標點、數值、正負號、單位、對象；只正規化 NFC、PDF 字型連字、空白與來源確定的斷行連字。不得刪掉數字／標點或以模糊比對直接宣布等義。

以正規化後的完整句子對齊輸出 native body item 順序，保留每次出現的位置及 item/provenance。跨 item 接續可合併比對，但必須保留映射及區分錯誤段落邊界。重複來源句子以 occurrence／上下文消歧，未消歧不當成漏重。字面不匹配屬候選差異，不等同語意缺陷；短句、公式、引用、縮寫及不完整句邊界人工確認。

## 指標與分母

| 指標 | 定義／必存 evidence |
|---|---|
| `missing_candidates` | 可靠正文句在 body stream 零次完整匹配；保留原句及最接近 output/provenance，人工核對是改義、字形差異或 oracle/切句失準。出現在 caption/furniture 而不在正文仍需核對歸屬。 |
| `duplicate_candidates` | 輸出 occurrence 數超過來源 occurrence 數；保留每次位置。來源本身重述或相同短句不算自動重複缺陷。 |
| `adjacent_inversions` | 原參考序列相鄰且兩句均唯一對齊時，前句 output 位置大於後句。分母是這種可判斷相鄰 pair；不跨未對齊句補 pair。另報每個 pair 的 page/column。 |
| `right_into_left` | 同頁已對齊左欄 paragraph 還有後繼左欄 paragraph 時，完整右欄 paragraph 出現在兩者之間；每個被插入的右欄 paragraph 算一次，附 L-before / R / L-after 三元組。缺句或非唯一對齊造成的未知段落另報，不能算零。 |
| `mixed_column_items` | 同一輸出正文段落 item 含同頁 L 與 R 的已對齊句，逐 item 計數；跨欄正確 continuation 亦會觸發候選，依來源段落 ID 判斷是否錯接。不能把所有跨欄延續都判錯。 |
| `furniture_in_body` | 來源 header/footer/page-number/stamp 文字出現在正文 item；以獨立區域文字／bbox及角色核對，短頁碼不能全文件 substring 比對。 |
| `footnote_caption_separation` | 每個來源 footnote/caption 是否獨立於 body、角色是否正確、與所屬圖表／註腳 anchor 是否可區分；漏失、正文混入及錯配分別列出，未檢查報 UNKNOWN。 |
| `heading_text_level` | 來源章節（LaTeX section=1/subsection=2，或明確編號）與輸出逐項對齊，漏標、角色錯、層級錯、父層錯分開；無明確來源層級者 UNKNOWN。 |
| `runtime` | initialization wall/CPU 單列；每頁 conversion wall、user+system CPU秒、每頁期間抽樣 process-tree peak RSS、保存時間；文檔 wall/CPU 不與逐頁重疊階段時間直接相加。batch1與CPU4不代表wall乘4就是CPU。 |

Smoke 每篇只取一頁，所以 conversion wall/CPU 即該頁數據。全量要以逐頁生命週期 observer 記錄，或明確報平均 wall/page 及 page-stage timings；不能把整篇平均偽裝成實測逐頁 latency。RSS 用單worker process tree 每0.1秒採樣，平台 RSS 為物理 resident bytes，不是機器總記憶體；不能把兩篇 RSS 相加當單worker容量。

## Q4 判定與呈現

每頁、每篇均列 `meaning_changing_omission`、`meaning_changing_duplication`、`meaning_changing_order_or_join`、`furniture_or_list_scope_error`，值只能為 **YES / NO / UNKNOWN**，附 sentence/item ID及原文／輸出 evidence。YES 即該必要內容阻擋；NO 要有該範圍完整人工核對，不能只因自動計數零。未核對或 oracle unresolved 為 UNKNOWN。空白、換行、字型與正確跨欄／跨頁 continuation 不算缺陷。否定、條件、數值、單位、對象、必要內容遺漏／重複、段落串錯、頁首頁尾混入、造成誤讀的清單從屬均阻擋。

本指標組是定位及核對工具，並非通用語意判定器。全量前若需改 metric，必須新版本並保存舊定義／hash，不能看過全量輸出後調門檻。
