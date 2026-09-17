"""Qualification-only cgroup and owned-process attribution telemetry.

The existing Q04 worker telemetry remains the fail-closed resource guard. This
module records auxiliary attribution evidence and never converts a missing PSS or
optional cgroup field into a memory-limit violation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable


MEMORY_STAT_FIELDS = (
    "anon",
    "file",
    "shmem",
    "file_mapped",
    "inactive_file",
    "slab",
    "kernel",
)


def _fields(text: str, *, kib: bool = False) -> dict[str, int]:
    result = {}
    for line in text.splitlines():
        parts = line.rstrip(":").split()
        if len(parts) < 2:
            continue
        try:
            value = int(parts[1])
        except ValueError:
            continue
        result[parts[0].rstrip(":")] = value * 1024 if kib else value
    return result


def _proc_stat(text: str) -> dict[str, int | str]:
    closing = text.rfind(")")
    if closing < 0:
        raise ValueError("process stat has no closing comm delimiter")
    fields = text[closing + 1 :].split()
    if len(fields) <= 19:
        raise ValueError("process stat is incomplete")
    return {
        "state": fields[0],
        "ppid": int(fields[1]),
        "minor_faults": int(fields[7]),
        "major_faults": int(fields[9]),
        "user_cpu_ticks": int(fields[11]),
        "system_cpu_ticks": int(fields[12]),
        "start_ticks": int(fields[19]),
    }


def cgroup_identity(
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    *,
    read_text: Callable[[Path], str] | None = None,
) -> dict:
    """Resolve the cgroup-v2 observation directory without changing counters."""
    reader = read_text or (lambda path: path.read_text())
    lines = reader(proc_root / "self/cgroup").splitlines()
    unified = [line for line in lines if line.startswith("0::")]
    if len(unified) != 1:
        raise ValueError("exactly one unified cgroup membership is required")
    unified_path = unified[0].split("::", 1)[1]
    mount_rows = [
        line
        for line in reader(proc_root / "self/mountinfo").splitlines()
        if " - cgroup2 " in line
    ]
    if len(mount_rows) != 1:
        raise ValueError("exactly one cgroup-v2 mount is required")
    before = mount_rows[0].split(" - ", 1)[0].split()
    if len(before) < 5:
        raise ValueError("cgroup-v2 mountinfo is incomplete")
    identity = cgroup_root.stat()
    return {
        "proc_cgroup": unified[0],
        "unified_path": unified_path,
        "mount_root": before[3],
        "mount_point": before[4],
        "observed_directory": str(cgroup_root),
        "device": identity.st_dev,
        "inode": identity.st_ino,
    }


def _read_optional_text(
    path: Path,
    issues: list[dict],
    reader: Callable[[Path], str],
) -> str | None:
    try:
        return reader(path)
    except (FileNotFoundError, PermissionError, ProcessLookupError) as error:
        issues.append(
            {"field": path.name, "reason": type(error).__name__, "optional": True}
        )
        return None


def _command_class(payload: bytes) -> str:
    text = payload.replace(b"\0", b" ").decode(errors="replace")
    if "acl_fresh_measure.py" in text:
        return "controller"
    if "q04/worker.py" in text or text.rstrip().endswith("worker.py"):
        return "worker"
    if "pdf_processing.warm_child" in text:
        return "parser"
    return "owned_descendant"


def _collect_process(
    pid: int,
    proc_root: Path,
    initial: dict[str, int | str],
    *,
    read_text: Callable[[Path], str],
    read_bytes: Callable[[Path], bytes],
) -> dict:
    root = proc_root / str(pid)
    issues: list[dict] = []
    try:
        current = _proc_stat(read_text(root / "stat"))
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return {
            "pid": pid,
            "ppid": initial["ppid"],
            "start_ticks": initial["start_ticks"],
            "status": "exited_during_sample",
            "attribution_complete": False,
        }
    if current["start_ticks"] != initial["start_ticks"]:
        return {
            "pid": pid,
            "ppid": current["ppid"],
            "start_ticks": current["start_ticks"],
            "status": "identity_changed_during_sample",
            "attribution_complete": False,
        }

    try:
        command = read_bytes(root / "cmdline")
        command_sha256 = hashlib.sha256(command).hexdigest()
        command_class = _command_class(command)
    except (FileNotFoundError, PermissionError, ProcessLookupError) as error:
        issues.append(
            {"field": "cmdline", "reason": type(error).__name__, "optional": True}
        )
        command_sha256 = None
        command_class = "unknown_owned"

    status_text = _read_optional_text(root / "status", issues, read_text)
    smaps_text = _read_optional_text(root / "smaps_rollup", issues, read_text)
    status = _fields(status_text or "", kib=True)
    smaps = _fields(smaps_text or "", kib=True)
    pss = smaps.get("Pss")
    requested = {
        "Rss": smaps.get("Rss"),
        "Pss": pss,
        "RssAnon": status.get("RssAnon"),
        "RssFile": status.get("RssFile"),
        "RssShmem": status.get("RssShmem"),
    }
    for name, value in requested.items():
        if value is None:
            issues.append({"field": name, "reason": "missing", "optional": True})
    return {
        "pid": pid,
        "ppid": current["ppid"],
        "start_ticks": current["start_ticks"],
        "state": current["state"],
        "status": "ok",
        "command_class": command_class,
        "command_sha256": command_sha256,
        "rss_bytes": smaps.get("Rss"),
        "pss_bytes": pss,
        "rss_anon_bytes": status.get("RssAnon"),
        "rss_file_bytes": status.get("RssFile"),
        "rss_shmem_bytes": status.get("RssShmem"),
        "minor_faults": current["minor_faults"],
        "major_faults": current["major_faults"],
        "user_cpu_ticks": current["user_cpu_ticks"],
        "system_cpu_ticks": current["system_cpu_ticks"],
        "issues": issues,
        "attribution_complete": command_sha256 is not None
        and all(value is not None for value in requested.values()),
    }


def _owned_identities(
    proc_root: Path,
    root_pid: int,
    read_text: Callable[[Path], str],
) -> dict[int, dict[str, int | str]]:
    identities = {}
    for path in proc_root.iterdir():
        if not path.name.isdigit():
            continue
        try:
            identities[int(path.name)] = _proc_stat(read_text(path / "stat"))
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
            continue
    if root_pid not in identities:
        raise ProcessLookupError("collector root process identity disappeared")

    owned = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, identity in identities.items():
            if pid not in owned and identity["ppid"] in owned:
                owned.add(pid)
                changed = True
    return {pid: identities[pid] for pid in sorted(owned)}


def attribution_sample(
    *,
    root_pid: int,
    expected_cgroup: dict,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    wall_time: Callable[[], float] = time.time,
    monotonic: Callable[[], float] = time.monotonic,
    read_text: Callable[[Path], str] | None = None,
    read_bytes: Callable[[Path], bytes] | None = None,
) -> dict:
    """Take one diagnostic sample; only cgroup identity/current/events are required."""
    started = monotonic()
    text_reader = read_text or (lambda path: path.read_text())
    bytes_reader = read_bytes or (lambda path: path.read_bytes())
    actual_cgroup = cgroup_identity(
        proc_root, cgroup_root, read_text=text_reader
    )
    if actual_cgroup != expected_cgroup:
        raise ValueError("cgroup observation identity changed")
    memory_current = int(text_reader(cgroup_root / "memory.current").strip())
    memory_events = _fields(text_reader(cgroup_root / "memory.events"))
    if "oom_kill" not in memory_events:
        raise ValueError("required cgroup OOM counter is missing")

    auxiliary_issues: list[dict] = []
    stat_text = _read_optional_text(
        cgroup_root / "memory.stat", auxiliary_issues, text_reader
    )
    peak_text = _read_optional_text(
        cgroup_root / "memory.peak", auxiliary_issues, text_reader
    )
    memory_stat = _fields(stat_text or "")
    memory_stat = {name: memory_stat.get(name) for name in MEMORY_STAT_FIELDS}
    for name, value in memory_stat.items():
        if value is None:
            auxiliary_issues.append(
                {"field": "memory.stat:" + name, "reason": "missing", "optional": True}
            )
    memory_peak = None
    if peak_text is not None:
        try:
            memory_peak = int(peak_text.strip())
        except ValueError:
            auxiliary_issues.append(
                {"field": "memory.peak", "reason": "invalid", "optional": True}
            )

    identities = _owned_identities(proc_root, root_pid, text_reader)
    processes = [
        _collect_process(
            pid,
            proc_root,
            identity,
            read_text=text_reader,
            read_bytes=bytes_reader,
        )
        for pid, identity in identities.items()
    ]
    pss_values = [
        row["pss_bytes"]
        for row in processes
        if row.get("status") == "ok" and row.get("pss_bytes") is not None
    ]
    attribution_complete = not auxiliary_issues and all(
        row.get("attribution_complete") for row in processes
    )
    pss_total = sum(pss_values)
    finished = monotonic()
    return {
        "time": wall_time(),
        "monotonic": finished,
        "sample_duration_seconds": finished - started,
        "cgroup": actual_cgroup,
        "memory_current": memory_current,
        "memory_events": memory_events,
        "memory_stat": memory_stat,
        "memory_peak": memory_peak,
        "memory_peak_scope": "shared_cgroup_lifetime_high_water_mark",
        "memory_peak_reset": False,
        "owned_root_pid": root_pid,
        "processes": processes,
        "owned_pss_total_bytes": pss_total,
        "cgroup_minus_owned_pss_bytes": memory_current - pss_total,
        "residual_is_diagnostic_only": True,
        "attribution_complete": attribution_complete,
        "auxiliary_issues": auxiliary_issues,
    }


@dataclass(frozen=True)
class CollectorOutcome:
    samples: int
    maximum_gap_seconds: float
    attribution_complete: bool
    errors: tuple[str, ...]


class ResourceCollector:
    """Deep module for periodic attribution evidence with bounded cleanup."""

    def __init__(
        self,
        output: Path,
        summary: Path,
        *,
        root_pid: int | None = None,
        interval_seconds: float = 0.25,
        attribution_gap_seconds: float = 1.0,
        shutdown_timeout_seconds: float = 2.0,
        proc_root: Path = Path("/proc"),
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        sampler=attribution_sample,
    ):
        if (
            interval_seconds <= 0
            or attribution_gap_seconds <= 0
            or shutdown_timeout_seconds <= 0
        ):
            raise ValueError("collector intervals must be positive")
        self.output = output
        self.summary = summary
        self.root_pid = root_pid or os.getpid()
        self.interval_seconds = interval_seconds
        self.attribution_gap_seconds = attribution_gap_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.proc_root = proc_root
        self.cgroup_root = cgroup_root
        self.sampler = sampler
        self.identity: dict | None = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._state_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stream = None
        self._rows: list[dict] = []
        self._errors: list[str] = []
        self._pending_markers: list[str] = []
        self._last_completed_monotonic: float | None = None

    @property
    def started(self) -> bool:
        return self._stream is not None

    def _capture(self, marker: str | None = None):
        assert self.identity is not None and self._stream is not None
        row = self.sampler(
            root_pid=self.root_pid,
            expected_cgroup=self.identity,
            proc_root=self.proc_root,
            cgroup_root=self.cgroup_root,
        )
        with self._state_lock:
            markers = self._pending_markers
            self._pending_markers = []
        if marker is not None:
            markers.insert(0, marker)
        if markers:
            row["marker"] = markers[0]
            if len(markers) > 1:
                row["markers"] = markers
        payload = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        written = self._stream.write(payload)
        if written is not None and written != len(payload):
            raise OSError("short resource-attribution write")
        self._stream.flush()
        completed = time.monotonic()
        with self._state_lock:
            if (
                self._last_completed_monotonic is not None
                and completed - self._last_completed_monotonic
                > self.attribution_gap_seconds
            ):
                self._errors.append(
                    "resource attribution sample gap exceeded: "
                    + f"{completed - self._last_completed_monotonic:.6f}s"
                )
            self._rows.append(row)
            self._last_completed_monotonic = completed

    def _record_error(self, error: BaseException | str):
        message = (
            error
            if isinstance(error, str)
            else type(error).__name__ + ": " + str(error)
        )
        with self._state_lock:
            self._errors.append(message)

    def _queue_marker(self, label: str):
        with self._state_lock:
            self._pending_markers.append(label)

    def _run(self):
        try:
            self._ready.set()
            while True:
                if self._stop.wait(self.interval_seconds):
                    self._capture("collector_stopped_after_cleanup")
                    return
                self._capture()
        except BaseException as error:
            self._record_error(error)
            self._stop.set()
            self._ready.set()
        finally:
            if self._stream is not None:
                self._stream.close()

    def start(self):
        self.identity = cgroup_identity(self.proc_root, self.cgroup_root)
        self._stream = self.output.open("x", buffering=1)
        self._capture("collector_started_before_worker")
        self._thread = threading.Thread(
            target=self._run, name="acl-resource-attribution", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout=2):
            raise RuntimeError("resource collector did not become ready")
        self.require_healthy()

    def mark(self, label: str):
        self.require_healthy()
        self._queue_marker(label)

    def require_healthy(self):
        with self._state_lock:
            errors = tuple(self._errors)
            last_completed = self._last_completed_monotonic
        if errors:
            raise RuntimeError("resource attribution failed: " + "; ".join(errors))
        if self._thread is not None and not self._thread.is_alive() and not self._stop.is_set():
            raise RuntimeError("resource attribution stopped unexpectedly")
        if (
            self._thread is not None
            and last_completed is not None
            and time.monotonic() - last_completed > self.attribution_gap_seconds
        ):
            raise RuntimeError("resource attribution sample gap exceeded")

    def stop(self) -> CollectorOutcome:
        if self._stream is None:
            raise RuntimeError("resource collector was not started")
        self._queue_marker("cleanup_stop_requested")
        self._stop.set()
        if self._thread is None:
            self._stream.close()
        else:
            self._thread.join(timeout=self.shutdown_timeout_seconds)
            if self._thread.is_alive():
                self._record_error("collector thread did not stop within shutdown timeout")
            else:
                self._stream.close()
        with self._state_lock:
            rows = list(self._rows)
            errors = tuple(self._errors)
        times = [row["monotonic"] for row in rows]
        gaps = [b - a for a, b in zip(times, times[1:])]
        max_gap = max(gaps, default=0.0)
        attribution_complete = (
            bool(rows)
            and not errors
            and all(row["attribution_complete"] for row in rows)
            and max_gap <= self.attribution_gap_seconds
            and self._thread is not None
            and not self._thread.is_alive()
        )
        outcome = CollectorOutcome(
            samples=len(rows),
            maximum_gap_seconds=max_gap,
            attribution_complete=attribution_complete,
            errors=errors,
        )
        payload = {
            "samples": outcome.samples,
            "maximum_gap_seconds": outcome.maximum_gap_seconds,
            "attribution_gap_seconds": self.attribution_gap_seconds,
            "attribution_complete": outcome.attribution_complete,
            "errors": list(outcome.errors),
            "auxiliary_attribution_only": True,
            "qualification_guard_source": "worker samples.jsonl via telemetry.check_sample",
            "memory_peak_scope": "shared_cgroup_lifetime_high_water_mark",
            "memory_peak_reset": False,
            "residual_is_diagnostic_only": True,
        }
        with self.summary.open("x") as stream:
            stream.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return outcome
