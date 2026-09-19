"""Prepare and inspect one run-owned directory inside a Q04 evidence volume.

The storage backend owns the mount root.  The unprivileged worker owns only the
exclusive child directory returned by this module.  Every durable evidence,
transport, and recovery path for the run is rooted at that child directory.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

from pod_durable_evidence import require_capacity, volume_capacity


RUN_UID = 1000
RUN_GID = 1000
DIRECTORY_MODE = 0o700
PROBE_INCOMPLETE = ".contract-probe.incomplete"
PROBE_COMPLETE = ".contract-probe"
PROBE_PAYLOAD = b"q04-evidence-directory-v1\n"


def _safe_name(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or value in {".", ".."}
        or path.is_absolute()
        or len(path.parts) != 1
        or path.parts[0] != value
    ):
        raise ValueError("evidence directory name must be one single safe path segment")
    return value


def _metadata(path: Path, *, label: str) -> dict:
    value = os.lstat(path)
    mode = stat.S_IMODE(value.st_mode)
    return {
        "path": str(path),
        "uid": value.st_uid,
        "gid": value.st_gid,
        "mode": oct(mode),
        "directory": stat.S_ISDIR(value.st_mode),
        "symlink": stat.S_ISLNK(value.st_mode),
        "writable": os.access(path, os.W_OK | os.X_OK),
        "label": label,
    }


def _validate_mount_root(path: Path) -> dict:
    value = _metadata(path, label="storage-backend-owned-mount-root")
    if value["symlink"]:
        raise ValueError("evidence mount root must not be a symlink")
    if not value["directory"]:
        raise ValueError("evidence mount root must be a directory")
    if not value["writable"]:
        raise ValueError("evidence mount root is not writable by the worker")
    return value


def _validate_run_directory(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
) -> dict:
    value = _metadata(path, label="application-owned-run-directory")
    if value["symlink"]:
        raise ValueError("run evidence directory must not be a symlink")
    if not value["directory"]:
        raise ValueError("run evidence path must be a directory")
    if value["uid"] != expected_uid or value["gid"] != expected_gid:
        raise ValueError("run evidence directory ownership changed")
    if value["mode"] != oct(DIRECTORY_MODE):
        raise ValueError("run evidence directory mode changed")
    if not value["writable"]:
        raise ValueError("run evidence directory is not writable")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _durable_probe(root: Path) -> dict:
    incomplete = root / PROBE_INCOMPLETE
    complete = root / PROBE_COMPLETE
    if os.path.lexists(incomplete) or os.path.lexists(complete):
        raise ValueError("evidence contract probe path already exists")
    with incomplete.open("xb") as stream:
        stream.write(PROBE_PAYLOAD)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(incomplete, complete)
    _fsync_directory(root)
    readback = complete.read_bytes()
    if readback != PROBE_PAYLOAD:
        raise ValueError("evidence contract probe readback changed")
    digest = hashlib.sha256(readback).hexdigest()
    complete.unlink()
    _fsync_directory(root)
    return {
        "bytes": len(readback),
        "sha256": digest,
        "file_fsync": True,
        "atomic_rename": True,
        "directory_fsync_after_rename": True,
        "readback_verified": True,
        "probe_removed": True,
        "directory_fsync_after_remove": True,
    }


def inspect_run_directory(
    mount_root: Path,
    directory_name: str,
    *,
    expected_uid: int = RUN_UID,
    expected_gid: int = RUN_GID,
) -> dict:
    """Inspect an existing run directory without creating or changing it."""
    name = _safe_name(directory_name)
    process = {"uid": os.getuid(), "gid": os.getgid()}
    if process != {"uid": expected_uid, "gid": expected_gid}:
        raise ValueError("evidence process identity changed")
    mount = _validate_mount_root(mount_root)
    run = mount_root / name
    entries = sorted(item.name for item in mount_root.iterdir())
    if entries != [name]:
        raise ValueError("evidence mount root contains foreign entries")
    directory = _validate_run_directory(
        run, expected_uid=expected_uid, expected_gid=expected_gid
    )
    capacity = volume_capacity(run)
    require_capacity(capacity)
    return {
        "schema_version": 1,
        "process": process,
        "mount": mount,
        "directory": directory,
        "capacity": capacity,
    }


def prepare_run_directory(
    mount_root: Path,
    directory_name: str,
    *,
    expected_uid: int = RUN_UID,
    expected_gid: int = RUN_GID,
) -> dict:
    """Exclusively create and prove one application-owned evidence directory."""
    name = _safe_name(directory_name)
    process = {"uid": os.getuid(), "gid": os.getgid()}
    if process != {"uid": expected_uid, "gid": expected_gid}:
        raise ValueError("evidence process identity changed")
    mount = _validate_mount_root(mount_root)
    run = mount_root / name
    entries = sorted(item.name for item in mount_root.iterdir())
    if entries:
        if name in entries or os.path.lexists(run):
            raise ValueError("run evidence path already exists")
        raise ValueError("evidence mount root contains foreign entries")
    if os.path.lexists(run):
        raise ValueError("run evidence path already exists")
    os.mkdir(run, DIRECTORY_MODE)
    directory = _validate_run_directory(
        run, expected_uid=expected_uid, expected_gid=expected_gid
    )
    capacity = volume_capacity(run)
    require_capacity(capacity)
    probe = _durable_probe(run)
    return {
        "schema_version": 1,
        "process": process,
        "mount": mount,
        "directory": directory,
        "capacity": volume_capacity(run),
        "durable_probe": probe,
    }
