# B：固定七張來源的實驗接口與評分路徑

2026-10-18。**七張來源的 producer／schema／requests／資源界線及 evaluator-only 手動評分路徑已固定；接口可執行，尚未執行任何新模型或 API。** 真實辨識品質、公司模型及完整 B 仍未通過。所有新增檔案只在本目錄，歷史 producer／schema／grader／oracle／模型結果不變。

## 現在可執行什麼

`candidate.json`沿用先前核對的七張 exact crops：原六個 targets（含兩張 collateral），加 WikiSkill p22 Table 7。共四文件、五個物理頁面。沒有把 evaluator 的四個 math group IDs、來源答案、預期列數或 oracle bbox 放進請求。

`prompt.txt`只要求通用 header paths、具名 row dimensions、明示 section membership、共同 source-cell identity 與 raw pairs／precision／blank／公式。圖片與圖中文字明示為不可信來源資料，不得當成指令。原印刷 colspan／格線形狀不構成新增門檻。

`protocol.py`以 strict／extra-forbid Pydantic envelope 解析，拒絕 missing／foreign／duplicate targets、未知欄位、numeric coercion、unknown 當空白及矛盾的 path／group／cell bindings；JSON duplicate keys 亦拒絕。合法回應會實際經既有 frozen normalized method、caption-ownership wrapper、公開 Core mapper、literal Markdown serializer 與 reload。沒有新 renderer、來源答案修補或 SDK 修改。

`runner.py`薄接既有 bounded HTTP runner 的 usage ledger、transport、wall timer 及整頁 atomic assembly。七個 materialized requests (`requests`)都有 exact SHA；不含 Authorization 或 credential。`--prepare`及`--dry-run`不讀金鑰，只有明示 `--live` 才從指定環境變數取值。嘗試目錄 exclusive-create，不能偷偷重播。原生 crop 在送出前重核；所有 baseline 在 assembly 前再核 SHA，防止拿舊 crop 配新共享工作區內容。

| 固定界線 | 值 |
|---|---:|
| 最大請求／並行／重試 | 7／1／0 |
| Input reservation 合計 | 106,634 tokens |
| Completion cap | 每次 32,768；合計 229,376 tokens |
| Request／總 wall-clock | 180／1,800 秒 |
| Request／content／transport bytes | 8 MiB／256 KiB／2 MiB |
| RSS／最低可用記憶體 | 12 GiB／8 GiB；啟動需可用 10 GiB |

Input reservation 為 prompt/schema UTF-8 bytes＋image/framing 預留，並非精確 tokenizer 保證；實際 usage 超限或不明會停止後續呼叫。這些是實驗資源界線，不是 production latency SLO 或預測實際花費。Refusal／截斷／內容 schema 失敗記為該 target 失敗、仍完成剩餘固定 jobs；transport／timeout／usage 不明等停止整輪。必要 sibling 失敗時整頁不交付。

舊 recursive process enumeration 在 sandbox 被拒絕，導致最初 mock run 在首個 request 前停止；見 precheck (`precheck.json`)。本 API runner 不建立子程序，因此改為明示 **current-process RSS**，保留實際每 0.25 秒 wall timer 與記憶體界線。Own RSS 實讀約 149 MB、可用記憶體約 16.7 GB；沒有假稱 process-tree 監控，也沒有要求擴權。

候選是既有 `gpt-6-luna` temporary OpenAI comparator。Service alias 不代表 immutable weights，不代表 Qwen3 品質；原始 response 的 model／ID／fingerprint／usage 仍完整保存。帳號存取、實際 provider 行為與 endpoint 可達性沒有於本輪呼叫驗證；credential 未讀。

## 評分接口也已固定

`evaluation-custody.json`先保存 producer／schema／candidate／七請求的 12 個 SHA，之後才開啟已曝光 DEV oracle。Producer bytes 此後不變。這是 exposed DEV review，不能稱盲測或獨立 holdout。

`scoring-manifest.json`與 固定 rubric (`evaluator/rubric.md`)採 **evaluator-only 手動語意 matching**，不把新 normalized 表格塞進原本依賴 compact grid／section-label rows 的舊 T05 grader，也不製造假 section rows。每個 worksheet 都有 exact oracle SHA、JSON pointer、來源 row context、數值點及註冊比較；新輸出需要同時對照 actual Core 與實際 rendered Markdown。

- 原主分母保持 **470 數值／23 比較**：T01 6／3、T02 84／8、T04 300／5、T05 80／7。逐 logical table 驗，不平均抵銷。複雜表最多 5% 數值錯；T01 原六點零錯界線保留，一錯本來也超過 5%。
- 所有 required points 即使 missing／unknown／錯綁／整個 panel 未交付也留在分母。同一點多個錯因只算一次；extra numeric outputs 算錯但不擴大分母。
- 全部關鍵關係、header／condition／unit／row dimensions／section scope 必須正確；不要求所有關鍵值 character-exact。T05 的 20 個 pairs 核對共同原始 cell、完整 raw pair 與角色順序；model IDs 不是 GT。
- 兩 collateral 分別保留 **24／90** 數值，來源 crop 及既有來源人工核對有固定引用，沒有加入 470。Table 7 的 **四組 math** 另列，允許等義表示／minor typography，但分數範圍、漏項與錯 row／column 是 material。
- T03 worksheet 另存 **264 數值／7 比較＋3 個 printed missing marks**，不混成 267 個數值，亦不納入七次單頁比較。

這些是未填的 source worksheets，不是合成輸出的準度成績。`null`／unreviewed 不能推定通過；未來需在 run 目錄寫結果副本、完成來源核對及 reviewer rationale 才能分配 pass／partial／fail。

## 真實 T03 的接合缺口已具體化

`T03-native-seam.json`同時保存歷史與 C 分支新產生的 current-S0 metadata。歷史快取是 Docling 2.102／Core 2.96；不可冒充目前 2.132／2.99。歷史 `metrics.json` 的 source／document SHA 已核實，沒有重跑該舊 profile。

新同版來源位於 `C/native/SRC08-p27-29/document.json`。目前 S0 仍有五個獨立 table items：p27 的兩個 Table 12 collateral，以及 Table 13 的 `#/tables/2`、`#/tables/3`、`#/tables/4`，分屬 p27／28／29，各自單頁 provenance。三段都有重複表頭，第一段 caption 帶條件，後兩段為 continued caption；它們沒有共同 logical owner，body 中還有非目標 continuation／footer 節點。

因此仍欠來源分組、共同 logical identity、重複 header 的角色／條件繼承，以及合併後保持非目標與有序來源 envelopes 的接點。本次只看實際 metadata，沒有猜 matching、丟 collateral、製作通用 merge 或稱來源內容已修復；亦沒有新增 per-cell bbox 的產品要求。

## 驗證與下一個門檻

最終 13 個測試 (`test-results.json`)通過：實際新 schema→parser→method→Core→Markdown／reload、真實七份 source baseline 的 injected transport、SkillOpt 雙 target 的 caption／collateral／provenance、整頁 atomic、duplicate JSON／unknown／refusal／截斷、overbudget／transport limit／timeout／wall timer、以及 request hash／assembly 前 stale baseline 拒絕。MockTransport 沒有 DNS／網路呼叫，合成內容不證 source accuracy。Root 另獨立核對 dry-run、request hashes 及這 13 個測試。

可重跑的 read-only 入口：

```sh
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B docs/research/pdf-core-eval-interfaces-2026-10-18/B/runner.py --dry-run
rtk <tmp>/pdf-core-native-std-20261017/venv/bin/python -B -W ignore::DeprecationWarning -m unittest discover -s docs/research/pdf-core-eval-interfaces-2026-10-18/B -p test_interface.py -v
```

**Readiness：** request materialization／offline transport gate／固定手動 scoring method 已成立；下一輪可在明示授權及安全配置 credential 後，執行唯一配置、最多七次的真實來源比較。本輪 remote/model calls 為 0，沒有自動進入 `--live`。七次結果仍須完成上述語意 worksheet，且不解除 T03、公司 GPU／Qwen3、獨立 holdout 或完整 Processing Profile 的阻擋。
