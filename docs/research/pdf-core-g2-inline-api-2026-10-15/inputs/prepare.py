"""Reference exact frozen CPU inputs for a later model comparison; no inference or API access."""

import copy
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PRIOR = REPO / "docs/research/pdf-core-g2-inline-2026-10-15"
OLD_INPUT = PRIOR / "inputs/input-manifest.json"
OLD_INPUT_SHA = "4fd11ccacd2819d0eb44461974315f217dee12e3fc58308b28875b0964e00ccf"
OLD_ARTIFACTS = PRIOR / "artifacts.json"
OLD_ARTIFACTS_SHA = "ac061b0f8a7efc5ae585793a6a8a55dc9d634f0a4bec10dcf87178797ace45d6"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
REGISTRY_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
PAPER_EVIDENCE = REPO / "docs/fixtures/agent-self-evolution-pilot-2026-10-11/manifest.json"
PAGE_IDS = ["wikiskill-p21", "dgm-p51", "seal-p3", "seal-p4", "controls-p1"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def ref(path, pointer=None):
    result = {"path": str(path.relative_to(REPO)), "sha256": sha(path)}
    if pointer is not None:
        result["json_pointer"] = pointer
    return result


def png_size(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("input is not a PNG")
    return list(struct.unpack(">II", data[16:24]))


def preserve_prior():
    assert sha(OLD_INPUT) == OLD_INPUT_SHA
    assert sha(OLD_ARTIFACTS) == OLD_ARTIFACTS_SHA
    assert sha(REGISTRY) == REGISTRY_SHA
    files = read(OLD_ARTIFACTS)["files"]
    assert len(files) == 646
    for file in files:
        assert sha(REPO / file["path"]) == file["sha256"], file["path"]
    return read(OLD_INPUT)


def image_ref(path):
    return {**ref(path), "pixels_wh": png_size(path), "transformation_for_this_step": "none; original saved PNG bytes referenced"}


def source_info(source, paper_rows):
    if source["id"] == "SRC05":
        return {"id": source["id"], "pdf_path": source["path"], "pdf_sha256": source["sha256"],
            "source_class": "original synthetic controls page 1 only", "eligible_page_scope": [1],
            "visibility_evidence": ref(REGISTRY, "/sources/4")}
    index = next(i for i, row in enumerate(paper_rows) if row["file"] == Path(source["path"]).name)
    paper = paper_rows[index]
    assert paper["pdf_url"].startswith("https://arxiv.org/pdf/")
    return {"id": source["id"], "pdf_path": source["path"], "pdf_sha256": source["sha256"],
        "source_class": "public fixed-version research paper", "public_pdf_url": paper["pdf_url"],
        "visibility_evidence": ref(PAPER_EVIDENCE, f"/papers/{index}")}


def prepare():
    prior = preserve_prior()
    papers = read(PAPER_EVIDENCE)["papers"]
    sources = {row["name"]: row for row in prior["sources"]}
    inputs = []
    for index, candidate in enumerate(prior["candidates"]):
        folder = PRIOR / "vlm/paragraph/runs" / candidate["id"]
        cpu_image = image_ref(folder / "engine-input.png")
        original_image = image_ref(REPO / candidate["image_path"])
        assert original_image["sha256"] == candidate["image_sha256"]
        assert original_image["pixels_wh"] == candidate["image_pixels_wh"] == cpu_image["pixels_wh"]
        source = sources[candidate["source"]]
        inputs.append({"id": "paragraph--"+candidate["id"], "phase": "paragraph", "kind": "whole_provider_item_paragraph",
            "image_path": original_image["path"], "image_sha256": original_image["sha256"], "image_pixels_wh": original_image["pixels_wh"],
            "prior_input_id": candidate["id"], "image": original_image,
            "source": source_info(source["source"], papers),
            "physical_pages_1based": [f["physical_page_1based"] for f in candidate["fragments"]],
            "provider_item_ref": candidate["item_ref"], "replacement_charspan": candidate["replacement_charspan"],
            "provider_text_sha256": candidate["provider_text_sha256"],
            "prior_candidate_ref": ref(OLD_INPUT, f"/candidates/{index}"),
            "source_fragments_and_transforms_ref": ref(OLD_INPUT, f"/candidates/{index}/fragments"),
            "source_fragment_count": len(candidate["fragments"]),
            "baseline_document_ref": {"path": candidate["baseline_document_path"], "sha256": candidate["baseline_document_sha256"]},
            "cpu_baseline": {"engine_input_image": cpu_image, "source_input_ref": ref(folder / "source-input.json"),
                "engine_input_metadata_ref": ref(folder / "engine-input.json"), "method_ref": ref(folder / "method.json"),
                "new_image_byte_identical_to_cpu_engine_input": original_image["sha256"] == cpu_image["sha256"]}})
    for page_id in PAGE_IDS:
        folder = PRIOR / "vlm/page/runs" / page_id
        cpu_source = read(folder / "source-input.json")
        cpu_input = read(folder / "engine-input.json")
        image = image_ref(folder / "engine-input.png")
        assert image["sha256"] == cpu_input["image_sha256"] and image["pixels_wh"] == cpu_input["pixels_wh"]
        source = next(s for s in prior["sources"] if s["source"]["id"] == cpu_source["source"]["id"])
        document = read(REPO / source["document_path"])
        page_no = cpu_source["physical_page_1based"]
        page_size = document["pages"][str(page_no)]["size"]
        scale = read(folder / "method.json")["options"]["vlm_options"]["scale"]
        assert scale == 2.0
        inputs.append({"id": "page--"+page_id, "phase": "page", "kind": "full_physical_page_cpu_engine_input",
            "image_path": image["path"], "image_sha256": image["sha256"], "image_pixels_wh": image["pixels_wh"],
            "prior_input_id": page_id, "image": image, "source": source_info(source["source"], papers),
            "physical_pages_1based": [page_no], "source_page_size_points": page_size,
            "source_crop_top_left_points": [0, 0, page_size["width"], page_size["height"]],
            "cpu_render_scale_pixels_per_point": scale,
            "input_pixels_to_source_top_left_points_3x3": [[1/scale, 0, 0], [0, 1/scale, 0], [0, 0, 1]],
            "mapping_precision": "Whole-page provider render mapping; pixel rounding and raster resampling remain, not glyph-measured positions",
            "baseline_document_ref": {"path": source["document_path"], "sha256": source["document_sha256"]},
            "cpu_baseline": {"engine_input_image": image, "source_input_ref": ref(folder / "source-input.json"),
                "engine_input_metadata_ref": ref(folder / "engine-input.json"), "method_ref": ref(folder / "method.json"),
                "new_image_byte_identical_to_cpu_engine_input": True}})
    manifest = {"format": "g2-inline-api-frozen-inputs-v1", "prepared_without_inference_or_api": True,
        "prior_input_manifest_ref": ref(OLD_INPUT), "prior_payload_manifest_ref": {**ref(OLD_ARTIFACTS), "payload_count": 646},
        "registry_ref": ref(REGISTRY),
        "selection_inventory_ref": ref(OLD_INPUT, "/ordinary_paragraph_inventory"),
        "selection_counts": prior["counts"],
        "model_input_policy": "Only referenced PNG bytes plus the separately approved output contract; no native transcription, expected content, prior model outputs or review material supplied as prompt content",
        "source_scope": "Three public fixed-version papers and original synthetic controls page 1; no other pages/content eligible in this manifest",
        "output_contract": "Not selected by preparation; root research/authorization determines later API method",
        "counts": {"paragraph_inputs": 17, "full_page_inputs": 5, "total_inputs": 22, "paragraph_source_fragments": 19,
            "ordinary_inventory_decisions_linked": 28}, "inputs": inputs}
    target = HERE / "input-manifest.json"
    assert not target.exists()
    save(target, manifest)
    save(HERE / "method.json", {"scope": "Frozen input references only; no inference, API, key access, image edits or baseline copies",
        "preparer_ref": ref(Path(__file__).resolve()), "input_manifest_ref": ref(target),
        "previous_payload_manifest_ref": ref(OLD_ARTIFACTS), "public_source_evidence_ref": ref(PAPER_EVIDENCE),
        "new_image_files_created": 0, "new_baseline_copies_created": 0, "api_requests": 0, "inference_calls": 0})


def validate_records(manifest):
    records = manifest["inputs"]
    ids = [row["id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate input id")
    forbidden = {"text", "provider_text", "expected", "answer", "answers", "reference_transcript", "oracle", "prompt"}

    def scan(value):
        if isinstance(value, dict):
            if set(value) & forbidden:
                raise ValueError("answer/transcription/prompt field in producer input record")
            for child in value.values():
                scan(child)
        elif isinstance(value, list):
            for child in value:
                scan(child)

    scan(records)
    for row in records:
        image = row["image"]
        if row["phase"] not in {"paragraph", "page"} or not row["id"].startswith(row["phase"]+"-"):
            raise ValueError("invalid input phase/id prefix")
        if (row["image_path"], row["image_sha256"], row["image_pixels_wh"]) != (image["path"], image["sha256"], image["pixels_wh"]):
            raise ValueError("inconsistent runner image fields")
        if sha(REPO / image["path"]) != image["sha256"]:
            raise ValueError("stale image hash")
        if png_size(REPO / image["path"]) != image["pixels_wh"]:
            raise ValueError("stale image dimensions")
        if sha(REPO / row["source"]["pdf_path"]) != row["source"]["pdf_sha256"]:
            raise ValueError("stale source PDF hash")
        if row["source"]["id"] == "SRC05" and set(row["physical_pages_1based"]) != {1}:
            raise ValueError("controls input outside original synthetic page scope")


def verify():
    prior = preserve_prior()
    manifest, method = read(HERE / "input-manifest.json"), read(HERE / "method.json")
    assert method["preparer_ref"] == ref(Path(__file__).resolve())
    assert method["input_manifest_ref"] == ref(HERE / "input-manifest.json")
    validate_records(manifest)
    paragraphs = [row for row in manifest["inputs"] if row["kind"] == "whole_provider_item_paragraph"]
    pages = [row for row in manifest["inputs"] if row["kind"] == "full_physical_page_cpu_engine_input"]
    assert len(paragraphs) == 17 and len(pages) == 5 and len(manifest["inputs"]) == 22
    assert [row["prior_input_id"] for row in paragraphs] == [row["id"] for row in prior["candidates"]]
    assert [row["prior_input_id"] for row in pages] == PAGE_IDS
    assert sum(row["source_fragment_count"] for row in paragraphs) == 19
    assert len(prior["ordinary_paragraph_inventory"]) == 28
    for row in manifest["inputs"]:
        refs = [row["baseline_document_ref"], row["source"]["visibility_evidence"],
            row["cpu_baseline"]["engine_input_image"], row["cpu_baseline"]["source_input_ref"],
            row["cpu_baseline"]["engine_input_metadata_ref"], row["cpu_baseline"]["method_ref"]]
        if row["kind"] == "whole_provider_item_paragraph":
            refs += [row["prior_candidate_ref"], row["source_fragments_and_transforms_ref"]]
        for entry in refs:
            assert sha(REPO / entry["path"]) == entry["sha256"]
    negative = []
    for name in ("stale_image", "duplicate_id", "answer_field"):
        bad = copy.deepcopy(manifest)
        if name == "stale_image":
            bad["inputs"][0]["image"]["sha256"] = "0"*64
        elif name == "duplicate_id":
            bad["inputs"][1]["id"] = bad["inputs"][0]["id"]
        else:
            bad["inputs"][0]["expected"] = "untrusted answer"
        try:
            validate_records(bad)
        except ValueError:
            negative.append(name)
        else:
            raise AssertionError(f"negative control accepted: {name}")
    save(HERE / "verification.json", {"passed": True, "counts": manifest["counts"],
        "prior_646_payloads_unchanged": True, "prior_manifest_sha256": OLD_INPUT_SHA,
        "exact_old_png_bytes_referenced": True, "producer_records_contain_no_transcriptions_or_answers": True,
        "negative_controls_rejected": negative, "api_requests": 0, "inference_calls": 0})
    print("Verified 17 paragraph + 5 full-page inputs, 19 fragment references, all 28 gate decisions and 646 unchanged prior payloads.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare"]:
        prepare()
    verify()
