"""Execute frozen controls against the existing rule policy without modifying it."""
import hashlib
import importlib.metadata
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
controls_path = OUT / "controls.json"
frozen_hash = (OUT / "controls.sha256").read_text().strip()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(controls_path) == frozen_hash, "frozen_controls_changed"
controls = json.loads(controls_path.read_text())
for item in controls["source_identities"]:
    assert sha(ROOT / item["path"]) == item["sha256"], item["path"]
assert sys.executable == controls["runtime"]["executable"]
assert {k: importlib.metadata.version(k) for k in controls["runtime"]["packages"]} == controls["runtime"]["packages"]

network_attempts = []


def deny_network(*args, **kwargs):
    network_attempts.append("network_attempt_blocked")
    raise AssertionError("network_not_authorized")


socket.socket.connect = deny_network
socket.create_connection = deny_network
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests/pdf_processing/q01"))
from docling_core.types.doc import CoordOrigin, RefItem, Size
from docling_ibm_models.reading_order.reading_order_rb import PageElement, ReadingOrderPredictor
from pdf_processing.continuation import predict_merges


def element(v):
    left, top, right, bottom = v["box_top_left"]
    width, height = v["page_size"]
    return PageElement(cid=v["cid"], ref=RefItem(cref=v["ref"]), page_no=v["page_no"],
                       page_size=Size(width=width, height=height), text=v["text"], label=v["label"],
                       l=left, r=right, t=height-top, b=height-bottom, coord_origin=CoordOrigin.BOTTOMLEFT)


def invariants(elements, before, actual):
    ids = {v.cid for v in elements}
    targets = [member for members in actual.values() for member in members]
    return {
        "input_unchanged": before == [v.model_dump(mode="json") for v in elements],
        "all_output_ids_exist": all(root in ids and all(member in ids for member in members) for root, members in actual.items()),
        "chains_have_no_self_or_cycle": all(len([root, *members]) == len(set([root, *members])) for root, members in actual.items()),
        "targets_have_single_ownership": len(targets) == len(set(targets)),
        "chain_roots_not_targets": not (set(actual) & set(targets)),
    }


start = time.perf_counter()
results = []
for control in controls["cases"]:
    elements = [element(v) for v in control["input_order"]]
    before = [v.model_dump(mode="json") for v in elements]
    actual = predict_merges(elements)
    checks = invariants(elements, before, actual)
    normalized = {str(k): v for k, v in actual.items()}
    expected_match = normalized == control["expected"]
    results.append({"id": control["id"], "required": control["required"], "expected": control["expected"],
                    "actual": normalized, "invariants": checks, "pass": expected_match and all(checks.values())})

test_path = ROOT / "tests/pdf_processing/q01/test_continuation.py"
spec = importlib.util.spec_from_file_location("unchanged_continuation_tests", test_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.TestSuite()
for cls_name in ("Continuations", "Preservation"):
    cls = getattr(module, cls_name)
    for name in unittest.defaultTestLoader.getTestCaseNames(cls):
        if name != "test_input_content_not_mutated":
            suite.addTest(cls(name))
log = io.StringIO()
test_result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
assert sha(controls_path) == frozen_hash
for item in controls["source_identities"]:
    assert sha(ROOT / item["path"]) == item["sha256"], item["path"]

learned_modules = sorted(k for k in sys.modules if k.split(".")[0] in {"torch", "transformers", "onnxruntime", "rapidocr", "mlx", "paddle", "paddlex", "openai"})
failures = [v["id"] for v in results if not v["pass"]]
record = {
    "format": "adapter-continuation-results-v1", "controls_sha256": frozen_hash,
    "runtime": controls["runtime"], "source_identities": controls["source_identities"],
    "policy": "unchanged src/pdf_processing/continuation.py predict_merges; ReadingOrderPredictor only as upstream rule helper",
    "results": results, "case_count": len(results), "passed": len(results)-len(failures), "failed": failures,
    "existing_unmodified_test_suite": {"tests_run": test_result.testsRun, "successful": test_result.wasSuccessful(),
                                       "log": log.getvalue(), "not_run": [
                                           {"test": "Continuation.test_source_continues_into_body", "reason": "Required historical /private/tmp checkpoint directory absent"},
                                           {"test": "Preservation.test_input_content_not_mutated", "reason": "Required historical /private/tmp checkpoint directory absent; per-control input preservation checks run separately"}]},
    "network_attempts": network_attempts, "known_learned_runtime_modules_imported": learned_modules,
    "model_loads": 0, "inferences": 0, "installs": 0, "environment_creations": 0, "pdf_image_holdout_reads": 0,
    "elapsed_seconds": time.perf_counter()-start,
    "stop_required": bool(failures or not test_result.wasSuccessful() or network_attempts or learned_modules),
    "interpretation": "Pure continuation prerequisite control; no mapper or live Paddle capture. A failed native-label control remains a failure even if its typed counterfactual passes.",
}
assert not (OUT / "results.json").exists(), "Do not overwrite an observed run"
(OUT / "results.json").write_text(json.dumps(record, indent=2, ensure_ascii=False)+"\n")
print(json.dumps({k: record[k] for k in ("case_count", "passed", "failed", "stop_required", "elapsed_seconds")}, ensure_ascii=False))
print(json.dumps({"existing_tests": test_result.testsRun, "success": test_result.wasSuccessful(), "network_attempts": len(network_attempts), "learned_modules": learned_modules}))
raise SystemExit(1 if record["stop_required"] else 0)
