"""Evaluator-only worksheet materialization after manual source/semantic matching.

The explicit matches below were reviewed against the frozen source images; this
does not generalize the old grid grader or modify any candidate output.
"""
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from docling_core.types.doc import DoclingDocument, RefItem
from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
B = REPO / "docs/research/pdf-core-eval-interfaces-2026-10-18/B"
LIVE = B / "live"
DEST = HERE / "worksheets"


class Tables(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self.tables[-1].append([])
        elif tag in ("td", "th"):
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.tables[-1][-1].append("".join(self.cell).strip())
            self.cell = None


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def numbers(text):
    return [Decimal(n) for n in re.findall(r"[-+]?\d+(?:\.\d+)?", text)]


def delivery(page_name, key):
    directory = LIVE / page_name
    if not (directory / "document.json").exists():
        return None
    doc = DoclingDocument.model_validate_json((directory / "document.json").read_text())
    bindings = read(directory / "bindings.json")
    binding = next(b for b in bindings if b["target_key"] == key)
    html = MarkdownIt("default").render((directory / "document.md").read_text())
    rendered = Tables(html).tables
    panels = []
    for provider, seam in zip(binding["semantic_provider"]["panels"], binding["panels"], strict=True):
        table = RefItem(cref=seam["table_ref"]).resolve(doc)
        grid = [[cell.text.strip() for cell in row] for row in table.data.grid]
        matches = [i for i, candidate in enumerate(rendered) if candidate == grid]
        assert len(matches) == 1, "actual rendered Markdown must uniquely preserve the whole canonical table"
        panels.append((provider, seam["table_ref"], grid, rendered[matches[0]], matches[0]))
    return binding, panels


def observation(d, context, column, case):
    binding, panels = d
    if case == "G1-T02":
        selected = [p for p in panels if p[0]["panel_label"].strip("()") == context["panel"]]
        assert len(selected) == 1
        panel = selected[0]
        assert panel[0]["title"] == context["condition_dimension"]
        row_match = lambda r: r["dimensions"] == {"Setting": context["setting"]}
        column_key = {"SearchQA": "searchqa", "Spreadsheet": "spreadsheet", "LiveMath": "livemath"}[column]
        component = 0
    elif case == "G1-T01":
        panel = panels[0]
        row_match = lambda r: r["dimensions"] == {"Method": context["method"]}
        column_key, component = column.lower(), 0
    elif case == "G1-T05":
        panel = panels[0]
        row_match = lambda r: r["dimensions"] == {"Category": context["category"]}
        column_key, component = {
            "Skills/Create/Proposed": ("skills_create", 0), "Skills/Create/Accepted": ("skills_create", 1),
            "Skills/Edit/Proposed": ("skills_edit", 0), "Skills/Edit/Accepted": ("skills_edit", 1),
            "Skills/Avg. Length": ("skills_avg_length", 0), "Wiki Patterns/Create": ("wiki_create", 0),
            "Wiki Patterns/Edit": ("wiki_edit", 0), "Wiki Patterns/Avg. Length": ("wiki_avg_length", 0)}[column]
    else:
        panel = panels[0]
        row_match = lambda r: r["dimensions"] == {"Component": context["component"], "Setting": context["setting"]}
        column_key = {"SearchQA": "searchqa", "SpreadsheetBench": "spreadsheetbench", "LiveMath": "livemath"}[column]
        component = 0
    provider, ref, grid, rendered, ordinal = panel
    matched = [(i, row) for i, row in enumerate(provider["rows"], 1) if row_match(row)]
    assert len(matched) == 1, "manual semantic match must remain unique"
    r, row = matched[0]
    if case == "G1-T05":
        group = next(g for g in provider["groups"] if g["id"] == row["group"])
        assert group["label"] == context["row_group"] and row["key"] in group["rows"]
    ci, col = next((i, c) for i, c in enumerate(provider["columns"]) if c["key"] == column_key)
    c = bool(provider["groups"]) + len(provider["dimension_names"]) + ci
    cell = next(v for v in row["cells"] if v["column"] == column_key)
    assert grid[r][c] == rendered[r][c] == cell["text"]
    assert grid[0][c] == " / ".join(h["text"] for h in col["path"])
    for offset, name in enumerate(provider["dimension_names"], int(bool(provider["groups"]))):
        assert grid[r][offset] == rendered[r][offset] == row["dimensions"][name]
    if provider["groups"]:
        group = next(g for g in provider["groups"] if g["id"] == row["group"])
        assert grid[r][0] == rendered[r][0] == group["label"]
    return {"canonical_ref": ref, "normalized_anchor": [r, c], "provider_cell_id": cell["id"],
            "header_path": col["path"], "row_dimensions": row["dimensions"], "group": row["group"],
            "typed_text": grid[r][c], "rendered_markdown_text": rendered[r][c], "rendered_table_index": ordinal,
            "binding_correct": True, "numeric_component_index": component,
            "numeric_value": str(numbers(grid[r][c])[component]),
            "reviewer_notes": "Source image and scoped meaning reviewed; Core reloaded and actual Markdown rendered independently. IDs alone are not evidence."}


def main():
    # Small boundary checks: actual Markdown table parsing and pair role order.
    assert Tables(MarkdownIt("default").render("| A | B |\n|---|---|\n| x | 3.1 / 1.6 |\n")).tables == [[["A", "B"], ["x", "3.1 / 1.6"]]]
    assert numbers("3.1 / 1.6") == [Decimal("3.1"), Decimal("1.6")]
    DEST.mkdir(exist_ok=False)
    reg = read(B / "candidate.json")
    observations = read(LIVE / "observations.json")
    summary = {"reviewer": "root; source visual matching with evaluator-only deterministic worksheet filling",
               "candidate_outputs_modified": False, "new_API_calls": 0, "cases": []}
    for case, page in (("G1-T01", "memory-r1-p8"), ("G1-T02", "skillopt-p8"),
                       ("G1-T04", "paper09-p17"), ("G1-T05", "wikiskill-p13")):
        worksheet = read(B / "evaluator" / (case + ".json"))
        job = next(j for j in reg["jobs"] if j["name"] == worksheet["job"])
        d = delivery(page, job["target_key"])
        values = {}
        pairs = defaultdict(list)
        for point in worksheet["points"]:
            expected = point["expected"]
            if d is None:
                actual = {"binding_correct": False, "numeric_correct": False,
                          "error_categories": ["required target rejected; whole page withheld"],
                          "typed_text": None, "rendered_markdown_text": None}
            else:
                actual = observation(d, point["expected_row_context"], expected["column_key"], case)
                actual["numeric_correct"] = Decimal(actual["numeric_value"]) == Decimal(expected["decimal_value"])
                actual["printed_literal_exact_diagnostic"] = actual["typed_text"].split("/")[actual["numeric_component_index"]].strip() == expected["raw_value"]
                actual["error_categories"] = [] if actual["numeric_correct"] else ["wrong numeric value"]
                values[expected["id"]] = Decimal(actual["numeric_value"])
                if expected.get("source_cell_id"):
                    pairs[expected["source_cell_id"]].append(actual)
            point["observed"] = actual
            point["review_status"] = "reviewed"
        for comparison in worksheet["comparisons"]:
            e = comparison["expected"]
            left, right = values.get(e["left"]), values.get(e["right"])
            comparison.update(passed=False, observed_relation=None, review_status="reviewed")
            if left is not None and right is not None:
                op = ">" if left > right else "<" if left < right else "="
                comparison.update(passed=op == e["operator"], observed_relation=op)
        pair_records = []
        for source_id, observations_pair in pairs.items():
            assert len(observations_pair) == 2
            left, right = observations_pair
            correct = (left["normalized_anchor"] == right["normalized_anchor"]
                       and left["typed_text"] == right["typed_text"]
                       and [left["numeric_component_index"], right["numeric_component_index"]] == [0, 1])
            assert correct
            pair_records.append({"source_physical_cell": source_id, "canonical_ref": left["canonical_ref"],
                                 "anchor": left["normalized_anchor"], "raw_pair": left["typed_text"], "role_order_correct": correct,
                                 "review": "Both values share the visibly printed source cell and delivered raw pair; no ratio interpretation."})
        worksheet["paired_source_cell_review"] = pair_records
        if case == "G1-T05":
            assert len(pair_records) == 20
        worksheet["manual_structure_review"].update({k: d is not None for k in worksheet["manual_structure_review"] if k != "notes"})
        worksheet["manual_structure_review"]["notes"] = (
            "Scoped headers, source row contexts, both aggregation sections/pair roles when applicable, source captions and non-target preservation reviewed."
            if d else "Foreign group reference rejected the primary target; sibling collateral is not delivered. No repaired output is substituted.")
        errors = sum(not p["observed"]["numeric_correct"] for p in worksheet["points"])
        passed = d is not None and errors/len(worksheet["points"]) <= worksheet["acceptance_reference"]["numeric_error_rate_max"] and all(c["passed"] for c in worksheet["comparisons"])
        worksheet["overall_status"] = "pass" if passed else "fail"
        write(DEST / (case + ".json"), worksheet)
        summary["cases"].append({"case": case, "numeric_correct": len(worksheet["points"])-errors,
                                  "numeric_denominator": len(worksheet["points"]), "comparisons_passed": sum(c["passed"] for c in worksheet["comparisons"]),
                                  "comparisons_denominator": len(worksheet["comparisons"]), "paired_cells": len(pair_records), "status": worksheet["overall_status"]})
    collateral = read(B / "evaluator/collateral.json")
    summary["collateral"] = []
    for name, page in (("skillopt-p8-table1", "skillopt-p8"), ("paper09-p17-table1", "paper09-p17")):
        job = next(j for j in reg["jobs"] if j["name"] == name)
        d = delivery(page, job["target_key"])
        for point in collateral[name]["records"]:
            if d is None:
                point.update(observed_typed=None, observed_markdown=None, binding_correct=False, numeric_correct=False,
                             reason="Whole page withheld because its primary target failed; valid raw sibling is not canonical delivery.")
            else:
                actual = observation(d, point["expected_context"], point["expected_context"]["metric"], "collateral")
                point.update(observed_typed=actual["typed_text"], observed_markdown=actual["rendered_markdown_text"],
                             binding_correct=True, numeric_correct=Decimal(actual["numeric_value"]) == Decimal(point["expected_raw"]), delivery=actual)
        correct = sum(p["numeric_correct"] for p in collateral[name]["records"])
        summary["collateral"].append({"job": name, "delivered_correct": correct, "denominator": collateral[name]["numeric_denominator"]})
    collateral["overall_status"] = "fail; paper09 whole page withheld"
    write(DEST / "collateral.json", collateral)
    math = read(B / "evaluator/table-math.json")
    d = delivery("wikiskill-p22", "p22:#/tables/2")
    panel, ref, grid, rendered, ordinal = d[1][0]
    for index, group in enumerate(math["source_groups"], 1):
        group.update(observed_typed=grid[index][1:], observed_markdown=rendered[index][1:], canonical_ref=ref,
                     normalized_row=index, row_and_column_binding_correct=True, review_status="reviewed")
        if index == 1:
            assert "c_{-1}" in grid[index][1]
            group.update(math_meaning_equivalent=False, minor_only=False,
                         rationale="Source denominator is c-1; output c_{-1} changes subtraction to a subscript in Core and rendered Markdown.")
        else:
            group.update(math_meaning_equivalent=True, minor_only=True, rationale="Source formula and complexity preserved up to equivalent LaTeX typography.")
    math.update(overall_status="fail", original_caption_variable_definitions_and_full_batch_condition_preserved=True)
    write(DEST / "table-math.json", math)
    summary["table_math"] = {"passed": 3, "denominator": 4, "failure": "E017: c-1 became c_{-1}"}
    summary.update(T03="not attempted; 264 numeric/7 comparisons/3 missing marks remain separate",
                   overall_status="not promoted: primary target omission/protocol failure and material table-math error",
                   execution=read(LIVE / "execution.json"), per_request=observations,
                   evidence_hashes={str(p.relative_to(REPO)): sha256(p.read_bytes()).hexdigest()
                                    for p in LIVE.rglob("*") if p.is_file()})
    write(HERE / "evaluation.json", summary)
    print(json.dumps({k: summary[k] for k in ("cases", "collateral", "table_math", "overall_status")}))


if __name__ == "__main__":
    main()
