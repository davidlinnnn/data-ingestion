"""The inference worker's weight check against the manifest (#129, toolchain)."""

import hashlib
import json

from kp_processing import weights
from kp_processing.weights import problems

MANIFEST = {
    "layout@1": {"source": "test", "files": {
        "layout/model.bin": hashlib.sha256(b"weights").hexdigest(),
        "layout/config.json": hashlib.sha256(b"{}").hexdigest(),
    }},
}  # fmt: skip


def weights_dir(tmp_path):
    (tmp_path / "layout").mkdir()
    (tmp_path / "layout/model.bin").write_bytes(b"weights")
    (tmp_path / "layout/config.json").write_bytes(b"{}")
    return tmp_path


def test_weights_that_match_the_manifest_pass(tmp_path):
    assert problems(["layout@1"], weights_dir(tmp_path), MANIFEST) == []


def test_a_changed_or_missing_file_is_named(tmp_path):
    root = weights_dir(tmp_path)
    (root / "layout/model.bin").write_bytes(b"weightz")
    (root / "layout/config.json").unlink()

    assert problems(["layout@1"], root, MANIFEST) == [
        "layout@1: layout/model.bin sha256 mismatch",
        "layout@1: layout/config.json missing",
    ]


def test_components_without_local_weights_are_not_checked(tmp_path):
    assert problems(["docling-slim@2.132.0", "company-vlm/x"], tmp_path, MANIFEST) == []


def test_the_installed_weights_match_the_committed_manifest():
    assert problems(json.loads(weights.MANIFEST.read_text()), weights.root()) == []
