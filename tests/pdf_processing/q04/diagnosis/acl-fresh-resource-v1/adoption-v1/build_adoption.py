"""Build and verify the immutable fixture-09 Option A qualification bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[6]
HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent / "candidate-review"
ACTIVE = Path("/private/tmp/q04-inputs-local-v5")
CANDIDATE = Path("/private/tmp/q04-option-a-review-v5")
DEFAULT_OUTPUT = Path("/private/tmp/q04-inputs-option-a-v7")
DEFAULT_STATE_PLAN = Path("/private/tmp/q04-option-a-state-v2")

ACTIVE_INPUTS_SHA = "b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297"
ACTIVE_REFERENCE_SHA = "aaa62538d423472fd4999675fdcd39501eaa11bce89d630843c8609177533c6c"
ACTIVE_QUALITY_SHA = "f9494c36cc7d628a73658f14b0a6637e20540641b8815c7313f9cbc6120d0bb2"
CANDIDATE_REFERENCE_SHA = "ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506"
CANDIDATE_QUALITY_SHA = "62d80c5c4d24a939cc774d3d2f210592a160c718d2b0e2692b885addcd5afe96"
CANDIDATE_EVIDENCE_SHA = "91fff9d1dfd7ab28e25d7c627f58f43f0e12565fe7d4eafbacdb960c3e209f7c"
FIXTURE_SHA = "bd33fffb2c91f35225f5b89feb29a93013f4814558ac578bef000b632fd169bf"
DECISION_ID = "q04-fixture09-option-a-v1"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def adopted_payloads() -> tuple[bytes, bytes]:
    """Create decision-bound oracle/evidence without rewriting candidate history."""
    quality = json.loads((CANDIDATE / "candidate-quality-oracle.json").read_text())
    require(quality.pop("candidate_status") == "NOT_ACCEPTED", "candidate quality disposition drift")
    quality["version"] = 2
    quality["scope"] = "ADOPTED qualification oracle for fixed fixture 09 only; non-09 pages unchanged"
    quality["adoption_decision"] = DECISION_ID

    evidence = json.loads((CANDIDATE / "candidate-content-evidence-09.json").read_text())
    require(evidence.pop("candidate_status") == "NOT_ACCEPTED", "candidate evidence disposition drift")
    evidence.pop("candidate_scope")
    require(evidence.pop("canonical_accepted") is False, "historical runtime disposition drift")
    evidence["version"] = 2
    evidence["adoption_decision"] = DECISION_ID
    evidence["qualification_expectation"] = "ADOPTED_FIXED_FIXTURE_09"
    evidence["historical_runtime_canonical_accepted"] = False
    return (
        (json.dumps(quality, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        (json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )


def _load_candidate_verifier():
    spec = importlib.util.spec_from_file_location(
        "q04_option_a_candidate_verify", REVIEW / "verify_candidate.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _outside_repo(path: Path) -> None:
    resolved = path.resolve()
    require(
        resolved != ROOT and ROOT not in resolved.parents,
        "private bundle and state plan must remain outside the repository",
    )


def _copy_file(source: str, destination: str) -> str:
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o644)
    return destination


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    os.chmod(root, 0o555)


def build(output: Path, state_plan: Path) -> dict:
    _outside_repo(output)
    _outside_repo(state_plan)
    if output.exists() or state_plan.exists():
        raise FileExistsError("adopted output identities must be new")

    require(file_sha(ACTIVE / "inputs.json") == ACTIVE_INPUTS_SHA, "active bundle drift")
    require(file_sha(ACTIVE / "references/09.json") == ACTIVE_REFERENCE_SHA, "active reference drift")
    require(file_sha(ACTIVE / "oracles/quality-oracle.json") == ACTIVE_QUALITY_SHA, "active quality oracle drift")
    require(file_sha(CANDIDATE / "candidate-reference-09.json") == CANDIDATE_REFERENCE_SHA, "candidate reference drift")
    require(file_sha(CANDIDATE / "candidate-quality-oracle.json") == CANDIDATE_QUALITY_SHA, "candidate quality oracle drift")
    require(file_sha(CANDIDATE / "candidate-content-evidence-09.json") == CANDIDATE_EVIDENCE_SHA, "candidate content evidence drift")
    require(file_sha(ACTIVE / "fixtures/09.pdf") == FIXTURE_SHA, "fixed fixture bytes drift")

    verifier = _load_candidate_verifier()
    verified = verifier.verify(
        reference=json.loads((ACTIVE / "references/09.json").read_text()),
        active_quality=json.loads((ACTIVE / "oracles/quality-oracle.json").read_text()),
        candidate_raw=(CANDIDATE / "candidate-reference-09.json").read_bytes(),
        report_raw=(CANDIDATE / "candidate-content-evidence-09.json").read_bytes(),
        quality_raw=(CANDIDATE / "candidate-quality-oracle.json").read_bytes(),
        manifest=json.loads((CANDIDATE / "review-manifest.json").read_text()),
    )
    require(verified["status"] == "PASS_REVIEW_PACKAGE_ONLY", "candidate proof failed")
    require(verified["acceptance_status"] == "NOT_ACCEPTED", "historical candidate status changed")

    shutil.copytree(ACTIVE, output, copy_function=_copy_file)
    (output / "content-evidence").mkdir()
    shutil.copyfile(CANDIDATE / "candidate-reference-09.json", output / "references/09.json")
    adopted_quality, adopted_evidence = adopted_payloads()
    (output / "oracles/quality-oracle.json").write_bytes(adopted_quality)
    (output / "content-evidence/09.json").write_bytes(adopted_evidence)

    inventory = json.loads((ACTIVE / "inputs.json").read_text())
    inventory["version"] = 2
    inventory["reference_graphs"]["09"] = CANDIDATE_REFERENCE_SHA
    inventory["oracles"]["quality-oracle.json"] = sha(adopted_quality)
    runtime_path = ROOT / "tests/pdf_processing/q04/q04_runtime.py"
    inventory["test_files"]["tests/pdf_processing/q04/q04_runtime.py"] = file_sha(runtime_path)
    inventory["qualification_adoption"] = {
        "decision_id": DECISION_ID,
        "decision_record_sha256": file_sha(HERE / "SOURCE-REVIEW-DECISION.md"),
        "scope": "fixed fixture 09 only: one provenance-preserving text split and following reference renumber",
        "fixture_sha256": FIXTURE_SHA,
        "original_pages": [2, 3, 4],
        "quality_items_by_page": {"1": 40, "2": 69, "3": 21},
        "reference_09_sha256": CANDIDATE_REFERENCE_SHA,
        "quality_oracle_sha256": sha(adopted_quality),
        "content_evidence_09_sha256": sha(adopted_evidence),
        "candidate_quality_oracle_sha256": CANDIDATE_QUALITY_SHA,
        "candidate_content_evidence_09_sha256": CANDIDATE_EVIDENCE_SHA,
        "previous_bundle_inputs_sha256": ACTIVE_INPUTS_SHA,
        "previous_reference_09_sha256": ACTIVE_REFERENCE_SHA,
        "previous_quality_oracle_sha256": ACTIVE_QUALITY_SHA,
        "production_method_changed": False,
        "historical_candidate_status": "NOT_ACCEPTED",
    }
    (output / "inputs.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")

    # Runtime staging preserves every old harness file except q04_runtime.py,
    # whose current workflow-intent fix is explicitly rebound above.  Verify
    # the portable files here; the remote preflight verifies the mixed harness
    # tree before live init.
    for entry in inventory["fixtures"]:
        require(file_sha(output / "fixtures" / (entry["id"] + ".pdf")) == entry["sha256"], "bundle fixture drift")
        require(file_sha(output / "originals" / (entry["id"] + ".pdf")) == entry["original_sha256"], "bundle original drift")
    for sid, digest in inventory["reference_graphs"].items():
        require(file_sha(output / "references" / (sid + ".json")) == digest, "bundle reference drift")
    for name, digest in inventory["oracles"].items():
        require(file_sha(output / "oracles" / name) == digest, "bundle oracle drift")
    require(inventory["base_profile"] == json.loads((ACTIVE / "inputs.json").read_text())["base_profile"], "processing profile changed")
    require(inventory["producer"] == json.loads((ACTIVE / "inputs.json").read_text())["producer"], "producer changed")

    bundle_sha = file_sha(output / "inputs.json")
    state_plan.mkdir()
    plan = {
        "status": "PLANNED_NOT_INITIALIZED",
        "decision_id": DECISION_ID,
        "bundle": str(output),
        "bundle_inputs_sha256": bundle_sha,
        "run_id": None,
        "state_sha256": None,
        "phase": "acl-option-a-window-b",
        "remote_root": "/tmp/q04-option-a-20260918-b",
        "object_prefix": "q04/option-a-20260918-b/",
        "local_output": "/private/tmp/q04-acl-option-a-window-20260918-b",
        "reservation": "/tmp/q04-option-a-20260918-b/reservation-acl-option-a-window-b.json",
        "driver_lock": "/tmp/q04-option-a-20260918-b/acl-option-a-window-b.driver.lock",
        "live_init_required": True,
        "old_request_boundary": {
            "original_prefix": "q04/keynote-18be1b3-20260916-b/",
            "new_prefix_contains_old_registrations": False,
            "copy_registrations": False,
        },
    }
    (state_plan / "plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    _make_read_only(output)
    _make_read_only(state_plan)
    return plan


def verify(output: Path, state_plan: Path) -> dict:
    inventory = json.loads((output / "inputs.json").read_text())
    plan = json.loads((state_plan / "plan.json").read_text())
    adoption = inventory["qualification_adoption"]
    require(adoption["decision_id"] == DECISION_ID, "adoption decision changed")
    require(adoption["decision_record_sha256"] == file_sha(HERE / "SOURCE-REVIEW-DECISION.md"), "decision record binding drift")
    require(file_sha(output / "references/09.json") == CANDIDATE_REFERENCE_SHA, "adopted reference drift")
    require(file_sha(output / "oracles/quality-oracle.json") == adoption["quality_oracle_sha256"], "adopted quality oracle drift")
    require(file_sha(output / "content-evidence/09.json") == adoption["content_evidence_09_sha256"], "adopted content evidence drift")
    require(adoption["quality_oracle_sha256"] != CANDIDATE_QUALITY_SHA, "candidate quality artifact reused")
    require(adoption["content_evidence_09_sha256"] != CANDIDATE_EVIDENCE_SHA, "candidate content evidence reused")
    require(file_sha(output / "fixtures/09.pdf") == FIXTURE_SHA, "adopted fixture drift")
    require(plan["bundle_inputs_sha256"] == file_sha(output / "inputs.json"), "state plan bundle binding drift")
    require(plan["run_id"] is None and plan["state_sha256"] is None, "offline state plan was initialized")
    require(plan["old_request_boundary"]["copy_registrations"] is False, "old registrations may not be copied")
    return {"status": "PASS_OFFLINE_ADOPTION", "bundle_inputs_sha256": plan["bundle_inputs_sha256"], "decision_id": DECISION_ID}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--state-plan", type=Path, default=DEFAULT_STATE_PLAN)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    result = verify(args.output, args.state_plan) if args.verify_only else build(args.output, args.state_plan)
    print(json.dumps(result, indent=2, sort_keys=True))
