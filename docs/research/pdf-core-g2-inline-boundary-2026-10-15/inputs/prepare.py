"""Expand provider boundaries and freeze six image inputs without inference or oracle boxes."""

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OLD = REPO / "docs/research/pdf-core-g2-inline-2026-10-15"
API_OLD = REPO / "docs/research/pdf-core-g2-inline-api-2026-10-15"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
SEAL_CHECKPOINT = REPO / "docs/research/paper-pdf-functional-2026-10-11/remaining-group5/17-2506.10943v1/group-001/checkpoints/page-0004.json"
CONTROL_CELLS = REPO / "docs/research/pdf-core-g2-heading-2026-10-15/runtime/controls-p1-final/parsed-page-0001.json"
SCALE, PAD, GAP = 3, 2, 24


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def ref(path, pointer=None):
    value = {"path": str(path.relative_to(REPO)), "sha256": sha(path)}
    if pointer is not None:
        value["json_pointer"] = pointer
    return value


def preserved():
    assert sha(REGISTRY) == "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
    manifests = []
    for path, count in [(OLD / "artifacts.json", 646), (API_OLD / "artifacts.json", 200)]:
        data = read(path)
        assert len(data["files"]) == count
        for file in data["files"]:
            assert sha(REPO / file["path"]) == file["sha256"], file["path"]
        manifests.append({**ref(path), "payload_count": count})
    return manifests


def top_left(provenance, document):
    box = provenance["bbox"]
    height = document["pages"][str(provenance["page_no"])]["size"]["height"]
    return [box["l"], box["t"], box["r"], box["b"]] if box["coord_origin"] == "TOPLEFT" else [box["l"], height-box["t"], box["r"], height-box["b"]]


def union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def normalized(text):
    return " ".join(text.split())


def continuation(document, item):
    first = item["prov"][0]
    box = top_left(first, document)
    start_text = item["text"][slice(*first["charspan"])].rstrip()
    if re.search(r"[.!?…:]$", start_text):
        raise ValueError("first fragment does not have an unfinished prose boundary")
    candidates = []
    for other in document["texts"]:
        if other["self_ref"] == item["self_ref"] or other["label"] != "text" or len(other["prov"]) != 1:
            continue
        p = other["prov"][0]
        if p["page_no"] != first["page_no"]:
            continue
        b = top_left(p, document)
        gap, height = b[1]-box[3], b[3]-b[1]
        if abs(b[0]-box[0]) <= 2 and 0 <= gap <= min(4, .5*height) and other["text"].lstrip()[:1].islower():
            candidates.append((gap, other))
    candidates.sort(key=lambda entry: entry[0])
    if not candidates or (len(candidates) > 1 and abs(candidates[0][0]-candidates[1][0]) < 1e-6):
        raise ValueError("no unique conservative spatial continuation")
    return candidates[0][1], candidates[0][0]


def make_crop(row, parts, source, document):
    folder = HERE / "images" / row["id"]
    folder.mkdir(parents=True, exist_ok=False)
    prior = read(OLD / "inputs/input-manifest.json")
    source_record = next(s for s in prior["sources"] if s["name"] == source)
    fragments, crops, offset = [], [], 0
    for index, part in enumerate(parts):
        page = part["physical_page_1based"]
        raster = next(p for p in source_record["full_page_renders"] if p["physical_page_1based"] == page)
        path = REPO / raster["path"]
        assert sha(path) == raster["sha256"]
        image = Image.open(path).convert("RGB")
        left, top, right, bottom = part["bbox_top_left_points"]
        pixel_box = [max(0, math.floor((left-PAD)*SCALE)), max(0, math.floor((top-PAD)*SCALE)),
            min(image.width, math.ceil((right+PAD)*SCALE)), min(image.height, math.ceil((bottom+PAD)*SCALE))]
        crop = image.crop(pixel_box)
        target = folder / f"fragment-{index}.png"
        crop.save(target)
        fragments.append({**part, "full_page_raster_ref": {"path": raster["path"], "sha256": raster["sha256"]},
            "crop_pixel_box": pixel_box, "image_ref": ref(target), "canvas_xywh": [0, offset, crop.width, crop.height],
            "canvas_pixels_to_source_top_left_points_3x3": [[1/SCALE, 0, pixel_box[0]/SCALE], [0, 1/SCALE, (pixel_box[1]-offset)/SCALE], [0, 0, 1]]})
        crops.append(crop)
        offset += crop.height+GAP
    canvas = Image.new("RGB", (max(c.width for c in crops), offset-GAP), "white")
    for crop, fragment in zip(crops, fragments, strict=True):
        canvas.paste(crop, tuple(fragment["canvas_xywh"][:2]))
    target = folder / "input.png"
    canvas.save(target)
    row.update(phase="boundary", image_path=str(target.relative_to(REPO)), image_sha256=sha(target), image_pixels_wh=list(canvas.size),
        source=source_record["source"], baseline_document_ref={"path": source_record["document_path"], "sha256": source_record["document_sha256"]},
        source_fragments=fragments, physical_pages_1based=sorted({p["physical_page_1based"] for p in parts}),
        render_scale=SCALE, padding_points=PAD, stitch_gap_pixels=GAP,
        mapping_precision="Producer component/paragraph regions and render-derived affine mapping; not measured model-token/glyph coordinates")
    return row


def prepare():
    old_manifests = preserved()
    controls = read(OLD / "inputs/baselines/controls/document.json")
    seal = read(OLD / "inputs/baselines/seal/document.json")
    seal_elements = [e["value"] for e in read(SEAL_CHECKPOINT)["assembled"]["elements"] if e["type"] == "TextElement"]
    jobs = []
    for picture in controls["pictures"]:
        children = [controls["texts"][int(child["$ref"].split("/")[-1])] for child in picture["children"] if child["$ref"].startswith("#/texts/")]
        if not children or any(child["label"] != "formula" for child in children):
            continue
        provenances = picture["prov"] + [p for child in children for p in child["prov"]]
        assert len({p["page_no"] for p in provenances}) == 1
        bounds = union([top_left(p, controls) for p in provenances])
        row = {"id": "controls-"+picture["self_ref"].replace("#/", "").replace("/", "-"),
            "selection_rule": "Floating formula boundary expands to union of parent picture and every child provenance; no child-only crop",
            "working_replacement_refs": [picture["self_ref"]], "consumed_item_refs": [picture["self_ref"]],
            "member_item_refs": [c["self_ref"] for c in children], "context_only_refs": [],
            "source_accounting": [{"item_ref": picture["self_ref"], "prov": picture["prov"]}] + [{"item_ref": c["self_ref"], "prov": c["prov"]} for c in children]}
        jobs.append(make_crop(row, [{"physical_page_1based": provenances[0]["page_no"], "bbox_top_left_points": bounds,
            "source_refs": [picture["self_ref"]]+[c["self_ref"] for c in children]}], "controls", controls))
    code_start = controls["texts"][12]
    body_refs = [r["$ref"] for r in controls["body"]["children"]]
    code_items = [code_start]
    for candidate_ref in body_refs[body_refs.index(code_start["self_ref"])+1:]:
        if not candidate_ref.startswith("#/texts/"):
            break
        candidate = controls["texts"][int(candidate_ref.split("/")[-1])]
        previous = code_items[-1]
        if candidate["label"] != "code" or candidate["parent"] != previous["parent"] or len(candidate["prov"]) != 1:
            break
        a, b = top_left(previous["prov"][0], controls), top_left(candidate["prov"][0], controls)
        if candidate["prov"][0]["page_no"] != previous["prov"][0]["page_no"] or abs(a[0]-b[0]) > 2 or not 0 <= b[1]-a[3] <= 14:
            break
        code_items.append(candidate)
    assert len(code_items) >= 2
    bounds = union([top_left(c["prov"][0], controls) for c in code_items])
    jobs.append(make_crop({"id": "controls-code-context", "selection_rule": "Uninterrupted adjacent same-parent CodeItems, one page, left edges within2pt and gap≤14pt; nested/group item excluded",
        "working_replacement_refs": [c["self_ref"] for c in code_items], "consumed_item_refs": [c["self_ref"] for c in code_items],
        "member_item_refs": [], "context_only_refs": [], "source_accounting": [{"item_ref": c["self_ref"], "prov": c["prov"]} for c in code_items]},
        [{"physical_page_1based": 1, "bbox_top_left_points": bounds, "source_refs": [c["self_ref"] for c in code_items]}], "controls", controls))
    item = seal["texts"][34]
    tail, gap = continuation(seal, item)
    caption_provenance = item["prov"][1]
    caption_text = item["text"][slice(*caption_provenance["charspan"])]
    old_caption_path = API_OLD / "api/paragraph--seal-texts-34/output.json"
    old_blocks = read(old_caption_path)["blocks"]
    matching = [i for i, block in enumerate(old_blocks) if normalized("".join(s["text"] or "" for s in block["segments"])) == normalized(caption_text)]
    assert len(matching) == 1
    caption_ref = {**ref(old_caption_path, f"/blocks/{matching[0]}"), "native_label": "text", "prior_model_role": old_blocks[matching[0]]["kind"],
        "provider_item_ref": item["self_ref"], "provider_provenance_index": 1, "provider_provenance": caption_provenance,
        "native_text_sha256": hashlib.sha256(caption_text.encode()).hexdigest(), "normalized_content_matches_native_fragment": True}
    parts = [{"physical_page_1based": p["page_no"], "bbox_top_left_points": top_left(p, seal), "source_refs": [reference], "provider_provenance": p}
        for p, reference in [(item["prov"][0], item["self_ref"]), (tail["prov"][0], tail["self_ref"])]]
    jobs.append(make_crop({"id": "seal-prose-continuation", "selection_rule": "Nearest lower text fragment: leftalign≤2pt, gap≤min(4pt,0.5*nextheight), unfinished firstfragment and lowercase successor; stitch separate spatial boxes to exclude parallel column",
        "working_replacement_refs": [item["self_ref"], tail["self_ref"]], "consumed_item_refs": [item["self_ref"], tail["self_ref"]],
        "member_item_refs": [], "context_only_refs": [], "continuation_gap_points": gap,
        "retained_spatial_fragment_reuse": caption_ref, "native_checkpoint_ref": ref(SEAL_CHECKPOINT),
        "source_accounting": [{"item_ref": item["self_ref"], "prov": item["prov"]}, {"item_ref": tail["self_ref"], "prov": tail["prov"]}]}, parts, "seal", seal))
    item = seal["texts"][32]
    body_refs = [r["$ref"] for r in seal["body"]["children"]]
    next_ref = body_refs[body_refs.index(item["self_ref"])+1]
    next_item = seal["texts"][int(next_ref.split("/")[-1])]
    first_box, next_box = top_left(item["prov"][0], seal), top_left(next_item["prov"][0], seal)
    assert item["text"].rstrip().endswith(":") and next_item["label"] == "formula" and 0 <= next_box[1]-first_box[3] <= 4
    jobs.append(make_crop({"id": "seal-paragraph-formula-context", "selection_rule": "Colon-ended body paragraph with immediately following same-page formula within4pt; following formula is context only",
        "working_replacement_refs": [item["self_ref"]], "consumed_item_refs": [item["self_ref"]], "member_item_refs": [],
        "context_only_refs": [next_ref], "native_checkpoint_ref": ref(SEAL_CHECKPOINT),
        "source_accounting": [{"item_ref": c["self_ref"], "prov": c["prov"]} for c in [item, next_item]]},
        [{"physical_page_1based": 4, "bbox_top_left_points": union([first_box, next_box]), "source_refs": [item["self_ref"], next_ref]}], "seal", seal))
    assert len(jobs) == 6
    inline = controls["texts"][14]
    inline_path = API_OLD / "api/paragraph--controls-texts-14/output.json"
    inline_blocks = read(inline_path)["blocks"]
    assert len(inline_blocks) == 1 and normalized("".join(s["text"] or "" for s in inline_blocks[0]["segments"])) == normalized(inline["text"])
    native_words = []
    box = top_left(inline["prov"][0], controls)
    for word in read(CONTROL_CELLS)["word_cells"]:
        rect = word["rect"]
        ys = [rect[f"r_y{i}"] for i in range(4)]
        if min(ys) >= box[1]-1 and max(ys) <= box[3]+1:
            native_words.append({"text": word["text"], "font_key": word.get("font_key"), "rect": rect})
    manifest = {"format": "g2-inline-boundary-inputs-v1", "prior_payload_manifests": old_manifests, "registry_ref": ref(REGISTRY),
        "method": "Six producer-derived context/boundary expansions; no source oracle coordinates/text or model answers used for crop selection",
        "model_input_policy": "PNG only plus generic complete-context instructions; source/reuse metadata and native text are not supplied to the model",
        "inputs": jobs, "reused_without_inference": {"inline_role": {**ref(inline_path), "target_ref": inline["self_ref"],
            "original_role": inline["label"], "working_role": inline_blocks[0]["kind"], "normalized_native_tokens_match": True,
            "native_word_style_evidence_ref": ref(CONTROL_CELLS), "native_word_styles": native_words}, "caption": caption_ref},
        "native_checkpoint_ref": ref(SEAL_CHECKPOINT), "native_cells_ref": ref(CONTROL_CELLS),
        "raw_graph_mutation": False, "api_calls": 0, "new_model_inference": 0}
    save(HERE / "input-manifest.json", manifest)
    save(HERE / "method.json", {"preparer_ref": ref(Path(__file__).resolve()), "input_manifest_ref": ref(HERE / "input-manifest.json"),
        "source_context_evidence": [ref(SEAL_CHECKPOINT), ref(CONTROL_CELLS)], "new_jobs": 6, "render_scale": SCALE, "padding_points": PAD,
        "continuation_guard": "Spatial/orthographic heuristic, not a general paragraph-boundary or source-truth proof", "old_payloads_unchanged": True})


def verify():
    preserved()
    manifest, method = read(HERE / "input-manifest.json"), read(HERE / "method.json")
    assert method["preparer_ref"] == ref(Path(__file__).resolve())
    assert method["input_manifest_ref"] == ref(HERE / "input-manifest.json")
    assert len(manifest["inputs"]) == 6 and len({r["id"] for r in manifest["inputs"]}) == 6
    for row in manifest["inputs"]:
        assert sha(REPO / row["image_path"]) == row["image_sha256"]
        with Image.open(REPO / row["image_path"]) as image:
            assert list(image.size) == row["image_pixels_wh"]
        assert sha(REPO / row["source"]["path"]) == row["source"]["sha256"]
        assert not set(row["consumed_item_refs"]) & set(row["context_only_refs"])
        for fragment in row["source_fragments"]:
            for key in ("full_page_raster_ref", "image_ref"):
                assert sha(REPO / fragment[key]["path"]) == fragment[key]["sha256"]
    save(HERE / "verification.json", {"passed": True, "new_jobs": 6, "source_fragments": sum(len(r["source_fragments"]) for r in manifest["inputs"]),
        "prior_cpu_646_and_api_200_payloads_unchanged": True, "api_calls": 0, "new_model_inference": 0})
    print("Verified six producer-derived boundary inputs and unchanged646+200 prior payloads.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare"]:
        assert not (HERE / "input-manifest.json").exists()
        prepare()
    verify()
