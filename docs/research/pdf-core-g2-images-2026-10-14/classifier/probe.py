"""One bounded offline CPU worker; source and layout crops, no detector qualification."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
INPUTS = HERE / "inputs.json"
LIMIT = 6 * 1024**3
TIMEOUT = 180


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def child():
    import torch
    from PIL import Image
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.base_models import ItemAndImageEnrichmentElement
    from docling.datamodel.image_classification_engine_options import TransformersImageClassificationEngineOptions
    from docling.datamodel.picture_classification_options import DocumentPictureClassifierOptions
    from docling.models.stages.chart_extraction.granite_vision import ChartExtractionModelGraniteVisionV4
    from docling.models.stages.picture_classifier.document_picture_classifier import DocumentPictureClassifier
    from docling_core.types.doc import DoclingDocument

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    downloaded = json.loads((HERE / "download.json").read_text())
    snapshot = Path(downloaded["snapshot_path"])
    for entry in downloaded["files"]:
        assert sha(snapshot / entry["name"]) == entry["sha256"]
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    link = artifacts / downloaded["repo"].replace("/", "--")
    if not link.exists():
        link.symlink_to(snapshot, target_is_directory=True)
    options = DocumentPictureClassifierOptions.from_preset("document_figure_classifier_v2",
        engine_options=TransformersImageClassificationEngineOptions(torch_dtype="float32", compile_model=False))
    options.model_spec.revision = downloaded["revision"]
    started = time.monotonic()
    stage = DocumentPictureClassifier(enabled=True, artifacts_path=artifacts, options=options,
             accelerator_options=AcceleratorOptions(device="cpu", num_threads=4), enable_remote_services=False)
    load_seconds = time.monotonic() - started
    model = stage.engine._model
    devices = sorted({str(p.device) for p in model.parameters()})
    dtypes = sorted({str(p.dtype) for p in model.parameters()})
    assert devices == ["cpu"] and dtypes == ["torch.float32"]
    save(HERE / "method.json", {"repo": downloaded["repo"], "revision": downloaded["revision"],
         "options": options.model_dump(mode="json", serialize_as_any=True), "devices": devices, "dtypes": dtypes,
         "threads": torch.get_num_threads(), "interop_threads": torch.get_num_interop_threads(), "batch": 1,
         "load_seconds": load_seconds, "classes": stage.engine.get_label_mapping(),
         "versions": {p: importlib.metadata.version(p) for p in ["docling", "docling-core", "transformers", "torch"]}})
    # Invoke the native gate without loading its independent multi-billion-parameter model.
    chart_gate = object.__new__(ChartExtractionModelGraniteVisionV4)
    chart_gate.enabled = True
    for locator in json.loads(INPUTS.read_text())["inputs"]:
        case_id = locator["input_id"]
        image_path = REPO / locator["path"]
        assert sha(image_path) == locator["sha256"]
        image = Image.open(image_path).convert("RGB")
        out = HERE / "runs" / case_id
        out.mkdir()
        if "provider_document" in locator:
            provider_path = REPO / locator["provider_document"]
            assert sha(provider_path) == locator["provider_document_sha256"]
            document = DoclingDocument.load_from_json(provider_path)
            picture = document.pictures[int(locator["picture_ref"].split("/")[-1])]
            assert picture.self_ref == locator["picture_ref"]
        else:
            document = DoclingDocument(name=case_id)
            picture = document.add_picture()
        save(out / "picture-before.json", picture.model_dump(mode="json"))
        original = stage.engine.predict_batch

        def observed_predict(inputs):
            assert len(inputs) == 1
            outputs = original(inputs)
            save(out / "engine-output.json", [o.model_dump(mode="json") for o in outputs])
            return outputs

        stage.engine.predict_batch = observed_predict
        assert stage.is_processable(document, picture)
        started = time.monotonic()
        outputs = list(stage(document, [ItemAndImageEnrichmentElement(item=picture, image=image)]))
        inference_seconds = time.monotonic() - started
        stage.engine.predict_batch = original
        assert len(outputs) == 1 and outputs[0] is picture
        predictions = picture.meta.classification.predictions
        assert len(predictions) == len(stage.engine.get_label_mapping()) == 26
        scores = [p.confidence for p in predictions]
        assert scores == sorted(scores, reverse=True) and abs(sum(scores) - 1) < 1e-5
        save(out / "picture-item.json", picture.model_dump(mode="json"))
        main = picture.meta.classification.get_main_prediction()
        result = {"execution_status": "completed", "case_id": case_id,
             "input": locator, "input_pixels": image.size, "stage_call_seconds": inference_seconds,
             "top_class": main.class_name, "top_score": main.confidence,
             "native_chart_gate_processable": chart_gate.is_processable(document, picture),
             "quality_status": "requires_source_review"}
        save(out / "result.json", result)
        print(json.dumps({k: result[k] for k in ["case_id", "top_class", "top_score", "stage_call_seconds"]}), flush=True)


def main():
    inputs = json.loads(INPUTS.read_text())
    assert len(inputs["inputs"]) == len({i["input_id"] for i in inputs["inputs"]}) == 12
    for entry in inputs["manifests"]:
        assert sha(REPO / entry["path"]) == entry["sha256"]
    summary = {"runner_sha256": sha(Path(__file__)), "registry_sha256": sha(REGISTRY),
               "inputs_sha256": sha(INPUTS), "scope": "Fixed and rerendered actual layout crops; not end-to-end enrichment"}
    (HERE / "runs").mkdir(exist_ok=False)
    environment = os.environ.copy()
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu",
                       OMP_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false")
    available = psutil.virtual_memory().available
    assert available >= 8 * 1024**3, "Less than 8 GiB available before starting a child"
    command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--child"]
    started, peak, stopped = time.monotonic(), 0, None
    with (HERE / "child.log").open("wb") as log:
        process = subprocess.Popen(command, cwd=REPO, env=environment, stdout=log, stderr=log, start_new_session=True)
        try:
            while process.poll() is None:
                try:
                    owner = psutil.Process(process.pid)
                    peak = max(peak, sum(p.memory_info().rss for p in [owner, *owner.children(recursive=True)]))
                except psutil.NoSuchProcess:
                    pass
                except (psutil.AccessDenied, PermissionError):
                    stopped = "resource_monitor_unavailable"
                    break
                if peak > LIMIT or time.monotonic() - started > TIMEOUT:
                    stopped = "sampled_memory_stop" if peak > LIMIT else "timeout"
                    break
                time.sleep(.25)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    summary.update(command=command, available_before_bytes=available, exit_code=process.returncode, stopped=stopped,
                   child_wall_seconds=time.monotonic()-started, sampled_tree_peak_rss_bytes=peak,
                   sample_seconds=.25, limit_bytes=LIMIT, timeout_seconds=TIMEOUT,
                   completed_inputs=sorted(p.parent.name for p in (HERE / "runs").glob("*/result.json")))
    save(HERE / "observations.json", summary)
    print(json.dumps(summary), flush=True)
    if process.returncode or stopped:
        raise RuntimeError("Bounded probe failed; preserve artifacts and inspect before retry")
    assert len(summary["completed_inputs"]) == 12
    assert sha(REGISTRY) == summary["registry_sha256"] and sha(INPUTS) == summary["inputs_sha256"]


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        child()
    else:
        main()
