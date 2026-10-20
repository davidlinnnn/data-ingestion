"""Freeze deterministic 10 flagged + 10 unflagged cases before page viewing."""
import hashlib
import json
from pathlib import Path
import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent
DEST = HERE / "audit"


def load(path):
    return json.loads(path.read_text())


def main():
    DEST.mkdir(exist_ok=True)
    assert not (DEST / "selection.json").exists(), "selection is immutable"
    jobs = {j["id"]: j for j in load(HERE / "jobs.json")["jobs"]}
    catalog = load(HERE / "analysis/candidate-catalog.json")
    specs = [
        ("F-cvpr_resnet", "md_lis_outside", 1),
        ("F-cvpr_yolo", "md_lis_outside", 1),
        ("F-ieee_tacotron2", "mixed_paragraph", 2),
        ("F-acl_bert", "furniture_in_body", 10),
        ("F-iclr_adam", "missing_anchor", 1),
        ("F-cvpr_yolo", "caption_in_body", 8),
        ("P-05-2602.08234v2", "duplicate_anchor", 22),
        ("P-07-2504.15228v2", "missing_anchor", 4),
        ("P-07-2504.15228v2", "missing_anchor", 12),
        ("F-acl_bert", "prose_role_or_layer_mismatch", 12),
    ]
    rows = []
    for jobid, kind, page in specs:
        c = next(c for c in catalog if c["job_id"] == jobid and c["kind"] == kind and page in c["pages"])
        rows.append(dict(sample_id=f"E{len(rows)+1:02d}", stratum="flagged", job_id=jobid,
                         page=page, candidate=c))
    controls = ["F-acl_sbert", "F-ieee_crnn", "F-acm_lightgcn", "F-cvpr_resnet",
                "F-icml_efficientnet", "F-nips_attention", "F-lncs_unet",
                "F-arxiv_gradientdescent", "P-02-2603.02766v1", "P-04-2605.23904v2"]
    for i, jobid in enumerate(controls):
        flagged = {a for c in catalog if c["job_id"] == jobid for a in c.get("anchor_ids", [])}
        anchors = load(HERE / "analysis" / jobid / "anchors.json")
        eligible = [a for a in anchors if a["kind"] == "prose" and a["anchor_id"] not in flagged
                    and len(a["markdown_offsets"]) == 1 and len(a["native_body"]) == 1
                    and a["pdf_pages"] == [2]]
        assert eligible, jobid
        anchor = eligible[len(eligible)//2]
        rows.append(dict(sample_id=f"C{i+1:02d}", stratum="unflagged", job_id=jobid, page=2,
                         anchor=anchor))
    for row in rows:
        row["pdf"] = jobs[row["job_id"]]["pdf"]
        row["page_image"] = str(DEST / f"{row['sample_id']}.png")
    payload = dict(method="audit-method.md; deterministic family/type spread; first 24 scored papers, before page-image viewing",
                   source_catalog_sha256=hashlib.sha256((HERE / "analysis/candidate-catalog.json").read_bytes()).hexdigest(), cases=rows)
    content = json.dumps(payload, ensure_ascii=False, indent=2)+"\n"
    (DEST / "selection.json").write_text(content)
    (DEST / "selection.sha256").write_text(hashlib.sha256(content.encode()).hexdigest()+"  selection.json\n")
    assert sum(r["stratum"] == "flagged" for r in rows) == 10
    assert sum(r["stratum"] == "unflagged" for r in rows) == 10
    for row in rows:
        with pdfium.PdfDocument(row["pdf"]) as doc:
            page = doc[row["page"]-1]
            assert page.get_width()*page.get_height()*1.5**2 < 8000000
            bitmap = page.render(scale=1.5)
            bitmap.to_pil().save(row["page_image"])
            bitmap.close()
            page.close()
    print((DEST / "selection.sha256").read_text())


if __name__ == "__main__":
    main()
