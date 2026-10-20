"""Two bounded CPU descriptions using the installed official small-model stage."""
import importlib.util
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("g2_supervisor", REPO / "docs/research/pdf-core-g2-round3-2026-10-14/vlm/probe.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def child():
    import torch
    from PIL import Image
    from docling.datamodel.accelerator_options import AcceleratorOptions
    from docling.datamodel.pipeline_options import PictureDescriptionVlmEngineOptions
    from docling.datamodel.vlm_engine_options import TransformersVlmEngineOptions
    from docling.models.stages.picture_description.picture_description_vlm_engine_model import PictureDescriptionVlmEngineModel

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    download = json.loads((HERE / "download.json").read_text())
    artifacts = HERE / "artifacts"
    artifacts.mkdir(exist_ok=True)
    link = artifacts / "HuggingFaceTB--SmolVLM-256M-Instruct"
    if not link.exists():
        link.symlink_to(download["snapshot_path"], target_is_directory=True)
    assert link.resolve() == Path(download["snapshot_path"]).resolve()
    options = PictureDescriptionVlmEngineOptions.from_preset("smolvlm", engine_options=
        TransformersVlmEngineOptions(device="cpu", torch_dtype="float32", compile_model=False,
                                     quantized=False, trust_remote_code=False))
    options.model_spec.revision = download["revision"]
    tick = time.monotonic()
    stage = PictureDescriptionVlmEngineModel(enabled=True, enable_remote_services=False, artifacts_path=artifacts,
        options=options, accelerator_options=AcceleratorOptions(device="cpu", num_threads=4))
    load_seconds = time.monotonic() - tick
    model = stage.engine.vlm_model
    devices = sorted({str(p.device) for p in model.parameters()})
    dtypes = sorted({str(p.dtype) for p in model.parameters()})
    assert devices == ["cpu"] and dtypes == ["torch.float32"]
    base.save(HERE / "run/method.json", {"model": download["repo"], "revision": download["revision"],
        "options": options.model_dump(mode="json", serialize_as_any=True), "devices": devices, "dtypes": dtypes,
        "threads": 4, "interop_threads": 1, "batch": 1, "stage_load_seconds": load_seconds,
        "scope": "Official _annotate_images on fixed source crops; source selection/size gate and Canonical backfill not executed",
        "max_new_tokens": 200, "source_runner_sha256": base.sha(Path(__file__)),
        "supervisor_sha256": base.sha(REPO / "docs/research/pdf-core-g2-round3-2026-10-14/vlm/probe.py")})
    original_generate, original_predict = model.generate, stage.engine.predict_batch
    current = None

    def observed_generate(**kwargs):
        raw = original_generate(**kwargs)
        prefix = kwargs["input_ids"].shape[1]
        tokens = raw[0, prefix:].tolist()
        eos = kwargs["generation_config"].eos_token_id
        base.save(current / "generation.json", {"input_tokens": prefix, "generated_tokens": len(tokens),
            "generated_ids": tokens, "eos_token_ids": eos, "last_token_is_eos": tokens[-1] in (eos if isinstance(eos,list) else [eos]),
            "at_token_limit": len(tokens) >= kwargs["max_new_tokens"], "max_new_tokens": kwargs["max_new_tokens"]})
        decoded = stage.engine.processor.batch_decode(raw[:, prefix:], skip_special_tokens=False)[0]
        (current / "decoded-before-engine-cleanup.txt").write_text(decoded)
        return raw

    def observed_predict(inputs):
        outputs = original_predict(inputs)
        base.save(current / "engine-output.json", [x.model_dump(mode="json") for x in outputs])
        return outputs

    model.generate, stage.engine.predict_batch = observed_generate, observed_predict
    inventory = json.loads((HERE.parent / "inputs/model-inputs.json").read_text())["inputs"]
    for item in inventory[:2]:
        current = HERE / "run" / item["input_id"].lower()
        current.mkdir(exist_ok=False)
        source = Path(item["image_path"])
        assert base.sha(source) == item["sha256"]
        (current / "input.png").write_bytes(source.read_bytes())
        base.save(current / "input.json", {**item, "scope": "Same fixed oracle crop; no inferred full-page context"})
        tick = time.monotonic()
        output = list(stage._annotate_images([Image.open(source).convert("RGB")]))
        assert len(output) == 1 and output[0].strip(), "Empty/swallowed stage output is not successful required work"
        (current / "description.txt").write_text(output[0])
        base.save(current / "result.json", {"annotate_images_seconds": time.monotonic()-tick,
            "execution_status": "completed", "quality_status": "requires_source_review"})


if __name__ == "__main__":
    if sys.argv[1:] == ["--child", "run"]:
        child()
    else:
        assert sys.argv[1:] == []
        base.HERE, base.JOBS, base.__file__ = HERE, ["run"], str(Path(__file__).resolve())
        base.main()
