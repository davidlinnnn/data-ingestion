# Standard 原生 CodeFormulaV2 enrichment：執行結果

2026-10-17。已依[確認計畫](pdf-core-standard-enrichment-plan-2026-10-17.md)完成 **E1 一組配置、8 頁、4 次 conversion、10 個 region inputs／4 個 enrichment batches**，沒有超額、調參、重裁、重跑或 API fallback。**原生接線可執行，部分 code／公式有恢復，但這個固定組合仍不合格，不升為完整候選；G2 未通過。**

有價值的新證據：在真實 Standard pipeline 中，CodeFormulaV2 能把受控 code 的行序／巢狀層級、SEAL Eq2 的完整 cases、Eq3／4 的主要數學重建成 typed text 和主要 Markdown。問題也確實出現在這條路徑：精確 literal 改字、式號遺失，以及原生擴張 crop 內相鄰內容被寫進 code，產生重複／錯歸屬。不能只挑成功輸出拼成另一個未執行過的配置。

## 固定配置與程序

| 項目 | 實際執行 |
|---|---|
| Pipeline／版本 | StandardPdfPipeline；Docling-slim 2.132.0／Core 2.99.0／Parse 7.22.3／pypdfium2 5.14.0；PyPdfiumDocumentBackend |
| 上游 | S0 Heron、selective RapidOCR v6 det／rec-small＋v2 cls、TableFormer V1 accurate；來源、資產 hash、layout／OCR／table batch 1、native reading order／assembly 與 S0 不變 |
| 新增 | do_code_enrichment=True、do_formula_enrichment=True；官方 codeformulav2 preset |
| 模型 | docling-project/CodeFormulaV2，revision ecedbe111d15c2dc60bfd4a823cbe80127b58af4；既有 630,993,616-byte 權重，12 檔完整 hash 重核相符 |
| Engine | Transformers 5.20.0；實際 471 個 parameter tensors 全為 CPU／FP32；4 threads、interop 1；compile／quantized／8bit／remote code 均 off |
| 原生有效參數 | scale 1.67、bbox expansion 0.18、prov[0]；temperature 0、cap 2048、skip_special_tokens=False；實際 batch 長度 2／1／4／3 |
| 順序 | Controls1 → Wiki20–22 → SEAL2–4 → DGM51；兩個三頁範圍各連續一次 conversion |
| 保存／匯出 | 公開 stage 前 snapshot、實際 crop／request、engine raw、stock cleanup 後 item、完整 JSON、預設 Markdown；不修改 private crop／parser |

完整[預登錄](pdf-core-standard-enrichment-2026-10-17/registration.json)、[有效 options](pdf-core-standard-enrichment-2026-10-17/registered-options.json)、[runtime](pdf-core-standard-enrichment-2026-10-17/runtime.json)、[模型資產](pdf-core-standard-enrichment-2026-10-17/model-assets.json)、[實際載入型別](pdf-core-standard-enrichment-2026-10-17/E1/loaded-engine.json)均已保存。原生 preset 內雖另有 BF16 default，實際 engine override 及 parameter 觀測確認本次為 FP32。

先完成[零模型 gate](pdf-core-standard-enrichment-2026-10-17/preflight.json)：root／group code、root formula 的 cleanup／寫回／stock export 可承載合成合法內容，observer 與無 observer 的結果完全相同，保留 `orig`／provenance。首次 mock 的目錄建立失敗在載模型前修正並[留存](pdf-core-standard-enrichment-2026-10-17/preflight-attempt01-failure.json)。沒有安裝新套件或改歷史 runtime／oracle。

## 逐任務結果

| 來源工作 | 內容與交付觀察 | 判定 |
|---|---|---|
| Controls comment／body | comment 找回獨立一行；六行 statement、`<=`、`+=`、ok／skip 及 if／else 相對巢狀恢復。Raw 有共同 4-space offset；stock language extraction 只清掉首行 comment 前空白，body 仍是 4／8／8／12／4／8，未符合原 41 項明定的 0／4／4／8／0／4。 | comment 通過；body 有結構恢復，完整縮排交付仍不符。沒有加上「必須可執行」的新條件。 |
| Controls inline code | 原生 crop 228×17 含相鄰冒號；輸出為 `: items [ i ] <= limit`，仍是獨立 code block。 | 新增冒號、原位表示仍有缺口。HTML language metadata 本身不是判失敗理由。 |
| DGM 完整 diff | 多數 identifier／default／必要行恢復；但原 `\n=== Attempt` 變 `\n== Attempt`，`:.2f` 變 `::2f`，context indentation 失真。846×735 原生 crop 也含下方 section title／正文開頭，模型一併寫進 code。 | material；精確 literal 錯誤已在 raw，且整頁多出重複／錯歸屬內容。 |
| DGM node6 指令 | 兩段原文、tools/edit.py、edit／str_replace／old_str／new_str 精確 literal 恢復；但 crop 內上方 `Feature suggestion to obtain node 6:` 被一併寫入，和正常正文 label 重複。 | 部分恢復，完整交付仍 material。 |
| DGM node24 指令 | 全部指令詞與精確 `'editor'` 恢復；原 printer-wrap 處變成 angle glyphs，未改行／token editing、atomic apply 或避免覆寫的意思。 | 按原 instruction-prose wrap ambiguity 列 accepted minor；不把該容忍外推到真實 code 運算子。 |
| SEAL Eq1 | LaTeX 可解析，但原 inner `SE ∼ LM` 變成 `mathbb S ∈ LM`，reward 的 SE 亦改為 S；漏式號 (1)。 | 真實數學 identifier／關係改義，material。 |
| SEAL Eq2 | 兩分支 1／0、Otherwise、條件、SE／tau／theta_t、式號 (2) 均保留，主要 Markdown 有可用 cases。 | 本來源單位通過。 |
| SEAL Eq3 | 梯度、負 1/NM、i／j sums、reward 及條件分布保留；漏式號 (3)。 | 主要數學恢復，完整來源單位仍 material。 |
| SEAL Eq4 | 三層 sums、token／history 與 `y_{<s}` 保留；漏式號 (4)。 | 主要數學恢復，完整來源單位仍 material。 |

Eq2 的 superscript 2 仍掛在條件句的 performance **文字**後，原頁 footnote2 本文完整留在同頁；依可見 marker／正文對應保留註腳解讀，沒有把它判作 reward 平方，也沒有新增「必須有 typed hyperlink」要求。這不等於 G3 的機器可用註腳關係已認證，亦不代表區域模型看過遠處 footnote body。

四個 SEAL 式的 LaTeX→MathML 均可解析，[語法檢查](pdf-core-standard-enrichment-2026-10-17/formula-syntax-check.json)只證明表示可處理；它不能讓 Eq1 改義或式號遺失變成通過。Raw 的 stop_reason 都為 unspecified，不宣稱已由它證明 EOS；沒有 cap 截斷證據，不調高 token 上限。

### 辨識、crop 與 source mapping 的界線

實際[10 個 region 證據](pdf-core-standard-enrichment-2026-10-17/region-review-evidence.json)與[crop contact sheet](pdf-core-standard-enrichment-2026-10-17/actual-crops-contact.png)保存且已目視。DGM 擴圖確有鄰接標題／正文，raw 也確有這些文字；這能支持「原生路徑發生 context ingestion／重複」，不能單獨證明 0.18 擴張是所有錯字的唯一原因。

寫回未改原 bbox、charspan 或 orig。這證明 metadata 保留，不代表新增在 code 內的相鄰文字擁有正確來源定位：它們被歸到原 code item，仍是交付缺陷。本輪不重裁、不搬節點、不刪掉新增文字來修成通過。

## 原 41 項與回歸

[逐項評讀](pdf-core-standard-enrichment-2026-10-17/unit-review.json)沿用全部 41 個來源單位；只對有改動及重複影響的工作重新評讀，其餘以原來源評讀加同 run exact comparison 保留結論。

| 交付狀態 | 原 S0 | E1 |
|---|---:|---:|
| Pass | 17 | 17 |
| Accepted minor | 0 | 1 |
| Material | 7 | 10 |
| 本配置未實作／未涵蓋的重建 | 17 | 13 |
| 合計 | 41 | 41 |

這不是模型 accuracy 排名：四個先前未重建的式子現在有輸出，其中三項完整契約仍失敗；同時 comment、node24 指令與 Eq2 有恢復，DGM 原正文開頭和 node6 label 又因重複出現新缺陷。數量不能抵銷精確 code 或數學改義。

同一次 E1 的[前後差異](pdf-core-standard-enrichment-2026-10-17/pre-post-diff.json)確認：

- 四份文件的 pre-enrichment `texts` 全部與保存的 S0 完全相同；除 `texts` 外的 document 欄位前後完全不變。
- 只變更預期 10 個元素：Controls 2、Wiki 1、SEAL 4、DGM 3；Wiki 這個獨立公式不屬原 41 項，僅作已計數 collateral，不加入成功分母。
- Wiki357／368、SEAL21／30 四個原生跨頁 join 的完整 item 與雙頁 provenance 均未改；沒有重接規則。
- 四個原保護錨點的原正文 item 未改：E04 五個 literal／node／數值綁定仍在，Wiki362 opening 仍在，E13／E14 的完整 inline math 仍未交付。**不能以 item 未改宣稱整份文件沒有 regression**：DGM E04 的 opening 被複製到 code，原 node6 label 也重複。原狹義正例與 41 項完整 fidelity 分別記錄，未改原 rubric。

Controls 三個 picture-child 公式和普通段落 inline math 未走原生 enrichment；這些保留未涵蓋狀態，不算模型辨識失敗。複雜表格、圖片 supplement、scan 未重跑，亦沒有新的通過主張。

## 時間、資源與去留

| 觀察 | 實測 |
|---|---:|
| Worker 總時間，含 import／load／export | 55.72 秒 |
| Pipeline eager 初始化 | 1.97 秒 |
| Controls／Wiki／SEAL／DGM range | 5.96／4.82／10.13／30.68 秒 |
| 四個公開 engine predict_batch，含前處理／decode | 4.57／1.81／7.57／27.53 秒 |
| Sampled tree RSS peak | 6.21 GiB |
| 最低 sampled system available | 14.72 GiB |
| Native status | 4/4 success；不作來源保真判準 |

[執行紀錄](pdf-core-standard-enrichment-2026-10-17/E1/execution.json)及[range metrics](pdf-core-standard-enrichment-2026-10-17/range-metrics.json)保留完整取樣，未觸及任何停止線。Engine metadata 的 generation_time 是 batch 平均分攤，不拿它當每個 crop 獨立 wall time；沒有 CPU／GPU 加速比、p95 或高頻 SLO 結論。載入時原生 Transformers 有 checkpoint tied-weight warning，未為消警告改 config；退出時有一則原生 cleanup log warning，worker 仍 exit0，所有結果已保存。

**去留：不升級 E1 為完整配置，也不把它全域開到正式管線。** 可保留「官方接點可在本機 CPU 執行、部分 root formula／code 內容有恢復」的有界研究證據；但原 code 路徑有新增內容污染，公式仍有數學改義及式號缺失，因此停止對這個固定組合追加調參。不能建立「遇到 Eq2 才用它」這類樣本專用路由。

下一個實質取捨是：是否接受另行設計、限制明確的通用 region API／表示層整合成本，或等公司有任務協定的 VLM 服務做具名候選比較。單純把通用 Qwen3／OpenAI 插入 `<code>/<formula>` 協定不保證有效；本輪沒有自行啟動這條擴充，也沒有恢復 C1、Paddle 或 holdout。

未修改 production、舊輸出或來源契約。未驗公司 GPU／vLLM、高頻負載、未曝光泛化與完整 Canonical Acceptance；這些風險仍保留。
