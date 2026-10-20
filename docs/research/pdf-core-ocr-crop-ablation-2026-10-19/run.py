"""One page, 1+15 OCR reader calls; crop ablation is diagnostic, never an SDK option."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from capture import Capture, write

HERE = Path(__file__).resolve().parent
TRACE = HERE.parent / "pdf-core-ocr-boundary-trace-2026-10-19"
GUARD = HERE.parent / "pdf-core-eval-interfaces-2026-10-18/C"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def legacy():
    spec = importlib.util.spec_from_file_location("retained_boundary_run", TRACE / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rects(arm):
    from docling_core.types.doc import BoundingBox
    analysis = read(TRACE / "analysis.json")
    values = analysis["dedup"]["20" if arm == "A" else "0"]["rects"]
    assert len(values) == (1 if arm == "A" else 15)
    return [BoundingBox.model_validate(v) for v in values]


def crop(array, rect, scale):
    origin = rects("A")[0]
    coordinates = [(rect.l-origin.l)*scale, (rect.t-origin.t)*scale,
                   (rect.r-origin.l)*scale, (rect.b-origin.t)*scale]
    assert all(abs(v-round(v)) < 1e-8 for v in coordinates)
    left, top, right, bottom = map(round, coordinates)
    assert 0 <= left < right <= array.shape[1] and 0 <= top < bottom <= array.shape[0]
    result = array[top:bottom, left:right].copy()
    assert result.shape[:2] == (round((rect.b-rect.t)*scale), round((rect.r-rect.l)*scale))
    return result


def verify():
    legacy().verify()
    registration = read(HERE / "registration.json")
    for path, expected in registration["hashes"].items():
        assert sha(path) == expected, f"registered asset changed: {path}"
    return registration


def prepare():
    import numpy as np
    import rapidocr
    import unittest
    import downstream
    import test_capture
    import test_score
    prior = legacy().verify()
    # All probes and the evaluator are checked without loading inference models.
    downstream_check = downstream.preflight()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(module)
        for module in (test_capture, test_score))
    tests = unittest.TextTestRunner(verbosity=1).run(suite)
    assert tests.wasSuccessful(), "preflight tests failed; no inference"
    image = np.load(TRACE / "live/trace/ocr-engine-001.npy", allow_pickle=False)
    assert hashlib.sha256(image.tobytes()).hexdigest() == read(TRACE / "live/trace/ocr-engine-001.json")["input_pixel_sha256"]
    assert np.array_equal(crop(image, rects("A")[0], 3.0), image)
    crops = {arm: [{"rect": b.model_dump(mode="json"), "shape": list(crop(image, b, 3.0).shape),
                    "pixel_sha256": hashlib.sha256(crop(image, b, 3.0).tobytes()).hexdigest()} for b in rects(arm)]
             for arm in ("A", "B")}
    rapid = Path(rapidocr.__file__).parent
    paths = [*HERE.glob("*.py"), HERE / "reference.json", HERE / "reference.md", TRACE / "analysis.json",
        TRACE / "live/trace/ocr-engine-001.npy", TRACE / "live/trace/ocr-engine-001.json",
        TRACE / "live/trace/layout-clusters-001.json", TRACE / "live/trace/ocr-cells-before-merge-001.json",
        TRACE / "live/result.json", TRACE / "live/document.md", GUARD / "cpu_baseline_v2.py", GUARD / "cpu_baseline.py"]
    paths += [rapid / p for p in ("main.py", "config.yaml", "utils/load_image.py", "utils/process_img.py",
        "ch_ppocr_det/main.py", "ch_ppocr_det/utils.py", "ch_ppocr_cls/main.py", "ch_ppocr_rec/main.py")]
    sdk = Path(sys.prefix) / "lib/python3.12/site-packages/docling"
    paths += [sdk / p for p in ("pipeline/standard_pdf_pipeline.py",
        "models/stages/page_preprocessing/page_preprocessing_model.py",
        "models/stages/reading_order/readingorder_model.py",
        "models/stages/table_structure/table_structure_model.py",
        "models/stages/heading_hierarchy/heading_hierarchy_model.py")]
    reference = read(HERE / "reference.json")
    for item in (reference["source"], reference["scan"], reference["visual_check"]):
        path = legacy().REPO / item.get("path", item.get("image"))
        assert sha(path) == item["sha256"]
        paths.append(path)
    hashes = dict(prior["hashes"])
    for path in paths:
        key, digest = str(path.resolve()), sha(path)
        assert key not in hashes or hashes[key] == digest
        hashes[key] = digest
    registration = {"date": "2026-10-19 Asia/Taipei", "source": prior["source"], "hashes": hashes,
        "effective_options": prior["effective_options"], "crops": crops, "preflight_downstream": downstream_check,
        "preflight_tests": {"tests_run": tests.testsRun, "successful": tests.wasSuccessful()},
        "arms": {"A": {"reader_calls": 1}, "B": {"reader_calls": 15}}, "whole_worker_seconds_per_arm": 180,
        "max_tree_rss_bytes": 12*2**30, "min_available_bytes": 8*2**30, "prelaunch_available_bytes": 10*2**30,
        "API_calls": 0, "retries": 0, "Heron_inference": 0, "model_downloads": 0,
        "diagnostic_only": "frozen component crops, native OCR mapping and original downstream replay; not a public SDK setting or a full pipeline qualification",
        "stop": "A must exactly reproduce prior OCR; no B otherwise; no extra crops/parameters/models"}
    write(HERE / "registration.json", registration)
    verify()
    print("Registered A=1 and B=15 reader calls, 180 seconds each, zero API/retry/Heron inference.")


def child(arm):
    registration = verify()
    import numpy as np
    import torch
    from PIL import Image
    from omegaconf import OmegaConf
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat, Page
    from docling.datamodel.document import ConversionResult, InputDocument
    from docling.datamodel.settings import DocumentLimits
    from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
    from docling_core.types.doc import Size
    import downstream
    import score

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    out = HERE / arm
    options = legacy().options()
    started = time.monotonic()
    model = RapidOcrModel(enabled=True, artifacts_path=options.artifacts_path,
        options=options.ocr_options, accelerator_options=options.accelerator_options)
    write(out / "initialization.json", {"seconds": time.monotonic()-started})
    write(out / "reader-config.json", OmegaConf.to_container(model.reader.cfg, resolve=True, enum_to_str=True))
    array = np.load(TRACE / "live/trace/ocr-engine-001.npy", allow_pickle=False)
    boxes = rects(arm)
    class Backend:
        def is_valid(self):
            return True
        def get_page_image(self, *, scale, cropbox):
            assert scale == 3.0
            assert cropbox in boxes
            return Image.fromarray(crop(array, cropbox, scale))
    source = Path(read(TRACE / "live/result.json")["input"]["file"])
    in_doc = InputDocument(source, format=InputFormat.PDF, backend=PyPdfiumDocumentBackend,
        limits=DocumentLimits(page_range=(1, 1)))
    conv = ConversionResult(input=in_doc)
    page = Page(page_no=1, size=Size.model_validate(read(TRACE / "live/trace/layout-clusters-001.json")["page_size"]))
    page._backend = Backend()
    cells = []
    trace = Capture(out / "trace", registration["arms"][arm]["reader_calls"])
    reader, get_rects, merge = model.reader, model.get_ocr_rects, model.post_process_cells
    try:
        trace.install(type(reader))
        model.reader = trace.reader(reader)
        model.get_ocr_rects = lambda _: boxes
        # Keep the SDK's exact quad-to-TextCell mapper; official merge runs in replay().
        model.post_process_cells = lambda actual, _page, _conv: cells.extend(actual)
        begin = time.monotonic()
        assert list(model(conv, [page])) == [page]
        ocr_seconds = time.monotonic()-begin
        assert trace.calls == registration["arms"][arm]["reader_calls"]
        write(out / "ocr-cells.json", [c.model_dump(mode="json") for c in cells])
    finally:
        model.reader, model.get_ocr_rects, model.post_process_cells = reader, get_rects, merge
        trace.restore()
        in_doc._backend.unload()
    if arm == "A":
        fresh = read(out / "trace/reader-001/result.json")
        old = read(TRACE / "live/trace/ocr-engine-001.json")
        comparisons = {"boxes": fresh["boxes"] == old["boxes"], "texts": fresh["txts"] == old["texts"],
            "scores": fresh["scores"] == old["scores"],
            "cells": read(out / "ocr-cells.json") == read(TRACE / "live/trace/ocr-cells-before-merge-001.json")}
        write(out / "reproduction.json", comparisons)
        assert all(comparisons.values()), "A does not exactly reproduce retained OCR; B must not run"
    result = downstream.replay(cells)
    write(out / "downstream.json", result)
    write(out / "document.json", result["document"])
    (out / "document.md").write_text(result["markdown"])
    write(out / "score.json", score.score([c.model_dump(mode="json") for c in cells], result["document"]))
    if arm == "A":
        assert result["document"] == read(TRACE / "live/result.json")["document"]
        assert result["markdown"].encode() == (TRACE / "live/document.md").read_bytes()
    write(out / "completed.json", {"reader_calls": trace.calls, "instrumented_ocr_seconds": ocr_seconds,
        "official_downstream_cost": result["cost"], "API_calls": 0, "retries": 0})
    verify()


def parent(arm):
    import psutil
    sys.path.insert(0, str(GUARD))
    from cpu_baseline_v2 import tree_rss
    registration = verify()
    if arm == "B":
        assert read(HERE / "A/execution.json")["status"] == "completed"
        assert all(read(HERE / "A/reproduction.json").values())
        assert (HERE / "A/completed.json").exists()
    out, worker, samples, status = HERE / arm, None, [], "not_started"
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(exist_ok=False)
        begin = time.monotonic()
        try:
            if psutil.virtual_memory().available < registration["prelaunch_available_bytes"]:
                status = "insufficient_prelaunch_memory"
                return
            with (out / "worker.log").open("x") as log:
                worker = subprocess.Popen(["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--child", arm],
                    stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                status = "running"
                while worker.poll() is None:
                    rss, available = tree_rss(worker.pid), psutil.virtual_memory().available
                    samples.append({"seconds": time.monotonic()-begin, "rss": rss, "available": available})
                    if time.monotonic()-begin >= registration["whole_worker_seconds_per_arm"] or rss >= registration["max_tree_rss_bytes"] or available < registration["min_available_bytes"]:
                        status = "time_or_memory_budget_stop"
                        break
                    time.sleep(.25)
                if status == "running":
                    status = "completed" if worker.returncode == 0 else "worker_error"
        except Exception:
            status = "parent_harness_error"
            raise
        finally:
            if worker is not None and worker.poll() is None:
                try:
                    os.killpg(worker.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                worker.wait()
            write(out / "execution.json", {"status": status, "seconds": time.monotonic()-begin,
                "exit_code": worker.returncode if worker else None, "samples": samples,
                "peak_sampled_tree_rss_bytes": max((s["rss"] for s in samples), default=0), "API_calls": 0, "retries": 0})
            print(arm, status, flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["--prepare"]:
        prepare()
    elif args == ["--check"]:
        verify()
        print("Frozen sources, runtime, models, options, evaluator and code verified.")
    elif len(args) == 2 and args[0] in ("--live", "--child") and args[1] in ("A", "B"):
        (parent if args[0] == "--live" else child)(args[1])
    else:
        raise SystemExit("use --prepare, --check, --live A/B or --child A/B")
