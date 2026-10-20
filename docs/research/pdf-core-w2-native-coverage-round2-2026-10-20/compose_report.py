"""Combine frozen measurements and separately recorded manual decisions."""
import collections
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(rel):
    return json.loads((HERE / rel).read_text())


def table(headers, rows):
    esc = lambda x: str(x).replace("|", "／").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(esc, headers)) + " |",
                       "| " + " | ".join("---" for _ in headers) + " |"] +
                      ["| " + " | ".join(map(esc, r)) + " |" for r in rows])


def percent(a, b):
    return f"{100*a/b:.2f}%" if b else "—"


def structural_counts(heading_job, version):
    return collections.Counter(h["status"] for h in heading_job.get(version, {}).get("headings", [])
                               if h["reference"]["command"] != "paragraph")


def main():
    rows = load("analysis/summary.json")
    manual = {r["id"]: r for r in load("manual-verdicts.json")["papers"]}
    heading = load("heading/assessment.json")
    hj = {r["id"]: r for r in heading["jobs"]}
    resources = load("resources.json")
    res = {r["id"]: r for r in resources["papers"]}
    families = collections.defaultdict(list)
    perpaper, combined = [], []
    pageverdicts = []
    for r in rows:
        rid = r["id"]
        m, rr = manual[rid], res[rid]
        good = r["metric_status"] == "SCORED_CANDIDATES"
        before, after = structural_counts(hj[rid], "baseline"), structural_counts(hj[rid], "official")
        fields = dict(id=rid, title=r["title"], set=r["set"], family=r["family"],
                      selected_pages=r["selected_pages"], completed_pages=r["selected_pages"] if good else 0,
                      status=r["conversion_status"], trusted_prose=r["trusted_prose"],
                      found=r.get("body_or_md_found"), missing=r.get("missing"), duplicate=r.get("duplicate"),
                      aligned=r.get("md_order", {}).get("aligned") if good else None,
                      lis_outside=r.get("md_lis_outside"), mixed=r.get("mixed_paragraphs"),
                      column_jumps=r.get("column_jumps"), furniture=r.get("furniture_contamination"),
                      captions=r.get("classes", {}).get("caption") if good else None,
                      footnotes=r.get("classes", {}).get("footnote") if good else None,
                      heading_baseline=dict(before), heading_official=dict(after),
                      F01_Q4=m["F01_Q4"], F02_Q4=m["F02_Q4"],
                      wall_seconds=rr["conversion_wall_seconds"], peak_rss_gib=rr["sampled_peak_tree_rss_bytes"]/2**30)
        combined.append(fields)
        families[r["family"]].append(fields)
        cap, foot = fields["captions"], fields["footnotes"]
        perpaper.append([rid, r["title"], r["family"], f"{fields['completed_pages']}/{r['selected_pages']}",
            f"{fields['found']}/{r['trusted_prose']} ({percent(fields['found'],r['trusted_prose'])})" if good else "UNKNOWN",
            fields["missing"] if good else "—", fields["duplicate"] if good else "—",
            f"{fields['lis_outside']}/{fields['aligned']} ({percent(fields['lis_outside'], fields['aligned'])})" if good else "—",
            fields["mixed"] if fields["mixed"] is not None else "UNKNOWN", fields["furniture"] if good else "—",
            f"{cap['in_body']}/{cap['trusted']}" if good else "—", f"{foot['in_body']}/{foot['trusted']}" if good else "—",
            f"{before['level_error']}→{after['level_error']}" if before or after else "UNKNOWN",
            m["F01_Q4"],m["F02_Q4"],f"{rr['conversion_wall_seconds']:.2f}" if rr['conversion_wall_seconds'] is not None else "截斷",
            f"{fields['peak_rss_gib']:.2f}"])
        for page in load(f"analysis/{rid}/pages.json"):
            pageno = page.get("page", page.get("page_no"))
            override = pageno in m["confirmed_pages"]
            pageverdicts.append(dict(id=rid, page=pageno,
                F01_Q4=m["F01_Q4"] if override else "UNKNOWN",
                F02_Q4=m["F02_Q4"] if override else "UNKNOWN",
                basis=m["reason"] if override else "未逐內容完整核對；機器候選見原pages.json"))
    assert len(combined) == 36 and sum(r["selected_pages"] for r in combined) == 715
    assert sum(r["completed_pages"] for r in combined) == 499 and len(pageverdicts) == 715
    assert sum(r["F01_Q4"] == "YES" for r in combined) == 8
    familyrows, familydata = [], []
    for family, papers in families.items():
        good = [p for p in papers if p["status"] == "success"]
        sumv = lambda name: sum(p[name] or 0 for p in good)
        q = lambda field: "/".join(str(sum(p[field] == value for p in papers)) for value in ("YES","NO","UNKNOWN"))
        capbody = sum(p["captions"]["in_body"] for p in good)
        captotal = sum(p["captions"]["trusted"] for p in good)
        footbody = sum(p["footnotes"]["in_body"] for p in good)
        foottotal = sum(p["footnotes"]["trusted"] for p in good)
        data = dict(family=family, papers=len(papers), selected_pages=sum(p["selected_pages"] for p in papers),
            completed_pages=sumv("completed_pages"), anchors=sumv("trusted_prose"), found=sumv("found"), missing=sumv("missing"),
            duplicate=sumv("duplicate"), lis_outside=sumv("lis_outside"), aligned=sumv("aligned"), mixed=sumv("mixed"),
            mixed_unknown_papers=sum(p["mixed"] is None for p in good), furniture=sumv("furniture"),
            caption_in_body=capbody, caption_trusted=captotal, footnote_in_body=footbody, footnote_trusted=foottotal,
            heading_before=sum(p["heading_baseline"].get("level_error",0) for p in good),
            heading_after=sum(p["heading_official"].get("level_error",0) for p in good),
            F01_Y_N_U=q("F01_Q4"), F02_Y_N_U=q("F02_Q4"))
        familydata.append(data)
        capcorrect=sum(p["captions"]["correct_role"] for p in good)
        cappicture=sum(p["captions"]["picture_text_separate"] for p in good)
        footcorrect=sum(p["footnotes"]["correct_role"] for p in good)
        familyrows.append([family,len(papers),f"{data['completed_pages']}/{data['selected_pages']}",
            f"{data['found']}/{data['anchors']} ({percent(data['found'],data['anchors'])})",data['missing'],data['duplicate'],
            f"{data['lis_outside']}/{data['aligned']} ({percent(data['lis_outside'],data['aligned'])})",
            str(data['mixed'])+("＋Adam UNKNOWN" if data['mixed_unknown_papers'] else ""), data['furniture'],
            f"{capcorrect}+圖內{cappicture}/{captotal}；入文{capbody}",f"{footcorrect}/{foottotal}；入文{footbody}",f"{data['heading_before']}→{data['heading_after']}",q("F01_Q4"),q("F02_Q4")])
    for name, value in [("combined-papers.json",combined),("family-summary.json",familydata),("page-verdicts.json",pageverdicts)]:
        (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
    headers=["篇 ID","論文","family","完成／選頁","anchor found／trusted","漏候選","重候選","LIS外／唯一對齊","混段候選","家具候選","caption入正文／trusted","footnote入正文／trusted","heading level錯 before→after","F01 Q4","F02 Q4","conversion wall秒","RSS GiB"]
    (HERE/"per-paper.md").write_text("# W2 第2回合逐篇表\n\n機器欄均為候選；Q4 YES表示人工已確認阻擋，UNKNOWN不代表通過；沒有整篇NO。RSS_stop沒有輸出，以—表示，未當全漏。LIS分母為Markdown唯一對齊anchors。\n\n"+table(headers,perpaper)+"\n")
    with (HERE/"per-paper.tsv").open("w",newline="") as f:
        writer=csv.writer(f,delimiter="\t"); writer.writerow(headers); writer.writerows(perpaper)
    familytable=table(["family","篇","完成／選頁","anchor found／trusted","漏候選","重候選","LIS外／對齊","混段候選","家具候選","caption正確角色+圖內／trusted；入正文","footnote正確角色／trusted；入正文","heading level錯前→後","F01 Y/N/U","F02 Y/N/U"],familyrows)
    valid=[r for r in rows if r["metric_status"]=="SCORED_CANDIDATES"]
    anchors=sum(r["trusted_prose"] for r in valid); found=sum(r["body_or_md_found"] for r in valid)
    aligned=sum(r["md_order"]["aligned"] for r in valid)
    cap=collections.Counter(); foot=collections.Counter()
    for r in valid:
        cap.update(r["classes"]["caption"]); foot.update(r["classes"]["footnote"])
    startup_cpu=sum(load(p.name)["cpu_seconds"] for p in HERE.glob("initialization-*.json"))
    report=f'''# W2 原生論文版型覆蓋：第2回合結果

36篇／715頁皆已按凍結順序嘗試，30篇／499頁成功；6篇／216頁在RSS守門停止，零重試。S0、CPU4、batch1、模型與enrichment關閉設定維持不變。全量conversion監督程序wall為{resources['execution_wall_seconds']:.2f}秒（13分38秒），沒有進入修復或再跑。這不是整體通過率：人工已確認F01阻擋8篇、F02阻擋7篇；其餘分別28／29篇UNKNOWN，整篇NO均0。

## 1. 按layout family彙總

本表以封存LaTeX模板／原凍結family登錄；P的article但模板不明與其他模板保留獨立組，沒有硬歸入已證實family。F8種family各2篇、164頁全部完成。完成／選頁欄揭露失敗篇範圍；其他機器欄只以成功輸出為分母。機器告警尚含oracle誤報，不可直接當改義失敗數。Y/N/U指有無已確認Q4阻擋。

{familytable}

成功輸出的可信正文anchors為{anchors}，找到{found}（{percent(found,anchors)}）；漏候選67、重複候選4、Markdown LIS外19/{aligned}（{percent(19,aligned)}），native LIS外18。漏候選中47在所有native可見文字／Markdown也找不到，20仍在其他角色；Adam備援oracle佔45個漏候選，已抽查出跨角色混句的誤報，不能宣稱45句真漏。

L→R→L告警0，僅適用可取得獨立欄位與可信來源順序的頁面，Adam為UNKNOWN；這不涵蓋R整欄先於L的錯誤，ResNet與YOLO由LIS抓出。混段4為rank-gap候選，Tacotron2已有合法continuation誤報；未將4全判Q4失敗。家具頁邊候選0，335個raw告警大多為書目arXiv字串，保存供查核，不計入主家具數。

caption可信{cap['trusted']}，找到{cap['found_visible_or_md']}，正確caption label {cap['correct_role']}、圖內文字獨立保存{cap['picture_text_separate']}、入正文{cap['in_body']}、其他角色未分開{cap['role_not_separate']}；footnote可信{foot['trusted']}，找到及正確footnote角色{foot['correct_role']}，入正文{foot['in_body']}。分母稀疏，不能外推所有caption／footnote均正確。

## 2. 逐篇及逐頁結果

完整36篇表見[per-paper.md](per-paper.md)／[TSV](per-paper.tsv)，機器與人工合併資料見[combined-papers.json](combined-papers.json)。715頁人工證據狀態見[page-verdicts.json](page-verdicts.json)，每篇`analysis/<id>/pages.json`保存逐頁候選；跨頁anchor可涉及兩頁，不可相加當全篇分母。

資源失敗為P03、P06、P10、P16、P18、P20（25、29、30、64、18、50頁）。沒有document輸出，不做heading後處理，品質全UNKNOWN。RSS失敗不可解讀為內容漏216頁。原始PDF／來源hash、URL見[jobs.json](jobs.json)及[oracle/source-manifest.json](oracle/source-manifest.json)。P20來源全取得，16篇新下載、4篇沿用已取得bytes；F來源hash全符合凍結。

## 3. 主要失敗類型與stage

下表按機器候選數排序；各類數量單位不同，不可加成總失敗數。代表頁與片段的零推論trace及完整stage證據見[diagnostics/](diagnostics/)。每類最多5個代表頁，未修conversion。

| 類型 | 數量／證據範圍 | 代表頁及片段 | 定位 |
| --- | --- | --- | --- |
| 標題level | baseline212候選；官方後32 | BERT p2的2.1等subsection原level1；另見heading五代表頁 | baseline未做hierarchy；官方bookmark／numbering／style規則有改善及退化 |
| 正文出口漏候選 | 67 anchors，含Adam45個備援候選；部分其實錯序／角色誤置 | Adam p1→2作者接Algorithm1；P07 p4句中LLM Context Window、p12附錄prompt只剩image；P17 p4 self-edits…Algorithm1…are sampled | Adam reading-order/paragraph merge；P07 layout picture角色＋reading-order/merge；P17 algorithm標題角色與merge |
| caption未與正文分離 | 33個正文污染anchors；非33個獨立事件 | ImageTransformer p5 depen-…Figure2…dence；P01 p8 competing…Table1…method；P14 p15獨立text圖說；YOLO p8為圖內subcaption FP | layout caption標記／reading-order／paragraph merge；獨立text誤label與真混段分開 |
| 正文錯序 | MD LIS外19／native18 anchors | ResNet p1 When deeper networks先於Abstract；YOLO p1 methods to first generate先於Abstract；Adam p1作者接p2演算法 | 正常分欄框進predictor後排成右欄先，後續merge跨頁接錯；Adam有錯合併 |
| RSS失敗 | 6篇／216頁 | 代表與頁尺寸／圖片檢查見resource-failures；沒有異常超大紙張的證據 | 未保存到perpage trace，確切layout/OCR/table stage UNKNOWN，不能聲稱已證實memory leak |
| 重複 | 4個anchors，集中P05 | p22 Task只印一次，Markdown colspan2展開兩欄重複；另p23–24 | native table merged-cell到Markdown serialization；非reading-order |
| 混段告警 | 4候選 | Tacotron2 p2 decoder／post-net自然續欄，屬FP；其他ACM候選仍待語義核對 | oracle段落定位／rank-gap啟發式限制，不全算merge缺陷 |

F13 inline-math另立[inline-math.json](inline-math.json)：全來源有5180個候選位置；已看頁圖確認Attention p2兩次下標攤平（`h_t`→`h t`、`h_{{t-1}}`→`ht − 1`），歸A分支，不影響F01/F02。2是已確認下限，5180不是錯誤次數，未宣稱完成逐公式語義驗收。

## 4. Oracle抽查與限制

以整篇LaTeX展開順序為主；選頁以PDFium字流定位，不用其順序改寫LaTeX。全36篇可信正文6097、caption528、footnote37；正文uncertain3478、範圍外167。成功30篇的分母為4841；失敗6篇剩餘1256個可信anchors不參加內容評分。source freeze SHA256 `17c02e47c9e11fabdeb996b2d7327d3326b45feff80baa3125218693cd518c4e`。

固定10個標錯raw候選、10個標正確案例後才看頁圖，selection SHA256 `7d0d71cc21d52f4a3759bdb2d25b5854c20d929a0a426725914b6e507f9eca1d`。十錯候選5 TP／5 FP；十正確案例10 TN／0 FN；UNKNOWN0。這是條件案例抽查，不是全體誤報／漏報率。E04是保留raw告警且在抽樣時已標不符合頁邊資格，不冒充最終主家具告警。E08／E09確有阻擋，但自動「漏句」分類不精確，分別有圖文插入與anchor尾端清單編號邊界誤差。

五個FP：合法跨欄延續（Tacotron）、書目arXiv非家具（BERT）、PDF字流把header/title/author混成一句（Adam）、圖內subcaption被忽略ancestor誤當正文（YOLO）、LaTeX prose誤收附錄標題（BERT）。分析器落實頁邊身分與picture/table ancestor的兩次修正均保留舊版及[analysis-change.md](analysis-change.md)，source oracle與audit選樣沒有改動。

完整20案逐一理由／原頁圖／輸出refs見[audit/results.json](audit/results.json)及[selection.json](audit/selection.json)。另外3個失敗定位追加頁圖見[audit/supplementary.json](audit/supplementary.json)，不併入十加十的FP/FN分母。純字元正規化可掩蓋負號／格式差異，只用作定位；已抽查否定、條件、數值、對象，但稀疏anchors零告警不證明全文無錯。宏、條件編譯、列表／boxed prompt、float、footnote、分段、跨頁與圖中文字仍是主要oracle風險。

## 5. Heading baseline與官方後處理

30個成功輸出全保存official JSON／Markdown；只用現有套件的`HeadingHierarchyModel.assign_heading_levels`，以原PDF native font／outline補輸入，沒有重跑conversion或模型推論。28篇有可評IN_SCOPE headings。381個section/subsection/subsubsection：baseline正確140、level錯212、missing候選27、role錯1、ambiguous1；官方後正確320、level錯32，其餘不變。

199個level error→correct，19個correct→error，原13個仍錯，淨減180。19個退化全是section被下沉；不能直接全面啟用後稱修好。另136個paragraph strict missing中131個有正文prefix，27個structural missing中20個也有正文prefix；它們是run-in／角色／精確匹配限制，不可報成163個內容漏失。共685個level欄位變更，30篇全為level-only、沒有新增heading、沒有重建semantic parent。逐項及五代表頁見[heading/assessment.json](heading/assessment.json)、[heading/transitions.json](heading/transitions.json)與[heading/README.md](heading/README.md)。

## 6. 耗時與RSS

| 量測 | p50 | 最大／合計 |
| --- | --- | --- |
| 每頁pipeline residence（499頁） | {resources['residence_wall_seconds']['p50']:.3f}秒 | {resources['residence_wall_seconds']['max']:.3f}秒 |
| 每頁各stage service wall合計（499頁） | {resources['stage_service_wall_seconds']['p50']:.3f}秒 | {resources['stage_service_wall_seconds']['max']:.3f}秒 |
| 每頁存活期間process-tree RSS峰值（499頁） | {resources['page_sampled_peak_tree_rss_bytes']['p50']/2**30:.3f} GiB | {resources['page_sampled_peak_tree_rss_bytes']['max']/2**30:.3f} GiB |
| conversion監督程序（含失敗及worker啟動／保存） | — | {resources['execution_wall_seconds']:.3f}秒wall |
| 成功30篇conversion（不含保存） | — | {resources['successful_conversion_wall_seconds']:.3f}秒wall；{resources['known_conversion_cpu_seconds']:.3f} CPU秒 |
| 已知CPU秒含6次pipeline初始化 | — | ≥{resources['known_conversion_cpu_seconds']+startup_cpu:.3f}秒；6篇被kill的CPU時間未保存，不能假報完整總和 |
| 全次最高RSS／最低host available | — | {resources['peak_sampled_tree_rss_bytes']/2**30:.3f}／{resources['minimum_host_available_bytes']/2**30:.3f} GiB |

Residence是preprocess開始到assemble完成，含queue且可跨頁重疊，不含全篇reading-order；不可相加當全量wall。RSS為0.1秒抽樣的整個worker process tree，非單頁獨占配置量。守門在觀測超8 GiB後kill；實際取樣峰8.230 GiB短暫超額，沒有聲稱全程≤8。主機available未低4 GiB，沒有timeout或預算停止。逐頁與逐篇資料見[resources.json](resources.json)；失敗頁時間沒有假造。

## 7. 只限官方選項的後續候選（未執行）

| 候選 | 理由與限制 |
| --- | --- |
| `PdfPipelineOptions.queue_max_size`降低（現100） | 減少pipeline queue同時保有的頁面／影像；六次RSS停止使其值得優先驗證，尚未證實可消除峰值。CPU4／batch1仍可維持。 |
| `generate_page_images=False`、`generate_picture_images=False`，必要時降低`images_scale`（現兩者True、scale2） | 使用者文字出口不一定需要保存高倍率影像；可能減少持有影像記憶體。會改變影像artifact／圖片匯出，必須另行驗證，不能當本輪已有效。 |
| `heading_hierarchy_options`的`use_bookmarks`／`use_numbering`／`use_style`官方開關 | 本輪199改善來源為bookmark144、numbering55；19退化為numbering10、style9。可列bookmark優先、numbering/style消融候選，會犧牲部分改善，不能宣稱通用修正或重建parent。 |
| `PdfPipelineOptions.use_reading_order_separators=False`（目前True） | 直接對應本輪`ReadingOrderOptions.use_page_separators`，且保存的shape bboxes非空。可驗證幾何separator是否影響predictor；無證據保證可修ResNet／YOLO，也可能傷害正常頁。 |

選項依據是固定安裝版官方原始碼`docling/datamodel/pipeline_options.py`及`standard_pdf_pipeline.py`，精確本機連結見[diagnostics/method.md](diagnostics/method.md)、[resource-failures.md](diagnostics/resource-failures.md)、[heading/README.md](heading/README.md)。本版本未找到可直接停用paragraph merge、修正colspan Markdown重複或預設Markdown圖子文字漏出的public pipeline開關，不把這些誤稱調參即可解決。

沒有推薦未公開heuristic補丁、OCR實驗、模型升版、VLM／API或掃描資料。原生多欄仍有已證實F01/F02阻擋；資源失敗與oracle盲區也尚未排除，因此本輪不足以宣告第一版profile達到全文Q4。

## 可重現性與停止點

方法凍結[registration.json](registration.json)、[metrics.md](metrics.md)、runner[run_full.py](run_full.py)、[effective-options.json](effective-options.json)、[runtime-identity.json](runtime-identity.json)、[execution.json](execution.json)。模型離線載入既有artifact；所有enrichment false、remote services false、CPU4、三batch1。失敗未重試。成功篇各有`result.json`、`document.json`、`document.md`、raw layout、private shapes、stage events及timings，diagnostic replay不呼叫backend或learned inference。

研究檔案均在本新目錄，未改既有目錄、Git index、commit、push或GitHub留言；未開holdout／R1資料。已停在主線要求回報檢查點，沒有執行候選修正。
'''
    (HERE/"report.md").write_text(report)
    print(f"report + 36-paper table + {len(familydata)} families + 715 page verdicts written")


if __name__ == "__main__":
    assert percent(1,4)=="25.00%" and percent(0,0)=="—"
    assert "a／b" in table(["x"],[["a|b"]])
    main()
