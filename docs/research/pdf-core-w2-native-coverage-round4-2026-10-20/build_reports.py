"""Render final evidence-driven W2 handoff. No inference or prior-directory writes."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text())


def table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |", *["| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in row) + " |" for row in rows]])


def main():
    semantic = load("comparison/V4-adjudicated.json")
    limits = load("selected-limitations.json")
    resource = load("resources.json")["runs"][0]
    metric = load("comparison/metric-summary.json")
    outline = load("heading-outline.json")
    mapper = load("mapper/summary.json")
    heading = load("heading/V4-assessment.json")
    names = {
        "reading_order_or_object_association": "正文／署名／prompt 對象錯序",
        "caption_or_algorithm_splices_body": "caption／圖／algorithm 插斷正文",
        "native_text_duplication_noise_or_furniture": "原生字流重複、圖字／頁外字與家具污染",
        "empty_text_orig_available": "formula 空 text，orig 有必要內容",
        "picture_children_export_suppression": "picture children 已有原生文字但出口省略",
        "markdown_colspan_expansion": "Markdown colspan 展開重複",
    }
    category_rows = []
    for c in limits["categories"]:
        distribution = "；".join(f'{f["family"]} {f["documents"]}篇/{f["affected_job_pages"]}頁' for f in c["families"])
        category_rows.append([names[c["category"]], c["events"], c["documents"], c["affected_job_pages"], distribution, c["destination"]])
    family_rows = [[f["family"], f["documents"], f["pages"], f["classifications"].get("CONFIRMED_BLOCKING", 0), f["classifications"].get("CLEAN_AFTER_ADJUDICATION", 0), f["classifications"].get("UNKNOWN", 0), f["affected_job_pages"]] for f in limits["families"]]
    no_outline = [j["id"] for j in outline["jobs"] if not j["has_outline"]]
    route83 = [c for c in limits["categories"] if c["destination"] == "#83"]
    docs83 = {case["job_id"] for c in route83 for case in c["cases"]}
    pages83 = {(case["job_id"], p) for c in route83 for case in c["cases"] for p in case["pages"]}
    decision = f'''# W2 最終決策紀錄：#84 的 F01–F03 研究交付

日期：2026-10-20。範圍為凍結 Set F 16 篇／164 頁與 Set P 20 篇／551 頁，共 36 篇／715 頁 born-digital 論文。W2 於本回合收斂，交 W3；沒有更動正式 Profile、Docling、pipeline、Git index 或 GitHub。

## 選定設定

保留 **StandardPdfPipeline + PyPdfiumDocumentBackend、Heron、use_reading_order_separators=True、官方 bookmark-only heading**。Heron revision `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8`；heading `enabled=True/use_bookmarks=True/use_numbering=False/use_style=False`，其餘數值沿用官方預設。未改動的 `use_font_style=True` 在 `use_style=False` 的關閉規則下不啟用 style heuristic。CPU4、batch1、TableFormer accurate/cell matching 與 RapidOCR v6 small 均沿用 S0；`do_ocr=True` 亦原樣保留，未另做掃描或 OCR 消融。公式、code、picture description/classification、chart 等 enrichment 及遠端服務全部關閉。套件固定 docling-slim 2.132.0／docling-core 2.99.0，沒有下載模型或安裝套件。

V1（separators=False）、V2（Egret）維持不採用。V4 官方預設 ThreadedDoclingParseDocumentBackend 雖完整修好原 26 件中的 **{semantic['full_fixed_groups']} 件**，但新增 **{semantic['new_blocking_groups']} 組**經頁圖確認的阻擋，故依「零新增阻擋且至少修好一件」規則 **不採用**。不以機器 anchor 找到率上升取代語義裁定。詳見 [V4 報告](report.md)、[逐事件／135 變動候選裁定](comparison/V4-adjudicated.json)。這是已測官方選項中全域採用的取捨，並非宣稱其他官方版本永遠無解。

**研究時 generate_page_images=False、generate_picture_images=False 只為記憶體安全。正式 Profile 必須開啟這兩項影像輸出，供 F06 使用；記憶體由正式 core 的 group5 分組處理。** 本研究不實作 group5。R3 兩篇影像開關等價控制僅證明該控制樣本的文字、label、結構、閱讀順序、Markdown 與評分未變，不證明圖片功能等價、全語料峰值記憶體相同，亦不是 V4 backend 等價控制。[繼承控制的來源與範圍](controls-equivalence.json)。[effective options](selected-effective-options.json) 是 V4 研究執行的設定；選定 Profile 使用相同 S0/options 組合但 backend 保留 PyPdfium，正式兩項影像開關恢復 True。

## F03：bookmark-only 的覆蓋範圍

26 篇有 PDF outline，10 篇沒有。467 個可評 section/subsection/subsubsection，baseline：177 正確／254 層級錯／33 strict missing／1 role error／2 ambiguous；bookmark-only：**352／79／33／1／2**，175 個轉正確、0 個由正確轉錯。所有改善都來自有 outline 組；對缺 outline 文件無效。

|組別|篇數（有可評標題）|bookmark-only 正確|層級錯|strict missing|role／ambiguous|仍有任一上述候選的篇數|
|---|---:|---:|---:|---:|---:|---:|
|有 outline|26（25）|311|8|33|1／2|10|
|無 outline|10（9）|41|71|0|0／0|9|

無 outline 清單：{', '.join(no_outline)}。Adam 沒有可評結構標題，不能當全對；有 outline 的 Matrix Calculus 亦無可評結構標題。層級錯分布於 14 篇；strict missing 分布 9 篇，role error 1 篇，ambiguous 2 篇，這些篇數可重疊。缺 outline 的 9 篇可評文件全部仍有層級不符。

79 個 level error 包含可能的全篇一致層級偏移，33 個 strict missing 只是凍結唯一匹配規則未對上，不能直接改稱必要文字真漏或 Q4 改義。此處如實列 F03 結構缺口；**沒有把 19 篇有標題候選當成 19 篇 Q4 阻擋，也沒有宣稱其他文件 F03 全文驗收通過**。另有 197 個 paragraph/subparagraph 命令不在此結構分母，與正文是否漏失不同。完整逐篇與定義見 [heading-outline.md](heading-outline.md)、[heading-outline.json](heading-outline.json)。#83 qualification 應保留這項限制；自訂 numbering/style 後處理只能列為可選方案，沒有實作或授權為 Profile。

## 已知阻擋與根因去向

選定組合保留原 26 件確認事件；本回合另人工發現 P20 p25、27、30、31、33 的 5 個既有重複 caption 事件。這些原已存在於 baseline，沒有列為 V4 新壞，也沒有改動原 26 件的修復分母。最終已知 **{limits['events']} 件／{limits['confirmed_documents']} 篇／{limits['affected_job_pages']} 個 job-pages**。分母是本文涵蓋的 36 篇，不把未選 Set F 後續頁納入。相同頁上的多個事件只計一次；各類篇數／頁數不可直接相加。

{table(['根因類別','事件','篇','頁','family 分布（篇／頁）','交接'], category_rows)}

其中 #81 為 4 件／4 篇／6 頁的出口映射可修證據；#83 為 {sum(c['events'] for c in route83)} 件／{len(docs83)} 篇／{len(pages83)} 頁，尚無已證實可全域安全採用的官方方案。後者部分事件在拒採的 V1/V2/V4 個別改善或修好，但不能將有新增阻擋的變體當正式解法。native duplication/noise 這一類不全是同一 clipping 機制：部分來源 PDF 有舊／隱藏字流，PyPdfium 合併 bbox 再取字會放大重複；p48 等未完整證明 clipping 根因。重複已在原生 orig／cells，不能全歸給 Markdown serializer。stage 與逐頁證據沿用 R3，加上 [backend 原始碼／五處核對](diagnostics/backend-notes.md)、[新增既有 caption 證據](comparison/newly-discovered-baseline.json)。

可選自訂方案僅供使用者裁定：float/caption 邊界後處理、跨頁句子保留可追溯續接、頁外／clipping 文字過濾與兩欄順序校正。這些都涉及刪字／重排風險，W2 沒有實作，也不把它們當作已解限制。標題 heuristic 的無退化組合只有本次選定 bookmark-only；不加單篇例外或數值調參。

{table(['family','篇','頁','CONFIRMED_BLOCKING','CLEAN_AFTER_ADJUDICATION','UNKNOWN','確認受影響頁'], family_rows)}

Pilot 的 family 使用 R3 已保存的來源／模板判定；Pilot-other/unknown 與 general arXiv（article; template uncertain）明保留不確定性，不硬歸到八個受控 family。[逐篇清單、每類事件與頁](selected-limitations.json) 保存全部 36 篇。

## #81 交接：最小匯出原型的證據與邊界

只讀原始 DoclingDocument JSON、零推論，全部 36 篇已套用：[原型與結果](mapper/README.md)、[四案逐 item 證據](mapper/four-case-evidence.json)。產生自訂 mapped.json 及可表達 span／uncertainty 的 MD(raw HTML)/HTML，沒有修改正式 mapper 或原 DoclingDocument。

|規則|代表事件與可回收資訊|已驗證的修復範圍|
|---|---|---|
|空 text 回退 orig，原位置交付並標角色不確定|Adam p12 texts/419 定義量詞及公式；P16 p25 task IDs|必要字詞可回收；P16 60 IDs 可取，35 個為回退。沒有證明公式、上下標、左右欄／清單關係完整正確|
|picture children 文字另成 picture-native channel，與 C supplement 分開|SICA p12 pictures/4、5，28 text items、21 list markers|第二框 text 1439／orig 1488，補 marker 後交付 1488；原出口省略可修。圖內文字不混正文，C supplement 未執行；不重建原生語義順序|
|native table_cells 單次交付、保留 row/col span|SkillRL p22–24 的 4 個 colspan 重複 instance|4 個已知 serializer 重複實例各交付一次；不是所有原生表格布局已正確|

影響量：366 個 orig 回退 text items（30 篇）；226 個 picture 框含 10,265 個原生 text items（36 篇）；238 個 table items、6,723 native cells，其中 74 表／26 篇含 282 個 merged cells。主要 item refs 聯集 830；加 picture descendants 為 11,095，不能當作語義段落或修好事件數。

所有來源 text/cell refs 及渲染 refs 各交付一次、來源 SHA 不變。**0 新增同 ref 重複不等於跨 ref 無語義重複**：來源 2,290 組同篇不同 ref 相同完整字串被保留。64 個 fallback items 含控制字元，明示不確定。所有 picture children 交付也暴露 16 個低字量框／4 篇；高字量圖仍可能只是軸標／數字，未逐字驗收噪聲。8 個原生重疊表格用 TABLE_LAYOUT_UNCERTAIN 單次 cell 清單，避免偽造欄位關係。純文字／會剝除 HTML 的下游未驗證。這些風險是 #81 正式 mapper 必須接手的界線，**不據原型將任何整篇改判通過**。

## 與 Q4 / Canonical Acceptance 的關係

{limits['confirmed_documents']}／36 篇（{limits['confirmed_documents']/36:.1%}）已有至少一個經頁圖確認、會改變意思或符合 Q4 明列家具／重複／必要資訊漏失的缺陷，故選定組合的原始 native/Markdown 交付無法讓這些文件通過 Canonical Acceptance。這是此凍結開發／pilot 語料中已知受影響的比例，**不是產品整體失敗率或自創通過門檻**。這 {limits['affected_job_pages']} 頁為已確認範圍，不是全語料缺陷頁的完整普查。

其餘 23 篇為 CLEAN_AFTER_ADJUDICATION，表示所有自動 F01/F02 候選已裁定且未見阻擋，並附已知 incidental 檢查；不是逐字完整驗收，也不能由此宣稱 Canonical Acceptance 23 篇通過。F03 尚有上述結構候選；數學、圖像內容與未被 anchor 覆蓋的文字仍有資格驗證限制。純行內數學／下標攤平另歸 F13，不以此單獨否決 F01/F02；若同時漏必要定義、條件或對象（如 Adam/P16），仍是 Q4 阻擋。

oracle 為凍結整篇 LaTeX prose anchors（含附錄），caption/footnote 分開，Adam 是 PDFium text-layer fallback；稀疏／唯一性／正規化、float/algorithm scope、符號編碼與 clipping 都有盲點。尤其 caption 重複和家具 margin gate 會漏報，本回合 5 個新增既有事件正是反例。v3 保留不變；新判定另存，不回寫 oracle 或舊分析器。沒有據「anchor 全找到」斷言全文完整。

## 稽核與完成範圍

V4 36/715 全成功、單一逐篇 CPU4 worker、零重試、12 GiB RSS／主機可用 4 GiB 守門；pipeline wall {resource['wall_seconds']:.2f} 秒，conversion CPU {resource['measured_conversion_cpu_seconds']:.2f} 秒（另初始化 CPU {resource['measured_initialization_cpu_seconds']:.2f} 秒），峰值 {resource['peak_tree_rss_bytes']/1024**3:.2f} GiB，取樣最低主機可用 {resource['minimum_host_available_bytes']/1024**3:.2f} GiB。[resources.json](resources.json)。36 份 PDF、44 個 frozen oracle 檔案、v3 分析器與註冊 runner/backend source hash 檢查 PASS；[verification.json](verification.json)。只把 dormant supported_engines 集合序列化順序正規化，未忽略有效設定值。

所有產物只在本 round4 新目錄；沒有開 holdout、碰 R1、下載模型、API/VLM、commit、push 或 GitHub 留言。W2 在此停止，W3 與 #81/#83 依上述證據接手；正式交付與任何自訂後處理由使用者裁定。
'''
    (HERE / "decision-record.md").write_text(decision)
    check_rows = [[r["source_rootcause_group"], r["job_id"], ','.join(map(str,r.get("affected_pages", []))), r["semantic_verdict"]] for r in semantic["baseline_group_checks"]]
    new_rows = [[g["group_id"], g["job_id"], ','.join(map(str,g["affected_pages"])), g["variant_reason"]] for g in semantic["new_groups"]]
    family_comparison = [[f["family"], f["fixed_groups"], f["partial_groups"], f["new_blocking_groups"]] for f in semantic["families"]]
    metric_rows = []
    for f in metric["families"]:
        b,v = f["baseline"],f["V4"]
        metric_rows.append([f["family"], v["pages"], f'{b["body_or_md_found"]}/{b["trusted_prose"]} → {v["body_or_md_found"]}/{v["trusted_prose"]}', f'{b["missing"]}→{v["missing"]}', f'{b["duplicate"]}→{v["duplicate"]}', f'{b["md_lis_outside"]}→{v["md_lis_outside"]}', f'{b["mixed_paragraphs"]}→{v["mixed_paragraphs"]}'])
    paper_rows = []
    for p in metric["papers"]:
        b,v = p["baseline"],p["V4"]
        paper_rows.append([p["id"],p["family"],p["pages"],f'{b["body_or_md_found"]}→{v["body_or_md_found"]}/{v["trusted_prose"]}',f'{b["missing"]}→{v["missing"]}',f'{b["duplicate"]}→{v["duplicate"]}',f'{b["md_lis_outside"]}→{v["md_lis_outside"]}',f'{b["mixed_paragraphs"]}→{v["mixed_paragraphs"]}'])
    report = f'''# W2 round4：V4 與 mapper 可修性驗證

最終建議：**不採 V4，維持 PyPdfium + Heron + separators=True + bookmark-only heading。** 全部 36 篇／715 頁成功、零重試。依原 26 件來源事件逐一核對，完整修好 **{semantic['full_fixed_groups']}**、部分改善 **{semantic['partial_fixed_groups']}**、未完整修好 **{semantic['persisting_without_full_fix']}**；新增 **{semantic['new_blocking_groups']} 組／{semantic['new_blocking_documents']} 篇／{semantic['new_blocking_job_pages']} job-pages** 的確認阻擋，所以未符合零新增條件。原事件內的對象替換退化另外報，不藏在群組計數裡。

## 方法與凍結

V4 唯一 backend 改為 pinned 2.132.0 的 PdfFormatOption 官方預設 `ThreadedDoclingParseDocumentBackend`（docling-parse 7.22.3），並非已 deprecated 的舊 V4 alias。其餘固定選定 S0 組合、研究影像關閉；26 件均重核對 native/MD/原頁圖。凍結 v3 source-identity 比較 72 removed／63 added，共 135 rows 全部逐頁圖裁定；移除警報不直接算修好，新增警報不直接算新壞。Adam 的數學符號／algorithm scope 假警報保留明確理由。未改 oracle、分析器與舊產物。

來源：[註冊與 SHA](registration.json)、[逐件裁定](comparison/V4-adjudicated.json)、[原30篇詳細報告](comparison/original30-summary.md)、[補跑6篇詳細報告](comparison/recovery-report.md)、[backend notes](diagnostics/backend-notes.md)。F03 的 heading transitions 另列於 [heading/V4-changes.json](heading/V4-changes.json)，不與正文候選混算。

## 完整修復／新增阻擋（來源群組）

{table(['family','原26完整修好','部分改善','新增阻擋'],family_comparison)}

{table(['原事件','論文','確認頁','V4裁定'],check_rows)}

{table(['新增事件','論文','頁','經原圖核對的缺陷'],new_rows)}

指定五處字層污染 **0 件完整修好，5 件皆部分改善**：P10 p9、p26；P20 p6、p28、p48。P10 p9仍圖字插入 WebArena/Shopping 和 between/memory，p26仍數字／圖例混在正文；P20仍重複或混入舊 figure 對象。另 P20 p46 Sudoku 重複也僅部分改善。docling-parse 避免 PyPdfium 合併 bbox 再取字的一部分放大，但來源舊字串仍存在，不能宣稱 clipping 問題已解。[五處原生字流與 backend cells 追蹤](diagnostics/backend-source-spotchecks.json)。

caption 插斷：只有 P20 Table2 p11–12 這件完整修好，其餘 8 件仍在；SICA p12 prompt 出口、p13 引言／payload 順序另完整修好，P10 p10 舊圖 reviewer 任務和 P20 p6 footer 污染完整修好。P16 60 IDs 中 4 個恢復、3 個新漏，交付 25→26，但仍 34 個 formula.text 空；這是同一既有群組內的得失，不是整件修復，也不能描述成「沒有新漏」。

## 新發現的既有阻擋與 oracle 盲點

P20 p25、27、30、31、33 各一個 caption 重複事件，baseline 原生與 Markdown 原已重複，V4少一些但仍2份。這5件不列新增回歸，不加進原26修復分母；最終選定設定已知31件／13篇／40頁，交接已納入 [decision-record.md](decision-record.md) 與 [selected-limitations.json](selected-limitations.json)。詳見 [逐圖的baseline/V4/source證據](comparison/newly-discovered-baseline.json)。

本輪固定 v3 不檢查 caption 字串重複的所有實例，家具50pt margin gate亦會漏識正文區內錯放的頁首；因此 machine furniture contamination 仍0，不等於沒有家具阻擋。原圖確認的新增頁首仍照 Q4 判阻擋。沒有用匹配失敗的符號、code／formula 角色或獨立腳註單獨當語義缺陷。

## 凍結 v3 描述指標（baseline→V4；非語義結論）

正文 anchor 6024/6097（98.803%）→6036/6097（99.000%），missing73→61、duplicate4→2、MD LIS外19/5982→21/6002、混段4→6。caption528全部找到，角色正確455→460、正文內71→66；footnote37全部找到、角色正確37→36，新增角色候選逐圖裁為獨立交付／metadata問題。欄跳躍0候選不能反證已確認的 CVPR 首頁錯序；Adam mixed/column仍NOT_EVALUABLE，未當0品質通過。

{table(['family','頁','anchor找到／分母','missing','duplicate','MD LIS外','混段'],metric_rows)}

逐篇數值（每列都 conversion success，表內均 baseline→V4）：

{table(['論文','family','頁','找到／分母','missing','duplicate','MD LIS外','混段'],paper_rows)}

標題467個：選定B-only 352正確／79層級錯／33 strictmissing／1role／2ambiguous；V4 351／79／33／4／0。correct→role兩件：SICA p15 ExampleTraces被頁首、MD不交付（F03內容損失，但未證成語義改義），P10p9 4.4變text（完整獨立文字仍在，未證從屬改義）。其餘ambiguous/missing轉換不當作整體修復。[逐項評分](heading/V4-assessment.json)與原30／6篇獨立heading review保留。這不是凍結v3正文指標的一部分。

## mapper 與最終交接

三條最小 JSON-only 匯出規則已套全部36篇。Adam定義、P16 IDs、SICA prompt原生文字皆可交付；SkillRL4個已知colspan重複實例可單次交付。未宣稱任何整篇因此通過Q4。366orig回退／226picture框／10,265picture文字項／282mergedcells；主要item聯集830。所有來源text/cells單次交付，但來源跨ref重複、64控制字元、低字量圖字及8重疊表格仍需qualification。完整原型、單位定義、四案證據和風險見 [mapper/README.md](mapper/README.md)。

正式 Profile 必須重開 page/picture images 供F06，group5處理記憶體。已知限制與#81交接、#83資格驗證、Q4受影響13/36（36.1%）的精確適用範圍全部在 [decision-record.md](decision-record.md)；其餘23篇CLEAN不是全文Canonical Acceptance通過。

## 時間與記憶體

36 conversions，715 pages；逐篇worker總wall **{resource['wall_seconds']:.2f}s**（{resource['wall_seconds']/60:.2f}min），其中conversionwall {resource['conversion_wall_seconds']:.2f}s。conversionCPU {resource['measured_conversion_cpu_seconds']:.2f}s，初始化CPU {resource['measured_initialization_cpu_seconds']:.2f}s。每頁stage service p50/max **{resource['stage_service_seconds']['p50']:.3f}/{resource['stage_service_seconds']['max']:.3f}s**；含佇列的residence p50/max {resource['residence_seconds']['p50']:.3f}/{resource['residence_seconds']['max']:.3f}s，不可累加當wall。每頁取樣所屬程序treeRSS p50/max **{resource['perpage_tree_rss_bytes']['p50']/1024**3:.2f}/{resource['peak_tree_rss_bytes']/1024**3:.2f}GiB**，不是每頁獨占記憶體；host取樣可用最低 {resource['minimum_host_available_bytes']/1024**3:.2f}GiB。[完整資源](resources.json)。

沒有失敗或重試。36PDF與44oracle files、v3、backend、runnerhash與有效設定檢查306項PASS：[verification.json](verification.json)。所有產物限本R4。W2完成，停在此檢查點，交W3；未commit/push/GitHub留言、未開holdout/R1、未下載模型。
'''
    (HERE / "report.md").write_text(report)
    print(json.dumps(dict(decision_record="decision-record.md", report="report.md", known_events=limits["events"], affected_pages=limits["affected_job_pages"])))


if __name__ == "__main__":
    main()
