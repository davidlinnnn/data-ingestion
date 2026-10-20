# W3b HTML 逐條公式答案（source-only）

本答案只讀精確版本 HTML、其 MathML/alttext 與原 PDF 文字層／頁圖，未讀任何 E0/E1 評分或保存輸出。HTML 原始 bytes、URL、arXiv version 與 SHA 來自主線 html-manifest.json；HTTP200 的可下載性與可評答案分開。

HTML 顯示公式以 ltx_eqn_row 為第一層：同一行左右多個 MathML fragments 依原欄位合成一條，不把左右片段各算公式。無 HTML equation row 的 block math 則為一個候選。align/aligned/gather/eqnarray/array 的多行僅在 top-level MathML mtr 與 TeX 行數一一對應時拆。矩陣、cases、fenced array 內部行不拆；無矩陣括號且每行獨立等式的 scalar array 可拆。列規格、頂層 alignment & 屬版面資訊；保留原 row raw、完整 alttext 與 MathML 供核對。

單條比較必須是完整等式、不等式或表達式。以等號起首的續行、括號未閉合的折行及不明 mtable 拆分保留 UNKNOWN；不冒稱獨立公式。這處理避免上一回外層 block 當作一條的口徑錯誤。MathML/TeX 嚴格不能解開時不猜。共485個顯示行候選，481 formula候選、4個literal display；source頁scope304 IN_SCOPE、97 OUT、84 UNKNOWN。granularity436個完整候選、33 equality續行、8 wrapped fragments、8 unresolved split；在選定PDF頁內、非literal且完整的可比候選286。這些是來源候選分母，尚非偵測／重建結果。

頁定位只用附近正文／caption的6–10詞唯一片段，要求前後證據指向同一原PDF頁；找不到則UNKNOWN。F沿原前12頁scope、P全文；超出範圍列OUT。此方法可能因附近float、相同語句或同一段橫跨頁失準，20抽查有核原圖，不能當整體定位已全證。

抽樣在讀任何模型輸出前，以 pre-registration.json 的固定 SHA 排序從可定位顯示行抽20，原樣保留，不因結果替換。原20 source-lines全部已看原圖：19個完整公式、1個內容正確但依賴父式的clip續行；沒有發現必要符號的LaTeXML誤轉或錯頁。此1項為獨立公式邊界UNKNOWN，排比較。完整結果在audit.json，不把20條全稱獨立公式通過率。

Adam HTML只有『See pages 1-last of 0_adam_main.pdf』wrapper，ANSWER_UNAVAILABLE；不能把0 math當成功涵蓋。P04 head title Introduction雖誤導，但body有完整paper身份與正文，保留，主線source identity證據見html-manifest。其他HTML有0顯示公式僅代表該HTML無此類候選，不由此宣稱PDF沒有數學或整篇答案完整。canonical無v不足以判錯版，必要內容仍以PDF局部核對。

未開瀏覽器驗MathML排版；HTML/browser render語法保持UNKNOWN。TeX alttext與Presentation MathML互證並不保證LaTeXML無錯，後續若來源與PDF不符必須列oracle誤差，不得歸模型。selfcheck.py涵蓋matrix原子、align逐行、nested matrix不拆、array格式參數移除。
