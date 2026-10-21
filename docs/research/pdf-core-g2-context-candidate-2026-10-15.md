# PDF core G2：通用 context 候選與回填回歸

日期：2026-10-15（Asia/Taipei）。承接[固定評估規則](pdf-core-g2-eval-freeze-2026-10-15.md)及 [#84](https://github.com/davidlinnnn/data-ingestion/issues/84)。**第一組通用候選已完成來源盤點、輸入生成及舊輸出回填回歸。四個既有正例沒有新增結構性誤拒，但新輸入尚未執行模型；目前不能選為 holdout challenger 或宣稱 F13／F14 品質通過。**

本輪只使用已曝光的 controls／SEAL／WikiSkill／DGM provider；六份新 holdout PDF 未開啟。沒有修改正式 pipeline、模型權重或前輪輸出，也未重新調整已否決的 token 保留規則。

## 一組方法，先登記再跑

實驗登記 (`pdf-core-g2-context-candidate-2026-10-15/experiment.json`)固定第一組候選及成功／退化判準；執行設定 (`pdf-core-g2-context-candidate-2026-10-15/execution-config.json`)在資料執行前記錄程式 hashes、3× render、2pt padding與24px fragment separator。這是最多三組開發配置中的第一組，沒有依結果調整門檻或新增第二組。

通用 planner (`pdf-core-g2-context-candidate-2026-10-15/candidate.py`)不依文件名稱、case ID、特定 ref 編號或答案字串作選擇：

- 盤點全部 body text、code與formula；原生文字是否含特殊數學字元不作拒絕門檻。這保留候選覆蓋，但未證明能辨識所有真正公式。
- Formula picture需有唯一互指 parent／child關係、全部直接 children為formula且同頁，才取 parent＋所有child的union，保留外層picture身分及子項來源。
- 相鄰同 parent、同頁code可共享完整context；每個job仍只有自己的target。不能將七行合併模型輸出硬塞給單一註解item，造成正文重複。
- 完整、無重疊字元範圍的跨頁段落保留原fragment順序；同頁多fragment的語意／欄位邊界未明者明列abstain，不推定可以拆正文／標題。
- Context永遠不因此成為該job的覆寫範圍；相鄰段落／公式的context條件固定，不為SEAL案例另加特例。

七個 synthetic assert checks核對名稱／字元不影響選擇、座標平移、ownership、code連續context、跨頁完整性及target／context分離。Selfchecks (`pdf-core-g2-context-candidate-2026-10-15/planner-selfchecks.json`)

## 實際來源盤點與輸入

獨立 evaluator在看新planner輸出前固定檢查契約 (`pdf-core-g2-context-candidate-2026-10-15/review/evaluation-contract.json`)：四份既有provider共 **1,594個原始item與60個group**；這是圖譜保留清單，不能當作1,594個已通過的來源語意測試。

| Provider | 方法盤點的項目 | Ready | Abstain | Unsupported | Envelope member |
| --- | ---: | ---: | ---: | ---: | ---: |
| WikiSkill，28頁 | 291 | 124 | 8 | 159 | 0 |
| DGM，64頁 | 371 | 139 | 45 | 187 | 0 |
| SEAL，22頁 | 142 | 118 | 5 | 19 | 0 |
| Controls，已選1頁 | 12 | 9 | 0 | 0 | 3 |
| 合計 | **816** | **390** | **58** | **365** | **3** |

816項是原生label／圖譜範圍內的planner紀錄，不是source-only公式／code oracle分母。大量picture內文字尚不具獨立段落／code的證據，因此明示unsupported；其原始內容仍保留，不能將它們從必要能力缺口中消失。

沿用前輪五個物理頁面（四份來源）生成輸入：44項紀錄中 **36組ready inputs＝27個普通段落＋6個code targets＋3個formula envelopes**；另有三個formula member由外層envelope處理，五項abstain保留。部分完整target跨過已選頁的邊界，因此實際引用8個來源物理頁面，不把它們當成八個獨立測試。36張canvas合計8,879,548 pixels，均附原頁／crop／canvas轉換、target／context refs及固定request契約。Input manifest (`pdf-core-g2-context-candidate-2026-10-15/input-manifest.json`)

重要限制直接保留：SEAL四個原生formula及混合正文／旁側標題的item34仍abstain。相鄰paragraph／formula的context規則在這五頁沒有觸發；只有兩個code jobs共享context。SEAL32沒有因此取得formula33的context或語義修正。三個controls envelope保住括號／分數線／brace，只支持裁圖完整性；這一輪未再呼叫VLM。

所有ready段落都生成request的做法也增加後續工作量：前輪選17個有字元訊號／controls的輸入，本輪準備36個不同scope的輸入。兩批不能直接當同質準確率或latency比較；若全文件都如此推論，尚需另評估成本與高頻負載。原生未emit的來源單位仍需獨立oracle才能量測偵測recall。

## 回填與17筆舊輸出回歸

Adapter (`pdf-core-g2-context-candidate-2026-10-15/adapter.py`)沿用既有serializer與strict segment parser，新增可重用的whole-target／context綁定。核對原始document／item／完整charspan／角色／member／context hashes，拒絕stale、foreign、重疊target、context誤消耗及未知內容。輸入影像、prompt／request或scope不同時必須有新推論，不能將舊成功結果搬給新裁圖。

在**原本的輸入、request與target scope**下，重放全部17筆既有API段落輸出：11筆可結構性回填，六筆因hidden child或block角色／數量不符保留。E14、E13、E04及WikiSkill362四個既有正例均仍具結構性適用性；E04的正例範圍仍只是所選code tokens／binding／numbers，不擴大為全文逐字通過。Replay結果 (`pdf-core-g2-context-candidate-2026-10-15/legacy-replay/results.json`)

本輪沒有使用已否決token gate，也沒有重現它對連字號／斷字差異造成的新增誤拒；這不是新模型準確率改善。SEAL32的舊錯誤輸出仍可能通過結構檢查，必須維持來源品質不合格；不能讓結構合法自動取得Canonical Acceptance。新36組的prompt／scope不同，**全部仍需新推論**，舊replay結果不歸到它們名下。

原始provider graph與模型回應均保留，另產生四份working Markdown與source association；未覆寫範圍的序列化literal spans保持原樣。跨job互為context可以存在，但每個來源target只有唯一覆寫owner，而且都以同一原始snapshot驗證。Adapter負例／小測驗 (`pdf-core-g2-context-candidate-2026-10-15/legacy-replay/selfcheck.json`)

## 決策與下一步

第一組方法具備可重現的source planning與結構性回填證據；**沒有選定holdout challenger，G2仍未全面通過**。同頁fragment、真實獨立公式、picture內內容、inline code角色及來源語義錯誤仍有缺口，不能把abstain／unsupported當已滿足必含能力。

接續先固定本輪新request／target契約，再於已曝光開發集進行新的候選推論及來源核對，特別核對context不重複、target全文／數學／code保真，以及成本。若要改方法，須登記下一組配置並保住適用正例，不能看holdout調參。通過適用回歸與來源品質後，才完成baseline／單一challenger lock與獨立holdout標註；六份新文件仍維持未啟用。

[獨立核對](pdf-core-g2-context-candidate-2026-10-15/review/output-review.md)、整體檢查 (`pdf-core-g2-context-candidate-2026-10-15/validation.json`)及artifact manifest (`pdf-core-g2-context-candidate-2026-10-15/artifacts.json`)保留實際範圍。沒有新模型API／GPU推論；本輪planning耗時及PNG生成不能視為公司vLLM或高頻ingest效能。完整Canonical整合、公司候選與負載仍待驗。

[結論摘要已寫回 #84](https://github.com/davidlinnnn/data-ingestion/issues/84#issuecomment-6194719552)，本文僅新增摘要連結，44個feature rows保持原樣，issue維持OPEN；寫回紀錄 (`pdf-core-g2-context-candidate-2026-10-15/ticket-update.json`)保存exact readback及hash。
