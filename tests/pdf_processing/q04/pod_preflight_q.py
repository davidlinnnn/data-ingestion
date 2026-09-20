"""Q pre-inference gates over the repaired producer and Q Pod contract."""

from __future__ import annotations

import argparse
import importlib
import json

import pod_preflight_p as base


PHASE = "aima-pod-cgroup-q"
TOPOLOGY_PHASE = "q04-pod-cgroup-q"
RUN_ID = "q04-aima-pod-cgroup-20260920-q"


def verify_configuration_q(**kwargs):
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
    if base.sha256(inputs) != kwargs["expected_bundle_sha256"]:
        raise ValueError("frozen bundle inputs changed")
    return source_manifest, {
        "status": "PASS",
        "capacity_sha256": base.sha256(kwargs["capacity"]),
        "source_manifest_sha256": base.sha256(kwargs["source_manifest_path"]),
        "bundle_inputs_sha256": kwargs["expected_bundle_sha256"],
    }


def verify_workload_imports_q(*, workspace, bundle, prefix):
    modules = (
        "candidate.aima_pod_window_q",
        "pod_init_p",
        "pod_workload_q",
        "pod_remote_evidence_q",
    )
    for module in modules:
        importlib.import_module(module)
    from candidate.aima_pod_window_o import validate_contract, validate_scope
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
        "profiles": profiles(
            inputs,
            {
                fixture["id"]: {
                    "key": prefix + "sources/" + fixture["id"] + ".pdf"
                }
                for fixture in inputs["fixtures"]
            },
        ),
    }
    validate_contract(config, inputs)
    path = workspace / "tests/pdf_processing/q04/pod-topology-v16/RUNTIME-INTEGRATION-MANIFEST.json"
    manifest = json.loads(path.read_text())
    validate_scope(
        argparse.Namespace(
            integration_manifest=path,
            authorization_scope_sha256=manifest["authorization_scope_sha256"],
            name=PHASE,
            expected_run_id=RUN_ID,
            expected_prefix=prefix,
        )
    )
    return {
        "status": "PASS",
        "modules": list(modules),
        "reviewed_contract": {
            "status": "PASS",
            "fixture": "08",
            "parser_max_requests": 20,
            "production_default_changed": False,
        },
    }


def main(argv=None) -> int:
    args = vars(base.parser().parse_args(argv))
    original = base.verify_configuration
    try:
        base.verify_configuration = verify_configuration_q
        value = base.run_preflight(
            **args, workload_import_probe=verify_workload_imports_q
        )
    finally:
        base.verify_configuration = original
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
