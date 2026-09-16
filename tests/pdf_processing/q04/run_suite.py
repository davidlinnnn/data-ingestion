"""Combined local PDF/Q04 regressions. Does not import or start runtime drivers as CLIs."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
suite = unittest.TestSuite()
for name in ('', 't04', 't05', 'q01', 'q02', 'q01_q02', 'q03', 'q04'):
    sys.path.insert(0, str(ROOT/'tests/pdf_processing'/name))
    suite.addTests(unittest.TestLoader().discover(str(ROOT/'tests/pdf_processing'/name)))
if 'PDF_TEST_FIXTURE_ROOT' in os.environ:
    setattr(sys.modules['test_restoration'], 'FIXED', Path(os.environ['PDF_TEST_FIXTURE_ROOT']))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
