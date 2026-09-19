"""Build and validate the inactive Q04 worker-Pod topology.

This module performs no cluster operation.  The rendered Kubernetes List keeps
replicas at zero and binds every mounted source byte to a generated immutable
ConfigMap name.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
Q04 = ROOT / "tests/pdf_processing/q04"
IMAGE = (
    "docker.io/library/pdf-t08-runtime@"
    "sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0"
)
NAMESPACE = "pdf-t09a-validation"
NODE = "internal-a2a-vs6-local-worker2"
PHASE = "q04-pod-cgroup-a"
DEPLOYMENT = PHASE + "-activities"
RUN_LABEL = PHASE
WORKFLOW_QUEUE = PHASE + "-workflows"
ACTIVITY_QUEUE = PHASE + "-07"
OBJECT_PREFIX = "q04/pod-cgroup-a/"
MEMORY_REQUEST = "4Gi"
MEMORY_LIMIT = "5Gi"
EPHEMERAL_REQUEST = "3Gi"
EPHEMERAL_LIMIT = "4Gi"
CGROUP_SAMPLE_GUARD_BYTES = 4 * 1024**3
VM_ADMISSION_BYTES = 4_831_838_208
VM_RUNTIME_FLOOR_BYTES = 1_610_612_736

PRODUCER_MANIFEST = Q04 / "candidate/yolo-lifecycle-v1/MANIFEST.json"
PRODUCER_ROOT = ROOT / "src/pdf_processing"
HARNESS_FILES = {
    "worker.py": Q04 / "worker.py",
    "consumer.py": Q04 / "consumer.py",
    "telemetry.py": Q04 / "telemetry.py",
    "acl_resource_telemetry.py": Q04 / "sentinel/acl_resource_telemetry.py",
    "yolo_reviewed_attribution_telemetry.py": Q04
    / "sentinel/yolo_reviewed_attribution_telemetry.py",
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _source_data() -> tuple[dict[str, str], dict[str, str]]:
    frozen = json.loads(PRODUCER_MANIFEST.read_text())
    producer = {
        name: (PRODUCER_ROOT / name).read_text()
        for name in sorted(frozen["producer"])
    }
    observed = {name: sha(value.encode()) for name, value in producer.items()}
    if observed != frozen["producer"]:
        raise ValueError("producer differs from frozen candidate manifest")
    harness = {name: path.read_text() for name, path in HARNESS_FILES.items()}
    return producer, harness


def source_manifest() -> dict[str, Any]:
    producer, harness = _source_data()
    producer_hashes = {name: sha(value.encode()) for name, value in producer.items()}
    harness_hashes = {name: sha(value.encode()) for name, value in harness.items()}
    producer_set = sha(canonical(producer_hashes))
    harness_set = sha(canonical(harness_hashes))
    return {
        "schema_version": 1,
        "phase": PHASE,
        "image": IMAGE,
        "producer": producer_hashes,
        "harness": harness_hashes,
        "producer_set_sha256": producer_set,
        "harness_set_sha256": harness_set,
        "config_maps": {
            "producer": "q04-pod-code-" + producer_set[:16],
            "harness": "q04-pod-harness-" + harness_set[:16],
        },
        "runtime_authorized": False,
    }


def kubernetes_list() -> dict[str, Any]:
    producer, harness = _source_data()
    identity = source_manifest()
    maps = identity["config_maps"]
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": DEPLOYMENT,
            "namespace": NAMESPACE,
            "labels": {"q04-topology": PHASE},
            "annotations": {
                "q04.openai/source-manifest-sha256": sha(canonical(identity)),
                "q04.openai/workflow-queue": WORKFLOW_QUEUE,
                "q04.openai/activity-queue": ACTIVITY_QUEUE,
                "q04.openai/cgroup-sample-guard-bytes": str(
                    CGROUP_SAMPLE_GUARD_BYTES
                ),
            },
        },
        "spec": {
            "replicas": 0,
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": {"q04-run": RUN_LABEL}},
            "template": {
                "metadata": {
                    "labels": {
                        "q04-run": RUN_LABEL,
                        "q04-topology": PHASE,
                    }
                },
                "spec": {
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "fsGroup": 1000,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "nodeSelector": {"kubernetes.io/hostname": NODE},
                    "terminationGracePeriodSeconds": 60,
                    "containers": [
                        {
                            "name": "worker",
                            "image": IMAGE,
                            "imagePullPolicy": "IfNotPresent",
                            "command": ["/bin/sh", "-c", "sleep infinity"],
                            "env": [
                                {
                                    "name": "AWS_ACCESS_KEY_ID",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "store-access",
                                            "key": "AWS_ACCESS_KEY_ID",
                                        }
                                    },
                                },
                                {
                                    "name": "AWS_SECRET_ACCESS_KEY",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "store-access",
                                            "key": "AWS_SECRET_ACCESS_KEY",
                                        }
                                    },
                                },
                                {"name": "PYTHONPATH", "value": "/app:/q04-harness"},
                                {"name": "HF_HUB_OFFLINE", "value": "1"},
                                {"name": "TRANSFORMERS_OFFLINE", "value": "1"},
                                {"name": "OMP_NUM_THREADS", "value": "4"},
                                {"name": "TEMPORAL_ADDRESS", "value": "temporal:7233"},
                                {"name": "OBJECT_ENDPOINT", "value": "http://objects:9000"},
                                {"name": "OBJECT_BUCKET", "value": "t09a"},
                                {"name": "OBJECT_PREFIX", "value": OBJECT_PREFIX},
                                {"name": "MODEL_CACHE", "value": "/experiment/PROTOTYPE-wipe-me/hf"},
                            ],
                            "resources": {
                                "requests": {
                                    "cpu": "100m",
                                    "memory": MEMORY_REQUEST,
                                    "ephemeral-storage": EPHEMERAL_REQUEST,
                                },
                                "limits": {
                                    "cpu": "4",
                                    "memory": MEMORY_LIMIT,
                                    "ephemeral-storage": EPHEMERAL_LIMIT,
                                },
                            },
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                                "readOnlyRootFilesystem": True,
                            },
                            "volumeMounts": [
                                {"name": "code", "mountPath": "/app/pdf_processing", "readOnly": True},
                                {"name": "harness", "mountPath": "/q04-harness", "readOnly": True},
                                {"name": "scratch", "mountPath": "/scratch"},
                                {"name": "control", "mountPath": "/q04-control"},
                                {"name": "tmp", "mountPath": "/tmp"},
                            ],
                            "readinessProbe": {
                                "exec": {"command": ["test", "-d", "/q04-control"]},
                                "periodSeconds": 2,
                                "failureThreshold": 15,
                            },
                        }
                    ],
                    "volumes": [
                        {"name": "code", "configMap": {"name": maps["producer"]}},
                        {"name": "harness", "configMap": {"name": maps["harness"]}},
                        {"name": "scratch", "emptyDir": {"sizeLimit": "2Gi"}},
                        {"name": "control", "emptyDir": {"sizeLimit": "256Mi"}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "512Mi"}},
                    ],
                },
            },
        },
    }
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": maps["producer"], "namespace": NAMESPACE},
                "immutable": True,
                "data": producer,
            },
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": maps["harness"], "namespace": NAMESPACE},
                "immutable": True,
                "data": harness,
            },
            deployment,
        ],
    }


def validate(value: dict[str, Any]) -> dict[str, Any]:
    expected = kubernetes_list()
    if value != expected:
        raise ValueError("rendered topology differs from fixed builder")
    deployment = value["items"][2]
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    if deployment["spec"]["replicas"] != 0:
        raise ValueError("offline topology must remain inactive")
    if len(deployment["spec"]["template"]["spec"]["containers"]) != 1:
        raise ValueError("qualification worker Pod must have one container")
    if container["resources"] != {
        "requests": {
            "cpu": "100m",
            "memory": "4Gi",
            "ephemeral-storage": "3Gi",
        },
        "limits": {
            "cpu": "4",
            "memory": "5Gi",
            "ephemeral-storage": "4Gi",
        },
    }:
        raise ValueError("resource identity changed")
    pod = deployment["spec"]["template"]["spec"]
    if pod["automountServiceAccountToken"]:
        raise ValueError("service-account token must remain disabled")
    if "envFrom" in container:
        raise ValueError("whole-Secret injection is forbidden")
    return {
        "status": "PASS_OFFLINE_ONLY",
        "runtime_authorized": False,
        "phase": PHASE,
        "deployment": DEPLOYMENT,
        "image": IMAGE,
        "workflow_queue": WORKFLOW_QUEUE,
        "activity_queue": ACTIVITY_QUEUE,
        "sample_guard_bytes": CGROUP_SAMPLE_GUARD_BYTES,
        "container_hard_limit_bytes": 5 * 1024**3,
        "vm_admission_bytes": VM_ADMISSION_BYTES,
        "vm_runtime_floor_bytes": VM_RUNTIME_FLOOR_BYTES,
    }


def render(output: Path, sources: Path) -> None:
    topology = kubernetes_list()
    validate(topology)
    output.write_text(json.dumps(topology, indent=2, ensure_ascii=False) + "\n")
    sources.write_text(json.dumps(source_manifest(), indent=2, sort_keys=True) + "\n")
