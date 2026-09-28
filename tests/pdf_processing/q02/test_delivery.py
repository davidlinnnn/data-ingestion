"""Consumer completion seam; fixture expectations are not production rules."""
import unittest
from pdf_processing.relationships import validate_policy

class ProfileContract(unittest.TestCase):
    def test_required_coverage_cannot_be_inferred_from_discovery(self):
        with self.assertRaisesRegex(ValueError, 'coverage'):
            validate_policy({'method': 'local-function-block-v1', 'coverage': {'mode': 'all'},
                             'unresolved': 'reject'})

class RelationshipReplay(unittest.TestCase):
    def test_baseline_delivers_required_bfs_and_uniform_cost(self):
        from fixtures import document, policy, SOURCE
        from pdf_processing.relationships import build
        report = build(document(), {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        self.assertEqual(len(report['resolved']), 2)
        self.assertEqual(report['unresolved'], [])
        self.assertGreater(report['resolved'][1]['members'][0]['range'][0], 0)

    def test_discovery_supports_a_header_split_across_items(self):
        import copy
        from fixtures import document, policy, SOURCE
        from pdf_processing.relationships import build
        doc = document()
        report = build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        header = report['resolved'][0]['members'][0]
        item = next(i for i in doc['texts'] if i['self_ref'] == header['ref'])
        index = doc['texts'].index(item)
        middle = len(item['text'])//2
        replacements = []
        for n, text in enumerate((item['text'][:middle], item['text'][middle:])):
            part = copy.deepcopy(item)
            part.update(self_ref=f'#/texts/split-{n}', text=text)
            part['prov'][0]['charspan'] = [0, len(text)]
            replacements.append(part)
        doc['texts'][index:index+1] = replacements
        result = build(doc, {'artifact': {'sha256': SOURCE}}, 'parsed', 'assembly', policy())
        self.assertEqual(len(result['resolved']), 2)
        self.assertEqual([m['role'] for m in result['resolved'][0]['members'][:2]], ['header', 'header'])
