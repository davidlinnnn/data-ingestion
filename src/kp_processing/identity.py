"""Method identity: package source digest and the reuse key (ADR-0010)."""

from collections.abc import Sequence
from pathlib import Path


def module_digest(package_dir: Path) -> str:
    """Hex sha256 over a method package's source files.

    Covers every file under package_dir, walked recursively, in sorted order of its
    POSIX path relative to package_dir; each file contributes its relative path and its
    bytes, framed so that moving bytes between a path and content changes the digest.
    Bytecode is excluded: `__pycache__` directories and `*.pyc` / `*.pyo` files.
    Independent of the directory's location, mtimes and permissions.
    """
    raise NotImplementedError


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
    raise NotImplementedError
