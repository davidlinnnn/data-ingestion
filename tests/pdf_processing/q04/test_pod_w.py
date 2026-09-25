"""Regression checks for the W warm Pod adapter."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pod_topology_w as topology
import pod_preflight_w as preflight
from sentinel import run_warm_pod_cgroup_w as runner


class WWarmPodAdapterTest(unittest.TestCase):
    def test_private_engine_binds_w_identity_before_function_definition(self):
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

    def test_w_is_new_inactive_fail_stop_identity(self):
        self.assertEqual(runner.RUN_IDENTITY, "q04-warm-pod-cgroup-20260921-w")
        self.assertEqual(runner.PREFIX, "q04/warm-pod-cgroup-20260921-w/")
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertIn("pod_workload_w.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_w.py", runner.preflight_argv()[1])

    def test_historical_w_bundle_is_rejected_after_x_sampler_repair(self):
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
            bundle = Path("/private/tmp/q04-inputs-warm-lifecycle-w-final")
            with self.assertRaisesRegex(ValueError, "bundle harness drift"):
                preflight.verify_configuration_w(
                    capacity=capacity,
                    authorization_scope_sha256=runner.authorization_scope_sha256(),
                    source_manifest_path=source,
                    bundle=bundle,
                    expected_bundle_sha256=preflight.sha256(bundle / "inputs.json"),
                )

    def test_preflight_rejects_bundle_with_stale_harness_binding(self):
        source_bundle = Path("/private/tmp/q04-inputs-warm-lifecycle-w-final")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            bundle.mkdir()
            for name in ("fixtures", "originals", "references", "oracles"):
                (bundle / name).symlink_to(source_bundle / name, target_is_directory=True)
            inputs = json.loads((source_bundle / "inputs.json").read_text())
            inputs["test_files"][
                "tests/pdf_processing/q04/sentinel/aima_attribution_telemetry_q.py"
            ] = "0" * 64
            (bundle / "inputs.json").write_text(json.dumps(inputs))
            capacity = root / "capacity.json"
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
            source = root / "source.json"
            source.write_text(json.dumps({"phase": preflight.TOPOLOGY_PHASE}))
            with self.assertRaisesRegex(ValueError, "bundle harness drift"):
                preflight.verify_configuration_w(
                    capacity=capacity,
                    authorization_scope_sha256=runner.authorization_scope_sha256(),
                    source_manifest_path=source,
                    bundle=bundle,
                    expected_bundle_sha256=preflight.sha256(bundle / "inputs.json"),
                )

    def test_s_and_w_import_order_is_isolated(self):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for modules in (
            "sentinel.run_warm_pod_cgroup_s,sentinel.run_warm_pod_cgroup_w",
            "sentinel.run_warm_pod_cgroup_w,sentinel.run_warm_pod_cgroup_s",
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

    def test_frozen_w_projection_retains_its_historical_sampler(self):
        source = json.loads(
            (Path(__file__).with_name("pod-topology-v22") / "SOURCE-MANIFEST.json").read_text()
        )
        name = "tests/pdf_processing/q04/sentinel/aima_attribution_telemetry_q.py"
        bundle = json.loads(
            Path("/private/tmp/q04-inputs-warm-lifecycle-w-final/inputs.json").read_text()
        )
        self.assertEqual(source["harness"][name], bundle["test_files"][name])
        self.assertNotEqual(source["harness"][name], preflight.sha256(Path(name)))


if __name__ == "__main__":
    unittest.main()
