"""Replay the real controller loop and worker/log layout without a cluster."""
import ast
import importlib
import json
import contextlib
import hashlib
import tarfile
import io
import subprocess
import sys
from unittest.mock import patch
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

VERSION = os.environ.get("Q04_RUNNER_VERSION", "i")
runner = importlib.import_module("sentinel.run_yolo_pod_cgroup_" + VERSION)
workload = importlib.import_module("pod_workload_" + VERSION)

class StopRegressions(unittest.TestCase):
    def test_rejected_sample_is_flushed_before_guard_raises(self):
        # Execute the actual production loop through its first identity check.
        tree = ast.parse(Path(runner.__file__).read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute_window")
        loop = next(n for n in ast.walk(function) if isinstance(n, ast.While) and ast.unparse(n.test) == "workload.poll() is None")
        boundary = next(i for i,n in enumerate(loop.body) if isinstance(n, ast.If) and "next_identity" in ast.unparse(n.test))
        module = ast.Module(body=loop.body[:boundary], type_ignores=[])
        baseline = {"time": 1, "available": 7 * 1024**3, "psi_full_avg10": 0.01,
                    "vm_oom_kill": 0, "memory_events": {}, "memory_current": 1024**3,
                    "evidence_used_bytes": 0, "evidence_free_bytes": 1024**3,
                    "evidence_filesystem_free_bytes": 1024**3}
        for field, value, message in (("psi_full_avg10", .01, "PSI guard"),
                                      ("available", 0, "memory floor"),
                                      ("vm_oom_kill", 1, "OOM counter"),
                                      ("time", 3, "telemetry gap")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                row = {**baseline, "psi_full_avg10": 0, field: value}
                path = Path(directory) / "samples.jsonl"
                with path.open("w") as stream:
                    namespace = {**vars(runner), "kube": SimpleNamespace(exec_python=lambda *a, **k: json.dumps(row)),
                                 "pod": "owned", "workload_deadline": 100,
                                 "remaining_timeout": lambda *a: 30,
                                 "sample_program": lambda: "sample", "baseline_oom": 0,
                                 "vm_rows": [{**baseline, "time": .5}], "vm_stream": stream}
                    with self.assertRaisesRegex(ValueError, message):
                        exec(compile(module, str(runner.__file__), "exec"), namespace)
                    self.assertEqual(path.read_text(), json.dumps(row, sort_keys=True) + "\n")

    def test_worker_log_sibling_does_not_block_terminal_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            phase = state / workload.PHASE
            worker = phase / "worker-1"
            worker.mkdir(parents=True)
            stopped = {"parser_absent": True, "scratch_absent": True}
            (worker / "stopped.json").write_text(json.dumps(stopped))
            (phase / "worker-1.log").write_text("worker trace\n")
            result = workload.cleanup_markers(state)
            self.assertEqual(result["worker_generations"], 1)
            self.assertTrue(result["worker_absent"])
            self.assertEqual(result["stopped"], [stopped])

    def test_terminal_rejecting_sample_is_saved(self):
        tree = ast.parse(Path(runner.__file__).read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute_window")
        block = next(n for n in ast.walk(function) if isinstance(n, ast.Try)
                     and n.body and isinstance(n.body[0], ast.Assign)
                     and ast.unparse(n.body[0].targets[0]) == "terminal_sample")
        with tempfile.TemporaryDirectory() as directory:
            row = {"available": 7 * 1024**3, "psi_full_avg10": .54}
            namespace = {**vars(runner), "OUT": Path(directory), "cleanup": {},
                         "pod_identity": {"pod_name": "owned"}, "cleanup_deadline": 100,
                         "capacity": {"expected_vm_oom_kill": 0},
                         "remaining_timeout": lambda *a: 30,
                         "kube": SimpleNamespace(exec_python=lambda *a, **k: json.dumps(row))}
            exec(compile(ast.Module(body=[block], type_ignores=[]), str(runner.__file__), "exec"), namespace)
            self.assertEqual(json.loads((Path(directory) / "terminal-cgroup-sample.json").read_text()), row)
            self.assertFalse(namespace["cleanup"]["terminal_cgroup_oom_proof"])

    def test_sample_contains_both_pressure_scopes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "/proc/meminfo": "MemAvailable: 7000000 kB\n",
                "/proc/vmstat": "oom_kill 0\n",
                "/proc/pressure/memory": "some avg10=0.80 avg60=0.10 avg300=0.00 total=12345\nfull avg10=0.54 avg60=0.10 avg300=0.00 total=12300\n",
                "/sys/fs/cgroup/memory.pressure": "some avg10=0.00 total=0\nfull avg10=0.00 total=0\n",
                "/sys/fs/cgroup/memory.current": "1024",
                "/sys/fs/cgroup/memory.events": "oom 0\noom_kill 0\noom_group_kill 0\n",
                "/sys/fs/cgroup/memory.stat": "anon 512\nfile 512\npgmajfault 0\n",
            }
            code = runner.sample_program()
            for name, data in files.items():
                target = root / name.lstrip("/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(data)
                code = code.replace(name, str(target))
            evidence = root / "evidence"
            evidence.mkdir()
            code = code.replace(runner.EVIDENCE, str(evidence))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(code, {})
            row = json.loads(output.getvalue())
            self.assertEqual(row["psi_full_avg10"], .54)
            self.assertEqual(row["node_memory_pressure"], files["/proc/pressure/memory"])
            self.assertEqual(row["cgroup_memory_pressure"], files["/sys/fs/cgroup/memory.pressure"])
            self.assertLessEqual(row["sample_started_at"], row["time"])

    def test_supervisor_interruption_seals_failed_workload_with_log_sibling(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "control"
            root.mkdir()
            args = workload.parser().parse_args(["--prefix", runner.PREFIX,
                "--authorization-scope-sha256", "a" * 64,
                "--control", str(root), "--state", str(root / "state"),
                "--capacity", str(root / "capacity.json"), "--workspace", str(Path(directory) / "workspace")])
            worker = args.state / workload.PHASE / "worker-1"
            worker.mkdir(parents=True)
            (worker / "stopped.json").write_text(json.dumps({"parser_absent": True, "scratch_absent": True}))
            (worker.parent / "worker-1.log").write_text("trace\n")
            (args.state / "config.json").write_text(json.dumps({"run_id": workload.RUN_ID}))
            args.capacity.write_text("{}")
            (root / "evidence-volume-identity.json").write_text('{"pvc_uid":"owned"}')
            measurement_argv = workload.build_measurement_argv(args, args.run_id, "reviewed")
            manifest = Path(measurement_argv[measurement_argv.index("--integration-manifest") + 1])
            manifest.parent.mkdir(parents=True)
            manifest.write_text('{"authorization_scope_sha256":"reviewed"}')
            remote = importlib.import_module("pod_remote_evidence_" + VERSION)
            config_hash = hashlib.sha256((args.state / "config.json").read_bytes()).hexdigest()
            identity = remote.PodEvidenceIdentity("owned-pod", "owned-container", os.getpid(), 1, config_hash)
            (root / "transport-identity.json").write_text(json.dumps(identity.__dict__))
            process = SimpleNamespace(pid=123, returncode=None)
            def wait(**kwargs):
                raise KeyboardInterrupt()
            process.wait = wait
            def stop(*args, **kwargs):
                process.returncode = 1
                return False
            with patch.object(workload, "require_pre_inference_gates"), patch.object(workload, "start_ticks", return_value=1), \
                 patch.object(workload, "adopt_budget", return_value={"config_sha256":config_hash}), \
                 patch.object(workload.subprocess, "run", return_value=SimpleNamespace(returncode=0,stdout="",stderr="")), \
                 patch.object(workload.subprocess, "Popen", return_value=process), patch.object(workload, "stop_group", side_effect=stop):
                with self.assertRaises(KeyboardInterrupt):
                    workload.run(args)
            sealed = json.loads((root / "durable-terminal-manifest.json").read_text())
            self.assertTrue(sealed["terminal"])
            self.assertTrue(sealed["cleanup_complete"])
            self.assertFalse(sealed["workload_succeeded"])
            self.assertEqual(sealed["status"], "INCOMPLETE")
            self.assertEqual(json.loads((root / "supervisor-interruption.json").read_text())["type"], "KeyboardInterrupt")
            # Replay the real receiver/archive path after supervisor exit.
            mirror = remote.IncrementalEvidenceMirror(Path(directory) / "mirror", identity)
            # The synthetic /proc view reports the now-exited supervisor absent.
            code = mirror.request_program(str(root)).replace(
                "Path('/proc')", "Path(" + repr(str(Path(directory) / "absent-proc")) + ")")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(code, {})
            mirror.ingest(json.loads(output.getvalue()), received_at=1)
            result = mirror.finalize(require_success=False)
            self.assertEqual(result["status"], "FAILURE_EVIDENCE_RETAINED")
            fingerprint = [[str(p.relative_to(root)), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()]
                           for p in sorted(root.rglob("*")) if p.is_file()]
            mirror.verify_archive_fingerprint(fingerprint)
            archive = Path(directory) / "evidence.tar"
            with tarfile.open(archive, "w") as tar:
                tar.add(root, arcname=".")
            runner.verify_local_archive(archive, fingerprint)

    def test_real_process_group_interrupt_is_reaped(self):
        process = subprocess.Popen([sys.executable, "-c",
            "import signal,time; signal.signal(signal.SIGINT, lambda *a: exit(0)); print('ready',flush=True); time.sleep(30)"],
            stdout=subprocess.PIPE, text=True, start_new_session=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), "ready")
            self.assertFalse(workload.stop_group(process, graceful_seconds=2))
            self.assertEqual(process.returncode, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()

if __name__ == "__main__":
    unittest.main()
