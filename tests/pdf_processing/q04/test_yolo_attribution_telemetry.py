"""Offline synthetic checks for strict YOLO attribution telemetry."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from sentinel.acl_resource_telemetry import cgroup_identity
from sentinel.yolo_attribution_telemetry import (
    ProcessLifecycle,
    StrictAttributionCollector,
    observed_runtime_markers,
    strict_attribution_sample,
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
        self.observed = root / "state"
        (self.proc / "self").mkdir(parents=True)
        self.cgroup.mkdir()
        self.observed.mkdir()
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
        (self.cgroup / "memory.pressure").write_text(
            "some avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
            "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
        )
        self.process(100, 1, 1000, b"python\0yolo_fresh_measure.py\0")
        self.process(101, 100, 1001, b"python\0q04/worker.py\0")
        self.process(102, 101, 1002, b"python\0-m\0pdf_processing.warm_child\0")
        self.process(103, 101, 1003, b"python\0-m\0pdf_processing.parse\0")
        self.process(200, 1, 2000, b"python\0shared-coordinator-task.py\0")

    def process(self, pid, ppid, start_ticks, command):
        root = self.proc / str(pid)
        root.mkdir()
        (root / "stat").write_text(proc_stat(pid, ppid, start_ticks))
        (root / "cgroup").write_text("0::/\n")
        (root / "cmdline").write_bytes(command)
        (root / "status").write_text(
            "RssAnon:\t1024 kB\nRssFile:\t512 kB\nRssShmem:\t64 kB\n"
        )
        (root / "smaps_rollup").write_text("Rss: 2048 kB\nPss: 1536 kB\n")


class YoloAttributionTelemetry(unittest.TestCase):
    def sample(self, linux, **kwargs):
        return strict_attribution_sample(
            root_pid=100,
            expected_cgroup=cgroup_identity(linux.proc, linux.cgroup),
            proc_root=linux.proc,
            cgroup_root=linux.cgroup,
            observation_root=linux.observed,
            **kwargs,
        )

    def test_complete_sample_has_identity_fenced_processes_and_synchronized_pss(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            row = self.sample(linux)

            self.assertTrue(row["attribution_complete"])
            self.assertEqual(row["process_coverage"]["status"], "complete")
            self.assertEqual(
                [item["command_class"] for item in row["processes"]],
                [
                    "controller",
                    "worker",
                    "warm_parser",
                    "fresh_parse_child",
                    "owned_descendant",
                ],
            )
            self.assertEqual(row["owned_pss_total_bytes"], 6 * 1024 * 1024)
            self.assertEqual(
                row["shared_cgroup_process_pss_total_bytes"],
                7_864_320,
            )
            self.assertEqual(
                row["diagnostic_unattributed_bytes"], 209_715_200 - 7_864_320
            )
            shared = next(item for item in row["processes"] if item["pid"] == 200)
            self.assertEqual(shared["ownership"], "shared_cgroup_other")
            self.assertFalse(row["diagnostic_unattributed_is_cache"])
            self.assertGreaterEqual(row["collector_thread_cpu_seconds"], 0)

    def test_unreadable_pss_is_unknown_and_never_becomes_zero_or_residual(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            (linux.proc / "103/smaps_rollup").unlink()
            row = self.sample(linux)

            fresh = next(item for item in row["processes"] if item["pid"] == 103)
            self.assertEqual(fresh["status"], "unknown")
            self.assertIsNone(fresh["pss_bytes"])
            self.assertIsNone(row["owned_pss_total_bytes"])
            self.assertIsNone(row["shared_cgroup_process_pss_total_bytes"])
            self.assertIsNone(row["diagnostic_unattributed_bytes"])
            self.assertFalse(row["attribution_complete"])

    def test_pid_reuse_during_sample_is_fenced_and_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            linux = SyntheticLinux(Path(directory))
            reads = 0

            def reader(path):
                nonlocal reads
                if path == linux.proc / "103/stat":
                    reads += 1
                    if reads >= 2:
                        return proc_stat(103, 101, 9003)
                return path.read_text()

            row = self.sample(linux, read_text=reader)
            fresh = next(item for item in row["processes"] if item["pid"] == 103)
            self.assertEqual(fresh["status"], "identity_changed_during_sample")
            self.assertIsNone(fresh["pss_bytes"])
            self.assertFalse(row["attribution_complete"])

    def test_synthetic_subprocess_lifecycle_retains_birth_exit_and_pid_reuse(self):
        tracker = ProcessLifecycle()
        child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
        try:
            born = tracker.update([
                {"pid": child.pid, "start_ticks": 10, "command_class": "owned_descendant"}
            ])
            reused = tracker.update([
                {"pid": child.pid, "start_ticks": 11, "command_class": "owned_descendant"}
            ])
        finally:
            child.terminate()
            child.wait(timeout=5)
        exited = tracker.update([])

        self.assertEqual(born[0]["event"], "birth_observed")
        self.assertEqual(reused[0]["event"], "pid_reuse_observed")
        self.assertEqual(exited[0]["event"], "exit_observed")

    def test_external_markers_do_not_claim_activity_or_materialization_start(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trial = root / "fresh-07"
            trial.mkdir()
            (trial / "workflow-intent.json").write_text("{}")
            (trial / "workflow.json").write_text("{}")
            (trial / "progress.jsonl").write_text(
                json.dumps({"progress": {"status": "assembling"}}) + "\n"
            )
            merged = root / "worker-1/scratch/07/pdf-x/merged"
            merged.mkdir(parents=True)
            markers, issues = observed_runtime_markers(root)

            self.assertEqual(issues, [])
            meanings = {row["meaning"] for row in markers}
            self.assertIn("workflow_query_state_not_activity_start", meanings)
            self.assertIn("filesystem_presence_not_materialization_start", meanings)
            self.assertNotIn("activity_started", meanings)

    def test_collector_records_cost_post_cleanup_and_complete_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            output = root / "attribution.jsonl"
            summary = root / "summary.json"
            collector = StrictAttributionCollector(
                output,
                summary,
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )
            trial = linux.observed / "fresh-07"
            trial.mkdir()
            (trial / "progress.jsonl").write_text(
                json.dumps({"progress": {"status": "assembling"}}) + "\n"
            )
            collector.start()
            time.sleep(0.035)
            collector.observe(
                "cancel_requested",
                source="synthetic_callback",
                meaning="test cancellation callback invoked",
            )
            collector.observe(
                "owned_cleanup_finished",
                source="synthetic_callback",
                meaning="test cleanup callback returned",
            )
            outcome = collector.stop()

            self.assertTrue(outcome.attribution_complete)
            rows = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(rows[0]["observations"][0]["label"], "baseline_before_worker")
            self.assertEqual(rows[-1]["observations"][-1]["label"], "post_cleanup_sample")
            report = json.loads(summary.read_text())
            self.assertGreater(report["collector_output_bytes"], 0)
            self.assertEqual(
                report["collector_output_bytes"],
                report["collector_committed_spool_bytes"],
            )
            self.assertTrue(report["collector_retains_compact_in_memory_summary_only"])
            self.assertGreaterEqual(report["collector_total_thread_cpu_seconds"], 0)
            self.assertFalse(report["collector_memory_cost_isolated"])
            self.assertTrue(report["collector_inprocess_memory_included_in_controller_pss"])
            self.assertTrue(report["pss_collected_within_sample_window"])
            self.assertFalse(report["pss_reading_is_atomic"])
            self.assertFalse(report["diagnostic_unattributed_is_cache"])
            self.assertEqual(report["missing_required_observation_labels"], [])

    def test_bounded_transition_remains_incomplete_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            calls = 0

            def transition_sampler(**kwargs):
                nonlocal calls
                calls += 1
                row = strict_attribution_sample(**kwargs)
                if calls == 2:
                    row["attribution_complete"] = False
                    row["owned_pss_total_bytes"] = None
                    row["shared_cgroup_process_pss_total_bytes"] = None
                    row["diagnostic_unattributed_bytes"] = None
                    row["process_coverage"]["status"] = "incomplete"
                    row["process_coverage"]["unknown"] = [{
                        "scope": "process_coverage",
                        "reason": "process_set_changed_during_sample",
                    }]
                return row

            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                sampler=transition_sampler,
            )
            collector.start()
            time.sleep(0.035)
            outcome = collector.stop()

            self.assertFalse(outcome.attribution_complete)
            self.assertEqual(outcome.status, "incomplete")
            self.assertEqual(outcome.incomplete_samples, 1)
            report = json.loads((root / "summary.json").read_text())
            self.assertEqual(report["hard_incomplete_sample_indexes"], [1])

    def test_missing_assembly_or_cancel_marker_makes_summary_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )
            collector.start()
            time.sleep(0.02)
            outcome = collector.stop()

            self.assertFalse(outcome.attribution_complete)
            report = json.loads((root / "summary.json").read_text())
            self.assertEqual(
                report["missing_required_observation_labels"],
                ["cancel_requested", "workflow_progress_assembling_observed"],
            )

    def test_required_markers_out_of_order_make_summary_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            trial = linux.observed / "fresh-07"
            trial.mkdir()
            (trial / "progress.jsonl").write_text(
                json.dumps({"progress": {"status": "assembling"}}) + "\n"
            )
            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )
            collector.observe(
                "cancel_requested",
                source="synthetic_callback",
                meaning="deliberately before baseline",
            )
            collector.start()
            time.sleep(0.02)
            outcome = collector.stop()

            self.assertFalse(outcome.attribution_complete)
            report = json.loads((root / "summary.json").read_text())
            self.assertEqual(report["missing_required_observation_labels"], [])
            self.assertFalse(report["required_observations_in_order"])

    def test_persistent_read_failure_makes_collector_summary_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            (linux.proc / "103/smaps_rollup").unlink()
            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
            )
            collector.start()
            time.sleep(0.02)
            outcome = collector.stop()

            self.assertFalse(outcome.attribution_complete)
            self.assertEqual(outcome.status, "incomplete")
            report = json.loads((root / "summary.json").read_text())
            self.assertTrue(report["hard_incomplete_sample_indexes"])

    def test_collector_gap_is_latched_and_cleanup_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            blocked = threading.Event()
            release = threading.Event()
            calls = 0

            def blocking_sampler(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    blocked.set()
                    release.wait(2)
                return strict_attribution_sample(**kwargs)

            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.05,
                shutdown_timeout_seconds=0.05,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                sampler=blocking_sampler,
            )
            collector.start()
            self.assertTrue(blocked.wait(1))
            time.sleep(0.06)
            with self.assertRaisesRegex(RuntimeError, "gap exceeded"):
                collector.require_healthy()
            started = time.perf_counter()
            outcome = collector.stop()
            self.assertLess(time.perf_counter() - started, 0.2)
            self.assertFalse(outcome.attribution_complete)
            self.assertEqual(outcome.status, "incomplete")
            size_before_release = (root / "attribution.jsonl").stat().st_size
            rows_before_release = (root / "attribution.jsonl").read_text().splitlines()
            release.set()
            collector._thread.join(1)
            self.assertFalse(collector._thread.is_alive())
            self.assertEqual(
                (root / "attribution.jsonl").stat().st_size,
                size_before_release,
            )
            self.assertEqual(
                (root / "attribution.jsonl").read_text().splitlines(),
                rows_before_release,
            )

    def test_flush_boundary_keeps_jsonl_and_summary_row_count_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)
            blocked = threading.Event()
            release = threading.Event()

            class BlockingStream:
                def __init__(self, path):
                    self.stream = path.open("x")
                    self.flushes = 0

                def write(self, payload):
                    return self.stream.write(payload)

                def flush(self):
                    self.flushes += 1
                    if self.flushes == 2:
                        blocked.set()
                        release.wait(2)
                    return self.stream.flush()

                def tell(self):
                    return self.stream.tell()

                def close(self):
                    return self.stream.close()

            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                shutdown_timeout_seconds=0.05,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                stream_factory=BlockingStream,
            )
            collector.start()
            self.assertTrue(blocked.wait(1))
            results = []
            stopper = threading.Thread(target=lambda: results.append(collector.stop()))
            stopper.start()
            time.sleep(0.07)
            self.assertFalse(stopper.is_alive())
            stopper.join(1)
            retained_before_release = (root / "attribution.jsonl").read_bytes()
            report_before_release = (root / "summary.json").read_bytes()
            release.set()
            collector._thread.join(1)
            self.assertFalse(collector._thread.is_alive())

            rows = (root / "attribution.jsonl").read_text().splitlines()
            report = json.loads((root / "summary.json").read_text())
            self.assertEqual(len(rows), report["samples"])
            self.assertEqual(len(rows), results[0].samples)
            self.assertFalse(results[0].attribution_complete)
            self.assertEqual(
                (root / "attribution.jsonl").read_bytes(), retained_before_release
            )
            self.assertEqual((root / "summary.json").read_bytes(), report_before_release)

    def test_periodic_partial_write_seals_only_prior_complete_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)

            class PartialWriteStream:
                def __init__(self, path):
                    self.stream = path.open("x")
                    self.writes = 0

                def write(self, payload):
                    self.writes += 1
                    if self.writes == 2:
                        self.stream.write(payload[:17])
                        self.stream.flush()
                        raise OSError("synthetic partial periodic write")
                    return self.stream.write(payload)

                def flush(self):
                    return self.stream.flush()

                def tell(self):
                    return self.stream.tell()

                def close(self):
                    return self.stream.close()

            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                stream_factory=PartialWriteStream,
            )
            collector.start()
            collector._thread.join(1)
            self.assertFalse(collector._thread.is_alive())
            outcome = collector.stop()

            rows = [
                json.loads(line)
                for line in (root / "attribution.jsonl").read_text().splitlines()
            ]
            self.assertEqual(len(rows), 1)
            self.assertEqual(outcome.samples, 1)
            self.assertFalse(outcome.attribution_complete)
            self.assertTrue(any("partial periodic write" in error for error in outcome.errors))

    def test_baseline_partial_write_seals_empty_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            linux = SyntheticLinux(root)

            class PartialBaselineStream:
                def __init__(self, path):
                    self.stream = path.open("x")

                def write(self, payload):
                    self.stream.write(payload[:17])
                    self.stream.flush()
                    raise OSError("synthetic partial baseline write")

                def flush(self):
                    return self.stream.flush()

                def tell(self):
                    return self.stream.tell()

                def close(self):
                    return self.stream.close()

            collector = StrictAttributionCollector(
                root / "attribution.jsonl",
                root / "summary.json",
                root_pid=100,
                observation_root=linux.observed,
                interval_seconds=0.01,
                attribution_gap_seconds=0.2,
                proc_root=linux.proc,
                cgroup_root=linux.cgroup,
                stream_factory=PartialBaselineStream,
            )
            with self.assertRaisesRegex(OSError, "partial baseline"):
                collector.start()
            outcome = collector.stop()

            self.assertEqual((root / "attribution.jsonl").read_text(), "")
            self.assertEqual(outcome.samples, 0)
            self.assertFalse(outcome.attribution_complete)
            self.assertTrue(any("partial baseline write" in error for error in outcome.errors))


if __name__ == "__main__":
    unittest.main()
