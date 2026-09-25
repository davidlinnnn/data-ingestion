"""Local-only contract tests for the executable readiness preflight."""

import json
from pathlib import Path
import shlex
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock

import pod_topology
from sentinel import run_yolo_pod_cgroup_a as consumed
from sentinel import run_yolo_readiness_preflight_b as runner


class ReadinessPreflightTests(unittest.TestCase):
    def args(self, digest=None):
        return SimpleNamespace(
            owner="main-session",
            approval_reference="separate future authorization",
            authorization_scope_sha256=digest or runner.authorization_scope_sha256(),
        )

    def deployment(self):
        return {
            "metadata": {
                "name": runner.DEPLOYMENT,
                "uid": "dep-uid",
                "resourceVersion": "rv",
            },
            "spec": {"replicas": 0},
        }

    def pod(self, *, ready=True, image_id=None):
        return {
            "metadata": {
                "name": "preflight-pod",
                "uid": "pod-uid",
                "resourceVersion": "pod-rv",
                "labels": {"q04-run": runner.RUN_LABEL},
                "ownerReferences": [{
                    "controller": True,
                    "kind": "ReplicaSet",
                    "name": "preflight-rs",
                    "uid": "rs-uid",
                }],
            },
            "spec": {
                "nodeName": runner.NODE,
                "containers": [{
                    "name": "worker",
                    "image": pod_topology.IMAGE,
                    "readinessProbe": runner.render_deployment()["spec"]["template"]["spec"]["containers"][0]["readinessProbe"],
                }],
            },
            "status": {
                "phase": "Running",
                "conditions": [{"type": "Ready", "status": "True" if ready else "False"}],
                "containerStatuses": [{
                    "name": "worker",
                    "ready": ready,
                    "restartCount": 0,
                    "image": pod_topology.IMAGE,
                    "imageID": image_id or pod_topology.IMAGE_CONTENT_ID,
                    "containerID": "containerd://preflight",
                    "state": {"running": {"startedAt": "2026-09-19T00:00:00Z"}},
                }],
            },
        }

    def replica_set(self):
        return {
            "metadata": {
                "name": "preflight-rs",
                "uid": "rs-uid",
                "ownerReferences": [{
                    "controller": True,
                    "kind": "Deployment",
                    "name": runner.DEPLOYMENT,
                    "uid": "dep-uid",
                }],
            }
        }

    def test_fixed_budget_scope_and_exact_cli_argv(self):
        scope = runner.authorization_scope()
        self.assertEqual(scope["window_seconds"], 600)
        self.assertEqual(scope["admission_observation_seconds"], 180)
        self.assertEqual(scope["admission_continuous_seconds"], 60)
        self.assertEqual(scope["readiness_seconds"], 120)
        self.assertEqual(scope["termination_grace_seconds"], 60)
        self.assertEqual(scope["cleanup_reserve_seconds"], 180)
        self.assertFalse(scope["automatic_retry"])
        self.assertFalse(scope["workflow_or_inference"])
        self.assertFalse(scope["persistent_volumes"])

        argv = shlex.split(runner.exact_command())
        parsed = runner.parser().parse_args(argv[2:])
        self.assertTrue(parsed.execute)
        self.assertEqual(parsed.owner, "main-session")
        self.assertEqual(
            parsed.authorization_scope_sha256,
            runner.authorization_scope_sha256(),
        )
        self.assertNotIn("--offline-check", argv)

    def test_render_is_one_inactive_deployment_with_only_emptydirs(self):
        rendered = runner.render_deployment()
        self.assertEqual(rendered["kind"], "Deployment")
        self.assertEqual(rendered["spec"]["replicas"], 0)
        pod = rendered["spec"]["template"]["spec"]
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertEqual(pod["terminationGracePeriodSeconds"], 60)
        self.assertEqual(len(pod["containers"]), 1)
        self.assertNotIn("env", pod["containers"][0])
        self.assertEqual(
            {item["name"] for item in pod["volumes"]},
            {"scratch", "control", "evidence", "tmp"},
        )
        self.assertTrue(all(set(item) == {"name", "emptyDir"} for item in pod["volumes"]))
        raw = json.dumps(rendered).lower()
        for forbidden in (
            "persistentvolumeclaim", "configmap", "secretkeyref", "temporal",
            "object_endpoint", "q04-pod-cgroup-a-evidence",
        ):
            self.assertNotIn(forbidden, raw)

    def test_new_identity_ready_and_image_rejection_snapshots_use_shared_classifier(self):
        test = self

        class Kube:
            def __init__(self, pod):
                self.pod = pod

            def json(self, *args, **kwargs):
                if args[1] == "pods":
                    return {"items": [self.pod]}
                if args[1] == "replicaset":
                    return test.replica_set()
                if args[1] == "events":
                    return {"items": [{
                        "type": "Warning",
                        "reason": "Unhealthy",
                        "message": "Readiness probe failed",
                        "count": 1,
                    }]}
                raise AssertionError(args)

        with tempfile.TemporaryDirectory() as directory:
            identity, cleanup = consumed.await_worker_pod(
                Kube(self.pod()),
                self.deployment(),
                Path(directory),
                run_label=runner.RUN_LABEL,
                node_name=runner.NODE,
                image=pod_topology.IMAGE,
                image_content_id=pod_topology.IMAGE_CONTENT_ID,
                include_events=True,
            )
            row = json.loads(
                (Path(directory) / "pod-readiness.jsonl").read_text().splitlines()[0]
            )
        self.assertEqual(row["classification"], "accepted")
        self.assertEqual(row["events"][0]["reason"], "Unhealthy")
        self.assertEqual(
            row["pods"][0]["spec"]["containers"][0]["readinessProbe"],
            runner.render_deployment()["spec"]["template"]["spec"]["containers"][0]["readinessProbe"],
        )
        self.assertEqual(identity["pod_uid"], "pod-uid")
        self.assertEqual(cleanup["deployment_uid"], "dep-uid")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(consumed.PodIdentityRejected, "digest changed"):
                consumed.await_worker_pod(
                    Kube(self.pod(image_id="sha256:" + "0" * 64)),
                    self.deployment(),
                    Path(directory),
                    run_label=runner.RUN_LABEL,
                    node_name=runner.NODE,
                    image=pod_topology.IMAGE,
                    image_content_id=pod_topology.IMAGE_CONTENT_ID,
                    include_events=True,
                )
            row = json.loads(
                (Path(directory) / "pod-readiness.jsonl").read_text().splitlines()[0]
            )
        self.assertEqual(row["classification"], "permanent_rejection")
        self.assertEqual(row["cleanup_identity"]["pod_uid"], "pod-uid")

    def test_execute_success_creates_only_render_and_confirms_cleanup(self):
        class Kube:
            def __init__(self, deployment):
                self.deployment = deployment
                self.calls = []

            def run(self, argv, **kwargs):
                self.calls.append((argv, kwargs))
                if argv[:2] == ["create", "-f"]:
                    return json.dumps({"metadata": {"uid": "dep-uid"}})
                return ""

            def json(self, *args, **kwargs):
                if args[1] == "deployment":
                    return self.deployment
                raise AssertionError(args)

        ready = {
            "pod_name": "preflight-pod",
            "pod_uid": "pod-uid",
            "node": runner.NODE,
            "container_id": "containerd://preflight",
            "image_id": pod_topology.IMAGE_CONTENT_ID,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            kube = Kube(self.deployment())
            with mock.patch.object(runner, "OUT", output), mock.patch.object(
                runner, "offline_check", return_value={}
            ), mock.patch.object(runner, "run_admission", return_value={"passed": True}), mock.patch.object(
                consumed, "await_worker_pod", return_value=(ready, ready)
            ), mock.patch.object(
                consumed, "cleanup_deployment_and_pod",
                return_value={"old_runtime_absent": True, "emptydirs_absent": True},
            ) as cleanup, mock.patch.object(runner, "wait_final_absence"):
                result = runner.execute_window(self.args(), kube=kube)
            created = next(call for call in kube.calls if call[0][:2] == ["create", "-f"])
            self.assertEqual(json.loads(created[1]["input"]), runner.render_deployment())
            self.assertEqual(result["status"], "PASS_IMAGE_READINESS_CLEANUP_ONLY")
            self.assertFalse(result["workflow_or_inference_started"])
            self.assertEqual(
                cleanup.call_args.kwargs["emptydir_names"],
                ("scratch", "control", "evidence", "tmp"),
            )
            self.assertEqual(json.loads((output / "cleanup.json").read_text())["disposition"], "CLEANED_NO_INFERENCE_PREFLIGHT")

    def test_creation_and_scale_consume_the_same_120_second_readiness_deadline(self):
        class Kube:
            def run(self, argv, **kwargs):
                if argv[:2] == ["create", "-f"]:
                    return json.dumps({"metadata": {"uid": "dep-uid"}})
                return ""

            def json(self, *args, **kwargs):
                return {
                    "metadata": {
                        "name": runner.DEPLOYMENT,
                        "uid": "dep-uid",
                        "resourceVersion": "rv",
                    },
                    "spec": {"replicas": 0},
                }

        ready = {
            "pod_name": "preflight-pod",
            "pod_uid": "pod-uid",
            "node": runner.NODE,
            "container_id": "containerd://preflight",
            "image_id": pod_topology.IMAGE_CONTENT_ID,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            with mock.patch.object(runner, "OUT", output), mock.patch.object(
                runner, "offline_check", return_value={}
            ), mock.patch.object(runner, "run_admission", return_value={"passed": True}), mock.patch.object(
                runner.time, "time", side_effect=[1000, 1100, 1130, 1140, 1150, 1170]
            ), mock.patch.object(
                consumed, "await_worker_pod", return_value=(ready, ready)
            ) as readiness, mock.patch.object(
                consumed, "cleanup_deployment_and_pod", return_value={}
            ), mock.patch.object(runner, "delete_deployment"), mock.patch.object(
                runner, "wait_final_absence"
            ):
                runner.execute_window(self.args(), kube=Kube())
        self.assertEqual(readiness.call_args.kwargs["timeout_seconds"], 50)

    def test_rejection_preserves_primary_and_passes_nonready_uid_to_cleanup(self):
        class Kube:
            def run(self, argv, **kwargs):
                if argv[:2] == ["create", "-f"]:
                    return json.dumps({"metadata": {"uid": "dep-uid"}})
                return ""

            def json(self, *args, **kwargs):
                return {"metadata": {"name": runner.DEPLOYMENT, "uid": "dep-uid", "resourceVersion": "rv"}, "spec": {"replicas": 0}}

        rejection = consumed.PodIdentityRejected("worker image digest changed")
        rejection.cleanup_identity = {
            "pod_name": "preflight-pod", "pod_uid": "pod-uid", "node": runner.NODE,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            with mock.patch.object(runner, "OUT", output), mock.patch.object(
                runner, "offline_check", return_value={}
            ), mock.patch.object(runner, "run_admission", return_value={"passed": True}), mock.patch.object(
                consumed, "await_worker_pod", side_effect=rejection
            ), mock.patch.object(
                consumed, "cleanup_deployment_and_pod", return_value={}
            ) as cleanup, mock.patch.object(runner, "wait_final_absence"):
                with self.assertRaisesRegex(consumed.PodIdentityRejected, "digest changed"):
                    runner.execute_window(self.args(), kube=Kube())
            self.assertEqual(cleanup.call_args.args[2]["pod_uid"], "pod-uid")
            record = json.loads((output / "cleanup.json").read_text())
            self.assertIn("digest changed", record["primary_error"])
            self.assertEqual(record["disposition"], "CLEANED_NO_INFERENCE_PREFLIGHT")

    def test_uncertain_scale_without_owner_chain_identity_needs_intervention(self):
        class Kube:
            def run(self, argv, **kwargs):
                if argv[:2] == ["create", "-f"]:
                    return json.dumps({"metadata": {"uid": "dep-uid"}})
                if argv[:2] == ["patch", "deployment"]:
                    raise RuntimeError("patch response unavailable")
                return ""

            def json(self, *args, **kwargs):
                return {
                    "metadata": {
                        "name": runner.DEPLOYMENT,
                        "uid": "dep-uid",
                        "resourceVersion": "rv",
                    },
                    "spec": {"replicas": 0},
                }

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            with mock.patch.object(runner, "OUT", output), mock.patch.object(
                runner, "offline_check", return_value={}
            ), mock.patch.object(runner, "run_admission", return_value={"passed": True}), mock.patch.object(
                consumed, "cleanup_deployment_and_pod", return_value={}
            ), mock.patch.object(runner, "wait_final_absence"):
                with self.assertRaisesRegex(RuntimeError, "patch response unavailable"):
                    runner.execute_window(self.args(), kube=Kube())
            record = json.loads((output / "cleanup.json").read_text())
            self.assertEqual(record["disposition"], "NEEDS_INTERVENTION")
            self.assertIn("no owner-chain UID", record["identity_gap"])

    def test_create_uid_is_retained_for_cleanup_when_name_reread_fails(self):
        class Kube:
            def run(self, argv, **kwargs):
                if argv[:2] == ["create", "-f"]:
                    return json.dumps({"metadata": {"uid": "create-returned-uid"}})
                return ""

            def json(self, *args, **kwargs):
                raise RuntimeError("Deployment GET unavailable")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            with mock.patch.object(runner, "OUT", output), mock.patch.object(
                runner, "offline_check", return_value={}
            ), mock.patch.object(runner, "run_admission", return_value={"passed": True}), mock.patch.object(
                consumed, "cleanup_deployment_and_pod", return_value={}
            ) as cleanup, mock.patch.object(runner, "delete_deployment") as deletion, mock.patch.object(
                runner, "wait_final_absence"
            ):
                with self.assertRaisesRegex(RuntimeError, "GET unavailable"):
                    runner.execute_window(self.args(), kube=Kube())
            self.assertEqual(cleanup.call_args.args[1]["metadata"]["uid"], "create-returned-uid")
            self.assertEqual(deletion.call_args.args[1]["metadata"]["uid"], "create-returned-uid")

    def test_consumed_scope_digest_is_rejected_before_any_output_or_kube_call(self):
        class Kube:
            def __getattr__(self, name):
                raise AssertionError("Kubernetes adapter must not be touched")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-output"
            with mock.patch.object(runner, "OUT", output), mock.patch.object(
                runner, "offline_check", return_value={}
            ), self.assertRaisesRegex(ValueError, "consumed run"):
                runner.execute_window(
                    self.args(consumed.authorization_scope_sha256()), kube=Kube()
                )
            self.assertFalse(output.exists())

    def test_committed_render_manifest_and_offline_check_are_exact(self):
        self.assertEqual(json.loads(runner.RENDER.read_text()), runner.render_deployment())
        self.assertEqual(json.loads(runner.MANIFEST.read_text()), runner.build_manifest())
        self.assertEqual(runner.offline_check()["status"], "PASS_OFFLINE_ONLY")


if __name__ == "__main__":
    unittest.main()
