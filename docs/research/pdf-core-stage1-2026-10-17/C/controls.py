"""Offline saved-response integration. No converter, model or client is constructed."""
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Literal

from PIL import Image
from pydantic import BaseModel, ConfigDict, model_validator
from docling_core.types.doc import (
    BoundingBox, DescriptionMetaField, DocItemLabel, DoclingDocument,
    ImageRef, ImageRefMode, PictureMeta, ProvenanceItem, Size,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HISTORY = ROOT / "docs/research/pdf-core-g2-images-2026-10-14"
OCR = ROOT / "docs/research/pdf-core-g2-round2-2026-10-14/ocr/runs/picture-scale3"
METHOD = "stage1-C-saved-image-supplement-v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class Work(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    state: Literal["saved_response", "mock_response", "no_text", "failed", "unattempted"]
    texts: list[str] = []
    diagnostic: str | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.state in ("no_text", "failed", "unattempted") and self.texts:
            raise ValueError("non-delivered OCR cannot contain delivered texts")
        if self.state == "failed" and not self.diagnostic:
            raise ValueError("failure needs diagnostic")
        return self


class Point(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    series: str | None
    category: str | None
    x: int | float | str | None
    value: int | float | str
    value_status: Literal["printed", "estimated"]


class Chart(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    chart_type: str
    unit: str | None
    data: list[Point]


def required_work(_classification):
    # No validated confidence router exists; classification never exempts work.
    return ["ocr", "description", "chart_assessment"]


def check_links(doc, supplement, baseline):
    if supplement["method"] != METHOD:
        raise ValueError("method mismatch")
    if supplement["document_revision"] != digest(baseline):
        raise ValueError("revision mismatch")
    records = supplement["images"]
    refs = [r["owner_ref"] for r in records]
    if len(refs) != len(set(refs)) or set(refs) != {p.self_ref for p in doc.pictures}:
        raise ValueError("missing/duplicate/foreign owner")
    keys = [r["image_key"] for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate image key")
    for record in records:
        picture = next(p for p in doc.pictures if p.self_ref == record["owner_ref"])
        expected_key = digest([supplement["document_revision"], picture.self_ref, record["crop_sha256"]])
        if record["image_key"] != expected_key:
            raise ValueError("image key mismatch")
        if str(picture.image.uri) != record["image_path"]:
            raise ValueError("image URI mismatch")
        if picture.prov[0].model_dump(mode="json") != record["provenance"]:
            raise ValueError("source provenance mismatch")
        Work.model_validate(record["ocr"])
        if record["required_work"] != required_work(record["classification"]):
            raise ValueError("classification exempted required work")
        if record["chart"] is not None:
            Chart.model_validate(record["chart"])
        for item in record["provider_artifacts"]:
            if item["role"] == "output":
                assert item["payload_sha256"] == digest(record["saved_payload"])


def verify_bundle(directory):
    manifest = read(directory / "bundle.json")
    for name, expected in manifest["files"].items():
        if sha(directory / name) != expected:
            raise ValueError("artifact hash mismatch: " + name)
    baseline = read(directory / "baseline.json")
    doc = DoclingDocument.load_from_json(directory / "document.json")
    supplement = read(directory / "supplement.json")
    check_links(doc, supplement, baseline)
    for record in supplement["images"]:
        assert sha(directory / record["image_path"]) == record["crop_sha256"]
        for artifact in record["provider_artifacts"]:
            assert sha(directory / artifact["path"]) == artifact["sha256"]
            if artifact["role"] == "output":
                assert read(directory / artifact["path"]) == record["saved_payload"]
    markdown = (directory / "document.md").read_text()
    assert markdown == doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED,
                                              allowed_meta_names=set(), include_annotations=False)
    for record in supplement["images"]:
        assert record["image_path"] in markdown
    assert markdown.count("Synthetic original caption") == 1
    assert "Untouched adjacent paragraph" in markdown
    for record in supplement["images"]:
        description = (record["saved_payload"] or {}).get("description")
        if description:
            assert description not in markdown
            assert next(p for p in doc.pictures if p.self_ref == record["owner_ref"]).meta.description.text == description
    return {"images": len(supplement["images"]), "relocated_bundle_verified": True}


def verify_native(directory):
    manifest = read(directory / "bundle.json")
    for name, expected in manifest["files"].items():
        assert sha(directory / name) == expected
    doc = DoclingDocument.load_from_json(directory / "document.json")
    baseline = read(directory / "baseline.json")
    supplement = read(directory / "supplement.json")
    restored = doc.export_to_dict()
    total = 0
    for record, picture, old_picture in zip(supplement["images"], doc.pictures, baseline["pictures"]):
        assert picture.self_ref == record["owner_ref"]
        assert record["revision"] == digest(baseline)
        assert record["image_key"] == digest([record["revision"], picture.self_ref, record["crop_sha256"]])
        assert str(picture.image.uri) == record["image_path"]
        assert sha(directory / record["image_path"]) == record["crop_sha256"]
        assert record["native_children"] == [r.resolve(doc).model_dump(mode="json", exclude_none=True) for r in picture.children]
        total += len(record["native_children"])
        restored["pictures"][int(picture.self_ref.rsplit("/",1)[1])]["image"] = old_picture["image"]
    assert len(supplement["images"]) == len(doc.pictures)
    assert restored == baseline, "native graph/text/caption/provenance changed"
    assert doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED, allowed_meta_names=set(), include_annotations=False) == (directory / "document.md").read_text()
    return {"native_pictures": len(doc.pictures), "native_picture_children_preserved": total,
            "only_document_change": "picture image resource URI/encoding", "relocated_bundle_verified": True}


def native_control(evidence):
    source_dir = ROOT / "docs/research/pdf-core-native-round-2026-10-17"
    source = source_dir / "S0/nccu/document.json"
    for path in [source, source_dir / "standard-runtime-v2.json", source_dir / "S0/effective-options.json"]:
        evidence[str(path.relative_to(ROOT))] = sha(path)
    doc = DoclingDocument.load_from_json(source)
    baseline = doc.export_to_dict()
    bundle = HERE / "native-bundle-original"
    (bundle / "images").mkdir(parents=True, exist_ok=True)
    write(bundle / "baseline.json", baseline)
    records = []
    for picture in doc.pictures:
        image = picture.get_image(doc)
        assert image is not None
        temp = bundle / "images/native.png"
        image.save(temp)
        image_hash = sha(temp)
        key = digest([digest(baseline), picture.self_ref, image_hash])
        uri = f"images/{key}.png"
        temp.rename(bundle / uri)
        records.append({"owner_ref": picture.self_ref, "revision": digest(baseline), "image_key": key,
                        "image_path": uri, "crop_sha256": image_hash,
                        "native_children": [r.resolve(doc).model_dump(mode="json", exclude_none=True) for r in picture.children],
                        "classification": "unknown", "required_work": required_work("unknown"),
                        "description_state": "unattempted", "chart_assessment_state": "unattempted"})
        picture.image = ImageRef(mimetype="image/png", dpi=144,
                                size=Size(width=image.width, height=image.height), uri=Path(uri))
    write(bundle / "document.json", doc.export_to_dict())
    write(bundle / "supplement.json", {"method": METHOD, "upstream": "cached pinned S0",
          "source_document_sha256": sha(source), "images": records})
    (bundle / "document.md").write_text(doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED,
                                       allowed_meta_names=set(), include_annotations=False))
    write(bundle / "bundle.json", {"files": {str(p.relative_to(bundle)):sha(p)
          for p in bundle.rglob("*") if p.is_file() and p.name != "bundle.json"}})
    verify_native(bundle)
    moved = HERE / "native-bundle-relocated"
    shutil.copytree(bundle, moved, dirs_exist_ok=True)
    child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--verify-native", str(moved)],
                           cwd=moved, capture_output=True, text=True, check=True)
    return json.loads(child.stdout)


def main():
    start = time.monotonic()
    versions = {n: importlib.metadata.version(n) for n in
                ["docling-slim", "docling-core", "docling-parse", "pypdfium2"]}
    assert versions == {"docling-slim": "2.132.0", "docling-core": "2.99.0",
                        "docling-parse": "7.22.3", "pypdfium2": "5.14.0"}
    bundle = HERE / "bundle-original"
    bundle.mkdir(exist_ok=True)
    (bundle / "images").mkdir(exist_ok=True)
    (bundle / "provider").mkdir(exist_ok=True)
    manifest_path = HISTORY / "inputs/input-manifest.json"
    source_manifest = read(manifest_path)
    evidence = {str(manifest_path.relative_to(ROOT)): sha(manifest_path)}
    doc = DoclingDocument(name="saved-response controlled public owner integration")
    doc.add_text(label=DocItemLabel.TEXT, text="Untouched adjacent paragraph")
    caption = doc.add_text(label=DocItemLabel.CAPTION, text="Synthetic original caption")
    records = []
    for i, entry in enumerate(source_manifest["inputs"]):
        case = entry["input_id"].lower()
        source = ROOT / entry["source_pdf_path"]
        assert sha(source) == entry["source_pdf_sha256"]
        crop = ROOT / entry["path"]
        assert sha(crop) == entry["sha256"]
        evidence[str(source.relative_to(ROOT))] = sha(source)
        evidence[str(crop.relative_to(ROOT))] = sha(crop)
        payload_path = HISTORY / "api" / case / "output.json"
        response_path = HISTORY / "api" / case / "response.json"
        payload = read(payload_path)
        bbox = entry["mapping"].get("effective_crop_bbox_pdf_points_top_left", entry["frozen_bbox_points_top_left"])
        prov = ProvenanceItem(page_no=entry["physical_page_1based"], charspan=(0, 0),
                             bbox=BoundingBox(l=bbox[0], t=bbox[1], r=bbox[2], b=bbox[3], coord_origin="TOPLEFT"))
        picture = doc.add_picture(prov=prov, caption=caption if i == 0 else None)
        if "description" in payload:
            picture.meta = PictureMeta(description=DescriptionMetaField(text=payload["description"],
                                      created_by="saved historical component API"))
        artifacts = []
        for role, path in [("output", payload_path), ("raw_response", response_path)]:
            target = f"provider/{case}-{role}.json"
            shutil.copyfile(path, bundle / target)
            evidence[str(path.relative_to(ROOT))] = sha(path)
            artifacts.append({"role": role, "path": target, "sha256": sha(path),
                              "payload_sha256": digest(payload) if role == "output" else None})
        record = {"case": case, "owner_ref": picture.self_ref, "source_sha256": sha(source),
                  "provenance": prov.model_dump(mode="json"), "crop_sha256": sha(crop),
                  "classification": "unknown", "required_work": required_work("unknown"),
                  "ocr": Work(state="unattempted").model_dump(), "saved_payload": payload,
                  "chart": payload if "chart_type" in payload else None,
                  "description_state": "saved_response" if "description" in payload else "unattempted",
                  "chart_assessment_state": "saved_response" if "chart_type" in payload else "unattempted",
                  "provider_artifacts": artifacts, "_crop": crop}
        records.append(record)
    # Existing OCR belongs to its own full-picture crop; never bind it to a different saved API crop.
    ocr_path = OCR / "ocr.json"
    ocr = read(ocr_path)
    crop = OCR / "figure.png"
    assert sha(crop) == ocr["crop_sha256"]
    evidence[str(ocr_path.relative_to(ROOT))] = sha(ocr_path)
    evidence[str(crop.relative_to(ROOT))] = sha(crop)
    picture = doc.add_picture(prov=ProvenanceItem.model_validate(ocr["provenance"]))
    shutil.copyfile(ocr_path, bundle / "provider/nccu-ocr.json")
    records.append({"case": "saved-nccu-ocr", "owner_ref": picture.self_ref,
                    "source_sha256": ocr["source_sha256"], "provenance": ocr["provenance"],
                    "crop_sha256": sha(crop), "classification": "unknown",
                    "required_work": required_work("unknown"),
                    "ocr": Work(state="saved_response", texts=ocr["texts"]).model_dump(),
                    "saved_payload": ocr, "chart": None, "description_state": "unattempted",
                    "chart_assessment_state": "unattempted", "_crop": crop,
                    "provider_artifacts": [{"role": "output", "path": "provider/nccu-ocr.json",
                                            "sha256": sha(ocr_path), "payload_sha256": digest(ocr)}]})
    for state in ["no_text", "failed"]:
        crop = HERE / f"mock-{state}.png"
        Image.new("RGB", (12, 12), "white").save(crop)
        prov = ProvenanceItem(page_no=1, bbox=BoundingBox(l=0,t=0,r=12,b=12,coord_origin="TOPLEFT"), charspan=(0,0))
        picture = doc.add_picture(prov=prov)
        records.append({"case": "mock-" + state, "owner_ref": picture.self_ref,
                        "source_sha256": sha(crop), "provenance": prov.model_dump(mode="json"),
                        "crop_sha256": sha(crop), "classification": "unknown",
                        "required_work": required_work("unknown"),
                        "ocr": Work(state=state, diagnostic="synthetic engine failure" if state == "failed" else None).model_dump(),
                        "saved_payload": None, "chart": None, "description_state": "unattempted",
                        "chart_assessment_state": "unattempted", "provider_artifacts": [], "_crop": crop})
    baseline = doc.export_to_dict()
    revision = digest(baseline)
    write(bundle / "baseline.json", baseline)
    for picture, record in zip(doc.pictures, records):
        key = digest([revision, picture.self_ref, record["crop_sha256"]])
        record["image_key"] = key
        record["image_path"] = f"images/{key}.png"
        crop = record.pop("_crop")
        shutil.copyfile(crop, bundle / record["image_path"])
        with Image.open(crop) as image:
            width, height = image.size
        picture.image = ImageRef(mimetype="image/png", dpi=216, size=Size(width=width,height=height),
                                 uri=Path(record["image_path"]))
    supplement = {"method": METHOD, "document_revision": revision, "evidence_kind": "saved-response-plus-mock-controls",
                  "owner_kind": "synthetic legal public owners; not new Standard output", "images": records}
    write(bundle / "document.json", doc.export_to_dict())
    write(bundle / "supplement.json", supplement)
    (bundle / "document.md").write_text(doc.export_to_markdown(image_mode=ImageRefMode.REFERENCED,
                                      allowed_meta_names=set(), include_annotations=False))
    write(bundle / "bundle.json", {"files": {str(p.relative_to(bundle)):sha(p)
          for p in bundle.rglob("*") if p.is_file() and p.name != "bundle.json"}})
    verify_bundle(bundle)
    negatives = []
    for name, change in [
        ("revision", lambda s: s.update(document_revision="stale")),
        ("method", lambda s: s.update(method="different")),
        ("foreign_owner", lambda s: s["images"][0].update(owner_ref="#/pictures/999")),
        ("duplicate_owner", lambda s: s["images"][1].update(owner_ref=s["images"][0]["owner_ref"])),
        ("missing_owner", lambda s: s["images"].pop()),
        ("unknown_class_exemption", lambda s: s["images"][0].update(required_work=[])),
        ("failure_with_delivered_texts", lambda s: s["images"][-1]["ocr"].update(texts=["silently delivered"])),
        ("provenance", lambda s: s["images"][0]["provenance"].update(page_no=99)),
        ("image_key", lambda s: s["images"][0].update(image_key="wrong")),
    ]:
        altered = copy.deepcopy(supplement)
        change(altered)
        try:
            check_links(doc, altered, baseline)
        except (ValueError, AssertionError):
            negatives.append(name)
        else:
            raise AssertionError("negative accepted: " + name)
    first_image = bundle / records[0]["image_path"]
    missing = first_image.with_suffix(".missing")
    first_image.rename(missing)
    try:
        try:
            verify_bundle(bundle)
        except FileNotFoundError:
            negatives.append("missing_image")
        else:
            raise AssertionError("missing image accepted")
    finally:
        missing.rename(first_image)
    # A second process reads a separately located copy; no historical directory is needed for resolution.
    moved = HERE / "bundle-relocated"
    shutil.copytree(bundle, moved, dirs_exist_ok=True)
    child = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--verify", str(moved)],
                           cwd=moved, capture_output=True, text=True, check=True)
    native_result = native_control(evidence)
    write(HERE / "evidence-hashes.json", evidence)
    assert all(sha(ROOT / name) == expected for name, expected in evidence.items())
    assert not any(m in sys.modules for m in ["torch", "onnxruntime", "rapidocr", "openai"])
    result = {"status": "partial", "integration_gate": "pass", "full_C_readiness": "partial",
              "runtime": versions, "elapsed_control_seconds": time.monotonic()-start,
              "saved_api_images": 6, "saved_ocr_images": 1, "synthetic_state_controls": 2,
              "chart_points_preserved": sum(len(r["chart"]["data"]) for r in records if r["chart"]),
              "negative_controls_rejected": negatives, "second_process": json.loads(child.stdout),
              "pinned_cached_S0_second_process": native_result,
              "no_inference_modules_loaded": True, "historical_evidence_unchanged": True,
              "limitations": ["Historical external API/OCR use synthetic legal owners; pinned S0 native graph replay separately",
                              "No complete source-only image census", "No new content accuracy score",
                              "No classifier/heading/orientation same-version end-to-end run",
                              "No Pod/checkpoint recovery proof", "Census/jobs/input budgets not frozen"]}
    write(HERE / "results.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        print(json.dumps(verify_bundle(Path(sys.argv[2]))))
    elif len(sys.argv) > 1 and sys.argv[1] == "--verify-native":
        print(json.dumps(verify_native(Path(sys.argv[2]))))
    else:
        main()
