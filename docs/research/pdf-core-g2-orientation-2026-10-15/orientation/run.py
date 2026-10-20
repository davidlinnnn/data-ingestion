"""Four full-page, model-decided orientation probes; no oracle input to inference."""

import copy
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REGISTRY = REPO / "docs/fixtures/pdf-core-g1-2026-10-14/cases.json"
PDF = REPO / "docs/fixtures/pdf-core-g1-controls-2026-10-14/controls.pdf"
MODEL = REPO / ".scratch/pdf-core-g2-orientation-2026-10-15/models/PP-LCNet_x1_0_doc_ori_onnx"
BASELINE = REPO / "docs/prototypes/pdf-checkpoint-prototype/.venv"
MODELS = BASELINE / "lib/python3.12/site-packages/rapidocr/models"
PAGES = (3, 4, 5, 6)
SCALE = 3
LABELS = (0, 90, 180, 270)
LIMIT = 6 * 1024**3
TIMEOUT = 180
LOCK = "/private/tmp/data-ingestion-pdf-qualification.lock"
EXPECTED = {
    "inference.onnx": "af9a0a4f317ff0709ce752067807f819cb15d883f8ecad89f28df1c6ee2d9c92",
    "PP-OCRv6_det_small.onnx": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    "PP-OCRv6_rec_small.onnx": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx": "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def plain(value):
    import numpy as np
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    return value


def forward_matrix(width, height, angle):
    # Continuous raster edges: samples sit at (column+.5, row+.5).
    return {
        0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        90: [[0, 1, 0], [-1, 0, width], [0, 0, 1]],
        180: [[-1, 0, width], [0, -1, height], [0, 0, 1]],
        270: [[0, -1, height], [1, 0, 0], [0, 0, 1]],
    }[angle]


def preprocess(image):
    import cv2
    import numpy as np
    height, width = image.shape[:2]
    ratio = 256 / min(width, height)
    resized = cv2.resize(image, (round(width * ratio), round(height * ratio)), interpolation=cv2.INTER_LINEAR)
    y, x = (resized.shape[0] - 224) // 2, (resized.shape[1] - 224) // 2
    crop = resized[y:y + 224, x:x + 224]
    channels = list(cv2.split(crop))
    for c, (mean, std) in enumerate(zip([.485, .456, .406], [.229, .224, .225])):
        channels[c] = channels[c].astype(np.float32)
        channels[c] *= (1 / 255) / std
        channels[c] += -mean / std
    value = cv2.merge(channels)
    tensor = value.transpose(2, 0, 1)[None].astype("float32")
    return tensor, crop, {"original_wh": [width, height], "resized_wh": [resized.shape[1], resized.shape[0]],
                          "crop_xywh": [x, y, 224, 224], "tensor_shape": list(tensor.shape),
                          "tensor_dtype": str(tensor.dtype), "tensor_sha256": hashlib.sha256(tensor.tobytes()).hexdigest()}


def self_check():
    import numpy as np
    image = np.arange(3 * 5).reshape(3, 5)
    for angle in LABELS:
        rotated = np.rot90(image, angle // 90)
        matrix = np.array(forward_matrix(5, 3, angle))
        inverse = np.linalg.inv(matrix)
        for row in range(3):
            for col in range(5):
                dest = matrix @ np.array([col + .5, row + .5, 1])
                assert rotated[int(dest[1]), int(dest[0])] == image[row, col]
                assert np.allclose(inverse @ dest, [col + .5, row + .5, 1])
        tensor, crop, record = preprocess(np.zeros((3 * 80, 5 * 80, 3), dtype=np.uint8))
        assert tensor.shape == (1, 3, 224, 224) and crop.shape == (224, 224, 3)
        assert np.allclose(tensor[0, :, 0, 0], -np.array([.485, .456, .406]) / [.229, .224, .225])
    print("preprocess and all four forward/inverse transforms: passed", flush=True)


def checked_inputs():
    registry = json.loads(REGISTRY.read_text())
    source = next(s for s in registry["sources"] if s["id"] == "SRC05")
    assert source["path"] == str(PDF.relative_to(REPO)) and sha(PDF) == source["sha256"]
    for name, expected in EXPECTED.items():
        assert sha((MODEL if name == "inference.onnx" else MODELS) / name) == expected
    return source


def prepare():
    import pypdfium2 as pdfium
    from PIL import Image
    source = checked_inputs()
    doc = pdfium.PdfDocument(PDF)
    manifest = {"source_id": "SRC05", "source_path": source["path"], "source_sha256": sha(PDF),
                "registry_sha256": sha(REGISTRY), "render_scale_pixels_per_point": SCALE,
                "render_dpi": 216, "producer_input_policy": "Full physical page RGB render only; no oracle text, region or expected angle.", "pages": []}
    for number in PAGES:
        folder = HERE / "inputs" / f"p{number}"
        folder.mkdir(parents=True, exist_ok=False)
        page = doc[number - 1]
        assert page.get_rotation() == 0
        textpage = page.get_textpage()
        assert textpage.count_chars() == 0
        image = page.render(scale=SCALE).to_pil().convert("RGB")
        image.save(folder / "source.png")
        with Image.open(folder / "source.png") as check:
            assert check.size == image.size
        manifest["pages"].append({"physical_page_1based": number, "page_size_points": list(page.get_size()),
                                  "pdf_rotate_degrees": page.get_rotation(), "native_text_characters": textpage.count_chars(),
                                  "path": str((folder / "source.png").relative_to(REPO)),
                                  "sha256": sha(folder / "source.png"), "pixels_wh": list(image.size)})
        textpage.close()
        page.close()
    doc.close()
    save(HERE / "input-manifest.json", manifest)
    save(HERE / "method.json", {"runner_sha256": sha(Path(__file__)), "model": json.loads((HERE / "model-download.json").read_text()),
         "source_registry_sha256": sha(REGISTRY), "source_sha256": sha(PDF), "model_sha256": EXPECTED,
         "environment": {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
                         "packages": {p: importlib.metadata.version(p) for p in ["rapidocr", "onnxruntime", "numpy", "opencv-python", "Pillow", "pypdfium2", "psutil"]}},
         "orientation": {"labels_in_index_order": LABELS, "label_semantics": "Corrective counterclockwise degrees; direct argmax of raw network output; no softmax added, threshold or oracle fallback.",
                         "preprocess": "RGB; aspect preserve short-edge256 round both dims; OpenCV INTER_LINEAR; center224 crop using integer floor; per-channel float32 pixel*=((1/255)/std), pixel+=(-mean/std), ImageNet RGB mean [.485,.456,.406], std [.229,.224,.225], matching tagged PaddleX arithmetic; NCHW batch1.",
                         "official_inference_yml": (MODEL / "inference.yml").read_text(),
                         "correction": "numpy.rot90(full RGB raster, predicted_label//90), exact right-angle permutation; no interpolation."},
         "ocr": {"engine": "RapidOCR 3.9.2", "backend": "onnxruntime", "recognizer_language": "CH explicitly fixed for English plus Chinese; no language detection or per-page switching.",
                 "scope": "Full normalized page; preserve library output order and all raw stage results before score filtering. No selected-region crop or reading-order repair.",
                 "threads_intra_inter": [4, 1], "batch_rec_cls": [1, 1]},
         "resources": {"lock": LOCK, "timeout_seconds_per_child": TIMEOUT, "sampled_tree_rss_limit_bytes": LIMIT,
                       "available_before_min_bytes": 8 * 1024**3, "sampling_seconds": .25, "one_model_child_at_a_time": True},
         "coordinate_convention": "Top-left origin, x right, y down, continuous raster edges [0,W]x[0,H]; sample centers column+.5,row+.5. Save 3x3 source-raster->normalized and inverse. Normalize detector quadrilaterals back through inverse then divide by render scale3 to original physical PDF points. Physical page never renumbered."})


def worker(number):
    import numpy as np
    import onnxruntime as ort
    from omegaconf import OmegaConf
    from PIL import Image
    from rapidocr import RapidOCR
    from rapidocr.utils.process_img import map_boxes_to_original
    checked_inputs()
    folder = HERE / "runs" / f"p{number}"
    manifest = json.loads((HERE / "input-manifest.json").read_text())
    item = next(p for p in manifest["pages"] if p["physical_page_1based"] == number)
    source = REPO / item["path"]
    assert sha(source) == item["sha256"]
    image = np.array(Image.open(source).convert("RGB"))
    start = time.perf_counter()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    options.enable_cpu_mem_arena = False
    session = ort.InferenceSession(str(MODEL / "inference.onnx"), sess_options=options, providers=["CPUExecutionProvider"])
    assert session.get_providers() == ["CPUExecutionProvider"]
    session.disable_fallback()
    load_seconds = time.perf_counter() - start
    tensor, crop, prep = preprocess(image)
    Image.fromarray(crop).save(folder / "orientation-input-224.png")
    np.save(folder / "orientation-input.npy", tensor, allow_pickle=False)
    infer_start = time.perf_counter()
    raw = session.run(None, {session.get_inputs()[0].name: tensor})
    infer_seconds = time.perf_counter() - infer_start
    assert len(raw) == 1 and raw[0].shape == (1, 4) and np.isfinite(raw[0]).all()
    np.save(folder / "orientation-output.npy", raw[0], allow_pickle=False)
    angle = LABELS[int(np.argmax(raw[0][0]))]
    save(folder / "orientation.json", {"physical_page_1based": number, "raw_outputs": plain(raw), "class_ids": [LABELS.index(angle)],
         "label_names": [str(angle)], "scores": [float(raw[0][0][LABELS.index(angle)])], "correction_ccw_degrees": angle,
         "preprocess": prep, "model_load_seconds": load_seconds, "inference_seconds": infer_seconds,
         "providers": session.get_providers(), "provider_options": session.get_provider_options(),
         "input_schema": [{"name": i.name, "shape": i.shape, "type": i.type} for i in session.get_inputs()],
         "output_schema": [{"name": i.name, "shape": i.shape, "type": i.type} for i in session.get_outputs()]})
    corrected = np.ascontiguousarray(np.rot90(image, angle // 90))
    Image.fromarray(corrected).save(folder / "normalized.png")
    matrix = np.array(forward_matrix(image.shape[1], image.shape[0], angle), dtype=float)
    inverse = np.linalg.inv(matrix)
    def mapped_boxes(boxes):
        result = []
        if boxes is None:
            return result
        for polygon in boxes:
            homogeneous = np.column_stack((polygon, np.ones(len(polygon))))
            pixels = (inverse @ homogeneous.T).T[:, :2]
            points = pixels / SCALE
            result.append({"normalized_polygon_pixels": plain(polygon), "original_source_polygon_pixels": plain(pixels),
                           "original_physical_page_1based": number, "original_source_polygon_pdf_points_top_left": plain(points),
                           "original_source_bbox_pdf_points_top_left": plain([*points.min(axis=0), *points.max(axis=0)])})
        return result
    params = {"Det.model_path": str(MODELS / "PP-OCRv6_det_small.onnx"), "Rec.model_path": str(MODELS / "PP-OCRv6_rec_small.onnx"),
              "Cls.model_path": str(MODELS / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"),
              "Det.lang_type": "ch", "Rec.lang_type": "ch", "Cls.lang_type": "ch",
              "EngineConfig.onnxruntime.intra_op_num_threads": 4, "EngineConfig.onnxruntime.inter_op_num_threads": 1,
              "EngineConfig.onnxruntime.use_cuda": False, "EngineConfig.onnxruntime.use_coreml": False,
              "EngineConfig.onnxruntime.use_dml": False, "EngineConfig.onnxruntime.use_cann": False,
              "Rec.rec_batch_num": 1, "Cls.cls_batch_num": 1}
    class ObservedOCR(RapidOCR):
        def build_final_output(self, ori_img, det_res, cls_res, rec_res, crops, op_record):
            mapped = None if det_res.boxes is None else map_boxes_to_original(copy.deepcopy(det_res.boxes), op_record, *ori_img.shape[:2])
            save(folder / "raw-ocr-stages.json", plain({"detector_boxes_pre_map": det_res.boxes, "detector_scores": det_res.scores,
                 "detector_boxes_normalized_page_pixels": mapped, "source_mapped_boxes": mapped_boxes(mapped),
                 "recognizer_texts": rec_res.txts, "recognizer_scores": rec_res.scores, "classifier_results": cls_res.cls_res,
                 "stage_seconds": [det_res.elapse, cls_res.elapse, rec_res.elapse], "preprocessing_coordinate_record": op_record}))
            return super().build_final_output(ori_img, det_res, cls_res, rec_res, crops, op_record)
    ocr_start = time.perf_counter()
    engine = ObservedOCR(params=params)
    sessions = {name: obj.session.session for name, obj in (("det", engine.text_det), ("cls", engine.text_cls), ("rec", engine.text_rec))}
    assert all(s.get_providers() == ["CPUExecutionProvider"] for s in sessions.values())
    for s in sessions.values():
        s.disable_fallback()
    characters = engine.text_rec.session.session.get_modelmeta().custom_metadata_map["character"]
    (folder / "recognizer-embedded-dictionary.txt").write_text(characters)
    (folder / "recognizer-decoder-dictionary.json").write_text(json.dumps(engine.text_rec.postprocess_op.character, ensure_ascii=False) + "\n")
    output = engine(Image.fromarray(corrected))
    ocr_seconds = time.perf_counter() - ocr_start
    save(folder / "ocr.json", plain({"texts": output.txts or [], "scores": output.scores or [], "boxes": output.boxes,
         "source_mapped_boxes": mapped_boxes(output.boxes), "stage_seconds": output.elapse_list,
         "seconds_including_ocr_engine_load": ocr_seconds, "normalized_pixels_wh": [corrected.shape[1], corrected.shape[0]]}))
    save(folder / "runtime.json", {"params": params, "resolved_config": OmegaConf.to_container(engine.cfg, resolve=True, enum_to_str=True),
         "sessions": {name: {"providers": s.get_providers(), "provider_options": s.get_provider_options(),
                    "threads_intra_inter": [s.get_session_options().intra_op_num_threads, s.get_session_options().inter_op_num_threads]} for name, s in sessions.items()},
         "dictionary": {"source": "recognizer ONNX custom_metadata_map.character; CTC decoder appends space and prepends blank if absent",
                        "embedded_sha256": sha(folder / "recognizer-embedded-dictionary.txt"), "embedded_entries": len(characters.splitlines()),
                        "decoder_sha256": sha(folder / "recognizer-decoder-dictionary.json"), "decoder_entries": len(engine.text_rec.postprocess_op.character)},
         "normalized_sha256": sha(folder / "normalized.png"), "source_render_sha256": sha(source), "source_pdf_sha256": sha(PDF)})
    save(folder / "source-mapping.json", {"source_id": "SRC05", "source_path": str(PDF.relative_to(REPO)), "source_sha256": sha(PDF),
         "physical_page_1based": number, "source_page_size_points": item["page_size_points"], "pdf_rotate_degrees": item["pdf_rotate_degrees"],
         "source_render_pixels_wh": item["pixels_wh"], "source_render_scale_pixels_per_point": SCALE,
         "model_predicted_corrective_ccw_degrees": angle, "normalized_pixels_wh": [corrected.shape[1], corrected.shape[0]],
         "source_raster_to_normalized_raster_3x3": matrix.tolist(), "normalized_raster_to_source_raster_3x3": inverse.tolist(),
         "normalized_raster_to_original_pdf_points_3x3": (np.diag([1 / SCALE, 1 / SCALE, 1]) @ inverse).tolist(),
         "coordinates": "Continuous raster edges, top-left, x right/y down; apply to every quadrilateral corner then min/max only for envelope."})
    checked_inputs()
    print(json.dumps({"page": number, "angle": angle, "orientation_inference_seconds": infer_seconds,
                      "ocr_seconds_including_load": ocr_seconds, "text_count": len(output.txts or [])}), flush=True)


def main():
    assert sha(Path(__file__)) == json.loads((HERE / "method.json").read_text())["runner_sha256"]
    checked_inputs()
    (HERE / "runs").mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", DOCLING_DEVICE="cpu", OMP_NUM_THREADS="4",
               OPENBLAS_NUM_THREADS="4", TOKENIZERS_PARALLELISM="false", PYTHONDONTWRITEBYTECODE="1")
    summary = {"runner_sha256": sha(Path(__file__)), "method_sha256": sha(HERE / "method.json"),
               "registry_sha256": sha(REGISTRY), "jobs": [], "resource_policy": json.loads((HERE / "method.json").read_text())["resources"]}
    save(HERE / "summary.json", summary)
    for number in PAGES:
        folder = HERE / "runs" / f"p{number}"
        folder.mkdir()
        with open(LOCK, "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            available = psutil.virtual_memory().available
            assert available >= 8 * 1024**3, "Less than 8 GiB available; no model child started"
            command = ["rtk", "proxy", sys.executable, "-B", str(Path(__file__)), "--worker", str(number)]
            started, peak, stopped = time.monotonic(), 0, None
            with (folder / "child.log").open("wb") as log:
                process = subprocess.Popen(command, cwd=REPO, env=env, stdout=log, stderr=log, start_new_session=True)
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
                        if time.monotonic() - started > TIMEOUT:
                            stopped = "timeout"
                            break
                        time.sleep(.25)
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
            summary["jobs"].append({"physical_page_1based": number, "command": command, "available_before_bytes": available,
                "child_pid_and_pgid": process.pid, "wall_seconds_including_process_start_exit": time.monotonic() - started,
                "sampled_tree_peak_rss_bytes": peak, "sample_period_seconds": .25, "exit_code": process.returncode,
                "stopped": stopped, "status": "completed" if process.returncode == 0 and stopped is None else "failed"})
            save(HERE / "summary.json", summary)
            print(json.dumps(summary["jobs"][-1]), flush=True)
            if summary["jobs"][-1]["status"] != "completed":
                break
    checked_inputs()
    assert sha(REGISTRY) == summary["registry_sha256"]


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-check":
        self_check()
    elif len(sys.argv) == 2 and sys.argv[1] == "--prepare":
        prepare()
    elif len(sys.argv) == 3 and sys.argv[1] == "--worker":
        worker(int(sys.argv[2]))
    else:
        main()
