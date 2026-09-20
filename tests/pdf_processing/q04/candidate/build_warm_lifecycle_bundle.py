"""Build the post-repair Q04 bundle while preserving the frozen payload."""

from __future__ import annotations

from build_yolo_lifecycle_bundle import build, main as _main
import build_yolo_lifecycle_bundle as base


base.CANDIDATE_VERSION = "q04-warm-lifecycle-q"
base.EXPECTED_CHANGED_PRODUCER_FILES = {
    "compatibility.py",
    "execution.py",
    "parse.py",
    "supervision.py",
    "warm_child.py",
}
base.REQUIRED_CANDIDATE_HARNESS_FILES |= {
    "tests/pdf_processing/q03/reviewed-representation.json",
    "tests/pdf_processing/t09a/evidence/code-source-oracle.json",
    "tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json",
    "tests/pdf_processing/q04/candidate/aima_image_supplement.py",
    "tests/pdf_processing/q04/candidate/aima_pod_window_q.py",
    "tests/pdf_processing/q04/candidate/yolo-equivalence-v1/BUNDLE.json",
    "tests/pdf_processing/q04/candidate/yolo_equivalence_candidate.py",
    "tests/pdf_processing/q04/candidate/yolo_resource_candidate.py",
    "tests/pdf_processing/q04/candidate/yolo_reviewed_window.py",
    "tests/pdf_processing/q04/sentinel/aima_attribution_telemetry_q.py",
    "tests/pdf_processing/q04/test_aima_attribution_q.py",
    "tests/pdf_processing/q04/test_warm_continuity.py",
    "tests/pdf_processing/q04/test_pod_q.py",
}


if __name__ == "__main__":
    _main()
