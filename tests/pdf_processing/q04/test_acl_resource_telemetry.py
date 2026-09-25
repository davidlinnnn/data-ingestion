"""Synthetic local checks for qualification-only resource attribution."""

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from sentinel.acl_resource_telemetry import (
    ResourceCollector,
    attribution_sample,
    cgroup_identity,
)


def proc_stat(pid, ppid, start_ticks, *, state="S"):
    fields = [state, str(ppid)] + ["0"] * 18
    fields[7] = "11"
    fields[9] = "3"
    fields[11] = "17"
    fields[12] = "5"
    fields[19] = str(start_ticks)
    return f"{pid} (synthetic process {pid}) " + " ".join(fields) + "\n"


class SyntheticLinux:
    def __init__(self, root: Path):
        self.proc = root / "proc"
        self.cgroup = root / "cgroup"
        (self.proc / "self").mkdir(parents=True)
        self.cgroup.mkdir()
        (self.proc / "self/cgroup").write_text("0::/\n")
        (self.proc / "self/mountinfo").write_text(
            "32 23 0:28 / /sys/fs/cgroup rw,nosuid,nodev,noexec,relatime"
            " - cgroup2 cgroup rw\n"
        )
        (self.cgroup / "memory.current").write_text("209715200\n")
        (self.cgroup / "memory.events").write_text(
            "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n"
        )
        (self.cgroup / "memory.stat").write_text(
            "anon 104857600\nfile 52428800\nshmem 0\nfile_mapped 4096\n"
            "inactive_file 1024\nslab 2048\nkernel 4096\n"
        )
        (self.cgroup / "memory.peak").write_text("314572800\n")
        self.process(100, 1, 1000, b"python\0acl_fresh_measure.py\0")
        self.process(101, 100, 1001, b"python\0-m\0pdf_processing.warm_child\0")

    def process(self, pid, ppid, start_ticks, command):
        root = self.proc / str(pid)
        root.mkdir()
        (root / "stat").write_text(proc_stat(pid, ppid, start_ticks))
        (root / "cmdline").write_bytes(command)
        (root / "status").write_text(
            "RssAnon:\t1024 kB\nRssFile:\t512 kB\nRssShmem:\t64 kB\n"
        )
        (root / "smaps_rollup").write_text("Rss: 2048 kB\nPss: 1536 kB\n")


class ResourceTelemetry(unittest.TestCase):
    def test_samples_shared_cgroup_and_owned_processes_without_resetting_peak(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            identity = cgroup_identity(linux.proc, linux.cgroup)
            row = attribution_sample(
                root_pid=100,
                expected_cgroup=identity,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )

            self.assertEqual(row["memory_current"], 209_715_200)
            self.assertEqual(row["memory_peak"], 314_572_800)
            self.assertEqual(
                row["memory_peak_scope"], "shared_cgroup_lifetime_high_water_mark"
            )
            self.assertFalse(row["memory_peak_reset"])
            self.assertEqual(
                [item["command_class"] for item in row["processes"]],
                ["controller", "parser"],
            )
            self.assertEqual(row["owned_pss_total_bytes"], 3 * 1024 * 1024)
            self.assertTrue(row["residual_is_diagnostic_only"])
            self.assertTrue(row["attribution_complete"])

    def test_missing_optional_fields_marks_attribution_incomplete_not_memory_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            (linux.cgroup / "memory.peak").unlink()
            (linux.proc / "101/smaps_rollup").unlink()
            identity = cgroup_identity(linux.proc, linux.cgroup)
            row = attribution_sample(
                root_pid=100,
                expected_cgroup=identity,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )

            self.assertEqual(row["memory_current"], 209_715_200)
            self.assertIsNone(row["memory_peak"])
            self.assertFalse(row["attribution_complete"])
            parser = next(item for item in row["processes"] if item["pid"] == 101)
            self.assertIsNone(parser["pss_bytes"])
            self.assertTrue(parser["issues"])

    def test_permission_and_process_exit_races_are_retained_as_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            identity = cgroup_identity(linux.proc, linux.cgroup)
            stat_reads = {100: 0, 101: 0}

            def read_text(path):
                if path.name == "smaps_rollup":
                    raise PermissionError(path)
                if path.name == "stat" and path.parent.name == "101":
                    stat_reads[101] += 1
                    if stat_reads[101] > 1:
                        raise FileNotFoundError(path)
                return path.read_text()

            row = attribution_sample(
                root_pid=100,
                expected_cgroup=identity,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                read_text=read_text,
            )
            root = next(item for item in row["processes"] if item["pid"] == 100)
            child = next(item for item in row["processes"] if item["pid"] == 101)
            self.assertIsNone(root["pss_bytes"])
            self.assertEqual(child["status"], "exited_during_sample")
            self.assertFalse(row["attribution_complete"])

    def test_synthetic_sampling_overhead_fits_250ms_design_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            identity = cgroup_identity(linux.proc, linux.cgroup)
            started = time.perf_counter()
            for _ in range(100):
                attribution_sample(
                    root_pid=100,
                    expected_cgroup=identity,
                    proc_root=linux.proc,
                    cgroup_root=linux.cgroup,
                )
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed / 100, 0.25)

    def test_collector_stops_and_writes_cleanup_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            output = root / "samples.jsonl"
            summary = root / "summary.json"
            collector = ResourceCollector(
                output,
                summary,
                root_pid=100,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )
            collector.start()
            time.sleep(0.04)
            collector.mark("synthetic_work_finished")
            outcome = collector.stop()

            self.assertGreaterEqual(outcome.samples, 4)
            self.assertTrue(outcome.attribution_complete)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(rows[0]["marker"], "collector_started_before_worker")
            self.assertEqual(rows[-1]["marker"], "collector_stopped_after_cleanup")
            report = json.loads(summary.read_text())
            self.assertTrue(report["auxiliary_attribution_only"])
            self.assertFalse(report["memory_peak_reset"])

    def test_collector_failure_still_closes_and_writes_error_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            calls = 0

            def failing_sampler(**kwargs):
                nonlocal calls
                calls += 1
                if calls > 1:
                    raise PermissionError("synthetic required cgroup read denied")
                return attribution_sample(**kwargs)

            output = root / "samples.jsonl"
            summary = root / "summary.json"
            collector = ResourceCollector(
                output,
                summary,
                root_pid=100,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                sampler=failing_sampler,
            )
            collector.start()
            time.sleep(0.03)
            with self.assertRaisesRegex(RuntimeError, "resource attribution failed"):
                collector.require_healthy()
            outcome = collector.stop()

            self.assertTrue(outcome.errors)
            self.assertFalse(outcome.attribution_complete)
            report = json.loads(summary.read_text())
            self.assertTrue(report["errors"])
            output.rename(root / "closed-stream-proof.jsonl")

    def test_stalled_sampler_trips_live_gap_guard_and_stop_remains_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            stalled = threading.Event()
            release = threading.Event()
            calls = 0

            def blocking_sampler(**kwargs):
                nonlocal calls
                calls += 1
                if calls > 1:
                    stalled.set()
                    release.wait(timeout=2)
                return attribution_sample(**kwargs)

            collector = ResourceCollector(
                root / "samples.jsonl",
                root / "summary.json",
                root_pid=100,
                interval_seconds=0.01,
                attribution_gap_seconds=0.05,
                shutdown_timeout_seconds=0.05,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                sampler=blocking_sampler,
            )
            collector.start()
            self.assertTrue(stalled.wait(timeout=1))
            time.sleep(0.06)
            with self.assertRaisesRegex(RuntimeError, "sample gap exceeded"):
                collector.require_healthy()

            started = time.perf_counter()
            outcome = collector.stop()
            elapsed = time.perf_counter() - started
            self.assertLess(elapsed, 0.2)
            self.assertFalse(outcome.attribution_complete)
            self.assertIn(
                "collector thread did not stop within shutdown timeout",
                outcome.errors,
            )
            release.set()
            time.sleep(0.03)

    def test_recovered_excessive_gap_remains_latched_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            stalled = threading.Event()
            release = threading.Event()
            resumed = threading.Event()
            calls = 0

            def recovering_sampler(**kwargs):
                nonlocal calls
                calls += 1
                call = calls
                if call == 2:
                    stalled.set()
                    release.wait(timeout=2)
                row = attribution_sample(**kwargs)
                if call == 2:
                    resumed.set()
                return row

            collector = ResourceCollector(
                root / "samples.jsonl",
                root / "summary.json",
                root_pid=100,
                interval_seconds=0.01,
                attribution_gap_seconds=0.05,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                sampler=recovering_sampler,
            )
            collector.start()
            self.assertTrue(stalled.wait(timeout=1))
            time.sleep(0.06)
            release.set()
            self.assertTrue(resumed.wait(timeout=1))
            time.sleep(0.03)

            with self.assertRaisesRegex(RuntimeError, "sample gap exceeded"):
                collector.require_healthy()
            outcome = collector.stop()
            self.assertFalse(outcome.attribution_complete)
            self.assertTrue(
                any("sample gap exceeded" in error for error in outcome.errors)
            )


if __name__ == "__main__":
    unittest.main()
