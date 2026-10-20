# W2 V3：官方 heading 規則全因子消融

只寫本目錄；round2 語料、oracle、native inputs 與 conversion 輸出唯讀。對所有已成功論文的同一份原始 baseline deepcopy，分別執行 bookmark／numbering／style 的全部八組官方設定。`use_font_style=True` 與所有數值參數保持官方既有預設，不作每篇例外或僅對退化案例調整。

`b0-n0-s0` 必須與 baseline model-normalized JSON 完全一致；`b1-n1-s1` 對既有 30 篇必須與 round2 官方結果一致。原始 JSON 的 Core-load alias/default normalization 差異獨立保存。

三十篇重用 round2 保存的 native font pages／outline；六篇若新增成功，才用相同版本 native parser 補 font inputs（parser_threads=1，render／bitmap／remote fetch／local fetch 全關）。不執行 conversion、神經模型或模型下載。

評分直接重用凍結的 round2 heading evaluator 和 oracle：唯一 normalized title＋PDF page 匹配，只有 `IN_SCOPE` 會評；paragraph／subparagraph run-in 另列，不把缺匹配當成真漏。家族採 oracle 已保存的 template family，保留原 jobs.json family 字串以便交叉核對。

每篇／每組保存完整 document JSON／Markdown、diff、heading list、source heading 逐案評分與 options。逐組核對完整 diff 是否只有 heading.level、文字序列／orig／provenance／原生 parent 是否保留。原生 parent 不會重建為語意章節樹。

`run_ablation.py` 的八組／evaluator／transition assert 自檢已通過。依主線要求，在影像關閉控制 PASS 前不執行消融。

## 完成結果

控制已 PASS；36 篇×8 組共 288 組完成。全組完整 diff 只有 heading.level；文字順序／orig／provenance／原生 parent 均保留。all-off 等於 Core-load 後的 image-free baseline；舊 30 篇的 all-rules 與 round2 去除影像後的官方結果相同。

| bookmark/numbering/style | 相對 baseline 修好 | 新壞 |
|---|---:|---:|
| 000 | 0 | 0 |
| 001 | 5 | 176 |
| 010 | 181 | 40 |
| 011 | 181 | 81 |
| 100 | 175 | 0 |
| 101 | 177 | 61 |
| 110 | 232 | 17 |
| 111 | 232 | 33 |

同一份凍結 oracle 的 IN_SCOPE 評估中，bookmark-only（100）是無新增退化且修好最多的組合。這是候選排序，沒有部署；來源 UNKNOWN／無 oracle 的標題不在此「零退化」範圍。主結構共 467 個：baseline correct177／level error254，100 correct352／level error79，111 correct376／level error55；各組另有 strict missing33／role error1／ambiguous2，不將 missing 視為真正漏內容。完整按家族與失敗轉移見 [results.md](results.md)、[summary.json](summary.json)。

首批 240 組 stage 僅使用文字／font／outline，但 deepcopy 保留了未使用的 image metadata。依主線指示，僅清除 round3 自有 artifact 的 image 欄、設 None，沒有重跑 stage；已逐檔驗證所有非 image 欄相同與 Markdown bytes 相同，保存 [image-cleanup.json](image-cleanup.json)。後續六篇 48 組則在建立 stage 輸入前清除所有 image 欄。所有 288 組保存結果與 36 個 baseline-imagefree.json 均無非空 image 欄。

Core load 的 alias/null normalization 與 stage 差異分開。P10／P20 原始 saved document 含超出頁面邊界的 provenance bbox，Core load 分別 clamp 79／143 個 bbox coordinate 欄位；完整列在各篇 inputs.json 的 source_to_core_normalization_diff。這些不是 heading stage 的修改，但屬輸入資料邊界，不能宣稱原始 raw bbox 逐值未變。
