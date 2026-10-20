"""Render round-3 evidence tables without changing any experiment or verdict."""
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text())


def table(headers, rows):
    def cell(value):
        return str(value).replace("|", "／").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def main():
    jobs = read("jobs.json")["jobs"]
    papers = read("adjudication/papers.json")
    families = read("adjudication/families.json")
    verdicts = read("adjudication/summary.json")
    heading = read("heading/summary.json")["totals"]
    heading_results = read("heading/results.json")
    resource = read("resources.json")
    runs = {r["run"]: r for r in resource["runs"]}
    baseline = {x["id"]: x for x in read("analysis/baseline/summary.json")}
    classified_families = sorted({x["family"] for x in baseline.values()})
    metrics = {}
    for variant in ("baseline", "V1", "V2-official", "V3_B"):
        values = read(f"analysis/{variant}/summary.json")
        metrics[variant] = {
            "papers": len(values), "pages": sum(x["selected_pages"] for x in values),
            "trusted": sum(x["trusted_prose"] for x in values),
            "found": sum(x["body_or_md_found"] for x in values),
            "missing": sum(x["missing"] for x in values),
            "duplicate": sum(x["duplicate"] for x in values),
            "md_lis_outside": sum(x["md_lis_outside"] for x in values),
            "mixed_paragraphs": sum(x["mixed_paragraphs"] or 0 for x in values),
            "mixed_paragraphs_not_evaluable_papers": [x["id"] for x in values if x["mixed_paragraphs"] is None],
            "caption_in_body": sum(x["classes"]["caption"]["in_body"] for x in values),
            "footnote_in_body": sum(x["classes"]["footnote"]["in_body"] for x in values),
        }
    (ROOT / "metric-totals.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
    raw_family_rows = []
    for variant in ("baseline", "V1", "V2-official", "V3_B"):
        values = read(f"analysis/{variant}/summary.json")
        for family in classified_families:
            members = [x for x in values if x["family"] == family]
            found = sum(x["body_or_md_found"] for x in members)
            trusted = sum(x["trusted_prose"] for x in members)
            raw_family_rows.append([variant, family, sum(x["selected_pages"] for x in members),
                                    f"{found}/{trusted}", f"{100*found/trusted:.3f}%",
                                    sum(x["missing"] for x in members), sum(x["duplicate"] for x in members),
                                    sum(x["md_lis_outside"] for x in members),
                                    sum(x["mixed_paragraphs"] or 0 for x in members),
                                    sum(x["classes"]["caption"]["in_body"] for x in members)])
    raw_type_rows = []
    for variant in ("V1", "V2-official", "V3_B"):
        deltas = read(f"comparison/{variant}-changed-cases.json")
        counts = collections.Counter((x["family"], x["kind"], x["direction"]) for x in deltas)
        for family, kind in sorted({(x["family"], x["kind"]) for x in deltas}):
            raw_type_rows.append([variant, family, kind, counts[(family, kind, "removed")], counts[(family, kind, "added")]])
    (ROOT / "comparison/automatic-family-type.md").write_text(
        "# 凍結 v3 自動指標（不是語意修好／新壞）\n\n混段加總只含可評估篇；Adam 為 NOT_EVALUABLE。\n\n" +
        table(["變體", "family", "頁", "找到／可信", "覆蓋率", "漏", "重", "MD LIS 外", "混段候選", "caption 入正文"], raw_family_rows) +
        "\n\n候選刪除／新增按來源 identity 去重；沒有變動的 family／type 不列。\n\n" +
        table(["變體", "family", "候選類型", "刪除", "新增"], raw_type_rows) + "\n")
    family_rows = []
    for f in families:
        s = f["status_counts"]
        family_rows.append([f["family"], f["papers"], f["pages"], s.get("CONFIRMED_BLOCKING", 0),
                            s.get("CLEAN_AFTER_ADJUDICATION", 0), s.get("UNKNOWN", 0),
                            f["confirmed_affected_job_pages"]])
    paper_rows = []
    for p in papers:
        b = baseline[p["job_id"]]
        h = heading_results[p["job_id"]]["b1-n0-s0"]
        paper_rows.append([p["job_id"], p["family"], p["pages"], p["status"],
                           ",".join(map(str, p["confirmed_affected_pages"])) or "—",
                           f'{p["adjudicated_count"]}/{p["candidate_count"]}',
                           f'{b["body_or_md_found"]}/{b["trusted_prose"]}',
                           b["missing"], b["duplicate"], b["md_lis_outside"],
                           f'{h["versus_baseline"]["fixed"]}/{h["versus_baseline"]["new_bad"]}'])
    paper_table = table(["論文 ID", "family", "頁", "最終三類判定", "確認受影響頁", "候選裁定", "找到／可信 prose anchor", "自動漏", "自動重", "MD LIS 外", "B-only 標題修好／新壞"], paper_rows)
    (ROOT / "papers.md").write_text("# 36 篇逐篇結果\n\n" +
        "自動候選不是 Q4 判定。CLEAN 限於候選及已發現的補充缺陷，附帶凍結 oracle 的限制；不等於全文逐字驗收。P02 的作者錯序是額外發現，已納入最終判定。\n\n" + paper_table + "\n")
    family_table = table(["family（保留凍結分類）", "篇", "頁", "BLOCKING", "CLEAN", "UNKNOWN", "確認受影響頁（篇內去重）"], family_rows)
    heading_rows = []
    for combination, result in heading.items():
        v = result["versus_baseline"]
        h = result["structural_counts"]
        heading_rows.append([combination, v["fixed"], v["new_bad"], h.get("correct", 0), h.get("level_error", 0)])
    # Heading comparisons count reference headings, not papers or semantic defect events.
    heading_family_rows = []
    for family in classified_families:
        members = [j["id"] for j in jobs if baseline[j["id"]]["family"] == family]
        row = [family]
        for combination in heading:
            fixed = sum(heading_results[j][combination]["versus_baseline"]["fixed"] for j in members)
            bad = sum(heading_results[j][combination]["versus_baseline"]["new_bad"] for j in members)
            row.append(f"{fixed}/{bad}")
        heading_family_rows.append(row)
    (ROOT / "heading/family-comparison.md").write_text("# 全部 36 篇的標題規則消融\n\n每格為標題修好／新壞；b=bookmark、n=numbering、s=style。未針對單篇設例外。\n\n" + table(["family"] + list(heading), heading_family_rows) + "\n")
    resource_rows = []
    for r in resource["runs"]:
        resource_rows.append([r["run"], f'{r["successful"]}/{r["attempts"]}', r["selected_pages"],
                              f'{r["wall_seconds"]:.1f}', f'{r["measured_conversion_cpu_seconds"]:.1f}',
                              f'{r["stage_service_seconds"]["p50"]:.3f}/{r["stage_service_seconds"]["max"]:.3f}',
                              f'{r["peak_tree_rss_bytes"]/2**30:.3f}',
                              f'{r["minimum_host_available_bytes"]/2**30:.3f}'])
    recovery_rows = [[r["id"], r["pages"], r["status"], f'{r["attempt_wall_seconds"]:.2f}',
                      f'{r["peak_tree_rss_bytes"]/2**30:.3f}', r["retries"]] for r in runs["recovery"]["papers"]]
    automatic_rows = [[k, v["pages"], f'{v["found"]}/{v["trusted"]}',
                       f'{100*v["found"]/v["trusted"]:.3f}%', v["missing"], v["duplicate"],
                       v["md_lis_outside"], v["mixed_paragraphs"], v["caption_in_body"], v["footnote_in_body"]]
                      for k, v in metrics.items()]
    groups = read("adjudication/root-groups.json")
    observed_official_fixes = {
        "p02-first-author-attribution-order": "V1 完整修好，但全域新增 3 件阻擋",
        "imagetransformer-figure2-breaks-body-sentence": "V2 完整修好，但全域新增 13 件阻擋",
        "p16-task-ids-formula-role-p25": "V2 完整修好，但全域新增 13 件阻擋",
        "incidental-p03-table3-breaks-reporting-clause-p5-p6": "V2 完整修好，但全域新增 13 件阻擋",
    }
    no_fix_groups = [g for g in groups if g["group_id"] not in observed_official_fixes]
    no_fix_papers = {g["job_id"] for g in no_fix_groups}
    no_fix_pages = {(g["job_id"], p) for g in no_fix_groups for p in g["confirmed_affected_pages"]}
    remaining_rows = [[g["group_id"], g["job_id"], ",".join(map(str, g["confirmed_affected_pages"])),
                       observed_official_fixes.get(g["group_id"], "本輪未觀察到完整官方選項修復"),
                       g["output_reason"]] for g in groups]
    group_count = len(groups)
    affected_count = verdicts["confirmed_affected_job_pages"]
    (ROOT / "remaining-blockers.md").write_text("# 建議組合下仍存在的已確認阻擋\n\n" +
        f"採 Heron＋原 reading-order separators＋bookmark-only heading；heading 不改正文，以下 {group_count} 個來源事件仍保留，分布於 13 篇、{affected_count} 個確認頁。沒有證實可全域安全解決它們的本輪官方選項組合；不代表官方永無解法。\n\n" +
        f"其中 {len(observed_official_fixes)} 件曾在未採用的官方變體個別修好；其餘 {len(no_fix_groups)} 件／{len(no_fix_papers)} 篇／{len(no_fix_pages)} 頁在本輪未觀察到完整修復。SkillRL 的一個 colspan instance 有局部改善，但同群其他頁仍重複。\n\n" +
        table(["來源根因事件", "論文", "頁", "本輪官方選項觀察", "可核對的缺陷"], remaining_rows) + "\n")
    report = f'''# W2 第 3 回合：補完、裁定與官方選項全量消融

完成 Set F 16 篇／164 頁及 Set P 20 篇／551 頁。建議 Profile 保留 Heron 與 `use_reading_order_separators=True`，關閉頁面／圖片產圖，啟用官方 **bookmark-only heading**。V1 與 V2 都有已確認的新阻擋，不建議全域納入。這是研究結論與候選設定，沒有修改正式 Profile 或既有檔案。

## 1. 等價控制及 6 篇補跑

Sentence-BERT（11 頁）與 P01（28 頁）控制均通過：只遞迴排除 `image` 欄位，DoclingDocument 其他每個值完全相同；Markdown 位元組完全相同；v3 的 metrics、anchors、candidates、pages 四份結果亦逐值相同。證據：[controls-equivalence.json](controls-equivalence.json)。通過後才執行補跑。

{table(["論文", "頁", "結果", "程序 wall 秒", "峰值 RSS GiB", "重試"], recovery_rows)}

全部實際 conversion 均逐篇啟動新的 CPU4 worker，batch 1，單工共享鎖，12 GiB RSS／主機可用 4 GiB 守門；沒有 conversion 重試。30 篇沿用第二回合輸出，補齊的 6 篇採影像關閉結果。不能把記憶體下降完全歸因於產圖開關：第二回合曾長駐 worker，本回合每篇新程序也是差異。

## 2. 全部候選裁定與 36 篇判定

875／875 個自動候選已對照頁圖裁定（包含 Adam 的 45 個 fallback 漏句候選）；747 個非阻擋、128 個阻擋告警，合併相同來源事件後為 23 件。額外全文差異檢查發現的已確認缺陷也獨立納入，最終合計 **{group_count} 個來源事件、13 篇 CONFIRMED_BLOCKING、23 篇 CLEAN_AFTER_ADJUDICATION、0 篇 UNKNOWN**。若只計自動候選則是 12／24／0，不能用來蓋過已確認的額外缺陷（例如 P02 首位作者錯序）。

三個額外事件為 P02 p1 首位作者錯序、P03 p5–6 Table3 切斷 `We report the ... official ANLS`、P10 p10 頁外舊圖字串新增不可見的 reviewer 任務對象。最後一項在 V1 只是拆段移位、V2 仍完整保留，均不算修好；已加入 baseline 的事件／受影響頁，沒有改凍結 oracle 或自動候選數。

{family_table}

全部 36 篇表：[papers.md](papers.md)。逐候選頁圖、來源理由、輸出理由與共用根因：[adjudication/records.json](adjudication/records.json)、[adjudication/root-groups.json](adjudication/root-groups.json)；額外缺陷亦保留獨立來源。

`CLEAN_AFTER_ADJUDICATION` 僅表示所有自動候選都已裁定，且沒有已知阻擋；不是全文逐字驗收。Oracle 是稀疏 anchor：可信正文共 6097 個；長度、唯一性、LaTeX 清理與可對齊範圍仍有限，作者、表格／algorithm、部分 prompt、數學與短句會漏檢。Adam 的 text-layer fallback 還會把跨欄作者、標題與數學組成不實複合句。公式符號的純呈現攤平另列 F13；必要英文條件或對象遺失仍是 F01。

Adam 的部分 display／algorithm 數學確有空 formula 輸出；這些 fallback 複合 prose 告警依 D1 記為 oracle 範圍錯誤，**沒有宣稱數學內容完整，也沒有一概當成 D3 的 inline-math 呈現差異**。已保留 actual_formula_loss 與數學未驗風險；該篇本身仍因必要英文條件等缺陷列為 BLOCKING。可信 footnote 37 個全數找到且角色分離；528 個可信 caption 全數找到，仍可能切斷正文，所以「找到」與「正確分離」分別報告。

## 3. 四類失敗的零推論根因

**CVPR 首頁右欄先讀。** ResNet 與 YOLO 的來源 layout 框已分欄，錯在 reading-order predictor 先取右欄，之後段落合併擴大成跨頁錯接（兩篇各 p1–2）。關閉 separators、改 Egret 都未修好既有首頁錯序。

**caption／algorithm 與正文錯接。** Image Transformer p5 的 `depen- ... dence`、p7 的 `Amazon Mechanical ... Turk`，WikiSkill p7–8 的跨頁句與 SEAL p4 的 `self-edits ... are sampled`，在原 layout 已把獨立圖說／演算法標題標為 text；reading-order 將它放在未完正文之間，再被 paragraph merge 串起。單純 label 不正確但仍是獨立完整段落的案例，裁為 metadata 差異，沒有算 Q4 阻擋。

**prompt 框被判 picture。** SICA P07 p12 的兩個 picture 均有原生 children，`orig` 分別保留 1238／1488 個字元（第二框 `text` 1439，另有 49 個清單標記在 orig）；Markdown 省掉整框。這是匯出／映射問題，應交 #81，不能宣稱 backend 沒抽到。全 715 頁共 235 個 picture，其中 **172 個框（73.2%）含 ≥30 個非空白 PDF 原生字元，分布 146 頁／35 篇**；172 個框都有大量 native children，但僅 14 個框至少一個 substantial child 在 Markdown 可找。這是「文字密集 picture」代理統計，包含圖表文字，**不是 172 個已確認 prompt 框或漏文事件**。見 [diagnostics/report-full36.md](diagnostics/report-full36.md)。

**colspan Markdown 重複。** SkillRL P05 p22–24 的 merged cell 在 native table 唯一；官方 serializer 按展開 grid 重複輸出。最小零推論樣本：native 唯一 1、grid 2、Markdown 2、HTML 1 並保留 colspan=2，確認是固定 Markdown 交付行為，歸 #81，沒有修改抽取器或 serializer。

另外兩個實質根因不能被上面四類掩蓋。Adam p12 的英文 Definition 10.1、P16 p25 必要 task IDs 被 layout 標為 formula，官方 reading-order 將文字放入 orig 並清空 text，公式 enrichment 關閉時 Markdown 只剩 placeholder；原字仍可回收，但交付漏必要條件／對象。P10 p9／26、P20 p6／28／48 的部分舊圖中文字則已存在於 PDF 的不可見或裁切 text layer；`get_text_bounded` 的重疊框再次放大重複。P20 p6 的舊頁碼是獨立且位於 clipping rectangle 外的 glyph，漏進 orphan body，不是同一頁碼的 serializer 重複。p48 部分覆蓋機制仍未確定，不能把所有案例都稱為 clip 問題。見 [diagnostics/adam-p12-formula-role.md](diagnostics/adam-p12-formula-role.md)、[adjudication/recovery-helper/source-cell-origin.md](adjudication/recovery-helper/source-cell-origin.md)。

## 4. 官方選項消融

V1、V2 各 36 篇／715 頁，均使用影像關閉、完全相同凍結 oracle 與原版 v3 分析器。Egret 權重已在本機，使用官方 `LayoutObjectDetectionOptions.from_preset("layout_egret_medium")`，沒有下載模型；其餘 layout 設定與 baseline 逐值核對。模型檔與 preset 證據：[diagnostics/egret-medium-local.json](diagnostics/egret-medium-local.json)。

### 自動候選與語意事件分開計數

{table(["變體", "頁", "prose 找到／可信", "覆蓋率", "自動漏", "自動重", "MD LIS 外", "混段候選", "caption 入正文候選", "footnote 入正文候選"], automatic_rows)}

覆蓋率不是通過率。混段候選的 4 件來自可評估的 35 篇；Adam 的跨欄混段為 NOT_EVALUABLE，沒有當成零錯誤。V1 自動候選刪除／新增為 0／0，但 full native 與完整 Markdown 差異檢查仍發現真退化。32／36 篇逐值相同；其餘 P02、P10、P13、P18 逐段核對。**V1 修好 1 個來源事件（P02 p1 首位作者），新增 3 個阻擋事件（P18 p18、P10 p23、P10 p24–25）**；P13 p19 完整 algorithm float 移位而內容／歸屬仍清楚，裁為允許的移位，沒有算修好。P10 的保存上游 layout、parsed pages、assembled 逐值相同；兩套 reading-order 零推論重播都與各自 native／Markdown 完全一致，確認變動發生在 separator 控制的讀序與後續 merge。

V2 的自動候選刪除／新增為 **88／242**（69 個篇內頁），不是 88 個修好或 242 個新壞。其逐案語意比較與按 family／失敗類型彙總另附 [comparison/semantic-summary.md](comparison/semantic-summary.md)。

自動指標另按 family／候選類型完整列在 [comparison/automatic-family-type.md](comparison/automatic-family-type.md)，保留原先對 Pilot 模板不確定的分類，不強行併入八個已知 family。逐篇原始 v3 JSON 中保留的 F01/F02 UNKNOWN 是未改動分析器的自動輸出；最終三類判定以獨立 adjudication 為準。

### V3：全部 36 篇 × 8 組規則

下表單位是參考標題，不是論文或 Q4 事件；b=bookmark、n=numbering、s=style。全部 288 份結果只變 heading level，文字、orig、順序、實際 parent 關係不變。

{table(["規則", "修好", "新壞", "正確標題", "層級錯誤"], heading_rows)}

**bookmark-only 修好 175、新壞 0**，剩下 79 個層級錯誤、33 個 structural heading 缺項、1 個 role error、2 個 ambiguous；另有 197 個 paragraph command 未被當 heading，已分開揭露，沒有當作正文遺失。按 family 的完整八組表：[heading/family-comparison.md](heading/family-comparison.md)。

使用實際 S0 PyPdfium backend 的官方 PDFium outline extractor、`parsed_pages=None` 重評 36 篇，完整 JSON、level 與 Markdown 都與 B-only 原結果相同，確認可直接用官方 pipeline options 整合。載入 Core 會裁正 P10／P20 共 222 個 bbox 欄位；已在 heading 的 source→Core normalization 單獨記錄，stage 的「只改 level」比較起點是同一份 Core baseline。早期 240 份 stage artifact 未先清除不使用的 image metadata，後來只在本回合目錄移除 image，逐值證實其他欄位及 Markdown 不變；其餘 48 份從一開始就關閉 image。詳見 [heading/verification.json](heading/verification.json)、[heading/pdfium-integration/summary.json](heading/pdfium-integration/summary.json)。

另對 Egret 的 36 份保存輸出評估 raw 與 B-only：raw 相對 Heron 是標題修好 0／新壞 1；Egret+B 相對 Egret raw 是 178／0，相對 Heron raw 是 178／1。其中多出的 3 件包含 missing／ambiguous 的匹配轉變，沒有當成額外的語意修復。B-only 不能彌補 Egret 引入的圖說／prompt 正文阻擋；其 1029 個 v3 候選與 Egret raw 逐值相同。見 [heading/V2-bookmarks/summary.json](heading/V2-bookmarks/summary.json)、[comparison/V2-Bonly-candidate-equivalence.json](comparison/V2-Bonly-candidate-equivalence.json)。

## 5. 建議 Profile 與剩餘阻擋

建議候選設定：[recommended-profile.json](recommended-profile.json)：Heron、separators=True、產圖 False／False，heading enabled=True、bookmarks=True、numbering=False、style=False，其他 baseline 值及所有 enrichment 關閉不變。這個組合的 B-only 後處理已在同一批保存輸出全量驗證，不需要重跑 conversion；凍結 v3 的正文候選亦完全不變。

V1 的作者收益伴隨 3 個新阻擋；V2 的 task ID／caption 收益也伴隨新正文錯接與 Markdown 遺失。這些結果不足以支持全域替換。沒有對個別文件設例外，沒有調數值參數。

採建議組合後，原有 **{group_count} 件／13 篇／{affected_count} 頁** 的已確認 F01/F02 阻擋仍在；完整範圍與來源片段：[remaining-blockers.md](remaining-blockers.md)。包括兩篇 CVPR、Adam、Image Transformer、WikiSkill、P02、P03、SkillRL、SICA、P10、P16、SEAL、P20。#81 可承接 picture-child、formula-orig 與 colspan 的可用文字／Markdown 交付問題；讀序、layout label、backend clipping 污染仍需要後續解法。本輪沒有證實一套無退化的官方選項可一起解決，不能寫成「官方永遠無解」。

其中 **4 件**曾由未採用的官方變體個別修好（P02 作者、Image Transformer p5、P03 p5–6、P16 p25）；**其餘 {len(no_fix_groups)} 件，影響 {len(no_fix_papers)} 篇／{len(no_fix_pages)} 頁，在本輪尚未觀察到完整的官方選項修復**。SkillRL 一個重複 cell 有局部改善但整群仍未解。這個區分避免把「沒有安全的全域替換」誤寫成「每個個案都沒有官方選項效果」。

## 6. 時間、RSS 與重現紀錄

{table(["實際 run", "成功／嘗試", "頁次", "wall 秒（含 init）", "conversion CPU 秒", "每頁 service p50／max 秒", "峰值 RSS GiB", "主機最低可用 GiB"], resource_rows)}

實際 80 次 conversion、1685 頁次；程序 wall 合計 {resource["pipeline_wall_seconds"]:.1f} 秒，已量測 conversion＋init CPU {resource["known_conversion_and_initialization_cpu_seconds"]:.1f} 秒。每頁 service 為 stage service 時間；pipeline residence 含排隊／重疊，不能逐頁相加當全程 wall。RSS 是採樣的 process tree 峰值，不是單頁專用記憶體；完整每頁 residence、RSS、CPU 在 [resources.json](resources.json)。

保留兩個 harness 預檢錯誤：先有 2 筆 options 比較因 set 序列化順序而失敗；另有 36 筆 Egret factory init 因誤用 legacy model constant 而失敗。兩者都在 conversion／模型推論前發生，原日誌完整保留；修正型別／比較方式後才進行上表實際 conversion，沒有重試已開始 conversion 的論文。見 [preflight-correction.json](preflight-correction.json)、[v2-initialization-correction.json](v2-initialization-correction.json)。

凍結 v3 SHA256：`915f598207a20e2ede942abedd12dd707e3d3620ff9748edb95e178c801176fa`；oracle seal SHA256：`17c02e47c9e11fabdeb996b2d7327d3326b45feff80baa3125218693cd518c4e`。原始分析器未改；所有新 runner、評分、裁定、設定、圖與報告均在本回合目錄。沒有 API／VLM、沒有新模型下載、沒有開 holdout、沒有碰 R1、沒有 commit／push／GitHub 留言。完成後停止，等待主線下一步。
'''
    (ROOT / "report.md").write_text(report)
    profile = {
        "status": "research_recommendation_not_applied_to_production",
        "basis": "S0 pinned baseline, all enrichment disabled; only changes below",
        "pipeline": "StandardPdfPipeline", "backend": "PyPdfiumDocumentBackend",
        "layout": "layout_heron", "layout_revision": "8f39ad3c",
        "changes": {
            "generate_page_images": False, "generate_picture_images": False,
            "heading_hierarchy_options": {"enabled": True, "use_bookmarks": True,
                                          "use_numbering": False, "use_style": False}},
        "retained": {"use_reading_order_separators": True, "CPU_threads": 4, "batch": 1},
        "numeric_parameters": "All unchanged; official defaults preserved",
        "verification": "36 saved documents, B-only structural 175 fixed / 0 new_bad; v3 candidate delta 0/0",
        "remaining_confirmed": {"source_groups": len(groups), "papers": verdicts["status_counts"]["CONFIRMED_BLOCKING"],
                                "job_pages": verdicts["confirmed_affected_job_pages"]}}
    (ROOT / "recommended-profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"papers": len(paper_rows), "families": len(family_rows), "metrics": metrics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
