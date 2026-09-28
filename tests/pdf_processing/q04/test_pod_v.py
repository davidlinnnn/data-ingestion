"""Regression checks for the V warm Pod adapter."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pod_topology_v as topology
import pod_preflight_v as preflight
from sentinel import run_warm_pod_cgroup_v as runner


class VWarmPodAdapterTest(unittest.TestCase):
    def test_private_engine_binds_v_identity_before_function_definition(self):
        deployment = {
            "metadata": {"name": topology.DEPLOYMENT, "uid": "t-deployment"}
        }
        owned = [{
            "kind": "Deployment",
            "name": topology.DEPLOYMENT,
            "uid": "t-deployment",
        }]
        self.assertIs(
            runner.base.validate_created_deployment(deployment, owned), deployment
        )
        self.assertEqual(
            runner.base.validate_created_deployment.__kwdefaults__["deployment_name"],
            topology.DEPLOYMENT,
        )
        for function in (
            runner.base.validate_pod,
            runner.base.capture_cleanup_identity,
            runner.base.await_worker_pod,
        ):
            self.assertEqual(
                function.__kwdefaults__["run_label"], topology.RUN_LABEL
            )
        self.assertEqual(
            runner.base.cleanup_deployment_and_pod.__kwdefaults__["deployment_name"],
            topology.DEPLOYMENT,
        )

    def test_import_restores_public_p_topology(self):
        public = importlib.import_module("pod_topology_p")
        self.assertEqual(public.PHASE, "q04-pod-cgroup-p")

    def test_v_is_new_inactive_fail_stop_identity(self):
        self.assertEqual(runner.RUN_IDENTITY, "q04-warm-pod-cgroup-20260921-v")
        self.assertEqual(runner.PREFIX, "q04/warm-pod-cgroup-20260921-v/")
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertIn("pod_workload_v.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_v.py", runner.preflight_argv()[1])

    def test_complete_preflight_configuration_gate_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            capacity = Path(tmp) / "capacity.json"
            source = Path(tmp) / "source.json"
            capacity.write_text(json.dumps({
                "status": "AUTHORIZED",
                "phase": preflight.PHASE,
                "authorization_scope_sha256": runner.authorization_scope_sha256(),
                "automatic_retry": False,
                "proposed_window_seconds": 1500,
                "outer_observation_seconds": 180,
                "outer_continuous_seconds": 60,
                "outer_admission_available_bytes": 4_831_838_208,
                "admission_available_bytes": 3_221_225_472,
                "minimum_work_seconds": 825,
                "cleanup_seconds": 300,
                "max_cgroup_bytes": 4_294_967_296,
                "container_hard_limit_bytes": 5_368_709_120,
            }))
            source.write_text(json.dumps({"phase": preflight.TOPOLOGY_PHASE}))
            bundle = Path("/private/tmp/q04-inputs-warm-lifecycle-q-final4")
            _, result = preflight.verify_configuration_v(
                capacity=capacity,
                authorization_scope_sha256=runner.authorization_scope_sha256(),
                source_manifest_path=source,
                bundle=bundle,
                expected_bundle_sha256=preflight.sha256(bundle / "inputs.json"),
            )
            self.assertEqual(result["status"], "PASS")

    def test_s_and_v_import_order_is_isolated(self):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for modules in (
            "sentinel.run_warm_pod_cgroup_s,sentinel.run_warm_pod_cgroup_v",
            "sentinel.run_warm_pod_cgroup_v,sentinel.run_warm_pod_cgroup_s",
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import importlib; [importlib.import_module(x) "
                    "for x in '" + modules + "'.split(',')]",
                ],
                check=True,
                env=env,
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parents[3],
            )

    def test_preflight_imports_from_exact_projected_workspace(self):
        rendered = topology.kubernetes_list()
        maps = {
            item["metadata"]["name"]: item["data"]
            for item in rendered["items"]
            if item["kind"] == "ConfigMap"
        }
        deployment = next(
            item for item in rendered["items"] if item["kind"] == "Deployment"
        )
        workspace = next(
            volume for volume in deployment["spec"]["template"]["spec"]["volumes"]
            if volume["name"] == "workspace"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for source in workspace["projected"]["sources"]:
                projection = source["configMap"]
                for item in projection["items"]:
                    path = root / item["path"]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(maps[projection["name"]][item["key"]])
            env = os.environ.copy()
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["PYTHONPATH"] = os.pathsep.join((
                str(root / "src"),
                str(root / "tests/pdf_processing/q04"),
                str(root / "tests/pdf_processing/q02"),
            ))
            subprocess.run(
                [sys.executable, "-c", "import pod_preflight_v"],
                check=True,
                env=env,
                cwd=root,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
