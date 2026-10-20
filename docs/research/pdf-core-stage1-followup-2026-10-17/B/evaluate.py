"""Post-six-calls evaluation only; never imported by the frozen producer."""
from copy import deepcopy
from collections import Counter, defaultdict
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, RefItem, TableData, TableItem
from markdown_it import MarkdownIt
import protocol as p

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]
ROOT = RESEARCH.parents[1]
LIVE = HERE / "live"
REPORTS = HERE / "rescore-v2"


def save(name, value):
    REPORTS.mkdir(exist_ok=True)
    with (REPORTS / name).open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def ordinary_all_panels(view, details, small):
    combined = deepcopy(view)
    combined["panels"] = [dict(view["panels"][0], rows=[row for panel in view["panels"] for row in panel["rows"]])]
    score = small.ordinary(combined, details)
    score["header_exact"] = all(panel["columns"] == [h["raw_text"] for h in details["headers"]]
                                for panel in view["panels"])
    observations = Counter((row["setting"], v["column"].removesuffix("↑"))
        for panel in view["panels"] for row in panel["rows"] for v in row["values"])
    methods = {row["row_id"]:row["context"]["method"] for row in details["rows"]}
    expected = {(methods[point["row_id"]], point["column_key"]) for point in details["expected_datapoints"]}
    duplicates = sum(max(0, count-1) for key,count in observations.items() if key in expected)
    score["duplicate_extra_outputs"] = duplicates
    score["extra_numeric_observations"] += duplicates
    score["panels_evaluated"] = len(view["panels"])
    return score


def small_case_score(view, details, small, case_id):
    score = ordinary_all_panels(view,details,small) if case_id == "G1-T01" else small.previous.evaluate_table(view,details)
    correct = score["source_numeric_bindings_correct"]
    errors = (len(details["expected_datapoints"])-correct+score["extra_numeric_observations"]
        if case_id == "G1-T01" else score["error_rate_including_unmatched_extras"]*len(details["expected_datapoints"]))
    comparisons = sum(bool(c.get("observed_relation_holds",c.get("passed",False))) for c in score["critical_comparisons"])
    headers = score["header_exact"] if case_id == "G1-T01" else not score["panel_header_issues"]
    score.update(errors_including_extras=errors,comparisons_correct=comparisons,header_scope_pass=headers,
        content_pass=errors/len(details["expected_datapoints"]) <= .05 and headers and comparisons == len(details["critical_comparisons"]))
    return score


def rendered_view(doc, binding, markdown, helper):
    parser = helper.RenderedTables()
    parser.feed(MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown))
    order = [item.self_ref for item,level in doc.iterate_items() if isinstance(item, TableItem)]
    if len(order) != len(parser.tables):
        raise ValueError("rendered table inventory differs from canonical inventory")
    view = deepcopy(binding["provider"])
    view["panels"] = []
    for panel,refs in zip(binding["provider"]["panels"],binding["panels"],strict=True):
        table = parser.tables[order.index(refs["table_ref"])]
        view["panels"].append(dict(panel_label=panel["panel_label"],title=panel["title"],columns=table[0],
            rows=[dict(setting=row[0],values=[dict(column=table[0][i],value=v) for i,v in enumerate(row) if i]) for row in table[1:]]))
    return view


def t05_score(paths, rows, compact, helpers, details, *, coherent=True):
    if "row_groups" not in compact:
        raise ValueError("explicit row_groups are required")
    norm = helpers.previous.norm
    groups = compact["row_groups"]
    label_rows = {group["label_row"] for group in groups}
    rows_by_index = dict(rows)
    score_labels = all(group["label_row"] in rows_by_index
        and len(rows_by_index[group["label_row"]]) > group["label_col"]
        and norm(rows_by_index[group["label_row"]][group["label_col"]])
            == norm(compact["grid"][group["label_row"]][group["label_col"]]) for group in groups)
    data_rows = [(i,row) for i,row in rows if i not in label_rows]
    actual = helpers.previous.observations(paths,data_rows)
    scope = {i:norm(compact["grid"][group["label_row"]][group["label_col"]])
             for group in groups for i in range(group["start"],group["end"])}
    for point in actual:
        point["group"] = scope.get(point["physical_cell"][0])
    score = helpers.previous.evaluate(actual,details)
    expected_contexts = Counter((norm(row["context"]["row_group"]),norm(row["context"]["category"])) for row in details["rows"])
    observed_contexts = Counter((scope.get(i),norm(row[0])) for i,row in data_rows)
    score["row_group_labels_match"] = score_labels
    score["row_group_scope_pass"] = observed_contexts == expected_contexts and score_labels
    row_contexts = {row["row_id"]:row["context"] for row in details["rows"]}
    by_key = defaultdict(list)
    for point in actual:
        by_key[point["group"],point["category"],point["column"]].append(point)
    by_id = {}
    for point in details["expected_datapoints"]:
        context = row_contexts[point["row_id"]]
        matches = by_key.get((norm(context["row_group"]),norm(context["category"]),point["column_key"]),[])
        if len(matches) == 1:
            by_id[point["id"]] = matches[0]
    pairs = []
    for pair in details["paired_source_cells"]:
        parts = [by_id.get(key) for key in pair["component_datapoints"]]
        good = all(part is not None for part in parts)
        if good:
            good = (parts[0]["physical_cell"] == parts[1]["physical_cell"]
                and [part["component_index"] for part in parts] == [0,1]
                and sum(point["physical_cell"] == parts[0]["physical_cell"] for point in actual) == 2)
        pairs.append(dict(source_cell_id=pair["id"],passed=good))
    score["paired_structure"] = pairs
    score["paired_structure_passed"] = sum(pair["passed"] for pair in pairs)
    score["supplement_matches_typed"] = coherent
    score["content_pass"] = (score["error_rate"] <= .05
        and score["critical_comparisons_passed"] == len(details["critical_comparisons"])
        and score["paired_structure_passed"] == len(details["paired_source_cells"])
        and score["row_group_scope_pass"] and coherent)
    return score


def t05_views(data, markdown, helpers, details, *, compact):
    declared = p.Grid.model_validate(compact)
    coherent = TableData.model_validate(declared.data()) == TableData.model_validate(data)
    grid = TableData.model_validate(data).grid
    header_rows = sorted({c.start_row_offset_idx for c in TableData.model_validate(data).table_cells if c.column_header})
    paths = []
    for col in range(1, len(grid[0])):
        path = []
        for row in header_rows:
            value = helpers.previous.norm(grid[row][col].text)
            if not path or value != path[-1]:
                path.append(value)
        paths.append(path)
    rows = [(i, [helpers.previous.norm(c.text) for c in row]) for i, row in enumerate(grid)
            if not any(c.column_header for c in row)]
    typed = t05_score(paths,rows,compact,helpers,details,coherent=coherent)
    rendered = None
    if markdown is not None:
        html = MarkdownIt("commonmark", {"html": True}).enable("table").render(markdown)
        parser = helpers.RenderedTables()
        parser.feed(html)
        candidates = [t for t in parser.tables if t and t[0] and t[0][0] == "Category"]
        if len(candidates) == 1:
            table = candidates[0]
            md_paths = [h.split(" - ", 1) for h in table[0][1:]]
            if len(table)-1 == len(rows):
                md_rows = [(index,row) for (index,_),row in zip(rows,table[1:],strict=True)]
                rendered = t05_score(md_paths,md_rows,compact,helpers,details,coherent=coherent)
    return typed, rendered


def main():
    execution = json.loads((LIVE / "execution.json").read_text())
    records = json.loads((LIVE / "observations.json").read_text())
    assert execution["all_six_attempted"] and execution["stopped"] is None and len(records) == 6
    import runner
    reg = runner.verify()
    # The source oracle is opened only after the fixed six requests have finished.
    oracle = ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
    cases = {c["id"]: c["details"] for c in json.loads(oracle.read_text())["cases"]}
    small = p.load("followup_small_evaluator", RESEARCH / "pdf-core-direct-cell-2026-10-17/evaluate-small.py")
    crop_small = p.load("followup_crop_small", RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-small.py")
    t04 = p.load("followup_t04_evaluator", RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-t04.py")
    t05 = p.load("followup_t05_evaluator", RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-t05.py")
    assembled = {item["name"]: item for item in json.loads((LIVE / "page-assembly.json").read_text())}
    by_job, compact_by_job, target_reports = {}, {}, []
    for job, record in zip(reg["jobs"], records, strict=True):
        raw_path = LIVE / job["name"] / "content.txt"
        entry = dict(name=job["name"], schema_status=record["result"], panels=None)
        if raw_path.exists():
            try:
                raw = json.loads(raw_path.read_text())
                candidates = [t for t in raw["targets"] if t["target_key"] == job["target_key"]]
                assert len(candidates) == 1
                compact_by_job[job["name"]] = candidates[0]
                target = deepcopy(candidates[0])
                for panel in target["panels"]:
                    panel["data"] = p.Grid.model_validate(panel["data"]).data()
                by_job[job["name"]] = target
                entry["panels"] = [(panel["data"]["num_rows"], panel["data"]["num_cols"]) for panel in target["panels"]]
            except (ValueError, KeyError, IndexError, TypeError, AssertionError) as error:
                entry["raw_grid_diagnostic_error"] = type(error).__name__
        target_reports.append(entry)
    scores = {}
    for case_id, page, job_name in (("G1-T01", "memory-r1-p8", "memory-r1-p8-table0"),
        ("G1-T02", "skillopt-p8", "skillopt-p8-table0"),
        ("G1-T04", "paper09-p17", "paper09-p17-table0"),
        ("G1-T05", "wikiskill-p13", "wikiskill-p13-table0")):
        details = cases[case_id]
        denominator = len(details["expected_datapoints"])
        item = dict(denominator=denominator, comparison_denominator=len(details["critical_comparisons"]),
            raw_correct=None, comparisons_correct=None, typed_delivered_correct=0, markdown_delivered_correct=0,
            page_status=assembled[page]["status"], content_pass=False)
        target = by_job.get(job_name)
        if target is None:
            item["reason"] = "No structurally interpretable raw grid; schema failure is not zero raw numeric accuracy."
            scores[case_id] = item
            continue
        if case_id in ("G1-T01", "G1-T02"):
            view = crop_small.raw_view(target)
            score = small_case_score(view,details,small,case_id)
            correct = score["source_numeric_bindings_correct"]
            comparisons = score["comparisons_correct"]
            errors,header_pass = score["errors_including_extras"],score["header_scope_pass"]
            item.update(raw_correct=correct, comparisons_correct=comparisons, errors_including_extras=errors,
                header_scope_pass=header_pass, raw_score=score)
        elif case_id == "G1-T04":
            score = t04.evaluate_table6(target["panels"][0]["data"], details)
            correct = score["raw_named_label_numeric_diagnostic_correct"]
            comparisons = score["raw_critical_arithmetic_holds"]
            errors = denominator-correct+len(score["extra_numeric_cells"])
            header_pass = (score["header_paths_after_minor_spelling_adjudication"] == len(details["headers"])
                and len(score["row_contexts"]) == len(details["rows"])
                and all(c["distinct_model_family_variant_method_columns"] for c in score["row_contexts"]))
            item.update(raw_correct=correct, comparisons_correct=comparisons, errors_including_extras=errors,
                header_scope_pass=header_pass, raw_score=score,
                note="Frozen evaluator's historical 'accepted_structural_binding:false' describes the old invalid producer; current Grid validation and distinct row dimensions are checked separately.")
        else:
            md_path = LIVE / page / "document.md"
            compact = compact_by_job[job_name]["panels"][0]["data"]
            score, rendered = t05_views(target["panels"][0]["data"], md_path.read_text() if md_path.exists() else None,
                t05, details,compact=compact)
            correct, comparisons = score["correct_expected_bindings"], score["critical_comparisons_passed"]
            errors = score["numeric_errors_including_extras"]
            header_pass = (score["paired_structure_passed"] == len(details["paired_source_cells"])
                and score["row_group_scope_pass"] and score["supplement_matches_typed"])
            item.update(raw_correct=correct, comparisons_correct=comparisons, errors_including_extras=errors,
                header_scope_pass=header_pass, raw_score=score, rendered_markdown=rendered)
        if case_id in ("G1-T04","G1-T05") and len(target["panels"]) != 1:
            extras = sum(small.previous.decimal(part.strip()) is not None for panel in target["panels"][1:]
                for cell in panel["data"]["table_cells"] if not cell["column_header"] and not cell["row_section"]
                for part in cell["text"].split("/"))
            errors += extras
            header_pass = False
            item.update(unmatched_extra_panels=len(target["panels"])-1,extra_panel_numeric_observations=extras,
                errors_including_extras=errors,header_scope_pass=False)
        mapped = item["page_status"].startswith("mapped and reloaded")
        if mapped:
            doc = DoclingDocument.model_validate_json((LIVE / page / "document.json").read_text())
            bindings = json.loads((LIVE / page / "bindings.json").read_text())
            binding = next(b for b in bindings if b["target_key"] == next(j["target_key"] for j in reg["jobs"] if j["name"] == job_name))
            assert all(RefItem(cref=refs["table_ref"]).resolve(doc).data == TableData.model_validate(panel["data"])
                for refs, panel in zip(binding["panels"], target["panels"], strict=True))
            assert p.adapter.export_markdown(doc, bindings) == (LIVE / page / "document.md").read_text()
            item["typed_delivered_correct"] = correct
            rendered_pass = False
            if case_id in ("G1-T01","G1-T02"):
                md = (LIVE / page / "document.md").read_text()
                rendered = small_case_score(rendered_view(doc,binding,md,t05),details,small,case_id)
                item["rendered_markdown"] = rendered
                item["markdown_delivered_correct"] = rendered["source_numeric_bindings_correct"]
                rendered_pass = rendered["content_pass"]
            elif case_id == "G1-T05" and item["rendered_markdown"] is not None:
                item["markdown_delivered_correct"] = item["rendered_markdown"]["correct_expected_bindings"]
                rendered_pass = item["rendered_markdown"]["content_pass"]
            else:
                item["rendered_review_required"] = True
            item["content_pass"] = (errors/denominator <= .05 and header_pass
                and comparisons == item["comparison_denominator"] and rendered_pass)
            item["manual_conditions_review_required"] = True
        scores[case_id] = item
    report = dict(evaluation_after_all_six_calls=True, new_api_calls=0, targets=target_reports, cases=scores,
        primary_denominator=sum(s["denominator"] for s in scores.values()),
        comparison_denominator=sum(s["comparison_denominator"] for s in scores.values()),
        oracle_sha256=runner.sha(oracle), method_sha256=runner.sha(Path(__file__)),
        limits="Exposed DEV comparison. Raw numeric diagnostics, validated typed delivery and rendered Markdown are separate. Collateral and visual ownership review recorded separately.")
    assert report["primary_denominator"] == 470 and report["comparison_denominator"] == 23
    save("evaluation.json", report)
    print(json.dumps({k:{field:v[field] for field in ("raw_correct","denominator","comparisons_correct","page_status","content_pass")} for k,v in scores.items()}))


if __name__ == "__main__":
    main()
