"""Single local-only gate for the reviewed fixture-07 candidate window."""

import sys
import unittest

from tests.pdf_processing.q04.yolo_lifecycle_offline_suite import build_suite as build_lifecycle_suite


NEW_MODULES = (
    "tests.pdf_processing.q04.test_yolo_review_candidates",
    "tests.pdf_processing.q04.test_yolo_reviewed_window",
)


def build_suite():
    suite = unittest.TestSuite()
    suite.addTests(build_lifecycle_suite())
    suite.addTests(unittest.defaultTestLoader.loadTestsFromNames(NEW_MODULES))
    return suite


def main():
    result = unittest.TextTestRunner(verbosity=1).run(build_suite())
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
