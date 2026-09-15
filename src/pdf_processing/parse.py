"""Fresh-process Docling extraction; checkpoint format remains prototype-internal.

Derived from the pinned experiment. No source, store or method is selected at import.
Fresh execution installs guards once. The private warm protocol rebinds request-local
state around one sequential capture converter; assembly always runs fresh.
"""
import collections
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import resource
import sys
import threading
import time

from dataclasses import dataclass
from .execution import ChildFailure
from .compatibility import methods_match, dependencies

@dataclass(frozen=True)
class ParseRequest:
    mode: str
    pdf: Path
    out: Path
    model_cache: Path
    checkpoint: Path | None = None
    scan: bool = False
    start: int = 1
    end: int = 9223372036854775807
    checkpoint_only: bool = False
    expected_method: dict | None = None
    checkpoint_compatibility: dict | None = None

    @classmethod
    def from_json(cls, value):
        value = dict(value)
        for key in ('pdf', 'out', 'model_cache', 'checkpoint'):
            if value.get(key) is not None: value[key] = Path(value[key])
        return cls(**value)


def execute(request: ParseRequest, receive=None, notify=lambda kind, **data: None):
    if receive is not None and (request.mode != 'capture' or not request.checkpoint_only or request.scan):
        raise ChildFailure('method', 'unsupported_warm_profile')
    if request.mode not in ('baseline', 'capture', 'restore', 'warmup'):
        raise ValueError('Unsupported execution mode')
    if request.out.exists() and any(request.out.iterdir()):
        raise ValueError('Output directory must be fresh')
    if request.mode == 'restore' and request.checkpoint is None:
        raise ValueError('Restore requires checkpoint')
    from .continuation import METHOD, ContinuationPredictor
    actual_continuation = None
    continuation = (request.expected_method or {}).get('continuation')
    if continuation is not None:
        actual_continuation = {
            'version': METHOD,
            'sha256': hashlib.sha256(Path(__file__).with_name('continuation.py').read_bytes()).hexdigest(),
        }
        if continuation != actual_continuation:
            raise ChildFailure('method', 'unsupported_continuation_method')

    os.environ['HF_HOME'] = str(request.model_cache)
    os.environ.setdefault('OMP_NUM_THREADS', '4')
    started = time.perf_counter()
    events = []
    lock = threading.Lock()
    from PIL import Image
    from docling.datamodel import base_models as bm
    from docling.datamodel.document import ConversionResult
    from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions, RapidOcrOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    from docling.models.stages.reading_order.readingorder_model import ReadingOrderModel, ReadingOrderOptions
    from docling_core.types.doc.base import Size
    
    TYPES = {c.__name__: c for c in (bm.TextElement, bm.Table, bm.FigureElement, bm.ContainerElement)}
    def sha(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    
    
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(data, indent=2, sort_keys=True, allow_nan=False).encode()
        tmp = path.with_suffix(path.suffix + ".incomplete")
        with tmp.open("wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    
    
    def event(stage, pages, elapsed, **extra):
        value = dict(pid=os.getpid(), stage=stage, pages=pages, seconds=elapsed, **extra)
        with lock:
            events.append(value)
            with (request.out / "events.jsonl").open("a") as f:
                f.write(json.dumps(value) + "\n")
                f.flush()
        if stage != "model_initialization":
            notify("progress", stage=stage, pages=pages)
        print(json.dumps(value), flush=True)
    
    
    def instrument(forbid=False):
        # Class-level wrappers count stage input pages/batches and fail closed on replay.
        from docling.models.stages.page_preprocessing.page_preprocessing_model import PagePreprocessingModel
        from docling.models.stages.layout.layout_model import LayoutModel
        from docling.models.stages.table_structure.table_structure_model import TableStructureModel
        from docling.models.stages.ocr.rapid_ocr_model import RapidOcrModel
        from docling.models.stages.page_assemble.page_assemble_model import PageAssembleModel
        if request.mode == "baseline":
            assemble = StandardPdfPipeline._assemble_document
            def timed_assembly(self, conv_res):
                t = time.perf_counter()
                result = assemble(self, conv_res)
                event("document_assembly", [], time.perf_counter() - t)
                return result
            StandardPdfPipeline._assemble_document = timed_assembly
        for cls in (PagePreprocessingModel, LayoutModel, TableStructureModel, RapidOcrModel, PageAssembleModel):
            original = cls.__call__
            def wrapped(self, conv_res, page_batch, _original=original, _name=cls.__name__):
                pages = list(page_batch)
                if forbid:
                    raise AssertionError(f"Repeated page stage: {_name}")
                t = time.perf_counter()
                event("stage_enter", [p.page_no for p in pages], 0, native_stage=_name)
                try:
                    yield from _original(self, conv_res, iter(pages))
                finally:
                    event(_name, [p.page_no for p in pages], time.perf_counter() - t)
            cls.__call__ = wrapped
    
    
    def options(scan=False):
        return ThreadedPdfPipelineOptions(
            do_ocr=scan,
            ocr_options=RapidOcrOptions(backend="onnxruntime", force_full_page_ocr=scan),
            do_table_structure=True,
            generate_page_images=True, generate_picture_images=True,
            images_scale=1.0,
            accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=4),
        )
    
    
    def confidence_json(value, restore=False):
        if isinstance(value, dict):
            return {k: confidence_json(v, restore) for k, v in value.items()}
        if restore and value is None:
            return float("nan")
        return None if isinstance(value, float) and math.isnan(value) else value
    
    
    def pack_assembled(unit):
        # Explicit tags prevent Pydantic's overlapping union from turning figures into text.
        return {key: [{"type": type(e).__name__, "value": e.model_dump(mode="json")}
                      for e in getattr(unit, key)] for key in ("elements", "headers", "body")}
    
    
    def unpack_assembled(data):
        return bm.AssembledUnit(**{k: [TYPES[e["type"]].model_validate(e["value"]) for e in v]
                                  for k, v in data.items()})
    
    
    class SelectedPipeline(StandardPdfPipeline):
        def _init_models(self):
            super()._init_models()
            if continuation is not None:
                self.reading_order_model.ro_model = ContinuationPredictor()

    class CapturePipeline(SelectedPipeline):
        def _release_page_resources(self, item):
            page = item.payload
            if page is not None and page.assembled is not None:
                t = time.perf_counter()
                image_path = request.out / "checkpoints" / f"page-{page.page_no:04}.png"
                image_path.parent.mkdir(parents=True, exist_ok=True)
                assert page.image is not None and page.size is not None
                page.image.save(image_path)
                with image_path.open("rb") as f:
                    os.fsync(f.fileno())
                data = {
                    "format": "PROTOTYPE-page-v1", "source_sha256": sha(request.pdf),
                    "method_sha256": sha(request.out / "method.json"),
                    "page_no": page.page_no, "size": page.size.model_dump(mode="json"),
                    "coordinate_contract": "Docling bboxes retain coord_origin; page units are PDF points",
                    "assembled": pack_assembled(page.assembled),
                    "visual": {"file": image_path.name, "sha256": sha(image_path), "scale": 1.0},
                }
                write(image_path.with_suffix(".json"), data)
                event("checkpoint_commit", [page.page_no], time.perf_counter() - t)
            super()._release_page_resources(item)
    
        def _assemble_document(self, conv_res):
            assert conv_res.status == bm.ConversionStatus.SUCCESS, conv_res.errors
            checkpoints = sorted((request.out / "checkpoints").glob("page-*.json"))
            assert len(checkpoints) == len(conv_res.pages)
            write(request.out / "complete.json", {
                "format": "PROTOTYPE-document-v1", "source_sha256": sha(request.pdf),
                "method_sha256": sha(request.out / "method.json"),
                "pages": [{"file": p.name, "sha256": sha(p)} for p in checkpoints],
                "confidence": confidence_json(conv_res.confidence.model_dump(mode="json")),
                "errors": [e.model_dump(mode="json") for e in conv_res.errors],
                "status": conv_res.status.value,
            })
            if request.checkpoint_only:
                return conv_res
            t = time.perf_counter()
            result = super()._assemble_document(conv_res)
            event("document_assembly", [], time.perf_counter() - t)
            return result
    
    
    class RestorePipeline(StandardPdfPipeline):
        def _init_models(self):
            # Only assembly is constructed; no page inference models or OCR engines exist.
            self.reading_order_model = ReadingOrderModel(options=ReadingOrderOptions())
            if continuation is not None:
                self.reading_order_model.ro_model = ContinuationPredictor()
            self.keep_images = True
            self.keep_backend = False
    
        def _build_document(self, conv_res):
            t = time.perf_counter()
            saved = request.checkpoint
            assert saved is not None
            manifest = json.loads((saved / "complete.json").read_text())
            assert manifest["format"] == "PROTOTYPE-document-v1"
            assert manifest["source_sha256"] == sha(request.pdf)
            assert manifest["method_sha256"] == sha(saved / "method.json")
            saved_method = json.loads((saved / "method.json").read_text())
            compatible = methods_match(saved_method, method())
            if request.checkpoint_compatibility is not None:
                compatible = (json.loads((saved / "compatibility.json").read_text()) == request.checkpoint_compatibility
                              and methods_match(saved_method, method(), True))
            if not compatible:
                raise ChildFailure("method", "worker_method_mismatch")
            pages = []
            for entry in manifest["pages"]:
                path = saved / "checkpoints" / entry["file"]
                assert sha(path) == entry["sha256"]
                data = json.loads(path.read_text())
                assert data["format"] == "PROTOTYPE-page-v1"
                assert data["source_sha256"] == manifest["source_sha256"]
                assert data["method_sha256"] == manifest["method_sha256"]
                picture = path.parent / data["visual"]["file"]
                assert sha(picture) == data["visual"]["sha256"]
                page = bm.Page(page_no=data["page_no"], size=Size.model_validate(data["size"]),
                               assembled=unpack_assembled(data["assembled"]))
                assert pack_assembled(page.assembled) == data["assembled"]
                page._image_cache = {1.0: Image.open(picture).copy()}
                page._default_image_scale = 1.0
                pages.append(page)
            assert [p.page_no for p in pages] == self._get_expected_page_nos(conv_res)
            conv_res.pages = pages
            conv_res.confidence = type(conv_res.confidence).model_validate(confidence_json(manifest["confidence"], restore=True))
            conv_res.errors = [bm.ErrorItem.model_validate(e) for e in manifest["errors"]]
            conv_res.status = bm.ConversionStatus(manifest["status"])
            self._page_sizes_by_no = {p.page_no: p.size for p in pages}
            event("checkpoint_load", [p.page_no for p in pages], time.perf_counter() - t)
            return conv_res
    
        def _assemble_document(self, conv_res):
            t = time.perf_counter()
            result = super()._assemble_document(conv_res)
            event("document_assembly", [], time.perf_counter() - t)
            return result
    
    
    def method():
        packages = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
        models = {str(p.relative_to(request.model_cache)): sha(p) for p in sorted((request.model_cache).glob("hub/models--*/snapshots/**/*")) if p.is_file()}
        import rapidocr
        models.update({"rapidocr/" + p.name: sha(p) for p in (Path(rapidocr.__file__).parent / "models").glob("*.onnx")})
        return {**({"continuation": actual_continuation} if continuation is not None else {}),
                "format": "PROTOTYPE-page-v1", "python": platform.python_version(),
                "platform": platform.platform(), "packages": packages, "model_artifacts": models,
                "options": options(request.scan).model_dump(mode="json", serialize_as_any=True),
                "option_types": {k: type(getattr(options(request.scan), k)).__name__ for k in ("ocr_options", "layout_options", "table_structure_options")},
                "backend": "PdfFormatOption default pinned by packages"}
    
    request.out.mkdir(parents=True, exist_ok=True)
    instrument(request.mode == "restore")
    pipeline = {"baseline": SelectedPipeline, "warmup": SelectedPipeline,
                "capture": CapturePipeline, "restore": RestorePipeline}[request.mode]
    converter = DocumentConverter(format_options={bm.InputFormat.PDF: PdfFormatOption(
        pipeline_cls=pipeline, pipeline_options=options(request.scan))})
    t = time.perf_counter()
    converter.initialize_pipeline(bm.InputFormat.PDF)
    event("model_initialization", [], time.perf_counter() - t)
    current_method = method()
    producer = {p.name: sha(p) for p in Path(__file__).parent.glob('*.py')}
    actual_checkpoint = dependencies('group', {'method': current_method}, producer)
    original_scan, original_cache = request.scan, request.model_cache
    while True:
        if receive is not None:
            if request.mode != 'capture' or not request.checkpoint_only or request.scan or request.scan != original_scan or request.model_cache != original_cache:
                raise ChildFailure('method', 'unsupported_warm_profile')
        request.out.mkdir(parents=True, exist_ok=True)
        if request.expected_method is not None:
            if not methods_match(current_method, request.expected_method, request.checkpoint_compatibility is not None):
                raise ChildFailure("method", "worker_method_mismatch")
        if request.checkpoint_compatibility is not None and request.checkpoint_compatibility != actual_checkpoint:
            raise ChildFailure("method", "checkpoint_producer_mismatch")
        notify("ready", method=current_method)
        write(request.out / "method.json", current_method)
        if request.checkpoint_compatibility is not None:
            write(request.out / "compatibility.json", request.checkpoint_compatibility)
        if request.mode == "warmup":
            return
        t = time.perf_counter()
        result = converter.convert(request.pdf, page_range=(request.start, request.end))
        elapsed = time.perf_counter() - t
        assert result.status == bm.ConversionStatus.SUCCESS, result.errors
        result.document.save_as_json(request.out / "document.json")
        (request.out / "document.md").write_text(result.document.export_to_markdown())
        counts = collections.Counter()
        seconds = collections.Counter()
        for e in events:
            counts[e["stage"]] += len(e["pages"])
            seconds[e["stage"]] += e["seconds"]
        report = {"pid": os.getpid(), "mode": request.mode, "wall_seconds": time.perf_counter()-started,
                  "convert_seconds": elapsed, "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "rss_units": "bytes" if sys.platform == "darwin" else "KiB", "page_stage_inputs": dict(counts),
                  "stage_seconds_sum_not_wall": dict(seconds), "source_sha256": sha(request.pdf),
                  "document_sha256": sha(request.out / "document.json"),
                  "labels": dict(collections.Counter(str(getattr(item, "label")) for item, _ in result.document.iterate_items() if hasattr(item, "label"))),
                  "errors": [e.model_dump(mode="json") for e in result.errors]}
        write(request.out / "metrics.json", report)
        print(json.dumps(report, indent=2))
        notify('done', memory={'peak_rss': report['peak_rss_bytes'], 'units': report['rss_units']})
        if receive is None:
            return
        request = receive()
        if request is None:
            return
        if request.out.exists() and any(request.out.iterdir()):
            raise ChildFailure('integrity', 'output_directory_not_fresh')
        events.clear()
        started = time.perf_counter()


if __name__ == "__main__":
    request = ParseRequest.from_json(json.load(sys.stdin))
    try:
        execute(request)
    except Exception as error:
        if isinstance(error, ChildFailure):
            category, code = error.category, error.code
        elif isinstance(error, AssertionError) and request.mode == 'restore':
            category, code = 'integrity', 'checkpoint_validation_failed'
        else:
            category, code = 'parser', 'parser_execution_failed'
        request.out.mkdir(parents=True, exist_ok=True)
        (request.out/'failure.json').write_text(json.dumps({'version': 1, 'category': category, 'code': code}))
        raise SystemExit(1)
