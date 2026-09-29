"""Exercise the supervisor's actual safe-path environment in fresh interpreters."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class SafePathTest(unittest.TestCase):
    def test_entry_points_import_with_supervisor_environment(self):
        here = Path(__file__).resolve().parent
        root = here.parents[2]
        env = dict(os.environ, PYTHONSAFEPATH='1', PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=os.pathsep.join(str(root / path) for path in (
                       'src', 'tests/pdf_processing/q04', 'tests/pdf_processing/q02',
                       'tests/pdf_processing/q03')))
        for name in ('worker.py', 'baseline_window.py', 'pod_workload.py', 'pod_preflight.py',
                     'pod_workload_a7.py', 'pod_preflight_a7.py',
                     'pod_workload_a8.py', 'pod_preflight_a8.py',
                     'pod_workload_a9.py', 'pod_preflight_a9.py',
                     'pod_workload_a10.py', 'pod_preflight_a10.py'):
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, '-B', str(here / name), '--help'],
                                        env=env, cwd='/', capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)
