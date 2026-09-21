"""Regression checks for the AA warm Pod adapter."""

import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pod_topology_aa as topology
import pod_preflight_aa as preflight
from sentinel import run_warm_pod_cgroup_aa as runner


class AAWarmPodAdapterTest(unittest.TestCase):
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

    def test_aa_is_new_inactive_fail_stop_identity(self):
        self.assertEqual(runner.RUN_IDENTITY, "q04-warm-pod-cgroup-20260921-aa")
        self.assertEqual(runner.PREFIX, "q04/warm-pod-cgroup-20260921-aa/")
        self.assertFalse(runner.authorization_scope()["automatic_retry"])
        self.assertEqual(topology.kubernetes_list()["items"][3]["spec"]["replicas"], 0)
        self.assertIn("pod_workload_aa.py", runner.workload_argv()[1])
        self.assertIn("pod_preflight_aa.py", runner.preflight_argv()[1])

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
            bundle = Path("/private/tmp/q04-inputs-warm-lifecycle-aa-final")
            _, result = preflight.verify_configuration_aa(
                capacity=capacity,
                authorization_scope_sha256=runner.authorization_scope_sha256(),
                source_manifest_path=source,
                bundle=bundle,
                expected_bundle_sha256=preflight.sha256(bundle / "inputs.json"),
            )
            self.assertEqual(result["status"], "PASS")

    def test_preflight_rejects_bundle_with_stale_harness_binding(self):
        source_bundle = Path("/private/tmp/q04-inputs-warm-lifecycle-aa-final")
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
                preflight.verify_configuration_aa(
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
            "sentinel.run_warm_pod_cgroup_s,sentinel.run_warm_pod_cgroup_aa",
            "sentinel.run_warm_pod_cgroup_aa,sentinel.run_warm_pod_cgroup_s",
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

    def test_preflight_gate_passes_from_exact_projected_workspace(self):
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
            document = (
                Path(__file__).resolve().parents[3]
                / "tests/pdf_processing/q04/pod-topology-v10/first-window-evidence"
                / "evidence/state/yolo-pod-cgroup-k/fresh-07/document.json"
            )
            subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import pod_preflight_aa; "
                    "import json,tempfile; from pathlib import Path; "
                    "from candidate.warm_pod_window_r import reviewed_reference_checker; "
                    "b=Path('/private/tmp/q04-inputs-warm-lifecycle-aa-final'); "
                    "pod_preflight_aa.verify_workload_imports_aa("
                    "workspace=Path.cwd(),bundle=b,"
                    "prefix='q04/warm-pod-cgroup-20260921-aa/'); "
                    "r=json.loads((b/'references/07.json').read_text()); "
                    f"d=json.loads(Path({str(document)!r}).read_text()); "
                    "c=reviewed_reference_checker(b,lambda *_args: None); "
                    "t=tempfile.TemporaryDirectory(); c(d,r,Path(t.name)); t.cleanup()",
                ],
                check=True,
                env=env,
                cwd=root,
                capture_output=True,
                text=True,
            )


if __name__ == "__main__":
    unittest.main()
