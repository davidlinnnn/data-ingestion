# 整頁 discovery：第一步離線輸入與接點結果

2026-10-17。**第一步離線 gate 完成；八頁偵測推論尚未開始。** 沒有新模型、API、重建、下載、安裝或 holdout 讀取；沒有修改既有封存證據、Docling SDK 或 production。

新假說是：保留 cached StandardPdfPipeline S0 主幹，以整頁影像偵測補充原生未 emit 及跨圖／正文邊界的 math/code 候選，再評估是否值得選擇性重建。這是額外提出的 discovery／routing 方法，不是已證明的官方 pipeline 能力。既有 A/B/C 與 retro 已完成本輪收斂，仍沒有完整合格配置。

## 固定輸入與成本邊界

- 四份既有來源、八個 physical pages：controls 1、DGM 51、SEAL 2–4、WikiSkill 20–22。沿用 S0 與原來源 hashes，沒有新增案例或重新執行 Standard。
- 以已安裝 PDFium 直接從原 PDF render 完整頁，scale 2／144 dpi。逐頁核對原生 page size、影像尺寸及重新 render 的實際 pixels；概覽亦已視覺檢查沒有裁去頁面。
- 保留 201 個原生 provenance scopes。這些是原 196 個 inventory rows 的頁面／fragment 投影，與 44 source groups、41 selected units、27 negatives 分開；它們不是 jobs、模型輸出或準確率。
- Detector 的輸入只含固定 prompt 與整頁圖；不附 native 文字、人工 bbox、來源答案或漏項清單。原生 scopes 只供輸出後關聯及保留，不進 detector request。
- 輸出只接受候選框、math/code/mixed 類型、body/caption/table/picture/unknown 的責任提示，以及明示 incomplete／issues；不轉錄全文。每頁最多 128 個框，超限／截斷不得丟掉部分框改判成功。
- 規劃沿用既有暫用 API 候選 gpt-6-luna、low reasoning、high image detail；最多 8 次、concurrency 1、retry 0，每次 180 秒、全輪 1,800 秒，completion cap 每次 8,192／總共 65,536 tokens。暫留 input 每頁 10,000／總共 80,000 的研究 reservation；不是已驗證 tokenizer 或可保證的 provider 硬上限，實際超支須停止後續呼叫。
- **本輪 reconstruction budget 是 0。** 真實 detector regions、漏失與成本評讀完成後，才能固定下一輪重建預算。

精確 prompt、頁面與方法 hashes、來源 paths 及成本邊界在 [registration.json](registration.json)。它是離線輸入 freeze，**不是 live-ready 登記**；網路 runner／用量、截斷與回應綁定檢查尚待建立及驗證。

## 已驗證的接點

候選框由 full-page normalized coordinates 轉 outward pixel crop，再轉為有界原頁 points。未命中任何 native owner 的框仍保留頁面與來源 hash；與多個 owner 重疊則保留全部幾何關聯。table/picture/caption 不強制改派 body；責任提示不是已證明的 ownership。所有新增候選都不 consume 既有 refs，不直接回填 Canonical，也不因 detector 的 complete=true 就宣稱來源覆蓋通過。

11 個 unittest 通過：包括無 native owner、重疊而不覆寫、跨元件提示、空結果仍未驗準度、abstention、非法座標／重複框／未知欄位／超限拒絕、改來源拒絕，以及協同更改頁碼／比例／範圍時對照不可變 inventory 拒絕。

另對八個實際頁面各用相同、來源無關的中心框 MOCK，核對頁面 mapping、raw response、native scopes、JSON reload 與不回填。這是接點控制，不是模型找到八個真實目標。實際 PDF pixel 負例亦通過：把頁圖換成同尺寸黑圖並同步更新 image hash，仍由原 PDF 重新 render 的比較拒絕。

舊 ABC compare-only gate 再次通過 71 tests；142 歷史 artifacts、35 live artifacts 未改。完整機械結果與封存 hashes 在 [verification.json](verification.json)。初次 PdfPage context-manager 相容性失敗及加強 metadata 比對前的離線 preparation 已在 precheck-v1／verification 保留，沒有因此重呼叫模型或更動來源判準。

## 停止位置與續接

目前環境沒有配置 `OPENAI_API_KEY`，已向使用者索取已配置的環境變數名稱或設定檔路徑，未讀取聊天歷史金鑰或把憑證寫入檔案。第一步已完成；API runner 與實際八次比較尚未開始。

後續先完成有界網路 runner，固定其方法與 request hashes、用量／截斷／錯誤拒絕控制，再在同一配置下每頁一次。不可因缺憑證、HTTP error、截斷或不完整輸出追加重試。來源評讀仍沿用原凍結 census，從原頁檢查 false negatives，而非只評已回報框；未驗來源覆蓋前不啟動重建。

本階段不放行完整 A，不解決 B 的 T04、四組 table math 或跨頁表，也不替 C 的真實 OCR／描述及完整配置補上品質成績。Holdout 與公司 Qwen3／vLLM／GPU 仍未驗證。這八頁是已曝光 DEV，不支持泛化資格。

可重跑的離線入口（不呼叫網路、不刷新 freeze）：

```sh
rtk /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-page-discovery-2026-10-17/discovery.py --verify
rtk /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B -m unittest discover -s docs/research/pdf-core-page-discovery-2026-10-17 -p 'test_*.py'
```
