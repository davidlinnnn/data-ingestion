"""Repair two stale R3 image locators in R4 evidence, without changing adjudication."""
import hashlib
import json
from pathlib import Path
import pypdfium2

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / "comparison/recovery-semantic-records.json"
    before = path.read_bytes()
    obj = json.loads(before)
    row = next(r for r in obj["baseline_group_checks"] if r["source_rootcause_group"] == "incidental-p03-table3-breaks-reporting-clause-p5-p6")
    old = row["page_images"]
    job = next(j for j in json.loads((HERE / "jobs.json").read_text())["jobs"] if j["id"] == row["job_id"])
    assert hashlib.sha256(Path(job["pdf"]).read_bytes()).hexdigest() == job["pdf_sha256"]
    folder = HERE / "adjudication/repaired-source-pages" / job["id"]
    folder.mkdir(parents=True, exist_ok=True)
    doc = pypdfium2.PdfDocument(job["pdf"])
    new = []
    for page_no in (5,6):
        target = folder / f"p{page_no:03d}.png"
        doc[page_no-1].render(scale=1.5).to_pil().save(target)
        new.append(str(target.relative_to(HERE)))
    doc.close()
    row["page_images"] = new
    row["evidence_locator_repair"] = dict(previous_nonexistent_locators=old, reason="R4 row had stale R3 p005/p006 filenames. Fresh source-PDF rendering only; semantic verdict, native/Markdown evidence and counts unchanged.", pdf_sha256=job["pdf_sha256"])
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    (HERE / "adjudication/evidence-link-repair.json").write_text(json.dumps(dict(input_sha256=hashlib.sha256(before).hexdigest(), output_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), group_id=row["source_rootcause_group"], old=old, new=new, adjudication_changed=False), ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(repaired_locators=2, conversion_calls=0, semantic_or_metric_changes=0)))


if __name__ == "__main__":
    main()
