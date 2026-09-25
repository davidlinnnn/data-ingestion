"""Local contracts for the AR observed relationship window."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from candidate import relationship_interruption_window_ao as matrix
from candidate.relationship_interruption_window_ao import validate_scope
import pod_topology_ar as topology
import pod_workload_ar as workload
from sentinel import node_pressure_attribution as probe
from sentinel import run_relationship_pod_cgroup_ar as runner
from sentinel import run_relationship_pod_cgroup_ar_guarded as guarded


BUNDLE = Path("/private/tmp/q04-inputs-warm-continuation-v3-ah")


class ARObservedRelationshipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / "inputs.json").exists():
            raise unittest.SkipTest("private v3 bundle unavailable")

    def test_identity_scope_and_owned_probe_command(self):
        path = topology.base.Q04 / "pod-topology-v43/RUNTIME-INTEGRATION-MANIFEST.json"
        manifest = json.loads(path.read_text())
        args = type("Args", (), {
            "integration_manifest": path,
            "authorization_scope_sha256": manifest["authorization_scope_sha256"],
            "name": workload.PHASE, "expected_run_id": runner.RUN_IDENTITY,
            "expected_prefix": runner.PREFIX})()
        self.assertEqual(validate_scope(args), manifest)
        self.assertEqual(topology.base.OBJECT_PREFIX, runner.PREFIX)
        self.assertEqual(runner.authorization_scope()["node_pressure_observer"], {
            "read_only": True, "sample_interval_seconds": .25, "owned_stop": True,
            "cgroup_namespace": "host", "network": "none",
            "image_id": guarded.PROBE_IMAGE})
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertIn("run_relationship_pod_cgroup_ar_guarded.py", runner.exact_command())
        command = shlex.split(runner.exact_command())
        parsed = runner.base.parser().parse_args(command[2:])
        self.assertTrue(parsed.execute)
        self.assertEqual(parsed.authorization_scope_sha256,
                         runner.authorization_scope_sha256())
        self.assertTrue(parsed.approval_reference)
        self.assertEqual(guarded.owned_probe_command()[-2:],
                         ["--run-id", runner.RUN_IDENTITY])
        self.assertIn("--cgroupns=host", guarded.owned_probe_command())
        self.assertIn("--network=none", guarded.owned_probe_command())
        self.assertIn("--read-only", guarded.owned_probe_command())
        self.assertIn("--pull=never", guarded.owned_probe_command())
        probe.self_test()
        self.assertEqual(runner.base.offline_check()["status"], "PASS_OFFLINE_ONLY")

    def test_ocr_phase_trace_preserves_fixture_result(self):
        from pdf_processing.ocr import execute as original_execute
        spec = importlib.util.spec_from_file_location('q04_ar_diagnostic_ocr',
            topology.base.Q04 / 'pod-topology-v43/ocr.py')
        diagnostic_ocr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(diagnostic_ocr)
        parsed = Path('/private/tmp/q04-relationship-pod-cgroup-20260925-aq/failure-evidence/state/relationship-pod-cgroup-aq/fresh-native/document.json')
        if not parsed.exists():
            self.skipTest('retained AQ parsed document unavailable')
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            request = {'parsed': str(parsed), 'pdf': str(BUNDLE / 'fixtures/native.pdf'),
                       'component': '#/pictures/2', 'scale': 3, 'allow_cropbox': True}
            original_execute({**request, 'out': str(root / 'plain')})
            with patch.dict(os.environ, {'Q04_OCR_TRACE_DIR': str(root / 'trace')}):
                diagnostic_ocr.execute({**request, 'out': str(root / 'observed')})
            plain = json.loads((root / 'plain/ocr.json').read_text())
            observed = json.loads((root / 'observed/ocr.json').read_text())
            plain.pop('seconds_including_engine_load')
            observed.pop('seconds_including_engine_load')
            self.assertEqual(plain, observed)
            self.assertEqual((root / 'plain/figure.png').read_bytes(),
                             (root / 'observed/figure.png').read_bytes())
            rows = [json.loads(line) for path in (root / 'trace').glob('*.jsonl')
                    for line in path.read_text().splitlines()]
            self.assertEqual([row['stage'] for row in rows],
                             runner.authorization_scope()['ocr_phase_trace']['stages'])
            env = topology.kubernetes_list()['items'][3]['spec']['template']['spec']['containers'][0]['env']
            self.assertIn({'name': 'Q04_OCR_TRACE_DIR',
                           'value': runner.authorization_scope()['ocr_phase_trace']['directory']}, env)

    def test_measurement_argv_parses_at_real_entrypoint(self):
        args = type("Args", (), {"python": "python", "bundle": Path("/bundle"),
            "state": Path("/state"), "capacity": Path("/capacity"),
            "prefix": runner.PREFIX, "workspace": Path("/workspace")})()
        argv = workload.build_measurement_argv(args, runner.RUN_IDENTITY, "inner-sha")
        async def no_runtime(_args):
            return None
        with patch.object(matrix, "run_window", no_runtime):
            self.assertEqual(matrix.main(argv[3:]), 0)

    def test_inspect_daemon_error_is_not_absence(self):
        with tempfile.TemporaryDirectory() as raw:
            cid = Path(raw) / "observer.cid"
            cid.write_text("expected-container")
            failed = subprocess.CompletedProcess([], 1, "", "Cannot connect to Docker daemon")
            with patch.object(guarded, "PROBE_CID", cid), \
                 patch.object(guarded, "inspect_probe", return_value=failed):
                with self.assertRaisesRegex(RuntimeError, "absence unverified"):
                    guarded.owner("verify", {"container_id": "expected-container"})
                with self.assertRaisesRegex(RuntimeError, "stop unverified"):
                    guarded.owner("stop", {"container_id": "expected-container"})

    def test_probe_cleanup_records_remote_stop_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "probe.jsonl"
            output.write_text('{"kind":"start","time":1}\n'
                              '{"kind":"sample","started_at":1,"ended_at":1.25,"node_full_delta_us":0}\n'
                              '{"kind":"end","time":1.25}\n')
            cleanup = Path(raw) / "cleanup.json"
            class Process:
                def wait(self, timeout):
                    return 0
            calls = []
            def owner(action, identity):
                calls.append(action)
                if action == "stop":
                    raise subprocess.CalledProcessError(1, "docker")
                return {"matches": [], "action": action}
            with patch.object(guarded, "PROBE_OUT", output), \
                 patch.object(guarded, "PROBE_CLEANUP", cleanup), \
                 patch.object(guarded, "owner", owner):
                with self.assertRaisesRegex(RuntimeError, "cleanup"):
                    guarded.stop_probe(Process(), {"time": 1})
            result = json.loads(cleanup.read_text())
            self.assertEqual(calls, ["stop", "verify"])
            self.assertFalse(result["remote_stop"]["ok"])
            self.assertTrue(result["remote_absence"]["ok"])
            self.assertTrue(result["terminal"]["ok"])
            self.assertFalse(result["complete"])

    def test_probe_cleanup_records_transport_timeout(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "probe.jsonl"
            output.write_text('{"kind":"start","time":1}\n'
                              '{"kind":"sample","started_at":1,"ended_at":1.25,"node_full_delta_us":0}\n'
                              '{"kind":"end","time":1.25}\n')
            cleanup = Path(raw) / "cleanup.json"
            class Process:
                def __init__(self):
                    self.forced = False
                def wait(self, timeout):
                    if not self.forced:
                        raise subprocess.TimeoutExpired("docker", timeout)
                    return -15
                def terminate(self):
                    self.forced = True
            process = Process()
            calls = []
            def owner(action, identity):
                calls.append(action)
                return {"matches": [], "action": action}
            with patch.object(guarded, "PROBE_OUT", output), \
                 patch.object(guarded, "PROBE_CLEANUP", cleanup), \
                 patch.object(guarded, "owner", owner):
                with self.assertRaisesRegex(RuntimeError, "cleanup"):
                    guarded.stop_probe(process, {"time": 1})
            result = json.loads(cleanup.read_text())
            self.assertTrue(process.forced)
            self.assertEqual(calls, ["stop", "verify"])
            self.assertFalse(result["transport"]["ok"])
            self.assertTrue(result["remote_absence"]["ok"])
            self.assertTrue(result["terminal"]["ok"])
            self.assertFalse(result["complete"])

    def test_host_probe_refuses_identity_change_before_stop(self):
        with tempfile.TemporaryDirectory() as raw:
            cid = Path(raw) / "observer.cid"
            cid.write_text("expected-container")
            with patch.object(guarded, "PROBE_CID", cid), \
                 patch.object(guarded, "inspect_probe") as inspect, \
                 patch.object(guarded.subprocess, "check_call") as stop:
                with self.assertRaisesRegex(RuntimeError, "identity changed"):
                    guarded.owner("stop", {"container_id": "other-container"})
            inspect.assert_not_called()
            stop.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec("pypdfium2"), "pinned image required")
    def test_exact_projected_workspace_imports(self):
        rendered = topology.kubernetes_list()
        maps = {item["metadata"]["name"]: item["data"] for item in rendered["items"]
                if item["kind"] == "ConfigMap"}
        deployment = next(item for item in rendered["items"] if item["kind"] == "Deployment")
        volume = next(item for item in deployment["spec"]["template"]["spec"]["volumes"]
                      if item["name"] == "workspace")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for source in volume["projected"]["sources"]:
                projection = source["configMap"]
                for item in projection["items"]:
                    path = root / item["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(maps[projection["name"]][item["key"]])
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONPATH"] = os.pathsep.join((str(root / "src"),
                str(root / "tests/pdf_processing/q04"),
                str(root / "tests/pdf_processing/q02"),
                str(root / "tests/pdf_processing/q03")))
            result = subprocess.run([sys.executable, "-c",
                "import pod_preflight_ar; from pathlib import Path; "
                "pod_preflight_ar.verify_workload_imports_ar("
                f"workspace=Path({str(root)!r}),"
                f"bundle=Path({str(BUNDLE)!r}),"
                f"prefix={runner.PREFIX!r})"],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
