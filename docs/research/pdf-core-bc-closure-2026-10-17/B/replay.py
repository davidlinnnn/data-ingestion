"""Save source-independent controls and recheck old evidence; never invoke a model."""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path

from docling_core.types.doc import DoclingDocument, RefItem
from PIL import Image

import method as m
import test_method as t

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / "docs/research/pdf-core-stage1-followup-2026-10-17"


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    registration = json.loads((HERE / "registration.json").read_text())
    assert datetime.now(timezone.utc) < datetime.fromisoformat(registration["deadline"])
    data, supplement = m.normalized_panel(t.fixture())
    baseline, keys, payload, _ = t.gate.fixture()
    payload["targets"][0]["panels"][0]["data"] = data
    out, bindings = m.adapter.map_response(baseline, payload, 1, keys)
    bindings[0]["semantic_supplement"] = supplement
    save("synthetic-semantic-input.json", t.fixture())
    save("synthetic-document.json", out.model_dump(mode="json"))
    save("synthetic-bindings.json", bindings)
    markdown = m.adapter.export_markdown(out, bindings)
    (HERE / "synthetic-document.md").write_text(markdown)
    tables, html = t.gate.rendered_tables(markdown)
    (HERE / "synthetic-rendered.html").write_text(html)
    save("synthetic-rendered-tables.json", tables)
    multi = t.MultipageControls(); multi.setUp()
    doc, binding = m.replace_already_logical_table(multi.baseline, multi.table.self_ref, multi.digest, multi.data)
    save("synthetic-multipage-baseline.json", multi.baseline.model_dump(mode="json"))
    save("synthetic-multipage-document.json", doc.model_dump(mode="json"))
    save("synthetic-multipage-binding.json", binding)
    (HERE / "synthetic-multipage-document.md").write_text(m.adapter.export_markdown(doc))

    padding = load("bc_prior_padding", OLD / "B-padding/method.py")
    old_registration = json.loads((OLD / "B/live-registration.json").read_text())
    inventory = []
    for job in old_registration["jobs"]:
        image_path = Path(job["image"])
        if not image_path.is_absolute():
            image_path = ROOT / image_path
        assert sha256(image_path.read_bytes()).hexdigest() == job["image_sha256"]
        with Image.open(image_path) as image:
            size = list(image.size)
        assert size == job["image_size"]
        inventory.append({key: job[key] for key in ("name", "page_name", "target_key",
            "physical_page", "source_path", "source_sha256", "baseline", "baseline_sha256",
            "image", "image_sha256", "image_size", "crop_box_full_pixels")})
    math_baseline_path = ROOT / "docs/research/pdf-core-native-round-2026-10-17/S0/wikiskill/document.json"
    math_doc = DoclingDocument.model_validate_json(math_baseline_path.read_text())
    math_table = RefItem(cref="#/tables/2").resolve(math_doc)
    assert list(m.adapter.inventory(math_doc, 22)) == ["p22:#/tables/2"]
    native_image = math_table.get_image(math_doc)
    assert native_image is not None and native_image.width > 0 and native_image.height > 0
    crop_path = HERE / "wikiskill-p22-table7-native.png"
    native_image.save(crop_path)
    prov = math_table.prov[0]
    page = math_doc.pages[22]
    pixel_box = prov.bbox.to_top_left_origin(page_height=page.size.height).scale_to_size(
        old_size=page.size, new_size=page.image.size)
    page_crop = page.image.pil_image.crop(pixel_box.as_tuple())
    assert page_crop.size == native_image.size and page_crop.tobytes() == native_image.tobytes()
    inventory.append({"name": "wikiskill-p22-table7", "page_name": "wikiskill-p22",
        "target_key": "p22:#/tables/2", "physical_page": 22,
        "source_path": "docs/fixtures/agent-self-evolution-pilot-2026-10-11/01-2608.27454v1.pdf",
        "source_sha256": "65afc6e12f6f707483fe1b79a97ab67c03abf4b4992f82fde03eb7b8d9ad4a69",
        "baseline": str(math_baseline_path.relative_to(ROOT)),
        "baseline_sha256": sha256(math_baseline_path.read_bytes()).hexdigest(),
        "image": str(crop_path.relative_to(ROOT)), "image_sha256": sha256(crop_path.read_bytes()).hexdigest(),
        "image_size": list(native_image.size), "crop_box_full_pixels": list(pixel_box.as_tuple()),
        "input_method": "public TableItem.get_image from cached page image; no padding or oracle bbox",
        "source_provenance": [p.model_dump(mode="json") for p in math_table.prov],
        "math_source_groups": ["E017", "E018", "E019", "E020"],
        "source_meaning_evidence": "docs/research/pdf-core-stage1-followup-2026-10-17/A-review/native-delivery-evidence.json",
        "caption_ref": [r.cref for r in math_table.captions]})
    assert len(inventory) == 7 and len({j["name"] for j in inventory}) == 7
    save("proposed-input-inventory.json", {"jobs": inventory, "calls_max_proposed": 7,
        "live_ready": False, "new_calls_this_round": 0,
        "not_ready_reasons": ["new model producer/prompt/response contract not frozen",
            "input/output/time/memory/transport budgets and runner controls not registered for the new representation"],
        "denominators": {"original_numeric": 470, "original_comparisons": 23,
            "original_collateral": 2, "table_math_groups_separate": 4, "T03_crosspage_not_included": True}})
    raw_gates = []
    for job in old_registration["jobs"]:
        source = OLD / "B/live" / job["name"] / "content.txt"
        raw = source.read_bytes()
        try:
            parsed, slots = padding.parse(json.loads(raw), [job["target_key"]])
            result = {"accepted_by_unchanged_padding_protocol": True, "padding_slots": slots}
        except (ValueError, TypeError) as exc:
            result = {"accepted_by_unchanged_padding_protocol": False, "error": str(exc)}
        raw_gates.append({"job": job["name"], "raw_sha256": sha256(raw).hexdigest(), **result})
    save("old-raw-gates.json", raw_gates)

    checker = load("bc_original_compare_only", OLD / "check.py")
    source_hashes = json.loads((HERE / "source-hashes.json").read_text())
    checker.compare_hashes(ROOT, source_hashes)
    history_dir = OLD.parent / "pdf-core-stage1-2026-10-17"
    historical = checker.compare_hashes(history_dir, {r["path"]: r["sha256"]
        for r in json.loads((history_dir / "artifact-hashes.json").read_text())})
    live = checker.compare_hashes(OLD / "B", {r["path"]: r["sha256"]
        for r in json.loads((OLD / "B/live-artifact-hashes.json").read_text())})
    audit = json.loads((OLD / "contract-audit-verification.json").read_text())
    checker.compare_hashes(ROOT, audit["inputs"]); checker.compare_hashes(OLD, audit["outputs"])
    current = json.loads((OLD / "ABC-followup-verification.json").read_text())
    checker.compare_hashes(ROOT, current["files"])
    record = {"completed_at": datetime.now(timezone.utc).isoformat(),
        "historical_artifacts_unchanged": historical, "live_artifacts_unchanged": live,
        "prior_ABC_artifacts_unchanged": len(current["files"]),
        "original_protocol_accepted_targets": sum(r["accepted_by_unchanged_padding_protocol"] for r in raw_gates),
        "new_semantic_source_accuracy": "not measured; synthetic transport only",
        "new_model_calls": 0, "api_calls": 0, "holdout_reads": 0}
    save("replay-verification.json", record)
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
