"""Fetch only the pinned public classifier files into an isolated G2 cache."""
import hashlib
import json
from pathlib import Path
import time

from huggingface_hub import HfApi, snapshot_download

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MODEL = "docling-project/DocumentFigureClassifier-v2.5"
REVISION = "f859dfbff5c9916cd996942d4b0db7fa25808220"
CACHE = REPO / "docs/prototypes/pdf-checkpoint-prototype/PROTOTYPE-wipe-me/g2-picture-classifier-hf"
EXPECTED = {
    "config.json": (2522, "dbed0349fb8b12fad95d8ff7f43b062c40971e06d9d957b25e90d91dfd3bd77e"),
    "preprocessor_config.json": (377, "118dc069572036346fbacc3e15586089d3f8a9aaf9036c0c54b4666236a28032"),
    "model.safetensors": (16378200, "6bf1e44d6bce316dcade6eb9929d8f8d23b6e8d9d29062b3b4011cff87c7c3cd"),
}

info = HfApi(token=False).model_info(MODEL, revision=REVISION, files_metadata=True)
assert info.sha == REVISION
files = {f.rfilename: f for f in info.siblings if f.rfilename in EXPECTED}
assert set(files) == set(EXPECTED)
for name, (size, digest) in EXPECTED.items():
    assert files[name].size == size
    if files[name].lfs:
        assert files[name].lfs.sha256 == digest
started = time.monotonic()
snapshot = Path(snapshot_download(MODEL, revision=REVISION, cache_dir=CACHE, token=False,
                                 allow_patterns=list(EXPECTED), max_workers=2))
result = {"repo": MODEL, "revision": REVISION, "snapshot_path": str(snapshot),
          "download_seconds": time.monotonic() - started, "anonymous": True, "files": []}
for name, (size, digest) in EXPECTED.items():
    path = snapshot / name
    assert path.stat().st_size == size
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    result["files"].append({"name": name, "bytes": size, "sha256": digest,
                            "official_lfs_sha256": files[name].lfs.sha256 if files[name].lfs else None})
(HERE / "download.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"revision": REVISION, "bytes": sum(v[0] for v in EXPECTED.values()),
                  "download_seconds": result["download_seconds"]}))
