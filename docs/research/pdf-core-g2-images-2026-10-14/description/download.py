"""Pinned public small description candidate, isolated from baseline caches."""
import hashlib
import json
from pathlib import Path
import time
from huggingface_hub import snapshot_download

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
metadata = json.loads((HERE / "model-costs.json").read_text())
files = [f for f in metadata["files"] if "/" not in f["name"] and
         (f["name"].endswith((".json", ".safetensors", ".txt", ".jinja")) or f["name"] == "README.md")]
assert sum(f["bytes"] for f in files if f["name"].endswith(".safetensors")) == 513028808
start = time.monotonic()
snapshot = Path(snapshot_download(metadata["repo"], revision=metadata["revision"], token=False, max_workers=2,
                allow_patterns=[f["name"] for f in files],
                cache_dir=REPO / "docs/prototypes/pdf-checkpoint-prototype/PROTOTYPE-wipe-me/g2-smolvlm-hf"))
result = {"repo": metadata["repo"], "revision": metadata["revision"], "snapshot_path": str(snapshot),
          "download_seconds": time.monotonic() - start, "files": []}
for record in files:
    path = snapshot / record["name"]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.stat().st_size == record["bytes"]
    if record["lfs_sha256"]:
        assert digest == record["lfs_sha256"]
    result["files"].append({**record, "sha256": digest})
(HERE / "download.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"files": len(files), "download_seconds": result["download_seconds"], "revision": result["revision"]}))
