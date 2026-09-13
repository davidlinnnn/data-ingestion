"""Acceptance seam: a request sent to a fresh parser process yields exact results."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / 'docs/prototypes/pdf-checkpoint-prototype'

class Restoration(unittest.TestCase):
    def test_scanned_request_restores_exactly_without_page_inference(self):
        with tempfile.TemporaryDirectory(prefix='t01-') as tmp:
            base = Path(tmp)
            request = {'pdf': str(FIXED/'fixtures/scan-pages-3-5.pdf'),
                       'model_cache': str(FIXED/'PROTOTYPE-wipe-me/hf'), 'scan': True}
            for mode in ('baseline', 'capture', 'restore'):
                payload = {**request, 'mode': mode, 'out': str(base/mode)}
                if mode == 'capture': payload['checkpoint_only'] = True
                if mode == 'restore': payload['checkpoint'] = str(base/'capture')
                result = subprocess.run([sys.executable, '-m', 'pdf_processing.parse'],
                    input=json.dumps(payload), text=True, capture_output=True,
                    env={**os.environ, 'PYTHONPATH': str(ROOT/'src'), 'HF_HUB_OFFLINE': '1'})
                self.assertEqual(result.returncode, 0, result.stderr[-4000:])
            self.assertEqual(json.loads((base/'baseline/document.json').read_text()),
                             json.loads((base/'restore/document.json').read_text()))
            metrics = json.loads((base/'restore/metrics.json').read_text())
            self.assertFalse(any(n for k,n in metrics['page_stage_inputs'].items()
                                 if k.endswith('Model')))
            self.assertNotEqual(metrics['pid'], json.loads((base/'capture/metrics.json').read_text())['pid'])

if __name__ == '__main__': unittest.main()
