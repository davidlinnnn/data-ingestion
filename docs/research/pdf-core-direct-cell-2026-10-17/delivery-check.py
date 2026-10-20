"""Independent saved-output delivery audit after all four requests; never runs inference."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.types.doc import DoclingDocument, RefItem, TableItem

import adapter
import gate

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize(text):
    return " ".join(text.split())


def expected_rows(data):
    """Apply the declared pipe-table policy to complete physical cells, independently of Core.grid."""
    grid = [[None] * data.num_cols for _ in range(data.num_rows)]
    for cell in data.table_cells:
        for r in range(cell.start_row_offset_idx, cell.end_row_offset_idx):
            for c in range(cell.start_col_offset_idx, cell.end_col_offset_idx):
                assert grid[r][c] is None
                grid[r][c] = cell
    assert all(c is not None for row in grid for c in row)
    starts = {c.start_row_offset_idx for c in data.table_cells if c.column_header}
    headers = 0
    while headers in starts:
        headers += 1
    if not starts:
        headers = 1
    def displayed(cell):
        return " ".join(cell.text.splitlines())
    heading = []
    for col in range(data.num_cols):
        ancestry = []
        for row in grid[:headers]:
            value = displayed(row[col])
            if value and (not ancestry or ancestry[-1] != value):
                ancestry.append(value)
        heading.append(" - ".join(ancestry))
    return [heading] + [[displayed(c) for c in row] for row in grid[headers:]]


def audit(job):
    dest = HERE / job["name"]
    paths = [Path(job["baseline"]), dest / "output.json", dest / "document.json", dest / "document.md", dest / "bindings.json"]
    before = {str(p): sha(p) for p in paths}
    baseline = DoclingDocument.model_validate_json(paths[0].read_text())
    raw = json.loads(paths[1].read_text())
    doc = DoclingDocument.model_validate_json(paths[2].read_text())
    markdown = paths[3].read_text()
    bindings = json.loads(paths[4].read_text())
    checks, errors = {}, []
    def check(name, predicate):
        try:
            assert predicate()
            checks[name] = True
        except Exception as error:
            checks[name] = False
            errors.append({"check": name, "error": repr(error)})
    check("registered baseline hash unchanged", lambda: before[str(paths[0])] == job["baseline_sha256"])
    original = baseline.model_dump_json()
    canonical = doc.model_dump_json()
    keys = [t["target_key"] for t in job["targets"]]
    parsed = adapter.parse_response(raw, keys)
    source_targets = adapter.inventory(baseline, job["page_no"])
    provider = {t.target_key: t for t in parsed.targets}
    check("all native targets once", lambda: set(keys) == set(source_targets) == {b["target_key"] for b in bindings} and len(bindings) == len(keys))
    check("valid graph and all references", lambda: (gate.old.assert_graph(doc) is None))
    source_changed = {n.self_ref for key in keys for n in gate.old.walk(baseline, source_targets[key])}
    output_changed = {n.self_ref for b in bindings for n in gate.old.walk(doc, RefItem(cref=b["group_ref"]).resolve(doc))}
    expected_untouched = [gate.source_signature(n, baseline) for n in gate.old.walk(baseline) if n.self_ref not in source_changed]
    actual_untouched = [gate.source_signature(n, doc) for n in gate.old.walk(doc) if n.self_ref not in output_changed]
    check("non-target content and body order preserved", lambda: expected_untouched == actual_untouched)
    check("pages origin furniture preserved", lambda: doc.pages == baseline.pages and doc.origin == baseline.origin and doc.furniture == baseline.furniture)
    target_data = {}
    duplicate_captions = []
    for b in bindings:
        target, old_table = provider[b["target_key"]], source_targets[b["target_key"]]
        check(b["target_key"] + " provider manifest exact", lambda b=b, t=target: b["provider"] == t.model_dump(mode="json"))
        check(b["target_key"] + " saved envelope exact", lambda b=b, t=old_table: b["original_provenance"] == [p.model_dump(mode="json") for p in t.prov])
        check(b["target_key"] + " panel inventory exact", lambda b=b, t=target: len(b["panels"]) == len(t.panels))
        for i, (panel, refs) in enumerate(zip(target.panels, b["panels"], strict=True)):
            item = RefItem(cref=refs["table_ref"]).resolve(doc)
            title = RefItem(cref=refs["title_ref"]).resolve(doc)
            target_data[item.self_ref] = panel.data
            label = f"{b['target_key']} panel {i}"
            check(label + " raw physical cells exact", lambda p=panel, t=item:
                t.data.num_rows == p.data.num_rows and t.data.num_cols == p.data.num_cols and
                [c.model_dump(include=set(adapter.CELL_FIELDS)) for c in t.data.table_cells] ==
                [c.model_dump() for c in p.data.table_cells])
            check(label + " provenance honest", lambda t=item, h=title, o=old_table:
                t.prov == h.prov == o.prov and all(c.bbox is None for c in t.data.table_cells))
            check(label + " panel label/title literal", lambda p=panel, t=title:
                t.text == " ".join(s for s in (p.panel_label, p.title) if s))
        if old_table.captions:
            check(b["target_key"] + " native captions preserved", lambda b=b, t=old_table:
                [gate.old.signature(RefItem(cref=r).resolve(doc)) for r in b["captions"]] ==
                [gate.old.signature(r.resolve(baseline)) for r in t.captions])
        elif target.caption:
            existing = [n.self_ref for n in baseline.texts if normalize(n.text) == normalize(target.caption)]
            copies = [n.self_ref for n in doc.texts if normalize(n.text) == normalize(target.caption)]
            if existing and len(copies) > len(existing):
                duplicate_captions.append({"target_key": b["target_key"], "native_body_refs": existing,
                    "output_copies": copies, "cause": "native caption unlinked; provider fallback adds source caption again"})
    check("source captions not duplicated", lambda: not duplicate_captions)
    serialized = adapter.serialize(doc, bindings)
    check("saved Markdown equals serializer output", lambda: serialized.text == markdown)
    check("every serialization span is original item", lambda:
        all(s.item.model_dump_json() == s.item.get_ref().resolve(doc).model_dump_json() for s in serialized.spans))
    check("canonical immutable during rendering", lambda: doc.model_dump_json() == canonical and baseline.model_dump_json() == original)
    tables, _ = gate.rendered_tables(markdown)
    ordered_tables = [n for n in gate.old.walk(doc) if isinstance(n, TableItem)]
    check("rendered table count matches typed traversal", lambda: len(tables) == len(ordered_tables))
    for table, rendered in zip(ordered_tables, tables, strict=True):
        if table.self_ref in target_data:
            check(table.self_ref + " actual rendered cells preserve typed values and header ancestry",
                  lambda t=table, r=rendered: r == expected_rows(target_data[t.self_ref]))
    loaded = DoclingDocument.model_validate_json(doc.model_dump_json())
    check("JSON reload exact", lambda: loaded.model_dump(mode="json") == doc.model_dump(mode="json"))
    check("JSON reload Markdown exact", lambda: adapter.export_markdown(loaded, bindings) == markdown)
    check("all saved inputs/outputs unchanged by audit", lambda: all(sha(p) == before[str(p)] for p in paths))
    return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
        "errors": errors, "duplicate_captions": duplicate_captions, "target_tables": len(bindings),
        "mapped_panels": len(target_data), "untouched_nodes": len(expected_untouched), "input_hashes": before}


def collateral():
    """Manual transcription after viewing the registered SkillOpt page-8 image, not a frozen oracle."""
    rows = [
        ["Learning-rate form", "lr=4 (default)", "87.1", "77.5", "61.3"],
        ["Learning-rate form", "dynamic lr", "85.8", "71.8", "54.0"],
        ["Learning-rate form", "without lr", "84.6", "75.7", "57.3"],
        ["Rejected buffer", "with rejected buffer", "87.1", "77.5", "61.3"],
        ["Rejected buffer", "without rejected buffer", "85.5", "72.9", "58.9"],
        ["Slow/meta update", "meta skill and slow update", "87.1", "77.5", "61.3"],
        ["Slow/meta update", "without meta skill", "85.1", "75.7", "58.1"],
        ["Slow/meta update", "without meta skill and slow update", "86.3", "55.0", "59.7"],
    ]
    dest = HERE / "skillopt-p8"
    raw = json.loads((dest / "output.json").read_text())
    doc = DoclingDocument.model_validate_json((dest / "document.json").read_text())
    bindings = json.loads((dest / "bindings.json").read_text())
    source = adapter.parse_response(raw, [b["target_key"] for b in bindings]).targets[1].panels[0].data
    table = RefItem(cref=bindings[1]["panels"][0]["table_ref"]).resolve(doc)
    typed = [[c.text for c in row] for row in table.data.grid]
    actual_rendered = gate.rendered_tables((dest / "document.md").read_text())[0][-1]
    expected = [["Component", "Setting", "SearchQA", "SpreadsheetBench", "LiveMath"], *rows]
    checks = {"raw row/column bindings match actual image": expected_rows(source) == expected,
              "typed row/column bindings match actual image": typed == expected,
              "rendered row/column bindings match actual image": actual_rendered == expected}
    return {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "numeric_bindings": 24, "row_dimension_bindings": 8, "metric_columns": 3,
            "independent_manual_source": "registered SkillOpt page-8 144dpi image; Table 3",
            "source_image_sha256": "b21496108e623d7399e1c6f3d8d653ca3e04446a6e9d8fbde78b393bd9a0870f",
            "source_rows": rows, "not_in_registered_470_primary_denominator": True}


def main():
    registration = json.loads((HERE / "live-registration.json").read_text())
    observations = {x["name"]: x for x in json.loads((HERE / "live-observations.json").read_text())}
    assert len(observations) == 4 and all(x["attempts"] == 1 for x in observations.values())
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "runner_sha256": sha(Path(__file__)), "pages": {}}
    for job in registration["jobs"]:
        if observations[job["name"]]["result"] == "mapped; quality not evaluated":
            report["pages"][job["name"]] = audit(job)
        else:
            dest = HERE / job["name"]
            assert not any((dest / p).exists() for p in ("document.json", "document.md", "bindings.json"))
            report["pages"][job["name"]] = {"status": "not delivered: whole-page rejected", "accepted_artifacts": 0}
    report["skillopt_collateral_table3"] = collateral()
    report["status"] = "failed" if any(x["status"] != "passed" for x in report["pages"].values()) else "passed"
    report["limitations"] = ["delivery semantics audit, not independent numeric accuracy assessment of primary cases",
        "collateral Table3 manual check is separate from frozen primary denominator", "no producer changes, repair or retry"]
    (HERE / "delivery-verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "pages": {k: {"status": v["status"], "errors": v.get("errors", [])}
         for k, v in report["pages"].items()}, "collateral": report["skillopt_collateral_table3"]["status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
