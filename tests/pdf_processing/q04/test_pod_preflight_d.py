"""Offline checks for the one-shot Q04 Pod pre-inference gate set."""

import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from unittest import mock

import pod_preflight_d as preflight
import pod_evidence_directory_d as evidence_directory


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class PodPreflightDTests(unittest.TestCase):
    def pod_identity(self, root: Path) -> Path:
        path = root / "pod-identity.json"
        path.write_text(json.dumps({
            "pod_name": "worker-d",
            "pod_uid": "pod-uid-d",
            "container_id": "containerd://worker-d",
            "node": preflight.EXPECTED_NODE,
            "image_id": preflight.EXPECTED_IMAGE,
            "image_id_representation": "repository-platform-manifest",
            "restart_count": 0,
        }))
        return path

    def test_source_hash_gate_covers_producer_and_harness(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            producer = workspace / "src/pdf_processing/a.py"
            harness = workspace / "tests/check.py"
            producer.parent.mkdir(parents=True)
            harness.parent.mkdir(parents=True)
            producer.write_bytes(b"producer\n")
            harness.write_bytes(b"harness\n")
            manifest = {
                "producer": {"a.py": digest(producer.read_bytes())},
                "harness": {"tests/check.py": digest(harness.read_bytes())},
                "producer_set_sha256": "producer-set",
                "harness_set_sha256": "harness-set",
            }
            result = preflight.verify_sources(workspace, manifest)
            self.assertEqual(result["producer_files"], 1)
            self.assertEqual(result["harness_files"], 1)
            harness.write_bytes(b"changed\n")
            with self.assertRaisesRegex(ValueError, "source hash changed"):
                preflight.verify_sources(workspace, manifest)

    def test_runtime_gate_checks_executable_packages_models_and_cgroup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "models"
            model.mkdir()
            expected_models = {}
            for index in range(17):
                path = model / f"expected-{index:02d}.bin"
                path.write_bytes(f"model-{index}".encode())
                expected_models[path.name] = preflight.sha256(path)
            for index in range(18):
                (model / f"cache-{index:02d}.meta").write_text("cache")
            packages = {name: "fixed" for name in preflight.PACKAGES.values()}
            provenance = root / "provenance.json"
            provenance.write_text(json.dumps({
                "fresh_accepted": {"profile": {"method": {
                    "python": platform.python_version(),
                    "packages": packages,
                    "model_artifacts": expected_models,
                }}}
            }))
            cgroup = root / "cgroup"
            cgroup.mkdir()
            (cgroup / "memory.max").write_text(str(5 * 1024**3))
            (cgroup / "memory.events").write_text(
                "low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\noom_group_kill 0\n"
            )
            with mock.patch.object(preflight.importlib, "import_module"), mock.patch.object(
                preflight.metadata, "version", return_value="fixed"
            ):
                result = preflight.verify_runtime_environment(
                    model_cache=model,
                    provenance=provenance,
                    python=Path(sys.executable),
                    cgroup_root=cgroup,
                )
            self.assertEqual(result["model_artifacts"], 17)
            self.assertEqual(result["model_files"], 35)
            (model / "expected-00.bin").write_bytes(b"wrong")
            with mock.patch.object(preflight.importlib, "import_module"), mock.patch.object(
                preflight.metadata, "version", return_value="fixed"
            ), self.assertRaisesRegex(ValueError, "model artifact"):
                preflight.verify_runtime_environment(
                    model_cache=model,
                    provenance=provenance,
                    python=Path(sys.executable),
                    cgroup_root=cgroup,
                )

    def test_single_preflight_returns_all_gates_without_starting_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            capacity = root / "capacity.json"
            capacity.write_text(json.dumps({
                "status": "AUTHORIZED",
                "phase": "yolo-pod-cgroup-d",
                "authorization_scope_sha256": "scope",
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
            source_manifest = root / "source.json"
            source_manifest.write_text(json.dumps({
                "phase": "q04-pod-cgroup-d", "producer": {}, "harness": {},
                "producer_set_sha256": "p", "harness_set_sha256": "h",
            }))
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "inputs.json").write_bytes(b"inputs")
            connectivity = mock.Mock(return_value={"status": "PASS"})
            objects = mock.Mock(return_value={"status": "PASS"})
            mount = root / "mount"
            mount.mkdir()
            evidence_directory.prepare_run_directory(
                mount,
                "q04-yolo-pod-cgroup-20260919-d",
                expected_uid=os.getuid(),
                expected_gid=os.getgid(),
            )
            with mock.patch.object(
                preflight, "verify_python_executable", return_value={"status": "PASS"}
            ), mock.patch.object(
                preflight, "verify_packages", return_value={"status": "PASS"}
            ), mock.patch.object(
                preflight, "verify_models", return_value={"status": "PASS"}
            ), mock.patch.object(
                preflight, "verify_cgroup", return_value={"status": "PASS"}
            ):
                result = preflight.run_preflight(
                    workspace=root,
                    mount_root=mount,
                    evidence_directory_name="q04-yolo-pod-cgroup-20260919-d",
                    model_cache=root,
                    provenance=root,
                    python=Path(sys.executable),
                    cgroup_root=root,
                    pod_identity=self.pod_identity(root),
                    capacity=capacity,
                    source_manifest_path=source_manifest,
                    bundle=bundle,
                    authorization_scope_sha256="scope",
                    expected_bundle_sha256=digest(b"inputs"),
                    temporal="temporal:7233",
                    endpoint="http://objects:9000",
                    bucket="t09a",
                    prefix="q04/new/",
                    expected_uid=os.getuid(),
                    expected_gid=os.getgid(),
                    temporal_probe=connectivity,
                    object_probe=objects,
                )
            self.assertEqual(result["status"], "PASS_PRE_INFERENCE")
            self.assertEqual(set(result["gates"]), {
                "image_identity", "mount_and_path", "python_executable",
                "packages_imports", "models", "cgroup", "configuration",
                "source_hashes", "temporal", "object_storage",
            })
            self.assertEqual(result["failed_gates"], [])
            self.assertFalse(result["inference_started"])
            self.assertFalse(result["workflow_started"])
            self.assertFalse(result["object_written"])
            connectivity.assert_called_once()
            objects.assert_called_once()

    def test_preflight_records_every_gate_when_multiple_gates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_manifest = root / "source.json"
            source_manifest.write_text(json.dumps({
                "phase": "q04-pod-cgroup-d", "producer": {}, "harness": {},
                "producer_set_sha256": "p", "harness_set_sha256": "h",
            }))
            capacity = root / "capacity.json"
            capacity.write_text("{}")
            bundle = root / "bundle"
            bundle.mkdir()
            (bundle / "inputs.json").write_bytes(b"inputs")
            connectivity = mock.Mock(return_value={"status": "PASS"})
            objects = mock.Mock(return_value={"status": "PASS"})
            with mock.patch.object(
                preflight, "inspect_run_directory", side_effect=ValueError("mount failed")
            ) as mount, mock.patch.object(
                preflight, "verify_python_executable",
                side_effect=RuntimeError("python failed"),
            ) as python, mock.patch.object(
                preflight, "verify_packages", return_value={"status": "PASS"}
            ) as packages, mock.patch.object(
                preflight, "verify_models", side_effect=ValueError("models failed")
            ) as models, mock.patch.object(
                preflight, "verify_cgroup", return_value={"status": "PASS"}
            ) as cgroup, mock.patch.object(
                preflight, "verify_configuration",
                side_effect=ValueError("configuration failed"),
            ) as configuration:
                result = preflight.run_preflight(
                    workspace=root,
                    mount_root=root,
                    evidence_directory_name="q04-yolo-pod-cgroup-20260919-d",
                    model_cache=root,
                    provenance=root,
                    python=Path(sys.executable),
                    cgroup_root=root,
                    pod_identity=self.pod_identity(root),
                    capacity=capacity,
                    source_manifest_path=source_manifest,
                    bundle=bundle,
                    authorization_scope_sha256="scope",
                    expected_bundle_sha256=digest(b"inputs"),
                    temporal="temporal:7233",
                    endpoint="http://objects:9000",
                    bucket="t09a",
                    prefix="q04/new/",
                    temporal_probe=connectivity,
                    object_probe=objects,
                )
            self.assertEqual(result["status"], "FAIL_PRE_INFERENCE")
            self.assertEqual(
                result["failed_gates"],
                ["mount_and_path", "python_executable", "models", "configuration"],
            )
            self.assertEqual(result["gates"]["source_hashes"]["status"], "PASS")
            self.assertEqual(
                result["gates"]["temporal"]["status"],
                "PASS",
            )
            self.assertEqual(result["gates"]["cgroup"]["status"], "PASS")
            self.assertEqual(result["gates"]["object_storage"]["status"], "PASS")
            mount.assert_called_once()
            python.assert_called_once()
            packages.assert_called_once()
            models.assert_called_once()
            cgroup.assert_called_once()
            configuration.assert_called_once()
            connectivity.assert_called_once()
            objects.assert_called_once()


if __name__ == "__main__":
    unittest.main()
