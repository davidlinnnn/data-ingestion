"""Fast offline driver contracts; no services, subprocesses or evidence rendering."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

from fixtures import document, SOURCE
from oracle.score import score
from pdf_processing.processing import encoded
from pdf_processing.object_store import digest
from pdf_processing.relationships import build, validate
from q03_fixtures import profile

# Several qualification directories have runtime.py; never depend on import order.
_spec = importlib.util.spec_from_file_location('q03_runtime_under_test', Path(__file__).with_name('runtime.py'))
assert _spec is not None and _spec.loader is not None
runtime = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = runtime
_spec.loader.exec_module(runtime)


class RuntimeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = document()
        cls.request = {'version': 3, 'source_revision': 'offline-test', 'artifact': {'sha256': SOURCE}}

    def files(self):
        return {'source.pdf': b'offline source placeholder', 'page-9.png': b'offline page placeholder',
                'content-evidence.json': encoded({'source': self.request,
                    'document_sha256': digest(encoded(self.doc)),
                    'pages': {'9': {'physical_page': 9, 'artifact': 'page-9.png',
                                    'sha256': digest(b'offline page placeholder')}}})}

    def test_matrix_has_21_unique_cases_and_seven_independent_gates(self):
        cases = list(runtime.scenarios())
        self.assertEqual(len(cases), 21)
        self.assertEqual(len({name for name, _ in cases}), 21)
        self.assertEqual([gate for _, gate in cases if gate is not None], [
            (2, 'header_body', 0), (2, 'header_body', 1), (2, 'symbol', 0),
            (3, 'header_body', 0), (3, 'caption', 0), (3, 'caption', 1), (3, 'symbol', 0)])

    def test_each_gate_rejects_structure_that_still_passes_all_four_oracles(self):
        for name, gate in runtime.scenarios():
            if gate is None:
                continue
            with self.subTest(case=name):
                prof = profile()
                ri, stream, index = gate
                review = prof['content_evidence']['relationships']['representation']['reviews'][ri]
                observation = review['isolated_symbols'][index] if stream == 'symbol' else review['streams'][stream]['differences'][index]
                observation['disposition'] = 'release_gate'
                policy = prof['content_evidence']['relationships']
                report = build(self.doc, self.request, 'parsed', 'assembly', policy)
                self.check_scores(report)
                with self.assertRaisesRegex(ValueError, 'representation_release_gate'):
                    validate(report, self.doc, self.request, 'parsed', 'assembly', policy)
        self.assertNotIn('release_gate', json.dumps(profile()))

    def check_scores(self, report):
        candidate = copy.deepcopy(report['candidates'])
        candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in report['resolved']]
        scores = score(self.doc, candidate)
        self.assertEqual([s['page'] for s in scores], [3, 5, 9, 10])
        self.assertEqual([s['structure_pass'] for s in scores], [True]*4)

    def test_valid_and_fragmented_reports_pass_all_four_oracles(self):
        original = copy.deepcopy(self.doc)
        for case in ('valid', 'split'):
            with self.subTest(case=case):
                files = self.files()
                runtime.inject(files, case, self.doc, self.request, profile())
                report = json.loads(files['relationships.json'])
                validate(report, self.doc, self.request, 'parsed', 'assembly', profile()['content_evidence']['relationships'])
                self.check_scores(report)
        self.assertEqual(self.doc, original)

    def test_injected_structure_and_representation_negatives_are_rejected(self):
        for case in ('missing_body', 'missing_recursive_body', 'missing_caption',
                     'wrong_raw_offset', 'fabricated_symbol_position', 'wrong_review'):
            with self.subTest(case=case):
                files = self.files()
                runtime.inject(files, case, self.doc, self.request, profile())
                with self.assertRaises(ValueError):
                    validate(json.loads(files['relationships.json']), self.doc, self.request,
                             'parsed', 'assembly', profile()['content_evidence']['relationships'])

    def test_attribution_injections_preserve_request_and_target_one_fault(self):
        original = copy.deepcopy(self.request)
        for case in ('wrong_page', 'wrong_source', 'wrong_document', 'corrupt_page', 'missing_source', 'missing_page'):
            with self.subTest(case=case):
                files = self.files()
                runtime.inject(files, case, self.doc, self.request, profile())
                content = json.loads(files['content-evidence.json'])
                page = content['pages']['9']
                if case == 'wrong_page': self.assertNotEqual(page['physical_page'], 9)
                elif case == 'wrong_source': self.assertNotEqual(content['source'], self.request)
                elif case == 'wrong_document': self.assertNotEqual(content['document_sha256'], digest(encoded(self.doc)))
                elif case == 'missing_source': self.assertNotIn('source.pdf', files)
                elif case == 'missing_page': self.assertNotIn(page['artifact'], files)
                elif case == 'corrupt_page':
                    self.assertEqual(page['sha256'], digest(files[page['artifact']]))
                    self.assertFalse(files[page['artifact']].startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertEqual(self.request, original)

    def test_complete_registration_on_later_page_is_not_missed(self):
        store = Mock()
        store.prefix = 'offline/'
        store.bucket = 'offline'
        store.client.get_paginator.return_value.paginate.return_value = [
            {'Contents': [{'Key': 'first'}]}, {'Contents': [{'Key': 'second'}]}]
        store.get.side_effect = [encoded({'operation': 'pdf-evidence-v1:abc'}),
                                 encoded({'operation': 'pdf-complete-v1:def'})]
        with self.assertRaises(AssertionError):
            runtime.absent_complete(store)
        self.assertEqual(store.get.call_count, 2)


if __name__ == '__main__':
    unittest.main()
