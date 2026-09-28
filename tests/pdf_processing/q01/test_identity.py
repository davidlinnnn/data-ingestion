"""The declared method and stage dependency contract are public retry boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from pdf_processing.compatibility import dependencies, methods_match
from pdf_processing.continuation import METHOD
from pdf_processing.execution import ChildFailure
from pdf_processing.parse import ParseRequest, execute

ROOT = Path(__file__).resolve().parents[3]


class Identity(unittest.TestCase):
    def test_correction_changes_parse_and_assembly_dependencies(self):
        profile = json.loads((ROOT/'deploy/pdf-processing/profiles/native-v1.json').read_text())
        producer = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (ROOT/'src/pdf_processing').glob('*.py')}
        changed = {**producer, 'continuation.py': 'different-implementation'}
        for stage in ('group', 'assembly'):
            self.assertNotEqual(dependencies(stage, profile, producer),
                                dependencies(stage, profile, changed))
        for stage in ('selection', 'ocr', 'evidence', 'finalize'):
            self.assertEqual(dependencies(stage, profile, producer),
                             dependencies(stage, profile, changed))
        corrected = copy.deepcopy(profile['method'])
        corrected['continuation'] = {'version': METHOD, 'sha256': producer['continuation.py']}
        self.assertFalse(methods_match(profile['method'], corrected, scoped=True))

    def test_unsupported_correction_fails_before_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for selection in ({'version': 'unknown', 'sha256': 'unknown'},
                              {'version': METHOD, 'sha256': 'wrong-bytes'}):
                request = ParseRequest(mode='restore', pdf=Path(tmp)/'missing.pdf',
                    out=Path(tmp)/'out', model_cache=Path(tmp), checkpoint=Path(tmp),
                    expected_method={'continuation': selection})
                with self.assertRaises(ChildFailure) as caught:
                    execute(request)
                self.assertEqual(caught.exception.code, 'unsupported_continuation_method')
                self.assertFalse(request.out.exists())
