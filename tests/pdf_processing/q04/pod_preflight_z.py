"""U pre-inference gates for the corrected Q04 warm sequence."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import sys


_spec = importlib.util.spec_from_file_location(
    "q04_pod_preflight_z_engine", Path(__file__).with_name("pod_preflight_q.py")
)
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)


PHASE = "warm-pod-cgroup-z"
TOPOLOGY_PHASE = "q04-pod-cgroup-z"
RUN_ID = "q04-warm-pod-cgroup-20260921-z"
sha256 = base.base.sha256


def verify_configuration_z(**kwargs):
    window = json.loads(kwargs["capacity"].read_text())
    required = {
        "status": "AUTHORIZED",
        "phase": PHASE,
        "authorization_scope_sha256": kwargs["authorization_scope_sha256"],
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
    changed = {
        key: window.get(key)
        for key, expected in required.items()
        if window.get(key) != expected
    }
    if changed:
        raise ValueError("capacity configuration changed: " + repr(changed))
    source_manifest = json.loads(kwargs["source_manifest_path"].read_text())
    if source_manifest.get("phase") != TOPOLOGY_PHASE:
        raise ValueError("source manifest phase changed")
    inputs = kwargs["bundle"] / "inputs.json"
    if sha256(inputs) != kwargs["expected_bundle_sha256"]:
        raise ValueError("frozen bundle inputs changed")
    from prepare import verify_bundle
    verify_bundle(kwargs["bundle"])
    return source_manifest, {
        "status": "PASS",
        "capacity_sha256": sha256(kwargs["capacity"]),
        "source_manifest_sha256": sha256(kwargs["source_manifest_path"]),
        "bundle_inputs_sha256": kwargs["expected_bundle_sha256"],
    }


def verify_workload_imports_z(*, workspace, bundle, prefix):
    modules = (
        "candidate.warm_pod_window_r",
        "pod_init_p",
        "pod_workload_z",
        "pod_remote_evidence_z",
    )
    for module in modules:
        importlib.import_module(module)
    from candidate.warm_pod_window_r import validate_contract, validate_scope
    from q04_runtime import profiles

    inputs = json.loads((bundle / "inputs.json").read_text())
    config = {
        "parser_budgets": {
            "startup_seconds": 120,
            "no_progress_seconds": 180,
            "terminate_seconds": 5,
            "reap_seconds": 5,
            "max_requests": 20,
        },
        "profiles": profiles(inputs, {
            fixture["id"]: {"key": prefix + "sources/" + fixture["id"] + ".pdf"}
            for fixture in inputs["fixtures"]
        }),
    }
    validate_contract(config, inputs)
    path = workspace / "tests/pdf_processing/q04/pod-topology-v25/RUNTIME-INTEGRATION-MANIFEST.json"
    manifest = json.loads(path.read_text())
    validate_scope(argparse.Namespace(
        integration_manifest=path,
        authorization_scope_sha256=manifest["authorization_scope_sha256"],
        name=PHASE,
        expected_run_id=RUN_ID,
        expected_prefix=prefix,
    ))
    return {
        "status": "PASS",
        "modules": list(modules),
        "reviewed_contract": {
            "status": "PASS",
            "sequence": ["06", "07", "08", "native", "06"],
            "group_requests": 29,
            "parser_max_requests": 20,
            "production_default_changed": False,
        },
    }


base.PHASE = PHASE
base.TOPOLOGY_PHASE = TOPOLOGY_PHASE
base.RUN_ID = RUN_ID
base.verify_configuration_q = verify_configuration_z
base.verify_workload_imports_q = verify_workload_imports_z
main = base.main


if __name__ == "__main__":
    raise SystemExit(main())
