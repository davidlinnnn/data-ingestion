"""Offline same-response replay; no model or network calls."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from docling_core.types.doc import DoclingDocument, RefItem, TableData

import method

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(BASE / "B"))
import evaluate as evaluator
import runner


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    registration = json.loads((BASE / "contract-audit-registration.json").read_text())
    assert datetime.now(timezone.utc) < datetime.fromisoformat(registration["deadline"])
    reg = runner.verify()
    raw, targets, target_results = {}, {}, []
    for job in reg["jobs"]:
        payload = json.loads((evaluator.LIVE / job["name"] / "content.txt").read_text())
        raw[job["name"]] = payload
        snapshot = json.dumps(payload, sort_keys=True)
        result = dict(job=job["name"], accepted=False)
        try:
            parsed, padding = method.parse(payload, [job["target_key"]])
        except ValueError as error:
            result["error"] = str(error)
        else:
            normalized = parsed.model_dump(mode="json")
            repeated, further_padding = method.parse(normalized, [job["target_key"]])
            assert repeated == parsed and not further_padding
            targets[job["name"]] = parsed.targets[0]
            result.update(accepted=True, covered_padding=padding)
            if not padding:
                assert parsed == method.strict.parse(payload, [job["target_key"]])
        assert json.dumps(payload, sort_keys=True) == snapshot
        target_results.append(result)

    gate = method.strict.policy.adapter.previous  # inventory only; no evaluator main.
    source_gate = method.strict.load("padding_source_signature", evaluator.RESEARCH / "pdf-core-direct-cell-2026-10-17/gate.py")
    pages = {}
    for page in reg["pages"]:
        jobs = [job for job in reg["jobs"] if job["page_name"] == page["name"]]
        result = dict(mapped=False)
        if not all(job["name"] in targets for job in jobs):
            result["reason"] = "Whole page remains unaccepted: at least one target is invalid."
            pages[page["name"]] = result
            continue
        baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
        before = baseline.model_dump_json()
        payload = dict(targets=[target for job in jobs for target in raw[job["name"]]["targets"]])
        doc, bindings = method.map_response(baseline, payload, page["page_no"], page["target_keys"])
        assert baseline.model_dump_json() == before
        source_gate.old.assert_graph(doc)
        excluded = {node.self_ref for table in gate.inventory(baseline, page["page_no"]).values()
                    for node in source_gate.old.walk(baseline, table)}
        changed = {node.self_ref for binding in bindings
                   for node in source_gate.old.walk(doc, RefItem(cref=binding["group_ref"]).resolve(doc))}
        assert [source_gate.source_signature(node, baseline) for node in source_gate.old.walk(baseline) if node.self_ref not in excluded] == [
            source_gate.source_signature(node, doc) for node in source_gate.old.walk(doc) if node.self_ref not in changed]
        assert (doc.pages, doc.origin, doc.furniture) == (baseline.pages, baseline.origin, baseline.furniture)
        native = gate.inventory(baseline, page["page_no"])
        for binding in bindings:
            original = next(target for target in payload["targets"] if target["target_key"] == binding["target_key"])
            assert binding["transport_provider"] == original
            for panel, refs in zip(binding["provider"]["panels"], binding["panels"], strict=True):
                table = RefItem(cref=refs["table_ref"]).resolve(doc)
                assert table.data == TableData.model_validate(panel["data"])
                assert table.prov == native[binding["target_key"]].prov
                assert all(cell.bbox is None for cell in table.data.table_cells)
        markdown = method.strict.adapter.export_markdown(doc, bindings)
        out = HERE / "replay" / page["name"]
        write(out / "document.json", doc.model_dump(mode="json"))
        write(out / "bindings.json", bindings)
        with (out / "document.md").open("x") as stream:
            stream.write(markdown)
        loaded = DoclingDocument.model_validate_json((out / "document.json").read_text())
        restored_bindings = json.loads((out / "bindings.json").read_text())
        assert loaded == doc and method.strict.adapter.export_markdown(loaded, restored_bindings) == markdown
        result.update(mapped=True, source_and_non_target_preserved=True, reload_pass=True)
        pages[page["name"]] = result

    # The producer above never reads the source oracle; only this review section does.
    cases = {case["id"]: case["details"] for case in json.loads((evaluator.ROOT / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json").read_text())["cases"]}
    small = method.strict.load("padding_small", evaluator.RESEARCH / "pdf-core-direct-cell-2026-10-17/evaluate-small.py")
    crop = method.strict.load("padding_crop", evaluator.RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-small.py")
    helper = method.strict.load("padding_html", evaluator.RESEARCH / "pdf-core-table-crops-2026-10-17/evaluate-t05.py")
    scores = {}
    for case_id, page_name in (("G1-T01", "memory-r1-p8"), ("G1-T02", "skillopt-p8"),
                              ("G1-T04", "paper09-p17"), ("G1-T05", "wikiskill-p13")):
        details = cases[case_id]
        score = dict(mapped=pages[page_name]["mapped"], denominator=len(details["expected_datapoints"]),
                     comparison_denominator=len(details["critical_comparisons"]), content_pass=False)
        if score["mapped"]:
            out = HERE / "replay" / page_name
            doc = DoclingDocument.model_validate_json((out / "document.json").read_text())
            bindings = json.loads((out / "bindings.json").read_text())
            binding = bindings[0]
            markdown = (out / "document.md").read_text()
            if case_id == "G1-T05":
                table = RefItem(cref=binding["panels"][0]["table_ref"]).resolve(doc)
                typed, rendered = evaluator.t05_views(table.data.model_dump(mode="json"), markdown, helper, details,
                    compact=binding["compact_provider"]["panels"][0]["data"])
                assert rendered is not None
            else:
                typed = evaluator.small_case_score(crop.raw_view(binding["provider"]), details, small, case_id)
                rendered = evaluator.small_case_score(evaluator.rendered_view(doc, binding, markdown, helper), details, small, case_id)
            page = next(page for page in reg["pages"] if page["name"] == page_name)
            baseline = DoclingDocument.model_validate_json(Path(page["baseline"]).read_text())
            captions = {text.text for text in baseline.texts if text.text.startswith("Table ")}
            caption_inventory = [dict(text=text, before=sum(node.text == text for node in baseline.texts),
                after=markdown.count(text)) for text in sorted(captions)]
            assert all(item["before"] == item["after"] for item in caption_inventory)
            score.update(typed=typed, rendered_markdown=rendered, native_caption_inventory=caption_inventory,
                         source_caption_literal_occurrences=markdown.count(details["caption"]["text"]),
                         content_pass=typed["content_pass"] and rendered["content_pass"], manual_source_review_required=True)
        scores[case_id] = score

    assert sum(result["accepted"] for result in target_results) == 5
    assert sum(result["mapped"] for result in pages.values()) == 3
    assert scores["G1-T05"]["typed"]["correct_expected_bindings"] == 80
    assert scores["G1-T05"]["rendered_markdown"]["correct_expected_bindings"] == 80
    assert not scores["G1-T04"]["content_pass"]
    assert datetime.now(timezone.utc) < datetime.fromisoformat(registration["deadline"])
    report = dict(method="grid-spans-v2-padding", saved_response_replay_only=True, new_api_calls=0,
        model_loads=0, holdout_reads=0, targets=target_results, pages=pages, cases=scores,
        primary_denominator=470, comparison_denominator=23, full_B_qualified=False,
        decision="Retain the small padding representation candidate; stop further inference on this B round because T04 remains unresolved.",
        method_files={name: sha256((HERE / name).read_bytes()).hexdigest() for name in ("method.py", "verify.py")})
    write(HERE / "results.json", report)
    print(json.dumps(dict(valid_targets=5, mapped_pages=3, T05_typed_and_rendered=80,
                         full_B_qualified=False, new_api_calls=0)))


if __name__ == "__main__":
    main()
