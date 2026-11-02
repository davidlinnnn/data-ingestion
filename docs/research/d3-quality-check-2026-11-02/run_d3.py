"""#153 d3 inference: official AutoModel + system_one, one model at a time, outside any sandbox.

    .../d3-runtime/venv/bin/python run_d3.py OUT MODEL SPLIT --model-dir DIR \
        --manifest WEIGHTS.json \
        --questions QUESTIONS.json [--control W4B_DIR W4B_ROOT] [--device mps]

Adapted from W4b's infer.py. Before loading: OUT/freeze.json hashes must match, every manifest
file must match on disk, and no docling process may be running (48 GiB host). Network is
forbidden during inference by a socket guard. Dev rows get both questions; test rows get the
question frozen in OUT/selection/MODEL.json. One result file per item under
OUT/runs/MODEL/SPLIT/; a run that finds results there refuses to start (no silent retry).
--control runs W4b's own dev inputs and questions (results under OUT/runs/control-MODEL/dev/)
to check this runtime reproduces W4b's saved scores.
"""

import argparse
import hashlib
import json
import os
import socket
import sys
import time
import traceback
import urllib.request
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("model")
    parser.add_argument("split", choices=["dev", "test"])
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--control", nargs=2, type=Path, metavar=("W4B_DIR", "W4B_ROOT"))
    parser.add_argument("--device", default="mps", choices=["mps", "cpu"])
    a = parser.parse_args()
    out = a.out.resolve()
    for key, value in {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTORCH_ENABLE_MPS_FALLBACK": "0",
        "HF_HOME": str(out / "hf-cache"),
        "HF_MODULES_CACHE": str(out / "hf-cache/modules"),
        "TMPDIR": str(out / "tmp"),
    }.items():
        os.environ[key] = value
    (out / "tmp").mkdir(exist_ok=True)
    import psutil
    import torch
    from PIL import Image
    from transformers import AutoModel

    manifest = json.loads(a.manifest.read_text())
    assert manifest["model"] == a.model and not manifest["mismatches"]
    for f in manifest["files"]:
        if "sha256" in f:
            assert sha(a.model_dir / f["file"]) == f["sha256"], f["file"]
    if a.control:
        w4b, root = a.control
        name, questions = f"control-{a.model}", json.loads((w4b / "questions.json").read_text())
        rows = [
            r
            for r in json.loads((w4b / "model-inputs.json").read_text())["items"]
            if r["split"] == a.split
        ]
        assert a.split == "dev"
    else:
        root, name = out, a.model
        for file, digest in json.loads((out / "freeze.json").read_text())["files"].items():
            assert sha(Path(file) if Path(file).is_absolute() else out / file) == digest, file
        questions = json.loads(a.questions.read_text())
        rows = [
            r
            for r in json.loads((out / "model-inputs.json").read_text())["items"]
            if r["split"] == a.split
        ]
    selection = None
    if a.split == "test":
        selection = json.loads((out / "selection" / f"{a.model}.json").read_text())["models"][
            a.model
        ]
    others = [
        p.info
        for p in psutil.process_iter(["pid", "cmdline"])
        if p.info["pid"] != os.getpid()
        and any("docling" in part for part in (p.info["cmdline"] or []))
    ]
    assert not others, f"docling is running: {others}"
    base = out / "runs" / name / a.split
    base.mkdir(parents=True, exist_ok=True)
    assert not list(base.glob("*.result.json")), "results exist; one execution per model and split"

    network_attempts = []
    connect = socket.socket.connect

    def no_connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            network_attempts.append(str(address))
            raise RuntimeError("NETWORK_FORBIDDEN_IN_INFERENCE")
        return connect(sock, address)

    socket.socket.connect = no_connect
    urllib.request.urlopen = lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("NETWORK_FORBIDDEN_IN_INFERENCE")
    )
    assert a.device != "mps" or torch.backends.mps.is_available()
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    if a.device == "mps":
        torch.mps.set_per_process_memory_fraction(0.45)

    def sync():
        if a.device == "mps":
            torch.mps.synchronize()

    t = time.monotonic()
    try:
        model = AutoModel.from_pretrained(
            str(a.model_dir),
            trust_remote_code=True,
            revision=manifest["revision"],
            code_revision=manifest["revision"],
            local_files_only=True,
            device=a.device,
            batch_size=1,
            verify="fast",
        )
        sync()
        assert all(
            x.device.type == a.device and x.dtype == torch.bfloat16
            for x in model.backbone.parameters()
        )
        assert (
            model.runtime.readout.device.type == a.device
            and model.runtime.readout.dtype == torch.float32
        )
        assert model.runtime.image_contract()["supported"], model.runtime.image_contract()
        write(
            base / "load.json",
            {
                "seconds": time.monotonic() - t,
                "device": a.device,
                "provenance": model.runtime.provenance(),
                "available_bytes": psutil.virtual_memory().available,
                "RSS_bytes": psutil.Process().memory_info().rss,
            },
        )
    except Exception as e:
        write(
            base / "load-error.json",
            {
                "type": type(e).__name__,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "network_attempts": network_attempts,
            },
        )
        raise
    for i, r in enumerate(rows):
        if psutil.virtual_memory().available < 8 * 1024**3:
            write(base / "stop.json", {"reason": "MEMORY_FENCE", "remaining": len(rows) - i})
            break
        assert set(r["state"]) == {"category", "reconstruction"}
        images = []
        for im in r["images"]:
            f = root / im["path"]
            assert sha(f) == im["sha256"], im["path"]
            images.append(Image.open(f).convert("RGB"))
        chosen = selection[r["category"]]["question"] if selection else None
        qs = {chosen: questions[r["category"]][chosen]} if chosen else questions[r["category"]]
        sync()
        t = time.monotonic()
        record = {
            "id": r["id"],
            "category": r["category"],
            "split": a.split,
            "device": a.device,
            "questions": list(qs),
            "input_image_sizes": [list(im.size) for im in images],
        }
        try:
            result = model.system_one(state=r["state"], images=images, questions=qs)
            sync()
            assert result["usage"]["output_tokens"] == 0
            scores = {}
            for q in qs:
                ans = result["answers"][q]
                score = ans["probabilities"]["faithful"] if q == "Q1" else ans["noul"]
                assert 0 <= score <= 1
                if q == "Q1":
                    assert set(ans["probabilities"]) == {
                        "faithful",
                        "minor_difference",
                        "meaning_changed",
                        "cannot_determine",
                    }
                    assert abs(sum(ans["probabilities"].values()) - 1) < 1e-5
                scores[q] = score
            assert not network_attempts
            record.update(state="OK", result=result, safe_scores=scores)
        except Exception as e:
            record.update(
                state="FAILED",
                error_type=type(e).__name__,
                error=str(e),
                traceback=traceback.format_exc(),
                network_attempts=network_attempts,
            )
        record.update(
            seconds=time.monotonic() - t,
            RSS_bytes=psutil.Process().memory_info().rss,
            host_available_bytes=psutil.virtual_memory().available,
            mps_driver_bytes=torch.mps.driver_allocated_memory() if a.device == "mps" else None,
        )
        write(base / (hashlib.sha256(r["id"].encode()).hexdigest() + ".result.json"), record)
        print(
            json.dumps(
                {
                    "model": name,
                    "split": a.split,
                    "completed": i + 1,
                    "total": len(rows),
                    "state": record["state"],
                    "seconds": round(record["seconds"], 3),
                }
            ),
            flush=True,
        )
        if record["state"] == "FAILED":
            write(
                base / "stop.json",
                {"reason": "RUNTIME_ERROR", "id": r["id"], "error_type": record["error_type"]},
            )
            break
        if a.device == "mps":
            torch.mps.empty_cache()
    write(
        base / "summary.json",
        {
            "expected": len(rows),
            "completed": len(list(base.glob("*.result.json"))),
            "network_attempts": network_attempts,
            "remote_inference_calls": 0,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
