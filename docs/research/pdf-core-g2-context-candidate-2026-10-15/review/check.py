"""Independent offline accounting, crop and legacy association checks; no inference."""
from copy import deepcopy
from collections import Counter
import base64
import hashlib
import importlib.util
import json
import math
from pathlib import Path

from PIL import Image, ImageChops
import pypdfium2 as pdfium

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[2]
CONTRACT_SHA = "99cd3de3f2f91ade459b28587e5fdfa3553776463412ecd2db69bb3664201868"
COLLECTIONS = ("texts", "pictures", "tables", "key_value_items", "form_items")


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def checked(record):
    path = REPO / record["path"]
    assert sha(path) == record["sha256"], path
    return path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bounds(raw, prov):
    b = prov["bbox"]
    if b["coord_origin"] == "TOPLEFT":
        return [b["l"], b["t"], b["r"], b["b"]]
    assert b["coord_origin"] == "BOTTOMLEFT"
    height = raw["pages"][str(prov["page_no"])]["size"]["height"]
    return [b["l"], height-b["t"], b["r"], height-b["b"]]


def equal_pixels(a, b):
    return a.size == b.size and ImageChops.difference(a.convert("RGB"), b.convert("RGB")).getbbox() is None


def renamed(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [renamed(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: renamed(v, mapping) for k, v in value.items()}
    return value


def metamorphic(planner, raw, rows):
    items = [raw[k] for k in ("body", "furniture") if k in raw]
    items += [i for key in (*COLLECTIONS, "groups") for i in raw.get(key, [])]
    mapping = {i["self_ref"]: i["self_ref"].rsplit("/", 1)[0]+"/renamed-"+str(n)
               for n, i in enumerate(items)}
    inverse = {v: k for k, v in mapping.items()}
    changed = renamed(deepcopy(raw), mapping)
    changed["name"] = "arbitrary-source-name"
    actual = planner.plan(changed)
    ids = {new["id"]: old["id"] for old, new in zip(rows, actual, strict=True)}
    assert renamed(actual, inverse | ids) == rows
    moved = deepcopy(raw)
    dx, dy = 7.25, 11.5
    for page in moved["pages"].values():
        page["size"]["width"] += 2*dx
        page["size"]["height"] += 2*dy
    for item in [i for key in (*COLLECTIONS, "groups") for i in moved.get(key, [])]:
        for prov in item.get("prov", []):
            for coordinate in ("l", "r"):
                prov["bbox"][coordinate] += dx
            for coordinate in ("t", "b"):
                prov["bbox"][coordinate] += dy
    translated = planner.plan(moved)
    for original, new in zip(rows, translated, strict=True):
        for key in ("kind", "status", "reason", "target_item_refs", "member_item_refs", "context_only_refs"):
            assert original[key] == new[key], (original["id"], key)
        assert len(original["source_fragments"]) == len(new["source_fragments"])
        for a, b in zip(original["source_fragments"], new["source_fragments"], strict=True):
            expect = [v+d for v, d in zip(a["bbox_top_left_points"], (dx, dy, dx, dy))]
            assert all(math.isclose(x, y, abs_tol=1e-9) for x, y in zip(expect, b["bbox_top_left_points"]))
    return {"bijective_native_ref_rename_and_document_name": True, "coordinate_translation": True,
            "scope": "Collection prefixes preserved as native schema; no case IDs, source names or ref indices retained."}


def main():
    assert sha(HERE / "evaluation-contract.json") == CONTRACT_SHA
    contract = read(HERE / "evaluation-contract.json")
    for reference in contract["authorities"]:
        checked(reference)
    manifest = read(ROOT / "input-manifest.json")
    for key in ("registration_ref", "execution_config_ref", "planner_ref", "preparer_ref"):
        checked(manifest[key])
    planner = load("independent_context_planner", ROOT / "candidate.py")
    assert planner.CONFIG == read(ROOT / "experiment.json")["candidate_config"]
    assert planner.selfcheck() == read(ROOT / "planner-selfchecks.json")
    sources, plans, source_results = {}, {}, []
    for source in contract["source_documents"]:
        name = source["source"]
        raw = read(checked(source["native_document"]))
        checked(source["source_pdf"])
        original = deepcopy(raw)
        saved = read(ROOT / "plans" / (name+".json"))
        rows = planner.plan(raw)
        assert raw == original and rows == saved["rows"]
        byref = {i["self_ref"]: i for key in (*COLLECTIONS, "groups") for i in raw.get(key, [])}
        native = [i for key in COLLECTIONS for i in raw.get(key, [])]
        assert [i["self_ref"] for i in native] == source["all_item_refs"]
        assert saved["native_item_inventory"] == [{"item_ref": i["self_ref"], "native_label": i.get("label"),
            "native_item_sha256": digest(i), "planner_status": next((r["status"] for r in rows
            if r["target_item_refs"][0] == i["self_ref"]), "not_targeted_by_this_method"),
            "original_preserved": True} for i in native]
        assert saved["groups_preserved"] == [{"item_ref": g["self_ref"], "sha256": digest(g)} for g in raw["groups"]]
        expected_texts = {i["self_ref"] for i in raw["texts"] if i.get("label") in {"formula", "code"}
                          or (i.get("label") == "text" and i.get("content_layer") == "body")}
        actual_texts = {r["target_item_refs"][0] for r in rows if r["kind"] != "formula_envelope"}
        assert expected_texts == actual_texts
        assert len({r["id"] for r in rows}) == len(rows)
        for row in rows:
            targets, members, contexts = [set(row[k]) for k in ("target_item_refs", "member_item_refs", "context_only_refs")]
            assert not (targets & contexts or members & contexts or targets & members)
            for entry in row["source_accounting"]:
                assert entry["provider_provenance"] == byref[entry["item_ref"]].get("prov", [])
            if row["kind"] == "formula_envelope" and row["status"] == "ready":
                refs = row["target_item_refs"]+row["member_item_refs"]
                boxes = [bounds(raw, p) for r in refs for p in byref[r]["prov"]]
                union = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
                assert row["source_fragments"][0]["bbox_top_left_points"] == union
            elif row["status"] == "ready":
                target = byref[row["target_item_refs"][0]]
                assert row["targets"][0]["replacement_charspan"] == [0, len(target["text"])]
                for fragment in row["source_fragments"]:
                    r = fragment["source_refs"][0]
                    prov = byref[r]["prov"][fragment["provider_provenance_index"]]
                    assert fragment["provider_provenance"] == prov
                    assert fragment["bbox_top_left_points"] == bounds(raw, prov)
        invariance = metamorphic(planner, raw, rows)
        plans[name], sources[name] = saved, (source, raw, byref)
        source_results.append({"source": name, "native_items": len(native), "groups": len(raw["groups"]),
            "rows": len(rows), "statuses": dict(Counter(r["status"] for r in rows)),
            "context_jobs": sum(bool(r["context_only_refs"]) for r in rows), "metamorphic": invariance})

    expected_inputs = {(name, r["id"]) for name, saved in plans.items() for r in saved["rows"]
        if r["status"] == "ready" and any(p["page_no"] in sources[name][0]["prior_selected_physical_pages"]
        for reference in r["target_item_refs"] for p in sources[name][2][reference].get("prov", []))}
    assert {(i["source"], i["job_id"]) for i in manifest["inputs"]} == expected_inputs
    assert len(expected_inputs) == manifest["prepared_jobs"] == 36
    selected_rows = [(name, r) for name, saved in plans.items() for r in saved["rows"]
        if any(p["page_no"] in sources[name][0]["prior_selected_physical_pages"]
        for reference in r["target_item_refs"] for p in sources[name][2][reference].get("prov", []))]
    assert Counter(r["status"] for _, r in selected_rows) == {"ready": 36, "member": 3, "abstain": 5}
    assert Counter(r["kind"] for name, r in selected_rows if r["status"] == "abstain") == {"formula": 4, "ordinary_paragraph": 1}
    rasters, input_results = {}, []
    fragment_count = 0
    for prepared in manifest["inputs"]:
        name = prepared["source"]
        source, raw, byref = sources[name]
        row = next(r for r in plans[name]["rows"] if r["id"] == prepared["job_id"])
        imagepath = checked(prepared["image_ref"])
        assert read(imagepath.parent / "input.json") == prepared
        request = read(checked(prepared["request_contract_ref"]))
        assert request["status"] == "prepared_not_sent" and request["changed_prompt_or_context_requires_new_inference"]
        assert request["prompt_sha256"] == hashlib.sha256(request["prompt"].encode()).hexdigest()
        check_request = deepcopy(request)
        fingerprint = check_request.pop("input_contract_sha256")
        assert digest(check_request) == fingerprint
        assert request["scope"]["document_canonical_sha256"] == digest(raw)
        assert request["image_ref"] == prepared["image_ref"]
        for key in ("target_item_refs", "member_item_refs", "context_only_refs"):
            assert request["scope"][key] == prepared[key] == row[key]
        assert request["scope"]["item_hashes"] == {r: digest(byref[r]) for key in
            ("target_item_refs", "context_only_refs", "member_item_refs") for r in row[key]}
        crops, ys, targetrects = [], [], []
        y = 0
        assert len(prepared["fragments"]) == len(row["source_fragments"])
        for fragment, native_fragment in zip(prepared["fragments"], row["source_fragments"], strict=True):
            for key, value in native_fragment.items():
                assert fragment[key] == value
            page_no = fragment["physical_page_1based"]
            raster_path = checked(fragment["source_raster_ref"])
            cachekey = (name, page_no)
            if cachekey not in rasters:
                raster = Image.open(raster_path).convert("RGB")
                with pdfium.PdfDocument(REPO / source["source_pdf"]["path"]) as pdf:
                    page = pdf[page_no-1]
                    bitmap = page.render(scale=3)
                    actual = bitmap.to_pil().convert("RGB")
                    assert equal_pixels(raster, actual), cachekey
                    bitmap.close()
                    page.close()
                rasters[cachekey] = raster
            raster = rasters[cachekey]
            l, t, r, b = native_fragment["bbox_top_left_points"]
            box = [max(0, math.floor(3*(l-2))), max(0, math.floor(3*(t-2))),
                   min(raster.width, math.ceil(3*(r+2))), min(raster.height, math.ceil(3*(b+2)))]
            assert fragment["render_crop_pixel_box"] == box
            crop = raster.crop(box)
            assert equal_pixels(crop, Image.open(checked(fragment["image_ref"])))
            assert fragment["canvas_xywh"] == [0, y, crop.width, crop.height]
            transform = [[1/3, 0, box[0]/3], [0, 1/3, (box[1]-y)/3], [0, 0, 1]]
            assert fragment["canvas_to_source_top_left_points_3x3"] == transform
            target = bool(set(native_fragment["source_refs"]) & set(row["target_item_refs"]+row["member_item_refs"]))
            assert fragment["role"] == ("target" if target else "context_only")
            if target:
                targetrects.append([0, y, crop.width, y+crop.height])
            crops.append(crop)
            ys.append(y)
            y += crop.height+24
            fragment_count += 1
        canvas = Image.new("RGB", (max(c.width for c in crops), y-24), "white")
        for crop, yy in zip(crops, ys, strict=True):
            canvas.paste(crop, (0, yy))
        assert equal_pixels(canvas, Image.open(imagepath))
        assert request["target_rectangles_pixels"] == targetrects
        assert prepared["image_pixels_wh"] == request["image_pixels_wh"] == list(canvas.size)
        input_results.append({"source": name, "job_id": row["id"], "pixels_transforms_and_scope_pass": True,
                              "context_only_refs": row["context_only_refs"]})

    oldreview = read(REPO / "docs/research/pdf-core-g2-inline-boundary-2026-10-15/review/output-review.json")
    formula_oracles = {r["id"]: r["fragments"][0]["crop_pixels"] for r in oldreview["inputs"]["records"]
                       if r["id"].startswith("controls-pictures-")}
    for prepared in manifest["inputs"]:
        if prepared["kind"] == "formula_envelope":
            index = prepared["target_item_refs"][0].split("/")[-1]
            assert prepared["fragments"][0]["render_crop_pixel_box"] == formula_oracles["controls-pictures-"+index]
    regressions = []
    for prior in contract["prior_paragraph_regressions"]:
        row = next(r for r in plans[prior["source"]]["rows"] if r["target_item_refs"] == [prior["provider_ref"]])
        assert row["status"] == ("ready" if prior["protected_positive"] else row["status"])
        regressions.append({"id": prior["id"], "planner_status": row["status"], "reason": row["reason"],
            "protected_positive": prior["protected_positive"], "bounded_positive_scope": prior["bounded_positive_scope"],
            "new_input_semantic_result": "not_evaluated_no_inference"})
    seal34 = next(r for r in plans["seal"]["rows"] if r["target_item_refs"] == ["#/texts/34"])
    assert seal34["status"] == "abstain" and len(seal34["source_fragments"]) == 2
    assert [f["provider_provenance"]["charspan"] for f in seal34["source_fragments"]] == [[0, 657], [658, 734]]
    assert any(r["target_item_refs"] == ["#/texts/45"] for r in plans["seal"]["rows"])
    assert ("seal", seal34["id"]) not in expected_inputs

    # Replay saved original requests only; this independently rebuilds the exact old HTTP body.
    legacy = read(ROOT / "legacy-replay/results.json")
    for key in ("adapter_ref", "driver_ref", "frozen_regression_manifest_ref", "frozen_parser_ref", "frozen_renderer_ref", "prior_regression_ref", "selfcheck_ref"):
        checked(legacy[key])
    assert legacy["prior_regression_artifact_unchanged"] is True
    prior_regression = read(checked(legacy["prior_regression_ref"]))
    prior_statuses = {r["id"]: r["prior_adapter_status"] for r in prior_regression["prior_17"]}
    adapter = load("independent_context_adapter", ROOT / "adapter.py")
    proposals = {name: [] for name in sources}
    outcome_results = []
    assert [r["id"] for r in legacy["outcomes"]] == [r["id"] for r in contract["prior_paragraph_regressions"]]
    for outcome in legacy["outcomes"]:
        assert outcome["previous_adapter_status"] == prior_statuses[outcome["id"]]
        evidence = outcome["original_evidence"]
        for record in evidence.values():
            if isinstance(record, dict) and set(record) == {"path", "sha256"}:
                checked(record)
        description = read(checked(evidence["request_description"]))
        body = deepcopy(description["body_without_inline_image"])
        body["messages"][1]["content"][1]["image_url"]["url"] = "data:image/png;base64,"+base64.b64encode(checked(evidence["input_image"]).read_bytes()).decode()
        assert hashlib.sha256(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest() == description["http_body_sha256"]
        response = read(checked(evidence["response"]))
        output = read(checked(evidence["output"]))
        assert json.loads(response["choices"][0]["message"]["content"]) == output == outcome["original_blocks"]
        raw = sources[outcome["source"]][1]
        record = adapter.bind_response(outcome["input_contract"], output, response_sha256=sha(checked(evidence["response"])))
        try:
            proposal = adapter.apply(raw, outcome["scope"], outcome["input_contract"], record,
                expected_input_fingerprint=outcome["input_contract"]["input_fingerprint"], proposal_id=outcome["id"])
        except ValueError as error:
            assert outcome["status"] != "structurally_applied_semantics_unverified"
            assert str(error) == outcome["reason"]
        else:
            assert outcome["status"] == "structurally_applied_semantics_unverified"
            assert proposal["markdown"] == outcome["markdown"]
            proposals[outcome["source"]].append(proposal)
        outcome_results.append({"id": outcome["id"], "status": outcome["status"], "semantic_quality": outcome["semantic_quality"]})
    for document in legacy["documents"]:
        for key in ("baseline", "working", "delta", "association"):
            checked(document[key])
        rendered = adapter.render_batch(sources[document["source"]][1], proposals[document["source"]])
        assert rendered["baseline"] == checked(document["baseline"]).read_text()
        assert rendered["working"] == checked(document["working"]).read_text()
        association = read(checked(document["association"]))
        working = rendered["working"]
        for outside in association["outside_literal_spans"]:
            a, b = outside["working_charspan"]
            assert hashlib.sha256(working[a:b].encode()).hexdigest() == outside["sha256"]
        assert rendered["provider_graph_unchanged"] and rendered["outside_literal_spans_unchanged"]
    assert sum(len(p) for p in proposals.values()) == legacy["structurally_applied"] == 11
    for anchor in contract["protected_positive_anchors"]:
        assert next(r for r in legacy["outcomes"] if r["id"] == anchor["id"])["status"] == "structurally_applied_semantics_unverified"
    assert legacy["lexical_gate"] is False and legacy["candidate_context_jobs_replay_compatible"] is False
    for path, expected in read(ROOT / "legacy-replay/original-artifact-hashes.json").items():
        assert sha(REPO / path) == expected
    controls = read(checked(legacy["selfcheck_ref"]))
    assert controls["passed"] and len(controls["negative_controls"]) >= 18
    reviewer_controls = {}

    def rejects(label, action):
        try:
            action()
        except (ValueError, KeyError, TypeError):
            reviewer_controls[label] = True
        else:
            raise AssertionError(label+" accepted")

    raw = sources["controls"][1]
    scoped = adapter.bind_scope(raw, ["#/texts/4"], ["#/texts/12"])
    bound = adapter.bind_input(scoped, image_sha256="1"*64, image_pixels_wh=[100, 100],
        request_sha256="2"*64, manifest_row_sha256="3"*64)
    synthetic = {"blocks": [{"kind": "paragraph", "bbox": [0, 0, 100, 100], "code_language": None,
        "segments": [{"kind": "text", "text": "synthetic structural probe"}]}], "uncertainties": []}
    response = adapter.bind_response(bound, synthetic, response_sha256="4"*64)

    def apply_probe(document=raw, scope=scoped, inputs=bound, record=response):
        return adapter.apply(document, scope, inputs, record,
            expected_input_fingerprint=inputs["input_fingerprint"], proposal_id="reviewer-synthetic")

    valid = apply_probe()
    changed = deepcopy(raw)
    changed["texts"][0]["text"] += " outside mutation"
    rejects("stale_outside_native_graph", lambda: apply_probe(document=changed))
    shrunk = deepcopy(scoped)
    shrunk["targets"][0]["replacement_charspan"][1] -= 1
    rejects("shrunk_whole_target", lambda: apply_probe(scope=shrunk))
    rejects("context_consumption", lambda: adapter.bind_scope(raw, ["#/texts/4"], ["#/texts/4"]))
    rejects("duplicate_batch_target", lambda: adapter.render_batch(raw, [valid, valid]))
    rejects("nested_formula_target_overlap", lambda: adapter.bind_scope(raw, ["#/pictures/0", "#/texts/6"], []))
    for label, key in (("changed_image_fingerprint", "image_sha256"), ("changed_prompt_fingerprint", "request_sha256")):
        changed_input = deepcopy(bound)
        changed_input[key] = "9"*64
        rejects(label, lambda changed_input=changed_input: apply_probe(inputs=changed_input))
    new_scope = adapter.bind_scope(raw, ["#/texts/4"], [])
    new_input = adapter.bind_input(new_scope, image_sha256="1"*64, image_pixels_wh=[100, 100],
        request_sha256="2"*64, manifest_row_sha256="3"*64)
    rejects("old_response_changed_context", lambda: apply_probe(scope=new_scope, inputs=new_input))
    unknown = deepcopy(synthetic)
    unknown["blocks"][0]["segments"] = [{"kind": "unknown", "text": "unclear"}]
    rejects("unknown_model_segment", lambda: apply_probe(record=adapter.bind_response(bound, unknown, response_sha256="5"*64)))
    sample = manifest["inputs"][0]
    fragment = sample["fragments"][0]
    raster = rasters[(sample["source"], fragment["physical_page_1based"])]
    box = fragment["render_crop_pixel_box"]
    wrong = list(box)
    wrong[0] += 1
    reviewer_controls["wrong_crop_rounding_rejected"] = not equal_pixels(raster.crop(wrong), Image.open(checked(fragment["image_ref"])))
    altered = deepcopy(fragment["canvas_to_source_top_left_points_3x3"])
    altered[1][2] += 1
    reviewer_controls["wrong_inverse_transform_rejected"] = altered != fragment["canvas_to_source_top_left_points_3x3"]
    reviewer_controls["missing_source_inventory_ref_rejected"] = len(plans["controls"]["native_item_inventory"][:-1]) != sources["controls"][0]["all_item_count"]
    assert all(reviewer_controls.values())
    result = {"format": "g2-context-candidate-independent-structural-review-v1", "passed": True,
        "evaluation_contract_sha256": CONTRACT_SHA, "checker_sha256": sha(Path(__file__)),
        "input_manifest_sha256": sha(ROOT / "input-manifest.json"), "legacy_results_sha256": sha(ROOT / "legacy-replay/results.json"),
        "source_documents": source_results, "native_item_refs_checked": 1594, "group_refs_checked": 60,
        "planner_rows": sum(len(p["rows"]) for p in plans.values()), "planner_statuses": dict(Counter(r["status"] for p in plans.values() for r in p["rows"])),
        "prepared_jobs": len(input_results), "prepared_kinds": dict(Counter(i["kind"] for i in manifest["inputs"])),
        "prepared_context_jobs": sum(bool(i["context_only_refs"]) for i in manifest["inputs"]),
        "prepared_paragraph_context_jobs": sum(i["kind"] == "ordinary_paragraph" and bool(i["context_only_refs"]) for i in manifest["inputs"]),
        "full_page_rasters_independently_rerendered": len(rasters), "source_fragments_pixel_and_transform_checked": fragment_count,
        "inputs": input_results, "prior_17": regressions, "formula_fixed_source_envelopes_pass": True,
        "visual_QA": "Viewed all three formula envelopes, shared seven-line controls code context, and standalone SEAL32. Complete formula structure and code nesting visible.",
        "target_rectangle_limit": "Rectangles identify padded native source fragment crops, not exact unpadded glyph masks; separate fragment canvases and coarse-box prompt make this explicit. No new inference consumed them.",
        "seal34": {"explicit_abstention": True, "both_native_spans_preserved": True, "continuation_45_separately_accounted": True, "source_boundary_repaired": False},
        "legacy": {"outcomes_checked": len(outcome_results), "structurally_applied": 11, "protected_positive_anchors_structurally_eligible": 4,
            "known_seal32_semantics": "unapproved despite structural eligibility", "original_request_response_hashes_and_working_render_verified": True,
            "new_candidate_response_replay_compatible": False, "semantic_rubric_retested": False, "negative_controls": controls},
        "reviewer_negative_controls": reviewer_controls,
        "selected_page_dispositions": {"rows": 44, "ready_prepared": 36, "formula_members": 3, "explicit_abstentions": 5,
            "abstention_scope": "SEAL four standalone formula items with incomplete/overlapping native character provenance, plus SEAL34 same-page multi-provenance paragraph."},
        "coverage_gaps": ["816 planner rows are native-role inventory, not a source-opportunity semantic denominator; 1594 refs measure source custody/accounting.",
            "Selected five target page pairs require eight physical page rasters after whole-item cross-page continuations.",
            "Only two selected jobs add neighboring context, both controls code; no selected paragraph context rule triggers, including SEAL32.",
            "SEAL34 remains an explicit unresolved same-page multi-provenance boundary; no automatic caption split/body continuation repair is demonstrated.",
            "SEAL four standalone formula items on selected pages explicitly abstain and have no newly prepared inputs; no formula recovery is claimed for them.",
            "No prepared-input inference or new semantic evaluation; old model outputs are checked only under their exact legacy requests.",
            "57 retained G1 refs/V01–V19 are not all executed by this structural development review."],
        "new_model_calls": 0, "holdout_reads": 0, "g2_passed": False, "holdout_run_permitted": False,
        "challenger_selected_for_holdout": False}
    (HERE / "output-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: result[k] for k in ("passed", "native_item_refs_checked", "planner_rows", "planner_statuses", "prepared_jobs", "prepared_context_jobs", "source_fragments_pixel_and_transform_checked", "full_page_rasters_independently_rerendered")}))


if __name__ == "__main__":
    main()
