"""Acquire one pinned public checkpoint to scratch and verify official LFS hashes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

HERE = Path(__file__).resolve().parent
MODEL = Path("/private/tmp/pdf-core-g2-dots-20261016/models/rednote-hilab--dots.ocr")
os.environ["HF_HOME"] = "/private/tmp/pdf-core-g2-dots-20261016/hf"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
from huggingface_hub import hf_hub_download

metadata = json.loads((HERE / "model-source/metadata.json").read_text())
assert metadata["sha"] == "c0111ce6bc07803dbc267932ffef0ae3a51dc951"
MODEL.mkdir(parents=True, exist_ok=True)
for source in (HERE / "model-source").iterdir():
    if source.name not in ("metadata.json", "download.json"):
        shutil.copyfile(source, MODEL / source.name)
files = [x for x in metadata["siblings"] if x["rfilename"].endswith(".safetensors")]
assert len(files) == 2 and sum(x["size"] for x in files) == 6078431736
records = []
begun = time.monotonic()
for item in files:
    start = time.monotonic()
    print("Downloading", item["rfilename"], item["size"], flush=True)
    path = Path(hf_hub_download("dots-studio/dots.ocr", filename=item["rfilename"],
                revision=metadata["sha"], local_dir=MODEL, token=False))
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8*1024*1024), b""):
            digest.update(chunk)
    assert path.stat().st_size == item["size"] and digest.hexdigest() == item["lfs"]["sha256"]
    records.append({"file": item["rfilename"], "bytes": path.stat().st_size,
                    "sha256": digest.hexdigest(), "seconds": time.monotonic()-start})
    (HERE / "weights.json").write_text(json.dumps({"repo": metadata["id"], "revision": metadata["sha"],
        "model_path": str(MODEL), "files": records, "seconds": time.monotonic()-begun,
        "complete": len(records)==2, "inference_calls": 0}, indent=2)+"\n")
    print("Verified", item["rfilename"], records[-1]["seconds"], flush=True)
