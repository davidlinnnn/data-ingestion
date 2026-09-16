"""Corrected Q01 checkpoint assembly through Q03's four-case delivery contract."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests/pdf_processing/q01'))
from assemble import assemble
from oracle.score import score
from q03_fixtures import policy
from fixtures import SOURCE
from pdf_processing.relationships import build, validate

class Q03Combined(unittest.TestCase):
    def test_corrected_continuation_and_all_four_algorithms_share_one_output(self):
        doc, _ = assemble(True)
        source = {'artifact': {'sha256': SOURCE}}
        report = build(doc, source, 'q03-corrected-parsed', 'q03-corrected-assembly', policy())
        validate(report, doc, source, 'q03-corrected-parsed', 'q03-corrected-assembly', policy())
        candidate = copy.deepcopy(report['candidates'])
        candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in report['resolved']]
        self.assertEqual([r['structure_pass'] for r in score(doc, candidate)], [True]*4)
        spec = importlib.util.spec_from_file_location('q01_runtime', ROOT/'tests/pdf_processing/q01/runtime.py')
        assert spec is not None and spec.loader is not None
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        runtime.verify_continuation(doc)

    def test_full_request_driver_checks_all_four_and_versions_evidence_variant(self):
        spec = importlib.util.spec_from_file_location('joint_runtime', ROOT/'tests/pdf_processing/q01_q02/runtime.py')
        assert spec is not None and spec.loader is not None
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        selected = runtime.qualification_policy('q03')
        variant = runtime.qualification_policy('q03', True)
        self.assertEqual(selected, policy())
        self.assertNotEqual(selected, variant)
        self.assertEqual(variant['unresolved'], 'reject')
        doc, _ = assemble(True)
        source = {'artifact': {'sha256': SOURCE}}
        report = build(doc, source, 'parsed', 'assembly', selected)
        runtime.verify_delivery(doc, report, source, 'parsed', 'assembly', selected, expected_count=4)
        report['resolved'].pop()
        with self.assertRaises((AssertionError, ValueError)):
            runtime.verify_delivery(doc, report, source, 'parsed', 'assembly', selected, expected_count=4)
