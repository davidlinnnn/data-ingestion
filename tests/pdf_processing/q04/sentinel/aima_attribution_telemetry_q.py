"""Strict Q attribution telemetry with complete process-set transition evidence.

This module reuses the verified ACL cgroup/proc parsers, but tightens process
coverage semantics for a diagnostic run.  A missing process value is ``None``
and makes that sample incomplete; it is never folded into a zero PSS total.
"""

from __future__ import annotations

import copy
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
    if "yolo_fresh_measure.py" in text or "yolo_candidate_window.py" in text:
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
        for path in root.rglob("samples.jsonl"):
            rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            handoff = next(
                (
                    row.get("parser", {})
                    for row in rows
                    if row.get("parser", {}).get("handoffs", 0) > 0
                    and row.get("parser", {}).get("termination_reason")
                    == "fresh_child_handoff"
                ),
                None,
            )
            if handoff is not None:
                markers.append({
                    "key": str(path.relative_to(root)) + ":parser_handoff",
                    "label": "warm_handoff_observed",
                    "meaning": "worker_supervision_sample_after_warm_reap",
                    "handoffs": handoff["handoffs"],
                })
    except (FileNotFoundError, PermissionError, OSError, ValueError, TypeError) as error:
        issues.append({"scope": "worker_samples", "reason": type(error).__name__})
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


def _process_identity(row: dict) -> tuple[int, int] | None:
    pid, start_ticks = row.get("pid"), row.get("start_ticks")
    if type(pid) is not int or type(start_ticks) is not int:
        return None
    return pid, start_ticks


def _cgroup_reading_complete(row: dict) -> bool:
    events = row.get("memory_events")
    stat = row.get("memory_stat")
    pressure = row.get("memory_pressure_raw")
    return (
        type(row.get("memory_current")) is int
        and isinstance(row.get("cgroup"), dict)
        and isinstance(events, dict)
        and all(type(events.get(key)) is int for key in ("oom", "oom_kill", "oom_group_kill"))
        and isinstance(stat, dict)
        and all(type(stat.get(key)) is int for key in MEMORY_STAT_FIELDS)
        and isinstance(pressure, str)
        and any(line.startswith("full ") and "avg10=" in line for line in pressure.splitlines())
    )


def classify_confirmed_exit_transition(
    rows: list[dict], index: int, *, attribution_gap_seconds: float, peak_index: int
) -> dict:
    """Classify one PSS-unknown sample without rewriting its raw facts.

    Qualification may retain continuous cgroup evidence across a proven process
    exit.  The process PSS remains unknown and attribution_complete remains
    false.  PID reuse, read denial, unknown identities and an unattributed peak
    all fail closed.
    """
    failure = lambda reason: {"status": "unclassified", "index": index, "reason": reason}
    if index <= 0 or index + 1 >= len(rows):
        return failure("transition_not_bounded")
    before, current, after = rows[index - 1], rows[index], rows[index + 1]
    if current.get("attribution_complete") is not False:
        return failure("sample_not_process_incomplete")
    if index == peak_index or current.get("memory_current") == rows[peak_index].get("memory_current"):
        return failure("peak_process_attribution_incomplete")
    if not all(_cgroup_reading_complete(row) for row in (before, current, after)):
        return failure("cgroup_reading_incomplete")
    if not (before["cgroup"] == current["cgroup"] == after["cgroup"]):
        return failure("cgroup_identity_changed")
    if any(
        row.get("attribution_complete") is not True
        or row.get("process_coverage", {}).get("status") != "complete"
        for row in (before, after)
    ):
        return failure("adjacent_process_enumeration_incomplete")
    if (
        current["monotonic"] - before["monotonic"] > attribution_gap_seconds
        or after["monotonic"] - current["monotonic"] > attribution_gap_seconds
    ):
        return failure("transition_gap_exceeded")
    unknown_reasons = current.get("process_coverage", {}).get("unknown")
    unknown = [row for row in current.get("processes", []) if row.get("status") != "complete"]
    events = current.get("process_events", []) + after.get("process_events", [])
    if unknown_reasons == [
        {"scope": "process_coverage", "reason": "cgroup_process_read_incomplete"}
    ]:
        if len(unknown) != 1:
            return failure("expected_one_exiting_process")
        exiting = unknown[0]
        identity = _process_identity(exiting)
        if identity is None:
            return failure("exiting_process_identity_missing")
        if exiting.get("reason") not in ("FileNotFoundError", "ProcessLookupError"):
            return failure("exit_read_was_not_process_absence")
    elif (
        {(row.get("scope"), row.get("reason")) for row in unknown_reasons or []}
        == {
            ("process_coverage", "process_set_changed_during_sample"),
            ("process_coverage", "process_transition_read_incomplete"),
        }
        and len(unknown) == 1
    ):
        exiting = unknown[0]
        identity = _process_identity(exiting)
        if identity is None:
            return failure("exiting_process_identity_missing")
        if exiting.get("reason") not in ("FileNotFoundError", "ProcessLookupError"):
            return failure("exit_read_was_not_process_absence")
        before_ids = {
            (row.get("pid"), row.get("start_ticks"))
            for row in current["process_coverage"].get("identities_before", [])
        }
        after_ids = {
            (row.get("pid"), row.get("start_ticks"))
            for row in current["process_coverage"].get("identities_after", [])
        }
        if before_ids - after_ids != {identity} or after_ids - before_ids:
            return failure("exit_membership_transition_not_confirmed")
    elif (
        len(unknown_reasons or []) == 1
        and not unknown
        and unknown_reasons[0].get("scope") == "proc_identity"
        and unknown_reasons[0].get("reason") in ("FileNotFoundError", "ProcessLookupError")
        and type(unknown_reasons[0].get("pid")) is int
    ):
        exits = [
            event for event in events
            if event.get("event") == "exit_observed"
            and event.get("pid") == unknown_reasons[0]["pid"]
            and type(event.get("start_ticks")) is int
        ]
        if len(exits) != 1:
            return failure("matching_exit_not_confirmed")
        identity = exits[0]["pid"], exits[0]["start_ticks"]
    else:
        return failure("unexpected_process_coverage_reason")
    prior = [row for row in before.get("processes", []) if _process_identity(row) == identity]
    if len(prior) != 1 or prior[0].get("status") != "complete":
        return failure("prior_process_identity_not_complete")
    if any(_process_identity(row) == identity for row in after.get("processes", [])):
        return failure("exiting_identity_still_present")
    if any(
        event.get("event") == "pid_reuse_observed" and event.get("pid") == identity[0]
        for event in events
    ):
        return failure("pid_reuse_observed")
    exits = [
        event
        for event in events
        if event.get("event") == "exit_observed"
        and (event.get("pid"), event.get("start_ticks")) == identity
    ]
    if len(exits) != 1:
        return failure("matching_exit_not_confirmed")
    return {
        "status": "classified_confirmed_exit",
        "index": index,
        "pid": identity[0],
        "start_ticks": identity[1],
        "prior_command_class": prior[0].get("command_class"),
        "pss_bytes": None,
        "process_attribution_complete": False,
        "cgroup_readings_complete": True,
    }


def evaluate_handoff_contract(rows: list[dict], observation_root: Path | None) -> dict:
    """Correlate observed identities with the source-bound reap-before-spawn barrier.

    Sampling alone cannot order events within one interval. The worker's retained
    successful reap record and the frozen Execution/WarmParser barrier supply that
    ordering; workflow query observation timing supplies no lifecycle evidence.
    """
    fail = lambda reason: {"complete": False, "reason": reason}
    if observation_root is None:
        return fail("observation_root_missing")
    try:
        worker_rows = [json.loads(line) for path in observation_root.glob('worker-*/samples.jsonl')
                       for line in path.read_text().splitlines() if line]
    except (OSError, ValueError):
        return fail("worker_reap_evidence_unreadable")
    warm = {_process_identity(p): p for row in rows for p in row['processes']
            if p.get('command_class') == 'warm_parser' and p.get('status') == 'complete'}
    if not warm or None in warm:
        return fail("warm_identity_missing")
    proofs = []
    events = [(i, e) for i, row in enumerate(rows) for e in row['process_events']]
    for identity, process in warm.items():
        pid, ticks = identity
        if any(e.get('event') == 'pid_reuse_observed' and e.get('pid') == pid for _, e in events):
            return fail("warm_pid_reused")
        exits = [i for i, e in events if e.get('event') == 'exit_observed'
                 and (e.get('pid'), e.get('start_ticks')) == identity]
        births = [(i, e) for i, e in events if e.get('event') == 'birth_observed'
                  and e.get('command_class') == 'fresh_parse_child'
                  and any(p.get('pid') == e['pid'] and p.get('start_ticks') == e['start_ticks']
                          and p.get('ppid') == process['ppid'] for p in rows[i]['processes'])]
        if len(exits) != 1 or len(births) != 1 or exits[0] > births[0][0]:
            return fail("handoff_process_boundary_unproven")
        index, birth = births[0]
        if any(_process_identity(p) == identity for row in rows[index:] for p in row['processes']):
            return fail("warm_present_at_or_after_fresh_birth")
        reaped = any(r.get('worker_pid') == process['ppid']
                     and r.get('parser', {}).get('pid') == pid
                     and r['parser'].get('termination_reason') == 'fresh_child_handoff'
                     and r['parser'].get('ready') is False
                     and type(r['parser'].get('exit_code')) is int
                     and not r['parser'].get('reap_failed') for r in worker_rows)
        if not reaped:
            return fail("successful_worker_reap_record_missing")
        proofs.append({'warm_pid': pid, 'warm_start_ticks': ticks, 'fresh_pid': birth['pid'],
                       'fresh_start_ticks': birth['start_ticks'], 'exit_sample': exits[0], 'birth_sample': index})
    return {'complete': True, 'status': 'source_bound_handoff_verified', 'handoffs': proofs,
            'sub_sample_order_measured': False, 'ordering_authority': 'frozen reap-before-spawn barrier plus successful worker reap record'}


def evaluate_warm_continuity_contract(
    rows: list[dict], observation_root: Path | None
) -> dict:
    """Prove native capture and restore shared one parser, then exited."""
    fail = lambda reason: {"complete": False, "reason": reason}
    if observation_root is None:
        return fail("observation_root_missing")
    try:
        accepted = json.loads((observation_root / "fresh-08/accepted.json").read_text())
        stopped = [
            json.loads(path.read_text())
            for path in observation_root.glob("worker-*/stopped.json")
        ]
    except (OSError, ValueError, TypeError, KeyError):
        return fail("warm_continuity_evidence_unreadable")
    steps = [
        step
        for step in accepted.get("result", {}).get("steps", [])
        if step.get("stage") in ("group", "assembly")
        and step.get("reused") is False
    ]
    parsers = [step.get("parser") for step in steps]
    if (
        [step.get("stage") for step in steps] != ["group"] * 3 + ["assembly"]
        or any(not isinstance(parser, dict) for parser in parsers)
    ):
        return fail("capture_restore_parser_records_missing")
    pids = {parser.get("pid") for parser in parsers}
    request_ids = {parser.get("request_id") for parser in parsers}
    if len(pids) != 1 or None in pids or len(request_ids) != 4 or None in request_ids:
        return fail("capture_restore_process_continuity_missing")
    if any(
        parser.get("ready") is not True
        or parser.get("restarts") != 1
        or parser.get("handoffs") != 0
        or parser.get("termination_reason") is not None
        for parser in parsers
    ):
        return fail("capture_restore_parser_state_invalid")
    pid = next(iter(pids))
    identities = {
        _process_identity(process)
        for row in rows
        for process in row.get("processes", [])
        if process.get("pid") == pid
        and process.get("command_class") == "warm_parser"
        and process.get("status") == "complete"
    }
    identities.discard(None)
    if len(identities) != 1:
        return fail("warm_parser_identity_not_unique")
    identity = next(iter(identities))
    events = [event for row in rows for event in row.get("process_events", [])]
    exits = [
        event
        for event in events
        if event.get("event") == "exit_observed"
        and (event.get("pid"), event.get("start_ticks")) == identity
    ]
    if (
        len(exits) != 1
        or any(
            event.get("event") == "pid_reuse_observed" and event.get("pid") == pid
            for event in events
        )
        or not stopped
        or not all(
            row.get("parser_absent") and row.get("scratch_absent") for row in stopped
        )
        or rows[-1].get("warm_parser_present")
    ):
        return fail("warm_parser_final_exit_unproven")
    return {
        "complete": True,
        "status": "native_capture_restore_same_process_then_reaped",
        "pid": pid,
        "start_ticks": identity[1],
        "requests": 4,
        "captures": 3,
        "restores": 1,
    }


def evaluate_parser_lifecycle_contract(
    rows: list[dict], observation_root: Path | None, *, require_recycle_exit: bool
) -> dict:
    if not require_recycle_exit:
        return {"status": "not_required", "complete": True}
    if observation_root is None:
        return {"status": "incomplete", "complete": False, "reason": "observation_root_missing"}
    accepted_path = observation_root / "fresh-07/accepted.json"
    try:
        accepted = json.loads(accepted_path.read_text())
    except (FileNotFoundError, PermissionError, OSError, ValueError, TypeError) as error:
        return {"status": "incomplete", "complete": False, "reason": type(error).__name__}
    groups = [step for step in accepted.get("result", {}).get("steps", []) if step.get("stage") == "group"]
    parsers = [step.get("parser") for step in groups if step.get("reused") is False]
    if len(groups) != 3 or len(parsers) != 3 or any(not isinstance(row, dict) for row in parsers):
        return {"status": "incomplete", "complete": False, "reason": "fresh_group_parser_records_missing"}
    if any(
        row.get("termination_reason") != "request_recycle"
        or row.get("ready") is not False
        or type(row.get("pid")) is not int
        for row in parsers
    ):
        return {"status": "incomplete", "complete": False, "reason": "request_recycle_record_invalid"}
    pids = [row["pid"] for row in parsers]
    if len(set(pids)) != len(pids):
        return {"status": "incomplete", "complete": False, "reason": "parser_pid_reused_across_groups"}
    assembly_indexes = [
        index
        for index, row in enumerate(rows)
        if "workflow_progress_assembling_observed" in row.get("observation_labels", [])
    ]
    if len(assembly_indexes) != 1:
        return {"status": "incomplete", "complete": False, "reason": "assembly_observation_ambiguous"}
    assembly_index = assembly_indexes[0]
    identities = {}
    for pid in pids:
        seen = {
            _process_identity(process)
            for row in rows[: assembly_index + 1]
            for process in row.get("processes", [])
            if process.get("pid") == pid
            and process.get("command_class") == "warm_parser"
            and process.get("status") == "complete"
        }
        seen.discard(None)
        if len(seen) != 1:
            return {"status": "incomplete", "complete": False, "reason": "parser_identity_not_uniquely_observed", "pid": pid}
        identities[pid] = next(iter(seen))
    all_events = [event for row in rows for event in row.get("process_events", [])]
    exits = []
    for pid, identity in identities.items():
        if any(event.get("event") == "pid_reuse_observed" and event.get("pid") == pid for event in all_events):
            return {"status": "incomplete", "complete": False, "reason": "parser_pid_reuse_observed", "pid": pid}
        matching = [
            (index, event)
            for index, row in enumerate(rows)
            for event in row.get("process_events", [])
            if event.get("event") == "exit_observed"
            and (event.get("pid"), event.get("start_ticks")) == identity
        ]
        if len(matching) != 1 or matching[0][0] >= assembly_index:
            return {"status": "incomplete", "complete": False, "reason": "parser_exit_not_confirmed_before_assembly", "pid": pid}
        exits.append({"pid": pid, "start_ticks": identity[1], "sample_index": matching[0][0]})
    if any(row.get("warm_parser_present") for row in rows[assembly_index:]):
        return {"status": "incomplete", "complete": False, "reason": "warm_parser_present_at_or_after_assembly"}
    return {
        "status": "complete_request_recycle_exit",
        "complete": True,
        "assembly_sample_index": assembly_index,
        "parser_exits": exits,
        "handoff_required": False,
    }


def _strict_attribution_sample_once(
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
            "identities_before": [
                {"pid": pid, "ppid": row["ppid"], "start_ticks": row["start_ticks"]}
                for pid, row in sorted(before.items())
            ],
            "identities_after": [
                {"pid": pid, "ppid": row["ppid"], "start_ticks": row["start_ticks"]}
                for pid, row in sorted(after.items())
            ],
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


def strict_attribution_sample(**kwargs) -> dict:
    """Capture one sample, retrying one whole transient identity read safely."""
    first = _strict_attribution_sample_once(**kwargs)
    unknown = first["process_coverage"]["unknown"]
    transient_reasons = {
        ("process_coverage", "cgroup_process_read_incomplete"),
        ("process_coverage", "process_set_changed_during_sample"),
        ("process_coverage", "process_transition_read_incomplete"),
    }
    incomplete_processes = [
        row for row in first["processes"] if row.get("status") != "complete"
    ]
    transient_churn = bool(unknown) and all(
        (
            issue.get("scope") == "proc_identity"
            and issue.get("reason") in ("FileNotFoundError", "ProcessLookupError")
        )
        or (issue.get("scope"), issue.get("reason")) in transient_reasons
        for issue in unknown
    ) and all(
        row.get("reason") in ("FileNotFoundError", "ProcessLookupError")
        for row in incomplete_processes
    )
    if not transient_churn:
        return first
    retry = _strict_attribution_sample_once(**kwargs)
    observations = {"first": copy.deepcopy(first), "retry": copy.deepcopy(retry)}
    def full_psi(row):
        try:
            line = next(
                line for line in row["memory_pressure_raw"].splitlines()
                if line.startswith("full ")
            )
            return float(next(field for field in line.split() if field.startswith("avg10=")).split("=", 1)[1])
        except (AttributeError, KeyError, StopIteration, ValueError):
            return None

    first_psi = full_psi(first)
    retry_psi = full_psi(retry)
    event_keys = set(first["memory_events"]) | set(retry["memory_events"])
    guards_do_not_decrease = (
        first_psi is not None
        and retry_psi is not None
        and retry_psi >= first_psi
        and all(
            type(first["memory_events"].get(key)) is int
            and type(retry["memory_events"].get(key)) is int
            and retry["memory_events"][key] >= first["memory_events"][key]
            for key in event_keys
        )
    )
    retry_safe = (
        retry["attribution_complete"]
        and type(first.get("memory_current")) is int
        and type(retry.get("memory_current")) is int
        and retry["memory_current"] >= first["memory_current"]
        and guards_do_not_decrease
    )
    evidence = {
        "reason": "transient_process_churn",
        "observations": observations,
        "discarded_memory_current": first.get("memory_current"),
        "retry_memory_current": retry.get("memory_current"),
        "discarded_memory_events": first["memory_events"],
        "retry_memory_events": retry["memory_events"],
        "discarded_memory_pressure_raw": first["memory_pressure_raw"],
        "retry_memory_pressure_raw": retry["memory_pressure_raw"],
        "retry_attribution_complete": retry["attribution_complete"],
        "accepted": retry_safe,
    }
    if retry_safe:
        retry["sample_duration_seconds"] += first["sample_duration_seconds"]
        retry["collector_thread_cpu_seconds"] += first["collector_thread_cpu_seconds"]
        retry["identity_resample"] = evidence
        return retry
    first["process_coverage"]["unknown"].extend({
        "scope": "identity_resample_retry",
        "reason": "retry_incomplete",
        "detail": issue,
    } for issue in retry["process_coverage"]["unknown"])
    values = [
        value for value in (first.get("memory_current"), retry.get("memory_current"))
        if type(value) is int
    ]
    first["memory_current"] = max(values, default=None)
    first["memory_events"] = {
        key: max(
            value for value in (
                first["memory_events"].get(key), retry["memory_events"].get(key)
            ) if type(value) is int
        )
        for key in event_keys
    }
    if retry_psi is not None and (first_psi is None or retry_psi > first_psi):
        first["memory_pressure_raw"] = retry["memory_pressure_raw"]
    first["monotonic"] = retry["monotonic"]
    first["time"] = retry["time"]
    first["sample_duration_seconds"] += retry["sample_duration_seconds"]
    first["collector_thread_cpu_seconds"] += retry["collector_thread_cpu_seconds"]
    first["identity_resample"] = evidence
    return first


@dataclass(frozen=True)
class CollectorOutcome:
    samples: int
    maximum_gap_seconds: float
    attribution_complete: bool
    qualification_complete: bool
    cgroup_resource_complete: bool
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
                    "cgroup": row["cgroup"],
                    "attribution_complete": row["attribution_complete"],
                    "process_coverage": row["process_coverage"],
                    "processes": [
                        {
                            key: process.get(key)
                            for key in (
                                "pid", "ppid", "start_ticks", "ownership",
                                "status", "reason", "command_class", "pss_bytes",
                            )
                        }
                        for process in row["processes"]
                    ],
                    "process_events": row["process_events"],
                    "memory_current": row["memory_current"],
                    "memory_events": row["memory_events"],
                    "memory_stat": row["memory_stat"],
                    "memory_pressure_raw": row["memory_pressure_raw"],
                    "sample_duration_seconds": row["sample_duration_seconds"],
                    "collector_thread_cpu_seconds": row["collector_thread_cpu_seconds"],
                    "controller_pss_bytes": controller_pss,
                    "warm_parser_present": any(
                        process.get("ownership") == "owned"
                        and process.get("command_class") == "warm_parser"
                        for process in row["processes"]
                    ),
                    "fresh_parse_present": any(
                        process.get("ownership") == "owned"
                        and process.get("command_class") == "fresh_parse_child"
                        for process in row["processes"]
                    ),
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

    def stop(
        self,
        *,
        expect_cancel: bool = True,
        require_handoff: bool = False,
        require_recycle_exit: bool = False,
        require_warm_continuity: bool = False,
        require_no_warm_fresh_overlap: bool = False,
    ) -> CollectorOutcome:
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
        peak_index = max(
            range(len(rows)),
            key=lambda item: rows[item]["memory_current"]
            if type(rows[item]["memory_current"]) is int
            else -1,
            default=None,
        )
        peak_row = None if peak_index is None else rows[peak_index]
        transition_classifications = []
        if peak_index is not None:
            transition_classifications = [
                classify_confirmed_exit_transition(
                    rows,
                    item,
                    attribution_gap_seconds=self.attribution_gap_seconds,
                    peak_index=peak_index,
                )
                for item in hard_incomplete
            ]
        classified_transition_indexes = [
            item["index"]
            for item in transition_classifications
            if item["status"] == "classified_confirmed_exit"
        ]
        unclassified_incomplete = sorted(
            set(hard_incomplete) - set(classified_transition_indexes)
        )
        observation_sequence = [
            label for row in rows for label in row["observation_labels"]
        ]
        observed_labels = set(observation_sequence)
        required_label_sequence = ["baseline_before_worker"]
        # Query visibility can lag process birth; it is not an Activity boundary.
        if require_handoff:
            required_label_sequence.append("warm_handoff_observed")
        if expect_cancel:
            required_label_sequence.append("cancel_requested")
        required_label_sequence.append("post_cleanup_sample")
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
        overlap_sample_indexes = [
            index
            for index, row in enumerate(rows)
            if row["warm_parser_present"] and row["fresh_parse_present"]
        ]
        no_warm_fresh_overlap = not overlap_sample_indexes
        parser_lifecycle = evaluate_parser_lifecycle_contract(
            rows,
            self.observation_root,
            require_recycle_exit=require_recycle_exit,
        )
        if require_handoff:
            parser_lifecycle = evaluate_handoff_contract(rows, self.observation_root)
        if require_warm_continuity:
            parser_lifecycle = evaluate_warm_continuity_contract(
                rows, self.observation_root
            )
        process_attribution_complete = not hard_incomplete
        cgroup_resource_complete = (
            bool(rows)
            and all(_cgroup_reading_complete(row) for row in rows)
            and not unclassified_incomplete
            and max(gaps, default=0) <= self.attribution_gap_seconds
        )
        qualification_complete = (
            bool(rows)
            and not errors
            and cgroup_resource_complete
            and not missing_required_labels
            and required_markers_in_order
            and peak_row is not None
            and peak_row["attribution_complete"]
            and parser_lifecycle["complete"]
            and (no_warm_fresh_overlap or not require_no_warm_fresh_overlap)
        )
        attribution_complete = qualification_complete and process_attribution_complete
        status = (
            "complete"
            if attribution_complete
            else "qualification_complete_process_attribution_incomplete"
            if qualification_complete
            else "incomplete"
        )
        outcome = CollectorOutcome(
            samples=len(rows),
            maximum_gap_seconds=max(gaps, default=0.0),
            attribution_complete=attribution_complete,
            qualification_complete=qualification_complete,
            cgroup_resource_complete=cgroup_resource_complete,
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
            "process_attribution_complete": process_attribution_complete,
            "qualification_complete": outcome.qualification_complete,
            "cgroup_resource_complete": outcome.cgroup_resource_complete,
            "status": outcome.status,
            "incomplete_samples": outcome.incomplete_samples,
            "hard_incomplete_sample_indexes": hard_incomplete,
            "classified_cgroup_transition_sample_indexes": classified_transition_indexes,
            "unclassified_incomplete_sample_indexes": unclassified_incomplete,
            "transition_classifications": transition_classifications,
            "required_observation_sequence": required_label_sequence,
            "observed_observation_labels": sorted(observed_labels),
            "missing_required_observation_labels": missing_required_labels,
            "required_observations_in_order": required_markers_in_order,
            "measurement_contract": "guard_failure" if expect_cancel else "successful_workload",
            "warm_continuity_required": require_warm_continuity,
            "cancel_observation_required": expect_cancel,
            "handoff_observation_required": require_handoff,
            "request_recycle_exit_required": require_recycle_exit,
            "parser_lifecycle_contract": parser_lifecycle,
            "no_warm_fresh_overlap_required": require_no_warm_fresh_overlap,
            "no_warm_fresh_overlap": no_warm_fresh_overlap,
            "warm_fresh_overlap_sample_indexes": overlap_sample_indexes,
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
