"""Local model weights, checked against the committed sha256 manifest (#129, toolchain).

scripts/fetch-models writes the manifest; the inference worker verifies at start that the
weights on disk are the ones the manifest pins, since reuse keys do not hash weights and a
changed file would register different output under the same key."""

import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path

MANIFEST = Path(__file__).parent / "model-manifest.json"


class WeightsMismatch(RuntimeError):
    pass


def root() -> Path:
    """Where the weights live: $DOCLING_ARTIFACTS_PATH, default ~/models/docling."""
    return Path(
        os.environ.get("DOCLING_ARTIFACTS_PATH", Path.home() / "models/docling")
    ).expanduser()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def problems(components: Iterable[str], root: Path, manifest: dict | None = None) -> list[str]:
    """One line per file of the given components that is missing or differs from the
    manifest. Components without a manifest entry (packages, remote services) are skipped."""
    pinned = manifest if manifest is not None else json.loads(MANIFEST.read_text())
    return [
        f"{component}: {rel} {'missing' if not (root / rel).is_file() else 'sha256 mismatch'}"
        for component in dict.fromkeys(components)
        if component in pinned
        for rel, digest in pinned[component]["files"].items()
        if not (root / rel).is_file() or sha256(root / rel) != digest
    ]


def verify(components: Iterable[str], root: Path) -> None:
    if found := problems(components, root):
        raise WeightsMismatch(
            f"model weights under {root} differ from the manifest:\n" + "\n".join(found)
        )
