# 圖片分類 CPU 結果

2026-10-14。**DocumentFigureClassifier-v2.5 已實際跑完 CPU 圖片分類。六個具名來源的 broad type 在固定 crop 與原生 layout bbox crop 都相符；四種 chart 在兩組均進入原生 chart gate。此結果只驗分類／路由，未產生圖意或 chart 數值。**

固定模型 revision `f859dfbff5c9916cd996942d4b0db7fa25808220`，模型權重 16,378,200B，三個必要 Transformers 檔案總16,381,099B；實際 bytes／官方 LFS SHA 相符，匿名下載3.439秒。使用 Docling2.102.0、Core2.96.0、Transformers5.8.1、Torch2.14.0，所有 parameters 為 CPU／FP32，4 threads／interop1／batch1、compile=False、offline。[下載](download.json) · [實際設定](method.json) · [方法與來源界線](method.md) · [官方研究](primary-research.md)

| 同一來源 | 固定 crop：top class／score | layout bbox crop：top class／score | 兩者原生 chart gate |
| --- | --- | --- | --- |
| G1-S05 Figure2 三層與四步流程 | `flow_chart`／0.991973 | `flow_chart`／0.990066 | false |
| G1-S07 繁中操作畫面 | `screenshot_from_computer`／0.799833 | `screenshot_from_computer`／0.988124 | false |
| G1-C03 印值長條 | `bar_chart`／0.998825 | `bar_chart`／0.999672（native picture0） | true |
| G1-C04 線性軸雙系列 | `line_chart`／0.976395 | `line_chart`／0.911478（native picture2） | true |
| G1-C05 對數軸折線 | `line_chart`／0.994658 | `line_chart`／0.989655（native picture1） | true |
| G1-C06 圓餅 | `pie_chart`／0.997544 | `pie_chart`／0.999846（native picture3） | true |

這是六個來源的兩種 crop，每種一次，不能當作十二個獨立樣本或新 holdout accuracy。對照 frozen oracle 的圖類別判斷：流程圖、操作截圖、長條、折線及圓餅的 broad family 均相符。`screenshot_from_computer` 只支持「操作截圖」類別，不驗證操作步驟、文字或 manual／computer 細分類定義。分數為模型 softmax 輸出，未做信心校準，不用高分替代 source review。[固定來源](../inputs/input-manifest.json) · [Oracle 參照](../inputs/oracle-references.json)

原生組由實際 provider document 載入未修改 `PictureItem`，使用實際 layout bbox 重新 scale3 render 的圖片做 enrichment，before／after 皆保存；不是 baseline cached crop pixels，也未因此證明 bbox 含全部 required content。固定 chart panel envelopes 的標題上緣有既存裁切；沒有為 classifier 擴框或補字。[Native inventory](../layout/native-inventory.json) · [十二張輸入與上游 manifest SHA](inputs.json)

每例 [runs/](runs/) 保存完整 engine `label_ids`／26類 softmax scores、stage `meta.classification`、deprecated annotation、native chart gate 及 crop locator。六個原生 PictureItem 的 provenance／caption refs／image 等非分類欄位與 before 相同。九個離線 gate controls 驗證低分 bar／pie 也進入；flow／scatter／box／other／unknown 不進入；次佳 bar 不會 fallback。[離線檢查](check.py) · [Validation](validation.json)

**路由判斷**：這四個 chart 沒有遭 classifier 擋住，足以繼續 chart producer 比較。S05／S07 不應送進 chart extractor，但仍須交付 F11 圖意。沒有 literal unknown／no-text 類別；`other`、低 confidence 或無文字皆不能作資訊豁免。原生 chart gate 只看 top class 是否在 bar／line／pie，不看 confidence，未測來源或未見類型仍可能誤送／漏送；不得把此小樣本擴成通用可靠路由。

一個 child 一次 eager load，十二次 batch1 stage calls 全部 exit0；child wall3.982秒，load0.0678秒，各 call0.0936～0.1070秒（合計1.1595秒），0.25秒 sampled process-tree peak608,124,928B（0.5664GiB），無 timeout／memory stop。初次 sandbox process inspection 失敗在推論前0.0036秒即停止，另存 `startup-failure-*`；後續使用同一 offline bounded runner完成。OS cache 未清空，未量 p95／整文件或高頻 ingest SLO。[Supervisor observations](observations.json) · [child log](child.log)

未執行 chart VLM、數值抽取、圖片描述、OCR、全 pipeline enrichment lifecycle、Canonical 回填或 Acceptance。此分類樣本可標示已執行並通過所選 broad family 核對；F11／F12 品質仍需各自的 producer 證據。
