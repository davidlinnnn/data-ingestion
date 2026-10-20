"""Materialize human case review after viewing all 20 frozen source page images."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def main():
    audit = HERE / "audit"
    selected_bytes = (audit / "selection.json").read_bytes()
    selected = json.loads(selected_bytes)["cases"]
    decisions = [
        ("E01", "TP", "原圖先左欄摘要、Introduction再右欄；輸出先右欄When deeper networks，再Abstract。另texts/43把p1左欄have also直接接p2左欄are comparably good，原本應接p1右欄greatly benefited。確認錯序與跨頁錯接。"),
        ("E02", "TP", "原圖先左欄摘要與Introduction；輸出先右欄methods to first generate，再Abstract。左欄More recent approaches like R-CNN use region proposal被接上p2 making predictions，應接p1右欄methods to first generate。"),
        ("E03", "FP", "原頁decoder段落自左欄底自然續至右欄post-net layer...；texts/27保留正確順序與內容。來源anchor分段與rank-gap告警把合法continuation誤稱混段。"),
        ("E04", "FP", "頁圖References中的arXiv preprint arXiv:1808.04444是完整書目，非頁邊stamp。凍結樣本保存raw告警；analysis-v2已將eligible_pdf_margin=false，主家具數不計它。"),
        ("E05", "FP", "備援anchor把頁首Published as...、標題及第一作者串成一句。頁首正確被分到furniture，不能將此anchor缺失稱正文漏句。另見Jimmy Lei Ba作者跨頁接入Algorithm1，獨立記為實際錯序／混段，非作者消失。"),
        ("E06", "FP", "原圖Figure5(b)的subcaption存在；texts/243是picture child，未混入正文段落。以body layer+text label忽略ancestor造成原告警；analysis-v3修正正文分類。其label仍text而非caption，另保留角色差異。"),
        ("E07", "TP", "原頁Task條件只出現一次，Markdown表格兩欄各重複一次相同Task。原native table colspan2的匯出展開造成重複；並非兩個來源實例。"),
        ("E08", "TP", "原頁sub-agent calls...naturally discarded...為連續正文。texts/67句中插入圖中文字LLM Context Window，接著圖中清單與caption，再由texts/85續句。詞仍在但正文被圖內容打斷，確認錯序／混入；不能解讀成整句文字全漏。"),
        ("E09", "TP", "原頁附錄含完整有從屬編號的prompt清單；JSON保留picture children，但Markdown只輸出image placeholder，找不到fully end-to-end等內容。確認文字出口漏必要附錄內容。來源anchor尾端2.是抽句邊界誤差，另記；不據它宣稱數字2本身被漏。"),
        ("E10", "FP", "原頁Appendix for BERT...是置中加粗標題，Docling section_header角色正確；LaTeX prose抽取誤收標題造成role mismatch。"),
    ]
    control_notes = [
        "跨欄BERT句保留；Semantic Textual Semilarity原PDF即如此，非新錯字；前後順序正確。",
        "整句compression敘述與原頁一致，前後CNN段落順序正確。",
        "原頁第三項contribution及其後In-depth analyses仍同一list item，無從屬錯置。",
        "152-layer及while still having lower complexity條件與對象保留；本句與同段3.57%敘述順序正確。",
        "跨欄5 out of 8與up to 21x保留；同段8.4x、6.1x、76.3%→83.0%及+6.7%亦一致。",
        "ConvS2S線性、ByteNet對數的對應對象保留，前後Transformer句順序正確；另於同頁其他段記F13。",
        "large/small patches的localization/context條件保留，前後順序正常。",
        "convex global minimum／non-convex local minimum對應完整，無條件對調。",
        "remains frozen及only skill repository and metadata的限制完整，未漏only。",
        "batch noise、learning rate、held-out gate與slow/meta momentum各對象及條件完整，順序正常。",
    ]
    verdict = {sid: (v, note) for sid, v, note in decisions}
    for i, note in enumerate(control_notes, 1):
        verdict[f"C{i:02d}"] = ("TN", note)
    cases = []
    for row in selected:
        v, note = verdict[row["sample_id"]]
        assert Path(row["page_image"]).exists()
        cases.append(dict(sample_id=row["sample_id"], stratum=row["stratum"], job_id=row["job_id"],
                          page=row["page"], result=v, reason=note, page_image=row["page_image"],
                          reviewed="Original full-page PNG + source anchor/LaTeX location + native item/Markdown + nearby sentence order"))
    result = dict(selection_sha256=hashlib.sha256(selected_bytes).hexdigest(),
        scope="20 conditional case checks; TP means a Q4 defect was found, not necessarily the automatic category was exact. Raw-candidate FP includes E04 already excluded by the margin eligibility fix.",
        flagged={"n":10,"TP":5,"FP":5,"UNKNOWN":0}, unflagged={"n":10,"TN":10,"FN":0,"UNKNOWN":0},
        limitations="非全體FP/FN率；沒有標正確案例的anchor以外全文無錯結論。E08是錯序混入而非文字全漏；E09的anchor尾端編號有oracle邊界誤差。", cases=cases)
    save(audit / "results.json", result)
    confirmed = [
        ("F-cvpr_resnet", [1,2], "YES", "YES", ["E01"], "右欄提前＋跨頁正文錯接"),
        ("F-cvpr_yolo", [1,2], "YES", "YES", ["E02"], "右欄提前＋跨頁正文錯接"),
        ("F-iclr_adam", [1,2], "YES", "YES", ["E05"], "作者Jimmy Lei Ba與下一頁Algorithm1說明錯合併；不是作者漏失"),
        ("P-05-2602.08234v2", [22], "YES", "UNKNOWN", ["E07"], "Markdown把單一colspan任務句重複兩次"),
        ("P-07-2504.15228v2", [4,12], "YES", "YES", ["E08","E09"], "圖中文字插入正文句中；附錄prompt被當image而Markdown漏文字"),
        ("F-icml_imagetransformer", [5], "YES", "YES", ["S01"], "正文depen-與dence間插入圖中文字及整段Figure2 caption"),
        ("P-01-2608.27454v1", [7,8], "YES", "YES", ["S02"], "跨頁正文strongest competing與method間插入Table1 caption並併入同段"),
        ("P-17-2506.10943v1", [4], "YES", "YES", ["S03"], "正文self-edits與are sampled間插入Algorithm1標題及流程"),
    ]
    jobs = json.loads((HERE / "jobs.json").read_text())["jobs"]
    manual = []
    for job in jobs:
        found = next((c for c in confirmed if c[0] == job["id"]), None)
        manual.append(dict(id=job["id"], F01_Q4=found[2] if found else "UNKNOWN", F02_Q4=found[3] if found else "UNKNOWN",
            confirmed_pages=found[1] if found else [], audit_cases=found[4] if found else [],
            reason=found[5] if found else "未完成整篇逐內容核對；機器零告警不能宣稱NO"))
    save(HERE / "manual-verdicts.json", dict(meaning="YES=已確認阻擋；NO=已完整檢查的宣稱範圍無阻擋；UNKNOWN=證據不足。", papers=manual))
    save(audit / "supplementary.json", dict(note="失敗定位後的追加驗證；不併入凍結十加十oracle抽查分母。",
        cases=[dict(id="S01", job_id="F-icml_imagetransformer", page=5, itemref="#/texts/108", continuation="#/texts/117",
                    page_image=str(audit/"F-icml_imagetransformer-p5.png"), result="CONFIRMED_Q4", fragment="simpler depen- Local 1D Attention Figure 2. ... dence across channels"),
               dict(id="S02", job_id="P-01-2608.27454v1", page=8, itemref="#/texts/139", continuation="#/texts/142",
                    page_image=str(audit/"P-01-2608.27454v1-p8.png"), result="CONFIRMED_Q4", fragment="strongest competing Table 1 | Method comparison ... method across all models"),
               dict(id="S03", job_id="P-17-2506.10943v1", page=4, itemref="#/texts/96", continuation="#/texts/106",
                    page_image=str(audit/"P-17-2506.10943v1-p4.png"), result="CONFIRMED_Q4", fragment="in which self-edits Algorithm 1 Self-Adapting ... are sampled from" )]))
    save(HERE / "inline-math.json", dict(category="F13 / A branch", source_candidates=5180,
        confirmed_flattening_count=2, exhaustive=False, count_basis="僅已看頁圖確認的occurrences；5180是來源候選，不能當flattening次數。",
        occurrences=[dict(job_id="F-nips_attention", page=2, itemref="#/texts/14", source_file="introduction.tex", source_line=3,
                          source_offset=2208, source="$h_t$", output="h t", defect="subscript flattened", affects_F01_F02=False),
                     dict(job_id="F-nips_attention", page=2, itemref="#/texts/14", source_file="introduction.tex", source_line=3,
                          source_offset=2258, source="$h_{t-1}$", output="ht − 1", defect="subscript flattened", affects_F01_F02=False)]))
    print("20 frozen + 3 supplementary page images reviewed; 5 TP / 5 FP; 10 TN / 0 FN; 8 F01 YES / 7 F02 YES; no full-paper NO")


if __name__ == "__main__":
    main()
