"""Offline contracts for the follow-up Q04 Pod cgroup J runner."""

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import pod_topology_k as topology
import pod_remote_evidence_k as remote_evidence
import pod_workload_k as workload
from sentinel import run_yolo_pod_cgroup_k as runner


class YoloPodCgroupJRunnerTests(unittest.TestCase):
    def test_complete_launch_arguments_parse_at_every_entrypoint(self):
        import pod_init_k
        import pod_preflight_k
        from candidate import yolo_reviewed_window
        args = workload.parser().parse_args(runner.workload_argv()[2:])
        preflight = pod_preflight_k.parser().parse_args(runner.preflight_argv()[2:])
        initialized = pod_init_k.parser().parse_args(workload.build_init_argv(args)[2:])
        manifest = json.loads((runner.Q04 / "pod-topology-v10/RUNTIME-INTEGRATION-MANIFEST.json").read_text())
        with patch.object(yolo_reviewed_window, "run_window", new_callable=AsyncMock) as execute:
            yolo_reviewed_window.main(workload.build_measurement_argv(
                args, args.run_id, manifest["authorization_scope_sha256"])[3:])
            measured = execute.call_args.args[0]
        self.assertEqual(args.run_id, runner.RUN_IDENTITY)
        self.assertEqual(initialized.prefix, runner.PREFIX)
        self.assertEqual(preflight.prefix, runner.PREFIX)
        self.assertEqual(measured.expected_prefix, runner.PREFIX)
        self.assertEqual(measured.expected_run_id, runner.RUN_IDENTITY)
        self.assertEqual(measured.modes, ["fresh", "restored", "replay"])

    def volume_objects(self):
        pvc = {
            "metadata": {
                "name": topology.EVIDENCE_PVC,
                "uid": "claim-d",
                "namespace": topology.NAMESPACE,
            },
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "storageClassName": "standard",
                "volumeName": "pv-d",
            },
            "status": {"phase": "Bound", "capacity": {"storage": "1Gi"}},
        }
        pv = {
            "metadata": {
                "name": "pv-d",
                "uid": "pv-uid-d",
                "annotations": {
                    "pv.kubernetes.io/provisioned-by": "rancher.io/local-path"
                },
            },
            "spec": {
                "claimRef": {
                    "uid": "claim-d",
                    "name": topology.EVIDENCE_PVC,
                    "namespace": topology.NAMESPACE,
                },
                "hostPath": {
                    "path": "/var/local-path-provisioner/pvc-claim-d",
                    "type": "DirectoryOrCreate",
                },
                "nodeAffinity": {"required": {"nodeSelectorTerms": [{
                    "matchExpressions": [{
                        "key": "kubernetes.io/hostname",
                        "values": [topology.NODE],
                    }]
                }]}},
            },
        }
        storage_class = {
            "metadata": {"name": "standard"},
            "provisioner": "rancher.io/local-path",
            "volumeBindingMode": "WaitForFirstConsumer",
            "reclaimPolicy": "Delete",
        }
        return pvc, pv, storage_class

    def test_new_identity_and_paths_do_not_reuse_c(self):
        scope = runner.authorization_scope()
        self.assertEqual(scope["run_identity"], "q04-yolo-pod-cgroup-20260920-k")
        self.assertEqual(scope["evidence_pvc"], "q04-pod-cgroup-k-evidence-20260920-k")
        self.assertEqual(
            scope["evidence_directory_name"], "q04-yolo-pod-cgroup-20260920-k"
        )
        self.assertEqual(runner.EVIDENCE_MOUNT, "/q04-evidence")
        self.assertEqual(
            runner.EVIDENCE,
            "/q04-evidence/q04-yolo-pod-cgroup-20260920-k",
        )
        self.assertNotIn("20260919-c", json.dumps(scope))
        argv = runner.workload_argv()
        self.assertEqual(argv[argv.index("--control") + 1], runner.EVIDENCE)
        self.assertEqual(argv[argv.index("--state") + 1], runner.EVIDENCE + "/state")

    def test_volume_gate_identifies_local_path_hostpath_backend(self):
        pvc, pv, storage_class = self.volume_objects()
        result = runner.validate_evidence_volume(pvc, pv, storage_class)
        self.assertEqual(
            result["volume_backend"],
            "rancher.io/local-path hostPath DirectoryOrCreate",
        )
        self.assertEqual(result["mount_path"], runner.EVIDENCE_MOUNT)
        self.assertEqual(result["evidence_directory"], runner.EVIDENCE)
        changed = copy.deepcopy(pv)
        changed["spec"]["hostPath"]["type"] = "Directory"
        with self.assertRaisesRegex(ValueError, "local-path hostPath"):
            runner.validate_evidence_volume(pvc, changed, storage_class)

    def test_mount_root_acceptance_does_not_claim_fsgroup_ownership(self):
        value = {
            "process_uid": 1000,
            "process_gid": 1000,
            "mount_uid": 0,
            "mount_gid": 0,
            "mode": "0o777",
            "directory": True,
            "symlink": False,
            "writable": True,
            "searchable": True,
        }
        self.assertEqual(runner.validate_evidence_mount_root(value), value)
        changed = {**value, "symlink": True}
        with self.assertRaisesRegex(ValueError, "mount root type"):
            runner.validate_evidence_mount_root(changed)

    def test_single_gate_set_precedes_workload_and_uses_staged_inputs(self):
        source = Path(runner.__file__).read_text()
        execute = source[source.index("def execute_window"):]
        prepare = execute.index("prepare_run_directory")
        bundle = execute.index("bundle-copy.log")
        capacity = execute.index("stage_capacity")
        preflight = execute.index("single pre-inference gate set")
        local_record = execute.index('OUT / "pod-pre-inference-gates.json"')
        durable_record = execute.index('EVIDENCE + "/pre-inference-gates.json"')
        pass_check = execute.index(
            'preflight_value.get("status") != "PASS_PRE_INFERENCE"'
        )
        start = execute.index("subprocess.Popen(")
        self.assertLess(prepare, bundle)
        self.assertLess(bundle, preflight)
        self.assertLess(capacity, preflight)
        self.assertLess(preflight, start)
        self.assertLess(preflight, local_record)
        self.assertLess(local_record, durable_record)
        self.assertLess(durable_record, pass_check)
        self.assertLess(pass_check, start)
        argv = runner.preflight_argv()
        self.assertIn("pod_preflight_k.py", argv[1])
        self.assertEqual(
            argv[argv.index("--evidence-directory-name") + 1],
            topology.EVIDENCE_DIRECTORY_NAME,
        )
        self.assertEqual(
            argv[argv.index("--pod-identity") + 1],
            runner.CONTROL + "/pod-identity.json",
        )

    def test_control_kson_staging_writes_stdin_bytes_to_binary_files(self):
        source = Path(runner.__file__).read_text()
        self.assertEqual(source.count("open('xb').write(sys.stdin.buffer.read())"), 3)
        self.assertNotIn("open('xb').write(sys.stdin.read())", source)

    def test_transport_appends_when_empty_stream_later_grows(self):
        identity = remote_evidence.PodEvidenceIdentity(
            "pod-uid", "container-id", 42, 99, "a" * 64
        )
        with tempfile.TemporaryDirectory() as directory:
            mirror = remote_evidence.IncrementalEvidenceMirror(
                Path(directory), identity
            )
            name = "workload.log"
            empty = b""
            first = {
                "schema_version": 1,
                "sequence": 1,
                "identity": identity.__dict__,
                "process_state": "live",
                "files": [{
                    "path": name, "offset": 0, "size": 0, "total_size": 0,
                    "eof": True, "sha256": hashlib.sha256(empty).hexdigest(),
                    "data": base64.b64encode(empty).decode(),
                }],
            }
            payload = b"started\n"
            second = {
                "schema_version": 1,
                "sequence": 2,
                "identity": identity.__dict__,
                "process_state": "live",
                "files": [{
                    "path": name, "offset": 0, "size": len(payload),
                    "total_size": len(payload), "eof": True,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "data": base64.b64encode(payload).decode(),
                }],
            }
            mirror.ingest(first, received_at=10)
            mirror.ingest(second, received_at=11)
            self.assertEqual((Path(directory) / name).read_bytes(), payload)

    def test_cleanup_labels_preworkload_pvc_separately(self):
        base = {
            "api_cleanup_confirmed": True,
            "pvc_retained": True,
            "pvc_expected": True,
        }
        self.assertEqual(
            runner.cleanup_disposition(
                **base, workload_evidence_status="NOT_STARTED"
            ),
            "CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED",
        )
        self.assertEqual(
            runner.cleanup_disposition(
                **base, workload_evidence_status="CONTROLLER_EXPORT_COMPLETE"
            ),
            "CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED",
        )
        self.assertEqual(
            runner.cleanup_disposition(
                **base, workload_evidence_status="INCOMPLETE"
            ),
            "CLEANED_WITH_PVC_RETAINED_WORKLOAD_EVIDENCE_INCOMPLETE",
        )

    def test_started_exec_without_validated_supervisor_is_not_started(self):
        status, record = runner.workload_evidence_classification(
            supervisor_identity_published=False,
            evidence_captured=False,
        )
        self.assertEqual(status, "NOT_STARTED")
        self.assertEqual(record["supervisor"], "NOT_STARTED")
        status, record = runner.workload_evidence_classification(
            supervisor_identity_published=True,
            evidence_captured=False,
        )
        self.assertEqual(status, "INCOMPLETE")
        self.assertEqual(record["supervisor"], "START_CONFIRMED")

    def test_workload_requires_complete_pre_inference_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = {
                "status": "PASS_PRE_INFERENCE",
                "inference_started": False,
                "workflow_started": False,
                "object_written": False,
                "gates": {name: {"status": "PASS"} for name in (
                    "image_identity",
                    "mount_and_path",
                    "python_executable",
                    "packages_imports",
                    "models",
                    "cgroup",
                    "configuration",
                    "source_hashes",
                    "workload_imports",
                    "temporal",
                    "object_storage",
                )},
            }
            (root / "pre-inference-gates.json").write_text(json.dumps(value))
            self.assertEqual(workload.require_pre_inference_gates(root), value)
            del value["gates"]["source_hashes"]
            (root / "pre-inference-gates.json").write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "gate set incomplete"):
                workload.require_pre_inference_gates(root)

    def test_topology_is_inactive_and_contains_only_h_identity(self):
        rendered = topology.kubernetes_list()
        topology.validate(rendered)
        manifest = topology.source_manifest()
        raw = json.dumps(rendered)
        self.assertEqual(rendered["items"][3]["spec"]["replicas"], 0)
        self.assertIn(topology.EVIDENCE_PVC, raw)
        self.assertIn(topology.EVIDENCE_DIRECTORY_NAME, raw)
        self.assertNotIn("q04-pod-cgroup-c-evidence-20260919-c", raw)
        self.assertIn(
            "tests/pdf_processing/q04/sentinel/acl_resource_telemetry.py",
            manifest["harness"],
        )
        self.assertIn(
            "tests/pdf_processing/q04/pod-topology-v10/RUNTIME-INTEGRATION-MANIFEST.json",
            manifest["harness"],
        )

    def test_runtime_manifest_changes_only_the_window_identity(self):
        historical = json.loads(
            (runner.Q04 / "pod-topology-v1/INTEGRATION-MANIFEST.json").read_text()
        )
        runtime = json.loads(
            (
                runner.Q04
                / "pod-topology-v10/RUNTIME-INTEGRATION-MANIFEST.json"
            ).read_text()
        )
        historical_identity = historical.pop("identity")
        runtime_identity = runtime.pop("identity")
        self.assertEqual(runtime, historical)
        self.assertEqual(historical_identity["phase"], "yolo-pod-cgroup-a")
        self.assertEqual(runtime_identity, {
            "driver_lock": "/q04-control/yolo-pod-cgroup-k.driver.lock",
            "local_output": "/private/tmp/q04-yolo-pod-cgroup-20260920-k",
            "phase": "yolo-pod-cgroup-k",
            "prefix": "q04/yolo-pod-cgroup-20260920-k/",
            "remote_root": "/q04-control",
            "runner_dir": "/workspace/tests/pdf_processing/q04",
        })

    def test_workload_uses_the_h_runtime_manifest_for_validation_and_scope(self):
        source = Path(workload.__file__).read_text()
        runtime_path = "pod-topology-v10/RUNTIME-INTEGRATION-MANIFEST.json"
        self.assertEqual(source.count(runtime_path), 2)
        self.assertNotIn(
            "pod-topology-v1/INTEGRATION-MANIFEST.json",
            source,
        )

    def test_projected_workspace_imports_the_runtime_entrypoints(self):
        rendered = topology.kubernetes_list()
        config_maps = {
            item["metadata"]["name"]: item["data"]
            for item in rendered["items"]
            if item["kind"] == "ConfigMap"
        }
        deployment = next(
            item for item in rendered["items"] if item["kind"] == "Deployment"
        )
        workspace = next(
            volume
            for volume in deployment["spec"]["template"]["spec"]["volumes"]
            if volume["name"] == "workspace"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspace"
            for source in workspace["projected"]["sources"]:
                projection = source["configMap"]
                data = config_maps[projection["name"]]
                for item in projection["items"]:
                    target = root / item["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(data[item["key"]])

            paths = [
                root / "src",
                root / "tests/pdf_processing/q04",
                root / "tests/pdf_processing/q02",
                root / "tests/pdf_processing/q03",
            ]
            environment = os.environ.copy()
            environment["PYTHONPATH"] = os.pathsep.join(map(str, paths))
            bundle = json.dumps(str(runner.BUNDLE))
            prefix = json.dumps(runner.PREFIX)
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; import pod_preflight_k as p; "
                    "result=p.verify_workload_imports("
                    f"workspace=Path.cwd(),bundle=Path({bundle}),prefix={prefix}); "
                    "assert result['status']=='PASS', result",
                ],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_manifests_and_offline_check_are_exact(self):
        self.assertEqual(
            json.loads(runner.WORKER_YAML.read_text()), topology.kubernetes_list()
        )
        self.assertEqual(
            json.loads((runner.Q04 / "pod-topology-v10/SOURCE-MANIFEST.json").read_text()),
            topology.source_manifest(),
        )
        self.assertEqual(
            json.loads(runner.OFFLINE_MANIFEST.read_text()),
            runner.build_offline_manifest(),
        )
        result = runner.offline_check()
        self.assertEqual(result["status"], "PASS_OFFLINE_ONLY")
        self.assertEqual(result["runtime_readiness"], "OFFLINE_READY_FOR_REVIEW")
        self.assertFalse(result["runtime_authorized"])


if __name__ == "__main__":
    unittest.main()
