"""Executable identity contract, not a claim of cluster runtime reuse."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from temporalio.exceptions import ApplicationError
from pdf_processing.compatibility import dependencies
from pdf_processing.processing import Processing
from pdf_processing.object_store import Store, digest
from test_publication import MemoryS3, seed, profile as legacy_profile
from q03_fixtures import profile, ROOT
from delivery import REQUEST, serialized_document

class Q03Compatibility(unittest.TestCase):
    def test_actual_baseline_to_q03_dependency_impact(self):
        baseline = json.loads((ROOT.parent/'q01_q02/evidence/runtime-20260916/summary.json').read_text())['cases'][0]['producer']
        current = {p.name: digest(p.read_bytes()) for p in (ROOT.parents[2]/'src/pdf_processing').glob('*.py')}
        prof = profile()
        prof['method'].update(format='PROTOTYPE-page-v1', option_types={})
        before = copy.deepcopy(prof)
        before['content_evidence'] = legacy_profile()['content_evidence']
        for stage in ('group', 'assembly'):
            self.assertEqual(dependencies(stage, before, baseline), dependencies(stage, prof, current))
        for stage in ('selection', 'ocr', 'evidence', 'finalize'):
            self.assertNotEqual(dependencies(stage, before, baseline), dependencies(stage, prof, current))
        changed = copy.deepcopy(prof)
        changed['content_evidence']['relationships']['representation']['reviews'][2]['isolated_symbols'][0]['disposition'] = 'release_gate'
        for stage in ('group', 'assembly', 'selection', 'ocr'):
            self.assertEqual(dependencies(stage, prof, current), dependencies(stage, changed, current))
        for stage in ('evidence', 'finalize'):
            self.assertNotEqual(dependencies(stage, prof, current), dependencies(stage, changed, current))

    def test_old_accepted_plan_cannot_be_reinterpreted_by_new_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(MemoryS3(), 'test', 'q03-compatibility')
            old = Processing(store, tmp, tmp, legacy_profile())
            seed(old, serialized_document(), REQUEST)
            current = Processing(store, tmp, tmp, profile())
            with self.assertRaises(ApplicationError): current.load_plan('plan')
            self.assertEqual(old.load_plan('plan')['profile'], legacy_profile())

    def test_legacy_policy_keeps_symbol_cases_unresolved(self):
        from pdf_processing.relationships import build
        from fixtures import document
        policy = profile()['content_evidence']['relationships']
        del policy['representation']
        report = build(document(), REQUEST, 'parsed', 'assembly', policy)
        self.assertEqual(len(report['resolved']), 2)
        self.assertEqual([r['reason'] for r in report['unresolved']], ['symbol_disposition_not_supported']*2)
