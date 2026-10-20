"""One bounded native CPU conversion; feasibility only, never a quality pass."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from unittest.mock import patch
import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "cpu-probe"
REG = json.loads((HERE / "cpu-probe-registration.json").read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n")


def child():
    import torch
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
    from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline
    from docling.models.inference_engines.vlm.transformers_engine import TransformersVlmEngine
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    weights = json.loads((HERE / "weights.json").read_text())
    assert weights["complete"] and weights["revision"] == REG["revision"]
    contract = json.loads((HERE.parent / "pdf-core-g2-official-method-2026-10-15/review/contract.json").read_text())
    source = next(x for x in contract["scope"]["page_manifest"] if x["source"] == "controls")
    pdf = REPO / source["source_pdf_ref"]["path"]
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == source["source_pdf_ref"]["sha256"]
    vlm = VlmConvertOptions.from_preset("dots_ocr", engine_options=TransformersVlmEngineOptions(
        device="cpu",torch_dtype="bfloat16",trust_remote_code=True,compile_model=False,quantized=False))
    vlm.model_spec.revision = REG["revision"]
    options = VlmPipelineOptions(vlm_options=vlm, artifacts_path=Path(weights["model_path"]).parent,
        accelerator_options=AcceleratorOptions(device="cpu",num_threads=4),
        generate_page_images=True,images_scale=2)
    save("options.json", options.model_dump(mode="json"))
    original_init = TransformersVlmEngine.initialize
    original_predict = TransformersVlmEngine.predict_batch
    def observed_init(engine):
        begin = time.monotonic()
        save("stage.json", {"stage":"loading_weights"})
        original_init(engine)
        model = engine.vlm_model
        devices = sorted({str(p.device) for p in model.parameters()})
        assert devices == ["cpu"]
        save("loaded.json", {"seconds":time.monotonic()-begin,"devices":devices,
            "dtypes":sorted({str(p.dtype) for p in model.parameters()}),
            "parameters":sum(p.numel() for p in model.parameters()),
            "vision_attention":model.config.vision_config.attn_implementation})
    def observed_predict(engine, inputs):
        save("stage.json", {"stage":"model_inference", "images":[x.image.size for x in inputs]})
        for i, value in enumerate(inputs):
            value.image.save(OUT / f"input-{i}.png")
        begin = time.monotonic()
        outputs = original_predict(engine, inputs)
        save("raw-outputs.json", {"seconds":time.monotonic()-begin,
            "outputs":[x.model_dump(mode="json") for x in outputs]})
        return outputs
    with patch.object(TransformersVlmEngine,"initialize",observed_init), patch.object(TransformersVlmEngine,"predict_batch",observed_predict):
        converter = DocumentConverter(format_options={InputFormat.PDF:PdfFormatOption(
            pipeline_cls=VlmPipeline,pipeline_options=options)})
        result = converter.convert(pdf,page_range=(1,1),raises_on_error=False)
    if result.document is not None:
        result.document.save_as_json(OUT / "document.json")
        (OUT / "document.md").write_text(result.document.export_to_markdown(escape_underscores=False,escape_html=False))
    save("conversion.json", {"status":result.status.value,"errors":[x.model_dump(mode="json") for x in result.errors],
        "source":source["source_pdf_ref"],"physical_page":1,"quality_review":False,"candidate_eligible":False})
    print("Native conversion finished",result.status.value,flush=True)


def main():
    OUT.mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HOME="/private/tmp/pdf-core-g2-dots-20261016/hf",HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",TOKENIZERS_PARALLELISM="false",DOCLING_DEVICE="cpu",OMP_NUM_THREADS="4")
    proc = None
    samples = []
    status = "not_started"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock","a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        start = time.monotonic()
        available = psutil.virtual_memory().available
        try:
            if available < REG["min_prelaunch_available_bytes"]:
                status = "insufficient_available_memory_before_launch"
                return
            with (OUT / "worker.log").open("w") as log:
                proc = subprocess.Popen(["rtk","proxy",sys.executable,str(Path(__file__).resolve()),"--child"],
                    env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                status = "running"
                while proc.poll() is None:
                    try:
                        root = psutil.Process(proc.pid)
                        rss = sum(x.memory_info().rss for x in [root]+root.children(recursive=True) if x.is_running())
                    except psutil.NoSuchProcess:
                        rss = 0
                    elapsed = time.monotonic()-start
                    samples.append({"seconds":elapsed,"rss_bytes":rss})
                    if elapsed > REG["max_worker_seconds"] or rss > REG["max_sampled_tree_rss_bytes"]:
                        status = "timeout" if elapsed > REG["max_worker_seconds"] else "memory_limit"
                        break
                    time.sleep(0.05)
                if status == "running":
                    status = "completed" if proc.returncode == 0 else "worker_error"
        except BaseException:
            status = "runner_or_monitor_error"
            raise
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            save("execution.json",{"status":status,"seconds":time.monotonic()-start,
                "prelaunch_available_bytes":available,"sampled_peak_rss_bytes":max((s["rss_bytes"] for s in samples),default=0),
                "exit_code":proc.returncode if proc else None,"samples":samples,
                "runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "all_owned_children_reaped":proc is None or proc.poll() is not None,
                "quality_pass":False,"holdout_reads":0,"automatic_retries":0})
            print(status,flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        child()
    else:
        assert not sys.argv[1:]
        main()
