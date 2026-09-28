"""Strict, qualification-only attribution telemetry for YOLO calibration.

This module reuses the verified ACL cgroup/proc parsers, but tightens process
coverage semantics for a diagnostic run.  A missing process value is ``None``
and makes that sample incomplete; it is never folded into a zero PSS total.
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

try:
    from .acl_resource_telemetry import MEMORY_STAT_FIELDS, _fields, _proc_stat, cgroup_identity
except ImportError:
    from acl_resource_telemetry import MEMORY_STAT_FIELDS, _fields, _proc_stat, cgroup_identity


def _command_class(payload: bytes) -> str:
    text = payload.replace(b"\0", b" ").decode(errors="replace")
    if "yolo_fresh_measure.py" in text:
        return "controller"
    if "q04/worker.py" in text or text.rstrip().endswith("worker.py"):
        return "worker"
    if "pdf_processing.warm_child" in text:
        return "warm_parser"
    if "-m pdf_processing.parse" in text:
        return "fresh_parse_child"
    if "-m pdf_processing." in text:
        return "fresh_owned_child"
    return "owned_descendant"


class ProcessLifecycle:
    """Track birth, exit, and PID reuse from identity-fenced snapshots."""

    def __init__(self):
        self._previous: dict[int, dict] = {}

    def update(self, processes: list[dict]) -> list[dict]:
        current = {
            int(row["pid"]): row
            for row in processes
            if row.get("start_ticks") is not None
        }
        events = []
        for pid, row in sorted(current.items()):
            before = self._previous.get(pid)
            if before is None:
                events.append({
                    "event": "birth_observed",
                    "pid": pid,
                    "start_ticks": row["start_ticks"],
                    "command_class": row.get("command_class", "unknown_owned"),
                })
            elif before["start_ticks"] != row["start_ticks"]:
                events.append({
                    "event": "pid_reuse_observed",
                    "pid": pid,
                    "prior_start_ticks": before["start_ticks"],
                    "start_ticks": row["start_ticks"],
                    "command_class": row.get("command_class", "unknown_owned"),
                })
        for pid, row in sorted(self._previous.items()):
            if pid not in current:
                events.append({
                    "event": "exit_observed",
                    "pid": pid,
                    "start_ticks": row["start_ticks"],
                    "command_class": row.get("command_class", "unknown_owned"),
                })
        self._previous = current
        return events


def _scan_identities(
    proc_root: Path,
    read_text: Callable[[Path], str],
    expected_membership: str,
) -> tuple[dict[int, dict], list[dict]]:
    identities = {}
    issues = []
    try:
        paths = list(proc_root.iterdir())
    except (FileNotFoundError, PermissionError, ProcessLookupError) as error:
        return {}, [{"scope": "proc_enumeration", "reason": type(error).__name__}]
    for path in paths:
        if not path.name.isdigit():
            continue
        try:
            row = _proc_stat(read_text(path / "stat"))
            memberships = [line for line in read_text(path / "cgroup").splitlines() if line]
            if expected_membership not in memberships:
                continue
            row["pid"] = int(path.name)
            identities[row["pid"]] = row
        except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError) as error:
            issues.append({
                "scope": "proc_identity",
                "pid": int(path.name),
                "reason": type(error).__name__,
            })
    return identities, issues


def _owned(identities: dict[int, dict], root_pid: int) -> dict[int, dict]:
    if root_pid not in identities:
        return {}
    result = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, row in identities.items():
            if pid not in result and row["ppid"] in result:
                result.add(pid)
                changed = True
    return {pid: identities[pid] for pid in sorted(result)}


def _read_process(
    proc_root: Path,
    initial: dict,
    read_text: Callable[[Path], str],
    read_bytes: Callable[[Path], bytes],
    owned: bool,
) -> dict:
    pid = initial["pid"]
    root = proc_root / str(pid)
    base = {
        "pid": pid,
        "ppid": initial["ppid"],
        "start_ticks": initial["start_ticks"],
        "ownership": "owned" if owned else "shared_cgroup_other",
    }
    try:
        current = _proc_stat(read_text(root / "stat"))
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError) as error:
        return {**base, "status": "unknown", "reason": type(error).__name__,
                "command_class": "unknown_owned", "pss_bytes": None}
    if current["start_ticks"] != initial["start_ticks"]:
        return {
            **base,
            "status": "identity_changed_during_sample",
            "observed_start_ticks": current["start_ticks"],
            "command_class": "unknown_owned",
            "pss_bytes": None,
        }
    try:
        command = read_bytes(root / "cmdline")
        command_hash = hashlib.sha256(command).hexdigest()
        command_class = _command_class(command)
    except (FileNotFoundError, PermissionError, ProcessLookupError) as error:
        return {**base, "status": "unknown", "reason": type(error).__name__,
                "command_class": "unknown_owned", "pss_bytes": None}
    try:
        status = _fields(read_text(root / "status"), kib=True)
        smaps = _fields(read_text(root / "smaps_rollup"), kib=True)
    except (FileNotFoundError, PermissionError, ProcessLookupError) as error:
        return {
            **base,
            "status": "unknown",
            "reason": type(error).__name__,
            "command_class": command_class,
            "command_sha256": command_hash,
            "pss_bytes": None,
        }
    required = {
        "rss_bytes": smaps.get("Rss"),
        "pss_bytes": smaps.get("Pss"),
        "rss_anon_bytes": status.get("RssAnon"),
        "rss_file_bytes": status.get("RssFile"),
        "rss_shmem_bytes": status.get("RssShmem"),
    }
    missing = sorted(name for name, value in required.items() if value is None)
    return {
        **base,
        "state": current["state"],
        "status": "complete" if not missing else "incomplete",
        "command_class": command_class,
        "command_sha256": command_hash,
        **required,
        "minor_faults": current["minor_faults"],
        "major_faults": current["major_faults"],
        "user_cpu_ticks": current["user_cpu_ticks"],
        "system_cpu_ticks": current["system_cpu_ticks"],
        "missing_fields": missing,
    }


def _read_required(path: Path, reader: Callable[[Path], str], issues: list[dict]) -> str | None:
    try:
        return reader(path)
    except (FileNotFoundError, PermissionError, ProcessLookupError) as error:
        issues.append({"scope": "cgroup", "field": path.name, "reason": type(error).__name__})
        return None


def observed_runtime_markers(root: Path) -> tuple[list[dict], list[dict]]:
    """Report only externally observable files; labels never assert stage start."""
    markers = []
    issues = []
    if not root.exists():
        return markers, issues
    patterns = (
        ("workflow-intent.json", "workflow_intent_file_observed", "intent_not_submission"),
        ("workflow.json", "workflow_record_file_observed", "submission_record_not_activity_start"),
        ("cancel-outcome.json", "cancel_outcome_file_observed", "retained_cleanup_record"),
    )
    for filename, label, meaning in patterns:
        try:
            for path in root.rglob(filename):
                markers.append({"key": str(path.relative_to(root)), "label": label, "meaning": meaning})
        except (FileNotFoundError, PermissionError, OSError) as error:
            issues.append({"scope": "runtime_files", "field": filename, "reason": type(error).__name__})
    try:
        for path in root.rglob("progress.jsonl"):
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            if rows and rows[-1].get("progress", {}).get("status") == "assembling":
                markers.append({
                    "key": str(path.relative_to(root)) + ":assembling",
                    "label": "workflow_progress_assembling_observed",
                    "meaning": "workflow_query_state_not_activity_start",
                })
    except (FileNotFoundError, PermissionError, OSError, ValueError, TypeError) as error:
        issues.append({"scope": "runtime_progress", "reason": type(error).__name__})
    try:
        for path in root.rglob("merged"):
            if path.is_dir():
                markers.append({
                    "key": str(path.relative_to(root)),
                    "label": "merged_directory_observed",
                    "meaning": "filesystem_presence_not_materialization_start",
                })
    except (FileNotFoundError, PermissionError, OSError) as error:
        issues.append({"scope": "runtime_files", "field": "merged", "reason": type(error).__name__})
    return markers, issues


def strict_attribution_sample(
    *,
    root_pid: int,
    expected_cgroup: dict,
    proc_root: Path = Path("/proc"),
    cgroup_root: Path = Path("/sys/fs/cgroup"),
    observation_root: Path | None = None,
    wall_time: Callable[[], float] = time.time,
    monotonic: Callable[[], float] = time.monotonic,
    thread_time: Callable[[], float] = time.thread_time,
    read_text: Callable[[Path], str] | None = None,
    read_bytes: Callable[[Path], bytes] | None = None,
) -> dict:
    """Capture one fenced sample; unavailable attribution remains unknown."""
    started = monotonic()
    cpu_started = thread_time()
    text_reader = read_text or (lambda path: path.read_text())
    bytes_reader = read_bytes or (lambda path: path.read_bytes())
    actual_cgroup = cgroup_identity(proc_root, cgroup_root, read_text=text_reader)
    if actual_cgroup != expected_cgroup:
        raise ValueError("cgroup observation identity changed")

    issues = []
    current_text = _read_required(cgroup_root / "memory.current", text_reader, issues)
    events_text = _read_required(cgroup_root / "memory.events", text_reader, issues)
    stat_text = _read_required(cgroup_root / "memory.stat", text_reader, issues)
    pressure_text = _read_required(cgroup_root / "memory.pressure", text_reader, issues)
    memory_current = None
    try:
        memory_current = int(current_text.strip()) if current_text is not None else None
    except ValueError:
        issues.append({"scope": "cgroup", "field": "memory.current", "reason": "invalid"})
    memory_events = _fields(events_text or "")
    if "oom_kill" not in memory_events:
        issues.append({"scope": "cgroup", "field": "memory.events:oom_kill", "reason": "missing"})
    raw_stat = _fields(stat_text or "")
    memory_stat = {name: raw_stat.get(name) for name in MEMORY_STAT_FIELDS}
    for name, value in memory_stat.items():
        if value is None:
            issues.append({"scope": "cgroup", "field": "memory.stat:" + name, "reason": "missing"})

    before, before_issues = _scan_identities(
        proc_root, text_reader, expected_cgroup["proc_cgroup"]
    )
    issues.extend(before_issues)
    owned = _owned(before, root_pid)
    if not owned:
        issues.append({"scope": "process_coverage", "reason": "owned_root_unknown", "pid": root_pid})
    processes = [
        _read_process(
            proc_root,
            row,
            text_reader,
            bytes_reader,
            owned=pid in owned,
        )
        for pid, row in sorted(before.items())
    ]
    after, after_issues = _scan_identities(
        proc_root, text_reader, expected_cgroup["proc_cgroup"]
    )
    issues.extend(after_issues)
    before_keys = sorted((pid, row["start_ticks"], row["ppid"]) for pid, row in before.items())
    after_keys = sorted((pid, row["start_ticks"], row["ppid"]) for pid, row in after.items())
    process_set_changed = before_keys != after_keys
    if process_set_changed:
        issues.append({"scope": "process_coverage", "reason": "process_set_changed_during_sample"})
    if any(row["status"] != "complete" for row in processes):
        issues.append({
            "scope": "process_coverage",
            "reason": (
                "process_transition_read_incomplete"
                if process_set_changed
                else "cgroup_process_read_incomplete"
            ),
        })

    runtime_markers, runtime_issues = observed_runtime_markers(observation_root) if observation_root else ([], [])
    issues.extend(runtime_issues)
    complete = not issues and memory_current is not None and bool(processes)
    cgroup_pss_total = sum(row["pss_bytes"] for row in processes) if complete else None
    owned_pss_total = (
        sum(row["pss_bytes"] for row in processes if row["ownership"] == "owned")
        if complete
        else None
    )
    unattributed = memory_current - cgroup_pss_total if complete else None
    finished = monotonic()
    cpu_finished = thread_time()
    return {
        "time": wall_time(),
        "monotonic": finished,
        "sample_duration_seconds": finished - started,
        "collector_thread_cpu_seconds": cpu_finished - cpu_started,
        "cgroup": actual_cgroup,
        "memory_current": memory_current,
        "memory_events": memory_events,
        "memory_stat": memory_stat,
        "memory_pressure_raw": pressure_text,
        "owned_root_pid": root_pid,
        "processes": processes,
        "process_coverage": {
            "status": "complete" if complete else "incomplete",
            "enumerated_before": len(before),
            "enumerated_after": len(after),
            "owned_before": len(owned),
            "shared_cgroup_other_before": len(before) - len(owned),
            "unknown": issues,
        },
        "owned_pss_total_bytes": owned_pss_total,
        "shared_cgroup_process_pss_total_bytes": cgroup_pss_total,
        "diagnostic_unattributed_bytes": unattributed,
        "diagnostic_unattributed_includes": "file/cache, kernel and other non-process cgroup charges, plus sequential-read timing skew",
        "diagnostic_unattributed_is_cache": False,
        "attribution_complete": complete,
        "runtime_observations": runtime_markers,
    }


@dataclass(frozen=True)
class CollectorOutcome:
    samples: int
    maximum_gap_seconds: float
    attribution_complete: bool
    status: str
    errors: tuple[str, ...]
    incomplete_samples: int


class StrictAttributionCollector:
    """Own sampling, lifecycle, observational markers, cost, and cleanup evidence."""

    def __init__(
        self,
        output: Path,
        summary: Path,
        *,
        root_pid: int | None = None,
        observation_root: Path | None = None,
        interval_seconds: float = 0.25,
        attribution_gap_seconds: float = 1.0,
        shutdown_timeout_seconds: float = 2.0,
        proc_root: Path = Path("/proc"),
        cgroup_root: Path = Path("/sys/fs/cgroup"),
        sampler=strict_attribution_sample,
        stream_factory=None,
    ):
        if min(interval_seconds, attribution_gap_seconds, shutdown_timeout_seconds) <= 0:
            raise ValueError("collector intervals must be positive")
        self.output = output
        self.spool = output.with_name(output.name + ".inflight")
        self.summary = summary
        self.root_pid = root_pid or os.getpid()
        self.observation_root = observation_root
        self.interval_seconds = interval_seconds
        self.attribution_gap_seconds = attribution_gap_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.proc_root = proc_root
        self.cgroup_root = cgroup_root
        self.sampler = sampler
        self.stream_factory = stream_factory or (
            lambda output: output.open("x", buffering=1)
        )
        self.identity = None
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._capture_lock = threading.Lock()
        self._thread = None
        self._stream = None
        self._final_stream = None
        self._committed_bytes = 0
        self._rows = []
        self._errors = []
        self._pending = []
        self._seen_runtime = set()
        self._last_completed = None
        self._lifecycle = ProcessLifecycle()
        self._abandoned = threading.Event()

    @property
    def started(self) -> bool:
        return self._stream is not None

    def observe(self, label: str, *, source: str, meaning: str):
        if not label or not source or not meaning:
            raise ValueError("observable marker fields are required")
        with self._lock:
            self._pending.append({
                "label": label,
                "source": source,
                "meaning": meaning,
                "observed_at": time.time(),
            })

    def _capture(self, terminal: bool = False):
        with self._capture_lock:
            if self.identity is None or self._stream is None:
                raise RuntimeError("collector is not initialized")
            if self._abandoned.is_set():
                return
            row = self.sampler(
                root_pid=self.root_pid,
                expected_cgroup=self.identity,
                proc_root=self.proc_root,
                cgroup_root=self.cgroup_root,
                observation_root=self.observation_root,
            )
            row["process_events"] = self._lifecycle.update(row["processes"])
            fresh_events = [
                {
                    "label": "fresh_parse_process_birth_observed",
                    "source": "identity_fenced_process_table",
                    "meaning": "process_birth_observed_operation_input_not_visible",
                    "observed_at": row["time"],
                }
                for event in row["process_events"]
                if event["event"] in ("birth_observed", "pid_reuse_observed")
                and event.get("command_class") == "fresh_parse_child"
            ]
            runtime = []
            for event in row.pop("runtime_observations"):
                if event["key"] not in self._seen_runtime:
                    self._seen_runtime.add(event["key"])
                    runtime.append({
                        "label": event["label"],
                        "source": "external_runtime_files",
                        "meaning": event["meaning"],
                        "observed_at": row["time"],
                    })
            controller_pss = next(
                (
                    process["pss_bytes"]
                    for process in row["processes"]
                    if process["pid"] == self.root_pid
                    and process.get("pss_bytes") is not None
                ),
                None,
            )
            completed = time.monotonic()
            with self._lock:
                if self._abandoned.is_set():
                    return
                markers = self._pending
                self._pending = []
                row["observations"] = markers + fresh_events + runtime
                if terminal:
                    row["observations"].append({
                        "label": "post_cleanup_sample",
                        "source": "collector_lifecycle",
                        "meaning": "sample_after_owned_cleanup_callback",
                        "observed_at": row["time"],
                    })
                summary_row = {
                    "monotonic": row["monotonic"],
                    "attribution_complete": row["attribution_complete"],
                    "unknown": row["process_coverage"]["unknown"],
                    "memory_current": row["memory_current"],
                    "sample_duration_seconds": row["sample_duration_seconds"],
                    "collector_thread_cpu_seconds": row["collector_thread_cpu_seconds"],
                    "controller_pss_bytes": controller_pss,
                    "observation_labels": [
                        observation["label"] for observation in row["observations"]
                    ],
                }
            payload = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            try:
                self._stream.write(payload)
                self._stream.flush()
                committed_bytes = self._stream.tell()
            except BaseException:
                self._abandoned.set()
                raise
            with self._lock:
                if self._abandoned.is_set():
                    return
                if self._last_completed is not None:
                    gap = completed - self._last_completed
                    if gap > self.attribution_gap_seconds:
                        self._errors.append(f"collector gap exceeded: {gap:.6f}s")
                self._last_completed = completed
                self._rows.append(summary_row)
                self._committed_bytes = committed_bytes

    def _run(self):
        try:
            self._ready.set()
            while not self._stop.wait(self.interval_seconds):
                self._capture()
        except BaseException as error:
            with self._lock:
                self._errors.append(type(error).__name__ + ": " + str(error))
            self._stop.set()
            self._ready.set()
        finally:
            if self._abandoned.is_set() and self._stream is not None:
                self._stream.close()

    def start(self):
        self.identity = cgroup_identity(self.proc_root, self.cgroup_root)
        self._final_stream = self.output.open("xb")
        self._stream = self.stream_factory(self.spool)
        self.observe(
            "baseline_before_worker",
            source="collector_lifecycle",
            meaning="sample_before_worker_start_callback",
        )
        try:
            self._capture()
        except BaseException as error:
            with self._lock:
                self._errors.append(type(error).__name__ + ": " + str(error))
            raise
        self._thread = threading.Thread(target=self._run, name="yolo-attribution", daemon=True)
        self._thread.start()
        if not self._ready.wait(2):
            raise RuntimeError("collector did not become ready")
        self.require_healthy()

    def require_healthy(self):
        with self._lock:
            errors = tuple(self._errors)
            last = self._last_completed
        if errors:
            raise RuntimeError("attribution collector failed: " + "; ".join(errors))
        if self._thread is not None and not self._thread.is_alive() and not self._stop.is_set():
            raise RuntimeError("attribution collector stopped unexpectedly")
        if last is not None and time.monotonic() - last > self.attribution_gap_seconds:
            raise RuntimeError("attribution collector gap exceeded")

    def stop(self) -> CollectorOutcome:
        if self._stream is None:
            raise RuntimeError("collector was not started")
        self._stop.set()
        if self._thread is not None:
            self._thread.join(self.shutdown_timeout_seconds)
            if self._thread.is_alive():
                self._abandoned.set()
                with self._lock:
                    self._errors.append("collector thread did not stop within cleanup timeout")
        if self._thread is None or not self._thread.is_alive():
            try:
                self._capture(terminal=True)
            except BaseException as error:
                with self._lock:
                    self._errors.append(type(error).__name__ + ": " + str(error))
        with self._lock:
            rows = list(self._rows)
            errors = tuple(self._errors)
            committed_bytes = self._committed_bytes
        thread_alive = self._thread is not None and self._thread.is_alive()
        if self._stream is not None and not thread_alive:
            self._stream.close()
        if self._final_stream is None:
            raise RuntimeError("collector output was not reserved")
        with self.spool.open("rb") as spool:
            retained = spool.read(committed_bytes)
        if len(retained) != committed_bytes:
            errors = errors + ("committed collector spool was truncated",)
        self._final_stream.write(retained)
        self._final_stream.flush()
        self._final_stream.close()
        gaps = [b["monotonic"] - a["monotonic"] for a, b in zip(rows, rows[1:])]
        incomplete = sum(not row["attribution_complete"] for row in rows)
        hard_incomplete = [
            index for index, row in enumerate(rows)
            if not row["attribution_complete"]
        ]
        transition_spans = []
        unbounded_transition = False
        index = 0
        while index < len(rows):
            if rows[index]["attribution_complete"]:
                index += 1
                continue
            start = index
            while index + 1 < len(rows) and not rows[index + 1]["attribution_complete"]:
                index += 1
            end = index
            if start == 0 or end + 1 == len(rows):
                unbounded_transition = True
            else:
                transition_spans.append(
                    rows[end + 1]["monotonic"] - rows[start - 1]["monotonic"]
                )
            index += 1
        peak_row = max(
            (row for row in rows if row["memory_current"] is not None),
            key=lambda row: row["memory_current"],
            default=None,
        )
        observation_sequence = [
            label for row in rows for label in row["observation_labels"]
        ]
        observed_labels = set(observation_sequence)
        required_label_sequence = [
            "baseline_before_worker",
            "workflow_progress_assembling_observed",
            "cancel_requested",
            "post_cleanup_sample",
        ]
        missing_required_labels = sorted(
            set(required_label_sequence) - observed_labels
        )
        required_markers_in_order = False
        if not missing_required_labels:
            cursor = -1
            required_markers_in_order = True
            for label in required_label_sequence:
                try:
                    cursor = observation_sequence.index(label, cursor + 1)
                except ValueError:
                    required_markers_in_order = False
                    break
        complete = (
            bool(rows)
            and not errors
            and not hard_incomplete
            and not missing_required_labels
            and required_markers_in_order
            and peak_row is not None
            and peak_row["attribution_complete"]
            and max(gaps, default=0) <= self.attribution_gap_seconds
        )
        status = "complete" if complete else "incomplete"
        outcome = CollectorOutcome(
            samples=len(rows),
            maximum_gap_seconds=max(gaps, default=0.0),
            attribution_complete=complete,
            status=status,
            errors=errors,
            incomplete_samples=incomplete,
        )
        controller_pss = [row["controller_pss_bytes"] for row in rows]
        known_controller_pss = [value for value in controller_pss if value is not None]
        payload = {
            "samples": outcome.samples,
            "maximum_gap_seconds": outcome.maximum_gap_seconds,
            "attribution_gap_seconds": self.attribution_gap_seconds,
            "attribution_complete": outcome.attribution_complete,
            "status": outcome.status,
            "incomplete_samples": outcome.incomplete_samples,
            "hard_incomplete_sample_indexes": hard_incomplete,
            "required_observation_sequence": required_label_sequence,
            "observed_observation_labels": sorted(observed_labels),
            "missing_required_observation_labels": missing_required_labels,
            "required_observations_in_order": required_markers_in_order,
            "maximum_transition_span_seconds": max(transition_spans, default=0),
            "unbounded_transition": unbounded_transition,
            "peak_sample_attribution_complete": bool(
                peak_row and peak_row["attribution_complete"]
            ),
            "errors": list(outcome.errors),
            "collector_total_sample_wall_seconds": sum(row["sample_duration_seconds"] for row in rows),
            "collector_total_thread_cpu_seconds": sum(row["collector_thread_cpu_seconds"] for row in rows),
            "collector_max_sample_wall_seconds": max((row["sample_duration_seconds"] for row in rows), default=0),
            "collector_output_bytes": self.output.stat().st_size,
            "collector_committed_spool_bytes": committed_bytes,
            "collector_commit_protocol": "flushed spool prefix sealed at stop",
            "collector_retains_compact_in_memory_summary_only": True,
            "controller_pss_baseline_bytes": controller_pss[0] if controller_pss else None,
            "controller_pss_maximum_bytes": max(known_controller_pss, default=None),
            "collector_memory_cost_isolated": False,
            "collector_inprocess_memory_included_in_controller_pss": True,
            "collector_memory_cost_limit": "controller PSS also includes driver allocations",
            "pss_collected_within_sample_window": True,
            "pss_reading_is_atomic": False,
            "pss_class_maxima_are_not_additive": True,
            "diagnostic_unattributed_is_cache": False,
            "guard_source": "unchanged q04 worker telemetry",
        }
        with self.summary.open("x") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        return outcome
