"""Regression checks for the S warm Pod adapter."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pod_topology_s as topology
import pod_preflight_s as preflight
from sentinel import run_warm_pod_cgroup_s as runner


class SWarmPodAdapterTest(unittest.TestCase):
    def test_private_engine_binds_s_identity_before_function_definition(self):
        deployment = {
            "metadata": {"name": topology.DEPLOYMENT, "uid": "s-deployment"}
        }
        owned = [{
            "kind": "Deployment",
            "name": topology.DEPLOYMENT,
            "uid": "s-deployment",
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

    def test_s_is_new_inactive_fail_stop_identity(self):
        self.assertEqual(runner.RUN_IDENTITY, "q04-warm-pod-cgroup-20260921-s")
        self.assertEqual(runner.PREFIX, "q04/warm-pod-cgroup-20260921-s/")
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertIn("pod_workload_s.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_s.py", runner.preflight_argv()[1])

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
            _, result = preflight.verify_configuration_s(
                capacity=capacity,
                authorization_scope_sha256=runner.authorization_scope_sha256(),
                source_manifest_path=source,
                bundle=bundle,
                expected_bundle_sha256=preflight.sha256(bundle / "inputs.json"),
            )
            self.assertEqual(result["status"], "PASS")

    def test_r_and_s_import_order_is_isolated(self):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for modules in (
            "sentinel.run_warm_pod_cgroup_r,sentinel.run_warm_pod_cgroup_s",
            "sentinel.run_warm_pod_cgroup_s,sentinel.run_warm_pod_cgroup_r",
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


if __name__ == "__main__":
    unittest.main()
