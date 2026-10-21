# W3 執行與交付口徑

本回合開始於 2026-10-20 08:15:05 UTC，總上限至 11:15:05 UTC；新 conversion 最晚 11:00:05 UTC 停止，保留彙整時間。36 篇／715 頁與 W2 相同，未開 holdout。

## 凍結與 E0 重用

先由三個獨立 source-only builder 建立 formula/code、table、image oracle。全部在讀 E0／執行 E1 前封存：`oracle-freeze.json`，時間 08:26:05 UTC，共24檔。表格 v1/v2 的根檔修正只依 source archive 重複 body SHA 和 PDF 題名，在全域封存前完成；舊版留存。後續不更改 gold、頁定位、scope 或複雜度。

原始來源 archive 與 PDF 的 36 份 SHA 全核對，`source-manifest.json`。Adam archive 是 PDF wrapper，沒有實際數學／code／表／圖 LaTeX，不假造其結構 oracle。source-file 字串的 hash 可能是 UTF-8 解碼後文字 hash；archive hash 才是來源 byte hash。

E0 為 PyPdfium、Heron、separators=True、bookmark-only，所有 enrichment 關閉。36 份選定設定的 JSON／Markdown 重用 W2 R3/V3_B 已保存輸出，`E0-inputs.json` 記錄每份 SHA；必要的 raw-layout、PDF 幾何與歷史資源均讀對應原 conversion，沒有重跑 E0。loader 曾 clamp 的 bbox 不當作模型行為改善。

E0 的歷史原 conversion 是30篇影像開啟、6篇影像關閉的成功輸出；W2 的兩篇影像開關等價控制支持文字／label／結構／讀序／Markdown 重用，不能把歷史資源當作全36新跑影像關閉的對照 benchmark。`E0-resources.json` 保留原設定與來源，新的 E0 conversion CPU 為0；讀檔／解析／評分仍有 CPU 開銷。

## E1 與成本分支

E1 只將 do_formula_enrichment、do_code_enrichment 設為 True，其他設定與研究用影像關閉的 E0 一致；使用既有 CodeFormulaV2 `ecedbe111d15c2dc60bfd4a823cbe80127b58af4`、CPU4，不改生成上限／數值參數，不下載或呼叫外部 API。所有 picture description、classification、chart enrichment 仍關閉。標準模型內部需要 PDF crop，影像輸出開關 False 不代表禁止內部渲染。

CRNN 5頁與 SICA 18頁先登錄作完整成本試跑。兩篇均成功；CRNN 沒有 native formula/code items，實際沒有 enrichment。SICA 2formula＋4code，兩批 enrichment 共400.32秒 wall、1526.86秒 CPU。這是較窄的成本樣本，不代表各 family 的推論成本分布。

用兩批的 orig 字元長度／batch overhead 作成本外推，加歷史 baseline conversion wall：全量約250分鐘，超過120分鐘，依指示改為已預登錄分層抽樣。來源樣本為每family最多40條獨立公式，共232條；code／algorithm全部99單位。所有 source IDs 在讀 E0 前已登錄；不能以定位不到、偵測失敗或困難案例替換成其他單位。

參考 `cost-decision.json`、`formula-code/sample-plan.json`。全量估計是成本模型，不是實測全量或準度。模型只有兩批，生成長度、padding、圖片和文字複雜度會影響成本，因此同時監督實際耗時與硬期限。

抽樣將 source IDs 對應到既有 E0 item refs，已知來源頁的 eligible refs 為143formula＋68code，共211；含已完成pilot的5個ref，其餘206ref分布25篇新 conversion。所有331來源單位仍有紀錄；UNKNOWN、偵測不到、非formula/code角色的項目保持原狀，不冒稱 E1 已重建。未知 gold 頁的 exploratory output 對齊不進已定位偵測分母。抽樣 gate 只控制推論範圍，不調模型或數值、不修正輸出；每個 ref 另核對原 label／orig SHA，避免指到別個元素。selected-item-map.json (`formula-code/selected-item-map.json`)。

**依預估超時提前停止。** 10:00:08 UTC 以22個完成batch更新非負成本外推：當時剩89formula＋42code refs，僅enrichment需77.0–89.4分鐘，已大於剩餘74.95分鐘的整個任務預算，還未包含conversion與彙整。這是實測更新後的外推而非精確保證；兩種模型都超時，因此按使用者指示停止新增conversion，沒有改抽樣、生成參數或另挑容易文件。`budget-stop.json`。

停止決策後P05已完成、P08為當時活動child；暫停supervisor以避免啟動下一篇，再於P08已完成後中止parent。P08保存success／JSON／Markdown／batch／CPU與wall，但parent尚未把該篇RSS samples寫入；手動monitor開始時child已結束，0新sample不等於0RSS。最後暫停區間的連續守門覆蓋與該篇完整peakRSS均UNKNOWN，不宣稱全17篇每一時刻都有完整RSS證據。其餘14篇v2與2篇pilot的已保存supervision照實保留。P08四份effective-options等artifact依原supervisor同規則從當時run root補拷，有來源SHA與assembly註記：budget-stop-supervision.json (`runs/E1_sampled_v2/budget-stop-supervision.json`)；原null-job／0sample紀錄另留v1。

最終成功17篇（pilot2＋sampled15），其餘10個planned sampled job未啟動；這是E1抽樣未完成，絕非36篇E1全量。211個gate refs中84已推論、127未推論；pilot另外1個非樣本code ref另列，實際85 refs。331個預登錄source units的處理／時間停止／gold未知／無eligible對齊另逐項保存，不能把這些未處理都算成模型漏抽。

E1 成功結果以 conversion.json success 最後寫入作可讀標記。抽樣清單以外未處理的元素，不當作 E1 模型錯誤。pilot內不在樣本的額外項目另外揭露，不混充 source-stratified 分母。

## Harness 更正與審查更正

第一版抽樣 gate 的 callback 名稱與官方 `element=` keyword 呼叫不相容。5篇在enrichment前回傳pipeline failure、另1篇因停止harness而中斷，全部沒有 enrichment active/batch檔，模型推論0。保留原 driver、seal、logs、document和進度，不把它們當模型品質失敗或抹掉成本。

修正版本只改 callback 介面，加入 keyword 呼叫、選中／跳過ref、orig變動拒絕的自檢；原 source名單／refs／模型／gold不變。v2 為一次明示的人工 harness repair/restart，沒有自動重試。`harness-repair.json`、`selector-selfcheck.json`、`selection-freeze-v2.json`。資源彙總包含失敗／中斷開銷，不能宣稱每篇只有一次 conversion attempt。

原 scoring v1 將50個人工樣本分為20formula/15code/15algorithm，與使用者要求不符；保留原檔，另封存修正為**50個公式來源單位**，只從已知gold頁、原232樣本、實際有E1formula推論的NEAR/ERROR中按固定hash選取。近／錯各25，不足跨類補，總不足就全收並報不足；不以exact、code或algorithm湊數。公式評分主責在讀 E1 document 內容前封存修正；主線此前已看過 pilot 的兩個 formula batch 輸出，因此這項協議修正不能稱全團隊對E1盲化。修正源於使用者明訂的50個公式，沿用既定seed/hash，不按已知錯誤挑案例。code／algorithm另做逐行比較和代表裁定。audit-protocol-amendment.json (`formula-code/audit-protocol-amendment.json`)。

分析器另有 v2 更正：v1 未完全去除字型 wrapper／hspace 尺寸，而且按 texts 陣列而非正文樹序組合已固定的 refs；code 的 Unicode NFKC 可能掩蓋 literal 改字。v2 以 brace-aware 方法只移除格式 wrapper 並保留 argument、依 body children／picture children／caption refs 去重取得實際順序，code literal 不做 Unicode 正規化。自檢保證 `<`／`<=`、`x_i`／`x_j`、美元／section 符號與 literal `①`／`1` 不被合併。未連到正文樹的項目保留 stable append 與位置未知標記，不藉 oracle 重排。E0 refs、抽樣 gate、gold、source scope 均不重配；v1程式與結果另存，50案按v2近／錯重新選擇，變exact的已審個案只作補充。analysis-v2-amendment.json (`formula-code/analysis-v2-amendment.json`)。

其中25份衍生審查packet因v2 scalar更新而重新產生，原review payload及其舊packet SHA留存，統合case另列current_packet_sha256／refresh note；不假稱舊SHA仍等於現行packet。來源頁圖／source及active model evidence未變，最終50個頁圖SHA及固定ID集合均核對通過。此處封存的是最終可重現的分析快照，不宣稱初版評分器完全無錯。

封存公式共有387個 outer environment／display block，並非387條獨立等式；內部 rows 已保存，衍生 TeX segment inventory 不修改來源分母。多列 align 既可能是單式跨行，也可能是多式，不能全自動區分。因此每family最多40及人工50，實際是 block單位：人工核對所選block全部可見列，但不能宣稱完全達成使用者逐條獨立公式的抽樣與偵測口徑。此限制必須隨結果揭露。完整正文行內數學攤平率也不能從4571個LaTeX行內span推得；另做固定hash小樣本頁圖核對，不提升原未定位gold為已知。

## RAW 與 MAPPED

RAW 同時保存官方 native active text／表格與官方 Markdown 出口。MAPPED 套 W2 三規則：text 空而 orig 非空時回退並標角色不確定；picture children 原生字獨立交付，與 C supplement 分開；native table cells 一次交付、保留span。兩者分子／分母／UNKNOWN都另報，偵測label/bbox本身不受mapper改變。

公式／code的 E1 非空 model text 不能再用 orig 聯集救成正確。原字串存在於 JSON、官方 Markdown 可取回、mapper 可交付與重建意義正確是四種不同證據。numeric 值仍在字串中不代表有正確 row/column label 關係；picture子文字不是圖片理解或C圖片supplement。

## 裁決邊界

表格 ordinary 必須零錯，complex逐表錯率<=5%，不跨表平均；分母無法完整解析不能PASS。ordinary若已確認一個必要資料點錯可FAIL_WITH_PARTIAL_ORACLE，complex則必須有完整分母或可證上界才能以錯誤下界判定。關鍵比較未評。

公式近／錯的自動分類不是 Q31 改義裁決；逐圖確認 math meaning 並排除 source→output alignment error。code 的逐行／字串／運算子變動只有能證邏輯改變才列Q33阻擋。圖的source-container候選偵測、caption連結、raster object bbox containment與實際可見像素裁失分開，vector/clip/未知物件不能由bbox統計冒稱正確。

未另造總體通過率。原始與mapper模式的精確範圍、人工樣本與UNKNOWN必須一起解讀，不能由一個高候選匹配率斷言某family全文可靠。所有產物僅在W3；不更動正式Profile或pipeline、不commit/push/GitHub留言。
