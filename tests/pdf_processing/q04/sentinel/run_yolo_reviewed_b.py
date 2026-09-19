"""Prepare one reviewed fixture-07 matrix under a new immutable identity.

The operational ownership, admission and cleanup implementation is reused from
the reviewed lifecycle-A launcher.  This module supplies a new identity, adopts
the one-field parser budget before any workload, and launches the fixture-local
review adapter.  Importing or validating this module never starts runtime work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
from types import SimpleNamespace

Q04_DIR = Path(__file__).resolve().parent.parent
if str(Q04_DIR) not in sys.path:
    sys.path.insert(0, str(Q04_DIR))

from candidate import yolo_reviewed_window
from sentinel import run_yolo_lifecycle_a as lifecycle


REPO = Path(__file__).resolve().parents[4]
PHASE = "yolo-reviewed-b"
REMOTE = "/tmp/q04-yolo-reviewed-20260919-b"
PREFIX = "q04/yolo-reviewed-20260919-b/"
OUT = Path("/private/tmp/q04-yolo-reviewed-20260919-b")
RUNNER_DIR = REMOTE + "/runner-yolo-reviewed-b"
CAPACITY = REMOTE + "/capacity-yolo-reviewed-b.json"
RESERVATION = REMOTE + "/reservation-yolo-reviewed-b.json"
RELEASE = REMOTE + "/release-reservation-yolo-reviewed-b"
ADMISSION_EVIDENCE = REMOTE + "/pre-admission-yolo-reviewed-b.jsonl"
ADMISSION_RESULT = REMOTE + "/admission-yolo-reviewed-b.json"
DRIVER_LOCK = REMOTE + "/yolo-reviewed-b.driver.lock"
INTEGRATION_ROOT = REPO / "tests/pdf_processing/q04/candidate/yolo-reviewed-v1"
INTEGRATION_MANIFEST = INTEGRATION_ROOT / "MANIFEST.json"
MAIN_REVIEW = INTEGRATION_ROOT / "MAIN-REVIEW.json"
OFFLINE_MANIFEST = (
    REPO
    / "tests/pdf_processing/q04/preflight/yolo-reviewed-b/OFFLINE-MANIFEST.json"
)
LOCAL_BUNDLE = Path("/private/tmp/q04-inputs-yolo-lifecycle-v1")
BASELINE_BUDGETS = yolo_reviewed_window.BASELINE_PARSER_BUDGETS
CANDIDATE_BUDGETS = yolo_reviewed_window.PARSER_BUDGETS


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def integration_manifest() -> dict:
    value = json.loads(INTEGRATION_MANIFEST.read_text())
    lifecycle.require(value.get("schema_version") == 1, "integration schema changed")
    lifecycle.require(value.get("candidate") == "q04-yolo-reviewed-v1", "candidate changed")
    lifecycle.require(value.get("fixture") == "07", "fixture changed")
    lifecycle.require(value.get("modes") == ["fresh", "restored", "replay"], "modes changed")
    lifecycle.require(value.get("runtime_authorized") is False, "manifest embeds authorization")
    lifecycle.require(value.get("production_default_changed") is False,
                      "manifest changes production defaults")
    scope_sha = hashlib.sha256(_canonical(value["authorization_scope"]).encode()).hexdigest()
    lifecycle.require(value.get("authorization_scope_sha256") == scope_sha,
                      "manifest authorization scope digest changed")
    lifecycle.require(
        value.get("identity")
        == {
            "phase": PHASE,
            "remote_root": REMOTE,
            "prefix": PREFIX,
            "local_output": str(OUT),
            "runner_dir": RUNNER_DIR,
            "driver_lock": DRIVER_LOCK,
        },
        "manifest execution identity changed",
    )
    return value


def authorization_scope_sha256() -> str:
    return hashlib.sha256(
        _canonical(integration_manifest()["authorization_scope"]).encode()
    ).hexdigest()


def staged_sources():
    return {
        "outer_admission.py": REPO / "tests/pdf_processing/q04/outer_admission.py",
        "acl_admission.py": REPO / "tests/pdf_processing/q04/sentinel/acl_admission.py",
        "telemetry.py": REPO / "tests/pdf_processing/q04/telemetry.py",
        "cleanup.py": REPO / "tests/pdf_processing/q04/sentinel/cleanup.py",
        "acl_resource_telemetry.py": REPO
        / "tests/pdf_processing/q04/sentinel/acl_resource_telemetry.py",
        "yolo_attribution_telemetry.py": REPO
        / "tests/pdf_processing/q04/sentinel/yolo_attribution_telemetry.py",
        "yolo_candidate_window.py": REPO
        / "tests/pdf_processing/q04/candidate/yolo_candidate_window.py",
        "yolo_candidate_measure.py": REPO
        / "tests/pdf_processing/q04/candidate/yolo_candidate_measure.py",
        "yolo_lifecycle.py": REPO
        / "tests/pdf_processing/q04/candidate/yolo_lifecycle.py",
        "yolo_reviewed_window.py": REPO
        / "tests/pdf_processing/q04/candidate/yolo_reviewed_window.py",
        "yolo_equivalence_candidate.py": REPO
        / "tests/pdf_processing/q04/candidate/yolo_equivalence_candidate.py",
        "yolo_resource_candidate.py": REPO
        / "tests/pdf_processing/q04/candidate/yolo_resource_candidate.py",
        "integration-manifest.json": INTEGRATION_MANIFEST,
        "main-review.json": MAIN_REVIEW,
        "equivalence-bundle.json": REPO
        / "tests/pdf_processing/q04/candidate/yolo-equivalence-v1/BUNDLE.json",
        "resource-bundle.json": REPO
        / "tests/pdf_processing/q04/candidate/yolo-resource-v1/BUNDLE.json",
        "parser-budgets.json": REPO
        / "tests/pdf_processing/q04/candidate/yolo-resource-v1/PARSER-BUDGETS.json",
        "resource-analysis.json": REPO
        / "tests/pdf_processing/q04/diagnosis/yolo-lifecycle-a/evidence/resource-peak.json",
        "historical-methods.json": REPO
        / "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json",
        "run_yolo_lifecycle_a.py": REPO
        / "tests/pdf_processing/q04/sentinel/run_yolo_lifecycle_a.py",
        "capacity-candidates.json": REPO
        / "tests/pdf_processing/q04/diagnosis/evidence/capacity-candidates.json",
        "remote_probe.py": REPO
        / "tests/pdf_processing/q04/preflight/remote_probe.py",
        "run_yolo_reviewed_b.py": Path(__file__),
    }


def offline_test_files():
    return {
        "tests/pdf_processing/q04/test_yolo_review_candidates.py": REPO
        / "tests/pdf_processing/q04/test_yolo_review_candidates.py",
        "tests/pdf_processing/q04/test_yolo_reviewed_window.py": REPO
        / "tests/pdf_processing/q04/test_yolo_reviewed_window.py",
        "tests/pdf_processing/q04/yolo_reviewed_offline_suite.py": REPO
        / "tests/pdf_processing/q04/yolo_reviewed_offline_suite.py",
        "tests/pdf_processing/q04/candidate/build_yolo_reviewed_manifest.py": REPO
        / "tests/pdf_processing/q04/candidate/build_yolo_reviewed_manifest.py",
    }


def source_hashes(sources=None):
    sources = staged_sources() if sources is None else sources
    return {name: _sha(path) for name, path in sources.items()}


def reviewed_source_hashes(sources=None, manifest_path=OFFLINE_MANIFEST):
    retained = json.loads(manifest_path.read_text())
    lifecycle.require(
        retained == build_offline_manifest(),
        "offline manifest differs from executable plan",
    )
    manifest = integration_manifest()
    lifecycle.require(retained.get("phase") == PHASE, "offline phase changed")
    lifecycle.require(retained.get("fixture") == "07", "offline fixture changed")
    lifecycle.require(retained.get("modes") == ["fresh", "restored", "replay"], "offline modes changed")
    lifecycle.require(retained.get("runtime_authorized") is False, "offline manifest embeds authorization")
    lifecycle.require(
        retained.get("integration_manifest_sha256") == _sha(INTEGRATION_MANIFEST),
        "integration manifest digest changed",
    )
    lifecycle.require(
        retained.get("authorization_scope_sha256") == authorization_scope_sha256(),
        "authorization scope digest changed",
    )
    lifecycle.require(
        retained.get("candidate_inputs_sha256")
        == _sha(LOCAL_BUNDLE / "inputs.json")
        == manifest["artifacts"]["candidate_inputs"],
        "candidate input bundle changed",
    )
    expected_candidate = {
        name: _sha(path)
        for name, path in lifecycle.candidate_staging_files().items()
    }
    lifecycle.require(
        retained.get("candidate_staging_files") == expected_candidate,
        "candidate staging files changed",
    )
    observed = source_hashes(sources)
    lifecycle.require(retained.get("staged_sources") == observed, "staged source changed")
    return observed


def require_reviewed_git_state(sources=None, manifest_path=OFFLINE_MANIFEST):
    sources = staged_sources() if sources is None else sources
    paths = [str(path.resolve().relative_to(REPO)) for path in sources.values()]
    paths.extend(
        str(path.resolve().relative_to(REPO))
        for path in lifecycle.candidate_staging_files().values()
    )
    paths.extend(
        [
            str(lifecycle.CANDIDATE_MANIFEST.resolve().relative_to(REPO)),
            str(manifest_path.resolve().relative_to(REPO)),
        ]
    )
    paths.extend(
        str(path.resolve().relative_to(REPO)) for path in offline_test_files().values()
    )
    paths = sorted(set(paths))
    subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", *paths],
        cwd=REPO,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for cached in (False, True):
        command = ["git", "diff", "--quiet"]
        if cached:
            command.append("--cached")
        command.extend(["HEAD", "--", *paths])
        lifecycle.require(
            subprocess.run(command, cwd=REPO, check=False).returncode == 0,
            "reviewed source or manifest has uncommitted changes",
        )
    return reviewed_source_hashes(sources, manifest_path)


def build_measurement_argv(
    expected_run_id,
    *,
    remote=REMOTE,
    capacity=CAPACITY,
    python=lifecycle.PYTHON,
):
    if not expected_run_id.startswith("q04-"):
        raise ValueError("initialized run identity is required")
    return [
        python,
        RUNNER_DIR + "/yolo_reviewed_window.py",
        "--bundle", remote + "/inputs",
        "--state", remote + "/state",
        "--capacity", capacity,
        "--name", PHASE,
        "--fixture", "07",
        "--modes", "fresh", "restored", "replay",
        "--expected-run-id", expected_run_id,
        "--expected-prefix", PREFIX,
        "--integration-manifest", RUNNER_DIR + "/integration-manifest.json",
        "--main-review", RUNNER_DIR + "/main-review.json",
        "--equivalence-bundle", RUNNER_DIR + "/equivalence-bundle.json",
        "--resource-bundle", RUNNER_DIR + "/resource-bundle.json",
        "--parser-budgets", RUNNER_DIR + "/parser-budgets.json",
        "--resource-analysis", RUNNER_DIR + "/resource-analysis.json",
        "--historical-methods", RUNNER_DIR + "/historical-methods.json",
        "--authorization-scope-sha256", authorization_scope_sha256(),
        "--attribution-interval-seconds", "0.25",
        "--attribution-gap-seconds", "1",
        "--capacity-approved",
    ]


def build_runtime_command(
    expected_run_id,
    *,
    remote=REMOTE,
    capacity=CAPACITY,
    python=lifecycle.PYTHON,
    timeout_program="timeout",
    driver_lock=DRIVER_LOCK,
):
    verify = (
        "import os;from pathlib import Path;from prepare import verify_bundle;"
        "verify_bundle(Path(os.environ['R'])/'inputs')"
    )
    inner = "\n".join(
        (
            f"{shlex.quote(python)} -c {shlex.quote(verify)}",
            "exec " + shlex.join(
                build_measurement_argv(
                    expected_run_id,
                    remote=remote,
                    capacity=capacity,
                    python=python,
                )
            ),
        )
    )
    return "\n".join(
        (
            "set -euC",
            "export R=" + shlex.quote(remote),
            "export PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 "
            "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4",
            'export PYTHONPATH="$R/runner-yolo-reviewed-b:$R/code/src:'
            '$R/code/tests/pdf_processing/q04:$R/code/tests/pdf_processing/q02:'
            '$R/code/tests/pdf_processing/q03"',
            "export PDF_QUALIFICATION_LOCK=" + shlex.quote(driver_lock),
            'cd "$R/code"',
            'test ! -e "$R/state/yolo-reviewed-b"',
            'test ! -e "$PDF_QUALIFICATION_LOCK"',
            shlex.quote(timeout_program)
            + " --signal=INT --kill-after=180s 825s sh -eu -c "
            + shlex.quote(inner)
            + ' > "$R/logs/yolo-reviewed-b.log" 2>&1',
            "",
        )
    )


def build_initialized_state_probe_program(*, root=REMOTE):
    return """import hashlib,json
from pathlib import Path
root=Path(ROOT)
config=json.loads((root/'state/config.json').read_text())
budget=json.loads((root/'budget-adoption.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'run_id':config['run_id'],'prefix':config['prefix'],
 'bundle':config['bundle'],'bundle_sha256':config['bundle_sha256'],
 'state_sha256':sha(root/'state/config.json'),'producer':config['producer'],
 'profile_method':config['profiles']['07']['method'],
 'profile_id':config['profiles']['07']['id'],
 'profile_release':config['profiles']['07']['release'],
 'config_keys':sorted(config),'profile_keys':sorted(config['profiles']),
 'queue_keys':sorted(config['queues']),'window_keys':sorted(config['window']),
 'parser_budgets':config['parser_budgets'],'budget_adoption':budget,
 'budget_adoption_sha256':sha(root/'budget-adoption.json')}))
""".replace("ROOT", repr(root))


def validate_initialized_state(initialized, bundle):
    extras = {key: initialized[key] for key in (
        "parser_budgets", "budget_adoption", "budget_adoption_sha256"
    )}
    core = {key: value for key, value in initialized.items() if key not in extras}
    lifecycle._yolo_reviewed_original_validate_initialized_state(
        core,
        bundle,
        remote_root=REMOTE,
        prefix=PREFIX,
        source_run_id=lifecycle.SOURCE_RUN_ID,
        bundle_sha256=lifecycle.EXPECTED_BUNDLE_SHA256,
    )
    lifecycle.require(extras["parser_budgets"] == CANDIDATE_BUDGETS,
                      "candidate parser budgets changed")
    record = extras["budget_adoption"]
    lifecycle.require(record.get("candidate") == "q04-yolo-reviewed-v1",
                      "budget candidate identity changed")
    lifecycle.require(record.get("before") == BASELINE_BUDGETS,
                      "baseline parser budgets changed")
    lifecycle.require(record.get("after") == CANDIDATE_BUDGETS,
                      "candidate parser budgets changed")
    lifecycle.require(
        record.get("parser_budgets_sha256")
        == integration_manifest()["artifacts"]["parser_budgets"],
        "parser budget file identity changed",
    )


def build_budget_adoption_program(*, root=REMOTE):
    return """import hashlib,json,os
from pathlib import Path
root=Path(ROOT)
path=root/'state/config.json'
config=json.loads(path.read_text())
before=config['parser_budgets']
expected=EXPECTED
if before!=expected:raise ValueError('baseline parser budgets changed')
budget_path=root/'runner-yolo-reviewed-b/parser-budgets.json'
raw=budget_path.read_bytes();after=json.loads(raw)
if after!=AFTER:raise ValueError('candidate parser budgets changed')
config['parser_budgets']=after
payload=(json.dumps(config,indent=2)+'\\n').encode()
temporary=path.with_suffix('.candidate')
temporary.open('xb').write(payload);os.replace(temporary,path)
record={'candidate':'q04-yolo-reviewed-v1','before':before,'after':after,
 'parser_budgets_sha256':hashlib.sha256(raw).hexdigest(),
 'final_config_sha256':hashlib.sha256(payload).hexdigest(),
 'production_default_changed':False,'fixture':'07'}
(root/'budget-adoption.json').open('x').write(json.dumps(record,indent=2)+'\\n')
print(json.dumps(record))
""".replace("ROOT", repr(str(root))).replace(
        "EXPECTED", repr(BASELINE_BUDGETS)
    ).replace("AFTER", repr(CANDIDATE_BUDGETS))


def run_live_init():
    command = " ".join(
        (
            "set -eu",
            "&& export PYTHONDONTWRITEBYTECODE=1 PYTHONSAFEPATH=1 "
            "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1",
            "&& export PDF_QUALIFICATION_LOCK="
            + shlex.quote(REMOTE + "/init.driver.lock"),
            "&& export PYTHONPATH="
            + shlex.quote(
                REMOTE
                + "/code/src:"
                + REMOTE
                + "/code/tests/pdf_processing/q04:"
                + REMOTE
                + "/code/tests/pdf_processing/q02:"
                + REMOTE
                + "/code/tests/pdf_processing/q03"
            ),
            "&& cd " + shlex.quote(REMOTE + "/code"),
            "&& timeout --signal=INT --kill-after=30s 180s "
            + shlex.quote(lifecycle.PYTHON),
            "tests/pdf_processing/q04/q04_runtime.py --phase init",
            "--bundle " + shlex.quote(REMOTE + "/inputs"),
            "--state " + shlex.quote(REMOTE + "/state"),
            "--capacity " + shlex.quote(CAPACITY),
            "--temporal temporal:7233 --endpoint http://objects:9000 --bucket t09a",
            "--prefix " + shlex.quote(PREFIX),
            "--model-cache " + shlex.quote(lifecycle.MODEL_CACHE),
            "--trial-seconds 180 --capacity-approved",
        )
    )
    output = lifecycle.k(
        lifecycle.NS,
        "exec",
        "coordinator",
        "--",
        "sh",
        "-c",
        command,
        timeout=210,
    )
    (OUT / "init.log").write_bytes(output)
    adoption = json.loads(lifecycle.remote(build_budget_adoption_program()))
    (OUT / "budget-adoption.json").write_text(
        json.dumps(adoption, indent=2, sort_keys=True) + "\n"
    )
    initialized = json.loads(
        lifecycle.remote(build_initialized_state_probe_program())
    )
    bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
    validate_initialized_state(initialized, bundle)
    (OUT / "state-init.json").write_text(
        json.dumps(initialized, indent=2, sort_keys=True) + "\n"
    )
    return initialized


def _validation_args():
    return SimpleNamespace(
        name=PHASE,
        expected_prefix=PREFIX,
        fixture="07",
        modes=["fresh", "restored", "replay"],
        integration_manifest=INTEGRATION_MANIFEST,
        main_review=MAIN_REVIEW,
        equivalence_bundle=REPO
        / "tests/pdf_processing/q04/candidate/yolo-equivalence-v1/BUNDLE.json",
        resource_bundle=REPO
        / "tests/pdf_processing/q04/candidate/yolo-resource-v1/BUNDLE.json",
        parser_budgets=REPO
        / "tests/pdf_processing/q04/candidate/yolo-resource-v1/PARSER-BUDGETS.json",
        resource_analysis=REPO
        / "tests/pdf_processing/q04/diagnosis/yolo-lifecycle-a/evidence/resource-peak.json",
        historical_methods=REPO
        / "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json",
        bundle=LOCAL_BUNDLE,
        authorization_scope_sha256=authorization_scope_sha256(),
    )


def build_offline_manifest():
    identity = {
        "phase": PHASE,
        "remote_root": REMOTE,
        "prefix": PREFIX,
        "local_output": str(OUT),
        "runner_dir": RUNNER_DIR,
        "driver_lock": DRIVER_LOCK,
    }
    run_id = "q04-offline-reviewed-candidate"
    manifest = integration_manifest()
    return {
        "schema_version": 1,
        "phase": PHASE,
        "fixture": "07",
        "modes": ["fresh", "restored", "replay"],
        "identity": identity,
        "candidate_inputs_sha256": _sha(LOCAL_BUNDLE / "inputs.json"),
        "integration_manifest_sha256": _sha(INTEGRATION_MANIFEST),
        "authorization_scope_sha256": authorization_scope_sha256(),
        "candidate_staging_files": {
            name: _sha(path)
            for name, path in lifecycle.candidate_staging_files().items()
        },
        "staged_sources": source_hashes(),
        "offline_test_files": {
            name: _sha(path) for name, path in offline_test_files().items()
        },
        "measurement_argv": build_measurement_argv(run_id),
        "runtime_command_sha256": hashlib.sha256(
            build_runtime_command(run_id).encode()
        ).hexdigest(),
        "parser_budgets": CANDIDATE_BUDGETS,
        "resource_gate": manifest["resource_gate"],
        "authorization_scope": manifest["authorization_scope"],
        "runtime_authorized": False,
        "production_default_changed": False,
        "historical_reference_mutated": False,
        "general_normalization": False,
    }


def offline_validation_record():
    retained = json.loads(OFFLINE_MANIFEST.read_text())
    lifecycle.require(retained == build_offline_manifest(),
                      "offline manifest differs from executable plan")
    reviewed_source_hashes()
    bundle = json.loads((LOCAL_BUNDLE / "inputs.json").read_text())
    config = {
        "parser_budgets": CANDIDATE_BUDGETS,
        "profiles": {"07": {"method": bundle["base_profile"]["method"]}},
    }
    validated = yolo_reviewed_window.validate_reviewed_inputs(
        _validation_args(), config, bundle
    )
    argv = build_measurement_argv("q04-offline-reviewed-candidate")
    command = build_runtime_command("q04-offline-reviewed-candidate")
    identity = {
        "phase": PHASE,
        "remote_root": REMOTE,
        "prefix": PREFIX,
        "local_output": str(OUT),
        "runner_dir": RUNNER_DIR,
        "driver_lock": DRIVER_LOCK,
    }
    lifecycle.require(retained["identity"] == identity, "offline identity changed")
    lifecycle.require(retained["measurement_argv"] == argv, "offline argv changed")
    return {
        "status": "PASS offline only",
        "identity": identity,
        "modes": ["fresh", "restored", "replay"],
        "parser_budgets": CANDIDATE_BUDGETS,
        "authorization_scope_sha256": authorization_scope_sha256(),
        "integration_artifacts": validated["artifact_sha256"],
        "runtime_command_sha256": hashlib.sha256(command.encode()).hexdigest(),
        "runtime_authorized": False,
    }


def configure_lifecycle():
    lifecycle.PHASE = PHASE
    lifecycle.REMOTE = REMOTE
    lifecycle.PREFIX = PREFIX
    lifecycle.OUT = OUT
    lifecycle.RUNNER_DIR = RUNNER_DIR
    lifecycle.CAPACITY = CAPACITY
    lifecycle.RESERVATION = RESERVATION
    lifecycle.RELEASE = RELEASE
    lifecycle.ADMISSION_EVIDENCE = ADMISSION_EVIDENCE
    lifecycle.ADMISSION_RESULT = ADMISSION_RESULT
    lifecycle.DRIVER_LOCK = DRIVER_LOCK
    lifecycle.LOCAL_BUNDLE = LOCAL_BUNDLE
    lifecycle.OFFLINE_MANIFEST = OFFLINE_MANIFEST
    lifecycle.STATE = {
        "phase": "preparing",
        "errors": [],
        "services_expected_closed": 32,
        "services_restored": False,
        "retry_count": 0,
        "fixture": "07",
        "modes": ["fresh", "restored", "replay"],
        "candidate": "q04-yolo-reviewed-v1",
        "parser_budgets": CANDIDATE_BUDGETS,
    }
    lifecycle.staged_sources = staged_sources
    lifecycle.reviewed_source_hashes = reviewed_source_hashes
    lifecycle.require_reviewed_git_state = require_reviewed_git_state
    lifecycle.build_staging_probe_program = lambda root=REMOTE: (
        lifecycle._yolo_reviewed_original_staging_probe(root=root)
    )
    lifecycle.build_measurement_argv = build_measurement_argv
    lifecycle.build_runtime_command = build_runtime_command
    lifecycle.build_initialized_state_probe_program = build_initialized_state_probe_program
    lifecycle.validate_initialized_state = validate_initialized_state
    lifecycle.run_live_init = run_live_init


if not hasattr(lifecycle, "_yolo_reviewed_original_staging_probe"):
    lifecycle._yolo_reviewed_original_staging_probe = lifecycle.build_staging_probe_program
if not hasattr(lifecycle, "_yolo_reviewed_original_validate_initialized_state"):
    lifecycle._yolo_reviewed_original_validate_initialized_state = (
        lifecycle.validate_initialized_state
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--owner")
    parser.add_argument("--approval-reference")
    parser.add_argument("--authorization-scope-sha256")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("runtime execution requires explicit --execute")
    if not args.owner or not args.approval_reference:
        parser.error("--owner and --approval-reference are required")
    if args.authorization_scope_sha256 != authorization_scope_sha256():
        parser.error("authorization scope does not match the reviewed single-run scope")
    configure_lifecycle()
    return lifecycle.main(
        [
            "--execute",
            "--owner",
            args.owner,
            "--approval-reference",
            args.approval_reference,
        ]
    )


if __name__ == "__main__":
    sys.exit(main())
