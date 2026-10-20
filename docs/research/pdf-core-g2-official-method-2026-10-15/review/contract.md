# G2 official full-page method：來源評分契約

在新推論前凍結；來源限定既有已曝光四份文件、8頁、41個 selected logical units（36既有＋5未執行）。這不是全頁完整 inventory 或獨立 validation。來源 expected、定位與hash見 [contract.json](contract.json)，不傳給模型。

## 分開評估的三層

- 內容：全文、名稱、code字面值／縮排、公式符號與關聯保真。
- 產品交付：F13可用LaTeX與原prose位置、原E13單一跨頁段落／11math／雙頁來源；F14inlinecode保真但不另要求自訂typed JSON。官方raw、parsed doc、stock Markdown分開，parser遺失不能當model讀錯。
- 實驗契約：上一輪native block／typedsegment／逐itemtarget-only規則只屬該自訂路徑；原25/5/6原封保留。

## 比較公平性

官方全頁可把controls comment＋body組成單一codeblock；SEAL34需把誤合併的prose與Algorithm1標題分離；公式3/4可合成aligned display；不強迫複製舊native錯誤。SEAL standalone SE不新增math門檻，E13沿用原11處。新增5項已對照SEAL p4原圖凍結完整要求。全頁其他真實內容不當作contextleak或加分，unsupported additions與重複另記。

## 停止與限制

單次固定配置，不重試／調prompt／猜修答案；有實質內容錯誤、必要F13／來源／跨頁交付缺口或四個正例退化，即不整體採用。官方parser若需大量客製才可交付，就記錄能力限制，停止此路。原最多3配置預算不變；holdout、本機GPU／公司Qwen3與高頻負載皆未驗。
