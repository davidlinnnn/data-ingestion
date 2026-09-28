"""Offline contract tests for the new single-use Pod/PVC window C."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from image_identity import (
    EVIDENCE as IMAGE_EVIDENCE,
    ImageIdentityError,
    PINNED_IMAGE_IDENTITY,
    load_pinned_image_identity,
)
import pod_topology_c as topology
import pod_workload_c as pod_workload
from sentinel import run_yolo_pod_cgroup_c as runner


class YoloPodCgroupCRunnerTests(unittest.TestCase):
    def test_expired_recovery_deadline_cannot_skip_owned_cleanup(self):
        process = mock.Mock()
        process.poll.return_value = None
        stop = runner.stop_transport_process(
            process,
            recovery_deadline=0,
            timeout_for=mock.Mock(side_effect=TimeoutError("deadline expired")),
        )
        self.assertTrue(stop["uncertain"])
        self.assertIn("graceful_wait", stop["errors"])
        self.assertIn("forced_wait", stop["errors"])
        process.kill.assert_called_once()
        self.assertEqual(
            runner.cleanup_disposition(
                api_cleanup_confirmed=not stop["uncertain"],
                pvc_retained=True,
            ),
            "NEEDS_INTERVENTION",
        )
        source = Path(runner.__file__).read_text()
        finalizer = source[source.index("finally:", source.index("def execute_window")):]
        self.assertLess(
            finalizer.index("stop_transport_process("),
            finalizer.index("cleanup_deployment_and_pod("),
        )
        self.assertLess(
            finalizer.index("cleanup_deployment_and_pod("),
            finalizer.index("verify_retained_evidence_claim("),
        )

    def test_transport_first_timeout_and_second_wait_failure_are_isolated(self):
        process = mock.Mock()
        process.poll.return_value = None
        process.wait.side_effect = [
            subprocess.TimeoutExpired("kubectl", 30),
            RuntimeError("second wait failed"),
        ]
        stop = runner.stop_transport_process(
            process,
            recovery_deadline=100,
            timeout_for=lambda *_: 1,
        )
        self.assertTrue(stop["graceful_timeout"])
        self.assertTrue(stop["forced"])
        self.assertTrue(stop["uncertain"])
        self.assertIn("forced_wait", stop["errors"])
        process.kill.assert_called_once()

    def test_transport_signal_error_is_recorded_without_escaping(self):
        process = mock.Mock()
        process.send_signal.side_effect = OSError("signal failed")
        process.poll.return_value = 0
        stop = runner.stop_transport_process(
            process,
            recovery_deadline=100,
            timeout_for=lambda *_: 1,
        )
        self.assertTrue(stop["confirmed_absent"])
        self.assertTrue(stop["uncertain"])
        self.assertIn("send_signal", stop["errors"])
        process.kill.assert_not_called()

    def real_ready_pod(self):
        path = (
            Path(__file__).parent
            / "pod-topology-v1/readiness-preflight-v1/evidence/run-b/pod-readiness.jsonl"
        )
        return json.loads(path.read_text().splitlines()[-1])["pods"][0]

    def test_real_preflight_snapshot_is_accepted_by_fixed_chain(self):
        pod = self.real_ready_pod()
        pod["metadata"]["labels"]["q04-run"] = runner.RUN_LABEL
        identity = runner.validate_pod(pod)
        self.assertEqual(identity["image_id_representation"], "repository-platform-manifest")
        self.assertEqual(identity["restart_count"], 0)
        self.assertTrue(identity["container_id"].startswith("containerd://"))

    def test_real_snapshot_rejects_wrong_manifest_content_repo_and_unbound_id(self):
        cases = (
            ("docker.io/library/pdf-t08-runtime@sha256:" + "0" * 64, "manifest"),
            ("docker.io/library/other@" + topology.IMAGE.split("@", 1)[1], "repository"),
            ("containerd://sha256:" + "0" * 64, "config content"),
            (topology.IMAGE_CONTENT_ID, "bare content"),
        )
        for image_id, message in cases:
            pod = self.real_ready_pod()
            pod["metadata"]["labels"]["q04-run"] = runner.RUN_LABEL
            pod["status"]["containerStatuses"][0]["imageID"] = image_id
            with self.subTest(image_id=image_id), self.assertRaisesRegex(
                runner.PodIdentityRejected, message
            ):
                runner.validate_pod(pod)

    def test_identity_scope_budget_and_new_pvc_are_exact(self):
        scope = runner.authorization_scope()
        self.assertEqual(scope["run_identity"], "q04-yolo-pod-cgroup-20260919-c")
        self.assertEqual(scope["modes"], ["fresh", "restored", "replay"])
        self.assertEqual(scope["window_seconds"], 1500)
        self.assertEqual(scope["outer_observation_seconds"], 180)
        self.assertEqual(scope["outer_continuous_seconds"], 60)
        self.assertEqual(scope["outer_available_bytes"], 4_831_838_208)
        self.assertEqual(scope["per_case_available_bytes"], 3_221_225_472)
        self.assertEqual(scope["workload_seconds"], 825)
        self.assertEqual(scope["cleanup_seconds"], 300)
        self.assertEqual(scope["cgroup_guard_bytes"], 4 * 1024**3)
        self.assertEqual(scope["container_hard_limit_bytes"], 5 * 1024**3)
        self.assertFalse(scope["automatic_retry"])
        self.assertEqual(
            scope["evidence_pvc"], "q04-pod-cgroup-c-evidence-20260919-c"
        )
        self.assertNotEqual(scope["evidence_pvc"], "q04-pod-cgroup-a-evidence-20260919-a")

    def test_topology_is_inactive_unique_and_source_hash_complete(self):
        rendered = json.loads(runner.WORKER_YAML.read_text())
        self.assertEqual(rendered, topology.kubernetes_list())
        self.assertEqual(json.loads(
            (runner.Q04 / "pod-topology-v2/SOURCE-MANIFEST.json").read_text()
        ), topology.source_manifest())
        raw = json.dumps(rendered)
        self.assertNotIn("q04-pod-cgroup-a-evidence-20260919-a", raw)
        self.assertIn(topology.EVIDENCE_PVC, raw)
        self.assertEqual(rendered["items"][3]["spec"]["replicas"], 0)
        self.assertEqual(rendered["items"][3]["metadata"]["name"], topology.DEPLOYMENT)

    def test_workload_receives_new_run_queues_prefix_and_fixed_modes(self):
        argv = runner.workload_argv()
        self.assertEqual(argv[argv.index("--run-id") + 1], runner.RUN_IDENTITY)
        self.assertEqual(
            argv[argv.index("--workflow-queue") + 1], topology.WORKFLOW_QUEUE
        )
        self.assertEqual(
            argv[argv.index("--activity-queue") + 1], topology.ACTIVITY_QUEUE
        )
        self.assertEqual(argv[argv.index("--prefix") + 1], runner.PREFIX)
        self.assertEqual(runner.authorization_scope()["modes"], ["fresh", "restored", "replay"])
        parsed = pod_workload.parser().parse_args(argv[2:])
        self.assertEqual(parsed.run_id, runner.RUN_IDENTITY)
        self.assertEqual(parsed.workflow_queue, topology.WORKFLOW_QUEUE)
        self.assertEqual(parsed.activity_queue, topology.ACTIVITY_QUEUE)
        init_argv = pod_workload.build_init_argv(parsed)
        self.assertEqual(init_argv[init_argv.index("--run-id") + 1], runner.RUN_IDENTITY)
        self.assertEqual(
            init_argv[init_argv.index("--workflow-queue") + 1],
            topology.WORKFLOW_QUEUE,
        )

    def test_readiness_and_image_chain_precede_workload_start(self):
        source = Path(runner.__file__).read_text()
        execute = source[source.index("def execute_window"):]
        self.assertLess(execute.index("await_worker_pod("), execute.index("subprocess.Popen("))
        self.assertLess(execute.index("await_worker_pod("), execute.index("pod-no-inference-preflight.json"))
        self.assertIn("from pod_workload_c import no_inference_preflight", execute)
        self.assertNotIn("from pod_workload import no_inference_preflight", execute)
        self.assertEqual(PINNED_IMAGE_IDENTITY.spec_reference, topology.IMAGE)
        self.assertIsNone(PINNED_IMAGE_IDENTITY.registry_index_digest)
        self.assertEqual(PINNED_IMAGE_IDENTITY.os, "linux")
        self.assertEqual(PINNED_IMAGE_IDENTITY.architecture, "arm64")
        self.assertEqual(
            PINNED_IMAGE_IDENTITY.bind_runtime_image_id(
                topology.IMAGE,
                spec_image=topology.IMAGE,
                status_image="docker.io/library/pdf-checkpoint-prototype:linux-v2",
            ),
            "repository-platform-manifest",
        )

    def test_failure_cleanup_targets_compatible_candidate_scratch(self):
        program = runner.force_stop_supervisor_program()
        self.assertIn("root/'state/yolo-pod-cgroup-c'", program)
        self.assertNotIn("root/'state/yolo-pod-cgroup-a'", program)
        self.assertIn("scratch_absent=all(not path.exists()", program)

    def test_contradictory_docker_platform_index_id_and_repo_fail_closed(self):
        mutations = (
            ("Architecture", "amd64", "Docker image platform changed"),
            ("Id", "sha256:" + "0" * 64, "Docker engine image ID changed"),
            ("RepoDigests", ["pdf-checkpoint-prototype@sha256:" + "0" * 64], "Docker repo digest"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                target = Path(directory)
                for source in IMAGE_EVIDENCE.iterdir():
                    if source.is_file():
                        shutil.copy2(source, target / source.name)
                path = target / "docker-inspect.json"
                rows = json.loads(path.read_text())
                rows[0][field] = value
                path.write_text(json.dumps(rows))
                with self.assertRaisesRegex(ImageIdentityError, message):
                    load_pinned_image_identity(target)

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for source in IMAGE_EVIDENCE.iterdir():
                if source.is_file():
                    shutil.copy2(source, target / source.name)
            path = target / "docker-inspect.json"
            rows = json.loads(path.read_text())
            rows[0]["Descriptor"]["mediaType"] = "application/vnd.oci.image.index.v1+json"
            path.write_text(json.dumps(rows))
            with self.assertRaisesRegex(ImageIdentityError, "image index"):
                load_pinned_image_identity(target)

    def test_offline_manifest_and_check_are_exact(self):
        committed = json.loads(runner.OFFLINE_MANIFEST.read_text())
        self.assertEqual(committed, runner.build_offline_manifest())
        docker_capture = IMAGE_EVIDENCE / "docker-inspect.json"
        expected = runner.sha256(docker_capture.read_bytes())
        self.assertEqual(committed["sources"]["image_docker_inspect"], expected)
        self.assertNotEqual(
            runner.sha256(docker_capture.read_bytes() + b"\n"), expected
        )
        self.assertIn("image_evidence_manifest", committed["sources"])
        self.assertIn("image_reconciliation", committed["sources"])
        result = runner.offline_check()
        self.assertEqual(result["status"], "PASS_OFFLINE_ONLY")
        self.assertFalse(result["runtime_authorized"])
        self.assertEqual(
            result["authorization_scope_sha256"],
            "bc889ca368fa9d6bd123d80004fd8f9f9f149e2ca4ee726ed470241b218c0202",
        )


if __name__ == "__main__":
    unittest.main()
