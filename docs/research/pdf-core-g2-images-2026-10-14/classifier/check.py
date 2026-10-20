"""Offline artifact and native chart-gate self-check; no model loading or inference."""
import hashlib
import json
from pathlib import Path

from docling.models.stages.chart_extraction.granite_vision import ChartExtractionModelGraniteVisionV4
from docling_core.types.doc import DoclingDocument, PictureClassificationMetaField, PictureMeta
from docling_core.types.doc.document import PictureClassificationPrediction

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


gate = object.__new__(ChartExtractionModelGraniteVisionV4)
gate.enabled = True
document = DoclingDocument(name="native-gate-check")
picture = document.add_picture()
assert not gate.is_processable(document, picture)
controls = []
for class_name, confidence, expected in [
    ("bar_chart", .001, True), ("line_chart", None, True), ("pie_chart", .001, True),
    ("flow_chart", .999, False), ("scatter_plot", .999, False), ("box_plot", .999, False),
    ("other", .999, False), ("unknown", .999, False),
]:
    picture.meta = PictureMeta(classification=PictureClassificationMetaField(predictions=[
        PictureClassificationPrediction(class_name=class_name, confidence=confidence)]))
    observed = gate.is_processable(document, picture)
    assert observed == expected
    controls.append({"class_name": class_name, "confidence": confidence, "native_chart_gate": observed})
picture.meta.classification = PictureClassificationMetaField(predictions=[
    PictureClassificationPrediction(class_name="other", confidence=.501),
    PictureClassificationPrediction(class_name="bar_chart", confidence=.499)])
assert not gate.is_processable(document, picture)
controls.append({"predictions": [{"class_name": "other", "confidence": .501},
                                {"class_name": "bar_chart", "confidence": .499}], "native_chart_gate": False})

observations = json.loads((HERE / "observations.json").read_text())
assert sha(HERE / "probe.py") == observations["runner_sha256"]
assert sha(REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json") == observations["registry_sha256"]
assert sha(HERE / "inputs.json") == observations["inputs_sha256"]
assert observations["exit_code"] == 0 and observations["stopped"] is None
assert len(observations["completed_inputs"]) == 12
method = json.loads((HERE / "method.json").read_text())
for entry in json.loads((HERE / "inputs.json").read_text())["manifests"]:
    assert sha(REPO / entry["path"]) == entry["sha256"]
for case_id in observations["completed_inputs"]:
    out = HERE / "runs" / case_id
    result = json.loads((out / "result.json").read_text())
    before = json.loads((out / "picture-before.json").read_text())
    item = json.loads((out / "picture-item.json").read_text())
    raw = json.loads((out / "engine-output.json").read_text())[0]
    assert sha(REPO / result["input"]["path"]) == result["input"]["sha256"]
    predictions = item["meta"]["classification"]["predictions"]
    assert len(predictions) == len(raw["scores"]) == 26
    assert [p["confidence"] for p in predictions] == raw["scores"]
    assert [p["class_name"] for p in predictions] == [method["classes"][str(i)] for i in raw["label_ids"]]
    assert item["annotations"][0]["predicted_classes"] == [
        {"class_name": p["class_name"], "confidence": p["confidence"]} for p in predictions]
    assert {k: v for k, v in item.items() if k not in {"annotations", "meta"}} == {
        k: v for k, v in before.items() if k not in {"annotations", "meta"}}
    assert method["devices"] == ["cpu"] and method["dtypes"] == ["torch.float32"]
    assert method["threads"] == 4 and method["interop_threads"] == 1 and method["batch"] == 1
    assert result["native_chart_gate_processable"] == (result["top_class"] in gate.SUPPORTED_CHART_TYPES)
report = {"artifact_checks": "passed", "classification_inference_cases": 12,
          "gate_checks_no_chart_model_loaded": controls,
          "scope": "Serialization/device/provenance and gate contract checks, not quality acceptance"}
(HERE / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"artifact_checks": "passed", "inference_cases": 12, "gate_controls": len(controls)}))
