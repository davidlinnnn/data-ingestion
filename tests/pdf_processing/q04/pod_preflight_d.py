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


def verify_runtime_environment(
    *,
    model_cache: Path,
    provenance: Path,
    python: Path,
    cgroup_root: Path,
) -> dict:
    method = _expected_method(provenance)
    if platform.python_version() != method["python"]:
        raise ValueError("frozen Python version changed")
    if Path(sys.executable) != python or not python.is_file() or not os.access(
        python, os.R_OK | os.X_OK
    ):
        raise ValueError("fixed Python executable changed")
    package_versions = {}
    for module_name, distribution_name in PACKAGES.items():
        importlib.import_module(module_name)
        package_versions[distribution_name] = metadata.version(distribution_name)
        if package_versions[distribution_name] != method["packages"][distribution_name]:
            raise ValueError("frozen package version changed: " + distribution_name)
    expected_models = method["model_artifacts"]
    observed_models = {
        name: sha256(model_cache / name) for name in sorted(expected_models)
        if (model_cache / name).is_file()
    }
    if observed_models != expected_models:
        raise ValueError("frozen model artifact set or hash changed")
    model_files = [path for path in model_cache.rglob("*") if path.is_file()]
    if len(model_files) != 35 or any(not os.access(path, os.R_OK) for path in model_files):
        raise ValueError("frozen model cache file count/readability changed")
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
        "python": method["python"],
        "python_executable": str(python),
        "packages": package_versions,
        "model_artifacts": len(expected_models),
        "model_files": len(model_files),
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
    if source_manifest.get("phase") != "q04-pod-cgroup-d":
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


def live_connectivity(*, temporal: str, endpoint: str, bucket: str, prefix: str) -> dict:
    import boto3
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
        "temporal_healthy": True,
        "temporal_running": [],
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
    capacity: Path,
    source_manifest_path: Path,
    bundle: Path,
    authorization_scope_sha256: str,
    expected_bundle_sha256: str,
    temporal: str,
    endpoint: str,
    bucket: str,
    prefix: str,
    connectivity=live_connectivity,
) -> dict:
    source_manifest, configuration = verify_configuration(
        capacity=capacity,
        source_manifest_path=source_manifest_path,
        bundle=bundle,
        authorization_scope_sha256=authorization_scope_sha256,
        expected_bundle_sha256=expected_bundle_sha256,
        expected_phase="yolo-pod-cgroup-d",
    )
    gates = {
        "mount_and_path": inspect_run_directory(
            mount_root, evidence_directory_name
        ),
        "executable_packages_models": verify_runtime_environment(
            model_cache=model_cache,
            provenance=provenance,
            python=python,
            cgroup_root=cgroup_root,
        ),
        "configuration": configuration,
        "source_hashes": verify_sources(workspace, source_manifest),
        "temporal_and_object_connectivity": connectivity(
            temporal=temporal,
            endpoint=endpoint,
            bucket=bucket,
            prefix=prefix,
        ),
    }
    return {
        "schema_version": 1,
        "status": "PASS_PRE_INFERENCE",
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
    value.add_argument("--capacity", type=Path, required=True)
    value.add_argument("--source-manifest", type=Path, required=True)
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
