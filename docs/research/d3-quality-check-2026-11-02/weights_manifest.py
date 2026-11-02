"""#153 §1: hash manifest of a downloaded d3 model, checked against the Hub's file tree.

    python3 docs/research/d3-quality-check-2026-11-02/weights_manifest.py \
        MODEL_DIR TREE_JSON REVISION OUT_JSON

TREE_JSON is the Hub API tree of the pinned revision (api/models/<repo>/tree/<revision>). Every
local file must match: LFS files by SHA-256, the rest by git blob SHA-1. Files the download
skipped (assets/, .eval_results/) are listed as absent. Weights never enter git; this manifest does.
"""

import hashlib
import json
import sys
from pathlib import Path


def main(model_dir: Path, tree: Path, revision: str, out: Path) -> int:
    entries = {e["path"]: e for e in json.loads(tree.read_text()) if e["type"] == "file"}
    files, mismatches = [], []
    for path, entry in sorted(entries.items()):
        local = model_dir / path
        if not local.is_file():
            files.append({"file": path, "absent": True})
            continue
        data = local.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        if "lfs" in entry:
            ok = sha256 == entry["lfs"]["oid"]
        else:
            ok = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest() == entry["oid"]
        files.append(
            {"file": path, "sha256": sha256, "bytes": len(data), "publisher_hash_match": ok}
        )
        if not ok:
            mismatches.append(path)
    extra = sorted(
        str(p.relative_to(model_dir))
        for p in model_dir.rglob("*")
        if p.is_file()
        and not p.name.endswith((".incomplete", ".lock", ".metadata"))
        and ".cache" not in p.parts
        and "__pycache__" not in p.parts
        and str(p.relative_to(model_dir)) not in entries
    )
    out.write_text(
        json.dumps(
            {
                "model": model_dir.name,
                "revision": revision,
                "files": files,
                "mismatches": mismatches,
                "unexpected_local_files": extra,
            },
            indent=1,
        )
        + "\n"
    )
    print(
        len(files),
        "tree files;",
        sum("sha256" in f for f in files),
        "present;",
        len(mismatches),
        "mismatches;",
        extra or "no extra files",
    )
    return 1 if mismatches or extra else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])))
