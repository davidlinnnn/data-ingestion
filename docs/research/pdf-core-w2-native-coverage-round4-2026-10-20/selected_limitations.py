"""Aggregate frozen, page-confirmed selected-profile events. No conversion."""
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R3 = HERE.parent / "pdf-core-w2-native-coverage-round3-2026-10-20"

CATEGORIES = {
    "reading_order_or_object_association": [
        "adam-author-merged-into-algorithm1", "resnet-p1-right-before-left",
        "yolo-p1-right-before-left", "p02-first-author-attribution-order",
        "sica-p13-initialrequest-problem-order"],
    "caption_or_algorithm_splices_body": [
        "imagetransformer-figure2-breaks-body-sentence",
        "imagetransformer-table5-breaks-amazon-mechanical-turk",
        "p03-caption-spliced-p14", "p03-caption-spliced-p21",
        "incidental-p03-table3-breaks-reporting-clause-p5-p6",
        "seal-algorithm1-breaks-onpolicy-sentence",
        "sica-figure2-breaks-subagent-sentence",
        "wikiskill-table1-breaks-crosspage-sentence",
        "p20-table2-caption-spliced-p12"],
    "native_text_duplication_noise_or_furniture": [
        "p10-chart-label-contamination-p9", "p10-chart-numeric-contamination-p26",
        "incidental-p10-offpage-old-figure-task-object-p10",
        "P-20-2505.03335v1:furniture_in_body:00035",
        "p20-caption-duplicated-p28", "p20-caption-object-contamination-p48",
        "p20-duplicated-corrupt-body-p6", "p20-sudoku-caption-duplicated-p46"],
    "empty_text_orig_available": [
        "adam-definition101-english-omitted", "p16-task-ids-formula-role-p25"],
    "picture_children_export_suppression": ["sica-p12-prompt-export-suppression"],
    "markdown_colspan_expansion": ["skillrl-colspan-markdown-duplicates"],
}


def main():
    load = lambda path: json.loads(path.read_text())
    papers = load(R3 / "adjudication/papers.json")
    byjob = {p["job_id"]: p for p in papers}
    frozen = load(R3 / "adjudication/root-groups.json")
    mapping = {gid: cat for cat, ids in CATEGORIES.items() for gid in ids}
    assert len(mapping) == 26 and set(mapping) == {g["group_id"] for g in frozen}
    discovered = load(HERE / "comparison/newly-discovered-baseline.json")
    assert isinstance(discovered, list)
    for group in discovered:
        assert group["group_id"] not in mapping
        mapping[group["group_id"]] = "native_text_duplication_noise_or_furniture"
        paper = byjob[group["job_id"]]
        paper["status"] = "CONFIRMED_BLOCKING"
        paper["confirmed_source_groups"].append(group["group_id"])
        paper["confirmed_affected_pages"] = sorted(set(paper["confirmed_affected_pages"]) | set(group["confirmed_affected_pages"]))
        paper.setdefault("newly_discovered_preexisting_groups", []).append(group["group_id"])
    groups = frozen + discovered
    out = []
    for cat in CATEGORIES:
        members = [g for g in groups if mapping[g["group_id"]] == cat]
        docs = {g["job_id"] for g in members}
        pages = {(g["job_id"], p) for g in members for p in g["confirmed_affected_pages"]}
        families = []
        for family in sorted({byjob[j]["family"] for j in docs}):
            familydocs = {j for j in docs if byjob[j]["family"] == family}
            families.append(dict(family=family, documents=len(familydocs),
                                 affected_job_pages=sum(j in familydocs for j,p in pages)))
        out.append(dict(category=cat, events=len(members), documents=len(docs),
                        affected_job_pages=len(pages), families=families,
                        destination="#81" if cat in ("empty_text_orig_available", "picture_children_export_suppression", "markdown_colspan_expansion") else "#83",
                        group_ids=[g["group_id"] for g in members],
                        cases=[dict(job_id=g["job_id"], pages=g["confirmed_affected_pages"]) for g in members]))
    family_rows = []
    for family in sorted({p["family"] for p in papers}):
        rows = [p for p in papers if p["family"] == family]
        family_rows.append(dict(family=family, documents=len(rows), pages=sum(p["pages"] for p in rows),
                                classifications=dict(collections.Counter(p["status"] for p in rows)),
                                affected_job_pages=len({(p["job_id"], page) for p in rows for page in p["confirmed_affected_pages"]})))
    result = dict(selected_backend="PyPdfiumDocumentBackend", selected_options="Heron; separators=True; bookmark-only heading",
                  source=str(R3 / "adjudication/root-groups.json"),
                  applicability="V4 rejected for new blocking defects. B-only does not alter these body candidates/events.",
                  original_comparison_denominator=len(frozen), newly_discovered_preexisting_events=len(discovered),
                  events=len(groups), confirmed_documents=len({g["job_id"] for g in groups}),
                  affected_job_pages=len({(g["job_id"], p) for g in groups for p in g["confirmed_affected_pages"]}),
                  categories=out, families=family_rows, papers=papers,
                  scope="F01/F02 candidate adjudication and known source events; not full-word acceptance. F03 and math risks separately qualified.")
    (HERE / "selected-limitations.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("papers","categories")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
