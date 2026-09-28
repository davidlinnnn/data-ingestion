"""One-shot pre-inference gate set for the Q04 fixture-07 Pod window D."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import sys
import urllib.request

from pod_evidence_directory_d import inspect_run_directory


PACKAGES = {
    "boto3": "boto3",
    "temporalio": "temporalio",
    "PIL": "pillow",
    "psutil": "psutil",
}

EXPECTED_IMAGE = (
    "docker.io/library/pdf-t08-runtime@"
    "sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0"
)
EXPECTED_NODE = "internal-a2a-vs6-local-worker2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_method(provenance: Path) -> dict:
    value = json.loads(provenance.read_text())
    return value["fresh_accepted"]["profile"]["method"]


def verify_sources(workspace: Path, source_manifest: dict) -> dict:
    expected = {}
    expected.update({
        str(workspace / "src/pdf_processing" / name): digest
        for name, digest in source_manifest["producer"].items()
    })
    expected.update({
        str(workspace / name): digest
        for name, digest in source_manifest["harness"].items()
    })
    missing = [name for name in expected if not Path(name).is_file()]
    if missing:
        raise ValueError("staged source path missing: " + repr(missing))
    observed = {name: sha256(Path(name)) for name in expected}
    if observed != expected:
        changed = [name for name in expected if observed[name] != expected[name]]
        raise ValueError("staged source hash changed: " + repr(changed))
    return {
        "status": "PASS",
        "producer_files": len(source_manifest["producer"]),
        "harness_files": len(source_manifest["harness"]),
        "producer_set_sha256": source_manifest["producer_set_sha256"],
        "harness_set_sha256": source_manifest["harness_set_sha256"],
    }


def verify_image_identity(path: Path) -> dict:
    value = json.loads(path.read_text())
    required = {
        "node": EXPECTED_NODE,
        "image_id": EXPECTED_IMAGE,
        "image_id_representation": "repository-platform-manifest",
        "restart_count": 0,
    }
    changed = {
        name: value.get(name)
        for name, expected in required.items()
        if value.get(name) != expected
    }
    for name in ("pod_name", "pod_uid", "container_id"):
        if not isinstance(value.get(name), str) or not value[name]:
            changed[name] = value.get(name)
    if changed:
        raise ValueError("accepted Pod image identity changed: " + repr(changed))
    return {
        "status": "PASS",
        **{name: value[name] for name in required},
        "pod_name": value["pod_name"],
        "pod_uid": value["pod_uid"],
        "container_id": value["container_id"],
    }


def verify_runtime_environment(
    *,
    model_cache: Path,
    provenance: Path,
    python: Path,
    cgroup_root: Path,
) -> dict:
    python_result = verify_python_executable(provenance=provenance, python=python)
    package_result = verify_packages(provenance=provenance)
    model_result = verify_models(model_cache=model_cache, provenance=provenance)
    cgroup_result = verify_cgroup(cgroup_root=cgroup_root)
    return {
        "status": "PASS",
        **python_result,
        "packages": package_result["packages"],
        **model_result,
        **cgroup_result,
    }


def verify_python_executable(*, provenance: Path, python: Path) -> dict:
    method = _expected_method(provenance)
    if platform.python_version() != method["python"]:
        raise ValueError("frozen Python version changed")
    if Path(sys.executable) != python or not python.is_file() or not os.access(
        python, os.R_OK | os.X_OK
    ):
        raise ValueError("fixed Python executable changed")
    return {
        "status": "PASS",
        "python": method["python"],
        "python_executable": str(python),
    }


def verify_packages(*, provenance: Path) -> dict:
    method = _expected_method(provenance)
    package_versions = {}
    for module_name, distribution_name in PACKAGES.items():
        importlib.import_module(module_name)
        package_versions[distribution_name] = metadata.version(distribution_name)
        if package_versions[distribution_name] != method["packages"][distribution_name]:
            raise ValueError("frozen package version changed: " + distribution_name)
    return {"status": "PASS", "packages": package_versions}


def verify_models(*, model_cache: Path, provenance: Path) -> dict:
    method = _expected_method(provenance)
    expected_models = method["model_artifacts"]
    rapidocr_names = {
        name for name in expected_models if name.startswith("rapidocr/")
    }
    rapidocr_root = None
    if rapidocr_names:
        module_path = getattr(importlib.import_module("rapidocr"), "__file__", None)
        if not isinstance(module_path, str) or not module_path:
            raise ValueError("rapidocr package path is unavailable")
        rapidocr_root = Path(module_path).resolve().parent / "models"
    resolved = {
        name: (
            rapidocr_root / name.removeprefix("rapidocr/")
            if name.startswith("rapidocr/")
            else model_cache / name
        )
        for name in expected_models
    }
    observed_models = {
        name: sha256(path)
        for name, path in sorted(resolved.items())
        if path.is_file() and os.access(path, os.R_OK)
    }
    if observed_models != expected_models:
        raise ValueError("frozen model artifact set or hash changed")
    return {
        "status": "PASS",
        "model_artifacts": len(expected_models),
        "cache_artifacts": sum(
            not name.startswith("rapidocr/") for name in expected_models
        ),
        "package_artifacts": sum(
            name.startswith("rapidocr/") for name in expected_models
        ),
    }


def verify_cgroup(*, cgroup_root: Path) -> dict:
    memory_max = (cgroup_root / "memory.max").read_text().strip()
    if memory_max != str(5 * 1024**3):
        raise ValueError("worker cgroup hard limit changed")
    events = {
        row.split()[0]: int(row.split()[1])
        for row in (cgroup_root / "memory.events").read_text().splitlines()
    }
    oom = {
        name: events.get(name, 0) for name in ("oom", "oom_kill", "oom_group_kill")
    }
    if any(oom.values()):
        raise ValueError("worker cgroup did not start with zero OOM counters")
    return {
        "status": "PASS",
        "memory_max": memory_max,
        "oom_counters": oom,
    }


def verify_configuration(
    *,
    capacity: Path,
    source_manifest_path: Path,
    bundle: Path,
    authorization_scope_sha256: str,
    expected_bundle_sha256: str,
    expected_phase: str,
) -> tuple[dict, dict]:
    window = json.loads(capacity.read_text())
    required = {
        "status": "AUTHORIZED",
        "phase": expected_phase,
        "authorization_scope_sha256": authorization_scope_sha256,
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
    }
    changed = {key: window.get(key) for key, expected in required.items() if window.get(key) != expected}
    if changed:
        raise ValueError("capacity configuration changed: " + repr(changed))
    source_manifest = json.loads(source_manifest_path.read_text())
    if source_manifest.get("phase") != "q04-pod-cgroup-f":
        raise ValueError("source manifest phase changed")
    inputs = bundle / "inputs.json"
    if sha256(inputs) != expected_bundle_sha256:
        raise ValueError("frozen bundle inputs changed")
    return source_manifest, {
        "status": "PASS",
        "capacity_sha256": sha256(capacity),
        "source_manifest_sha256": sha256(source_manifest_path),
        "bundle_inputs_sha256": expected_bundle_sha256,
    }


def verify_temporal_connectivity(*, temporal: str) -> dict:
    from temporalio.client import Client

    async def temporal_probe() -> dict:
        client = await Client.connect(temporal)
        healthy = await client.service_client.check_health()
        running = [
            workflow.id
            async for workflow in client.list_workflows(query='ExecutionStatus="Running"')
        ]
        return {"healthy": healthy, "running": running}

    temporal_result = asyncio.run(temporal_probe())
    if not temporal_result["healthy"] or temporal_result["running"]:
        raise ValueError("Temporal is unhealthy or not idle")
    return {
        "status": "PASS",
        "temporal_healthy": True,
        "temporal_running": [],
    }


def verify_object_connectivity(*, endpoint: str, bucket: str, prefix: str) -> dict:
    import boto3

    ready = urllib.request.urlopen(endpoint + "/minio/health/ready", timeout=5).status
    if ready != 200:
        raise ValueError("object health endpoint changed")
    client = boto3.client("s3", endpoint_url=endpoint)
    versioning = client.get_bucket_versioning(Bucket=bucket).get("Status")
    if versioning != "Enabled":
        raise ValueError("versioned object bucket required")
    if client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1).get("Contents"):
        raise ValueError("object prefix is not unused")
    return {
        "status": "PASS",
        "object_health": ready,
        "bucket_versioning": versioning,
        "object_prefix_unused": True,
    }


def run_preflight(
    *,
    workspace: Path,
    mount_root: Path,
    evidence_directory_name: str,
    model_cache: Path,
    provenance: Path,
    python: Path,
    cgroup_root: Path,
    pod_identity: Path,
    capacity: Path,
    source_manifest_path: Path,
    bundle: Path,
    authorization_scope_sha256: str,
    expected_bundle_sha256: str,
    temporal: str,
    endpoint: str,
    bucket: str,
    prefix: str,
    expected_uid: int = 1000,
    expected_gid: int = 1000,
    temporal_probe=verify_temporal_connectivity,
    object_probe=verify_object_connectivity,
) -> dict:
    gates = {}

    def capture(name, operation) -> None:
        try:
            value = operation()
            if value.get("status") != "PASS":
                raise ValueError("gate returned a non-PASS result")
            gates[name] = value
        except Exception as error:
            gates[name] = {
                "status": "FAIL",
                "error_type": type(error).__name__,
                "reason": str(error),
            }

    capture("image_identity", lambda: verify_image_identity(pod_identity))
    capture(
        "mount_and_path",
        lambda: inspect_run_directory(
            mount_root,
            evidence_directory_name,
            expected_uid=expected_uid,
            expected_gid=expected_gid,
        ),
    )
    capture(
        "python_executable",
        lambda: verify_python_executable(
            provenance=provenance,
            python=python,
        ),
    )
    capture("packages_imports", lambda: verify_packages(provenance=provenance))
    capture(
        "models",
        lambda: verify_models(model_cache=model_cache, provenance=provenance),
    )
    capture("cgroup", lambda: verify_cgroup(cgroup_root=cgroup_root))
    capture(
        "configuration",
        lambda: verify_configuration(
            capacity=capacity,
            source_manifest_path=source_manifest_path,
            bundle=bundle,
            authorization_scope_sha256=authorization_scope_sha256,
            expected_bundle_sha256=expected_bundle_sha256,
            expected_phase="yolo-pod-cgroup-f",
        )[1],
    )
    capture(
        "source_hashes",
        lambda: verify_sources(
            workspace, json.loads(source_manifest_path.read_text())
        ),
    )
    capture(
        "temporal",
        lambda: temporal_probe(temporal=temporal),
    )
    capture(
        "object_storage",
        lambda: object_probe(
            endpoint=endpoint,
            bucket=bucket,
            prefix=prefix,
        ),
    )
    failed = [name for name, value in gates.items() if value["status"] != "PASS"]
    return {
        "schema_version": 1,
        "status": "PASS_PRE_INFERENCE" if not failed else "FAIL_PRE_INFERENCE",
        "failed_gates": failed,
        "gates": gates,
        "inference_started": False,
        "workflow_started": False,
        "object_written": False,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--workspace", type=Path, required=True)
    value.add_argument("--mount-root", type=Path, required=True)
    value.add_argument("--evidence-directory-name", required=True)
    value.add_argument("--model-cache", type=Path, required=True)
    value.add_argument("--provenance", type=Path, required=True)
    value.add_argument("--python", type=Path, required=True)
    value.add_argument("--cgroup-root", type=Path, default=Path("/sys/fs/cgroup"))
    value.add_argument("--pod-identity", type=Path, required=True)
    value.add_argument("--capacity", type=Path, required=True)
    value.add_argument(
        "--source-manifest", dest="source_manifest_path", type=Path, required=True
    )
    value.add_argument("--bundle", type=Path, required=True)
    value.add_argument("--authorization-scope-sha256", required=True)
    value.add_argument("--expected-bundle-sha256", required=True)
    value.add_argument("--temporal", required=True)
    value.add_argument("--endpoint", required=True)
    value.add_argument("--bucket", required=True)
    value.add_argument("--prefix", required=True)
    return value


def main(argv=None) -> int:
    print(json.dumps(run_preflight(**vars(parser().parse_args(argv))), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
