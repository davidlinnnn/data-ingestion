"""Checked operation contracts: evidence policy/helper changes vs parsing changes."""
import copy
import tempfile
import unittest
from pdf_processing.compatibility import dependencies
from pdf_processing.processing import Processing
from test_publication import MemoryS3, profile
from pdf_processing.object_store import Store

class Compatibility(unittest.TestCase):
    def test_evidence_change_reuses_only_equal_operation_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = profile()
            prof['method'].update(format='PROTOTYPE-page-v1', option_types={}, model_artifacts={})
            processing = Processing(Store(MemoryS3(), 'test', 'q02'), tmp, tmp, prof)
            plan = {'request': {'artifact': {'sha256': 'a'*64}, 'source_revision': 'fixed'},
                    'profile': prof, 'producer': processing.producer, 'groups': [[1, 2]]}
            changed = copy.deepcopy(plan)
            changed['profile']['content_evidence']['relationships']['unresolved'] = 'allow_unknown'
            changed['producer']['relationship_method.py'] = 'changed-method'
            for operation in [{'kind': 'group', 'start': 1, 'end': 2},
                              {'kind': 'assembly', 'start': 1, 'end': 2, 'groups': ['fixed']}]:
                self.assertEqual(processing.operation_contract(plan, operation), processing.operation_contract(changed, operation))
            for stage in ('evidence', 'finalize'):
                self.assertNotEqual(dependencies(stage, prof, plan['producer']), dependencies(stage, changed['profile'], changed['producer']))
            changed['producer']['parse.py'] = 'changed-parser'
            self.assertNotEqual(processing.operation_contract(plan, {'kind': 'group'}), processing.operation_contract(changed, {'kind': 'group'}))
            changed = copy.deepcopy(plan)
            changed['producer']['compatibility.py'] = 'changed-contract'
            self.assertNotEqual(processing.operation_contract(plan, {'kind': 'group'}), processing.operation_contract(changed, {'kind': 'group'}))

    def test_old_evidence_policy_and_unsupported_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = profile()
            prof['content_evidence'] = {'version': 'typed-source-evidence-v1', 'reviews': {}}
            Processing(Store(MemoryS3(), 'test', 'q02'), tmp, tmp, prof)
            prof = profile()
            prof['content_evidence']['relationships']['method'] = 'unknown-required-method'
            with self.assertRaisesRegex(ValueError, 'unsupported_relationship_method'):
                Processing(Store(MemoryS3(), 'test', 'q02'), tmp, tmp, prof)
