"""Run one authorized, no-inference worker image/readiness/cleanup preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import sys
import time

Q04 = Path(__file__).resolve().parent.parent
if str(Q04) not in sys.path:
    sys.path.insert(0, str(Q04))

import pod_topology
from outer_admission import OuterAdmissionPolicy, observe_capacity
from sentinel import run_yolo_pod_cgroup_a as shared


PHASE = "yolo-readiness-preflight-b"
RUN_IDENTITY = "q04-yolo-readiness-preflight-20260919-b"
RUN_LABEL = RUN_IDENTITY
DEPLOYMENT = "q04-yolo-readiness-preflight-b"
NAMESPACE = pod_topology.NAMESPACE
NODE = pod_topology.NODE
OUT = Path("/private/tmp/q04-yolo-readiness-preflight-20260919-b")
ROOT = Q04 / "pod-topology-v1/readiness-preflight-v1"
RENDER = ROOT / "WORKER.json"
MANIFEST = ROOT / "RUNNER-MANIFEST.json"
LOCAL_PYTHON = Path(
    "/Users/david/work/data-ingestion/docs/prototypes/"
    "pdf-checkpoint-prototype/.venv/bin/python"
)

WINDOW_SECONDS = 600
ADMISSION_OBSERVATION_SECONDS = 180
ADMISSION_CONTINUOUS_SECONDS = 60
READINESS_SECONDS = 120
TERMINATION_GRACE_SECONDS = 60
CLEANUP_RESERVE_SECONDS = 180
ADMISSION_AVAILABLE_BYTES = 4_831_838_208
CGROUP_GUARD_BYTES = 4_294_967_296
HARD_LIMIT_BYTES = 5_368_709_120


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def authorization_scope() -> dict:
    return {
        "phase": PHASE,
        "run_identity": RUN_IDENTITY,
        "purpose": "worker image, readiness probe, and cleanup only",
        "workflow_or_inference": False,
        "automatic_retry": False,
        "window_seconds": WINDOW_SECONDS,
        "admission_observation_seconds": ADMISSION_OBSERVATION_SECONDS,
        "admission_continuous_seconds": ADMISSION_CONTINUOUS_SECONDS,
        "readiness_seconds": READINESS_SECONDS,
        "termination_grace_seconds": TERMINATION_GRACE_SECONDS,
        "cleanup_reserve_seconds": CLEANUP_RESERVE_SECONDS,
        "admission_available_bytes": ADMISSION_AVAILABLE_BYTES,
        "cgroup_guard_bytes": CGROUP_GUARD_BYTES,
        "container_hard_limit_bytes": HARD_LIMIT_BYTES,
        "namespace": NAMESPACE,
        "node": NODE,
        "deployment": DEPLOYMENT,
        "kubernetes_objects": ["Deployment"],
        "source_configmaps": False,
        "credentials": False,
        "temporal": False,
        "object_storage": False,
        "persistent_volumes": False,
        "retained_pvc_touched": False,
        "held_deployments_restored": False,
    }


def authorization_scope_sha256() -> str:
    return sha256(canonical(authorization_scope()))


def exact_command() -> str:
    return shlex.join([
        str(LOCAL_PYTHON),
        str(Path(__file__).resolve()),
        "--execute",
        "--owner", "main-session",
        "--approval-reference",
        "Separate explicit main-session authorization for " + RUN_IDENTITY,
        "--authorization-scope-sha256", authorization_scope_sha256(),
    ])


def render_deployment() -> dict:
    labels = {"app": DEPLOYMENT, "q04-run": RUN_LABEL}
    empty_dirs = {
        "scratch": "2Gi",
        "control": "64Mi",
        "evidence": "64Mi",
        "tmp": "256Mi",
    }
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": DEPLOYMENT,
            "namespace": NAMESPACE,
            "labels": {"q04-run": RUN_LABEL},
        },
        "spec": {
            "replicas": 0,
            "revisionHistoryLimit": 0,
            "strategy": {"type": "Recreate"},
            "selector": {"matchLabels": labels},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "automountServiceAccountToken": False,
                    "nodeName": NODE,
                    "terminationGracePeriodSeconds": TERMINATION_GRACE_SECONDS,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "fsGroup": 1000,
                    },
                    "containers": [{
                        "name": "worker",
                        "image": pod_topology.IMAGE,
                        "imagePullPolicy": "IfNotPresent",
                        "command": ["/bin/sh", "-c", "sleep infinity"],
                        "resources": {
                            "requests": {"cpu": "100m", "memory": "4Gi"},
                            "limits": {"cpu": "4", "memory": "5Gi"},
                        },
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "readOnlyRootFilesystem": True,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "volumeMounts": [
                            {"name": name, "mountPath": "/" + ("q04-" + name if name in ("control", "evidence") else name)}
                            for name in empty_dirs
                        ],
                        "readinessProbe": {
                            "exec": {"command": [
                                "/bin/sh", "-c",
                                "test -d /q04-control && test -w /q04-evidence",
                            ]},
                            "periodSeconds": 2,
                            "failureThreshold": 15,
                        },
                    }],
                    "volumes": [
                        {"name": name, "emptyDir": {"sizeLimit": size}}
                        for name, size in empty_dirs.items()
                    ],
                },
            },
        },
    }


def build_manifest() -> dict:
    sources = {
        "runner": Path(__file__),
        "shared_readiness_cleanup": Path(shared.__file__),
        "outer_admission": Q04 / "outer_admission.py",
        "render": RENDER,
        "plan": ROOT / "RUN-PLAN.md",
    }
    return {
        "schema_version": 1,
        "identity": {
            "phase": PHASE,
            "run_identity": RUN_IDENTITY,
            "output": str(OUT),
            "deployment": DEPLOYMENT,
        },
        "authorization_scope": authorization_scope(),
        "authorization_scope_sha256": authorization_scope_sha256(),
        "sources": {name: sha256(path.read_bytes()) for name, path in sources.items()},
        "render_sha256": sha256(canonical(render_deployment())),
        "exact_single_run_command": exact_command(),
        "runtime_authorized": False,
        "runtime_readiness": "READY_FOR_SEPARATE_AUTHORIZATION",
        "runtime_blocker": "one explicit main-session capacity authorization",
        "automatic_retry": False,
    }


def offline_check() -> dict:
    rendered = json.loads(RENDER.read_text())
    if rendered != render_deployment():
        raise ValueError("committed preflight render changed")
    if json.loads(MANIFEST.read_text()) != build_manifest():
        raise ValueError("preflight manifest differs from executable plan")
    raw = canonical(rendered)
    forbidden = (
        b"PersistentVolumeClaim", b"configMap", b"secretKeyRef",
        b"temporal", b"object", b"endpoint", b"q04-pod-cgroup-a-evidence",
    )
    if any(value.lower() in raw.lower() for value in forbidden):
        raise ValueError("preflight render contains forbidden integration")
    if rendered["spec"]["replicas"] != 0:
        raise ValueError("committed preflight Deployment is active")
    return {
        "status": "PASS_OFFLINE_ONLY",
        "authorization_scope_sha256": authorization_scope_sha256(),
        "exact_single_run_command": exact_command(),
        "runtime_authorized": False,
        "runtime_readiness": "READY_FOR_SEPARATE_AUTHORIZATION",
    }


def build_capacity(starts_at: float, owner: str, approval_reference: str) -> dict:
    if not owner or not approval_reference:
        raise ValueError("capacity owner and approval reference required")
    return {
        "status": "AUTHORIZED",
        "phase": PHASE,
        "owner": owner,
        "approval_reference": approval_reference,
        "starts_at": starts_at,
        "ends_at": starts_at + WINDOW_SECONDS,
        "window_seconds": WINDOW_SECONDS,
        "admission_observation_seconds": ADMISSION_OBSERVATION_SECONDS,
        "admission_continuous_seconds": ADMISSION_CONTINUOUS_SECONDS,
        "readiness_seconds": READINESS_SECONDS,
        "termination_grace_seconds": TERMINATION_GRACE_SECONDS,
        "cleanup_reserve_seconds": CLEANUP_RESERVE_SECONDS,
        "expected_vm_oom_kill": 0,
        "authorization_scope_sha256": authorization_scope_sha256(),
        "automatic_retry": False,
    }


def verify_preflight_identity(kube, *, require_absent: bool, deadline=None) -> None:
    def timeout(action: str) -> float:
        return 30 if deadline is None else shared.remaining_timeout(
            deadline, 30, action
        )

    node = kube.json(
        "get", "node", NODE, timeout=timeout("preflight node identity")
    )
    if node["metadata"]["uid"] != "b33ff221-3443-4b27-83bd-01ce69d0bb01":
        raise ValueError("node UID changed")
    if node["status"]["nodeInfo"]["bootID"] != "c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3":
        raise ValueError("node boot identity changed")
    shared.verify_held_deployments(kube, deadline=deadline)
    pods = kube.json(
        "get", "pods", "-l", "q04-run=" + RUN_LABEL,
        timeout=timeout("preflight Pod absence"),
    )["items"]
    replica_sets = kube.json(
        "get", "replicasets", "-l", "q04-run=" + RUN_LABEL,
        timeout=timeout("preflight ReplicaSet absence"),
    )["items"]
    deployment = kube.run(
        ["get", "deployment", DEPLOYMENT, "--ignore-not-found", "-o", "name"],
        timeout=timeout("preflight Deployment absence"),
    ).strip()
    if require_absent and (pods or replica_sets or deployment):
        raise ValueError("preflight identity already exists")


def run_admission(kube, capacity: dict) -> dict:
    stream = (OUT / "pre-admission.jsonl").open("x", buffering=1)
    policy = OuterAdmissionPolicy(
        available_bytes=ADMISSION_AVAILABLE_BYTES,
        continuous_seconds=ADMISSION_CONTINUOUS_SECONDS,
        observation_seconds=ADMISSION_OBSERVATION_SECONDS,
        sample_interval_seconds=1,
        max_sample_gap_seconds=2,
        max_cgroup_bytes=CGROUP_GUARD_BYTES,
        expected_vm_oom_kill=capacity["expected_vm_oom_kill"],
        expected_cgroup_oom_kill=0,
        minimum_work_seconds=READINESS_SECONDS,
        cleanup_seconds=CLEANUP_RESERVE_SECONDS,
    )
    try:
        result = observe_capacity(
            policy,
            lease_ends_at=capacity["ends_at"],
            sample=shared.node_vm_sample,
            verify_identity=lambda: verify_preflight_identity(
                kube, require_absent=True
            ),
            record=lambda row: stream.write(json.dumps(row, sort_keys=True) + "\n"),
        )
    finally:
        stream.close()
    (OUT / "admission.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def delete_deployment(kube, deployment: dict, *, deadline: float) -> None:
    body = {
        "apiVersion": "v1",
        "kind": "DeleteOptions",
        "preconditions": {"uid": deployment["metadata"]["uid"]},
    }
    kube.run(
        [
            "delete", "--raw",
            f"/apis/apps/v1/namespaces/{NAMESPACE}/deployments/{DEPLOYMENT}",
            "-f", "-",
        ],
        input=json.dumps(body),
        timeout=shared.remaining_timeout(deadline, 30, "Deployment UID delete"),
    )


def wait_final_absence(kube, *, deadline: float) -> None:
    while True:
        pods = kube.json(
            "get", "pods", "-l", "q04-run=" + RUN_LABEL,
            timeout=shared.remaining_timeout(
                deadline, 15, "final preflight Pod absence"
            ),
        )["items"]
        replica_sets = kube.json(
            "get", "replicasets", "-l", "q04-run=" + RUN_LABEL,
            timeout=shared.remaining_timeout(
                deadline, 15, "final preflight ReplicaSet absence"
            ),
        )["items"]
        deployment = kube.run(
            ["get", "deployment", DEPLOYMENT, "--ignore-not-found", "-o", "name"],
            timeout=shared.remaining_timeout(
                deadline, 15, "final preflight Deployment absence"
            ),
        ).strip()
        if not pods and not replica_sets and not deployment:
            verify_preflight_identity(
                kube, require_absent=True, deadline=deadline
            )
            return
        if time.time() >= deadline:
            raise TimeoutError("preflight Kubernetes objects did not disappear")
        time.sleep(1)


def execute_window(args, kube=None) -> dict:
    offline_check()
    if args.authorization_scope_sha256 != authorization_scope_sha256():
        raise ValueError("authorization scope digest changed or belongs to a consumed run")
    kube = kube or shared.Kubectl()
    OUT.mkdir(exist_ok=False)
    capacity = build_capacity(time.time(), args.owner, args.approval_reference)
    (OUT / "capacity.json").write_text(json.dumps(capacity, indent=2) + "\n")
    deployment = None
    cleanup_identity = None
    ready_identity = None
    scale_requested = False
    primary_error = None
    cleanup = {"automatic_retry": False}
    try:
        run_admission(kube, capacity)
        startup_deadline = min(
            time.time() + READINESS_SECONDS,
            capacity["ends_at"] - CLEANUP_RESERVE_SECONDS,
        )
        created = json.loads(kube.run(
            ["create", "-f", "-", "-o", "json"],
            input=json.dumps(render_deployment()),
            timeout=shared.remaining_timeout(
                startup_deadline, 30, "preflight Deployment create"
            ),
        ))
        # Retain the create-returned UID before any name-based re-read. If the
        # re-read fails, cleanup can still scale/delete only this exact object.
        deployment = created
        deployment = shared.validate_created_deployment(
            kube.json(
                "get", "deployment", DEPLOYMENT,
                timeout=shared.remaining_timeout(
                    startup_deadline, 30, "preflight Deployment identity"
                ),
            ),
            [{"kind": "Deployment", "name": DEPLOYMENT, "uid": created["metadata"]["uid"]}],
            deployment_name=DEPLOYMENT,
        )
        if deployment["spec"].get("replicas") != 0:
            raise ValueError("new preflight Deployment was not inactive")
        patch = shared.scale_patch(
            deployment["metadata"]["uid"],
            deployment["metadata"]["resourceVersion"],
            0,
            1,
        )
        scale_requested = True
        kube.run([
            "patch", "deployment", DEPLOYMENT, "--type=json", "-p", json.dumps(patch)
        ], timeout=shared.remaining_timeout(
            startup_deadline, 30, "preflight scale-up"
        ))
        try:
            ready_identity, cleanup_identity = shared.await_worker_pod(
                kube,
                deployment,
                OUT,
                timeout_seconds=shared.remaining_timeout(
                    startup_deadline, READINESS_SECONDS, "preflight readiness"
                ),
                run_label=RUN_LABEL,
                node_name=NODE,
                image=pod_topology.IMAGE,
                image_content_id=pod_topology.IMAGE_CONTENT_ID,
                include_events=True,
            )
        except BaseException as error:
            cleanup_identity = getattr(error, "cleanup_identity", cleanup_identity)
            raise
        (OUT / "ready-identity.json").write_text(
            json.dumps(ready_identity, indent=2) + "\n"
        )
    except BaseException as error:
        primary_error = error
    finally:
        deadline = capacity["ends_at"]
        cleanup["primary_error"] = None if primary_error is None else repr(primary_error)
        if deployment is not None:
            try:
                cleanup.update(shared.cleanup_deployment_and_pod(
                    kube,
                    deployment,
                    ready_identity or cleanup_identity,
                    deadline=deadline,
                    deployment_name=DEPLOYMENT,
                    namespace=NAMESPACE,
                    node_name=NODE,
                    emptydir_names=("scratch", "control", "evidence", "tmp"),
                ))
                delete_deployment(kube, deployment, deadline=deadline)
                wait_final_absence(kube, deadline=deadline)
                cleanup["final_absence"] = True
            except BaseException as error:
                cleanup["cleanup_error"] = repr(error)
                cleanup["final_absence"] = False
        cleanup["disposition"] = (
            "CLEANED_NO_INFERENCE_PREFLIGHT"
            if (
                deployment is not None
                and cleanup.get("final_absence") is True
                and (not scale_requested or ready_identity is not None or cleanup_identity is not None)
            )
            else "NEEDS_INTERVENTION"
        )
        if scale_requested and ready_identity is None and cleanup_identity is None:
            cleanup["identity_gap"] = (
                "scale may have created a Pod but no owner-chain UID was captured"
            )
        (OUT / "cleanup.json").write_text(json.dumps(cleanup, indent=2) + "\n")
    if primary_error is not None:
        raise primary_error
    if cleanup["disposition"] != "CLEANED_NO_INFERENCE_PREFLIGHT":
        raise RuntimeError("preflight cleanup was not confirmed")
    result = {
        "status": "PASS_IMAGE_READINESS_CLEANUP_ONLY",
        "run_identity": RUN_IDENTITY,
        "workflow_or_inference_started": False,
        "pod_uid": ready_identity["pod_uid"],
        "image_id": ready_identity["image_id"],
        "cleanup": cleanup["disposition"],
    }
    (OUT / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


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
    if args.execute:
        if not args.owner or not args.approval_reference or not args.authorization_scope_sha256:
            parser().error("--execute requires owner, approval reference and scope digest")
        print(json.dumps(execute_window(args), indent=2))
        return 0
    parser().error("choose --offline-check or --execute")


if __name__ == "__main__":
    raise SystemExit(main())
