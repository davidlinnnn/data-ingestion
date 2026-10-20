"""Replay native reading-order stages from saved results; observe without changing output."""
import importlib.util
import json
from pathlib import Path
import sys

from docling.datamodel.base_models import AssembledUnit, InputFormat, Page
from docling.datamodel.document import ConversionResult, InputDocument
from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel, ReadingOrderOptions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
BASE = ROOT / "pdf-core-ocr-regression-2026-10-19"
ORDER = ROOT / "pdf-core-official-multicol-2026-10-20"
sys.path.insert(0, str(ORDER))
spec = importlib.util.spec_from_file_location("frozen_order_diagnostics", ORDER / "analyze.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
legacy = audit.legacy

PROFILES = {
    "Heron-full": ROOT / "pdf-core-ocr-official-options-2026-10-19/full",
    "Egret-default": ORDER / "E-default",
    "Egret-full": ORDER / "E-full",
    "C10": ROOT / "pdf-core-ocr-region-policy-2026-10-20/C10",
    "Tesseract-fast": BASE / "T1",
    "EasyOCR": ROOT / "pdf-core-ocr-official-options-2026-10-19/easy",
}


def read(path):
    return json.loads(path.read_text())


def stage_score(elements, ref):
    included = [u for u in ref["items"] if u.get("scored", True)]
    ids = {u["id"] for u in included}
    reference = {**ref, "items": [{**u, "role": "section_header" if u["role"] == "heading" else u["role"]} for u in included],
                 "body_order": [u for u in ref["body_order"] if u in ids]}
    score = legacy.score_stage(elements, reference)
    rows = {u["id"]: u for u in score["paragraphs_and_furniture"]}
    found = [u for u in reference["body_order"] if rows[u]["median_anchor_position"] is not None]
    return {"observed_anchor_order": sorted(found, key=lambda u: rows[u]["median_anchor_position"]),
            "unlocated_units": [u for u in reference["body_order"] if u not in found],
            "inversion_candidates": score["body_order_inversions_candidates"],
            "mixed_elements": score["cross_column_mixed_elements"],
            "element_source_hits": score["elements"]}


def replay(path, ref):
    raw = read(path)
    # InputDocument's constructor opens a backend. Restore only verified saved metadata instead.
    metadata = {**raw["input"], "file": Path(raw["input"]["file"]), "format": InputFormat(raw["input"]["format"])}
    conv = ConversionResult.model_construct(input=InputDocument.model_construct(**metadata),
        pages=[Page.model_validate(p) for p in raw["pages"]],
        assembled=AssembledUnit.model_validate(raw["assembled"]), timings={})
    model = ReadingOrderModel(ReadingOrderOptions(use_page_separators=True))
    stages = {"assembled": [{"id": model._element_ref(e), "text": e.text or "", "label": e.label.value,
        "bbox": e.cluster.bbox.model_dump(mode="json")} for e in conv.assembled.elements]}
    calls = {}

    def observe(name):
        native = getattr(model.ro_model, name)

        def wrapped(*args, **kwargs):
            result = native(*args, **kwargs)
            if name == "predict_reading_order":
                stages["predictor_output"] = [{"id": e.ref.cref, "text": e.text or "", "label": e.label.value,
                    "cid": e.cid, "bbox": {k: getattr(e, k) for k in ("l", "t", "r", "b")}} for e in result]
                calls["predictor_output_cids"] = [e.cid for e in result]
            else:
                calls[name] = result
            return result

        setattr(model.ro_model, name, wrapped)

    for name in ("predict_reading_order", "predict_to_captions", "predict_to_footnotes", "predict_merges"):
        observe(name)
    final = model(conv)
    actual = final.model_dump(mode="json")
    equal = {k: actual[k] == raw["document"][k] for k in ("texts", "groups", "body", "furniture", "tables")}
    # Standard attaches picture images after reading order; compare all other picture fields.
    equal["pictures_except_later_image_attachment"] = [
        {k: v for k, v in p.items() if k != "image"} for p in actual["pictures"]
    ] == [{k: v for k, v in p.items() if k != "image"} for p in raw["document"]["pictures"]]
    assert all(equal.values()), (str(path), equal)
    assert final.export_to_markdown() == path.with_name("document.md").read_text(), path
    stages["final_body"] = legacy.document_elements(actual)
    scores = {name: stage_score(items, ref) for name, items in stages.items()}
    return {"input_result": str(path.resolve()), "input_sha256": audit.sha(path), "new_model_inferences": 0,
        "native_replay_equal": equal, "markdown_equal": True, "stages": stages, "scores": scores,
        "native_relation_mappings": calls,
        "limitations": "PyPdfium raster fixtures supply no vector separators. Assembled input array order is a predictor input, not an accepted reading sequence. Observer wraps only this local predictor instance; no SDK file or inference/output changed."}


def main():
    refs = {p["id"]: p for p in read(BASE / "corpus/reference.json")["pages"]}
    refs["known"] = read(BASE / "known-reference.json")
    profiles = {"Tesseract-best": HERE / "TB"} if sys.argv[1:] == ["--best"] else PROFILES
    out = HERE / ("best-order-traces" if "Tesseract-best" in profiles else "order-traces")
    out.mkdir(exist_ok=False)
    summary = []
    for name, folder in profiles.items():
        for page in ("known", "acl-p2"):
            value = replay(folder / page / "result.json", refs[page])
            (out / f"{name}-{page}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            row = {"profile": name, "page": page, "native_text_structure_replay_exact": True,
                   "stage_flags": {k: {"mixed": len(s["mixed_elements"]), "inversions": len(s["inversion_candidates"]),
                                        "unlocated": s["unlocated_units"]} for k, s in value["scores"].items()},
                   "merge_mapping": value["native_relation_mappings"].get("predict_merges", {})}
            summary.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    assert len(summary) == (2 if "Tesseract-best" in profiles else 12)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
