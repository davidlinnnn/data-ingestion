"""Execute one fixed non-YOLO phase through the reviewed Q04 process runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from sentinel import run_yolo_lifecycle_a as engine


REPO = Path(__file__).resolve().parents[4]
MANIFEST = REPO / "tests/pdf_processing/q04/preflight/candidate-batch-a/MANIFEST.json"
CANDIDATE_MANIFEST = (
    REPO / "tests/pdf_processing/q04/candidate/yolo-lifecycle-v1/MANIFEST.json"
)
LOCAL_BUNDLE = Path("/private/tmp/q04-inputs-yolo-lifecycle-v1")
DRIVER = REPO / "tests/pdf_processing/q04/candidate/candidate_matrix_window.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def load_manifest(path=MANIFEST):
    manifest = json.loads(path.read_text())
    require(manifest["schema_version"] == 1, "batch manifest schema changed")
    require(manifest["runtime_authorized"] is False, "manifest embeds authorization")
    require(manifest["candidate_bundle"] == str(LOCAL_BUNDLE), "candidate bundle path changed")
    require(
        manifest["candidate_inputs_sha256"] == sha256(LOCAL_BUNDLE / "inputs.json"),
        "candidate bundle digest changed",
    )
    require(
        manifest["candidate_manifest_sha256"] == sha256(CANDIDATE_MANIFEST),
        "candidate manifest digest changed",
    )
    candidate = json.loads(CANDIDATE_MANIFEST.read_text())
    require(
        manifest["producer_manifest_sha256"]
        == candidate["producer_manifest_sha256"],
        "candidate producer identity changed",
    )
    phases = manifest["phases"]
    require(
        [phase["fixture"] for phase in phases]
        == ["07", "09", "10", "08", "06", "native"],
        "batch fixture order changed",
    )
    require(sum(phase["window_seconds"] for phase in phases) == 8025,
            "batch lease budget changed")
    require(manifest["lease_budget_seconds"] == 8025,
            "recorded batch lease budget changed")
    require(
        [(phase["window_seconds"], phase["workload_seconds"]) for phase in phases]
        == [(1500, 825), (1200, 525), (1200, 525), (1275, 600),
            (1350, 675), (1500, 825)],
        "reviewed phase budgets changed",
    )
    require(all(phase["candidate_inputs_sha256"]
                == manifest["candidate_inputs_sha256"] for phase in phases),
            "phase candidate bundle identity changed")
    require(all(phase["cleanup_seconds"] == 300 and
                phase["prelease_seconds"] == 300 and
                phase["outer_cleanup_grace_seconds"] == 300 and
                phase["automatic_retry"] is False for phase in phases),
            "phase stop or cleanup contract changed")
    for field in ("phase", "remote_root", "prefix", "local_output", "runner_dir"):
        require(len({phase[field] for phase in phases}) == len(phases),
                field + " identity is not exclusive")
    observed_sources = {
        relative: sha256(REPO / relative)
        for relative in manifest["runner_source_sha256"]
    }
    require(observed_sources == manifest["runner_source_sha256"],
            "batch runner source changed")
    return manifest


def phase_by_key(key, manifest=None):
    manifest = load_manifest() if manifest is None else manifest
    matches = [phase for phase in manifest["phases"] if phase["key"] == key]
    require(len(matches) == 1, "unknown or duplicate phase key")
    phase = matches[0]
    require(phase["fixture"] != "07", "YOLO uses its attributed fixed runner")
    return phase


def runner_sources():
    return {
        "outer_admission.py": REPO / "tests/pdf_processing/q04/outer_admission.py",
        "acl_admission.py": REPO / "tests/pdf_processing/q04/sentinel/acl_admission.py",
        "telemetry.py": REPO / "tests/pdf_processing/q04/telemetry.py",
        "cleanup.py": REPO / "tests/pdf_processing/q04/sentinel/cleanup.py",
        "acl_resource_telemetry.py": REPO
        / "tests/pdf_processing/q04/sentinel/acl_resource_telemetry.py",
        "candidate_matrix_window.py": DRIVER,
        "run_candidate_batch.py": REPO
        / "tests/pdf_processing/q04/sentinel/run_candidate_batch.py",
        "run_candidate_matrix_phase.py": Path(__file__),
        "run_yolo_lifecycle_a.py": REPO
        / "tests/pdf_processing/q04/sentinel/run_yolo_lifecycle_a.py",
    }


def build_staging_probe_program(spec, *, root=None):
    root = spec["remote_root"] if root is None else root
    candidate_files = sorted(engine.candidate_staging_files())
    return """import hashlib,json,sys
from pathlib import Path
root=Path(ROOT)
sys.path[:0]=[str(root/'code/src'),str(root/'code/tests/pdf_processing/q04'),str(root/'code/tests/pdf_processing/q02'),str(root/'code/tests/pdf_processing/q03')]
from prepare import verify_bundle
bundle=verify_bundle(root/'inputs')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'bundle_sha256':sha(root/'inputs/inputs.json'),
 'runtime_sha256':sha(root/'code/tests/pdf_processing/q04/q04_runtime.py'),
 'reference_sha256':sha(root/'inputs/references'/REFERENCE),
 'method':bundle['base_profile']['method'],'producer':bundle['producer'],
 'bound_files':{name:sha(root/'code'/name) for name in CANDIDATE_FILES}}))
""".replace("ROOT", repr(root)).replace(
        "REFERENCE", repr(spec["fixture"] + ".json")
    ).replace("CANDIDATE_FILES", repr(candidate_files))


def validate_staged_runtime(spec, staged, bundle):
    require(
        set(staged)
        == {"bundle_sha256", "runtime_sha256", "reference_sha256", "method",
            "producer", "bound_files"},
        "staging probe schema changed",
    )
    require(staged["bundle_sha256"] == spec["candidate_inputs_sha256"],
            "staged candidate bundle changed")
    require(staged["runtime_sha256"] == spec["runtime_sha256"],
            "staged q04 runtime changed")
    require(staged["reference_sha256"] == spec["reference_sha256"],
            "staged reference graph changed")
    require(staged["method"] == bundle["base_profile"]["method"],
            "staged method changed")
    require(staged["producer"] == bundle["producer"], "staged producer changed")
    expected = {
        name: sha256(path) for name, path in engine.candidate_staging_files().items()
    }
    require(staged["bound_files"] == expected,
            "staged candidate worker or harness changed")


def build_initialized_state_probe_program(spec, *, root=None):
    root = spec["remote_root"] if root is None else root
    return """import hashlib,json
from pathlib import Path
root=Path(ROOT)
config=json.loads((root/'state/config.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
profile=config['profiles'][FIXTURE]
print(json.dumps({'run_id':config['run_id'],'prefix':config['prefix'],
 'bundle':config['bundle'],'bundle_sha256':config['bundle_sha256'],
 'state_sha256':sha(root/'state/config.json'),'producer':config['producer'],
 'profile_method':profile['method'],'profile_id':profile['id'],
 'profile_release':profile['release'],'config_keys':sorted(config),
 'profile_keys':sorted(config['profiles']),'queue_keys':sorted(config['queues']),
 'window':config['window']}))
""".replace("ROOT", repr(root)).replace("FIXTURE", repr(spec["fixture"]))


def validate_initialized_state(spec, initialized, bundle):
    expected_keys = {
        "run_id", "prefix", "bundle", "bundle_sha256", "state_sha256",
        "producer", "profile_method", "profile_id", "profile_release",
        "config_keys", "profile_keys", "queue_keys", "window",
    }
    require(set(initialized) == expected_keys, "initialized state schema changed")
    expected_config_keys = {
        "run_id", "profiles", "producer", "bundle", "state", "temporal",
        "endpoint", "bucket", "prefix", "window", "model_cache", "python",
        "pod_namespace", "trial_seconds", "workflow_queue", "queues", "limits",
        "parser_budgets", "drain_seconds", "bundle_sha256",
    }
    require(set(initialized["config_keys"]) == expected_config_keys,
            "q04 init config fields changed")
    expected_profiles = {row["id"] for row in bundle["fixtures"]} | {
        "native-evidence", "native-method"
    }
    require(set(initialized["profile_keys"]) == expected_profiles,
            "q04 init profile keys changed")
    require(initialized["queue_keys"] == initialized["profile_keys"],
            "q04 init queue/profile keys differ")
    require(initialized["run_id"].startswith("q04-"), "new run id format changed")
    require(initialized["run_id"] != engine.SOURCE_RUN_ID, "source run id reused")
    require(initialized["prefix"] == spec["prefix"], "initialized prefix changed")
    require(
        initialized["bundle"] == spec["remote_root"] + "/inputs",
        "initialized bundle path changed",
    )
    require(
        initialized["bundle_sha256"] == spec["candidate_inputs_sha256"],
        "initialized bundle hash changed",
    )
    require(initialized["producer"] == bundle["producer"],
            "initialized producer changed")
    require(initialized["profile_method"] == bundle["base_profile"]["method"],
            "initialized profile method changed")
    require(initialized["profile_id"] == bundle["base_profile"]["id"],
            "initialized profile id changed")
    require(initialized["profile_release"].startswith("q04-"),
            "initialized profile release format changed")
    window = initialized["window"]
    require(window["status"] == "AUTHORIZED", "capacity status changed")
    require(bool(window["owner"]) and bool(window["approval_reference"]),
            "capacity authorization fields are empty")
    expected_window = {
        "proposed_window_seconds": spec["window_seconds"],
        "admission_seconds": 60,
        "admission_available_bytes": spec["per_case_available_bytes"],
        "outer_observation_seconds": spec["outer_observation_seconds"],
        "outer_continuous_seconds": spec["outer_continuous_seconds"],
        "outer_admission_available_bytes": spec["outer_available_bytes"],
        "minimum_work_seconds": spec["workload_seconds"],
        "cleanup_seconds": spec["cleanup_seconds"],
        "max_cgroup_bytes": spec["max_cgroup_bytes"],
    }
    require({key: window[key] for key in expected_window} == expected_window,
            "initialized capacity window changed")


def build_measurement_argv(spec, expected_run_id, *, python=engine.PYTHON):
    require(expected_run_id.startswith("q04-"), "initialized run identity required")
    return [
        python,
        spec["runner_dir"] + "/candidate_matrix_window.py",
        "--bundle", spec["remote_root"] + "/inputs",
        "--state", spec["remote_root"] + "/state",
        "--capacity", spec["capacity"],
        "--name", spec["phase"],
        "--fixture", spec["fixture"],
        "--expected-run-id", expected_run_id,
        "--expected-prefix", spec["prefix"],
        "--capacity-approved",
    ]


def build_runtime_command(spec, expected_run_id, *, timeout_program="timeout"):
    verify = (
        "import os;from pathlib import Path;from prepare import verify_bundle;"
        "verify_bundle(Path(os.environ['R'])/'inputs')"
    )
    inner = "\n".join(
        (
            f"{shlex.quote(engine.PYTHON)} -c {shlex.quote(verify)}",
            "exec " + shlex.join(build_measurement_argv(spec, expected_run_id)),
        )
    )
    return "\n".join(
        (
            "set -euC",
            "export R=" + shlex.quote(spec["remote_root"]),
            "export PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 "
            "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4",
            'export PYTHONPATH="$R/' + Path(spec["runner_dir"]).name
            + ':$R/code/src:$R/code/tests/pdf_processing/q04:'
            '$R/code/tests/pdf_processing/q02:$R/code/tests/pdf_processing/q03"',
            "export PDF_QUALIFICATION_LOCK=" + shlex.quote(spec["driver_lock"]),
            'cd "$R/code"',
            'test ! -e "$R/state/' + spec["phase"] + '"',
            'test ! -e "$PDF_QUALIFICATION_LOCK"',
            shlex.quote(timeout_program)
            + " --signal=INT --kill-after=180s "
            + str(spec["workload_seconds"])
            + "s sh -eu -c "
            + shlex.quote(inner)
            + ' > "$R/logs/' + spec["phase"] + '.log" 2>&1',
            "",
        )
    )


def require_reviewed_git_state(manifest, sources=None):
    sources = runner_sources() if sources is None else sources
    expected = manifest["runner_source_sha256"]
    observed = {
        str(path.resolve().relative_to(REPO)): sha256(path)
        for path in sources.values()
    }
    require(observed == expected, "reviewed phase runner source changed")
    paths = sorted(set(observed) | {
        str(MANIFEST.relative_to(REPO)), str(CANDIDATE_MANIFEST.relative_to(REPO))
    } | {
        str(path.resolve().relative_to(REPO))
        for path in engine.candidate_staging_files().values()
    })
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *paths],
        cwd=REPO, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for cached in (False, True):
        command = ["git", "diff", "--quiet"]
        if cached:
            command.append("--cached")
        command.extend(["HEAD", "--", *paths])
        require(subprocess.run(command, cwd=REPO).returncode == 0,
                "reviewed phase source has uncommitted changes")
    return {path.name: sha256(path) for path in sources.values()}


def configure_engine(spec, manifest):
    for name, value in {
        "REMOTE": spec["remote_root"],
        "PREFIX": spec["prefix"],
        "PHASE": spec["phase"],
        "OUT": Path(spec["local_output"]),
        "CAPACITY": spec["capacity"],
        "RESERVATION": spec["reservation"],
        "RELEASE": spec["release"],
        "ADMISSION_EVIDENCE": spec["admission_evidence"],
        "ADMISSION_RESULT": spec["admission_result"],
        "RUNNER_DIR": spec["runner_dir"],
        "DRIVER_LOCK": spec["driver_lock"],
        "LOCAL_BUNDLE": LOCAL_BUNDLE,
        "EXPECTED_BUNDLE_SHA256": spec["candidate_inputs_sha256"],
        "WORKLOAD_SECONDS": spec["workload_seconds"],
        "WINDOW_SECONDS": spec["window_seconds"],
    }.items():
        setattr(engine, name, value)
    engine.STATE = {
        "phase": "preparing", "errors": [], "services_expected_closed": 32,
        "services_restored": False, "retry_count": 0,
        "fixture": spec["fixture"], "modes": ["fresh", "restored", "replay"],
    }
    engine.build_staging_probe_program = lambda root=spec["remote_root"]: (
        build_staging_probe_program(spec, root=root)
    )
    engine.validate_staged_runtime = lambda staged, bundle: (
        validate_staged_runtime(spec, staged, bundle)
    )
    engine.build_initialized_state_probe_program = lambda root=spec["remote_root"]: (
        build_initialized_state_probe_program(spec, root=root)
    )
    engine.validate_initialized_state = lambda initialized, bundle: (
        validate_initialized_state(spec, initialized, bundle)
    )
    engine.build_measurement_argv = lambda expected_run_id, **_kwargs: (
        build_measurement_argv(spec, expected_run_id)
    )
    engine.build_runtime_command = lambda expected_run_id, **_kwargs: (
        build_runtime_command(spec, expected_run_id)
    )
    engine.staged_sources = runner_sources
    engine.reviewed_source_hashes = lambda sources=None, manifest_path=None: (
        require_reviewed_git_state(manifest, sources)
    )
    engine.require_reviewed_git_state = lambda sources=None, manifest_path=None: (
        require_reviewed_git_state(manifest, sources)
    )


def offline_phase_record(key, manifest=None):
    manifest = load_manifest() if manifest is None else manifest
    spec = phase_by_key(key, manifest)
    bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
    staged = {
        "bundle_sha256": sha256(LOCAL_BUNDLE / "inputs.json"),
        "runtime_sha256": sha256(REPO / "tests/pdf_processing/q04/q04_runtime.py"),
        "reference_sha256": sha256(LOCAL_BUNDLE / "references" / (spec["fixture"] + ".json")),
        "method": bundle["base_profile"]["method"],
        "producer": bundle["producer"],
        "bound_files": {
            name: sha256(path) for name, path in engine.candidate_staging_files().items()
        },
    }
    validate_staged_runtime(spec, staged, bundle)
    window = {
        "status": "AUTHORIZED", "owner": "offline-review",
        "approval_reference": "offline-validation-only",
        "proposed_window_seconds": spec["window_seconds"],
        "admission_seconds": 60,
        "admission_available_bytes": spec["per_case_available_bytes"],
        "outer_observation_seconds": spec["outer_observation_seconds"],
        "outer_continuous_seconds": spec["outer_continuous_seconds"],
        "outer_admission_available_bytes": spec["outer_available_bytes"],
        "minimum_work_seconds": spec["workload_seconds"],
        "cleanup_seconds": spec["cleanup_seconds"],
        "max_cgroup_bytes": spec["max_cgroup_bytes"],
    }
    profile_keys = sorted(
        {row["id"] for row in bundle["fixtures"]}
        | {"native-evidence", "native-method"}
    )
    initialized = {
        "run_id": "q04-offline-candidate", "prefix": spec["prefix"],
        "bundle": spec["remote_root"] + "/inputs",
        "bundle_sha256": spec["candidate_inputs_sha256"],
        "state_sha256": "offline-state-sha256", "producer": bundle["producer"],
        "profile_method": bundle["base_profile"]["method"],
        "profile_id": bundle["base_profile"]["id"],
        "profile_release": "q04-offline-release",
        "config_keys": sorted({
            "run_id", "profiles", "producer", "bundle", "state", "temporal",
            "endpoint", "bucket", "prefix", "window", "model_cache", "python",
            "pod_namespace", "trial_seconds", "workflow_queue", "queues", "limits",
            "parser_budgets", "drain_seconds", "bundle_sha256",
        }),
        "profile_keys": profile_keys, "queue_keys": profile_keys,
        "window": window,
    }
    validate_initialized_state(spec, initialized, bundle)
    argv = build_measurement_argv(spec, "q04-offline-candidate")
    require(argv == spec["measurement_argv"], "reviewed measurement argv changed")
    command = build_runtime_command(spec, "q04-offline-candidate")
    command_sha256 = hashlib.sha256(command.encode()).hexdigest()
    require(command_sha256 == spec["runtime_command_sha256"],
            "reviewed runtime command changed")
    require(sha256(DRIVER) == manifest["driver_sha256"], "candidate driver changed")
    return {
        "key": key, "fixture": spec["fixture"], "identity": {
            field: spec[field] for field in (
                "phase", "remote_root", "prefix", "local_output", "runner_dir",
                "driver_lock",
            )
        },
        "measurement_argv": argv,
        "runtime_command_sha256": command_sha256,
        "window_seconds": spec["window_seconds"],
        "workload_seconds": spec["workload_seconds"],
        "cleanup_seconds": spec["cleanup_seconds"],
        "runtime_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-key", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner")
    parser.add_argument("--approval-reference")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("runtime execution requires explicit --execute")
    if not args.owner or not args.approval_reference:
        parser.error("--owner and --approval-reference are required")
    manifest = load_manifest()
    spec = phase_by_key(args.phase_key, manifest)
    configure_engine(spec, manifest)
    return engine.main(
        ["--execute", "--owner", args.owner,
         "--approval-reference", args.approval_reference]
    )


if __name__ == "__main__":
    sys.exit(main())
