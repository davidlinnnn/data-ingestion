"""P2 role/order/source-content oracle at the retained checkpoint seam."""
import copy
import unittest
from fixtures import document, policy, mutate, FAILURES, SOURCE
from pdf_processing.relationships import build
from oracle.score import score

class IndependentOracle(unittest.TestCase):
    def test_source_reviewed_bfs_and_uniform_cost_and_negative_mutations(self):
        doc = document()
        report = build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        def checked(value, document=doc):
            candidate = copy.deepcopy(value['candidates'])
            candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in value['resolved']]
            return [r['structure_pass'] for r in score(document, candidate)][:2]
        self.assertEqual(checked(report), [True, True])
        self.assertEqual(checked(mutate(report, 'split', doc)), [True, True])
        for case in ['body_as_header', 'missing_role', 'missing_body', 'missing_result', 'short_header',
                     'wide_header', 'truncated_caption', 'float_order', 'bool_order', 'duplicate_order',
                     'contradictory_order', 'reordered', 'duplicate_member']:
            with self.subTest(case=case):
                try:
                    verdict = all(checked(mutate(report, case, doc)))
                except AssertionError:
                    verdict = False
                self.assertFalse(verdict)

    def test_caption_corruption_cannot_pass_independent_source_review(self):
        doc = document()
        report = build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        ref = report['resolved'][0]['members'][-1]['ref']
        item = next(i for i in doc['texts'] if i['self_ref'] == ref)
        item['text'] = item['text'].replace('search', 'WRONG!')
        item['prov'][0]['charspan'][1] = len(item['text'])
        value = build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        self.assertFalse(score(doc, value['candidates'])[0]['structure_pass'])
