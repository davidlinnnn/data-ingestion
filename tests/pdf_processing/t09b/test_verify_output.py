import json
from pathlib import Path
import tempfile
import unittest

from verify_output import verify


class OutputTest(unittest.TestCase):
    def test_group_change_preserves_full_oracle_and_requires_business_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            actual, reference = (Path(directory) / name for name in ('actual', 'reference'))
            for root in (actual, reference):
                root.mkdir()
                for name, data in (('document.json', {'children': ['required OCR']}),
                                   ('checks.json', {'quality': True}),
                                   ('result.json', {'processing_complete': True})):
                    (root / name).write_text(json.dumps(data))
            for size, groups in ((5, [[1, 5], [6, 10], [11, 12]]),
                                  (10, [[1, 10], [11, 12]])):
                self.assertEqual(verify(actual, reference, 12, size, groups)['groups'],
                                 len(groups))
            with self.assertRaisesRegex(ValueError, 'coverage'):
                verify(actual, reference, 12, 10, [[1, 10]])
            (actual / 'document.json').write_text('{"children": []}')
            with self.assertRaisesRegex(ValueError, 'complete output mismatch'):
                verify(actual, reference, 12, 10, [[1, 10], [11, 12]])
            (actual / 'document.json').write_bytes((reference / 'document.json').read_bytes())
            (actual / 'result.json').write_text('{"processing_complete": false}')
            with self.assertRaisesRegex(ValueError, 'business completion'):
                verify(actual, reference, 12, 10, [[1, 10], [11, 12]])
