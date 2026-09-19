"""Run one authorized fixture-07 matrix in the reviewed worker Pod cgroup.

Import and ``--offline-check`` are local-only.  ``--execute`` is the sole path
that may upload the private ConfigMaps, create Kubernetes objects, or start the
Pod-local supervisor.  It is intentionally single-use and never retries.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
import uuid

Q04 = Path(__file__).resolve().parent.parent
REPO = Q04.parents[2]
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology_d as pod_topology
from image_identity import ImageIdentityError, PINNED_IMAGE_IDENTITY
from outer_admission import OuterAdmissionPolicy, observe_capacity
from pod_remote_evidence_d import (
    FINAL_REQUIRED,
    IncrementalEvidenceMirror,
    PodEvidenceIdentity,
    pull_once,
)
from sentinel import run_yolo_lifecycle_a as lifecycle


PHASE = "yolo-pod-cgroup-d"
RUN_IDENTITY = "q04-yolo-pod-cgroup-20260919-d"
PREFIX = "q04/yolo-pod-cgroup-20260919-d/"
OUT = Path("/private/tmp/q04-yolo-pod-cgroup-20260919-d")
CONTROL = "/q04-control"
EVIDENCE_MOUNT = "/q04-evidence"
EVIDENCE_DIRECTORY_NAME = pod_topology.EVIDENCE_DIRECTORY_NAME
EVIDENCE = EVIDENCE_MOUNT + "/" + EVIDENCE_DIRECTORY_NAME
BUNDLE = Path("/private/tmp/q04-inputs-yolo-lifecycle-v1")
WINDOW_SECONDS = 1500
OUTER_OBSERVATION_SECONDS = 180
CONTINUOUS_SECONDS = 60
WORKLOAD_SECONDS = 825
CLEANUP_SECONDS = 300
OUTER_AVAILABLE_BYTES = 4_831_838_208
PER_CASE_AVAILABLE_BYTES = 3_221_225_472
VM_RUNTIME_FLOOR_BYTES = 1_610_612_736
CGROUP_GUARD_BYTES = 4_294_967_296
HARD_LIMIT_BYTES = 5_368_709_120
SAMPLE_INTERVAL_SECONDS = 0.25
TRANSPORT_INTERVAL_SECONDS = 2.0
TRANSPORT_GAP_SECONDS = 5.0
CONTEXT = "kind-internal-a2a-vs6-local"
NAMESPACE = pod_topology.NAMESPACE
DEPLOYMENT = pod_topology.DEPLOYMENT
RUN_LABEL = pod_topology.RUN_LABEL
NODE = pod_topology.NODE
WORKER_YAML = Q04 / "pod-topology-v3/WORKER.yaml"
OFFLINE_MANIFEST = Q04 / "pod-topology-v3/RUNNER-MANIFEST.json"
LOCAL_PYTHON = Path(
    "/Users/david/work/data-ingestion/docs/prototypes/"
    "pdf-checkpoint-prototype/.venv/bin/python"
)


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def authorization_scope() -> dict:
    return {
        "phase": PHASE,
        "run_identity": RUN_IDENTITY,
        "fixture": "07",
        "modes": ["fresh", "restored", "replay"],
        "automatic_retry": False,
        "window_seconds": WINDOW_SECONDS,
        "outer_observation_seconds": OUTER_OBSERVATION_SECONDS,
        "outer_continuous_seconds": CONTINUOUS_SECONDS,
        "outer_available_bytes": OUTER_AVAILABLE_BYTES,
        "per_case_available_bytes": PER_CASE_AVAILABLE_BYTES,
        "workload_seconds": WORKLOAD_SECONDS,
        "cleanup_seconds": CLEANUP_SECONDS,
        "sample_interval_seconds": SAMPLE_INTERVAL_SECONDS,
        "transport_interval_seconds": TRANSPORT_INTERVAL_SECONDS,
        "cgroup_guard_bytes": CGROUP_GUARD_BYTES,
        "container_hard_limit_bytes": HARD_LIMIT_BYTES,
        "vm_runtime_floor_bytes": VM_RUNTIME_FLOOR_BYTES,
        "deployment": DEPLOYMENT,
        "evidence_pvc": pod_topology.EVIDENCE_PVC,
        "evidence_directory_name": EVIDENCE_DIRECTORY_NAME,
        "evidence_pvc_bytes": 1024**3,
        "evidence_pvc_automatic_delete": False,
        "deployment_initial_replicas": 0,
        "held_deployments_restored": False,
    }


def authorization_scope_sha256() -> str:
    return sha256(canonical(authorization_scope()))


def build_capacity(*, starts_at: float, owner: str, approval_reference: str) -> dict:
    if not owner or not approval_reference:
        raise ValueError("capacity owner and approval reference required")
    return {
        "status": "AUTHORIZED",
        "phase": PHASE,
        "owner": owner,
        "approval_reference": approval_reference,
        "starts_at": starts_at,
        "ends_at": starts_at + WINDOW_SECONDS,
        "proposed_window_seconds": WINDOW_SECONDS,
        "outer_observation_seconds": OUTER_OBSERVATION_SECONDS,
        "outer_continuous_seconds": CONTINUOUS_SECONDS,
        "outer_admission_available_bytes": OUTER_AVAILABLE_BYTES,
        "admission_seconds": CONTINUOUS_SECONDS,
        "admission_available_bytes": PER_CASE_AVAILABLE_BYTES,
        "minimum_work_seconds": WORKLOAD_SECONDS,
        "cleanup_seconds": CLEANUP_SECONDS,
        "min_available_bytes": VM_RUNTIME_FLOOR_BYTES,
        "max_cgroup_bytes": CGROUP_GUARD_BYTES,
        "container_hard_limit_bytes": HARD_LIMIT_BYTES,
        "max_full_psi": 0,
        "max_sample_gap_seconds": 1,
        "max_replacement_seconds": 120,
        "expected_vm_oom_kill": 0,
        "expected_cgroup_oom_kill": 0,
        "automatic_retry": False,
        "authorization_scope_sha256": authorization_scope_sha256(),
    }


def workload_argv() -> list[str]:
    return [
        "/experiment/.venv/bin/python",
        "/workspace/tests/pdf_processing/q04/pod_workload_d.py",
        "--prefix", PREFIX,
        "--authorization-scope-sha256", authorization_scope_sha256(),
        "--workload-seconds", str(WORKLOAD_SECONDS),
        "--control", EVIDENCE,
        "--state", EVIDENCE + "/state",
        "--bundle", CONTROL + "/inputs",
        "--capacity", CONTROL + "/capacity.json",
        "--pod-temporal", "temporal:7233",
        "--pod-objects", "http://objects:9000",
        "--run-id", RUN_IDENTITY,
        "--workflow-queue", pod_topology.WORKFLOW_QUEUE,
        "--activity-queue", pod_topology.ACTIVITY_QUEUE,
    ]


def preflight_argv() -> list[str]:
    return [
        "/experiment/.venv/bin/python",
        "/workspace/tests/pdf_processing/q04/pod_preflight_d.py",
        "--workspace", "/workspace",
        "--mount-root", EVIDENCE_MOUNT,
        "--evidence-directory-name", EVIDENCE_DIRECTORY_NAME,
        "--model-cache", "/experiment/PROTOTYPE-wipe-me/hf",
        "--provenance",
        "/workspace/tests/pdf_processing/q04/candidate/"
        "yolo-reviewed-b-fail/RETAINED-REPLAY.json",
        "--python", "/experiment/.venv/bin/python",
        "--capacity", CONTROL + "/capacity.json",
        "--source-manifest", CONTROL + "/source-manifest.json",
        "--bundle", CONTROL + "/inputs",
        "--authorization-scope-sha256", authorization_scope_sha256(),
        "--expected-bundle-sha256", sha256((BUNDLE / "inputs.json").read_bytes()),
        "--temporal", "temporal:7233",
        "--endpoint", "http://objects:9000",
        "--bucket", "t09a",
        "--prefix", PREFIX,
    ]


def exact_command() -> str:
    return shlex.join(
        [
            str(LOCAL_PYTHON),
            str(Path(__file__).resolve()),
            "--execute",
            "--owner", "main-session",
            "--approval-reference",
            "Separate explicit main-session authorization for q04-yolo-pod-cgroup-20260919-d",
            "--authorization-scope-sha256", authorization_scope_sha256(),
        ]
    )


def scale_patch(uid: str, resource_version: str, before: int, after: int) -> list[dict]:
    return [
        {"op": "test", "path": "/metadata/uid", "value": uid},
        {
            "op": "test",
            "path": "/metadata/resourceVersion",
            "value": resource_version,
        },
        {"op": "test", "path": "/spec/replicas", "value": before},
        {"op": "replace", "path": "/spec/replicas", "value": after},
    ]


def pod_delete_options(uid: str) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "DeleteOptions",
        "gracePeriodSeconds": 60,
        "preconditions": {"uid": uid},
    }


class PodNotReady(RuntimeError):
    """The owned Pod may still become acceptable without changing identity."""


class PodIdentityRejected(ValueError):
    """The Pod cannot be used by this run and must fail closed immediately."""


def validate_pod(
    pod: dict,
    *,
    run_label: str = RUN_LABEL,
    node_name: str = NODE,
    image: str = pod_topology.IMAGE,
    image_identity=PINNED_IMAGE_IDENTITY,
) -> dict:
    if pod["metadata"]["labels"].get("q04-run") != run_label:
        raise PodIdentityRejected("Pod run label changed")
    phase = pod.get("status", {}).get("phase")
    if phase not in ("Pending", "Running"):
        raise PodIdentityRejected(f"worker Pod phase is terminal or unexpected: {phase!r}")
    node = pod["spec"].get("nodeName")
    if node is None:
        raise PodNotReady("Pod is not scheduled")
    if node != node_name:
        raise PodIdentityRejected("Pod node changed")
    containers = pod["spec"].get("containers", [])
    if len(containers) != 1 or containers[0].get("image") != image:
        raise PodIdentityRejected("worker image reference changed")
    statuses = pod["status"].get("containerStatuses", [])
    if not statuses:
        raise PodNotReady("worker container status not published")
    if len(statuses) != 1:
        raise PodIdentityRejected("exactly one worker container status required")
    if statuses[0].get("state", {}).get("terminated") is not None:
        raise PodIdentityRejected("worker container terminated")
    if statuses[0].get("restartCount") != 0:
        raise PodIdentityRejected("worker Pod restarted")
    image_id = statuses[0].get("imageID")
    if not image_id:
        raise PodNotReady("worker image identity not published")
    try:
        image_representation = image_identity.bind_runtime_image_id(
            image_id,
            spec_image=containers[0]["image"],
            status_image=statuses[0].get("image"),
        )
    except ImageIdentityError as error:
        raise PodIdentityRejected(str(error)) from error
    if phase != "Running":
        raise PodNotReady("worker Pod phase is not Running")
    if not statuses[0].get("ready"):
        raise PodNotReady("worker container is not Ready")
    if not statuses[0].get("containerID"):
        raise PodNotReady("worker container identity not published")
    return {
        "pod_name": pod["metadata"]["name"],
        "pod_uid": pod["metadata"]["uid"],
        "resource_version": pod["metadata"]["resourceVersion"],
        "container_id": statuses[0]["containerID"],
        "image_id": statuses[0]["imageID"],
        "image_id_representation": image_representation,
        "restart_count": statuses[0]["restartCount"],
        "node": pod["spec"]["nodeName"],
    }


def controller_owner(metadata: dict, kind: str) -> dict:
    owners = [
        item for item in metadata.get("ownerReferences", [])
        if item.get("controller") is True
    ]
    if len(owners) != 1 or owners[0].get("kind") != kind:
        raise PodIdentityRejected(f"exactly one controlling {kind} owner required")
    owner = owners[0]
    if not owner.get("name") or not owner.get("uid"):
        raise PodIdentityRejected(f"controlling {kind} owner identity incomplete")
    return owner


def capture_cleanup_identity(
    kube,
    pod: dict,
    deployment: dict,
    *,
    run_label: str = RUN_LABEL,
    timeout: float = 30,
) -> dict:
    """Prove a Pod's owner chain before returning its UID for cleanup."""
    if pod["metadata"].get("labels", {}).get("q04-run") != run_label:
        raise PodIdentityRejected("Pod run label changed")
    replica_set_owner = controller_owner(pod["metadata"], "ReplicaSet")
    replica_set = kube.json(
        "get", "replicaset", replica_set_owner["name"], timeout=timeout
    )
    if replica_set.get("metadata", {}).get("uid") != replica_set_owner["uid"]:
        raise PodIdentityRejected("Pod ReplicaSet owner UID changed")
    deployment_owner = controller_owner(replica_set["metadata"], "Deployment")
    expected = deployment["metadata"]
    if (
        deployment_owner["name"] != expected["name"]
        or deployment_owner["uid"] != expected["uid"]
    ):
        raise PodIdentityRejected("ReplicaSet Deployment owner identity changed")
    metadata = pod["metadata"]
    return {
        "pod_name": metadata["name"],
        "pod_uid": metadata["uid"],
        "resource_version": metadata["resourceVersion"],
        "node": pod.get("spec", {}).get("nodeName"),
        "replica_set_name": replica_set_owner["name"],
        "replica_set_uid": replica_set_owner["uid"],
        "deployment_name": deployment_owner["name"],
        "deployment_uid": deployment_owner["uid"],
    }


def pod_readiness_snapshot(pod: dict) -> dict:
    status = pod.get("status", {})
    return {
        "metadata": {
            key: pod.get("metadata", {}).get(key)
            for key in ("name", "uid", "resourceVersion", "labels", "ownerReferences")
        },
        "spec": {
            "nodeName": pod.get("spec", {}).get("nodeName"),
            "containers": [
                {
                    "name": item.get("name"),
                    "image": item.get("image"),
                    "readinessProbe": item.get("readinessProbe"),
                }
                for item in pod.get("spec", {}).get("containers", [])
            ],
        },
        "status": {
            "phase": status.get("phase"),
            "conditions": status.get("conditions", []),
            "containerStatuses": [
                {
                    key: item.get(key)
                    for key in (
                        "name", "ready", "restartCount", "image", "imageID",
                        "containerID", "state", "lastState",
                    )
                }
                for item in status.get("containerStatuses", [])
            ],
        },
    }


def await_worker_pod(
    kube,
    deployment: dict,
    output: Path,
    *,
    timeout_seconds: float = 120,
    monotonic=None,
    sleep=None,
    run_label: str = RUN_LABEL,
    node_name: str = NODE,
    image: str = pod_topology.IMAGE,
    image_identity=PINNED_IMAGE_IDENTITY,
    include_events: bool = False,
) -> tuple[dict, dict]:
    """Observe one owned Pod until Ready, preserving every decision as JSONL."""
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep
    deadline = monotonic() + timeout_seconds
    cleanup_identity = None

    def request_timeout(action: str) -> float:
        remaining = deadline - monotonic()
        if remaining <= 0:
            error = TimeoutError(f"worker Pod readiness expired before {action}")
            setattr(error, "cleanup_identity", cleanup_identity)
            raise error
        return max(0.001, min(30, remaining))

    def require_time(action: str) -> None:
        if monotonic() >= deadline:
            error = TimeoutError(f"worker Pod readiness expired after {action}")
            setattr(error, "cleanup_identity", cleanup_identity)
            raise error

    with (output / "pod-readiness.jsonl").open("x", buffering=1) as stream:
        while True:
            observed_at = time.time()
            record = {"time": observed_at}
            try:
                pods = kube.json(
                    "get", "pods", "-l", "q04-run=" + run_label,
                    timeout=request_timeout("Pod list"),
                )["items"]
                require_time("Pod list")
                record = {
                    "time": observed_at,
                    "pod_count": len(pods),
                    "pods": [pod_readiness_snapshot(pod) for pod in pods],
                }
                if include_events and len(pods) == 1:
                    try:
                        events = kube.json(
                            "get",
                            "events",
                            "--field-selector",
                            "involvedObject.uid=" + pods[0]["metadata"]["uid"],
                            timeout=request_timeout("Pod Event list"),
                        )["items"]
                        require_time("Pod Event list")
                        record["events"] = [
                            {
                                key: item.get(key)
                                for key in (
                                    "type", "reason", "message", "count",
                                    "firstTimestamp", "lastTimestamp",
                                )
                            }
                            for item in events
                        ]
                    except TimeoutError:
                        raise
                    except Exception as event_error:
                        record["events_error"] = repr(event_error)
                if len(pods) > 1:
                    raise PodIdentityRejected("multiple owned-label Pods observed")
                if len(pods) == 1:
                    candidate = capture_cleanup_identity(
                        kube,
                        pods[0],
                        deployment,
                        run_label=run_label,
                        timeout=request_timeout("ReplicaSet owner read"),
                    )
                    require_time("ReplicaSet owner read")
                    if cleanup_identity is not None and (
                        candidate["pod_uid"] != cleanup_identity["pod_uid"]
                    ):
                        raise PodIdentityRejected("owned Pod UID changed during readiness")
                    cleanup_identity = candidate
                    try:
                        ready_identity = validate_pod(
                            pods[0],
                            run_label=run_label,
                            node_name=node_name,
                            image=image,
                            image_identity=image_identity,
                        )
                    except PodNotReady as error:
                        record.update(
                            classification="temporary_not_ready",
                            rejection=repr(error),
                            cleanup_identity=cleanup_identity,
                        )
                    else:
                        pod_identity = {**cleanup_identity, **ready_identity}
                        record.update(
                            classification="accepted",
                            rejection=None,
                            cleanup_identity=cleanup_identity,
                        )
                        stream.write(json.dumps(record, sort_keys=True) + "\n")
                        (output / "created-pod-spec.json").write_text(
                            json.dumps(pods[0], indent=2) + "\n"
                        )
                        return pod_identity, cleanup_identity
                else:
                    record.update(
                        classification="temporary_not_ready",
                        rejection="no owned-label Pod observed",
                        cleanup_identity=cleanup_identity,
                    )
                stream.write(json.dumps(record, sort_keys=True) + "\n")
            except PodIdentityRejected as error:
                record.update(
                    classification="permanent_rejection",
                    rejection=repr(error),
                    cleanup_identity=cleanup_identity,
                )
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                setattr(error, "cleanup_identity", cleanup_identity)
                raise
            except BaseException as error:
                record.update(
                    classification="observation_error",
                    rejection=repr(error),
                    cleanup_identity=cleanup_identity,
                )
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                setattr(error, "cleanup_identity", cleanup_identity)
                raise
            remaining = deadline - monotonic()
            if remaining <= 0:
                error = TimeoutError("worker Pod readiness expired")
                setattr(error, "cleanup_identity", cleanup_identity)
                raise error
            sleep(min(1, remaining))


def validate_evidence_volume(pvc: dict, pv: dict, storage_class: dict) -> dict:
    metadata = pvc["metadata"]
    spec = pvc["spec"]
    status = pvc["status"]
    if metadata["name"] != pod_topology.EVIDENCE_PVC:
        raise ValueError("evidence PVC name changed")
    if metadata.get("ownerReferences"):
        raise ValueError("evidence PVC has garbage-collection owner")
    if spec.get("accessModes") != ["ReadWriteOnce"]:
        raise ValueError("evidence PVC access mode changed")
    if spec.get("storageClassName") != "standard":
        raise ValueError("evidence PVC storage class changed")
    if status.get("phase") != "Bound" or not spec.get("volumeName"):
        raise ValueError("evidence PVC is not bound")
    if status.get("capacity", {}).get("storage") != "1Gi":
        raise ValueError("evidence PVC capacity changed")
    if (
        storage_class["metadata"].get("name") != "standard"
        or storage_class.get("provisioner") != "rancher.io/local-path"
        or storage_class.get("volumeBindingMode") != "WaitForFirstConsumer"
        or storage_class.get("reclaimPolicy") != "Delete"
    ):
        raise ValueError("evidence StorageClass contract changed")
    host_path = pv["spec"].get("hostPath")
    if (
        not isinstance(host_path, dict)
        or host_path.get("type") != "DirectoryOrCreate"
        or not str(host_path.get("path", "")).startswith("/var/local-path-provisioner/")
        or pv["metadata"].get("annotations", {}).get(
            "pv.kubernetes.io/provisioned-by"
        ) != "rancher.io/local-path"
    ):
        raise ValueError("evidence PV is not the reviewed local-path hostPath type")
    claim = pv["spec"].get("claimRef", {})
    if (
        claim.get("uid") != metadata["uid"]
        or claim.get("name") != metadata["name"]
        or claim.get("namespace") != NAMESPACE
    ):
        raise ValueError("evidence PV claim identity changed")
    terms = pv["spec"].get("nodeAffinity", {}).get("required", {}).get(
        "nodeSelectorTerms", []
    )
    nodes = {
        value
        for term in terms
        for expression in term.get("matchExpressions", [])
        if expression.get("key") == "kubernetes.io/hostname"
        for value in expression.get("values", [])
    }
    if NODE not in nodes:
        raise ValueError("evidence PV node affinity changed")
    return {
        "pvc_name": metadata["name"],
        "pvc_uid": metadata["uid"],
        "pv_name": spec["volumeName"],
        "pv_uid": pv["metadata"]["uid"],
        "namespace": NAMESPACE,
        "node": NODE,
        "access_modes": spec["accessModes"],
        "storage_class": spec["storageClassName"],
        "capacity": status["capacity"]["storage"],
        "volume_backend": "rancher.io/local-path hostPath DirectoryOrCreate",
        "host_path": host_path["path"],
        "mount_path": EVIDENCE_MOUNT,
        "evidence_directory_name": EVIDENCE_DIRECTORY_NAME,
        "evidence_directory": EVIDENCE,
        "run_as_uid": 1000,
        "run_as_gid": 1000,
        "fs_group": 1000,
        "automatic_delete": False,
        "recovery_mode": "read-only helper Pod on the bound node",
    }


def validate_evidence_mount_root(value: dict) -> dict:
    if value.get("process_uid") != 1000 or value.get("process_gid") != 1000:
        raise ValueError("evidence mount process identity changed")
    if not value.get("directory") or value.get("symlink"):
        raise ValueError("evidence mount root type changed")
    if not value.get("writable") or not value.get("searchable"):
        raise ValueError("evidence mount root is not usable by the worker")
    return value


def build_offline_manifest() -> dict:
    paths = {
        "runner": Path(__file__),
        "pod_workload": Q04 / "pod_workload_d.py",
        "pod_init": Q04 / "pod_init_d.py",
        "remote_evidence": Q04 / "pod_remote_evidence_d.py",
        "durable_evidence": Q04 / "pod_durable_evidence.py",
        "evidence_directory": Q04 / "pod_evidence_directory_d.py",
        "pre_inference": Q04 / "pod_preflight_d.py",
        "topology_builder": Q04 / "pod_topology_d.py",
        "worker_yaml": WORKER_YAML,
        "source_manifest": Q04 / "pod-topology-v3/SOURCE-MANIFEST.json",
        "run_plan": Q04 / "pod-topology-v3/RUN-PLAN.md",
        "readme": Q04 / "pod-topology-v3/README.md",
        "pre_inference_gates": Q04 / "pod-topology-v3/PRE-INFERENCE-GATES.md",
        "storage_reconciliation": Q04 / "pod-topology-v3/STORAGE-RECONCILIATION.json",
        "offline_validation": Q04 / "pod-topology-v3/OFFLINE-VALIDATION.md",
        "integration_manifest": Q04 / "pod-topology-v1/INTEGRATION-MANIFEST.json",
        "durable_evidence_feasibility": Q04 / "pod-topology-v1/DURABLE-EVIDENCE-FEASIBILITY.md",
        "server_dry_run_scope": Q04 / "pod-topology-v1/SERVER-DRY-RUN-SCOPE.md",
        "evidence_capacity": Q04 / "pod-topology-v1/EVIDENCE-CAPACITY.json",
        "pvc_window_plan": Q04 / "pod-topology-v1/PVC-WINDOW-PLAN.md",
        "image_identity_contract": Q04 / "pod-topology-v1/IMAGE-IDENTITY-CONTRACT.md",
        "readiness_preflight_plan": Q04 / "pod-topology-v1/READINESS-PREFLIGHT-PLAN.md",
        "image_identity": Q04 / "image_identity.py",
        "image_manifest": Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/image-chain/platform-manifest.json",
        "image_config": Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/image-chain/config.json",
        "image_cri_inspect": Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/image-chain/cri-inspect.json",
        "image_docker_inspect": Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/image-chain/docker-inspect.json",
        "image_evidence_manifest": Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/EVIDENCE-MANIFEST.json",
        "image_reconciliation": Q04 / "pod-topology-v1/readiness-preflight-v1/evidence/RECONCILIATION.md",
        "outer_admission": Q04 / "outer_admission.py",
        "held_deployment_identity": Q04 / "sentinel/run_yolo_lifecycle_a.py",
    }
    return {
        "schema_version": 1,
        "identity": {
            "phase": PHASE,
            "run_identity": RUN_IDENTITY,
            "prefix": PREFIX,
            "output": str(OUT),
            "deployment": DEPLOYMENT,
        },
        "authorization_scope": authorization_scope(),
        "authorization_scope_sha256": authorization_scope_sha256(),
        "sources": {name: sha256(path.read_bytes()) for name, path in paths.items()},
        "bundle_inputs_sha256": sha256((BUNDLE / "inputs.json").read_bytes()),
        "workload_argv": workload_argv(),
        "exact_single_run_command": exact_command(),
        "runtime_authorized": False,
        "runtime_readiness": "OFFLINE_READY_FOR_REVIEW",
        "runtime_blocker": (
            "main review of the D directory contract and one separate authorization; "
            "live D hostPath feasibility remains unproven"
        ),
        "private_configmap_upload_requires_approval": True,
        "cluster_mutation_requires_approval": True,
        "server_side_dry_run_forbidden": True,
    }


def offline_check() -> dict:
    manifest = build_offline_manifest()
    if json.loads(OFFLINE_MANIFEST.read_text()) != manifest:
        raise ValueError("runner manifest differs from executable plan")
    topology = json.loads(WORKER_YAML.read_text())
    pod_topology.validate(topology)
    if topology["items"][3]["spec"]["replicas"] != 0:
        raise ValueError("committed topology is active")
    if workload_argv()[workload_argv().index("--workload-seconds") + 1] != "825":
        raise ValueError("workload budget changed")
    return {
        "status": "PASS_OFFLINE_ONLY",
        "authorization_scope_sha256": authorization_scope_sha256(),
        "exact_single_run_command": exact_command(),
        "runtime_authorized": False,
        "runtime_readiness": "OFFLINE_READY_FOR_REVIEW",
    }


class Kubectl:
    """Small command adapter used by the runner and replaced by local tests."""

    base = ["kubectl", "--context", CONTEXT, "--request-timeout=15s", "-n", NAMESPACE]

    def run(self, args, *, input=None, text=True, timeout=30):
        return subprocess.check_output(
            self.base + list(args), input=input, text=text, timeout=timeout
        )

    def json(self, *args, timeout=30):
        return json.loads(self.run([*args, "-o", "json"], timeout=timeout))

    def exec_python(self, pod: str, program: str, timeout=30) -> str:
        return self.run(
            ["exec", pod, "--", "/experiment/.venv/bin/python", "-c", program],
            timeout=timeout,
        )


def sample_program() -> str:
    return """import json,os,time
from pathlib import Path
def fields(path):return {x.split()[0].rstrip(':'):int(x.split()[1]) for x in Path(path).read_text().splitlines()}
full=next(x for x in Path('/proc/pressure/memory').read_text().splitlines() if x.startswith('full '))
pressure=dict(x.split('=') for x in full.split()[1:])
evidence=Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d');used=sum(p.stat().st_size for p in evidence.rglob('*') if p.is_file())
fs=os.statvfs(evidence);filesystem_free=fs.f_frsize*fs.f_bavail
print(json.dumps({'time':time.time(),'available':fields('/proc/meminfo')['MemAvailable']*1024,
 'vm_oom_kill':fields('/proc/vmstat')['oom_kill'],'memory_current':int(Path('/sys/fs/cgroup/memory.current').read_text()),
 'memory_events':fields('/sys/fs/cgroup/memory.events'),'psi_full_avg10':float(pressure['avg10']),
 'evidence_used_bytes':used,'evidence_free_bytes':max(0,1073741824-used),
 'evidence_filesystem_free_bytes':filesystem_free}))
"""


def _fields(raw: str) -> dict[str, int]:
    return {
        line.split()[0].rstrip(":"): int(line.split()[1])
        for line in raw.splitlines()
        if len(line.split()) >= 2 and line.split()[1].isdigit()
    }


def node_vm_sample(*, deadline: float | None = None) -> dict:
    """Read the Docker VM/node view before a worker cgroup exists."""
    def cat(path):
        timeout = 10 if deadline is None else remaining_timeout(
            deadline, 10, "node VM telemetry"
        )
        return subprocess.check_output(
            ["docker", "exec", NODE, "cat", path], text=True, timeout=timeout
        )

    meminfo = _fields(cat("/proc/meminfo"))
    vmstat = _fields(cat("/proc/vmstat"))
    full = next(
        row for row in cat("/proc/pressure/memory").splitlines()
        if row.startswith("full ")
    )
    pressure = dict(field.split("=") for field in full.split()[1:])
    return {
        "time": time.time(),
        "available": meminfo["MemAvailable"] * 1024,
        "psi_full_avg10": float(pressure["avg10"]),
        "vm_oom_kill": vmstat["oom_kill"],
        # The worker Pod must not exist during outer admission. Its future cgroup
        # therefore has no current charge or OOM event yet.
        "memory_current": 0,
        "memory_events": {"oom_kill": 0},
    }


def verify_outer_identity(kube: Kubectl, *, deadline: float | None = None) -> None:
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "node identity")
    node = kube.json("get", "node", NODE, timeout=timeout)
    if node["metadata"]["uid"] != "b33ff221-3443-4b27-83bd-01ce69d0bb01":
        raise ValueError("node UID changed")
    boot = node["status"]["nodeInfo"]["bootID"]
    if boot != "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3":
        raise ValueError("node boot identity changed")
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "Pod absence")
    pods = kube.json("get", "pods", "-l", "q04-run=" + RUN_LABEL, timeout=timeout)["items"]
    if pods:
        raise ValueError("owned worker Pod already exists")
    verify_held_deployments(kube, deadline=deadline)


def verify_held_deployments(kube: Kubectl, *, deadline: float | None = None) -> None:
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "held Deployments")
    deployments = kube.json("get", "deployments", "-A", timeout=timeout)["items"]
    observed = {
        (item["metadata"]["namespace"], item["metadata"]["name"]): item
        for item in deployments
    }
    for expected in lifecycle.CANDIDATES:
        item = observed[(expected["namespace"], expected["name"])]
        if item["metadata"]["uid"] != expected["uid"]:
            raise ValueError("held Deployment UID changed")
        if item["spec"].get("replicas", 1) != 0 or item["status"].get("readyReplicas", 0) != 0:
            raise ValueError("held Deployment resumed")


def verify_live_pod_identity(
    kube: Kubectl, identity: dict, *, deadline: float | None = None
) -> None:
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "live Pod identity")
    pod = kube.json("get", "pod", identity["pod_name"], timeout=timeout)
    current = validate_pod(pod)
    if (
        current["pod_uid"] != identity["pod_uid"]
        or current["container_id"] != identity["container_id"]
    ):
        raise ValueError("worker Pod/container identity changed")
    verify_held_deployments(kube, deadline=deadline)


def t09a_health(
    kube: Kubectl,
    output: Path,
    *,
    require_idle: bool,
    deadline: float | None = None,
) -> dict:
    health_program = """import asyncio,json,urllib.request
from temporalio.client import Client
async def main():
 c=await Client.connect('temporal:7233')
 print(json.dumps({'healthy':await c.service_client.check_health(),
  'running':[w.id async for w in c.list_workflows(query='ExecutionStatus="Running"')],
  'objects':urllib.request.urlopen('http://objects:9000/minio/health/ready',timeout=5).status}))
asyncio.run(main())
"""
    timeout = 30 if deadline is None else remaining_timeout(deadline, 30, "T09a health")
    value = json.loads(kube.exec_python("coordinator", health_program, timeout=timeout))
    if not (
        value["healthy"]
        and (not require_idle or not value["running"])
        and value["objects"] == 200
    ):
        raise ValueError("T09a is not idle and healthy")
    output.write_text(json.dumps(value, indent=2) + "\n")
    return value


def run_outer_admission(kube: Kubectl, capacity: dict) -> dict:
    t09a_health(
        kube, OUT / "pod-cgroup-health-before-admission.json", require_idle=True
    )
    stream = (OUT / "pre-admission.jsonl").open("x", buffering=1)
    policy = OuterAdmissionPolicy(
        available_bytes=OUTER_AVAILABLE_BYTES,
        continuous_seconds=CONTINUOUS_SECONDS,
        observation_seconds=OUTER_OBSERVATION_SECONDS,
        sample_interval_seconds=1,
        max_sample_gap_seconds=2,
        max_cgroup_bytes=CGROUP_GUARD_BYTES,
        expected_vm_oom_kill=capacity["expected_vm_oom_kill"],
        expected_cgroup_oom_kill=0,
        minimum_work_seconds=WORKLOAD_SECONDS,
        cleanup_seconds=CLEANUP_SECONDS,
    )
    try:
        result = observe_capacity(
            policy,
            lease_ends_at=capacity["ends_at"],
            sample=node_vm_sample,
            verify_identity=lambda: verify_outer_identity(kube),
            record=lambda row: stream.write(json.dumps(row, sort_keys=True) + "\n"),
        )
    finally:
        stream.close()
    t09a_health(
        kube, OUT / "pod-cgroup-health-after-admission.json", require_idle=True
    )
    (OUT / "admission.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def verify_runtime_sample(row: dict, baseline_oom: int) -> None:
    if row["available"] < VM_RUNTIME_FLOOR_BYTES:
        raise ValueError("VM runtime memory floor breached")
    if row["psi_full_avg10"] != 0:
        raise ValueError("VM PSI guard breached")
    if row["vm_oom_kill"] != baseline_oom:
        raise ValueError("VM OOM counter changed")
    events = row["memory_events"]
    if any(events.get(name, 0) != 0 for name in ("oom", "oom_kill", "oom_group_kill")):
        raise ValueError("worker cgroup OOM counter changed")
    if row["memory_current"] > CGROUP_GUARD_BYTES:
        raise ValueError("4 GiB qualification guard breached")
    if (
        row.get("evidence_used_bytes", 2**63) > 939_524_096
        or row.get("evidence_free_bytes", -1) < 134_217_728
        or row.get("evidence_filesystem_free_bytes", -1) < 134_217_728
    ):
        raise ValueError("evidence PVC stop watermark reached")


def stop_owned_supervisor_program(graceful_seconds: float) -> str:
    return """import json,os,signal,time
from pathlib import Path
path=Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d/supervisor-ownership.json')
if not path.exists(): print(json.dumps({'identity_published':False}));raise SystemExit(0)
owner=json.loads(path.read_text());pid=owner['pid']
raw=(Path('/proc')/str(pid)/'stat').read_text();ticks=int(raw[raw.rfind(')')+1:].split()[19])
if ticks!=owner['start_ticks']: raise ValueError('supervisor PID identity changed')
os.kill(pid,signal.SIGINT)
deadline=time.monotonic()+GRACE
while (Path('/proc')/str(pid)).exists() and time.monotonic()<deadline: time.sleep(.2)
print(json.dumps({'identity_published':True,'pid':pid,'start_ticks':ticks,
 'absent':not (Path('/proc')/str(pid)).exists()}))
""".replace("GRACE", repr(graceful_seconds))


def terminal_cleanup_program() -> str:
    return """import json
from pathlib import Path
root=Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d');owner=json.loads((root/'supervisor-ownership.json').read_text())
cleanup=json.loads((root/'cleanup-complete.json').read_text())
absent=not (Path('/proc')/str(owner['pid'])).exists()
complete=all(cleanup.get(k) is True for k in ('worker_absent','owned_children_absent','scratch_absent'))
print(json.dumps({'pid':owner['pid'],'start_ticks':owner['start_ticks'],
 'supervisor_absent':absent,'cleanup_complete':complete}))
"""


def force_stop_supervisor_program() -> str:
    return """import json,os,shutil,signal,time,psutil
from pathlib import Path
root=Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d');owner=json.loads((root/'supervisor-ownership.json').read_text());pid=owner['pid']
proc=Path('/proc')/str(pid);stat=proc/'stat';supervisor=psutil.Process(pid);owned=supervisor.children(recursive=True)
raw=stat.read_text();ticks=int(raw[raw.rfind(')')+1:].split()[19])
if ticks!=owner['start_ticks']: raise ValueError('supervisor PID identity changed')
groups=set()
for child in owned:
 try: groups.add(os.getpgid(child.pid))
 except ProcessLookupError: pass
owned_path=root/'ownership.json'
if owned_path.exists():
 execution=json.loads(owned_path.read_text());epid=execution['pid'];eproc=Path('/proc')/str(epid)
 if (eproc/'stat').exists():
  raw=(eproc/'stat').read_text();ticks=int(raw[raw.rfind(')')+1:].split()[19])
  if ticks!=execution['start_ticks']: raise ValueError('measurement PID identity changed')
  process=psutil.Process(epid);owned=list({p.pid:p for p in owned+process.children(recursive=True)}.values())
  if os.getpgid(epid)!=epid: raise ValueError('measurement process group changed')
  groups.add(epid);os.killpg(epid,signal.SIGKILL)
for child in reversed(owned):
 try:
  group=os.getpgid(child.pid)
  if group==child.pid: os.killpg(group,signal.SIGKILL)
  else: child.kill()
 except (ProcessLookupError,psutil.NoSuchProcess): pass
if owned: psutil.wait_procs(owned,timeout=10)
if stat.exists():
 os.kill(pid,signal.SIGKILL)
 deadline=time.monotonic()+10
 while proc.exists() and time.monotonic()<deadline: time.sleep(.05)
unknown=[];remaining=[]
for candidate in Path('/proc').iterdir():
 if not candidate.name.isdigit(): continue
 try:
  row=(candidate/'stat').read_text();pgrp=int(row[row.rfind(')')+1:].split()[2])
  if pgrp in groups: remaining.append(int(candidate.name))
 except FileNotFoundError: pass
 except (PermissionError,ValueError,IndexError) as error: unknown.append([candidate.name,type(error).__name__])
owned_absent=not remaining and not unknown and all(not (Path('/proc')/str(p.pid)).exists() for p in owned)
config=json.loads((root/'state/config.json').read_text());scratches=[]
if config.get('pod_namespace'): scratches=[Path('/scratch')/config['run_id']]
else: scratches=[path/'scratch' for path in (root/'state/yolo-pod-cgroup-d').glob('worker-*')]
if owned_absent and not proc.exists():
 for scratch in scratches: shutil.rmtree(scratch,ignore_errors=True)
scratch_absent=all(not path.exists() for path in scratches)
print(json.dumps({'pid':pid,'start_ticks':owner['start_ticks'],'absent':not proc.exists(),
 'owned_group_absent':owned_absent,'remaining_group_pids':remaining,'proc_scan_unknown':unknown,
 'scratch_paths':[str(path) for path in scratches],'scratch_absent':scratch_absent}))
"""


def archive_fingerprint_program() -> str:
    return """import hashlib,json
from pathlib import Path
root=Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d');rows=[]
for path in sorted(root.rglob('*')):
 if not path.is_file(): continue
 name=path.relative_to(root).as_posix()
 if name=='inputs' or name.startswith('inputs/'): continue
 raw=path.read_bytes();rows.append([name,len(raw),hashlib.sha256(raw).hexdigest()])
print(json.dumps(rows,separators=(',',':')))
"""


def verify_local_archive(path: Path, remote_rows: list[list]) -> None:
    expected = {name: (size, digest) for name, size, digest in remote_rows}
    observed = {}
    with tarfile.open(path, "r") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            name = member.name.removeprefix("./")
            if name == "inputs" or name.startswith("inputs/"):
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError("archive file body missing")
            raw = stream.read()
            if name in observed:
                raise ValueError("duplicate archive evidence path")
            observed[name] = (len(raw), sha256(raw))
    if observed != expected:
        raise ValueError("local archive differs from stable remote fingerprint")


def verify_terminal_volume_identity(path: Path, expected: dict) -> None:
    terminal = json.loads(path.read_text())
    if terminal.get("volume_identity") != expected:
        raise ValueError("durable terminal PVC identity changed")


def remaining_timeout(deadline: float, maximum: float, action: str) -> float:
    remaining = deadline - time.time()
    if remaining <= 0:
        raise TimeoutError(f"lease expired before {action}")
    return max(0.001, min(maximum, remaining))


def stop_transport_process(
    process,
    *,
    recovery_deadline: float,
    timeout_for=remaining_timeout,
) -> dict:
    """Stop the local kubectl transport without blocking owned-Pod cleanup."""
    result = {
        "signal_sent": False,
        "graceful_timeout": False,
        "forced": False,
        "confirmed_absent": False,
        "errors": {},
    }
    try:
        process.send_signal(2)
        result["signal_sent"] = True
    except BaseException as error:
        result["errors"]["send_signal"] = repr(error)

    if process.poll() is None:
        try:
            process.wait(timeout=timeout_for(
                recovery_deadline, 30, "kubectl transport stop"
            ))
        except subprocess.TimeoutExpired:
            result["graceful_timeout"] = True
        except BaseException as error:
            result["errors"]["graceful_wait"] = repr(error)

    if process.poll() is None:
        try:
            process.kill()
            result["forced"] = True
        except BaseException as error:
            result["errors"]["kill"] = repr(error)
        if process.poll() is None:
            try:
                process.wait(timeout=timeout_for(
                    recovery_deadline, 10, "forced kubectl transport stop"
                ))
            except BaseException as error:
                result["errors"]["forced_wait"] = repr(error)

    result["confirmed_absent"] = process.poll() is not None
    result["uncertain"] = bool(result["errors"]) or not result["confirmed_absent"]
    return result


def transport_receipt_expired(future, submitted_at: float | None, now: float) -> bool:
    return (
        future is not None
        and submitted_at is not None
        and now - submitted_at > TRANSPORT_GAP_SECONDS
    )


def create_owned_objects(kube: Kubectl, items: list[dict], owned: list[dict]) -> list[dict]:
    """Atomically create each object and record only server-returned ownership."""
    created = []
    for item in items:
        obj = json.loads(kube.run(
            ["create", "-f", "-", "-o", "json"],
            input=json.dumps(item),
            timeout=30,
        ))
        owned.append({
            "kind": item["kind"],
            "name": item["metadata"]["name"],
            "uid": obj["metadata"]["uid"],
        })
        created.append(obj)
    return created


def validate_created_deployment(
    deployment: dict,
    owned_objects: list[dict],
    *,
    deployment_name: str = DEPLOYMENT,
) -> dict:
    recorded = [
        item for item in owned_objects
        if item["kind"] == "Deployment" and item["name"] == deployment_name
    ]
    if len(recorded) != 1:
        raise PodIdentityRejected("exactly one created Deployment identity required")
    if deployment.get("metadata", {}).get("uid") != recorded[0]["uid"]:
        raise PodIdentityRejected("created Deployment UID changed")
    return deployment


def cleanup_deployment_and_pod(
    kube: Kubectl,
    deployment: dict,
    pod_identity: dict | None,
    *,
    deadline: float,
    deployment_name: str = DEPLOYMENT,
    namespace: str = NAMESPACE,
    node_name: str = NODE,
    emptydir_names: tuple[str, ...] = ("scratch", "control", "tmp"),
) -> dict:
    result = {}
    current = kube.json(
        "get", "deployment", deployment_name,
        timeout=remaining_timeout(deadline, 30, "Deployment cleanup identity"),
    )
    before = current["spec"].get("replicas", 0)
    patch = scale_patch(
        deployment["metadata"]["uid"],
        current["metadata"]["resourceVersion"],
        before,
        0,
    )
    kube.run(
        ["patch", "deployment", deployment_name, "--type=json", "-p", json.dumps(patch)],
        timeout=remaining_timeout(deadline, 30, "scale-to-zero"),
    )
    result["deployment_scaled_zero"] = True
    if pod_identity is None:
        return result
    current_pod = kube.run(
        [
            "get", "pod", pod_identity["pod_name"],
            "--ignore-not-found", "-o", "name",
        ],
        timeout=remaining_timeout(deadline, 15, "Pod cleanup identity"),
    ).strip()
    if current_pod:
        live_pod = kube.json(
            "get", "pod", pod_identity["pod_name"],
            timeout=remaining_timeout(deadline, 15, "Pod cleanup UID re-read"),
        )
        if live_pod.get("metadata", {}).get("uid") != pod_identity["pod_uid"]:
            raise PodIdentityRejected("Pod cleanup UID changed")
        observed_node = live_pod.get("spec", {}).get("nodeName")
        if observed_node is not None:
            pod_identity = {**pod_identity, "node": observed_node}
        kube.run(
            [
                "delete", "--raw",
                f"/api/v1/namespaces/{namespace}/pods/{pod_identity['pod_name']}",
                "-f", "-",
            ],
            input=json.dumps(pod_delete_options(pod_identity["pod_uid"])),
            timeout=remaining_timeout(deadline, 30, "Pod UID-fenced delete"),
        )
        result["pod_delete_uid_precondition_sent"] = True
        result["pod_delete_grace_seconds"] = 60
    while kube.run(
        ["get", "pod", pod_identity["pod_name"], "--ignore-not-found", "-o", "name"],
        timeout=remaining_timeout(deadline, 15, "Pod absence check"),
    ).strip():
        if time.time() >= deadline:
            raise TimeoutError("owned Pod did not terminate")
        time.sleep(1)
    # The reviewed Deployment is pinned to NODE. Even an initially unscheduled
    # Pod may have reached the kubelet and disappeared before the API re-read,
    # so absence must still be proved against that node.
    node = pod_identity.get("node") or node_name
    while True:
        raw = subprocess.check_output(
            [
                "docker", "exec", node, "crictl", "ps", "-a",
                "--label", "io.kubernetes.pod.uid=" + pod_identity["pod_uid"],
                "-o", "json",
            ],
            text=True,
            timeout=remaining_timeout(deadline, 20, "container absence check"),
        )
        containers_absent = not json.loads(raw)["containers"]
        emptydirs_absent = all(
            subprocess.run(
                [
                    "docker", "exec", node, "test", "!", "-e",
                    f"/var/lib/kubelet/pods/{pod_identity['pod_uid']}/volumes/kubernetes.io~empty-dir/{volume}",
                ],
                check=False,
                timeout=remaining_timeout(deadline, 20, "emptyDir absence check"),
            ).returncode == 0
            for volume in emptydir_names
        )
        if containers_absent and emptydirs_absent:
            break
        if time.time() >= deadline:
            raise TimeoutError("owned Pod runtime or emptyDir did not disappear")
        time.sleep(1)
    result["old_runtime_absent"] = True
    result["emptydirs_absent"] = True
    return result


def delete_owned_objects(
    kube: Kubectl, owned_objects: list[dict], *, deadline: float
) -> dict:
    deleted = []
    retained = []
    errors = {}
    for obj in reversed(owned_objects):
        if obj["kind"] == "PersistentVolumeClaim":
            retained.append(obj)
            continue
        resource = {"Deployment": "deployments", "ConfigMap": "configmaps"}[
            obj["kind"]
        ]
        body = json.dumps({
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {"uid": obj["uid"]},
        })
        try:
            kube.run(
                [
                    "delete", "--raw",
                    f"/apis/apps/v1/namespaces/{NAMESPACE}/{resource}/{obj['name']}"
                    if obj["kind"] == "Deployment"
                    else f"/api/v1/namespaces/{NAMESPACE}/{resource}/{obj['name']}",
                    "-f", "-",
                ],
                input=body,
                timeout=remaining_timeout(deadline, 30, "owned object deletion"),
            )
            deleted.append(obj)
        except BaseException as error:
            errors[obj["kind"] + "/" + obj["name"]] = repr(error)
    return {"deleted": deleted, "retained": retained, "errors": errors}


def cleanup_disposition(
    *,
    api_cleanup_confirmed: bool,
    pvc_retained: bool,
    workload_evidence_status: str,
    pvc_expected: bool = True,
) -> str:
    if not api_cleanup_confirmed:
        return "NEEDS_INTERVENTION"
    if not pvc_expected:
        return "CLEANED_NO_OBJECTS"
    if not pvc_retained:
        return "FAIL_EVIDENCE_PVC_NOT_RETAINED"
    if workload_evidence_status == "NOT_STARTED":
        return "CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED"
    if workload_evidence_status == "CONTROLLER_EXPORT_COMPLETE":
        return "CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED"
    return "CLEANED_WITH_PVC_RETAINED_WORKLOAD_EVIDENCE_INCOMPLETE"


def cleanup_policy(
    *, controller_export_complete: bool, deployment_created: bool, pvc_created: bool
) -> dict:
    return {
        "controller_export_complete": controller_export_complete,
        "remove_owned_runtime": deployment_created,
        "retain_evidence_pvc": pvc_created,
    }


def verify_retained_evidence_claim(
    kube: Kubectl,
    owned_objects: list[dict],
    evidence_volume: dict | None,
    *,
    deadline: float,
) -> dict:
    claims = [
        item for item in owned_objects
        if item["kind"] == "PersistentVolumeClaim"
    ]
    if len(claims) != 1:
        raise ValueError("exactly one owned evidence PVC required")
    expected = claims[0]
    pvc = kube.json(
        "get", "pvc", expected["name"],
        timeout=remaining_timeout(deadline, 30, "retained PVC identity"),
    )
    if pvc["metadata"]["uid"] != expected["uid"]:
        raise ValueError("retained evidence PVC UID changed")
    if pvc["metadata"].get("deletionTimestamp"):
        raise ValueError("retained evidence PVC is terminating")
    if pvc["metadata"].get("ownerReferences"):
        raise ValueError("retained evidence PVC acquired an owner")
    result = {
        "pvc_name": expected["name"],
        "pvc_uid": expected["uid"],
        "phase": pvc.get("status", {}).get("phase"),
        "retained": True,
        "automatic_delete": False,
    }
    if evidence_volume is not None:
        pv = kube.json(
            "get", "pv", evidence_volume["pv_name"],
            timeout=remaining_timeout(deadline, 30, "retained PV identity"),
        )
        storage_class = kube.json(
            "get", "storageclass", "standard",
            timeout=remaining_timeout(deadline, 30, "retained StorageClass identity"),
        )
        observed = validate_evidence_volume(pvc, pv, storage_class)
        if any(evidence_volume.get(key) != value for key, value in observed.items()):
            raise ValueError("retained evidence volume identity changed")
        result["recovery_identity"] = evidence_volume
    return result


def execute_window(args, kube=None) -> dict:
    """Execute exactly once; callers must provide the explicit reviewed digest."""
    offline_check()
    if args.authorization_scope_sha256 != authorization_scope_sha256():
        raise ValueError("authorization scope digest changed")
    kube = kube or Kubectl()
    OUT.mkdir(exist_ok=False)
    capacity = build_capacity(
        starts_at=time.time(), owner=args.owner, approval_reference=args.approval_reference
    )
    (OUT / "capacity.json").write_text(json.dumps(capacity, indent=2) + "\n")
    deployment = None
    owned_objects = []
    pod_identity = None
    cleanup_identity = None
    evidence_volume = None
    workload = None
    vm_stream = None
    mirror = None
    transport_pool = None
    transport_future = None
    transport_submitted_at = None
    evidence_captured = False
    primary_error = None
    baseline_oom = None
    try:
        admission = run_outer_admission(kube, capacity)
        if admission["minimum_available"] < OUTER_AVAILABLE_BYTES:
            raise ValueError("outer admission threshold changed")
        rendered = json.loads(WORKER_YAML.read_text())
        created_specs = create_owned_objects(kube, rendered["items"], owned_objects)
        (OUT / "created-object-specs.json").write_text(
            json.dumps(created_specs, indent=2) + "\n"
        )
        deployment = validate_created_deployment(
            kube.json("get", "deployment", DEPLOYMENT), owned_objects
        )
        if deployment["spec"].get("replicas") != 0:
            raise ValueError("new Deployment was not inactive")
        patch = scale_patch(
            deployment["metadata"]["uid"],
            deployment["metadata"]["resourceVersion"],
            0,
            1,
        )
        kube.run(
            ["patch", "deployment", DEPLOYMENT, "--type=json", "-p", json.dumps(patch)]
        )
        try:
            pod_identity, cleanup_identity = await_worker_pod(
                kube, deployment, OUT
            )
        except BaseException as readiness_error:
            cleanup_identity = getattr(
                readiness_error, "cleanup_identity", cleanup_identity
            )
            raise
        pod = pod_identity["pod_name"]
        pvc = kube.json("get", "pvc", pod_topology.EVIDENCE_PVC)
        pv = kube.json("get", "pv", pvc["spec"]["volumeName"])
        storage_class = kube.json("get", "storageclass", "standard")
        evidence_volume = validate_evidence_volume(pvc, pv, storage_class)
        created_claim = next(
            item for item in owned_objects
            if item["kind"] == "PersistentVolumeClaim"
        )
        if created_claim["uid"] != evidence_volume["pvc_uid"]:
            raise ValueError("created evidence PVC UID changed")
        mount_permissions = json.loads(kube.exec_python(
            pod,
            "import json,os,stat;from pathlib import Path;"
            "p=Path('/q04-evidence');s=os.lstat(p);m=stat.S_IMODE(s.st_mode);"
            "print(json.dumps({'process_uid':os.getuid(),'process_gid':os.getgid(),"
            "'mount_uid':s.st_uid,'mount_gid':s.st_gid,'mode':oct(m),"
            "'directory':stat.S_ISDIR(s.st_mode),'symlink':stat.S_ISLNK(s.st_mode),"
            "'writable':os.access(p,os.W_OK),'searchable':os.access(p,os.X_OK)}))",
        ))
        evidence_volume["mount_root_permissions"] = validate_evidence_mount_root(
            mount_permissions
        )
        prepare_directory = (
            "from pathlib import Path;import json,sys;"
            "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
            "from pod_evidence_directory_d import prepare_run_directory;"
            "print(json.dumps(prepare_run_directory(Path('/q04-evidence'),"
            + repr(EVIDENCE_DIRECTORY_NAME)
            + "),sort_keys=True))"
        )
        evidence_volume["directory_contract"] = json.loads(
            kube.exec_python(pod, prepare_directory)
        )
        stage_volume_identity = (
            "from pathlib import Path;import json,sys;"
            "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
            "from pod_durable_evidence import write_once;"
            "write_once(Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d/evidence-volume-identity.json'),json.loads(sys.stdin.read()))"
        )
        kube.run(
            ["exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c", stage_volume_identity],
            input=json.dumps(evidence_volume, sort_keys=True),
        )
        (OUT / "evidence-volume-identity.json").write_text(
            json.dumps(evidence_volume, indent=2) + "\n"
        )
        subprocess.run(
            kube.base + ["cp", str(BUNDLE), pod + ":" + CONTROL + "/inputs"],
            check=True,
            timeout=180,
            stdout=(OUT / "bundle-copy.log").open("x"),
            stderr=subprocess.STDOUT,
        )
        capacity_raw = (OUT / "capacity.json").read_bytes()
        stage_capacity = (
            "from pathlib import Path;import sys;"
            "Path('/q04-control/capacity.json').open('xb').write(sys.stdin.buffer.read())"
        )
        kube.run(
            ["exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c", stage_capacity],
            input=capacity_raw.decode(),
        )
        source_manifest_raw = (
            json.dumps(pod_topology.source_manifest(), sort_keys=True) + "\n"
        )
        stage_source_manifest = (
            "from pathlib import Path;import sys;"
            "Path('/q04-control/source-manifest.json').open('xb').write(sys.stdin.read())"
        )
        kube.run(
            [
                "exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c",
                stage_source_manifest,
            ],
            input=source_manifest_raw,
        )
        preflight_deadline = capacity["ends_at"] - WORKLOAD_SECONDS - CLEANUP_SECONDS
        preflight = kube.run(
            ["exec", pod, "--", *preflight_argv()],
            timeout=remaining_timeout(
                preflight_deadline, 180, "single pre-inference gate set"
            ),
        )
        preflight_value = json.loads(preflight)
        if preflight_value.get("status") != "PASS_PRE_INFERENCE":
            raise ValueError("Pod pre-inference gate set did not pass")
        (OUT / "pod-pre-inference-gates.json").write_text(
            json.dumps(preflight_value, indent=2, sort_keys=True) + "\n"
        )
        stage_preflight = (
            "from pathlib import Path;import json,sys;"
            "sys.path.insert(0,'/workspace/tests/pdf_processing/q04');"
            "from pod_durable_evidence import write_once;"
            "write_once(Path(" + repr(EVIDENCE + "/pre-inference-gates.json")
            + "),json.loads(sys.stdin.read()),volume_root=Path(" + repr(EVIDENCE) + "))"
        )
        kube.run(
            [
                "exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c",
                stage_preflight,
            ],
            input=json.dumps(preflight_value, sort_keys=True),
        )
        if time.time() + WORKLOAD_SECONDS + CLEANUP_SECONDS > capacity["ends_at"]:
            raise ValueError("insufficient fixed lease for workload and cleanup")
        evidence_deadline = capacity["ends_at"] - 120
        workload = subprocess.Popen(
            kube.base + ["exec", pod, "--", *workload_argv()],
            stdout=(OUT / "workload-transport.log").open("x"),
            stderr=subprocess.STDOUT,
        )
        vm_stream = (OUT / "vm-controller.jsonl").open("x", buffering=1)
        started = time.monotonic()
        workload_deadline = min(
            capacity["ends_at"] - CLEANUP_SECONDS,
            time.time() + WORKLOAD_SECONDS,
        )
        baseline_oom = capacity["expected_vm_oom_kill"]
        next_transport = started
        next_identity = started
        vm_rows = []
        while workload.poll() is None:
            row = json.loads(kube.exec_python(
                pod, sample_program(),
                timeout=remaining_timeout(workload_deadline, 30, "VM telemetry sample"),
            ))
            verify_runtime_sample(row, baseline_oom)
            if vm_rows:
                gap = row["time"] - vm_rows[-1]["time"]
                if gap <= 0 or gap > 1:
                    raise ValueError("controller VM telemetry gap exceeded")
            vm_rows.append(row)
            vm_stream.write(json.dumps(row, sort_keys=True) + "\n")
            if time.monotonic() >= next_identity:
                verify_live_pod_identity(
                    kube, pod_identity, deadline=workload_deadline
                )
                next_identity = time.monotonic() + TRANSPORT_INTERVAL_SECONDS
            if mirror is None:
                try:
                    owner = json.loads(
                        kube.exec_python(
                            pod,
                            "from pathlib import Path;import json;"
                            "s=json.loads(Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d/supervisor-ownership.json').read_text());"
                            "w=json.loads(Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d/ownership.json').read_text());"
                            "print(json.dumps({'pid':s['pid'],'start_ticks':s['start_ticks'],"
                            "'config_sha256':w['config_sha256']}))",
                        )
                    )
                    identity = PodEvidenceIdentity(
                        pod_uid=pod_identity["pod_uid"],
                        container_id=pod_identity["container_id"],
                        worker_pid=owner["pid"],
                        worker_start_ticks=owner["start_ticks"],
                        config_sha256=owner["config_sha256"],
                    )
                    kube.run(
                        ["exec", "-i", pod, "--", "/experiment/.venv/bin/python", "-c",
                         "from pathlib import Path;import sys;Path('/q04-evidence/q04-yolo-pod-cgroup-20260919-d/transport-identity.json').open('x').write(sys.stdin.read())"],
                        input=json.dumps(identity.__dict__, sort_keys=True),
                    )
                    mirror = IncrementalEvidenceMirror(
                        OUT / "evidence", identity,
                        maximum_transport_gap_seconds=TRANSPORT_GAP_SECONDS,
                    )
                    transport_pool = ThreadPoolExecutor(max_workers=1)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    pass
            if transport_receipt_expired(
                transport_future, transport_submitted_at, time.monotonic()
            ):
                raise TimeoutError("evidence transport receipt gap exceeded")
            if transport_future is not None and transport_future.done():
                transport_future.result()
                transport_future = None
                transport_submitted_at = None
            if mirror is not None and transport_future is None and time.monotonic() >= next_transport:
                transport_future = transport_pool.submit(
                    pull_once, mirror, EVIDENCE,
                    lambda program: kube.exec_python(pod, program),
                    now=time.monotonic,
                )
                transport_submitted_at = time.monotonic()
                next_transport = time.monotonic() + TRANSPORT_INTERVAL_SECONDS
            if time.time() >= workload_deadline:
                raise TimeoutError("Pod workload budget expired")
            time.sleep(SAMPLE_INTERVAL_SECONDS)
        vm_stream.close()
        if not vm_rows:
            raise ValueError("controller VM telemetry never started")
        (OUT / "vm-controller-summary.json").write_text(
            json.dumps(
                {
                    "samples": len(vm_rows),
                    "maximum_gap_seconds": max(
                        (b["time"] - a["time"] for a, b in zip(vm_rows, vm_rows[1:])),
                        default=0,
                    ),
                    "minimum_available_bytes": min(row["available"] for row in vm_rows),
                    "maximum_cgroup_bytes": max(row["memory_current"] for row in vm_rows),
                    "pod_uid": pod_identity["pod_uid"],
                    "container_id": pod_identity["container_id"],
                },
                indent=2,
            )
            + "\n"
        )
        if workload.returncode != 0:
            raise RuntimeError("Pod workload failed; no retry")
        if mirror is None:
            raise ValueError("worker ownership/evidence identity was never published")
        if transport_future is not None:
            transport_future.result(
                timeout=remaining_timeout(evidence_deadline, 30, "final transport")
            )
            transport_future = None
        while not set(FINAL_REQUIRED).issubset(mirror.complete):
            remaining_timeout(evidence_deadline, 30, "complete evidence drain")
            pull_once(
                mirror, EVIDENCE,
                lambda program: kube.exec_python(
                    pod, program,
                    timeout=remaining_timeout(
                        evidence_deadline, 30, "complete evidence drain"
                    ),
                ),
                now=time.monotonic,
            )
        result = mirror.finalize(require_success=True)
        verify_terminal_volume_identity(
            OUT / "evidence/durable-terminal-manifest.json", evidence_volume
        )
        (OUT / "transport-ledger.json").write_text(
            json.dumps({"records": mirror.records, "result": result}, indent=2) + "\n"
        )
        terminal = json.loads(kube.exec_python(
            pod, terminal_cleanup_program(),
            timeout=remaining_timeout(evidence_deadline, 30, "terminal cleanup proof"),
        ))
        if not (terminal["supervisor_absent"] and terminal["cleanup_complete"]):
            raise ValueError("supervisor or cleanup remained after successful workload")
        before_archive = kube.exec_python(
            pod, archive_fingerprint_program(),
            timeout=remaining_timeout(evidence_deadline, 30, "archive fingerprint"),
        )
        mirror.verify_archive_fingerprint(json.loads(before_archive))
        with (OUT / "pod-control-evidence.tar").open("xb") as output:
            subprocess.run(
                kube.base + ["exec", pod, "--", "tar", "cf", "-", "-C", EVIDENCE, "."],
                check=True,
                timeout=remaining_timeout(evidence_deadline, 120, "success evidence export"),
                stdout=output,
                stderr=(OUT / "evidence-tar.log").open("x"),
            )
        after_archive = kube.exec_python(
            pod, archive_fingerprint_program(),
            timeout=remaining_timeout(evidence_deadline, 30, "archive stability proof"),
        )
        if before_archive != after_archive:
            raise ValueError("evidence changed during archive export")
        verify_local_archive(
            OUT / "pod-control-evidence.tar", json.loads(before_archive)
        )
        evidence_captured = True
        return result
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup = {"primary_error": None if primary_error is None else repr(primary_error)}
        cleanup_deadline = capacity["ends_at"]
        recovery_deadline = cleanup_deadline - 120
        terminal_stop_proven = False
        if vm_stream is not None and not vm_stream.closed:
            vm_stream.close()
        if workload is not None and workload.poll() is None:
            if pod_identity is not None:
                try:
                    graceful = max(0.001, remaining_timeout(
                        recovery_deadline, 165, "supervisor graceful stop"
                    ) - 15)
                    cleanup["supervisor_stop"] = json.loads(
                        kube.exec_python(
                            pod_identity["pod_name"],
                            stop_owned_supervisor_program(graceful),
                            timeout=remaining_timeout(
                                recovery_deadline, graceful + 5, "supervisor stop"
                            ),
                        )
                    )
                    if not cleanup["supervisor_stop"].get("absent"):
                        raise RuntimeError("owned supervisor did not stop")
                    terminal_stop_proven = True
                except BaseException as stop_error:
                    cleanup["supervisor_stop_error"] = repr(stop_error)
                    try:
                        cleanup["supervisor_force_stop"] = json.loads(
                            kube.exec_python(
                                pod_identity["pod_name"],
                                force_stop_supervisor_program(),
                                timeout=remaining_timeout(
                                    recovery_deadline, 15, "forced supervisor stop"
                                ),
                            )
                        )
                        terminal_stop_proven = (
                            cleanup["supervisor_force_stop"].get("absent") is True
                            and cleanup["supervisor_force_stop"].get("owned_group_absent") is True
                            and cleanup["supervisor_force_stop"].get("scratch_absent") is True
                        )
                    except BaseException as force_error:
                        cleanup["supervisor_force_stop_error"] = repr(force_error)
            cleanup["transport_stop"] = stop_transport_process(
                workload, recovery_deadline=recovery_deadline
            )
            cleanup["transport_stop_uncertain"] = cleanup["transport_stop"][
                "uncertain"
            ]
        if transport_future is not None:
            try:
                transport_future.result(timeout=remaining_timeout(
                    recovery_deadline, 30, "pending evidence transport"
                ))
            except BaseException as transport_error:
                cleanup["pending_transport_error"] = repr(transport_error)
        if transport_pool is not None:
            transport_pool.shutdown(wait=False, cancel_futures=True)
        if pod_identity is not None and not evidence_captured and workload is not None:
            cleanup["evidence_preserved_before_scale_down"] = False
            try:
                pod = pod_identity["pod_name"]
                terminal = json.loads(kube.exec_python(
                    pod, terminal_cleanup_program(),
                    timeout=remaining_timeout(
                        recovery_deadline, 30, "failure terminal cleanup proof"
                    ),
                ))
                if not (terminal["supervisor_absent"] and terminal["cleanup_complete"]):
                    raise ValueError("failure cleanup markers are incomplete")
                terminal_stop_proven = True
                if mirror is not None and not mirror.finalized:
                    try:
                        while "workload-exit.json" not in mirror.complete:
                            remaining_timeout(
                                recovery_deadline, 30, "failure evidence drain"
                            )
                            pull_once(
                                mirror, EVIDENCE,
                                lambda program: kube.exec_python(
                                    pod, program,
                                    timeout=remaining_timeout(
                                        recovery_deadline, 30,
                                        "failure evidence drain",
                                    ),
                                ),
                                now=time.monotonic,
                            )
                        failure_result = mirror.finalize(require_success=False)
                        (OUT / "transport-ledger.json").write_text(
                            json.dumps(
                                {"records": mirror.records, "result": failure_result},
                                indent=2,
                            )
                            + "\n"
                        )
                    except BaseException as transport_error:
                        cleanup["final_transport_error"] = repr(transport_error)
                before_archive = kube.exec_python(
                    pod, archive_fingerprint_program(),
                    timeout=remaining_timeout(
                        recovery_deadline, 30, "failure archive fingerprint"
                    ),
                )
                if mirror is not None:
                    mirror.verify_archive_fingerprint(json.loads(before_archive))
                with (OUT / "pod-control-failure-evidence.tar").open("xb") as output:
                    subprocess.run(
                        kube.base + ["exec", pod, "--", "tar", "cf", "-", "-C", EVIDENCE, "."],
                        check=True,
                        timeout=remaining_timeout(
                            recovery_deadline, 120, "failure evidence export"
                        ),
                        stdout=output,
                        stderr=(OUT / "failure-evidence-tar.log").open("x"),
                    )
                after_archive = kube.exec_python(
                    pod, archive_fingerprint_program(),
                    timeout=remaining_timeout(
                        recovery_deadline, 30, "failure archive stability proof"
                    ),
                )
                if before_archive != after_archive:
                    raise ValueError("failure evidence changed during archive export")
                verify_local_archive(
                    OUT / "pod-control-failure-evidence.tar",
                    json.loads(before_archive),
                )
                cleanup["evidence_preserved_before_scale_down"] = True
                evidence_captured = True
            except BaseException as capture_error:
                cleanup["evidence_capture_error"] = repr(capture_error)
        if workload is None:
            workload_evidence_status = "NOT_STARTED"
            cleanup["workload_evidence"] = {
                "status": "NOT_STARTED",
                "supervisor": "NOT_STARTED",
                "workflow": "NOT_STARTED",
                "inference": "NOT_STARTED",
            }
        elif evidence_captured:
            workload_evidence_status = "CONTROLLER_EXPORT_COMPLETE"
            cleanup["workload_evidence"] = {
                "status": workload_evidence_status,
                "controller_export_complete": True,
            }
        else:
            workload_evidence_status = "INCOMPLETE"
            cleanup["workload_evidence"] = {
                "status": workload_evidence_status,
                "controller_export_complete": False,
            }
        # The PVC is retained storage. It is called workload evidence only after
        # the supervisor produced terminal records. Always remove owned runtime
        # objects; export failure retains the PVC, never the worker Pod.
        policy = cleanup_policy(
            controller_export_complete=evidence_captured,
            deployment_created=deployment is not None,
            pvc_created=any(
                item["kind"] == "PersistentVolumeClaim" for item in owned_objects
            ),
        )
        cleanup["policy"] = policy
        cleanup["controller_export_complete"] = evidence_captured
        cleanup["retained_for_evidence_recovery"] = False
        cleanup["terminal_stop_proven"] = terminal_stop_proven
        if pod_identity is not None:
            try:
                terminal_sample = json.loads(kube.exec_python(
                    pod_identity["pod_name"], sample_program(),
                    timeout=remaining_timeout(
                        cleanup_deadline, 15, "terminal cgroup OOM sample"
                    ),
                ))
                verify_runtime_sample(
                    terminal_sample, capacity["expected_vm_oom_kill"]
                )
                (OUT / "terminal-cgroup-sample.json").write_text(
                    json.dumps(terminal_sample, indent=2) + "\n"
                )
                cleanup["terminal_cgroup_oom_proof"] = True
            except BaseException as terminal_sample_error:
                cleanup["terminal_cgroup_oom_proof"] = False
                cleanup["terminal_cgroup_sample_error"] = repr(terminal_sample_error)
        if policy["remove_owned_runtime"]:
            try:
                cleanup.update(
                    cleanup_deployment_and_pod(
                        kube,
                        deployment,
                        pod_identity or cleanup_identity,
                        deadline=cleanup_deadline,
                    )
                )
            except BaseException as runtime_cleanup_error:
                cleanup["runtime_cleanup_error"] = repr(runtime_cleanup_error)
        deletion = delete_owned_objects(
            kube, owned_objects, deadline=cleanup_deadline
        )
        cleanup["owned_object_deletion"] = deletion
        expected_deleted = [
            item for item in owned_objects
            if item["kind"] != "PersistentVolumeClaim"
        ]
        cleanup["owned_objects_deleted_with_uid_preconditions"] = (
            deletion["deleted"] == list(reversed(expected_deleted))
            and not deletion["errors"]
        )
        pvc_expected = policy["retain_evidence_pvc"]
        pvc_retained = False
        if pvc_expected:
            try:
                cleanup["retained_evidence_claim"] = verify_retained_evidence_claim(
                    kube,
                    owned_objects,
                    evidence_volume,
                    deadline=cleanup_deadline,
                )
                pvc_retained = True
            except BaseException as retained_error:
                cleanup["retained_evidence_claim_error"] = repr(retained_error)
        try:
            verify_outer_identity(kube, deadline=cleanup_deadline)
            t09a_health(
                kube, OUT / "pod-cgroup-health-after-cleanup.json",
                require_idle=True,
                deadline=cleanup_deadline,
            )
            final_vm = node_vm_sample(deadline=cleanup_deadline)
            if (
                final_vm["vm_oom_kill"] != capacity["expected_vm_oom_kill"]
                or final_vm["psi_full_avg10"] != 0
            ):
                raise ValueError("post-cleanup VM OOM/PSI guard changed")
            (OUT / "post-cleanup-vm-sample.json").write_text(
                json.dumps(final_vm, indent=2) + "\n"
            )
            cleanup["post_cleanup_vm_oom_proof"] = True
            cleanup["final_identity_and_health"] = True
        except BaseException as final_error:
            cleanup["final_identity_and_health"] = False
            cleanup["final_identity_or_health_error"] = repr(final_error)
        api_cleanup_confirmed = (
            not cleanup.get("transport_stop_uncertain", False)
            and not cleanup.get("runtime_cleanup_error")
            and cleanup.get("owned_objects_deleted_with_uid_preconditions") is True
            and cleanup.get("final_identity_and_health") is True
        )
        cleanup["disposition"] = cleanup_disposition(
            api_cleanup_confirmed=api_cleanup_confirmed,
            pvc_retained=pvc_retained,
            workload_evidence_status=workload_evidence_status,
            pvc_expected=pvc_expected,
        )
        cleanup["evidence_state"] = {
            "local_controller_evidence_persisted": OUT.is_dir(),
            "pvc_retained": pvc_retained,
            "workload_evidence": workload_evidence_status,
        }
        OUT.mkdir(exist_ok=True)
        (OUT / "outer-cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
        if primary_error is None and (
            cleanup.get("runtime_cleanup_error")
            or not cleanup.get("terminal_cgroup_oom_proof")
            or not cleanup.get("post_cleanup_vm_oom_proof")
            or not cleanup.get("owned_objects_deleted_with_uid_preconditions")
            or not cleanup.get("final_identity_and_health")
            or cleanup.get("disposition")
            != "CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED"
        ):
            raise RuntimeError("owned Pod cleanup or final health proof failed")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--offline-check", action="store_true")
    value.add_argument("--execute", action="store_true")
    value.add_argument("--owner")
    value.add_argument("--approval-reference")
    value.add_argument("--authorization-scope-sha256")
    return value


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if args.offline_check and not args.execute:
        print(json.dumps(offline_check(), indent=2))
        return 0
    if not args.execute:
        raise SystemExit("--execute plus a separately approved admission record required")
    if not all(
        (args.owner, args.approval_reference, args.authorization_scope_sha256)
    ):
        raise SystemExit("execution identity, approval, digest and admission are required")
    execute_window(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
