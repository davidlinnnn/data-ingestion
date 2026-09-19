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

    def test_scale_and_delete_are_uid_fenced(self):
        patch = runner.scale_patch("uid", "rv", 0, 1)
        self.assertEqual(patch[:3], [
            {"op": "test", "path": "/metadata/uid", "value": "uid"},
            {"op": "test", "path": "/metadata/resourceVersion", "value": "rv"},
            {"op": "test", "path": "/spec/replicas", "value": 0},
        ])
        self.assertEqual(runner.pod_delete_options("pod-uid")["preconditions"], {"uid": "pod-uid"})

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

    def test_cleanup_timeout_is_capped_by_one_absolute_deadline(self):
        with mock.patch("sentinel.run_yolo_pod_cgroup_a.time.time", return_value=100):
            self.assertEqual(runner.remaining_timeout(105, 30, "cleanup"), 5)
            with self.assertRaisesRegex(TimeoutError, "lease expired"):
                runner.remaining_timeout(100, 30, "cleanup")

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
        pod = {
            "metadata": {
                "name": "owned",
                "uid": "pod-uid",
                "resourceVersion": "rv",
                "labels": {"q04-run": pod_topology.RUN_LABEL},
            },
            "status": {"containerStatuses": [{
                "ready": True,
                "restartCount": 0,
                "containerID": "containerd://one",
                "imageID": pod_topology.IMAGE_CONTENT_ID,
            }]},
            "spec": {
                "nodeName": pod_topology.NODE,
                "containers": [{"image": pod_topology.IMAGE}],
            },
        }
        self.assertEqual(runner.validate_pod(pod)["pod_uid"], "pod-uid")
        pod["status"]["containerStatuses"][0]["restartCount"] = 1
        with self.assertRaisesRegex(ValueError, "restarted"):
            runner.validate_pod(pod)

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
            ):
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

    def test_offline_manifest_binds_exact_command_and_forbids_server_dry_run(self):
        retained = json.loads(runner.OFFLINE_MANIFEST.read_text())
        self.assertEqual(retained, runner.build_offline_manifest())
        self.assertFalse(retained["runtime_authorized"])
        self.assertEqual(retained["runtime_readiness"], "NOT_RUNTIME_READY")
        self.assertEqual(
            retained["runtime_blocker"], "durable evidence path not implemented"
        )
        self.assertTrue(retained["server_side_dry_run_forbidden"])
        command = retained["exact_single_run_command"]
        self.assertIn("--execute", command)
        self.assertNotIn("dry-run=server", command)
        self.assertNotIn("retry", command)
        self.assertIn("outer_admission", retained["sources"])
        self.assertIn("held_deployment_identity", retained["sources"])

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
