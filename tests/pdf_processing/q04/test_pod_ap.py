"""Local contracts for the AP observed relationship window."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from candidate.relationship_interruption_window_ao import validate_scope
import pod_topology_ap as topology
import pod_workload_ap as workload
from sentinel import node_pressure_attribution as probe
from sentinel import run_relationship_pod_cgroup_ap as runner
from sentinel import run_relationship_pod_cgroup_ap_guarded as guarded


BUNDLE = Path("/private/tmp/q04-inputs-warm-continuation-v3-ah")


class APObservedRelationshipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / "inputs.json").exists():
            raise unittest.SkipTest("private v3 bundle unavailable")

    def test_identity_scope_and_owned_probe_command(self):
        path = topology.base.Q04 / "pod-topology-v41/RUNTIME-INTEGRATION-MANIFEST.json"
        manifest = json.loads(path.read_text())
        args = type("Args", (), {
            "integration_manifest": path,
            "authorization_scope_sha256": manifest["authorization_scope_sha256"],
            "name": workload.PHASE, "expected_run_id": runner.RUN_IDENTITY,
            "expected_prefix": runner.PREFIX})()
        self.assertEqual(validate_scope(args), manifest)
        self.assertEqual(topology.base.OBJECT_PREFIX, runner.PREFIX)
        self.assertEqual(runner.authorization_scope()["node_pressure_observer"], {
            "read_only": True, "sample_interval_seconds": .25, "owned_stop": True})
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertIn("run_relationship_pod_cgroup_ap_guarded.py", runner.exact_command())
        self.assertEqual(guarded.owned_probe_command()[-2:],
                         ["--run-id", runner.RUN_IDENTITY])
        compile(guarded.OWNER_PROGRAM, "owner", "exec")
        probe.self_test()
        self.assertEqual(runner.base.offline_check()["status"], "PASS_OFFLINE_ONLY")

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
                "import pod_preflight_ap; from pathlib import Path; "
                "pod_preflight_ap.verify_workload_imports_ap("
                f"workspace=Path({str(root)!r}),"
                f"bundle=Path({str(BUNDLE)!r}),"
                f"prefix={runner.PREFIX!r})"],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
