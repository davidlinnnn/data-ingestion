"""Source-only diagnosis; never supplies crops or answers to a producer."""
from hashlib import sha256
import json
from pathlib import Path
import sys

from docling.backend.docling_parse_backend import ThreadedDoclingParseDocumentBackend
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.backend_options import ThreadedDoclingParseBackendOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import InputDocument
from docling.datamodel.settings import DocumentLimits
from docling_core.types.doc import BoundingBox

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FROZEN = REPO / "docs/research/pdf-core-eval-interfaces-2026-10-18/C"


def evidence():
    inventory = json.loads((FROZEN / "producer-inventory.json").read_text())
    rows = []
    for source_id, owner in (("SRC11", "#/pictures/0"), ("SRC13", "#/pictures/1")):
        native = next(p for p in inventory["pictures"] if p["source_id"] == source_id and p["owner_ref"] == owner)
        source = REPO / native["source"]["path"]
        baseline = REPO / native["baseline"]
        assert sha256(source.read_bytes()).hexdigest() == native["source"]["sha256"]
        assert sha256(baseline.read_bytes()).hexdigest() == native["baseline_sha256"]
        document = json.loads(baseline.read_text())
        picture = document["pictures"][int(owner.rsplit("/", 1)[1])]
        captions = [document["texts"][int(ref.rsplit("/", 1)[1])] for ref in native["caption_refs"]]
        rows.append((native, document, picture, captions))
    return rows


def source_checks():
    seal, reason = evidence()
    title = next(t for t in seal[1]["texts"] if "RL Outer Loop Iteration" in t.get("text", ""))
    picture = BoundingBox.model_validate(seal[2]["prov"][0]["bbox"])
    box = BoundingBox.model_validate(title["prov"][0]["bbox"])
    title_contained = (picture.l <= box.l and picture.r >= box.r and picture.b <= box.b and picture.t >= box.t)
    caption = " ".join(reason[3][0]["text"].split())
    clean_caption = caption.startswith("Figure 5") and "Better memory mechanism enables" not in caption
    return {"seal_title_contained_in_native_crop": title_contained,
            "reasoningbank_caption_without_neighbor_pollution": clean_caption}


def trace():
    report = {"source_checks": source_checks(), "new_model_calls": 0, "API_calls": 0, "sources": []}
    for native, document, picture, captions in evidence():
        page_no = native["provenance"][0]["page_no"]
        row = {"source_id": native["source_id"], "page": page_no, "source": native["source"],
               "baseline": native["baseline"], "baseline_sha256": native["baseline_sha256"],
               "picture_provenance": picture["prov"], "captions": captions, "backends": {}}
        for backend in (PyPdfiumDocumentBackend, ThreadedDoclingParseDocumentBackend):
            options = ThreadedDoclingParseBackendOptions(parser_threads=1, render_pages=False)
            input_doc = InputDocument(REPO / native["source"]["path"], InputFormat.PDF, backend,
                                      backend_options=options, limits=DocumentLimits(page_range=(page_no, page_no)))
            assert input_doc.valid
            instance = input_doc._backend
            try:
                if backend is PyPdfiumDocumentBackend:
                    page = instance.load_page(page_no - 1)
                else:
                    pages = list(instance.iter_pages())
                    assert len(pages) == 1, "fixed single-page source probe"
                    page = pages[0]
                segmented = page.get_segmented_page()
                assert segmented is not None
                def text_in_source_box(box):
                    # The threaded backend expects the parsed cells' top-left frame.
                    rect = BoundingBox.model_validate(box).to_top_left_origin(page.get_size().height)
                    return page.get_text_in_rect(rect)
                row["backends"][backend.__name__] = {
                    "caption_bbox_text": [text_in_source_box(c["prov"][0]["bbox"]) for c in captions],
                    "textline_cells": [{"text": c.text, "bbox": c.rect.to_bounding_box().model_dump(mode="json")}
                                       for c in segmented.textline_cells],
                    "picture_bbox_text": text_in_source_box(picture["prov"][0]["bbox"])}
                page.unload()
            finally:
                instance.unload()
        report["sources"].append(row)
    report["script_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    with (HERE / "source-trace.json").open("x") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"source_checks": report["source_checks"], "source_probes": len(report["sources"]),
                      "model_calls": 0, "API_calls": 0}))


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-baseline"]:
        checks = source_checks()
        print(json.dumps(checks), flush=True)
        assert all(checks.values()), "known source defects still reproduce"
    elif sys.argv[1:] == ["--trace"]:
        trace()
    else:
        raise SystemExit("use --check-baseline or --trace")
