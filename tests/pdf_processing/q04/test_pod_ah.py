"""Local contracts for the v3-bound Q04 warm Pod adapter."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from candidate.warm_v3_reference import reviewed_reference_checker, verify_v3_bundle
from consumer import check_reference
import pod_preflight_ah as preflight
import pod_topology_ah as topology
import pod_workload_ah as workload
from sentinel import run_warm_pod_cgroup_ah as runner


BUNDLE = Path("/private/tmp/q04-inputs-warm-continuation-v3-ah")
CAPTURES = Path("/private/tmp/q04-local-native-v3-envelope")


class AHWarmPodAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BUNDLE / "inputs.json").exists():
            raise unittest.SkipTest("private AH bundle unavailable")

    def test_identity_argv_and_inactive_topology(self):
        manifest = json.loads((topology.base.Q04 / "pod-topology-v33/RUNTIME-INTEGRATION-MANIFEST.json").read_text())
        self.assertEqual(manifest["identity"], {
            "phase": workload.PHASE,
            "run_id": runner.RUN_IDENTITY,
            "prefix": runner.PREFIX,
        })
        self.assertEqual(topology.OBJECT_PREFIX, runner.PREFIX)
        self.assertEqual(topology.source_manifest()["producer"]["continuation.py"],
                         verify_v3_bundle(BUNDLE)[0]["continuation_source_sha256"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertIn("pod_workload_ah.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_ah.py", runner.preflight_argv()[1])
        measurement = workload.build_measurement_argv(
            type("Args", (), {"python": sys.executable, "bundle": BUNDLE,
                "state": Path("/state"), "capacity": Path("/capacity"),
                "prefix": runner.PREFIX, "workspace": topology.base.ROOT})(),
            runner.RUN_IDENTITY, manifest["authorization_scope_sha256"])
        self.assertIn("candidate.warm_pod_window_v3", measurement)
        self.assertIn("pod-topology-v33/RUNTIME-INTEGRATION-MANIFEST.json",
                      " ".join(measurement))
        self.assertEqual(runner.base.validate_created_deployment.__kwdefaults__["deployment_name"],
                         topology.DEPLOYMENT)
        self.assertEqual(runner.base.cleanup_deployment_and_pod.__kwdefaults__["deployment_name"],
                         topology.DEPLOYMENT)
        self.assertEqual(runner.base.offline_check()["status"], "PASS_OFFLINE_ONLY")

    def test_preflight_contract_and_stale_bundle_rejection(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            capacity = root / "capacity.json"
            capacity.write_text(json.dumps({
                "status": "AUTHORIZED", "phase": preflight.PHASE,
                "authorization_scope_sha256": runner.authorization_scope_sha256(),
                "automatic_retry": False, "proposed_window_seconds": 1500,
                "outer_observation_seconds": 180, "outer_continuous_seconds": 60,
                "outer_admission_available_bytes": 4_831_838_208,
                "admission_available_bytes": 3_221_225_472,
                "minimum_work_seconds": 825, "cleanup_seconds": 300,
                "max_cgroup_bytes": 4_294_967_296,
                "container_hard_limit_bytes": 5_368_709_120,
            }))
            source = root / "source.json"
            source.write_text(json.dumps(topology.source_manifest()))
            kwargs = dict(capacity=capacity,
                          authorization_scope_sha256=runner.authorization_scope_sha256(),
                          source_manifest_path=source, bundle=BUNDLE,
                          expected_bundle_sha256=preflight.sha256(BUNDLE / "inputs.json"))
            self.assertEqual(preflight.verify_configuration_ah(**kwargs)[1]["status"], "PASS")
            with self.assertRaisesRegex(ValueError, "frozen bundle inputs changed"):
                preflight.verify_configuration_ah(**{**kwargs, "expected_bundle_sha256": "0" * 64})
            with self.assertRaisesRegex(ValueError, "capacity configuration changed"):
                capacity.write_text(capacity.read_text().replace("1500", "1501"))
                preflight.verify_configuration_ah(**kwargs)

    def test_exact_graph_and_method_fail_closed(self):
        if not (CAPTURES / "capture-native/document.json").exists():
            self.skipTest("offline captures unavailable")
        checker = reviewed_reference_checker(BUNDLE, check_reference)
        for sid in ("native", "06", "07", "09", "10"):
            document = json.loads((CAPTURES / f"capture-{sid}/document.json").read_text())
            reference = json.loads((BUNDLE / "references" / f"{sid}.json").read_text())
            with self.subTest(sid=sid), tempfile.TemporaryDirectory() as raw:
                self.assertEqual(checker(document, reference, Path(raw)),
                                 verify_v3_bundle(BUNDLE)[0]["local_v3_graph_sha256"][sid])
                altered = copy.deepcopy(document)
                altered["texts"][0]["text"] += "!"
                with self.assertRaisesRegex(ValueError, "graph differs"):
                    checker(altered, reference, Path(raw))
        with tempfile.TemporaryDirectory() as raw:
            candidate = Path(raw)
            data = json.loads((BUNDLE / "inputs.json").read_text())
            data["base_profile"]["method"]["continuation"]["version"] = "column-edge-continuation-v2"
            (candidate / "inputs.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "bundle or oracle bytes changed"):
                verify_v3_bundle(candidate)

    def test_cleanup_ignores_worker_log_and_preserves_stop_proof(self):
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            phase = state / workload.PHASE
            worker = phase / "worker-1"
            worker.mkdir(parents=True)
            (phase / "worker-1.log").write_text("retained log")
            (worker / "stopped.json").write_text(json.dumps({
                "parser_absent": True, "scratch_absent": True}))
            self.assertEqual(workload.cleanup_markers(state)["worker_generations"], 1)
            self.assertTrue(workload.cleanup_markers(state)["owned_children_absent"])

    @unittest.skipUnless(importlib.util.find_spec("pypdfium2"), "pinned image required")
    def test_v3_driver_does_not_mutate_r_driver_in_either_import_order(self):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for order in ("r,v3", "v3,r"):
            code = (
                "import importlib; "
                "names={'r':'candidate.warm_pod_window_r',"
                "'v3':'candidate.warm_pod_window_v3'}; "
                f"[importlib.import_module(names[x]) for x in {order!r}.split(',')]; "
                "r=importlib.import_module(names['r']); "
                "v3=importlib.import_module(names['v3']); "
                "assert r.reviewed_reference_checker is not v3.base.reviewed_reference_checker; "
                "assert v3.base.reviewed_reference_checker is v3.reviewed_reference_checker"
            )
            result = subprocess.run([sys.executable, "-c", code], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

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
                "import pod_preflight_ah; from pathlib import Path; "
                "pod_preflight_ah.verify_workload_imports_ah("
                f"workspace=Path({str(root)!r}),"
                f"bundle=Path({str(BUNDLE)!r}),"
                f"prefix={runner.PREFIX!r})"],
                cwd=root, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
