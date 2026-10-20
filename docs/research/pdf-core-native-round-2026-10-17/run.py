"""Bounded official-pipeline comparison; no output repairs or inference retries."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ART = Path("/private/tmp/pdf-core-native-20261017/artifacts")

def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n")
    tmp.replace(path)

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(8388608), b""):
            h.update(b)
    return h.hexdigest()

def options(profile):
    from docling.datamodel.pipeline_options import (VlmConvertOptions, VlmPipelineOptions,
        PdfPipelineOptions, LayoutObjectDetectionOptions, RapidOcrOptions)
    from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
    if profile == "C1":
        from docling.datamodel.vlm_engine_options import MlxVlmEngineOptions
        vlm = VlmConvertOptions.from_preset("nemotron_parse_v2", engine_options=MlxVlmEngineOptions())
        vlm.model_spec.revision = "e7e89479657fb3631028ac12b6bc0d5a59ceafe4"
        return VlmPipelineOptions(vlm_options=vlm, artifacts_path=ART,
            generate_page_images=True, images_scale=2)
    from docling.datamodel.object_detection_engine_options import TransformersObjectDetectionEngineOptions
    layout = LayoutObjectDetectionOptions.from_preset(
        "layout_heron_default" if profile == "S0" else "layout_egret_medium",
        engine_options=TransformersObjectDetectionEngineOptions(torch_dtype="float32", compile_model=False))
    layout.model_spec.revision = ("8f39ad3c0b4c58e9c2d2c84a38465abf757272d8" if profile == "S0"
        else "77ede7cc7bed96d853c58f319734803d6ea2ea5c")
    ocrdir = REPO / "docs/prototypes/pdf-checkpoint-prototype/.venv/lib/python3.12/site-packages/rapidocr/models"
    ocr = RapidOcrOptions(use_det=True, use_cls=True, use_rec=True,
        det_model_path=str(ocrdir / "PP-OCRv6_det_small.onnx"),
        rec_model_path=str(ocrdir / "PP-OCRv6_rec_small.onnx"),
        cls_model_path=str(ocrdir / "ch_ppocr_mobile_v2.0_cls_mobile.onnx"),
        rapidocr_params={"EngineConfig.onnxruntime.intra_op_num_threads": 4,
                         "EngineConfig.onnxruntime.inter_op_num_threads": 1})
    return PdfPipelineOptions(artifacts_path=ART, layout_options=layout, ocr_options=ocr,
        accelerator_options=AcceleratorOptions(num_threads=4, device=AcceleratorDevice.CPU),
        generate_page_images=True, generate_picture_images=True, generate_parsed_pages=True,
        images_scale=2, ocr_batch_size=1, layout_batch_size=1, table_batch_size=1)

def stage(out, name, seconds, job=None):
    save(out / "stage.json", dict(stage=name, job=job, started=time.monotonic(), limit=seconds))

def child(profile):
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.pipeline.vlm_pipeline import VlmPipeline
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
    out = HERE / profile
    if profile == "C1":
        import mlx.core as mx
        assert mx.metal.is_available()
        mx.set_default_device(mx.gpu)
        mx.set_memory_limit(18 * 2**30)
        mx.set_cache_limit(256 * 2**20)
    else:
        import torch
        torch.set_num_threads(4)
        torch.set_num_interop_threads(1)
    opts = options(profile)
    save(out / "effective-options.json", opts.model_dump(mode="json", serialize_as_any=True))
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(
        pipeline_cls=VlmPipeline if profile == "C1" else StandardPdfPipeline,
        pipeline_options=opts, backend=PyPdfiumDocumentBackend)})
    if profile == "C1":
        from docling.models.inference_engines.vlm.mlx_engine import MlxVlmEngine
        original_predict = MlxVlmEngine.predict_batch
        count = 0
        def observe_public_input(engine, inputs):
            nonlocal count
            for request in inputs:
                count += 1
                image = request.image.convert("RGB")
                image.save(out / f"actual-input-{count}.png")
                save(out / f"request-{count}.json", dict(image_size=image.size,
                    pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest(),
                    request=request.model_dump(mode="json",exclude={"image"})))
            return original_predict(engine, inputs)
        MlxVlmEngine.predict_batch = observe_public_input
    stage(out, "initialize", 300 if profile == "C1" else 180)
    begin = time.monotonic()
    converter.initialize_pipeline(InputFormat.PDF)
    save(out / "loaded.json", dict(seconds=time.monotonic()-begin))
    for job in json.loads((HERE / "inputs.json").read_text())["jobs"]:
        dst = out / job["id"]
        dst.mkdir(exist_ok=False)
        stage(out, "conversion", 180 * (job["last"]-job["first"]+1), job["id"])
        begin = time.monotonic()
        if profile == "C1":
            mx.reset_peak_memory()
        try:
            result = converter.convert(REPO / job["source"]["path"],
                page_range=(job["first"],job["last"]), raises_on_error=False)
            # Public result includes VLM raw, parsed cells and postprocessed predictions.
            (dst / "result.json").write_text(result.model_dump_json(indent=2, serialize_as_any=True))
            for page in result.pages:
                if page.predictions.vlm_response is not None:
                    save(dst / f"page-{page.page_no}-vlm.json", page.predictions.vlm_response.model_dump(mode="json"))
                image = page.get_image(scale=2)
                if image is not None:
                    image.save(dst / f"page-{page.page_no}.png")
            if result.document is not None:
                result.document.save_as_json(dst / "document.json")
                (dst / "document.md").write_text(result.document.export_to_markdown())
            record = dict(status=result.status.value, errors=[x.model_dump(mode="json") for x in result.errors])
        except Exception:
            record = dict(status="error", traceback=traceback.format_exc())
        record.update(seconds=time.monotonic()-begin, id=job["id"])
        if profile == "C1":
            record.update(metal_peak_bytes=mx.get_peak_memory(), metal_active_bytes=mx.get_active_memory())
        save(dst / "conversion.json", record)
        print(json.dumps(record), flush=True)
    stage(out, "complete", 10)

def reason(elapsed, stage_elapsed, stage_limit, rss, available, profile):
    if elapsed > (2700 if profile == "C1" else 4500): return "profile_time_limit"
    if stage_elapsed > stage_limit: return "stage_timeout"
    if rss > (20 if profile == "C1" else 12)*2**30: return "rss_limit"
    if available < 8*2**30: return "available_memory_limit"

def parent(profile):
    out = HERE / profile
    out.mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HOME="/private/tmp/pdf-core-native-20261017/hf", HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    proc = None
    samples = []
    status = "not_started"
    begin = time.monotonic()
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            available = psutil.virtual_memory().available
            # shortcut: available memory is a host estimate; sampled guard remains authoritative during inference.
            if available < (15 if profile == "C1" else 10)*2**30:
                status = "insufficient_prelaunch_memory"
                return
            with (out / "worker.log").open("w") as log:
                proc = subprocess.Popen(["rtk","proxy",sys.executable,str(Path(__file__).resolve()),"--child",profile],
                    stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
                status = "running"
                while proc.poll() is None:
                    try:
                        root=psutil.Process(proc.pid)
                        rss=sum(p.memory_info().rss for p in [root]+root.children(recursive=True) if p.is_running())
                    except psutil.NoSuchProcess:
                        rss=0
                    st=json.loads((out / "stage.json").read_text()) if (out / "stage.json").exists() else dict(started=begin,limit=300)
                    free=psutil.virtual_memory().available
                    samples.append(dict(seconds=time.monotonic()-begin,rss=rss,available=free,stage=st.get("stage"),job=st.get("job")))
                    if profile == "S1" and (HERE / "S0/execution.json").exists():
                        previous = json.loads((HERE / "S0/execution.json").read_text())["seconds"]
                    else:
                        previous = 0
                    stop=reason(time.monotonic()-begin+previous,time.monotonic()-st["started"],st["limit"],rss,free,profile)
                    if stop:
                        status=stop
                        break
                    time.sleep(.1)
                if status=="running": status="completed" if proc.returncode==0 else "worker_error"
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            save(out / "execution.json",dict(status=status,seconds=time.monotonic()-begin,
                prelaunch_available_bytes=available,exit_code=proc.returncode if proc else None,
                peak_sampled_tree_rss_bytes=max((s["rss"] for s in samples),default=0),samples=samples,
                runner_sha256=sha(__file__),automatic_retries=0,holdout_reads=0))
            print(profile,status,flush=True)

if __name__=="__main__":
    if sys.argv[1:]==["--selfcheck"]:
        assert reason(1,181,180,0,20*2**30,"S0")=="stage_timeout"
        assert reason(1,1,180,13*2**30,20*2**30,"S1")=="rss_limit"
        assert reason(1,1,180,0,7*2**30,"C1")=="available_memory_limit"
        assert reason(1,1,180,0,20*2**30,"C1") is None
        print("resource boundary self-check passed; no model loaded")
    elif sys.argv[1]=="--child": child(sys.argv[2])
    else: parent(sys.argv[1])
