"""Offline contract tests for the executable Pod-cgroup runner."""

import json
from pathlib import Path
import tempfile
import tarfile
from types import SimpleNamespace
import unittest
from unittest import mock

from sentinel import run_yolo_pod_cgroup_a as runner
import pod_topology
import pod_workload
import pod_init
from candidate import yolo_reviewed_window


class YoloPodCgroupRunnerTests(unittest.TestCase):
    @staticmethod
    def owned_pod(*, ready=False, image_id=None, pod_uid="pod-uid"):
        status = {
            "name": "worker",
            "ready": ready,
            "restartCount": 0,
            "containerID": "containerd://one",
            "imageID": image_id or pod_topology.IMAGE_CONTENT_ID,
            "state": {"running": {"startedAt": "2026-09-19T00:00:00Z"}},
        }
        return {
            "metadata": {
                "name": "owned",
                "uid": pod_uid,
                "resourceVersion": "rv",
                "labels": {"q04-run": pod_topology.RUN_LABEL},
                "ownerReferences": [{
                    "controller": True,
                    "kind": "ReplicaSet",
                    "name": "worker-rs",
                    "uid": "rs-uid",
                }],
            },
            "status": {
                "phase": "Running",
                "conditions": [{"type": "Ready", "status": "True" if ready else "False"}],
                "containerStatuses": [status],
            },
            "spec": {
                "nodeName": pod_topology.NODE,
                "containers": [{"name": "worker", "image": pod_topology.IMAGE}],
            },
        }

    @staticmethod
    def deployment():
        return {"metadata": {"name": runner.DEPLOYMENT, "uid": "dep-uid"}}

    @staticmethod
    def replica_set():
        return {
            "metadata": {
                "name": "worker-rs",
                "uid": "rs-uid",
                "ownerReferences": [{
                    "controller": True,
                    "kind": "Deployment",
                    "name": runner.DEPLOYMENT,
                    "uid": "dep-uid",
                }],
            }
        }

    def test_capacity_keeps_outer_per_case_workload_cleanup_and_resource_guards(self):
        value = runner.build_capacity(
            starts_at=1000,
            owner="main-session",
            approval_reference="future explicit approval",
        )
        self.assertEqual(value["proposed_window_seconds"], 1500)
        self.assertEqual(value["outer_observation_seconds"], 180)
        self.assertEqual(value["outer_continuous_seconds"], 60)
        self.assertEqual(value["outer_admission_available_bytes"], 4_831_838_208)
        self.assertEqual(value["admission_available_bytes"], 3_221_225_472)
        self.assertEqual(value["minimum_work_seconds"], 825)
        self.assertEqual(value["cleanup_seconds"], 300)
        self.assertEqual(value["max_cgroup_bytes"], 4 * 1024**3)
        self.assertEqual(value["container_hard_limit_bytes"], 5 * 1024**3)
        self.assertEqual(value["min_available_bytes"], 1_610_612_736)
        self.assertFalse(value["automatic_retry"])

    def test_single_fixture_modes_and_service_addresses_are_exact(self):
        argv = runner.workload_argv()
        self.assertEqual(argv[0], "/experiment/.venv/bin/python")
        self.assertEqual(argv[argv.index("--workload-seconds") + 1], "825")
        self.assertEqual(argv[argv.index("--pod-temporal") + 1], "temporal:7233")
        self.assertEqual(argv[argv.index("--pod-objects") + 1], "http://objects:9000")
        scope = runner.authorization_scope()
        self.assertEqual(scope["fixture"], "07")
        self.assertEqual(scope["modes"], ["fresh", "restored", "replay"])
        self.assertFalse(scope["automatic_retry"])
        self.assertEqual(scope["evidence_pvc"], pod_topology.EVIDENCE_PVC)
        self.assertEqual(scope["evidence_pvc_bytes"], 1024**3)
        self.assertFalse(scope["evidence_pvc_automatic_delete"])
        self.assertEqual(
            argv[argv.index("--control") + 1], "/q04-evidence"
        )
        self.assertEqual(
            argv[argv.index("--state") + 1], "/q04-evidence/state"
        )
        self.assertEqual(argv[argv.index("--bundle") + 1], "/q04-control/inputs")

    def test_scale_and_delete_are_uid_fenced(self):
        patch = runner.scale_patch("uid", "rv", 0, 1)
        self.assertEqual(patch[:3], [
            {"op": "test", "path": "/metadata/uid", "value": "uid"},
            {"op": "test", "path": "/metadata/resourceVersion", "value": "rv"},
            {"op": "test", "path": "/spec/replicas", "value": 0},
        ])
        self.assertEqual(runner.pod_delete_options("pod-uid")["preconditions"], {"uid": "pod-uid"})
        self.assertEqual(runner.pod_delete_options("pod-uid")["gracePeriodSeconds"], 60)

    def test_cleanup_deletes_uid_fenced_runtime_objects_but_retains_pvc(self):
        class Kube:
            def __init__(self):
                self.calls = []

            def run(self, argv, **kwargs):
                self.calls.append((argv, kwargs))
                return "{}"

        kube = Kube()
        owned = [
            {"kind": "ConfigMap", "name": "code", "uid": "cm-uid"},
            {
                "kind": "PersistentVolumeClaim",
                "name": pod_topology.EVIDENCE_PVC,
                "uid": "pvc-uid",
            },
            {"kind": "Deployment", "name": runner.DEPLOYMENT, "uid": "dep-uid"},
        ]
        value = runner.delete_owned_objects(
            kube, owned, deadline=runner.time.time() + 60
        )
        self.assertEqual(value["retained"], [owned[1]])
        self.assertEqual(value["deleted"], [owned[2], owned[0]])
        raw_calls = [call for call in kube.calls if "--raw" in call[0]]
        self.assertEqual(len(raw_calls), 2)
        self.assertTrue(all('"preconditions"' in call[1]["input"] for call in raw_calls))
        self.assertTrue(
            all(pod_topology.EVIDENCE_PVC not in " ".join(call[0]) for call in raw_calls)
        )

    def test_cleanup_disposition_never_claims_success_when_api_is_unreachable(self):
        self.assertEqual(
            runner.cleanup_disposition(
                api_cleanup_confirmed=False, pvc_retained=True
            ),
            "NEEDS_INTERVENTION",
        )
        self.assertEqual(
            runner.cleanup_disposition(
                api_cleanup_confirmed=True, pvc_retained=False
            ),
            "FAIL_EVIDENCE_PVC_NOT_RETAINED",
        )
        self.assertEqual(
            runner.cleanup_disposition(
                api_cleanup_confirmed=True, pvc_retained=True
            ),
            "CLEANED_WITH_DURABLE_EVIDENCE",
        )
        self.assertEqual(
            runner.cleanup_disposition(
                api_cleanup_confirmed=True,
                pvc_retained=False,
                pvc_expected=False,
            ),
            "CLEANED_NO_OBJECTS",
        )

    def test_export_failure_still_removes_runtime_and_retains_claim(self):
        self.assertEqual(
            runner.cleanup_policy(
                controller_export_complete=False,
                deployment_created=True,
                pvc_created=True,
            ),
            {
                "controller_export_complete": False,
                "remove_owned_runtime": True,
                "retain_evidence_pvc": True,
            },
        )

    def test_retained_claim_is_re_read_and_uid_fenced(self):
        class Kube:
            uid = "claim-uid"

            def json(self, *args, **kwargs):
                return {
                    "metadata": {
                        "name": pod_topology.EVIDENCE_PVC,
                        "uid": self.uid,
                    },
                    "status": {"phase": "Bound"},
                }

        owned = [{
            "kind": "PersistentVolumeClaim",
            "name": pod_topology.EVIDENCE_PVC,
            "uid": "claim-uid",
        }]
        kube = Kube()
        value = runner.verify_retained_evidence_claim(
            kube, owned, None, deadline=runner.time.time() + 60
        )
        self.assertTrue(value["retained"])
        kube.uid = "replacement"
        with self.assertRaisesRegex(ValueError, "UID changed"):
            runner.verify_retained_evidence_claim(
                kube, owned, None, deadline=runner.time.time() + 60
            )

    def test_evidence_volume_identity_binds_claim_pv_node_and_permissions(self):
        pvc = {
            "metadata": {"name": pod_topology.EVIDENCE_PVC, "uid": "claim-uid"},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "storageClassName": "standard",
                "volumeName": "pv-name",
            },
            "status": {"phase": "Bound", "capacity": {"storage": "1Gi"}},
        }
        pv = {
            "metadata": {"uid": "pv-uid"},
            "spec": {
                "claimRef": {
                    "uid": "claim-uid",
                    "name": pod_topology.EVIDENCE_PVC,
                    "namespace": runner.NAMESPACE,
                },
                "nodeAffinity": {
                    "required": {
                        "nodeSelectorTerms": [{
                            "matchExpressions": [{
                                "key": "kubernetes.io/hostname",
                                "values": [pod_topology.NODE],
                            }]
                        }]
                    }
                },
            },
        }
        value = runner.validate_evidence_volume(pvc, pv)
        self.assertEqual(value["pvc_uid"], "claim-uid")
        self.assertEqual(value["pv_uid"], "pv-uid")
        self.assertEqual(value["node"], pod_topology.NODE)
        self.assertEqual(value["run_as_uid"], 1000)
        self.assertFalse(value["automatic_delete"])
        pvc["metadata"]["uid"] = "replacement"
        with self.assertRaisesRegex(ValueError, "claim identity"):
            runner.validate_evidence_volume(pvc, pv)

    def test_terminal_manifest_must_bind_the_same_volume_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            terminal = Path(directory) / "durable-terminal-manifest.json"
            terminal.write_text(json.dumps({"volume_identity": {"pvc_uid": "one"}}))
            runner.verify_terminal_volume_identity(terminal, {"pvc_uid": "one"})
            with self.assertRaisesRegex(ValueError, "PVC identity changed"):
                runner.verify_terminal_volume_identity(
                    terminal, {"pvc_uid": "replacement"}
                )

    def test_mount_permissions_record_actual_uid_gid_mode_and_write_access(self):
        observed = {
            "process_uid": 1000,
            "process_gid": 1000,
            "mount_uid": 0,
            "mount_gid": 1000,
            "mode": "0o770",
            "directory": True,
            "symlink": False,
            "writable": True,
            "group_write": True,
        }
        self.assertIs(
            runner.validate_evidence_mount_permissions(observed), observed
        )
        for name, value in (
            ("mount_gid", 0),
            ("writable", False),
            ("group_write", False),
            ("symlink", True),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                runner.validate_evidence_mount_permissions(
                    {**observed, name: value}
                )

    def test_atomic_create_records_only_uids_returned_by_successful_create(self):
        items = [
            {"kind": "ConfigMap", "metadata": {"name": "one"}},
            {"kind": "ConfigMap", "metadata": {"name": "collision"}},
        ]
        class Kube:
            calls = 0
            def run(self, argv, **kwargs):
                self.calls += 1
                self.assert_create(argv)
                if self.calls == 2:
                    raise RuntimeError("AlreadyExists")
                return json.dumps({"metadata": {"uid": "uid-one"}})
            def assert_create(self, argv):
                if argv[:2] != ["create", "-f"]:
                    raise AssertionError(argv)
        owned = []
        with self.assertRaisesRegex(RuntimeError, "AlreadyExists"):
            runner.create_owned_objects(Kube(), items, owned)
        self.assertEqual(owned, [{"kind": "ConfigMap", "name": "one", "uid": "uid-one"}])

    def test_deployment_get_must_match_uid_returned_by_create(self):
        owned = [{
            "kind": "Deployment", "name": runner.DEPLOYMENT, "uid": "created-uid",
        }]
        deployment = {
            "metadata": {"name": runner.DEPLOYMENT, "uid": "created-uid"},
            "spec": {"replicas": 0},
        }
        self.assertIs(runner.validate_created_deployment(deployment, owned), deployment)
        replacement = {
            **deployment,
            "metadata": {"name": runner.DEPLOYMENT, "uid": "replacement-uid"},
        }
        with self.assertRaisesRegex(runner.PodIdentityRejected, "UID changed"):
            runner.validate_created_deployment(replacement, owned)

    def test_cleanup_timeout_is_capped_by_one_absolute_deadline(self):
        with mock.patch("sentinel.run_yolo_pod_cgroup_a.time.time", return_value=100):
            self.assertEqual(runner.remaining_timeout(105, 30, "cleanup"), 5)
            with self.assertRaisesRegex(TimeoutError, "lease expired"):
                runner.remaining_timeout(100, 30, "cleanup")

    def test_runtime_sample_separates_memory_guard_from_evidence_watermark(self):
        row = {
            "available": runner.VM_RUNTIME_FLOOR_BYTES,
            "psi_full_avg10": 0,
            "vm_oom_kill": 0,
            "memory_events": {"oom": 0, "oom_kill": 0, "oom_group_kill": 0},
            "memory_current": runner.CGROUP_GUARD_BYTES,
            "evidence_used_bytes": 939_524_096,
            "evidence_free_bytes": 134_217_728,
            "evidence_filesystem_free_bytes": 134_217_728,
        }
        runner.verify_runtime_sample(row, 0)
        for name, value in (
            ("evidence_used_bytes", 939_524_097),
            ("evidence_free_bytes", 134_217_727),
            ("evidence_filesystem_free_bytes", 134_217_727),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(
                ValueError, "evidence PVC stop watermark"
            ):
                runner.verify_runtime_sample({**row, name: value}, 0)

    def test_pending_transport_exceeding_five_seconds_fails_closed(self):
        future = mock.Mock()
        future.done.return_value = False
        self.assertFalse(runner.transport_receipt_expired(future, 10, 15))
        self.assertTrue(runner.transport_receipt_expired(future, 10, 15.001))
        future.done.return_value = True
        self.assertTrue(runner.transport_receipt_expired(future, 10, 30))

    def test_local_archive_must_match_stable_remote_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "evidence"
            evidence.mkdir()
            (evidence / "workload-exit.json").write_bytes(b"{}\n")
            archive = root / "evidence.tar"
            with tarfile.open(archive, "w") as output:
                output.add(evidence, arcname=".")
            rows = [["workload-exit.json", 3, runner.sha256(b"{}\n")]]
            runner.verify_local_archive(archive, rows)
            with self.assertRaisesRegex(ValueError, "differs"):
                runner.verify_local_archive(
                    archive, [["workload-exit.json", 3, "0" * 64]]
                )

    def test_forced_stop_targets_measurement_group_before_supervisor(self):
        program = runner.force_stop_supervisor_program()
        self.assertIn("execution['start_ticks']", program)
        self.assertIn("os.killpg(epid,signal.SIGKILL)", program)
        self.assertLess(program.index("os.killpg"), program.index("os.kill(pid"))
        self.assertIn("scratch_absent", program)

    def test_pod_identity_requires_one_unrestarted_pinned_container(self):
        pod = self.owned_pod(ready=True)
        self.assertEqual(runner.validate_pod(pod)["pod_uid"], "pod-uid")
        pod["status"]["containerStatuses"][0]["restartCount"] = 1
        with self.assertRaisesRegex(runner.PodIdentityRejected, "restarted"):
            runner.validate_pod(pod)

    def test_started_not_ready_is_recorded_then_ready_path_is_accepted(self):
        pods = [self.owned_pod(ready=False), self.owned_pod(ready=True)]

        class Kube:
            def json(inner, *args, **kwargs):
                if args[1] == "pods":
                    return {"items": [pods.pop(0)]}
                if args[1] == "replicaset":
                    return self.replica_set()
                raise AssertionError(args)

        with tempfile.TemporaryDirectory() as directory:
            identity, cleanup = runner.await_worker_pod(
                Kube(), self.deployment(), Path(directory),
                monotonic=iter([0, 1, 2]).__next__, sleep=lambda _: None,
            )
            rows = [
                json.loads(row)
                for row in (Path(directory) / "pod-readiness.jsonl").read_text().splitlines()
            ]
        self.assertEqual([row["classification"] for row in rows], [
            "temporary_not_ready", "accepted",
        ])
        self.assertIn("not Ready", rows[0]["rejection"])
        self.assertEqual(identity["pod_uid"], "pod-uid")
        self.assertEqual(cleanup["replica_set_uid"], "rs-uid")

    def test_permanent_image_mismatch_stops_immediately_with_snapshot(self):
        pod = self.owned_pod(ready=True, image_id="sha256:" + "0" * 64)

        class Kube:
            def json(inner, *args, **kwargs):
                if args[1] == "pods":
                    return {"items": [pod]}
                return self.replica_set()

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(runner.PodIdentityRejected, "digest changed"):
                runner.await_worker_pod(Kube(), self.deployment(), Path(directory))
            row = json.loads(
                (Path(directory) / "pod-readiness.jsonl").read_text().splitlines()[0]
            )
        self.assertEqual(row["classification"], "permanent_rejection")
        self.assertEqual(row["cleanup_identity"]["pod_uid"], "pod-uid")
        self.assertEqual(row["pods"][0]["status"]["containerStatuses"][0]["imageID"], pod["status"]["containerStatuses"][0]["imageID"])

    def test_terminal_pod_or_container_status_stops_on_first_snapshot(self):
        terminal_pods = []
        failed = self.owned_pod(ready=False)
        failed["status"]["phase"] = "Failed"
        terminal_pods.append(failed)
        terminated = self.owned_pod(ready=False)
        terminated["status"]["containerStatuses"][0]["state"] = {
            "terminated": {"exitCode": 1, "reason": "Error"}
        }
        terminal_pods.append(terminated)

        for pod in terminal_pods:
            class Kube:
                def json(inner, *args, **kwargs):
                    if args[1] == "pods":
                        return {"items": [pod]}
                    return self.replica_set()

            with self.subTest(phase=pod["status"]["phase"]), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(runner.PodIdentityRejected):
                    runner.await_worker_pod(Kube(), self.deployment(), Path(directory))
                rows = (Path(directory) / "pod-readiness.jsonl").read_text().splitlines()
                self.assertEqual(len(rows), 1)
                self.assertEqual(json.loads(rows[0])["classification"], "permanent_rejection")

    def test_common_image_id_wrappers_preserve_content_digest_contract(self):
        expected = pod_topology.IMAGE_CONTENT_ID
        for value in (
            expected,
            "docker.io/library/pdf-t08-runtime@" + expected,
            "docker-pullable://docker.io/library/pdf-t08-runtime@" + expected,
            "containerd://" + expected,
        ):
            with self.subTest(value=value):
                self.assertEqual(runner.validate_pod(self.owned_pod(ready=True, image_id=value))["image_id"], value)
        with self.assertRaisesRegex(runner.PodIdentityRejected, "digest changed"):
            runner.validate_pod(self.owned_pod(
                ready=True,
                image_id=pod_topology.IMAGE.split("@", 1)[1],
            ))

    def test_nonready_owned_uid_is_returned_on_readiness_timeout(self):
        pod = self.owned_pod(ready=False)

        class Kube:
            def json(inner, *args, **kwargs):
                if args[1] == "pods":
                    return {"items": [pod]}
                return self.replica_set()

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TimeoutError) as raised:
                runner.await_worker_pod(
                    Kube(), self.deployment(), Path(directory), timeout_seconds=0,
                    monotonic=lambda: 0, sleep=lambda _: None,
                )
        self.assertEqual(raised.exception.cleanup_identity["pod_uid"], "pod-uid")

    def test_label_without_matching_owner_chain_cannot_authorize_cleanup(self):
        pod = self.owned_pod(ready=False)
        pod["metadata"]["ownerReferences"][0]["uid"] = "replacement-rs"

        class Kube:
            def json(inner, *args, **kwargs):
                if args[1] == "pods":
                    return {"items": [pod]}
                return self.replica_set()

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(runner.PodIdentityRejected, "owner UID changed") as raised:
                runner.await_worker_pod(Kube(), self.deployment(), Path(directory))
        self.assertIsNone(raised.exception.cleanup_identity)

    def test_readiness_api_error_is_recorded_and_propagated(self):
        class Kube:
            def json(self, *args, **kwargs):
                raise RuntimeError("API unavailable")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "API unavailable"):
                runner.await_worker_pod(Kube(), self.deployment(), Path(directory))
            row = json.loads(
                (Path(directory) / "pod-readiness.jsonl").read_text().splitlines()[0]
            )
        self.assertEqual(row["classification"], "observation_error")

    def test_cleanup_waits_for_graceful_pod_cri_and_emptydir_absence(self):
        class Kube:
            def __init__(self):
                self.pod_reads = iter(["pod/owned", "pod/owned", ""])
                self.calls = []

            def json(self, *args, **kwargs):
                if args[1] == "pod":
                    return {
                        "metadata": {"uid": "pod-uid"},
                        "spec": {"nodeName": pod_topology.NODE},
                    }
                return {"metadata": {"uid": "dep-uid", "resourceVersion": "rv"}, "spec": {"replicas": 1}}

            def run(self, argv, **kwargs):
                self.calls.append((argv, kwargs))
                if argv[:2] == ["get", "pod"]:
                    return next(self.pod_reads)
                return "{}"

        kube = Kube()
        identity = {
            "pod_name": "owned", "pod_uid": "pod-uid", "node": pod_topology.NODE,
        }
        with mock.patch(
            "sentinel.run_yolo_pod_cgroup_a.subprocess.check_output",
            return_value=json.dumps({"containers": []}),
        ) as cri, mock.patch(
            "sentinel.run_yolo_pod_cgroup_a.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ), mock.patch("sentinel.run_yolo_pod_cgroup_a.time.sleep"):
            result = runner.cleanup_deployment_and_pod(
                kube,
                {"metadata": {"uid": "dep-uid"}},
                identity,
                deadline=runner.time.time() + 60,
            )
        delete = next(call for call in kube.calls if "delete" in call[0])
        self.assertEqual(json.loads(delete[1]["input"])["gracePeriodSeconds"], 60)
        self.assertIn("-a", cri.call_args.args[0])
        self.assertTrue(result["old_runtime_absent"])
        self.assertTrue(result["emptydirs_absent"])

    def test_cleanup_timeout_and_api_unreachable_fail_closed(self):
        class NeverGone:
            def json(self, *args, **kwargs):
                if args[1] == "pod":
                    return {
                        "metadata": {"uid": "pod-uid"},
                        "spec": {"nodeName": pod_topology.NODE},
                    }
                return {"metadata": {"uid": "dep-uid", "resourceVersion": "rv"}, "spec": {"replicas": 1}}
            def run(self, argv, **kwargs):
                return "pod/owned" if argv[:2] == ["get", "pod"] else "{}"

        identity = {"pod_name": "owned", "pod_uid": "pod-uid", "node": pod_topology.NODE}
        with mock.patch(
            "sentinel.run_yolo_pod_cgroup_a.time.time",
            side_effect=[0, 0, 0, 0, 0, 0, 5],
        ), mock.patch("sentinel.run_yolo_pod_cgroup_a.time.sleep"):
            with self.assertRaisesRegex(TimeoutError, "did not terminate"):
                runner.cleanup_deployment_and_pod(
                    NeverGone(), {"metadata": {"uid": "dep-uid"}}, identity, deadline=5,
                )

        class Unreachable:
            def json(self, *args, **kwargs):
                raise RuntimeError("API unavailable")

        with self.assertRaisesRegex(RuntimeError, "API unavailable"):
            runner.cleanup_deployment_and_pod(
                Unreachable(), {"metadata": {"uid": "dep-uid"}}, identity,
                deadline=runner.time.time() + 60,
            )

    def test_unscheduled_cleanup_still_proves_pinned_node_runtime_absence(self):
        class Kube:
            def json(self, *args, **kwargs):
                return {
                    "metadata": {"uid": "dep-uid", "resourceVersion": "rv"},
                    "spec": {"replicas": 1},
                }

            def run(self, argv, **kwargs):
                if argv[:2] == ["get", "pod"]:
                    return ""
                return "{}"

        identity = {"pod_name": "owned", "pod_uid": "pod-uid", "node": None}
        with mock.patch(
            "sentinel.run_yolo_pod_cgroup_a.subprocess.check_output",
            return_value=json.dumps({"containers": []}),
        ) as cri, mock.patch(
            "sentinel.run_yolo_pod_cgroup_a.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ):
            result = runner.cleanup_deployment_and_pod(
                Kube(), {"metadata": {"uid": "dep-uid"}}, identity,
                deadline=runner.time.time() + 60,
            )
        self.assertEqual(cri.call_args.args[0][2], pod_topology.NODE)
        self.assertTrue(result["old_runtime_absent"])

    def test_workload_supervisor_fixes_max_requests_and_exact_three_modes(self):
        parser = pod_workload.parser()
        args = parser.parse_args([
            "--prefix", runner.PREFIX,
            "--authorization-scope-sha256", runner.authorization_scope_sha256(),
        ])
        argv = pod_workload.build_measurement_argv(args, "q04-run", runner.authorization_scope_sha256())
        self.assertEqual(argv[argv.index("--fixture") + 1], "07")
        self.assertEqual(argv[argv.index("--modes") + 1:argv.index("--expected-run-id")], ["fresh", "restored", "replay"])
        self.assertEqual(pod_workload.PARSER_BUDGETS["max_requests"], 1)
        self.assertEqual(pod_workload.WORKFLOW_QUEUE, pod_topology.WORKFLOW_QUEUE)
        self.assertEqual(pod_workload.ACTIVITY_QUEUE, pod_topology.ACTIVITY_QUEUE)
        init_argv = pod_workload.build_init_argv(args)
        self.assertTrue(init_argv[1].endswith("/pod_init.py"))
        self.assertNotIn("--trial-seconds", init_argv)
        reviewed = json.loads(
            (
                runner.Q04
                / "pod-topology-v1/INTEGRATION-MANIFEST.json"
            ).read_text()
        )["authorization_scope_sha256"]
        reviewed_argv = pod_workload.build_measurement_argv(args, "q04-run", reviewed)
        self.assertEqual(
            reviewed_argv[reviewed_argv.index("--authorization-scope-sha256") + 1],
            reviewed,
        )

    def test_uid_1000_no_inference_preflight_checks_read_only_sources_model_and_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            control = root / "control"
            model = root / "models"
            cgroup = root / "cgroup"
            control.mkdir()
            model.mkdir()
            cgroup.mkdir()
            (cgroup / "memory.max").write_text(str(5 * 1024**3))
            (cgroup / "memory.events").write_text("oom 0\noom_kill 0\noom_group_kill 0\n")
            for index in range(35):
                (model / f"model-{index}").write_bytes(b"x")
            for relative in (
                "src/pdf_processing/__init__.py",
                "tests/pdf_processing/q04/q04_runtime.py",
                "tests/pdf_processing/q04/candidate/yolo_reviewed_window.py",
            ):
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# fixed\n")
            with mock.patch("pod_workload.os.getuid", return_value=1000), mock.patch(
                "pod_workload.os.getgid", return_value=1000
            ), mock.patch("pod_workload.importlib.import_module"):
                result = pod_workload.no_inference_preflight(
                    workspace, control, model, cgroup
                )
            self.assertEqual(result["status"], "PASS_NO_INFERENCE")
            self.assertFalse(result["inference_started"])
            self.assertFalse((control / ".write-probe").exists())
            with mock.patch("pod_workload.os.getuid", return_value=0), mock.patch(
                "pod_workload.os.getgid", return_value=0
            ):
                with self.assertRaisesRegex(ValueError, "UID/GID 1000"):
                    pod_workload.no_inference_preflight(workspace, control, model, cgroup)

    def test_budget_adoption_reduces_runtime_to_one_fixed_fixture_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir()
            original = {
                "run_id": "q04-random-initialized",
                "parser_budgets": {**pod_workload.PARSER_BUDGETS, "max_requests": 20},
                "pod_namespace": "unexpected",
                "workflow_queue": "old-workflows",
                "profiles": {"07": {"id": "p07"}, "08": {"id": "p08"}},
                "queues": {"07": "old-07", "08": "old-08"},
            }
            (state / "config.json").write_text(json.dumps(original))
            record = pod_workload.adopt_budget(state, Path(directory) / "adopt.json")
            adopted = json.loads((state / "config.json").read_text())
            self.assertEqual(adopted["run_id"], pod_workload.RUN_ID)
            self.assertEqual(adopted["profiles"], {"07": {"id": "p07"}})
            self.assertEqual(adopted["queues"], {"07": pod_topology.ACTIVITY_QUEUE})
            self.assertEqual(adopted["workflow_queue"], pod_topology.WORKFLOW_QUEUE)
            self.assertIsNone(adopted["pod_namespace"])
            self.assertEqual(record["initialized_run_id"], "q04-random-initialized")

    def test_fixture_init_builds_only_reviewed_fixture07_profile(self):
        bundle = json.loads((runner.BUNDLE / "inputs.json").read_text())
        profile = pod_init.fixture_profile(
            bundle,
            {
                "key": runner.PREFIX + "sources/original-07.pdf",
                "version_id": "v1",
                "sha256": "0" * 64,
            },
        )
        fixture = next(row for row in bundle["fixtures"] if row["id"] == "07")
        self.assertEqual(
            set(profile["content_evidence"]["reviews"]), {fixture["sha256"]}
        )
        self.assertEqual(
            profile["content_evidence"]["relationships"]["coverage"],
            {"mode": "unknown"},
        )
        self.assertTrue(profile["release"].startswith("q04-"))

    def test_offline_manifest_marks_executed_identity_consumed(self):
        retained = json.loads(runner.OFFLINE_MANIFEST.read_text())
        self.assertEqual(retained, runner.build_offline_manifest())
        self.assertFalse(retained["runtime_authorized"])
        self.assertEqual(retained["runtime_readiness"], "CONSUMED_FAILURE_DO_NOT_REUSE")
        self.assertIn("new identity", retained["runtime_blocker"])
        self.assertTrue(retained["server_side_dry_run_forbidden"])
        self.assertIsNone(retained["exact_single_run_command"])
        command = retained["historical_exact_single_run_command"]
        self.assertTrue(command.startswith(str(runner.LOCAL_PYTHON)))
        self.assertIn("--execute", command)
        self.assertNotIn("dry-run=server", command)
        self.assertNotIn("retry", command)
        self.assertIn("outer_admission", retained["sources"])
        self.assertIn("held_deployment_identity", retained["sources"])
        self.assertIn("consumed_run_record", retained["sources"])

    def test_execute_refuses_consumed_identity_before_cluster_adapter_use(self):
        args = SimpleNamespace(
            authorization_scope_sha256=runner.authorization_scope_sha256(),
            owner="main-session",
            approval_reference="historical",
        )
        with mock.patch.object(runner, "offline_check", return_value={}), self.assertRaisesRegex(
            RuntimeError, "identity.*consumed"
        ):
            runner.execute_window(args, kube=mock.Mock())

    def test_new_identity_reuses_reviewed_equivalence_without_rewriting_reference(self):
        q04 = runner.Q04
        manifest = json.loads(
            (q04 / "pod-topology-v1/INTEGRATION-MANIFEST.json").read_text()
        )
        bundle_root = runner.BUNDLE
        bundle = json.loads((bundle_root / "inputs.json").read_text())
        args = SimpleNamespace(
            fixture="07",
            modes=["fresh", "restored", "replay"],
            name=runner.PHASE,
            expected_prefix=runner.PREFIX,
            integration_manifest=q04 / "pod-topology-v1/INTEGRATION-MANIFEST.json",
            main_review=q04 / "candidate/yolo-reviewed-v1/MAIN-REVIEW.json",
            equivalence_bundle=q04 / "candidate/yolo-equivalence-v1/BUNDLE.json",
            resource_bundle=q04 / "candidate/yolo-resource-v1/BUNDLE.json",
            parser_budgets=q04 / "candidate/yolo-resource-v1/PARSER-BUDGETS.json",
            resource_analysis=q04 / "diagnosis/yolo-lifecycle-a/evidence/resource-peak.json",
            historical_methods=runner.REPO
            / "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json",
            bundle=bundle_root,
            authorization_scope_sha256=manifest["authorization_scope_sha256"],
        )
        result = yolo_reviewed_window.validate_reviewed_inputs(
            args,
            {
                "parser_budgets": pod_workload.PARSER_BUDGETS,
                "profiles": {"07": {"method": bundle["base_profile"]["method"]}},
            },
            bundle,
        )
        self.assertEqual(result["review"]["historical_reference_mutated"], False)
        self.assertEqual(result["review"]["general_normalization"], False)


if __name__ == "__main__":
    unittest.main()
