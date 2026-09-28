"""Q keeps unknown PSS unknown and records both process enumerations."""

import asyncio
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from sentinel import aima_attribution_telemetry_q as telemetry


class ProcessTransitionEvidenceTest(unittest.TestCase):
    def test_lifecycle_wrapper_preserves_fresh_parse_classification(self):
        command = (
            b"python\0-m\0pdf_processing.lifecycle_child\0pdf_processing.parse\0"
        )
        self.assertEqual(telemetry._command_class(command), "fresh_parse_child")

    def test_collector_lifecycle_lock_wait_is_bounded_before_sampling(self):
        import fcntl
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            lock_path = root / "lifecycle.lock"
            sampler = mock.Mock()
            collector = telemetry.StrictAttributionCollector(
                root / "samples.jsonl",
                root / "summary.json",
                shutdown_timeout_seconds=.02,
                lifecycle_lock_path=lock_path,
                sampler=sampler,
            )
            collector.identity = {}
            collector._stream = object()
            with lock_path.open("a") as held:
                fcntl.flock(held, fcntl.LOCK_EX)
                with self.assertRaisesRegex(
                    RuntimeError, "process lifecycle lock timed out"
                ):
                    collector._capture()
            sampler.assert_not_called()

    @unittest.skipUnless(
        Path("/sys/fs/cgroup/memory.current").is_file(),
        "requires Linux cgroup v2",
    )
    def test_linux_child_shutdown_keeps_complete_samples_and_outer_observer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            collector = telemetry.StrictAttributionCollector(
                root / "samples.jsonl",
                root / "summary.json",
                root_pid=os.getpid(),
                interval_seconds=0.02,
                attribution_gap_seconds=0.5,
                shutdown_timeout_seconds=0.5,
            )
            outer_stop = threading.Event()
            outer_samples = []

            def observe_cgroup():
                while not outer_stop.wait(0.002):
                    outer_samples.append(
                        int(Path("/sys/fs/cgroup/memory.current").read_text())
                    )

            observer = threading.Thread(target=observe_cgroup)
            observer.start()
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
            collector.start()
            time.sleep(0.05)

            async def shutdown():
                child.terminate()
                await asyncio.to_thread(child.wait, 1)

            asyncio.run(collector.process_transition("child_shutdown", shutdown))
            outcome = collector.stop(expect_cancel=False)
            outer_stop.set()
            observer.join(1)
            summary = json.loads((root / "summary.json").read_text())

        self.assertTrue(outcome.attribution_complete)
        self.assertTrue(outer_samples)
        self.assertTrue(
            summary["process_transition_windows"][0]["sampler_lock_acquired"]
        )

    def test_controlled_process_transition_preserves_shutdown_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = telemetry.StrictAttributionCollector(
                Path(tmp) / "samples.jsonl",
                Path(tmp) / "summary.json",
            )
            collector._stream = object()
            collector._last_completed = 1.0

            async def shutdown():
                def failed_capture():
                    with collector._capture_lock:
                        with collector._lock:
                            collector._errors.append("capture failed")
                            collector._last_completed = 2.0

                threading.Thread(target=failed_capture).start()
                raise ValueError("shutdown failed")

            with self.assertRaisesRegex(ValueError, "shutdown failed"):
                asyncio.run(collector.process_transition("worker_shutdown", shutdown))

        self.assertEqual(
            collector._process_transition_windows[0]["label"], "worker_shutdown"
        )

    def test_sampler_lock_timeout_does_not_block_worker_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = telemetry.StrictAttributionCollector(
                Path(tmp) / "samples.jsonl",
                Path(tmp) / "summary.json",
                shutdown_timeout_seconds=0.01,
            )
            collector._stream = object()
            collector._capture_lock.acquire()
            stopped = []

            async def shutdown():
                stopped.append(True)

            try:
                with self.assertRaisesRegex(RuntimeError, "sampler lock timed out"):
                    asyncio.run(collector.process_transition("worker_shutdown", shutdown))
            finally:
                collector._capture_lock.release()

        self.assertEqual(stopped, [True])

    def test_transition_keeps_sampler_out_and_enforces_existing_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = telemetry.StrictAttributionCollector(
                Path(tmp) / "samples.jsonl",
                Path(tmp) / "summary.json",
                attribution_gap_seconds=0.005,
            )
            collector._stream = object()
            collector._last_completed = 1.0
            competing_capture_entered = threading.Event()
            outer_samples = []

            def competing_capture():
                with collector._capture_lock:
                    with collector._lock:
                        collector._last_completed = 2.0
                    competing_capture_entered.set()

            async def shutdown():
                thread = threading.Thread(target=competing_capture)
                thread.start()
                for _ in range(3):
                    outer_samples.append(time.monotonic())
                    await asyncio.sleep(0.003)
                self.assertFalse(competing_capture_entered.is_set())
                return thread

            with self.assertRaisesRegex(RuntimeError, "window exceeded"):
                asyncio.run(collector.process_transition("worker_shutdown", shutdown))

        self.assertGreaterEqual(len(outer_samples), 3)
        self.assertTrue(competing_capture_entered.wait(1))

    def test_cancelled_lock_wait_cannot_leave_sampler_lock_acquired(self):
        with tempfile.TemporaryDirectory() as tmp:
            collector = telemetry.StrictAttributionCollector(
                Path(tmp) / "samples.jsonl",
                Path(tmp) / "summary.json",
                shutdown_timeout_seconds=0.2,
            )
            collector._stream = object()
            collector._capture_lock.acquire()

            async def scenario():
                task = asyncio.create_task(collector.process_transition(
                    "worker_shutdown", lambda: asyncio.sleep(0)
                ))
                await asyncio.sleep(0.01)
                task.cancel()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                collector._capture_lock.release()

            asyncio.run(scenario())

        self.assertTrue(collector._capture_lock.acquire(timeout=0.1))
        collector._capture_lock.release()

    def test_short_lived_owned_descendants_are_read_first(self):
        identities = {
            20: {"pid": 20, "ppid": 1, "start_ticks": 20},
            21: {"pid": 21, "ppid": 20, "start_ticks": 21},
            22: {"pid": 22, "ppid": 21, "start_ticks": 22},
            5: {"pid": 5, "ppid": 1, "start_ticks": 5},
        }
        owned = telemetry._owned(identities, 20)

        ordered = telemetry._process_read_order(identities, owned, 20)

        self.assertEqual([pid for pid, _row in ordered], [22, 21, 20, 5])

    def test_transient_identity_exit_is_rescanned_before_sample_is_sealed(self):
        stable = {
            100: {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"},
        }
        vanished = [{
            "pid": 1887,
            "scope": "proc_identity",
            "reason": "FileNotFoundError",
        }]

        def read_text(path):
            return {
                "memory.current": "1000\n",
                "memory.events": "oom 0\noom_kill 0\noom_group_kill 0\n",
                "memory.stat": "".join(
                    f"{key} 0\n" for key in telemetry.MEMORY_STAT_FIELDS
                ),
                "memory.pressure": "full avg10=0.00 total=0\n",
            }[path.name]

        process = {
            **stable[100],
            "ownership": "owned",
            "status": "complete",
            "command_class": "worker",
            "pss_bytes": 10,
        }
        monotonic = iter((0.0, 1.0, 2.0, 4.0))
        thread_time = iter((0.0, 0.1, 0.2, 0.5))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            telemetry, "cgroup_identity", return_value={"proc_cgroup": "0::/"}
        ), mock.patch.object(
            telemetry,
            "_scan_identities",
            side_effect=[(stable, vanished), (stable, []), (stable, []), (stable, [])],
        ), mock.patch.object(telemetry, "_read_process", return_value=process):
            row = telemetry.strict_attribution_sample(
                root_pid=100,
                expected_cgroup={"proc_cgroup": "0::/"},
                proc_root=Path(tmp) / "proc",
                cgroup_root=Path(tmp) / "cgroup",
                read_text=read_text,
                read_bytes=lambda _path: b"",
                monotonic=lambda: next(monotonic),
                thread_time=lambda: next(thread_time),
            )

        self.assertTrue(row["attribution_complete"])
        self.assertEqual(row["process_coverage"]["unknown"], [])
        self.assertEqual(row["process_coverage"]["enumerated_before"], 1)
        self.assertTrue(row["identity_resample"]["accepted"])
        self.assertEqual(row["sample_duration_seconds"], 3.0)
        self.assertAlmostEqual(row["collector_thread_cpu_seconds"], 0.4)
        observations = row["identity_resample"]["observations"]
        self.assertEqual(observations["first"]["process_coverage"]["unknown"], vanished)
        self.assertEqual(observations["retry"]["process_coverage"]["unknown"], [])
        self.assertEqual(observations["first"]["monotonic"], 1.0)
        self.assertEqual(observations["retry"]["monotonic"], 4.0)

    def test_transient_rescan_cannot_hide_a_higher_unattributed_reading(self):
        stable = {
            100: {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"},
        }
        vanished = [{
            "pid": 1887,
            "scope": "proc_identity",
            "reason": "FileNotFoundError",
        }]
        memory_current = iter(("2000\n", "1000\n"))

        def read_text(path):
            if path.name == "memory.current":
                return next(memory_current)
            return {
                "memory.events": "oom 0\noom_kill 0\noom_group_kill 0\n",
                "memory.stat": "".join(
                    f"{key} 0\n" for key in telemetry.MEMORY_STAT_FIELDS
                ),
                "memory.pressure": "full avg10=0.00 total=0\n",
            }[path.name]

        process = {
            **stable[100],
            "ownership": "owned",
            "status": "complete",
            "command_class": "worker",
            "pss_bytes": 10,
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            telemetry, "cgroup_identity", return_value={"proc_cgroup": "0::/"}
        ), mock.patch.object(
            telemetry,
            "_scan_identities",
            side_effect=[(stable, vanished), (stable, []), (stable, []), (stable, [])],
        ), mock.patch.object(telemetry, "_read_process", return_value=process):
            row = telemetry.strict_attribution_sample(
                root_pid=100,
                expected_cgroup={"proc_cgroup": "0::/"},
                proc_root=Path(tmp) / "proc",
                cgroup_root=Path(tmp) / "cgroup",
                read_text=read_text,
                read_bytes=lambda _path: b"",
            )

        self.assertFalse(row["attribution_complete"])
        self.assertEqual(row["memory_current"], 2000)
        self.assertFalse(row["identity_resample"]["accepted"])

    def test_transient_rescan_preserves_higher_permission_failure_as_peak(self):
        stable = {
            100: {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"},
        }
        vanished = [{
            "pid": 1887,
            "scope": "proc_identity",
            "reason": "FileNotFoundError",
        }]
        denied = [{
            "pid": 1948,
            "scope": "proc_identity",
            "reason": "PermissionError",
        }]
        memory_current = iter(("1000\n", "2000\n"))

        def read_text(path):
            if path.name == "memory.current":
                return next(memory_current)
            return {
                "memory.events": "oom 0\noom_kill 0\noom_group_kill 0\n",
                "memory.stat": "".join(
                    f"{key} 0\n" for key in telemetry.MEMORY_STAT_FIELDS
                ),
                "memory.pressure": "full avg10=0.00 total=0\n",
            }[path.name]

        process = {
            **stable[100],
            "ownership": "owned",
            "status": "complete",
            "command_class": "worker",
            "pss_bytes": 10,
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            telemetry, "cgroup_identity", return_value={"proc_cgroup": "0::/"}
        ), mock.patch.object(
            telemetry,
            "_scan_identities",
            side_effect=[
                (stable, vanished), (stable, []),
                (stable, denied), (stable, []),
            ],
        ), mock.patch.object(telemetry, "_read_process", return_value=process):
            row = telemetry.strict_attribution_sample(
                root_pid=100,
                expected_cgroup={"proc_cgroup": "0::/"},
                proc_root=Path(tmp) / "proc",
                cgroup_root=Path(tmp) / "cgroup",
                read_text=read_text,
                read_bytes=lambda _path: b"",
            )

        self.assertFalse(row["attribution_complete"])
        self.assertEqual(row["memory_current"], 2000)
        self.assertFalse(row["identity_resample"]["retry_attribution_complete"])
        self.assertEqual(
            row["process_coverage"]["unknown"][-1]["detail"], denied[0]
        )

    def test_transient_rescan_cannot_hide_first_psi_pressure(self):
        stable = {
            100: {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"},
        }
        vanished = [{
            "pid": 1887,
            "scope": "proc_identity",
            "reason": "FileNotFoundError",
        }]
        pressure = iter((
            "full avg10=0.25 total=100\n",
            "full avg10=0.00 total=100\n",
        ))

        def read_text(path):
            if path.name == "memory.pressure":
                return next(pressure)
            return {
                "memory.current": "1000\n",
                "memory.events": "oom 0\noom_kill 0\noom_group_kill 0\n",
                "memory.stat": "".join(
                    f"{key} 0\n" for key in telemetry.MEMORY_STAT_FIELDS
                ),
            }[path.name]

        process = {
            **stable[100],
            "ownership": "owned",
            "status": "complete",
            "command_class": "worker",
            "pss_bytes": 10,
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            telemetry, "cgroup_identity", return_value={"proc_cgroup": "0::/"}
        ), mock.patch.object(
            telemetry,
            "_scan_identities",
            side_effect=[(stable, vanished), (stable, []), (stable, []), (stable, [])],
        ), mock.patch.object(telemetry, "_read_process", return_value=process):
            row = telemetry.strict_attribution_sample(
                root_pid=100,
                expected_cgroup={"proc_cgroup": "0::/"},
                proc_root=Path(tmp) / "proc",
                cgroup_root=Path(tmp) / "cgroup",
                read_text=read_text,
                read_bytes=lambda _path: b"",
            )

        self.assertFalse(row["attribution_complete"])
        self.assertIn("avg10=0.25", row["memory_pressure_raw"])
        self.assertFalse(row["identity_resample"]["accepted"])

    def test_disappeared_child_identity_is_a_bounded_confirmed_exit(self):
        process = {
            "pid": 1887,
            "ppid": 112,
            "start_ticks": 17906968,
            "command_class": "fresh_owned_child",
            "status": "complete",
        }

        def row(monotonic, processes, *, complete=True, unknown=None, events=None):
            identities = [
                {key: process[key] for key in ("pid", "ppid", "start_ticks")}
                for process in processes
            ]
            return {
                "monotonic": monotonic,
                "memory_current": 100,
                "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
                "memory_stat": {key: 0 for key in telemetry.MEMORY_STAT_FIELDS},
                "memory_pressure_raw": "full avg10=0.00 total=0\n",
                "cgroup": {"device": 1, "inode": 2},
                "attribution_complete": complete,
                "processes": processes,
                "process_events": events or [],
                "process_coverage": {
                    "status": "complete" if complete else "incomplete",
                    "identities_before": identities,
                    "identities_after": identities,
                    "unknown": unknown or [],
                },
            }

        rows = [
            row(1.0, [process]),
            row(
                1.25,
                [],
                complete=False,
                unknown=[{
                    "pid": 1887,
                    "scope": "proc_identity",
                    "reason": "FileNotFoundError",
                }],
                events=[{
                    "event": "exit_observed",
                    "pid": 1887,
                    "start_ticks": 17906968,
                    "command_class": "fresh_owned_child",
                }],
            ),
            row(1.5, []),
        ]
        rows[1]["memory_current"] = 90
        rows[2]["memory_current"] = 80
        result = telemetry.classify_confirmed_exit_transition(
            rows, 1, attribution_gap_seconds=1.0, peak_index=0
        )
        self.assertEqual(result["status"], "classified_confirmed_exit")
        self.assertEqual(result["prior_command_class"], "fresh_owned_child")

    def test_changed_membership_persists_exact_before_and_after_identities(self):
        before = {
            100: {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"},
            101: {"pid": 101, "ppid": 100, "start_ticks": 1001, "state": "S"},
        }
        after = {
            **before,
            102: {"pid": 102, "ppid": 101, "start_ticks": 1002, "state": "R"},
        }

        def read_text(path):
            return {
                "memory.current": "1000\n",
                "memory.events": "oom_kill 0\n",
                "memory.stat": (
                    "anon 1\nfile 1\nshmem 0\nfile_mapped 0\n"
                    "inactive_file 0\nslab 1\nkernel 1\n"
                ),
                "memory.pressure": "some avg10=0.00 total=0\nfull avg10=0.00 total=0\n",
            }[path.name]

        def process(_proc, identity, _text, _bytes, owned):
            return {
                **identity,
                "ownership": "owned" if owned else "shared_cgroup_other",
                "status": "complete",
                "command_class": "worker",
                "pss_bytes": 10,
            }

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            telemetry, "cgroup_identity", return_value={"proc_cgroup": "0::/"}
        ), mock.patch.object(
            telemetry,
            "_scan_identities",
            side_effect=[
                (before, []), (after, []),
                (after, []), (after, []),
            ],
        ), mock.patch.object(telemetry, "_read_process", side_effect=process):
            row = telemetry.strict_attribution_sample(
                root_pid=100,
                expected_cgroup={"proc_cgroup": "0::/"},
                proc_root=Path(tmp) / "proc",
                cgroup_root=Path(tmp) / "cgroup",
                read_text=read_text,
                read_bytes=lambda _path: b"",
            )

        coverage = row["process_coverage"]
        self.assertTrue(row["attribution_complete"])
        self.assertEqual(row["owned_pss_total_bytes"], 30)
        self.assertTrue(row["identity_resample"]["accepted"])
        first = row["identity_resample"]["observations"]["first"]
        coverage = first["process_coverage"]
        self.assertEqual(
            coverage["identities_before"],
            [
                {"pid": 100, "ppid": 1, "start_ticks": 1000},
                {"pid": 101, "ppid": 100, "start_ticks": 1001},
            ],
        )
        self.assertEqual(
            coverage["identities_after"],
            coverage["identities_before"]
            + [{"pid": 102, "ppid": 101, "start_ticks": 1002}],
        )

    def test_exit_during_sample_is_retried_and_remains_classifiable(self):
        worker = {"pid": 100, "ppid": 1, "start_ticks": 1000, "state": "S"}
        child = {"pid": 101, "ppid": 100, "start_ticks": 1001, "state": "R"}
        before = {100: worker, 101: child}
        after = {100: worker}
        memory_current = iter((2000, 1000))

        first = {
            **child,
            "ownership": "owned",
            "status": "unknown",
            "reason": "FileNotFoundError",
            "command_class": "fresh_owned_child",
            "pss_bytes": None,
        }
        complete = {
            **worker,
            "ownership": "owned",
            "status": "complete",
            "command_class": "worker",
            "pss_bytes": 10,
        }
        with mock.patch.object(
            telemetry, "_strict_attribution_sample_once", side_effect=[
                {
                    "monotonic": 1.25,
                    "time": 1.25,
                    "sample_duration_seconds": 0.1,
                    "collector_thread_cpu_seconds": 0.01,
                    "cgroup": {"device": 1, "inode": 2},
                    "memory_current": next(memory_current),
                    "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
                    "memory_stat": {key: 0 for key in telemetry.MEMORY_STAT_FIELDS},
                    "memory_pressure_raw": "full avg10=0.00 total=0\n",
                    "processes": [complete, first],
                    "process_events": [],
                    "process_coverage": {
                        "status": "incomplete",
                        "identities_before": [worker, child],
                        "identities_after": [worker],
                        "unknown": [
                            {"scope": "process_coverage", "reason": "process_set_changed_during_sample"},
                            {"scope": "process_coverage", "reason": "process_transition_read_incomplete"},
                        ],
                    },
                    "attribution_complete": False,
                },
                {
                    "monotonic": 1.35,
                    "time": 1.35,
                    "sample_duration_seconds": 0.1,
                    "collector_thread_cpu_seconds": 0.01,
                    "cgroup": {"device": 1, "inode": 2},
                    "memory_current": next(memory_current),
                    "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
                    "memory_stat": {key: 0 for key in telemetry.MEMORY_STAT_FIELDS},
                    "memory_pressure_raw": "full avg10=0.00 total=0\n",
                    "processes": [complete],
                    "process_events": [],
                    "process_coverage": {"status": "complete", "unknown": []},
                    "attribution_complete": True,
                },
            ]
        ):
            current = telemetry.strict_attribution_sample()

        self.assertFalse(current["attribution_complete"])
        self.assertFalse(current["identity_resample"]["accepted"])
        self.assertEqual(current["memory_current"], 2000)
        prior = {
            **current,
            "monotonic": 1.0,
            "memory_current": 2100,
            "processes": [complete, {**complete, **child, "command_class": "fresh_owned_child"}],
            "process_events": [],
            "process_coverage": {"status": "complete", "unknown": []},
            "attribution_complete": True,
        }
        following = {
            **current,
            "monotonic": 1.5,
            "memory_current": 900,
            "processes": [complete],
            "process_events": [{
                "event": "exit_observed", "pid": 101,
                "start_ticks": 1001, "command_class": "fresh_owned_child",
            }],
            "process_coverage": {"status": "complete", "unknown": []},
            "attribution_complete": True,
        }
        result = telemetry.classify_confirmed_exit_transition(
            [prior, current, following], 1,
            attribution_gap_seconds=1.0, peak_index=0,
        )
        self.assertEqual(result["status"], "classified_confirmed_exit")

        current["process_coverage"]["identities_after"].append(
            {"pid": 102, "ppid": 100, "start_ticks": 1002}
        )
        result = telemetry.classify_confirmed_exit_transition(
            [prior, current, following], 1,
            attribution_gap_seconds=1.0, peak_index=0,
        )
        self.assertEqual(result["reason"], "exit_membership_transition_not_confirmed")

    def test_failed_resample_still_classifies_only_the_same_exact_exit(self):
        worker = {
            "pid": 100, "ppid": 1, "start_ticks": 1000,
            "status": "complete", "command_class": "worker", "pss_bytes": 10,
        }
        child = {
            "pid": 101, "ppid": 100, "start_ticks": 1001,
            "status": "complete", "command_class": "warm_parser", "pss_bytes": 20,
        }
        absent = {**child, "status": "unknown", "reason": "ProcessLookupError", "pss_bytes": None}
        identities = [{key: row[key] for key in ("pid", "ppid", "start_ticks")} for row in (worker, child)]
        direct = [{"scope": "process_coverage", "reason": "cgroup_process_read_incomplete"}]

        def sample(monotonic, processes, unknown, before_ids, after_ids, *, complete=False):
            return {
                "monotonic": monotonic,
                "time": monotonic,
                "memory_current": 90,
                "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
                "memory_stat": {key: 0 for key in telemetry.MEMORY_STAT_FIELDS},
                "memory_pressure_raw": "full avg10=0.00 total=0\n",
                "cgroup": {"device": 1, "inode": 2},
                "attribution_complete": complete,
                "processes": processes,
                "process_events": [],
                "process_coverage": {
                    "status": "complete" if complete else "incomplete",
                    "identities_before": before_ids,
                    "identities_after": after_ids,
                    "unknown": unknown,
                },
            }

        before = sample(1.0, [worker, child], [], identities, identities, complete=True)
        before["memory_current"] = 100
        after_ids = identities[:1]
        after = sample(1.5, [worker], [], after_ids, after_ids, complete=True)
        after["memory_current"] = 80
        after["process_events"] = [
            {"event": "exit_observed", "pid": 101, "start_ticks": 1001},
            {"event": "birth_observed", "pid": 102, "start_ticks": 1002},
        ]
        first = sample(1.2, [worker, absent], direct, identities, identities)
        retry_direct = sample(1.25, [worker, absent], direct, identities, identities)
        transition_issues = [
            {"scope": "proc_identity", "pid": 101, "reason": "FileNotFoundError"},
            {"scope": "process_coverage", "reason": "process_set_changed_during_sample"},
            {"scope": "process_coverage", "reason": "process_transition_read_incomplete"},
        ]
        retry_transition = sample(1.25, [worker, absent], transition_issues, identities, after_ids)

        def retained(retry):
            current = copy.deepcopy(first)
            current["monotonic"] = retry["monotonic"]
            current["process_coverage"]["unknown"] += [
                {"scope": "identity_resample_retry", "reason": "retry_incomplete", "detail": issue}
                for issue in retry["process_coverage"]["unknown"]
            ]
            current["identity_resample"] = {
                "accepted": False,
                "observations": {"first": copy.deepcopy(first), "retry": copy.deepcopy(retry)},
            }
            return current

        for name, retry in (("same_read", retry_direct), ("membership_exit", retry_transition)):
            with self.subTest(name=name):
                result = telemetry.classify_confirmed_exit_transition(
                    [before, retained(retry), after], 1,
                    attribution_gap_seconds=1.0, peak_index=0,
                )
                self.assertEqual(result["status"], "classified_confirmed_exit")

        wrong_identity = copy.deepcopy(retry_direct)
        wrong_identity["processes"][-1]["start_ticks"] = 9999
        denied = copy.deepcopy(retry_direct)
        denied["processes"][-1]["reason"] = "PermissionError"
        simultaneous_birth = copy.deepcopy(retry_transition)
        simultaneous_birth["process_coverage"]["identities_after"].append(
            {"pid": 102, "ppid": 100, "start_ticks": 1002}
        )
        between_observation_birth = copy.deepcopy(retry_direct)
        between_observation_birth["process_coverage"]["identities_before"].append(
            {"pid": 102, "ppid": 100, "start_ticks": 1002}
        )
        between_observation_birth["process_coverage"]["identities_after"].append(
            {"pid": 102, "ppid": 100, "start_ticks": 1002}
        )
        for name, retry in (
            ("different_identity", wrong_identity),
            ("permission_denied", denied),
            ("simultaneous_retry_birth", simultaneous_birth),
            ("between_observation_birth", between_observation_birth),
        ):
            with self.subTest(name=name):
                result = telemetry.classify_confirmed_exit_transition(
                    [before, retained(retry), after], 1,
                    attribution_gap_seconds=1.0, peak_index=0,
                )
                self.assertEqual(result["status"], "unclassified")

    def test_lower_complete_retry_confirms_membership_exit(self):
        worker = {
            "pid": 100, "ppid": 1, "start_ticks": 1000,
            "status": "complete", "command_class": "worker", "pss_bytes": 10,
        }
        child = {
            "pid": 101, "ppid": 100, "start_ticks": 1001,
            "status": "complete", "command_class": "fresh_owned_child", "pss_bytes": 20,
        }
        identities = [
            {key: row[key] for key in ("pid", "ppid", "start_ticks")}
            for row in (worker, child)
        ]
        remaining = identities[:1]

        def sample(monotonic, processes, before_ids, after_ids, *, complete):
            return {
                "monotonic": monotonic,
                "time": monotonic,
                "memory_current": 90,
                "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
                "memory_stat": {key: 0 for key in telemetry.MEMORY_STAT_FIELDS},
                "memory_pressure_raw": "full avg10=0.00 total=0\n",
                "cgroup": {"device": 1, "inode": 2},
                "attribution_complete": complete,
                "processes": processes,
                "process_events": [],
                "process_coverage": {
                    "status": "complete" if complete else "incomplete",
                    "identities_before": before_ids,
                    "identities_after": after_ids,
                    "unknown": [] if complete else [{
                        "scope": "process_coverage",
                        "reason": "process_set_changed_during_sample",
                    }],
                },
            }

        before = sample(1.0, [worker, child], identities, identities, complete=True)
        before["memory_current"] = 100
        first = sample(1.2, [worker], identities, remaining, complete=False)
        first["memory_current"] = 95
        retry = sample(1.25, [worker], remaining, remaining, complete=True)
        retry["memory_current"] = 90
        current = copy.deepcopy(first)
        current["monotonic"] = retry["monotonic"]
        current["identity_resample"] = {
            "accepted": False,
            "observations": {"first": first, "retry": retry},
        }
        after = sample(1.5, [worker], remaining, remaining, complete=True)
        after["memory_current"] = 80
        after["process_events"] = [{
            "event": "exit_observed", "pid": 101, "start_ticks": 1001,
            "command_class": "fresh_owned_child",
        }]

        result = telemetry.classify_confirmed_exit_transition(
            [before, current, after], 1,
            attribution_gap_seconds=1.0, peak_index=0,
        )
        self.assertEqual(result["status"], "classified_confirmed_exit")

    def test_membership_churn_does_not_retry_permission_failure(self):
        row = {
            "processes": [{"status": "unknown", "reason": "PermissionError"}],
            "process_coverage": {
                "unknown": [
                    {"scope": "process_coverage", "reason": "process_set_changed_during_sample"},
                    {"scope": "process_coverage", "reason": "process_transition_read_incomplete"},
                ]
            },
            "attribution_complete": False,
        }
        with mock.patch.object(
            telemetry, "_strict_attribution_sample_once", return_value=row
        ) as sample:
            self.assertIs(telemetry.strict_attribution_sample(), row)
        sample.assert_called_once_with()

    def test_disappearing_process_read_retries_whole_sample(self):
        first = {
            "monotonic": 1.0,
            "time": 1.0,
            "sample_duration_seconds": 0.1,
            "collector_thread_cpu_seconds": 0.01,
            "memory_current": 1000,
            "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
            "memory_pressure_raw": "full avg10=0.00 total=0\n",
            "processes": [{"status": "unknown", "reason": "ProcessLookupError"}],
            "process_coverage": {
                "unknown": [{
                    "scope": "process_coverage",
                    "reason": "cgroup_process_read_incomplete",
                }]
            },
            "attribution_complete": False,
        }
        retry = {
            **first,
            "monotonic": 1.1,
            "time": 1.1,
            "memory_current": 1100,
            "processes": [{"status": "complete", "pss_bytes": 10}],
            "process_coverage": {"unknown": []},
            "attribution_complete": True,
        }
        with mock.patch.object(
            telemetry, "_strict_attribution_sample_once", side_effect=[first, retry]
        ) as sample:
            row = telemetry.strict_attribution_sample()

        self.assertTrue(row["attribution_complete"])
        self.assertTrue(row["identity_resample"]["accepted"])
        self.assertEqual(row["memory_current"], 1100)
        self.assertEqual(sample.call_count, 2)

    def test_native_capture_restore_reuses_one_parser_then_reaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trial = root / "fresh-08"
            worker = root / "worker-1"
            trial.mkdir()
            worker.mkdir()
            parser = {
                "pid": 42,
                "ready": True,
                "restarts": 1,
                "handoffs": 0,
                "termination_reason": None,
            }
            steps = [
                {
                    "stage": stage,
                    "reused": False,
                    "parser": {**parser, "request_id": str(index)},
                }
                for index, stage in enumerate(["group", "group", "group", "assembly"])
            ]
            (trial / "accepted.json").write_text(
                __import__("json").dumps({"result": {"steps": steps}})
            )
            (worker / "stopped.json").write_text(
                __import__("json").dumps(
                    {"parser_absent": True, "scratch_absent": True}
                )
            )
            process = {
                "pid": 42,
                "ppid": 10,
                "start_ticks": 420,
                "command_class": "warm_parser",
                "status": "complete",
            }
            rows = [
                {
                    "processes": [process],
                    "process_events": [],
                    "warm_parser_present": True,
                },
                {
                    "processes": [],
                    "process_events": [
                        {
                            "event": "exit_observed",
                            "pid": 42,
                            "start_ticks": 420,
                        }
                    ],
                    "warm_parser_present": False,
                },
            ]
            result = telemetry.evaluate_warm_continuity_contract(rows, root)
            self.assertTrue(result["complete"], result)
            self.assertEqual(result["captures"], 3)
            self.assertEqual(result["restores"], 1)


if __name__ == "__main__":
    unittest.main()
