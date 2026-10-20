"""Fixed native Docling/MLX experiment; observations never repair model output."""
import dataclasses
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time
from unittest.mock import patch

import psutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REG = json.loads((HERE / "registration.json").read_text())
OUT = HERE / "run"
MODEL = Path("/private/tmp/pdf-core-g2-dots-20261016/hf/hub/models--rednote-hilab--dots.ocr/snapshots") / REG["revision"]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def state(stage, page=None):
    save(OUT / "stage.json", {"stage": stage, "page": page, "started_monotonic": time.monotonic()})


def limit_reason(elapsed, rss, available):
    if elapsed > REG["max_seconds_per_page"]:
        return "timeout"
    if rss > REG["max_process_tree_rss_bytes"]:
        return "rss_limit"
    if available < REG["stop_if_available_memory_below_bytes"]:
        return "available_memory_limit"


@dataclasses.dataclass
class TensorShape:
    source: str
    shape: tuple
    permutation: tuple = ()

    def transpose(self, *axes):
        return TensorShape(self.source, tuple(self.shape[i] for i in axes), axes)


def source_shapes():
    result = {}
    for path in sorted(MODEL.glob("*.safetensors")):
        with path.open("rb") as stream:
            length = struct.unpack("<Q", stream.read(8))[0]
            header = json.loads(stream.read(length))
        for key, value in header.items():
            if key != "__metadata__":
                assert value["dtype"] == "BF16" and key not in result
                result[key] = TensorShape(key, tuple(value["shape"]))
    assert len(result) == 643 and sum(math.prod(v.shape) for v in result.values()) == 3039179264
    return result


def child():
    import importlib
    import mlx.core as mx
    import numpy as np
    import mlx_vlm
    dispatch = importlib.import_module("mlx_vlm.generate.dispatch")
    from mlx.utils import tree_flatten
    from PIL import Image
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
    from docling.datamodel.vlm_engine_options import MlxVlmEngineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.vlm_pipeline import VlmPipeline
    from docling.models.inference_engines.vlm.mlx_engine import MlxVlmEngine
    from mlx_vlm.generate.common import DEFAULT_TEMPERATURE
    assert mx.metal.is_available() and DEFAULT_TEMPERATURE == REG["temperature"] == 0
    mx.set_default_device(mx.gpu)
    mx.set_memory_limit(REG["mlx_memory_limit_bytes"])
    mx.set_cache_limit(REG["mlx_cache_limit_bytes"])
    pages = json.loads((HERE / "inputs.json").read_text())["pages"]
    for record in pages:
        assert hashlib.sha256((REPO / record["source_pdf"]["path"]).read_bytes()).hexdigest() == record["source_pdf"]["sha256"]
    weights = json.loads((HERE.parent / "pdf-core-g2-dots-2026-10-16/weights.json").read_text())
    for item in weights["files"]:
        digest = hashlib.sha256()
        with (MODEL / item["file"]).open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        assert digest.hexdigest() == item["sha256"]
    raw_shapes = source_shapes()
    active = {}
    original_load = mlx_vlm.load
    original_init = MlxVlmEngine.initialize
    original_predict = MlxVlmEngine.predict_batch
    original_prepare = dispatch.prepare_inputs

    def audited_load(*args, **kwargs):
        # Docling 2.132 omits these public loader kwargs; preserve the source processor.
        kwargs.update(trust_remote_code=True, use_fast=False)
        assert kwargs.get("strict", True)
        begin = time.monotonic()
        model, processor = original_load(*args, **kwargs)
        mapped = model.sanitize(raw_shapes)
        mapped = model.vision_tower.sanitize(mapped)
        mapped = model.language_model.sanitize(mapped)
        actual = dict(tree_flatten(model.parameters()))
        assert set(mapped) == set(actual)
        for key, tensor in actual.items():
            assert tuple(tensor.shape) == mapped[key].shape and tensor.dtype == mx.bfloat16, key
        save(OUT / "weight-mapping.json", {"strict_loading": True, "parameters": sum(v.size for v in actual.values()),
            "tensor_count": len(actual), "all_bfloat16": True, "key_and_shape_coverage": True,
            "full_tensor_value_checksums": False, "seconds": time.monotonic() - begin,
            "mappings": [{"target": key, **dataclasses.asdict(value)} for key, value in mapped.items()],
            "public_loader_kwargs": kwargs, "default_device": str(mx.default_device())})
        return model, processor

    def observed_init(engine):
        original_init(engine)
        original_stream = engine.stream_generate

        def observed_stream(*args, **kwargs):
            path = OUT / active["id"]
            begin = time.monotonic()
            count = 0
            with (path / "raw.txt").open("w") as stream:
                for token in original_stream(*args, **kwargs):
                    stream.write(token.text)
                    count += 1
                    if count == 1 or count % 64 == 0:
                        stream.flush()
                        save(path / "progress.json", {"stream_yields": count, "seconds": time.monotonic() - begin,
                            "generation_tokens": token.generation_tokens, "mlx_active_bytes": mx.get_active_memory(),
                            "mlx_peak_bytes": mx.get_peak_memory()})
                    if token.finish_reason is not None:
                        save(path / "generation.json", {"finish_reason": token.finish_reason,
                            "prompt_tokens": token.prompt_tokens, "generation_tokens": token.generation_tokens,
                            "prompt_tps": token.prompt_tps, "generation_tps": token.generation_tps,
                            "token_ids": token.token_ids, "seconds": time.monotonic() - begin,
                            "mlx_peak_bytes": mx.get_peak_memory(), "stream_kwargs": kwargs})
                    yield token
        engine.stream_generate = observed_stream
        save(OUT / "loaded.json", {"default_device": str(mx.default_device()), "metal_available": mx.metal.is_available(),
            "active_bytes": mx.get_active_memory(), "cache_bytes": mx.get_cache_memory()})

    def observed_prepare(*args, **kwargs):
        result = original_prepare(*args, **kwargs)
        arrays = {}
        for key, value in result.items():
            if isinstance(value, mx.array):
                value = np.asarray(value)
                canonical = value.astype(np.int64) if value.dtype.kind in "iu" else value
                arrays[key] = {"shape": list(value.shape), "dtype": str(value.dtype),
                    "canonical_sha256": hashlib.sha256(canonical.tobytes()).hexdigest()}
        save(OUT / active["id"] / "actual-processor.json", {"arrays": arrays,
            "grid": np.asarray(result["image_grid_thw"]).tolist()})
        return result

    def observed_predict(engine, inputs):
        assert len(inputs) == 1
        path = OUT / active["id"]
        image = inputs[0].image.convert("RGB")
        image.save(path / "input.png")
        if active["id"] == "controls-p1":
            old = Image.open(HERE.parent / "pdf-core-g2-dots-2026-10-16/cpu-probe/input-0.png").convert("RGB")
            assert image.size == old.size and image.tobytes() == old.tobytes()
        save(path / "request.json", {"source": active, "image_size": image.size,
            "image_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
            "engine_input": inputs[0].model_dump(mode="json", exclude={"image"}), "max_new_tokens": inputs[0].max_new_tokens})
        begin = time.monotonic()
        outputs = original_predict(engine, inputs)
        assert outputs[0].text == (path / "raw.txt").read_text()
        try:
            parsed = json.loads(outputs[0].text)
            strict_json = isinstance(parsed, list) and len(parsed) > 0
        except json.JSONDecodeError:
            strict_json = False
        save(path / "prediction.json", {"outputs": [x.model_dump(mode="json") for x in outputs],
            "seconds": time.monotonic() - begin, "strict_nonempty_json_array": strict_json})
        return outputs

    vlm = VlmConvertOptions.from_preset("dots_ocr", engine_options=MlxVlmEngineOptions(trust_remote_code=True))
    vlm.model_spec.revision = REG["revision"]
    options = VlmPipelineOptions(vlm_options=vlm, generate_page_images=True, images_scale=2)
    save(OUT / "options.json", options.model_dump(mode="json"))
    results = []
    with patch("mlx_vlm.load", audited_load), patch.object(MlxVlmEngine, "initialize", observed_init), \
         patch.object(MlxVlmEngine, "predict_batch", observed_predict), patch.object(dispatch, "prepare_inputs", observed_prepare):
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_cls=VlmPipeline, pipeline_options=options)})
        state("initializing")
        converter.initialize_pipeline(InputFormat.PDF)
        for active in pages:
            path = OUT / active["id"]
            path.mkdir(exist_ok=False)
            mx.reset_peak_memory()
            state("page", active["id"])
            begin = time.monotonic()
            page = active["physical_page"]
            result = converter.convert(REPO / active["source_pdf"]["path"], page_range=(page, page), raises_on_error=False)
            if result.document is not None:
                result.document.save_as_json(path / "document.json")
                (path / "document.md").write_text(result.document.export_to_markdown(**REG["official_export_options"]))
            record = {"id": active["id"], "status": result.status.value, "seconds": time.monotonic() - begin,
                "errors": [x.model_dump(mode="json") for x in result.errors], "mlx_peak_bytes": mx.get_peak_memory()}
            save(path / "conversion.json", record)
            results.append(record)
            save(OUT / "completed-pages.json", results)
            print(json.dumps(record), flush=True)
            assert result.status.value == "success", record
    state("completed")


def main():
    OUT.mkdir(exist_ok=False)
    env = os.environ.copy()
    env.update(HF_HOME="/private/tmp/pdf-core-g2-dots-20261016/hf", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               TOKENIZERS_PARALLELISM="false", OMP_NUM_THREADS="4")
    proc = None
    samples = []
    status = "not_started"
    with open("/private/tmp/data-ingestion-pdf-qualification.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        begin = time.monotonic()
        available = psutil.virtual_memory().available
        try:
            if available < REG["min_prelaunch_available_bytes"]:
                status = "insufficient_available_memory_before_launch"
                return
            with (OUT / "worker.log").open("w") as log:
                proc = subprocess.Popen(["rtk", "proxy", sys.executable, str(Path(__file__).resolve()), "--child"],
                    env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                status = "running"
                while proc.poll() is None:
                    try:
                        root = psutil.Process(proc.pid)
                        rss = sum(p.memory_info().rss for p in [root] + root.children(recursive=True) if p.is_running())
                    except psutil.NoSuchProcess:
                        rss = 0
                    stage = json.loads((OUT / "stage.json").read_text()) if (OUT / "stage.json").exists() else {"started_monotonic": begin}
                    free = psutil.virtual_memory().available
                    elapsed = time.monotonic() - stage["started_monotonic"]
                    samples.append({"seconds": time.monotonic() - begin, "rss_bytes": rss, "available_bytes": free, "stage": stage.get("stage"), "page": stage.get("page")})
                    reason = limit_reason(elapsed, rss, free)
                    if reason:
                        status = reason
                        break
                    time.sleep(0.05)
                if status == "running":
                    status = "completed" if proc.returncode == 0 else "worker_error"
        except BaseException:
            status = "runner_or_monitor_error"
            raise
        finally:
            if proc is not None and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            save(OUT / "execution.json", {"status": status, "seconds": time.monotonic() - begin,
                "prelaunch_available_bytes": available, "peak_sampled_tree_rss_bytes": max((x["rss_bytes"] for x in samples), default=0),
                "exit_code": proc.returncode if proc else None, "samples": samples,
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "all_owned_children_reaped": proc is None or proc.poll() is not None, "holdout_reads": 0, "automatic_retries": 0})
            print(status, flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--selfcheck"]:
        assert limit_reason(181, 0, 20 * 2**30) == "timeout"
        assert limit_reason(1, 13 * 2**30, 20 * 2**30) == "rss_limit"
        assert limit_reason(1, 0, 3 * 2**30) == "available_memory_limit"
        assert limit_reason(1, 0, 20 * 2**30) is None
        shapes = source_shapes()
        assert shapes["vision_tower.patch_embed.patchifier.proj.weight"].transpose(0, 2, 3, 1).shape == (1536, 14, 14, 3)
        print("Resource boundaries and pinned checkpoint header self-check passed; no model instances")
    elif sys.argv[1:] == ["--child"]:
        child()
    else:
        assert not sys.argv[1:]
        main()
