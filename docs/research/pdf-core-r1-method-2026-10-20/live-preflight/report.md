# R1 A/C live 前置檢查：零推論交接

2026-10-20。本回合停在 **live_ready=false**。沒有送出真實推論；不是四項全部完成，不應把 dry-run 當作可以直接核准 43 次的證據。方向、排序與後續預算仍交主線 Claude 決定。#84 可作決策／交接票結案，品質資格交 #80–#83 gates；本報告不另外要求 DEV 全品質通過才可結案。

## 四項狀態

| 前置 | 狀態 | 證據／未完成原因 |
|---|---|---|
| 1. 固定模型與能力紀錄 | 模型／endpoint／參數已固定；一次存取確認完成 | `gpt-6.1-sol`，與 B 相同 Chat Completions endpoint、low reasoning、high image detail、JSON object、store=false、無 temperature。唯一 GET 回傳 200／同名 id。官方記載 context 1,050,000、max input 922,000、max output 128,000。模型專屬 image sizing/billing 規則未確認，列入第 2 項缺口 |
| 2. 每 job token reservation／費用 | **未完成，不能聲稱 verified reservation** | 官方 vision sizing/multiplier 表與 calculator 文字沒有 `gpt-6.1-sol`；精確官方搜尋沒有補上依據。保留的 tiktoken 0.14.0 也沒有該模型映射。不得套用 Astra／GPT-5 規則或把文字 bytes 當 tokens。每 job 的真實總 input、image token、完整估價均保留 null |
| 3. 評分規約與 expected answers | **規則／43 個非目標 QA 已凍結；完整 golden 尚未完成** | 新增 11 份 source-specific 檢查表，逐頁查看 14 張原圖；抽取來源 PDF 文字作參考，所有 43 job 固定完整 native unit／順序／邊的回歸答案。仍缺所有 inline math/code 的完整逐 occurrence 清冊，NCCU screenshot／timeline 完整 OCR 答案亦保留既有 partial；不能用必要關鍵字清單冒充完整 golden |
| 4. bounded runner／43-job dry-run | **mock 範圍完成** | 43/43 驗證、11 份 A 同來源組裝、14 份 C supplement／29 張圖；24 個控制通過。HTTP seam 用 httpx.MockTransport 驗證，無網路 POST。當前 CLI 只能 mock，live gate 明確拒絕。正式啟動仍依第 2、3 項與主線授權 |

模型存取不是 endpoint 行為的完整測試：image high／JSON mode 的實際可用性另有先前 B 七次比較佐證，本回合沒有重新推論探測。詳細能力狀態在 [endpoint-capabilities.json](endpoint-capabilities.json)。原 B 未指定 service_tier，本回合沿用；project 實際 routing／premium 未查明，不能保證 Standard 計價適用。公司模型型號／GPU 未取得，資格仍是 #82/#83 的 gate。

## 43 job 預算盤點

請求有 15 次 source reconstruction、14 次 description+context OCR、14 次 chart assessment。completion cap 暫固定來源重建 16,384／job、C 各 lane 8,192／job，合計 **475,136**（含 reasoning 與 visible output）。這是有限上限，不代表每個語意完整答案都能放入；最長合法回應的模型 tokenizer 預檢仍未通過。

- 實際兩個 text message strings 的 `o200k_base` **參考編碼計數**合計 **189,438**；不含圖片與 Chat framing，**不是固定模型的正式 input 預估**。
- model-specific input、image token 及正式逐 job 費用：**未能確認**。43 筆逐 job 記錄在 [token-budget.json](token-budget.json)，沒有以 0 或其他模型值補缺。
- 請求總 bytes 39,739,703，最大 2,771,681；本機 16 MiB input gate 全部通過。未發現已確認的 byte/image-count 超限；沒有依未確認 token 規則擅自拆 job。
- 只計 completion cap，若每個 input 都不超過 272K、Standard tier，output 上限為 **US$4.75136**，不含 input。
- 若完全不用實際內容估計，改以每 job 最大 input 容量 922,000 及 long-context 最貴 cache-write rate 計，得到 **39,646,000 input 容量、US$205.35704 的條件式容量級界線**。這是假設 Standard、無區域 premium，input 全以 $5/M、output $15/M 計的極鬆上限；**不是本批估價、不是 verified reservation，更不是已批准預算**。service tier 未確認時不能當正式帳單保證。

以下僅按文字 proxy 排序；圖片規則未明，不能稱為總 input 最大的五筆。

| Job／來源 | 頁 | 文字 proxy | 圖片數 | completion cap |
|---|---:|---:|---:|---:|
| ce6064e5aa／SEAL | 2–4 | 16,869 | 3 | 16,384 |
| c613789b3a／WikiSkill | 10–12 | 15,728 | 3 | 16,384 |
| d3e2dd02ca／ReasoningBank | 9 | 14,721 | 1 | 16,384 |
| b14b461006／Memory-R1 | 8 | 13,374 | 1 | 16,384 |
| ecaf1dce6d／既有 timeline scan | 2 | 11,564 | 1 | 16,384 |

未更改 43 job 的分組／來源方法。若正式 token 預檢後超限，不能把有共同 provenance 的群組任意按頁切開：必須保留完整來源、owner exactly-once 與同來源原子組裝；需要新增請求或更改 cap 時，先交主線裁定。本輪未進行此變更。固定集合原本含 scan fixture，不代表改變「掃描往後排」優先序或新增掃描實驗。

## 評讀規約與 freeze

[rubric.md](evaluator/rubric.md)沿用 Q4、Q30/Q31、Q32/Q33、Q44–Q46、Q27–Q29，沒有新通過率。來源重建看全部必要 math/code/caption、原文／順序與主要 Markdown；圖片 lanes 必須同圖 key、分清 crop/context OCR，不把 description/chart 寫成原文。Chart 的 series／category／unit／printed／estimated 與條件歸屬分開評。

**非目標 QA 不只檢查 keep**：所有被 consume 的 ordinary prose 仍對原稿；tables、pictures、caption/footnote edges 與原閱讀順序固定比對。baseline snapshots 是回歸對照，不是語意 golden。ReasoningBank 圖題以原稿為答案，保留原文 `under with` 的不順語句，不保留 OCR 混接，也不修來源文法。

在任何本批真實模型輸出出現前，已凍結：

| 檔案 | SHA-256 |
|---|---|
| evaluator/freeze.json（含 64 份來源／規約檔案的 hash） | `309803ccb9bf2b464bbe5b0c39c17670a70b28c430d6e2398cb4a10d7c816eca` |
| evaluator/rubric.md | `07549a2e3d808689a0f926faac178f638ee2816286b4ca22ff7b0de34f30bc16` |
| evaluator/expected-answers.json | `532295405d38849b88bedc5c150f2de4b1b17a0154c149cb6b7ac686c7c9a3a0` |
| evaluator/non-target-manifest.json | `c829cee1ce42ec20d4ce2c7b4605b80d6bffbf11ad8f973cf56f8305ebae9b5a` |

完整 golden 缺口不是模型品質失敗或可以自動忽略的項目；本次規約不能用來宣布所有 source groups 已合格。補充時應保留本次 freeze、另立版本，在真實輸出前由主線確認，不覆寫舊答案。

## Dry-run 與失敗處置

[dry-run/summary.json](dry-run/summary.json)的最終全批 mock 無失敗；所有 request SHA 與 image bytes 都可重建。逐 job 原始 MOCK 回應／收據與最終 ledger 保留。24 個控制驗證 binding、缺圖、JSON、incomplete、拒答、截斷、空白描述、錯 model、usage 與 byte 上限、hard timeout、停止後不送下一筆、不 retry、HTTP 不跟 redirect，以及部分組裝不發布。HTTP seam 的測試只使用記憶體 MockTransport、dummy credential。

工程過程的先前兩次完整 mock pass 保留在 dry-run-initial 與 dry-run-before-atomic-delivery；不是額外模型重試。最後加固原子交付後重新完成全批 mock。mock 的 source keep、chart unknown、OCR unreadable 都是測接點的占位，不是內容正確、完整 OCR 或可接受偏差。

runner 的固定上限：concurrency=1、retry=0、best_of=1；180s/request、3600s/batch，16 MiB request、1 MiB response。超額／逾時／傳輸／拒答／schema／binding／來源不完整即停止，剩餘 job 記 NOT_RUN，沒有自動 resume。原始 oversized body 不落盤，留 bytes/hash；不完整組裝留 delivery-pending，全部成功才改名 delivery。CLI 明確拒絕 live；HTTP seam 已備妥但這次沒呼叫遠端。

## 若主線日後批准真實執行

先補第 2、3 項並封存可執行批次，主線再取得使用者核准與明確下令；此報告不替代該步驟。公司模型／GPU 資格仍不能由 OpenAI DEV 結果代替。

沒有可信的 A/C 全批 latency 點估。歷史 B 七次串行 214.50s，線性換算 43 次約 **22 分鐘**只能作參考，A/C 的頁數、輸出與 OCR 負載不同。**60 分鐘是停止線，不是保證完成時間**；43×180s 的理論最壞為 129 分鐘，與批次上限不相容。要全批完成，含組裝 overhead 的平均每次須少於約 83.7s，不能藉縮減必要內容去達成。

任何失敗保留成功與失敗收據，未送工作記 NOT_RUN，不挑另一個模型、不自動重試、不延長 deadline。timeout 只終止本機等待，不保證 provider 停止生成或不計費；不明用量需記 unknown 並交主線決策。未完成批次不得冒充完整 A/C 或公司正式資格。

## 邊界與重查

本回合只新增 live-preflight 產物並更新唯一最新狀態入口；沒有修改原 thread 狀態、W2、SDK、歷史 seals；沒有 commit、push、GitHub 留言或 holdout。只取得 BPE vocabulary 作明示的參考編碼，沒有下載模型權重或更動保留 runtime。模型 alias 不代表 immutable weights。

既有完整 109 個測試／控制及歷史封存檢查通過；原 R1 的 161 檔 seal 與兩個 relocated MOCK bundles 仍通過。新的唯讀重查：

```sh
rtk proxy /private/tmp/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-r1-method-2026-10-20/live-preflight/check.py
```

官方依據：[模型規格](https://developers.openai.com/api/docs/models/gpt-6.1-sol)、[Vision 計價與限制](https://developers.openai.com/api/docs/guides/images-vision)、[價格](https://developers.openai.com/api/docs/pricing)、[JSON mode](https://developers.openai.com/api/docs/guides/structured-outputs#json-mode)。取得的頁面與 hashes 保留在 official/；模型專屬規則缺漏如實列為未完成。
