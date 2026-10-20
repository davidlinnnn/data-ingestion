"""One unchanged S0 conversion with temporary, pass-through boundary observers."""
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
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD = HERE.parent / "pdf-core-native-round-2026-10-17"
GUARD = HERE.parent / "pdf-core-eval-interfaces-2026-10-18/C"
SDK = Path(sys.prefix) / "lib/python3.12/site-packages/docling"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def options():
    return load("retained_s0_options", OLD / "run.py").options("S0")


def normalized(value):
    value = json.loads(json.dumps(value))
    value["chart_extraction_options"]["model_spec"]["supported_engines"].sort()
    return value


def verify():
    r = json.loads((HERE / "registration.json").read_text())
    for path, expected in r["hashes"].items():
        assert sha(path) == expected, f"frozen input changed: {path}"
    assert normalized(options().model_dump(mode="json", serialize_as_any=True)) == r["effective_options"]
    for item in r["runtime"]:
        assert importlib.metadata.version(item["name"]) == item["version"], item["name"]
    return r


def prepare():
    source = next(j for j in json.loads((OLD / "inputs.json").read_text())["jobs"] if j["id"] == "scan")
    assert source["first"] == source["last"] == 1
    assert sha(REPO / source["source"]["path"]) == source["source"]["sha256"]
    original = json.loads((OLD / "S0/effective-options.json").read_text())
    assert normalized(options().model_dump(mode="json", serialize_as_any=True)) == normalized(original)
    hashes = dict(json.loads((GUARD / "native-preregistration.json").read_text())["active_asset_hashes"])
    for path, expected in hashes.items():
        assert sha(path) == expected, f"original frozen asset changed: {path}"
    paths = [REPO / source["source"]["path"], OLD / "run.py", OLD / "S0/effective-options.json",
             OLD / "S0/scan/result.json", OLD / "S1/scan/result.json", Path(__file__), HERE / "check.py",
             HERE / "test_capture.py", GUARD / "cpu_baseline_v2.py", GUARD / "cpu_baseline.py"]
    paths += [SDK / p for p in ("models/base_ocr_model.py", "models/stages/ocr/rapid_ocr_model.py",
              "models/stages/layout/layout_object_detection_model.py",
              "models/stages/layout/layout_postprocessing_model.py",
              "models/stages/page_assemble/page_assemble_model.py")]
    for p in paths:
        key, digest = str(p.resolve()), sha(p)
        assert key not in hashes or hashes[key] == digest, f"frozen identity conflict: {key}"
        hashes[key] = digest
    r = {"date": "2026-10-19 Asia/Taipei", "source": source,
         "effective_options": normalized(original), "hashes": hashes,
         "runtime": json.loads((OLD / "standard-runtime-v2.json").read_text()),
         "whole_worker_seconds": 180, "max_tree_rss_bytes": 12*2**30,
         "min_available_bytes": 8*2**30, "prelaunch_available_bytes": 10*2**30,
         "conversions": 1, "pages": 1, "retries": 0, "API_calls": 0,
         "method": "unchanged S0; temporary pass-through observers; no output repair",
         "hypotheses": ["raw layout already spans columns", "rect dilation/connectivity merges columns",
                        "OCR returns mixed lines within its actual crop", "later cell/cluster processing joins separate raw lines"]}
    write(HERE / "registration.json", r)
    verify()
    print("Registered one unchanged S0 page, 180 seconds total worker, zero retries/API.")


class Trace:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=False)
        self.counts = {}
        self.originals = []

    def record(self, name, value):
        self.counts[name] = self.counts.get(name, 0) + 1
        stem = f"{name}-{self.counts[name]:03}"
        write(self.directory / f"{stem}.json", value)
        return stem

    def patch(self, cls, name, wrapper):
        owned = name in cls.__dict__
        original = getattr(cls, name)
        self.originals.append((cls, name, original, owned))
        setattr(cls, name, wrapper(original))

    def restore(self):
        for cls, name, original, owned in reversed(self.originals):
            if owned:
                setattr(cls, name, original)
            else:
                delattr(cls, name)

    def reader(self, original):
        def observed(image, **kwargs):
            import numpy as np
            from PIL import Image
            index = self.counts.get("ocr-engine", 0) + 1
            stem = f"ocr-engine-{index:03}"
            np.save(self.directory / f"{stem}.npy", image, allow_pickle=False)
            Image.fromarray(image).save(self.directory / f"{stem}.png")
            before = hashlib.sha256(image.tobytes()).hexdigest()
            result = original(image, **kwargs)
            self.record("ocr-engine", {"input_shape": list(image.shape), "input_dtype": str(image.dtype),
                "input_pixel_sha256": before, "kwargs": kwargs,
                "boxes": None if result is None or result.boxes is None else result.boxes.tolist(),
                "texts": None if result is None or result.txts is None else list(result.txts),
                "scores": None if result is None or result.scores is None else [float(v) for v in result.scores]})
            return result
        return observed

    def install(self):
        from docling.models.base_ocr_model import BaseOcrModel
        from docling.models.stages.layout.layout_object_detection_model import LayoutObjectDetectionModel
        from docling.models.stages.layout.layout_postprocessing_model import LayoutPostprocessingModel
        from docling.models.stages.page_assemble.page_assemble_model import PageAssembleModel

        def layout(original):
            def observed(model, page, image, engine_output):
                image.save(self.directory / "layout-input.png")
                self.record("layout-engine", {"page_no": page.page_no, "image_size": list(image.size),
                    "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                    "output": engine_output.model_dump(mode="json")})
                result = original(model, page, image, engine_output)
                self.record("layout-clusters", {"page_no": page.page_no,
                    "page_size": page.size.model_dump(mode="json"),
                    "clusters": [c.model_dump(mode="json") for c in result]})
                return result
            return observed

        def dedup(original):
            def observed(model, size, rects, dilation_size=0):
                rects = list(rects)
                before = [b.model_dump(mode="json") for b in rects]
                result = original(model, size, rects, dilation_size=dilation_size)
                self.record("ocr-dedup", {"page_size": size.model_dump(mode="json"),
                    "dilation_size": dilation_size, "candidates": before, "coverage": result[0],
                    "rects": [b.model_dump(mode="json") for b in result[1]]})
                return result
            return observed

        def rects(original):
            def observed(model, page):
                result = original(model, page)
                self.record("ocr-rects", {"page_no": page.page_no, "scale": model.scale,
                    "rects": [b.model_dump(mode="json") for b in result],
                    "reader_mapping": "sequential nonzero-area rectangles in this exact list"})
                return result
            return observed

        def cells(original):
            def observed(model, ocr_cells, page, conv_res, priority=None):
                self.record("ocr-cells-before-merge", [c.model_dump(mode="json") for c in ocr_cells])
                result = original(model, ocr_cells, page, conv_res, priority=priority)
                self.record("ocr-cells-after-merge", [c.model_dump(mode="json") for c in page.cells])
                return result
            return observed

        def postlayout(original):
            def observed(model, conv_res, pages):
                pages = list(pages)
                self.record("layout-before-postprocess", [p.predictions.layout.model_dump(mode="json") for p in pages])
                result = original(model, conv_res, pages)
                self.record("layout-after-postprocess", [p.model_dump(mode="json") for p in result])
                return result
            return observed

        def assembly(original):
            def observed(model, lines):
                before = list(lines)
                result = original(model, lines)
                self.record("assembly-lines", {"before": before, "after": result})
                return result
            return observed

        self.patch(LayoutObjectDetectionModel, "_predictions_to_clusters", layout)
        self.patch(BaseOcrModel, "_deduplicate_rects", dedup)
        self.patch(BaseOcrModel, "get_ocr_rects", rects)
        self.patch(BaseOcrModel, "post_process_cells", cells)
        self.patch(LayoutPostprocessingModel, "postprocess_layout", postlayout)
        self.patch(PageAssembleModel, "sanitize_text", assembly)


def child():
    r = verify()
    import torch
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=StandardPdfPipeline, pipeline_options=options(), backend=PyPdfiumDocumentBackend)})
    begin = time.monotonic()
    converter.initialize_pipeline(InputFormat.PDF)
    write(HERE / "live/initialization.json", {"seconds": time.monotonic()-begin})
    pipeline = next(iter(converter.initialized_pipelines.values()))
    trace = Trace(HERE / "live/trace")
    reader = pipeline.ocr_model.reader
    try:
        trace.install()
        pipeline.ocr_model.reader = trace.reader(reader)
        begin = time.monotonic()
        result = converter.convert(REPO / r["source"]["source"]["path"], page_range=(1, 1), raises_on_error=False)
        (HERE / "live/result.json").write_text(result.model_dump_json(indent=2, serialize_as_any=True))
        result.document.save_as_json(HERE / "live/document.json")
        (HERE / "live/document.md").write_text(result.document.export_to_markdown())
        result.pages[0].get_image(scale=2).save(HERE / "live/page.png")
        write(HERE / "live/conversion.json", {"status": result.status.value,
              "seconds": time.monotonic()-begin, "trace_counts": trace.counts})
        assert result.status.value == "success", "partial conversion; no retry"
    finally:
        pipeline.ocr_model.reader = reader
        trace.restore()
    verify()


def parent():
    import psutil
    sys.path.insert(0, str(GUARD))
    from cpu_baseline_v2 import tree_rss
    r = verify()
    out = HERE / "live"
    env = os.environ.copy()
    env.pop("OPENAI_API_KEY", None)
    env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf", HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    begin, samples, worker, status = time.monotonic(), [], None, "not_started"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out.mkdir(exist_ok=False)
        try:
            if psutil.virtual_memory().available < r["prelaunch_available_bytes"]:
                status = "insufficient_prelaunch_memory"
                return
            with (out / "worker.log").open("x") as log:
                worker = subprocess.Popen(["rtk", "proxy", sys.executable, "-B", str(Path(__file__).resolve()), "--child"],
                    stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                status = "running"
                while worker.poll() is None:
                    rss, available = tree_rss(worker.pid), psutil.virtual_memory().available
                    samples.append({"seconds": time.monotonic()-begin, "rss": rss, "available": available})
                    if time.monotonic()-begin >= r["whole_worker_seconds"] or rss >= r["max_tree_rss_bytes"] or available < r["min_available_bytes"]:
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
                "peak_sampled_tree_rss": max((s["rss"] for s in samples), default=0),
                "API_calls": 0, "retries": 0})
            print(status, flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--prepare"]:
        prepare()
    elif sys.argv[1:] == ["--check"]:
        verify()
        print("Frozen inputs, runtime and unchanged S0 options verified.")
    elif sys.argv[1:] == ["--live"]:
        parent()
    elif sys.argv[1:] == ["--child"]:
        child()
    else:
        raise SystemExit("use --prepare, --check, --live or --child")
