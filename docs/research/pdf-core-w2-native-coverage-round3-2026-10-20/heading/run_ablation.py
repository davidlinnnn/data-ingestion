"""Eight official heading rule combinations on immutable saved baseline documents."""
import argparse
import collections
import importlib.metadata
import importlib.util
import itertools
import hashlib
import json
import sys
import time
from pathlib import Path

from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import SectionHeaderItem
from docling_core.types.doc.page import SegmentedPdfPage
from docling.datamodel.pipeline_options import HeadingHierarchyOptions
from docling.models.stages.heading_hierarchy.heading_hierarchy_model import HeadingHierarchyModel
from docling.utils.pdf_outline import _PdfOutlineItem

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
OLD = ROOT.parent / "pdf-core-w2-native-coverage-round2-2026-10-20"

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

HELPERS = module("round2_heading_helpers", OLD / "heading/apply_heading.py")
EVALUATOR = module("frozen_round2_heading_evaluator", OLD / "heading/assess_headings.py")
COMBINATIONS = [("b%d-n%d-s%d" % bits, dict(zip(("use_bookmarks", "use_numbering", "use_style"), map(bool, bits))))
                for bits in itertools.product((0, 1), repeat=3)]

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

def clear_images(value, path=""):
    cleared = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "image" and child is not None:
                digest = hashlib.sha256(json.dumps(child, sort_keys=True).encode()).hexdigest()
                cleared.append({"path": f"{path}/{key}", "previous_value_sha256": digest})
                value[key] = None
            else:
                cleared.extend(clear_images(child, f"{path}/{key}"))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            cleared.extend(clear_images(child, f"{path}/{i}"))
    return cleared

def native_inputs(job, output):
    existing = OLD / "heading" / job["id"]
    expected = list(range(job["first"], job["last"] + 1))
    if (existing / "native-outline.json").exists():
        paths = sorted(existing.glob("native-page-*.json"))
        pages = {int(p.stem.rsplit("-", 1)[1]): SegmentedPdfPage.model_validate_json(p.read_text()) for p in paths}
        assert sorted(pages) == expected
        outline = [_PdfOutlineItem.model_validate(v) for v in json.loads((existing / "native-outline.json").read_text())]
        source = {"method": "Reuse immutable round2 native font cells and outline; no reparse.",
            "directory": str(existing), "sha256": {p.name: HELPERS.sha(p) for p in paths + [existing / "native-outline.json"]}}
    else:
        native = output / "native"
        native.mkdir()
        pages, outline = HELPERS.parse_fonts(job, native)
        source = {"method": "Existing same-version official native parser, render/bitmap/fetch disabled, parser_threads=1. No inference.",
            "directory": str(native), "manifest": json.loads((native / "native-manifest.json").read_text())}
    write(output / "native-inputs.json", source)
    return pages, outline

def compare(reference_rows, candidate_rows):
    return dict(collections.Counter(a["status"] + " -> " + b["status"] for a, b in zip(reference_rows, candidate_rows)))

def report_counts(rows):
    return dict(collections.Counter(v["status"] for v in rows if v["reference"].get("command") not in ("paragraph", "subparagraph")))

def changed(reference, candidate):
    good = {"correct"}
    return {"fixed": sum(a["status"] not in good and b["status"] in good for a, b in zip(reference, candidate)),
            "new_bad": sum(a["status"] in good and b["status"] not in good for a, b in zip(reference, candidate)),
            "transitions": compare(reference, candidate)}

def run_job(job, input_dir):
    HELPERS.guard()
    output = OUT / "jobs" / job["id"]
    output.mkdir(parents=True, exist_ok=True)
    input_path = Path(input_dir) / "document.json"
    original_source = input_path.read_bytes()
    imagefree_source = json.loads(original_source)
    removed_images = clear_images(imagefree_source)
    doc = DoclingDocument.model_validate(imagefree_source)
    before = doc.model_dump(mode="json")
    write(output / "baseline-imagefree.json", before)
    write(output / "image-removal.json", removed_images)
    index = json.loads((OLD / "oracle/job-index.json").read_text())
    oracle_path = Path(index[job["id"]])
    oracle = json.loads(oracle_path.read_text())
    family = oracle.get("template", {}).get("family") or job["family"]
    scoped = [v for v in oracle["headings"] if v.get("scope") == "IN_SCOPE"]
    baseline_assessment = EVALUATOR.assess(before, scoped)
    write(output / "baseline-assessment.json", baseline_assessment)
    write(output / "inputs.json", {"document": str(input_path), "document_sha256": HELPERS.sha(input_path),
        "oracle": str(oracle_path), "oracle_sha256": HELPERS.sha(oracle_path),
        "oracle_headings": len(oracle["headings"]), "in_scope": len(scoped),
        "excluded_scopes": dict(collections.Counter(v.get("scope", "UNSPECIFIED") for v in oracle["headings"] if v.get("scope") != "IN_SCOPE")),
        "source_to_core_normalization_diff": HELPERS.differences(imagefree_source, before),
        "image_fields_cleared": removed_images,
        "stage_image_policy": "Every image field is None before loading stage input; no rendering or image fetching."})
    ready = [name for name, _ in COMBINATIONS if not (output / name / "summary.json").exists()]
    pages, outline = native_inputs(job, output) if ready else ({}, [])
    summaries, assessed = {}, {}
    for name, switches in COMBINATIONS:
        result_dir = output / name
        if (result_dir / "summary.json").exists():
            summaries[name] = json.loads((result_dir / "summary.json").read_text())
            assessed[name] = json.loads((result_dir / "assessment.json").read_text())
            assert summaries[name]["baseline_sha256"] == HELPERS.sha(input_path)
            continue
        HELPERS.guard()
        result_dir.mkdir(exist_ok=False)
        options = HeadingHierarchyOptions(enabled=True, **switches)
        start = time.monotonic()
        result = HeadingHierarchyModel(options=options).assign_heading_levels(
            doc.model_copy(deep=True), parsed_pages=pages, outline=outline)
        seconds = time.monotonic() - start
        after = result.model_dump(mode="json")
        assert doc.model_dump(mode="json") == before
        assert input_path.read_bytes() == original_source
        assert result.validate_tree(result.body, raise_on_error=True)
        assert DoclingDocument.model_validate(after).model_dump(mode="json") == after
        if name == "b0-n0-s0":
            assert after == before, "All-off differs from immutable baseline"
        diff = HELPERS.differences(before, after)
        allowed = {f"/texts/{i}/level" for i, item in enumerate(doc.texts) if isinstance(item, SectionHeaderItem)}
        write(result_dir / "document.json", after)
        (result_dir / "document.md").write_text(result.export_to_markdown())
        write(result_dir / "diff.json", diff)
        write(result_dir / "headings.json", HELPERS.headings(result))
        assessment = EVALUATOR.assess(after, scoped)
        write(result_dir / "assessment.json", assessment)
        equal_previous_all_rules = None
        previous = OLD / "heading" / job["id"] / "document-official.json"
        if name == "b1-n1-s1" and previous.exists():
            prior_imagefree = json.loads(previous.read_text())
            clear_images(prior_imagefree)
            equal_previous_all_rules = prior_imagefree == after
            assert equal_previous_all_rules, "All-rules output differs from earlier same-input stage"
        summary = {"id": job["id"], "family": family, "registered_family": job["family"], "set": job["set"], "combination": name,
            "baseline_sha256": HELPERS.sha(input_path), "effective_options": options.model_dump(mode="json"),
            "stage_seconds": seconds, "changed_fields": len(diff),
            "level_only": all(v["path"] in allowed for v in diff),
            "nonlevel_changes": [v for v in diff if v["path"] not in allowed],
            "text_sequence_unchanged": [v.text for v in doc.texts] == [v.text for v in result.texts],
            "orig_and_provenance_unchanged": [(v.orig, v.prov) for v in doc.texts] == [(v.orig, v.prov) for v in result.texts],
            "actual_parents_unchanged": [v.parent for v in doc.texts] == [v.parent for v in result.texts],
            "structural_counts": report_counts(assessment["headings"]),
            "all_source_command_counts": assessment["counts"],
            "equal_round2_all_rules": equal_previous_all_rules,
            "in_scope_headings": len(scoped), "status": "completed"}
        summary["stage_input_images_cleared"] = True
        write(result_dir / "summary.json", summary)
        summaries[name], assessed[name] = summary, assessment
    for name in summaries:
        summaries[name]["versus_baseline"] = changed(baseline_assessment["headings"], assessed[name]["headings"])
        summaries[name]["versus_all_rules"] = changed(assessed["b1-n1-s1"]["headings"], assessed[name]["headings"])
        write(output / name / "summary.json", summaries[name])
    write(output / "summary.json", summaries)
    return summaries

def selfcheck():
    assert len(COMBINATIONS) == 8 and len({name for name, _ in COMBINATIONS}) == 8
    assert COMBINATIONS[0][0] == "b0-n0-s0" and COMBINATIONS[-1][0] == "b1-n1-s1"
    assert all(HeadingHierarchyOptions(enabled=True, **v).use_font_style is True for _, v in COMBINATIONS)
    images = {"a": [{"image": {"uri": "bytes"}, "text": "same"}]}
    assert len(clear_images(images)) == 1 and images == {"a": [{"image": None, "text": "same"}]}
    EVALUATOR.selfcheck()
    assert changed([{"status": "correct"}, {"status": "level_error"}],
                   [{"status": "level_error"}, {"status": "correct"}])["new_bad"] == 1
    print("eight-way heading selfcheck passed")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--id", action="append")
    parser.add_argument("--controls-evidence")
    args = parser.parse_args()
    selfcheck()
    if not args.run:
        return
    method = {"scope": "Eight official rule combinations on original saved baseline copies. No conversion, no model inference. No numeric thresholds changed. Inputs readonly; native render/bitmap/fetch off.",
        "packages": {k: importlib.metadata.version(k) for k in ("docling-slim", "docling-core", "docling-parse")},
        "options": {name: HeadingHierarchyOptions(enabled=True, **v).model_dump(mode="json") for name, v in COMBINATIONS},
        "runner_sha256": HELPERS.sha(Path(__file__)), "evaluator_path": str(OLD / "heading/assess_headings.py"),
        "evaluator_sha256": HELPERS.sha(OLD / "heading/assess_headings.py"),
        "controls_evidence": args.controls_evidence,
        "inference_note": "Official library imports may transitively import torch/transformers; no neural model/weights constructed or executed."}
    write(OUT / "method.json", method)
    raw = json.loads((ROOT / "baseline-inputs.json").read_text())
    mapping = raw.get("jobs", raw)
    jobs = json.loads((OLD / "jobs.json").read_text())["jobs"]
    results = {}
    for job in jobs:
        if args.id and job["id"] not in args.id:
            continue
        if job["id"] not in mapping:
            results[job["id"]] = {"status": "baseline_unavailable"}
            continue
        entry = mapping[job["id"]]
        input_dir = entry.get("job_dir", entry.get("directory")) if isinstance(entry, dict) else entry
        if not input_dir or not (Path(input_dir) / "document.json").exists():
            results[job["id"]] = {"status": "baseline_unavailable"}
            continue
        conversion = Path(input_dir) / "conversion.json"
        if conversion.exists() and json.loads(conversion.read_text()).get("status") != "success":
            results[job["id"]] = {"status": "baseline_unavailable"}
            continue
        results[job["id"]] = run_job(job, input_dir)
        write(OUT / "results.json", results)
        print(f"{job['id']} eight combinations completed", flush=True)
    write(OUT / "results.json", results)

if __name__ == "__main__":
    main()

