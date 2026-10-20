"""Seven bounded stock Docling CPU probes; observe without changing OCR decisions."""

import copy
import fcntl
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROTOTYPE = REPO / "docs/prototypes/pdf-checkpoint-prototype"
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
REGISTRY_SHA = "8b798cdf808d01782b8dce9fabf85c7373effaa63477248dc1e95f8410813c6a"
MODELS = PROTOTYPE / ".venv/lib/python3.12/site-packages/rapidocr/models"
LOCK = Path("/private/tmp/data-ingestion-pdf-qualification.lock")
JOBS = [(f"controls-p{p}-full", p, True, ["en"]) for p in range(3, 7)] + [
    ("controls-p7-selective", 7, False, ["chinese"]),
    ("controls-p7-full", 7, True, ["chinese"]),
    ("controls-p8-full", 8, True, ["chinese"]),
]
LIMIT = 6 * 1024**3
TIMEOUT = 180


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def frozen_files():
    files = [REGISTRY, PROTOTYPE / "experiment.py", Path(__file__).resolve()]
    files += [p for p in sorted((PROTOTYPE / "PROTOTYPE-wipe-me/hf").glob(
        "hub/models--*/snapshots/**/*")) if p.is_file()]
    files += sorted(MODELS.glob("*.onnx"))
    files += [REPO / next(s for s in json.loads(REGISTRY.read_text())["sources"]
                         if s["id"] == "SRC05")["path"]]
    return {str(p.relative_to(REPO)): sha(p) for p in files}


def check():
    assert sha(REGISTRY) == REGISTRY_SHA
    assert importlib.metadata.version("docling") == "2.102.0"
    assert importlib.metadata.version("docling-core") == "2.96.0"
    pins = json.loads((PROTOTYPE / "evidence/native-method.json").read_text())["model_artifacts"]
    actual = {"rapidocr/" + p.name: sha(p) for p in MODELS.glob("*.onnx")}
    assert actual == {k: v for k, v in pins.items() if k.startswith("rapidocr/")}
    assert len(actual) == 3
    assert len(JOBS) == 7 and {j[1] for j in JOBS} == set(range(3, 9))
    return frozen_files()


def worker(job):
    name, page, full, languages = job
    out = HERE / "runs" / name
    registry = json.loads(REGISTRY.read_text())
    source = next(s for s in registry["sources"] if s["id"] == "SRC05")
    pdf = REPO / source["path"]
    assert sha(pdf) == source["sha256"]
    import numpy as np
    import rapidocr
    from rapidocr import RapidOCR
    from rapidocr.utils.process_img import map_boxes_to_original
    from omegaconf import OmegaConf
    from PIL import Image
    import torch
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    state = threading.local()
    calls = out / "raw-ocr-calls"
    calls.mkdir()
    counter = []

    def plain(value):
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, (list, tuple)):
            return [plain(v) for v in value]
        if isinstance(value, dict):
            return {k: plain(v) for k, v in value.items()}
        return value

    class ObservedRapidOCR(RapidOCR):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            sessions = {key: obj.session.session for key, obj in
                        (("det", self.text_det), ("cls", self.text_cls), ("rec", self.text_rec))}
            assert all(s.get_providers() == ["CPUExecutionProvider"] for s in sessions.values())
            assert self.use_cls is True and self.text_rec.rec_batch_num == 1
            assert self.text_cls.cls_batch_num == 1
            dictionary = self.text_rec.session.get_character_list()
            save(out / "producer.json", {
                "constructor_params": kwargs.get("params"),
                "resolved_config": OmegaConf.to_container(self.cfg, resolve=True, enum_to_str=True),
                "actual_sessions": {key: {"providers": s.get_providers(),
                    "provider_options": s.get_provider_options(),
                    "intra_op_num_threads": s.get_session_options().intra_op_num_threads,
                    "inter_op_num_threads": s.get_session_options().inter_op_num_threads}
                    for key, s in sessions.items()},
                "model_sha256": {p.name: sha(p) for p in MODELS.glob("*.onnx")},
                "recognizer_dictionary": {"origin": "recognizer ONNX embedded metadata",
                    "character_count": len(dictionary),
                    "utf8_newline_joined_sha256": hashlib.sha256("\n".join(dictionary).encode()).hexdigest()},
                "requested_docling_lang": languages,
                "actual_recognizer": "fixed cached PP-OCRv6_rec_small Chinese model, embedded dictionary",
                "use_cls_option": None, "effective_use_cls": self.use_cls,
            })

        def __call__(self, image, *args, **kwargs):
            number = len(counter)
            counter.append(number)
            state.call = calls / f"{number:03}"
            rect = state.rects.pop(0)
            state.mapping = {"physical_page_1based": page, "ocr_rect_top_left_points": rect,
                "docling_render_scale": 3,
                "pixel_to_source_pdf_top_left": {"x_scale": 1/3, "y_scale": 1/3,
                    "x_offset": rect[0], "y_offset": rect[1]},
                "source_sha256": source["sha256"], "source_path": source["path"]}
            Image.fromarray(image).save(state.call.with_suffix(".png"))
            started = time.perf_counter()
            result = super().__call__(image, *args, **kwargs)
            save(state.call.with_suffix(".output.json"), plain({
                "source_mapping": state.mapping, "effective_call_kwargs": kwargs,
                "boxes_crop_pixels": result.boxes,
                "texts": result.txts, "scores": result.scores,
                "stage_seconds": result.elapse_list,
                "seconds_including_observation": time.perf_counter()-started}))
            return result

        def build_final_output(self, image, det, cls, rec, crops, record):
            mapped = None if det.boxes is None else map_boxes_to_original(
                copy.deepcopy(det.boxes), record, *image.shape[:2])
            save(state.call.with_suffix(".raw.json"), plain({
                "source_mapping": state.mapping,
                "detector_boxes_before_mapping": det.boxes,
                "detector_boxes_crop_pixels": mapped, "detector_scores": det.scores,
                "recognizer_texts": rec.txts, "recognizer_scores": rec.scores,
                "classifier_results": cls.cls_res,
                "stage_seconds": [det.elapse, cls.elapse, rec.elapse],
                "preprocessing_coordinate_record": record,
                "input_image_shape_hwc": image.shape,
            }))
            return super().build_final_output(image, det, cls, rec, crops, record)

    rapidocr.RapidOCR = ObservedRapidOCR
    spec = importlib.util.spec_from_file_location("g2_stock_experiment", PROTOTYPE / "experiment.py")
    experiment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiment)
    from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
    original_rects = RapidOcrModel.get_ocr_rects
    original_merge = RapidOcrModel.post_process_cells

    def observed_rects(self, pdf_page):
        rects = original_rects(self, pdf_page)
        state.rects = [r.as_tuple() for r in rects if r.area() > 0]
        return rects

    def observed_merge(self, cells, pdf_page):
        native = [c.model_dump(mode="json") for c in pdf_page.cells]
        ocr = [c.model_dump(mode="json") for c in cells]
        original_merge(self, cells, pdf_page)
        save(out / "cell-merge.json", {"physical_page_1based": page,
            "native_before": native, "ocr_before": ocr,
            "merged_after": [c.model_dump(mode="json") for c in pdf_page.cells]})

    RapidOcrModel.get_ocr_rects = observed_rects
    RapidOcrModel.post_process_cells = observed_merge
    original_options = experiment.options

    def options(scan=False):
        result = original_options(scan)
        result.do_ocr = True
        result.layout_batch_size = result.ocr_batch_size = result.table_batch_size = 1
        result.ocr_options.lang = languages
        result.ocr_options.force_full_page_ocr = full
        result.ocr_options.det_model_path = str(MODELS / "PP-OCRv6_det_small.onnx")
        result.ocr_options.rec_model_path = str(MODELS / "PP-OCRv6_rec_small.onnx")
        result.ocr_options.cls_model_path = str(MODELS / "ch_ppocr_mobile_v2.0_cls_mobile.onnx")
        result.ocr_options.rapidocr_params = {
            "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            "EngineConfig.onnxruntime.use_cuda": False,
            "EngineConfig.onnxruntime.use_coreml": False,
            "EngineConfig.onnxruntime.use_dml": False,
            "EngineConfig.onnxruntime.use_cann": False,
            "Rec.rec_batch_num": 1, "Cls.cls_batch_num": 1,
        }
        return result

    experiment.options = options
    original_convert = experiment.DocumentConverter.convert

    def observed_convert(self, *args, **kwargs):
        result = original_convert(self, *args, **kwargs)
        raw = result.model_dump_json(indent=2)
        assert isinstance(json.loads(raw), dict)
        (out / "conversion-result.json").write_text(raw)
        return result

    experiment.DocumentConverter.convert = observed_convert
    sys.argv = [str(PROTOTYPE / "experiment.py"), "baseline", str(pdf), "--out", str(out),
                "--start", str(page), "--end", str(page)]
    experiment.main()
    metrics = json.loads((out / "metrics.json").read_text())
    assert metrics["source_sha256"] == source["sha256"]
    assert metrics["page_stage_inputs"]["LayoutModel"] == 1
    assert metrics["page_stage_inputs"]["RapidOcrModel"] == 1
    assert len(counter) >= 1


def main():
    frozen = json.loads((HERE / "frozen-inputs.json").read_text())
    assert check() == frozen
    (HERE / "runs").mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HOME=str(PROTOTYPE / "PROTOTYPE-wipe-me/hf"), HF_HUB_OFFLINE="1",
               TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu", OMP_NUM_THREADS="4",
               OPENBLAS_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false")
    summary = {"scope": "Stock local CPU rotation/mixed probes; no Canonical Acceptance or SLO qualification",
        "registry_sha256": REGISTRY_SHA, "runner_sha256": sha(Path(__file__)),
        "sampled_tree_rss_stop_bytes": LIMIT, "timeout_seconds_per_child": TIMEOUT,
        "sample_period_seconds": .25, "shared_lock": str(LOCK), "jobs": []}
    save(HERE / "summary.json", summary)
    for job in JOBS:
        name, page, full, languages = job
        folder = HERE / "runs" / name
        folder.mkdir()
        with LOCK.open("a+") as lock:
            print(json.dumps({"event": "waiting_for_lock", "job": name}), flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX)
            available = psutil.virtual_memory().available
            assert available >= 8 * 1024**3, "Less than 8 GiB available before starting a child"
            command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--worker", name]
            started = time.monotonic()
            peak, stopped = 0, None
            print(json.dumps({"event": "start", "job": name}), flush=True)
            with (folder / "child.log").open("wb") as log:
                process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log, stderr=log,
                                           start_new_session=True)
                try:
                    while process.poll() is None:
                        try:
                            parent = psutil.Process(process.pid)
                            peak = max(peak, sum(p.memory_info().rss for p in
                                       [parent, *parent.children(recursive=True)]))
                        except psutil.NoSuchProcess:
                            pass
                        except (psutil.AccessDenied, PermissionError):
                            stopped = "resource_monitor_unavailable"
                            break
                        if peak > LIMIT:
                            stopped = "sampled_memory_stop"
                            break
                        if time.monotonic() - started > TIMEOUT:
                            stopped = "timeout"
                            break
                        time.sleep(.25)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            row = {"name": name, "source_id": "SRC05", "original_physical_page": page,
                "force_full_page_ocr": full, "requested_docling_lang": languages,
                "command": command, "available_before_bytes": available,
                "seconds_including_process_start_exit": time.monotonic()-started,
                "sampled_tree_peak_rss_bytes": peak, "exit_code": process.returncode, "stopped": stopped,
                "execution_status": "completed" if process.returncode == 0 and stopped is None else "failed"}
            summary["jobs"].append(row)
            save(HERE / "summary.json", summary)
            print(json.dumps(row), flush=True)
        if row["execution_status"] != "completed":
            break
    assert check() == frozen


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        assert check() == json.loads((HERE / "frozen-inputs.json").read_text())
        worker(next(j for j in JOBS if j[0] == sys.argv[2]))
    elif sys.argv[1:] == ["--freeze"]:
        target = HERE / "frozen-inputs.json"
        assert not target.exists()
        save(target, check())
        print("Frozen source, runner, stock runner and model hashes verified; no inference.")
    else:
        main()
