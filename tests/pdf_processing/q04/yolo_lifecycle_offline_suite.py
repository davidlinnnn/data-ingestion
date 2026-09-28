"""Single offline gate for the YOLO lifecycle executable window."""

import sys
import unittest


TEST_MODULES = (
    "tests.pdf_processing.q04.test_yolo_lifecycle_runner",
    "tests.pdf_processing.q04.test_yolo_lifecycle_candidate",
    "tests.pdf_processing.q04.test_yolo_candidate_harness",
    "tests.pdf_processing.q04.test_yolo_candidate_bundle",
    "tests.pdf_processing.q04.test_yolo_attribution_telemetry",
    "tests.pdf_processing.q04.test_yolo_overlap_analysis",
    "tests.pdf_processing.q04.test_acceptance_matrix",
    "tests.pdf_processing.q04.test_candidate_batch_runner",
    "tests.pdf_processing.t05.test_supervision",
)


def build_suite():
    return unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)


def main():
    result = unittest.TextTestRunner(verbosity=1).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
