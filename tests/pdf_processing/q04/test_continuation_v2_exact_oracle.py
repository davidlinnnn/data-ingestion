"""The source-reviewed v2 oracle rejects collateral graph changes."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

Q04 = Path(__file__).resolve().parent
sys.path.insert(0, str(Q04))
from consumer import source_signature
spec = importlib.util.spec_from_file_location(
    'exact_oracle', Q04 / 'diagnosis/continuation-v2/exact_oracle.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


class ExactV2Oracle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = Path(os.environ.get('Q04_V2_EVIDENCE', '/private/tmp/q04-local-native-v2'))
        cls.inputs = Path(os.environ.get('Q04_V2_INPUTS', '/private/tmp/q04-inputs-warm-lifecycle-ag-final'))
        if not (cls.evidence / 'capture-full-51/document.json').exists():
            raise unittest.SkipTest('retained local v2 captures unavailable')
        cls.manifest = json.loads((Q04 / 'diagnosis/continuation-v2/EXACT-ORACLE.json').read_text())
        cls.method = json.loads((cls.evidence / 'expected-v2.json').read_text())
        cls.documents = {
            sid: json.loads((cls.evidence / folder / 'document.json').read_text())
            for sid, folder in (('native', 'capture-full-51'), ('06', 'capture-wiki-28'))
        }
        cls.sources = {sid: (cls.inputs / 'originals' / (sid + '.pdf')).read_bytes()
                       for sid in cls.documents}
        cls.references = {sid: (cls.inputs / 'references' / (sid + '.json')).read_bytes()
                          for sid in cls.documents}

    def check(self, sid, document, source=None, reference=None, method=None):
        return oracle.check(sid, document, self.sources[sid] if source is None else source,
                            self.references[sid] if reference is None else reference,
                            self.method if method is None else method,
                            self.manifest)

    def test_exact_local_captures_and_restores_pass(self):
        for sid, folder in (('native', 'restore-full-51'), ('06', 'restore-wiki-28')):
            with self.subTest(sid=sid):
                self.assertEqual(self.check(sid, self.documents[sid]),
                                 self.manifest['fixtures'][sid]['exact_graph_sha256'])
                restored = json.loads((self.evidence / folder / 'document.json').read_text())
                self.assertEqual(self.check(sid, restored), self.check(sid, self.documents[sid]))

    def test_graph_mutations_fail_closed(self):
        sid = 'native'
        original = self.documents[sid]

        def altered(change):
            document = copy.deepcopy(original)
            change(document)
            with self.assertRaisesRegex(ValueError, 'unreviewed exact v2 graph delta'):
                self.check(sid, document)

        altered(lambda d: d['texts'][0].__setitem__('text', d['texts'][0]['text'] + '!'))
        altered(lambda d: d['texts'][0]['prov'][0]['bbox'].__setitem__(
            'l', d['texts'][0]['prov'][0]['bbox']['l'] + 1))
        altered(lambda d: d['texts'][0]['parent'].__setitem__('$ref', '#/groups/0'))
        altered(lambda d: d['body']['children'].__setitem__(slice(0, 2),
            list(reversed(d['body']['children'][:2]))))
        altered(lambda d: d['pictures'][0].__setitem__('captions', []))
        altered(lambda d: d['tables'][0]['data']['table_cells'][0].__setitem__(
            'text', d['tables'][0]['data']['table_cells'][0]['text'] + '!'))

        def extra_source_preserving_split(d):
            node = next(x for x in d['texts'] if x['self_ref'] == '#/texts/20')
            first, second = node['prov']
            cut = first['charspan'][1]
            new = copy.deepcopy(node)
            new['self_ref'] = '#/texts/extra'
            new['text'], new['orig'] = node['text'][cut + 1:], node['orig'][cut + 1:]
            new['prov'] = [copy.deepcopy(second)]
            new['prov'][0]['charspan'] = [0, len(new['text'])]
            node['text'], node['orig'], node['prov'] = node['text'][:cut], node['orig'][:cut], [first]
            index = next(i for i, ref in enumerate(d['body']['children'])
                         if ref['$ref'] == node['self_ref'])
            d['body']['children'].insert(index + 1, {'$ref': new['self_ref']})
            d['texts'].insert(d['texts'].index(node) + 1, new)

        split = copy.deepcopy(original)
        extra_source_preserving_split(split)
        self.assertEqual(source_signature(split), source_signature(original))
        with self.assertRaisesRegex(ValueError, 'unreviewed exact v2 graph delta'):
            self.check(sid, split)

    def test_input_and_method_mutations_fail_closed(self):
        sid = '06'
        with self.assertRaisesRegex(ValueError, 'input or method changed'):
            self.check(sid, self.documents[sid], source=self.sources[sid] + b'!')
        with self.assertRaisesRegex(ValueError, 'input or method changed'):
            self.check(sid, self.documents[sid], reference=self.references[sid] + b'!')
        method = copy.deepcopy(self.method)
        method['continuation']['version'] = 'column-edge-continuation-v1'
        with self.assertRaisesRegex(ValueError, 'input or method changed'):
            self.check(sid, self.documents[sid], method=method)


if __name__ == '__main__':
    unittest.main()
