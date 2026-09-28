"""Replay the actual N failure and reject collateral graph/image changes."""
import base64
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from analyze_graph_delta import compare, REFERENCE_SHA, sha
from consumer import check_reference

BUNDLE = Path('/private/tmp/q04-inputs-yolo-lifecycle-v1')
DOCUMENT = Path('/private/tmp/q04-aima-pod-cgroup-20260920-n/failure-evidence/state/aima-pod-cgroup-n/fresh-08/document.json')


class ImageAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (BUNDLE/'references/08.json').read_bytes()
        assert sha(raw) == REFERENCE_SHA
        cls.reference = json.loads(raw)
        cls.document = json.loads(DOCUMENT.read_text())

    def test_original_consumer_stays_red_and_complete_supplement_is_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'unreviewed full graph delta'):
                check_reference(self.document, self.reference, Path(tmp))
        report = compare(self.document, self.reference, BUNDLE/'fixtures/08.pdf')
        self.assertEqual(report['image_count'], 21)
        self.assertFalse(report['runtime_acceptance'])

    def test_collateral_graph_and_image_mutations_fail_closed(self):
        for kind in ('text', 'caption', 'geometry', 'page_pixel', 'picture_pixel', 'dpi', 'missing_image'):
            with self.subTest(kind=kind):
                d = copy.deepcopy(self.document)
                if kind == 'text': d['texts'][0]['text'] += 'changed'
                elif kind == 'caption': d['pictures'][0]['captions'] = []
                elif kind == 'geometry': d['pictures'][0]['prov'][0]['bbox']['l'] += 1
                elif kind == 'dpi': d['pages']['1']['image']['dpi'] = 144
                elif kind == 'missing_image': del d['pages']['1']['image']
                else:
                    image = d['pages']['1']['image'] if kind == 'page_pixel' else d['pictures'][0]['image']
                    pixels = Image.open(io.BytesIO(base64.b64decode(image['uri'].split(',', 1)[1])))
                    pixels.putpixel((0, 0), (0, 0, 0) if pixels.getpixel((0, 0)) != (0, 0, 0) else (255, 255, 255))
                    encoded = io.BytesIO(); pixels.save(encoded, format='PNG')
                    image['uri'] = 'data:image/png;base64,'+base64.b64encode(encoded.getvalue()).decode()
                with self.assertRaises((ValueError, KeyError)):
                    compare(d, self.reference, BUNDLE/'fixtures/08.pdf')


if __name__ == '__main__':
    unittest.main()
