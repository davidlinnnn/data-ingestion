# Native owner／完整 context 的零推論評估

2026-10-17。**完整 owner 輸入可以補回前輪的三處裁切；但這套通用選路仍未通過回填 gate，不進入新的重建推論。** 本輪完成全部八頁、40 個保存框的映射、工作量與來源 context 對照，沒有追加模型、API、修框或 padding。這是有界失敗／部分成立的結論，不表示 Docling 或 VLM 無法做到。

## 本輪真正新增的問題

完整 native owner 本身不是新方法；舊 A 已驗過部分公開接點與 MOCK。這次只評估兩個增量：保存的粗框能否用通用規則選到完整 owner；跨 owner context 能否有界組合，並沿既有接點限制回填範圍。沒有把舊 MOCK 當新轉錄成績。

資料沿用原 S0、八頁影像與全部 40 個保存 proposals。Routing method／tests／research bounds 先在 `registration.json`固定，再一次執行；來源 census 評讀在 routing freeze／replay 之後，沒有回饋 producer 改規則。這是已曝光 DEV，並非盲測或 holdout。

## 固定規則

- Native-only 候選使用既有 native code／formula、pure-formula-picture disposition，以及原 2026-10-15 的 Unicode Sm／Greek／math-alphanumeric／`_=<>^{}` character signal。不新增 `SKILL.md` 或文件名稱規則。它只是待比較的來源選路 baseline，非已合格 detector。
- Hybrid 保留全部 native 候選，再加入粗框命中的 owner。匹配需有正面積相交，且至少一個框的中心在另一框內；不遞迴用擴張後的矩形尋找更多 owner，也不以最近距離補無對應框。
- Picture children 合併到原 picture owner；table cells 歸原 table，caption 保留獨立責任。偵測器宣稱的 body／table 類別不凌駕 native 結構。
- 同一 owner 命中多次，以及 target owners 相互重疊的工作，以共同 owners 合併，避免重複消耗。輸入影像取完整 selected owner fragments 的 hull；保留分頁與來源綁定，不使用 VLM 小框的精準邊線。
- 研究上限：每組最多 4 owners、2 頁、每頁影像面積 50%；每條 route 最多 64 組、總 crop pixels 不超過原八頁完整影像總量。上限是本輪投入邊界，不是新增品質要求或正式 SLO。超限保留原 proposal 並標失敗，不刪部分 owner 硬湊通過。
- 真正可替換範圍只有明列 target owners；crop 中其他節點是 context-only。既有 A scope 必須能接受 targets；跨 component／跨 native parent 不猜測如何回填。

## 全量 replay 與工作量

| 量測 | Native-only | Native＋保存 discovery |
|---|---:|---:|
| 候選工作組 | 41 | 40 |
| 不重複 target owners | 41 | 51 |
| 分頁 crop images | 42 | 41 |
| Summed crop pixels | 3,229,151 | 4,350,441 |
| 占原八頁 pixels（可含工作間重複面積） | 20.5% | 27.6% |
| 符合每組 context 上限 | 41/41 | 39/40 |
| Public Core body scope 可建立 | 33 | 29 |
| 既有 pure-formula-picture seam | 3 | 3 |
| 既有 plain-caption seam | 3 | 3 |
| Table／B 責任，未重開品質驗證 | 2 | 3 |
| 缺少既有共同回填 scope | 0 | 2 |

全部 40 框有 native 幾何對應，沒有 unmatched；但這不能推論未 emit／無 native owner 的其他來源也可處理。真實資料檢查確認 41 個 native candidates 全保留，每條 route 沒有重複 target consumption；Hybrid 新增 10 個 target owners。

候選組數略減，主要是合併，不是工作量減少：crop pixels **增加 34.7%**，可改寫 targets 也增加。這些是規劃單位，不是已排定／可直接發送的 API jobs；輸出協定、token 上限及實際重建耗時尚未確立。`N_CF` 不能由 40 直接代入。

若實際使用 discovery，還須加上前輪八次 detector 的 **87.04 秒、20,896 input／5,368 completion tokens**。本輪重用保存結果，新增費用為零。不能用像素比例推算 token、latency 或公司 Qwen3 吞吐。

## 實際輸入有改善，但不是模型準度改善

已輸出並以保存頁圖核對 41 張 Hybrid context crops。逐一目視三個前輪必要符號反例與圖題邊界：

| 原反例 | Owner context 結果 | 可以支持的結論 |
|---|---|---|
| WikiSkill 21 的 `D_test`／cardinality | 完整段落含兩個 notation、上下標與閉合符號 | 不依賴 VLM 精準框邊可補足該輸入 |
| WikiSkill 21 的 `SKILL.md` | 完整 EvoSkill 段落保留末尾 `d` | 新選到的原生段落可提供完整識別字；未證明需重建或模型會正確輸出 |
| SEAL 4 公式 (3) | 整個公式區塊含 `i=1`／`j=1` 及式號 | 輸入不再切掉運算下限；未重跑公式模型 |
| SEAL 2 圖 1／圖題 | Picture＋title hull 包含 `RL Outer Loop Iteration t` 與圖內分支 | 圖題字形可進輸入；17 個 math occurrences 並未重建／交付，共同回填仍未解 |

三處 cropped symbol 恢復是 context 的實證，不是對所有 native boxes 完整性的保證。沒有在這些反例上新增 margin、手工 bbox 或單獨模型路由。

## 兩個停止點

1. **SEAL 圖片＋圖題：兩種責任的共同輸出契約缺失。** `#/pictures/0` 與 `#/texts/0` 均可進 input，影像面積僅占該頁 7.8%，沒有成本超限。然而現有 body fragment-order scope 明確要求 leaf text；它不能把一般 picture 與 title 當同類節點回填。Pure-formula-picture 控制也不代表一般混合圖已支援。這是輸出／責任整合缺口，不能把原圖保存、幾何覆蓋或新 crop 當成 source reconstruction。
2. **SEAL 算法與正文：11 個節點跨兩個 parent。** 兩個保存粗框加 native seeds 經共享 owner 合併，形成 11 targets，跨 `#/body` 與 `#/groups/0`；既有 scope 拒絕，原因是 `ordered scope requires one native parent`。本組也超過 4-owner 研究上限。即使放寬該上限，既有回填接點仍不適用，不能將它描述為僅受任意數量門檻阻擋。

這兩組沒有被丟掉，也沒有拆成看似通過的小組來規避來源讀序、context 或重複交付問題。完整路徑 gate 未成立，因此本輪不只挑可建立 scope 的 29 組去叫模型。

## 全來源對照的界線

`coverage.json`沿用既有 2pt 非空白 glyph-center proxy，分母與先前 frozen source evaluator 精確對齊：44 source groups、27 negatives、另列 41 legacy locators。

| Proxy | Native-only 選中的 context | Hybrid 選中的 context |
|---|---:|---:|
| 完整 source-group context | 37/44 | 43/44 |
| 普通陰性被完整納入 context | 2/27 | 3/27 |
| 舊 41 units 的所有 fragments 有 ≥0.45 locator | 24/41 | 27/41 |

與前輪「所有 native envelopes 聯集本來 44/44」不同，這裡只計實際選中的 candidate contexts；也包含尚未解回填或超限的 proposed inputs，不能當可執行成功率。六組新增完整 context 不等於六組內容已修好或都需要 VLM。尚未全框入的 controls inline-code group 主要缺周邊 prose context，不能因此自動判必要識別字失敗。舊41 overlap 是定位指標，也不是模型成功率。

所有來源的必要意思與既有 minor tolerance 保留；沒有將語意準確率改成幾何滿分，也沒有收窄必要公式／code 要求。

## 去留建議

**保留完整 owner 作為已有可靠接點之 component 的輸入策略；不採納目前這套整頁 detector＋通用多-owner 回填為正式配置。** 第一、二步已提供答案：裁切可改善，但會擴大影像及改寫範圍，且新增的關鍵跨界工作缺少共同回填契約。依門檻不進入第三步的新模型推論。

不建議為了這兩個已曝光 DEV 阻擋持續擴張 mapper 或增加個案規則。下一個方法決策可集中在少量困難頁的頁級 fallback，並先界定可通用的觸發條件與成本上限；它尚未實測，也不能用本輪案例 ID 作觸發規則。本輪沒有啟動其他 pipeline／Paddle 或新的候選模型。

原 B 的 T04、四組 table math、跨頁表與 C 完整品質仍未解；公司 Qwen3／vLLM／GPU、高頻負載、holdout／完整 profile 均未驗。本輪沒有改 production、SDK、歷史實驗或發佈 GitHub。

## 程序驗證

7 個新 routing tests 通過，含 transitive merge 保留 native seed、context-only 不擴成 target、跨 component 不冒稱 body scope、超限不裁掉來源及原 character gate 無 filename 特例。實際 replay 再檢查所有 native targets 保留、每 route 不重複 target、44／27／41 source 分母與既有 evaluator 一致。舊封存 hashes 逐一比對，未刷新期望值。

首次 evaluator import 因獨立研究目錄的 import path 缺少 `discovery` 而停止，發生在 source evaluation 產物建立之前；僅修 evaluator 的 module search path，routing freeze／規則／結果未改，沒有推論或資料修補。

可比對 `registration.json`、`results.json`、`crop-manifest.json`及最終 verification；沒有 live API mode。
