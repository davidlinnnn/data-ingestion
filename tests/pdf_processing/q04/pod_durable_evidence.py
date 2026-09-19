"""Durable evidence volume protocol for the Q04 fixture-07 Pod runner."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath


PVC_REQUEST_BYTES = 1024**3
STOP_FREE_BYTES = 128 * 1024**2
MAX_USED_BYTES = PVC_REQUEST_BYTES - STOP_FREE_BYTES
TERMINAL_MANIFEST = "durable-terminal-manifest.json"


class EvidenceCapacityError(RuntimeError):
    pass


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def volume_capacity(path: Path, statvfs=os.statvfs) -> dict:
    value = statvfs(path)
    filesystem_free = value.f_frsize * value.f_bavail
    used = sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return {
        "requested_bytes": PVC_REQUEST_BYTES,
        "evidence_used_bytes": used,
        "evidence_free_bytes": max(0, PVC_REQUEST_BYTES - used),
        "filesystem_free_bytes": filesystem_free,
    }


def require_capacity(value: dict) -> None:
    if (
        value["filesystem_free_bytes"] < STOP_FREE_BYTES
        or value["evidence_free_bytes"] < STOP_FREE_BYTES
        or value["evidence_used_bytes"] > MAX_USED_BYTES
    ):
        raise EvidenceCapacityError("evidence PVC stop watermark reached")


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_once(path: Path, value: dict, *, volume_root: Path | None = None) -> None:
    """Create one JSON record and durably commit file plus directory entry."""
    volume_root = volume_root or path.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        raise FileExistsError(path)
    capacity = volume_capacity(volume_root)
    capacity["evidence_used_bytes"] += len(raw)
    capacity["evidence_free_bytes"] = max(
        0, PVC_REQUEST_BYTES - capacity["evidence_used_bytes"]
    )
    capacity["filesystem_free_bytes"] = max(
        0, capacity["filesystem_free_bytes"] - len(raw)
    )
    require_capacity(capacity)
    temporary = path.with_name(path.name + ".incomplete")
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    _fsync_directory(path.parent)


def _safe_relative(path: Path, root: Path) -> str:
    relative = path.relative_to(root).as_posix()
    value = PurePosixPath(relative)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("unsafe evidence path")
    return relative


def sync_inventory(root: Path) -> list[dict]:
    """Flush every completed evidence file and return a full immutable inventory."""
    require_capacity(volume_capacity(root))
    entries = []
    directories = {root}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("evidence symlink forbidden")
        if path.is_dir():
            directories.add(path)
            continue
        relative = _safe_relative(path, root)
        if relative.endswith(".incomplete"):
            raise ValueError("partial durable evidence file present")
        if relative == TERMINAL_MANIFEST:
            continue
        with path.open("rb") as stream:
            raw = stream.read()
            os.fsync(stream.fileno())
        entries.append({"path": relative, "bytes": len(raw), "sha256": digest(raw)})
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        _fsync_directory(directory)
    return entries


def verify_readback(root: Path, manifest: dict) -> None:
    if manifest.get("schema_version") != 1 or not manifest.get("terminal"):
        raise ValueError("terminal evidence manifest incomplete")
    observed = []
    for item in manifest.get("inventory", []):
        path = root.joinpath(*PurePosixPath(item["path"]).parts)
        raw = path.read_bytes()
        observed.append({"path": item["path"], "bytes": len(raw), "sha256": digest(raw)})
    if observed != manifest["inventory"]:
        raise ValueError("durable evidence readback mismatch")


def seal(
    root: Path,
    *,
    volume_identity: dict,
    workload_succeeded: bool,
    cleanup_complete: bool,
) -> dict:
    """Flush evidence, write the terminal commit, then read everything back."""
    if (root / TERMINAL_MANIFEST).exists():
        raise FileExistsError("durable evidence already sealed")
    inventory = sync_inventory(root)
    status = "PASS_CANDIDATE" if workload_succeeded and cleanup_complete else "INCOMPLETE"
    manifest = {
        "schema_version": 1,
        "terminal": True,
        "status": status,
        "workload_succeeded": workload_succeeded,
        "cleanup_complete": cleanup_complete,
        "volume_identity": volume_identity,
        "inventory": inventory,
        "inventory_sha256": digest(
            json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
        ),
        "capacity": volume_capacity(root),
    }
    write_once(root / TERMINAL_MANIFEST, manifest, volume_root=root)
    retained = json.loads((root / TERMINAL_MANIFEST).read_text())
    verify_readback(root, retained)
    return retained


def recover(root: Path, expected_volume_identity: dict) -> dict:
    terminal = root / TERMINAL_MANIFEST
    if not terminal.is_file():
        return {"status": "INCOMPLETE", "reason": "terminal_manifest_missing"}
    manifest = json.loads(terminal.read_text())
    if manifest.get("volume_identity") != expected_volume_identity:
        raise ValueError("evidence PVC identity changed")
    verify_readback(root, manifest)
    return manifest
