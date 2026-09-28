"""Local contracts for the current required-relationship interruption window."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import psutil
import signal
import subprocess
import sys
import tempfile
import unittest

from candidate.relationship_interruption_window_ao import validate_recovery, validate_scope
from host_ao import Host
import pod_preflight_ao as preflight
import pod_topology_ao as topology
import pod_workload_ao as workload
from sentinel import run_relationship_pod_cgroup_ao as runner
from worker_ao import audit_plan_incomplete, owned_evidence_child_command, should_inject


BUNDLE = Path("/private/tmp/q04-inputs-warm-continuation-v3-ah")
AL = Path("/private/tmp/q04-profile-pod-cgroup-20260924-al/evidence/state/profile-pod-cgroup-al")


class AORelationshipPodTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / "inputs.json").exists():
            raise unittest.SkipTest("private v3 bundle unavailable")

    def test_scoped_incomplete_audit_preserves_older_fresh_result(self):
        class Store:
            def __init__(self):
                self.registrations = {"pdf-complete-old": {"files": [{"name": "processing-result.json"}]}}
                self.plan = "old-plan"
            def resolve(self, identity):
                return self.registrations.get(identity)
            def read_artifact(self, _):
                return json.dumps({"plan": self.plan}).encode()
        store = Store()
        operations = ["pdf-complete-old"]
        self.assertEqual(audit_plan_incomplete(store, "new-evidence", "new-plan", operations), operations)
        store.plan = "new-plan"
        with self.assertRaisesRegex(RuntimeError, "complete_already_published"):
            audit_plan_incomplete(store, "new-evidence", "new-plan", operations)
        store.plan = "old-plan"
        store.registrations["new-evidence"] = {}
        with self.assertRaisesRegex(RuntimeError, "evidence_already_published"):
            audit_plan_incomplete(store, "new-evidence", "new-plan", operations)

    def test_single_generation_and_owned_child_commands(self):
        self.assertTrue(should_inject(1))
        self.assertFalse(should_inject(2))
        python = "/experiment/.venv/bin/python"
        self.assertTrue(owned_evidence_child_command(
            [python, "-m", "pdf_processing.evidence"], python))
        self.assertTrue(owned_evidence_child_command(
            [python, "-m", "pdf_processing.lifecycle_child", "pdf_processing.evidence"], python))
        self.assertFalse(owned_evidence_child_command(
            [python, "-m", "pdf_processing.lifecycle_child", "pdf_processing.parser"], python))

    def test_local_ao_stop_targets_exact_owned_worker(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "q04" / "worker_ao.py"
            path.parent.mkdir()
            path.write_text("import time\ntime.sleep(30)\n")
            command = [sys.executable, str(path)]
            process = subprocess.Popen(command)
            try:
                owner = psutil.Process(process.pid)
                current = Path(raw) / "worker-1"
                current.mkdir()
                (current / "ownership.json").write_text(json.dumps({
                    "pid": process.pid, "created": owner.create_time()}))
                host = Host.__new__(Host)
                host.config = {"python": sys.executable}
                host.current = current
                host.worker_command = command
                host.signal(process.pid, signal.SIGTERM)
                process.wait(timeout=5)
                self.assertIsNotNone(process.returncode)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()

    def test_identity_scope_projection_and_inactive_topology(self):
        path = topology.base.Q04 / "pod-topology-v40/RUNTIME-INTEGRATION-MANIFEST.json"
        manifest = json.loads(path.read_text())
        self.assertEqual(validate_scope(type("Args", (), {
            "integration_manifest": path,
            "authorization_scope_sha256": manifest["authorization_scope_sha256"],
            "name": workload.PHASE, "expected_run_id": runner.RUN_IDENTITY,
            "expected_prefix": runner.PREFIX})()), manifest)
        self.assertEqual(manifest["identity"]["prefix"], runner.PREFIX)
        self.assertEqual(runner.authorization_scope()["modes"],
                         ["fresh", "interrupt", "recovery", "replay"])
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(runner.authorization_scope()["expected_worker_generations"], 2)
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        source = topology.source_manifest()["harness"]
        self.assertIn("tests/pdf_processing/q04/worker_ao.py", source)
        self.assertIn("tests/pdf_processing/q03/interruption.py", source)
        self.assertIn("candidate.relationship_interruption_window_ao",
                      workload.build_measurement_argv(type("Args", (), {
                          "python": sys.executable, "bundle": BUNDLE,
                          "state": Path("/state"), "capacity": Path("/capacity"),
                          "prefix": runner.PREFIX, "workspace": topology.base.ROOT})(),
                          runner.RUN_IDENTITY, manifest["authorization_scope_sha256"]))
        self.assertEqual(runner.base.offline_check()["status"], "PASS_OFFLINE_ONLY")

    def test_recovery_contract_rejects_changed_request_or_missing_kill(self):
        if not (AL / "fresh-native/accepted.json").exists():
            self.skipTest("retained AL evidence unavailable")
        fresh = json.loads((AL / "fresh-native/accepted.json").read_text())
        recovery = json.loads((AL / "evidence-native/accepted.json").read_text())
        recovery = copy.deepcopy(recovery)
        for step in recovery["result"]["steps"]:
            if step["stage"] == "component_ocr":
                step["reused"] = True
        manifest = json.loads((topology.base.Q04 /
            "pod-topology-v40/RUNTIME-INTEGRATION-MANIFEST.json").read_text())
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            def write(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            write("fresh-native/accepted.json", fresh)
            write("recovery-native/accepted.json", recovery)
            replay = copy.deepcopy(recovery)
            replay["mode"] = "replay"
            replay["workflow_id"] += "-replay"
            for step in replay["result"]["steps"]:
                step["reused"] = True
            write("replay-native/accepted.json", replay)
            write("interrupted-native/admission.json", recovery)
            write("interrupted-native/result.json", {
                "status": "failed", "processing_complete": False,
                "error": {"category": "parser", "code": "execution_failed"},
                "plan": recovery["result"]["plan"], "registered_pages": 51,
                "registered_components": 7, "selected_components": 7,
                "steps": [{**step, "reused": False}
                          for step in recovery["result"]["steps"]]})
            write("worker-1/interruption-result.json", {
                "plan": recovery["result"]["plan"], "evidence_id": "evidence",
                "observation": {"signal": "SIGKILL", "scope": "owned evidence child only",
                    "progress": "first_page_decoded", "source_checked": True,
                    "evidence_id": "evidence"}})
            write("worker-1/interruption/partial-manifest.json", {"files": {"page-1.png": "hash"}})
            write("worker-1/stopped.json", {"parser_absent": True, "scratch_absent": True})
            write("interrupted-native/publication-outcome.json", {"ok": True})
            write("interrupted-native/failure-history.json", {"events": [
                {"eventType": "EVENT_TYPE_ACTIVITY_TASK_FAILED"},
                {"eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"}]})
            for label in ("fresh-native", "recovery-native", "replay-native"):
                write(f"{label}/history.json", {"events": [
                    {"eventType": "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"}]})
            validate_recovery(root, manifest)
            broken = copy.deepcopy(recovery)
            broken["request"]["request_id"] = "changed"
            write_path = root / "replay-native/accepted.json"
            write_path.write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, "recovery changed accepted request"):
                validate_recovery(root, manifest)
            write_path.write_text(json.dumps(replay))
            broken = copy.deepcopy(recovery)
            next(step for step in broken["result"]["steps"]
                 if step["stage"] == "component_ocr")["reused"] = False
            (root / "recovery-native/accepted.json").write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, "new evidence downstream identity missing"):
                validate_recovery(root, manifest)

    def test_cleanup_ignores_worker_logs(self):
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            worker = state / workload.PHASE / "worker-1"
            worker.mkdir(parents=True)
            (worker.parent / "worker-1.log").write_text("retained")
            (worker / "stopped.json").write_text(json.dumps({
                "parser_absent": True, "scratch_absent": True}))
            self.assertEqual(workload.cleanup_markers(state)["worker_generations"], 1)

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
                "import pod_preflight_ao; from pathlib import Path; "
                "pod_preflight_ao.verify_workload_imports_ao("
                f"workspace=Path({str(root)!r}),"
                f"bundle=Path({str(BUNDLE)!r}),"
                f"prefix={runner.PREFIX!r})"],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
