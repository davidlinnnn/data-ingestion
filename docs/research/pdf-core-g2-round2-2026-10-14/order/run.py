"""Replay only ReadingOrderModel from immutable, already inferred page results."""

import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ.update(OMP_NUM_THREADS="4", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  DOCLING_DEVICE="cpu", TOKENIZERS_PARALLELISM="false")

import torch
from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import ConversionResult, InputDocument
from docling.datamodel.settings import DocumentLimits
from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel, ReadingOrderOptions
from docling_ibm_models.reading_order.reading_order_rb import ReadingOrderPredictor

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASE = REPO / "docs/research/pdf-core-g2-local-cpu-2026-10-14/runs/english-scan-p1-ocr"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
COMMIT = "f46f51115cd0444a59c22b4de13666bd1ef93602"
V3_SHA = "ab5f1bb51b86c1cd8966c645e6e96df839c86460ce265be079451530402935ed"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def restore_confidence(value):
    if isinstance(value, dict):
        return {k: restore_confidence(v) for k, v in value.items()}
    return float("nan") if value is None else value


def reconstruct(raw):
    data = json.loads(raw)
    item = data["input"].copy()
    item.update(file=Path(item["file"]), limits=DocumentLimits.model_validate(item["limits"]),
                format=InputFormat(item["format"]))
    # InputDocument's custom constructor opens a backend; this replay needs metadata only.
    data["input"] = InputDocument.model_construct(**item)
    data["confidence"] = restore_confidence(data["confidence"])
    result = ConversionResult.model_validate(data)
    assert json.loads(result.model_dump_json()) == json.loads(raw), "roundtrip changed provider data"
    assert len(result.pages) == 1 and len(result.assembled.elements) == 15
    assert all(type(e).__name__ == "TextElement" for e in result.assembled.elements)
    assert math.isnan(result.confidence.parse_score) and math.isnan(result.confidence.table_score)
    return result


def inventory(doc):
    return [(t.text, t.orig, t.label.value, [p.model_dump(mode="json") for p in t.prov])
            for t in doc.texts]


def normalized(text):
    return " ".join(text.replace("re- sources", "resources").replace("–", "-").split())


def run(name, predictor, raw, paragraphs):
    result = reconstruct(raw)
    original = result.document
    model = ReadingOrderModel(options=ReadingOrderOptions())
    model.ro_model = predictor
    trace = {}
    for method_name in ("predict_reading_order", "predict_to_captions", "predict_to_footnotes", "predict_merges"):
        original_method = getattr(predictor, method_name)

        def recorded(*args, _method=original_method, _name=method_name, **kwargs):
            output = _method(*args, **kwargs)
            trace[_name] = ([e.model_dump(mode="json") for e in output]
                            if _name == "predict_reading_order" else output)
            return output

        setattr(predictor, method_name, recorded)
    started = time.perf_counter()
    doc = model(result)
    elapsed = time.perf_counter() - started
    # Standard pipeline attaches page images after reading order; retain the original bytes.
    for page_no, page in original.pages.items():
        doc.pages[page_no].image = page.image
    out = HERE / name
    out.mkdir(exist_ok=False)
    result.document = doc
    (out / "conversion-result-reassembled.json").write_text(result.model_dump_json(indent=2))
    doc.save_as_json(out / "document.json")
    doc.save_as_markdown(out / "document.md")
    save(out / "predictor-trace.json", trace)
    selected = []
    for expected in paragraphs:
        matches = [(i, t) for i, t in enumerate(doc.texts) if normalized(t.text) == expected]
        assert len(matches) == 1, "missing or duplicated selected paragraph"
        selected.append(matches[0])
    a, b = [entry[0] for entry in selected]
    assert a < b
    between = [{"index": i, "ref": doc.texts[i].self_ref, "text": doc.texts[i].text}
               for i in range(a + 1, b)]
    checks = {
        "execution_status": "completed", "assembly_only_seconds": elapsed,
        "timing_scope": "one assembly replay; concurrent CPU work possible; not a performance comparison",
        "complete_document_equal_original_after_retaining_original_page_image":
            doc.model_dump(mode="json") == original.model_dump(mode="json"),
        "text_orig_label_provenance_sequence_equal_original": inventory(doc) == inventory(original),
        "selected_paragraphs_normalized_exact": [True, True],
        "selected_paragraph_refs": [t.self_ref for _, t in selected],
        "intervening_items": between,
        "selected_paragraphs_adjacent": not between,
        "text_count": len(doc.texts), "picture_count": len(doc.pictures), "table_count": len(doc.tables),
        "output_hashes": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    save(out / "checks.json", checks)
    return checks, trace


def main():
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    raw_path = BASE / "conversion-result.json"
    raw = raw_path.read_text()
    before_hash = sha(raw_path)
    source = Path(json.loads(raw)["input"]["file"])
    assert sha(source) == json.loads(raw)["input"]["document_hash"]
    v3 = subprocess.run(["rtk", "git", "show", f"{COMMIT}:src/pdf_processing/continuation.py"],
                        check=True, capture_output=True).stdout
    assert hashlib.sha256(v3).hexdigest() == V3_SHA
    adapter_path = HERE / "historical-continuation-v3.py"
    adapter_path.write_bytes(v3)
    spec = importlib.util.spec_from_file_location("g2_fixed_continuation_v3", adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    assert adapter.METHOD == "column-edge-continuation-v3"
    method_path = REPO / "docs/research/paper-pdf-functional-2026-10-11/dgm-group5/16-2505.22954v1/native/method.json"
    assert json.loads(method_path.read_text())["continuation"] == {"sha256": V3_SHA, "version": adapter.METHOD}
    registry = json.loads(REGISTRY.read_text())
    case = next(c for c in registry["cases"] if c["id"] == "G1-O03")
    items = {i["id"]: i["text"] for i in case["details"]["expected"]["items"]}
    paragraphs = [normalized(" ".join(items[key] for key in group))
                  for group in case["details"]["expected"]["paragraph_groups"]]
    roundtrip = reconstruct(raw)
    (HERE / "conversion-result-roundtrip.json").write_text(roundtrip.model_dump_json(indent=2))
    stock, stock_trace = run("stock", ReadingOrderPredictor(), raw, paragraphs)
    candidate, candidate_trace = run("continuation-v3", adapter.ContinuationPredictor(), raw, paragraphs)
    assert stock_trace["predict_reading_order"] == candidate_trace["predict_reading_order"]
    assert stock["selected_paragraphs_adjacent"] is False
    assert candidate["selected_paragraphs_adjacent"] is False
    assert stock["intervening_items"] == candidate["intervening_items"]
    assert before_hash == sha(raw_path)
    module_sources = [Path(inspect.getsourcefile(ReadingOrderModel)),
                      Path(inspect.getsourcefile(ReadingOrderPredictor))]
    summary = {
        "scope": "G1-O03 physical scan page 1; stock vs fixed historical v3; reading-order assembly only",
        "device": "cpu", "torch_threads": 4, "torch_interop_threads": 1, "workers": 1,
        "page_inference_models_executed": [], "remote_calls": 0,
        "input_files": {str(p.relative_to(REPO)): sha(p) for p in
                        [raw_path, BASE / "method.json", BASE / "document.json", BASE / "document.md", REGISTRY, source]},
        "versions": json.loads(raw)["version"],
        "upstream_source_sha256": {str(p): sha(p) for p in module_sources},
        "original_model_config_hashes": json.loads((BASE / "method.json").read_text())["model_artifacts"],
        "continuation_candidate": {"commit": COMMIT, "sha256": V3_SHA, "version": adapter.METHOD,
                                   "historical_method": str(method_path.relative_to(REPO)),
                                   "historical_method_sha256": sha(method_path)},
        "current_worktree_continuation_not_executed": {"method": "column-edge-continuation-v1",
                        "sha256": sha(REPO / "src/pdf_processing/continuation.py")},
        "roundtrip": {"entire_serialized_conversion_equal": True,
                      "confidence_null_restored_to_nan_only_in_memory": ["parse_score", "table_score", "pages.1.parse_score", "pages.1.table_score"],
                      "alias_mode": "model_dump_json default aliases; no cref/$ref rewriting needed",
                      "original_provider_bytes_unchanged": True},
        "stock": stock, "continuation_v3": candidate,
        "predict_reading_order_equal": True,
        "caption_footnote_merge_mappings_equal": all(stock_trace[k] == candidate_trace[k]
              for k in ("predict_to_captions", "predict_to_footnotes", "predict_merges")),
        "negative_order_check_detects_same_wrong_interleaving_in_both": True,
        "runner_sha256": sha(Path(__file__)),
    }
    save(HERE / "summary.json", summary)
    print(json.dumps({"stock": stock["selected_paragraphs_adjacent"],
                      "continuation_v3": candidate["selected_paragraphs_adjacent"],
                      "all_document_text_sequence_equal": stock["text_orig_label_provenance_sequence_equal_original"]
                          and candidate["text_orig_label_provenance_sequence_equal_original"]}))


if __name__ == "__main__":
    main()
