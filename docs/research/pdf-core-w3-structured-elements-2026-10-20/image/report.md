# W3 E0 圖像結構與交付評測

完成36篇／715頁，零新conversion、零API／VLM／模型推論。先封存source-only oracle，再於主線全域凍結後讀取E0。全部結果只寫本image目錄。

來源可得35篇，Adam只有PDF-wrapper，結構總數UNKNOWN，沒有把它算成0張圖。已知來源有220個figure/figure*、58個子figure／subfigure／subfloat、8個含圖table floats（另列）、508次includegraphics。呼叫數不是可見圖數，父圖與子圖不混算偵測率。

## Family 表

「連結」是來源caption身分片段與同頁native文字精確匹配後，存在明確picture parent／caption ref的**結構證據候選**，不是全部圖內容或caption接對圖的人工認證。「無picture」只表示來源頁沒有picture label，原生code/prompt可能仍以文字交付。UNKNOWN包含定位、條件與映射歧義，不當成漏圖或通過。

| family | 篇／頁 | 主figure已知／IN | 明確連結候選 | 無picture標籤 | 主figure UNKNOWN／OUT | 子圖已知／連結候選 | raster全bbox／partial／無交／頁外 |
|---|---:|---:|---:|---:|---:|---:|---:|
|ACL/EMNLP|5／86|35／32|22|7|3／3|0／0|81／11／0／0|
|IEEE conference|2／10|6／5|5|0|1／0|4／0|1／1／0／0|
|ACM sigconf|2／20|12／10|9|0|3／0|25／7|20／8／0／0|
|CVPR/AAAI|2／22|13／12|10|0|3／0|2／1|7／2／0／0|
|ICML|3／39|14／13|12|0|2／0|0／0|237／11／8／0|
|NeurIPS/ICLR|9／238|37／32|27|0|7／3|13／0|165／28／0／0|
|Springer LNCS|2／20|10／8|8|0|0／2|0／0|11／1／0／0|
|general arXiv|2／24|4／0|0|0|4／0|4／1|2／5／0／0|
|Pilot-other/unknown|6／167|41／38|31|4|6／0|10／4|295／21／3／3|
|general arXiv (article; template uncertain)|3／89|48／45|20|18|10／0|0／0|46／15／1／0|

全主figure：220已知來源，195在選定頁；144有explicit caption-picture連結候選、29來源頁無picture標籤、其餘39 UNKNOWN（其中17來源定位未知、1條件未知、21 native caption／child映射未知），8在選定頁外。子圖58中13有explicit link候選；其餘保留子圖定位／繼承父圖／映射限制。8個image-table floats中4可定位並連結、4 UNKNOWN。完整分子、分母與各原因：`family-summary.csv`、`E0-evaluation.json`。不把known-link比例當整體通過率。

## RAW／MAPPED 與 UNKNOWN

| 項目 | RAW | MAPPED | UNKNOWN／限制 |
|---|---:|---:|---|
| IN_SCOPE source caption身分片段交付 | 204／222 | 220／222 | 2個連native也未能身分匹配；非完整caption語義正確率 |
| 主figure explicit caption-picture候選 | 144 | 144 | 兩模式不改label/bbox／native graph |
| 子figure explicit候選 | 13 | 13 | 多panel／共享caption仍可能只有一個panel連上 |
| image-table float explicit候選 | 4 | 4 | 另4來源定位UNKNOWN |
| native picture frames | 235 | 235 | 不等於source figure數 |
| source raster object完整bbox被frame包含 | 865／980個on-page bbox | 相同 | 只證幾何涵蓋，不證向量／遮擋／實際bitmap交付 |
| raster partial／無交 | 103／12 | 相同 | clip與可見性未證者保留UNKNOWN |
| selected JSON有image payload | 0／235 | 0／235 | 原生字channel不是C圖片supplement |

Mapper只用W2三條JSON規則：empty text回退orig並標不確定、picture descendants獨立native文字channel、table native cells一次且保留span。它改善片段交付，但不修正caption關聯、paragraph merges或錯table結構。不能把回收文字當圖片內容被描述。

E0全36重用V3_B保存文件；原30篇conversion的image generation曾開、6篇關閉，不能當作新uniform-images-OFF效能benchmark。選定JSON與原conversion的235個picture provenance沒有差異（loader bbox變更0），本次幾何差異不能歸因新模型改善。

## 裁切：把白邊與必要內容分開

原PDF遞迴Form imageobjects 983個，3個bbox完全頁外；980個on-page bbox中865完整落至少一個picture框，103僅部分相交、12無交。全部保留原bbox、quad、clip計數與Form矩陣；nested Form synthetic bbox驗證PASS。這些不是「983張可見圖」，clip／舊隱藏字圖／遮擋可使物件不可見；vector也不在raster分母。

已渲染12個原來源頁、檢視source與overlay；其中10頁有實際figure、2頁是無figure的來源控制頁。抽查6個partial raster objects：Tacotron2 p3、NGCF p2、Attention p4兩圖、GradientDescent p4兩圖，縮掉的皆是白邊；原頁排除strip在1.6 scale下均0個<200灰階ink pixels，另保存50／100／250閾值原始測量。這是本樣本頁圖判斷的佐證，pixel閾值不是新接受規則，也不外推其餘partial通過。本樣本未確證必要raster像素遺失；未審的partial／無交仍UNKNOWN。頁圖審查 (`visual-audit/records.json`)、strip證據 (`visual-audit/excluded-strips-pixel-evidence.json`)。

ResNet p1是vector圖，crop完整性保留UNKNOWN；U-Net p3 photos bbox完整，但箭頭vector不由raster測量認證。P10 p26現行vector曲線被偵測，舊clip／頁外raster未入框不能直接宣稱當前圖遺失。

## 已確認的失敗與stage

1. **ImageTransformer p5 Figure2：caption未接兩panel，且插入正文。** 來源兩panel為pictures/2、/3，caption卻在text108，插斷原body「simpler depen- … dence」。RAW/MAPPED均阻擋；mapper不改merge。raw layout將caption標text，舊exact零推論reading-order trace與本次layout重播保存stage證據。
2. **P13 AgeMem p8 Figure4：圖被table吸收。** raw detector有picture8/10/12/13，官方layout postprocessor同類overlap保13，cross-type再讓table11勝出。native tables/1 rows15–16把bar/綠色增益箭頭字放進上方Table2：例如HotpotQA Base=38.36出現在row15 col5（BabyAI欄）。RAW/MAPPED均保留錯對象。這是layout postprocessing→table reconstruction，非serializer新生資料、非單純vector無法量測。

Attention p4的source Figure2共享caption只接右picture，左panel只保留其小標；記結構關聯部分不足，Q4是否改義UNKNOWN。P20 p28 Figure21則是原生code／prompt文字圖，無picture label不等於內容真缺；code正確性由另項oracle處理。

5個代表頁官方LayoutPostprocessor零推論重播，full clusters（忽略order）及geometry／label／children全與保存輸出相等；每個官方函式只forward一次，沒有模型或backend呼叫。replay (`layout-zero-inference-replay.json`)、blocking cases (`blocking-cases.json`)。stage原始碼：LayoutPostprocessor (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/utils/layout_postprocessor.py:108>`)、picture/table跨類優先 (`<<tmp>/pdf-core-native-std-20261017/venv/lib/python3.12/site-packages/docling/utils/layout_postprocessor.py:450>`)。

## 沿用W2 picture原生字頻率

W2 full36的**235個picture frames**中，172框含至少30個**原PDFium原生非空白字元**，涉及35篇／146頁；172框皆已有至少30個native descendant字元。只有14／172框在預設MD找到至少一個完整≥30字child；327個substantial child nodes中28個在MD找到。這些frame/doc/page分母來自原PDF字層幾何inventory，**不是從mapped children文字量反推**，不是圖內全文／語義正確率。MAPPED將native children放picture_native_uncertain，不作C_image_supplement。既有inventory (`docs/research/pdf-core-w2-native-coverage-round3-2026-10-20/diagnostics/picture-text-full36.json`)、[既有報告](../../pdf-core-w2-native-coverage-round3-2026-10-20/diagnostics/report-full36.md)。

來源oracle、方法與freeze原檔未修改；本報告未執行任何修正、API、conversion或模型下載／推論。
