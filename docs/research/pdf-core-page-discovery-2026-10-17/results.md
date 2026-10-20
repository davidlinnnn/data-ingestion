# 整頁 discovery 固定八次比較

2026-10-17。**八次請求已完成；這版 VLM detector 不採作直接裁圖重建的正式配置，依既定停止條件不進入 reconstruction。** 它提供有用的粗定位證據，但必要符號會被框邊切掉；本輪沒有增加 padding、修框、改 prompt、換模型或重試。沒有完整 profile 合格。

## 固定方法與實測成本

保留 cached StandardPdfPipeline S0（Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3、Heron／RapidOCR／TableFormer V1）。本輪只增加獨立整頁 detector，不重新跑 Standard 或改 Canonical；不是改用整頁 VLM 轉錄 pipeline。八頁使用 scale 2／144 dpi，VLM 只收頁圖及固定 prompt，不收人工 bbox／來源答案／native 文字。

暫用 `gpt-6-luna`、Chat Completions、low reasoning、high image detail、JSON mode、store=false。影像輸入、Chat Completions 與 reasoning 支援已依 [OpenAI Docs 模型頁](https://developers.openai.com/api/docs/models/gpt-6-luna)核對；completion cap 包含 reasoning，依 [API reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)計量，不把 reasoning tokens 再加一次。沒有替換成公司 Qwen3，亦不將代理模型的品質／速度視為 Qwen3 結果。

| 頁面 | 候選框 | 自報完整 | Client 秒數 |
|---|---:|---|---:|
| controls 1 | 6 | 是 | 9.59 |
| DGM 51 | 4 | 否：ambiguous_boundary | 12.09 |
| SEAL 2 | 2 | 是 | 9.80 |
| SEAL 3 | 1 | 是 | 7.64 |
| SEAL 4 | 12 | 是 | 16.43 |
| WikiSkill 20 | 4 | 是 | 11.71 |
| WikiSkill 21 | 4 | 是 | 11.13 |
| WikiSkill 22 | 7 | 是 | 8.62 |

- 8/8 HTTP 200、8/8 response 格式合法、retry 0；7 頁自報 complete，不能當成 evaluator acceptance。
- 共 40 個候選框，**不是已排定的 reconstruction jobs**。跨 owner 歸屬仍未交付，也沒有 consume／覆寫任何 native refs。
- 總 client elapsed **87.04 秒**；input **20,896** tokens，completion **5,368** tokens，其中 reasoning 4,228 已包含於 completion。沒有觸發 80,000 input reservation／65,536 completion／8 calls 預算。
- detector 看完整八頁共 15,777,840 pixels；候選框每頁聯集共 3,931,859 pixels，約 24.9%。這只是幾何面積，不等於 token、呼叫數或 latency 可減少 75.1%。實際重建成本未量測。
- 這是 concurrency=1 的一次暫用 API 測量；約 10.88 秒／頁是本輪平均額外偵測成本，不是高頻吞吐、p95、fresh Standard 總成本或公司 SLO。未換算成實際帳單金額。

## 來源判讀：有進展，也有明確反例

Producer／requests 先 freeze，再封存 evaluator 方法與既有 census；之後才送出第一個請求。來源評讀沒有回饋給 producer 重試。原 44 groups、41 selected units、27 negatives 各自保留，未當 API jobs 或混成一個 accuracy。

| 來源 | 實際證據 | 判讀 |
|---|---|---|
| E026／SEAL 2 圖 1 | 新 r0 crop 含 `RL Outer Loop Iteration t` 的 `t` 及圖內分支；原 picture envelope 不含完整圖題 | 整頁 discovery 可以提供原 native picture 外的輸入，但這只證明該 crop 有涵蓋來源；17 個 math occurrences 尚未轉錄／重建／交付。模型也未按 prompt 分開外部 title，不能宣稱 ownership 已解 |
| E013／WikiSkill 21 | r1 crop 左邊漏掉第一個 `D_test`，右邊切掉 cardinality expression 的下標及閉合符號 | 必要 notation 不在實際 crop；不是單純 prose context 未全框入。該頁仍自報 complete=true，不能用它作 production 語意 gate |
| E015／WikiSkill 21 | r3 實際 crop 切掉 `SKILL.md` 的末尾 `d` | 識別字不完整，不能把小框直接交給必要 code enhancement |
| E037／SEAL 4 公式 (3) | r9 實際 crop 切掉兩個求和下限 `i=1`、`j=1`；凍結 source glyph 對照同樣顯示這六個字形未覆蓋 | 運算範圍所需內容不足，超出可接受的小排版差異。沒有用補 padding 改判通過 |
| DGM 51 | 模型自報 ambiguous_boundary | 格式合法，但此頁 discovery 不完整；保留 abstention，不加第二次機會 |
| N014／SEAL 2 普通陰性 | detector 完整框入一段原 ordinary-negative prose | 至少有不必要的額外候選工作；1/27 是此陰性集的覆蓋結果，不是所有內容的 false-positive rate |

檢視了八頁 [overlay 概覽](overlays/overview.png)，並逐一查看上述必要符號的實際 crop。原樣回應、綁定及頁級用量保留於 `live/`；來源-only glyph diagnostics 在 [source-diagnostics.json](source-diagnostics.json)。沒有把同輸入 mock 或 raw response 當成重建成功。

## 幾何 proxy 的限制

[coverage.json](coverage.json)依既有 2pt tolerance 計算非空白 glyph centers：native envelope 聯集本來即為 44/44 full context；detector 單獨為 35/44，native＋detector 聯集仍為 44/44。舊 41 units 的 0.45 overlap locator 為 41/41；27 negatives 中 1 個被 detector 完整覆蓋。

**這不是 44/44 語意準確率，也沒有證明提升了來源覆蓋。** 原 title envelope 可能幾何上包含字形，但 native text 沒有 emit 該字；PDF text layer 也未 emit 圖中全部數學符號。幾何 union 無法偵測這種內容漏失。另一方面，35/44 是完整 context 是否在 detector 框內，不是「9 組公式全錯」；例如只框公式但沒框原 prose，也會不滿分。停止判定依上表的必要符號裁切、abstention 與原有必要意思判準，不另改容忍線。

## 決定與後續邊界

1. 保留 Standard 主幹及已驗證的公開 Core 接點；**不採用本次 VLM bbox 作精準裁圖來源**，不進入本候選的 reconstruction。
2. 保留整頁 discovery 能跨 native picture 邊界提出輸入的證據，定位為粗候選提示；沒有直接晉升為正式 detector 或吞吐合格配置。
3. 若下一輪投入，問題應改為「能否由通用 native owner／完整來源 context 承擔實際重建輸入，而不依賴 VLM 精準框邊；native 外內容如何有界納入」。先用保存結果作有界可行性判斷，再決定是否值得新增 API 預算。本次不開始這個新方法，不對已曝光反例逐一修框。

B 的 T04／四組 table math／跨頁表、C 的完整圖片品質、heading／方向等其他完整配置缺口仍保留。Holdout、公司 Qwen3／vLLM／GPU 及高頻負載未執行；沒有修改 production／SDK，沒有 GitHub 發佈。這八頁屬已曝光 DEV，不支持泛化合格。

## 程序核對

本目錄 23 tests 通過（原接點 11、API runner 8、evaluator 4）；包含 HTTP 失敗只消耗一次 attempt、未知 usage 停止、actual overrun 計費後停止、重複 JSON／截斷拒絕、輸入 freeze 不刷新、跨元件與空結果不冒稱成功。Live 結束後 `api.py --verify` 再次通過，沒有改 producer／request／evaluator 方法。

憑證透過不回顯輸入交給單一推論程序，沒有寫入 request body、結果、報告、環境設定或 runner source。磁碟保留的是無認證 header 的 request hash 與模型回應。原離線 [summary](summary.md)、freeze 與 prechecks 作為歷史保留；本檔是本輪最新結論。
