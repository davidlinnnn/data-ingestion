# PDF core G2：第一組通用 context 的36筆新推論

日期：2026-10-15（Asia/Taipei）。承接[通用候選第一輪](pdf-core-g2-context-candidate-2026-10-15.md)與 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。**36筆新推論全部完成；來源初評25 pass、5 minor、6 material。結構回填可處理34筆，但仍包含來源錯誤。第一組配置不選為holdout challenger，G2尚未全面通過。**

本輪是固定開發資料的新API執行，不是舊回應重放。兩個獨立source-only評分契約在第一個HTTP請求前固定，原圖、target／context與來源判準先核對；沒有調整prompt、裁圖、門檻、候選模型或原始答案去配合結果。六份新holdout PDF未開啟。

## 執行與來源範圍

沿用已固定的candidate1、36張PNG、producer導出的target rectangles／角色及user prompt。暫用使用者指定的 `gpt-6-luna`，direct Chat Completions component、low reasoning、high image detail、strict JSON schema、4096 completion-token cap、`store=false`、不帶temperature；順序執行且每項只有一次attempt。System prompt沿用最初安全client的原文，未沿用較長inline比較prompt；實際HTTP body全部獨立重建核對。因此不能把歷史與本輪差異歸因單一裁圖或context變因。[登記](pdf-core-g2-context-api-2026-10-15/run-registration.json)／[方法](pdf-core-g2-context-api-2026-10-15/api/method.json)

36次皆HTTP200、`finish_reason=stop`、無refusal，沒有撞completion cap或語意重跑。Runner沿用既有記憶體client，憑證未寫入檔案、命令參數或報告。[獨立API核對](pdf-core-g2-context-api-2026-10-15/api/verification.json)保留影像、prompt、schema、request body、response、usage及唯一request ID的證據。Structured Outputs只約束JSON結構，不能證明原稿忠實；本輪兩筆仍未通過本案parser的typed-segment相容條件。[官方請求欄位](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)

本輪準備的36項之外，原selected scope還有五項明確未執行：SEAL四個formula因原生text／charspan不完整，及混合正文／旁側標題的item34。它們是清楚的來源內容但方法未能建立scope，不是來源天生模糊。三個hidden formula children已由三個外層envelope處理，不重複計分。因此要同時保留 **36個已執行target與41個selected logical work units**，不能只看模型願意處理的部分。[未執行清單](pdf-core-g2-context-api-2026-10-15/review-seal-controls/unprepared-scope.md)

## 來源評分與交付

| 來源 | 新請求 | Pass | Minor | Material | 可結構性回填 |
| --- | ---: | ---: | ---: | ---: | ---: |
| WikiSkill | 7 | 5 | 1 | 1 | 7 |
| DGM | 6 | 2 | 1 | 3 | 5 |
| SEAL | 14 | 10 | 2 | 2 | 14 |
| Controls | 9 | 8 | 1 | 0 | 8 |
| 合計 | **36** | **25** | **5** | **6** | **34** |

這些是兩組事先固定rubric的原始分類，不是production accuracy。Minor的型別不同，不能全部自動升為完整交付成功；兩組reviewer的full-target flags亦不直接相加當成統一Acceptance指標。文字／code內容、數值及數學意思層面有32／36保留，但這排除了typed segments／source block role的必要交付條件，不能代替完整成功率。[完整分母與分層統計](pdf-core-g2-context-api-2026-10-15/summary.json)

六項material均保留原始回應：

| Target | 實際缺陷 | 層次 |
| --- | --- | --- |
| WikiSkill368 | 原稿方法名 `ReflACT` 被讀成 `RefIACT` | 來源識別字 |
| DGM646 | 原稿預設 `{}` 被改成 `[]`，部分相對縮排也改變 | Code字面值／結構 |
| DGM648 | 文字／code tokens、綁定與數值保留，但第一個monospace `edit` 沒有code segment | Typed inline code |
| DGM650 | code block的segment卻標成text | Typed block契約；strict parser拒絕 |
| SEAL32 | `LM` 的theta下標遺失prime；部分強調prose也被當math | 數學身份／型別 |
| SEAL49 | 兩字母identifier `SE` 被改成 `S_E` | 數學身份 |

成功的有界部分：三個controls公式保留完整矩陣、分數及分段式；行內平方正確。Code12只輸出註解，code13只輸出六行主體，縮排為0／4／4／8／0／4，兩項context沒有混入對方的內容。這些結果支持局部方法，但不能外推所有真實公式／code。[SEAL／controls來源核對](pdf-core-g2-context-api-2026-10-15/review-seal-controls/results.md)／[WikiSkill／DGM來源核對](pdf-core-g2-context-api-2026-10-15/review-wiki-dgm/reviewresults.md)

Minor項目為WikiSkill362的數字排版空格、DGM652的印刷換行懸掛縮排、SEAL28／30額外的standalone `SE` math型別解讀，以及controls14的source paragraph被既有native/request role帶成code block。Controls14的文字與inline-code segments正確，卻因block／segment不相容被parser拒絕；這是來源角色與契約接點，不應靠修正答案字串掩蓋。

## 評分一致性與既有正例

四個既有bounded正例均按**原本判準**保留：WikiSkill363／E14的六個inline math、WikiSkill362段首與完整prose、DGM648／E04的所選tokens／binding／numbers，以及SEAL30／E13的11個inline math與跨頁完整段落。E04仍有新完整typed-role缺陷，不能用bounded內容通過替它取得完整交付通過。

另外發現一項annotation解讀差異：本輪SEAL source contract額外要求standalone `SE` 成為math，但原G1-E13 oracle將該處保留為prose，原分母是11個math spans。因此SEAL30的新增minor註記不是舊F13退化；本輪contract與原始評分都保持原樣，另存[解讀註記](pdf-core-g2-context-api-2026-10-15/review-seal-controls/role-interpretation-annotations.md)。原checker對跨行hyphen／whitespace的診斷也與來源允許的reflow分開記錄，不能讓字面regex取代原稿判準。[獨立一致性核對](pdf-core-g2-context-api-2026-10-15/integration/source-review-consistency.md)

不因這項解讀差異更動輸出、調參或刪案例；它也不抵銷其他material錯誤。這是評估資料品質的核對，不是將失敗改標成功以挑選方法。

## Parser與回填

沿用凍結的strict parser與candidate1 adapter：34筆完成parse／結構回填，DGM650與controls14保留為兩筆明確parse失敗。原始provider、圖片、模型回應及所有範圍外的序列化literal spans保持不變；23個邊界負例均通過。[Parser結果](pdf-core-g2-context-api-2026-10-15/parsed/summary.json)／[回填結果](pdf-core-g2-context-api-2026-10-15/integration/results.json)

34份結構結果只是working候選，內含SEAL32等來源語義錯誤，不能直接轉成Canonical Knowledge。Source reviewer是在本輪驗證中對照原稿，不是已實作的runtime語義驗收器。本輪沒有把人工oracle審核或review-selected subset偷偷當作production gate。

## 時間與成本

36次順序請求的client RTT合計 **193.37秒**；median **5.03秒**，樣本p95 **11.00秒**，範圍 **1.92–12.45秒**。Prompt25,720＋completion13,643＝**39,363 tokens**；reasoning7,143已包含在completion，不能再加一次。沒有cached prompt tokens。[Usage與計算](pdf-core-g2-context-api-2026-10-15/usage.json)

按本日官方標準token費率估算約 **US$0.0094**；這不是已核對帳單，未驗證帳戶tariff、cache-write、地域／service tier加價、稅與credit。[官方模型費率](https://developers.openai.com/api/docs/models/gpt-6-luna)

這些時間包含網路與remote queue／inference，不含source準備、評分、完整mapping或Canonical Acceptance，也沒有remote GPU量測。小樣本p95與順序RTT不能推算公司Qwen3／vLLM、高頻容量或production SLO。

## 採用決策與接續

**保留局部成功證據，不選candidate1作完整holdout challenger。** 類型／角色接點與數學／code保真仍有實質失敗，五個selected來源單位也尚未執行；G2仍未全面通過。

下一步先將這些失敗分成來源角色／typed契約、原生scope與模型語義三層，選一個可跨案例驗證的改善假設登記為第2組配置，保持原36項、五項未執行工作及四個既有正例可對照。一次只改一類，不直接修特定identifier／prime／答案，也不因語意錯誤就放寬拒絕規則。公司候選、GPU、完整Canonical整合與高頻負載仍待驗；holdout維持未啟用。

[整體檢查](pdf-core-g2-context-api-2026-10-15/validation.json)與[artifact manifest](pdf-core-g2-context-api-2026-10-15/artifacts.json)保存本輪證據及前輪未變範圍。

[結論摘要已寫回 #84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6195331080)，本文只加入摘要連結，44個feature rows保持原樣，issue維持OPEN；[寫回紀錄](pdf-core-g2-context-api-2026-10-15/ticket-update.json)保存exact readback及hash。
