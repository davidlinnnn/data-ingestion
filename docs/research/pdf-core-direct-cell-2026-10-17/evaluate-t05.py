"""Post-inference T05 evaluator; never imported by the producer."""
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from docling_core.types.doc import DoclingDocument, RefItem
from markdown_it import MarkdownIt


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASE = HERE / "wikiskill-p13"
ORACLE = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"


def norm(text):
    return " ".join(text.split())


def columns(header_paths):
    """Recover named measurements from the delivered header, including pair order."""
    result = []
    for path in header_paths:
        parent, child = path
        match = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", child)
        if match:
            metric, raw_roles = match.groups()
            roles = [norm(x) for x in raw_roles.split("/")]
            result.append([f"{parent}/{norm(metric)}/{role}" for role in roles])
        else:
            result.append([f"{parent}/{child}"])
    return result


def observations(paths, rows):
    """Keep row-group and physical cell identity with every semantic value."""
    schema = columns(paths)
    group = None
    result = []
    for index, row in rows:
        if len(set(row)) == 1 and row[0].startswith("By "):
            group = row[0]
            continue
        for col, (text, keys) in enumerate(zip(row[1:], schema, strict=True), 1):
            parts = [norm(v) for v in text.split("/")]
            for component, value in enumerate(parts):
                key = keys[component] if component < len(keys) else "EXTRA_COMPONENT"
                result.append({"group": group, "category": row[0], "column": key,
                    "value": value, "physical_cell": [index, col],
                    "component_index": component, "raw_cell": norm(text)})
    return result


def markdown_tables(markdown):
    tables, table, row, current = [], None, None, None
    for token in MarkdownIt("commonmark", {"html": True}).enable("table").parse(markdown):
        if token.type == "table_open":
            table = []
        elif token.type == "tr_open" and table is not None:
            row = []
        elif token.type in ("th_open", "td_open"):
            current = ""
        elif token.type == "inline" and current is not None:
            current += "".join(t.content if t.type in ("text", "code_inline") else " "
                for t in token.children or [])
        elif token.type in ("th_close", "td_close"):
            row.append(norm(current))
            current = None
        elif token.type == "tr_close" and table is not None:
            table.append(row)
        elif token.type == "table_close":
            tables.append(table)
            table = None
    return tables


def evaluate(actual, details):
    rows = {r["row_id"]: r["context"] for r in details["rows"]}
    expected = {(rows[p["row_id"]]["row_group"], rows[p["row_id"]]["category"],
        p["column_key"]): p for p in details["expected_datapoints"]}
    observed = {}
    for point in actual:
        key = point["group"], point["category"], point["column"]
        observed.setdefault(key, []).append(point)
    errors, ids, paired = [], {}, []
    for key, point in expected.items():
        candidates = observed.get(key, [])
        if len(candidates) != 1 or candidates[0]["value"] != point["raw_value"]:
            errors.append({"id": point["id"], "expected": point["raw_value"],
                "observed": [x["value"] for x in candidates], "binding": key})
        if len(candidates) == 1:
            ids[point["id"]] = candidates[0]
    extras = [v for key, values in observed.items() if key not in expected for v in values]
    duplicate_extras = sum(max(0, len(values)-1) for key, values in observed.items() if key in expected)
    comparisons = []
    for rule in details["critical_comparisons"]:
        left, right = ids.get(rule["left"]), ids.get(rule["right"])
        try:
            valid = left is not None and right is not None and {
                ">": lambda: Decimal(left["value"]) > Decimal(right["value"]),
                "<": lambda: Decimal(left["value"]) < Decimal(right["value"]),
                "=": lambda: Decimal(left["value"]) == Decimal(right["value"]),
            }[rule["operator"]]()
        except (InvalidOperation, KeyError):
            valid = False
        comparisons.append({**rule, "passed": valid,
            "observed_left": left["value"] if left else None,
            "observed_right": right["value"] if right else None})
    for source_cell in details["paired_source_cells"]:
        parts = [ids.get(key) for key in source_cell["component_datapoints"]]
        valid = all(x is not None for x in parts)
        if valid:
            valid = (parts[0]["physical_cell"] == parts[1]["physical_cell"]
                and [x["component_index"] for x in parts] == [0, 1]
                and parts[0]["raw_cell"] == norm(source_cell["raw_text"]))
        paired.append({"source_cell_id": source_cell["id"], "passed": valid})
    count = len(errors)+len(extras)+duplicate_extras
    return {"numeric_denominator": 80, "correct_expected_bindings": 80-len(errors),
        "numeric_errors_including_extras": count, "error_rate": count/80,
        "observed_numeric_measurements": len(actual), "errors": errors, "extras": extras,
        "duplicate_extra_outputs": duplicate_extras, "critical_comparisons": comparisons,
        "critical_comparisons_passed": sum(x["passed"] for x in comparisons),
        "paired_physical_cells": paired,
        "paired_physical_cells_passed": sum(x["passed"] for x in paired),
        "observations": actual,
        "numeric_and_critical_threshold_passed": count <= 4 and all(x["passed"] for x in comparisons)}


def main():
    completed = json.loads((HERE/"live-observations.json").read_text())
    assert len(completed) == 4 and all(x["attempts"] == 1 for x in completed)
    details = next(c for c in json.loads(ORACLE.read_text())["cases"] if c["id"] == "G1-T05")["details"]
    doc = DoclingDocument.model_validate_json((CASE/"document.json").read_text())
    bindings = json.loads((CASE/"bindings.json").read_text())
    assert len(bindings) == 1 and len(bindings[0]["panels"]) == 1
    table = RefItem(cref=bindings[0]["panels"][0]["table_ref"]).resolve(doc)
    grid = table.data.grid
    paths = [[norm(grid[0][col].text), norm(grid[1][col].text)] for col in range(1, 7)]
    typed_rows = [(i, [norm(c.text) for c in row]) for i, row in enumerate(grid)
        if not any(c.column_header for c in row)]
    typed = evaluate(observations(paths, typed_rows), details)
    markdown = (CASE/"document.md").read_text()
    rendered = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
    tables = markdown_tables(markdown)
    assert len(tables) == 1
    md_paths = [h.split(" - ", 1) for h in tables[0][0][1:]]
    markdown_result = evaluate(observations(md_paths, list(enumerate(tables[0][1:]))), details)
    sections = [c for c in table.data.table_cells if c.row_section]
    structural = {
        "literal_left_header_category": grid[0][0].text == "Category" and grid[0][0].column_header,
        "hierarchical_headers_preserved": paths == [["Skills", "Create (Proposed / Accepted)"],
            ["Skills", "Edit (Proposed / Accepted)"], ["Skills", "Avg. Length"],
            ["Wiki Patterns", "Create"], ["Wiki Patterns", "Edit"], ["Wiki Patterns", "Avg. Length"]],
        "parent_spans_preserved": grid[0][1].col_span == 3 and grid[0][4].col_span == 3,
        "two_groups_have_correct_typed_role": len(sections) == 2 and all(
            c.col_span == 7 and not c.column_header and not c.row_header for c in sections),
        "group_names_and_order_preserved": [norm(c.text) for c in sections] == [
            r["text"] for r in details["structure"]["row_group_headers"]],
        "all_ten_categories_are_row_headers": sum(c.row_header for c in table.data.table_cells) == 10,
        "all_twenty_pairs_typed_and_rendered": typed["paired_physical_cells_passed"] == 20
            and markdown_result["paired_physical_cells_passed"] == 20,
        "caption_retains_units_and_wiki_scope": details["caption"]["text"] in markdown,
    }
    # A swapped role/header or edited numeric value must fail independently of source ordering.
    bad = [dict(x) for x in typed["observations"]]
    bad[0]["value"] = "999"
    assert evaluate(bad, details)["numeric_errors_including_extras"] == 1
    bad[0]["column"] = "Wiki Patterns/Create"
    assert evaluate(bad, details)["numeric_errors_including_extras"] > 1
    visual = ROOT / details["rendered_evidence"][1]["path"]
    assert hashlib.sha256(visual.read_bytes()).hexdigest() == details["rendered_evidence"][1]["sha256"]
    source = json.loads((CASE/"source.json").read_text())
    source_pdf = ROOT / source["path"]
    assert hashlib.sha256(source_pdf.read_bytes()).hexdigest() == source["sha256"]
    caption_count = markdown.count(details["caption"]["text"])
    content_pass = all(structural.values()) and typed["numeric_and_critical_threshold_passed"] \
        and markdown_result["numeric_and_critical_threshold_passed"]
    report = {"case": "G1-T05", "evaluation_after_all_four_fixed_requests": True,
        "method": "Source crop visually reviewed; every saved canonical and actual rendered Markdown value bound by group/category/header/component against frozen oracle.",
        "source_visual_review": "docs/research/evidence/pdf-core-g1-2026-10-14/tables/01-2608.27454v1-p13-table4-216dpi.png",
        "typed": typed, "markdown": markdown_result, "structural_checks": structural,
        "source_shape_note": "Two typed header rows combine the source's wrapped Create/Edit role labels; semantic header paths and spans survive.",
        "caption_occurrences_in_main_markdown": caption_count,
        "delivery_issue": None if caption_count == 1 else
            "Complete Table4 caption is duplicated or missing; numeric/structural pass does not constitute complete delivery pass.",
        "content_pass": content_pass,
        "complete_delivery_pass": content_pass and caption_count == 1,
        "evaluator_self_checks": ["single_numeric_change_detected", "wrong_header_binding_detected"],
        "limitations": ["Exposed DEV case, not unseen generalization evidence.",
            "Producer, frozen configuration and raw outputs unchanged; no extra model/API request."],
        "sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ORACLE, visual, source_pdf, CASE/"document.json", CASE/"document.md",
                CASE/"output.json", Path(__file__))}}
    (CASE/"evaluated-rendered.html").write_text(rendered)
    (HERE/"t05-evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"case": report["case"], "typed_correct": typed["correct_expected_bindings"],
        "markdown_correct": markdown_result["correct_expected_bindings"],
        "critical_each": typed["critical_comparisons_passed"], "pairs_each": typed["paired_physical_cells_passed"],
        "structural_checks": structural, "caption_occurrences": report["caption_occurrences_in_main_markdown"],
        "content_pass": report["content_pass"], "complete_delivery_pass": report["complete_delivery_pass"]}, indent=2))


if __name__ == "__main__":
    main()
