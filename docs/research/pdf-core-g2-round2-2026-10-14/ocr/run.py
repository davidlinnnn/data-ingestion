"""Three bounded, offline CPU probes; preserve raw OCR before output filtering."""

import base64
import copy
import hashlib
import importlib.metadata
import importlib.util
import io
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
PARSED = REPO / "docs/research/pdf-core-g2-local-cpu-2026-10-14/runs/nccu-p3-native/document.json"
SOURCE_OCR = REPO / "src/pdf_processing/ocr.py"
JOBS = ("fixed-panel-1x", "picture-scale3", "fixed-panel-2x")
LIMIT = 6 * 1024**3
TIMEOUT = 180


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def worker(name):
    import numpy as np
    import rapidocr
    from rapidocr import RapidOCR
    from rapidocr.utils.process_img import map_boxes_to_original
    from omegaconf import OmegaConf
    from PIL import Image

    folder = HERE / "runs" / name
    registry = json.loads(REGISTRY.read_text())
    case = next(c for c in registry["cases"] if c["id"] == "G1-O01")
    source = next(s for s in registry["sources"] if s["id"] == "SRC03")
    pdf = REPO / source["path"]
    assert sha(pdf) == source["sha256"]
    region = case["details"]["region"]
    models = Path(rapidocr.__file__).parent / "models"
    params = {
        "Det.model_path": str(models / "PP-OCRv6_det_small.onnx"),
        "Rec.model_path": str(models / "PP-OCRv6_rec_small.onnx"),
        "Cls.model_path": str(models / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"),
        "EngineConfig.onnxruntime.intra_op_num_threads": 4,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_coreml": False,
        "EngineConfig.onnxruntime.use_dml": False,
        "EngineConfig.onnxruntime.use_cann": False,
        "Rec.rec_batch_num": 1,
        "Cls.cls_batch_num": 1,
    }
    assert all(Path(v).is_file() for k, v in params.items() if k.endswith("model_path"))

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
        def __init__(self):
            super().__init__(params=params)
            sessions = {key: obj.session.session for key, obj in
                        (("det", self.text_det), ("cls", self.text_cls), ("rec", self.text_rec))}
            assert all(session.get_providers() == ["CPUExecutionProvider"] for session in sessions.values())
            save(folder / "producer.json", {
                "rapidocr": importlib.metadata.version("rapidocr"),
                "onnxruntime": importlib.metadata.version("onnxruntime"),
                "model_sha256": {p.name: sha(p) for p in models.glob("*.onnx")},
                "params": params,
                "resolved_config": OmegaConf.to_container(self.cfg, resolve=True, enum_to_str=True),
                "actual_sessions": {key: {"providers": s.get_providers(),
                                           "provider_options": s.get_provider_options(),
                                           "intra_op_num_threads": s.get_session_options().intra_op_num_threads,
                                           "inter_op_num_threads": s.get_session_options().inter_op_num_threads}
                                    for key, s in sessions.items()},
                "source_sha256": source["sha256"], "source_page_1based": 3,
            })

        def build_final_output(self, ori_img, det_res, cls_res, rec_res, crops, op_record):
            # Record once before the library drops blank or low-confidence recognition.
            mapped = None if det_res.boxes is None else map_boxes_to_original(
                copy.deepcopy(det_res.boxes), op_record, *ori_img.shape[:2])
            save(folder / "raw-stages.json", plain({
                "detector_boxes_pre_map": det_res.boxes,
                "detector_boxes_crop_pixels": mapped,
                "detector_scores": det_res.scores,
                "recognizer_texts": rec_res.txts,
                "recognizer_scores": rec_res.scores,
                "classifier_results": cls_res.cls_res,
                "stage_seconds": [det_res.elapse, cls_res.elapse, rec_res.elapse],
                "preprocessing_coordinate_record": op_record,
            }))
            return super().build_final_output(ori_img, det_res, cls_res, rec_res, crops, op_record)

    if name == "picture-scale3":
        spec = importlib.util.spec_from_file_location("existing_picture_ocr", SOURCE_OCR)
        existing = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(existing)
        rapidocr.RapidOCR = ObservedRapidOCR
        existing.execute({"parsed": str(PARSED), "pdf": str(pdf), "out": str(folder),
                          "component": "#/pictures/0", "scale": 3})
        result = json.loads((folder / "ocr.json").read_text())
        parsed = json.loads(PARSED.read_text())
        page_size = parsed["pages"]["3"]["size"]
        bbox = result["provenance"]["bbox"]
        height = page_size["height"]
        top_left = [bbox["l"], height - bbox["t"], bbox["r"], height - bbox["b"]]
        source_mapping = {"kind": "existing_component_integrity_checked_page_render",
                          "source_page_size_points": page_size, "bbox_top_left_points": top_left,
                          "pixel_to_pdf_top_left": {"x_scale": 1/3, "y_scale": 1/3,
                                                     "x_offset": round(top_left[0]*3)/3,
                                                     "y_offset": round(top_left[1]*3)/3},
                          "crop_rounding": "PIL crop rounds scale-multiplied bounds; offsets use rounded pixel edges",
                          "existing_crop_validation_source_sha256": sha(SOURCE_OCR),
                          "parsed_result_sha256": sha(PARSED)}
    else:
        evidence = region["selected_evidence"]
        original = REPO / evidence["path"]
        assert sha(original) == evidence["sha256"]
        crop = Image.open(original).convert("RGB")
        scale = 1 if name.endswith("1x") else 2
        if scale == 2:
            crop = crop.resize((crop.width*2, crop.height*2), Image.Resampling.LANCZOS)
        crop.save(folder / "figure.png")
        started = time.perf_counter()
        engine = ObservedRapidOCR()
        output = engine(crop)
        result = {"texts": list(output.txts or []), "scores": list(output.scores or []),
                  "boxes": [] if output.boxes is None else output.boxes.tolist(),
                  "stage_seconds": output.elapse_list,
                  "seconds_including_engine_load": time.perf_counter()-started,
                  "pixel_dimensions": crop.size, "crop_sha256": sha(folder / "figure.png")}
        save(folder / "ocr.json", result)
        image_box = region["image_placement_pdf_points_top_left"]
        xratio, yratio = (image_box[2]-image_box[0])/1262, (image_box[3]-image_box[1])/731
        source_mapping = {"kind": "fixed_original_embedded_image_panel",
                          "source_evidence": evidence, "resample_scale": scale,
                          "resample": "none" if scale == 1 else "PIL.LANCZOS",
                          "embedded_image_bbox_pixels": region["bbox"],
                          "bbox_top_left_points": region["pdf_points_top_left"],
                          "pixel_to_pdf_top_left": {"x_scale": xratio/scale, "y_scale": yratio/scale,
                                                     "x_offset": image_box[0]+region["bbox"][0]*xratio,
                                                     "y_offset": image_box[1]+region["bbox"][1]*yratio}}
    source_mapping.update({"source_path": source["path"], "source_sha256": source["sha256"],
                           "physical_page_1based": 3, "registry_sha256": sha(REGISTRY),
                           "oracle_pdf_bbox_top_left_points": region["pdf_points_top_left"],
                           "oracle_item_positions": case["details"]["expected"]["items"]})
    save(folder / "source-mapping.json", source_mapping)


def main():
    (HERE / "runs").mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu",
               OMP_NUM_THREADS="4", OPENBLAS_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false")
    summary = {"scope": "G1-O01 selected image OCR diagnosis, not qualification",
               "runner_sha256": sha(Path(__file__)), "source_ocr_sha256": sha(SOURCE_OCR),
               "registry_sha256": sha(REGISTRY), "sampled_tree_rss_limit_bytes": LIMIT,
               "timeout_seconds_per_child": TIMEOUT, "sample_period_seconds": .25, "jobs": []}
    save(HERE / "summary.json", summary)
    for name in JOBS:
        folder = HERE / "runs" / name
        folder.mkdir()
        available = psutil.virtual_memory().available
        assert available >= 8*1024**3, "Insufficient available memory"
        command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--worker", name]
        peak, stopped = 0, None
        started = time.monotonic()
        with (folder / "child.log").open("wb") as log:
            process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log, stderr=log,
                                       start_new_session=True)
            try:
                while process.poll() is None:
                    try:
                        parent = psutil.Process(process.pid)
                        peak = max(peak, sum(p.memory_info().rss for p in [parent, *parent.children(recursive=True)]))
                    except psutil.NoSuchProcess:
                        pass
                    except (psutil.AccessDenied, PermissionError):
                        stopped = "resource_monitor_unavailable"
                        break
                    if peak > LIMIT:
                        stopped = "sampled_memory_stop"
                        break
                    if time.monotonic()-started > TIMEOUT:
                        stopped = "timeout"
                        break
                    time.sleep(.25)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        row = {"job": name, "command": command, "available_before_bytes": available,
               "seconds_including_process_start_exit": time.monotonic()-started,
               "sampled_tree_peak_rss_bytes": peak, "exit_code": process.returncode, "stopped": stopped}
        summary["jobs"].append(row)
        save(HERE / "summary.json", summary)
        print(json.dumps(row), flush=True)
        if process.returncode != 0 or stopped is not None:
            break
    assert sha(REGISTRY) == summary["registry_sha256"]
    assert sha(SOURCE_OCR) == summary["source_ocr_sha256"]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(sys.argv[2])
    else:
        main()
