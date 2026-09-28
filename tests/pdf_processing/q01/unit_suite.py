"""Run all package unittest suites; service acceptance drivers are separate."""
import os,sys,unittest
from pathlib import Path
root=Path(__file__).resolve().parents[3]
suite=unittest.TestSuite()
for directory in ('tests/pdf_processing','tests/pdf_processing/t04','tests/pdf_processing/t05','tests/pdf_processing/q01'):
 suite.addTests(unittest.TestLoader().discover(str(root/directory)))
if 'PDF_TEST_FIXTURE_ROOT' in os.environ:
 sys.modules['test_restoration'].FIXED=Path(os.environ['PDF_TEST_FIXTURE_ROOT'])
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
