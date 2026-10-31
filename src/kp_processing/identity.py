"""Method identity: package source digest and the reuse key (ADR-0010)."""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> bytes:
    """UTF-8 JSON with sorted keys, no whitespace and no NaN or infinity: the bytes of every
    registered JSON object outside the method packages."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def module_digest(package_dir: Path) -> str:
    """Hex sha256 over a method package's source files.

    Covers every file under package_dir, walked recursively, in sorted order of its
    POSIX path relative to package_dir; each file contributes its relative path and its
    bytes, framed so that moving bytes between a path and content changes the digest.
    Bytecode (`__pycache__`, `*.pyc`, `*.pyo`) and hidden files or directories are excluded.
    Independent of the directory's location, mtimes and permissions.
    """
    digest = hashlib.sha256()
    for path in sorted(package_dir.rglob("*"), key=lambda p: p.relative_to(package_dir).as_posix()):
        relative = path.relative_to(package_dir)
        # Hidden files (.DS_Store, editor swap files) are never part of the shipped package.
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts) or (
            path.suffix in {".pyc", ".pyo"}
        ):
            continue
        if path.is_file():
            for value in (relative.as_posix().encode("utf-8"), path.read_bytes()):
                digest.update(len(value).to_bytes(8, "big"))
                digest.update(value)
    return digest.hexdigest()


def reuse_key(
    document_uid: str,
    method_ref: str,
    components: Sequence[str],
    module_digest: str,
    input_digests: Sequence[str],
) -> str:
    """Hex sha256 of the five parts, encoded unambiguously (compact JSON array of
    [document_uid, method_ref, [components...], module_digest, [input_digests...]]).
    Order of components and input_digests is significant as given."""
    parts = [document_uid, method_ref, list(components), module_digest, list(input_digests)]
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode("utf-8")).hexdigest()
