# PDF-core G2：行內公式、code 與段落回填 CPU 比較

日期：2026-10-15（Asia/Taipei）。承接 [G2 計畫](docling-pdf-core-g2-pipeline-start-2026-10-14.md)與 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。**完成 17 個完整 item 的段落模型比較及 5 次真正的官方逐頁 `VlmPipeline`；目前兩路都不足以交付必含的行內公式／code。** 整頁路徑在受控公式及 code 上有局部優勢，但不能由此取代 Standard 主流程或宣告 G2 通過。

本輪是任務適配驗證。原始 provider、模型輸出、失敗、候選 Markdown 與補充結構各自保存；沒有修改 production parser、Canonical mapper、baseline 套件或既有 oracle。先前使用者接受的一般說明文字 `OpenAI`→`OpenAl` 輕微誤差不影響本輪結論；公式運算子、變數、code 邊界及重複內容另依來源判斷。

## 固定輸入與實際比較

[G1 registry](../fixtures/pdf-core-g1-2026-10-14/cases.json) 保持原 SHA256 `8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a`。主要來源為 WikiSkill p21 普通附錄段落（E14）、DGM p51 行內命令段落（E04）、SEAL p3→4 跨頁段落（E13），另用 controls p1 回歸矩陣／分數／分段式、行內平方、七行 code 及行內 `items[i] <= limit`。不是只拿答案已知的公式小框給模型。

先重用既有完整 Standard/native 文件結果及 controls 的 page-1 結果，未重跑 Standard inference。選定頁面共有 **28 個普通正文 items**；固定的 producer-text 字元規則（Unicode 數學／Greek／數學字母，或 `_ = < > ^ { }`）選中 **11 個**，另加 **6 個 FORMULA／code controls**。共 **17 candidates、19 個來源 fragments**，完整保留每個 item 的文字、charspan、前後鄰居及來源。模型不讀 oracle 文字、LaTeX 或 gold bbox。[輸入 manifest](pdf-core-g2-inline-2026-10-15/inputs/input-manifest.json)／[獨立來源核對](pdf-core-g2-inline-2026-10-15/review/source-review.md)

這個入口找到了三個目標普通段落，**不是全文件的 inline recall 證據**。若 native 文字把數學字形壓成普通字母、或 code 沒有觸發字元，仍可能漏選。SEAL 的跨頁 item 已由歷史 continuation-v3 合併；本輪保留兩個 fragment 並拼圖，不冒稱新做出跨頁發現。

| 路徑 | 本輪實際執行 | 範圍限制 |
| --- | --- | --- |
| Standard 結果 → whole-item crop → VLM → 解析／回填候選 | 17 個 3× paragraph/item crops，使用官方 engine＋Core parser component；prompt `Convert this page to docling.`，cap 1024 | 是獨立 adapter 實驗，未接成官方 enrichment 或 production pipeline；多 fragment 依 provider charspan 拼接 |
| 官方逐頁 `VlmPipeline` | 從原 PDF 直接轉 WikiSkill p21、DGM p51、SEAL p3／p4、controls p1；官方 converter／assembly，stage scale 2、cap 4096 | 是替代主轉換方法；表格、圖像、順序、全文件來源及恢復都須另驗 |

兩路使用同一個固定 `ibm-granite/granite-docling-258M` revision `982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe`（Apache-2.0），重用已驗模型快取；[固定模型卡](https://huggingface.co/ibm-granite/granite-docling-258M/blob/982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe/README.md)的 inline 能力宣告僅是候選理由。實際 Docling 2.102／Core 2.96，CPU FP32、batch 1；所有 22 次均保存 actual tensors/device、generated IDs、EOS、cap 及原始文字。沒有 GPU、remote API 或新增下載。兩路的輸入解析度、上下文與 token cap 不同，因此比較的是配置與方法，不能把差異只歸因模型。[固定執行與官方 source audit](pdf-core-g2-inline-2026-10-15/inline-primary.md)

## 來源內容與交付結果

| 案例 | 段落 crop 路徑 | 官方整頁路徑 | 判斷 |
| --- | --- | --- | --- |
| E14：七行正文、六處 `M*`／`p<0.05`／`p≥0.05` | 關鍵門檻及量詞仍在；以普通文字交付 | 同樣保留主要條件，仍是普通文字 | 沒有完整 inline LaTeX 與逐片段結構，不能算 F13 完成 |
| E04：五個 inline code token、node 6／24 與 23.3%／40.5% | 名稱及 binding 保留，以普通文字交付 | 名稱及 binding 保留，仍放在普通文字 | 保真有局部可行證據；沒有 typed inline code 是交付觀察，不另創 F14 必須 backticks／inline-group 的門檻。全文完整性依來源視覺核對，未捏造 frozen 百分比分母 |
| E13：p3→4、八行同一段落、十一處 inline math | 原始模型已重複整個 p4 片段，形成 15 處對應數學 occurrences；回填候選拒絕替換 | 兩頁合看可找回十一處意思，但保存回應重放官方兩頁 assembly 仍為兩個 items | 未通過跨頁完整段落交付；不得取第一個 block 或去重後當原模型成功 |
| Controls 行內平方與獨立公式 | 普通文字把 `x²` 攤成 `x 2`；矩陣改成直線括號、分數多出積分符號，分段式亦有結構錯誤 | 矩陣、分數、分段式局部較好；行內 `x²` 仍攤平 | 獨立公式變好不能代表行內公式已通過 |
| Controls C02 code | 六行主體保住縮排及 `<=`，語言誤標 YAML；獨立 comment 重複；inline code 遺失 `<=` 並把 `limit` 改為 `limits` | 七行註解／主體／巢狀關係及 `items[i] <= limit` 保留，code 標 Python | 整頁 C02 有局部可行證據；段落路徑 C02 不合格，不能放寬邊界或變數規則 |

上述完整原始輸出、來源差異、語義核對與負例檢查保留在 [獨立 review 說明](pdf-core-g2-inline-2026-10-15/review/output-review.md)及[機器結果](pdf-core-g2-inline-2026-10-15/review/output-review.json)。字串可讀、parser 成功及 inference exit 0 都不等於行內 LaTeX、prose binding 及 Canonical 交付通過。F13 明定行內 LaTeX；F14 的重點為內容、符號與區塊忠實，不把欠缺 inline-group 本身新增為 code 的淘汰條件。這也不是排除 Granite-Docling 所有任務；結論限定此 revision、default DocTags prompt、這兩種輸入配置與固定案例。

## 解碼、來源定位及回填的邊界

**解碼缺陷與模型內容錯誤分開。** 22 次原始 IDs 都到 EOS、未碰 token cap，模型原始 decode 有完整結尾；安裝版 engine 的 `rstrip(pad_token)` 把 token 當字元集合，22 次皆刪去 closing tag 的最後 `>`。保留原 engine／parser 結果，另做只移除 terminal EOS/PAD IDs 的 token-aware decode＋官方 Core parser 候選，沒有改套件、補答案或重跑模型。修復這個結尾問題並不消除上表的內容錯誤。[執行檢查](pdf-core-g2-inline-2026-10-15/vlm/verification.json)

官方 Core parser 對這個尾端缺陷仍可讀取，22 組 decoder 對照各自產生相同的 parsed document。0／17 回填是實驗 adapter 的 strict wrapper 規則拒絕，不是官方 parser 全部失敗；token-aware 候選也沒有因此改善模型語義。

**官方輸出須有來源映射。** isolated physical p21／51／3／4 在 parser 中會成 page 1，以 pipeline 基礎影像像素為 page size。另存原 physical page、PDF 尺寸、影像尺寸與轉換矩陣；段落拼圖則保留每個來源 fragment。這些 sidecars 僅映射模型所產生的區域，不把推論中的 token box 說成來源測量值，也不覆寫官方 raw document。44 份兩種 decoder 的 parsed outputs 都有對應 sidecar。[幾何核對](pdf-core-g2-inline-2026-10-15/vlm/mapped-geometry-check.json)

SEAL 的第一個模型 block 雖然含兩頁全文，它的預測 box 卻只落在 p3 片段。矩陣計算正確仍會把這個 block 映成 p3，不能據此宣稱文字的語義位置正確；跨 fragment 的語義對齊仍未完成。

另外把 SEAL p3／p4 的 exact 保存回應與 pipeline 基礎影像送進真正的 `VlmPipeline._turn_dt_into_doc`，分別重放原 engine 與 token-aware 版本，沒有新 inference。兩者皆產生 36 個 text items、parser pages 1／2；段尾 `questions and` 與次頁 `associated answers` 仍是不同 items，沒有多頁 provenance 的 text item。這是官方 assembly 行為的證據，**不是新跑一次完整雙頁 pipeline**。[重放檢查](pdf-core-g2-inline-2026-10-15/vlm/assembly-replay/verification.json)

回填實驗使用 Docling Markdown text-serializer extension point，對 exact document／item／text／neighbor hashes 和完整 item charspan 產生獨立候選 Markdown。原 provider 不變，也不採 token 文字模糊搜尋對齊。

| 回填方法 | 結構上套用 | 保留原文／未套用 |
| --- | ---: | ---: |
| 原 engine decode | 0 | 17（strict wrapper 檢查拒絕） |
| Token-aware decoder candidate | 9 | 8 |

8 筆未套用包括：3 個 SEAL items 產生多個 root blocks（含 E13）、1 筆 comment 新增五詞重複、1 筆 inline code 多 block，以及 3 個藏於 picture 下、stock Markdown 不獨立輸出的 formula children。未增加 picture-parent rewrite。多 block 全部留存，不擅取其中一塊。規則亦擋住 stale hash、unknown／duplicate ref、不完整 replacement 及 scope 外內容變更；小型負例與 whole-document serialization 核對均通過。[回填方法與限制](pdf-core-g2-inline-2026-10-15/reinsertion/README.md)／[self-check](pdf-core-g2-inline-2026-10-15/reinsertion/selfcheck.json)／[verification](pdf-core-g2-inline-2026-10-15/reinsertion/verification.json)

**9 筆套用僅證明結構來源關聯。** E14 缺必要 LaTeX；錯標 YAML 或平方攤平也不會被 hash 檢查判出。獨立 review 更發現已套用的相鄰 `wikiskill-texts-362` 遺失段首「Statistical significance testing…1,000 iterations」，直接從 `for each benchmark.` 開始。這是替換範圍內的模型遺漏；scope 外不變不能掩蓋它。五詞重複規則是有界防護，不能證明數學正確、沒有漏字或所有語義重複。這些候選輸出沒有通過 Canonical Acceptance，也沒有寫入正式 Canonical content。

獨立 checker 的 17 個 in-memory tamper controls 能拒絕錯誤門檻／prime／arrow／subscript、漏字／重複、code 邊界／縮排及來源／範圍竄改；22 組 raw output、44 個 geometry sidecars 與完整外圍 Markdown 也已核對。這些固定來源的驗證期檢查不是通用 runtime 語義判定器，不能用來宣稱每次 ingest 都可自動知道答案是否正確。

## 執行成本與後續決策

17 個 paragraph jobs 各 **5.04–9.86 秒／2.37–3.32 GiB** sampled process-tree RSS；5 個官方 page jobs 各 **14.65–31.44 秒／3.10–3.43 GiB**。合計 child wall **216.87 秒**，包含每個 fresh child 的 model load／觀察／退出，未含 shared-lock 等候。這不是整份文件 latency、warm serving 吞吐或高頻 SLO。所有 children 在 180 秒、6 GiB sampled RSS、啟動前 available ≥8 GiB 的守門下完成；owned process groups 無殘留。[paragraph timings](pdf-core-g2-inline-2026-10-15/vlm/paragraph/summary.json)／[page timings](pdf-core-g2-inline-2026-10-15/vlm/page/summary.json)

建議維持 Standard 為目前主路徑，不將這組 default Granite paragraph／page 設定升為行內內容的最終方案。下一個有價值的比較是沿用相同完整段落及逐頁來源，評估較強 VLM 對 **inline LaTeX、code 保真、完整 prose、跨頁去重與來源回填** 的輸出契約；暫用已允許的 hosted candidate 可供比較，公司 self-hosted 候選仍須獨立驗證。不能由 model card 或較強模型名稱推定成功。專用 formula prompt 不能直接替代保留整段 prose 的要求。

G2 仍保留既有 heading、order、繁中 OCR、delivery 及其他未驗來源缺口；完成本輪不代表全部模型、G2、G3 整合或 G4 效能已通過。沒有增加模型笛卡兒積或讓所有文件都走 VLM。高頻 ingestion 的最終 routing、GPU／vLLM serving、批次／併發及公司模型仍待相應環境驗證。

本輪 [整體驗證](pdf-core-g2-inline-2026-10-15/validation.json)／[payload manifest](pdf-core-g2-inline-2026-10-15/artifacts.json)核對新證據、未變動 G1 與前七輪 871 個 payload、local links 及 credential pattern。完整證據留在本機；GitHub #84 僅回寫[結論摘要](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6191642892)與正文指標。[逐字 readback 紀錄](pdf-core-g2-inline-2026-10-15/ticket-update.json)確認 44 個 feature rows 不變、issue 保持 OPEN。
