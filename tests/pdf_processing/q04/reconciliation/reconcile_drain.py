"""Project R3 drain evidence across the Q04 stage-impact boundary."""

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def display_path(path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def build_report(audit, *, evidence_paths):
    direct = audit["direct_stage_dependency_changes"]["r3_to_integrated"]
    changed = sorted(stage for stage, value in direct.items() if value)
    return {
        "schema_version": 1,
        "stage_impact": {
            "source": "tests/pdf_processing/q04/evidence/static-audit-v2.json",
            "r3_to_integrated_direct_changes": direct,
            "changed_stages": changed,
            "all_delivery_stages_affected": set(changed) == {
                "assembly", "evidence", "finalize", "group", "ocr", "selection"
            },
        },
        "r3_evidence": {
            "status": "supporting_method_and_topology_only",
            "reusable": [
                "five-page retention and unfinished-group retry oracle",
                "exact Pod UID delete precondition and replacement UID observation",
                "old CRI container and emptyDir absence checks",
                "old/new cgroup stream and continuous VM telemetry method",
                "owned cleanup and final-equality assertion pattern",
            ],
            "not_reusable_as_q04_pass": [
                "R3 group/assembly registrations or outputs",
                "R3 selection/OCR/evidence/finalize results",
                "R3 attempt counts or final equality under the integrated producer",
                "R3 resource measurements as an integrated bound",
            ],
            "evidence": {
                name: {"path": display_path(path), "sha256": digest(path)}
                for name, path in evidence_paths.items()
            },
        },
        "process_mode": {
            "status": "unproven",
            "claim_if_passed": "actual Temporal/shared-store worker-process recovery only",
            "pod_loss_claim": False,
            "role": "optional preflight; does not close the Pod recovery gate",
        },
        "pod_mode": {
            "status": "unqualified",
            "minimum_q04_requalification": (
                "one new owned native-fixture drain using the integrated producer, actual Temporal/shared storage, "
                "and actual Pod replacement after the documented topology is reviewed"
            ),
            "required_observations": [
                "five pages committed before exact-UID deletion",
                "first group retained; pages 6-10 alone retry on replacement",
                "old API UID absent and replacement UID distinct",
                "old CRI container stopped and old emptyDir absent",
                "VM telemetry across replacement and separate old/new cgroup streams",
                "complete checked graph equals the Q04 fresh baseline",
                "zero forbidden publication and complete owned cleanup on failure",
            ],
        },
        "decision": {
            "issue_51_gate_remains_open": True,
            "pod_gate_reassigned_to_issue_46": False,
            "deployment_creation_authorized": False,
            "runtime_authorized": False,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--controller", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        json.loads(args.audit.read_text()),
        evidence_paths={"r3_controller": args.controller, "r3_matrix": args.matrix, "integration_review": args.integration},
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
