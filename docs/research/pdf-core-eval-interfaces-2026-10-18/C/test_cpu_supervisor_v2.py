"""Exercise the supervisor itself; no PDF conversion or model import."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import psutil
import cpu_baseline_v2 as supervisor


class SupervisorExitTests(unittest.TestCase):
    def run_parent(self, process, *, exit_code=0, kill_race=False):
        module = __import__(supervisor.parent.__module__)
        with tempfile.TemporaryDirectory(prefix="pdf-supervisor-") as folder:
            directory = Path(folder)
            worker = SimpleNamespace(pid=123456789, returncode=None)
            polls = iter([None, None] if kill_race else [None, exit_code, exit_code])
            def poll():
                worker.returncode = next(polls)
                return worker.returncode
            def wait():
                worker.returncode = exit_code
                return exit_code
            worker.poll, worker.wait = poll, wait
            with patch.object(module, "HERE", directory), \
                 patch.object(module.subprocess, "Popen", return_value=worker), \
                 patch.object(module.psutil, "Process", side_effect=process), \
                 patch.object(module.psutil, "virtual_memory", return_value=SimpleNamespace(available=20*2**30)), \
                 patch.object(module.time, "sleep"), \
                 patch.object(module.fcntl, "flock"), \
                 patch.object(module.os, "killpg", side_effect=ProcessLookupError if kill_race else None):
                error = None
                try:
                    supervisor.parent()
                except Exception as caught:
                    error = caught
            record = directory / "cpu-execution.json"
            return error, json.loads(record.read_text()) if record.exists() else None

    def test_child_dies_between_enumeration_and_memory_read(self):
        child = SimpleNamespace(is_running=lambda: True,
            memory_info=lambda: (_ for _ in ()).throw(psutil.ZombieProcess(123456788)))
        tree = SimpleNamespace(children=lambda **kwargs: [child], is_running=lambda: True,
            memory_info=lambda: SimpleNamespace(rss=1024))
        error, record = self.run_parent(lambda pid: tree)
        self.assertIsNone(error)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["exit_code"], 0)
        self.assertEqual(record["samples"][0]["rss"], 1024)

    def test_root_exits_before_process_object_is_created(self):
        def gone(pid):
            raise psutil.NoSuchProcess(pid)
        error, record = self.run_parent(gone)
        self.assertIsNone(error)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["exit_code"], 0)

    def test_enumeration_race_keeps_surviving_root_memory(self):
        def disappeared(**kwargs):
            raise psutil.NoSuchProcess(123456788)
        tree = SimpleNamespace(children=disappeared,
            memory_info=lambda: SimpleNamespace(rss=1024))
        error, record = self.run_parent(lambda pid: tree)
        self.assertIsNone(error)
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["samples"][0]["rss"], 1024)

    def test_worker_failure_is_not_changed_to_success(self):
        def gone(pid):
            raise psutil.ZombieProcess(pid)
        error, record = self.run_parent(gone, exit_code=7)
        self.assertIsNone(error)
        self.assertEqual(record["status"], "worker_error")
        self.assertEqual(record["exit_code"], 7)

    def test_access_denied_remains_a_monitor_error(self):
        def denied(pid):
            raise psutil.AccessDenied(pid)
        error, record = self.run_parent(denied)
        self.assertIsInstance(error, psutil.AccessDenied)
        self.assertEqual(record["status"], "parent_harness_error")

    def test_budget_stop_survives_process_exiting_before_kill(self):
        tree = SimpleNamespace(children=lambda **kwargs: [], is_running=lambda: True,
            memory_info=lambda: SimpleNamespace(rss=13*2**30))
        error, record = self.run_parent(lambda pid: tree, kill_race=True)
        self.assertIsNone(error)
        self.assertEqual(record["status"], "time_or_memory_budget_stop")
        self.assertEqual(record["exit_code"], 0)

    def test_existing_attempt_is_never_restarted(self):
        with tempfile.TemporaryDirectory(prefix="pdf-supervisor-") as folder:
            directory = Path(folder)
            (directory / "cpu-execution.json").write_text('{"original":true}')
            with patch.object(supervisor, "HERE", directory), patch.object(supervisor.subprocess, "Popen") as spawn:
                with self.assertRaisesRegex(RuntimeError, "already exists"):
                    supervisor.parent()
                spawn.assert_not_called()
            self.assertEqual((directory / "cpu-execution.json").read_text(), '{"original":true}')

    def test_real_short_lived_workers_without_models(self):
        original_spawn = subprocess.Popen
        for code in (0, 7):
            with self.subTest(exit_code=code), tempfile.TemporaryDirectory(prefix="pdf-supervisor-") as folder:
                directory = Path(folder)
                def spawn(command, **kwargs):
                    self.assertEqual(command[-1], "--child")
                    return original_spawn(["rtk", "proxy", sys.executable, "-B", "-c",
                        f"import time; time.sleep(0.05); raise SystemExit({code})"], **kwargs)
                with patch.object(supervisor, "HERE", directory), \
                     patch.object(supervisor.subprocess, "Popen", side_effect=spawn):
                    supervisor.parent()
                record = json.loads((directory / "cpu-execution.json").read_text())
                self.assertEqual(record["status"], "completed" if code == 0 else "worker_error")
                self.assertEqual(record["exit_code"], code)
        self.assertNotIn("torch", sys.modules)
        self.assertNotIn("onnxruntime", sys.modules)


if __name__ == "__main__":
    unittest.main()
