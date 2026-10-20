"""Rendered delivery and rejected-output diagnostics; never creates candidate data."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, RefItem
from markdown_it import MarkdownIt
import evaluate as e
import protocol as p
import runner


def relation(a, b, operator):
    try:
        a, b = Decimal(a), Decimal(b)
        return {">": a > b, "<": a < b, "=": a == b}[operator]
    except (InvalidOperation, TypeError):
        return False


def main():
    reg = runner.verify()
    execution = json.loads((e.LIVE / "execution.json").read_text())
    assert execution["all_six_attempted"] and execution["stopped"] is None
    gold_path = e.ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
    cases = {c["id"]: c["details"] for c in json.loads(gold_path.read_text())["cases"]}
    small = p.load("postrun_small", e.RESEARCH / "pdf-core-direct-cell-2026-10-17/evaluate-small.py")
    html_helper = p.load("postrun_html", e.RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-t05.py")
    t04_helper = p.load("postrun_collateral", e.RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-t04.py")
    gate = p.load("postrun_source_signatures", e.RESEARCH / "pdf-core-direct-cell-2026-10-17/gate.py")
    results = dict(rendered_delivery={}, rejected_diagnostics={}, collateral={}, evaluator_controls={})
    for case_id, page_name, job_name in (("G1-T01", "memory-r1-p8", "memory-r1-p8-table0"),
        ("G1-T02", "skillopt-p8", "skillopt-p8-table0")):
        dest = e.LIVE / page_name
        doc = DoclingDocument.model_validate_json((dest / "document.json").read_text())
        md = (dest / "document.md").read_text()
        bindings = json.loads((dest / "bindings.json").read_text())
        page = next(pg for pg in reg["pages"] if pg["name"] == page_name)
        baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        rendered = MarkdownIt("commonmark", {"html": True}).enable("table").render(md)
        binding = bindings[0]
        view = e.rendered_view(doc,binding,md,html_helper)
        score = e.small_case_score(view,cases[case_id],small,case_id)
        changed = deepcopy(view)
        changed["panels"][0]["rows"][0]["values"][0]["value"] = "999"
        bad = e.small_case_score(changed,cases[case_id],small,case_id)
        assert bad["source_numeric_bindings_correct"] < score["source_numeric_bindings_correct"]
        caption = cases[case_id]["caption"]["text"]
        native = p.adapter.inventory(baseline,page["page_no"])
        excluded = {n.self_ref for target in native.values() for n in gate.old.walk(baseline,target)}
        changed_refs = {n.self_ref for b in bindings for n in gate.old.walk(doc,RefItem(cref=b["group_ref"]).resolve(doc))}
        captions = [t.text for t in baseline.texts if t.text.startswith("Table ")]
        results["rendered_delivery"][case_id] = dict(score=score, caption_occurrences=md.count(caption),
            original_caption_occurrences=[dict(text=text,before=sum(t.text==text for t in baseline.texts),after=md.count(text)) for text in captions],
            all_non_target_content_order_and_provenance_preserved=[gate.source_signature(n,baseline) for n in gate.old.walk(baseline) if n.self_ref not in excluded] ==
                [gate.source_signature(n,doc) for n in gate.old.walk(doc) if n.self_ref not in changed_refs],
            provenance_preserved=all(RefItem(cref=refs["table_ref"]).resolve(doc).prov == baseline.tables[0].prov for refs in binding["panels"]))
        results["evaluator_controls"][case_id] = "numeric mutation detected in rendered table"
        rendered_dest = e.REPORTS / page_name
        rendered_dest.mkdir(parents=True,exist_ok=True)
        with (rendered_dest / "evaluated-rendered.html").open("x") as stream:
            stream.write(rendered)

    failures = {}
    for job in reg["jobs"]:
        raw = json.loads((e.LIVE / job["name"] / "content.txt").read_text())
        try:
            p.parse(raw, [job["target_key"]])
        except ValueError as error:
            failures[job["name"]] = error.errors(include_input=False, include_context=False, include_url=False)
    raw4 = json.loads((e.LIVE / "paper09-p17-table0/content.txt").read_text())["targets"][0]["panels"][0]["data"]
    gold4 = cases["G1-T04"]
    numeric_rows = [(r,row) for r,row in enumerate(raw4["grid"]) if len(row) == 13 and sum(t04_helper.number(v) for v in row) == 10]
    assert len(numeric_rows) == len(gold4["rows"]) == 30
    row_ids = [row["row_id"] for row in gold4["rows"]]
    col_keys = [h["key"] for h in gold4["headers"]]
    points4 = []
    for point in gold4["expected_datapoints"]:
        row, values = numeric_rows[row_ids.index(point["row_id"])]
        col = 3 + col_keys.index(point["column_key"])
        points4.append(dict(id=point["id"], expected=point["raw_value"], actual=values[col],
            raw_position=[row,col], correct=values[col] == point["raw_value"]))
    by_id = {point["id"]:point for point in points4}
    critical4 = [{**rule, "positional_relation_holds":relation(by_id[rule["left"]]["actual"],
        by_id[rule["right"]]["actual"],rule["operator"])} for rule in gold4["critical_comparisons"]]
    results["rejected_diagnostics"]["G1-T04"] = dict(schema_errors=failures["paper09-p17-table0"],
        row_lengths=[len(row) for row in raw4["grid"]], positional_literal_correct=sum(p["correct"] for p in points4),
        denominator=300, positional_comparisons=sum(c["positional_relation_holds"] for c in critical4),
        comparison_denominator=5, points=points4, comparisons=critical4,
        interpretation="Position-only reading diagnostic. Ragged shifted category header and inconsistent spans prevent valid hierarchical binding; no padding, shifting or accepted document was made.")

    raw5 = json.loads((e.LIVE / "wikiskill-p13-table0/content.txt").read_text())["targets"][0]["panels"][0]["data"]
    grid = raw5["grid"]
    def declared_text(row,col):
        if grid[row][col] is not None:
            return grid[row][col]
        spans = [s for s in raw5["spans"] if s["row"]<=row<s["row"]+s["rows"] and s["col"]<=col<s["col"]+s["cols"]]
        return grid[spans[0]["row"]][spans[0]["col"]] if len(spans)==1 else None
    paths = [[declared_text(0,col), declared_text(1,col)] for col in range(1,7)]
    rows5 = [(row,[declared_text(row,col) for col in range(len(grid[row]))]) for row in range(2,len(grid))]
    score5 = e.t05_score(paths,rows5,raw5,html_helper,cases["G1-T05"],coherent=False)
    results["rejected_diagnostics"]["G1-T05"] = dict(schema_errors=failures["wikiskill-p13-table0"],
        raw_semantic_diagnostic=score5, covered_category_slot=grid[1][0],
        interpretation="Evaluation reads raw declared row_groups and resolves header null slots through their explicit spans. Category rowspan covers a non-null empty string; row sections lack printed full-width spans and category row roles are absent. No null replacement or candidate repair was made.")

    # Source-only collateral references, kept outside the 470/23 primary denominator.
    table7 = json.loads((e.LIVE / "paper09-p17-table1/output.json").read_text())["targets"][0]["panels"][0]["data"]
    results["collateral"]["paper09-table7"] = t04_helper.collateral(p.Grid.model_validate(table7).data())
    results["collateral"]["paper09-table7"]["header_binding_limit"] = "Historical helper caveat superseded: current compact Grid is valid, but the whole page is unaccepted because its primary target failed."
    expected3 = ["87.1 77.5 61.3", "85.8 71.8 54.0", "84.6 75.7 57.3", "87.1 77.5 61.3",
        "85.5 72.9 58.9", "87.1 77.5 61.3", "85.1 75.7 58.1", "86.3 55.0 59.7"]
    table3 = json.loads((e.LIVE / "skillopt-p8-table1/output.json").read_text())["targets"][0]["panels"][0]["data"]
    values3 = [row[2:] for row in table3["grid"][1:]]
    assert len(values3) == len(expected3)
    results["collateral"]["skillopt-table3"] = dict(denominator=24,
        numeric_literals_correct=sum(a==b for actual,expected in zip(values3,expected3,strict=True) for a,b in zip(actual,expected.split(),strict=True)),
        source="Original registered body crop visually reviewed after all six calls; printed Component/Setting rows preserved.",
        whole_page_delivered=True, primary_denominator_increase=0)

    old_obs = json.loads((e.RESEARCH / "pdf-core-table-crops-2026-10-17/live-observations.json").read_text())
    old_exec = json.loads((e.RESEARCH / "pdf-core-table-crops-2026-10-17/execution.json").read_text())
    obs = json.loads((e.LIVE / "observations.json").read_text())
    old_output = sum(o["usage"]["completion_tokens"] for o in old_obs)
    results["cost"] = dict(old_completion_tokens=old_output, new_completion_tokens=execution["ledger"]["completion"],
        completion_reduction_fraction=1-execution["ledger"]["completion"]/old_output,
        old_input_tokens=sum(o["usage"]["prompt_tokens"] for o in old_obs), new_input_tokens=execution["ledger"]["input"],
        old_live_seconds=old_exec["elapsed_seconds"], new_live_seconds=execution["elapsed_seconds"],
        new_http_seconds=sum(o["http_response_seconds"] for o in obs),
        max_new_request_seconds=max(o["http_response_seconds"] for o in obs),
        caveat="One exposed DEV run each, same six crops/model alias; compact protocol/prompt and completion cap differ. Cached Standard cost excluded. Server queue and immutable model weights unknown; no p95 or GPU-speed claim.")
    e.save("postrun-review.json",results)
    print(json.dumps(dict(rendered={k:v["score"]["source_numeric_bindings_correct"] for k,v in results["rendered_delivery"].items()},
        T04_position_only=results["rejected_diagnostics"]["G1-T04"]["positional_literal_correct"],
        T05_raw_only=score5["correct_expected_bindings"],collateral={k:v.get("numeric_literals_correct",v.get("numeric_literals_at_named_group_method_and_metric_position_correct")) for k,v in results["collateral"].items()},cost=results["cost"])))


if __name__ == "__main__":
    main()
