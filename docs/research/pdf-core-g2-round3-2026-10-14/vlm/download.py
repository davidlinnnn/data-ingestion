"""Fetch one public, pinned CPU candidate into a separate evaluation cache."""
import hashlib
import json
from pathlib import Path
import time

from huggingface_hub import HfApi, snapshot_download

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODEL = "ibm-granite/granite-docling-258M"
REVISION = "982fe3b40f2fa73c365bdb1bcacf6c81b7184bfe"
CACHE = REPO / "docs/prototypes/pdf-checkpoint-prototype/PROTOTYPE-wipe-me/g2-granite-docling-hf"

info = HfApi(token=False).model_info(MODEL, revision=REVISION, files_metadata=True)
assert info.sha == REVISION
files = [f for f in info.siblings if "/" not in f.rfilename and f.rfilename != ".gitattributes"
         and not f.rfilename.endswith(".png")]
assert sum(f.size for f in files if f.rfilename.endswith(".safetensors")) == 515093104
started = time.monotonic()
snapshot = Path(snapshot_download(MODEL, revision=REVISION, cache_dir=CACHE, token=False,
                                 allow_patterns=[f.rfilename for f in files], max_workers=2))
result = {"repo": MODEL, "revision": REVISION, "snapshot_path": str(snapshot),
          "download_seconds": time.monotonic() - started, "files": []}
for f in files:
    path = snapshot / f.rfilename
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.stat().st_size == f.size
    if f.lfs:
        assert digest == f.lfs.sha256
    result["files"].append({"name": f.rfilename, "bytes": path.stat().st_size,
                            "sha256": digest, "official_lfs_sha256": f.lfs.sha256 if f.lfs else None})
HERE.mkdir(parents=True, exist_ok=True)
(HERE / "download.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"revision": REVISION, "files": len(files), "seconds": result["download_seconds"]}))
