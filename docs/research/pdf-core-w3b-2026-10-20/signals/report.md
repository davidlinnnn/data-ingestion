# Stage 5：自動 verified 訊號與人工標籤交叉檢查

固定 primary 規則在本批資料沒有可判個案：公式須 a∧b∧c、code 須 a∧b；獨立第二重建器 b 的同來源完整範圍配對為 0，因此 primary verified=0、NO_DECISION=全部個案。這是 **覆蓋不足，不能宣稱錯誤率為 0 或已校準**。

較弱的 a∧c 在原 W3 50 個公式 block 中驗證 2 個有人工標籤的 block，其中 SICA 1 個已確認改義；誤驗 1/2，exact 95% CI [0.01257911709342505, 0.9874208829065749]。可 render 與高字元一致，仍不足以證明必要數學意義保留。

## 分母與來源

共保留 207 筆原人工單位作稽核清單，**不把它們當成 207 個互相獨立或隨機樣本**。W3 50 是原整個 source block，沒有展開成逐行假標籤；21 code 排除 4 alignment-error、2 UNKNOWN。R1 原 44 mixed group、額外 28 math/6 image math/28 inline code/1 procedure、29 whole-description 分層呈現，可能互相重疊，不能加總成整體準確率。R1保留原strict grade（含typed coverage/placement與符號、字型角色要求），不是以本輪Q31/Q33重判；W3 code是Q4 literal faithfulness，description是whole semantic obligations，各自criteria不混用。43 個 code-font 證據不冒充獨立語義標籤。

| stratum | 原筆數 | label 可用 | native 可用 | a known | b known | c known | 實際 render | prediction groups* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1_ADDITIONAL_CODE_AND_PROCEDURAL_FILE_CONTENTS | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| R1_ADDITIONAL_IMAGE_MATH | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| R1_ADDITIONAL_INLINE_CODE | 28 | 28 | 0 | 0 | 0 | 0 | 0 | 25 |
| R1_ADDITIONAL_MATH | 28 | 28 | 28 | 7 | 0 | 28 | 28 | 28 |
| R1_DESCRIPTION29 | 29 | 28 | 0 | 0 | 0 | 0 | 0 | 29 |
| R1_OLD44 | 44 | 44 | 13 | 11 | 0 | 9 | 9 | 13 |
| W3_CODE21 | 21 | 15 | 17 | 8 | 0 | 0 | 0 | 20 |
| W3_FORMULA50 | 50 | 43 | 50 | 44 | 0 | 40 | 29 | 50 |

*Prediction groups 僅計可明確歸屬的已觀察預測，不把未能綁定的原 group 當成模型沒有輸出。W3 code21 有20個 groups；ImageTransformer 兩公式block共享一個per-ref預測，雖composite集合不同仍相關。原R1group常夾帶全job片段，未能以source scope唯一綁定者保留UNKNOWN。

## 固定規則結果

| stratum / rule | known-label 可判 | verified known | TP / FP / FN / TN（error-positive） | error precision / recall | pass precision / recall | verified error | 95% CI |
|---|---:|---:|---|---|---|---|---|
| W3_FORMULA50 / a | 37 | 2 | 10 / 25 / 1 / 1 | 0.286 / 0.909 | 0.500 / 0.038 | 0.500 | [0.01257911709342505, 0.9874208829065749] |
| W3_FORMULA50 / c | 35 | 25 | 3 / 7 / 7 / 18 | 0.300 / 0.300 | 0.720 / 0.720 | 0.280 | [0.12071668850406662, 0.49387682180625553] |
| W3_FORMULA50 / a&c | 34 | 2 | 8 / 24 / 1 / 1 | 0.250 / 0.889 | 0.500 / 0.040 | 0.500 | [0.01257911709342505, 0.9874208829065749] |
| W3_FORMULA50 / primary | 0 | 0 | 0 / 0 / 0 / 0 | NA / NA | NA / NA | NA | None |
| W3_CODE21 / a | 8 | 0 | 2 / 6 / 0 / 0 | 0.250 / 1.000 | NA / 0.000 | NA | None |
| W3_CODE21 / c | 0 | 0 | 0 / 0 / 0 / 0 | NA / NA | NA / NA | NA | None |
| W3_CODE21 / a&c | 0 | 0 | 0 / 0 / 0 / 0 | NA / NA | NA / NA | NA | None |
| W3_CODE21 / primary | 0 | 0 | 0 / 0 / 0 / 0 | NA / NA | NA / NA | NA | None |
| R1_OLD44 / a | 11 | 2 | 3 / 6 / 1 / 1 | 0.333 / 0.750 | 0.500 / 0.143 | 0.500 | [0.01257911709342505, 0.9874208829065749] |
| R1_OLD44 / c | 9 | 9 | 0 / 0 / 2 / 7 | NA / 0.000 | 0.778 / 1.000 | 0.222 | [0.028144973477898197, 0.600093573716312] |
| R1_OLD44 / a&c | 8 | 2 | 1 / 5 / 1 / 1 | 0.167 / 0.500 | 0.500 / 0.167 | 0.500 | [0.01257911709342505, 0.9874208829065749] |
| R1_OLD44 / primary | 0 | 0 | 0 / 0 / 0 / 0 | NA / NA | NA / NA | NA | None |
| R1_ADDITIONAL_MATH / a | 7 | 4 | 0 / 3 / 0 / 4 | 0.000 / NA | 1.000 / 0.571 | 0.000 | [0.0, 0.6023646356164746] |
| R1_ADDITIONAL_MATH / c | 28 | 28 | 0 / 0 / 0 / 28 | NA / NA | 1.000 / 1.000 | 0.000 | [0.0, 0.12343611850026383] |
| R1_ADDITIONAL_MATH / a&c | 7 | 4 | 0 / 3 / 0 / 4 | 0.000 / NA | 1.000 / 0.571 | 0.000 | [0.0, 0.6023646356164746] |
| R1_ADDITIONAL_MATH / primary | 0 | 0 | 0 / 0 / 0 / 0 | NA / NA | NA / NA | NA | None |

所有單訊號與組合、全部 cohort/eligible/verified/unknown-label 分母、固定 sensitivity grid、各原始訊號連續/二元 ROC 與每個固定 .95 單訊號/組合規則的binary operating-point ROC原始點在 `metrics.json`。NO_DECISION 不列為已證實錯誤；excluded/UNKNOWN-label verified另列，不進混淆矩陣。沒有 verified 時 error/CI 為 null，不能報0%。

## 訊號與限制

- a：原 PDFium 字元 bbox 中心落入已綁定 source bbox union；公式與R1按原 physical char index保序。code 沿 Stage4 封存的 glyph+x 分行排序及等寬字距重建空白，故其空白不是原始 byte 字串；這會造成保義 code 也被拒，不能把所有拒絕稱語義錯。assembled orig 只可診斷，未冒充原PDF或第二模型。
- R1 額外單項只允許 frozen complete expected（不看prediction）在source bbox原始glyph唯一exact定位。重複、非exact、whole-group的一個關鍵字都不拆、不模糊對齊。R1 scan-pages只讀既有metadata/grade，未開原scan PDF，沒有OCR實驗。
- b：同PDF SHA、完整human-unit scope、不同模型且非orig-copy；必須相同非空physical visible-character集合才能配對。Terminal式號只有locator，不能當wholeblock身份。原50公式與R1唯一PDF交集P03卻是p18 vs p2；code交集P01為W3p24/25/28 vsR1其他頁、P03為W3p23/24/25 vsR1p2。故無同範圍pair，不是「兩模型全部不一致」。額外source40的P01 p6/p23也無R1對應，不建立secondary cohort。
- c：實際本機Chrome MathML render，禁止外部網路；rawTeX支援子集的未閉brace/環境外裸&為KNOWN false，unsupported macro/未知語法/環境故障為UNKNOWN。三階段raw_tex_syntax/mathml_serialization/actual_render分開保存。沒有TeX compiler，故不稱TeX compile成功，更不稱數學保義。
- universal converter XML escaping修正保留所有&glyph；原始不合法&仍由raw syntax guard拒絕。v1 features與helpers已另存，統一修正amendment有舊新SHA；threshold、normalizer、human label皆未改。
- PDFium char index其實是UTF16 code unit；先前逐index讀單一字會丟掉supplementary math alphabet。統一decoder只在原選區內相鄰完整high/low pair合成scalar，保留兩physical indices；半pair UNKNOWN、不擴框。所有非surrogate BMP的原text（含sentinel/空字/control表示）byte保留，沒有未知font映射、手工補括號或清洗。a只是固定文字投影proxy，不能保證所有glyph/2D/角色真值。全部舊features/metrics/plots已保存，原source geometry、gold、labels、normalizer、門檻不變。W3恢復P03一個block的23pair，a分數上升但pass不變；R1 E023 a由false變true，A2-014分數上升仍false。
- R1 E023原人類F2逐字理由：Complexity identifier uses plain C rather than the source calligraphic C; equation number and relation otherwise present.（human-A-review-v3.json old_A_groups unit_id=E023）。這是R1嚴格符號/字型角色忠實度標籤，與本輪會忽略font commands的Q31核心改義界線不同。修正UTF16後a=1且c通過，仍按原R1 label計false verification；不新宣稱Q31改義、不加入W3b confirmed Q31阻擋總數。各stratum保留自身criteria，不能pool人口誤驗率。
- R1 A2-100/101原state BLOCKED_TYPED_OCCURRENCE_AMBIGUITY是同一個2required recalc.py但只有1typed的F1 coverage group，不是oracle alignment error。原label完整保留為blocking；這兩筆皆無可判features，不列為獨立預測，兩人類義務相關性已標記。
- code人工標籤主要是Q4 literal faithfulness（prompt/log/file/條件字），不能用aggregate精確率宣稱可執行邏輯檢測能力；R1 whole圖描述不是literal OCR，a/b/c皆NA，未以字元相似度代替語義真實。
- .95 是事前固定門檻；ROC以error-positive方向、全部observed risk thresholds描述，不由圖選新門檻。缺少正負任一類或無可判值時AUROC null。CI是條件binomial描述，樣本相關與purposive抽樣限制其推廣，並非部署可信度保證。

## 圖與重現

ROC by source stratum (`figures/roc-by-cohort.png`)

Fixed a threshold sensitivity (`figures/a-threshold-sensitivity.png`)

另保存PDF/SVG。`build_r1_cohort.py`、`integrate_signals.py`、`publish_signal_report.py`，全部零API/模型推論；Chrome與Matplotlib產物置於本W3b目錄。來源/labels/helper SHA在各cohort與amendment，外部exact引用讀取在 `../required-external-reference-read-log.json`。
