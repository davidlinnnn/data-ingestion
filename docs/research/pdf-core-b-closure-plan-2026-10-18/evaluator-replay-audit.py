"""Read-only probes of the completed run and next-model evaluator readiness."""
import base64
from copy import deepcopy
from hashlib import sha256
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from PIL import Image
from docling_core.types.doc import DoclingDocument

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
B = REPO / "docs/research/pdf-core-eval-interfaces-2026-10-18/B"
EVALUATOR = REPO / "docs/research/pdf-core-fixed-seven-source-2026-10-18/evaluate.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(path.read_text())


def save_delivery(protocol, payload, job, destination):
    baseline = DoclingDocument.model_validate_json(Path(job["baseline"]).read_text())
    protocol.parse(payload, [job["target_key"]])
    document, bindings = protocol.map_response(baseline, payload, job["physical_page"], [job["target_key"]])
    directory = destination / job["page_name"]
    directory.mkdir()
    (directory / "document.json").write_text(document.model_dump_json())
    (directory / "bindings.json").write_text(json.dumps(bindings))
    (directory / "document.md").write_text(protocol.adapter.export_markdown(document, bindings))


def main():
    protocol = load("audit_semantic_protocol", B / "protocol.py")
    evaluator = load("audit_manual_evaluator", EVALUATOR)
    registration = read(B / "candidate.json")
    tracked = [EVALUATOR, B / "protocol.py", B / "candidate.json", B / "prompt.txt"]
    tracked += [p for p in (B / "live").rglob("*") if p.is_file()]
    before = {str(p.relative_to(REPO)): sha256(p.read_bytes()).hexdigest() for p in tracked}
    jobs = {j["name"]: j for j in registration["jobs"]}
    report = {"new_model_calls": 0, "new_API_calls": 0, "frozen_files_modified": False}
    t04 = jobs["paper09-p17-table0"]
    raw = read(B / "live/paper09-p17-table0/content.txt")
    parsed_error = None
    try:
        protocol.parse(raw, [t04["target_key"]])
    except ValueError as error:
        parsed_error = str(error)
    assert parsed_error and "foreign group" in parsed_error
    panel = raw["targets"][0]["panels"][0]
    wire = read(B / "requests/paper09-p17-table0.json")
    encoded = wire["messages"][0]["content"][1]["image_url"]["url"].split(",", 1)[1]
    image = base64.b64decode(encoded)
    assert sha256(image).hexdigest() == t04["image_sha256"]
    response = read(B / "live/paper09-p17-table0/response.json")
    report["actual_T04_failure_reproduced"] = {
        "wire_image_size": list(Image.open(BytesIO(image)).size), "wire_crop_sha256": sha256(image).hexdigest(),
        "returned_rows": len(panel["rows"]), "returned_metric_cells": sum(len(r["cells"]) for r in panel["rows"]),
        "parser_rejects_foreign_group": True, "finish_reason": response["choices"][0]["finish_reason"],
        "completion_tokens": response["usage"]["completion_tokens"], "completion_cap": t04["completion_cap"]}
    t01 = jobs["memory-r1-p8-table0"]
    source = read(B / "live/memory-r1-p8-table0/output.json")
    equivalent = deepcopy(source)
    panel = equivalent["targets"][0]["panels"][0]
    panel["dimension_names"] = ["method"]
    for row in panel["rows"]:
        row["dimensions"] = {"method": row["dimensions"]["Method"]}
    rejected = False
    with tempfile.TemporaryDirectory() as td:
        temporary = Path(td)
        save_delivery(protocol, equivalent, t01, temporary)
        with patch.object(evaluator, "LIVE", temporary):
            delivered = evaluator.delivery(t01["page_name"], t01["target_key"])
            try:
                evaluator.observation(delivered, {"method": "PPO (J-based reward model)"}, "F1", "G1-T01")
            except AssertionError as error:
                rejected = "manual semantic match" in str(error)
    assert rejected
    report["equivalent_dimension_case"] = {"change": "Method -> method only", "parser_Core_Markdown_pass": True,
                                            "current_evaluator_rejects": True}
    worksheet = read(B / "evaluator/G1-T04.json")
    delivered_t01 = evaluator.delivery(t01["page_name"], t01["target_key"])
    missing_t04_branch = False
    try:
        evaluator.observation(delivered_t01, worksheet["points"][0]["expected_row_context"],
                              worksheet["points"][0]["expected"]["column_key"], "G1-T04")
    except KeyError as error:
        missing_t04_branch = str(error) == "'Multi Hop/ME'"
    assert missing_t04_branch
    report["T04_success_branch_missing"] = {"actual_T04_oracle_column": "Multi Hop/ME", "current_error": "KeyError"}
    t7 = read(B / "live/wikiskill-p22-table7/output.json")
    actual_formula = t7["targets"][0]["panels"][0]["rows"][0]["cells"][0]["text"]
    assert "c_{-1}" in actual_formula
    corrected = actual_formula.replace("c_{-1}", "c-1")
    assert "c_{-1}" not in corrected
    assert 'assert "c_{-1}" in grid[index][1]' in EVALUATOR.read_text()
    report["table_math_evaluator_is_run_specific"] = {
        "actual_provider_error_present": True, "source_corrected_expression_fails_current_literal_assert": True,
        "scope": "Probe of the exact current assertion, not a new model result or a claim of general symbolic grading."}
    after = {str(p.relative_to(REPO)): sha256(p.read_bytes()).hexdigest() for p in tracked}
    assert before == after
    report["frozen_input_hashes"] = before
    with (HERE / "evaluator-replay-audit.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({k: v for k, v in report.items() if k != "frozen_input_hashes"}))


if __name__ == "__main__":
    main()
