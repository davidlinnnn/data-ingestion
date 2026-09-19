"""Offline checks for the inactive independent worker-cgroup topology."""

import json
from pathlib import Path
import unittest

import pod_topology as topology


HERE = Path(__file__).resolve().parent
PLAN = HERE / "pod-topology-v1"


class PodTopologyTests(unittest.TestCase):
    def test_rendered_manifest_is_exact_and_inactive(self):
        rendered = json.loads((PLAN / "WORKER.yaml").read_text())
        result = topology.validate(rendered)

        self.assertEqual(result["status"], "PASS_OFFLINE_ONLY")
        self.assertFalse(result["runtime_authorized"])
        self.assertEqual(result["sample_guard_bytes"], 4 * 1024**3)
        self.assertEqual(result["container_hard_limit_bytes"], 5 * 1024**3)
        self.assertEqual(result["vm_runtime_floor_bytes"], 1_610_612_736)
        self.assertNotEqual(
            result["sample_guard_bytes"], result["container_hard_limit_bytes"]
        )

    def test_sources_and_mounts_are_hash_bound(self):
        rendered = topology.kubernetes_list()
        sources = topology.source_manifest()
        self.assertEqual(
            json.loads((PLAN / "SOURCE-MANIFEST.json").read_text()), sources
        )
        maps = {item["metadata"]["name"]: item for item in rendered["items"][:2]}
        self.assertTrue(all(item["immutable"] for item in maps.values()))
        self.assertEqual(
            set(maps), set(sources["config_maps"].values())
        )

        pod = rendered["items"][2]["spec"]["template"]["spec"]
        self.assertEqual(len(pod["containers"]), 1)
        mounts = {
            row["mountPath"]: row for row in pod["containers"][0]["volumeMounts"]
        }
        self.assertTrue(mounts["/workspace"]["readOnly"])
        self.assertIn("/scratch", mounts)
        self.assertIn("/q04-control", mounts)
        self.assertIn("/tmp", mounts)
        projected = next(
            volume["projected"]
            for volume in pod["volumes"]
            if volume["name"] == "workspace"
        )
        paths = {
            item["path"]
            for source in projected["sources"]
            for item in source["configMap"]["items"]
        }
        self.assertIn("src/pdf_processing/processing.py", paths)
        self.assertIn("tests/pdf_processing/q04/pod_workload.py", paths)
        self.assertIn(
            "tests/pdf_processing/q04/sentinel/yolo_reviewed_attribution_telemetry.py",
            paths,
        )

    def test_pod_security_and_secret_scope_are_fixed(self):
        pod = topology.kubernetes_list()["items"][2]["spec"]["template"]["spec"]
        container = pod["containers"][0]

        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertEqual(pod["securityContext"]["runAsUser"], 1000)
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        self.assertEqual(
            pod["securityContext"]["seccompProfile"]["type"], "RuntimeDefault"
        )
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
        self.assertNotIn("envFrom", container)
        secret_env = {
            row["name"]: row["valueFrom"]["secretKeyRef"]
            for row in container["env"]
            if "valueFrom" in row
        }
        self.assertEqual(
            secret_env,
            {
                "AWS_ACCESS_KEY_ID": {
                    "name": "store-access",
                    "key": "AWS_ACCESS_KEY_ID",
                },
                "AWS_SECRET_ACCESS_KEY": {
                    "name": "store-access",
                    "key": "AWS_SECRET_ACCESS_KEY",
                },
            },
        )

    def test_memory_and_ephemeral_resources_are_independently_fixed(self):
        container = topology.kubernetes_list()["items"][2]["spec"]["template"][
            "spec"
        ]["containers"][0]
        self.assertEqual(container["resources"]["requests"]["memory"], "4Gi")
        self.assertEqual(container["resources"]["limits"]["memory"], "5Gi")
        self.assertEqual(
            container["resources"]["requests"]["ephemeral-storage"], "3Gi"
        )
        self.assertEqual(
            container["resources"]["limits"]["ephemeral-storage"], "4Gi"
        )

    def test_capacity_baseline_does_not_claim_guaranteed_fit(self):
        baseline = json.loads((PLAN / "READONLY-BASELINE.json").read_text())
        conclusion = baseline["capacity_conclusion"]
        self.assertTrue(conclusion["current_12gib_vm_can_accommodate_one_proposed_worker"])
        self.assertFalse(conclusion["guarantee"])
        self.assertTrue(conclusion["admission_still_required"])
        self.assertTrue(conclusion["page_cache_charge_may_recur"])
        self.assertTrue(conclusion["ephemeral_scheduler_fit"])
        self.assertFalse(conclusion["docker_ram_increase_required_now"])
        self.assertEqual(baseline["held_deployments"]["expected"], 32)
        self.assertTrue(baseline["held_deployments"]["all_replicas_zero"])
        self.assertFalse(baseline["runtime_authorized"])

    def test_task_queue_and_cleanup_identity_are_fixed(self):
        rendered = topology.kubernetes_list()
        deployment = rendered["items"][2]
        annotations = deployment["metadata"]["annotations"]
        self.assertEqual(annotations["q04.openai/workflow-queue"], topology.WORKFLOW_QUEUE)
        self.assertEqual(annotations["q04.openai/activity-queue"], topology.ACTIVITY_QUEUE)
        self.assertEqual(deployment["spec"]["strategy"]["type"], "Recreate")
        self.assertEqual(deployment["spec"]["replicas"], 0)
        self.assertEqual(
            deployment["spec"]["template"]["metadata"]["labels"]["q04-run"],
            topology.RUN_LABEL,
        )


if __name__ == "__main__":
    unittest.main()
